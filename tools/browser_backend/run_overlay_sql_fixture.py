#!/usr/bin/env python3
"""PRD 038: run the PENDING serving view (supabase/pending/038_overlay_serving.sql) over the shared parity fixture.
NOT part of CI. SELECT only: the view body runs with `public.cds_artifacts` replaced by a CTE of the fixture rows and
`public.cds_overlay_serve_classes()` replaced by each variant's ARRAY[...], inside BEGIN READ ONLY ... ROLLBACK, through a
read-only psql wrapper you pass. No table is read and nothing is created.

    python tools/browser_backend/run_overlay_sql_fixture.py /path/to/read_only_psql_wrapper.sh

Exits 0 when every variant of every case matches the fixture's hand-written expectation (base artifact id, plain values),
plus the `sql` leg of the recorded divergence case; prints each mismatch otherwise."""
import json
import re
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = json.loads((ROOT / "tools/browser_backend/fixtures/overlay_parity.json").read_text())


def view_body() -> str:
    text = (ROOT / "supabase/pending/038_overlay_serving.sql").read_text()
    start = text.index("WITH serve AS (")
    end = text.index("WHERE b.rn = 1;") + len("WHERE b.rn = 1")
    return text[start:end]


def run_variant(psql: str, serve: list[str], rows: list[dict]) -> dict:
    array = "ARRAY[" + ",".join("'" + c.replace("'", "''") + "'" for c in serve) + "]::text[]"
    body = view_body().replace("public.cds_overlay_serve_classes()", array).replace("public.cds_artifacts", "fx")
    fx = ("fx AS (SELECT * FROM jsonb_to_recordset($fx$" + json.dumps(rows) + "$fx$::jsonb) AS t(id text, document_id text, kind text, "
          "producer text, producer_version text, schema_version text, created_at timestamptz, notes jsonb))")
    body = body.replace("WITH serve AS (", "WITH " + fx + ",\nserve AS (", 1)
    query = ("BEGIN READ ONLY;\nSELECT coalesce(json_agg(json_build_object('doc', v.document_id, 'base', v.base_artifact_id, 'vals', v.selected_values)), '[]'::json)"
             " FROM (" + body + ") v;\nROLLBACK;\n")
    out = subprocess.run([psql, "-At", "-c", query], capture_output=True, text=True)
    lines = [ln for ln in out.stdout.splitlines() if ln.startswith("[")]
    if not lines:
        raise SystemExit(f"psql failed for serve={serve}: {out.stdout[-300:]} {out.stderr[-500:]}")
    return {r["doc"]: r for r in json.loads(lines[0])}


def plain(values: dict) -> dict:
    return {k: (x.get("value") if isinstance(x, dict) else x) for k, x in values.items()}


def main(psql: str) -> int:
    rows = [a for c in FIXTURE["cases"] for a in c["artifacts"]]
    by_serve: dict[tuple, list] = defaultdict(list)
    for case in FIXTURE["cases"]:
        for variant in case.get("variants", []):
            by_serve[tuple(variant["serve"])].append((case, variant))
    compared = bad = 0
    for serve, items in by_serve.items():
        got = run_variant(psql, list(serve), rows)
        for case, variant in items:
            doc = case["artifacts"][0]["document_id"]
            row = got.get(doc)
            compared += 1
            if row is None or row["base"] != case["base_artifact_id"] or plain(row["vals"]) != variant["values"]:
                bad += 1
                print("MISMATCH", case["name"], list(serve), None if row is None else (row["base"], plain(row["vals"])), variant["values"])
    print(f"sql leg: {compared} comparisons over {len(by_serve)} served sets, {bad} mismatches")
    return 1 if bad else 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit(__doc__)
    sys.exit(main(sys.argv[1]))
