"use client";

import { useMemo, useState } from "react";
import { formatRecipeShare } from "@/lib/format";
import {
  endowmentTercile,
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
]);

const W = 920;
const H = 560;
const M = { l: 72, r: 28, t: 36, b: 56 };
const IW = W - M.l - M.r;
const IH = H - M.t - M.b;
const MERIT_MIN = 50;
const MERIT_MAX = 40_000;
const GAP_MIN = -8000;
const GAP_MAX = 4000;
const TERCILES = ALIGNMENT_GAP_MERIT_META.endowmentTerciles;

function logX(merit: number): number {
  const clamped = Math.min(MERIT_MAX, Math.max(MERIT_MIN, merit));
  const t =
    (Math.log10(clamped) - Math.log10(MERIT_MIN)) /
    (Math.log10(MERIT_MAX) - Math.log10(MERIT_MIN));
  return M.l + t * IW;
}

function yGap(gap: number): number {
  const t = (gap - GAP_MIN) / (GAP_MAX - GAP_MIN);
  return M.t + (1 - t) * IH;
}

function tercileMark(endowmentPerStudent: number): {
  fill: string;
  open: boolean;
} {
  const band = endowmentTercile(endowmentPerStudent, TERCILES[0], TERCILES[1]);
  if (band === 2) return { fill: "none", open: true };
  if (band === 1) return { fill: "var(--forest)", open: false };
  return { fill: "var(--ochre)", open: false };
}

function shortName(name: string): string {
  return name
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
  none: "no gap to close",
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
        cx: logX(row.meritPerFirstYear),
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
            Vertical axis: alignment gap, dollars per year — College Scorecard.
            Horizontal axis: non-need merit spend per first-year student, log
            scale — CDS H2A. Color: endowment per undergraduate — IPEDS. The
            brick diagonal is where merit spend equals the annual gap.
            Everything to its right is already spending more than it would take
            to close it. Hover any dot — every school is named.
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
        aria-label="Scatter plot of alignment gap against merit spend per first-year student"
        onMouseMove={pickFromPointer}
        onPointerMove={pickFromPointer}
        onMouseLeave={() => setHoverId(null)}
        onPointerLeave={() => setHoverId(null)}
      >
        <line x1={M.l} x2={W - M.r} y1={zeroY} y2={zeroY} stroke="var(--rule-strong)" />
        <polyline
          points={diagonal}
          fill="none"
          stroke="var(--brick)"
          strokeWidth={1.5}
        />
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
        {[50, 200, 1000, 5000, 20_000].map((tick) => (
          <text
            key={`x${tick}`}
            x={logX(tick)}
            y={H - M.b + 20}
            textAnchor="middle"
            fontFamily="var(--mono)"
            fontSize="11"
            fill="var(--chart-axis)"
          >
            {formatUsd(tick)}
          </text>
        ))}
        <text x={M.l} y={22} fontFamily="var(--mono)" fontSize="10" fill="var(--ink-3)" letterSpacing="0.06em">
          GENUINELY CONSTRAINED · {ALIGNMENT_GAP_MERIT_META.regions.constrained}
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
          ALREADY SPENDING IT · {ALIGNMENT_GAP_MERIT_META.regions.covers}
        </text>
        <text
          x={M.l + IW / 2}
          y={H - 8}
          textAnchor="middle"
          fontFamily="var(--mono)"
          fontSize="10"
          fill="var(--ink-3)"
          letterSpacing="0.06em"
        >
          NO GAP TO CLOSE · {ALIGNMENT_GAP_MERIT_META.regions.none}
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
          const mark = tercileMark(pt.endowmentPerStudent);
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
                fill={mark.fill}
                fillOpacity={mark.open ? 1 : active ? 1 : 0.92}
                stroke={active || mark.open ? "var(--ink)" : "none"}
                strokeWidth={mark.open ? (active ? 2 : 1.45) : active ? 1.25 : 0}
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
          ALIGNMENT GAP · $ PER YEAR · SCORECARD
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
          <div>Merit spend {formatUsd(hover.meritPerFirstYear)} / first-year</div>
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
          ■ under {formatEndowmentPerStudent(TERCILES[0])}
        </span>
        <span style={{ color: "var(--forest)" }}>
          ■ {formatEndowmentPerStudent(TERCILES[0])}–{formatEndowmentPerStudent(TERCILES[1])}
        </span>
        <span style={{ color: "var(--ink)" }}>
          ○ {formatEndowmentPerStudent(TERCILES[1])} and over
        </span>
        <span style={{ color: "var(--brick)" }}>— merit = gap</span>
      </div>
    </div>
  );
}
