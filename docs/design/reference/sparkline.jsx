// Tiny inline sparkline. Designed to sit baseline-aligned next to numbers.
// Props: data [n], w, h, color, showDot (last point dot)
function Sparkline({ data = [], w = 48, h = 14, color = "var(--forest)", dot = true, area = true }) {
  if (!data.length) return null;
  const min = Math.min(...data), max = Math.max(...data);
  const pad = 1.5;
  const nx = (i) => pad + (i / (data.length - 1)) * (w - pad * 2);
  const ny = (v) => {
    if (max === min) return h / 2;
    return pad + (1 - (v - min) / (max - min)) * (h - pad * 2);
  };
  const pts = data.map((v, i) => `${nx(i).toFixed(2)},${ny(v).toFixed(2)}`);
  const d = "M" + pts.join(" L ");
  const areaD = `${d} L ${nx(data.length - 1).toFixed(2)},${h} L ${nx(0).toFixed(2)},${h} Z`;
  const lx = nx(data.length - 1), ly = ny(data[data.length - 1]);
  return (
    <svg width={w} height={h} viewBox={`0 0 ${w} ${h}`} style={{ verticalAlign: "baseline", display: "inline-block", marginLeft: 6 }} aria-hidden="true">
      {area && <path d={areaD} fill={color} opacity="0.12" />}
      <path d={d} stroke={color} strokeWidth="1.25" fill="none" strokeLinecap="round" strokeLinejoin="round" />
      {dot && <circle cx={lx} cy={ly} r="1.6" fill={color} />}
    </svg>
  );
}

window.Sparkline = Sparkline;
