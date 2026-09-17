"""Load an FSA institutional nonpayment workbook into Postgres.

Dry run is the default. Use --apply only from fresh main after the
migration is on main. Matching uses the Scorecard CSV plus live
directory identity; school_id is stamped on facts here and is not
recomputed in SQL.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

if __package__ is None or __package__ == "":
    sys.path.append(str(Path(__file__).resolve().parents[2]))

from tools.fsa.match import (
    DirectoryRow,
    collapse_to_school_id,
    directory_from_scorecard,
    match_fsa_rows,
)
from tools.fsa.opeid import normalize_opeid8, opeid6_from_opeid8
from tools.fsa.parse import (
    LISTING_PAGE,
    SOURCE_URL,
    ColumnDriftError,
    ParsedWorkbook,
    parse_workbook,
    sha256_file,
)
from tools.fsa.report_m0 import read_hd_opeid

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_ANNOUNCEMENT = (
    "https://fsapartners.ed.gov/knowledge-center/library/electronic-announcements/"
    "2026-06-23/federal-student-aid-posts-updated-reports-fsa-data-center"
)


def load_env(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def read_scorecard_opeids(path: Path) -> dict[str, dict[str, Any]]:
    by_unitid: dict[str, dict[str, Any]] = {}
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        required = {"UNITID", "OPEID"}
        missing = required - set(reader.fieldnames or [])
        if missing:
            raise ColumnDriftError(f"Scorecard CSV missing {sorted(missing)}")
        for raw in reader:
            try:
                ipeds_id = f"{int(float(raw['UNITID'])):06d}"
            except (TypeError, ValueError):
                continue
            opeid = normalize_opeid8(raw.get("OPEID"))
            opeid6_csv = None
            if raw.get("OPEID6") not in (None, "", "NULL"):
                from tools.fsa.opeid import restore_fsa_opeid
                opeid6_csv = restore_fsa_opeid(raw.get("OPEID6"))
            if opeid and opeid6_csv and opeid6_csv != opeid[:6]:
                raise ValueError(
                    f"Scorecard OPEID6 {opeid6_csv} != left(OPEID,6) {opeid[:6]} "
                    f"for UNITID {ipeds_id}"
                )
            by_unitid[ipeds_id] = {
                "OPEID": opeid,
                "OPEID6": opeid6_from_opeid8(opeid),
                "INSTNM": raw.get("INSTNM"),
            }
    return by_unitid


def attach_directory(
    directory_rows: list[dict[str, Any]],
    scorecard: dict[str, dict[str, Any]],
    hd: dict[str, str | None] | None = None,
) -> list[DirectoryRow]:
    attached: list[DirectoryRow] = []
    hd = hd or {}
    for raw in directory_rows:
        ipeds_id = str(raw["ipeds_id"])
        sc = scorecard.get(ipeds_id) or {}
        opeid = sc.get("OPEID") or hd.get(ipeds_id)
        attached.append(
            directory_from_scorecard(
                ipeds_id=ipeds_id,
                school_id=raw["school_id"],
                school_name=raw.get("school_name") or "",
                in_scope=bool(raw.get("in_scope")),
                main_campus=raw.get("main_campus"),
                scorecard_opeid=opeid,
            )
        )
    return attached


def opeid_directory_updates(directory: list[DirectoryRow]) -> list[dict[str, str]]:
    return [
        {"ipeds_id": row.ipeds_id, "opeid": row.opeid}
        for row in directory
        if row.opeid
    ]


def fact_records(
    parsed: ParsedWorkbook,
    directory: list[DirectoryRow],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    matches = match_fsa_rows(parsed.rows, directory)
    collapsed = collapse_to_school_id(matches)
    school_by_opeid = {m.opeid: m for m in collapsed.kept}
    facts: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in parsed.rows:
        if row.opeid in seen:
            raise ValueError(f"Duplicate FSA OPEID {row.opeid}")
        seen.add(row.opeid)
        match = school_by_opeid.get(row.opeid)
        school_id = match.school_id if match else None
        if school_id and school_id in collapsed.omitted_school_ids:
            school_id = None
        facts.append(
            {
                "opeid": row.opeid,
                "school_id": school_id,
                "school_name_raw": row.school_name,
                "school_type": row.school_type,
                "state": row.state,
                "borrowers_in_denom": row.borrowers_in_denom,
                "borrowers_raw": row.borrowers_raw,
                "nonpayment_rate": row.nonpayment_rate,
                "rate_raw": row.rate_raw,
                "suppressed": row.suppressed,
                "public_visible": bool(row.public_visible and school_id),
            }
        )
    summary = {
        "fsa_rows": len(parsed.rows),
        "matched": sum(1 for f in facts if f["school_id"]),
        "public_visible": sum(1 for f in facts if f["public_visible"]),
        "omitted_after_collapse": list(collapsed.omitted_school_ids),
        "collisions_before_collapse": list(collapsed.collisions_before_collapse),
        "directory_null_opeid": sum(1 for row in directory if row.in_scope and not row.opeid),
    }
    return facts, summary


def fetch_directory_rows(client: Any) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    offset = 0
    page = 1000
    while True:
        response = (
            client.table("institution_directory")
            .select("ipeds_id,school_id,school_name,in_scope,main_campus")
            .order("ipeds_id")
            .range(offset, offset + page - 1)
            .execute()
        )
        batch = response.data or []
        rows.extend(batch)
        if len(batch) < page:
            break
        offset += page
    return rows


def apply_opeid_fill(client: Any, updates: list[dict[str, str]], batch_size: int = 500) -> int:
    updated = 0
    for i in range(0, len(updates), batch_size):
        batch = updates[i : i + batch_size]
        response = client.rpc("apply_directory_opeid_fill", {"updates": batch}).execute()
        if response.data:
            updated += int(response.data)
    return updated


def apply_release(
    client: Any,
    parsed: ParsedWorkbook,
    facts: list[dict[str, Any]],
    *,
    source_url: str,
    source_sha256: str,
    announcement_url: str | None,
) -> str:
    existing = (
        client.table("fsa_releases")
        .select("id")
        .eq("source_sha256", source_sha256)
        .limit(1)
        .execute()
    )
    payload = {
        "as_of_date": parsed.as_of_date.isoformat(),
        "as_of_label": parsed.as_of_label,
        "cohort_window_start": parsed.cohort_window_start.isoformat(),
        "cohort_window_end": parsed.cohort_window_end.isoformat(),
        "source_url": source_url,
        "source_sha256": source_sha256,
        "announcement_url": announcement_url,
        "title": parsed.title,
        "downloaded_at": datetime.now(timezone.utc).isoformat(),
    }
    if existing.data:
        release_id = existing.data[0]["id"]
        client.table("fsa_releases").update(payload).eq("id", release_id).execute()
        client.table("fsa_nonpayment_facts").delete().eq("release_id", release_id).execute()
    else:
        inserted = client.table("fsa_releases").insert(payload).execute()
        release_id = inserted.data[0]["id"]
    for i in range(0, len(facts), 500):
        batch = [{**row, "release_id": release_id} for row in facts[i : i + 500]]
        client.table("fsa_nonpayment_facts").insert(batch).execute()
    return release_id


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--xlsx", required=True, type=Path)
    parser.add_argument("--csv", required=True, type=Path, help="Scorecard Most-Recent Institution CSV")
    parser.add_argument(
        "--hd",
        type=Path,
        help="Optional IPEDS HD CSV ZIP used to fill in-scope OPEIDs Scorecard left null",
    )
    parser.add_argument("--source-url", default=SOURCE_URL)
    parser.add_argument("--announcement-url", default=DEFAULT_ANNOUNCEMENT)
    parser.add_argument("--env", default=str(REPO_ROOT / ".env"))
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--fill-directory-opeid", action="store_true", default=True)
    parser.add_argument("--out-dir", type=Path, default=REPO_ROOT / "scratch" / "fsa")
    args = parser.parse_args()

    parsed = parse_workbook(args.xlsx)
    source_sha256 = sha256_file(args.xlsx)
    scorecard = read_scorecard_opeids(args.csv)

    report: dict[str, Any] = {
        "xlsx": str(args.xlsx),
        "sha256": source_sha256,
        "source_url": args.source_url,
        "listing_page": LISTING_PAGE,
        "as_of_label": parsed.as_of_label,
        "as_of_date": parsed.as_of_date.isoformat(),
        "opeid_digit_length": parsed.opeid_digit_length,
        "rate_scale": parsed.rate_scale,
        "suppression_tokens": list(parsed.suppression_tokens),
        "apply": args.apply,
    }

    load_env(Path(args.env).expanduser())
    parent = Path("/Users/santhonys/Projects/Owen/colleges/collegedata-fyi/.env")
    load_env(parent)

    if not os.environ.get("SUPABASE_URL") or not os.environ.get("SUPABASE_SERVICE_ROLE_KEY"):
        if args.apply:
            print("SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY not set", file=sys.stderr)
            return 1
        directory: list[DirectoryRow] = []
        facts, summary = [], {"note": "no directory fetch without credentials"}
    else:
        from supabase import create_client

        client = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_ROLE_KEY"])
        directory = attach_directory(
            fetch_directory_rows(client),
            scorecard,
            read_hd_opeid(args.hd) if args.hd and args.hd.exists() else None,
        )
        facts, summary = fact_records(parsed, directory)
        report["summary"] = summary
        report["directory_opeid_updates"] = len(opeid_directory_updates(directory))
        if args.apply:
            if args.fill_directory_opeid:
                apply_opeid_fill(client, opeid_directory_updates(directory))
            release_id = apply_release(
                client,
                parsed,
                facts,
                source_url=args.source_url,
                source_sha256=source_sha256,
                announcement_url=args.announcement_url,
            )
            report["release_id"] = release_id
        else:
            print("Dry run — no writes. Pass --apply after the migration is on main.", file=sys.stderr)

    args.out_dir.mkdir(parents=True, exist_ok=True)
    out = args.out_dir / f"load-{parsed.as_of_date.isoformat()}-report.json"
    out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps(report, indent=2, sort_keys=True))
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
