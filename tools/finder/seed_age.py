#!/usr/bin/env python3
"""Date every discovery seed by the last new CDS year it produced (#462).

A seed that has not produced a new CDS year within one cycle is suspect,
whatever kind of URL it is: one file, listing page, blocked listing, or a
page whose relative links never resolved (#457). `stuck_pdf_seeds.py` only
looks at one-file seeds. This module looks at every school that has a seed.

For each such school it derives, from live published documents in
`cds_manifest`:

- `newest_year`: the newest valid filed year (`canonical_year`), else None.
  `unknown` and malformed values are not years (`unknown` sorts above every
  real year as text, so years are compared by integer start year only).
- `newest_year_first_seen`: the earliest `discovered_at` among live
  documents filed under that newest year. If any of those documents has no
  `discovered_at`, the date is unknown (None, `first_seen_known` False)
  rather than a guess.
- `behind_cycle`: newest valid year is older than the current CDS year
  (`cds_freshness_floor`, the Python copy in `tools/ops/discovery_renewal.py`),
  or there is no valid year at all.

Operative rule today: the year test. The archive only began in April 2026,
so first-seen dates cannot yet show a year-long gap between new years. The
date is reported so the age becomes usable as history accrues; no decision
here depends on it.

`seeds_without_new_year` is the number of schools with a seed (any kind)
that are behind the cycle, broken down by seed kind. Every school with a
seed lands in exactly one kind, and `check_accounting` raises if the kinds
do not add up to the total.

Standalone use (reads production through PostgREST, narrow `select=`):
    python tools/finder/seed_age.py --anon-key "$NEXT_PUBLIC_SUPABASE_ANON_KEY"
    python tools/finder/seed_age.py --manifest-json snapshot.json
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import asdict, dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

# One copy of the mechanism: the year parser, the freshness floor, the
# manifest paging helpers and the seed-kind rule all live in the renewal
# module (PR #474). This file imports only once that module is on main.
from tools.ops.discovery_renewal import (  # noqa: E402
    DEFAULT_API,
    DEFAULT_SCHOOLS_YAML,
    VALID_PARTICIPATION,
    RenewalError,
    _parse_ts,
    cds_freshness_floor,
    check_floor_agrees,
    fetch_live_manifest,
    fetch_sql_floor,
    format_year,
    load_schools,
    parse_year,
    seed_for,
)

SEED_KINDS = ("one_file", "listing_page")
# Fewer live schools than this means the read was not what we think it is.
MIN_SCHOOLS_WITH_DOCS = 200


@dataclass
class SeedAge:
    school_id: str
    seed_url: str
    seed_kind: str
    newest_year: str | None
    newest_year_first_seen: str | None
    first_seen_known: bool
    behind_cycle: bool


def newest_year_info(
    rows: list[dict[str, Any]],
) -> dict[str, tuple[int, datetime | None, bool]]:
    """Per school: (newest valid start year, earliest discovered_at, all dated).

    Only live published documents count. `first_seen` is the minimum
    `discovered_at` over documents filed under the newest year; `all dated`
    is False when any of them has no `discovered_at`, in which case the
    first-seen date is reported as unknown.
    """
    best: dict[str, int] = {}
    for row in rows:
        if row.get("removed_at") or row.get("participation_status") != VALID_PARTICIPATION:
            continue
        sid = row.get("school_id")
        year = parse_year(row.get("canonical_year"))
        if not sid or year is None:
            continue
        if year > best.get(sid, -1):
            best[sid] = year
    seen: dict[str, datetime | None] = {}
    dated: dict[str, bool] = {sid: True for sid in best}
    for row in rows:
        if row.get("removed_at") or row.get("participation_status") != VALID_PARTICIPATION:
            continue
        sid = row.get("school_id")
        if sid not in best or parse_year(row.get("canonical_year")) != best[sid]:
            continue
        ts = _parse_ts(row.get("discovered_at"))
        if ts is None:
            dated[sid] = False
            continue
        if seen.get(sid) is None or ts < seen[sid]:  # type: ignore[operator]
            seen[sid] = ts
    return {sid: (best[sid], seen.get(sid), dated[sid]) for sid in best}


def compute_seed_ages(
    schools: dict[str, dict[str, Any]],
    rows: list[dict[str, Any]],
    as_of: date,
) -> list[SeedAge]:
    """One SeedAge per school that has a seed, sorted by school id."""
    floor = parse_year(cds_freshness_floor(as_of))
    if floor is None:
        raise RenewalError("freshness floor is not a CDS year")
    info = newest_year_info(rows)
    out: list[SeedAge] = []
    for sid in sorted(schools):
        url, kind = seed_for(schools[sid])
        if kind == "no_seed":
            continue
        if sid in info:
            start, first_seen, all_dated = info[sid]
            known = all_dated and first_seen is not None
            out.append(
                SeedAge(
                    sid, url, kind, format_year(start),
                    first_seen.isoformat() if known and first_seen else None,
                    known, start < floor,
                )
            )
        else:
            out.append(SeedAge(sid, url, kind, None, None, False, True))
    return out


def summarize(ages: list[SeedAge]) -> dict[str, Any]:
    """`seeds_without_new_year` plus the by-kind breakdown. Raises if kinds leak."""
    by_kind = {k: {"seeds": 0, "behind": 0} for k in SEED_KINDS}
    for a in ages:
        if a.seed_kind not in by_kind:
            raise RenewalError(f"{a.school_id}: unknown seed kind {a.seed_kind!r}")
        by_kind[a.seed_kind]["seeds"] += 1
        by_kind[a.seed_kind]["behind"] += a.behind_cycle
    summary = {
        "seeds": len(ages),
        "seeds_without_new_year": sum(a.behind_cycle for a in ages),
        "by_kind": by_kind,
    }
    check_accounting(summary)
    return summary


def check_accounting(summary: dict[str, Any]) -> None:
    kinds = summary["by_kind"]
    if (
        sum(k["seeds"] for k in kinds.values()) != summary["seeds"]
        or sum(k["behind"] for k in kinds.values()) != summary["seeds_without_new_year"]
    ):
        raise RenewalError(f"seed accounting does not add up: {summary}")


def behind_listing_seeds(ages: list[SeedAge]) -> list[SeedAge]:
    """Listing-page seeds behind the cycle, oldest newest-year first."""
    rows = [a for a in ages if a.seed_kind == "listing_page" and a.behind_cycle]
    rows.sort(key=lambda a: (parse_year(a.newest_year) or -1, a.school_id))
    return rows


def render_section(ages: list[SeedAge], floor: str) -> str:
    """Markdown section for the renewal report."""
    summary = summarize(ages)
    rows = behind_listing_seeds(ages)
    kinds = summary["by_kind"]
    lines = [
        "## Seeds without a new year",
        "",
        f"Schools with a seed whose newest valid filed year is older than `{floor}` "
        f"(or that have none): **{summary['seeds_without_new_year']}** of {summary['seeds']}. "
        f"One-file seeds: {kinds['one_file']['behind']} of {kinds['one_file']['seeds']}. "
        f"Listing-page seeds: {kinds['listing_page']['behind']} of {kinds['listing_page']['seeds']}.",
        "",
        "Listing-page seeds behind the cycle (newest year, and when the archive first saw it; "
        "the archive began in April 2026, so the date is not yet a gap):",
        "",
        "| school_id | newest year | first seen | seed |",
        "|---|---|---|---|",
    ]
    for a in rows:
        seen = a.newest_year_first_seen[:10] if a.newest_year_first_seen else "unknown"
        url = a.seed_url.replace("|", "\\|")
        lines.append(f"| `{a.school_id}` | {a.newest_year or 'none'} | {seen} | `{url}` |")
    lines.append("")
    return "\n".join(lines)


def run_seed_age(
    schools: dict[str, dict[str, Any]], rows: list[dict[str, Any]], as_of: date
) -> tuple[list[SeedAge], dict[str, Any]]:
    """Compute and sanity-check. Raises on an input too small to trust."""
    with_docs = {r.get("school_id") for r in rows if r.get("school_id")}
    if len(with_docs) < MIN_SCHOOLS_WITH_DOCS:
        raise RenewalError(
            f"only {len(with_docs)} schools have live documents "
            f"(expected at least {MIN_SCHOOLS_WITH_DOCS}); refusing to date seeds"
        )
    ages = compute_seed_ages(schools, rows, as_of)
    if not ages:
        raise RenewalError("no schools with a seed found in schools.yaml")
    return ages, summarize(ages)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.strip().split("\n\n")[0])
    ap.add_argument("--schools-yaml", type=Path, default=DEFAULT_SCHOOLS_YAML)
    ap.add_argument("--api-url", default=os.environ.get("NEXT_PUBLIC_SUPABASE_URL") or DEFAULT_API)
    ap.add_argument("--anon-key", default=os.environ.get("NEXT_PUBLIC_SUPABASE_ANON_KEY") or "")
    ap.add_argument("--manifest-json", type=Path, help="local manifest snapshot instead of the API")
    ap.add_argument("--as-of", help="YYYY-MM-DD; default today (UTC)")
    ap.add_argument("--out-json", type=Path)
    ap.add_argument("--out-md", type=Path)
    args = ap.parse_args(argv)
    try:
        as_of = date.fromisoformat(args.as_of) if args.as_of else datetime.now(timezone.utc).date()
        if args.manifest_json:
            rows = json.loads(args.manifest_json.read_text(encoding="utf-8"))
        else:
            if not args.anon_key:
                raise RenewalError("no anon key: set NEXT_PUBLIC_SUPABASE_ANON_KEY or pass --anon-key")
            rows = fetch_live_manifest(args.api_url, args.anon_key)
            check_floor_agrees(
                cds_freshness_floor(as_of), fetch_sql_floor(args.api_url, args.anon_key, as_of)
            )
        ages, summary = run_seed_age(load_schools(args.schools_yaml), rows, as_of)
    except RenewalError as exc:
        print(f"::error::seed age: {exc}", file=sys.stderr)
        return 1
    floor = cds_freshness_floor(as_of)
    if args.out_json:
        args.out_json.parent.mkdir(parents=True, exist_ok=True)
        args.out_json.write_text(
            json.dumps({"floor": floor, "summary": summary, "seeds": [asdict(a) for a in ages]}, indent=2) + "\n",
            encoding="utf-8",
        )
    if args.out_md:
        args.out_md.parent.mkdir(parents=True, exist_ok=True)
        args.out_md.write_text(render_section(ages, floor), encoding="utf-8")
    print(json.dumps({"floor": floor, **summary}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
