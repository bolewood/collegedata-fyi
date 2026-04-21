// School detail — Bethel University, in the archival voice.
// Uses the same token system as home. Key moves:
//  · Serif display for name, mono marginalia with IPEDS id, state, last drain
//  · Documents listed like ledger rows (not cards), stamped with YEAR + FORMAT
//  · "Federal outcomes" banded with a lead rule and a vintage caveat
//  · Net-price bars in ink, highlighted bar in forest

function School() {
  const docs = [
    { year: "2024-25", kind: "XLSX", status: "Extracted", added: "20 Apr 2026" },
    { year: "2022-23", kind: "XLSX", status: "Extracted", added: "04 Jun 2023" },
    { year: "2017-18", kind: "XLSX", status: "Extracted", added: "11 Sep 2018" },
    { year: "2015-16", kind: "XLSX", status: "Extracted", added: "18 Nov 2016" },
  ];
  const priceRows = [
    { band: "$0 – $30,000",      pct: 78, net: "$11,871" },
    { band: "$30,001 – $48,000", pct: 100, net: "$17,356", highlight: true },
    { band: "$48,001 – $75,000", pct: 78, net: "$11,713" },
    { band: "$75,001 – $110,000",pct: 66, net: "$10,473" },
    { band: "$110,001 and up",   pct: 88, net: "$15,163" },
  ];

  return (
    <div className="cd-theme" style={{ width: W, background: "var(--paper)", fontSize: 14 }}>
      <NavRow variant="dotted" active="Schools" />

      {/* Header */}
      <div style={{ padding: "56px 48px 24px", display: "grid", gridTemplateColumns: "1fr 320px", gap: 48, alignItems: "end" }}>
        <div>
          <div className="mono" style={{ fontSize: 11, color: "var(--ink-3)", letterSpacing: "0.08em", marginBottom: 12 }}>
            <a href="#" style={{ color: "var(--ink-3)" }}>SCHOOLS</a> / MN / <span style={{ color: "var(--ink)" }}>BETHEL UNIVERSITY</span>
          </div>
          <h1 style={{
            fontFamily: "var(--serif)", fontWeight: 400, fontSize: 58, margin: 0,
            letterSpacing: "-0.02em", lineHeight: 1,
          }}>Bethel <span style={{ fontStyle: "italic" }}>University</span></h1>
          <div style={{ display: "flex", gap: 22, marginTop: 16, alignItems: "baseline", color: "var(--ink-2)", fontSize: 14 }}>
            <span>St. Paul, Minnesota</span>
            <span className="mono" style={{ fontSize: 11.5, color: "var(--ink-3)" }}>IPEDS 173045</span>
            <span className="mono" style={{ fontSize: 11.5, color: "var(--ink-3)" }}>CARNEGIE M1</span>
            <span className="mono" style={{ fontSize: 11.5, color: "var(--ink-3)" }}>PRIVATE, NON-PROFIT</span>
          </div>
        </div>
        <div style={{ textAlign: "right" }}>
          <div className="meta" style={{ marginBottom: 6 }}>§ 4 documents archived · 2015 – 2024</div>
          <Sparkline data={[1, 1, 1, 2, 2, 2, 3, 3, 4]} w={120} h={26} color="var(--forest)" />
          <div className="mono" style={{ fontSize: 11, color: "var(--ink-3)", marginTop: 4 }}>
            LAST DRAIN · 20 APR 2026 · NO CHANGE
          </div>
        </div>
      </div>

      {/* Documents ledger */}
      <div style={{ padding: "16px 48px 0" }}>
        <div className="rule-2" style={{ paddingTop: 20 }}>
          {docs.map((d, i) => (
            <div key={d.year} style={{
              display: "grid",
              gridTemplateColumns: "96px 70px 110px 1fr auto auto",
              gap: 20, alignItems: "center",
              padding: "16px 0",
              borderBottom: i === docs.length - 1 ? "1px solid var(--rule)" : "1px dashed var(--rule)",
            }}>
              <span className="serif" style={{ fontSize: 24, letterSpacing: "-0.01em" }}>{d.year}</span>
              <span className="cd-chip">{d.kind}</span>
              <span className="cd-chip cd-chip--forest">{d.status}</span>
              <span className="mono" style={{ fontSize: 11, color: "var(--ink-3)", letterSpacing: "0.05em" }}>
                ADDED {d.added.toUpperCase()} · §A–§J · 382 fields
              </span>
              <a href="#" style={{ fontSize: 13 }}>View fields →</a>
              <a href="#" style={{ fontSize: 13 }}>Download PDF</a>
            </div>
          ))}
        </div>
      </div>

      {/* Federal outcomes */}
      <div style={{ padding: "56px 48px 0" }}>
        <div style={{ display: "flex", alignItems: "baseline", justifyContent: "space-between" }}>
          <div>
            <div className="meta" style={{ marginBottom: 6 }}>§ Federal outcomes</div>
            <h2 style={{ fontFamily: "var(--serif)", fontWeight: 400, fontSize: 32, margin: 0, letterSpacing: "-0.015em" }}>
              What federal data says
            </h2>
          </div>
          <div className="mono" style={{ fontSize: 11, color: "var(--ink-3)", letterSpacing: "0.05em", textAlign: "right", maxWidth: 360 }}>
            SRC · U.S. DEPT. OF ED., COLLEGE SCORECARD 2022-23.<br/>
            OUTCOMES LAG THE CDS YEAR SHOWN ABOVE.
          </div>
        </div>

        <div className="rule-2" style={{ marginTop: 20, paddingTop: 24,
          display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 32 }}>
          <Kpi label="Median earnings" value="$47,482" note="10 yrs after enrollment" />
          <Kpi label="Graduation rate" value="35%"     note="6-year completion" />
          <Kpi label="Average net price" value="$12,595" note="sticker minus grants" />
          <Kpi label="Median debt at grad." value="$27,249" note="federal loans only" />
        </div>
      </div>

      {/* Earnings distribution */}
      <div style={{ padding: "48px 48px 0" }}>
        <div className="meta" style={{ marginBottom: 6 }}>§ Earnings distribution</div>
        <h3 style={{ fontFamily: "var(--serif)", fontWeight: 400, fontSize: 22, margin: 0, letterSpacing: "-0.01em" }}>
          Ten years after enrollment, in 2022-23 dollars
        </h3>

        <div style={{ marginTop: 24, position: "relative", height: 120 }}>
          <EarningsAxis p25={30259} p50={47482} p75={68992} />
        </div>
      </div>

      {/* Net price */}
      <div style={{ padding: "48px 48px 0" }}>
        <div style={{ display: "flex", alignItems: "baseline", justifyContent: "space-between" }}>
          <div>
            <div className="meta" style={{ marginBottom: 6 }}>§H · Net price by family income</div>
            <h3 style={{ fontFamily: "var(--serif)", fontWeight: 400, fontSize: 22, margin: 0 }}>
              Average cost after grants
            </h3>
          </div>
          <div className="mono" style={{ fontSize: 11, color: "var(--ink-3)" }}>CDS H2A · 2022-23</div>
        </div>
        <div className="rule-2" style={{ marginTop: 20, paddingTop: 14 }}>
          {priceRows.map((r, i) => (
            <div key={i} style={{
              display: "grid", gridTemplateColumns: "170px 1fr 90px", gap: 20, alignItems: "center",
              padding: "14px 0", borderBottom: i === priceRows.length - 1 ? "none" : "1px dashed var(--rule)",
            }}>
              <span style={{ fontSize: 14, color: "var(--ink-2)" }}>{r.band}</span>
              <div style={{ height: 18, background: "var(--paper-2)", position: "relative" }}>
                <div style={{
                  position: "absolute", inset: 0, right: "auto",
                  width: `${r.pct}%`, background: r.highlight ? "var(--forest)" : "var(--ink)",
                }} />
                {r.highlight && (
                  <span className="mono" style={{
                    position: "absolute", right: -94, top: "50%", transform: "translateY(-50%)",
                    fontSize: 10.5, color: "var(--forest)", letterSpacing: "0.05em",
                  }}>← MODAL BRACKET</span>
                )}
              </div>
              <span className="mono nums" style={{ fontSize: 14, textAlign: "right" }}>{r.net}</span>
            </div>
          ))}
        </div>
      </div>

      {/* Completion & retention */}
      <div style={{ padding: "48px 48px 0" }}>
        <div className="meta" style={{ marginBottom: 6 }}>§B · Completion and retention</div>
        <div className="rule-2" style={{ marginTop: 14, paddingTop: 20,
          display: "grid", gridTemplateColumns: "repeat(6, 1fr)", gap: 24 }}>
          <Kpi small label="4-yr grad"  value="14%" />
          <Kpi small label="6-yr grad"  value="35%" />
          <Kpi small label="8-yr grad"  value="31%" />
          <Kpi small label="Retention"  value="54%" />
          <Kpi small label="Pell grad"  value="14%" />
          <Kpi small label="Transfer"   value="0%"  />
        </div>
      </div>

      <div style={{ height: 72 }}/>
      <Footer />
    </div>
  );
}

function Kpi({ label, value, note, small }) {
  return (
    <div>
      <div className="meta" style={{ marginBottom: small ? 4 : 8 }}>{label}</div>
      <div className="serif stat-num" style={{ fontSize: small ? 26 : 34, lineHeight: 1, letterSpacing: "-0.02em" }}>{value}</div>
      {note && <div className="mono" style={{ fontSize: 11, color: "var(--ink-3)", marginTop: 6 }}>{note}</div>}
    </div>
  );
}

// Earnings as a flat scale — dots for P25/P50/P75, forest line between.
function EarningsAxis({ p25, p50, p75 }) {
  const min = 15000, max = 85000;
  const pct = v => ((v - min) / (max - min)) * 100;
  return (
    <div>
      <div style={{ position: "relative", height: 44 }}>
        <div style={{ position: "absolute", left: 0, right: 0, top: 22, height: 1, background: "var(--rule-strong)" }}/>
        {[p25, p75].map((v, i) => (
          <div key={i} style={{
            position: "absolute", top: 17, left: `${pct(v)}%`, transform: "translateX(-50%)",
            width: 10, height: 10, background: "var(--ink)", borderRadius: "50%",
          }}/>
        ))}
        <div style={{
          position: "absolute", top: 16, left: `${pct(p25)}%`, width: `${pct(p75) - pct(p25)}%`,
          height: 12, background: "var(--forest)", opacity: 0.22, borderRadius: 6,
        }}/>
        <div style={{
          position: "absolute", top: 12, left: `${pct(p50)}%`, transform: "translateX(-50%)",
          width: 18, height: 18, background: "var(--forest)", borderRadius: "50%",
          boxShadow: "0 0 0 3px var(--paper)",
        }}/>
        {[
          { v: p25, label: "P25" },
          { v: p50, label: "Median" },
          { v: p75, label: "P75" },
        ].map(t => (
          <div key={t.label} style={{
            position: "absolute", top: 44, left: `${pct(t.v)}%`, transform: "translateX(-50%)",
            textAlign: "center",
          }}>
            <div className="mono" style={{ fontSize: 10, color: "var(--ink-3)", letterSpacing: "0.06em" }}>{t.label.toUpperCase()}</div>
            <div className="serif" style={{ fontSize: 20, marginTop: 2 }}>${t.v.toLocaleString()}</div>
          </div>
        ))}
      </div>
      <div style={{ position: "relative", marginTop: 60, height: 16 }}>
        {[20000, 40000, 60000, 80000].map(v => (
          <div key={v} className="mono" style={{
            position: "absolute", left: `${pct(v)}%`, transform: "translateX(-50%)",
            fontSize: 10, color: "var(--ink-4)", letterSpacing: "0.04em",
          }}>${(v / 1000)}k</div>
        ))}
      </div>
    </div>
  );
}

window.School = School;
