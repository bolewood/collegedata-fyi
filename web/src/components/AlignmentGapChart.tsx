"use client";

import { useMemo, useRef, useState } from "react";
import { ChartHoverTooltip } from "@/components/ChartHoverTooltip";
import { formatRecipeShare } from "@/lib/format";
import {
  bandCircleStyle,
  bandMark,
  formatEndowmentPerStudent,
  formatGapUsd,
  formatUsd,
  formatInstructionShare,
  instructionShareBand,
  quadrantFor,
} from "@/lib/alignment-gap-recipe-analysis";
import {
  ALIGNMENT_GAP_META,
  ALIGNMENT_GAP_SCHOOLS,
} from "@/lib/alignment-gap-recipe-data";

const LABEL_IDS = new Set([
  "hollins-university",
  "bennington-college",
  "sarah-lawrence-college",
  "bard-college",
  "pratt-institute-main",
  "mcpherson-college",
  "catawba-college",
  "mount-holyoke-college",
  "grinnell-college",
  "bentley-university",
  "santa-clara-university",
  "babson-college",
  "wellesley-college",
  "princeton",
  "stanford",
  "earlham-college",
]);

const W = 920;
const H = 560;
const M = { l: 72, r: 28, t: 36, b: 56 };
const IW = W - M.l - M.r;
const IH = H - M.t - M.b;
const EPS_MIN = 2000;
const EPS_MAX = 8_000_000;
const GAP_MIN = -8000;
const GAP_MAX = 4000;

function logX(eps: number): number {
  const clamped = Math.min(EPS_MAX, Math.max(EPS_MIN, eps));
  const t =
    (Math.log10(clamped) - Math.log10(EPS_MIN)) /
    (Math.log10(EPS_MAX) - Math.log10(EPS_MIN));
  return M.l + t * IW;
}

function yGap(gap: number): number {
  const t = (gap - GAP_MIN) / (GAP_MAX - GAP_MIN);
  return M.t + (1 - t) * IH;
}

function shareMark(share: number) {
  return bandMark(instructionShareBand(share));
}

function shortName(name: string): string {
  return name
    .replace(" Institute of Technology", "")
    .replace(" Institute-Main", "")
    .replace(" Institute", "")
    .replace(/ \(.*\)$/, "")
    .replace(/ University$/, "")
    .replace(/ College$/, "");
}

type Point = (typeof ALIGNMENT_GAP_SCHOOLS)[number] & {
  cx: number;
  cy: number;
};

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

const QUADRANT_LABEL: Record<string, string> = {
  capacity: "higher burden · higher endowment",
  constrained: "higher burden · lower endowment",
  absorbs: "lower burden · higher endowment",
  earnings: "lower burden · lower endowment",
};

function hitRadiusInSvg(svg: SVGSVGElement): number {
  const ctm = svg.getScreenCTM();
  if (!ctm) return 20;
  const scale = Math.hypot(ctm.a, ctm.b);
  if (!Number.isFinite(scale) || scale <= 0) return 20;
  return 20 / scale;
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

export function AlignmentGapChart() {
  const wrapRef = useRef<HTMLDivElement>(null);
  const [hoverId, setHoverId] = useState<string | null>(null);
  const [query, setQuery] = useState("");

  const pts: Point[] = useMemo(
    () =>
      ALIGNMENT_GAP_SCHOOLS.map((row) => ({
        ...row,
        cx: logX(row.endowmentPerStudent),
        cy: yGap(row.gap),
      })),
    [],
  );

  const match = query.trim().toLowerCase();
  const searched = match
    ? pts.find(
        (pt) =>
          pt.schoolName.toLowerCase().includes(match) ||
          pt.schoolId.includes(match.replace(/\s+/g, "-")),
      ) ?? null
    : null;
  const hover = searched ?? (hoverId ? pts.find((pt) => pt.schoolId === hoverId) ?? null : null);

  const medianX = logX(ALIGNMENT_GAP_META.medianEndowmentPerStudent);
  const zeroY = yGap(0);

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
      data-testid="alignment-gap-endowment-chart"
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
          <div className="meta">Fig. 2 · Compare debt burden with endowment per student</div>
          <p style={{ margin: "6px 0 0", fontSize: 13, color: "var(--ink-2)", maxWidth: 640, lineHeight: 1.5 }}>
            The vertical axis again shows the alignment gap. A value above zero
            means the school&apos;s debt burden is above the{" "}
            {formatRecipeShare(ALIGNMENT_GAP_META.medianBurden, 2)} median. A
            value below zero means it is below the median. The horizontal axis
            shows endowment per undergraduate on a log scale. The vertical
            divider marks the sample median of about{" "}
            {formatUsd(Math.round(ALIGNMENT_GAP_META.medianEndowmentPerStudent / 1000) * 1000)}{" "}
            per undergraduate.
          </p>
          <p style={{ margin: "8px 0 0", fontSize: 13, color: "var(--ink-2)", maxWidth: 640, lineHeight: 1.5 }}>
            Color shows instructional spending per student as a share of average
            net price. This adds some context about the relationship between
            what students pay and what the institution reports spending on
            instruction. Endowment per student is only a broad measure of
            financial capacity. Endowments contain restricted funds, and two
            colleges with the same endowment per student may have very different
            obligations and spending policies. The chart is intended to show
            financial context, not available cash. Hover over any dot to see the
            school.
          </p>
        </div>
        <label style={{ display: "flex", flexDirection: "column", gap: 4, fontSize: 12, color: "var(--ink-3)" }}>
          Find a school
          <input
            list="alignment-gap-schools"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Hollins, Stanford…"
            aria-label="Find a school in the endowment join"
            style={{
              border: "1px solid var(--rule-strong)",
              background: "var(--paper)",
              color: "var(--ink)",
              padding: "6px 10px",
              fontSize: 13,
              minWidth: 220,
            }}
          />
          <datalist id="alignment-gap-schools">
            {ALIGNMENT_GAP_SCHOOLS.map((row) => (
              <option key={row.schoolId} value={row.schoolName} />
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
        aria-label="Scatter plot of alignment gap against endowment per undergraduate"
        onMouseMove={pickFromPointer}
        onPointerMove={pickFromPointer}
        onMouseLeave={() => setHoverId(null)}
        onPointerLeave={() => setHoverId(null)}
      >
        <line x1={M.l} x2={W - M.r} y1={zeroY} y2={zeroY} stroke="var(--brick)" strokeWidth={1.25} />
        <line x1={medianX} x2={medianX} y1={M.t} y2={H - M.b} stroke="var(--rule-strong)" />
        {[-6000, -3000, 0, 3000].map((tick) => (
          <g key={`y${tick}`}>
            <text
              x={M.l - 10}
              y={yGap(tick) + 4}
              textAnchor="end"
              fontFamily="var(--mono)"
              fontSize="11"
              fill="var(--chart-axis)"
            >
              {tick === 0 ? "$0" : formatGapUsd(tick)}
            </text>
          </g>
        ))}
        {[2000, 10_000, 50_000, 250_000, 1_000_000, 5_000_000].map((tick) => (
          <text
            key={`x${tick}`}
            x={logX(tick)}
            y={H - M.b + 20}
            textAnchor="middle"
            fontFamily="var(--mono)"
            fontSize="11"
            fill="var(--chart-axis)"
          >
            {formatEndowmentPerStudent(tick)}
          </text>
        ))}
        <text x={M.l} y={22} fontFamily="var(--mono)" fontSize="10" fill="var(--ink-3)" letterSpacing="0.06em">
          II · HIGHER BURDEN, LOWER ENDOWMENT · {ALIGNMENT_GAP_META.quadrants.constrained}
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
          I · HIGHER BURDEN, HIGHER ENDOWMENT · {ALIGNMENT_GAP_META.quadrants.capacity}
        </text>
        <text x={M.l} y={H - 8} fontFamily="var(--mono)" fontSize="10" fill="var(--ink-3)" letterSpacing="0.06em">
          IV · LOWER BURDEN, LOWER ENDOWMENT · {ALIGNMENT_GAP_META.quadrants.earnings}
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
          III · LOWER BURDEN, HIGHER ENDOWMENT · {ALIGNMENT_GAP_META.quadrants.absorbs}
        </text>
        <text
          x={W - M.r}
          y={zeroY - 6}
          textAnchor="end"
          fontFamily="var(--mono)"
          fontSize="10"
          fill="var(--brick)"
        >
          median burden {formatRecipeShare(ALIGNMENT_GAP_META.medianBurden, 2)}
        </text>
        {pts.map((pt) => {
          const active = hover?.schoolId === pt.schoolId;
          const mark = shareMark(pt.instructionShare);
          return (
            <g key={pt.schoolId}>
              <circle
                data-school-id={pt.schoolId}
                cx={pt.cx}
                cy={pt.cy}
                r={10}
                fill="transparent"
                onMouseEnter={() => setHoverId(pt.schoolId)}
                onPointerEnter={() => setHoverId(pt.schoolId)}
              />
              <circle
                cx={pt.cx}
                cy={pt.cy}
                r={active ? 6.5 : 4}
                {...bandCircleStyle(mark, active)}
                pointerEvents="none"
              />
            </g>
          );
        })}
        {pts
          .filter((pt) => LABEL_IDS.has(pt.schoolId))
          .map((pt) => (
            <text
              key={`label-${pt.schoolId}`}
              x={pt.cx + 8}
              y={pt.cy - 6}
              fontFamily="var(--sans)"
              fontSize="11"
              fill="var(--ink-2)"
              pointerEvents="none"
            >
              {shortName(pt.schoolName)}
            </text>
          ))}
        <text
          transform={`translate(18 ${M.t + IH / 2}) rotate(-90)`}
          textAnchor="middle"
          fontFamily="var(--mono)"
          fontSize="10"
          fill="var(--chart-axis)"
          letterSpacing="0.08em"
        >
          ALIGNMENT GAP · $ PER YEAR
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
          ENDOWMENT PER UNDERGRADUATE · LOG SCALE
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
          testId="alignment-gap-tooltip"
        >
          <div className="serif" style={{ fontSize: 16 }}>
            {hover.schoolName}
          </div>
          <div style={{ color: "var(--paper-3)", marginTop: 2 }}>
            CDS {hover.cdsYear} ·{" "}
            {QUADRANT_LABEL[
              quadrantFor(
                hover.gap,
                hover.endowmentPerStudent,
                ALIGNMENT_GAP_META.medianEndowmentPerStudent,
              )
            ]}
          </div>
          <div style={{ marginTop: 6 }}>Gap {formatGapUsd(hover.gap)}/yr</div>
          <div>Endowment {formatEndowmentPerStudent(hover.endowmentPerStudent)}/student</div>
          <div>Instruction {formatInstructionShare(hover.instructionShare)}</div>
          <div>Burden {formatRecipeShare(hover.burden, 1)}</div>
        </ChartHoverTooltip>
      )}
      </div>

      <div
        style={{
          display: "flex",
          flexWrap: "wrap",
          gap: 16,
          marginTop: 10,
          fontSize: 11,
          color: "var(--ink-3)",
          fontFamily: "var(--mono)",
          letterSpacing: "0.04em",
        }}
      >
        <span>INSTRUCTION / NET PRICE</span>
        <span style={{ color: "var(--ochre)" }}>■ under 55%</span>
        <span style={{ color: "var(--forest)" }}>■ 55–90%</span>
        <span style={{ color: "var(--ink)" }}>○ 90% and over</span>
        <span style={{ color: "var(--brick)" }}>— median burden</span>
      </div>
    </div>
  );
}
