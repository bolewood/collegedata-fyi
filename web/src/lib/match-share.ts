// PRD 024 M1: plain-text "Copy summary" for /match. Pure and deterministic.
//
// Privacy: the input is only per-bucket school counts computed from default
// filters. The output never contains GPA, SAT, ACT, home state, major, school
// names, or the profile share code. The link it carries is the generic
// /match page, not the code link; "Copy link" is the control that shares the
// profile.

import type { AcademicFit } from "./positioning";

export type MatchFitCounts = Record<AcademicFit, number>;

const ROWS: { fit: AcademicFit; label: string }[] = [
  { fit: "strong_academic_fit", label: "Strong fit" },
  { fit: "above_range", label: "Above range" },
  { fit: "in_range", label: "In range" },
  { fit: "below_range", label: "Below range" },
  { fit: "unknown", label: "Unknown" },
];

const BAR_CHAR = "█";
const MAX_BAR = 10;
export const MATCH_SUMMARY_URL = "https://www.collegedata.fyi/match";

export function countsFromGroups(
  groups: Record<AcademicFit, readonly unknown[]>,
): MatchFitCounts {
  return {
    strong_academic_fit: groups.strong_academic_fit.length,
    above_range: groups.above_range.length,
    in_range: groups.in_range.length,
    below_range: groups.below_range.length,
    unknown: groups.unknown.length,
  };
}

function bar(count: number, max: number): string {
  if (count <= 0 || max <= 0) return "";
  return BAR_CHAR.repeat(Math.max(1, Math.round((count / max) * MAX_BAR)));
}

export function formatMatchSummary(counts: MatchFitCounts): string {
  const total = ROWS.reduce((sum, { fit }) => sum + counts[fit], 0);
  const head = "CollegeData.fyi Match";
  if (total === 0) {
    return [head, "No schools ranked yet", "", MATCH_SUMMARY_URL].join("\n");
  }
  const max = Math.max(...ROWS.map(({ fit }) => counts[fit]));
  const labelWidth = Math.max(...ROWS.map((r) => r.label.length));
  const countWidth = String(max).length;
  const lines = ROWS.map(({ fit, label }) => {
    const n = counts[fit];
    const b = bar(n, max);
    return `${label.padEnd(labelWidth)}  ${b.padEnd(MAX_BAR)}  ${String(n).padStart(countWidth)}`.trimEnd();
  });
  return [
    head,
    `${total} ${total === 1 ? "school" : "schools"} ranked`,
    "Counts use the default filters.",
    "",
    ...lines,
    "",
    MATCH_SUMMARY_URL,
  ].join("\n");
}
