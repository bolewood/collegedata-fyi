// Home v1 — "Moderate archival"
// Centered hero with serif display heading. Marginalia with CDS section
// numbers (§C, §B) runs down the left gutter. Stat counters sit on a
// horizontal rule with inline sparklines. Simple, restrained.

function HomeV1() {
  return (
    <div className="cd-theme" style={{ width: W, background: "var(--paper)", fontSize: 14, color: "var(--ink)" }}>
      <NavRow variant="dotted" />

      {/* Hero */}
      <div style={{ display: "grid", gridTemplateColumns: "80px 1fr 80px", padding: "96px 48px 40px" }}>
        <div style={{ textAlign: "right", paddingRight: 18 }} className="meta">
          <div style={{ lineHeight: 1.8 }}>§ ARCHIVE</div>
          <div style={{ lineHeight: 1.8 }}>EST. 2024</div>
          <div style={{ lineHeight: 1.8 }}>VOL. III</div>
        </div>
        <div style={{ textAlign: "center", maxWidth: 780, margin: "0 auto" }}>
          <div className="meta" style={{ marginBottom: 24 }}>An open archive of U.S. Common Data Set documents</div>
          <h1 style={{
            fontSize: 72, lineHeight: 0.98, margin: 0, letterSpacing: "-0.025em",
            fontFamily: "var(--serif)", fontWeight: 400,
          }}>
            College data,<br />
            <span style={{ fontStyle: "italic", color: "var(--forest-ink)" }}>straight from the source.</span>
          </h1>
          <p style={{
            marginTop: 28, fontSize: 18, lineHeight: 1.55, color: "var(--ink-2)",
            maxWidth: 580, margin: "28px auto 0", textWrap: "balance",
          }}>
            Every fact on this site is pulled verbatim from a school&rsquo;s own Common Data Set —
            archived as a PDF and extracted cell-by-cell, so the numbers stay public
            even when the source page disappears. <a href="#">Read the method.</a>
          </p>

          <div style={{ marginTop: 36, maxWidth: 560, margin: "36px auto 0" }}>
            <SearchBar />
          </div>

          <div style={{ display: "flex", gap: 12, justifyContent: "center", marginTop: 24 }}>
            <button className="cd-btn">Browse all schools →</button>
            <button className="cd-btn cd-btn--ghost">API docs</button>
            <button className="cd-btn cd-btn--ghost">GitHub</button>
          </div>
        </div>
        <div style={{ paddingLeft: 18 }} className="meta">
          <div style={{ lineHeight: 1.8 }}>§C · ADMISSIONS</div>
          <div style={{ lineHeight: 1.8 }}>§B · ENROLLMENT</div>
          <div style={{ lineHeight: 1.8 }}>§H · FIN. AID</div>
        </div>
      </div>

      {/* Stat band with sparklines */}
      <div style={{ padding: "0 48px", marginTop: 48 }}>
        <div className="rule-2" style={{ paddingTop: 24, display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 40 }}>
          <StatCell label="Schools archived" value="697" spark={HX.schools} note="+22 this qtr." />
          <StatCell label="CDS documents"    value="3,924" spark={HX.docs} note="+212 this qtr." />
          <StatCell label="Year range"       value="1998–2025" spark={HX.range} note="27 yrs deep" dot={false} />
          <StatCell label="Structured extraction" value="98%" spark={HX.pct} note="last drain" suffix="" />
        </div>
      </div>

      {/* Latest drains feed */}
      <div style={{ padding: "64px 48px 32px", display: "grid", gridTemplateColumns: "200px 1fr", gap: 40 }}>
        <div>
          <div className="meta" style={{ marginBottom: 6 }}>§ Latest drain</div>
          <div style={{ fontSize: 14, color: "var(--ink-3)", lineHeight: 1.5 }}>
            Every Sunday we re-pull each school&rsquo;s CDS page and diff the PDF. Nothing is stored opaquely.
          </div>
        </div>
        <div>
          {[
            { when: "Sun 20 Apr", school: "Bethel University",        action: "+ 2024-25 CDS",      tag: "XLSX" },
            { when: "Sun 20 Apr", school: "Harvey Mudd College",     action: "· re-extract §C",    tag: "PDF"  },
            { when: "Sat 12 Apr", school: "Univ. of Notre Dame",      action: "+ 2025-26 CDS",      tag: "PDF"  },
            { when: "Sat 12 Apr", school: "William & Mary",           action: "+ 2024-25 CDS",      tag: "PDF"  },
            { when: "Sun 06 Apr", school: "Johns Hopkins University", action: "· backfill 2019-20", tag: "PDF"  },
          ].map((r, i) => (
            <div key={i} className="rule"
              style={{ display: "grid", gridTemplateColumns: "96px 1fr auto auto", gap: 16, alignItems: "baseline", padding: "10px 0", fontSize: 14 }}>
              <span className="mono" style={{ color: "var(--ink-3)", fontSize: 12 }}>{r.when}</span>
              <span style={{ fontFamily: "var(--serif)", fontSize: 18 }}>{r.school}</span>
              <span className="mono" style={{ fontSize: 12, color: "var(--ink-2)" }}>{r.action}</span>
              <span className="cd-chip">{r.tag}</span>
            </div>
          ))}
        </div>
      </div>

      <Footer />
    </div>
  );
}

function StatCell({ label, value, spark, note, dot = true, suffix = "" }) {
  return (
    <div>
      <div className="meta" style={{ marginBottom: 10 }}>{label}</div>
      <div style={{ display: "flex", alignItems: "baseline", gap: 2 }}>
        <span className="serif stat-num" style={{ fontSize: 42, lineHeight: 1, letterSpacing: "-0.02em" }}>{value}{suffix}</span>
        <Sparkline data={spark} w={54} h={18} dot={dot} />
      </div>
      <div className="mono" style={{ fontSize: 11, color: "var(--ink-3)", marginTop: 8 }}>{note}</div>
    </div>
  );
}

function Footer() {
  return (
    <footer className="rule" style={{ marginTop: 80, padding: "32px 48px 56px",
      display: "grid", gridTemplateColumns: "1fr auto", gap: 32, fontSize: 13, color: "var(--ink-3)" }}>
      <div>
        <Wordmark size={18} />
        <div style={{ marginTop: 10, maxWidth: 520, lineHeight: 1.55 }}>
          An open-source archive of U.S. college Common Data Set documents.
          MIT License. Data sourced from each school&rsquo;s IR office via the CDS Initiative template.
        </div>
        <div className="mono" style={{ marginTop: 14, fontSize: 11, color: "var(--ink-4)", letterSpacing: "0.05em" }}>
          LAST DRAIN · SUN 20 APR 2026 · 697 SCHOOLS · 3,924 DOCS
        </div>
      </div>
      <div style={{ display: "flex", gap: 28, alignSelf: "end" }}>
        {["GitHub", "Recipes", "API", "About"].map(l => (
          <a key={l} href="#" style={{ color: "var(--ink-2)" }}>{l}</a>
        ))}
      </div>
    </footer>
  );
}

window.HomeV1 = HomeV1; window.Footer = Footer;
