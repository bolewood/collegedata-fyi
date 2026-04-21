// Home v3 — "Index page"
// Dense, broadsheet-style. Two-column: editorial intro on left, a big
// A–Z index of schools on the right. Stats are run as inline prose.
// Designed to feel like opening a catalog.

function HomeV3() {
  // Alphabetical sample — visual only
  const index = {
    A: ["Amherst", "Arizona State", "Auburn"],
    B: ["Barnard", "Bates", "Berkeley", "Bethel", "Boston College", "Bowdoin", "Brown"],
    C: ["Caltech", "Carleton", "Carnegie Mellon", "Chicago", "Claremont McKenna", "Colgate", "Columbia", "Cornell"],
    D: ["Dartmouth", "Davidson", "Denison", "Duke"],
    E: ["Emory"],
    F: ["Florida", "Fordham"],
    G: ["Georgetown", "Georgia Tech", "Grinnell"],
    H: ["Hamilton", "Harvard", "Harvey Mudd", "Haverford"],
    J: ["Johns Hopkins"],
    M: ["Macalester", "MIT", "Middlebury"],
    N: ["Northeastern", "Northwestern", "Notre Dame", "NYU"],
    P: ["Penn", "Pomona", "Princeton", "Purdue"],
    R: ["Reed", "Rice", "Rochester"],
    S: ["Smith", "Stanford", "Swarthmore"],
    T: ["Tufts", "Tulane"],
    U: ["UCLA", "UChicago", "UMich", "UNC", "USC", "UVA"],
    V: ["Vanderbilt", "Vassar", "Villanova", "Virginia Tech"],
    W: ["Wake Forest", "Washington St. Louis", "Wellesley", "Wesleyan", "Williams", "William & Mary"],
    Y: ["Yale"],
  };

  return (
    <div className="cd-theme" style={{ width: W, background: "var(--paper)", fontSize: 14 }}>
      <NavRow variant="dotted" active="Schools" />

      {/* Masthead */}
      <div style={{
        borderBottom: "1px solid var(--rule-strong)",
        padding: "20px 48px",
        display: "flex", alignItems: "baseline", justifyContent: "space-between",
      }}>
        <div className="mono" style={{ fontSize: 11, color: "var(--ink-2)", letterSpacing: "0.08em" }}>
          VOL. III · NO. 16 · SUNDAY 20 APRIL 2026
        </div>
        <div style={{ fontFamily: "var(--serif)", fontStyle: "italic", fontSize: 14, color: "var(--ink-2)" }}>
          “Kept open, on the record.”
        </div>
        <div className="mono" style={{ fontSize: 11, color: "var(--ink-2)", letterSpacing: "0.08em" }}>
          697 · 3,924 · 1998–2025
        </div>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1.2fr", gap: 48, padding: "56px 48px 48px" }}>
        {/* Left column — editorial */}
        <div>
          <div className="meta" style={{ marginBottom: 10 }}>§ The paper</div>
          <h1 style={{
            fontFamily: "var(--serif)", fontWeight: 400, fontSize: 64, lineHeight: 0.98,
            margin: 0, letterSpacing: "-0.025em",
          }}>
            College data,<br />
            <span style={{ fontStyle: "italic" }}>straight</span> from<br />
            the source.
          </h1>

          <div style={{ marginTop: 28, maxWidth: 460 }}>
            <SearchBar />
          </div>

          <p style={{ marginTop: 32, fontSize: 15.5, lineHeight: 1.6, color: "var(--ink-2)", maxWidth: 480, textWrap: "pretty" }}>
            <span className="serif" style={{ fontSize: 48, float: "left", lineHeight: 0.8, paddingRight: 10, paddingTop: 4, fontStyle: "italic" }}>T</span>
            his archive holds{" "}
            <b style={{ fontFamily: "var(--serif)", fontWeight: 500, fontStyle: "italic" }}>697 schools</b>
            <Sparkline data={HX.schools} w={34} h={12} />, {" "}
            <b style={{ fontFamily: "var(--serif)", fontWeight: 500, fontStyle: "italic" }}>3,924 CDS documents</b>
            <Sparkline data={HX.docs} w={34} h={12} />, {" "}
            covering {" "}
            <b style={{ fontFamily: "var(--serif)", fontWeight: 500, fontStyle: "italic" }}>1998 through 2025</b>.
            Ninety-eight per cent <Sparkline data={HX.pct} w={28} h={12} /> of those
            pages have been structured into queryable JSON, the rest are held as PDFs
            until a reviewer clears them.
          </p>

          <p style={{ marginTop: 20, fontSize: 15.5, lineHeight: 1.6, color: "var(--ink-2)", maxWidth: 480 }}>
            Every Sunday a scheduled drain re-pulls each school&rsquo;s published CDS page,
            diffs the file, and keeps the older version. Nothing is ever overwritten.
            The whole thing is <a href="#">open source</a>, the whole thing is <a href="#">free</a>,
            and the whole thing takes contributions via <a href="#">pull request</a>.
          </p>

          <div style={{ marginTop: 32, display: "flex", gap: 10 }}>
            <button className="cd-btn">Browse schools</button>
            <button className="cd-btn cd-btn--ghost">Recipes</button>
            <button className="cd-btn cd-btn--ghost">API</button>
          </div>

          {/* Highlighted recipe */}
          <div className="cd-card" style={{ marginTop: 40, padding: 20 }}>
            <div className="meta" style={{ marginBottom: 8, color: "var(--forest)" }}>§ Featured recipe</div>
            <div style={{ fontFamily: "var(--serif)", fontSize: 22, letterSpacing: "-0.01em" }}>
              Acceptance rate <span style={{ fontStyle: "italic" }}>vs.</span> yield
            </div>
            <div style={{ fontSize: 13.5, color: "var(--ink-2)", marginTop: 6, lineHeight: 1.5 }}>
              Two numbers, eighteen schools worth of context. A scatter with quadrants.
            </div>
            <div style={{ marginTop: 12, display: "flex", gap: 10, alignItems: "center" }}>
              <span className="cd-chip">CDS C1</span>
              <span className="cd-chip">B1</span>
              <span className="cd-chip">B22</span>
              <a href="#" style={{ marginLeft: "auto", fontFamily: "var(--mono)", fontSize: 11, letterSpacing: "0.05em" }}>OPEN DEMO →</a>
            </div>
          </div>
        </div>

        {/* Right column — A–Z index */}
        <div>
          <div style={{ display: "flex", alignItems: "baseline", justifyContent: "space-between" }}>
            <div className="meta">§ Index · A–Z · 697 entries</div>
            <div className="mono" style={{ fontSize: 11, color: "var(--ink-3)" }}>SHOWING 72 · FILTER ↓</div>
          </div>
          <div className="rule-2" style={{ marginTop: 12, paddingTop: 20, columnCount: 2, columnGap: 40 }}>
            {Object.entries(index).map(([letter, schools]) => (
              <div key={letter} style={{ breakInside: "avoid", marginBottom: 22 }}>
                <div style={{
                  display: "flex", alignItems: "baseline", gap: 10,
                  borderBottom: "1px solid var(--rule-strong)", paddingBottom: 4, marginBottom: 8,
                }}>
                  <span className="serif" style={{ fontSize: 22, fontStyle: "italic" }}>{letter}</span>
                  <span className="mono" style={{ fontSize: 10, color: "var(--ink-4)", letterSpacing: "0.08em" }}>
                    {schools.length} {schools.length === 1 ? "school" : "schools"}
                  </span>
                </div>
                {schools.map(s => (
                  <div key={s} style={{
                    display: "flex", justifyContent: "space-between", alignItems: "baseline",
                    fontSize: 13.5, padding: "2px 0", color: "var(--ink)",
                  }}>
                    <a href="#" style={{ textDecoration: "none", color: "inherit" }}>{s}</a>
                    <span className="mono" style={{ fontSize: 10.5, color: "var(--ink-4)" }}>
                      {"·".repeat(Math.floor(Math.random() * 2) + 2)} {Math.floor(Math.random() * 6) + 2}
                    </span>
                  </div>
                ))}
              </div>
            ))}
          </div>
        </div>
      </div>

      <Footer />
    </div>
  );
}

window.HomeV3 = HomeV3;
