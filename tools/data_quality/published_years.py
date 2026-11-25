"""Paginated published-year coverage queries.

Shared by the kids worklist and the top-100 coverage scorer so those
tools cannot drift on what a published year means.

A published year is keyed on the document's canonical year (the same
`coalesce(detected_year, cds_year)` the `cds_manifest` view serves), counts
only live rows (`removed_at is null`), and is read with a stable order and a
row-count check, so a short page raises instead of reporting fewer years.
"""

from __future__ import annotations

import re
from typing import Any, Callable

PAGE_SIZE = 1000
_YEAR_RE = re.compile(r"^\d{4}-\d{2}$")


def canonical_year(row: dict[str, Any]) -> str | None:
    """`coalesce(detected_year, cds_year)`, accepting only YYYY-YY values.

    A doc filed under `unknown` but dated by `detected_year` counts under the
    detected year; one with neither returns None (never an `unknown` year).
    """
    for key in ("detected_year", "cds_year"):
        value = row.get(key)
        if value and _YEAR_RE.match(str(value).strip()):
            return str(value).strip()
    return None


def _year_filter(years: list[str]) -> str:
    joined = ",".join(years)
    return f"cds_year.in.({joined}),detected_year.in.({joined})"


def fetch_all_rows(
    make_query: Callable[[], Any], *, page_size: int = PAGE_SIZE
) -> list[dict[str, Any]]:
    """Read every row of a query, page by page.

    `make_query()` must return a fresh query that already has its filters and
    a unique `.order(...)`, and was built with `select(..., count="exact")`.
    Raises if the server gives no count or the rows read fall short of it,
    because a silent short page looks the same as a school with no document.
    """
    rows: list[dict[str, Any]] = []
    offset = 0
    while True:
        result = make_query().range(offset, offset + page_size - 1).execute()
        batch = result.data or []
        total = getattr(result, "count", None)
        if total is None:
            raise RuntimeError("paged read returned no row count")
        rows.extend(batch)
        if len(rows) >= total:
            return rows
        if not batch:
            raise RuntimeError(
                f"paged read stopped at {len(rows)} of {total} rows"
            )
        offset += len(batch)


def fetch_published_years(
    sb, school_ids: list[str], years: list[str]
) -> dict[str, set[str]]:
    """Return {school_id: {years_present}} for published documents."""
    have: dict[str, set[str]] = {sid: set() for sid in school_ids}
    want = set(school_ids)
    year_set = set(years)
    rows = fetch_all_rows(
        lambda: sb.table("cds_documents")
        .select(
            "id, school_id, cds_year, detected_year, participation_status",
            count="exact",
        )
        .or_(_year_filter(years))
        .is_("removed_at", "null")
        .order("id")
    )
    for row in rows:
        sid = row["school_id"]
        year = canonical_year(row)
        if (
            sid in want
            and year in year_set
            and row.get("participation_status") == "published"
        ):
            have[sid].add(year)
    return have


def fetch_year_byte_coverage(
    sb, school_ids: list[str], years: list[str]
) -> dict[str, dict[str, dict[str, Any]]]:
    """Published-year rows plus source-byte evidence.

    A year is `has_bytes` when participation_status is published, source_sha256
    is present, and a cds_artifacts row of kind=source has a storage_path.
    Withdrawn / verified_absent / unknown years do not count.
    """
    want = set(school_ids)
    year_set = set(years)
    by_school: dict[str, dict[str, dict[str, Any]]] = {
        sid: {
            year: {
                "published": False,
                "sha256": None,
                "document_id": None,
                "has_source_artifact": False,
            }
            for year in years
        }
        for sid in school_ids
    }
    doc_ids: list[str] = []
    docs = fetch_all_rows(
        lambda: sb.table("cds_documents")
        .select(
            "id, school_id, cds_year, detected_year, participation_status, "
            "source_sha256",
            count="exact",
        )
        .or_(_year_filter(years))
        .is_("removed_at", "null")
        .order("id")
    )
    for row in docs:
        sid = row["school_id"]
        year = canonical_year(row)
        if sid not in want or year not in year_set:
            continue
        if row.get("participation_status") != "published":
            continue
        slot = by_school[sid][year]
        sha = row.get("source_sha256") or None
        if slot["published"] and slot["sha256"]:
            continue
        slot["published"] = True
        slot["sha256"] = sha
        slot["document_id"] = row["id"]
        if sha:
            doc_ids.append(row["id"])

    artifact_docs: set[str] = set()
    for i in range(0, len(doc_ids), 100):
        chunk = doc_ids[i : i + 100]
        arts = fetch_all_rows(
            lambda chunk=chunk: sb.table("cds_artifacts")
            .select("id, document_id, storage_path, kind", count="exact")
            .eq("kind", "source")
            .in_("document_id", chunk)
            .order("id")
        )
        for row in arts:
            if row.get("storage_path"):
                artifact_docs.add(row["document_id"])

    for sid, years_map in by_school.items():
        for year, slot in years_map.items():
            doc_id = slot.get("document_id")
            if doc_id and doc_id in artifact_docs:
                slot["has_source_artifact"] = True
            slot["has_bytes"] = bool(
                slot["published"] and slot["sha256"] and slot["has_source_artifact"]
            )
    return by_school
