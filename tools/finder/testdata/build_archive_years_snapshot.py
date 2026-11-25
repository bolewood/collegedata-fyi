"""Rebuild archive_years_snapshot.json from a cds_manifest dump.

    python tools/finder/testdata/build_archive_years_snapshot.py MANIFEST.json

MANIFEST.json is a list of cds_manifest rows (school_id, canonical_year,
removed_at, participation_status). The snapshot maps school_id to the sorted
distinct canonical_years of live published documents, which is what
stuck_pdf_seeds.fetch_years_by_school returns. Only schools in schools.yaml
are kept. Real years only: `unknown` is dropped here as it is in the job.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent
YEAR_RE = re.compile(r"^\d{4}-\d{2}$")


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print(__doc__, file=sys.stderr)
        return 2
    rows = json.loads(Path(argv[1]).read_text())
    schools = yaml.safe_load((HERE.parent / "schools.yaml").read_text())["schools"]
    known = {s["id"] for s in schools}
    years: dict[str, set[str]] = {}
    for row in rows:
        if row.get("removed_at") is not None or row.get("participation_status") != "published":
            continue
        sid, year = row.get("school_id"), row.get("canonical_year")
        if sid in known and year and YEAR_RE.match(year):
            years.setdefault(sid, set()).add(year)
    out = {sid: sorted(ys) for sid, ys in sorted(years.items())}
    (HERE / "archive_years_snapshot.json").write_text(
        json.dumps(out, indent=0, sort_keys=True) + "\n"
    )
    print(f"{len(out)} schools with at least one dated live document", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
