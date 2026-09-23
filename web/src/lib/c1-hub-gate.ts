// Which first-year counts a school hub (and its year page) may show.
//
// The printed-total resolver fixes many projected rows, but outside the 20
// validated pilot schools a new number must be corroborated before it
// replaces what production shows today. IPEDS admissions (APPLCN/ADMSSN,
// already fetched on the hub) is the independent check. Every decision
// carries a reason code for the audit trail
// (docs/prd/assets/031/m0-lite-validation.md).

import administrativeUnits from "../data/ipeds-administrative-units.json";
import type { SchoolFactUnifiedRow } from "./types";

export type C1Counts = { applied: number | null; admitted: number | null; enrolled: number | null };

export type IpedsAdmissions = {
  /** Fall of the admissions cohort (ADM2024 = fall 2024 = the 2024-25 report). */
  year: number | null;
  applied: number | null;
  admitted: number | null;
  openAdmission: boolean | null;
  /** System / central office, or not degree-granting: reports no students of its own. */
  administrativeUnit: boolean;
};

export type GateReason =
  | "administrative_unit"
  | "pilot_resolver"
  | "no_resolver_keep_projection"
  | "no_resolver_suppress"
  | "unchanged"
  | "tiny_adjustment"
  | "ipeds_accept_resolver"
  | "ipeds_keep_projection_closer"
  | "ipeds_keep_projection"
  | "ipeds_suppress"
  | "no_ipeds_projection_broken_accept_resolver"
  | "no_ipeds_keep_projection"
  | "no_ipeds_suppress"
  | "insane_suppress";

export type GateResult = { counts: C1Counts | null; reason: GateReason };

const ADMIN_IPEDS_IDS = new Set(administrativeUnits.units.map((unit) => unit.ipeds_id));

/** IPEDS facts the hub already has, reduced to what the gate needs. */
export function ipedsAdmissions(
  facts: Pick<SchoolFactUnifiedRow, "field_key" | "value_numeric" | "value_label" | "data_year">[],
  ipedsId: string | null | undefined,
): IpedsAdmissions {
  const field = (key: string) => facts.find((fact) => fact.field_key === key);
  const applied = field("applicants_total");
  const admitted = field("admissions_total");
  const open = field("open_admissions_policy")?.value_label?.toLowerCase();
  const sector = field("sector")?.value_label?.toLowerCase() ?? "";
  const degree = field("degree_granting_status")?.value_label?.toLowerCase() ?? "";
  return {
    year: applied?.data_year ?? admitted?.data_year ?? null,
    applied: applied?.value_numeric ?? null,
    admitted: admitted?.value_numeric ?? null,
    openAdmission: open == null ? null : open.startsWith("yes"),
    administrativeUnit:
      (ipedsId != null && ADMIN_IPEDS_IDS.has(ipedsId)) ||
      sector.includes("administrative unit") ||
      degree.startsWith("nondegree") ||
      degree.startsWith("non-degree"),
  };
}

type Full = { applied: number; admitted: number; enrolled: number | null };

function full(counts: C1Counts | null): Full | null {
  if (!counts || counts.applied == null || counts.admitted == null) return null;
  return { applied: counts.applied, admitted: counts.admitted, enrolled: counts.enrolled };
}

/** 0 < admitted ≤ applied, enrolled ≤ admitted, applied ≥ 50; applied = admitted only for open admission. */
export function saneCounts(counts: C1Counts | null, openAdmission: boolean | null): counts is Full {
  const c = full(counts);
  if (!c) return false;
  if (c.applied < 50 || c.admitted <= 0 || c.admitted > c.applied) return false;
  if (c.enrolled != null && c.enrolled > c.admitted) return false;
  if (c.applied === c.admitted && openAdmission !== true) return false;
  return true;
}

function within(a: number, b: number, share: number): boolean {
  return Math.abs(a - b) <= share * b;
}

/**
 * IPEDS for the same fall: applied and admitted each within ±10%. IPEDS one
 * fall older (2025-26 reports against fall 2024): rate within ±10 points
 * and applied within ±35%. Null when there is no usable IPEDS year.
 */
export function corroborates(counts: Full, yearStart: number, ipeds: IpedsAdmissions): boolean | null {
  if (ipeds.year == null || ipeds.applied == null || ipeds.admitted == null || ipeds.applied <= 0) return null;
  if (ipeds.year === yearStart) {
    return within(counts.applied, ipeds.applied, 0.1) && within(counts.admitted, ipeds.admitted, 0.1);
  }
  if (ipeds.year === yearStart - 1) {
    const rate = counts.admitted / counts.applied;
    const ipedsRate = ipeds.admitted / ipeds.applied;
    return Math.abs(rate - ipedsRate) <= 0.1 && within(counts.applied, ipeds.applied, 0.35);
  }
  return null;
}

export function gateC1Counts({
  pilot,
  yearStart,
  projection,
  resolver,
  ipeds,
}: {
  pilot: boolean;
  yearStart: number;
  projection: C1Counts | null;
  resolver: C1Counts | null;
  ipeds: IpedsAdmissions;
}): GateResult {
  if (ipeds.administrativeUnit) return { counts: null, reason: "administrative_unit" };
  const open = ipeds.openAdmission;
  const p = saneCounts(projection, open) ? full(projection) : null;
  const r = saneCounts(resolver, open) ? full(resolver) : null;

  if (pilot) {
    if (r) return { counts: r, reason: "pilot_resolver" };
    return p ? { counts: p, reason: "no_resolver_keep_projection" } : { counts: null, reason: "insane_suppress" };
  }
  if (!full(resolver)) {
    return p ? { counts: p, reason: "no_resolver_keep_projection" } : { counts: null, reason: "no_resolver_suppress" };
  }
  const rv = full(resolver)!;
  const pv = full(projection);
  if (pv && pv.applied === rv.applied && pv.admitted === rv.admitted) {
    return r ? { counts: r, reason: "unchanged" } : { counts: null, reason: "insane_suppress" };
  }
  if (
    r && pv &&
    Math.abs(rv.applied - pv.applied) <= Math.max(5, 0.001 * pv.applied) &&
    Math.abs(rv.admitted - pv.admitted) <= Math.max(5, 0.001 * pv.admitted)
  ) {
    return { counts: r, reason: "tiny_adjustment" };
  }

  const rOk = r ? corroborates(r, yearStart, ipeds) : null;
  const pOk = p ? corroborates(p, yearStart, ipeds) : null;
  const ipedsUsable = corroborates(rv, yearStart, ipeds) !== null;

  if (ipedsUsable) {
    if (r && rOk && p && pOk) {
      // Both agree with IPEDS: keep whichever is closer on applicants, so a
      // hub never moves away from the federal count it already matched.
      const dr = Math.abs(r.applied - (ipeds.applied as number));
      const dp = Math.abs(p.applied - (ipeds.applied as number));
      return dr <= dp ? { counts: r, reason: "ipeds_accept_resolver" } : { counts: p, reason: "ipeds_keep_projection_closer" };
    }
    if (r && rOk) return { counts: r, reason: "ipeds_accept_resolver" };
    if (p && pOk) return { counts: p, reason: "ipeds_keep_projection" };
    return { counts: null, reason: "ipeds_suppress" };
  }

  const broken = !pv || pv.admitted > pv.applied || pv.applied < 0.25 * rv.applied;
  if (broken) {
    return r ? { counts: r, reason: "no_ipeds_projection_broken_accept_resolver" } : { counts: null, reason: "no_ipeds_suppress" };
  }
  if (p && Math.abs(rv.applied - p.applied) <= 0.02 * p.applied && Math.abs(rv.admitted - p.admitted) <= 0.02 * p.admitted) {
    return { counts: p, reason: "no_ipeds_keep_projection" };
  }
  return { counts: null, reason: "no_ipeds_suppress" };
}
