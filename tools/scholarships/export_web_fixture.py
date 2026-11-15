#!/usr/bin/env python3
"""Export scholarship_directory-shaped rows for the web fixtures (PRD 036 M3).

Builds the rows the public view would serve, from a tree of programs (YAML),
using model.py, as of a given date, and writes one JSON file. The web app reads
it only in development (SCHOLARSHIP_FIXTURE) and in vitest.

    python tools/scholarships/export_web_fixture.py DIR [DIR ...] --out FILE [--today 2026-11-14]
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import model  # noqa: E402
import validate  # noqa: E402

ATTRIBUTION = next(
    line.strip()
    for line in (validate.REPO_ROOT / "data" / "scholarships" / "LICENSE").read_text(encoding="utf-8").splitlines()
    if line.strip().startswith("Scholarship program data from")
)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("dirs", nargs="+")
    ap.add_argument("--out", required=True)
    ap.add_argument("--today", default=dt.date.today().isoformat())
    args = ap.parse_args()
    today = dt.date.fromisoformat(args.today)
    docs = {}
    for d in args.dirs:
        for path in sorted(Path(d).glob("*/*.yaml")):
            docs[str(path)] = validate.load_yaml_text(path.read_text(encoding="utf-8"))
    ds = model.build_dataset(docs)
    rows = []
    for version in model.select_published(ds):
        program = ds.program(version["program_id"])
        for school in model.participants_of(program):
            rec = model.public_record(program, version, school)
            rec["freshness_status"] = model.freshness_status(
                version["entry_year"], version["verification_status"],
                version["cycle_through_date"], version["last_reviewed_at"],
                None, None, today,
            )
            rec["current_entry_year"] = model.current_entry_year(today)
            rec["last_check_at"] = None
            rec["last_check_result"] = None
            rec["needs_review"] = None
            rec["license"] = "CC-BY-SA-4.0"
            rec["attribution"] = ATTRIBUTION
            # The page names what disagrees from the conflicting locators only; the rest is trimmed.
            rec["evidence"] = [e for e in rec["evidence"] if e["value_status"] == "conflicting"]
            rows.append(rec)
    rows.sort(key=lambda r: (r["school_id"], r["program_id"]))
    Path(args.out).write_text(json.dumps(rows, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    print(f"{len(rows)} rows -> {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
