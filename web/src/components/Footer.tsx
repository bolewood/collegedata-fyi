import { isUsageLaunched } from "@/lib/usage";
import { dataQualityLaunched } from "@/lib/data-quality";
import { CommunityLink } from "./CommunityInvitation";
import { FORMER_NAME, SITE_NAME } from "@/lib/site";
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
            Open-source college data with source-linked school publications,
            NCES/IPEDS baselines, College Scorecard context, and public APIs.
            Code: MIT License. Data: <a href="/api#credit">CC BY 4.0</a>.
          </div>
          <div style={{ marginTop: 6 }}>
            {SITE_NAME} is a project of Bolewood Group, LLC. Formerly {FORMER_NAME}.
          </div>
        </div>
        <div className="cd-footer-links" style={{ display: "flex", gap: 24, alignSelf: "end", flexWrap: "wrap" }}>
          <a href="https://github.com/bolewood/collegedata-fyi" target="_blank" rel="noopener noreferrer">
            GitHub
          </a>
          <CommunityLink surface="footer">Feedback</CommunityLink>
          <a href="/coverage">{dataQualityLaunched() ? "Archive status" : "Coverage"}</a>
          <a href="/scholarships">Scholarships</a>
          <a href="/pipeline-observation">Pipeline</a>
          {isUsageLaunched() ? <a href="/usage">Usage</a> : null}
          <a href="/recipes">Recipes</a>
          <a href="/api">API</a>
          <a href="/privacy">Privacy</a>
          <a href="/about">About</a>
          <a href="/about/common-data-set">CDS</a>
          <a href="/about/college-scorecard">Scorecard</a>
          <a href="/about/ipeds">IPEDS</a>
        </div>
      </div>
    </footer>
  );
}
