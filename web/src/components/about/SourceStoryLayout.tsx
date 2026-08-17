import type { ReactNode } from "react";
import Link from "next/link";

export const SOURCE_STORY_REVIEWED = "2026-08-17";

export function SourceStoryLayout({
  kicker,
  title,
  lede,
  lastReviewed = SOURCE_STORY_REVIEWED,
  jsonLd,
  children,
}: {
  kicker: string;
  title: ReactNode;
  lede: ReactNode;
  lastReviewed?: string;
  jsonLd: Record<string, unknown> | Record<string, unknown>[];
  children: ReactNode;
}) {
  const reviewed = new Date(`${lastReviewed}T00:00:00Z`).toLocaleDateString(
    "en-US",
    { year: "numeric", month: "long", day: "numeric", timeZone: "UTC" },
  );

  return (
    <article
      className="mx-auto max-w-3xl px-4 py-12 sm:px-6"
      style={{ color: "var(--ink-2)" }}
    >
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{
          __html: JSON.stringify(jsonLd).replace(/</g, "\\u003c"),
        }}
      />
      <nav className="meta" style={{ marginBottom: 16 }}>
        <Link href="/about" style={{ color: "var(--ink-3)", textDecoration: "none" }}>
          About
        </Link>
        {" / "}
        <span style={{ color: "var(--ink)" }}>{kicker}</span>
      </nav>
      <p
        className="mono"
        style={{
          fontSize: 11,
          letterSpacing: "0.08em",
          textTransform: "uppercase",
          color: "var(--ink-3)",
          margin: "0 0 12px",
        }}
      >
        Last reviewed {reviewed}
      </p>
      <h1
        className="serif"
        style={{
          fontWeight: 400,
          fontSize: "clamp(40px, 6vw, 56px)",
          lineHeight: 1.05,
          letterSpacing: "-0.02em",
          color: "var(--ink)",
          margin: 0,
        }}
      >
        {title}
      </h1>
      <p
        className="serif"
        style={{
          fontStyle: "italic",
          fontSize: 18,
          lineHeight: 1.55,
          color: "var(--ink-2)",
          margin: "20px 0 0",
          maxWidth: "40rem",
        }}
      >
        {lede}
      </p>
      <div className="cd-source-story">{children}</div>
    </article>
  );
}

export function StoryFigure({
  src,
  alt,
  caption,
  href,
  hrefLabel,
}: {
  src: string;
  alt: string;
  caption: ReactNode;
  href?: string;
  hrefLabel?: string;
}) {
  return (
    <figure className="cd-story-figure">
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img src={src} alt={alt} />
      <figcaption>
        {caption}
        {href && (
          <>
            {" "}
            <Link href={href}>{hrefLabel ?? "Open the live page"}</Link>.
          </>
        )}
      </figcaption>
    </figure>
  );
}

export function StoryTable({
  caption,
  headers,
  rows,
}: {
  caption: string;
  headers: string[];
  rows: ReactNode[][];
}) {
  return (
    <div className="cd-story-table-wrap">
      <table className="cd-story-table">
        <caption className="sr-only">{caption}</caption>
        <thead>
          <tr>
            {headers.map((header) => (
              <th key={header} scope="col">
                {header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, i) => (
            <tr key={i}>
              {row.map((cell, j) => (
                <td key={j}>{cell}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
