// Acceptance vs yield — scatter in the unified chart palette.
// Primary series: ink black dots. Highlighted callouts: forest green,
// larger, labeled. Axis in mono, quadrants separated by dashed rules
// with editorial labels set in italic serif. Matches token palette.

function Recipe() {
  // x = acceptance %, y = yield %, r = class size bucket
  const pts = [
    { n: "Harvard",                        x: 3.2, y: 83, r: 22, hi: true },
    { n: "Stanford",                       x: 3.9, y: 82, r: 22 },
    { n: "Princeton",                      x: 4.5, y: 75, r: 19 },
    { n: "Dartmouth",                      x: 5.3, y: 69, r: 14, hi: true },
    { n: "Brown",                          x: 5.5, y: 66, r: 18 },
    { n: "Columbia",                       x: 3.9, y: 64, r: 18 },
    { n: "Notre Dame",                     x: 8.9, y: 64, r: 21 },
    { n: "Duke",                           x: 6.3, y: 59, r: 18 },
    { n: "Northeastern",                   x: 6.7, y: 54, r: 28 },
    { n: "NYU",                            x: 8.0, y: 56, r: 30 },
    { n: "Johns Hopkins",                  x: 7.3, y: 48, r: 19 },
    { n: "Wash U in St. Louis",            x: 10.7, y: 46, r: 20 },
    { n: "Rice",                           x: 8.0, y: 45, r: 16 },
    { n: "USC",                            x: 10.1, y: 44, r: 24 },
    { n: "UVA",                            x: 16.3, y: 41, r: 25 },
    { n: "Harvey Mudd",                    x: 12.3, y: 37, r: 8,  hi: true },
    { n: "UC Berkeley",                    x: 11.6, y: 44, r: 28 },
    { n: "William & Mary",                 x: 37.0, y: 26, r: 18 },
  ];

  const M = { l: 72, r: 24, t: 28, b: 56 };
  const W_ = 820, H_ = 500;
  const iw = W_ - M.l - M.r, ih = H_ - M.t - M.b;
  const xMin = 0, xMax = 40, yMin = 0, yMax = 100;
  const xs = v => M.l + ((v - xMin) / (xMax - xMin)) * iw;
  const ys = v => M.t + (1 - (v - yMin) / (yMax - yMin)) * ih;
  const rs = v => 5 + (v / 30) * 10;

  return (
    <div className="cd-theme" style={{ width: W, background: "var(--paper)", fontSize: 14 }}>
      <NavRow variant="dotted" active="Recipes" />

      <div style={{ padding: "48px 48px 0", display: "grid", gridTemplateColumns: "1fr auto", alignItems: "end" }}>
        <div>
          <div className="mono" style={{ fontSize: 11, color: "var(--ink-3)", letterSpacing: "0.08em" }}>
            <a href="#" style={{ color: "var(--ink-3)" }}>RECIPES</a> / <span style={{ color: "var(--ink)" }}>ACCEPTANCE × YIELD</span>
          </div>
          <h1 style={{
            fontFamily: "var(--serif)", fontWeight: 400, fontSize: 52,
            margin: "12px 0 0", letterSpacing: "-0.02em", lineHeight: 1,
          }}>
            Acceptance rate <span style={{ fontStyle: "italic" }}>vs.</span> yield
          </h1>
          <p style={{ maxWidth: 640, marginTop: 12, color: "var(--ink-2)", fontSize: 16, lineHeight: 1.55 }}>
            Two numbers, eighteen schools worth of context. A <span style={{ fontFamily: "var(--serif)", fontStyle: "italic" }}>collegedata.fyi</span> recipe.
          </p>
        </div>
        <div style={{ display: "flex", gap: 8 }}>
          <span className="cd-chip">CDS C1</span>
          <span className="cd-chip">B1</span>
          <span className="cd-chip">B22</span>
        </div>
      </div>

      {/* Chart */}
      <div style={{ padding: "28px 48px 0" }}>
        <div className="cd-card" style={{ padding: 24 }}>
          <div style={{ display: "flex", alignItems: "baseline", justifyContent: "space-between", marginBottom: 12 }}>
            <div className="meta">Fig. 1 · 2024-25 cycle, 18 schools</div>
            <div className="mono" style={{ fontSize: 11, color: "var(--ink-3)" }}>DOT SIZE = ENROLLED CLASS · FOREST = CALLOUT</div>
          </div>
          <svg width={W_} height={H_} viewBox={`0 0 ${W_} ${H_}`} style={{ display: "block", margin: "0 auto", maxWidth: "100%" }}>
            {/* grid */}
            {[0,20,40,60,80,100].map(v => (
              <g key={v}>
                <line x1={M.l} x2={W_-M.r} y1={ys(v)} y2={ys(v)} stroke="var(--chart-grid)" />
                <text x={M.l - 10} y={ys(v)+4} textAnchor="end" fontFamily="var(--mono)" fontSize="11" fill="var(--chart-axis)">{v}%</text>
              </g>
            ))}
            {[0,10,20,30,40].map(v => (
              <g key={v}>
                <line y1={M.t} y2={H_-M.b} x1={xs(v)} x2={xs(v)} stroke="var(--chart-grid)" />
                <text y={H_-M.b + 20} x={xs(v)} textAnchor="middle" fontFamily="var(--mono)" fontSize="11" fill="var(--chart-axis)">{v}%</text>
              </g>
            ))}
            {/* quadrant dividers */}
            <line x1={xs(10)} x2={xs(10)} y1={M.t} y2={H_-M.b} stroke="var(--rule-strong)" strokeDasharray="3 3"/>
            <line y1={ys(50)} y2={ys(50)} x1={M.l} x2={W_-M.r} stroke="var(--rule-strong)" strokeDasharray="3 3"/>
            {/* quadrant labels (italic serif) */}
            <text x={xs(10) - 10} y={M.t + 20} textAnchor="end" fontFamily="var(--serif)" fontStyle="italic" fontSize="15" fill="var(--forest-ink)">selective · desired</text>
            <text x={xs(10) + 10} y={M.t + 20} fontFamily="var(--serif)" fontStyle="italic" fontSize="15" fill="var(--ink-3)">loved despite openness</text>
            <text x={xs(10) - 10} y={H_-M.b - 10} textAnchor="end" fontFamily="var(--serif)" fontStyle="italic" fontSize="15" fill="var(--ink-3)">selective · second-choice</text>
            <text x={xs(10) + 10} y={H_-M.b - 10} fontFamily="var(--serif)" fontStyle="italic" fontSize="15" fill="var(--ink-3)">accessible · optional</text>

            {/* axes */}
            <line x1={M.l} x2={M.l} y1={M.t} y2={H_-M.b} stroke="var(--ink)"/>
            <line x1={M.l} x2={W_-M.r} y1={H_-M.b} y2={H_-M.b} stroke="var(--ink)"/>

            {/* dots */}
            {pts.map((p, i) => (
              <g key={i}>
                <circle cx={xs(p.x)} cy={ys(p.y)} r={rs(p.r)}
                        fill={p.hi ? "var(--forest)" : "var(--ink)"}
                        opacity={p.hi ? 0.95 : 0.82}
                        stroke="var(--paper)" strokeWidth="1.5"/>
                {p.hi && (
                  <g>
                    <text x={xs(p.x) + rs(p.r) + 6} y={ys(p.y) + 4}
                          fontFamily="var(--serif)" fontStyle="italic" fontSize="13" fill="var(--forest-ink)">
                      {p.n}
                    </text>
                  </g>
                )}
                {!p.hi && rs(p.r) > 9 && (
                  <text x={xs(p.x) + rs(p.r) + 5} y={ys(p.y) + 3}
                        fontFamily="var(--sans)" fontSize="11" fill="var(--ink-2)">{p.n}</text>
                )}
              </g>
            ))}

            {/* axis titles */}
            <text x={M.l + iw/2} y={H_ - 12} textAnchor="middle" fontFamily="var(--sans)" fontSize="12" fill="var(--ink)">Acceptance rate →</text>
            <text x={-H_/2} y={18} transform={`rotate(-90)`} textAnchor="middle" fontFamily="var(--sans)" fontSize="12" fill="var(--ink)">Yield (enrolled ÷ admitted) →</text>
          </svg>

          <div style={{ display: "flex", gap: 16, alignItems: "center", marginTop: 12, paddingTop: 12, borderTop: "1px solid var(--rule)" }}>
            <span style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
              <span style={{ width: 9, height: 9, borderRadius: "50%", background: "var(--ink)" }}/>
              <span className="mono" style={{ fontSize: 11, color: "var(--ink-2)" }}>CDS-VERIFIED SCHOOL</span>
            </span>
            <span style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
              <span style={{ width: 9, height: 9, borderRadius: "50%", background: "var(--forest)" }}/>
              <span className="mono" style={{ fontSize: 11, color: "var(--forest-ink)" }}>HAND-AUDITED SEED</span>
            </span>
            <span className="mono" style={{ fontSize: 11, color: "var(--ink-3)", marginLeft: "auto" }}>
              DOT SIZE = ENROLLED FIRST-YEAR CLASS
            </span>
          </div>
        </div>
      </div>

      {/* Reader's guide */}
      <div style={{ padding: "48px 48px 0", display: "grid", gridTemplateColumns: "200px 1fr", gap: 40 }}>
        <div>
          <div className="meta" style={{ marginBottom: 6 }}>§ How to read</div>
          <div style={{ fontFamily: "var(--serif)", fontSize: 20, fontStyle: "italic", color: "var(--ink-2)" }}>
            &ldquo;Four quadrants, each<br/>with teeth.&rdquo;
          </div>
        </div>
        <p style={{ fontSize: 16, lineHeight: 1.65, color: "var(--ink-2)", maxWidth: 720, margin: 0 }}>
          The x-axis is how selective a school <span style={{ fontStyle: "italic", fontFamily: "var(--serif)" }}>looks</span> on paper —
          its acceptance rate. The y-axis is how selective it actually{" "}
          <span style={{ fontStyle: "italic", fontFamily: "var(--serif)" }}>is</span> in practice — its yield, the share
          of admitted students who actually enroll. Low acceptance + high yield is the top-left quadrant:
          schools that turn most applicants away and still capture most of the students they admit.
          Low acceptance + low yield is the bottom-left: schools that look selective but lose most of their
          admits to competitors.
        </p>
      </div>

      <div style={{ padding: "48px 48px 0", display: "grid", gridTemplateColumns: "repeat(2, 1fr)", gap: 24 }}>
        {[
          { num: "I", head: "Selective and desired", body: "Low acceptance, high yield. Both hard to get into and hard to turn down." },
          { num: "II", head: "Loved despite openness", body: "Higher acceptance but strong yield. Often regional flagships or niche-fit schools." },
          { num: "III", head: "Selective but second-choice", body: "Hard to get into, but most admits choose somewhere else. Cross-admit peers of top-left." },
          { num: "IV", head: "Accessible and optional", body: "Admits freely, captures a smaller share. Common among safety-school territory." },
        ].map(q => (
          <div key={q.num} className="cd-card" style={{ padding: 20, display: "flex", gap: 16 }}>
            <div className="serif" style={{ fontSize: 38, lineHeight: 0.9, color: "var(--forest)", fontStyle: "italic" }}>{q.num}.</div>
            <div>
              <div className="meta" style={{ marginBottom: 4, color: "var(--ink-3)" }}>QUADRANT {q.num}</div>
              <div style={{ fontFamily: "var(--serif)", fontSize: 20, letterSpacing: "-0.005em" }}>{q.head}</div>
              <div style={{ fontSize: 14, color: "var(--ink-2)", lineHeight: 1.55, marginTop: 6 }}>{q.body}</div>
            </div>
          </div>
        ))}
      </div>

      {/* Query block */}
      <div style={{ padding: "48px 48px 0" }}>
        <div className="meta" style={{ marginBottom: 10 }}>§ Scale to all 697 schools</div>
        <pre style={{
          background: "var(--ink)", color: "var(--paper)", padding: "20px 24px",
          fontFamily: "var(--mono)", fontSize: 13, lineHeight: 1.55, margin: 0,
          borderRadius: 2, overflow: "hidden",
        }}>
{`curl https://collegedata.fyi/api/facts \\
  ?fields=C.116,C.117,C.118        `}<span style={{ color: "#c9c2ae" }}>{`# accept · admit · enroll`}</span>{`
  &year=latest                     `}<span style={{ color: "#c9c2ae" }}>{`# most-recent CDS per school`}</span>{`
  &verified=true                   `}<span style={{ color: "#c9c2ae" }}>{`# skip PDFs awaiting review`}</span>
        </pre>
      </div>

      <div style={{ height: 72 }}/>
      <Footer />
    </div>
  );
}

window.Recipe = Recipe;
