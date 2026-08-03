#!/usr/bin/env python3
"""Reproduce PRD 027's College Scorecard endowment reconciliation gate.

The comparison is exact and reporting-entity aware. It never uses fuzzy school
names: direct UNITID matches come first, followed by exact OPEID6 allocation
rollups and then unique two-value residual matches.
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from collections import defaultdict
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping

if __package__ is None or __package__ == "":
    sys.path.append(str(Path(__file__).resolve().parents[2]))

from tools.ipeds.load_release import load_env

REPO_ROOT = Path(__file__).resolve().parents[2]
ENDOWMENT_FIELDS = ("endowment_value_begin", "endowment_value_end")
DEFAULT_FIXTURE_UNITIDS = (201195, 148131, 231420, 203580, 152080)
DEFAULT_PAGE_SIZE = 1000
DEFAULT_MIN_REPORTING_COVERAGE = Decimal("0.95")
METHOD_DIRECT_UNITID = "direct_unitid"
METHOD_OPEID6_ROLLUP = "opeid6_rollup"
METHOD_UNIQUE_RESIDUAL = "unique_residual_match"


@dataclass(frozen=True)
class ScorecardRow:
    unitid: int
    opeid6: str
    institution_name: str
    control: int | None
    main_campus: bool | None
    endowment_begin: Decimal | None
    endowment_end: Decimal | None

    @property
    def pair(self) -> tuple[Decimal, Decimal] | None:
        if self.endowment_begin is None or self.endowment_end is None:
            return None
        return self.endowment_begin, self.endowment_end


@dataclass(frozen=True)
class FactPair:
    unitid: int
    data_year: int
    endowment_begin: Decimal
    endowment_end: Decimal

    @property
    def pair(self) -> tuple[Decimal, Decimal]:
        return self.endowment_begin, self.endowment_end


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("scorecard", type=Path, help="Raw Scorecard institution CSV or ZIP")
    parser.add_argument("--min-year", type=int, default=2020)
    parser.add_argument("--max-year", type=int, default=2024)
    parser.add_argument("--threshold", type=Decimal, default=Decimal("0.99"))
    parser.add_argument(
        "--min-reporting-coverage",
        type=Decimal,
        default=DEFAULT_MIN_REPORTING_COVERAGE,
        help="Minimum share of in-scope Scorecard rows that must have complete F2 facts",
    )
    parser.add_argument("--out", type=Path, help="Optional machine-readable JSON report")
    args = parser.parse_args()

    if args.min_year > args.max_year:
        parser.error("--min-year must be less than or equal to --max-year")
    if not args.threshold.is_finite() or args.threshold < 0 or args.threshold > 1:
        parser.error("--threshold must be between 0 and 1")
    if (
        not args.min_reporting_coverage.is_finite()
        or args.min_reporting_coverage < 0
        or args.min_reporting_coverage > 1
    ):
        parser.error("--min-reporting-coverage must be between 0 and 1")

    load_env(REPO_ROOT / ".env")
    supabase_url = os.environ.get("SUPABASE_URL", "").strip()
    api_key = (
        os.environ.get("SUPABASE_ANON_KEY", "").strip()
        or os.environ.get("NEXT_PUBLIC_SUPABASE_ANON_KEY", "").strip()
    )
    if not supabase_url or not api_key:
        print(
            "error: SUPABASE_URL and SUPABASE_ANON_KEY (or "
            "NEXT_PUBLIC_SUPABASE_ANON_KEY) are required",
            file=sys.stderr,
        )
        return 2

    try:
        scorecard_rows = read_scorecard_rows(args.scorecard)
        fact_rows = fetch_ipeds_endowment_facts(
            supabase_url,
            api_key,
            min_year=args.min_year,
            max_year=args.max_year,
        )
        directory_rows = fetch_in_scope_private_nonprofit_directory(
            supabase_url,
            api_key,
        )
        report = reconcile_scorecard(
            scorecard_rows,
            fact_rows,
            directory_rows,
            min_year=args.min_year,
            max_year=args.max_year,
            threshold=args.threshold,
            min_reporting_coverage=args.min_reporting_coverage,
        )
    except (OSError, ValueError, zipfile.BadZipFile) as exc:
        print(f"error: reconciliation failed: {exc}", file=sys.stderr)
        return 2

    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(f"wrote {args.out}")
    print_summary(report)
    return 0 if report["gate"]["passed"] else 1


def parse_decimal(value: Any) -> Decimal | None:
    if value is None:
        return None
    text = str(value).strip()
    if text.lower() in {"", "na", "null", "privacysuppressed"}:
        return None
    try:
        parsed = Decimal(text)
    except InvalidOperation:
        return None
    return parsed if parsed.is_finite() else None


def parse_int(value: Any) -> int | None:
    parsed = parse_decimal(value)
    if parsed is None or parsed != parsed.to_integral_value():
        return None
    return int(parsed)


def normalize_opeid6(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    parsed = parse_decimal(text)
    if parsed is None or parsed != parsed.to_integral_value():
        return text
    return f"{int(parsed):06d}"


def scorecard_row(raw: Mapping[str, Any]) -> ScorecardRow | None:
    unitid = parse_int(raw.get("UNITID"))
    if unitid is None:
        return None
    main = parse_int(raw.get("MAIN"))
    return ScorecardRow(
        unitid=unitid,
        opeid6=normalize_opeid6(raw.get("OPEID6")),
        institution_name=str(raw.get("INSTNM") or "").strip(),
        control=parse_int(raw.get("CONTROL")),
        main_campus=None if main is None else main == 1,
        endowment_begin=parse_decimal(raw.get("ENDOWBEGIN")),
        endowment_end=parse_decimal(raw.get("ENDOWEND")),
    )


def read_scorecard_rows(path: Path) -> list[ScorecardRow]:
    if not path.exists():
        raise ValueError(f"Scorecard source does not exist: {path}")
    if path.suffix.lower() == ".zip":
        with zipfile.ZipFile(path) as archive:
            members = [
                name
                for name in archive.namelist()
                if name.lower().endswith(".csv") and not name.startswith("__MACOSX/")
            ]
            if len(members) != 1:
                raise ValueError(
                    f"Scorecard ZIP must contain exactly one CSV; found {len(members)}"
                )
            with archive.open(members[0]) as raw:
                with io.TextIOWrapper(raw, encoding="utf-8-sig", newline="") as text:
                    return parse_scorecard_reader(csv.DictReader(text))
    with path.open("r", encoding="utf-8-sig", newline="") as source:
        return parse_scorecard_reader(csv.DictReader(source))


def parse_scorecard_reader(reader: csv.DictReader[str]) -> list[ScorecardRow]:
    required = {"UNITID", "OPEID6", "INSTNM", "MAIN", "CONTROL", "ENDOWBEGIN", "ENDOWEND"}
    missing = sorted(required - set(reader.fieldnames or []))
    if missing:
        raise ValueError("Scorecard source is missing columns: " + ", ".join(missing))
    parsed = [row for raw in reader if (row := scorecard_row(raw)) is not None]
    if not parsed:
        raise ValueError("Scorecard source contains no valid UNITID rows")
    return parsed


def rest_url(base_url: str, table: str, params: Mapping[str, str]) -> str:
    return (
        base_url.rstrip("/")
        + "/rest/v1/"
        + table
        + "?"
        + urllib.parse.urlencode(params, safe="(),.*")
    )


def postgrest_get_all(
    base_url: str,
    api_key: str,
    table: str,
    params: Mapping[str, str],
    *,
    page_size: int = DEFAULT_PAGE_SIZE,
    opener: Callable[..., Any] = urllib.request.urlopen,
) -> list[dict[str, Any]]:
    if page_size <= 0 or page_size > 1000:
        raise ValueError("PostgREST page size must be between 1 and 1000")
    rows: list[dict[str, Any]] = []
    offset = 0
    while True:
        page_params = dict(params)
        page_params.update({"limit": str(page_size), "offset": str(offset)})
        request = urllib.request.Request(
            rest_url(base_url, table, page_params),
            headers={"apikey": api_key, "Authorization": f"Bearer {api_key}"},
        )
        try:
            with opener(request, timeout=60) as response:
                page = json.load(response)
        except urllib.error.HTTPError as exc:
            raise ValueError(
                f"PostgREST {table} request failed with HTTP {exc.code}"
            ) from None
        except urllib.error.URLError:
            raise ValueError(f"PostgREST {table} request could not connect") from None
        if not isinstance(page, list) or any(not isinstance(row, dict) for row in page):
            raise ValueError(f"PostgREST {table} returned a non-row response")
        if not page:
            return rows
        rows.extend(page)
        offset += len(page)


def fetch_ipeds_endowment_facts(
    base_url: str,
    api_key: str,
    *,
    min_year: int,
    max_year: int,
) -> list[dict[str, Any]]:
    return postgrest_get_all(
        base_url,
        api_key,
        "ipeds_facts",
        {
            "select": (
                "release_id,ipeds_id,unitid,data_year,field_key,value_numeric,"
                "source_table,source_variable"
            ),
            "field_key": "in.(endowment_value_begin,endowment_value_end)",
            "data_year": f"gte.{min_year}",
            "and": f"(data_year.lte.{max_year},source_table.like.F*_F2)",
            "public_visible": "eq.true",
            "order": (
                "data_year.asc,unitid.asc,field_key.asc,source_table.asc,"
                "source_variable.asc,release_id.asc"
            ),
        },
    )


def fetch_in_scope_private_nonprofit_directory(
    base_url: str,
    api_key: str,
) -> list[dict[str, Any]]:
    return postgrest_get_all(
        base_url,
        api_key,
        "institution_directory",
        {
            "select": "ipeds_id,school_name,control,in_scope,main_campus,branch_count",
            "control": "eq.2",
            "in_scope": "eq.true",
            "order": "ipeds_id.asc",
        },
    )


def build_fact_pairs(rows: Iterable[Mapping[str, Any]]) -> dict[int, dict[int, FactPair]]:
    values: dict[tuple[int, int, str], Decimal] = {}
    for row in rows:
        unitid = parse_int(row.get("unitid")) or parse_int(row.get("ipeds_id"))
        year = parse_int(row.get("data_year"))
        field = str(row.get("field_key") or "")
        value = parse_decimal(row.get("value_numeric"))
        if unitid is None or year is None or field not in ENDOWMENT_FIELDS or value is None:
            continue
        key = (year, unitid, field)
        if key in values and values[key] != value:
            raise ValueError(
                f"Conflicting public IPEDS values for FY{year} UNITID {unitid} {field}"
            )
        values[key] = value

    pairs: dict[int, dict[int, FactPair]] = defaultdict(dict)
    unit_years = {(year, unitid) for year, unitid, _field in values}
    for year, unitid in sorted(unit_years):
        beginning = values.get((year, unitid, ENDOWMENT_FIELDS[0]))
        ending = values.get((year, unitid, ENDOWMENT_FIELDS[1]))
        if beginning is None or ending is None:
            continue
        pairs[year][unitid] = FactPair(unitid, year, beginning, ending)
    return dict(pairs)


def member_report(row: ScorecardRow, *, included: bool) -> dict[str, Any]:
    return {
        "unitid": row.unitid,
        "institution_name": row.institution_name,
        "opeid6": row.opeid6,
        "main_campus": row.main_campus,
        "endowment_begin": decimal_json(row.endowment_begin),
        "endowment_end": decimal_json(row.endowment_end),
        "included_in_sum": included,
    }


def reconcile_entity(
    reporter: ScorecardRow,
    fact: FactPair,
    *,
    opeid_groups: Mapping[str, list[ScorecardRow]],
    residual_candidates: Mapping[tuple[Decimal, Decimal], list[ScorecardRow]],
    reporting_unitids: set[int] | frozenset[int] = frozenset(),
) -> dict[str, Any]:
    direct_pair = reporter.pair
    base = {
        "reporter_unitid": reporter.unitid,
        "reporter_name": reporter.institution_name,
        "opeid6": reporter.opeid6,
        "ipeds": {
            "endowment_begin": decimal_json(fact.endowment_begin),
            "endowment_end": decimal_json(fact.endowment_end),
        },
    }
    if direct_pair == fact.pair:
        return {
            **base,
            "matched": True,
            "method": METHOD_DIRECT_UNITID,
            "members": [member_report(reporter, included=True)],
        }

    group = (
        [
            row
            for row in opeid_groups.get(reporter.opeid6, [])
            if row.unitid == reporter.unitid or row.unitid not in reporting_unitids
        ]
        if reporter.opeid6
        else []
    )
    complete_group = [row for row in group if row.pair is not None]
    if len(group) > 1 and complete_group:
        rollup_pair = (
            sum(
                (
                    row.endowment_begin
                    for row in complete_group
                    if row.endowment_begin is not None
                ),
                Decimal(0),
            ),
            sum(
                (
                    row.endowment_end
                    for row in complete_group
                    if row.endowment_end is not None
                ),
                Decimal(0),
            ),
        )
        if rollup_pair == fact.pair:
            return {
                **base,
                "matched": True,
                "method": METHOD_OPEID6_ROLLUP,
                "scorecard_rollup": {
                    "endowment_begin": decimal_json(rollup_pair[0]),
                    "endowment_end": decimal_json(rollup_pair[1]),
                },
                "allocation_member_unitids": sorted(
                    row.unitid
                    for row in complete_group
                    if row.unitid != reporter.unitid
                ),
                "members": [
                    member_report(row, included=row.pair is not None)
                    for row in sorted(group, key=lambda item: item.unitid)
                ],
            }

    candidates: list[ScorecardRow] = []
    residual_pair: tuple[Decimal, Decimal] | None = None
    if direct_pair is not None:
        residual_pair = (
            fact.endowment_begin - direct_pair[0],
            fact.endowment_end - direct_pair[1],
        )
        candidates = [
            row
            for row in residual_candidates.get(residual_pair, [])
            if row.unitid != reporter.unitid
        ]
        if len(candidates) == 1:
            return {
                **base,
                "matched": True,
                "method": METHOD_UNIQUE_RESIDUAL,
                "residual_candidate_unitid": candidates[0].unitid,
                "allocation_member_unitids": [candidates[0].unitid],
                "residual": {
                    "endowment_begin": decimal_json(residual_pair[0]),
                    "endowment_end": decimal_json(residual_pair[1]),
                },
                "members": [
                    member_report(reporter, included=True),
                    member_report(candidates[0], included=True),
                ],
            }

    method = "ambiguous_residual" if len(candidates) > 1 else "unreconciled"
    return {
        **base,
        "matched": False,
        "method": method,
        "direct_scorecard": {
            "endowment_begin": decimal_json(reporter.endowment_begin),
            "endowment_end": decimal_json(reporter.endowment_end),
        },
        "residual": {
            "endowment_begin": decimal_json(residual_pair[0]),
            "endowment_end": decimal_json(residual_pair[1]),
        }
        if residual_pair is not None
        else None,
        "members": [
            member_report(row, included=row.pair is not None)
            for row in sorted(group or [reporter], key=lambda item: item.unitid)
        ],
        "residual_candidates": [
            member_report(row, included=False)
            for row in sorted(candidates, key=lambda item: item.unitid)
        ],
    }


def reconcile_year(
    year: int,
    in_scope_rows: Iterable[ScorecardRow],
    facts: Mapping[int, FactPair],
    all_private_nonprofit_rows: Iterable[ScorecardRow],
) -> dict[str, Any]:
    scorecard_rows = sorted(in_scope_rows, key=lambda row: row.unitid)
    private_rows = list(all_private_nonprofit_rows)
    opeid_groups: dict[str, list[ScorecardRow]] = defaultdict(list)
    residual_candidates: dict[tuple[Decimal, Decimal], list[ScorecardRow]] = defaultdict(list)
    for row in private_rows:
        if row.opeid6:
            opeid_groups[row.opeid6].append(row)
        if row.pair is not None and row.unitid not in facts:
            residual_candidates[row.pair].append(row)

    entities: list[dict[str, Any]] = []
    no_f2_rows: list[dict[str, Any]] = []
    for row in scorecard_rows:
        fact = facts.get(row.unitid)
        if fact is None:
            no_f2_rows.append({
                "unitid": row.unitid,
                "institution_name": row.institution_name,
                "opeid6": row.opeid6,
                "reason": "no_complete_f2_fact_pair",
            })
            continue
        entities.append(
            reconcile_entity(
                row,
                fact,
                opeid_groups=opeid_groups,
                residual_candidates=residual_candidates,
                reporting_unitids=set(facts),
            )
        )

    allocation_claims: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for entity in entities:
        if not entity["matched"]:
            continue
        for member_unitid in entity.get("allocation_member_unitids", []):
            allocation_claims[int(member_unitid)].append(entity)
    conflicting_members_by_reporter: dict[int, set[int]] = defaultdict(set)
    for member_unitid, claims in allocation_claims.items():
        if len(claims) <= 1:
            continue
        for entity in claims:
            conflicting_members_by_reporter[int(entity["reporter_unitid"])].add(
                member_unitid
            )
    for entity in entities:
        conflicts = conflicting_members_by_reporter.get(int(entity["reporter_unitid"]))
        if not conflicts:
            continue
        entity["matched"] = False
        entity["method"] = "ambiguous_branch_allocation"
        entity["members"] = [
            {
                **member,
                "included_in_sum": (
                    member["included_in_sum"] and member["unitid"] not in conflicts
                ),
            }
            for member in entity["members"]
        ]
        entity["conflicting_allocation_unitids"] = sorted(conflicts)

    direct_exact = sum(entity["method"] == METHOD_DIRECT_UNITID for entity in entities)
    consolidation_required = len(entities) - direct_exact
    consolidation_matched = sum(
        entity["matched"] and entity["method"] != METHOD_DIRECT_UNITID
        for entity in entities
    )
    matched = sum(entity["matched"] for entity in entities)
    denominator = len(entities)
    rate = Decimal(matched) / Decimal(denominator) if denominator else Decimal(0)
    return {
        "data_year": year,
        "reporting_entities": denominator,
        "matched_reporting_entities": matched,
        "reporting_entity_rate": decimal_json(rate),
        "direct_exact_unitid_rows": direct_exact,
        "direct_exact_rate": decimal_json(
            Decimal(direct_exact) / Decimal(denominator) if denominator else Decimal(0)
        ),
        "consolidation_required": consolidation_required,
        "consolidation_matched": consolidation_matched,
        "unreconciled_count": sum(not entity["matched"] for entity in entities),
        "entities": entities,
        "no_f2_rows": no_f2_rows,
    }


def alignment_sort_key(alignment: Mapping[str, Any]) -> tuple[Decimal, int, int, int]:
    reporting_entities = int(alignment["reporting_entities"])
    rate = (
        Decimal(int(alignment["matched_reporting_entities"]))
        / Decimal(reporting_entities)
        if reporting_entities
        else Decimal(0)
    )
    return (
        rate,
        int(alignment["matched_reporting_entities"]),
        int(alignment["reporting_entities"]),
        int(alignment["data_year"]),
    )


def fixture_results(
    fixture_unitids: Iterable[int],
    scorecard_by_unitid: Mapping[int, ScorecardRow],
    facts: Mapping[int, FactPair],
) -> list[dict[str, Any]]:
    results = []
    for unitid in fixture_unitids:
        scorecard = scorecard_by_unitid.get(unitid)
        fact = facts.get(unitid)
        matched = scorecard is not None and fact is not None and scorecard.pair == fact.pair
        results.append({
            "unitid": unitid,
            "institution_name": scorecard.institution_name if scorecard else None,
            "matched": matched,
            "scorecard": {
                "endowment_begin": decimal_json(scorecard.endowment_begin),
                "endowment_end": decimal_json(scorecard.endowment_end),
            }
            if scorecard
            else None,
            "ipeds": {
                "endowment_begin": decimal_json(fact.endowment_begin),
                "endowment_end": decimal_json(fact.endowment_end),
            }
            if fact
            else None,
        })
    return results


def reconcile_scorecard(
    scorecard_rows: Iterable[ScorecardRow],
    fact_rows: Iterable[Mapping[str, Any]],
    directory_rows: Iterable[Mapping[str, Any]],
    *,
    min_year: int,
    max_year: int,
    threshold: Decimal,
    min_reporting_coverage: Decimal = DEFAULT_MIN_REPORTING_COVERAGE,
) -> dict[str, Any]:
    all_rows = list(scorecard_rows)
    private_with_values = [row for row in all_rows if row.control == 2 and row.pair is not None]
    private_rows = [row for row in all_rows if row.control == 2]
    directory_unitids = {
        unitid
        for row in directory_rows
        if (unitid := parse_int(row.get("ipeds_id"))) is not None
        and parse_int(row.get("control")) == 2
        and row.get("in_scope") is True
    }
    in_scope = [row for row in private_with_values if row.unitid in directory_unitids]
    excluded = [
        {
            "unitid": row.unitid,
            "institution_name": row.institution_name,
            "reason": "not_in_current_in_scope_private_nonprofit_directory",
        }
        for row in private_with_values
        if row.unitid not in directory_unitids
    ]
    pairs_by_year = build_fact_pairs(fact_rows)
    alignments = [
        reconcile_year(year, in_scope, pairs_by_year.get(year, {}), private_rows)
        for year in range(min_year, max_year + 1)
    ]
    if not alignments:
        raise ValueError("No candidate data years were requested")
    in_scope_count = len(in_scope)
    coverage_by_year: dict[int, Decimal] = {}
    for alignment in alignments:
        year = int(alignment["data_year"])
        coverage = (
            Decimal(int(alignment["reporting_entities"])) / Decimal(in_scope_count)
            if in_scope_count
            else Decimal(0)
        )
        coverage_by_year[year] = coverage
        alignment["scorecard_population_coverage"] = decimal_json(coverage)
    population_eligible = [
        alignment
        for alignment in alignments
        if coverage_by_year[int(alignment["data_year"])] >= min_reporting_coverage
    ]
    best = max(population_eligible or alignments, key=alignment_sort_key)
    best_year = int(best["data_year"])
    scorecard_by_unitid = {row.unitid: row for row in all_rows}
    fixtures = fixture_results(
        DEFAULT_FIXTURE_UNITIDS,
        scorecard_by_unitid,
        pairs_by_year.get(best_year, {}),
    )
    best_denominator = int(best["reporting_entities"])
    best_rate = (
        Decimal(int(best["matched_reporting_entities"]))
        / Decimal(best_denominator)
        if best_denominator
        else Decimal(0)
    )
    best_coverage = coverage_by_year[best_year]
    return {
        "methodology": {
            "population": (
                "Current in-scope private-nonprofit Scorecard rows with both ENDOWBEGIN "
                "and ENDOWEND, restricted to UNITIDs with a complete F2 fact pair"
            ),
            "matching_order": [
                METHOD_DIRECT_UNITID,
                METHOD_OPEID6_ROLLUP,
                METHOD_UNIQUE_RESIDUAL,
            ],
            "fuzzy_name_matching": False,
        },
        "candidate_years": list(range(min_year, max_year + 1)),
        "scorecard_private_nonprofit_rows_with_values": len(private_with_values),
        "in_scope_private_nonprofit_rows_with_values": len(in_scope),
        "excluded_scorecard_rows": excluded,
        "alignments": alignments,
        "best_alignment": best,
        "fixtures": fixtures,
        "fixtures_all_match": all(item["matched"] for item in fixtures),
        "gate": {
            "threshold": decimal_json(threshold),
            "rate": decimal_json(best_rate),
            "rate_passed": best_rate >= threshold,
            "min_reporting_coverage": decimal_json(min_reporting_coverage),
            "reporting_coverage": decimal_json(best_coverage),
            "reporting_coverage_passed": best_coverage >= min_reporting_coverage,
            "passed": (
                best_rate >= threshold and best_coverage >= min_reporting_coverage
            ),
        },
    }


def decimal_json(value: Decimal | None) -> int | float | None:
    if value is None:
        return None
    if value == value.to_integral_value():
        return int(value)
    return float(value)


def print_summary(report: Mapping[str, Any]) -> None:
    best = report["best_alignment"]
    gate = report["gate"]
    print(
        f"Best alignment: FY{best['data_year']} | in-scope Scorecard rows with values: "
        f"{report['in_scope_private_nonprofit_rows_with_values']}"
    )
    print(
        f"Direct exact UNITID: {best['direct_exact_unitid_rows']}/{best['reporting_entities']} | "
        f"consolidated: {best['consolidation_matched']}/{best['consolidation_required']}"
    )
    print(
        f"Reporting entities: {best['matched_reporting_entities']}/{best['reporting_entities']} "
        f"= {float(best['reporting_entity_rate']):.3%} | gate "
        f"{float(gate['threshold']):.3%}: {'PASS' if gate['passed'] else 'FAIL'}"
    )
    print(
        f"F2 reporting coverage: {float(gate['reporting_coverage']):.3%} | minimum "
        f"{float(gate['min_reporting_coverage']):.3%}: "
        f"{'PASS' if gate['reporting_coverage_passed'] else 'FAIL'}"
    )
    print(
        f"Excluded/no-F2: {len(report['excluded_scorecard_rows'])}/"
        f"{len(best['no_f2_rows'])} | fixtures: "
        f"{sum(item['matched'] for item in report['fixtures'])}/{len(report['fixtures'])}"
    )
    for entity in best["entities"]:
        if not entity["matched"]:
            print(
                f"Unreconciled: {entity['reporter_unitid']} {entity['reporter_name']} "
                f"({entity['method']})"
            )


if __name__ == "__main__":
    raise SystemExit(main())
