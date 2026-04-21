// Side-by-side wordmark comparison sheet.
function WordmarkCompare() {
  const variants = [
    { v: "stamp",    label: "A · Section stamp",   note: "Circled § glyph. Default." },
    { v: "corner",   label: "B · Catalog corner",  note: "Index-card corner cut." },
    { v: "bracket",  label: "C · Editorial",       note: "[§] inline bracket stamp." },
    { v: "monogram", label: "D · Monogram",        note: "Serif ‘cd’ in a thin square." },
    { v: "rule",     label: "E · Rule",            note: "Minimal — rule + mark only." },
    { v: "dotted",   label: "F · Call-number",     note: "Two dots, catalog style." },
    { v: "plain",    label: "G · Plain",           note: "No glyph at all." },
  ];
  return (
    <div className="cd-theme" style={{ width: 1120, background: "var(--paper)", padding: "48px 48px 72px" }}>
      <div className="meta" style={{ marginBottom: 10 }}>§ Wordmark explorations</div>
      <h1 style={{ fontFamily: "var(--serif)", fontWeight: 400, fontSize: 40, margin: 0, letterSpacing: "-0.015em" }}>
        Seven wordmark takes, same type, tighter spacing.
      </h1>
      <p style={{ maxWidth: 640, color: "var(--ink-2)", fontSize: 15, lineHeight: 1.55, marginTop: 10 }}>
        Reduced the glyph-to-domain gap from 8px to 5–6px, thinned the stroke to 1.1px,
        and tried the mark in a few non-stamp registers. Two display sizes each.
      </p>

      <div className="rule-2" style={{ marginTop: 32, paddingTop: 24,
        display: "grid", gridTemplateColumns: "repeat(2, 1fr)", gap: 32 }}>
        {variants.map(({ v, label, note }) => (
          <div key={v} className="cd-card" style={{ padding: "22px 24px" }}>
            <div style={{ display: "flex", alignItems: "baseline", justifyContent: "space-between", marginBottom: 14 }}>
              <div className="meta">{label}</div>
              <div className="mono" style={{ fontSize: 10.5, color: "var(--ink-4)" }}>variant="{v}"</div>
            </div>
            <div style={{ display: "flex", alignItems: "center", gap: 28, minHeight: 56,
              borderBottom: "1px dashed var(--rule)", paddingBottom: 16 }}>
              <Wordmark variant={v} size={30} />
            </div>
            <div style={{ display: "flex", alignItems: "center", gap: 20, minHeight: 32, paddingTop: 14 }}>
              <Wordmark variant={v} size={18} />
              <span style={{ flex: 1 }}/>
              <span className="mono" style={{ fontSize: 11, color: "var(--ink-3)" }}>nav size</span>
            </div>
            <div style={{ marginTop: 12, fontSize: 13, color: "var(--ink-2)", fontFamily: "var(--serif)", fontStyle: "italic" }}>
              {note}
            </div>
          </div>
        ))}
      </div>

      {/* on-card demo — wordmark against a real nav row */}
      <div className="meta" style={{ marginTop: 48, marginBottom: 12 }}>§ In context</div>
      <div style={{ display: "grid", gap: 0 }}>
        {["stamp", "corner", "bracket", "monogram"].map(v => (
          <div key={v} style={{
            display: "flex", alignItems: "center", justifyContent: "space-between",
            padding: "14px 22px", borderTop: "1px solid var(--rule)",
            background: "#faf6ec",
          }}>
            <Wordmark variant={v} size={18} />
            <nav style={{ display: "flex", gap: 22, fontSize: 13, color: "var(--ink-3)" }}>
              {["Schools","Recipes","About","API","GitHub"].map(l => <span key={l}>{l}</span>)}
            </nav>
          </div>
        ))}
      </div>
    </div>
  );
}

window.WordmarkCompare = WordmarkCompare;
