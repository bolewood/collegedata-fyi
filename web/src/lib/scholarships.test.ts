import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";
import fixture from "./__fixtures__/scholarship-directory.json";
import {
  SCHOLARSHIP_ATTRIBUTION,
  amountText,
  benefitLine,
  conflictTopics,
  consideredLines,
  countProgramsByControl,
  coverageSummary,
  deadlineLine,
  filterRows,
  freshnessLine,
  freshnessShort,
  normalizeScholarshipRow,
  renewalSummary,
  sortRows,
  EMPTY_FILTERS,
  type Benefit,
  type IndexRow,
  type ScholarshipDirectoryRow,
} from "./scholarships";

// 24 rows built by tools/scholarships/export_web_fixture.py from the 23 real
// canary records (Robertson is one program at Duke and UNC), as of 2026-11-14.
const ROWS = (fixture as unknown[]).map(normalizeScholarshipRow) as ScholarshipDirectoryRow[];
const row = (programId: string, schoolId?: string) => {
  const r = ROWS.find((x) => x.program_id === programId && (!schoolId || x.school_id === schoolId));
  if (!r) throw new Error(`fixture row ${programId} missing`);
  return r;
};
const FORBIDDEN = /\b(verified|full ride|best|odds of winning|guaranteed)\b/i;

describe("attribution", () => {
  it("is the exact line in data/scholarships/LICENSE", () => {
    const license = readFileSync(resolve(__dirname, "../../../data/scholarships/LICENSE"), "utf8");
    const line = license.split("\n").map((l) => l.trim()).find((l) => l.startsWith("Scholarship program data from"));
    expect(line).toBe(SCHOLARSHIP_ATTRIBUTION);
  });
  it("matches the string every fixture row carries", () => {
    for (const r of ROWS) expect(r.attribution).toBe(SCHOLARSHIP_ATTRIBUTION);
  });
});

describe("fixture", () => {
  it("holds the 23 canary programs as 24 per-school rows", () => {
    expect(ROWS).toHaveLength(24);
    expect(new Set(ROWS.map((r) => r.program_id)).size).toBe(23);
    expect(ROWS.filter((r) => r.program_id === "robertson-scholars").map((r) => r.school_id).sort()).toEqual(["duke", "unc"]);
  });
});

describe("amountText", () => {
  it("keeps the school's qualifier and period", () => {
    expect(amountText({ qualifier: "exact", value: 20000, min: null, max: null, period: "academic_year" })).toBe("$20,000 a year");
    expect(amountText({ qualifier: "up_to", value: 12000, min: null, max: null, period: "total_program" })).toBe("up to $12,000 in total");
    expect(amountText({ qualifier: "range", value: null, min: 4000, max: 8000, period: "academic_year" })).toBe("$4,000 to $8,000 a year");
    expect(amountText({ qualifier: "not_published", value: null, min: null, max: null, period: null })).toBeNull();
  });
});

describe("coverage summary", () => {
  it("names a waiver as a waiver and shows its condition (real: Texas A&M)", () => {
    const tamu = row("national-merit-scholars", "texas-am");
    const waiver = tamu.offers.flatMap((o) => o.benefits ?? []).find((b) => b.instrument === "tuition_waiver" && b.conditions_text);
    expect(waiver).toBeTruthy();
    const line = benefitLine(waiver as Benefit);
    expect(line.flags.waiver).toBe(true);
    expect(line.flags.conditional).toBe(true);
    expect(line.text).toMatch(/^waiver, not a scholarship/);
    expect(line.text).toMatch(/Condition: Needs competitive scholarships/);
    expect(line.text).not.toMatch(/tuition covered|covers all/i);
  });

  it("shows a capped housing benefit as capped (derived from a real housing benefit)", () => {
    const real = ROWS.flatMap((r) => r.offers).flatMap((o) => o.benefits ?? []).find((b) => b.category === "housing");
    expect(real).toBeTruthy();
    // Derived: a real housing benefit with the school's amount set to "up to".
    const capped: Benefit = {
      ...(real as Benefit),
      coverage: "full",
      amount: { qualifier: "up_to", value: 11000, min: null, max: null, period: "academic_year" },
    };
    const line = benefitLine(capped);
    expect(line.label).toBe("Housing");
    expect(line.flags.capped).toBe(true);
    expect(line.text).toBe("capped. Up to $11,000 a year.");
  });

  it("shows a conditional benefit with its condition (real: Texas A&M stipend line)", () => {
    const tamu = row("national-merit-scholars", "texas-am");
    const cond = tamu.offers.flatMap((o) => o.benefits ?? []).find((b) => b.conditions_text && b.instrument !== "tuition_waiver");
    expect(cond).toBeTruthy();
    const line = benefitLine(cond as Benefit);
    expect(line.flags.conditional).toBe(true);
    expect(line.text).toMatch(/Condition: Only for Finalists/);
  });

  it("shows school-quoted totals as quotes with their scope, never summed (real: Washington and Lee, Oklahoma)", () => {
    const wl = row("johnson-scholarship");
    const offer = wl.offers.find((o) => (o.advertised_totals ?? []).length > 0)!;
    const summary = coverageSummary(offer, wl.offers);
    expect(summary.quotedTotals[0].quote).toBe("at least $89,000 a year");
    expect(summary.quotedTotals[0].scope).toMatch(/not a sum made here/);
    const ou = row("national-merit-nonresident-package");
    const quoted = ou.offers.flatMap((o) => coverageSummary(o, ou.offers).quotedTotals);
    expect(quoted.map((q) => q.quote)).toContain("$70,000 in total");
    // No line of ours adds components into a number.
    for (const o of wl.offers) for (const b of coverageSummary(o, wl.offers).benefits) expect(b.text).not.toMatch(/total of|combined/i);
  });

  it("says a tier builds on its parent (real: Texas A&M)", () => {
    const al = row("national-merit-scholars", "texas-am");
    const tier = al.offers.find((o) => o.parent_offer_id)!;
    const summary = coverageSummary(tier, al.offers);
    expect(summary.parentName).toBeTruthy();
  });

  it("handles a retired program with no offers without inventing coverage (real: Vanderbilt Chancellor's)", () => {
    const vandy = row("chancellors-scholarship");
    expect(vandy.offers).toEqual([]);
    expect(vandy.coverages).toEqual([]);
    expect(vandy.program_status_for_entry).toBe("closed_to_new_entrants");
  });
});

describe("considered versus guaranteed", () => {
  it("uses different words for competitive and automatic", () => {
    const base = ROWS[0].offers[0];
    const comp = consideredLines({ ...base, selection_mode: "competitive" })[0];
    const auto = consideredLines({ ...base, selection_mode: "automatic_guaranteed" })[0];
    expect(comp).toMatch(/^Competitive/);
    expect(auto).toMatch(/^Automatic if you meet/);
    expect(consideredLines({ ...base, selection_mode: "unknown" })[0]).toBe("How recipients are chosen is not stated.");
  });
});

describe("freshness line", () => {
  it("states the entering class and the date for a stated class (real: Tulsa)", () => {
    const r = row("national-merit-semifinalist-package");
    expect(r.cycle_basis).toBe("entry_year");
    const line = freshnessLine(r);
    expect(line.tone).toBe("plain");
    expect(line.text).toMatch(/^Terms for fall 2027 entry, as published on the school's page [A-Z][a-z]{2} \d{1,2}, 2026\.$/);
  });

  it("says the dates run through a month and the page names no class (real: milestone_dates)", () => {
    const r = ROWS.find((x) => x.cycle_basis === "milestone_dates" && x.freshness_status === "current_cycle_verified")!;
    const line = freshnessLine(r);
    expect(line.text).toMatch(/^The dates on the school's page run through [A-Z][a-z]+ \d{4}\. The page does not name the entering class\./);
    expect(line.text).not.toMatch(/entry/);
  });

  it("says the page names no year, with the date we read it (real: year_not_stated)", () => {
    const r = ROWS.find((x) => x.freshness_status === "year_not_stated")!;
    const line = freshnessLine(r);
    expect(line.tone).toBe("plain");
    expect(line.text).toMatch(/^The school's page does not name a year\. We read it [A-Z][a-z]{2} \d{1,2}, 2026\.$/);
  });

  it("is amber and says the cycle has passed for a past cycle (real: Arizona)", () => {
    const r = row("national-merit-scholars-tuition-award");
    expect(r.freshness_status).toBe("past_cycle");
    const line = freshnessLine(r);
    expect(line.tone).toBe("amber");
    expect(line.text).toMatch(/^These terms may be out of date\. The page we read described fall 2026 entry, which has passed\./);
  });

  it("is amber and names what disagrees for conflicting pages (real: Tuskegee, UCF)", () => {
    const tusk = row("distinguished-presidential-scholarship");
    const line = freshnessLine(tusk);
    expect(line.tone).toBe("amber");
    expect(line.text).toMatch(/^The school's pages disagree on whether a separate application is needed and a date\./);
    const ucf = freshnessLine(row("national-merit-benacquisto"));
    expect(ucf.text).toMatch(/disagree on how recipients are chosen/);
    // No named field falls back to a plain statement, not a guess.
    const bare = freshnessLine({ ...tusk, evidence: [] });
    expect(bare.text).toMatch(/^The school's pages disagree with each other\./);
  });

  it("says terms have not been re-read when unconfirmed", () => {
    const r = { ...row("national-merit-semifinalist-package"), freshness_status: "current_cycle_unconfirmed" as const };
    expect(freshnessLine(r)).toMatchObject({ tone: "plain" });
    expect(freshnessLine(r).text).toMatch(/^These terms have not been re-read for this cycle\. Last read /);
  });

  it("handles past cycle by milestone dates, aged-out, and historical-only without rolling dates forward", () => {
    const base = row("national-merit-semifinalist-package");
    const byDates = freshnessLine({ ...base, freshness_status: "past_cycle", cycle_basis: "milestone_dates", entry_year: null, cycle_through_date: "2026-10-15" });
    expect(byDates.text).toMatch(/ran through October 2026, which have passed/);
    const aged = freshnessLine({ ...base, freshness_status: "past_cycle", cycle_basis: "none", entry_year: null, cycle_through_date: null });
    expect(aged.text).toMatch(/named no year, and a newer cycle has begun/);
    const hist = freshnessLine({ ...base, freshness_status: "past_cycle", verification_status: "historical_only" });
    expect(hist.text).toMatch(/^Kept for reference/);
  });

  it("never uses banned words for any fixture row, and short labels agree", () => {
    for (const r of ROWS) {
      expect(freshnessLine(r).text).not.toMatch(FORBIDDEN);
      expect(freshnessShort(r).text.length).toBeGreaterThan(0);
    }
    const past = freshnessShort(row("national-merit-scholars-tuition-award"));
    expect(past).toEqual({ tone: "amber", text: "Past cycle" });
  });

  it("names conflict topics once each", () => {
    expect(conflictTopics([
      { field_path: "renewal_rules/0/gpa_min", value_status: "conflicting" },
      { field_path: "renewal_rules/0/gpa_min", value_status: "conflicting" },
      { field_path: "offers/0/selection_mode", value_status: "reported" },
    ])).toEqual(["the renewal GPA"]);
  });
});

describe("deadline and renewal", () => {
  it("prints a dated deadline with a confirm line, and marks a passed one", () => {
    const r = row("robertson-scholars", "duke");
    const d = deadlineLine(r, "2026-11-14");
    expect(d.text).toMatch(/^Required deadline: Nov 15, 2026/);
    expect(d.text).toMatch(/Confirm on the official page\.$/);
    expect(d.past).toBe(false);
    expect(deadlineLine(r, "2026-11-20").past).toBe(true);
  });
  it("never invents a deadline", () => {
    const none = ROWS.find((r) => !r.key_deadline && !(r.application?.milestones ?? []).some((m) => m.recurring))!;
    expect(deadlineLine(none, "2026-11-14").text).toBe("No deadline stated on the page we read.");
  });
  it("distinguishes not documented from documented as none", () => {
    expect(renewalSummary(null)).toEqual(["Renewal terms not documented."]);
    expect(renewalSummary([])).toEqual(["The school's page lists no renewal conditions."]);
    expect(renewalSummary([{ gpa_min: 3, gpa_scale: 4, credit_load_min_per_term: 12, max_semesters: 8 }])[0])
      .toBe("Keep a 3.0 GPA on a 4 scale, 12 credits a term, up to 8 semesters.");
  });
});

describe("index filters and sort", () => {
  const index: IndexRow[] = ROWS.map((r) => ({ ...r, school_name: r.school_id }));
  it("filters by coverage, National Merit and school name", () => {
    expect(filterRows(index, { ...EMPTY_FILTERS, coverage: "full_tuition" }).every((r) => r.coverages.includes("full_tuition"))).toBe(true);
    expect(filterRows(index, { ...EMPTY_FILTERS, nationalMerit: "finalist" }).length).toBeGreaterThan(0);
    expect(filterRows(index, { ...EMPTY_FILTERS, school: "TULSA" }).map((r) => r.school_id)).toEqual(["university-of-tulsa"]);
  });
  it("sorts by deadline with undated rows last, never by generosity", () => {
    const sorted = sortRows(index, "deadline");
    const dated = sorted.filter((r) => r.key_deadline).map((r) => r.key_deadline!);
    expect([...dated].sort()).toEqual(dated);
    const firstUndated = sorted.findIndex((r) => !r.key_deadline);
    expect(sorted.slice(firstUndated).every((r) => !r.key_deadline)).toBe(true);
    expect(sortRows(index, "school").map((r) => r.school_name)).toEqual([...index.map((r) => r.school_name)].sort((a, b) => a.localeCompare(b)));
  });
  it("counts a shared program once, by its lead school", () => {
    const counts = countProgramsByControl(ROWS, (id) => (id === "duke" ? "private_nonprofit" : id === "unc" ? "public" : "unknown"));
    expect(counts.private_nonprofit).toBeGreaterThanOrEqual(2); // Karsh and Robertson at Duke
    expect(counts.public + counts.private_nonprofit + counts.unknown).toBe(23);
  });
});
