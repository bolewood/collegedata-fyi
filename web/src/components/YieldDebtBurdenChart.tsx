"use client";

import { useMemo, useRef, useState } from "react";
import { ChartHoverTooltip } from "@/components/ChartHoverTooltip";
import {
  formatBurdenPercent,
  formatInstructionRatio,
  formatRatePercent,
  formatUsd,
  formatUsdCents,
  panelBQuadrant,
  panelBSchools,
} from "@/lib/pricing-power-recipe-analysis";
import {
  PRICING_POWER_ANNOTATION_SCHOOL_ID,
  PRICING_POWER_META,
  PRICING_POWER_SCHOOLS,
} from "@/lib/pricing-power-recipe-data";

const W = 920;
const H = 560;
const M = { l: 72, r: 28, t: 40, b: 58 };
const IW = W - M.l - M.r;
const IH = H - M.t - M.b;
const UNIFORM_R = 3.5;
const SIZE_R_MIN = 3.5;
const SIZE_R_MAX = 6.5;
const BURDEN_MAX = 0.16;

const QUADRANT_LABEL: Record<string, string> = {
  higherYieldHigherBurden: "higher yield · higher debt burden",
  lowerYieldHigherBurden: "lower yield · higher debt burden",
  higherYieldLowerBurden: "higher yield · lower debt burden",
  lowerYieldLowerBurden: "lower yield · lower debt burden",
};

const PANEL_B = panelBSchools(PRICING_POWER_SCHOOLS);

export type Point = (typeof PANEL_B)[number] & {
  cx: number;
  cy: number;
  r: number;
};

function xs(rate: number): number {
  return M.l + rate * IW;
}

export function ys(burden: number): number {
  const t = Math.min(1, Math.max(0, burden / BURDEN_MAX));
  return M.t + (1 - t) * IH;
}

export function radiusForNetPrice(
  netPrice: number,
  minPrice: number,
  maxPrice: number,
  sizeEncoding: boolean,
): number {
  if (!sizeEncoding) return UNIFORM_R;
  const span = maxPrice - minPrice;
  if (span <= 0) return UNIFORM_R;
  const t = Math.sqrt(Math.min(1, Math.max(0, (netPrice - minPrice) / span)));
  return SIZE_R_MIN + t * (SIZE_R_MAX - SIZE_R_MIN);
}

function svgCoords(
  event: React.MouseEvent<SVGSVGElement> | React.PointerEvent<SVGSVGElement>,
): { x: number; y: number } | null {
  const svg = event.currentTarget;
  const ctm = svg.getScreenCTM();
  if (!ctm) return null;
  const pt = svg.createSVGPoint();
  pt.x = event.clientX;
  pt.y = event.clientY;
  const loc = pt.matrixTransform(ctm.inverse());
  return { x: loc.x, y: loc.y };
}

function hitRadiusInSvg(svg: SVGSVGElement): number {
  const ctm = svg.getScreenCTM();
  if (!ctm) return 20;
  const scale = Math.hypot(ctm.a, ctm.b);
  if (!Number.isFinite(scale) || scale <= 0) return 20;
  return 20 / scale;
}

export function nearestPoint(
  pts: readonly Point[],
  x: number,
  y: number,
  maxDist: number,
): Point | null {
  let best: Point | null = null;
  let bestDist = maxDist;
  for (const pt of pts) {
    const dist = Math.hypot(pt.cx - x, pt.cy - y);
    if (dist < bestDist) {
      best = pt;
      bestDist = dist;
    }
  }
  return best;
}

export function YieldDebtBurdenChart({
  sizeEncoding = false,
}: {
  sizeEncoding?: boolean;
} = {}) {
  const wrapRef = useRef<HTMLDivElement>(null);
  const [hoverId, setHoverId] = useState<string | null>(null);
  const [query, setQuery] = useState("");

  const pts: Point[] = useMemo(() => {
    let minPrice = Infinity;
    let maxPrice = 0;
    for (const row of PANEL_B) {
      if (row.avgNetPrice < minPrice) minPrice = row.avgNetPrice;
      if (row.avgNetPrice > maxPrice) maxPrice = row.avgNetPrice;
    }
    return PANEL_B.map((row) => ({
      ...row,
      cx: xs(row.yieldRate),
      cy: ys(row.burden),
      r: radiusForNetPrice(row.avgNetPrice, minPrice, maxPrice, sizeEncoding),
    }));
  }, [sizeEncoding]);

  const dotsHtml = useMemo(
    () =>
      pts
        .map(
          (pt) =>
            `<circle cx="${pt.cx.toFixed(1)}" cy="${pt.cy.toFixed(1)}" r="${pt.r.toFixed(2)}" fill="var(--chart-ink)" fill-opacity="0.45"/>`,
        )
        .join(""),
    [pts],
  );

  const match = query.trim().toLowerCase();
  const searched = match
    ? pts.find(
        (pt) =>
          pt.name.toLowerCase() === match ||
          pt.name.toLowerCase().includes(match) ||
          pt.schoolId.includes(match.replace(/\s+/g, "-")),
      ) ?? null
    : null;
  const hover =
    searched ?? (hoverId ? pts.find((pt) => pt.schoolId === hoverId) ?? null : null);
  const syracuse = pts.find(
    (pt) => pt.schoolId === PRICING_POWER_ANNOTATION_SCHOOL_ID,
  );

  const medianX = xs(PRICING_POWER_META.medianYieldB);
  const medianY = ys(PRICING_POWER_META.medianBurden);
  const scorecardYears = PRICING_POWER_META.scorecardYears.join(", ");

  const pickFromPointer = (
    event: React.MouseEvent<SVGSVGElement> | React.PointerEvent<SVGSVGElement>,
  ) => {
    const loc = svgCoords(event);
    if (!loc) return;
    const next = nearestPoint(
      pts,
      loc.x,
      loc.y,
      hitRadiusInSvg(event.currentTarget),
    );
    setHoverId(next?.schoolId ?? null);
  };

  return (
    <div
      className="cd-card"
      data-testid="yield-debt-burden-chart"
      style={{ padding: 24, position: "relative" }}
    >
      <div
        style={{
          display: "flex",
          alignItems: "baseline",
          justifyContent: "space-between",
          gap: 12,
          flexWrap: "wrap",
          marginBottom: 12,
        }}
      >
        <div>
          <div className="meta">Fig. 2 · Yield vs. graduate debt burden</div>
          <p
            style={{
              margin: "6px 0 0",
              fontSize: 13,
              color: "var(--ink-2)",
              maxWidth: 640,
              lineHeight: 1.5,
            }}
          >
            Dividers are this sample&apos;s medians:{" "}
            {formatRatePercent(PRICING_POWER_META.medianYieldB, 1)} yield and{" "}
            {formatBurdenPercent(PRICING_POWER_META.medianBurden)} debt burden among{" "}
            {PRICING_POWER_META.panelBCount.toLocaleString("en-US")} schools.
          </p>
          <p
            style={{
              margin: "8px 0 0",
              fontSize: 13,
              color: "var(--ink-2)",
              maxWidth: 640,
              lineHeight: 1.5,
            }}
          >
            {sizeEncoding
              ? "Dot size is a rough cue to average net price for Title IV aid recipients, compressed so the largest schools do not dominate the plot. It is not a second quantitative axis, and it is not what a full-pay family pays."
              : "Each school is drawn at the same size. Average net price is in the tooltip. It is the College Scorecard average for Title IV aid recipients, not the price a full-pay family pays."}
          </p>
          <p
            style={{
              margin: "8px 0 0",
              fontSize: 13,
              color: "var(--ink-2)",
              maxWidth: 640,
              lineHeight: 1.5,
            }}
          >
            Hover over any school to see the underlying values. Tooltips also
            show reported instructional spending per student divided by average
            net price. That ratio is not the share of a college&apos;s budget
            spent on teaching. Many schools overlap. Use search to highlight one.
          </p>
        </div>
        <label
          style={{
            display: "flex",
            flexDirection: "column",
            gap: 4,
            fontSize: 12,
            color: "var(--ink-3)",
          }}
        >
          Find a school
          <input
            list="pricing-power-panel-b-schools"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Syracuse, Fordham…"
            aria-label="Find a school in the yield and debt-burden chart"
            style={{
              border: "1px solid var(--rule-strong)",
              background: "var(--paper)",
              color: "var(--ink)",
              padding: "6px 10px",
              fontSize: 13,
              minWidth: 220,
            }}
          />
          <datalist id="pricing-power-panel-b-schools">
            {PANEL_B.map((row) => (
              <option key={row.schoolId} value={row.name} />
            ))}
          </datalist>
        </label>
      </div>

      <div ref={wrapRef} style={{ position: "relative" }}>
        <svg
          width={W}
          height={H}
          viewBox={`0 0 ${W} ${H}`}
          style={{ display: "block", margin: "0 auto", maxWidth: "100%", height: "auto" }}
          role="img"
          aria-label={`Scatter plot of yield against graduate debt burden for ${PRICING_POWER_META.panelBCount} schools. Yield runs from 0 to 100 percent. Debt burden is annual federal loan payments divided by median 10-year earnings. Dividers mark the sample medians.`}
          onMouseMove={pickFromPointer}
          onPointerMove={pickFromPointer}
          onMouseLeave={() => setHoverId(null)}
          onPointerLeave={() => setHoverId(null)}
        >
          <rect width={W} height={H} fill="transparent" />
          {[0, 0.04, 0.08, 0.12, 0.16].map((tick) => (
            <g key={`y${tick}`}>
              <line
                x1={M.l}
                x2={W - M.r}
                y1={ys(tick)}
                y2={ys(tick)}
                stroke="var(--chart-grid)"
              />
              <text
                x={M.l - 10}
                y={ys(tick) + 4}
                textAnchor="end"
                fontFamily="var(--mono)"
                fontSize="11"
                fill="var(--chart-axis)"
              >
                {formatBurdenPercent(tick, 0)}
              </text>
            </g>
          ))}
          {[0, 0.2, 0.4, 0.6, 0.8, 1].map((tick) => (
            <g key={`x${tick}`}>
              <line
                y1={M.t}
                y2={H - M.b}
                x1={xs(tick)}
                x2={xs(tick)}
                stroke="var(--chart-grid)"
              />
              <text
                y={H - M.b + 20}
                x={xs(tick)}
                textAnchor="middle"
                fontFamily="var(--mono)"
                fontSize="11"
                fill="var(--chart-axis)"
              >
                {formatRatePercent(tick, 0)}
              </text>
            </g>
          ))}
          <line
            x1={medianX}
            x2={medianX}
            y1={M.t}
            y2={H - M.b}
            stroke="var(--rule-strong)"
          />
          <line
            x1={M.l}
            x2={W - M.r}
            y1={medianY}
            y2={medianY}
            stroke="var(--rule-strong)"
          />
          <text
            x={medianX + 6}
            y={M.t + 14}
            fontFamily="var(--mono)"
            fontSize="10"
            fill="var(--ink-3)"
          >
            Median yield {formatRatePercent(PRICING_POWER_META.medianYieldB, 1)}
          </text>
          <text
            x={W - M.r}
            y={medianY - 6}
            textAnchor="end"
            fontFamily="var(--mono)"
            fontSize="10"
            fill="var(--ink-3)"
          >
            Median burden {formatBurdenPercent(PRICING_POWER_META.medianBurden)}
          </text>
          <text
            x={M.l}
            y={22}
            fontFamily="var(--mono)"
            fontSize="10"
            fill="var(--ink-3)"
            letterSpacing="0.06em"
          >
            II · LOWER YIELD, HIGHER BURDEN ·{" "}
            {PRICING_POWER_META.quadrantsB.lowerYieldHigherBurden}
          </text>
          <text
            x={W - M.r}
            y={22}
            textAnchor="end"
            fontFamily="var(--mono)"
            fontSize="10"
            fill="var(--ink-3)"
            letterSpacing="0.06em"
          >
            I · HIGHER YIELD, HIGHER BURDEN ·{" "}
            {PRICING_POWER_META.quadrantsB.higherYieldHigherBurden}
          </text>
          <text
            x={M.l}
            y={H - 8}
            fontFamily="var(--mono)"
            fontSize="10"
            fill="var(--ink-3)"
            letterSpacing="0.06em"
          >
            IV · LOWER YIELD, LOWER BURDEN ·{" "}
            {PRICING_POWER_META.quadrantsB.lowerYieldLowerBurden}
          </text>
          <text
            x={W - M.r}
            y={H - 8}
            textAnchor="end"
            fontFamily="var(--mono)"
            fontSize="10"
            fill="var(--ink-3)"
            letterSpacing="0.06em"
          >
            III · HIGHER YIELD, LOWER BURDEN ·{" "}
            {PRICING_POWER_META.quadrantsB.higherYieldLowerBurden}
          </text>
          <line x1={M.l} x2={M.l} y1={M.t} y2={H - M.b} stroke="var(--ink)" />
          <line
            x1={M.l}
            x2={W - M.r}
            y1={H - M.b}
            y2={H - M.b}
            stroke="var(--ink)"
          />
          <g pointerEvents="none" dangerouslySetInnerHTML={{ __html: dotsHtml }} />
          {syracuse && (
            <text
              x={syracuse.cx + 8}
              y={syracuse.cy - 6}
              fontFamily="var(--sans)"
              fontSize="11"
              fill="var(--ink-2)"
              pointerEvents="none"
            >
              Syracuse
            </text>
          )}
          {hover && (
            <g pointerEvents="none">
              <circle
                cx={hover.cx}
                cy={hover.cy}
                r={8}
                fill="var(--paper)"
                fillOpacity={0.92}
              />
              <circle
                cx={hover.cx}
                cy={hover.cy}
                r={5.5}
                fill="var(--forest)"
              />
            </g>
          )}
          <text
            transform={`translate(18 ${M.t + IH / 2}) rotate(-90)`}
            textAnchor="middle"
            fontFamily="var(--mono)"
            fontSize="10"
            fill="var(--chart-axis)"
            letterSpacing="0.08em"
          >
            DEBT BURDEN · ANNUAL FEDERAL LOAN PAYMENTS ÷ 10-YR EARNINGS
          </text>
          <text
            x={M.l + IW / 2}
            y={H - 2}
            textAnchor="middle"
            fontFamily="var(--mono)"
            fontSize="10"
            fill="var(--chart-axis)"
            letterSpacing="0.08em"
          >
            YIELD · ENROLLED ÷ ADMITTED
          </text>
        </svg>

        {hover && (
          <ChartHoverTooltip
            wrapRef={wrapRef}
            viewW={W}
            viewH={H}
            cx={hover.cx}
            cy={hover.cy}
            placementKey={hover.schoolId}
            testId="yield-debt-burden-tooltip"
          >
            <div className="serif" style={{ fontSize: 16 }}>
              {hover.name}
            </div>
            <div style={{ color: "var(--paper-3)", marginTop: 2 }}>
              {
                QUADRANT_LABEL[
                  panelBQuadrant(
                    hover.yieldRate,
                    hover.burden,
                    PRICING_POWER_META.medianYieldB,
                    PRICING_POWER_META.medianBurden,
                  )
                ]
              }
            </div>
            <div className="nums" style={{ marginTop: 6 }}>
              Yield {formatRatePercent(hover.yieldRate, 1)}
            </div>
            <div className="nums">
              Acceptance {formatRatePercent(hover.acceptanceRate, 1)}
            </div>
            <div className="nums">
              Debt burden {formatBurdenPercent(hover.burden)}
            </div>
            <div className="nums">Median debt {formatUsd(hover.medianDebt)}</div>
            <div className="nums">
              Annual payment {formatUsd(hover.monthlyPayment * 12)} (
              {formatUsdCents(hover.monthlyPayment)} × 12)
            </div>
            <div className="nums">
              Median 10-yr earnings {formatUsd(hover.earnings10yr)}
            </div>
            <div className="nums">Avg net price {formatUsd(hover.avgNetPrice)}</div>
            <div className="nums">
              Instruction/FTE {formatUsd(hover.instructionFte)}
            </div>
            <div className="nums">
              Instruction/net-price {formatInstructionRatio(hover.instructionNetPriceRatio)}{" "}
              — not a budget share
            </div>
            {hover.cdsYear &&
              hover.cdsAcceptanceRate != null &&
              hover.cdsYieldRate != null && (
                <div style={{ marginTop: 6, color: "var(--paper-3)" }}>
                  CDS {hover.cdsYear} cross-check: acceptance{" "}
                  {formatRatePercent(hover.cdsAcceptanceRate, 1)}, yield{" "}
                  {formatRatePercent(hover.cdsYieldRate, 1)}
                </div>
              )}
            <div style={{ marginTop: 6, color: "var(--paper-3)" }}>
              IPEDS {PRICING_POWER_META.ipedsCycle}; Scorecard {scorecardYears}
              {hover.cdsYear ? `; CDS ${hover.cdsYear}` : ""}
            </div>
          </ChartHoverTooltip>
        )}
      </div>
    </div>
  );
}
