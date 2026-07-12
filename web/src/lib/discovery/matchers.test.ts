import { describe, expect, it } from "vitest";
import { POLICY } from "./content";
import { bandTest, evidenceValue, haversineMiles, matcher } from "./matchers";
import type { EvidenceSchool } from "./types";

const SCORECARD_NULLS: EvidenceSchool["scorecard"] = {
  locale: null,
  avg_net_price: null,
  net_price_0_30k: null,
  median_debt_completers: null,
  retention_rate_ft: null,
  graduation_rate_4yr: null,
  graduation_rate_6yr: null,
  earnings_10yr_median: null,
  pell_grant_rate: null,
  scorecard_data_year: null,
};

// Synthetic evidence rows: every field null unless the test says otherwise,
// mirroring how the bundle represents missing data.
type SchoolOver = Partial<Omit<EvidenceSchool, "scorecard">> & {
  scorecard?: Partial<EvidenceSchool["scorecard"]>;
};

function school(over: SchoolOver = {}): EvidenceSchool {
  return {
    school_id: "test-school",
    ipeds_id: "000000",
    name: "Test School",
    city: null,
    state: "MT",
    control: 1,
    lat: null,
    lon: null,
    enrollment: null,
    direct: {},
    adjacent: {},
    ...over,
    scorecard: { ...SCORECARD_NULLS, ...(over.scorecard ?? {}) },
  };
}

describe("bandTest", () => {
  it("requires every op in the band to pass", () => {
    expect(bandTest(10, { gte: 5, lte: 15 })).toBe(true);
    expect(bandTest(20, { gte: 5, lte: 15 })).toBe(false);
    expect(bandTest(5, { gt: 5 })).toBe(false);
    expect(bandTest(5, { lt: 6 })).toBe(true);
  });
});

describe("matcher", () => {
  it("returns 0 for unsupported keys (ledger-only)", () => {
    expect(matcher("reflect.some_future_key", school())).toBe(0);
  });

  it("numeric_band_inverted: seek low, oppose high, unknown neutral", () => {
    expect(matcher("scale.small", school({ enrollment: 3000 }))).toBe(1);
    expect(matcher("scale.small", school({ enrollment: 20000 }))).toBe(-1);
    expect(matcher("scale.small", school({ enrollment: 8000 }))).toBe(0);
    expect(matcher("scale.small", school())).toBe(0); // missing ≠ mismatch
  });

  it("numeric_band falls through unresolvable evidence keys to the next source", () => {
    // out.retention lists cds.b22.retention first (no resolver yet), then
    // the Scorecard fallback — absence of the CDS load must not zero it.
    expect(
      matcher("out.retention", school({ scorecard: { retention_rate_ft: 0.9 } })),
    ).toBe(1);
    expect(
      matcher("out.retention", school({ scorecard: { retention_rate_ft: 0.5 } })),
    ).toBe(-1);
    expect(matcher("out.retention", school())).toBe(0);
  });

  it("count_band counts related programs and treats zero as unknown", () => {
    const many = school({
      direct: { "03.0103": 5, "03.0104": 2, "40.0601": 1 },
      adjacent: { "45.0601": 3, "14.0801": 2 },
    });
    expect(matcher("academic.breadth", many)).toBe(1); // 5 related ≥ 5
    expect(matcher("academic.breadth", school({ direct: { "03.0103": 5 } }))).toBe(-1); // 1 ≤ 1
    // Zero related CIPs resolves to null (not in-family evidence), never -1.
    expect(matcher("academic.breadth", school())).toBe(0);
  });

  it("category_set: seek set +1, opposite set -1, everything else neutral", () => {
    expect(matcher("place.big_city", school({ scorecard: { locale: 11 } }))).toBe(1);
    expect(matcher("place.big_city", school({ scorecard: { locale: 32 } }))).toBe(-1);
    expect(matcher("place.big_city", school({ scorecard: { locale: 21 } }))).toBe(0);
    expect(matcher("place.big_city", school())).toBe(0);
  });

  it("returns 0 for matchers whose evidence sources have not shipped (cds.*)", () => {
    // offering_any and aggregated CDS bands must stay neutral, not negative,
    // until the CDS evidence load exists — mirroring the Python engine.
    const s = school({ enrollment: 4000 });
    expect(matcher("academic.honors_program", s)).toBe(0);
    expect(matcher("life.greek_scene", s)).toBe(0);
    expect(matcher("opp.study_abroad", s)).toBe(0);
  });
});

describe("evidenceValue", () => {
  it("returns the raw value behind a matched key", () => {
    expect(
      evidenceValue("cost.low_debt", school({ scorecard: { median_debt_completers: 17500 } })),
    ).toBe(17500);
  });

  it("skips unresolvable evidence keys the way matcher does", () => {
    expect(
      evidenceValue("out.retention", school({ scorecard: { retention_rate_ft: 0.87 } })),
    ).toBe(0.87);
  });

  it("returns null for unsupported keys and fully missing evidence", () => {
    expect(evidenceValue("reflect.some_future_key", school())).toBeNull();
    expect(evidenceValue("cost.low_debt", school())).toBeNull();
  });

  it("aggregates with max across resolvable numeric evidence keys", () => {
    // No shipped matcher has a resolvable max aggregation yet (greek_scene
    // waits on cds.f1.*), so pin the branch with a synthetic spec.
    POLICY.matchers["test.max_aggregation"] = {
      kind: "numeric_band",
      evidence_keys: ["directory.enrollment", "program.related_cip_count"],
      aggregation: "max",
      seek: { gte: 4 },
      limitation_id: "lim.size_proxy",
    };
    try {
      const s = school({ enrollment: 2, direct: { a: 1, b: 1, c: 1, d: 1, e: 1 } });
      expect(evidenceValue("test.max_aggregation", s)).toBe(5); // max(2, 5)
      expect(matcher("test.max_aggregation", s)).toBe(1); // matcher uses max too
      const t = school({ enrollment: 9, direct: { a: 1 } });
      expect(evidenceValue("test.max_aggregation", t)).toBe(9); // max(9, 1)
    } finally {
      delete POLICY.matchers["test.max_aggregation"];
    }
  });
});

describe("haversineMiles", () => {
  it("returns 0 for identical points and known distances elsewhere", () => {
    expect(haversineMiles(40.0, -100.0, 40.0, -100.0)).toBe(0);
    const jfkToLax = haversineMiles(40.6413, -73.7781, 33.9416, -118.4085);
    expect(jfkToLax).toBeGreaterThan(2400);
    expect(jfkToLax).toBeLessThan(2550);
  });
});
