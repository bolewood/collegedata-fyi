// Home v2 — "Catalog drawer"
// Hero is split: headline+search on the left; a live catalog column on
// the right showing recently-added CDS documents. Wordmark uses the
// catalog-card corner glyph. Feels like walking into a library.

function HomeV2() {
  const recent = [
    { school: "Bethel University",        year: "2024-25", section: "§A–§J", state: "MN", kind: "XLSX" },
    { school: "Harvey Mudd College",      year: "2024-25", section: "§A–§J", state: "CA", kind: "PDF" },
    { school: "University of Notre Dame", year: "2025-26", section: "§A–§J", state: "IN", kind: "PDF" },
    { school: "William & Mary",           year: "2024-25", section: "§A–§J", state: "VA", kind: "PDF" },
    { school: "Johns Hopkins University", year: "2019-20", section: "§A–§J", state: "MD", kind: "PDF" },
    { school: "Stanford University",      year: "2024-25", section: "§A–§J", state: "CA", kind: "PDF" },
    { school: "Wake Forest University",   year: "2024-25", section: "§C",    state: "NC", kind: "PDF" },
    { school: "Rice University",          year: "2024-25", section: "§A–§J", state: "TX", kind: "PDF" },
  ];

  return (
    <div className="cd-theme" style={{ width: W, background: "var(--paper)", fontSize: 14 }}>
      <NavRow variant="dotted" />

      <div style={{ display: "grid", gridTemplateColumns: "1.1fr 1fr", gap: 64, padding: "80px 48px 48px" }}>
        {/* Left: headline */}
        <div>
          <div className="meta" style={{ marginBottom: 28 }}>
            <span style={{ color: "var(--ink-2)" }}>VOL. III</span> · SPRING DRAIN · APRIL 2026
          </div>
          <h1 style={{
            fontFamily: "var(--serif)", fontWeight: 400, fontSize: 76, lineHeight: 0.96,
            margin: 0, letterSpacing: "-0.025em",
          }}>
            Every college&rsquo;s<br />
            <span style={{ fontStyle: "italic" }}>receipts</span>, kept<br />
            on the record.
          </h1>
          <p style={{ marginTop: 28, fontSize: 17, lineHeight: 1.55, color: "var(--ink-2)", maxWidth: 460 }}>
            <span className="serif" style={{ fontSize: 28, float: "left", lineHeight: 0.85, paddingRight: 8, paddingTop: 6, fontStyle: "italic" }}>W</span>
            e archive each U.S. school&rsquo;s Common Data Set the moment it&rsquo;s
            published, extract every field, and publish the structured numbers
            back as an open API. No dashboards, no editorializing — just the
            source document and the table it produced.
          </p>

          <div style={{ marginTop: 32, maxWidth: 520 }}>
            <SearchBar />
            <div className="mono" style={{ fontSize: 11, color: "var(--ink-3)", marginTop: 8, letterSpacing: "0.04em" }}>
              TRY: “NOTRE DAME” · “PELL GRAD RATE” · “C9 2024” · “CALIFORNIA”
            </div>
          </div>

          <div style={{ marginTop: 40, display: "grid", gridTemplateColumns: "repeat(2, 1fr)", gap: 28, maxWidth: 520 }}>
            <InlineStat label="schools" value="697" spark={HX.schools} />
            <InlineStat label="documents" value="3,924" spark={HX.docs} />
            <InlineStat label="years covered" value="1998–2025" spark={HX.range} dot={false} />
            <InlineStat label="extraction" value="98%" spark={HX.pct} />
          </div>
        </div>

        {/* Right: catalog drawer */}
        <div>
          <div style={{
            border: "1px solid var(--rule-strong)", background: "#faf6ec", padding: "18px 0 0",
            boxShadow: "0 1px 0 0 var(--paper), 0 2px 0 0 var(--rule-strong), 0 3px 0 0 var(--paper), 0 4px 0 0 var(--rule-strong)",
          }}>
            <div style={{ padding: "0 18px 14px", display: "flex", alignItems: "baseline", justifyContent: "space-between", borderBottom: "1px solid var(--rule-strong)" }}>
              <div>
                <div className="meta">Recently archived</div>
                <div style={{ fontFamily: "var(--serif)", fontSize: 22, marginTop: 2 }}>Drain · Week 16</div>
              </div>
              <a className="mono" style={{ fontSize: 11, color: "var(--ink-2)" }} href="#">ALL DRAINS →</a>
            </div>
            {recent.map((r, i) => (
              <div key={i} style={{
                display: "grid", gridTemplateColumns: "44px 1fr 88px 62px 40px",
                alignItems: "center", padding: "14px 18px",
                borderBottom: i === recent.length - 1 ? "none" : "1px dashed var(--rule)",
                gap: 12,
              }}>
                <span className="mono" style={{ color: "var(--ink-4)", fontSize: 11 }}>{String(i + 1).padStart(3, "0")}</span>
                <div>
                  <div style={{ fontFamily: "var(--serif)", fontSize: 16, lineHeight: 1.2 }}>{r.school}</div>
                  <div className="mono" style={{ fontSize: 10.5, color: "var(--ink-3)", marginTop: 3, letterSpacing: "0.05em" }}>
                    {r.state} · {r.section}
                  </div>
                </div>
                <span className="mono" style={{ fontSize: 12, color: "var(--ink-2)" }}>{r.year}</span>
                <span className="cd-chip" style={{ justifyContent: "center" }}>{r.kind}</span>
                <a href="#" className="mono" style={{ fontSize: 10.5, textAlign: "right" }}>OPEN</a>
              </div>
            ))}
          </div>
          <div className="mono" style={{ fontSize: 11, color: "var(--ink-3)", marginTop: 14, textAlign: "right", letterSpacing: "0.04em" }}>
            THE SHELF IS READ-ONLY. EACH ROW LINKS TO ITS SOURCE URL AND ITS EXTRACTED JSON.
          </div>
        </div>
      </div>

      <Footer />
    </div>
  );
}

function InlineStat({ label, value, spark, dot = true }) {
  return (
    <div style={{ borderTop: "1px solid var(--rule-strong)", paddingTop: 12 }}>
      <div className="meta" style={{ marginBottom: 6 }}>{label}</div>
      <div style={{ display: "flex", alignItems: "baseline", gap: 4 }}>
        <span className="serif stat-num" style={{ fontSize: 30, lineHeight: 1, letterSpacing: "-0.015em" }}>{value}</span>
        <Sparkline data={spark} w={44} h={14} dot={dot} />
      </div>
    </div>
  );
}

window.HomeV2 = HomeV2;
