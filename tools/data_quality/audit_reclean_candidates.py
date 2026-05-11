#!/usr/bin/env python3
"""Find Tier 4 artifacts that likely need a deterministic re-clean.

This targets cleaner misses where the stored Docling markdown contains an
answerable CDS subsection, but the canonical values and browser projection are
missing the corresponding fields. It is intentionally conservative: it emits a
worklist for re-clean/redrain, not a migration by itself.

Usage:
    python tools/data_quality/audit_reclean_candidates.py --env .env.local
    python tools/data_quality/audit_reclean_candidates.py --school boston-university
    python tools/data_quality/audit_reclean_candidates.py --output .context/reclean-candidates.json
"""

from __future__ import annotations

import argparse
import json
import os
import re
import time
from collections import Counter
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from supabase import create_client


PUBLIC_SUPABASE_URL = "https://isduwmygvmdozhpvzaix.supabase.co"

ED_FIELDS = ("C.2101", "C.2110", "C.2111", "C.2201")
ADMISSION_POLICY_FIELDS = (
    "C.1301",
    "C.1302",
    "C.1304",
    "C.1305",
    "C.1401",
    "C.1402",
    "C.1403",
    "C.1501",
    "C.1604",
    "C.1605",
    "C.1606",
    "C.1701",
    "C.1702",
    "C.1703",
    "C.1709",
    "C.1710",
    "C.1711",
    "C.1801",
    "C.1901",
)


@dataclass
class Candidate:
    category: str
    confidence: str
    reason: str
    document_id: str
    school_id: str
    school_name: str
    canonical_year: str
    applied: int | None
    producer_version: str
    artifact_id: str
    artifact_created_at: str
    browser_ed_offered: bool | None
    browser_ed_applicants: int | None
    browser_ed_admitted: int | None
    inferred_ed_offered: bool | None
    inferred_ed_applicants: int | None
    inferred_ed_admitted: int | None
    missing_fields: list[str]
    present_fields: list[str]


def load_env(path: Path | None) -> None:
    if not path or not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key.strip(), value)


def make_client(env_path: Path | None) -> Any:
    load_env(env_path)
    url = (
        os.environ.get("SUPABASE_URL")
        or os.environ.get("NEXT_PUBLIC_SUPABASE_URL")
        or PUBLIC_SUPABASE_URL
    )
    key = (
        os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
        or os.environ.get("SUPABASE_ANON_KEY")
        or os.environ.get("NEXT_PUBLIC_SUPABASE_ANON_KEY")
    )
    if not key:
        raise SystemExit(
            "Missing SUPABASE_ANON_KEY, NEXT_PUBLIC_SUPABASE_ANON_KEY, or SUPABASE_SERVICE_ROLE_KEY"
        )
    return create_client(url, key)


def fetch_all(query: Any, page_size: int = 1000) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    offset = 0
    while True:
        batch: list[dict[str, Any]] = []
        for attempt in range(4):
            try:
                batch = query.range(offset, offset + page_size - 1).execute().data or []
                break
            except Exception:
                if attempt == 3:
                    raise
                time.sleep(2**attempt)
        rows.extend(batch)
        if len(batch) < page_size:
            return rows
        offset += page_size


def fetch_browser_rows(
    client: Any,
    *,
    school: str | None,
    min_year_start: int,
    limit: int | None,
) -> list[dict[str, Any]]:
    select_cols = (
        "document_id,school_id,school_name,canonical_year,year_start,producer,"
        "applied,admitted,ed_offered,ed_applicants,ed_admitted,ed_has_second_deadline,"
        "ea_offered,ea_restrictive"
    )
    query = (
        client.table("school_browser_rows")
        .select(select_cols)
        .gte("year_start", min_year_start)
        .is_("sub_institutional", "null")
        .order("year_start", desc=True)
        .order("school_id", desc=False)
    )
    if school:
        query = query.eq("school_id", school)
    rows = fetch_all(query)
    rows = [row for row in rows if row.get("producer") == "tier4_docling"]
    return rows[:limit] if limit else rows


def latest_canonical_artifacts(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    latest: dict[str, dict[str, Any]] = {}
    for row in sorted(rows, key=lambda item: str(item.get("created_at") or ""), reverse=True):
        doc_id = str(row.get("document_id") or "")
        if doc_id and doc_id not in latest:
            latest[doc_id] = row
    return latest


def fetch_artifacts(client: Any, document_ids: list[str]) -> dict[str, dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    select_cols = "id,document_id,kind,producer,producer_version,schema_version,created_at,notes"
    for start in range(0, len(document_ids), 25):
        chunk = document_ids[start : start + 25]
        for attempt in range(4):
            try:
                batch = (
                    client.table("cds_artifacts")
                    .select(select_cols)
                    .eq("kind", "canonical")
                    .eq("producer", "tier4_docling")
                    .in_("document_id", chunk)
                    .execute()
                    .data
                    or []
                )
                rows.extend(batch)
                break
            except Exception:
                if attempt == 3:
                    raise
                time.sleep(2**attempt)
    return latest_canonical_artifacts(rows)


def int_or_none(value: Any) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(str(value).replace(",", ""))
    except ValueError:
        return None


def field_value(record: Any) -> Any:
    if isinstance(record, dict) and "value" in record:
        return record["value"]
    return record


def normalized_values(notes: dict[str, Any]) -> dict[str, Any]:
    raw = notes.get("values") or {}
    if not isinstance(raw, dict):
        return {}
    return {str(key): field_value(value) for key, value in raw.items()}


def section_between(text: str, start_re: str, end_re: str) -> str:
    start = re.search(start_re, text, re.IGNORECASE)
    if not start:
        return ""
    end = re.search(end_re, text[start.end() :], re.IGNORECASE)
    end_idx = start.end() + end.start() if end else len(text)
    return text[start.end() : end_idx]


def nonempty_lines(text: str) -> list[str]:
    return [line.strip() for line in text.splitlines() if line.strip()]


def leading_yes_no(section: str) -> bool | None:
    lines = nonempty_lines(section)
    for line in lines[:8]:
        normalized = re.sub(r"\s+", "", line).lower()
        if normalized == "yes":
            return True
        if normalized in {"no", "n/a", "na"}:
            return False
    return None


def extract_count_pair(section: str) -> tuple[int, int] | None:
    compact = re.sub(r"\s+", " ", section)
    labeled_apps = re.search(
        r"Number of early decision applications received.*?(\d[\d,]{2,})",
        compact,
        re.IGNORECASE,
    )
    labeled_admitted = re.search(
        r"Number of applicants admitted under early decision plan.*?(\d[\d,]{2,})",
        compact,
        re.IGNORECASE,
    )
    if labeled_apps and labeled_admitted:
        pair = int(labeled_apps.group(1).replace(",", "")), int(
            labeled_admitted.group(1).replace(",", "")
        )
        return pair if pair[1] < pair[0] else None

    before_details = re.split(
        r"Please provide significant details|C22\.?\s+Early action",
        section,
        maxsplit=1,
        flags=re.IGNORECASE,
    )[0]
    values: list[int] = []
    for match in re.finditer(r"\b\d{1,3}(?:,\d{3})+\b|\b\d{3,6}\b", before_details):
        value = int(match.group(0).replace(",", ""))
        if 1900 <= value <= 2099:
            continue
        if value < 100:
            continue
        values.append(value)
    if len(values) >= 2:
        pair = values[0], values[1]
        return pair if pair[1] < pair[0] else None
    return None


def classify_ed(row: dict[str, Any], artifact: dict[str, Any], values: dict[str, Any]) -> Candidate | None:
    notes = artifact.get("notes") or {}
    markdown = str(notes.get("markdown") or "")
    c21 = section_between(
        markdown,
        r"(?:^|\n)\s*(?:#+\s*)?C21\.?\s+Early Decision",
        r"(?:^|\n)\s*(?:#+\s*)?C22\.?\s+Early action",
    )
    if not c21:
        return None

    inferred_offered = leading_yes_no(c21)
    count_pair = extract_count_pair(c21)
    browser_apps = int_or_none(row.get("ed_applicants"))
    browser_admitted = int_or_none(row.get("ed_admitted"))
    browser_offered = row.get("ed_offered") if isinstance(row.get("ed_offered"), bool) else None
    artifact_apps = int_or_none(values.get("C.2110"))
    artifact_admitted = int_or_none(values.get("C.2111"))

    if (
        inferred_offered is not True
        or count_pair is None
        or (browser_apps is not None and browser_admitted is not None)
        or (artifact_apps is not None and artifact_admitted is not None)
    ):
        return None

    missing = [
        field
        for field in ("C.2101", "C.2110", "C.2111")
        if values.get(field) in (None, "")
    ]
    if browser_offered is not True:
        missing.append("browser.ed_offered")
    if browser_apps is None:
        missing.append("browser.ed_applicants")
    if browser_admitted is None:
        missing.append("browser.ed_admitted")

    return Candidate(
        category="early_decision_counts",
        confidence="high",
        reason="C21 block has ED=Yes and a two-number applicant/admit pair, but canonical/browser ED counts are missing",
        document_id=str(row["document_id"]),
        school_id=str(row["school_id"]),
        school_name=str(row.get("school_name") or ""),
        canonical_year=str(row.get("canonical_year") or ""),
        applied=int_or_none(row.get("applied")),
        producer_version=str(artifact.get("producer_version") or ""),
        artifact_id=str(artifact.get("id") or ""),
        artifact_created_at=str(artifact.get("created_at") or ""),
        browser_ed_offered=browser_offered,
        browser_ed_applicants=browser_apps,
        browser_ed_admitted=browser_admitted,
        inferred_ed_offered=inferred_offered,
        inferred_ed_applicants=count_pair[0],
        inferred_ed_admitted=count_pair[1],
        missing_fields=missing,
        present_fields=sorted(field for field in ED_FIELDS if values.get(field) not in (None, "")),
    )


def classify_admission_policy(
    row: dict[str, Any], artifact: dict[str, Any], values: dict[str, Any]
) -> Candidate | None:
    notes = artifact.get("notes") or {}
    markdown = str(notes.get("markdown") or "")
    compact_signature = all(
        re.search(pattern, markdown, re.IGNORECASE)
        for pattern in (
            r"C13\.?\s+Application Fee",
            r"C14\.?\s+Application closing date",
            r"C15\.?\s+Are first-time",
            r"C16\.?\s+Notification to applicants",
            r"C17\.?\s+Reply policy",
        )
    )
    if not compact_signature:
        return None
    present = sorted(field for field in ADMISSION_POLICY_FIELDS if values.get(field) not in (None, ""))
    missing = [field for field in ADMISSION_POLICY_FIELDS if field not in present]
    if len(missing) < 8:
        return None

    return Candidate(
        category="compact_admission_policy_section",
        confidence="medium",
        reason="C13-C17 compact section headings are present in markdown, but many deterministic policy fields are absent",
        document_id=str(row["document_id"]),
        school_id=str(row["school_id"]),
        school_name=str(row.get("school_name") or ""),
        canonical_year=str(row.get("canonical_year") or ""),
        applied=int_or_none(row.get("applied")),
        producer_version=str(artifact.get("producer_version") or ""),
        artifact_id=str(artifact.get("id") or ""),
        artifact_created_at=str(artifact.get("created_at") or ""),
        browser_ed_offered=row.get("ed_offered") if isinstance(row.get("ed_offered"), bool) else None,
        browser_ed_applicants=int_or_none(row.get("ed_applicants")),
        browser_ed_admitted=int_or_none(row.get("ed_admitted")),
        inferred_ed_offered=None,
        inferred_ed_applicants=None,
        inferred_ed_admitted=None,
        missing_fields=missing,
        present_fields=present,
    )


def build_report(rows: list[dict[str, Any]], artifacts: dict[str, dict[str, Any]]) -> dict[str, Any]:
    candidates_by_key: dict[tuple[str, str], Candidate] = {}
    for row in rows:
        artifact = artifacts.get(str(row["document_id"]))
        if not artifact:
            continue
        notes = artifact.get("notes") or {}
        if not isinstance(notes, dict):
            continue
        values = normalized_values(notes)
        for candidate in (
            classify_ed(row, artifact, values),
            classify_admission_policy(row, artifact, values),
        ):
            if candidate:
                candidates_by_key[(candidate.document_id, candidate.category)] = candidate

    candidates = list(candidates_by_key.values())
    candidates.sort(
        key=lambda item: (
            {"high": 0, "medium": 1, "low": 2}.get(item.confidence, 9),
            item.category,
            -(item.applied or 0),
            item.school_id,
            item.canonical_year,
        )
    )
    category_counts = Counter(candidate.category for candidate in candidates)
    confidence_counts = Counter(candidate.confidence for candidate in candidates)
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": "school_browser_rows + latest canonical tier4_docling artifacts",
        "rows_scanned": len(rows),
        "artifacts_scanned": len(artifacts),
        "candidate_count": len(candidates),
        "category_counts": dict(sorted(category_counts.items())),
        "confidence_counts": dict(sorted(confidence_counts.items())),
        "candidates": [asdict(candidate) for candidate in candidates],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.strip().split("\n\n")[0])
    parser.add_argument("--env", type=Path, default=Path(".env.local"))
    parser.add_argument("--school", help="Restrict to one school_id")
    parser.add_argument("--min-year-start", type=int, default=2024)
    parser.add_argument("--limit", type=int, help="Limit browser rows before artifact fetch")
    parser.add_argument("--output", type=Path, default=Path(".context/reclean-candidates.json"))
    parser.add_argument("--json", action="store_true", help="Print full JSON report")
    args = parser.parse_args()

    client = make_client(args.env)
    rows = fetch_browser_rows(
        client,
        school=args.school,
        min_year_start=args.min_year_start,
        limit=args.limit,
    )
    artifacts = fetch_artifacts(client, [str(row["document_id"]) for row in rows])
    report = build_report(rows, artifacts)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    summary = {
        key: report[key]
        for key in (
            "generated_at",
            "rows_scanned",
            "artifacts_scanned",
            "candidate_count",
            "category_counts",
            "confidence_counts",
        )
    }
    print(json.dumps(report if args.json else summary, indent=2, sort_keys=True))
    print(f"Wrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
