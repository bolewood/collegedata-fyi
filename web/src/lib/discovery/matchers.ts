// Policy matcher engine — the TypeScript twin of data_spike.py's executor.
// Semantics must stay identical (a committed conformance fixture pins the
// two engines against each other): -1 | 0 | +1, where 0 is unknown /
// unsupported / missing / neutral. Absence never means mismatch.

import { POLICY } from "./content";
import type { EvidenceSchool, MatcherSpec } from "./types";

type Resolver = (s: EvidenceSchool) => number | string | string[] | null;

// Evidence-key resolvers for the sources the bundle carries. Keys without a
// resolver (cds.*, ipeds.ic.*, distance.*, merit_profile.*) resolve to null,
// so their matchers return 0 until those loads ship — mirroring Python.
const FIELD_RESOLVERS: Record<string, Resolver> = {
  "directory.enrollment": (s) => s.enrollment,
  "program.related_cip_count": (s) =>
    Object.keys(s.direct).length + Object.keys(s.adjacent).length || null,
  "scorecard.locale": (s) => s.scorecard.locale,
  "scorecard.net_price_0_30k": (s) => s.scorecard.net_price_0_30k,
  "scorecard.median_debt_completers": (s) => s.scorecard.median_debt_completers,
  "scorecard.retention_rate_ft": (s) => s.scorecard.retention_rate_ft,
  "scorecard.graduation_rate_4yr": (s) => s.scorecard.graduation_rate_4yr,
  "scorecard.earnings_10yr_median": (s) => s.scorecard.earnings_10yr_median,
  "scorecard.pell_grant_rate": (s) => s.scorecard.pell_grant_rate,
};

const OPS: Record<string, (v: number, t: number) => boolean> = {
  gte: (v, t) => v >= t,
  gt: (v, t) => v > t,
  lte: (v, t) => v <= t,
  lt: (v, t) => v < t,
};

export function bandTest(value: number, band: Record<string, number>): boolean {
  return Object.entries(band).every(([op, t]) => OPS[op](value, t));
}

export const SUPPORTED_KEYS = new Set(Object.keys(POLICY.matchers));

// Keys whose matcher can actually resolve evidence from the current bundle.
// A spec whose evidence keys all lack resolvers (cds.*, ipeds.ic.*,
// distance.*) is policy-supported but not yet actionable — matcher() always
// returns 0 for it, so it neither scores nor produces reasons. UI that
// claims such a key "shapes scoring" would be lying; use this set to tell
// the truth.
export const ACTIONABLE_KEYS = new Set(
  Object.keys(POLICY.matchers).filter((k) =>
    POLICY.matchers[k].evidence_keys.some((ek) => ek in FIELD_RESOLVERS),
  ),
);

/** Execute the policy matcher for a preference key → -1 | 0 | +1. */
export function matcher(key: string, school: EvidenceSchool): -1 | 0 | 1 {
  const spec: MatcherSpec | undefined = POLICY.matchers[key];
  if (!spec) return 0; // unsupported key: ledger-only

  const vals: (number | string | string[])[] = [];
  for (const ek of spec.evidence_keys) {
    const resolve = FIELD_RESOLVERS[ek];
    const v = resolve ? resolve(school) : null;
    if (v !== null && v !== undefined) vals.push(v);
  }

  switch (spec.kind) {
    case "offering_any":
      return vals.some(Boolean) ? 1 : 0;
    case "checklist_membership": {
      for (const v of vals) {
        if (Array.isArray(v)) {
          const hits = (spec.members ?? []).filter((m) => v.includes(m)).length;
          if (hits >= (spec.min_members ?? 1)) return 1;
        }
      }
      return 0;
    }
    case "category_set": {
      if (vals.length === 0) return 0;
      const v = vals[0];
      if ((spec.seek_set ?? []).includes(v as never)) return 1;
      if ((spec.opposite_set ?? []).includes(v as never)) return -1;
      return 0;
    }
    default: {
      // numeric_band, numeric_band_inverted, count_band
      const nums = vals.filter((v): v is number => typeof v === "number");
      if (nums.length === 0) return 0;
      const v = spec.aggregation === "max" ? Math.max(...nums) : nums[0];
      if (spec.seek && bandTest(v, spec.seek)) return 1;
      if (spec.opposite && bandTest(v, spec.opposite)) return -1;
      return 0;
    }
  }
}

/** Resolve the raw evidence value behind a matcher (for reason rendering). */
export function evidenceValue(
  key: string,
  school: EvidenceSchool,
): number | string | null {
  const spec = POLICY.matchers[key];
  if (!spec) return null;
  for (const ek of spec.evidence_keys) {
    const resolve = FIELD_RESOLVERS[ek];
    const v = resolve ? resolve(school) : null;
    if (v !== null && v !== undefined && !Array.isArray(v)) {
      if (spec.aggregation === "max") {
        const nums = spec.evidence_keys
          .map((k) => FIELD_RESOLVERS[k]?.(school))
          .filter((x): x is number => typeof x === "number");
        return nums.length ? Math.max(...nums) : null;
      }
      return v;
    }
  }
  return null;
}

export function haversineMiles(
  lat1: number,
  lon1: number,
  lat2: number,
  lon2: number,
): number {
  const r = 3958.8;
  const p1 = (lat1 * Math.PI) / 180;
  const p2 = (lat2 * Math.PI) / 180;
  const dp = ((lat2 - lat1) * Math.PI) / 180;
  const dl = ((lon2 - lon1) * Math.PI) / 180;
  const a =
    Math.sin(dp / 2) ** 2 +
    Math.cos(p1) * Math.cos(p2) * Math.sin(dl / 2) ** 2;
  return 2 * r * Math.asin(Math.sqrt(a));
}
