import Link from "next/link";
import type { FieldValue, ScorecardSummary, SchoolFactUnifiedRow } from "@/lib/types";
import { c1HeadlineTotals, type C1HeadlineTotals } from "@/lib/c1-headline-totals";
import {
  acceptanceRateOf,
  usableFacts,
  type SchoolYearFacts,
} from "@/lib/school-summary";
import type { SchoolAcademicProfile } from "@/lib/positioning";
import { formatCurrency } from "@/lib/format";
import { Sparkline } from "./Sparkline";

export type FactRibbonRangeBar = {
  low: number;
  high: number;
  min: number;
  max: number;
  median?: number | null;
};

export type FactRibbonCell = {
  key: string;
  label: string;
  value: string;
  sourceLabel: string;
  sourceHref?: string | null;
  subCaption?: string | null;
  deltaText?: string | null;
  rangeBar?: FactRibbonRangeBar | null;
  sparkline?: {
    data: number[];
    yearSpan?: string | null;
  } | null;
};

export type FactRibbonBand = {
  key: string;
  heading: string;
  sectionCode: string;
  sectionHref?: string | null;
  cells: FactRibbonCell[];
};

function getRawNum(values: Record<string, FieldValue>, id: string): number | null {
  const field = values[id];
  if (!field) return null;
  const v = field.value_decoded ?? field.value;
  if (!v) return null;
  const cleaned = v.replace(/[,%$]/g, "").trim();
  const n = parseFloat(cleaned);
  return Number.isFinite(n) ? n : null;
}

/**
 * Normalizes a percentage field that might be stored as 0.72 (fraction) or 72 (percent).
 * Returns a percentage on [0, 100], or null if invalid.
 */
export function parsePercentField(
  values: Record<string, FieldValue>,
  id: string,
): number | null {
  const field = values[id];
  if (!field) return null;
  const rawStr = (field.value_decoded ?? field.value ?? "").trim();
  if (!rawStr) return null;
  const hadPercentSign = rawStr.includes("%");
  const n = getRawNum(values, id);
  if (n == null || n < 0) return null;
  if (hadPercentSign) {
    return n <= 100 ? n : null;
  }
  if (n > 0 && n <= 1) {
    return n * 100;
  }
  return n <= 100 ? n : null;
}

function formatPct100(pct: number, decimals = 1): string {
  const rounded = Number(pct.toFixed(decimals));
  return `${rounded % 1 === 0 && decimals === 0 ? Math.round(pct) : pct.toFixed(decimals)}%`;
}

function validScore(n: number | null, min: number, max: number): number | null {
  if (n == null || !Number.isFinite(n)) return null;
  if (n < min || n > max) return null;
  return Math.round(n);
}

function formatSubmitSubCaption(
  submitPct: number | null,
  median: number | null,
): string {
  const subPart =
    submitPct != null ? `${Math.round(submitPct)}% SUB` : "SUB % N/A";
  const medPart = median != null ? `MED ${Math.round(median)}` : null;
  return [subPart, medPart].filter(Boolean).join(" · ");
}

function formatPointDelta(currentRate01: number, priorRate01: number): string | null {
  const diffPts = (currentRate01 - priorRate01) * 100;
  if (Math.abs(diffPts) < 0.05) return "0.0 pts YoY";
  const sign = diffPts > 0 ? "+" : "−";
  return `${sign}${Math.abs(diffPts).toFixed(1)} pts YoY`;
}

export function buildYearPageRibbonBands({
  values,
  schemaVersion,
  c1,
  priorFacts,
  currentYearStart,
}: {
  values: Record<string, FieldValue>;
  schemaVersion?: string;
  c1?: C1HeadlineTotals;
  priorFacts?: SchoolYearFacts | null;
  currentYearStart?: number | null;
}): FactRibbonBand[] {
  const bands: FactRibbonBand[] = [];
  const { applied, admitted, enrolled } =
    c1 ?? c1HeadlineTotals(values, schemaVersion);

  const isConsecutivePrior =
    usableFacts(priorFacts) &&
    currentYearStart != null &&
    priorFacts.yearStart === currentYearStart - 1;

  const admissionsCells: FactRibbonCell[] = [];

  if (
    applied &&
    admitted != null &&
    applied > 0 &&
    admitted > 0 &&
    admitted <= applied &&
    (enrolled == null || enrolled <= admitted)
  ) {
    const rate01 = admitted / applied;
    const priorRate01 = isConsecutivePrior ? acceptanceRateOf(priorFacts!) : null;
    admissionsCells.push({
      key: "acceptance-rate",
      label: "Accept rate",
      value: `${(rate01 * 100).toFixed(1)}%`,
      sourceLabel: "§C1",
      sourceHref: "#sec-c1",
      deltaText:
        priorRate01 != null ? formatPointDelta(rate01, priorRate01) : null,
      subCaption: `${admitted.toLocaleString("en-US")} of ${applied.toLocaleString("en-US")}`,
    });
  }

  if (
    admitted &&
    enrolled != null &&
    admitted > 0 &&
    enrolled > 0 &&
    enrolled <= admitted
  ) {
    const yield01 = enrolled / admitted;
    const priorYield01 =
      isConsecutivePrior &&
      priorFacts!.admitted &&
      priorFacts!.enrolledFirstYear != null &&
      priorFacts!.admitted > 0 &&
      priorFacts!.enrolledFirstYear <= priorFacts!.admitted
        ? priorFacts!.enrolledFirstYear / priorFacts!.admitted
        : null;
    admissionsCells.push({
      key: "yield-rate",
      label: "Yield",
      value: `${(yield01 * 100).toFixed(1)}%`,
      sourceLabel: "§C1",
      sourceHref: "#sec-c1",
      deltaText:
        priorYield01 != null ? formatPointDelta(yield01, priorYield01) : null,
      subCaption: `${enrolled.toLocaleString("en-US")} enrolled`,
    });
  }

  if (applied && applied > 0) {
    admissionsCells.push({
      key: "applications",
      label: "Applications",
      value: applied.toLocaleString("en-US"),
      sourceLabel: "§C1",
      sourceHref: "#sec-c1",
    });
  }

  if (admitted != null && admitted > 0) {
    admissionsCells.push({
      key: "admitted",
      label: "Admitted",
      value: admitted.toLocaleString("en-US"),
      sourceLabel: "§C1",
      sourceHref: "#sec-c1",
    });
  }

  if (enrolled != null && enrolled > 0) {
    admissionsCells.push({
      key: "enrolled",
      label: "Enrolled",
      value: enrolled.toLocaleString("en-US"),
      sourceLabel: "§C1",
      sourceHref: "#sec-c1",
    });
  }

  // First-year retention (B.2203 rate or B.2202 / B.2201)
  const b22RatePct = parsePercentField(values, "B.2203");
  const b22Cohort = getRawNum(values, "B.2201");
  const b22Retained = getRawNum(values, "B.2202");
  const computedB22Pct =
    b22RatePct ??
    (b22Cohort && b22Retained != null && b22Cohort > 0 && b22Retained <= b22Cohort
      ? (b22Retained / b22Cohort) * 100
      : null);
  if (computedB22Pct != null && computedB22Pct > 0 && computedB22Pct <= 100) {
    admissionsCells.push({
      key: "retention-rate",
      label: "Retention",
      value: formatPct100(computedB22Pct, computedB22Pct % 1 === 0 ? 0 : 1),
      sourceLabel: "§B22",
      sourceHref: "#sec-b22",
      subCaption: "Full-time 1st-yr",
    });
  }

  if (admissionsCells.length > 0) {
    bands.push({
      key: "c1-admissions",
      heading: "First-year admissions & retention",
      sectionCode: "§C1 · §B22",
      sectionHref: "#sec-C",
      cells: admissionsCells,
    });
  }

  // Band 2: C9 Testing
  const testingCells: FactRibbonCell[] = [];
  const satSubPct = parsePercentField(values, "C.901");
  const actSubPct = parsePercentField(values, "C.902");

  const sat25 = validScore(getRawNum(values, "C.905"), 400, 1600);
  const sat50 = validScore(getRawNum(values, "C.906"), 400, 1600);
  const sat75 = validScore(getRawNum(values, "C.907"), 400, 1600);
  if (sat25 != null && sat75 != null && sat25 <= sat75) {
    testingCells.push({
      key: "sat-composite",
      label: "SAT 25–75",
      value: `${sat25}–${sat75}`,
      sourceLabel: "§C9",
      sourceHref: "#testing",
      subCaption: formatSubmitSubCaption(satSubPct, sat50),
      rangeBar: {
        low: sat25,
        high: sat75,
        min: 400,
        max: 1600,
        median: sat50 && sat50 >= sat25 && sat50 <= sat75 ? sat50 : null,
      },
    });
  } else if (sat25 != null) {
    testingCells.push({
      key: "sat-composite-25",
      label: "SAT 25th",
      value: sat25.toLocaleString("en-US"),
      sourceLabel: "§C9",
      sourceHref: "#testing",
      subCaption: formatSubmitSubCaption(satSubPct, null),
    });
  }

  const satRead25 = validScore(getRawNum(values, "C.908"), 200, 800);
  const satRead50 = validScore(getRawNum(values, "C.909"), 200, 800);
  const satRead75 = validScore(getRawNum(values, "C.910"), 200, 800);
  if (satRead25 != null && satRead75 != null && satRead25 <= satRead75) {
    testingCells.push({
      key: "sat-ebrw",
      label: "SAT EBRW",
      value: `${satRead25}–${satRead75}`,
      sourceLabel: "§C9",
      sourceHref: "#testing",
      subCaption: satRead50 != null ? `25TH–75TH · MED ${satRead50}` : "25TH–75TH",
      rangeBar: {
        low: satRead25,
        high: satRead75,
        min: 200,
        max: 800,
        median:
          satRead50 && satRead50 >= satRead25 && satRead50 <= satRead75
            ? satRead50
            : null,
      },
    });
  }

  const satMath25 = validScore(getRawNum(values, "C.911"), 200, 800);
  const satMath50 = validScore(getRawNum(values, "C.912"), 200, 800);
  const satMath75 = validScore(getRawNum(values, "C.913"), 200, 800);
  if (satMath25 != null && satMath75 != null && satMath25 <= satMath75) {
    testingCells.push({
      key: "sat-math",
      label: "SAT Math",
      value: `${satMath25}–${satMath75}`,
      sourceLabel: "§C9",
      sourceHref: "#testing",
      subCaption: satMath50 != null ? `25TH–75TH · MED ${satMath50}` : "25TH–75TH",
      rangeBar: {
        low: satMath25,
        high: satMath75,
        min: 200,
        max: 800,
        median:
          satMath50 && satMath50 >= satMath25 && satMath50 <= satMath75
            ? satMath50
            : null,
      },
    });
  }

  const act25 = validScore(getRawNum(values, "C.914"), 1, 36);
  const act50 = validScore(getRawNum(values, "C.915"), 1, 36);
  const act75 = validScore(getRawNum(values, "C.916"), 1, 36);
  if (act25 != null && act75 != null && act25 <= act75) {
    testingCells.push({
      key: "act-composite",
      label: "ACT 25–75",
      value: `${act25}–${act75}`,
      sourceLabel: "§C9",
      sourceHref: "#testing",
      subCaption: formatSubmitSubCaption(actSubPct, act50),
      rangeBar: {
        low: act25,
        high: act75,
        min: 1,
        max: 36,
        median: act50 && act50 >= act25 && act50 <= act75 ? act50 : null,
      },
    });
  }

  if (testingCells.length > 0) {
    bands.push({
      key: "c9-testing",
      heading: "Enrolled score bands (25th–75th percentile)",
      sectionCode: "§C9",
      sectionHref: "#testing",
      cells: testingCells,
    });
  }

  return bands;
}

export function buildHubRibbonCells({
  schoolId,
  latestFacts,
  shownFacts,
  positioningSchool,
  scorecard,
  federalFacts,
}: {
  schoolId: string;
  latestFacts: SchoolYearFacts | null;
  shownFacts: SchoolYearFacts[];
  positioningSchool?: SchoolAcademicProfile | null;
  scorecard?: ScorecardSummary | null;
  federalFacts?: SchoolFactUnifiedRow[];
}): FactRibbonCell[] {
  const cells: FactRibbonCell[] = [];
  const chronological = [...shownFacts]
    .filter(usableFacts)
    .sort((a, b) => (a.yearStart ?? 0) - (b.yearStart ?? 0));

  const latestYear = latestFacts?.canonical_year ?? positioningSchool?.cdsYear ?? null;
  const yearBaseHref = latestYear ? `/schools/${schoolId}/${latestYear}` : null;

  const priorFacts =
    latestFacts && latestFacts.yearStart != null
      ? shownFacts.find(
          (row) =>
            usableFacts(row) && row.yearStart === latestFacts.yearStart! - 1,
        ) ?? null
      : null;

  // 1. Acceptance Rate
  const acceptRate = latestFacts
    ? acceptanceRateOf(latestFacts)
    : positioningSchool?.acceptanceRate ?? null;
  if (acceptRate != null && acceptRate > 0 && acceptRate <= 1) {
    const acceptSeries = chronological
      .map((r) => ({ year: r.canonical_year, val: acceptanceRateOf(r) }))
      .filter((item): item is { year: string; val: number } => item.val != null);
    const priorAccept = priorFacts ? acceptanceRateOf(priorFacts) : null;
    cells.push({
      key: "hub-acceptance",
      label: "Accept rate",
      value: `${(acceptRate * 100).toFixed(1)}%`,
      sourceLabel: "§C1",
      sourceHref: yearBaseHref ? `${yearBaseHref}#sec-c1` : null,
      deltaText:
        priorAccept != null ? formatPointDelta(acceptRate, priorAccept) : null,
      subCaption:
        latestFacts?.applied && latestFacts?.admitted != null
          ? `${latestFacts.admitted.toLocaleString("en-US")} of ${latestFacts.applied.toLocaleString("en-US")}`
          : null,
      sparkline:
        acceptSeries.length >= 3
          ? {
              data: acceptSeries.map((s) => Number((s.val * 100).toFixed(2))),
              yearSpan: `${acceptSeries[0].year.split("-")[0]}–${acceptSeries[acceptSeries.length - 1].year.split("-")[0]}`,
            }
          : null,
    });
  }

  // 2. Yield Rate
  if (
    latestFacts?.admitted &&
    latestFacts?.enrolledFirstYear != null &&
    latestFacts.admitted > 0 &&
    latestFacts.enrolledFirstYear > 0 &&
    latestFacts.enrolledFirstYear <= latestFacts.admitted
  ) {
    const yieldRate = latestFacts.enrolledFirstYear / latestFacts.admitted;
    const yieldSeries = chronological
      .map((r) => {
        if (
          r.admitted &&
          r.enrolledFirstYear != null &&
          r.admitted > 0 &&
          r.enrolledFirstYear > 0 &&
          r.enrolledFirstYear <= r.admitted
        ) {
          return {
            year: r.canonical_year,
            val: r.enrolledFirstYear / r.admitted,
          };
        }
        return null;
      })
      .filter((item): item is { year: string; val: number } => item != null);

    cells.push({
      key: "hub-yield",
      label: "Yield",
      value: `${(yieldRate * 100).toFixed(1)}%`,
      sourceLabel: "§C1",
      sourceHref: yearBaseHref ? `${yearBaseHref}#sec-c1` : null,
      subCaption: `${latestFacts.enrolledFirstYear.toLocaleString("en-US")} enrolled`,
      sparkline:
        yieldSeries.length >= 3
          ? {
              data: yieldSeries.map((s) => Number((s.val * 100).toFixed(2))),
              yearSpan: `${yieldSeries[0].year.split("-")[0]}–${yieldSeries[yieldSeries.length - 1].year.split("-")[0]}`,
            }
          : null,
    });
  }

  // 3. SAT 25th-75th
  const sat25 =
    validScore(latestFacts?.satCompositeP25 ?? null, 400, 1600) ??
    validScore(positioningSchool?.satCompositeP25 ?? null, 400, 1600);
  const sat75 =
    validScore(latestFacts?.satCompositeP75 ?? null, 400, 1600) ??
    validScore(positioningSchool?.satCompositeP75 ?? null, 400, 1600);
  const sat50 = validScore(positioningSchool?.satCompositeP50 ?? null, 400, 1600);
  const satSubRate = positioningSchool?.satSubmitRate ?? null;
  if (sat25 != null && sat75 != null && sat25 <= sat75) {
    cells.push({
      key: "hub-sat",
      label: "SAT 25–75",
      value: `${sat25}–${sat75}`,
      sourceLabel: "§C9",
      sourceHref: yearBaseHref ? `${yearBaseHref}#testing` : null,
      subCaption: formatSubmitSubCaption(
        satSubRate != null ? satSubRate * 100 : null,
        sat50,
      ),
      rangeBar: {
        low: sat25,
        high: sat75,
        min: 400,
        max: 1600,
        median: sat50 && sat50 >= sat25 && sat50 <= sat75 ? sat50 : null,
      },
    });
  }

  // 4. ACT 25th-75th
  const act25 =
    validScore(latestFacts?.actCompositeP25 ?? null, 1, 36) ??
    validScore(positioningSchool?.actCompositeP25 ?? null, 1, 36);
  const act75 =
    validScore(latestFacts?.actCompositeP75 ?? null, 1, 36) ??
    validScore(positioningSchool?.actCompositeP75 ?? null, 1, 36);
  const act50 = validScore(positioningSchool?.actCompositeP50 ?? null, 1, 36);
  const actSubRate = positioningSchool?.actSubmitRate ?? null;
  if (act25 != null && act75 != null && act25 <= act75) {
    cells.push({
      key: "hub-act",
      label: "ACT 25–75",
      value: `${act25}–${act75}`,
      sourceLabel: "§C9",
      sourceHref: yearBaseHref ? `${yearBaseHref}#testing` : null,
      subCaption: formatSubmitSubCaption(
        actSubRate != null ? actSubRate * 100 : null,
        act50,
      ),
      rangeBar: {
        low: act25,
        high: act75,
        min: 1,
        max: 36,
        median: act50 && act50 >= act25 && act50 <= act75 ? act50 : null,
      },
    });
  }

  // 5. Retention (from federalFacts IPEDS series or Scorecard)
  const ipedsRetentionRows = (federalFacts ?? [])
    .filter(
      (f) =>
        f.field_key === "retention_rate_full_time" &&
        f.value_numeric != null &&
        f.value_numeric > 0 &&
        f.value_numeric <= 100,
    )
    .sort((a, b) => a.data_year - b.data_year);
  const latestIpedsRetention = ipedsRetentionRows.at(-1);
  if (scorecard?.retention_rate_ft != null && scorecard.retention_rate_ft > 0) {
    cells.push({
      key: "hub-retention",
      label: "Retention",
      value: `${Math.round(scorecard.retention_rate_ft * 100)}%`,
      sourceLabel: "SCORECARD",
      sourceHref: "#outcomes",
      subCaption: "Full-time 1st-yr",
      sparkline:
        ipedsRetentionRows.length >= 3
          ? {
              data: ipedsRetentionRows.map((r) => r.value_numeric!),
              yearSpan: `${ipedsRetentionRows[0].data_year}–${ipedsRetentionRows.at(-1)!.data_year}`,
            }
          : null,
    });
  } else if (latestIpedsRetention?.value_numeric != null) {
    cells.push({
      key: "hub-retention",
      label: "Retention",
      value: `${Math.round(latestIpedsRetention.value_numeric)}%`,
      sourceLabel: `IPEDS ${latestIpedsRetention.data_year}`,
      sourceHref: "#outcomes",
      subCaption: "Full-time 1st-yr",
      sparkline:
        ipedsRetentionRows.length >= 3
          ? {
              data: ipedsRetentionRows.map((r) => r.value_numeric!),
              yearSpan: `${ipedsRetentionRows[0].data_year}–${ipedsRetentionRows.at(-1)!.data_year}`,
            }
          : null,
    });
  }

  // 6. Average Net Price (Scorecard)
  if (scorecard?.avg_net_price != null && scorecard.avg_net_price > 0) {
    cells.push({
      key: "hub-net-price",
      label: "Net price",
      value: formatCurrency(scorecard.avg_net_price),
      sourceLabel: "SCORECARD",
      sourceHref: "#outcomes",
      subCaption: scorecard.scorecard_data_year
        ? `After grants · ${scorecard.scorecard_data_year}`
        : "After grants",
    });
  }

  return cells.slice(0, 6);
}

function RangeTickBar({ bar }: { bar: FactRibbonRangeBar }) {
  const span = bar.max - bar.min;
  if (span <= 0) return null;
  const leftPct = Math.max(0, Math.min(100, ((bar.low - bar.min) / span) * 100));
  const rightPct = Math.max(leftPct, Math.min(100, ((bar.high - bar.min) / span) * 100));
  const widthPct = Math.max(4, rightPct - leftPct);
  const medPct =
    bar.median != null
      ? Math.max(0, Math.min(100, ((bar.median - bar.min) / span) * 100))
      : null;

  return (
    <div
      className="cd-ribbon-range"
      aria-hidden="true"
      title={`25th–75th range on ${bar.min}–${bar.max} scale`}
    >
      <div className="cd-ribbon-range__track">
        <span
          className="cd-ribbon-range__fill"
          style={{ left: `${leftPct.toFixed(1)}%`, width: `${widthPct.toFixed(1)}%` }}
        />
        {medPct != null && (
          <span
            className="cd-ribbon-range__median"
            style={{ left: `${medPct.toFixed(1)}%` }}
          />
        )}
      </div>
    </div>
  );
}

function RibbonCellView({ cell }: { cell: FactRibbonCell }) {
  return (
    <div className="cd-ribbon__cell" data-testid={`ribbon-cell-${cell.key}`}>
      <div className="cd-ribbon__cell-head">
        <span className="meta cd-ribbon__label" title={cell.label}>
          {cell.label}
        </span>
        {cell.sourceHref ? (
          <Link href={cell.sourceHref} className="mono cd-ribbon__source">
            {cell.sourceLabel}
          </Link>
        ) : (
          <span className="mono cd-ribbon__source">{cell.sourceLabel}</span>
        )}
      </div>

      <div className="cd-ribbon__value-row">
        <span className="nums cd-ribbon__value">{cell.value}</span>
        {cell.sparkline && cell.sparkline.data.length >= 3 && (
          <span
            className="cd-ribbon__spark"
            title={
              cell.sparkline.yearSpan
                ? `Trend (${cell.sparkline.yearSpan})`
                : "Multi-year trend"
            }
          >
            <Sparkline
              data={cell.sparkline.data}
              w={40}
              h={14}
              color="var(--forest)"
            />
          </span>
        )}
      </div>

      {cell.rangeBar && <RangeTickBar bar={cell.rangeBar} />}

      {(cell.deltaText || cell.subCaption) && (
        <div className="mono cd-ribbon__sub">
          {cell.deltaText && (
            <span className="cd-ribbon__delta">{cell.deltaText}</span>
          )}
          {cell.subCaption && (
            <span className="cd-ribbon__sub-text">{cell.subCaption}</span>
          )}
        </div>
      )}
    </div>
  );
}

export function SchoolFactRibbon({
  bands,
  ariaLabel = "Key Common Data Set statistics",
}: {
  bands: FactRibbonBand[];
  ariaLabel?: string;
}) {
  const nonEmptyBands = bands.filter((b) => b.cells.length > 0);
  if (nonEmptyBands.length === 0) return null;

  return (
    <section className="cd-ribbon" aria-label={ariaLabel}>
      {nonEmptyBands.map((band) => (
        <div key={band.key} className="cd-ribbon__band">
          <div className="cd-ribbon__band-head">
            <span className="meta">{band.heading}</span>
            {band.sectionHref ? (
              <Link href={band.sectionHref} className="mono cd-ribbon__band-link">
                {band.sectionCode} →
              </Link>
            ) : (
              <span className="mono cd-ribbon__band-link">{band.sectionCode}</span>
            )}
          </div>
          <div className="cd-ribbon__grid">
            {band.cells.map((cell) => (
              <RibbonCellView key={cell.key} cell={cell} />
            ))}
          </div>
        </div>
      ))}
    </section>
  );
}
