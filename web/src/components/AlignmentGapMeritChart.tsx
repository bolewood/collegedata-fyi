"use client";

import { useMemo, useState } from "react";
import { formatRecipeShare } from "@/lib/format";
import {
  bandCircleStyle,
  bandMark,
  endowmentBand,
  formatEndowmentPerStudent,
  formatGapUsd,
  formatUsd,
  meritRegion,
} from "@/lib/alignment-gap-recipe-analysis";
import {
  ALIGNMENT_GAP_MERIT_META,
  ALIGNMENT_GAP_MERIT_SCHOOLS,
} from "@/lib/alignment-gap-recipe-data";

const LABEL_IDS = new Set([
  "quincy-university",
  "depauw-university",
  "beloit-college",
  "pratt-institute-main",
  "kentucky-state-university",
  "hollins-university",
  "north-carolina-a-and-t-state-university",
  "university-of-the-incarnate-word",
]);

const W = 920;
const H = 580;
const PLOT_T = 36;
const PLOT_B = H - 76;
const PLOT_R = W - 24;
const RAIL_L = 66;
const RAIL_W = 44;
const RAIL_R = RAIL_L + RAIL_W;
const RAIL_GAP = 20;
const LOG_L = RAIL_R + RAIL_GAP;
const RAIL_CX = RAIL_L + RAIL_W / 2;
const MERIT_MIN = 5;
const MERIT_MAX = 40_000;
const GAP_MIN = -8000;
const GAP_MAX = 4000;
const LOW_CUT = ALIGNMENT_GAP_MERIT_META.endowmentLowCut;
const HIGH_CUT = ALIGNMENT_GAP_MERIT_META.endowmentHighCut;

function logX(merit: number): number {
  const clamped = Math.min(MERIT_MAX, Math.max(MERIT_MIN, merit));
  const t =
    (Math.log10(clamped) - Math.log10(MERIT_MIN)) /
    (Math.log10(MERIT_MAX) - Math.log10(MERIT_MIN));
  return LOG_L + t * (PLOT_R - LOG_L);
}

function meritX(merit: number): number {
  if (merit <= 0) return RAIL_CX;
  return logX(merit);
}

function yGap(gap: number): number {
  const t = (gap - GAP_MIN) / (GAP_MAX - GAP_MIN);
  return PLOT_T + (1 - t) * (PLOT_B - PLOT_T);
}

function endowmentMark(endowmentPerStudent: number) {
  return bandMark(endowmentBand(endowmentPerStudent, LOW_CUT, HIGH_CUT));
}

function shortName(name: string): string {
  return name
    .replace("University of the Incarnate Word", "Incarnate Word")
    .replace(" Institute of Technology", "")
    .replace(" Institute-Main", "")
    .replace(" Institute", "")
    .replace(" State University", "")
    .replace(/ \(.*\)$/, "")
    .replace("North Carolina A & T", "NC A&T")
    .replace(/ University$/, "")
    .replace(/ College$/, "");
}

type Point = (typeof ALIGNMENT_GAP_MERIT_SCHOOLS)[number] & {
  cx: number;
  cy: number;
  zeroMerit: boolean;
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

const REGION_LABEL: Record<string, string> = {
  covers: "already spending it",
  constrained: "genuinely constrained",
  none: "gap ≤ 0",
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

function diagonalPoints(): string {
  const pts: string[] = [];
  const steps = 48;
  for (let i = 0; i <= steps; i += 1) {
    const t = i / steps;
    const merit = MERIT_MIN * (MERIT_MAX / MERIT_MIN) ** t;
    if (merit > GAP_MAX) {
      pts.push(`${logX(GAP_MAX)},${yGap(GAP_MAX)}`);
      break;
    }
    pts.push(`${logX(merit)},${yGap(merit)}`);
  }
  return pts.join(" ");
}

export function AlignmentGapMeritChart() {
  const [hoverId, setHoverId] = useState<string | null>(null);
  const [query, setQuery] = useState("");

  const pts: Point[] = useMemo(
    () =>
      ALIGNMENT_GAP_MERIT_SCHOOLS.map((row) => ({
        ...row,
        cx: meritX(row.meritPerFirstYear),
        cy: yGap(row.gap),
        zeroMerit: row.meritPerFirstYear <= 0,
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

  const zeroY = yGap(0);
  const diagonal = useMemo(() => diagonalPoints(), []);

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
      data-testid="alignment-gap-merit-chart"
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
          <div className="meta">Fig. 1 · Are they already spending it?</div>
          <p style={{ margin: "6px 0 0", fontSize: 13, color: "var(--ink-2)", maxWidth: 640, lineHeight: 1.5 }}>
            Vertical axis: alignment gap, dollars per year — College Scorecard,
            against the same {formatRecipeShare(ALIGNMENT_GAP_MERIT_META.medianBurden, 2)}{" "}
            median as Fig. 2. Horizontal axis: non-need merit spend per
            first-year student — CDS H2A. Values above $0 use a log scale;{" "}
            {ALIGNMENT_GAP_MERIT_META.zeroMeritCount} schools that award no
            merit aid sit on the left rail, off that scale. Color: endowment
            per undergraduate — IPEDS, with the same{" "}
            {formatEndowmentPerStudent(HIGH_CUT)} high cut as Fig. 2. The brick
            diagonal is where merit spend equals the annual gap. Everything to
            its right is already spending more than it would take to close it.
            Hover any dot — every school is named.
          </p>
        </div>
        <label style={{ display: "flex", flexDirection: "column", gap: 4, fontSize: 12, color: "var(--ink-3)" }}>
          Find a school
          <input
            list="alignment-gap-merit-schools"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Quincy, Hollins…"
            aria-label="Find a school in the merit join"
            style={{
              border: "1px solid var(--rule-strong)",
              background: "var(--paper)",
              color: "var(--ink)",
              padding: "6px 10px",
              fontSize: 13,
              minWidth: 220,
            }}
          />
          <datalist id="alignment-gap-merit-schools">
            {ALIGNMENT_GAP_MERIT_SCHOOLS.map((row) => (
              <option key={row.schoolId} value={row.schoolName} />
            ))}
          </datalist>
        </label>
      </div>

      <div style={{ position: "relative" }}>
      <svg
        width={W}
        height={H}
        viewBox={`0 0 ${W} ${H}`}
        style={{ display: "block", margin: "0 auto", maxWidth: "100%", height: "auto" }}
        role="img"
        aria-label="Scatter plot of alignment gap against merit spend per first-year student, with a separate rail for schools that award no merit aid"
        onMouseMove={pickFromPointer}
        onPointerMove={pickFromPointer}
        onMouseLeave={() => setHoverId(null)}
        onPointerLeave={() => setHoverId(null)}
      >
        <rect
          data-testid="alignment-gap-zero-rail"
          x={RAIL_L}
          y={PLOT_T}
          width={RAIL_W}
          height={PLOT_B - PLOT_T}
          fill="var(--paper-2)"
        />
        <line
          x1={RAIL_R}
          x2={RAIL_R}
          y1={PLOT_T}
          y2={PLOT_B}
          stroke="var(--rule-strong)"
        />
        <line x1={RAIL_L} x2={RAIL_R} y1={zeroY} y2={zeroY} stroke="var(--rule-strong)" />
        <line x1={LOG_L} x2={PLOT_R} y1={zeroY} y2={zeroY} stroke="var(--rule-strong)" />
        <polyline
          points={diagonal}
          fill="none"
          stroke="var(--brick)"
          strokeWidth={1.5}
        />
        {[-6000, -3000, 0, 3000].map((tick) => (
          <g key={`y${tick}`}>
            <text
              x={RAIL_L - 8}
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
        <text
          x={RAIL_CX}
          y={PLOT_B + 20}
          textAnchor="middle"
          fontFamily="var(--mono)"
          fontSize="11"
          fill="var(--chart-axis)"
        >
          $0
        </text>
        <text
          x={RAIL_CX}
          y={PLOT_B + 34}
          textAnchor="middle"
          fontFamily="var(--mono)"
          fontSize="9"
          fill="var(--ink-3)"
          letterSpacing="0.06em"
        >
          NO MERIT AID
        </text>
        {[10, 100, 1000, 5000, 20_000].map((tick) => (
          <text
            key={`x${tick}`}
            x={logX(tick)}
            y={PLOT_B + 20}
            textAnchor="middle"
            fontFamily="var(--mono)"
            fontSize="11"
            fill="var(--chart-axis)"
          >
            {formatUsd(tick)}
          </text>
        ))}
        <text x={LOG_L} y={22} fontFamily="var(--mono)" fontSize="10" fill="var(--ink-3)" letterSpacing="0.06em">
          GENUINELY CONSTRAINED · {ALIGNMENT_GAP_MERIT_META.regions.constrained}
        </text>
        <text
          x={PLOT_R}
          y={22}
          textAnchor="end"
          fontFamily="var(--mono)"
          fontSize="10"
          fill="var(--ink-3)"
          letterSpacing="0.06em"
        >
          ALREADY SPENDING IT · {ALIGNMENT_GAP_MERIT_META.regions.covers}
        </text>
        <text
          x={(LOG_L + PLOT_R) / 2}
          y={PLOT_B - 10}
          textAnchor="middle"
          fontFamily="var(--mono)"
          fontSize="10"
          fill="var(--ink-3)"
          letterSpacing="0.06em"
        >
          GAP ≤ 0 · {ALIGNMENT_GAP_MERIT_META.regions.none}
        </text>
        <text
          x={PLOT_R}
          y={zeroY - 6}
          textAnchor="end"
          fontFamily="var(--mono)"
          fontSize="10"
          fill="var(--brick)"
        >
          median burden {formatRecipeShare(ALIGNMENT_GAP_MERIT_META.medianBurden, 2)}
        </text>
        <text
          x={logX(1400)}
          y={yGap(1400) - 8}
          textAnchor="middle"
          fontFamily="var(--mono)"
          fontSize="10"
          fill="var(--brick)"
        >
          merit spend = annual gap
        </text>
        {pts.map((pt) => {
          const active = hover?.schoolId === pt.schoolId;
          const mark = endowmentMark(pt.endowmentPerStudent);
          return (
            <g key={pt.schoolId}>
              <circle
                data-school-id={pt.schoolId}
                data-zero-merit={pt.zeroMerit ? "true" : "false"}
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
              x={pt.zeroMerit ? RAIL_R + 6 : pt.cx + 8}
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
          transform={`translate(16 ${(PLOT_T + PLOT_B) / 2}) rotate(-90)`}
          textAnchor="middle"
          fontFamily="var(--mono)"
          fontSize="10"
          fill="var(--chart-axis)"
          letterSpacing="0.08em"
        >
          ALIGNMENT GAP · $ PER YEAR · SCORECARD
        </text>
        <text
          x={(LOG_L + PLOT_R) / 2}
          y={H - 8}
          textAnchor="middle"
          fontFamily="var(--mono)"
          fontSize="10"
          fill="var(--chart-axis)"
          letterSpacing="0.08em"
        >
          MERIT SPEND PER FIRST-YEAR · LOG SCALE · CDS H2A
        </text>
      </svg>

      {hover && (
        <div
          data-testid="alignment-gap-merit-tooltip"
          style={{
            position: "absolute",
            left: `${Math.min(((hover.cx + 12) / W) * 100, 72)}%`,
            top: `${Math.max(((hover.cy - 36) / H) * 100, 6)}%`,
            pointerEvents: "none",
            background: "var(--ink)",
            color: "var(--paper)",
            padding: "10px 12px",
            fontSize: 13,
            lineHeight: 1.45,
            minWidth: 200,
            zIndex: 2,
          }}
        >
          <div className="serif" style={{ fontSize: 16 }}>
            {hover.schoolName}
          </div>
          <div style={{ color: "var(--paper-3)", marginTop: 2 }}>
            CDS {hover.cdsYear} · {REGION_LABEL[meritRegion(hover.gap, hover.meritPerFirstYear)]}
          </div>
          <div style={{ marginTop: 6 }}>Gap {formatGapUsd(hover.gap)}/yr</div>
          <div>
            Merit spend {hover.zeroMerit ? "$0 · no merit aid" : `${formatUsd(hover.meritPerFirstYear)} / first-year`}
          </div>
          <div>
            {formatRecipeShare(hover.meritShare, 0)} receive {formatUsd(hover.avgMeritGrant)}
          </div>
          <div>Endowment {formatEndowmentPerStudent(hover.endowmentPerStudent)}/student</div>
          <div>Burden {formatRecipeShare(hover.burden, 1)}</div>
        </div>
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
        <span>ENDOWMENT / UNDERGRADUATE</span>
        <span style={{ color: "var(--ochre)" }}>
          ■ under {formatEndowmentPerStudent(LOW_CUT)}
        </span>
        <span style={{ color: "var(--forest)" }}>
          ■ {formatEndowmentPerStudent(LOW_CUT)}–{formatEndowmentPerStudent(HIGH_CUT)}
        </span>
        <span style={{ color: "var(--ink)" }}>
          ○ {formatEndowmentPerStudent(HIGH_CUT)} and over
        </span>
        <span style={{ color: "var(--brick)" }}>— merit = gap</span>
      </div>
    </div>
  );
}
