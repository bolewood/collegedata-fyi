"""M0 join report: FSA workbook × Scorecard CSV × public institution directory."""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
import zipfile
from collections import Counter
from pathlib import Path
from typing import Any, Iterable
from urllib.request import Request, urlopen

if __package__ is None or __package__ == "":
    sys.path.append(str(Path(__file__).resolve().parents[2]))

from tools.fsa.match import (
    DirectoryRow,
    collapse_to_school_id,
    directory_from_scorecard,
    match_fsa_rows,
)
from tools.fsa.opeid import normalize_opeid8, restore_fsa_opeid
from tools.fsa.parse import ParsedWorkbook, parse_workbook, sha256_file, SOURCE_URL, LISTING_PAGE

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_XLSX = REPO_ROOT / "scratch" / "fsa" / "2026-05" / "nonpayment-rates.xlsx"
DEFAULT_SCORECARD = Path(
    "/Users/santhonys/Projects/Owen/colleges/collegedata-fyi/scratch/"
    "scorecard-reconciliation/Most-Recent-Cohorts-Institution.csv"
)
DEFAULT_HD = Path(
    "/Users/santhonys/Projects/Owen/colleges/collegedata-fyi/scratch/"
    "ipeds/2024-25-final/HD2024.zip"
)
DIRECTORY_URL = "https://api.collegedata.fyi/rest/v1/institution_directory"
CANARIES = {
    "uf": "University of Florida",
    "uei": "UEI",
    "miller-motte": "Miller-Motte",
}

PUBLIC_FLAGSHIP_HINTS = ("university of michigan", "university of california-berkeley", "university of virginia")
NONPROFIT_HINTS = ("amherst college", "swarthmore college", "pomona college")


def _env(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def fetch_directory(url: str, anon_key: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    offset = 0
    page = 1000
    while True:
        req = Request(
            f"{url}?select=ipeds_id,school_id,school_name,in_scope,main_campus,currently_operating,state,control"
            f"&order=ipeds_id&offset={offset}&limit={page}",
            headers={
                "apikey": anon_key,
                "Authorization": f"Bearer {anon_key}",
                "Prefer": "count=exact",
            },
        )
        with urlopen(req, timeout=60) as response:
            batch = json.loads(response.read().decode("utf-8"))
        rows.extend(batch)
        if len(batch) < page:
            break
        offset += page
    return rows


def read_scorecard(path: Path) -> dict[str, dict[str, Any]]:
    by_unitid: dict[str, dict[str, Any]] = {}
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        missing = {"UNITID", "OPEID"} - set(reader.fieldnames or [])
        if missing:
            raise ValueError(f"Scorecard CSV missing {sorted(missing)}")
        for raw in reader:
            unitid = str(raw.get("UNITID") or "").strip()
            if not unitid:
                continue
            try:
                ipeds_id = f"{int(float(unitid)):06d}"
            except ValueError:
                continue
            by_unitid[ipeds_id] = raw
    return by_unitid


def read_hd_opeid(path: Path) -> dict[str, str | None]:
    out: dict[str, str | None] = {}
    with zipfile.ZipFile(path) as archive:
        name = next(n for n in archive.namelist() if n.lower().endswith(".csv"))
        with archive.open(name) as handle:
            reader = csv.DictReader((line.decode("utf-8-sig") for line in handle))
            for raw in reader:
                try:
                    ipeds_id = f"{int(float(raw['UNITID'])):06d}"
                except (KeyError, TypeError, ValueError):
                    continue
                out[ipeds_id] = normalize_opeid8(raw.get("OPEID"))
    return out


def attach_directory(
    directory_rows: Iterable[dict[str, Any]],
    scorecard: dict[str, dict[str, Any]],
) -> list[DirectoryRow]:
    attached: list[DirectoryRow] = []
    for raw in directory_rows:
        ipeds_id = str(raw["ipeds_id"])
        sc = scorecard.get(ipeds_id) or {}
        attached.append(
            directory_from_scorecard(
                ipeds_id=ipeds_id,
                school_id=raw["school_id"],
                school_name=raw.get("school_name") or "",
                in_scope=bool(raw.get("in_scope")),
                main_campus=raw.get("main_campus"),
                scorecard_opeid=sc.get("OPEID"),
            )
        )
    return attached


def _canary_rows(parsed: ParsedWorkbook, directory: list[DirectoryRow], matches) -> list[dict[str, Any]]:
    by_opeid = {row.opeid: row for row in parsed.rows}
    by_school = {row.school_id: row for row in directory}
    named = []
    wanted_opeids = {
        "001535": "University of Florida",
        "031133": "UEI College",
        "039696": "UEI College",
        "023068": "Miller-Motte",
        "004992": "Miller-Motte",
        "026142": "Miller-Motte",
    }
    match_by_opeid = {m.opeid: m for m in matches}
    for opeid, label in wanted_opeids.items():
        fsa = by_opeid.get(opeid)
        match = match_by_opeid.get(opeid)
        named.append(
            {
                "label": label,
                "fsa_opeid": opeid,
                "fsa_name": fsa.school_name if fsa else None,
                "rate": fsa.nonpayment_rate if fsa else None,
                "rate_raw": fsa.rate_raw if fsa else None,
                "public_visible": fsa.public_visible if fsa else None,
                "school_id": match.school_id if match else None,
                "match_kind": match.match_kind if match else None,
                "reason": match.reason if match else None,
            }
        )

    def pick(hints: tuple[str, ...], control: int | None = None) -> DirectoryRow | None:
        for row in directory:
            if not row.in_scope:
                continue
            name = row.school_name.lower()
            if any(hint in name for hint in hints):
                return row
        return None

    extra = []
    umich = pick(PUBLIC_FLAGSHIP_HINTS)
    amherst = pick(NONPROFIT_HINTS)
    for row in (umich, amherst):
        if not row:
            continue
        extra.append(
            {
                "label": row.school_name,
                "school_id": row.school_id,
                "ipeds_id": row.ipeds_id,
                "opeid": row.opeid,
                "opeid6": row.opeid6,
                "main_campus": row.main_campus,
            }
        )
    return named + extra


def build_report(
    parsed: ParsedWorkbook,
    directory: list[DirectoryRow],
    scorecard: dict[str, dict[str, Any]],
    hd: dict[str, str | None],
    source_sha256: str,
) -> dict[str, Any]:
    matches = match_fsa_rows(parsed.rows, directory)
    collapsed = collapse_to_school_id(matches)
    in_scope = [row for row in directory if row.in_scope]
    match_kinds = Counter(m.match_kind for m in matches)
    reasons = Counter(m.reason for m in matches)
    in_scope_null_opeid = sum(1 for row in in_scope if not row.opeid)
    scorecard_opeid_present = sum(
        1 for row in in_scope if normalize_opeid8((scorecard.get(row.ipeds_id) or {}).get("OPEID"))
    )
    hd_opeid_present = sum(1 for row in in_scope if hd.get(row.ipeds_id))
    return {
        "source_url": SOURCE_URL,
        "listing_page": LISTING_PAGE,
        "sha256": source_sha256,
        "title": parsed.title,
        "as_of_label": parsed.as_of_label,
        "as_of_date": parsed.as_of_date.isoformat(),
        "cohort_window": [parsed.cohort_window_start.isoformat(), parsed.cohort_window_end.isoformat()],
        "header_row": parsed.header_row,
        "headers": ["OPE ID", "School Name", "School Type", "State", "Total Borrowers Evaluated", "Nonpayment Rate"],
        "opeid_digit_length": parsed.opeid_digit_length,
        "opeid_storage": parsed.opeid_storage,
        "rate_scale": parsed.rate_scale,
        "suppression_tokens": list(parsed.suppression_tokens),
        "small_n_cut": 10,
        "fsa_rows": len(parsed.rows),
        "skipped_blank": parsed.skipped_blank,
        "directory_rows": len(directory),
        "in_scope_directory_rows": len(in_scope),
        "exact_8": match_kinds.get("exact_8", 0),
        "rollup_6": match_kinds.get("rollup_6", 0),
        "unmatched": match_kinds.get("unmatched", 0),
        "unmatched_reasons": dict(reasons),
        "fsa_only": sum(1 for m in matches if m.reason in {"no_in_scope_main", "ambiguous_main", "ambiguous_opeid8"}),
        "directory_in_scope_null_opeid": in_scope_null_opeid,
        "school_ids_with_multiple_fsa_rows_before_collapse": len(collapsed.collisions_before_collapse),
        "omitted_after_collapse": len(collapsed.omitted_school_ids),
        "kept_matched_school_ids": sum(1 for m in collapsed.kept if m.school_id),
        "scorecard_in_scope_with_opeid": scorecard_opeid_present,
        "hd_in_scope_with_opeid": hd_opeid_present,
        "hd_beats_scorecard": hd_opeid_present > scorecard_opeid_present,
        "canaries": _canary_rows(parsed, directory, matches),
        "older_vintages": "only the current hosted file is still at the stable Data Center URL",
    }


def render_markdown(report: dict[str, Any]) -> str:
    canaries = "\n".join(
        f"- {row.get('label')}: FSA `{row.get('fsa_opeid') or row.get('opeid')}` "
        f"→ `{row.get('school_id')}` ({row.get('match_kind') or row.get('match_kind') or 'directory'}) "
        f"rate={row.get('rate') if 'rate' in row else 'n/a'}"
        for row in report["canaries"]
    )
    return f"""# FSA nonpayment M0 join report

Sanitized spike report for the May 2026 FSA institutional nonpayment workbook.
The xlsx stays in gitignored `scratch/fsa/`. This file is the M1 gate.

## Source

- Listing: {report['listing_page']} (in-page search: `nonpayment`)
- File: `{report['source_url']}`
- SHA-256: `{report['sha256']}`
- Title: {report['title']}
- Public as-of: **{report['as_of_label']}** (`as_of_date` {report['as_of_date']}; delinquency pull date from Definitions, not the June 23 announcement)
- Cohort window: Direct Loan borrowers who entered repayment {report['cohort_window'][0]} through {report['cohort_window'][1]}
- Older vintages: {report['older_vintages']}

## Headers, grain, units

- School-level sheet header row: **{report['header_row']}**
- Columns: {', '.join(f'`{h}`' for h in report['headers'])}
- FSA OPE ID grain: **{report['opeid_digit_length']}-digit** main-campus key (Definitions: "six-digit code identifying the school at its main branch")
- Excel storage: mostly **{report['opeid_storage']}** with `000000` format; numeric cells must still restore leading zeros without padding 6-digit keys to 8
- Rate scale: **{report['rate_scale']}** (UI multiplies by 100)
- Suppression tokens: {', '.join(f'`{t}`' for t in report['suppression_tokens'])}; denom token `<100`
- Small-n cut: n < {report['small_n_cut']} (file already rounds denom to nearest 100)

## Join counts (in-scope directory)

| Metric | Count |
| --- | --- |
| FSA school-level rows | {report['fsa_rows']} |
| In-scope directory rows | {report['in_scope_directory_rows']} |
| Exact 8-digit matches | {report['exact_8']} |
| 6-digit main rollups | {report['rollup_6']} |
| Unmatched FSA rows | {report['unmatched']} |
| Directory in-scope with null Scorecard OPEID | {report['directory_in_scope_null_opeid']} |
| `school_id`s with >1 matched FSA row before collapse | {report['school_ids_with_multiple_fsa_rows_before_collapse']} |
| Omitted after collapse | {report['omitted_after_collapse']} |
| Kept matched school_ids | {report['kept_matched_school_ids']} |

Unmatched reasons: `{report['unmatched_reasons']}`

## Scorecard vs IPEDS HD OPEID coverage (in-scope)

- Scorecard OPEID present: **{report['scorecard_in_scope_with_opeid']}**
- HD2024 OPEID present: **{report['hd_in_scope_with_opeid']}**
- HD beats Scorecard: **{report['hd_beats_scorecard']}**

M1 reads Scorecard `OPEID` unless this flag is true.

## Named rows

{canaries}
"""


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--xlsx", type=Path, default=DEFAULT_XLSX)
    parser.add_argument("--csv", type=Path, default=DEFAULT_SCORECARD)
    parser.add_argument("--hd", type=Path, default=DEFAULT_HD)
    parser.add_argument("--env", default=str(REPO_ROOT / ".env"))
    parser.add_argument(
        "--out",
        type=Path,
        default=REPO_ROOT / "docs" / "designs" / "fsa-m0-join-report.md",
    )
    args = parser.parse_args()
    _env(Path(args.env).expanduser())
    parent_env = Path("/Users/santhonys/Projects/Owen/colleges/collegedata-fyi/.env")
    _env(parent_env)
    anon = os.environ.get("SUPABASE_ANON_KEY") or os.environ.get("NEXT_PUBLIC_SUPABASE_ANON_KEY")
    if not anon:
        print("Need SUPABASE_ANON_KEY to fetch institution_directory", file=sys.stderr)
        return 1

    parsed = parse_workbook(args.xlsx)
    scorecard = read_scorecard(args.csv)
    directory = attach_directory(fetch_directory(DIRECTORY_URL, anon), scorecard)
    hd = read_hd_opeid(args.hd) if args.hd.exists() else {}
    report = build_report(parsed, directory, scorecard, hd, sha256_file(args.xlsx))
    json_path = REPO_ROOT / "scratch" / "fsa" / "2026-05" / "join-report.json"
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    args.out.write_text(render_markdown(report))
    print(f"wrote {args.out}")
    print(f"wrote {json_path}")
    print(json.dumps({k: report[k] for k in (
        "fsa_rows", "exact_8", "rollup_6", "unmatched",
        "directory_in_scope_null_opeid",
        "school_ids_with_multiple_fsa_rows_before_collapse",
        "scorecard_in_scope_with_opeid", "hd_in_scope_with_opeid",
        "hd_beats_scorecard",
    )}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
