import { formatCount, formatDay, type DayPoint, type Spike } from "@/lib/usage";

function niceStep(max: number): number {
  const target = max / 5;
  const magnitude = 10 ** Math.floor(Math.log10(Math.max(target, 1)));
  for (const multiple of [1, 2, 2.5, 5, 10]) {
    if (multiple * magnitude >= target) return multiple * magnitude;
  }
  return 10 * magnitude;
}

export function DownloadsChart({
  averages,
  spikes,
  markers,
}: {
  averages: DayPoint[];
  spikes: Spike[];
  markers: { day: string; label: string }[];
}) {
  const W = 960;
  const H = 300;
  const L = 48;
  const R = 68;
  const T = 14;
  const B = 30;
  const peak = Math.max(1, ...averages.flatMap((p) => [p.browser, p.machine, p.bots]));
  const step = niceStep(peak);
  const max = Math.ceil(peak / step) * step;
  const last = averages.length - 1;
  const x = (i: number) => L + (last > 0 ? i / last : 0.5) * (W - L - R);
  const y = (v: number) => T + (1 - v / max) * (H - T - B);
  const path = (key: "browser" | "machine" | "bots") =>
    averages.map((p, i) => `${i ? "L" : "M"}${x(i).toFixed(1)},${y(p[key]).toFixed(1)}`).join("");
  const ticks: number[] = [];
  for (let v = 0; v <= max; v += step) ticks.push(v);
  const index = new Map(averages.map((p, i) => [p.day, i]));
  const ends = [
    { label: "Browser", value: averages[last]?.browser ?? 0, color: "var(--browser)" },
    { label: "Machine", value: averages[last]?.machine ?? 0, color: "var(--ink)" },
    { label: "Bots", value: averages[last]?.bots ?? 0, color: "var(--ink-3)" },
  ].sort((a, b) => b.value - a.value);
  // Keep end labels at least 13px apart.
  const endY: number[] = [];
  for (const end of ends) {
    const want = y(end.value) + 4;
    endY.push(endY.length ? Math.max(want, endY[endY.length - 1] + 13) : want);
  }

  return (
    <svg
      viewBox={`0 0 ${W} ${H}`}
      role="img"
      aria-label="Unique downloads per day, 7-day average, for browser, machine, and bots and crawlers. The table below has the numbers by week."
    >
      {ticks.map((v) => (
        <g key={`tick-${v}`}>
          <line x1={L} x2={W - R} y1={y(v)} y2={y(v)} stroke="var(--chart-grid)" />
          <text x={L - 8} y={y(v) + 3.5} textAnchor="end">
            {formatCount(v)}
          </text>
        </g>
      ))}
      {averages.map((p, i) =>
        p.day.endsWith("-01") ? (
          <g key={`month-${p.day}`}>
            <line x1={x(i)} x2={x(i)} y1={T} y2={H - B} stroke="var(--chart-grid)" />
            <text
              x={x(i) > W - R - 40 ? x(i) - 4 : x(i) + 4}
              y={H - B + 18}
              textAnchor={x(i) > W - R - 40 ? "end" : "start"}
            >
              {formatDay(p.day)}
            </text>
          </g>
        ) : null,
      )}
      {averages.length && !averages[0].day.endsWith("-01") ? (
        <text x={L} y={H - B + 18}>
          {formatDay(averages[0].day)}
        </text>
      ) : null}
      {markers.map((m) =>
        index.has(m.day) ? (
          <g key={`marker-${m.day}`}>
            <line
              x1={x(index.get(m.day)!)}
              x2={x(index.get(m.day)!)}
              y1={T}
              y2={H - B}
              stroke="var(--ink-2)"
              strokeDasharray="2 3"
            />
            <text x={x(index.get(m.day)!) + 4} y={T + 10}>
              {m.label}
            </text>
          </g>
        ) : null,
      )}
      {averages.length ? (
        <path d={`${path("browser")}L${x(last)},${y(0)}L${x(0)},${y(0)}Z`} fill="var(--browser-fill)" />
      ) : null}
      <path d={path("bots")} fill="none" stroke="var(--ink-4)" strokeWidth={1.5} strokeDasharray="4 3" />
      <path d={path("machine")} fill="none" stroke="var(--ink)" strokeWidth={1.25} />
      <path d={path("browser")} fill="none" stroke="var(--browser)" strokeWidth={3} strokeLinejoin="round" />
      {spikes.map((s) =>
        index.has(s.day) ? (
          <g key={`spike-${s.day}`}>
            <path
              d={`M${x(index.get(s.day)!)},${T + 2}l-4,-6h8z`}
              transform={`translate(0, 6)`}
              fill="var(--ink)"
            />
            <title>{`${formatDay(s.day)}: ${formatCount(s.machine)} machine downloads`}</title>
          </g>
        ) : null,
      )}
      <line x1={L} x2={W - R} y1={y(0)} y2={y(0)} stroke="var(--chart-axis)" />
      {ends.map((end, i) => (
        <text
          key={end.label}
          x={x(last) + 6}
          y={endY[i]}
          className="usage-end-label"
          style={{ fill: end.color }}
        >
          {end.label}
        </text>
      ))}
    </svg>
  );
}

export function ApiBars({
  daily,
  highlight,
}: {
  daily: { day: string; value: number }[];
  highlight: { start: string; end: string };
}) {
  const W = 640;
  const H = 90;
  const max = Math.max(1, ...daily.map((d) => d.value));
  const bw = W / Math.max(1, daily.length);
  return (
    <svg
      viewBox={`0 0 ${W} ${H}`}
      role="img"
      aria-label="API requests by others per day. Darker bars are the headline period. The weekly table above has the numbers."
    >
      {daily.map((d, i) => {
        const h = Math.max(1, (d.value / max) * (H - 16));
        const inPeriod = d.day >= highlight.start && d.day <= highlight.end;
        return (
          <rect
            key={d.day}
            x={(i * bw).toFixed(1)}
            y={(H - 14 - h).toFixed(1)}
            width={Math.max(0.5, bw - 1.5).toFixed(1)}
            height={h.toFixed(1)}
            fill={inPeriod ? "var(--ink)" : "var(--chart-faint)"}
          >
            <title>{`${formatDay(d.day)}: ${formatCount(d.value)}`}</title>
          </rect>
        );
      })}
      {daily.length ? (
        <>
          <text x={0} y={H - 1}>
            {formatDay(daily[0].day)}
          </text>
          <text x={W} y={H - 1} textAnchor="end">
            {formatDay(daily[daily.length - 1].day)}
          </text>
        </>
      ) : null}
    </svg>
  );
}
