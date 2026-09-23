import { describe, expect, it } from "vitest";
import { gateC1Counts, ipedsAdmissions, saneCounts, type IpedsAdmissions } from "./c1-hub-gate";

const c = (applied: number | null, admitted: number | null, enrolled: number | null = null) => ({ applied, admitted, enrolled });

function ipeds(year: number | null, applied: number | null, admitted: number | null, openAdmission: boolean | null = false): IpedsAdmissions {
  return { year, applied, admitted, openAdmission, administrativeUnit: false };
}

const none = ipeds(null, null, null, null);

// Production values, 2026-09-23 (projection = school_browser_rows; resolver =
// printed C1 totals; IPEDS = school_facts_unified ADM/IC).
describe("non-pilot hub gate: named cases", () => {
  it("Lake Superior State: applied = admitted fails IPEDS (68% for fall 2023) — suppressed", () => {
    const result = gateC1Counts({
      pilot: false,
      yearStart: 2024,
      projection: c(2146, 2106),
      resolver: c(2106, 2106),
      ipeds: ipeds(2023, 2473, 1682, true),
    });
    expect(result).toEqual({ counts: null, reason: "ipeds_suppress" });
  });

  it("Washington University 2025-26: broken projection (7,830 / 575) repaired, corroborated by fall 2024 IPEDS", () => {
    const result = gateC1Counts({
      pilot: false,
      yearStart: 2025,
      projection: c(7830, 575),
      resolver: c(35316, 4359),
      ipeds: ipeds(2024, 32754, 3951),
    });
    expect(result).toEqual({ counts: c(35316, 4359), reason: "ipeds_accept_resolver" });
  });

  it("Fitchburg State 2024-25: resolver 16% below IPEDS applicants — keeps the projection, which matches IPEDS", () => {
    const result = gateC1Counts({
      pilot: false,
      yearStart: 2024,
      projection: c(4582, 3983),
      resolver: c(3831, 3404),
      ipeds: ipeds(2024, 4582, 3983),
    });
    expect(result).toEqual({ counts: c(4582, 3983), reason: "ipeds_keep_projection" });
  });

  it("Arkansas 2024-25: both within ±10% of IPEDS — keeps the projection, which is closer (30,549 vs 30,555)", () => {
    const result = gateC1Counts({
      pilot: false,
      yearStart: 2024,
      projection: c(30549, 22701),
      resolver: c(28873, 22701),
      ipeds: ipeds(2024, 30555, 22703),
    });
    expect(result).toEqual({ counts: c(30549, 22701), reason: "ipeds_keep_projection_closer" });
  });

  it("University of Houston System Administration shows no C1 figures", () => {
    const unit = ipedsAdmissions([], "229407");
    expect(unit.administrativeUnit).toBe(true);
    expect(gateC1Counts({ pilot: false, yearStart: 2025, projection: c(28115, 21788), resolver: c(34728, 26312), ipeds: unit })).toEqual({
      counts: null,
      reason: "administrative_unit",
    });
    expect(ipedsAdmissions([], "225511").administrativeUnit).toBe(false);
  });
});

describe("non-pilot hub gate: rules", () => {
  it("basic sanity", () => {
    expect(saneCounts(c(1000, 100, 50), false)).toBe(true);
    expect(saneCounts(c(40, 10), false)).toBe(false);
    expect(saneCounts(c(1000, 1100), false)).toBe(false);
    expect(saneCounts(c(1000, 100, 200), false)).toBe(false);
    expect(saneCounts(c(1000, 1000), false)).toBe(false);
    expect(saneCounts(c(1000, 1000), true)).toBe(true);
  });

  it("pilots always take the resolver", () => {
    expect(gateC1Counts({ pilot: true, yearStart: 2024, projection: c(13742, 1238), resolver: c(13743, 1238), ipeds: none }).reason).toBe("pilot_resolver");
  });

  it("tiny adjustments within max(5, 0.1%) are accepted without IPEDS", () => {
    expect(gateC1Counts({ pilot: false, yearStart: 2024, projection: c(21384, 8569), resolver: c(21384, 8570), ipeds: none })).toEqual({
      counts: c(21384, 8570),
      reason: "tiny_adjustment",
    });
  });

  it("no IPEDS: repairs a missing or broken projection, keeps a close one, otherwise suppresses", () => {
    expect(gateC1Counts({ pilot: false, yearStart: 2024, projection: c(null, null), resolver: c(5965, 5892), ipeds: none }).reason)
      .toBe("no_ipeds_projection_broken_accept_resolver");
    expect(gateC1Counts({ pilot: false, yearStart: 2024, projection: c(159, 39), resolver: c(7842, 6696), ipeds: none }).reason)
      .toBe("no_ipeds_projection_broken_accept_resolver");
    expect(gateC1Counts({ pilot: false, yearStart: 2024, projection: c(10000, 5000), resolver: c(10150, 5050), ipeds: none })).toEqual({
      counts: c(10000, 5000),
      reason: "no_ipeds_keep_projection",
    });
    // Hard stop: a sane projection is never replaced by a resolver value >2% lower without IPEDS.
    expect(gateC1Counts({ pilot: false, yearStart: 2024, projection: c(10000, 5000), resolver: c(9000, 5000), ipeds: none })).toEqual({
      counts: null,
      reason: "no_ipeds_suppress",
    });
  });

  it("IPEDS two or more falls old does not count as corroboration", () => {
    const result = gateC1Counts({ pilot: false, yearStart: 2025, projection: c(1000, 500), resolver: c(1200, 600), ipeds: ipeds(2022, 1200, 600) });
    expect(result.reason).toBe("no_ipeds_suppress");
  });

  it("no resolver reading keeps the projection when sane", () => {
    expect(gateC1Counts({ pilot: false, yearStart: 2024, projection: c(1000, 500), resolver: null, ipeds: none }).reason).toBe("no_resolver_keep_projection");
    expect(gateC1Counts({ pilot: false, yearStart: 2024, projection: c(1000, 1500), resolver: null, ipeds: none }).reason).toBe("no_resolver_suppress");
  });
});
