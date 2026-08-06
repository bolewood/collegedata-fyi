#!/usr/bin/env python3
"""Measure source-format sniff risk and verify a 100-PDF byte/year sample.

Read-only. The corpus probe fetches only the first 4 KiB of every current
source object. ZIP sources and the deterministic 100-PDF sample are fetched in
full, bounded by the archive pipeline's 50 MiB object limit. No source bytes
are written to disk or included in the report.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Mapping, Sequence


REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "tools" / "data_quality"))
sys.path.insert(0, str(REPO_ROOT / "tools" / "extraction_worker"))

from run_data_integrity_audit import (  # noqa: E402
    ReadOnlyPostgrest,
    load_env,
    sha256_json,
    utc_now,
)
from worker import detect_year_from_bytes, sniff_zip_inner_format  # noqa: E402


HEAD_BYTES = 4096
MAX_SOURCE_BYTES = 50 * 1024 * 1024
B1_SAMPLE_SIZE = 100
B1_SAMPLE_SALT = "audit-2026-08-06-b1"


def strip_leading_html_noise(head: str) -> str:
    head = head.lstrip("\ufeff").lstrip()
    while head.startswith("<!--"):
        end = head.find("-->")
        if end < 0:
            return head
        head = head[end + 3 :].lstrip()
    return head


def looks_like_html(data: bytes, limit: int) -> bool:
    head = strip_leading_html_noise(data[:limit].decode("utf-8", errors="ignore").lower())
    return (
        head.startswith("<!doctype html")
        or head.startswith("<html")
        or head.startswith("<head")
        or (head.startswith("<?xml") and "<html" in head)
    )


def object_url(base_url: str, storage_path: str) -> str:
    return (
        base_url.rstrip("/")
        + "/storage/v1/object/public/sources/"
        + urllib.parse.quote(storage_path, safe="/")
    )


def fetch_head(base_url: str, row: Mapping[str, Any]) -> dict[str, Any]:
    url = object_url(base_url, str(row["storage_path"]))
    requested_end = HEAD_BYTES - 1
    for attempt in range(5):
        request = urllib.request.Request(url, headers={"Range": f"bytes=0-{requested_end}"})
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                data = response.read(HEAD_BYTES + 1)
                if response.status != 206 or len(data) > HEAD_BYTES:
                    raise RuntimeError("storage server did not honor bounded Range request")
                return {
                    "document_id": row["document_id"],
                    "artifact_id": row["id"],
                    "data": data,
                    "content_range": response.headers.get("Content-Range"),
                }
        except (urllib.error.URLError, TimeoutError, RuntimeError) as exc:
            if isinstance(exc, urllib.error.HTTPError) and exc.code == 400 and requested_end > 0:
                # Supabase Storage rejects a range whose end exceeds a very
                # small object's length. Probe one byte to learn the total,
                # then retry with an exact bounded end.
                try:
                    one_byte = urllib.request.Request(url, headers={"Range": "bytes=0-0"})
                    with urllib.request.urlopen(one_byte, timeout=30) as response:
                        content_range = response.headers.get("Content-Range") or ""
                        match = __import__("re").search(r"/(\d+)$", content_range)
                        if match:
                            requested_end = min(HEAD_BYTES, int(match.group(1))) - 1
                            continue
                except (urllib.error.URLError, TimeoutError):
                    pass
            if attempt == 4:
                return {
                    "document_id": row["document_id"],
                    "artifact_id": row["id"],
                    "error_type": type(exc).__name__,
                    "http_status": exc.code if isinstance(exc, urllib.error.HTTPError) else None,
                }
            retry_after = (
                exc.headers.get("Retry-After")
                if isinstance(exc, urllib.error.HTTPError) and exc.headers
                else None
            )
            delay = float(retry_after) if retry_after and retry_after.isdigit() else min(20, 2 ** (attempt + 1))
            time.sleep(delay)
    raise AssertionError("unreachable")


def fetch_full(base_url: str, row: Mapping[str, Any]) -> bytes:
    url = object_url(base_url, str(row["storage_path"]))
    for attempt in range(3):
        request = urllib.request.Request(url)
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                chunks: list[bytes] = []
                size = 0
                while True:
                    chunk = response.read(1024 * 1024)
                    if not chunk:
                        break
                    size += len(chunk)
                    if size > MAX_SOURCE_BYTES:
                        raise RuntimeError("source object exceeded the 50 MiB archive cap")
                    chunks.append(chunk)
            return b"".join(chunks)
        except (urllib.error.URLError, TimeoutError) as exc:
            if attempt == 2:
                raise
            time.sleep(2**attempt)
    raise AssertionError("unreachable")


def latest_sources(rows: Sequence[Mapping[str, Any]]) -> dict[str, Mapping[str, Any]]:
    latest: dict[str, Mapping[str, Any]] = {}
    for row in sorted(
        rows,
        key=lambda item: (str(item.get("created_at") or ""), str(item.get("id") or "")),
        reverse=True,
    ):
        document_id = str(row.get("document_id") or "")
        if document_id and document_id not in latest:
            latest[document_id] = row
    return latest


def deterministic_pdf_sample(
    sources: Mapping[str, Mapping[str, Any]],
    head_results: Mapping[str, Mapping[str, Any]],
) -> list[Mapping[str, Any]]:
    candidates = [
        source
        for document_id, source in sources.items()
        if isinstance(head_results.get(document_id, {}).get("data"), bytes)
        and head_results[document_id]["data"].find(b"%PDF") >= 0
        and source.get("sha256")
    ]
    candidates.sort(
        key=lambda row: hashlib.sha256(
            f"{B1_SAMPLE_SALT}\0{row['document_id']}".encode("utf-8")
        ).hexdigest()
    )
    if len(candidates) < B1_SAMPLE_SIZE:
        raise RuntimeError(f"only {len(candidates)} current PDF sources are sample-eligible")
    return candidates[:B1_SAMPLE_SIZE]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--env", type=Path, default=REPO_ROOT / ".env")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--workers", type=int, default=12)
    args = parser.parse_args()

    env = load_env(args.env)
    base_url = env.get("SUPABASE_URL")
    api_key = env.get("SUPABASE_SERVICE_ROLE_KEY")
    if not base_url or not api_key:
        print("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY are required", file=sys.stderr)
        return 2

    run_started_at = utc_now()
    client = ReadOnlyPostgrest(base_url, api_key)
    documents, document_pagination = client.paginate(
        "cds_documents.source_probe",
        "cds_documents",
        {
            "select": (
                "id,school_id,school_name,cds_year,detected_year,source_url,source_format,"
                "source_sha256"
            ),
            "order": "id.asc",
        },
        unique_key=lambda row: row["id"],
    )
    source_rows, source_pagination = client.paginate(
        "cds_artifacts.current_source_candidates",
        "cds_artifacts",
        {
            "select": "id,document_id,storage_path,sha256,created_at",
            "kind": "eq.source",
            "order": "id.asc",
        },
        unique_key=lambda row: row["id"],
    )
    docs_by_id = {str(row["id"]): row for row in documents}
    sources = latest_sources(source_rows)

    head_results: list[dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = {
            executor.submit(fetch_head, base_url, row): document_id
            for document_id, row in sources.items()
        }
        for index, future in enumerate(as_completed(futures), start=1):
            head_results.append(future.result())
            if index % 250 == 0:
                print(f"head probes {index}/{len(futures)}", file=sys.stderr, flush=True)

    head_by_doc = {str(row["document_id"]): row for row in head_results}
    failures = [row for row in head_results if row.get("error_type")]
    leading_junk_pdf: list[dict[str, Any]] = []
    html_after_512: list[dict[str, Any]] = []
    observed_head: Counter[str] = Counter()
    zip_sources: list[Mapping[str, Any]] = []
    for document_id, source in sources.items():
        result = head_by_doc.get(document_id, {})
        data = result.get("data")
        if not isinstance(data, bytes):
            continue
        pdf_offset = data.find(b"%PDF")
        if pdf_offset == 0:
            observed_head["pdf"] += 1
        elif pdf_offset > 0:
            observed_head["pdf_with_leading_junk"] += 1
            leading_junk_pdf.append(
                {"document_id": document_id, "school_id": docs_by_id.get(document_id, {}).get("school_id"), "pdf_offset": pdf_offset}
            )
        elif data.startswith(b"PK\x03\x04"):
            observed_head["zip"] += 1
            zip_sources.append(source)
        elif looks_like_html(data, 512):
            observed_head["html_within_512"] += 1
        elif looks_like_html(data, HEAD_BYTES):
            observed_head["html_after_512_within_4096"] += 1
            html_after_512.append(
                {"document_id": document_id, "school_id": docs_by_id.get(document_id, {}).get("school_id")}
            )
        else:
            observed_head["other"] += 1

    zip_results: list[dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=min(args.workers, 8)) as executor:
        futures = {executor.submit(fetch_full, base_url, row): row for row in zip_sources}
        for index, future in enumerate(as_completed(futures), start=1):
            row = futures[future]
            document_id = str(row["document_id"])
            try:
                data = future.result()
                detected = sniff_zip_inner_format(data)
                actual_sha = hashlib.sha256(data).hexdigest()
                zip_results.append(
                    {
                        "document_id": document_id,
                        "detected": detected,
                        "declared": docs_by_id.get(document_id, {}).get("source_format"),
                        "sha_matches_artifact": actual_sha == row.get("sha256"),
                    }
                )
            except Exception as exc:  # error type only; never persist a URL/body
                zip_results.append(
                    {
                        "document_id": document_id,
                        "error_type": type(exc).__name__,
                        "http_status": exc.code if isinstance(exc, urllib.error.HTTPError) else None,
                    }
                )
            if index % 100 == 0:
                print(f"ZIP probes {index}/{len(futures)}", file=sys.stderr, flush=True)

    sample = deterministic_pdf_sample(sources, head_by_doc)
    b1_rows: list[dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=min(args.workers, 8)) as executor:
        futures = {executor.submit(fetch_full, base_url, row): row for row in sample}
        for future in as_completed(futures):
            row = futures[future]
            document_id = str(row["document_id"])
            doc = docs_by_id[document_id]
            try:
                data = future.result()
                actual_sha = hashlib.sha256(data).hexdigest()
                embedded_year = detect_year_from_bytes(data)
                b1_rows.append(
                    {
                        "document_id": document_id,
                        "school_id": doc.get("school_id"),
                        "cds_year": doc.get("cds_year"),
                        "detected_year": doc.get("detected_year"),
                        "byte_detected_year": embedded_year,
                        "artifact_sha_matches_bytes": actual_sha == row.get("sha256"),
                        "document_sha_matches_bytes": actual_sha == doc.get("source_sha256"),
                    }
                )
            except Exception as exc:
                b1_rows.append(
                    {
                        "document_id": document_id,
                        "school_id": doc.get("school_id"),
                        "error_type": type(exc).__name__,
                        "http_status": exc.code if isinstance(exc, urllib.error.HTTPError) else None,
                    }
                )
    b1_rows.sort(key=lambda row: str(row["document_id"]))
    completed_sample = [row for row in b1_rows if not row.get("error_type")]

    report = {
        "label": "Source corpus format sniff and deterministic 100-PDF byte/year probe",
        "run_started_at": run_started_at,
        "run_finished_at": utc_now(),
        "method": {
            "current_source_selection": "Newest kind=source artifact per document by created_at then id",
            "head_probe": f"HTTP Range bytes=0-{HEAD_BYTES - 1}; fail if the storage server does not return 206",
            "zip_probe": "Full current ZIP sources, capped at 50 MiB, using worker.sniff_zip_inner_format",
            "b1_sample": (
                "100 current sources whose 4 KiB head probe contains %PDF, with smallest "
                f"SHA-256({B1_SAMPLE_SALT}\\0document_id)"
            ),
            "bytes_persisted": False,
        },
        "pagination": {
            "cds_documents": document_pagination,
            "source_artifacts": source_pagination,
        },
        "format_sniff": {
            "current_source_documents": len(sources),
            "head_probe_successes": len(head_results) - len(failures),
            "head_probe_failures": len(failures),
            "head_probe_failure_types": dict(sorted(Counter(row["error_type"] for row in failures).items())),
            "head_probe_failure_rows": [
                {
                    "document_id": row["document_id"],
                    "school_id": docs_by_id.get(str(row["document_id"]), {}).get("school_id"),
                    "error_type": row["error_type"],
                    "http_status": row.get("http_status"),
                }
                for row in sorted(failures, key=lambda item: str(item["document_id"]))
            ],
            "observed_head": dict(sorted(observed_head.items())),
            "leading_junk_pdf": {
                "numerator": len(leading_junk_pdf),
                "denominator": len(head_results) - len(failures),
                "rows": leading_junk_pdf,
            },
            "html_marker_after_512_within_4096": {
                "numerator": len(html_after_512),
                "denominator": len(head_results) - len(failures),
                "rows": html_after_512,
            },
            "zip": {
                "denominator": len(zip_results),
                "detected": dict(sorted(Counter(row.get("detected", "probe_error") for row in zip_results).items())),
                "declared_mismatches": [
                    row
                    for row in zip_results
                    if row.get("detected") and row.get("detected") != row.get("declared")
                ],
                "sha_mismatches": sum(row.get("sha_matches_artifact") is False for row in zip_results),
                "probe_errors": sum(bool(row.get("error_type")) for row in zip_results),
            },
            "interpretation": (
                "These measurements quantify current-corpus exposure to the 100-character PDF and "
                "512-byte HTML routing heuristics. They do not claim that extra OCR cost is silent data loss."
            ),
        },
        "b1_source_byte_sample": {
            "sample_salt": B1_SAMPLE_SALT,
            "requested": B1_SAMPLE_SIZE,
            "completed": len(completed_sample),
            "errors": len(b1_rows) - len(completed_sample),
            "artifact_sha_mismatches": sum(row.get("artifact_sha_matches_bytes") is False for row in completed_sample),
            "document_sha_mismatches": sum(row.get("document_sha_matches_bytes") is False for row in completed_sample),
            "byte_year_vs_detected_year_mismatches": sum(
                bool(row.get("byte_detected_year"))
                and bool(row.get("detected_year"))
                and row.get("byte_detected_year") != row.get("detected_year")
                for row in completed_sample
            ),
            "byte_year_undetected": sum(not row.get("byte_detected_year") for row in completed_sample),
            "rows": b1_rows,
            "cohort_sha256": sha256_json(
                sorted(str(row["document_id"]) for row in sample)
            ),
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(
        json.dumps(
            {
                "output": str(args.output),
                "current_source_documents": len(sources),
                "head_probe_failures": len(failures),
                "zip_sources": len(zip_results),
                "b1_completed": len(completed_sample),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
