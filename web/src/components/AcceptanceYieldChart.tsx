"use client";

import { useState } from "react";

type SchoolPoint = {
  school: string;
  cdsYear: string;
  applied: number;
  admitted: number;
  enrolled: number;
  source: "ground-truth" | "api";
};

const DATA: SchoolPoint[] = [
  // Hand-audited ground-truth seeds
  { school: "Harvard University", cdsYear: "2024-25", applied: 54008, admitted: 1970, enrolled: 1647, source: "ground-truth" },
  { school: "Dartmouth College", cdsYear: "2024-25", applied: 31656, admitted: 1710, enrolled: 1182, source: "ground-truth" },
  { school: "Harvey Mudd College", cdsYear: "2025-26", applied: 5213, admitted: 641, enrolled: 234, source: "ground-truth" },
  // Live-API rows
  { school: "Stanford University", cdsYear: "2024-25", applied: 57326, admitted: 2067, enrolled: 1693, source: "api" },
  { school: "Princeton University", cdsYear: "2024-25", applied: 40468, admitted: 1868, enrolled: 1410, source: "api" },
  { school: "Brown University", cdsYear: "2024-25", applied: 48904, admitted: 2638, enrolled: 1719, source: "api" },
  { school: "Duke University", cdsYear: "2024-25", applied: 51795, admitted: 2957, enrolled: 1740, source: "api" },
  { school: "Cornell University", cdsYear: "2024-25", applied: 65612, admitted: 5516, enrolled: 3525, source: "api" },
  { school: "Northeastern University", cdsYear: "2024-25", applied: 98425, admitted: 5133, enrolled: 2759, source: "api" },
  { school: "University of Notre Dame", cdsYear: "2025-26", applied: 35401, admitted: 3320, enrolled: 2118, source: "api" },
  { school: "Rice University", cdsYear: "2024-25", applied: 32473, admitted: 2597, enrolled: 1148, source: "api" },
  { school: "Johns Hopkins University", cdsYear: "2024-25", applied: 45895, admitted: 2954, enrolled: 1389, source: "api" },
  { school: "New York University", cdsYear: "2024-25", applied: 110807, admitted: 10232, enrolled: 5666, source: "api" },
  { school: "University of Southern California", cdsYear: "2024-25", applied: 82027, admitted: 8050, enrolled: 3489, source: "api" },
  { school: "Washington University in St Louis", cdsYear: "2024-25", applied: 32754, admitted: 3951, enrolled: 1847, source: "api" },
  { school: "Boston College", cdsYear: "2024-25", applied: 34779, admitted: 5632, enrolled: 2394, source: "api" },
  { school: "University of Virginia", cdsYear: "2024-25", applied: 58951, admitted: 9909, enrolled: 3961, source: "api" },
  { school: "William & Mary", cdsYear: "2025-26", applied: 16895, admitted: 6245, enrolled: 1639, source: "api" },
];

const W = 820;
const H = 500;
const M = { l: 64, r: 24, t: 28, b: 56 };
const IW = W - M.l - M.r;
const IH = H - M.t - M.b;
const X_MAX = 40;
const Y_MAX = 100;
const ENROLLED_MAX = 6000;

const xs = (v: number) => M.l + (v / X_MAX) * IW;
const ys = (v: number) => M.t + (1 - v / Y_MAX) * IH;
const rs = (enr: number) => 5 + Math.sqrt(enr / ENROLLED_MAX) * 13;

function shortName(name: string): string {
  return name.replace(/ (University|College)$/, "");
}

export function AcceptanceYieldChart() {
  const [hover, setHover] = useState<number | null>(null);

  const pts = DATA.map((d) => {
    const accept = (d.admitted / d.applied) * 100;
    const yieldPct = (d.enrolled / d.admitted) * 100;
    return {
      ...d,
      accept,
      yieldPct,
      cx: xs(accept),
      cy: ys(yieldPct),
      r: rs(d.enrolled),
      hi: d.source === "ground-truth",
    };
  });

  const tooltip = hover != null ? pts[hover] : null;

  return (
    <div className="cd-card" style={{ padding: 24, position: "relative" }}>
      <div
        style={{
          display: "flex",
          alignItems: "baseline",
          justifyContent: "space-between",
          marginBottom: 12,
          flexWrap: "wrap",
          gap: 8,
        }}
      >
        <div className="meta">Fig. 1 · 2024-25 cycle, 18 schools</div>
        <div className="mono" style={{ fontSize: 11, color: "var(--ink-3)" }}>
          DOT SIZE = ENROLLED CLASS · FOREST = HAND-AUDITED
        </div>
      </div>

      <svg
        width={W}
        height={H}
        viewBox={`0 0 ${W} ${H}`}
        style={{ display: "block", margin: "0 auto", maxWidth: "100%", height: "auto" }}
        role="img"
        aria-label="Scatter plot of acceptance rate against yield for 18 schools"
      >
        {[0, 20, 40, 60, 80, 100].map((v) => (
          <g key={`y${v}`}>
            <line x1={M.l} x2={W - M.r} y1={ys(v)} y2={ys(v)} stroke="var(--chart-grid)" />
            <text
              x={M.l - 10}
              y={ys(v) + 4}
              textAnchor="end"
              fontFamily="var(--mono)"
              fontSize="11"
              fill="var(--chart-axis)"
            >
              {v}%
            </text>
          </g>
        ))}
        {[0, 10, 20, 30, 40].map((v) => (
          <g key={`x${v}`}>
            <line y1={M.t} y2={H - M.b} x1={xs(v)} x2={xs(v)} stroke="var(--chart-grid)" />
            <text
              y={H - M.b + 20}
              x={xs(v)}
              textAnchor="middle"
              fontFamily="var(--mono)"
              fontSize="11"
              fill="var(--chart-axis)"
            >
              {v}%
            </text>
          </g>
        ))}

        <line
          x1={xs(10)}
          x2={xs(10)}
          y1={M.t}
          y2={H - M.b}
          stroke="var(--rule-strong)"
          strokeDasharray="3 3"
        />
        <line
          y1={ys(50)}
          y2={ys(50)}
          x1={M.l}
          x2={W - M.r}
          stroke="var(--rule-strong)"
          strokeDasharray="3 3"
        />

        <text
          x={xs(10) - 10}
          y={M.t + 20}
          textAnchor="end"
          fontFamily="var(--serif)"
          fontStyle="italic"
          fontSize="15"
          fill="var(--forest-ink)"
        >
          selective · desired
        </text>
        <text
          x={xs(10) + 10}
          y={M.t + 20}
          fontFamily="var(--serif)"
          fontStyle="italic"
          fontSize="15"
          fill="var(--ink-3)"
        >
          loved despite openness
        </text>
        <text
          x={xs(10) - 10}
          y={H - M.b - 10}
          textAnchor="end"
          fontFamily="var(--serif)"
          fontStyle="italic"
          fontSize="15"
          fill="var(--ink-3)"
        >
          selective · second-choice
        </text>
        <text
          x={xs(10) + 10}
          y={H - M.b - 10}
          fontFamily="var(--serif)"
          fontStyle="italic"
          fontSize="15"
          fill="var(--ink-3)"
        >
          accessible · optional
        </text>

        <line x1={M.l} x2={M.l} y1={M.t} y2={H - M.b} stroke="var(--ink)" />
        <line x1={M.l} x2={W - M.r} y1={H - M.b} y2={H - M.b} stroke="var(--ink)" />

        {pts.map((p, i) => (
          <g key={p.school}>
            <circle
              cx={p.cx}
              cy={p.cy}
              r={p.r}
              fill={p.hi ? "var(--forest)" : "var(--ink)"}
              opacity={p.hi ? 0.95 : 0.82}
              stroke="var(--paper)"
              strokeWidth="1.5"
              style={{ cursor: "pointer" }}
              onMouseEnter={() => setHover(i)}
              onMouseLeave={() => setHover(null)}
            />
            {p.hi && (
              <text
                x={p.cx + p.r + 6}
                y={p.cy + 4}
                fontFamily="var(--serif)"
                fontStyle="italic"
                fontSize="13"
                fill="var(--forest-ink)"
                pointerEvents="none"
              >
                {shortName(p.school)}
              </text>
            )}
            {!p.hi && p.r > 9 && (
              <text
                x={p.cx + p.r + 5}
                y={p.cy + 3}
                fontFamily="var(--sans)"
                fontSize="11"
                fill="var(--ink-2)"
                pointerEvents="none"
              >
                {shortName(p.school)}
              </text>
            )}
          </g>
        ))}

        <text
          x={M.l + IW / 2}
          y={H - 12}
          textAnchor="middle"
          fontFamily="var(--sans)"
          fontSize="12"
          fill="var(--ink)"
        >
          Acceptance rate →
        </text>
        <text
          x={-H / 2}
          y={18}
          transform="rotate(-90)"
          textAnchor="middle"
          fontFamily="var(--sans)"
          fontSize="12"
          fill="var(--ink)"
        >
          Yield (enrolled ÷ admitted) →
        </text>
      </svg>

      <div
        style={{
          display: "flex",
          gap: 16,
          alignItems: "center",
          marginTop: 12,
          paddingTop: 12,
          borderTop: "1px solid var(--rule)",
          flexWrap: "wrap",
        }}
      >
        <span style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
          <span style={{ width: 9, height: 9, borderRadius: "50%", background: "var(--ink)" }} />
          <span className="mono" style={{ fontSize: 11, color: "var(--ink-2)" }}>
            CDS-VERIFIED SCHOOL
          </span>
        </span>
        <span style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
          <span style={{ width: 9, height: 9, borderRadius: "50%", background: "var(--forest)" }} />
          <span className="mono" style={{ fontSize: 11, color: "var(--forest-ink)" }}>
            HAND-AUDITED SEED
          </span>
        </span>
        <span
          className="mono"
          style={{ fontSize: 11, color: "var(--ink-3)", marginLeft: "auto" }}
        >
          DOT SIZE = ENROLLED FIRST-YEAR CLASS
        </span>
      </div>

      {tooltip && (
        <div
          role="status"
          aria-live="polite"
          className="mono"
          style={{
            position: "absolute",
            left: 24,
            bottom: 70,
            background: "var(--ink)",
            color: "var(--paper)",
            padding: "10px 14px",
            borderRadius: 2,
            fontSize: 12,
            lineHeight: 1.5,
            maxWidth: 320,
            pointerEvents: "none",
          }}
        >
          <div className="serif" style={{ fontSize: 14, color: "var(--paper)" }}>
            {tooltip.school}
          </div>
          <div style={{ color: "var(--ink-4)", marginTop: 2 }}>CDS {tooltip.cdsYear}</div>
          <div style={{ marginTop: 6 }}>
            Acceptance rate: {tooltip.accept.toFixed(2)}%
          </div>
          <div>Yield: {tooltip.yieldPct.toFixed(1)}%</div>
          <div style={{ marginTop: 6, color: "var(--ink-4)" }}>
            Applied {tooltip.applied.toLocaleString("en-US")} · Admitted{" "}
            {tooltip.admitted.toLocaleString("en-US")} · Enrolled{" "}
            {tooltip.enrolled.toLocaleString("en-US")}
          </div>
          <div style={{ marginTop: 6, color: "var(--forest-2)" }}>
            {tooltip.source === "ground-truth"
              ? "GROUND TRUTH · HAND-AUDITED"
              : "LIVE API · C.116/C.117/C.118"}
          </div>
        </div>
      )}
    </div>
  );
}
