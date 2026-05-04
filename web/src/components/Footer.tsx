import { Wordmark } from "./Wordmark";

export function Footer() {
  return (
    <footer
      className="mt-auto"
      style={{
        borderTop: "1px solid var(--rule)",
        background: "var(--paper)",
      }}
    >
      <div
        className="mx-auto max-w-5xl cd-footer-inner"
        style={{
          padding: "32px 24px 56px",
          display: "grid",
          gridTemplateColumns: "1fr auto",
          gap: 32,
          fontSize: 13,
          color: "var(--ink-3)",
        }}
      >
        <div>
          <Wordmark size={18} variant="dotted" />
          <div style={{ marginTop: 10, maxWidth: 520, lineHeight: 1.55 }}>
            An open-source archive of U.S. college Common Data Set documents.
            MIT License. Data sourced from each school&rsquo;s IR office via the
            CDS Initiative template.
          </div>
        </div>
        <div className="cd-footer-links" style={{ display: "flex", gap: 24, alignSelf: "end" }}>
          <a href="https://github.com/bolewood/collegedata-fyi" target="_blank" rel="noopener noreferrer">
            GitHub
          </a>
          <a href="/recipes">Recipes</a>
          <a href="/api">API</a>
          <a href="/about">About</a>
        </div>
      </div>
    </footer>
  );
}
