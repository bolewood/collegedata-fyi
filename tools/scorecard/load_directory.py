#!/usr/bin/env python3
"""Refresh institution_directory from the College Scorecard
Most-Recent Institution-Level CSV.

PRD 015 M1. The directory is keyed by IPEDS UNITID and includes one
row per Title-IV institution in the loaded Scorecard vintage. The
``in_scope`` flag captures whether the row meets the MVP public
defaults (active, undergraduate-serving, four-year or two-year,
degree-granting); out-of-scope rows are still loaded but flagged
with an ``exclusion_reason``.

The loader also writes the slug crosswalk: every (ipeds_id, alias) →
school_id mapping needed to resolve search and prior-slug redirects.
Existing ``tools/finder/schools.yaml`` slugs are preserved when the
IPEDS ID matches; new Scorecard-only rows get a deterministic slug
from INSTNM with collision resolution (``-state`` → ``-city`` →
``-ipeds_id``).

Usage:
    # Dry run — parse, compute slugs, print summary, write nothing.
    python tools/scorecard/load_directory.py \\
      --csv ~/Downloads/Most-Recent-Cohorts-Institution.csv \\
      --previous-csv ~/Downloads/Previous-Most-Recent-Cohorts-Institution.csv \\
      --data-year 2022-23

    # Apply — reconcile directory + crosswalk, then refresh public coverage.
    python tools/scorecard/load_directory.py \\
      --csv ~/Downloads/Most-Recent-Cohorts-Institution.csv \\
      --previous-csv ~/Downloads/Previous-Most-Recent-Cohorts-Institution.csv \\
      --data-year 2022-23 \\
      --apply

Requirements:
  - pip install pandas pyyaml supabase python-dotenv
  - .env file at repo root with SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Optional

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SCHOOLS_YAML = REPO_ROOT / "tools" / "finder" / "schools.yaml"
MISSING_FROM_CURRENT_SCORECARD = "missing_from_current_scorecard"

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.finder.identity_guard import (  # noqa: E402
    DEFAULT_EXCEPTIONS as DEFAULT_IDENTITY_EXCEPTIONS,
    audit_school_identities,
    load_identity_exceptions,
    load_school_claims,
    official_records_from_directory_rows,
    school_claim_retired_alias_map,
    school_claim_slug_map,
)


# Scorecard CSV column → directory field. Source-of-truth list comes
# straight from PRD 015's directory data model. Keep this set distinct
# from refresh_summary.py's COLUMN_MAP — those columns are curated
# outcome metrics, not directory identity.
DIRECTORY_COLUMN_MAP: dict[str, str] = {
    "school_name":               "INSTNM",
    "city":                      "CITY",
    "state":                     "STABBR",
    "zip":                       "ZIP",
    "website_url":               "INSTURL",
    "undergraduate_enrollment":  "UGDS",
    "control":                   "CONTROL",
    "institution_level":         "ICLEVEL",
    "predominant_degree":        "PREDDEG",
    "highest_degree":            "HIGHDEG",
    "currently_operating":       "CURROPER",
    "main_campus":               "MAIN",
    "branch_count":              "NUMBRANCH",
    "latitude":                  "LATITUDE",
    "longitude":                 "LONGITUDE",
}

INT_COLS = {
    "undergraduate_enrollment",
    "control",
    "institution_level",
    "predominant_degree",
    "highest_degree",
    "branch_count",
}

NUMERIC_COLS = {"latitude", "longitude"}

BOOL_COLS = {"currently_operating", "main_campus"}


# In-scope filter, per PRD 015 "MVP Scope Decision". Fail conditions
# return the exclusion_reason that ends up persisted on the row.
def _scope_decision(row: dict[str, Any]) -> tuple[bool, Optional[str]]:
    if row.get("currently_operating") is False:
        return False, "closed"
    enr = row.get("undergraduate_enrollment")
    if enr is None or enr <= 0:
        return False, "no_undergraduate_enrollment"
    icl = row.get("institution_level")
    if icl not in (1, 2):
        return False, "not_two_or_four_year"
    pred = row.get("predominant_degree")
    if pred not in (2, 3, 4):
        return False, "non_degree_predominant"
    return True, None


def _coerce(value: Any, col: str) -> Any:
    """Mirror refresh_summary.py's _coerce semantics. Treat NULL,
    'NULL', and 'PrivacySuppressed' as missing; cast int / float per
    column's declared type."""
    if value is None or (isinstance(value, float) and value != value):
        return None
    if isinstance(value, str):
        s = value.strip()
        if s in {"", "NULL", "PrivacySuppressed"}:
            return None
        value = s
    if col in INT_COLS:
        try:
            return int(float(value))
        except (TypeError, ValueError):
            return None
    if col in NUMERIC_COLS:
        try:
            return float(value)
        except (TypeError, ValueError):
            return None
    if col in BOOL_COLS:
        try:
            return bool(int(float(value)))
        except (TypeError, ValueError):
            return None
    return value


def normalize_ipeds(unitid: Any) -> Optional[str]:
    """Zero-pad to six digits when possible. Same convention as
    refresh_summary.py — see that script for the rationale (silent
    LEFT JOIN misses if formats diverge)."""
    if unitid is None:
        return None
    if isinstance(unitid, float) and unitid != unitid:
        return None
    try:
        n = int(float(unitid))
    except (TypeError, ValueError):
        return None
    if n <= 0:
        return None
    return f"{n:06d}"


# Slug generation. Deterministic and reversible enough that an operator
# can predict a school's slug from its INSTNM and state without running
# the loader.
_SLUG_NONALNUM = re.compile(r"[^a-z0-9]+")


def base_slug(name: str) -> str:
    """Lowercase, replace runs of non-alphanumerics with single
    hyphens, strip leading/trailing hyphens. Empty result raises —
    callers must skip rows whose INSTNM produces no slug at all."""
    s = _SLUG_NONALNUM.sub("-", name.lower()).strip("-")
    if not s:
        raise ValueError(f"INSTNM produced an empty slug: {name!r}")
    return s


def state_suffix(state: Optional[str]) -> str:
    return (state or "").lower().strip()


def city_suffix(city: Optional[str]) -> str:
    return _SLUG_NONALNUM.sub("-", (city or "").lower()).strip("-")


def assign_slugs(
    rows: list[dict[str, Any]],
    schools_yaml_map: dict[str, str],
) -> tuple[dict[str, str], list[dict[str, Any]]]:
    """Two-pass slug assignment.

    Pass 1: claim all schools.yaml slugs (these are sacred). For
    Scorecard rows whose IPEDS appears in schools.yaml, use that slug.

    Pass 2: for remaining rows, compute base_slug. Any base_slug that
    collides with another row OR a claimed slug escalates to
    base-state, then base-state-city, then base-state-city-ipeds.

    Returns:
        (ipeds_id → school_id mapping for rows we slugged,
         list of collision-report entries for the summary)
    """
    assigned: dict[str, str] = {}
    claimed: set[str] = set()
    collisions: list[dict[str, Any]] = []

    # Pre-pass: detect schools.yaml self-collisions where multiple IPEDS
    # claim the same slug. Pre-existing data bug in tools/finder/schools.yaml
    # — 12 duplicated slugs spanning ~25 entries as of 2026-04-29
    # (bethel-university across 3 IPEDS, anderson-university across 2,
    # etc.). Pick the IPEDS with the largest UGDS as the canonical winner;
    # the losers fall through to Pass 2's auto-slug + collision tier
    # treatment. Their schools.yaml-claimed slug becomes a non-primary
    # alias in the crosswalk so existing search/redirect URLs keep working.
    by_yaml_slug: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        slug = schools_yaml_map.get(row["ipeds_id"])
        if slug:
            by_yaml_slug[slug].append(row)

    yaml_winners: dict[str, str] = {}  # ipeds_id → preserved slug
    yaml_demoted: dict[str, str] = {}  # ipeds_id → demoted yaml slug (becomes alias)
    for slug, claimants in by_yaml_slug.items():
        if len(claimants) == 1:
            yaml_winners[claimants[0]["ipeds_id"]] = slug
            continue
        # Collision. Sort by UGDS descending; tie-break on ipeds_id for determinism.
        ranked = sorted(
            claimants,
            key=lambda r: (-(r.get("undergraduate_enrollment") or 0), r["ipeds_id"]),
        )
        winner = ranked[0]
        yaml_winners[winner["ipeds_id"]] = slug
        for loser in ranked[1:]:
            yaml_demoted[loser["ipeds_id"]] = slug
            collisions.append(
                {
                    "ipeds_id": loser["ipeds_id"],
                    "school_name": loser["school_name"],
                    "base_slug": slug,
                    "resolved_slug": "(deferred to scorecard tier)",
                    "tier": "yaml_self_collision",
                    "winner_ipeds": winner["ipeds_id"],
                }
            )

    # Pass 1: assign winners. Losers stay unassigned and flow into Pass 2
    # where they get auto-slug treatment based on their INSTNM.
    for row in rows:
        ipeds = row["ipeds_id"]
        if ipeds in yaml_winners:
            slug = yaml_winners[ipeds]
            assigned[ipeds] = slug
            claimed.add(slug)
            row["_slug_source"] = "schools_yaml"
        elif ipeds in yaml_demoted:
            # Block the demoted yaml slug from being stolen by other rows
            # whose auto-base happens to match it — the winner already
            # claimed it.
            claimed.add(yaml_demoted[ipeds])

    # Pass 2: bucket remaining rows by base_slug, escalate collisions.
    pending = [r for r in rows if r["ipeds_id"] not in assigned]
    by_base: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in pending:
        try:
            row["_base_slug"] = base_slug(row["school_name"])
        except ValueError as e:
            row["_slug_error"] = str(e)
            continue
        by_base[row["_base_slug"]].append(row)

    for slug, group in by_base.items():
        # If only one row claims this base, and the slug is not already
        # claimed by schools.yaml, take it as-is.
        if len(group) == 1 and slug not in claimed:
            row = group[0]
            assigned[row["ipeds_id"]] = slug
            claimed.add(slug)
            row["_slug_source"] = "scorecard"
            continue

        # Collision (either group size > 1, or schools.yaml already
        # owns this slug). Escalate. First try base-state.
        unresolved = list(group)
        for tier_fn, tier_name in (
            (lambda r: f"{slug}-{state_suffix(r['state'])}".rstrip("-"), "state"),
            (
                lambda r: f"{slug}-{state_suffix(r['state'])}-{city_suffix(r['city'])}".rstrip("-"),
                "city",
            ),
            (
                lambda r: f"{slug}-{state_suffix(r['state'])}-{city_suffix(r['city'])}-{r['ipeds_id']}".rstrip("-"),
                "ipeds",
            ),
        ):
            still_colliding: list[dict[str, Any]] = []
            tier_buckets: dict[str, list[dict[str, Any]]] = defaultdict(list)
            for row in unresolved:
                tier_buckets[tier_fn(row)].append(row)
            for candidate, bucket in tier_buckets.items():
                if len(bucket) == 1 and candidate not in claimed:
                    row = bucket[0]
                    assigned[row["ipeds_id"]] = candidate
                    claimed.add(candidate)
                    row["_slug_source"] = "scorecard"
                    collisions.append(
                        {
                            "ipeds_id": row["ipeds_id"],
                            "school_name": row["school_name"],
                            "base_slug": slug,
                            "resolved_slug": candidate,
                            "tier": tier_name,
                        }
                    )
                else:
                    still_colliding.extend(bucket)
            unresolved = still_colliding
            if not unresolved:
                break

        # If anything is still colliding after the ipeds tier, the
        # caller has duplicate (ipeds_id, INSTNM, state, city) tuples,
        # which means the input CSV is corrupt. Fail loudly.
        if unresolved:
            raise RuntimeError(
                "slug assignment failed after all collision tiers; "
                f"unresolved rows: {[r['ipeds_id'] for r in unresolved]}"
            )

    return assigned, collisions


def load_schools_yaml(path: Path) -> dict[str, str]:
    """Return ipeds_id → school_id from schools.yaml. Skips entries
    without an ipeds_id (none currently, but the loader shouldn't
    crash if one shows up)."""
    return school_claim_slug_map(load_school_claims(path))


def audit_directory_identities(
    claims: Iterable[dict[str, str]],
    directory_rows: Iterable[dict[str, Any]],
    exceptions: Iterable[dict[str, str]] = (),
) -> dict[str, Any]:
    """Validate every curated UNITID claim against the incoming federal row."""
    return audit_school_identities(
        claims,
        official_records_from_directory_rows(directory_rows),
        exceptions,
    )


def build_directory_row(
    raw: dict[str, Any],
    data_year: str,
    previous_predominant_degree: Optional[int] = None,
) -> Optional[dict[str, Any]]:
    """Transform one Scorecard CSV row into a directory row, or None
    when UNITID is missing/invalid."""
    ipeds = normalize_ipeds(raw.get("UNITID"))
    if ipeds is None:
        return None
    out: dict[str, Any] = {
        "ipeds_id": ipeds,
        "scorecard_data_year": data_year,
        "directory_source": "scorecard",
    }
    for target, source in DIRECTORY_COLUMN_MAP.items():
        out[target] = _coerce(raw.get(source), target)
    if not out.get("school_name"):
        return None

    # PREDDEG is a derived annual classification, not a statement that the
    # institution stopped awarding degrees. The March 2026 Scorecard release
    # moved Spelman and dozens of other established degree-granting schools
    # from PREDDEG 2/3 to 1 for a single release while HIGHDEG still reported
    # an associate-or-higher award. When the operator supplies the immediately
    # previous release, keep its degree-predominant classification for this
    # narrow regression. Genuine closures, enrollment changes, level changes,
    # and schools whose HIGHDEG also falls below 2 still follow current data.
    if (
        out.get("predominant_degree") == 1
        and previous_predominant_degree in (2, 3, 4)
        and out.get("highest_degree") in (2, 3, 4)
    ):
        out["_current_predominant_degree"] = 1
        out["_previous_predominant_degree"] = previous_predominant_degree
        out["predominant_degree"] = previous_predominant_degree

    in_scope, reason = _scope_decision(out)
    out["in_scope"] = in_scope
    out["exclusion_reason"] = reason
    return out


def build_crosswalk_rows(
    directory_rows: list[dict[str, Any]],
    schools_yaml_map: dict[str, str],
    retired_aliases_by_ipeds: Optional[dict[str, list[str]]] = None,
) -> list[dict[str, Any]]:
    """One row per known alias. Each ipeds_id always has at least one
    primary row (its school_id). When a schools.yaml ID and the
    Scorecard auto-slug differ, both end up in the table — schools.yaml
    as primary, the auto-generated as a non-primary alias for redirect
    resolution. When schools.yaml self-collides (same slug claimed by
    multiple IPEDS), the loser IPEDS still get the schools.yaml slug
    as a non-primary alias so legacy URLs keep resolving."""
    out: list[dict[str, Any]] = []
    retired_aliases_by_ipeds = retired_aliases_by_ipeds or {}
    for row in directory_rows:
        ipeds = row["ipeds_id"]
        primary = row["school_id"]
        yaml_slug = schools_yaml_map.get(ipeds)
        retired_aliases = set(retired_aliases_by_ipeds.get(ipeds, []))
        # Source tag: schools_yaml when this ipeds's primary equals its
        # yaml claim. If yaml-demoted (yaml_slug exists but primary is
        # auto-generated), the primary is scorecard-source.
        source = "schools_yaml" if yaml_slug and yaml_slug == primary else "scorecard"
        out.append(
            {
                "ipeds_id": ipeds,
                "school_id": primary,
                "alias": primary,
                "source": source,
                "is_primary": True,
            }
        )
        # Auto-generated slug as a non-primary alias when the curated
        # schools.yaml slug differs from what the loader would compute
        # — useful when an operator searches by INSTNM tokens.
        if yaml_slug and yaml_slug == primary:
            try:
                auto = base_slug(row["school_name"])
            except ValueError:
                auto = None
            if auto and auto != primary and auto not in retired_aliases:
                out.append(
                    {
                        "ipeds_id": ipeds,
                        "school_id": primary,
                        "alias": auto,
                        "source": "scorecard",
                        "is_primary": False,
                    }
                )
        # Yaml-demoted ipeds: keep the schools.yaml-claimed slug as a
        # non-primary alias so search and any prior public links to
        # it still resolve to this institution.
        if yaml_slug and yaml_slug != primary:
            out.append(
                {
                    "ipeds_id": ipeds,
                    "school_id": primary,
                    "alias": yaml_slug,
                    "source": "schools_yaml",
                    "is_primary": False,
                }
            )
        # Retired public routes are durable corpus configuration. In
        # particular, an annual Scorecard refresh must not recreate an
        # official-name slug as a searchable alias after a repair retired it.
        for alias in sorted(retired_aliases):
            out.append(
                {
                    "ipeds_id": ipeds,
                    "school_id": primary,
                    "alias": alias,
                    "source": "redirect",
                    "is_primary": False,
                }
            )
    return out


def fetch_existing_redirect_alias_keys(
    client: Any, page_size: int = 1000
) -> set[tuple[str, str]]:
    """Fetch live redirect keys so a refresh cannot overwrite provenance."""
    keys: set[tuple[str, str]] = set()
    offset = 0
    while True:
        response = (
            client.table("institution_slug_crosswalk")
            .select("ipeds_id,alias")
            .eq("source", "redirect")
            .order("ipeds_id")
            .order("alias")
            .range(offset, offset + page_size - 1)
            .execute()
        )
        batch = response.data or []
        keys.update(
            (str(row["ipeds_id"]), str(row["alias"]))
            for row in batch
            if row.get("ipeds_id") and row.get("alias")
        )
        if len(batch) < page_size:
            break
        offset += page_size
    return keys


def preserve_existing_redirect_aliases(
    crosswalk_rows: list[dict[str, Any]],
    existing_redirect_keys: set[tuple[str, str]],
) -> tuple[list[dict[str, Any]], int]:
    """Keep live redirects intact and reject a redirect becoming primary."""
    conflicts = [
        row
        for row in crosswalk_rows
        if (row["ipeds_id"], row["alias"]) in existing_redirect_keys
        and row["source"] != "redirect"
    ]
    primary_conflicts = [row for row in conflicts if row["is_primary"]]
    if primary_conflicts:
        rendered = ", ".join(
            f"{row['ipeds_id']}:{row['alias']}" for row in primary_conflicts
        )
        raise ValueError(
            "Scorecard refresh would promote retired alias(es) to primary: "
            f"{rendered}. Add durable retired_aliases/canonical slug claims "
            "to schools.yaml before applying."
        )

    protected_keys = {
        (row["ipeds_id"], row["alias"]) for row in conflicts
    }
    return (
        [
            row
            for row in crosswalk_rows
            if (row["ipeds_id"], row["alias"]) not in protected_keys
            or row["source"] == "redirect"
        ],
        len(protected_keys),
    )


def required_scorecard_columns() -> set[str]:
    return {"UNITID"} | set(DIRECTORY_COLUMN_MAP.values())


def previous_predominant_degrees(df: Any) -> dict[str, int]:
    """Return normalized UNITID -> PREDDEG for a prior Scorecard release."""
    required = {"UNITID", "PREDDEG"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(
            f"Previous Scorecard CSV is missing required columns: {sorted(missing)}"
        )

    result: dict[str, int] = {}
    for raw in df.to_dict(orient="records"):
        ipeds_id = normalize_ipeds(raw.get("UNITID"))
        preddeg = _coerce(raw.get("PREDDEG"), "predominant_degree")
        if ipeds_id is not None and preddeg is not None:
            result[ipeds_id] = preddeg
    return result


def directory_refresh_delta(
    existing_rows: Iterable[dict[str, Any]],
    incoming_rows: Iterable[dict[str, Any]],
) -> dict[str, Any]:
    """Describe public-scope changes before a directory refresh is applied.

    Public scope mirrors one Scorecard vintage rather than appending forever.
    This comparison makes scope changes reviewable and identifies rows that
    disappeared from the incoming vintage so they can be retained for aliases
    while hidden from current public search and coverage.
    """
    existing = {row["ipeds_id"]: row for row in existing_rows}
    incoming = {row["ipeds_id"]: row for row in incoming_rows}

    def transition(
        ipeds_id: str,
        old: dict[str, Any],
        new: dict[str, Any],
    ) -> dict[str, Any]:
        return {
            "ipeds_id": ipeds_id,
            "school_name": new.get("school_name") or old.get("school_name"),
            "old_reason": old.get("exclusion_reason"),
            "new_reason": new.get("exclusion_reason"),
            "old_predominant_degree": old.get("predominant_degree"),
            "new_predominant_degree": new.get("predominant_degree"),
            "old_undergraduate_enrollment": old.get("undergraduate_enrollment"),
            "new_undergraduate_enrollment": new.get("undergraduate_enrollment"),
        }

    entering_scope: list[dict[str, Any]] = []
    leaving_scope: list[dict[str, Any]] = []
    for ipeds_id in existing.keys() & incoming.keys():
        old = existing[ipeds_id]
        new = incoming[ipeds_id]
        if not old.get("in_scope") and new.get("in_scope"):
            entering_scope.append(transition(ipeds_id, old, new))
        elif old.get("in_scope") and not new.get("in_scope"):
            leaving_scope.append(transition(ipeds_id, old, new))

    entering_scope.sort(
        key=lambda row: (
            -(row.get("new_undergraduate_enrollment") or 0),
            row.get("school_name") or "",
        )
    )
    leaving_scope.sort(
        key=lambda row: (
            -(row.get("old_undergraduate_enrollment") or 0),
            row.get("school_name") or "",
        )
    )

    missing_ipeds_ids = sorted(existing.keys() - incoming.keys())
    new_ipeds_ids = sorted(incoming.keys() - existing.keys())
    return {
        "existing_rows": len(existing),
        "incoming_rows": len(incoming),
        "new_rows": len(new_ipeds_ids),
        "missing_rows": len(missing_ipeds_ids),
        "entering_scope": len(entering_scope),
        "leaving_scope": len(leaving_scope),
        "entering_scope_old_reasons": dict(
            Counter(row["old_reason"] for row in entering_scope)
        ),
        "leaving_scope_new_reasons": dict(
            Counter(row["new_reason"] for row in leaving_scope)
        ),
        "new_ipeds_ids": new_ipeds_ids,
        "missing_ipeds_ids": missing_ipeds_ids,
        "entering_scope_rows": entering_scope,
        "leaving_scope_rows": leaving_scope,
    }


def fetch_existing_directory_rows(client: Any, page_size: int = 1000) -> list[dict[str, Any]]:
    """Fetch the complete live directory with stable PostgREST pagination."""
    rows: list[dict[str, Any]] = []
    offset = 0
    while True:
        response = (
            client.table("institution_directory")
            .select(
                "ipeds_id,school_name,in_scope,exclusion_reason,"
                "predominant_degree,undergraduate_enrollment"
            )
            .order("ipeds_id")
            .range(offset, offset + page_size - 1)
            .execute()
        )
        batch = response.data or []
        rows.extend(batch)
        if len(batch) < page_size:
            break
        offset += page_size
    return rows


def printable_refresh_delta(delta: dict[str, Any], sample_size: int = 20) -> dict[str, Any]:
    """Keep the operator report compact while retaining high-impact samples."""
    compact = {
        key: value
        for key, value in delta.items()
        if key not in {
            "new_ipeds_ids",
            "missing_ipeds_ids",
            "entering_scope_rows",
            "leaving_scope_rows",
        }
    }
    compact.update(
        {
            "new_ipeds_ids_sample": delta["new_ipeds_ids"][:sample_size],
            "missing_ipeds_ids_sample": delta["missing_ipeds_ids"][:sample_size],
            "entering_scope_sample": delta["entering_scope_rows"][:sample_size],
            "leaving_scope_sample": delta["leaving_scope_rows"][:sample_size],
        }
    )
    return compact


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csv", required=True, help="Path to Most-Recent-Cohorts-Institution.csv")
    parser.add_argument(
        "--previous-csv",
        help=(
            "Immediately previous complete Most-Recent Institution CSV. When "
            "provided, stabilizes one-release PREDDEG 2/3/4 -> 1 regressions "
            "only while the current HIGHDEG remains 2/3/4."
        ),
    )
    parser.add_argument("--data-year", required=True, help="Scorecard vintage, e.g. 2022-23")
    parser.add_argument("--schools-yaml", default=str(DEFAULT_SCHOOLS_YAML),
                        help="Path to schools.yaml for slug preservation (default: tools/finder/schools.yaml)")
    parser.add_argument(
        "--identity-exceptions",
        default=str(DEFAULT_IDENTITY_EXCEPTIONS),
        help=(
            "Exact reviewed identity exceptions. Mismatches still fail closed; "
            "there is no ignore flag."
        ),
    )
    parser.add_argument("--apply", action="store_true",
                        help="Write to Supabase. Without this flag the loader is a dry run that prints the summary only.")
    parser.add_argument(
        "--audit-live",
        action="store_true",
        help="Compare the incoming vintage with the live directory without writing",
    )
    parser.add_argument("--summary-out", default=None,
                        help="Optional path to write the refresh summary as JSON. Defaults to scratch/scorecard/directory-refresh-<data_year>.json")
    parser.add_argument("--env", default=str(REPO_ROOT / ".env"), help=".env path")
    parser.add_argument("--batch-size", type=int, default=500, help="Upsert batch size")
    parser.add_argument(
        "--max-missing",
        type=int,
        default=250,
        help=(
            "Abort --apply when more than this many live UNITIDs are absent "
            "from the incoming full vintage (default: 250)"
        ),
    )
    args = parser.parse_args()

    try:
        import pandas as pd
    except ImportError:
        print("pandas not installed. pip install pandas", file=sys.stderr)
        return 1

    csv_path = Path(args.csv).expanduser()
    if not csv_path.exists():
        print(f"CSV not found: {csv_path}", file=sys.stderr)
        return 1

    yaml_path = Path(args.schools_yaml).expanduser()
    if not yaml_path.is_file():
        print(
            f"Refusing to continue: schools.yaml not found: {yaml_path}",
            file=sys.stderr,
        )
        return 4
    try:
        school_claims = load_school_claims(yaml_path)
    except Exception as exc:
        print(
            f"Refusing to continue: invalid schools.yaml identity corpus: {exc}",
            file=sys.stderr,
        )
        return 4
    if not school_claims:
        print(
            "Refusing to continue: schools.yaml identity corpus is empty",
            file=sys.stderr,
        )
        return 4
    schools_yaml_map = school_claim_slug_map(school_claims)
    retired_aliases_by_ipeds = school_claim_retired_alias_map(school_claims)
    print(f"Loaded {len(schools_yaml_map)} schools.yaml slug claims", file=sys.stderr)

    print(f"Reading {csv_path} ...", file=sys.stderr)
    df = pd.read_csv(csv_path, dtype=str, low_memory=False)
    print(f"  {len(df):,} rows x {len(df.columns):,} cols", file=sys.stderr)

    # Schema-drift guard. Fail loud if Scorecard renamed a directory
    # column between releases.
    required = required_scorecard_columns()
    missing = required - set(df.columns)
    if missing:
        print(
            f"Scorecard CSV is missing required columns: {sorted(missing)}",
            file=sys.stderr,
        )
        return 2

    prior_predominant_by_ipeds: dict[str, int] = {}
    previous_csv_path: Optional[Path] = None
    if args.previous_csv:
        previous_csv_path = Path(args.previous_csv).expanduser()
        if not previous_csv_path.exists():
            print(f"Previous CSV not found: {previous_csv_path}", file=sys.stderr)
            return 1
        print(f"Reading previous release {previous_csv_path} ...", file=sys.stderr)
        previous_df = pd.read_csv(
            previous_csv_path,
            dtype=str,
            usecols=lambda column: column in {"UNITID", "PREDDEG"},
            low_memory=False,
        )
        try:
            prior_predominant_by_ipeds = previous_predominant_degrees(previous_df)
        except ValueError as exc:
            print(str(exc), file=sys.stderr)
            return 2
        print(
            f"  {len(prior_predominant_by_ipeds):,} prior PREDDEG values",
            file=sys.stderr,
        )

    # Build directory rows. Skip rows missing UNITID or INSTNM.
    rows: list[dict[str, Any]] = []
    skipped_no_ipeds = 0
    skipped_no_name = 0
    for raw in df.to_dict(orient="records"):
        ipeds = normalize_ipeds(raw.get("UNITID"))
        if ipeds is None:
            skipped_no_ipeds += 1
            continue
        row = build_directory_row(
            raw,
            args.data_year,
            prior_predominant_by_ipeds.get(ipeds),
        )
        if row is None:
            skipped_no_name += 1
            continue
        rows.append(row)

    # Identity guard. Slugs are allowed to differ from official institution
    # names, but the UNITID claim must share either the official normalized
    # name or website domain. Run before slug assignment and before any live
    # client is constructed so a bad corpus mapping cannot reach Supabase.
    identity_exceptions_path = Path(args.identity_exceptions).expanduser()
    identity_exceptions = load_identity_exceptions(identity_exceptions_path)
    identity_audit = audit_directory_identities(
        school_claims, rows, identity_exceptions
    )
    print(
        "Identity guard: "
        f"{identity_audit['matched']:,} matched, "
        f"{identity_audit['excepted']:,} excepted, "
        f"{len(identity_audit['warnings']):,} warnings, "
        f"{len(identity_audit['errors']):,} errors",
        file=sys.stderr,
    )
    for issue in identity_audit["warnings"]:
        print(f"  WARNING {json.dumps(issue, sort_keys=True)}", file=sys.stderr)
    if identity_audit["errors"]:
        for issue in identity_audit["errors"]:
            print(f"  ERROR {json.dumps(issue, sort_keys=True)}", file=sys.stderr)
        print(
            "Refusing to continue: schools.yaml identity claims do not match "
            "the incoming Scorecard institution file.",
            file=sys.stderr,
        )
        return 4

    # Slug assignment. We slug every row, in-scope or not, so the
    # crosswalk includes inactive/closed institutions too (they may
    # still need search redirects).
    assigned, collisions = assign_slugs(rows, schools_yaml_map)
    for row in rows:
        row["school_id"] = assigned.get(row["ipeds_id"])

    # Drop rows we couldn't slug. Per PRD 015 "Do not publish directory
    # rows that fail slug assignment" — these are typically rows whose
    # INSTNM normalized to an empty string.
    no_slug = [r for r in rows if not r.get("school_id")]
    rows = [r for r in rows if r.get("school_id")]

    predominant_degree_stabilizations = [
        {
            "ipeds_id": row["ipeds_id"],
            "school_name": row["school_name"],
            "current_predominant_degree": row["_current_predominant_degree"],
            "previous_predominant_degree": row["_previous_predominant_degree"],
            "current_highest_degree": row.get("highest_degree"),
            "undergraduate_enrollment": row.get("undergraduate_enrollment"),
        }
        for row in rows
        if "_previous_predominant_degree" in row
    ]
    predominant_degree_stabilizations.sort(
        key=lambda row: (
            -(row.get("undergraduate_enrollment") or 0),
            row["school_name"],
        )
    )

    # Strip transient reconciliation/slug-assignment fields before persistence.
    for row in rows:
        row.pop("_slug_source", None)
        row.pop("_base_slug", None)
        row.pop("_slug_error", None)
        row.pop("_current_predominant_degree", None)
        row.pop("_previous_predominant_degree", None)

    crosswalk_rows = build_crosswalk_rows(
        rows, schools_yaml_map, retired_aliases_by_ipeds
    )

    in_scope_rows = [r for r in rows if r["in_scope"]]
    excluded_rows = [r for r in rows if not r["in_scope"]]
    no_url_rows = [r for r in in_scope_rows if not (r.get("website_url") or "").strip()]
    exclusion_breakdown = Counter(r["exclusion_reason"] for r in excluded_rows)

    summary: dict[str, Any] = {
        "data_year": args.data_year,
        "csv_path": str(csv_path),
        "previous_csv_path": str(previous_csv_path) if previous_csv_path else None,
        "total_csv_rows": int(len(df)),
        "skipped_no_ipeds": skipped_no_ipeds,
        "skipped_no_name": skipped_no_name,
        "skipped_no_slug": len(no_slug),
        "directory_rows": len(rows),
        "in_scope_rows": len(in_scope_rows),
        "excluded_rows": len(excluded_rows),
        "exclusion_breakdown": dict(exclusion_breakdown),
        "in_scope_without_website_url": len(no_url_rows),
        "slug_collisions_resolved": len(collisions),
        "slug_collisions_by_tier": dict(Counter(c["tier"] for c in collisions)),
        "schools_yaml_preserved": sum(1 for r in rows if r["ipeds_id"] in schools_yaml_map),
        "identity_claims_matched": identity_audit["matched"],
        "identity_claims_excepted": identity_audit["excepted"],
        "identity_claim_warnings": len(identity_audit["warnings"]),
        "crosswalk_rows": len(crosswalk_rows),
        "predominant_degree_stabilizations": len(
            predominant_degree_stabilizations
        ),
        "predominant_degree_stabilizations_by_previous_value": dict(
            Counter(
                row["previous_predominant_degree"]
                for row in predominant_degree_stabilizations
            )
        ),
    }

    print("\n=== Refresh summary ===", file=sys.stderr)
    print(json.dumps(summary, indent=2), file=sys.stderr)

    if collisions:
        print("\n=== Sample slug collisions (first 10) ===", file=sys.stderr)
        for c in collisions[:10]:
            print(
                f"  {c['ipeds_id']} {c['school_name']!r}: "
                f"{c['base_slug']} -> {c['resolved_slug']} (tier={c['tier']})",
                file=sys.stderr,
            )

    if predominant_degree_stabilizations:
        print(
            "\n=== Stabilized PREDDEG regressions (first 20) ===",
            file=sys.stderr,
        )
        for row in predominant_degree_stabilizations[:20]:
            print(
                f"  {row['ipeds_id']} {row['school_name']!r}: "
                f"current={row['current_predominant_degree']} -> "
                f"previous={row['previous_predominant_degree']} "
                f"(HIGHDEG={row['current_highest_degree']})",
                file=sys.stderr,
            )

    summary_path = Path(args.summary_out) if args.summary_out else (
        REPO_ROOT / "scratch" / "scorecard" / f"directory-refresh-{args.data_year}.json"
    )
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(
        json.dumps(
            {
                "summary": summary,
                "collisions": collisions,
                "predominant_degree_stabilizations": predominant_degree_stabilizations,
            },
            indent=2,
        )
        + "\n"
    )
    print(f"\nWrote summary to {summary_path}", file=sys.stderr)

    if not args.apply and not args.audit_live:
        print(
            "\nDry run — no writes. Pass --audit-live to preview the production "
            "scope delta or --apply to reconcile it.",
            file=sys.stderr,
        )
        return 0

    # Live audit/apply path. Service-role client; same pattern as refresh_summary.py.
    from supabase import create_client  # type: ignore

    env_path = Path(args.env).expanduser()
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))

    if not os.environ.get("SUPABASE_URL") or not os.environ.get("SUPABASE_SERVICE_ROLE_KEY"):
        print("SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY not set", file=sys.stderr)
        return 1

    client = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_ROLE_KEY"])

    existing_rows = fetch_existing_directory_rows(client)
    delta = directory_refresh_delta(existing_rows, rows)
    summary["live_delta"] = delta
    summary_path.write_text(
        json.dumps(
            {
                "summary": summary,
                "collisions": collisions,
                "predominant_degree_stabilizations": predominant_degree_stabilizations,
            },
            indent=2,
        )
        + "\n"
    )
    print("\n=== Live directory delta ===", file=sys.stderr)
    print(json.dumps(printable_refresh_delta(delta), indent=2), file=sys.stderr)
    if delta["missing_rows"] > args.max_missing:
        print(
            f"Refusing to continue: {delta['missing_rows']:,} live UNITIDs are absent "
            f"from the incoming vintage, above --max-missing={args.max_missing:,}. "
            "Confirm that this is the complete institution-level file, then "
            "raise --max-missing deliberately if the release is valid.",
            file=sys.stderr,
        )
        return 3

    if not args.apply:
        print("\nLive audit complete — no writes.", file=sys.stderr)
        return 0

    # Existing redirects remain redirects even if they have not yet been
    # promoted into schools.yaml. This protects operator-created legacy URLs
    # while the corpus is brought up to date.
    existing_redirect_keys = fetch_existing_redirect_alias_keys(client)
    try:
        crosswalk_rows, protected_redirect_count = preserve_existing_redirect_aliases(
            crosswalk_rows, existing_redirect_keys
        )
    except ValueError as exc:
        print(f"Refusing to continue: {exc}", file=sys.stderr)
        return 4
    if protected_redirect_count:
        print(
            f"Preserving {protected_redirect_count:,} live redirect alias(es) from "
            "Scorecard overwrite.",
            file=sys.stderr,
        )

    refreshed_at = datetime.now(timezone.utc).isoformat()
    for row in rows:
        row["refreshed_at"] = refreshed_at

    print(f"\nUpserting {len(rows)} institution_directory rows in batches of {args.batch_size}...", file=sys.stderr)
    for i in range(0, len(rows), args.batch_size):
        batch = rows[i : i + args.batch_size]
        client.table("institution_directory").upsert(batch, on_conflict="ipeds_id").execute()
        print(f"  {i + len(batch):,}/{len(rows):,}", file=sys.stderr)

    print(f"\nUpserting {len(crosswalk_rows)} institution_slug_crosswalk rows...", file=sys.stderr)
    for i in range(0, len(crosswalk_rows), args.batch_size):
        batch = crosswalk_rows[i : i + args.batch_size]
        client.table("institution_slug_crosswalk").upsert(
            batch, on_conflict="ipeds_id,alias"
        ).execute()
        print(f"  {i + len(batch):,}/{len(crosswalk_rows):,}", file=sys.stderr)

    missing_ipeds_ids = delta["missing_ipeds_ids"]
    if missing_ipeds_ids:
        print(
            f"\nMarking {len(missing_ipeds_ids):,} rows absent from this Scorecard "
            "vintage as out of scope...",
            file=sys.stderr,
        )
        for i in range(0, len(missing_ipeds_ids), args.batch_size):
            batch = missing_ipeds_ids[i : i + args.batch_size]
            (
                client.table("institution_directory")
                .update(
                    {
                        "in_scope": False,
                        "exclusion_reason": MISSING_FROM_CURRENT_SCORECARD,
                        "refreshed_at": refreshed_at,
                    }
                )
                .in_("ipeds_id", batch)
                .execute()
            )
            print(f"  {i + len(batch):,}/{len(missing_ipeds_ids):,}", file=sys.stderr)

    print("\nRefreshing institution_cds_coverage...", file=sys.stderr)
    coverage_response = client.rpc("refresh_institution_cds_coverage").execute()
    if coverage_response.data:
        print(json.dumps(coverage_response.data, indent=2), file=sys.stderr)

    print("\nDone.", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
