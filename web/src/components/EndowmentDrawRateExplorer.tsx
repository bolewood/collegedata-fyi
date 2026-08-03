"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import {
  ENDOWMENT_DRAW_RATE_META,
  ENDOWMENT_DRAW_RATE_SCHOOLS,
  ENDOWMENT_DRAW_RATE_YEAR_SUMMARIES,
  type EndowmentDrawRateSchool,
} from "@/lib/endowment-draw-rate-recipe-data";
import {
  DEFAULT_ENDOWMENT_RECIPE_SCHOOL_ID,
  endowmentSchoolHistory,
  endowmentSchoolLabel,
  type EndowmentDrawRatePointView,
} from "@/lib/endowment-draw-rate-recipe-analysis";

const SECTOR_WIDTH = 920;
const SECTOR_HEIGHT = 360;
const SECTOR_MARGIN = { left: 76, right: 30, top: 36, bottom: 54 };
const SECTOR_MAX_RATE = 0.15;
const RATE_TICKS = [0, 0.05, 0.07, 0.1, 0.15] as const;

const SCHOOL_WIDTH = 920;
const SCHOOL_HEIGHT = 470;
const SCHOOL_MARGIN = { left: 82, right: 32, top: 42, bottom: 50 };
const SCHOOL_VALUE_TOP = 42;
const SCHOOL_VALUE_BOTTOM = 208;
const SCHOOL_RATE_TOP = 280;
const SCHOOL_RATE_BOTTOM = 420;

function formatPct(value: number | null, digits = 1): string {
  return value == null || !Number.isFinite(value)
    ? "n/a"
    : `${(value * 100).toFixed(digits)}%`;
}

function formatCurrency(value: number | null): string {
  if (value == null || !Number.isFinite(value)) return "n/a";
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: 0,
  }).format(value);
}

function formatCompactCurrency(value: number | null): string {
  if (value == null || !Number.isFinite(value)) return "n/a";
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    notation: "compact",
    maximumFractionDigits: 1,
  }).format(value);
}

function sectorX(value: number | null): number {
  const plotWidth = SECTOR_WIDTH - SECTOR_MARGIN.left - SECTOR_MARGIN.right;
  const bounded = Math.max(0, Math.min(SECTOR_MAX_RATE, value ?? 0));
  return SECTOR_MARGIN.left + (bounded / SECTOR_MAX_RATE) * plotWidth;
}

function sectorY(index: number): number {
  const plotHeight = SECTOR_HEIGHT - SECTOR_MARGIN.top - SECTOR_MARGIN.bottom;
  return SECTOR_MARGIN.top + (plotHeight / ENDOWMENT_DRAW_RATE_YEAR_SUMMARIES.length) * (index + 0.5);
}

function SectorDistributionChart() {
  return (
    <div className="endowment-chart-card cd-card">
      <div className="endowment-chart-head">
        <div className="meta">Fig. 1 · Reported draw-rate distribution</div>
        <div className="mono endowment-chart-key">
          LINE P10–P90 · BAR P25–P75 · DOT MEDIAN
        </div>
      </div>
      <div className="endowment-chart-scroll" tabIndex={0}>
        <svg
          width={SECTOR_WIDTH}
          height={SECTOR_HEIGHT}
          viewBox={`0 0 ${SECTOR_WIDTH} ${SECTOR_HEIGHT}`}
          className="endowment-chart-svg"
          role="img"
          aria-label={`Annual private nonprofit IPEDS endowment draw-rate distributions from fiscal year ${ENDOWMENT_DRAW_RATE_META.minYear} through ${ENDOWMENT_DRAW_RATE_META.maxYear}`}
        >
          {RATE_TICKS.map((tick) => (
            <g key={tick}>
              <line
                x1={sectorX(tick)}
                x2={sectorX(tick)}
                y1={SECTOR_MARGIN.top - 10}
                y2={SECTOR_HEIGHT - SECTOR_MARGIN.bottom}
                stroke={tick === 0.05 || tick === 0.07 ? "var(--forest)" : "var(--chart-grid)"}
                strokeDasharray={tick === 0.05 || tick === 0.07 ? "4 4" : undefined}
                opacity={tick === 0.05 || tick === 0.07 ? 0.55 : 1}
              />
              <text
                x={sectorX(tick)}
                y={SECTOR_HEIGHT - 22}
                textAnchor="middle"
                fontFamily="var(--mono)"
                fontSize="11"
                fill="var(--chart-axis)"
              >
                {formatPct(tick, 0)}
              </text>
            </g>
          ))}
          {ENDOWMENT_DRAW_RATE_YEAR_SUMMARIES.map((summary, index) => {
            const y = sectorY(index);
            return (
              <g key={summary.year}>
                <line
                  x1={SECTOR_MARGIN.left}
                  x2={SECTOR_WIDTH - SECTOR_MARGIN.right}
                  y1={y}
                  y2={y}
                  stroke="var(--rule)"
                />
                <text
                  x={SECTOR_MARGIN.left - 16}
                  y={y + 4}
                  textAnchor="end"
                  fontFamily="var(--mono)"
                  fontSize="12"
                  fill="var(--ink)"
                >
                  FY{summary.year}
                </text>
                <line
                  x1={sectorX(summary.p10)}
                  x2={sectorX(summary.p90)}
                  y1={y}
                  y2={y}
                  stroke="var(--chart-ink)"
                  strokeWidth="2"
                >
                  <title>{`FY${summary.year}: 10th percentile ${formatPct(summary.p10)}, 90th percentile ${formatPct(summary.p90)}`}</title>
                </line>
                <line
                  x1={sectorX(summary.p25)}
                  x2={sectorX(summary.p75)}
                  y1={y}
                  y2={y}
                  stroke="var(--chart-ink)"
                  strokeWidth="12"
                  opacity="0.28"
                >
                  <title>{`FY${summary.year}: middle half ${formatPct(summary.p25)} to ${formatPct(summary.p75)}`}</title>
                </line>
                <circle cx={sectorX(summary.median)} cy={y} r="5" fill="var(--forest)">
                  <title>{`FY${summary.year} median: ${formatPct(summary.median)}`}</title>
                </circle>
              </g>
            );
          })}
          <text
            x={(SECTOR_MARGIN.left + SECTOR_WIDTH - SECTOR_MARGIN.right) / 2}
            y={SECTOR_HEIGHT - 2}
            textAnchor="middle"
            fontFamily="var(--sans)"
            fontSize="12"
            fill="var(--ink)"
          >
            Spending distribution ÷ beginning-of-year endowment value →
          </text>
        </svg>
      </div>
      <p className="endowment-chart-note">
        Reference lines mark 5% and 7%. The scale stops at 15% to keep the main distribution
        readable. The table below includes every eligible school, including rates beyond the
        chart.
      </p>
    </div>
  );
}

function ThresholdTable() {
  return (
    <div className="endowment-table-wrap" tabIndex={0}>
      <table className="endowment-table">
        <thead>
          <tr>
            <th>Fiscal year</th>
            <th>Eligible / reporters</th>
            <th>Median</th>
            <th>Above 5%</th>
            <th>Above 7%</th>
            <th>Above 15%</th>
            <th>Release</th>
          </tr>
        </thead>
        <tbody>
          {ENDOWMENT_DRAW_RATE_YEAR_SUMMARIES.map((summary) => (
            <tr key={summary.year}>
              <th>FY{summary.year}</th>
              <td>{summary.eligible.toLocaleString()} / {summary.reporters.toLocaleString()}</td>
              <td>{formatPct(summary.median)}</td>
              <td>{formatPct(summary.above5Share)} <span>({summary.above5Count})</span></td>
              <td>{formatPct(summary.above7Share)} <span>({summary.above7Count})</span></td>
              <td>{formatPct(summary.above15Share)} <span>({summary.above15Count})</span></td>
              <td><span className="cd-chip">{summary.releaseType}</span></td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function schoolX(index: number, count: number): number {
  const plotWidth = SCHOOL_WIDTH - SCHOOL_MARGIN.left - SCHOOL_MARGIN.right;
  return count <= 1
    ? SCHOOL_MARGIN.left + plotWidth / 2
    : SCHOOL_MARGIN.left + (index / (count - 1)) * plotWidth;
}

function scaleY(value: number, maximum: number, top: number, bottom: number): number {
  if (maximum <= 0) return bottom;
  return bottom - (value / maximum) * (bottom - top);
}

function SchoolHistoryChart({ school }: { school: EndowmentDrawRateSchool }) {
  const history = endowmentSchoolHistory(school);
  const valueMaximum = Math.max(
    1,
    ...history.map((point) => point.endingValue ?? 0),
  );
  const rateMaximum = Math.max(
    0.15,
    ...history.map((point) => point.drawRate ?? 0),
  ) * 1.08;
  const rateSegments: { point: EndowmentDrawRatePointView; x: number }[][] = [];
  let activeSegment: { point: EndowmentDrawRatePointView; x: number }[] = [];
  history.forEach((point, index) => {
    if (point.drawRate == null) {
      if (activeSegment.length > 0) rateSegments.push(activeSegment);
      activeSegment = [];
      return;
    }
    activeSegment.push({ point, x: schoolX(index, history.length) });
  });
  if (activeSegment.length > 0) rateSegments.push(activeSegment);
  const barWidth = Math.min(58, 480 / Math.max(history.length, 1));

  return (
    <div className="endowment-chart-scroll" tabIndex={0}>
      <svg
        width={SCHOOL_WIDTH}
        height={SCHOOL_HEIGHT}
        viewBox={`0 0 ${SCHOOL_WIDTH} ${SCHOOL_HEIGHT}`}
        className="endowment-chart-svg"
        role="img"
        aria-label={`Endowment value and draw-rate history for ${school.schoolName}`}
      >
        <text x="0" y="16" fontFamily="var(--mono)" fontSize="11" fill="var(--ink-3)">
          ENDING ENDOWMENT VALUE
        </text>
        <text x="0" y={SCHOOL_RATE_TOP - 22} fontFamily="var(--mono)" fontSize="11" fill="var(--ink-3)">
          DRAW RATE
        </text>
        <line
          x1={SCHOOL_MARGIN.left}
          x2={SCHOOL_WIDTH - SCHOOL_MARGIN.right}
          y1={SCHOOL_VALUE_BOTTOM}
          y2={SCHOOL_VALUE_BOTTOM}
          stroke="var(--rule-strong)"
        />
        {history.map((point, index) => {
          const x = schoolX(index, history.length);
          const y = scaleY(point.endingValue ?? 0, valueMaximum, SCHOOL_VALUE_TOP, SCHOOL_VALUE_BOTTOM);
          return (
            <g key={`value-${point.year}`}>
              {point.endingValue != null && (
                <rect
                  x={x - barWidth / 2}
                  y={y}
                  width={barWidth}
                  height={SCHOOL_VALUE_BOTTOM - y}
                  fill="var(--chart-ink)"
                  opacity="0.78"
                >
                  <title>{`FY${point.year} ending value: ${formatCurrency(point.endingValue)}`}</title>
                </rect>
              )}
              <text
                x={x}
                y={Math.max(SCHOOL_VALUE_TOP + 12, y - 8)}
                textAnchor="middle"
                fontFamily="var(--mono)"
                fontSize="10"
                fill="var(--ink-3)"
              >
                {formatCompactCurrency(point.endingValue)}
              </text>
            </g>
          );
        })}
        {[0.05, 0.07, 0.15].map((threshold) => {
          const y = scaleY(threshold, rateMaximum, SCHOOL_RATE_TOP, SCHOOL_RATE_BOTTOM);
          return (
            <g key={threshold}>
              <line
                x1={SCHOOL_MARGIN.left}
                x2={SCHOOL_WIDTH - SCHOOL_MARGIN.right}
                y1={y}
                y2={y}
                stroke={threshold === 0.15 ? "var(--chart-grid)" : "var(--forest)"}
                strokeDasharray="4 4"
                opacity="0.55"
              />
              <text
                x={SCHOOL_MARGIN.left - 12}
                y={y + 4}
                textAnchor="end"
                fontFamily="var(--mono)"
                fontSize="10"
                fill="var(--chart-axis)"
              >
                {formatPct(threshold, 0)}
              </text>
            </g>
          );
        })}
        {rateSegments.map((segment) => {
          const path = segment
            .map(({ point, x }, index) =>
              `${index === 0 ? "M" : "L"} ${x} ${scaleY(point.drawRate!, rateMaximum, SCHOOL_RATE_TOP, SCHOOL_RATE_BOTTOM)}`,
            )
            .join(" ");
          return (
            <path
              key={`${segment[0].point.year}-${segment.at(-1)!.point.year}`}
              d={path}
              fill="none"
              stroke="var(--forest)"
              strokeWidth="2.5"
            />
          );
        })}
        {history.map((point, index) => {
          const x = schoolX(index, history.length);
          return (
            <g key={`rate-${point.year}`}>
              {point.drawRate != null ? (
                <circle
                  cx={x}
                  cy={scaleY(point.drawRate, rateMaximum, SCHOOL_RATE_TOP, SCHOOL_RATE_BOTTOM)}
                  r="5"
                  fill="var(--forest)"
                  stroke="var(--paper)"
                  strokeWidth="2"
                >
                  <title>{`FY${point.year} draw rate: ${formatPct(point.drawRate, 2)}`}</title>
                </circle>
              ) : (
                <text
                  x={x}
                  y={SCHOOL_RATE_BOTTOM - 8}
                  textAnchor="middle"
                  fontFamily="var(--mono)"
                  fontSize="12"
                  fill="var(--ink-4)"
                >
                  n/a
                </text>
              )}
              <text
                x={x}
                y={SCHOOL_HEIGHT - 20}
                textAnchor="middle"
                fontFamily="var(--mono)"
                fontSize="11"
                fill="var(--ink)"
              >
                FY{point.year}
              </text>
            </g>
          );
        })}
      </svg>
    </div>
  );
}

function exclusionLabel(point: EndowmentDrawRatePointView): string {
  switch (point.exclusionReason) {
    case "accounting_identity_mismatch":
      return "component identity mismatch";
    case "nonpositive_beginning_value":
      return "nonpositive beginning value";
    case "non_reported_input":
      return "non-reported input";
    case "incomplete_components":
      return "incomplete components";
    default:
      return "not eligible";
  }
}

function SchoolDetail({ school }: { school: EndowmentDrawRateSchool }) {
  const history = endowmentSchoolHistory(school);
  const hasSmallDenominator = history.some(
    (point) => point.beginningValue != null && point.beginningValue < 5_000_000,
  );
  return (
    <section className="endowment-school-detail cd-card">
      <div className="endowment-school-title-row">
        <div>
          <div className="meta">§ School history</div>
          <h3>{school.schoolName}</h3>
          <p className="endowment-school-meta mono">
            IPEDS {school.ipedsId}{school.state ? ` · ${school.state}` : ""}
          </p>
        </div>
        {school.hasCurrentSchoolPage && school.schoolId ? (
          <Link href={`/schools/${school.schoolId}`} className="cd-btn cd-btn--ghost">
            Open school page →
          </Link>
        ) : (
          <span className="cd-chip">Historical/raw API only</span>
        )}
      </div>
      <SchoolHistoryChart school={school} />
      {hasSmallDenominator && (
        <p className="endowment-volatility-note">
          At least one beginning value is below $5 million. A single gift, transfer, or
          spend-down can move this ratio by several percentage points. Treat this series as
          volatile context.
        </p>
      )}
      <div className="endowment-table-wrap endowment-school-table-wrap" tabIndex={0}>
        <table className="endowment-table">
          <thead>
            <tr>
              <th>FY</th>
              <th>Beginning value</th>
              <th>Ending value</th>
              <th>Reported spending</th>
              <th>Draw rate</th>
              <th>Source</th>
            </tr>
          </thead>
          <tbody>
            {history.map((point) => (
              <tr key={point.year}>
                <th>{point.year}</th>
                <td>{formatCurrency(point.beginningValue)}</td>
                <td>{formatCurrency(point.endingValue)}</td>
                <td>{formatCurrency(point.spendingDistribution)}</td>
                <td>
                  {point.drawRate == null
                    ? <span title={exclusionLabel(point)}>n/a*</span>
                    : formatPct(point.drawRate, 2)}
                </td>
                <td><span className="mono">{point.sourceTable}</span> · {point.releaseType}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

export function EndowmentDrawRateExplorer() {
  const [selectedIpedsId, setSelectedIpedsId] = useState<string | null>(
    DEFAULT_ENDOWMENT_RECIPE_SCHOOL_ID,
  );
  const selectedSchool = useMemo(
    () => ENDOWMENT_DRAW_RATE_SCHOOLS.find((school) => school.ipedsId === selectedIpedsId) ?? null,
    [selectedIpedsId],
  );

  return (
    <div className="endowment-explorer">
      <section>
        <div className="endowment-section-heading">
          <div>
            <div className="meta">§ Sector view</div>
            <h2>An independent estimate from public federal data</h2>
          </div>
          <div className="endowment-data-stamp mono">
            {ENDOWMENT_DRAW_RATE_META.datasetVersion}<br />
            Generated {ENDOWMENT_DRAW_RATE_META.generatedAt}
          </div>
        </div>
        <p className="endowment-section-copy">
          Each year covers schools that were private nonprofits and reported Finance Part H.
          The denominator includes rows with a positive beginning value and reported inputs.
          Rows must also pass the component identity check (the beginning value plus the reported
          parts equals the year-end value). Rates use the absolute reported spending amount. This
          sign-normalizes the mixed positive and negative reporting convention in FY2020–21.
        </p>
        <SectorDistributionChart />
        <ThresholdTable />
      </section>

      <section className="endowment-school-section rule-2">
        <div className="endowment-section-heading">
          <div>
            <div className="meta">§ Pick a school</div>
            <h2>Compare a school to the sector</h2>
          </div>
          <span className="cd-chip">{ENDOWMENT_DRAW_RATE_SCHOOLS.length.toLocaleString()} schools</span>
        </div>
        <label className="endowment-school-picker">
          <span className="meta">School</span>
          <select
            value={selectedIpedsId ?? ""}
            onChange={(event) => setSelectedIpedsId(event.target.value || null)}
          >
            <option value="">Choose a school (none selected by default)</option>
            {ENDOWMENT_DRAW_RATE_SCHOOLS.map((school) => (
              <option key={school.ipedsId} value={school.ipedsId}>
                {endowmentSchoolLabel(school)}
              </option>
            ))}
          </select>
        </label>
        {selectedSchool ? (
          <SchoolDetail school={selectedSchool} />
        ) : (
          <div className="endowment-neutral-default cd-card cd-card--cut">
            <p>
              No school is preselected or highlighted, so the sector-wide view stays up until
              you choose one.
            </p>
          </div>
        )}
      </section>
    </div>
  );
}
