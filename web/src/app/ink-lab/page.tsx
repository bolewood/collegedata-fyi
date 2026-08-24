import type { Metadata } from "next";
import {
  INK_LAB_PRESETS,
  deriveInks,
  HOUSE_A,
  HOUSE_B,
} from "@/lib/derive-inks";

export const metadata: Metadata = {
  title: "Ink lab",
  robots: { index: false, follow: false },
};

export default function InkLabPage() {
  const house = deriveInks([]);
  const rows = [
    ["House inks (no brand colours)", ""] as [string, string],
    ...INK_LAB_PRESETS,
  ];

  return (
    <div className="mx-auto max-w-5xl px-4 py-10">
      <p className="meta">§ Internal · not indexed</p>
      <h1 className="serif" style={{ fontSize: 42, fontWeight: 400, margin: "8px 0 0" }}>
        Ink lab
      </h1>
      <p style={{ maxWidth: "62ch", color: "var(--ink-2)", marginTop: 12 }}>
        Regression grid for the two-plate school inks. House A/B must stay{" "}
        <code>{HOUSE_A}</code> / <code>{HOUSE_B}</code>. Michigan maize must stay
        maize. A failed B-on-A gate means the name stays cream on the hero band.
      </p>
      <p className="meta" style={{ marginTop: 10 }}>
        House aOnCream {house.contrast.aOnCream}:1 (site forest, not forced to 7:1)
      </p>
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fill, minmax(220px, 1fr))",
          gap: 14,
          marginTop: 28,
        }}
      >
        {rows.map(([name, hexes]) => {
          const inks = deriveInks(hexes);
          return (
            <article
              key={name}
              style={{
                border: "1px solid var(--rule-strong)",
                background: "var(--paper)",
              }}
            >
              <div style={{ display: "flex", height: 54 }}>
                <i style={{ flex: 1, background: inks.a }} />
                <i style={{ flex: 0.62, background: inks.b }} />
              </div>
              <div style={{ padding: "10px 12px 12px" }}>
                <div className="serif" style={{ fontSize: 16 }}>
                  {name}
                </div>
                <p
                  className="mono"
                  style={{
                    fontSize: 10,
                    letterSpacing: "0.04em",
                    textTransform: "uppercase",
                    color: "var(--ink-3)",
                    margin: "6px 0 0",
                    lineHeight: 1.45,
                  }}
                >
                  {inks.rule}
                </p>
                <p
                  className="mono"
                  style={{
                    fontSize: 10,
                    margin: "8px 0 0",
                    display: "flex",
                    justifyContent: "space-between",
                    gap: 8,
                  }}
                >
                  <span>A {inks.contrast.aOnCream}:1</span>
                  <span>onB {inks.contrast.textOnB}:1</span>
                  <span>B {inks.contrast.bOnCream}:1</span>
                  <span style={{ color: inks.bTypeOnA ? "var(--forest)" : "var(--ochre)" }}>
                    B/A {inks.contrast.bOnA}:1
                  </span>
                </p>
              </div>
            </article>
          );
        })}
      </div>
    </div>
  );
}
