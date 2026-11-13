import { describe, expect, it } from "vitest";
import { readdirSync, readFileSync } from "node:fs";
import { join } from "node:path";

// PRD 038 A2/A13/A15: the SQL leg of the overlay serving rules is a text assertion here (the repo has no live-Postgres test pattern).
// The semantics are checked by running the migration over the shared fixture: tools/browser_backend/run_overlay_sql_fixture.py
// (read-only, SELECT only) and run_overlay_migration_local.py (a throwaway local Postgres), both by hand, not CI.
const root = join(process.cwd(), "..");
const pending = readFileSync(join(root, "supabase/migrations/20261113042000_overlay_serving_view.sql"), "utf8");
const columnMigration = readFileSync(join(root, "supabase/migrations/20261113042100_school_browser_rows_overlay_producer_version.sql"), "utf8");
const current = readFileSync(join(root, "supabase/migrations/20260428153000_tier4_fallback_compatibility.sql"), "utf8");

const selectColumns = (sql: string) => {
  const head = sql.slice(sql.lastIndexOf("SELECT\n  b.document_id"), sql.indexOf("FROM ranked_base b"));
  return head
    .split("\n")
    .map((line) => line.match(/AS\s+(\w+),?\s*$/)?.[1] ?? line.match(/^\s*b\.(\w+),?\s*$/)?.[1])
    .filter(Boolean);
};

describe("supabase/migrations/20261113042000_overlay_serving_view.sql", () => {
  it("is a migration, the pending serving file is gone and the Decision 1 diff query stays pending", () => {
    const migrations = readdirSync(join(root, "supabase/migrations"));
    expect(migrations).toContain("20261113042000_overlay_serving_view.sql");
    expect(readdirSync(join(root, "supabase/pending")).sort()).toEqual(["038_decision1_selection_diff.sql", "README.md"]);
  });

  it("creates the STABLE function with the default classes before the view, and grants execute", () => {
    expect(pending).toMatch(/FUNCTION public\.cds_overlay_serve_classes\(\)\s+RETURNS text\[\]\s+LANGUAGE sql\s+STABLE\s+AS \$\$ SELECT ARRAY\['numeric', 'choice', 'checkbox_box', 'ocr_numeric'\]::text\[\] \$\$/);
    expect(pending).not.toMatch(/IMMUTABLE/);
    expect(pending.indexOf("FUNCTION public.cds_overlay_serve_classes()")).toBeLessThan(pending.indexOf("CREATE OR REPLACE VIEW public.cds_selected_extraction_result"));
    expect(pending).toContain("GRANT EXECUTE ON FUNCTION public.cds_overlay_serve_classes() TO anon, authenticated, service_role;");
    expect(pending).toContain("cardinality(sv.classes) > 0");
    expect(pending).not.toMatch(/current_setting|set_config/); // no GUC
    expect(pending).toContain("ROLLBACK");
    expect(pending).toContain("SELECT '{}'::text[]");           // the rollback statement is documented in the header
  });

  it("only asserts schema shape in its DO block, never row counts", () => {
    const block = pending.slice(pending.lastIndexOf("DO $$"));
    expect(block).toContain("to_regprocedure('public.cds_overlay_serve_classes()')");
    expect(block).toContain("information_schema.columns");
    expect(block).not.toMatch(/count\(|FROM public\.cds_artifacts|cds_selected_extraction_result\s*\)/i);
  });

  it("requires strict sha equality, only for a Tier 4 base whose sha is recorded", () => {
    expect(pending).toContain("NULLIF(a.notes ->> 'source_sha256', '') =");
    expect(pending).toContain("COALESCE(NULLIF(b.notes ->> 'source_sha256', ''), NULLIF(b.notes -> 'source_artifact' ->> 'sha256', ''))");
    expect(pending).toContain("IS NOT NULL");
    expect(pending).toContain("b.producer = 'tier4_docling'");
    expect(pending).toContain("a.schema_version = b.schema_version");
    expect(pending).toContain("NULLIF(b.schema_version, '') IS NOT NULL");
    expect(pending).toContain("NULLIF(a.schema_version, '') IS NOT NULL");
    expect(pending).toContain("a.producer = 'tier2_template_overlay'");
    expect(pending).toContain("a.kind = 'cleaned'");
  });

  it("filters by served class and applies the Lane 2 / vector-page rule", () => {
    expect(pending).toContain("e.value ->> 'emission_class' = ANY (sv.classes)");
    // lane 2 in any spelling (2, 2.0, "2") on the record and inside derived_lanes
    expect(pending).toContain("(e.value ->> 'lane')::numeric = 2");
    expect(pending).toContain("btrim(e.value ->> 'lane')::numeric = 2");
    expect(pending).toContain("jsonb_array_elements(");
    expect(pending).toContain("(d.lane #>> '{}')::numeric = 2");
    // ocr_numeric: Lane 2 evidence, then a direct value needs page_kind 'vector' and a derived total needs only-vector input kinds
    expect(pending).toContain("WHEN e.value ->> 'emission_class' = 'ocr_numeric' THEN");
    expect(pending).toContain("(f.lane_two OR f.derived_two)");
    expect(pending).toContain("CASE WHEN f.lane_two THEN e.value ->> 'page_kind' = 'vector' ELSE f.inputs_all_vector END");
    expect(pending).toContain("ELSE NOT (f.lane_two OR f.derived_two)");
    expect(pending).toContain("jsonb_array_length(e.value -> 'input_page_kinds') > 0");
    expect(pending).toContain("k.kind IS DISTINCT FROM '\"vector\"'::jsonb");
  });

  it("validates the whole served set, skips blanks and guards a non-object values", () => {
    expect(pending).toMatch(/WHEN c <@ ARRAY\['numeric', 'choice', 'checkbox_box', 'checkbox_boxless', 'free_text', 'ocr_numeric'\]::text\[\]\s+THEN c\s+ELSE '\{\}'::text\[\]/);
    expect(pending).toContain("COALESCE(NULLIF(btrim(e.value ->> 'value_decoded'), ''), NULLIF(btrim(e.value ->> 'value'), '')) IS NOT NULL");
    expect(pending).toContain("jsonb_typeof(o.notes -> 'values') = 'object'");
  });

  it("excludes held overlays (held must be exactly false) and takes the newest", () => {
    expect(pending).toContain("(a.notes -> 'held') = 'false'::jsonb");
    expect(pending).toMatch(/ORDER BY a\.created_at DESC, a\.id DESC\s+LIMIT 1\s+\) o/);
  });

  it("merges fallback || tier4 base || overlay (overlay last, so it wins)", () => {
    const merge = pending.slice(pending.indexOf("AS selected_values") - 400, pending.indexOf("AS selected_values"));
    const fallback = merge.indexOf("f.notes -> 'values'");
    const base = merge.indexOf("b.notes -> 'values'");
    const overlay = merge.indexOf("ov.served_values");
    expect(fallback).toBeGreaterThanOrEqual(0);
    expect(fallback).toBeLessThan(base);
    expect(base).toBeLessThan(overlay);
  });

  it("exposes exactly the columns of the current view", () => {
    expect(selectColumns(pending)).toEqual(selectColumns(current));
    expect(selectColumns(current)).toContain("selected_values");
  });

  it("is not the Decision 1 selection change: the base ranking is untouched", () => {
    expect(pending).toContain("WHERE b.rn = 1");
    expect(pending).not.toMatch(/current_sha|source_selection/);
    const code = pending.split("\n").filter((line) => !line.trim().startsWith("--")).join("\n");
    expect(code).not.toMatch(/hold_threshold|disagree/i); // the disagreement hold is a write-time fact, not evaluated here
    const diff = readFileSync(join(root, "supabase/pending/038_decision1_selection_diff.sql"), "utf8");
    expect(diff).not.toMatch(/\b(INSERT|UPDATE|DELETE|CREATE|ALTER|DROP)\b/);
  });
});

describe("supabase/migrations/20261113042100_school_browser_rows_overlay_producer_version.sql", () => {
  it("adds the nullable column and writes it through the RPC (insert list, select list and record definition)", () => {
    expect(columnMigration).toContain("ADD COLUMN IF NOT EXISTS overlay_producer_version text");
    expect(columnMigration.split("ADD COLUMN")[1].split(";")[0]).not.toMatch(/NOT NULL|DEFAULT/i);       // nullable, no default
    const fn = columnMigration.slice(columnMigration.indexOf("CREATE OR REPLACE FUNCTION public.replace_browser_projection_for_document"));
    const browser = fn.slice(fn.indexOf("INSERT INTO public.school_browser_rows"));
    expect(browser.match(/overlay_producer_version,\n/g)?.length).toBe(2);        // insert list and select list
    expect(browser).toContain("overlay_producer_version text,");                   // jsonb_to_record column definition
    // the field-row projection (cds_fields) is untouched
    expect(fn.slice(0, fn.indexOf("INSERT INTO public.school_browser_rows"))).not.toContain("overlay_producer_version");
  });
});
