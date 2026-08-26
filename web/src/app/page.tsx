import Link from "next/link";
import { fetchManifest, fetchSiteStats, fetchBrandColorIndex } from "@/lib/queries";
import { formatCount, formatShortDate } from "@/lib/format";
import type { ManifestRow } from "@/lib/types";
import { SchoolSearch } from "@/components/SchoolSearch";
import { SchoolGlyph } from "@/components/SchoolGlyph";

export const revalidate = 3600; // ISR: revalidate every hour

const HOME_DESCRIPTION =
  "The most comprehensive free college data we know of — the report each college publishes, plus the government’s own numbers, in one public place.";

const homeJsonLd = {
  "@context": "https://schema.org",
  "@type": "WebSite",
  name: "collegedata.fyi",
  url: "https://www.collegedata.fyi",
  description: HOME_DESCRIPTION,
};

// Short calendar-year-boundary format for the two-segment year-range label.
// Collapses "1998-99" -> "1998" and "2025-26" -> "2025" so mobile viewports
// don't break on internal hyphens. Falls back to the raw value if either
// side is already a single number or null.
function compactYearRange(earliest: string | null, latest: string | null): string {
  if (!earliest || !latest) return earliest ?? latest ?? "—";
  const startOf = (y: string) => y.split("-")[0];
  return `${startOf(earliest)}\u2013${startOf(latest)}`;
}

// Map a source_format enum to a 3-4 char display tag used in the drain feed.
function tagForFormat(f: string | null): string {
  if (!f) return "CDS";
  if (f.startsWith("pdf_")) return "PDF";
  return f.toUpperCase();
}

// "Sun 20 Apr" — render the newest-first drain entries with a short, neutral
// calendar stamp. Uses the server's locale to format; date granularity
// alone is fine because the drain feed is a weekly-cadence signal.
function formatDrainDate(iso: string): string {
  const d = new Date(iso);
  const weekday = d.toLocaleDateString("en-US", { weekday: "short" });
  const day = d.toLocaleDateString("en-US", { day: "2-digit" });
  const month = d.toLocaleDateString("en-US", { month: "short" });
  return `${weekday} ${day} ${month}`;
}

// The five most recently-discovered schools. Dedupes by school_id so a
// single school with many historical years doesn't monopolize the feed.
// Source of truth is the live manifest — every entry here is real.
type DrainEntry = {
  when: string;
  school: string;
  schoolId: string;
  action: string;
  tag: string;
  href: string;
  brandColors: string[] | null;
};

function latestDrain(
  rows: ManifestRow[],
  brandIndex: Record<string, string[]>,
): DrainEntry[] {
  const sorted = rows
    .filter((r) => r.discovered_at && r.school_name && r.school_id)
    .slice()
    .sort((a, b) =>
      (b.discovered_at ?? "").localeCompare(a.discovered_at ?? ""),
    );
  const seen = new Set<string>();
  const out: DrainEntry[] = [];
  for (const r of sorted) {
    if (out.length >= 5) break;
    const sid = r.school_id!;
    if (seen.has(sid)) continue;
    seen.add(sid);
    out.push({
      when: formatDrainDate(r.discovered_at!),
      school: r.school_name ?? sid,
      schoolId: sid,
      action: `+ ${r.canonical_year ?? "new"} report`,
      tag: tagForFormat(r.source_format),
      href: r.canonical_year ? `/schools/${sid}/${r.canonical_year}` : `/schools/${sid}`,
      brandColors: brandIndex[sid] ?? null,
    });
  }
  return out;
}

export default async function HomePage() {
  const [manifest, stats, brandIndex] = await Promise.all([
    fetchManifest(),
    fetchSiteStats(),
    fetchBrandColorIndex(),
  ]);
  const drain = latestDrain(manifest, brandIndex);

  const schoolsValue = stats.total_schools.toLocaleString();
  const docsValue = stats.total_documents.toLocaleString();
  const yearRangeValue = compactYearRange(stats.earliest_year, stats.latest_year);
  const queryableFieldsValue = formatCount(stats.queryable_field_count);
  const browserRowsValue = formatCount(stats.browser_primary_row_count);

  return (
    <div className="mx-auto max-w-5xl" style={{ padding: "0 24px" }}>
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{
          __html: JSON.stringify(homeJsonLd).replace(/</g, "\\u003c"),
        }}
      />
      {/* Hero with left/right marginalia */}
      <section
        className="cd-hero"
        style={{
          display: "grid",
          gridTemplateColumns: "80px 1fr 80px",
          padding: "96px 0 40px",
        }}
      >
        <div className="meta cd-marginalia-left" style={{ textAlign: "right", paddingRight: 18 }}>
          <div style={{ lineHeight: 1.8 }}>§ OPEN DATA</div>
          <div style={{ lineHeight: 1.8 }}>SOURCE LINKS</div>
          <div style={{ lineHeight: 1.8 }}>PUBLIC API</div>
        </div>

        <div style={{ textAlign: "center", maxWidth: 780, margin: "0 auto" }}>
          <h1
            style={{
              fontFamily: "var(--serif)",
              fontWeight: 400,
              fontSize: "clamp(44px, 7vw, 72px)",
              lineHeight: 0.98,
              margin: 0,
              letterSpacing: "-0.025em",
            }}
          >
            College data,
            <br />
            <span style={{ fontStyle: "italic", color: "var(--forest-ink)" }}>straight from the source.</span>
          </h1>
          <p
            style={{
              marginTop: 28,
              fontSize: 18,
              lineHeight: 1.55,
              color: "var(--ink-2)",
              maxWidth: 580,
              margin: "28px auto 0",
              textWrap: "balance",
            }}
          >
            The most comprehensive free college data we know of — the report each
            college publishes about itself, plus the government&apos;s own numbers,
            in one public place.
          </p>
          <p
            style={{
              marginTop: 16,
              fontSize: 16,
              lineHeight: 1.55,
              color: "var(--ink-2)",
              maxWidth: 580,
              marginInline: "auto",
              textWrap: "balance",
            }}
          >
            Search a school. Compare admissions, cost, and aid. Open the original
            file. No account.
          </p>

          <div style={{ marginTop: 36, maxWidth: 560, marginInline: "auto" }}>
            <SchoolSearch />
          </div>

          <div style={{ display: "flex", gap: 12, justifyContent: "center", marginTop: 24, flexWrap: "wrap" }}>
            <Link href="/match" className="cd-btn">
              Build match list
            </Link>
            <Link href="/browse" className="cd-btn">
              Compare schools
            </Link>
            <Link href="/schools" className="cd-btn">
              Browse all schools
            </Link>
            <Link href="/api" className="cd-btn cd-btn--ghost">
              API
            </Link>
          </div>
        </div>

        <div className="meta cd-marginalia-right" style={{ paddingLeft: 18 }}>
          <div style={{ lineHeight: 1.8 }}>ADMISSIONS</div>
          <div style={{ lineHeight: 1.8 }}>AFFORDABILITY</div>
          <div style={{ lineHeight: 1.8 }}>OUTCOMES</div>
        </div>
      </section>

      {/* Stat band */}
      <section style={{ marginTop: 48 }}>
        <div
          className="rule-2 cd-stat-grid"
          style={{
            paddingTop: 24,
            display: "grid",
            gridTemplateColumns: "repeat(4, 1fr)",
            gap: 40,
          }}
        >
          <StatCell label="Schools" value={schoolsValue} note="Latest reports we have on file" />
          <StatCell label="Documents" value={docsValue} note={`School files, ${yearRangeValue}`} />
          <StatCell label="Facts you can compare" value={queryableFieldsValue} note="From current school reports" />
          <StatCell
            label="Schools you can compare"
            value={browserRowsValue}
            note={`side by side · refreshed ${formatShortDate(stats.browser_updated_at)}`}
          />
        </div>
      </section>

      {/* Recently added — sourced from the live manifest, one row per
          most-recently-discovered school. */}
      {drain.length > 0 && (
        <section
          className="cd-drain"
          style={{ padding: "64px 0 48px", display: "grid", gridTemplateColumns: "200px 1fr", gap: 40 }}
        >
          <div>
            <div className="meta" style={{ marginBottom: 6 }}>Recently added</div>
            <div style={{ fontSize: 14, color: "var(--ink-3)", lineHeight: 1.5 }}>
              New school reports in the archive. Each row opens the school and
              the original file.
            </div>
          </div>
          <div>
            {drain.map((r, i) => (
              <Link
                key={`${r.school}-${i}`}
                href={r.href}
                className="rule cd-drain-row"
                style={{
                  display: "grid",
                  gridTemplateColumns: "96px 1fr auto auto",
                  gap: 16,
                  alignItems: "center",
                  padding: "10px 0",
                  fontSize: 14,
                  color: "inherit",
                  textDecoration: "none",
                }}
              >
                <span className="mono" style={{ color: "var(--ink-3)", fontSize: 12 }}>{r.when}</span>
                <span className="cd-drain-row__school">
                  <SchoolGlyph brandColors={r.brandColors} />
                  {r.school}
                </span>
                <span className="mono" style={{ fontSize: 12, color: "var(--ink-2)" }}>{r.action}</span>
                <span className="cd-chip">{r.tag}</span>
              </Link>
            ))}
          </div>
        </section>
      )}

      <style>{`
        .cd-drain-row__school {
          display: inline-flex;
          min-width: 0;
          align-items: center;
          gap: 14px;
          font-family: var(--serif);
          font-size: 18px;
        }
        .cd-drain-row:hover .cd-drain-row__school { color: var(--forest-ink); text-decoration: underline; text-underline-offset: 3px; }
        @media (max-width: 860px) {
          .cd-hero { grid-template-columns: 1fr !important; padding-top: 48px !important; }
          .cd-marginalia-left, .cd-marginalia-right { display: none !important; }
          .cd-stat-grid { grid-template-columns: repeat(2, 1fr) !important; gap: 24px !important; }
          .cd-drain { grid-template-columns: 1fr !important; gap: 16px !important; }
          .cd-drain-row { grid-template-columns: 88px 1fr auto !important; gap: 10px 12px !important; }
          .cd-drain-row__school { grid-column: 1 / -1; grid-row: 2; }
        }
      `}</style>
    </div>
  );
}

function StatCell({
  label,
  value,
  note,
}: {
  label: string;
  value: string | number;
  note: string;
}) {
  return (
    <div>
      <div className="meta" style={{ marginBottom: 10 }}>{label}</div>
      <div style={{ display: "flex", alignItems: "baseline", gap: 2 }}>
        <span
          className="stat-num"
          style={{
            fontFamily: "var(--serif)",
            fontSize: 42,
            lineHeight: 1,
            letterSpacing: "-0.02em",
            whiteSpace: "nowrap",
          }}
        >
          {value}
        </span>
      </div>
      <div className="mono" style={{ fontSize: 11, color: "var(--ink-3)", marginTop: 8 }}>{note}</div>
    </div>
  );
}
