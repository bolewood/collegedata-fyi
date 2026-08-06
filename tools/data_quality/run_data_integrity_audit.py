#!/usr/bin/env python3
"""Run the read-only, database-backed portions of the 2026-08-06 audit.

The runner deliberately uses raw PostgREST range requests instead of the
Supabase client.  Every collection has a stable order, an exact first-page
count, captured Content-Range headers, duplicate-key checks, and a final
fetched-row assertion.  It never sends a mutating HTTP method or calls an RPC.

Usage:
    python tools/data_quality/run_data_integrity_audit.py \
      --output scratch/data-integrity-audit/live-readonly.json \
      --pagination-output scratch/data-integrity-audit/pagination.json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping, Sequence


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PAGE_SIZE = 1000
IPEDS_PAGE_SIZE = 500
FINANCE_FIELDS = (
    "endowment_value_begin",
    "endowment_value_end",
    "endowment_new_gifts",
    "endowment_investment_return",
    "endowment_spending_distribution",
    "endowment_other_change",
)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def load_env(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if path.exists():
        for raw in path.read_text().splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            values[key.strip()] = value.strip().strip('"').strip("'")
    values.update(os.environ)
    return values


def sha256_json(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def git_value(*args: str) -> str:
    return subprocess.check_output(
        ["git", *args], cwd=REPO_ROOT, text=True, stderr=subprocess.DEVNULL
    ).strip()


@dataclass(frozen=True)
class ContentRange:
    start: int | None
    end: int | None
    total: int | None


def parse_content_range(value: str | None) -> ContentRange:
    if not value:
        raise RuntimeError("PostgREST response omitted Content-Range")
    match = re.fullmatch(r"(?:(\d+)-(\d+)|\*)/(\d+|\*)", value.strip())
    if not match:
        raise RuntimeError(f"invalid Content-Range shape: {value!r}")
    start = int(match.group(1)) if match.group(1) is not None else None
    end = int(match.group(2)) if match.group(2) is not None else None
    total = int(match.group(3)) if match.group(3) != "*" else None
    return ContentRange(start, end, total)


class ReadOnlyPostgrest:
    def __init__(self, base_url: str, api_key: str) -> None:
        self.base_url = base_url.rstrip("/") + "/rest/v1"
        self.api_key = api_key

    def _get(
        self,
        table: str,
        params: Mapping[str, str],
        *,
        start: int,
        end: int,
        exact_count: bool,
        timeout: int = 60,
    ) -> tuple[list[dict[str, Any]], str, int]:
        query = urllib.parse.urlencode(params, safe="(),.*->:")
        url = f"{self.base_url}/{urllib.parse.quote(table, safe='')}?{query}"
        headers = {
            "apikey": self.api_key,
            "Authorization": f"Bearer {self.api_key}",
            "Range-Unit": "items",
            "Range": f"{start}-{end}",
        }
        if exact_count:
            headers["Prefer"] = "count=exact"
        request = urllib.request.Request(url, headers=headers, method="GET")
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                payload = json.load(response)
                if not isinstance(payload, list):
                    raise RuntimeError(f"{table}: expected a JSON list")
                return payload, response.headers.get("Content-Range", ""), response.status
        except urllib.error.HTTPError as exc:
            # Do not persist a response body: operational errors can contain URLs.
            raise RuntimeError(f"{table}: PostgREST HTTP {exc.code}") from None

    def page_once(
        self,
        table: str,
        params: Mapping[str, str],
        *,
        start: int = 0,
        end: int = 999,
    ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        rows, raw_range, status = self._get(
            table, params, start=start, end=end, exact_count=True
        )
        parsed = parse_content_range(raw_range)
        return rows, {
            "http_status": status,
            "content_range": raw_range,
            "returned_rows": len(rows),
            "expected_total": parsed.total,
        }

    def exact_count(self, table: str, params: Mapping[str, str] | None = None) -> dict[str, Any]:
        query = {"select": "*", **(params or {})}
        rows, raw_range, status = self._get(
            table, query, start=0, end=0, exact_count=True
        )
        parsed = parse_content_range(raw_range)
        if parsed.total is None:
            raise RuntimeError(f"{table}: exact count did not return a total")
        return {
            "count": parsed.total,
            "captured_at": utc_now(),
            "content_range": raw_range,
            "http_status": status,
            "probe_rows": len(rows),
        }

    def paginate(
        self,
        identifier: str,
        table: str,
        params: Mapping[str, str],
        *,
        unique_key: Callable[[Mapping[str, Any]], Any],
        page_size: int = DEFAULT_PAGE_SIZE,
        timeout: int = 60,
    ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        if "order" not in params:
            raise ValueError(f"{identifier}: a stable PostgREST order is required")
        captured_at = utc_now()
        rows: list[dict[str, Any]] = []
        seen: set[Any] = set()
        ranges: list[str] = []
        result_hasher = hashlib.sha256()
        expected_total: int | None = None
        offset = 0
        page = 0

        while expected_total is None or offset < expected_total:
            batch, raw_range, _status = self._get(
                table,
                params,
                start=offset,
                end=offset + page_size - 1,
                exact_count=(page == 0),
                timeout=timeout,
            )
            parsed = parse_content_range(raw_range)
            ranges.append(raw_range)
            if page == 0:
                if parsed.total is None:
                    raise RuntimeError(f"{identifier}: first page lacked an exact total")
                expected_total = parsed.total
                if expected_total == 0 and not batch:
                    page += 1
                    break
            if not batch:
                raise RuntimeError(
                    f"{identifier}: empty page at offset {offset} before {expected_total} rows"
                )
            if parsed.start != offset or parsed.end != offset + len(batch) - 1:
                raise RuntimeError(
                    f"{identifier}: Content-Range gap/cap at offset {offset}: {raw_range}"
                )
            if len(batch) > page_size:
                raise RuntimeError(f"{identifier}: server returned an oversized page")
            if len(batch) < page_size and offset + len(batch) != expected_total:
                raise RuntimeError(
                    f"{identifier}: short page before expected total ({raw_range})"
                )
            for row in batch:
                key = unique_key(row)
                if key in seen:
                    raise RuntimeError(f"{identifier}: duplicate key encountered: {key!r}")
                seen.add(key)
                encoded = json.dumps(
                    row, sort_keys=True, separators=(",", ":"), ensure_ascii=False
                ).encode("utf-8")
                result_hasher.update(encoded)
                result_hasher.update(b"\n")
            rows.extend(batch)
            offset += len(batch)
            page += 1

        if expected_total is None or len(rows) != expected_total:
            raise RuntimeError(
                f"{identifier}: fetched {len(rows)} rows, expected {expected_total}"
            )
        query_contract = {
            "table": table,
            "params": dict(params),
            "page_size": page_size,
        }
        return rows, {
            "identifier": identifier,
            "captured_at": captured_at,
            "query_sha256": sha256_json(query_contract),
            "result_sha256": result_hasher.hexdigest(),
            "expected_rows": expected_total,
            "fetched_rows": len(rows),
            "page_size": page_size,
            "page_count": page,
            "content_ranges": ranges,
            "assertions": {
                "stable_order_declared": True,
                "no_gaps_or_caps": True,
                "unique_keys": True,
                "fetched_equals_expected": True,
            },
        }

    def fetch_id_chunks(
        self,
        identifier: str,
        table: str,
        ids: Sequence[str],
        params: Mapping[str, str],
        *,
        unique_key: Callable[[Mapping[str, Any]], Any],
        chunk_size: int = 25,
        timeout: int = 60,
    ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        """Fetch an exact declared primary-key cohort without an offset scan.

        This is used for large JSON payloads after a lightweight view has
        already selected the corpus. Each bounded ID query still captures an
        exact Content-Range and asserts that every requested row arrived.
        """
        requested = sorted(set(ids))
        captured_at = utc_now()
        rows: list[dict[str, Any]] = []
        seen: set[Any] = set()
        ranges: list[str] = []
        result_hasher = hashlib.sha256()
        for start in range(0, len(requested), chunk_size):
            chunk = requested[start : start + chunk_size]
            chunk_params = {
                **params,
                "id": f"in.({','.join(chunk)})",
                "order": "id.asc",
            }
            batch, raw_range, _status = self._get(
                table,
                chunk_params,
                start=0,
                end=len(chunk) - 1,
                exact_count=True,
                timeout=timeout,
            )
            parsed = parse_content_range(raw_range)
            ranges.append(raw_range)
            if parsed.total != len(chunk) or len(batch) != len(chunk):
                raise RuntimeError(
                    f"{identifier}: requested {len(chunk)} IDs but got "
                    f"{len(batch)} rows ({raw_range})"
                )
            for row in batch:
                key = unique_key(row)
                if key in seen:
                    raise RuntimeError(f"{identifier}: duplicate key encountered: {key!r}")
                seen.add(key)
                encoded = json.dumps(
                    row, sort_keys=True, separators=(",", ":"), ensure_ascii=False
                ).encode("utf-8")
                result_hasher.update(encoded)
                result_hasher.update(b"\n")
            rows.extend(batch)
        if len(rows) != len(requested):
            raise RuntimeError(
                f"{identifier}: fetched {len(rows)} rows, expected {len(requested)}"
            )
        query_contract = {
            "table": table,
            "params": dict(params),
            "selection": "exact IDs from cds_selected_extraction_result",
            "chunk_size": chunk_size,
            "requested_ids_sha256": sha256_json(requested),
        }
        return rows, {
            "identifier": identifier,
            "captured_at": captured_at,
            "query_sha256": sha256_json(query_contract),
            "result_sha256": result_hasher.hexdigest(),
            "expected_rows": len(requested),
            "fetched_rows": len(rows),
            "page_size": chunk_size,
            "page_count": len(ranges),
            "content_ranges": ranges,
            "selection": "exact selected artifact IDs; no obsolete-artifact offset scan",
            "assertions": {
                "all_requested_ids_returned": True,
                "unique_keys": True,
                "fetched_equals_expected": True,
            },
        }


def parse_year_start(value: Any) -> int | None:
    match = re.fullmatch(r"((?:19|20)\d{2})-\d{2}", str(value or ""))
    return int(match.group(1)) if match else None


def section_bucket(field_id: Any) -> str:
    match = re.match(r"^([A-Z])\.", str(field_id or ""))
    return match.group(1) if match else "?"


def decimal_value(value: Any) -> Decimal | None:
    if value in (None, ""):
        return None
    try:
        return Decimal(str(value))
    except InvalidOperation:
        return None


def parse_timestamp(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None


def percentile(values: Iterable[int | float], fraction: float) -> float | None:
    ordered = sorted(float(value) for value in values)
    if not ordered:
        return None
    if len(ordered) == 1:
        return ordered[0]
    position = fraction * (len(ordered) - 1)
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)


def summarize_counter(counter: Counter[Any]) -> dict[str, int]:
    return {str(key): counter[key] for key in sorted(counter, key=lambda item: str(item))}


def document_summary(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    mismatch = [
        row
        for row in rows
        if row.get("cds_year") is not None
        and row.get("detected_year") is not None
        and row.get("cds_year") != row.get("detected_year")
    ]
    return {
        "rows": len(rows),
        "non_null_cds_year_detected_year_mismatches": len(mismatch),
        "mismatch_rate": len(mismatch) / len(rows) if rows else None,
        "interpretation": (
            "detected_year is intentionally authoritative; a mismatch is an identity-audit "
            "candidate, not automatically a defect"
        ),
        "source_format": summarize_counter(Counter(row.get("source_format") for row in rows)),
        "data_quality_flag": summarize_counter(
            Counter(row.get("data_quality_flag") for row in rows)
        ),
        "detected_year": summarize_counter(Counter(row.get("detected_year") for row in rows)),
    }


def archive_summary(
    rows: Sequence[Mapping[str, Any]], first_page_rows: Sequence[Mapping[str, Any]]
) -> dict[str, Any]:
    no_pdfs = [row for row in rows if row.get("last_outcome") == "no_pdfs_found"]
    done = [row for row in rows if row.get("status") == "done"]
    done_null = [row for row in done if row.get("last_outcome") is None]
    return {
        "rows": len(rows),
        "status": summarize_counter(Counter(row.get("status") for row in rows)),
        "last_outcome": summarize_counter(Counter(row.get("last_outcome") for row in rows)),
        "no_pdfs_found": {
            "rows": len(no_pdfs),
            "distinct_schools": len({row.get("school_id") for row in no_pdfs}),
        },
        "completed_rows_with_null_outcome": {
            "numerator": len(done_null),
            "denominator": len(done),
            "rate": len(done_null) / len(done) if done else None,
        },
        "unpaged_first_1000_diagnostic": {
            "rows": len(first_page_rows),
            "no_pdfs_found": sum(
                row.get("last_outcome") == "no_pdfs_found" for row in first_page_rows
            ),
            "warning": "Diagnostic only: unordered first-page results are not a corpus estimate.",
        },
    }


def attempt_summary(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    completed_durations = [
        int(row["duration_ms"])
        for row in rows
        if row.get("duration_ms") is not None and row.get("terminal_state") is not None
    ]
    timeouts = [row for row in rows if row.get("terminal_state") == "timed_out"]
    finished = [row for row in rows if row.get("terminal_state") is not None]
    return {
        "cohort_definition": (
            "All archive_queue_attempts rows; the table was introduced by migration "
            "20260716010500, so the table itself defines the post-ledger cohort."
        ),
        "attempts": len(rows),
        "finished_attempts": len(finished),
        "open_attempts": len(rows) - len(finished),
        "terminal_state": summarize_counter(Counter(row.get("terminal_state") for row in rows)),
        "duration_ms": {
            "denominator": len(completed_durations),
            "p50": percentile(completed_durations, 0.50),
            "p95": percentile(completed_durations, 0.95),
            "max": max(completed_durations) if completed_durations else None,
        },
        "timeout_rate": {
            "numerator": len(timeouts),
            "denominator": len(finished),
            "rate": len(timeouts) / len(finished) if finished else None,
        },
    }


def field_summary(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    questions: dict[str, Counter[str]] = defaultdict(Counter)
    question_docs: dict[str, set[str]] = defaultdict(set)
    sections: dict[str, Counter[str]] = defaultdict(Counter)
    section_docs: dict[str, set[str]] = defaultdict(set)
    doc_updated_at: dict[str, datetime] = {}
    for row in rows:
        field_id = str(row.get("field_id") or "")
        section = section_bucket(field_id)
        status = str(row.get("value_status") or "unknown")
        document_id = str(row.get("document_id") or "")
        questions[field_id][status] += 1
        question_docs[field_id].add(document_id)
        sections[section][status] += 1
        section_docs[section].add(document_id)
        updated = parse_timestamp(row.get("updated_at"))
        if updated and (document_id not in doc_updated_at or updated > doc_updated_at[document_id]):
            doc_updated_at[document_id] = updated
    return {
        "rows": len(rows),
        "authorization": (
            "service_role read succeeded; exact count and every 1,000-row range completed. "
            "The prior RLS diagnosis was not reproduced."
        ),
        "schema_version": summarize_counter(Counter(row.get("schema_version") for row in rows)),
        "producer": summarize_counter(Counter(row.get("producer") for row in rows)),
        "source_format": summarize_counter(Counter(row.get("source_format") for row in rows)),
        "sections": {
            key: {
                "documents": len(section_docs[key]),
                "values": sum(sections[key].values()),
                "value_status": summarize_counter(sections[key]),
            }
            for key in sorted(sections)
        },
        "questions": {
            key: {
                "documents": len(question_docs[key]),
                "values": sum(questions[key].values()),
                "value_status": summarize_counter(questions[key]),
            }
            for key in sorted(questions)
        },
        "document_max_updated_at": {
            key: value.isoformat().replace("+00:00", "Z")
            for key, value in doc_updated_at.items()
        },
    }


def artifact_summary(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    source_parts_by_document: Counter[str] = Counter(
        str(row.get("document_id")) for row in rows if row.get("kind") == "source_part"
    )
    undersized_part_sets = {
        document_id: count
        for document_id, count in source_parts_by_document.items()
        if count < 2
    }
    return {
        "rows": len(rows),
        "kind": summarize_counter(Counter(row.get("kind") for row in rows)),
        "producer": summarize_counter(Counter(row.get("producer") for row in rows)),
        "producer_version": summarize_counter(
            Counter((row.get("producer"), row.get("producer_version")) for row in rows)
        ),
        "section_packages": {
            "documents_with_preserved_source_parts": len(source_parts_by_document),
            "source_part_artifacts": sum(source_parts_by_document.values()),
            "documents_with_fewer_than_two_parts": undersized_part_sets,
            "limitation": (
                "Preserved source_part rows can check that persisted packages have at least "
                "two inputs. They cannot reveal resolver candidates that were never selected "
                "or persisted, and package notes were intentionally not projected because "
                "that JSON-path query repeatedly exceeded the API statement timeout."
            ),
        },
    }


def tier4_summary(
    rows: Sequence[Mapping[str, Any]],
    selected_rows: Sequence[Mapping[str, Any]],
    documents: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    by_id = {str(row.get("id")): row for row in rows}
    selected_tier4 = [row for row in selected_rows if row.get("base_producer") == "tier4_docling"]
    field_counts: list[int] = []
    merged_counts: list[int] = []
    fallback_deltas: list[int] = []
    stratified: dict[tuple[str, str, str, str, str], list[int]] = defaultdict(list)
    section_docs: dict[str, int] = Counter()
    section_values: dict[str, int] = Counter()
    visual_ocr_docs = 0
    missing_artifact_rows = 0
    for selected in selected_tier4:
        base = by_id.get(str(selected.get("base_artifact_id")))
        if not base:
            missing_artifact_rows += 1
            continue
        base_values = base.get("values") if isinstance(base.get("values"), dict) else {}
        merged = dict(base_values)
        fallback_id = selected.get("fallback_artifact_id")
        fallback = by_id.get(str(fallback_id)) if fallback_id else None
        if fallback and isinstance(fallback.get("values"), dict):
            for key, value in fallback["values"].items():
                merged.setdefault(key, value)
        base_count = len(base_values)
        merged_count = len(merged)
        field_counts.append(base_count)
        merged_counts.append(merged_count)
        fallback_deltas.append(merged_count - base_count)
        doc = documents.get(str(selected.get("document_id")), {})
        canonical_year = str(doc.get("detected_year") or doc.get("cds_year") or "unknown")
        disagreement = str(
            bool(doc.get("detected_year") and doc.get("cds_year") != doc.get("detected_year"))
        ).lower()
        key = (
            canonical_year,
            str(doc.get("source_format") or "unknown"),
            str(base.get("producer_version") or "unknown"),
            str(base.get("schema_version") or "unknown"),
            disagreement,
        )
        stratified[key].append(merged_count)
        sections_present = {section_bucket(field_id) for field_id in merged}
        for section in sections_present:
            section_docs[section] += 1
        for field_id in merged:
            section_values[section_bucket(field_id)] += 1
        stats = base.get("stats") if isinstance(base.get("stats"), dict) else {}
        if isinstance(stats.get("visual_ocr_pages"), list) and stats.get("visual_ocr_pages"):
            visual_ocr_docs += 1
    return {
        "selected_tier4_documents": len(selected_tier4),
        "selected_rows_missing_from_tier4_payload_query": missing_artifact_rows,
        "cleaner_field_count": {
            "p50": percentile(field_counts, 0.50),
            "p95": percentile(field_counts, 0.95),
            "min": min(field_counts) if field_counts else None,
            "max": max(field_counts) if field_counts else None,
        },
        "merged_field_count": {
            "p50": percentile(merged_counts, 0.50),
            "p95": percentile(merged_counts, 0.95),
            "min": min(merged_counts) if merged_counts else None,
            "max": max(merged_counts) if merged_counts else None,
        },
        "fallback": {
            "documents_with_selected_fallback": sum(
                bool(row.get("fallback_artifact_id")) for row in selected_tier4
            ),
            "documents_with_positive_delta": sum(delta > 0 for delta in fallback_deltas),
            "fields_added": sum(fallback_deltas),
            "delta_p50": percentile(fallback_deltas, 0.50),
            "delta_p95": percentile(fallback_deltas, 0.95),
        },
        "section_distribution": {
            key: {"documents": section_docs[key], "values": section_values[key]}
            for key in sorted(section_docs)
        },
        "visual_ocr": {
            "documents_with_visual_ocr_pages": visual_ocr_docs,
            "denominator": len(field_counts),
            "limitation": (
                "Visual-OCR use and section value distribution are measured, but no "
                "section-specific human ground truth exists; this does not estimate recall."
            ),
        },
        "stratification": [
            {
                "canonical_year": key[0],
                "source_format": key[1],
                "producer_version": key[2],
                "schema_version": key[3],
                "year_disagreement": key[4],
                "documents": len(values),
                "merged_field_count_p50": percentile(values, 0.50),
                "merged_field_count_p95": percentile(values, 0.95),
            }
            for key, values in sorted(stratified.items())
        ],
    }


def projection_summary(
    documents: Sequence[Mapping[str, Any]],
    selected_rows: Sequence[Mapping[str, Any]],
    browser_rows: Sequence[Mapping[str, Any]],
    field_rows: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    docs = {str(row.get("id")): row for row in documents}
    selected = {str(row.get("document_id")): row for row in selected_rows}
    browser = {str(row.get("document_id")): row for row in browser_rows}
    field_doc_ids = {str(row.get("document_id")) for row in field_rows}
    field_updated: dict[str, datetime] = {}
    for row in field_rows:
        doc_id = str(row.get("document_id"))
        updated = parse_timestamp(row.get("updated_at"))
        if updated and (doc_id not in field_updated or updated > field_updated[doc_id]):
            field_updated[doc_id] = updated

    eligible = {
        doc_id
        for doc_id, doc in docs.items()
        if doc.get("extraction_status") == "extracted"
        and (parse_year_start(doc.get("detected_year") or doc.get("cds_year")) or 0) >= 2024
        and doc_id in selected
    }
    wrong_file = {doc_id for doc_id in eligible if docs[doc_id].get("data_quality_flag") == "wrong_file"}
    browser_expected = eligible - wrong_file
    browser_missing = sorted(browser_expected - set(browser))
    browser_unexpected = sorted(set(browser) - browser_expected)
    field_missing = sorted(eligible - field_doc_ids)
    browser_stale: list[str] = []
    field_stale: list[str] = []
    identity_mismatch: list[str] = []
    projection_lags: list[float] = []
    extraction_lags: list[float] = []
    for doc_id in eligible:
        selected_at = parse_timestamp(selected[doc_id].get("base_created_at"))
        discovered_at = parse_timestamp(docs[doc_id].get("discovered_at"))
        if selected_at and discovered_at:
            extraction_lags.append((selected_at - discovered_at).total_seconds())
        browser_row = browser.get(doc_id)
        if browser_row and selected_at:
            updated = parse_timestamp(browser_row.get("updated_at"))
            if updated:
                projection_lags.append((updated - selected_at).total_seconds())
                if updated < selected_at:
                    browser_stale.append(doc_id)
            if (
                browser_row.get("producer") != selected[doc_id].get("base_producer")
                or browser_row.get("producer_version")
                != selected[doc_id].get("base_producer_version")
                or browser_row.get("schema_version") != selected[doc_id].get("base_schema_version")
            ):
                identity_mismatch.append(doc_id)
        if doc_id in field_updated and selected_at and field_updated[doc_id] < selected_at:
            field_stale.append(doc_id)
    return {
        "eligible_denominator": {
            "definition": (
                "cds_documents with extraction_status=extracted, canonical year start >=2024, "
                "and a row in cds_selected_extraction_result"
            ),
            "documents": len(eligible),
            "browser_intended_exclusions_wrong_file": len(wrong_file),
            "browser_expected": len(browser_expected),
            "field_projection_expected": len(eligible),
        },
        "school_browser_rows": {
            "actual": len(browser),
            "missing_expected": len(browser_missing),
            "unexpected": len(browser_unexpected),
            "updated_before_selected_artifact": len(browser_stale),
            "producer_version_schema_proxy_mismatch": len(identity_mismatch),
            "missing_document_ids": browser_missing,
            "unexpected_document_ids": browser_unexpected,
            "stale_document_ids": sorted(browser_stale),
            "identity_mismatch_document_ids": sorted(identity_mismatch),
        },
        "cds_fields": {
            "projected_documents": len(field_doc_ids),
            "missing_expected": len(field_missing),
            "updated_before_selected_artifact": len(field_stale),
            "missing_document_ids": field_missing,
            "stale_document_ids": sorted(field_stale),
        },
        "lags_seconds": {
            "document_discovered_to_selected_artifact_p50": percentile(extraction_lags, 0.50),
            "document_discovered_to_selected_artifact_p95": percentile(extraction_lags, 0.95),
            "selected_artifact_to_browser_updated_p50": percentile(projection_lags, 0.50),
            "selected_artifact_to_browser_updated_p95": percentile(projection_lags, 0.95),
        },
        "provenance_limitation": (
            "updated_at is a practical delete/reinsert refresh timestamp, but neither "
            "projection table stores selected artifact_id or copied source_sha256. Producer, "
            "version, schema, and time checks are therefore proxies rather than byte identity."
        ),
    }


def admissions_summary(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    incoherent: list[str] = []
    withheld_values = 0
    for row in rows:
        applied = row.get("applied")
        admitted = row.get("admitted")
        enrolled = row.get("enrolled_first_year")
        bad = (
            applied is not None
            and admitted is not None
            and admitted > applied
        ) or (
            admitted is not None
            and enrolled is not None
            and enrolled > admitted
        )
        if bad:
            incoherent.append(str(row.get("document_id")))
            withheld_values += sum(
                value is not None for value in (applied, admitted, enrolled)
            )
    return {
        "incoherent_rows": len(incoherent),
        "denominator": len(rows),
        "non_null_values_withheld_by_friendly_api": withheld_values,
        "document_ids": sorted(incoherent),
        "behavior": (
            "public-data.ts withholds applied/admitted/enrolled_first_year for these rows "
            "and emits low_confidence_extract with a reason; the browser row remains queryable."
        ),
    }


def finance_summary(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    by_year_field: Counter[Any] = Counter()
    by_release_field: dict[tuple[str, str, int, str], Counter[str]] = defaultdict(Counter)
    negative_numeric_labeled = 0
    negative_numeric_unlabeled = 0
    labeled_negative_status = 0
    provenance_missing = 0
    grouped: dict[tuple[str, str, int], dict[str, Mapping[str, Any]]] = defaultdict(dict)
    for row in rows:
        by_year_field[(row.get("data_year"), row.get("field_key"))] += 1
        release_key = (
            str(row.get("release_id") or ""),
            str(row.get("release_type") or ""),
            int(row.get("data_year") or 0),
            str(row.get("field_key") or ""),
        )
        by_release_field[release_key]["rows"] += 1
        numeric = decimal_value(row.get("value_numeric"))
        label = str(row.get("value_label") or "").strip()
        raw_text = decimal_value(row.get("value_text"))
        if numeric is not None and numeric < 0:
            if label:
                negative_numeric_labeled += 1
                by_release_field[release_key]["negative_numeric_labeled"] += 1
            else:
                negative_numeric_unlabeled += 1
                by_release_field[release_key]["negative_numeric_unlabeled"] += 1
        if numeric is None and raw_text is not None and raw_text < 0 and label:
            labeled_negative_status += 1
            by_release_field[release_key]["labeled_negative_status"] += 1
        if not row.get("source_table") or not row.get("source_variable") or not row.get("release_type"):
            provenance_missing += 1
        key = (
            str(row.get("release_id") or ""),
            str(row.get("ipeds_id") or ""),
            int(row.get("data_year") or 0),
        )
        grouped[key][str(row.get("field_key"))] = row

    exclusions: Counter[str] = Counter()
    eligible = 0
    rates: list[Decimal] = []
    for cells in grouped.values():
        if any(field not in cells for field in FINANCE_FIELDS):
            exclusions["incomplete_components"] += 1
            continue
        if any(cells[field].get("quality_flag") != "reported" for field in FINANCE_FIELDS):
            exclusions["non_reported_input"] += 1
            continue
        values = {field: decimal_value(cells[field].get("value_numeric")) for field in FINANCE_FIELDS}
        if any(values[field] is None for field in FINANCE_FIELDS):
            exclusions["incomplete_components"] += 1
            continue
        beginning = values["endowment_value_begin"]
        ending = values["endowment_value_end"]
        spending = values["endowment_spending_distribution"]
        assert beginning is not None and ending is not None and spending is not None
        if beginning <= 0:
            exclusions["nonpositive_beginning_value"] += 1
            continue
        components = sum(
            (
                values["endowment_new_gifts"],
                values["endowment_investment_return"],
                values["endowment_spending_distribution"],
                values["endowment_other_change"],
            ),
            Decimal(0),
        )
        if ending - beginning != components:
            exclusions["accounting_identity_mismatch"] += 1
            continue
        eligible += 1
        rates.append(abs(spending) / beginning)
    return {
        "rows": len(rows),
        "by_year_field": [
            {"data_year": key[0], "field_key": key[1], "rows": count}
            for key, count in sorted(by_year_field.items())
        ],
        "sign_contract": {
            "negative_numeric_with_value_label": negative_numeric_labeled,
            "negative_numeric_without_value_label": negative_numeric_unlabeled,
            "negative_raw_text_status_with_value_label": labeled_negative_status,
            "interpretation": (
                "A labeled negative is stored as a status fact; an unlabeled negative remains "
                "numeric. A blanket allowNegative registry would be incorrect."
            ),
        },
        "sign_contract_by_release_field": [
            {
                "release_id": key[0],
                "release_type": key[1],
                "data_year": key[2],
                "field_key": key[3],
                "rows": counts["rows"],
                "negative_numeric_labeled": counts["negative_numeric_labeled"],
                "negative_numeric_unlabeled": counts["negative_numeric_unlabeled"],
                "labeled_negative_status": counts["labeled_negative_status"],
            }
            for key, counts in sorted(by_release_field.items())
        ],
        "provenance_rows_missing_source_table_variable_or_release_type": provenance_missing,
        "draw_rate": {
            "formula": "abs(F2H03C) / F2H01",
            "raw_F2H03D_preserved": True,
            "candidate_reporter_years": len(grouped),
            "eligible": eligible,
            "exclusions": summarize_counter(exclusions),
            "rate_p50": float(percentile([float(rate) for rate in rates], 0.50)) if rates else None,
            "rate_p95": float(percentile([float(rate) for rate in rates], 0.95)) if rates else None,
        },
    }


def directory_finance_scope_summary(
    finance_rows: Sequence[Mapping[str, Any]], directory_rows: Sequence[Mapping[str, Any]]
) -> dict[str, Any]:
    directory = {str(row.get("ipeds_id")): row for row in directory_rows}
    loaded_ids = {str(row.get("ipeds_id")) for row in finance_rows if row.get("ipeds_id")}
    served = {ipeds_id for ipeds_id in loaded_ids if directory.get(ipeds_id, {}).get("in_scope") is True}
    absent = loaded_ids - set(directory)
    out_of_scope = {
        ipeds_id
        for ipeds_id in loaded_ids
        if ipeds_id in directory and directory[ipeds_id].get("in_scope") is not True
    }
    return {
        "bounded_population": (
            "IPEDS endowment reporter UNITIDs present in the FY2020-FY2024 six-field slice; "
            "this is not an all-ipeds_facts inventory"
        ),
        "loaded_reporters": len(loaded_ids),
        "served_in_scope": len(served),
        "loaded_but_unserved": len(loaded_ids - served),
        "absent_from_directory": len(absent),
        "directory_out_of_scope": len(out_of_scope),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--env", type=Path, default=REPO_ROOT / ".env")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--pagination-output", type=Path, required=True)
    args = parser.parse_args()

    env = load_env(args.env)
    base_url = env.get("SUPABASE_URL")
    api_key = env.get("SUPABASE_SERVICE_ROLE_KEY")
    if not base_url or not api_key:
        print("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY are required", file=sys.stderr)
        return 2

    client = ReadOnlyPostgrest(base_url, api_key)
    run_started_at = utc_now()
    pagination: dict[str, Any] = {}

    core_counts = {
        table: client.exact_count(table)
        for table in (
            "cds_documents",
            "cds_artifacts",
            "school_browser_rows",
            "cds_fields",
            "ipeds_facts",
            "archive_queue",
            "institution_cds_coverage",
        )
    }

    documents, pagination["cds_documents"] = client.paginate(
        "cds_documents.full",
        "cds_documents",
        {
            "select": (
                "id,school_id,school_name,sub_institutional,ipeds_id,cds_year,detected_year,"
                "source_url,source_format,source_sha256,participation_status,extraction_status,"
                "data_quality_flag,discovered_at,created_at,updated_at"
            ),
            "order": "id.asc",
        },
        unique_key=lambda row: row["id"],
    )
    selected, pagination["cds_selected_extraction_result"] = client.paginate(
        "cds_selected_extraction_result.full",
        "cds_selected_extraction_result",
        {
            "select": (
                "document_id,base_artifact_id,base_producer,base_producer_version,"
                "base_schema_version,base_created_at,fallback_artifact_id,"
                "fallback_producer_version,fallback_created_at"
            ),
            "order": "document_id.asc",
        },
        unique_key=lambda row: row["document_id"],
    )
    artifacts, pagination["cds_artifacts"] = client.paginate(
        "cds_artifacts.metadata",
        "cds_artifacts",
        {
            "select": (
                "id,document_id,kind,producer,producer_version,schema_version,storage_path,sha256,"
                "created_at"
            ),
            "order": "id.asc",
        },
        unique_key=lambda row: row["id"],
    )
    selected_tier4_ids = [
        str(row["base_artifact_id"])
        for row in selected
        if row.get("base_producer") == "tier4_docling" and row.get("base_artifact_id")
    ]
    selected_tier4_ids.extend(
        str(row["fallback_artifact_id"])
        for row in selected
        if row.get("base_producer") == "tier4_docling" and row.get("fallback_artifact_id")
    )
    tier4_rows, pagination["tier4_artifact_values"] = client.fetch_id_chunks(
        "cds_artifacts.tier4_and_fallback_values",
        "cds_artifacts",
        selected_tier4_ids,
        {
            "select": (
                "id,document_id,kind,producer,producer_version,schema_version,created_at,"
                "values:notes->values,stats:notes->stats"
            ),
        },
        unique_key=lambda row: row["id"],
        chunk_size=25,
    )
    browser, pagination["school_browser_rows"] = client.paginate(
        "school_browser_rows.full",
        "school_browser_rows",
        {
            "select": (
                "document_id,school_id,canonical_year,schema_version,producer,producer_version,"
                "data_quality_flag,applied,admitted,enrolled_first_year,updated_at"
            ),
            "order": "document_id.asc",
        },
        unique_key=lambda row: row["document_id"],
    )
    fields, pagination["cds_fields"] = client.paginate(
        "cds_fields.per_question",
        "cds_fields",
        {
            "select": (
                "document_id,schema_version,field_id,value_status,producer,source_format,updated_at"
            ),
            "order": "document_id.asc,schema_version.asc,field_id.asc",
        },
        unique_key=lambda row: (row["document_id"], row["schema_version"], row["field_id"]),
    )
    queue, pagination["archive_queue"] = client.paginate(
        "archive_queue.full",
        "archive_queue",
        {
            "select": (
                "id,enqueued_run_id,school_id,school_name,cds_url_hint,status,attempts,"
                "enqueued_at,processed_at,last_outcome,source"
            ),
            "order": "id.asc",
        },
        unique_key=lambda row: row["id"],
    )
    first_queue_page, first_queue_meta = client.page_once(
        "archive_queue",
        {"select": "id,last_outcome,status"},
        start=0,
        end=999,
    )
    attempts, pagination["archive_queue_attempts"] = client.paginate(
        "archive_queue_attempts.post_ledger",
        "archive_queue_attempts",
        {
            "select": (
                "queue_id,attempt_number,claimed_at,finished_at,duration_ms,terminal_state,last_outcome"
            ),
            "order": "queue_id.asc,attempt_number.asc",
        },
        unique_key=lambda row: (row["queue_id"], row["attempt_number"]),
    )
    directory, pagination["institution_directory"] = client.paginate(
        "institution_directory.full",
        "institution_directory",
        {
            "select": "ipeds_id,school_id,school_name,in_scope",
            "order": "ipeds_id.asc",
        },
        unique_key=lambda row: row["ipeds_id"],
    )

    finance_rows: list[dict[str, Any]] = []
    for field_key in FINANCE_FIELDS:
        identifier = f"ipeds_facts.finance.{field_key}"
        rows, meta = client.paginate(
            identifier,
            "ipeds_facts",
            {
                "select": (
                    "release_id,unitid,ipeds_id,data_year,field_key,value_numeric,value_text,"
                    "value_label,quality_flag,source_table,source_variable,release_type,"
                    "imputation_flag,imputation_label,definition_alignment,public_visible"
                ),
                "field_key": f"eq.{field_key}",
                "data_year": "gte.2020",
                "and": "(data_year.lte.2024,source_table.like.F*_F2)",
                "order": (
                    "release_id.asc,unitid.asc,field_key.asc,source_table.asc,source_variable.asc"
                ),
            },
            unique_key=lambda row: (
                row["release_id"],
                row["unitid"],
                row["field_key"],
                row["source_table"],
                row["source_variable"],
            ),
            page_size=IPEDS_PAGE_SIZE,
        )
        finance_rows.extend(rows)
        pagination[identifier] = meta

    docs_by_id = {str(row["id"]): row for row in documents}
    fields_report = field_summary(fields)
    report = {
        "label": "Partial execution — network reprobe, source-byte corpus probe, and manual checks run separately",
        "run_started_at": run_started_at,
        "run_finished_at": utc_now(),
        "snapshot_semantics": (
            "Sequential live read-only requests; not an atomic database snapshot. Per-query "
            "captured_at timestamps, Content-Range headers, and result checksums are in pagination.json."
        ),
        "source": {
            "git_commit": git_value("rev-parse", "HEAD"),
            "origin_main": git_value("rev-parse", "origin/main"),
        },
        "core_exact_counts": core_counts,
        "documents": document_summary(documents),
        "artifacts": artifact_summary(artifacts),
        "tier4": tier4_summary(tier4_rows, selected, docs_by_id),
        "cds_fields": {
            key: value
            for key, value in fields_report.items()
            if key != "document_max_updated_at"
        },
        "archive_queue": archive_summary(queue, first_queue_page),
        "archive_queue_first_page_request": first_queue_meta,
        "archive_attempts": attempt_summary(attempts),
        "projection": projection_summary(documents, selected, browser, fields),
        "admissions_withholding": admissions_summary(browser),
        "ipeds_finance": finance_summary(finance_rows),
        "loaded_but_unserved_finance": directory_finance_scope_summary(finance_rows, directory),
        "limitations": [
            "No production mutation or mutating RPC was executed.",
            "The run is sequential and cannot freeze concurrent production writes.",
            "The selected-extraction view is used as a provenance proxy because projection rows lack artifact_id/source_sha256.",
            "The bounded IPEDS finance slice does not stand in for a 4.4-million-row full-table export.",
            "Concurrency invariants require an isolated local/test database and are not exercised here.",
        ],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.pagination_output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    args.pagination_output.write_text(json.dumps(pagination, indent=2, sort_keys=True) + "\n")
    print(
        json.dumps(
            {
                "output": str(args.output),
                "pagination_output": str(args.pagination_output),
                "counts": {table: value["count"] for table, value in core_counts.items()},
                "queries": len(pagination),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
