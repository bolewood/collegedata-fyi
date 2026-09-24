// CDS C21 early-decision counts. Modern templates print applications
// received and admits; they do not print early-action counts (C22 is
// offered / restrictive / dates only). So a second series on the
// acceptance-rate page is early decision, never inferred REA/EA.

import { c1TemplateForArtifact, fieldNumber, type C1Template } from "./c1-headline-totals";
import type { FieldValue } from "./types";

export type C21Counts = { applied: number; admitted: number; rate: number };

function c21Ids(template: C1Template): { applied: string; admitted: string } {
  // 2025-26 inserted extra date parts, so counts moved to C.2110 / C.2111.
  // 2023-24 and 2024-25 keep them at C.2106 / C.2107 (same as the browser
  // projection in tools/browser_backend/project_browser_data.py).
  if (template === "2025-26") return { applied: "C.2110", admitted: "C.2111" };
  return { applied: "C.2106", admitted: "C.2107" };
}

export function readC21Counts(extract: {
  values: Record<string, FieldValue>;
  schemaVersion?: string | null;
  producer?: string | null;
  yearStart?: number | null;
}): C21Counts | null {
  const resolved = c1TemplateForArtifact({
    schemaVersion: extract.schemaVersion,
    producer: extract.producer,
    yearStart: extract.yearStart,
  });
  if (!resolved.template) return null;
  const ids = c21Ids(resolved.template);
  const applied = fieldNumber(extract.values, ids.applied);
  const admitted = fieldNumber(extract.values, ids.admitted);
  return saneEdCounts(applied, admitted);
}

export function saneEdCounts(
  applied: number | null | undefined,
  admitted: number | null | undefined,
  overallAdmitted?: number | null,
): C21Counts | null {
  if (applied == null || applied <= 0) return null;
  if (admitted == null || admitted <= 0) return null;
  if (admitted > applied) return null;
  if (overallAdmitted != null && overallAdmitted > 0 && admitted > overallAdmitted) return null;
  return { applied, admitted, rate: admitted / applied };
}
