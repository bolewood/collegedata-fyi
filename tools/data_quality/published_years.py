"""Paginated published-year coverage queries.

Shared by the kids worklist and the top-100 coverage scorer so those
tools cannot drift on what a published year means.
"""

from __future__ import annotations

from typing import Any


def fetch_published_years(
    sb, school_ids: list[str], years: list[str]
) -> dict[str, set[str]]:
    """Return {school_id: {years_present}} for published documents."""
    have: dict[str, set[str]] = {sid: set() for sid in school_ids}
    want = set(school_ids)
    year_set = set(years)
    page_size = 1000
    offset = 0
    while True:
        batch = (
            sb.table("cds_documents")
            .select("school_id, cds_year, participation_status")
            .in_("cds_year", years)
            .range(offset, offset + page_size - 1)
            .execute()
            .data
            or []
        )
        for row in batch:
            sid = row["school_id"]
            year = row["cds_year"]
            if (
                sid in want
                and year in year_set
                and row.get("participation_status") == "published"
            ):
                have[sid].add(year)
        if len(batch) < page_size:
            break
        offset += page_size
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
    page_size = 1000
    offset = 0
    while True:
        batch = (
            sb.table("cds_documents")
            .select(
                "id, school_id, cds_year, participation_status, source_sha256"
            )
            .in_("cds_year", years)
            .range(offset, offset + page_size - 1)
            .execute()
            .data
            or []
        )
        for row in batch:
            sid = row["school_id"]
            year = row["cds_year"]
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
        if len(batch) < page_size:
            break
        offset += page_size

    artifact_docs: set[str] = set()
    for i in range(0, len(doc_ids), 100):
        chunk = doc_ids[i : i + 100]
        art_offset = 0
        while True:
            arts = (
                sb.table("cds_artifacts")
                .select("document_id, storage_path, kind")
                .eq("kind", "source")
                .in_("document_id", chunk)
                .range(art_offset, art_offset + page_size - 1)
                .execute()
                .data
                or []
            )
            for row in arts:
                if row.get("storage_path"):
                    artifact_docs.add(row["document_id"])
            if len(arts) < page_size:
                break
            art_offset += page_size

    for sid, years_map in by_school.items():
        for year, slot in years_map.items():
            doc_id = slot.get("document_id")
            if doc_id and doc_id in artifact_docs:
                slot["has_source_artifact"] = True
            slot["has_bytes"] = bool(
                slot["published"] and slot["sha256"] and slot["has_source_artifact"]
            )
    return by_school
