"""Row building for the scholarship directory (PRD 036 M2).

Pure functions, no network and no database. The loader (load.py) writes the
rows this module builds; the download builder (build_downloads.py) publishes
the same selection. The SQL cache in the migration mirrors `select_published`;
keep the two in step.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Set

# One canonical attribution string. LICENSE, README, the migration, the view
# contract and every download carry it; test_load.py fails if any drifts.
ATTRIBUTION = (
    "Scholarship program data from collegedata.fyi (https://collegedata.fyi/scholarships), "
    "CC BY-SA 4.0. Terms as published by each school; see the source link on each record."
)
LICENSE_ID = "CC-BY-SA-4.0"
LICENSE_URL = "https://creativecommons.org/licenses/by-sa/4.0/"
SOURCE_REPOSITORY = "https://github.com/bolewood/collegedata-fyi"
# Bump when the download shape changes or a release is cut. Names the files:
# scholarships-v<N>.json and scholarships-v<N>.csv.zip.
DATASET_VERSION = 1

# Milestone kinds that count as deadlines for the deadline-month filter and the
# key deadline. Notification, interview and similar kinds do not.
DEADLINE_KINDS = frozenset(
    {
        "admission_deadline",
        "application_deadline",
        "nomination_deadline",
        "supporting_materials_deadline",
        "test_score_deadline",
    }
)

# Coverage derivation. A benefit counts toward tuition coverage only when it is
# a real scholarship. A tuition_waiver instrument or a nonresident_differential
# category never counts, in any bracket and never as partial coverage.
NORMALIZED_COVERAGE = (
    "full_tuition",
    "full_tuition_fees",
    "tuition_housing_meals",
    "full_school_coa",
    "partial_or_fixed",
    "other",
)
_PARTIAL_INSTRUMENTS = frozenset({"scholarship", "cash_stipend", "restricted_fund"})
_PARTIAL_COVERAGES = frozenset({"partial", "fixed_amount", "variable"})


def derive_normalized_coverage(benefits: Optional[List[Dict[str, Any]]]) -> Optional[str]:
    """Normalized coverage for one offer, from that offer's own benefits.

    - `None` benefits means not documented: returns None (unknown is not no).
    - Only `instrument: scholarship` + `coverage: full` benefits make a full
      bracket. Waivers, the nonresident differential, and `unknown` instruments
      are excluded everywhere.
    - Brackets, highest first:
        full_school_coa        tuition + mandatory_fees + housing + meals + books
                               all full, plus a stipend benefit (scholarship or
                               cash_stipend, any amount), because cost of
                               attendance also includes personal and travel costs
        tuition_housing_meals  tuition + housing + meals full (fees optional)
        full_tuition_fees      tuition + mandatory_fees full
        full_tuition           tuition full
        partial_or_fixed       no full tuition, but some non-waiver benefit is
                               partial, fixed_amount or variable
        other                  anything else, including coverage `unknown`
    - A child offer does not inherit from its parent.
    """
    if benefits is None:
        return None
    counted = [
        b
        for b in benefits
        if b.get("instrument") != "tuition_waiver" and b.get("category") != "nonresident_differential"
    ]
    full = {
        b["category"]
        for b in counted
        if b.get("instrument") == "scholarship" and b.get("coverage") == "full"
    }
    has_stipend = any(
        b.get("category") == "stipend" and b.get("instrument") in ("scholarship", "cash_stipend")
        for b in counted
    )
    if {"tuition", "mandatory_fees", "housing", "meals", "books"} <= full and has_stipend:
        return "full_school_coa"
    if {"tuition", "housing", "meals"} <= full:
        return "tuition_housing_meals"
    if {"tuition", "mandatory_fees"} <= full:
        return "full_tuition_fees"
    if "tuition" in full:
        return "full_tuition"
    if any(
        b.get("instrument") in _PARTIAL_INSTRUMENTS and b.get("coverage") in _PARTIAL_COVERAGES
        for b in counted
    ):
        return "partial_or_fixed"
    return "other"


def derive_offers(offers: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Copy of the offers with `normalized_coverage` added to each."""
    out = []
    for offer in offers:
        o = copy.deepcopy(offer)
        o["normalized_coverage"] = derive_normalized_coverage(offer.get("benefits"))
        out.append(o)
    return out


def chain_heads(doc: Dict[str, Any]) -> Set[str]:
    """version_ids that no other version supersedes.

    `supersedes` is a correction chain inside one entry_year (the validator
    guarantees that and at most one head per entry_year). The head is the
    version the directory serves for that year.
    """
    superseded = {v["supersedes"] for v in doc["versions"] if v.get("supersedes")}
    return {v["version_id"] for v in doc["versions"] if v["version_id"] not in superseded}


def _distinct(values: Iterable[Any]) -> List[Any]:
    return sorted({v for v in values if v is not None})


def _milestones(version: Dict[str, Any]) -> List[Dict[str, Any]]:
    app = version.get("application") or {}
    return app.get("milestones") or []


def deadline_months(version: Dict[str, Any]) -> List[int]:
    """Months of required or priority deadlines, dated or recurring."""
    months = set()
    for m in _milestones(version):
        if m["kind"] not in DEADLINE_KINDS or m["requirement"] not in ("required", "priority"):
            continue
        if m.get("date"):
            months.add(int(m["date"][5:7]))
        elif m.get("recurring"):
            months.add(int(m["recurring"]["month"]))
    return sorted(months)


def key_deadline(version: Dict[str, Any]) -> Optional[str]:
    """Earliest dated required deadline; if none, earliest dated priority one."""
    for requirement in ("required", "priority"):
        dates = [
            m["date"]
            for m in _milestones(version)
            if m["kind"] in DEADLINE_KINDS and m["requirement"] == requirement and m.get("date")
        ]
        if dates:
            return min(dates)
    return None


def latest_milestone_date(version: Dict[str, Any]) -> Optional[str]:
    dates = [m["date"] for m in _milestones(version) if m.get("date")]
    return max(dates) if dates else None


def participants(doc: Dict[str, Any]) -> List[Dict[str, str]]:
    """Every participating school; a single-school program lists just itself."""
    listed = doc.get("participating_schools") or []
    if listed:
        return [{"school_id": p["school_id"], "ipeds_id": p["ipeds_id"]} for p in listed]
    return [{"school_id": doc["school_id"], "ipeds_id": doc["ipeds_id"]}]


def participants_of(program_row: Dict[str, Any]) -> List[Dict[str, str]]:
    """Participants of a built program row, lead school first."""
    return program_row["participating_schools"]


def build_program_row(doc: Dict[str, Any], file_path: str) -> Dict[str, Any]:
    return {
        "program_id": doc["program_id"],
        "school_id": doc["school_id"],
        "ipeds_id": doc["ipeds_id"],
        "participating_schools": participants(doc),
        "applicable_campuses": doc.get("applicable_campuses") or [],
        "official_name": doc["official_name"],
        "aliases": doc.get("aliases") or [],
        "program_family": doc["program_family"],
        "awarding_authority": doc["awarding_authority"],
        "related_programs": doc.get("related_programs") or [],
        "status": doc["status"],
        "file_path": file_path,
    }


def build_version_row(doc: Dict[str, Any], version: Dict[str, Any], heads: Set[str]) -> Dict[str, Any]:
    offers = derive_offers(version["offers"])
    elig = [o.get("eligibility") or {} for o in version["offers"]]
    app = version.get("application") or {}
    retrieved = [s["retrieved_at"] for s in version["sources"]]
    return {
        "program_id": doc["program_id"],
        "version_id": version["version_id"],
        "supersedes": version.get("supersedes"),
        "is_chain_head": version["version_id"] in heads,
        "entry_year": version["entry_year"],
        "entry_year_label": version.get("entry_year_label"),
        "entry_terms": version.get("entry_terms") or [],
        "source_cohort_text": version.get("source_cohort_text"),
        "verification_status": version["verification_status"],
        "last_reviewed_at": version.get("last_reviewed_at"),
        "reviewed_by": version.get("reviewed_by"),
        "owner_spot_checked": version.get("owner_spot_checked"),
        "program_status_for_entry": version.get("program_status_for_entry"),
        "coverages": _distinct(o["normalized_coverage"] for o in offers),
        "selection_modes": _distinct(o.get("selection_mode") for o in version["offers"]),
        "residencies": _distinct(o.get("residency") for o in version["offers"]),
        "national_merit_statuses": _distinct(
            s for e in elig for s in (e.get("national_merit_statuses") or [])
        ),
        "need_roles": _distinct(o.get("need_role") for o in version["offers"]),
        "separate_application": app.get("separate_application"),
        "deadline_months": deadline_months(version),
        "key_deadline": key_deadline(version),
        "latest_milestone_date": latest_milestone_date(version),
        "source_retrieved_at": max(retrieved) if retrieved else None,
        "offers": offers,
        "record": version,
    }


def build_source_rows(doc: Dict[str, Any], version: Dict[str, Any]) -> List[Dict[str, Any]]:
    return [
        {
            "program_id": doc["program_id"],
            "version_id": version["version_id"],
            "source_id": s["source_id"],
            "url": s["url"],
            "authority": s["authority"],
            "retrieved_at": s["retrieved_at"],
            "content_sha256": s.get("content_sha256"),
            "archive_url": s.get("archive_url"),
        }
        for s in version["sources"]
    ]


@dataclass
class Dataset:
    programs: List[Dict[str, Any]] = field(default_factory=list)
    versions: List[Dict[str, Any]] = field(default_factory=list)
    sources: List[Dict[str, Any]] = field(default_factory=list)

    def program(self, program_id: str) -> Dict[str, Any]:
        return next(p for p in self.programs if p["program_id"] == program_id)


def build_dataset(docs: Dict[str, Dict[str, Any]], root: Optional[Path] = None) -> Dataset:
    """Rows for already validated docs, keyed by file path. Order is stable."""
    ds = Dataset()
    for path in sorted(docs):
        doc = docs[path]
        shown = path
        if root is not None:
            try:
                shown = Path(path).resolve().relative_to(root.resolve()).as_posix()
            except ValueError:
                shown = str(path)
        heads = chain_heads(doc)
        ds.programs.append(build_program_row(doc, shown))
        for version in doc["versions"]:
            ds.versions.append(build_version_row(doc, version, heads))
            ds.sources.extend(build_source_rows(doc, version))
    ds.programs.sort(key=lambda r: r["program_id"])
    ds.versions.sort(key=lambda r: (r["program_id"], r["version_id"]))
    ds.sources.sort(key=lambda r: (r["program_id"], r["version_id"], r["source_id"]))
    return ds


def select_published(ds: Dataset) -> List[Dict[str, Any]]:
    """The version the public view serves per program.

    Chain heads that are not `unverified`, latest entry_year first with a null
    entry_year last; ties on version_id. Mirrors the SQL in
    scholarship_directory_cache. An unverified correction at the head of a
    chain hides that entry year (the older verified version it supersedes is not
    a head); the next-latest year is served instead, if any.
    """
    best: Dict[str, Dict[str, Any]] = {}
    for row in ds.versions:
        if not row["is_chain_head"] or row["verification_status"] == "unverified":
            continue
        cur = best.get(row["program_id"])
        if cur is None or _rank(row) < _rank(cur):
            best[row["program_id"]] = row
    return [best[pid] for pid in sorted(best)]


def _rank(row: Dict[str, Any]):
    year = row["entry_year"]
    return (year is None, -(year or 0), row["version_id"])


def public_record(program: Dict[str, Any], version: Dict[str, Any], school: Dict[str, str]) -> Dict[str, Any]:
    """One public record: the view's columns that are not time-dependent."""
    record = version["record"]
    app = record.get("application")
    return {
        "program_id": program["program_id"],
        "school_id": school["school_id"],
        "ipeds_id": school["ipeds_id"],
        "participating_school_ids": [p["school_id"] for p in program["participating_schools"]],
        "official_name": program["official_name"],
        "aliases": program["aliases"],
        "program_family": program["program_family"],
        "awarding_authority": program["awarding_authority"],
        "program_status": program["status"],
        "applicable_campuses": program["applicable_campuses"],
        "related_programs": program["related_programs"],
        "version_id": version["version_id"],
        "entry_year": version["entry_year"],
        "entry_year_label": version["entry_year_label"],
        "entry_terms": version["entry_terms"],
        "source_cohort_text": version["source_cohort_text"],
        "verification_status": version["verification_status"],
        "last_reviewed_at": version["last_reviewed_at"],
        "reviewed_by": version["reviewed_by"],
        "owner_spot_checked": version["owner_spot_checked"],
        "program_status_for_entry": version["program_status_for_entry"],
        "coverages": version["coverages"],
        "selection_modes": version["selection_modes"],
        "residencies": version["residencies"],
        "national_merit_statuses": version["national_merit_statuses"],
        "need_roles": version["need_roles"],
        "separate_application": version["separate_application"],
        "deadline_months": version["deadline_months"],
        "key_deadline": version["key_deadline"],
        "latest_milestone_date": version["latest_milestone_date"],
        "source_retrieved_at": version["source_retrieved_at"],
        "offers": version["offers"],
        "application": app,
        "renewal_rules": record.get("renewal_rules"),
        "stacking_rules": record.get("stacking_rules"),
        "award_counts": record.get("award_counts") or [],
        "sources": [
            {
                "source_id": s["source_id"],
                "url": s["url"],
                "authority": s["authority"],
                "retrieved_at": s["retrieved_at"],
                "archive_url": s.get("archive_url"),
            }
            for s in sorted(record["sources"], key=lambda s: s["source_id"])  # the SQL orders by source_id too
        ],
    }
