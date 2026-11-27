"""Row building for the scholarship directory (PRD 036 M2).

Pure functions, no network and no database. The loader (load.py) writes the
rows this module builds; the download builder (build_downloads.py) publishes
the same selection. The SQL cache in the migration mirrors `select_published`;
keep the two in step.
"""

from __future__ import annotations

import copy
import datetime as dt
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
SOURCE_REPOSITORY = "https://github.com/bolewood/quadfile"
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

# Coverage derivation. A benefit counts toward a full_* label only when it is a
# real scholarship (or restricted fund) with full coverage, no conditions_text,
# and an amount that is not capped. A waiver of tuition itself (category
# `tuition`, instrument `tuition_waiver`) counts the same way: the student is
# charged no tuition. Any other waiver, and the nonresident_differential
# category under any instrument, never counts, in any bracket and never as
# partial coverage. advertised_totals are never used.
NORMALIZED_COVERAGE = (
    "full_tuition",
    "full_tuition_fees",
    "tuition_housing_meals",
    "full_school_coa",
    "partial_or_fixed",
    "other",
)
_FULL_INSTRUMENTS = frozenset({"scholarship", "restricted_fund"})
_PARTIAL_INSTRUMENTS = frozenset({"scholarship", "cash_stipend", "restricted_fund"})
_PARTIAL_COVERAGES = frozenset({"partial", "fixed_amount", "variable"})
# A stipend unlocks full_school_coa only when its size is something the school stated.
_STATED_COVERAGES = frozenset({"full", "partial", "fixed_amount", "variable"})


def _tuition_waiver(b: Dict[str, Any]) -> bool:
    """A waiver of the tuition charge itself, not of the out-of-state differential."""
    return b.get("instrument") == "tuition_waiver" and b.get("category") == "tuition"


def _counted(b: Dict[str, Any]) -> bool:
    if b.get("category") == "nonresident_differential":
        return False
    return b.get("instrument") != "tuition_waiver" or _tuition_waiver(b)


def _uncapped(b: Dict[str, Any]) -> bool:
    """`full` with an up_to, at_least, range or approximate amount is not full."""
    amount = b.get("amount")
    return amount is None or amount.get("qualifier") in ("exact", "not_published")


def _full(b: Dict[str, Any], instruments: frozenset = _FULL_INSTRUMENTS) -> bool:
    return (
        _counted(b)
        and b.get("coverage") == "full"
        and (b.get("instrument") in instruments or _tuition_waiver(b))
        and not b.get("conditions_text")
        and _uncapped(b)
    )


def derive_normalized_coverage(benefits: Optional[List[Dict[str, Any]]]) -> Optional[str]:
    """Normalized coverage from a list of benefits (see derive_offers for scope).

    - `None` benefits means not documented: returns None (unknown is not no).
    - Brackets, highest first:
        full_school_coa        a full `cost_of_attendance` scholarship benefit; or
                               tuition + mandatory_fees + housing + meals + books
                               all full plus a stipend of stated size, because
                               cost of attendance also includes personal costs
        tuition_housing_meals  tuition + housing + meals full (fees optional)
        full_tuition_fees      tuition + mandatory_fees full
        full_tuition           tuition full
        partial_or_fixed       no bracket, but some counted benefit is partial,
                               fixed_amount, variable, or `full` yet capped,
                               conditional, or short of a bracket
        other                  anything else, including coverage `unknown`
    - `full` counts only for instrument scholarship or restricted_fund (cost of
      attendance: scholarship only), with no conditions_text and an amount that
      is null, exact or not_published.
    - A tuition_waiver on category `tuition` counts like a scholarship there. A
      waiver on any other category, and every nonresident_differential benefit,
      is ignored.
    """
    if benefits is None:
        return None
    if any(b.get("category") == "cost_of_attendance" and _full(b, frozenset({"scholarship"})) for b in benefits):
        return "full_school_coa"
    full = {b["category"] for b in benefits if _full(b)}
    has_stipend = any(
        b.get("category") == "stipend"
        and _counted(b)
        and b.get("instrument") in ("scholarship", "cash_stipend")
        and b.get("coverage") in _STATED_COVERAGES
        and not b.get("conditions_text")
        for b in benefits
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
        _counted(b)
        and (b.get("instrument") in _PARTIAL_INSTRUMENTS or _tuition_waiver(b))
        and (b.get("coverage") in _PARTIAL_COVERAGES or b.get("coverage") == "full")
        for b in benefits
    ):
        return "partial_or_fixed"
    return "other"


def derive_offers(offers: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Copy of the offers with `normalized_coverage` added to each.

    A tier nests under its parent (`parent_offer_id`) and may list only what it
    adds, so an offer's coverage is derived from its own benefits plus those of
    all its ancestors. An offer whose own `benefits` is null stays null (not
    documented). Differential waivers are excluded by the derivation.
    """
    by_id = {o["offer_id"]: o for o in offers}
    out = []
    for offer in offers:
        o = copy.deepcopy(offer)
        own = offer.get("benefits")
        if own is None:
            o["normalized_coverage"] = None
        else:
            combined = list(own)
            seen = {offer["offer_id"]}
            parent = offer.get("parent_offer_id")
            while parent and parent in by_id and parent not in seen:
                seen.add(parent)
                combined += by_id[parent].get("benefits") or []
                parent = by_id[parent].get("parent_offer_id")
            o["normalized_coverage"] = derive_normalized_coverage(combined)
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


def published_ids(doc: Dict[str, Any]) -> Set[str]:
    """version_ids the directory may serve: per supersedes chain, the newest
    member that is not `unverified`.

    Walk from each chain head back through `supersedes` until a version that is
    not unverified. An unverified correction therefore leaves the verified
    version it supersedes in place; a chain that is unverified throughout
    publishes nothing.
    """
    by_id = {v["version_id"]: v for v in doc["versions"]}
    out: Set[str] = set()
    for head in chain_heads(doc):
        cur = by_id[head]
        while cur["verification_status"] == "unverified" and cur.get("supersedes") in by_id:
            cur = by_id[cur["supersedes"]]
        if cur["verification_status"] != "unverified":
            out.add(cur["version_id"])
    return out


# ------------------------------------------------------------ freshness reference
# Python reference of the SQL functions in the migration, used for the tests and
# the SQL parity check. Keep in step with scholarship_freshness_status.


def cycle_year(d: dt.date) -> int:
    """Entry year whose cycle a date falls in: a class entering in fall Y is
    current from 1 July of Y-1, so July to December belong to year + 1."""
    return d.year + (1 if d.month >= 7 else 0)


def current_entry_year(today: dt.date) -> int:
    return cycle_year(today)


def cycle_basis(entry_year: Optional[int], cycle_through_date: Optional[str]) -> str:
    if entry_year is not None:
        return "entry_year"
    return "milestone_dates" if cycle_through_date else "none"


def year_not_stated_expiry(last_reviewed_at: str) -> dt.date:
    """The first 1 July strictly after the review date. A verified version with no
    entry_year and no dated milestone becomes past_cycle from this day."""
    return dt.date(cycle_year(dt.date.fromisoformat(last_reviewed_at)), 7, 1)


def freshness_status(
    entry_year: Optional[int],
    verification_status: str,
    cycle_through_date: Optional[str],
    last_reviewed_at: Optional[str],
    check_result: Optional[str],
    needs_review: Optional[bool],
    today: dt.date,
) -> str:
    """conflicting, past_cycle, current_cycle_unconfirmed, year_not_stated, else
    current_cycle_verified. See the migration comment and the view contract."""
    if verification_status == "conflicting" or check_result == "conflicting":
        return "conflicting"
    basis = cycle_basis(entry_year, cycle_through_date)
    if verification_status == "historical_only":
        return "past_cycle"
    if basis == "entry_year" and entry_year < current_entry_year(today):
        return "past_cycle"
    if basis == "milestone_dates" and dt.date.fromisoformat(cycle_through_date) < today:
        return "past_cycle"
    plain = verification_status == "verified" and not needs_review
    if basis == "none" and plain and last_reviewed_at and today >= year_not_stated_expiry(last_reviewed_at):
        return "past_cycle"  # a verified version that states no year ages out
    if bool(needs_review) or verification_status != "verified":
        return "current_cycle_unconfirmed"
    if basis == "none":
        return "year_not_stated"
    return "current_cycle_verified"


def rank_year(entry_year: Optional[int], cycle_through_date: Optional[str], source_retrieved_at: Optional[str]) -> Optional[int]:
    """Year used to pick a program's latest version. A dated version ranks by its
    entry_year; an undated one by the cycle its latest milestone falls in, else
    the cycle of the day its sources were retrieved."""
    if entry_year is not None:
        return entry_year
    for d in (cycle_through_date, source_retrieved_at):
        if d:
            return cycle_year(dt.date.fromisoformat(d))
    return None


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


def cycle_through_date(version: Dict[str, Any]) -> Optional[str]:
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


def build_version_row(
    doc: Dict[str, Any], version: Dict[str, Any], heads: Set[str], published: Set[str]
) -> Dict[str, Any]:
    offers = derive_offers(version["offers"])
    elig = [o.get("eligibility") or {} for o in version["offers"]]
    app = version.get("application") or {}
    retrieved = [s["retrieved_at"] for s in version["sources"]]
    return {
        "program_id": doc["program_id"],
        "version_id": version["version_id"],
        "supersedes": version.get("supersedes"),
        "is_chain_head": version["version_id"] in heads,
        "is_published": version["version_id"] in published,
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
        "statuses_required": _distinct(e.get("status_required_for_award") for e in elig),
        "need_roles": _distinct(o.get("need_role") for o in version["offers"]),
        "separate_application": app.get("separate_application"),
        "deadline_months": deadline_months(version),
        "key_deadline": key_deadline(version),
        "cycle_through_date": cycle_through_date(version),
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
        published = published_ids(doc)
        ds.programs.append(build_program_row(doc, shown))
        for version in doc["versions"]:
            ds.versions.append(build_version_row(doc, version, heads, published))
            ds.sources.extend(build_source_rows(doc, version))
    ds.programs.sort(key=lambda r: r["program_id"])
    ds.versions.sort(key=lambda r: (r["program_id"], r["version_id"]))
    ds.sources.sort(key=lambda r: (r["program_id"], r["version_id"], r["source_id"]))
    return ds


def select_published(ds: Dataset) -> List[Dict[str, Any]]:
    """The version the public view serves per program.

    Among the published versions (`is_published`: per supersedes chain, the
    newest member that is not `unverified`), the one with the latest rank year;
    see `rank_year`. A dated version beats an undated one of the same rank year;
    ties on version_id. Mirrors the SQL in scholarship_directory_cache.
    """
    best: Dict[str, Dict[str, Any]] = {}
    for row in ds.versions:
        if not row["is_published"]:
            continue
        cur = best.get(row["program_id"])
        if cur is None or _rank(row) < _rank(cur):
            best[row["program_id"]] = row
    return [best[pid] for pid in sorted(best)]


def _rank(row: Dict[str, Any]):
    year = rank_year(row["entry_year"], row["cycle_through_date"], row["source_retrieved_at"])
    return (year is None, -(year or 0), row["entry_year"] is None, row["version_id"])


def public_evidence(record: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Evidence locators for the public view: where on which source, never the excerpt."""
    return [
        {
            "field_path": e["field_path"],
            "source_ref": e["source_ref"],
            "locator": e["locator"],
            "value_status": e["value_status"],
        }
        for e in record.get("field_evidence") or []
    ]


def public_other_info(record: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Display-only other_info entries for the public view: the text, which source, and its URL.

    Never the quoted excerpt (same rule as public_evidence). Mirrors the SQL in
    scholarship_directory_cache: '[]' when the key is absent or null.
    """
    urls = {s["source_id"]: s["url"] for s in record.get("sources") or []}
    return [
        {"text": e["text"], "source_ref": e["source_ref"], "source_url": urls.get(e["source_ref"])}
        for e in record.get("other_info") or []
    ]


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
        "cycle_basis": cycle_basis(version["entry_year"], version["cycle_through_date"]),
        "cycle_through_date": version["cycle_through_date"],
        "last_reviewed_at": version["last_reviewed_at"],
        "reviewed_by": version["reviewed_by"],
        "owner_spot_checked": version["owner_spot_checked"],
        "program_status_for_entry": version["program_status_for_entry"],
        "coverages": version["coverages"],
        "selection_modes": version["selection_modes"],
        "residencies": version["residencies"],
        "national_merit_statuses": version["national_merit_statuses"],
        "statuses_required": version["statuses_required"],
        "need_roles": version["need_roles"],
        "separate_application": version["separate_application"],
        "deadline_months": version["deadline_months"],
        "key_deadline": version["key_deadline"],
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
        "evidence": public_evidence(record),
        "other_info": public_other_info(record),
    }
