import { describe, expect, it } from "vitest";
import { readdirSync, readFileSync } from "node:fs";
import { join } from "node:path";

// PRD 038 A2/A13: the SQL leg of the overlay serving rules is a text assertion (the repo has no live-Postgres
// test pattern; the same fixture runs by hand against `supabase start` when it is available: not run in M3).
const root = join(process.cwd(), "..");
const pending = readFileSync(join(root, "supabase/pending/038_overlay_serving.sql"), "utf8");
const current = readFileSync(join(root, "supabase/migrations/20260428153000_tier4_fallback_compatibility.sql"), "utf8");

const selectColumns = (sql: string) => {
  const head = sql.slice(sql.lastIndexOf("SELECT\n  b.document_id"), sql.indexOf("FROM ranked_base b"));
  return head
    .split("\n")
    .map((line) => line.match(/AS\s+(\w+),?\s*$/)?.[1] ?? line.match(/^\s*b\.(\w+),?\s*$/)?.[1])
    .filter(Boolean);
};

describe("supabase/pending/038_overlay_serving.sql", () => {
  it("is not under supabase/migrations", () => {
    const migrations = readdirSync(join(root, "supabase/migrations"));
    expect(migrations.some((name) => name.includes("overlay_serving"))).toBe(false);
    expect(readFileSync(join(root, "supabase/pending/README.md"), "utf8")).toContain("**not** a migration");
  });

  it("serves nothing by default: cds_overlay_serve_classes() returns an empty array", () => {
    expect(pending).toMatch(/FUNCTION public\.cds_overlay_serve_classes\(\)\s+RETURNS text\[\][\s\S]*?SELECT '\{\}'::text\[\]/);
    expect(pending).toContain("cardinality(public.cds_overlay_serve_classes()) > 0");
    expect(pending).not.toMatch(/current_setting|set_config/); // no GUC
  });

  it("requires strict sha equality, only for a Tier 4 base whose sha is recorded", () => {
    expect(pending).toContain("a.notes ->> 'source_sha256' =");
    expect(pending).toContain("COALESCE(b.notes ->> 'source_sha256', b.notes -> 'source_artifact' ->> 'sha256')");
    expect(pending).toContain("IS NOT NULL");
    expect(pending).toContain("b.producer = 'tier4_docling'");
    expect(pending).toContain("a.schema_version = b.schema_version");
    expect(pending).toContain("b.schema_version IS NOT NULL");
    expect(pending).toContain("a.producer = 'tier2_template_overlay'");
    expect(pending).toContain("a.kind = 'cleaned'");
  });

  it("filters by served class and never serves Lane 2 evidence", () => {
    expect(pending).toContain("e.value ->> 'emission_class' = ANY (public.cds_overlay_serve_classes())");
    expect(pending).toContain("COALESCE(e.value ->> 'lane', '') <> '2'");
    expect(pending).toContain("NOT (COALESCE(e.value -> 'derived_lanes', '[]'::jsonb) @> '2'::jsonb)");
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
    const diff = readFileSync(join(root, "supabase/pending/038_decision1_selection_diff.sql"), "utf8");
    expect(diff).not.toMatch(/\b(INSERT|UPDATE|DELETE|CREATE|ALTER|DROP)\b/);
  });
});
