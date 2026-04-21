// Wordmark — tightened spacing, multiple variants.
// Each variant keeps the same domain type treatment; only the glyph/layout changes.
// Use: <Wordmark variant="stamp|corner|bracket|rule|dotted|monogram|plain" size={20} />

function Wordmark({ size = 22, variant = "dotted" }) {
  const ink = "var(--ink)";
  const paper = "var(--paper)";
  const domain = (
    <span style={{ whiteSpace: "nowrap", letterSpacing: "-0.015em" }}>
      <span style={{ fontStyle: "italic", fontWeight: 400 }}>collegedata</span><span style={{ opacity: 0.55 }}>.fyi</span>
    </span>
  );
  const base = {
    display: "inline-flex", alignItems: "center",
    fontFamily: "var(--serif)", fontSize: size, color: ink,
    lineHeight: 1,
  };

  if (variant === "stamp") {
    return (
      <span style={{ ...base, gap: 6 }}>
        <span style={{
          width: size * 1.05, height: size * 1.05, borderRadius: "50%",
          border: `1.1px solid ${ink}`, display: "inline-flex", alignItems: "center", justifyContent: "center",
          fontFamily: "var(--serif)", fontSize: size * 0.72, lineHeight: 1, paddingTop: 1,
          flexShrink: 0,
        }}>§</span>
        {domain}
      </span>
    );
  }
  if (variant === "corner") {
    return (
      <span style={{ ...base, gap: 6 }}>
        <span style={{
          width: size * 1.0, height: size * 1.0,
          border: `1.1px solid ${ink}`, position: "relative", display: "inline-block", flexShrink: 0,
        }}>
          <span style={{
            position: "absolute", top: -1, right: -1, width: size * 0.38, height: size * 0.38,
            background: paper, borderLeft: `1.1px solid ${ink}`, borderBottom: `1.1px solid ${ink}`,
          }}/>
        </span>
        {domain}
      </span>
    );
  }
  if (variant === "bracket") {
    // Editorial bracket stamp: [§]
    return (
      <span style={{ ...base, gap: 5, fontVariantNumeric: "tabular-nums" }}>
        <span style={{ fontSize: size * 0.95, color: "var(--ink-3)" }}>[</span>
        <span style={{ fontFamily: "var(--serif)", fontStyle: "italic", fontSize: size * 0.95 }}>§</span>
        <span style={{ fontSize: size * 0.95, color: "var(--ink-3)", marginRight: 2 }}>]</span>
        {domain}
      </span>
    );
  }
  if (variant === "rule") {
    // No glyph — just a small rule + the mark
    return (
      <span style={{ ...base, gap: 8 }}>
        <span style={{ width: size * 0.9, height: 1.5, background: ink, display: "inline-block" }}/>
        {domain}
      </span>
    );
  }
  if (variant === "dotted") {
    // Pair of small dots (catalog call-number style)
    return (
      <span style={{ ...base, gap: 6 }}>
        <span style={{ display: "inline-flex", gap: 3, alignItems: "center" }}>
          <span style={{ width: 4, height: 4, borderRadius: "50%", background: ink }}/>
          <span style={{ width: 4, height: 4, borderRadius: "50%", background: ink }}/>
        </span>
        {domain}
      </span>
    );
  }
  if (variant === "monogram") {
    // Tight "CD" monogram in a thin square rule
    return (
      <span style={{ ...base, gap: 6 }}>
        <span style={{
          width: size * 1.1, height: size * 1.1,
          border: `1.1px solid ${ink}`, display: "inline-flex", alignItems: "center", justifyContent: "center",
          fontFamily: "var(--serif)", fontSize: size * 0.6, fontStyle: "italic",
          letterSpacing: "-0.03em", flexShrink: 0,
        }}>cd</span>
        {domain}
      </span>
    );
  }
  // plain — no glyph, tight
  return <span style={base}>{domain}</span>;
}

window.Wordmark = Wordmark;
