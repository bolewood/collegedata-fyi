import { externalLinkRel } from "@/lib/client-info";
import { officialPageLabel } from "@/lib/archive-lead";
import { getOfficialCdsPage } from "@/lib/official-cds-page";
import { buildYearKeyFacts } from "@/lib/school-seo";
import type { SchoolYearFacts } from "@/lib/school-summary";

export function YearKeyFacts({
  schoolId,
  schoolName,
  year,
  ipedsId,
  facts,
  sourceDownloadHref,
}: {
  schoolId: string;
  schoolName: string;
  year: string;
  ipedsId?: string | null;
  facts: SchoolYearFacts | null | undefined;
  sourceDownloadHref?: string | null;
}) {
  const items = buildYearKeyFacts(facts);
  const official = getOfficialCdsPage(schoolId, ipedsId);

  if (items.length === 0 && !sourceDownloadHref && !official) {
    return null;
  }

  return (
    <section
      aria-label={`${schoolName} ${year} Common Data Set key facts`}
      className="cd-card"
      style={{
        marginTop: 20,
        padding: "16px 20px",
      }}
    >
      <div
        className="meta"
        style={{
          marginBottom: 12,
          color: "var(--ink-3)",
        }}
      >
        § {year} key facts
      </div>
      <dl
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(150px, 1fr))",
          gap: "12px 24px",
          margin: 0,
        }}
      >
        {items.map((item) => (
          <div
            key={item.label}
            style={{
              borderTop: "1px solid var(--rule)",
              paddingTop: 8,
            }}
          >
            <dt
              className="meta"
              style={{
                fontSize: 10.5,
                color: "var(--ink-3)",
                marginBottom: 4,
              }}
            >
              {item.label}
            </dt>
            <dd
              className="nums"
              style={{
                margin: 0,
                fontSize: 16,
                fontWeight: 500,
                color: "var(--ink)",
              }}
            >
              {item.value}
            </dd>
          </div>
        ))}
        {(sourceDownloadHref || official) && (
          <div
            style={{
              borderTop: "1px solid var(--rule)",
              paddingTop: 8,
            }}
          >
            <dt
              className="meta"
              style={{
                fontSize: 10.5,
                color: "var(--ink-3)",
                marginBottom: 4,
              }}
            >
              Original source
            </dt>
            <dd
              style={{
                margin: 0,
                fontSize: 14,
                lineHeight: 1.45,
                color: "var(--ink-2)",
              }}
            >
              {sourceDownloadHref ? (
                <a
                  href={sourceDownloadHref}
                  target="_blank"
                  rel={externalLinkRel(sourceDownloadHref)}
                  style={{ color: "var(--forest-ink)" }}
                >
                  Download {year} file
                </a>
              ) : null}
              {sourceDownloadHref && official ? " · " : null}
              {official ? (
                <a
                  href={official.url}
                  title={officialPageLabel(official.url)}
                  target="_blank"
                  rel="noopener noreferrer"
                  style={{ color: "var(--forest-ink)" }}
                >
                  Official school page
                </a>
              ) : null}
            </dd>
          </div>
        )}
      </dl>
    </section>
  );
}
