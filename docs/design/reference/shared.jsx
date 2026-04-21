// Shared bits used by every Home variant.
const W = 1120;   // artboard width
const NAV_LINKS = ["Schools", "Recipes", "About", "API", "GitHub"];

// Example ~18-tick drain histories. Monotonic-ish, rooted at the headline number.
const HX = {
  schools:  [612, 618, 625, 631, 640, 648, 655, 661, 668, 673, 678, 682, 686, 689, 692, 694, 695, 697],
  docs:     [3120, 3215, 3302, 3388, 3466, 3540, 3611, 3680, 3742, 3801, 3851, 3879, 3892, 3901, 3909, 3915, 3920, 3924],
  pct:      [82, 84, 86, 87, 88, 90, 91, 92, 93, 94, 95, 95, 96, 96, 97, 97, 98, 98],
  range:    [1998, 2000, 2005, 2010, 2015, 2018, 2020, 2022, 2023, 2024, 2024, 2024, 2025, 2025, 2025, 2025, 2025, 2025],
};

// Pure-html search input (not wired) — same styling across all variants.
function SearchBar({ placeholder = "Search 697 schools by name, state, or IPEDS id…", density = "comfortable" }) {
  const pad = density === "compact" ? "11px 14px" : "15px 18px";
  return (
    <div style={{
      display: "flex", alignItems: "center", gap: 12,
      border: "1px solid var(--ink)", background: "#faf6ec",
      padding: pad, borderRadius: 2,
    }}>
      <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" style={{ flexShrink: 0 }}>
        <circle cx="7" cy="7" r="5"/><path d="M11 11l3.5 3.5" strokeLinecap="round"/>
      </svg>
      <input
        placeholder={placeholder}
        style={{
          border: "none", outline: "none", background: "transparent",
          fontFamily: "var(--sans)", fontSize: 15, color: "var(--ink)", flex: 1, letterSpacing: "-0.005em",
        }}
      />
      <kbd className="mono" style={{
        fontSize: 10.5, padding: "2px 6px", border: "1px solid var(--rule-strong)",
        color: "var(--ink-3)", borderRadius: 2, background: "var(--paper)",
      }}>⌘K</kbd>
    </div>
  );
}

// Skinny tag row (just visual)
function NavRow({ variant = "dotted", active = "" }) {
  return (
    <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between",
      padding: "18px 48px", borderBottom: "1px solid var(--rule)" }}>
      <Wordmark variant={variant} size={20} />
      <nav style={{ display: "flex", gap: 28, fontSize: 14 }}>
        {NAV_LINKS.map(l => (
          <a key={l} href="#" style={{
            textDecoration: "none", color: l === active ? "var(--ink)" : "var(--ink-3)",
            borderBottom: l === active ? "1px solid var(--ink)" : "1px solid transparent",
            paddingBottom: 2,
          }}>{l}</a>
        ))}
      </nav>
    </div>
  );
}

window.W = W; window.HX = HX;
window.SearchBar = SearchBar; window.NavRow = NavRow;
