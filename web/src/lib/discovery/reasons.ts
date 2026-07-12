// Template-grounded reason rendering (PRD 026 §9). Every displayed reason
// resolves to a policy template, a live evidence value with its data year,
// and limitation copy — a reason missing any of those is omitted (fail
// closed), and a school with zero valid reasons cannot be shown.

import { LIMITATIONS, ONTOLOGY, POLICY } from "./content";
import { evidenceValue, matcher } from "./matchers";
import type { Candidate } from "./rounds";
import type { RoundReason } from "./types";

const COMPLETIONS_DISPLAY_YEAR = "2023-24"; // bundle completions_release

const METRIC_LABELS: Record<string, string> = {
  "scale.small": "undergraduate enrollment",
  "scale.large": "undergraduate enrollment",
  "scale.tight_knit": "undergraduate enrollment",
  "out.retention": "first-year retention",
  "out.four_year_grad": "four-year graduation rate",
  "out.career_track_record": "median earnings ten years after entry",
  "cost.low_debt": "median borrower debt",
  "cost.need_aid_strength": "average net price for families earning under $30k",
  "people.first_gen_common": "share of students with Pell grants",
  "academic.breadth": "related programs in this interest area",
  "academic.pivot_flexibility": "related programs in this interest area",
};

const LOCALE_LABELS: Record<number, string> = {
  11: "a large city", 12: "a midsize city", 13: "a small city",
  21: "a large suburb", 22: "a midsize suburb", 23: "a small suburb",
  31: "a town near a metro area", 32: "a town", 33: "a remote town",
  41: "a rural area near a metro", 42: "a rural area", 43: "a remote rural area",
};

const FRACTION_KEYS = new Set([
  "out.retention", "out.four_year_grad", "people.first_gen_common",
]);
const USD_KEYS = new Set([
  "cost.low_debt", "cost.need_aid_strength", "out.career_track_record",
]);

function template(id: string): { text: string; limitation_id: string } | null {
  const tpl = POLICY.reason_templates[id];
  return tpl && typeof tpl !== "string" ? tpl : null;
}

function fill(text: string, vars: Record<string, string>): string | null {
  let out = text;
  for (const [k, v] of Object.entries(vars)) {
    out = out.replaceAll(`{${k}}`, v);
  }
  // Fail closed on unresolved placeholders.
  return /\{[a-z_]+\}/.test(out) ? null : out;
}

function formatValue(key: string, value: number | string): string {
  if (typeof value === "string") return value;
  if (FRACTION_KEYS.has(key)) return `${Math.round(value * 100)}%`;
  if (USD_KEYS.has(key)) return `$${Math.round(value).toLocaleString("en-US")}`;
  return Math.round(value).toLocaleString("en-US");
}

function academicReason(
  candidate: Candidate,
  kind: "academic_direct" | "academic_adjacent",
  concepts: string[],
  directCips: Set<string>,
  adjacentCips: Set<string>,
): RoundReason | null {
  const school = candidate.school;
  const wanted = kind === "academic_direct" ? directCips : adjacentCips;
  const hits = Object.entries({ ...school.adjacent, ...school.direct })
    .filter(([cip]) => wanted.has(cip))
    .sort((a, b) => b[1] - a[1]);
  if (hits.length === 0) return null;
  const [cip, awards] = hits[0];
  const conceptSet = concepts.length > 0 ? new Set(concepts) : null;
  const edge = ONTOLOGY.edges.find(
    (e) =>
      e.to_cip === cip &&
      e.relationship === (kind === "academic_direct" ? "direct" : "adjacent") &&
      (!conceptSet || conceptSet.has(e.from_concept_id)),
  );
  if (!edge) return null;
  const concept = ONTOLOGY.concepts.find((c) => c.concept_id === edge.from_concept_id);
  const tpl = template(`tpl.${kind}.v1`);
  if (!tpl || !concept) return null;
  const text = fill(tpl.text, {
    program_label: edge.cip_label,
    data_year: COMPLETIONS_DISPLAY_YEAR,
    concept_label: concept.label,
  });
  const limitation = LIMITATIONS[tpl.limitation_id];
  if (!text || !limitation) return null;
  return {
    kind,
    ref: `program.recent_awards.${cip}`,
    text: `${text} (${awards.toLocaleString("en-US")} degrees)`,
    evidence_class: "program",
    data_year: COMPLETIONS_DISPLAY_YEAR,
    limitation,
    tunable_key: null,
  };
}

const KIND_TEMPLATE: Record<string, string> = {
  numeric_band: "tpl.numeric_high.v1",
  count_band: "tpl.numeric_high.v1",
  numeric_band_inverted: "tpl.numeric_low_good.v1",
  category_set: "tpl.category.v1",
  offering_any: "tpl.offering.v1",
};

function preferenceReason(key: string, candidate: Candidate): RoundReason | null {
  const spec = POLICY.matchers[key];
  if (!spec || matcher(key, candidate.school) !== 1) return null;
  const tplId = KIND_TEMPLATE[spec.kind];
  const tpl = tplId ? template(tplId) : null;
  if (!tpl) return null;
  const value = evidenceValue(key, candidate.school);
  if (value === null) return null;

  // Program-count evidence comes from the completions cycle, not the
  // Scorecard vintage; everything else in the bundle carries the school's
  // scorecard_data_year.
  const isProgram = spec.evidence_keys[0]?.startsWith("program.");
  const scorecardYear = isProgram
    ? COMPLETIONS_DISPLAY_YEAR
    : candidate.school.scorecard.scorecard_data_year ?? "recent";
  let text: string | null;
  if (spec.kind === "category_set") {
    const label =
      typeof value === "number" ? LOCALE_LABELS[value] : String(value);
    if (!label) return null;
    text = fill(tpl.text, { category_label: label, data_year: scorecardYear });
  } else {
    const label = METRIC_LABELS[key];
    if (!label) return null;
    text = fill(tpl.text, {
      metric_label: label,
      value: formatValue(key, value),
      data_year: scorecardYear,
    });
  }
  // The matcher's own limitation overrides the template default (policy note).
  const limitation = LIMITATIONS[spec.limitation_id] ?? LIMITATIONS[tpl.limitation_id];
  if (!text || !limitation) return null;
  const evidenceClass = isProgram
    ? "program"
    : spec.evidence_keys[0]?.startsWith("directory.")
      ? "directory"
      : "scorecard";
  return {
    kind: key,
    ref: `match:${key}`,
    text,
    evidence_class: evidenceClass,
    data_year: scorecardYear,
    limitation,
    tunable_key: key,
  };
}

/** Render up to three fail-closed reasons for a chosen candidate. */
export function renderReasons(
  candidate: Candidate,
  concepts: string[],
  directCips: Set<string>,
  adjacentCips: Set<string>,
  aggregates: Record<string, number>,
): RoundReason[] {
  const reasons: RoundReason[] = [];
  const academicKind = candidate.reasons.find(([k]) =>
    k.startsWith("academic_"),
  )?.[0] as "academic_direct" | "academic_adjacent" | undefined;
  if (academicKind) {
    const r = academicReason(candidate, academicKind, concepts, directCips, adjacentCips);
    if (r) reasons.push(r);
  }
  // Strongest positive preference matches next (by contribution).
  const prefKinds = candidate.reasons
    .filter(([k]) => !k.startsWith("academic_"))
    .map(([k]) => k)
    .sort((a, b) => (aggregates[b] ?? 0) - (aggregates[a] ?? 0));
  for (const key of prefKinds) {
    if (reasons.length >= 3) break;
    const r = preferenceReason(key, candidate);
    if (r) reasons.push(r);
  }
  return reasons;
}
