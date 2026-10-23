import type { FieldValue } from "@/lib/types";
import type { C1HeadlineTotals } from "@/lib/c1-headline-totals";
import type { SchoolYearFacts } from "@/lib/school-summary";
import {
  buildYearPageRibbonBands,
  SchoolFactRibbon,
} from "./SchoolFactRibbon";

export function KeyStats({
  schemaVersion,
  values,
  c1,
  priorFacts,
  currentYearStart,
}: {
  schemaVersion?: string;
  values: Record<string, FieldValue>;
  /** Pre-read C1 totals (see readC1Totals); computed from values when omitted. */
  c1?: C1HeadlineTotals;
  /** Optional prior-year facts for consecutive YoY delta annotations. */
  priorFacts?: SchoolYearFacts | null;
  currentYearStart?: number | null;
}) {
  const bands = buildYearPageRibbonBands({
    values,
    schemaVersion,
    c1,
    priorFacts,
    currentYearStart,
  });

  if (bands.length === 0) return null;

  return (
    <SchoolFactRibbon
      bands={bands}
      ariaLabel="Common Data Set headline statistics"
    />
  );
}
