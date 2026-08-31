"use client";

import { useMemo, useRef, useState } from "react";
import { ChartHoverTooltip } from "@/components/ChartHoverTooltip";
import {
  formatRatePercent,
  panelAQuadrant,
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
const DOT_R = 3.5;
// Pointer hit radius in CSS pixels, rescaled into SVG units per event.
const HIT_RADIUS_CSS_PX = 20;

const QUADRANT_LABEL: Record<string, string> = {
  lowerAcceptanceHigherYield: "lower acceptance · higher yield",
  higherAcceptanceHigherYield: "higher acceptance · higher yield",
  lowerAcceptanceLowerYield: "lower acceptance · lower yield",
  higherAcceptanceLowerYield: "higher acceptance · lower yield",
};

type Point = (typeof PRICING_POWER_SCHOOLS)[number] & {
  cx: number;
  cy: number;
};

function xs(rate: number): number {
  return M.l + rate * IW;
}

function ys(rate: number): number {
  return M.t + (1 - rate) * IH;
}

function svgCoords(
  event: React.PointerEvent<SVGSVGElement>,
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
  if (!ctm) return HIT_RADIUS_CSS_PX;
  const scale = Math.hypot(ctm.a, ctm.b);
  if (!Number.isFinite(scale) || scale <= 0) return HIT_RADIUS_CSS_PX;
  return HIT_RADIUS_CSS_PX / scale;
}

function nearestPoint(
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

export function AcceptanceYieldChart() {
  const wrapRef = useRef<HTMLDivElement>(null);
  const [hoverId, setHoverId] = useState<string | null>(null);
  const [query, setQuery] = useState("");

  const pts: Point[] = useMemo(
    () =>
      PRICING_POWER_SCHOOLS.map((row) => ({
        ...row,
        cx: xs(row.acceptanceRate),
        cy: ys(row.yieldRate),
      })),
    [],
  );

  const dotsHtml = useMemo(
    () =>
      pts
        .map(
          (pt) =>
            `<circle cx="${pt.cx.toFixed(1)}" cy="${pt.cy.toFixed(1)}" r="${DOT_R}" fill="var(--chart-ink)" fill-opacity="0.45"/>`,
        )
        .join(""),
    [pts],
  );

  // Eight school names appear more than once in the dataset (branch
  // campuses in different states). Disambiguate their search labels so
  // every school is reachable and the tooltip never shows a namesake's
  // numbers.
  const searchable = useMemo(() => {
    const nameCounts = new Map<string, number>();
    for (const pt of pts) {
      const key = pt.name.toLowerCase();
      nameCounts.set(key, (nameCounts.get(key) ?? 0) + 1);
    }
    return pts.map((pt) => ({
      pt,
      label:
        (nameCounts.get(pt.name.toLowerCase()) ?? 0) > 1
          ? `${pt.name} (IPEDS ${pt.ipedsId})`
          : pt.name,
    }));
  }, [pts]);

  const datalistOptions = useMemo(
    () =>
      searchable.map(({ pt, label }) => (
        <option key={pt.schoolId} value={label} />
      )),
    [searchable],
  );

  const match = query.trim().toLowerCase();
  const searched = match
    ? (searchable.find((s) => s.label.toLowerCase() === match)?.pt ??
      searchable.find(
        (s) =>
          s.label.toLowerCase().includes(match) ||
          s.pt.schoolId.includes(match.replace(/\s+/g, "-")),
      )?.pt ??
      null)
    : null;
  const hover =
    searched ?? (hoverId ? pts.find((pt) => pt.schoolId === hoverId) ?? null : null);
  const syracuse = pts.find(
    (pt) => pt.schoolId === PRICING_POWER_ANNOTATION_SCHOOL_ID,
  );

  const medianX = xs(PRICING_POWER_META.medianAcceptance);
  const medianY = ys(PRICING_POWER_META.medianYield);

  const pickFromPointer = (event: React.PointerEvent<SVGSVGElement>) => {
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
      data-testid="acceptance-yield-chart"
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
          <div className="meta">Fig. 1 · Acceptance rate vs. yield</div>
          <p
            style={{
              margin: "6px 0 0",
              fontSize: 13,
              color: "var(--ink-2)",
              maxWidth: 640,
              lineHeight: 1.5,
            }}
          >
            Dividers are this sample&apos;s medians, not 50% lines:{" "}
            {formatRatePercent(PRICING_POWER_META.medianAcceptance, 1)} acceptance
            and {formatRatePercent(PRICING_POWER_META.medianYield, 1)} yield among{" "}
            {PRICING_POWER_META.panelACount.toLocaleString("en-US")} schools.
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
            Hover over any dot to see the school and its underlying numbers. Many
            schools overlap. Use search to highlight one.
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
            list="pricing-power-panel-a-schools"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Syracuse, Reed…"
            aria-label="Find a school in the acceptance and yield chart"
            style={{
              border: "1px solid var(--rule-strong)",
              background: "var(--paper)",
              color: "var(--ink)",
              padding: "6px 10px",
              fontSize: 13,
              minWidth: 220,
            }}
          />
          <datalist id="pricing-power-panel-a-schools">{datalistOptions}</datalist>
        </label>
      </div>

      <div ref={wrapRef} style={{ position: "relative" }}>
        <svg
          width={W}
          height={H}
          viewBox={`0 0 ${W} ${H}`}
          style={{ display: "block", margin: "0 auto", maxWidth: "100%", height: "auto" }}
          role="img"
          aria-label={`Scatter plot of acceptance rate against yield for ${PRICING_POWER_META.panelACount} schools. Both axes run from 0 to 100 percent. Dividers mark the sample medians.`}
          onPointerMove={pickFromPointer}
          onPointerLeave={() => setHoverId(null)}
        >
          <rect width={W} height={H} fill="transparent" />
          {[0, 0.2, 0.4, 0.6, 0.8, 1].map((tick) => (
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
                {formatRatePercent(tick, 0)}
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
            Median acceptance {formatRatePercent(PRICING_POWER_META.medianAcceptance, 1)}
          </text>
          <text
            x={W - M.r}
            y={medianY - 6}
            textAnchor="end"
            fontFamily="var(--mono)"
            fontSize="10"
            fill="var(--ink-3)"
          >
            Median yield {formatRatePercent(PRICING_POWER_META.medianYield, 1)}
          </text>
          <text
            x={M.l}
            y={22}
            fontFamily="var(--mono)"
            fontSize="10"
            fill="var(--ink-3)"
            letterSpacing="0.06em"
          >
            I · LOWER ACCEPTANCE, HIGHER YIELD ·{" "}
            {PRICING_POWER_META.quadrantsA.lowerAcceptanceHigherYield}
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
            II · HIGHER ACCEPTANCE, HIGHER YIELD ·{" "}
            {PRICING_POWER_META.quadrantsA.higherAcceptanceHigherYield}
          </text>
          <text
            x={M.l}
            y={H - 8}
            fontFamily="var(--mono)"
            fontSize="10"
            fill="var(--ink-3)"
            letterSpacing="0.06em"
          >
            III · LOWER ACCEPTANCE, LOWER YIELD ·{" "}
            {PRICING_POWER_META.quadrantsA.lowerAcceptanceLowerYield}
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
            IV · HIGHER ACCEPTANCE, LOWER YIELD ·{" "}
            {PRICING_POWER_META.quadrantsA.higherAcceptanceLowerYield}
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
            YIELD · ENROLLED ÷ ADMITTED
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
            ACCEPTANCE RATE · ADMITTED ÷ APPLIED
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
            testId="acceptance-yield-tooltip"
          >
            <div className="serif" style={{ fontSize: 16 }}>
              {hover.name}
            </div>
            <div style={{ color: "var(--paper-3)", marginTop: 2 }}>
              {PRICING_POWER_META.ipedsCycle} ·{" "}
              {
                QUADRANT_LABEL[
                  panelAQuadrant(
                    hover.acceptanceRate,
                    hover.yieldRate,
                    PRICING_POWER_META.medianAcceptance,
                    PRICING_POWER_META.medianYield,
                  )
                ]
              }
            </div>
            <div className="nums" style={{ marginTop: 6 }}>
              Acceptance {formatRatePercent(hover.acceptanceRate, 1)}
            </div>
            <div className="nums">Yield {formatRatePercent(hover.yieldRate, 1)}</div>
            <div style={{ marginTop: 6, color: "var(--paper-3)" }}>
              Applied {hover.applied.toLocaleString("en-US")} · Admitted{" "}
              {hover.admitted.toLocaleString("en-US")} · Enrolled{" "}
              {hover.enrolled.toLocaleString("en-US")}
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
              IPEDS {PRICING_POWER_META.ipedsCycle}
            </div>
          </ChartHoverTooltip>
        )}
      </div>
    </div>
  );
}
