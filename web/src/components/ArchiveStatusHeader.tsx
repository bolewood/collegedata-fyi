// PRD 040: shared header for /coverage and /data-quality. Navigation only, no
// counts, so neither route needs the other's data. The Data quality tab is
// gated: before launch only the Coverage tab shows.

import Link from "next/link";
import { dataQualityLaunched } from "@/lib/data-quality";

export const ARCHIVE_TABS = [
  { id: "coverage", label: "Coverage by school", href: "/coverage" },
  { id: "quality", label: "Data quality", href: "/data-quality" },
] as const;

export type ArchiveTabId = (typeof ARCHIVE_TABS)[number]["id"];

export function visibleArchiveTabs(launched: boolean) {
  return ARCHIVE_TABS.filter((t) => t.id === "coverage" || launched);
}

export function ArchiveStatusHeader({
  active,
  launched = dataQualityLaunched(),
}: {
  active: ArchiveTabId;
  /** Test seam. Defaults to the launch gate. */
  launched?: boolean;
}) {
  const tabs = visibleArchiveTabs(launched);
  return (
    <nav aria-label="Archive status" className="archive-status-header">
      <div className="meta" style={{ marginBottom: 10 }}>
        § Archive status
      </div>
      <ul
        style={{
          display: "flex",
          flexWrap: "wrap",
          gap: 24,
          listStyle: "none",
          margin: 0,
          padding: 0,
          borderBottom: "1px solid var(--rule)",
        }}
      >
        {tabs.map((t) => {
          const isActive = t.id === active;
          return (
            <li key={t.id}>
              <Link
                href={t.href}
                aria-current={isActive ? "page" : undefined}
                style={{
                  display: "inline-block",
                  padding: "6px 0",
                  textDecoration: "none",
                  fontFamily: "var(--mono)",
                  fontSize: 12,
                  letterSpacing: "0.06em",
                  textTransform: "uppercase",
                  color: isActive ? "var(--ink)" : "var(--ink-3)",
                  borderBottom: isActive ? "2px solid var(--ink)" : "2px solid transparent",
                  marginBottom: -1,
                }}
              >
                {t.label}
              </Link>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}
