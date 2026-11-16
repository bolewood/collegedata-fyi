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
  toIndexRow,
  selectionCell,
  deadlineCell,
  closedLabel,
  NOT_STATED,
  otherDateLines,
  sourceLabel,
  recurringDeadline,
  relatedItems,
  renewalSummary,
  sortRows,
  EMPTY_FILTERS,
  COVERAGE_LABEL,
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

  it("names a full waiver of tuition itself as waived in full (derived: Hawaii at Manoa Regents)", () => {
    const real = ROWS.flatMap((r) => r.offers).flatMap((o) => o.benefits ?? []).find((b) => b.category === "tuition" && b.coverage === "full" && !b.conditions_text);
    expect(real).toBeTruthy();
    // Derived: a real full-tuition benefit with the instrument set to a waiver and no amount.
    const waived: Benefit = { ...(real as Benefit), instrument: "tuition_waiver", amount: null };
    const line = benefitLine(waived);
    expect(line.flags.waiver).toBe(true);
    expect(line.text).toMatch(/^waived in full by the school\./);
    expect(line.text).not.toMatch(/not a scholarship/);
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
  const TODAY = "2026-11-14";
  const index: IndexRow[] = ROWS.map((r) => toIndexRow(r, r.school_id));
  const ids = (f: Partial<typeof EMPTY_FILTERS>) => filterRows(index, { ...EMPTY_FILTERS, ...f }).map((r) => `${r.school_id}/${r.program_id}`);

  it("filters by coverage, National Merit and school name (non-empty results)", () => {
    const full = filterRows(index, { ...EMPTY_FILTERS, coverage: "full_tuition" });
    expect(full.length).toBeGreaterThan(0);
    expect(full.every((r) => r.coverages.includes("full_tuition"))).toBe(true);
    expect(filterRows(index, { ...EMPTY_FILTERS, nationalMerit: "finalist" }).length).toBeGreaterThan(0);
    expect(filterRows(index, { ...EMPTY_FILTERS, school: "TULSA" }).map((r) => r.school_id)).toEqual(["university-of-tulsa"]);
  });

  it("a residency choice keeps programs open to all residencies, and has a Not stated option", () => {
    // Boston College Gabelli is open to all; it used to vanish under "In-state".
    for (const choice of ["in_state", "out_of_state", "international"]) {
      expect(ids({ residency: choice })).toContain("boston-college/gabelli-presidential-scholars");
    }
    expect(ids({ residency: "any" })).toContain("boston-college/gabelli-presidential-scholars");
    const unstated = ids({ residency: NOT_STATED });
    expect(unstated).toContain("university-of-tulsa/national-merit-semifinalist-package");
    expect(unstated).toContain("vanderbilt/chancellors-scholarship"); // empty residencies
    expect(unstated).not.toContain("boston-college/gabelli-presidential-scholars");
  });

  it("no filter silently drops a record: every row is found by some option of each filter", () => {
    const filters: [keyof typeof EMPTY_FILTERS, string[]][] = [
      ["coverage", [...Object.keys(COVERAGE_LABEL), NOT_STATED]],
      ["selection", ["competitive", "automatic_guaranteed", "hybrid", NOT_STATED]],
      ["separateApplication", ["required", "encouraged", "not_required", "invitation_only", "no_form_other_steps_required", NOT_STATED]],
      ["deadlineMonth", [...Array.from({ length: 12 }, (_, i) => String(i + 1)), NOT_STATED]],
    ];
    for (const [key, options] of filters) {
      const found = new Set(options.flatMap((o) => ids({ [key]: o })));
      for (const r of index) expect(found, `${key}: ${r.school_id}/${r.program_id}`).toContain(`${r.school_id}/${r.program_id}`);
    }
  });

  it("Not stated coverage finds rows with no coverage, and Other no longer claims them", () => {
    expect(ids({ coverage: NOT_STATED })).toEqual(expect.arrayContaining(["uga/stamps-scholars", "vanderbilt/chancellors-scholarship"]));
    expect(ids({ coverage: "other" })).not.toContain("uga/stamps-scholars");
  });

  it("Not stated selection finds Texas A&M, whose offers include unstated ones", () => {
    expect(ids({ selection: NOT_STATED })).toContain("texas-am/national-merit-scholars");
  });

  it("sorts by deadline: upcoming first, then passed, then undated", () => {
    const sorted = sortRows(index, "deadline", TODAY);
    const kinds = sorted.map((r) => (!r.key_deadline ? "none" : r.key_deadline < TODAY ? "passed" : "upcoming"));
    expect(kinds.indexOf("upcoming")).toBe(0);
    const order = { upcoming: 0, passed: 1, none: 2 } as const;
    expect(kinds.map((k) => order[k])).toEqual([...kinds.map((k) => order[k])].sort((a, b) => a - b));
    expect(kinds).toContain("passed"); // Georgia Tech Stamps, 2026-10-15
    const gt = sorted.findIndex((r) => r.program_id === "stamps-presidents-scholars");
    const duke = sorted.findIndex((r) => r.program_id === "robertson-scholars");
    expect(duke).toBeLessThan(gt);
  });

  it("sorts by school and by coverage label, never by generosity", () => {
    expect(sortRows(index, "school", TODAY).map((r) => r.school_name)).toEqual([...index.map((r) => r.school_name)].sort((a, b) => a.localeCompare(b)));
    const labels = sortRows(index, "coverage", TODAY).map((r) => [...r.coverages].map((c) => COVERAGE_LABEL[c]).sort()[0] ?? "~");
    expect(labels).toEqual([...labels].sort((a, b) => a.localeCompare(b)));
  });

  it("marks a passed deadline and never prints a year for a recurring one", () => {
    const gt = index.find((r) => r.program_id === "stamps-presidents-scholars")!;
    expect(deadlineCell(gt, TODAY)).toEqual({ text: "Oct 15, 2026 (passed)", past: true });
    const duke = index.find((r) => r.program_id === "robertson-scholars" && r.school_id === "duke")!;
    expect(deadlineCell(duke, TODAY)).toEqual({ text: "Nov 15, 2026", past: false });
    const tulsa = index.find((r) => r.school_id === "university-of-tulsa")!;
    expect(deadlineCell(tulsa, TODAY).text).toMatch(/^Each [A-Z][a-z]+$/);
  });

  it("the recurring cell follows the deadline_months rule (UCF's May 31 is not a deadline)", () => {
    const ucf = index.find((r) => r.program_id === "national-merit-benacquisto")!;
    expect(ucf.deadline_months).toEqual([]);
    expect(deadlineCell(ucf, TODAY).text).toBe("Not stated");
    expect(recurringDeadline(row("national-merit-benacquisto").application)).toBeNull();
    expect(otherDateLines(row("national-merit-benacquisto").application).join(" ")).toMatch(/not a deadline for the award/);
  });

  it("counts a shared program once, by its lead school", () => {
    const counts = countProgramsByControl(ROWS, (id) => (id === "duke" ? "private_nonprofit" : id === "unc" ? "public" : "unknown"));
    expect(counts.private_nonprofit).toBeGreaterThanOrEqual(2);
    expect(counts.public + counts.private_nonprofit + counts.unknown).toBe(23);
  });
});

describe("the index row carries only what the table reads", () => {
  it("drops offers, evidence, application and renewal from what goes to the browser", () => {
    const slim = toIndexRow(row("national-merit-scholars", "texas-am"), "Texas A&M");
    const keys = Object.keys(slim);
    for (const heavy of ["offers", "evidence", "application", "renewal_rules", "stacking_rules", "award_counts", "attribution"]) {
      expect(keys).not.toContain(heavy);
    }
    expect(JSON.stringify(ROWS.map((r) => toIndexRow(r, r.school_id))).length).toBeLessThan(JSON.stringify(ROWS).length / 8);
    expect(slim.sources.length).toBeLessThanOrEqual(2);
  });
});

describe("program-level selection label", () => {
  it("is shown only when every offer shares it, else 'Varies by award' (Texas A&M, UCF)", () => {
    expect(selectionCell(row("national-merit-scholars", "texas-am").selection_modes)).toBe("Varies by award");
    expect(selectionCell(row("national-merit-benacquisto").selection_modes)).toBe("Varies by award");
    expect(selectionCell(["competitive"])).toBe("Competitive");
    expect(selectionCell(["automatic_guaranteed"])).toBe("Automatic if you qualify");
    expect(selectionCell([])).toBe("Not stated");
    expect(selectionCell(["unknown"])).toBe("Not stated");
  });
});

describe("exclusions, duration and conflicting amounts sit with the benefit", () => {
  const lines = (r: ScholarshipDirectoryRow) =>
    r.offers.flatMap((o) => coverageSummary(o, r.offers, r.evidence).benefits.map((b) => `${b.label}: ${b.text}`));

  it("prints UMD's fee exclusions next to 'covers all of it' (real: Banneker/Key)", () => {
    const fees = lines(row("banneker-key-scholarship")).filter((l) => l.startsWith("Mandatory fees: the school says it covers all of it"));
    expect(fees.length).toBeGreaterThan(0);
    expect(fees.every((l) => /Not included: .*(Miscellaneous fees|departmental fees)/.test(l))).toBe(true);
  });
  it("prints Tuskegee's enrollment-fee exclusion on its fees line (real)", () => {
    const l = lines(row("distinguished-presidential-scholarship")).find((x) => x.startsWith("Mandatory fees"))!;
    expect(l).toMatch(/Not included: .*enrollment fee/i);
  });
  it("prints duration terms (real: Robertson, eight semesters)", () => {
    expect(lines(row("robertson-scholars", "duke")).some((l) => /For Eight semesters\./i.test(l))).toBe(true);
  });
  it("says the pages give different amounts, not 'not published', where the amount conflicts (real: UMD out-of-state tuition)", () => {
    const r = row("banneker-key-scholarship");
    const conflicted = r.evidence.filter((e) => e.value_status === "conflicting" && /benefits\/\d+\/amount$/.test(e.field_path));
    expect(conflicted.length).toBeGreaterThan(0);
    const all = lines(r).join("\n");
    expect(all).toMatch(/Tuition: the school's pages give different amounts\./);
    // Same benefit without the evidence falls back to the generic wording, proving the evidence drives it.
    const without = r.offers.flatMap((o) => coverageSummary(o, r.offers, []).benefits.map((b) => b.text)).join("\n");
    expect(without).not.toMatch(/different amounts/);
  });
  it("benefitLine adds exclusions and duration (unit)", () => {
    const b: Benefit = { category: "mandatory_fees", instrument: "scholarship", coverage: "full", amount: null, exclusions: ["Parking"], duration_terms: "four years" };
    expect(benefitLine(b).text).toBe("the school says it covers all of it. Not included: Parking. For four years.");
  });
});

describe("closed programs never read as open", () => {
  it("replaces the 'terms for fall N entry' line with the closed status (real: Vanderbilt Chancellor's)", () => {
    const v = row("chancellors-scholarship");
    expect(closedLabel(v)).toBe("Closed to new entrants");
    const line = freshnessLine(v).text;
    expect(line).toMatch(/^Closed to new entrants as of the page we read [A-Z][a-z]{2} \d{1,2}, 2026\.$/);
    expect(line).not.toMatch(/Terms for/);
    expect(freshnessShort(v)).toEqual({ tone: "plain", text: "Closed to new entrants" });
  });
  it("still shows conflicting as a conflict even if closed", () => {
    const v = { ...row("distinguished-presidential-scholarship"), program_status_for_entry: "paused" };
    expect(freshnessLine(v).tone).toBe("amber");
  });
});

describe("unknown freshness status", () => {
  it("never reads as current", () => {
    const odd = { ...row("national-merit-semifinalist-package"), freshness_status: "something_new" as never };
    expect(freshnessLine(odd).text).toBe("Read the official page for the current terms.");
    expect(freshnessShort(odd).text).toBe("Check the official page");
  });
});

describe("normalizeScholarshipRow survives malformed elements", () => {
  it("drops null offers, null milestones, null benefits and sources without a url", () => {
    const base = ROWS[0] as unknown as Record<string, unknown>;
    const messy = normalizeScholarshipRow({
      ...base,
      offers: [null, 5, { offer_id: "o1", benefits: [null, { category: "tuition", instrument: "scholarship", coverage: "full", amount: null }] }],
      application: { milestones: [null, { kind: "application_deadline", requirement: "required", date: "2026-12-01", recurring: null }] },
      sources: [null, { source_id: "x" }, { source_id: "y", url: "javascript:alert(1)", authority: "official_program" }, { source_id: "z", url: "https://example.edu/a", authority: "official_program" }],
      related_programs: [null],
      renewal_rules: [null],
    })!;
    expect(messy.offers.map((o) => o.offer_id)).toEqual(["o1"]);
    expect(messy.offers[0].benefits).toHaveLength(1);
    expect(messy.application?.milestones).toHaveLength(1);
    expect(messy.sources.map((s) => s.source_id)).toEqual(["z"]);
    expect(messy.renewal_rules).toEqual([]);
    expect(() => coverageSummary(messy.offers[0], messy.offers)).not.toThrow();
    expect(() => deadlineLine(messy, "2026-11-14")).not.toThrow();
  });
});

describe("related programs link when documented on the page", () => {
  it("marks a related program on the same page (UGA Stamps -> Foundation Fellowship)", () => {
    const stamps = row("stamps-scholars", "uga");
    const items = relatedItems(stamps, { "foundation-fellowship": "Foundation Fellowship" });
    expect(items.some((i) => i.programId === "foundation-fellowship" && i.onPage && i.name === "Foundation Fellowship")).toBe(true);
    expect(relatedItems(stamps, {}).every((i) => !i.onPage)).toBe(true);
  });
});

describe("benefit names and source labels (owner review)", () => {
  const benefit = (over: Partial<Benefit>): Benefit => ({ category: "other", instrument: "scholarship", coverage: "fixed_amount", amount: { qualifier: "exact", value: 3000, min: null, max: null, period: "academic_year" }, ...over });

  it("leads with the school's own name for an 'other' benefit, never 'Other' (real: Texas A&M)", () => {
    const tamu = row("national-merit-scholars", "texas-am");
    const labels = tamu.offers.flatMap((o) => coverageSummary(o, tamu.offers).benefits.map((b) => b.label));
    expect(labels).not.toContain("Other");
    expect(labels).toContain("President's Endowed Scholarship");
    expect(labels).toContain("National Merit Sponsorship");
  });
  it("uses advertised_coverage_label first, scope text second, 'Award' last", () => {
    expect(benefitLine(benefit({ advertised_coverage_label: "Presidential Award" })).label).toBe("Presidential Award");
    expect(benefitLine(benefit({ advertised_coverage_label: "Presidential Award" })).quotedLabel).toBeNull();
    expect(benefitLine(benefit({ scope_text: "Dean's Award; table also shows a total" })).label).toBe("Dean's Award");
    expect(benefitLine(benefit({})).label).toBe("Award");
    expect(benefitLine(benefit({ scope_text: "x".repeat(120) })).label).toBe("Award");
  });
  it("keeps the standard label for a standard category", () => {
    expect(benefitLine(benefit({ category: "housing", scope_text: "Something; else" })).label).toBe("Housing");
  });
  it("labels sources by authority so two links are told apart", () => {
    expect(sourceLabel("official_program")).toBe("Program page ↗");
    expect(sourceLabel("official_aid_policy")).toBe("Aid policy page ↗");
    expect(sourceLabel("official_admissions")).toBe("Admissions page ↗");
    expect(sourceLabel("official_news")).toBe("News page ↗");
    expect(sourceLabel("archived_official")).toBe("Archived page ↗");
    expect(sourceLabel("foundation_official")).toBe("Foundation's page ↗");
    // Real rows: the labels follow the authority, so a program page and an aid policy page differ.
    const auths = new Set(ROWS.flatMap((r) => r.sources.map((x) => x.authority)));
    expect(new Set([...auths].map(sourceLabel)).size).toBe(auths.size);
  });
});
