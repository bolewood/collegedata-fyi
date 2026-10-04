"use client";

import { useMemo, useRef, useState, useEffect } from "react";
import { ChartHoverTooltip } from "@/components/ChartHoverTooltip";
import { formatRecipeShare } from "@/lib/format";
import {
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
const H = 600;
const PLOT_T = 38;
const GAP_ZERO_Y = 380;
const SHELF_T = 416;
const SHELF_B = 496;
const PLOT_R = W - 24;
const RAIL_L = 66;
const RAIL_W = 44;
const RAIL_R = RAIL_L + RAIL_W;
const RAIL_GAP = 20;
const LOG_L = RAIL_R + RAIL_GAP;
const RAIL_CX = RAIL_L + RAIL_W / 2;
const MERIT_MIN = 5;
const MERIT_MAX = 40_000;
const POS_GAP_MAX = 3600;

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
  if (gap > 0) {
    const clamped = Math.min(POS_GAP_MAX, gap);
    return PLOT_T + (1 - clamped / POS_GAP_MAX) * (GAP_ZERO_Y - PLOT_T);
  }
  // Base shelf for debt burden at or below median
  const clamped = Math.max(-6000, gap);
  const t = (clamped - (-6000)) / (0 - (-6000));
  return SHELF_B - t * (SHELF_B - SHELF_T);
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
  region: "covers" | "constrained" | "none";
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
  covers: "merit aid larger than the gap",
  constrained: "merit aid smaller than the gap",
  none: "debt burden at or below the median",
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
  currentId: string | null,
): Point | null {
  let best: Point | null = null;
  let bestDist = maxDist;
  for (const pt of pts) {
    const dist = Math.hypot(pt.cx - x, pt.cy - y);
    // Hysteresis: keep currently hovered point unless another is distinctly closer
    const effectiveDist = pt.schoolId === currentId ? dist - 4 : dist;
    if (effectiveDist < bestDist) {
      best = pt;
      bestDist = effectiveDist;
    }
  }
  return best;
}

function diagonalPoints(): string {
  const pts: string[] = [];
  const steps = 48;
  for (let i = 0; i <= steps; i += 1) {
    const t = i / steps;
    const merit = MERIT_MIN * (POS_GAP_MAX / MERIT_MIN) ** t;
    if (merit > POS_GAP_MAX) {
      pts.push(`${Math.round(logX(POS_GAP_MAX))},${Math.round(yGap(POS_GAP_MAX))}`);
      break;
    }
    pts.push(`${Math.round(logX(merit))},${Math.round(yGap(merit))}`);
  }
  return pts.join(" ");
}

export function AlignmentGapMeritChart({
  selectedSchoolId,
  onSelectSchool,
}: {
  selectedSchoolId?: string | null;
  onSelectSchool?: (schoolId: string | null) => void;
} = {}) {
  const wrapRef = useRef<HTMLDivElement>(null);
  const [hoverId, setHoverId] = useState<string | null>(null);
  const [query, setQuery] = useState("");

  const pts: Point[] = useMemo(
    () =>
      ALIGNMENT_GAP_MERIT_SCHOOLS.map((row) => ({
        ...row,
        cx: meritX(row.meritPerFirstYear),
        cy: yGap(row.gap),
        zeroMerit: row.meritPerFirstYear <= 0,
        region: meritRegion(row.gap, row.meritPerFirstYear),
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

  // Sync external selection if provided or via global event
  useEffect(() => {
    if (selectedSchoolId) {
      const found = pts.find((pt) => pt.schoolId === selectedSchoolId);
      if (found && query !== found.schoolName) {
        setQuery(found.schoolName);
      }
    }
  }, [selectedSchoolId, pts, query]);

  useEffect(() => {
    const handleSelect = (event: Event) => {
      const custom = event as CustomEvent<string | null>;
      const id = custom.detail;
      setHoverId(id);
      if (id) {
        const found = pts.find((pt) => pt.schoolId === id);
        if (found && query !== found.schoolName) setQuery(found.schoolName);
      }
    };
    window.addEventListener("collegedata:select-school", handleSelect);
    return () => window.removeEventListener("collegedata:select-school", handleSelect);
  }, [pts, query]);

  const activeId = selectedSchoolId ?? searched?.schoolId ?? hoverId;
  const hover = activeId ? pts.find((pt) => pt.schoolId === activeId) ?? null : null;

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
      hoverId,
    );
    setHoverId(next?.schoolId ?? null);
  };

  const handleCircleClick = (schoolId: string) => {
    const nextId = activeId === schoolId ? null : schoolId;
    if (onSelectSchool) {
      onSelectSchool(nextId);
    }
    if (typeof window !== "undefined") {
      window.dispatchEvent(
        new CustomEvent("collegedata:select-school", { detail: nextId }),
      );
    }
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
          <div className="meta">Fig. 1 · Compare the debt gap with merit aid</div>
          <p style={{ margin: "6px 0 0", fontSize: 13, color: "var(--ink-2)", maxWidth: 640, lineHeight: 1.5 }}>
            The vertical axis shows the alignment gap in dollars per year. The
            horizontal axis shows estimated non-need merit aid per full-time
            first-year student, using the Common Data Set. Because most values
            are spread over a wide range, the axis uses a log scale. Schools
            reporting no non-need merit aid are shown separately at $0.
          </p>
          <p style={{ margin: "8px 0 0", fontSize: 13, color: "var(--ink-2)", maxWidth: 640, lineHeight: 1.5 }}>
            The diagonal line is where the two amounts are equal. Schools to the
            lower-right of the line report more non-need merit aid per first-year
            student than the size of their alignment gap. Schools to the
            upper-left report less. Color highlights this trade-off: forest green
            schools award more in merit aid than their debt gap, while ochre
            schools carry a debt gap larger than their merit budget.
          </p>
          <p style={{ margin: "8px 0 0", fontSize: 13, color: "var(--ink-2)", maxWidth: 640, lineHeight: 1.5 }}>
            These amounts are useful for comparison, but they are not
            interchangeable dollar for dollar. Merit aid is generally a tuition
            discount rather than a cash expenditure, and changing a college&apos;s
            aid policy would not necessarily produce an equal change in student
            borrowing. Hover over any dot to see the school.
          </p>
        </div>
        <label style={{ display: "flex", flexDirection: "column", gap: 4, fontSize: 12, color: "var(--ink-3)" }}>
          Find a school
          <div style={{ display: "flex", gap: 6, alignItems: "center" }}>
            <input
              list="alignment-gap-merit-schools"
              value={query}
              onChange={(event) => {
                setQuery(event.target.value);
                const typed = event.target.value.trim().toLowerCase();
                const found = pts.find(
                  (pt) =>
                    pt.schoolName.toLowerCase() === typed ||
                    pt.schoolId === typed.replace(/\s+/g, "-"),
                );
                if (found) {
                  if (onSelectSchool) onSelectSchool(found.schoolId);
                  if (typeof window !== "undefined") {
                    window.dispatchEvent(
                      new CustomEvent("collegedata:select-school", { detail: found.schoolId }),
                    );
                  }
                }
              }}
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
            {query && (
              <button
                type="button"
                onClick={() => {
                  setQuery("");
                  setHoverId(null);
                  if (onSelectSchool) onSelectSchool(null);
                  if (typeof window !== "undefined") {
                    window.dispatchEvent(
                      new CustomEvent("collegedata:select-school", { detail: null }),
                    );
                  }
                }}
                style={{
                  border: "1px solid var(--rule)",
                  background: "transparent",
                  color: "var(--ink-3)",
                  padding: "6px 8px",
                  fontSize: 12,
                  cursor: "pointer",
                }}
                title="Clear selection"
              >
                ✕
              </button>
            )}
          </div>
          <datalist id="alignment-gap-merit-schools">
            {ALIGNMENT_GAP_MERIT_SCHOOLS.map((row) => (
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
          aria-label="Scatter plot of alignment gap against merit spend per first-year student, with a separate rail for schools that award no merit aid"
          onMouseMove={pickFromPointer}
          onPointerMove={pickFromPointer}
          onMouseLeave={() => setHoverId(null)}
          onPointerLeave={() => setHoverId(null)}
        >
          {/* Zero merit aid rail on left */}
          <rect
            data-testid="alignment-gap-zero-rail"
            x={RAIL_L}
            y={PLOT_T}
            width={RAIL_W}
            height={SHELF_B - PLOT_T}
            fill="var(--paper-2)"
          />
          <line
            x1={RAIL_R}
            x2={RAIL_R}
            y1={PLOT_T}
            y2={SHELF_B}
            stroke="var(--rule-strong)"
          />

          {/* Dedicated base shelf for below-median debt burden */}
          <rect
            x={RAIL_L}
            y={SHELF_T}
            width={PLOT_R - RAIL_L}
            height={SHELF_B - SHELF_T}
            fill="var(--paper-2)"
            fillOpacity={0.65}
          />
          <line x1={RAIL_L} x2={PLOT_R} y1={SHELF_T} y2={SHELF_T} stroke="var(--rule)" strokeDasharray="3 3" />

          {/* Median burden divider line ($0 annual gap) */}
          <line x1={RAIL_L} x2={RAIL_R} y1={GAP_ZERO_Y} y2={GAP_ZERO_Y} stroke="var(--rule-strong)" />
          <line x1={LOG_L} x2={PLOT_R} y1={GAP_ZERO_Y} y2={GAP_ZERO_Y} stroke="var(--rule-strong)" strokeWidth={1.25} />

          {/* Diagonal parity line: merit = gap */}
          <polyline
            points={diagonal}
            fill="none"
            stroke="var(--brick)"
            strokeWidth={1.75}
          />

          {/* Y-axis Ticks for positive gap */}
          {[1000, 2000, 3000].map((tick) => (
            <g key={`y${tick}`}>
              <line
                x1={RAIL_L - 4}
                x2={RAIL_L}
                y1={yGap(tick)}
                y2={yGap(tick)}
                stroke="var(--chart-axis)"
              />
              <text
                x={RAIL_L - 8}
                y={yGap(tick) + 4}
                textAnchor="end"
                fontFamily="var(--mono)"
                fontSize="11"
                fill="var(--chart-axis)"
              >
                {formatGapUsd(tick)}
              </text>
            </g>
          ))}

          {/* $0 Tick */}
          <text
            x={RAIL_L - 8}
            y={GAP_ZERO_Y + 4}
            textAnchor="end"
            fontFamily="var(--mono)"
            fontSize="11"
            fill="var(--chart-axis)"
          >
            $0
          </text>

          {/* Base shelf tick */}
          <text
            x={RAIL_L - 8}
            y={(SHELF_T + SHELF_B) / 2 + 4}
            textAnchor="end"
            fontFamily="var(--mono)"
            fontSize="10"
            fill="var(--ink-3)"
          >
            ≤ $0
          </text>

          {/* X-axis: Zero Rail label */}
          <text
            x={RAIL_CX}
            y={SHELF_B + 18}
            textAnchor="middle"
            fontFamily="var(--mono)"
            fontSize="11"
            fill="var(--chart-axis)"
          >
            $0
          </text>
          <text
            x={RAIL_CX}
            y={SHELF_B + 32}
            textAnchor="middle"
            fontFamily="var(--mono)"
            fontSize="9"
            fill="var(--ink-3)"
            letterSpacing="0.06em"
          >
            NO MERIT AID
          </text>

          {/* X-axis: Log Ticks */}
          {[10, 100, 1000, 5000, 20_000].map((tick) => (
            <g key={`x${tick}`}>
              <line
                x1={logX(tick)}
                x2={logX(tick)}
                y1={SHELF_B}
                y2={SHELF_B + 5}
                stroke="var(--chart-axis)"
              />
              <text
                x={logX(tick)}
                y={SHELF_B + 18}
                textAnchor="middle"
                fontFamily="var(--mono)"
                fontSize="11"
                fill="var(--chart-axis)"
              >
                {formatUsd(tick)}
              </text>
            </g>
          ))}

          {/* Region Annotations */}
          <text x={LOG_L} y={22} fontFamily="var(--mono)" fontSize="10" fill="var(--ochre)" letterSpacing="0.06em" fontWeight={600}>
            SMALLER THAN THE GAP · {ALIGNMENT_GAP_MERIT_META.regions.constrained}
          </text>
          <text
            x={PLOT_R}
            y={22}
            textAnchor="end"
            fontFamily="var(--mono)"
            fontSize="10"
            fill="var(--forest)"
            letterSpacing="0.06em"
            fontWeight={600}
          >
            LARGER THAN THE GAP · {ALIGNMENT_GAP_MERIT_META.regions.covers}
          </text>
          <text
            x={(LOG_L + PLOT_R) / 2}
            y={SHELF_T - 8}
            textAnchor="middle"
            fontFamily="var(--mono)"
            fontSize="10"
            fill="var(--ink-3)"
            letterSpacing="0.06em"
          >
            AT OR BELOW MEDIAN · {ALIGNMENT_GAP_MERIT_META.regions.none}
          </text>
          <text
            x={PLOT_R}
            y={GAP_ZERO_Y - 6}
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
            fontWeight={600}
          >
            merit spend = annual gap
          </text>

          {/* Points */}
          {pts.map((pt) => {
            const active = hover?.schoolId === pt.schoolId;
            const isZero = pt.zeroMerit;
            const isNone = pt.region === "none";
            const isCovers = pt.region === "covers";

            // Visual encoding: Forest for covers, Ochre for constrained, open circle for none
            let fill = isCovers ? "var(--forest)" : "var(--ochre)";
            let stroke = isCovers ? "var(--forest)" : "var(--ochre)";
            let open = false;

            if (isNone) {
              open = true;
              fill = "none";
              stroke = "var(--ink)";
            }

            return (
              <g
                key={pt.schoolId}
                style={{ cursor: "pointer" }}
                onClick={() => handleCircleClick(pt.schoolId)}
              >
                {/* Hit target */}
                <circle
                  data-school-id={pt.schoolId}
                  data-zero-merit={isZero ? "true" : "false"}
                  cx={pt.cx}
                  cy={pt.cy}
                  r={12}
                  fill="transparent"
                  onMouseEnter={() => setHoverId(pt.schoolId)}
                  onPointerEnter={() => setHoverId(pt.schoolId)}
                />
                {/* Outer halo when active */}
                {active && (
                  <circle
                    cx={pt.cx}
                    cy={pt.cy}
                    r={9}
                    fill="none"
                    stroke="var(--ink)"
                    strokeWidth={2}
                    opacity={0.8}
                    pointerEvents="none"
                  />
                )}
                {/* Core dot */}
                <circle
                  cx={pt.cx}
                  cy={pt.cy}
                  r={active ? 6 : 4}
                  fill={fill}
                  fillOpacity={open ? 1 : active ? 1 : 0.88}
                  stroke={open ? "var(--ink)" : active ? "var(--ink)" : stroke}
                  strokeWidth={open ? (active ? 2 : 1.45) : active ? 1.5 : 0.5}
                  pointerEvents="none"
                />
              </g>
            );
          })}

          {/* Named School Labels */}
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
                style={{ textShadow: "0 0 3px var(--paper), 0 0 5px var(--paper)" }}
              >
                {shortName(pt.schoolName)}
              </text>
            ))}

          {/* Axis Titles */}
          <text
            transform={`translate(16 ${(PLOT_T + SHELF_B) / 2}) rotate(-90)`}
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
            y={H - 12}
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
          <ChartHoverTooltip
            wrapRef={wrapRef}
            viewW={W}
            viewH={H}
            cx={hover.cx}
            cy={hover.cy}
            placementKey={hover.schoolId}
            testId="alignment-gap-merit-tooltip"
          >
            <div className="serif" style={{ fontSize: 16 }}>
              {hover.schoolName}
            </div>
            <div style={{ color: "var(--paper-3)", marginTop: 2 }}>
              CDS {hover.cdsYear} · {REGION_LABEL[hover.region]}
            </div>
            <div style={{ marginTop: 6, fontWeight: 600 }}>Gap {formatGapUsd(hover.gap)}/yr</div>
            <div>
              Merit spend {hover.zeroMerit ? "$0 · no merit aid" : `${formatUsd(hover.meritPerFirstYear)} / first-year`}
            </div>
            {!hover.zeroMerit && (
              <div>
                {formatRecipeShare(hover.meritShare, 0)} receive {formatUsd(hover.avgMeritGrant)}
              </div>
            )}
            <div>Endowment {formatEndowmentPerStudent(hover.endowmentPerStudent)}/student</div>
            <div>Burden {formatRecipeShare(hover.burden, 1)}</div>
          </ChartHoverTooltip>
        )}
      </div>

      {/* Legend */}
      <div
        style={{
          display: "flex",
          flexWrap: "wrap",
          gap: 16,
          marginTop: 12,
          fontSize: 11,
          color: "var(--ink-3)",
          fontFamily: "var(--mono)",
          letterSpacing: "0.04em",
          alignItems: "center",
        }}
      >
        <span>STATUS</span>
        <span style={{ color: "var(--forest)", display: "inline-flex", alignItems: "center", gap: 5 }}>
          ● Merit aid exceeds gap ({ALIGNMENT_GAP_MERIT_META.regions.covers})
        </span>
        <span style={{ color: "var(--ochre)", display: "inline-flex", alignItems: "center", gap: 5 }}>
          ● Debt gap exceeds merit aid ({ALIGNMENT_GAP_MERIT_META.regions.constrained})
        </span>
        <span style={{ color: "var(--ink)", display: "inline-flex", alignItems: "center", gap: 5 }}>
          ○ At or below median debt burden ({ALIGNMENT_GAP_MERIT_META.regions.none})
        </span>
        <span style={{ color: "var(--brick)" }}>— merit spend = annual gap</span>
      </div>
    </div>
  );
}
