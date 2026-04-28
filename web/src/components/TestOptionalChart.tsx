"use client";

import { useMemo, useState } from "react";

type Point = { year: string; sat: number; act: number | null };
type Series = {
  id: string;
  name: string;
  color: string;
  data: Point[];
};

const SCHOOLS: Series[] = [
  {
    id: "yale",
    name: "Yale University",
    color: "var(--ink)",
    data: [
      { year: "2009-10", sat: 91.0, act: null },
      { year: "2010-11", sat: 89.0, act: null },
      { year: "2011-12", sat: 85.0, act: null },
      { year: "2012-13", sat: 84.0, act: null },
      { year: "2013-14", sat: 81.0, act: null },
      { year: "2014-15", sat: 79.0, act: null },
      { year: "2015-16", sat: 74.0, act: null },
      { year: "2016-17", sat: 69.0, act: null },
      { year: "2017-18", sat: 61.0, act: null },
      { year: "2018-19", sat: 68.0, act: null },
      { year: "2019-20", sat: 68.0, act: null },
      { year: "2020-21", sat: 70.0, act: 46.0 },
      { year: "2021-22", sat: 54.0, act: 35.0 },
      { year: "2022-23", sat: 59.0, act: null },
      { year: "2023-24", sat: 56.0, act: 26.0 },
      { year: "2024-25", sat: 61.0, act: 25.0 },
    ],
  },
  {
    id: "caltech",
    name: "Caltech",
    color: "var(--brick)",
    data: [
      { year: "2002-03", sat: 100.0, act: null },
      { year: "2003-04", sat: 100.0, act: null },
      { year: "2004-05", sat: 100.0, act: null },
      { year: "2005-06", sat: 99.0, act: null },
      { year: "2006-07", sat: 99.0, act: null },
      { year: "2007-08", sat: 99.0, act: null },
      { year: "2008-09", sat: 97.0, act: null },
      { year: "2009-10", sat: 97.0, act: null },
      { year: "2011-12", sat: 91.0, act: null },
      { year: "2012-13", sat: 90.0, act: null },
      { year: "2013-14", sat: 88.0, act: null },
      { year: "2014-15", sat: 88.0, act: null },
      { year: "2015-16", sat: 78.0, act: null },
      { year: "2016-17", sat: 81.0, act: null },
      { year: "2017-18", sat: 65.0, act: null },
      { year: "2018-19", sat: 68.0, act: null },
      { year: "2019-20", sat: 79.0, act: null },
      { year: "2020-21", sat: 45.0, act: null },
    ],
  },
  {
    id: "mit",
    name: "MIT",
    color: "var(--forest)",
    data: [
      { year: "2021-22", sat: 70.0, act: 34.0 },
      { year: "2022-23", sat: 78.0, act: 32.0 },
      { year: "2023-24", sat: 83.0, act: 31.0 },
      { year: "2024-25", sat: 83.0, act: 29.0 },
    ],
  },
  {
    id: "princeton",
    name: "Princeton University",
    color: "var(--ochre)",
    data: [
      { year: "2018-19", sat: 68.0, act: null },
      { year: "2019-20", sat: 71.0, act: null },
      { year: "2020-21", sat: 71.0, act: null },
      { year: "2021-22", sat: 56.0, act: 35.0 },
      { year: "2022-23", sat: 60.0, act: null },
      { year: "2023-24", sat: 57.0, act: null },
      { year: "2024-25", sat: 56.0, act: null },
    ],
  },
  {
    id: "stanford",
    name: "Stanford University",
    color: "var(--forest-2)",
    data: [
      { year: "2020-21", sat: 71.9, act: null },
      { year: "2021-22", sat: 48.0, act: 31.0 },
      { year: "2023-24", sat: 47.0, act: 22.0 },
    ],
  },
  {
    id: "harvard",
    name: "Harvard University",
    color: "var(--ink-2)",
    data: [
      { year: "2020-21", sat: 72.0, act: null },
      { year: "2023-24", sat: 52.0, act: null },
      { year: "2024-25", sat: 54.0, act: null },
    ],
  },
  {
    id: "wake-forest",
    name: "Wake Forest",
    color: "var(--forest-ink)",
    data: [
      { year: "2007-08", sat: 80.0, act: null },
      { year: "2014-15", sat: 45.0, act: null },
      { year: "2015-16", sat: 53.0, act: null },
      { year: "2016-17", sat: 43.0, act: null },
      { year: "2017-18", sat: 38.0, act: null },
      { year: "2018-19", sat: 41.0, act: null },
      { year: "2019-20", sat: 44.0, act: null },
      { year: "2020-21", sat: 50.0, act: 45.0 },
      { year: "2021-22", sat: 23.0, act: null },
      { year: "2023-24", sat: 26.0, act: null },
      { year: "2024-25", sat: 22.2, act: 25.7 },
    ],
  },
];

function leadingYear(s: string): number {
  return parseInt(s.split("-")[0], 10);
}

const W = 980;
const H = 520;
const M = { l: 60, r: 24, t: 28, b: 56 };
const IW = W - M.l - M.r;
const IH = H - M.t - M.b;
const X_MIN = 2002;
const X_MAX = 2024;

const xs = (year: number) =>
  M.l + ((year - X_MIN) / (X_MAX - X_MIN)) * IW;
const ys = (pct: number) => M.t + (1 - pct / 100) * IH;

export function TestOptionalChart() {
  const [hidden, setHidden] = useState<Set<string>>(new Set());
  const [hover, setHover] = useState<{ id: string; idx: number } | null>(null);

  const visible = useMemo(
    () => SCHOOLS.filter((s) => !hidden.has(s.id)),
    [hidden],
  );

  function toggle(id: string) {
    setHidden((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  const xTicks = [2005, 2010, 2015, 2020, 2024];
  const yTicks = [0, 20, 40, 60, 80, 100];

  const hoverPoint =
    hover != null
      ? SCHOOLS.find((s) => s.id === hover.id)?.data[hover.idx]
      : null;
  const hoverSchool =
    hover != null ? SCHOOLS.find((s) => s.id === hover.id) : null;

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
        <div className="meta">Fig. 1 · % submitting SAT, by year</div>
        <div className="mono" style={{ fontSize: 11, color: "var(--ink-3)" }}>
          CDS C.901 · 2002-2024 · 7 SCHOOLS
        </div>
      </div>

      <svg
        width={W}
        height={H}
        viewBox={`0 0 ${W} ${H}`}
        style={{ display: "block", margin: "0 auto", maxWidth: "100%", height: "auto" }}
        role="img"
        aria-label="Line chart of SAT submission rate over time for seven schools"
      >
        {/* Threshold bands — paint behind grid */}
        <rect
          x={M.l}
          y={ys(100)}
          width={IW}
          height={ys(85) - ys(100)}
          fill="var(--brick)"
          opacity="0.06"
        />
        <rect
          x={M.l}
          y={ys(10)}
          width={IW}
          height={ys(0) - ys(10)}
          fill="var(--forest)"
          opacity="0.06"
        />

        {/* Grid */}
        {yTicks.map((v) => (
          <g key={`y${v}`}>
            <line
              x1={M.l}
              x2={W - M.r}
              y1={ys(v)}
              y2={ys(v)}
              stroke="var(--chart-grid)"
            />
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
        {xTicks.map((y) => (
          <g key={`x${y}`}>
            <line
              x1={xs(y)}
              x2={xs(y)}
              y1={M.t}
              y2={H - M.b}
              stroke="var(--chart-grid)"
            />
            <text
              x={xs(y)}
              y={H - M.b + 20}
              textAnchor="middle"
              fontFamily="var(--mono)"
              fontSize="11"
              fill="var(--chart-axis)"
            >
              {y}
            </text>
          </g>
        ))}

        {/* Threshold lines + labels */}
        <line
          x1={M.l}
          x2={W - M.r}
          y1={ys(85)}
          y2={ys(85)}
          stroke="var(--brick)"
          strokeDasharray="4 3"
          opacity="0.6"
        />
        <text
          x={W - M.r - 4}
          y={ys(85) - 4}
          textAnchor="end"
          fontFamily="var(--mono)"
          fontSize="10"
          fill="var(--brick)"
          letterSpacing="0.05em"
        >
          85% · TEST-REQUIRED
        </text>
        <line
          x1={M.l}
          x2={W - M.r}
          y1={ys(10)}
          y2={ys(10)}
          stroke="var(--forest)"
          strokeDasharray="4 3"
          opacity="0.6"
        />
        <text
          x={W - M.r - 4}
          y={ys(10) - 4}
          textAnchor="end"
          fontFamily="var(--mono)"
          fontSize="10"
          fill="var(--forest)"
          letterSpacing="0.05em"
        >
          10% · TEST-BLIND
        </text>

        {/* Axes */}
        <line x1={M.l} x2={M.l} y1={M.t} y2={H - M.b} stroke="var(--ink)" />
        <line
          x1={M.l}
          x2={W - M.r}
          y1={H - M.b}
          y2={H - M.b}
          stroke="var(--ink)"
        />

        {/* Series lines + dots */}
        {visible.map((s) => {
          const path = s.data
            .map((p, i) => {
              const x = xs(leadingYear(p.year));
              const y = ys(p.sat);
              return `${i === 0 ? "M" : "L"}${x.toFixed(2)},${y.toFixed(2)}`;
            })
            .join(" ");
          return (
            <g key={s.id}>
              <path
                d={path}
                fill="none"
                stroke={s.color}
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
              />
              {s.data.map((p, i) => {
                const cx = xs(leadingYear(p.year));
                const cy = ys(p.sat);
                return (
                  <circle
                    key={i}
                    cx={cx}
                    cy={cy}
                    r={4}
                    fill={s.color}
                    stroke="var(--paper)"
                    strokeWidth="1.5"
                    style={{ cursor: "pointer" }}
                    onMouseEnter={() => setHover({ id: s.id, idx: i })}
                    onMouseLeave={() => setHover(null)}
                  />
                );
              })}
            </g>
          );
        })}

        {/* Axis titles */}
        <text
          x={M.l + IW / 2}
          y={H - 12}
          textAnchor="middle"
          fontFamily="var(--sans)"
          fontSize="12"
          fill="var(--ink)"
        >
          CDS year →
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
          % submitting SAT →
        </text>
      </svg>

      {/* Legend */}
      <div
        style={{
          marginTop: 14,
          paddingTop: 14,
          borderTop: "1px solid var(--rule)",
          display: "flex",
          flexWrap: "wrap",
          gap: 16,
        }}
      >
        {SCHOOLS.map((s) => {
          const off = hidden.has(s.id);
          return (
            <button
              key={s.id}
              type="button"
              onClick={() => toggle(s.id)}
              aria-pressed={!off}
              style={{
                display: "inline-flex",
                alignItems: "center",
                gap: 8,
                padding: "4px 8px",
                background: "transparent",
                border: "1px solid transparent",
                borderRadius: 2,
                cursor: "pointer",
                color: off ? "var(--ink-4)" : "var(--ink-2)",
                opacity: off ? 0.5 : 1,
                fontFamily: "var(--sans)",
                fontSize: 12,
              }}
            >
              <span
                style={{
                  width: 18,
                  height: 3,
                  background: s.color,
                  display: "inline-block",
                  borderRadius: 1.5,
                  opacity: off ? 0.4 : 1,
                }}
              />
              {s.name}
            </button>
          );
        })}
        <span
          className="mono"
          style={{
            fontSize: 11,
            color: "var(--ink-3)",
            marginLeft: "auto",
            alignSelf: "center",
          }}
        >
          CLICK TO TOGGLE
        </span>
      </div>

      {hoverPoint && hoverSchool && (
        <div
          role="status"
          aria-live="polite"
          className="mono"
          style={{
            position: "absolute",
            left: 24,
            top: 60,
            background: "var(--ink)",
            color: "var(--paper)",
            padding: "10px 14px",
            borderRadius: 2,
            fontSize: 12,
            lineHeight: 1.5,
            maxWidth: 260,
            pointerEvents: "none",
          }}
        >
          <div className="serif" style={{ fontSize: 14, color: "var(--paper)" }}>
            {hoverSchool.name}
          </div>
          <div style={{ color: "var(--ink-4)", marginTop: 2 }}>
            CDS {hoverPoint.year}
          </div>
          <div style={{ marginTop: 6 }}>
            SAT submitted: {hoverPoint.sat.toFixed(1)}%
          </div>
          {hoverPoint.act != null && (
            <div>ACT submitted: {hoverPoint.act.toFixed(1)}%</div>
          )}
        </div>
      )}
    </div>
  );
}
