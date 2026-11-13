#!/usr/bin/env python3
"""PRD 038 A15: run the two serving migrations on a THROWAWAY local Postgres (not production, not Supabase) and check them
against the shared parity fixture. NOT part of CI.

    python tools/browser_backend/run_overlay_migration_local.py PG_BIN_DIR PG_SOCKET_DIR PORT TABLES_SQL

The local server must already be running and empty. TABLES_SQL (not in the repo; I produced it by selecting column_name, udt_name and is_nullable from production's information_schema.columns, read-only, for the three tables, and writing one CREATE TABLE per table) creates minimal copies of public.cds_artifacts (id and document_id as
text so the fixture ids fit), public.cds_fields and public.school_browser_rows (the columns production has). The script then:
  1. creates roles and the `extensions` schema, applies the PREVIOUS view definition (20260428153000), loads the fixture rows and
     snapshots the old view's output;
  2. applies 20261113042000 (function + view) and checks that with the function replaced by '{}' the new view equals the old view on
     every row and column, that the default function returns the four default classes, that anon/authenticated can SELECT the view,
     and that every fixture variant resolves as recorded when the function returns that variant's served set;
  3. applies 20261113042100 (column + RPC), checks the RPC stores overlay_producer_version, and that an RPC call without the key
     (the window before the migration) still works."""
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = json.loads((ROOT / "tools/browser_backend/fixtures/overlay_parity.json").read_text())


def main(bin_dir: str, sock: str, port: str, tables_sql: str) -> int:
    def sql(text: str, db: str = "postgres", tuples: bool = True) -> str:
        r = subprocess.run([f"{bin_dir}/psql", "-h", sock, "-p", port, "-U", "postgres", "-d", db, "-v", "ON_ERROR_STOP=1", "-X", "-q"]
                           + (["-At"] if tuples else []), input=text, capture_output=True, text=True)
        if r.returncode:
            raise SystemExit(f"psql failed: {r.stderr[-800:]}")
        return r.stdout

    bad = 0

    def check(ok: bool, what: str) -> None:
        nonlocal bad
        if not ok:
            bad += 1
            print("FAIL", what)

    sql("DROP DATABASE IF EXISTS overlay_local;")
    sql("CREATE DATABASE overlay_local;")
    db = "overlay_local"
    sql("""
      DO $$ BEGIN CREATE ROLE anon NOLOGIN; EXCEPTION WHEN duplicate_object THEN NULL; END $$;
      DO $$ BEGIN CREATE ROLE authenticated NOLOGIN; EXCEPTION WHEN duplicate_object THEN NULL; END $$;
      DO $$ BEGIN CREATE ROLE service_role NOLOGIN; EXCEPTION WHEN duplicate_object THEN NULL; END $$;
      CREATE SCHEMA extensions;
      CREATE EXTENSION pgcrypto WITH SCHEMA extensions;
      GRANT USAGE ON SCHEMA public, extensions TO anon, authenticated, service_role;
    """, db)
    sql(Path(tables_sql).read_text().replace('"id" uuid', '"id" text').replace('"document_id" uuid NOT NULL,\n  "kind"', '"document_id" text NOT NULL,\n  "kind"'), db)
    sql("GRANT SELECT ON public.cds_artifacts, public.cds_fields, public.school_browser_rows TO anon, authenticated, service_role;", db)
    # 1. the previous view and the fixture rows
    old_view = (ROOT / "supabase/migrations/20260428153000_tier4_fallback_compatibility.sql").read_text()
    sql(old_view, db)
    sql("GRANT SELECT ON public.cds_selected_extraction_result TO anon, authenticated;", db)
    rows = [a for c in FIXTURE["cases"] for a in c["artifacts"]]
    ins = "INSERT INTO public.cds_artifacts (id, document_id, kind, producer, producer_version, schema_version, created_at, notes) SELECT id, document_id, kind, producer, producer_version, schema_version, created_at, notes FROM jsonb_to_recordset($j$" \
          + json.dumps(rows) + "$j$::jsonb) AS t(id text, document_id text, kind text, producer text, producer_version text, schema_version text, created_at timestamptz, notes jsonb);"
    sql(ins, db)
    sql("CREATE TABLE old_result AS SELECT * FROM public.cds_selected_extraction_result;", db)
    # 2. migration 1
    mig1 = (ROOT / "supabase/migrations/20261113042000_overlay_serving_view.sql").read_text()
    sql(mig1, db)
    check(sql("SELECT sorted FROM (SELECT array_agg(x ORDER BY x) AS sorted FROM unnest(public.cds_overlay_serve_classes()) x) s", db).strip()
          == "{checkbox_box,choice,numeric,ocr_numeric}", "the default function returns the four default classes")
    check(sql("SELECT provolatile FROM pg_proc WHERE proname = 'cds_overlay_serve_classes'", db).strip() == "s", "the function is STABLE")
    for role in ("anon", "authenticated"):
        check(sql(f"SET ROLE {role}; SELECT count(*) FROM public.cds_selected_extraction_result; SELECT unnest(public.cds_overlay_serve_classes());", db).count("\n") > 3,
              f"{role} can select the view and execute the function")

    def set_classes(classes):
        arr = "ARRAY[" + ",".join("'" + c + "'" for c in classes) + "]::text[]"
        sql(f"CREATE OR REPLACE FUNCTION public.cds_overlay_serve_classes() RETURNS text[] LANGUAGE sql STABLE AS $$ SELECT {arr} $$;", db)

    set_classes([])
    diff = sql("SELECT count(*) FROM ((SELECT * FROM public.cds_selected_extraction_result EXCEPT SELECT * FROM old_result) UNION ALL "
               "(SELECT * FROM old_result EXCEPT SELECT * FROM public.cds_selected_extraction_result)) d", db).strip()
    check(diff == "0", f"with the function returning '{{}}' the new view equals the previous view on every row and column ({diff} differing)")
    n_old = sql("SELECT count(*) FROM old_result", db).strip()
    check(sql("SELECT count(*) FROM public.cds_selected_extraction_result", db).strip() == n_old, "same row count")
    by_serve: dict = {}
    for case in FIXTURE["cases"]:
        for v in case.get("variants", []):
            by_serve.setdefault(tuple(v["serve"]), []).append((case, v))
    compared = 0
    for serve, items in by_serve.items():
        set_classes(list(serve))
        out = sql("SELECT coalesce(json_agg(json_build_object('doc', document_id, 'base', base_artifact_id, 'vals', selected_values)), '[]') FROM public.cds_selected_extraction_result", db)
        got = {r["doc"]: r for r in json.loads(out)}
        for case, v in items:
            row = got.get(case["artifacts"][0]["document_id"])
            plain = {k: (x.get("value") if isinstance(x, dict) else x) for k, x in row["vals"].items()}
            compared += 1
            check(row["base"] == case["base_artifact_id"] and plain == v["values"], f"fixture {case['name']} {list(serve)}")
    set_classes(["numeric", "choice", "checkbox_box", "ocr_numeric"])
    # 3. migration 2
    mig2 = (ROOT / "supabase/migrations/20261113042100_school_browser_rows_overlay_producer_version.sql").read_text()
    sql(mig2, db)
    doc = "11111111-1111-1111-1111-111111111111"
    base_row = {"document_id": doc, "school_id": "s", "school_name": "S", "canonical_year": "2025-26", "year_start": 2025, "schema_version": "2025-26",
                "source_format": "pdf_flat", "producer": "tier4_docling", "producer_version": "0.3.17"}
    for payload, expect in (({**base_row, "overlay_producer_version": "0.7.0/choice,numeric"}, "0.7.0/choice,numeric"), (base_row, "")):
        sql(f"SELECT public.replace_browser_projection_for_document('{doc}'::uuid, '[]'::jsonb, $j${json.dumps(payload)}$j$::jsonb);", db)
        got = sql(f"SELECT coalesce(overlay_producer_version, ''), producer_version FROM public.school_browser_rows WHERE document_id = '{doc}'", db).strip()
        check(got == f"{expect}|0.3.17", f"RPC stored {got!r} for {payload.get('overlay_producer_version')!r}")
    check(sql("SELECT count(*) FROM public.school_browser_rows", db).strip() == "1", "the RPC replaced the row")
    print(f"local migration check: {compared} fixture comparisons over {len(by_serve)} served sets, {bad} failures")
    return 1 if bad else 0


if __name__ == "__main__":
    if len(sys.argv) != 5:
        raise SystemExit(__doc__)
    sys.exit(main(*sys.argv[1:]))
