#!/usr/bin/env python3
"""Read-only audit for active cds_documents filed under non-canonical alias slugs.

Queries institution_slug_crosswalk and active cds_documents (removed_at IS NULL),
lists any active document whose school_id is an alias that maps to a different
canonical school_id, and classifies whether the canonical school_id already has
an active document for the same year and/or with the same source_sha256.

Exits 0 when no alias-filed active documents exist, 1 when any are found, and 2
on configuration or transport errors.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Iterable, Mapping

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.ops.directory_enqueue_batches import (  # noqa: E402
    OpsError,
    SupabaseClient,
    configure_output_buffering,
)

PAGE_SIZE = 1000


def load_env(path: Path) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def fetch_all_rows(
    client: SupabaseClient,
    table: str,
    params: dict[str, str],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    offset = 0
    while True:
        batch = client.rest_get(
            table,
            params,
            page=(offset, offset + PAGE_SIZE - 1),
        )
        if not isinstance(batch, list):
            raise OpsError(f"Expected list from {table}, got {type(batch).__name__}")
        rows.extend(batch)
        if len(batch) < PAGE_SIZE:
            break
        offset += PAGE_SIZE
    return rows


def fetch_slug_crosswalk(client: SupabaseClient) -> list[dict[str, Any]]:
    return fetch_all_rows(
        client,
        "institution_slug_crosswalk",
        {
            "select": "alias,school_id,ipeds_id,is_primary,alias_type",
            "order": "alias.asc,school_id.asc",
        },
    )


def fetch_active_documents(client: SupabaseClient) -> list[dict[str, Any]]:
    return fetch_all_rows(
        client,
        "cds_documents",
        {
            "select": (
                "id,school_id,school_name,cds_year,detected_year,"
                "sub_institutional,source_sha256,source_provenance,"
                "extraction_status,source_url,created_at,updated_at"
            ),
            "removed_at": "is.null",
            "order": "school_id.asc,cds_year.asc,id.asc",
        },
    )


def build_alias_to_canonical_map(
    crosswalk_rows: Iterable[Mapping[str, Any]],
) -> dict[str, str]:
    """Return alias -> canonical school_id for non-canonical crosswalk aliases."""
    rows = list(crosswalk_rows)
    canonical_school_ids = {
        str(row.get("school_id") or "").strip()
        for row in rows
        if str(row.get("school_id") or "").strip()
    }
    by_alias: dict[str, list[Mapping[str, Any]]] = {}
    for row in rows:
        alias = str(row.get("alias") or "").strip()
        school_id = str(row.get("school_id") or "").strip()
        if not alias or not school_id:
            continue
        by_alias.setdefault(alias, []).append(row)

    alias_map: dict[str, str] = {}
    for alias, matches in sorted(by_alias.items()):
        if alias in canonical_school_ids:
            continue
        primary_targets = {
            str(row.get("school_id") or "").strip()
            for row in matches
            if row.get("is_primary") is True and str(row.get("school_id") or "").strip()
        }
        if len(primary_targets) == 1:
            target = next(iter(primary_targets))
            if target != alias:
                alias_map[alias] = target
            continue
        if len(primary_targets) > 1:
            continue
        distinct_targets = {
            str(row.get("school_id") or "").strip()
            for row in matches
            if str(row.get("school_id") or "").strip()
        }
        if len(distinct_targets) == 1:
            target = next(iter(distinct_targets))
            if target != alias:
                alias_map[alias] = target
    return alias_map


def _year_tokens(doc: Mapping[str, Any]) -> set[str]:
    tokens: set[str] = set()
    for field in ("cds_year", "detected_year"):
        value = str(doc.get(field) or "").strip()
        if value:
            tokens.add(value)
    return tokens


def _sub_institutional_key(doc: Mapping[str, Any]) -> str:
    return str(doc.get("sub_institutional") or "").strip()


def classify_alias_documents(
    documents: Iterable[Mapping[str, Any]],
    crosswalk_rows: Iterable[Mapping[str, Any]],
) -> dict[str, Any]:
    """Identify and classify active cds_documents filed under alias slugs."""
    active_docs = [
        dict(doc)
        for doc in documents
        if doc.get("removed_at") is None and str(doc.get("school_id") or "").strip()
    ]
    alias_to_canonical = build_alias_to_canonical_map(crosswalk_rows)

    docs_by_school: dict[str, list[dict[str, Any]]] = {}
    for doc in active_docs:
        sid = str(doc.get("school_id") or "").strip()
        docs_by_school.setdefault(sid, []).append(doc)

    findings: list[dict[str, Any]] = []
    by_classification: Counter[str] = Counter()
    by_alias: Counter[str] = Counter()

    for doc in sorted(
        active_docs,
        key=lambda item: (
            str(item.get("school_id") or ""),
            str(item.get("cds_year") or item.get("detected_year") or ""),
            str(item.get("id") or ""),
        ),
    ):
        alias_slug = str(doc.get("school_id") or "").strip()
        canonical_slug = alias_to_canonical.get(alias_slug)
        if not canonical_slug or canonical_slug == alias_slug:
            continue

        canonical_docs = docs_by_school.get(canonical_slug, [])
        alias_years = _year_tokens(doc)
        alias_sub = _sub_institutional_key(doc)
        alias_sha = str(doc.get("source_sha256") or "").strip()

        same_year_docs = [
            cand
            for cand in canonical_docs
            if _sub_institutional_key(cand) == alias_sub
            and bool(alias_years & _year_tokens(cand))
        ]
        same_sha_docs = [
            cand
            for cand in canonical_docs
            if alias_sha and str(cand.get("source_sha256") or "").strip() == alias_sha
        ]
        same_year = bool(same_year_docs)
        same_source_sha256 = bool(
            alias_sha
            and any(
                str(cand.get("source_sha256") or "").strip() == alias_sha
                for cand in (same_year_docs or canonical_docs)
            )
        )

        if same_year and same_source_sha256:
            classification = "exact_duplicate"
        elif same_year:
            classification = "same_year_different_sha256"
        elif same_source_sha256:
            classification = "same_sha256_different_year"
        else:
            classification = "alias_only_year"

        matching_canonical_docs = same_year_docs or same_sha_docs
        finding = {
            "document_id": doc.get("id"),
            "alias_school_id": alias_slug,
            "canonical_school_id": canonical_slug,
            "cds_year": doc.get("cds_year"),
            "detected_year": doc.get("detected_year"),
            "sub_institutional": doc.get("sub_institutional"),
            "source_sha256": alias_sha or None,
            "source_provenance": doc.get("source_provenance"),
            "extraction_status": doc.get("extraction_status"),
            "same_year": same_year,
            "same_source_sha256": same_source_sha256,
            "classification": classification,
            "canonical_document_ids": [
                cand.get("id") for cand in matching_canonical_docs if cand.get("id")
            ],
            "canonical_source_sha256s": [
                str(cand.get("source_sha256") or "").strip()
                for cand in matching_canonical_docs
                if str(cand.get("source_sha256") or "").strip()
            ],
        }
        findings.append(finding)
        by_classification[classification] += 1
        by_alias[alias_slug] += 1

    return {
        "active_document_count": len(active_docs),
        "alias_mapping_count": len(alias_to_canonical),
        "duplicate_count": len(findings),
        "by_classification": dict(sorted(by_classification.items())),
        "by_alias_school_id": dict(sorted(by_alias.items())),
        "findings": findings,
    }


def format_report(report: Mapping[str, Any]) -> str:
    lines = [
        "Duplicate slug audit: "
        f"{report['duplicate_count']} active document(s) under alias slugs "
        f"(scanned {report['active_document_count']} active cds_documents across "
        f"{report['alias_mapping_count']} non-canonical crosswalk aliases)"
    ]
    if report["by_classification"]:
        breakdown = ", ".join(
            f"{key}={count}"
            for key, count in sorted(report["by_classification"].items())
        )
        lines.append(f"Classifications: {breakdown}")
    for item in report["findings"]:
        year = item.get("cds_year") or item.get("detected_year") or "unknown-year"
        lines.append(
            f"  - doc={item['document_id']} "
            f"alias={item['alias_school_id']} -> canonical={item['canonical_school_id']} "
            f"year={year} same_year={item['same_year']} "
            f"same_source_sha256={item['same_source_sha256']} "
            f"class={item['classification']} "
            f"provenance={item.get('source_provenance') or 'unknown'}"
        )
    return "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--env",
        type=Path,
        default=REPO_ROOT / ".env",
        help="Optional .env file to load before reading SUPABASE_URL/SUPABASE_SERVICE_ROLE_KEY",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit the audit report as JSON",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    configure_output_buffering()
    args = build_parser().parse_args(argv)
    load_env(args.env)
    if args.env == REPO_ROOT / ".env":
        load_env(REPO_ROOT.parent / ".env")

    supabase_url = os.environ.get("SUPABASE_URL", "").strip()
    service_role_key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "").strip()
    if not supabase_url or not service_role_key:
        print(
            "error: SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY are required",
            file=sys.stderr,
        )
        return 2

    client = SupabaseClient(supabase_url, service_role_key)
    try:
        crosswalk_rows = fetch_slug_crosswalk(client)
        documents = fetch_active_documents(client)
    except OpsError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    report = classify_alias_documents(documents, crosswalk_rows)
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print(format_report(report))
    return 1 if report["duplicate_count"] > 0 else 0


if __name__ == "__main__":
    raise SystemExit(main())
