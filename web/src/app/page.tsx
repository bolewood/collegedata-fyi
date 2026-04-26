import Link from "next/link";
import { fetchManifest, aggregateSchools, computeStats } from "@/lib/queries";
import type { ManifestRow } from "@/lib/types";
import { SchoolSearch } from "@/components/SchoolSearch";

export const revalidate = 3600; // ISR: revalidate every hour

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
type DrainEntry = { when: string; school: string; action: string; tag: string };

function latestDrain(rows: ManifestRow[]): DrainEntry[] {
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
      action: `+ ${r.canonical_year ?? "new"} CDS`,
      tag: tagForFormat(r.source_format),
    });
  }
  return out;
}

export default async function HomePage() {
  const manifest = await fetchManifest();
  const schools = aggregateSchools(manifest);
  const stats = computeStats(manifest);
  const drain = latestDrain(manifest);

  const schoolsValue = stats.total_schools.toLocaleString();
  const docsValue = stats.total_documents.toLocaleString();
  const yearRangeValue = compactYearRange(stats.earliest_year, stats.latest_year);
  const pctValue = `${stats.extraction_pct}%`;

  return (
    <div className="mx-auto max-w-5xl" style={{ padding: "0 24px" }}>
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
          <div style={{ lineHeight: 1.8 }}>§ ARCHIVE</div>
          <div style={{ lineHeight: 1.8 }}>EST. 2024</div>
          <div style={{ lineHeight: 1.8 }}>VOL. III</div>
        </div>

        <div style={{ textAlign: "center", maxWidth: 780, margin: "0 auto" }}>
          <div className="meta" style={{ marginBottom: 24 }}>
            An open archive of U.S. Common Data Set documents
          </div>
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
            Every fact on this site starts with a school&rsquo;s own Common Data Set. We archive the source file and map it
            into a queryable schema; some formats extract cleanly, while flattened PDFs still need template-specific
            cleaners that improve over time.{" "}
            <Link href="/about">Read the method.</Link>
          </p>

          <div style={{ marginTop: 36, maxWidth: 560, marginInline: "auto" }}>
            <SchoolSearch schools={schools} />
          </div>

          <div style={{ display: "flex", gap: 12, justifyContent: "center", marginTop: 24, flexWrap: "wrap" }}>
            <Link href="/schools" className="cd-btn">
              Browse all schools →
            </Link>
            <Link href="/api" className="cd-btn cd-btn--ghost">
              API docs
            </Link>
            <a
              href="https://github.com/bolewood/collegedata-fyi"
              target="_blank"
              rel="noopener noreferrer"
              className="cd-btn cd-btn--ghost"
            >
              GitHub
            </a>
          </div>
        </div>

        <div className="meta cd-marginalia-right" style={{ paddingLeft: 18 }}>
          <div style={{ lineHeight: 1.8 }}>§C · ADMISSIONS</div>
          <div style={{ lineHeight: 1.8 }}>§B · ENROLLMENT</div>
          <div style={{ lineHeight: 1.8 }}>§H · FIN. AID</div>
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
          <StatCell label="Schools archived" value={schoolsValue} note={`${stats.extracted_count.toLocaleString()} extracted`} />
          <StatCell label="CDS documents" value={docsValue} note={`${stats.extraction_pct}% structured`} />
          <StatCell label="Year range" value={yearRangeValue} note={`${stats.total_documents.toLocaleString()} docs across the span`} />
          <StatCell label="Structured extraction" value={pctValue} note="last manifest drain" />
        </div>
      </section>

      {/* Latest drain feed — sourced from the live manifest, one row per
          most-recently-discovered school. */}
      {drain.length > 0 && (
        <section
          className="cd-drain"
          style={{ padding: "64px 0 48px", display: "grid", gridTemplateColumns: "200px 1fr", gap: 40 }}
        >
          <div>
            <div className="meta" style={{ marginBottom: 6 }}>§ Latest drain</div>
            <div style={{ fontSize: 14, color: "var(--ink-3)", lineHeight: 1.5 }}>
              The most recent additions to the archive. Every row is a real
              CDS document we discovered, downloaded, and indexed.
            </div>
          </div>
          <div>
            {drain.map((r, i) => (
              <div
                key={`${r.school}-${i}`}
                className="rule"
                style={{
                  display: "grid",
                  gridTemplateColumns: "96px 1fr auto auto",
                  gap: 16,
                  alignItems: "baseline",
                  padding: "10px 0",
                  fontSize: 14,
                }}
              >
                <span className="mono" style={{ color: "var(--ink-3)", fontSize: 12 }}>{r.when}</span>
                <span style={{ fontFamily: "var(--serif)", fontSize: 18 }}>{r.school}</span>
                <span className="mono" style={{ fontSize: 12, color: "var(--ink-2)" }}>{r.action}</span>
                <span className="cd-chip">{r.tag}</span>
              </div>
            ))}
          </div>
        </section>
      )}

      <style>{`
        @media (max-width: 860px) {
          .cd-hero { grid-template-columns: 1fr !important; padding-top: 48px !important; }
          .cd-marginalia-left, .cd-marginalia-right { display: none !important; }
          .cd-stat-grid { grid-template-columns: repeat(2, 1fr) !important; gap: 24px !important; }
          .cd-drain { grid-template-columns: 1fr !important; gap: 16px !important; }
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
