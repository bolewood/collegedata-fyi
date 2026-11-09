import { readdirSync, readFileSync, statSync } from "node:fs";
import { join, relative } from "node:path";
import { describe, expect, it } from "vitest";
import searchableSlugAliases from "../data/searchable-slug-aliases.json";
import {
  ALIGNMENT_GAP_MERIT_SCHOOLS,
  ALIGNMENT_GAP_SCHOOLS,
} from "./alignment-gap-recipe-data";
import { ENDOWMENT_DRAW_RATE_SCHOOLS } from "./endowment-draw-rate-recipe-data";
import { PRICING_POWER_SCHOOLS } from "./pricing-power-recipe-data";
import { WAITLIST_ROWS } from "./waitlist-recipe-data";

const SCANNED_EXTENSIONS = /\.(ts|tsx|js|jsx|mjs|cjs|json|md)$/;
const TEST_FILE = /\.test\.(ts|tsx|js|jsx)$/;

function escapeRegExp(value: string): string {
  return value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

function sourceFiles(dir: string): string[] {
  return readdirSync(dir).flatMap((name) => {
    const fullPath = join(dir, name);
    if (statSync(fullPath).isDirectory()) return sourceFiles(fullPath);
    if (!SCANNED_EXTENSIONS.test(name) || TEST_FILE.test(name)) return [];
    return [fullPath];
  });
}

describe("searchable canonical school slugs", () => {
  it("lists all nine PR #187 federal alias slugs and their canonical targets", () => {
    expect(
      searchableSlugAliases.map((entry) => [entry.alias, entry.school_id]),
    ).toEqual([
      ["california-institute-of-technology", "caltech"],
      ["georgia-institute-of-technology-main-campus", "georgia-tech"],
      ["rutgers-university-new-brunswick", "rutgers"],
      ["texas-a-and-m-university-college-station", "texas-am"],
      ["tulane-university-of-louisiana", "tulane-university"],
      ["university-of-chicago", "uchicago"],
      ["university-of-virginia-main-campus", "uva"],
      ["university-of-washington-seattle-campus", "uw"],
      ["virginia-polytechnic-institute-and-state-university", "virginia-tech"],
    ]);
  });

  it("no web/src file links to /schools/<alias-slug> for the nine renamed schools", () => {
    const root = process.cwd();
    const files = sourceFiles(join(root, "src"));
    const aliasPatterns = searchableSlugAliases.map(({ alias, school_id }) => ({
      alias,
      schoolId: school_id,
      linkPattern: new RegExp(
        `/schools/${escapeRegExp(alias)}(?=[/"'\\s?#)\`]|$)`,
      ),
      idPattern: new RegExp(
        `["']?schoolId["']?\\s*:\\s*["']${escapeRegExp(alias)}["']`,
      ),
    }));

    const offenders = files.flatMap((file) => {
      const text = readFileSync(file, "utf8");
      const rel = relative(root, file);
      return aliasPatterns.flatMap(({ alias, schoolId, linkPattern, idPattern }) => {
        const hits: string[] = [];
        if (linkPattern.test(text)) {
          hits.push(`${rel} links to /schools/${alias} (use /schools/${schoolId})`);
        }
        if (idPattern.test(text)) {
          hits.push(`${rel} sets schoolId to ${alias} (use ${schoolId})`);
        }
        return hits;
      });
    });

    expect(offenders).toEqual([]);
  });

  it("recipe datasets use canonical schoolId and /schools/<canonical> URLs", () => {
    const aliasSet = new Set(searchableSlugAliases.map((entry) => entry.alias));

    for (const row of WAITLIST_ROWS) {
      expect(aliasSet.has(row.schoolId), `waitlist schoolId ${row.schoolId}`).toBe(
        false,
      );
      for (const { alias } of searchableSlugAliases) {
        expect(row.schoolUrl).not.toContain(`/schools/${alias}`);
        expect(row.archiveUrl ?? "").not.toContain(`/schools/${alias}`);
      }
    }

    for (const row of PRICING_POWER_SCHOOLS) {
      expect(
        aliasSet.has(row.schoolId),
        `pricing-power schoolId ${row.schoolId}`,
      ).toBe(false);
    }

    for (const row of ALIGNMENT_GAP_SCHOOLS) {
      expect(
        aliasSet.has(row.schoolId),
        `alignment-gap endowment schoolId ${row.schoolId}`,
      ).toBe(false);
    }

    for (const row of ALIGNMENT_GAP_MERIT_SCHOOLS) {
      expect(
        aliasSet.has(row.schoolId),
        `alignment-gap merit schoolId ${row.schoolId}`,
      ).toBe(false);
    }

    for (const row of ENDOWMENT_DRAW_RATE_SCHOOLS) {
      if (row.schoolId) {
        expect(
          aliasSet.has(row.schoolId),
          `endowment-draw-rate schoolId ${row.schoolId}`,
        ).toBe(false);
      }
    }

    const vtWaitlist = WAITLIST_ROWS.filter(
      (row) => row.schoolId === "virginia-tech",
    );
    expect(vtWaitlist.length).toBeGreaterThanOrEqual(2);
    for (const row of vtWaitlist) {
      expect(row.schoolUrl).toMatch(/^\/schools\/virginia-tech\//);
    }
  });
});
