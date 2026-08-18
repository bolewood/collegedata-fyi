import { describe, expect, it } from "vitest";
import { readFileSync } from "node:fs";
import { join } from "node:path";

describe("PRD 029 demand tier is independent of PRD 019", () => {
  it("ranks from school_browser_rows.applied and does not query the operator-only watchlist", () => {
    const root = join(process.cwd(), "..");
    const sql = readFileSync(
      join(root, "supabase/migrations/20260818120000_cds_publish_events.sql"),
      "utf8",
    );
    const fnBody = sql.slice(
      sql.indexOf("create or replace function public.publish_alert_tier_schools"),
      sql.indexOf("comment on function public.publish_alert_tier_schools"),
    );
    expect(fnBody).toContain("school_browser_rows");
    expect(fnBody).toContain("sbr.applied");
    expect(fnBody).not.toContain("top_200_change_intelligence.yaml");

    for (const rel of [
      "supabase/functions/archive-enqueue/index.ts",
      "supabase/functions/archive-enqueue/schedule.ts",
    ]) {
      const text = readFileSync(join(root, rel), "utf8");
      expect(text).not.toContain("top_200_change_intelligence");
    }
  });
});
