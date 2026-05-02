import type { Metadata } from "next";
import { notFound } from "next/navigation";
import Link from "next/link";
import {
  fetchSchoolDocuments,
  fetchScorecardByIpedsId,
  fetchInstitutionCoverage,
  fetchBrowserRowBySchoolId,
  fetchAvgGpaBySchoolId,
  fetchAdmissionStrategyBySchoolId,
} from "@/lib/queries";
import { OutcomesSection } from "@/components/OutcomesSection";
import { PositioningCard } from "@/components/PositioningCard";
import { AdmissionStrategyCard } from "@/components/AdmissionStrategyCard";
import { SchoolDocumentsLedger } from "@/components/SchoolDocumentsLedger";
import { ScorecardVintageNote } from "@/components/ScorecardVintageNote";
import { Sparkline } from "@/components/Sparkline";
import { CoverageBadge } from "@/components/CoverageBadge";
import { SubmissionForm } from "@/components/SubmissionForm";
import { storageUrl, yearRange } from "@/lib/format";
import type { ManifestRow, InstitutionCoverage } from "@/lib/types";

export const revalidate = 3600;

export async function generateMetadata({
  params,
}: {
  params: Promise<{ school_id: string }>;
}): Promise<Metadata> {
  const { school_id } = await params;
  const docs = await fetchSchoolDocuments(school_id);
  if (docs.length === 0) {
    // PRD 015 M4 — directory-only schools render a coverage stub.
    // Title reflects the school name (not "Not Found") so the browser
    // tab and OG share match what the user sees.
    const coverage = await fetchInstitutionCoverage(school_id);
    if (coverage) {
      const path = `/schools/${school_id}`;
      return {
        title: `${coverage.school_name} - ${coverage.coverage_label}`,
        description: coverage.coverage_summary,
        alternates: { canonical: path },
        openGraph: {
          url: path,
          title: coverage.school_name,
          description: coverage.coverage_summary,
        },
      };
    }
    return { title: "School Not Found" };
  }

  const name = docs[0].school_name;
  const years = docs
    .map((d) => d.canonical_year)
    .filter((y): y is string => y != null)
    .sort();
  const path = `/schools/${school_id}`;
  const description = `${docs.length} archived Common Data Set document${docs.length !== 1 ? "s" : ""} for ${name}, ${yearRange(years[0], years[years.length - 1])}.`;

  return {
    title: `${name} - Common Data Set Archive`,
    description,
    alternates: { canonical: path },
    openGraph: { url: path, title: `${name} - Common Data Set Archive`, description },
  };
}

// Italicize a trailing institution-type word ("University", "College", etc.)
// to give the serif headline a bit of editorial rhythm. Keeps the leading
// proper noun in roman; falls back to roman-only for names without a known
// suffix.
function splitInstitutionalSuffix(name: string): {
  head: string;
  tail: string | null;
} {
  const SUFFIXES = [
    "University",
    "College",
    "Institute",
    "Polytechnic",
    "Academy",
    "School",
    "Seminary",
    "Conservatory",
  ];
  for (const s of SUFFIXES) {
    if (name.endsWith(` ${s}`)) {
      return { head: name.slice(0, -s.length - 1), tail: s };
    }
  }
  return { head: name, tail: null };
}

// Ascending step series of the school's archived document count over time.
// Drives the small forest sparkline next to the count. One step per CDS
// year archived; if everything was added at once the line goes flat and
// the sparkline collapses to a baseline (which is fine).
function archiveHistory(docs: ManifestRow[]): number[] {
  const years = docs
    .map((d) => d.canonical_year)
    .filter((y): y is string => y != null)
    .sort();
  if (years.length === 0) return [];
  const series: number[] = [];
  for (let i = 0; i < years.length; i++) series.push(i + 1);
  return series.length === 1 ? [0, 1] : series;
}

export default async function SchoolDetailPage({
  params,
}: {
  params: Promise<{ school_id: string }>;
}) {
  const { school_id } = await params;
  const docs = await fetchSchoolDocuments(school_id);

  if (docs.length === 0) {
    // PRD 015 M4 — directory-only stub. Search now returns Title-IV
    // schools that have no archived CDS yet; clicking those slugs
    // would otherwise hit a 404, contradicting the search promise.
    // If we have a coverage row, render the minimal panel; otherwise
    // genuine 404.
    const coverage = await fetchInstitutionCoverage(school_id);
    if (coverage && coverage.coverage_status !== "out_of_scope") {
      return <DirectoryOnlySchoolPage coverage={coverage} school_id={school_id} />;
    }
    notFound();
  }

  // Every cds_documents row for a school carries the same ipeds_id, so we
  // only need the first one. Scorecard data is per-school-per-vintage, not
  // per-document, so one query returns everything.
  const ipedsId = docs.find((d) => d.ipeds_id)?.ipeds_id ?? null;
  const [scorecard, browserRow, gpaProfile, admissionStrategySchool] = await Promise.all([
    fetchScorecardByIpedsId(ipedsId),
    fetchBrowserRowBySchoolId(school_id),
    fetchAvgGpaBySchoolId(school_id),
    fetchAdmissionStrategyBySchoolId(school_id),
  ]);
  const positioningSchool = browserRow
    ? { ...browserRow, ...gpaProfile }
    : null;

  const name = docs[0].school_name ?? "Unknown school";
  const { head, tail } = splitInstitutionalSuffix(name);
  const years = docs
    .map((d) => d.canonical_year)
    .filter((y): y is string => y != null)
    .sort();

  const hasSubs = docs.some((d) => d.sub_institutional != null);
  const groups: { label: string | null; docs: typeof docs }[] = [];
  if (hasSubs) {
    const subMap = new Map<string | null, typeof docs>();
    for (const doc of docs) {
      const key = doc.sub_institutional;
      const group = subMap.get(key) ?? [];
      group.push(doc);
      subMap.set(key, group);
    }
    for (const [label, groupDocs] of subMap) {
      groups.push({ label, docs: groupDocs });
    }
  } else {
    groups.push({ label: null, docs });
  }

  const schoolUrl = `https://www.collegedata.fyi/schools/${school_id}`;
  const uniqueYears = Array.from(new Set(years));
  const earliestYear = years.length > 0 ? years[0]?.split("-")[0] : null;
  const latestYear =
    years.length > 0 ? years[years.length - 1]?.split("-")[0] : null;

  const jsonLd = [
    {
      "@context": "https://schema.org",
      "@type": "CollegeOrUniversity",
      name,
      url: schoolUrl,
      description: `Common Data Set archive for ${name}. ${docs.length} document${docs.length !== 1 ? "s" : ""} archived${years.length > 0 ? `, ${yearRange(years[0], years[years.length - 1])}` : ""}.`,
    },
    {
      "@context": "https://schema.org",
      "@type": "BreadcrumbList",
      itemListElement: [
        { "@type": "ListItem", position: 1, name: "Schools", item: "https://www.collegedata.fyi/schools" },
        { "@type": "ListItem", position: 2, name, item: schoolUrl },
      ],
    },
    {
      "@context": "https://schema.org",
      "@type": "DataCatalog",
      name: `${name} Common Data Set archive`,
      url: schoolUrl,
      description: `Every archived Common Data Set year for ${name}, keyed to the canonical 1,105-field schema published by the Common Data Set Initiative.`,
      creator: { "@type": "Organization", name, url: schoolUrl },
      provider: { "@type": "Organization", name: "collegedata.fyi", url: "https://www.collegedata.fyi" },
      isAccessibleForFree: true,
      license: "https://opensource.org/licenses/MIT",
      dataset: uniqueYears.map((year) => ({
        "@type": "Dataset",
        name: `${name} Common Data Set ${year}`,
        url: `https://www.collegedata.fyi/schools/${school_id}/${year}`,
        temporalCoverage: year,
      })),
    },
  ];

  const history = archiveHistory(docs);
  const carnegieCode = scorecard?.carnegie_basic;
  const positioningSourceDoc = positioningSchool
    ? docs.find((doc) => doc.canonical_year === positioningSchool.cdsYear) ?? docs[0]
    : null;
  const positioningSourceHref =
    storageUrl(positioningSourceDoc?.source_storage_path ?? null) ??
    positioningSchool?.archiveUrl ??
    null;
  const admissionStrategySourceDoc = admissionStrategySchool
    ? docs.find((doc) => doc.canonical_year === admissionStrategySchool.cdsYear) ?? docs[0]
    : null;
  const admissionStrategySourceHref =
    storageUrl(admissionStrategySourceDoc?.source_storage_path ?? null) ??
    admissionStrategySchool?.archiveUrl ??
    null;

  return (
    <div className="mx-auto max-w-5xl px-4 sm:px-6 py-8">
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{
          __html: JSON.stringify(jsonLd).replace(/</g, "\\u003c"),
        }}
      />

      {/* Header */}
      <header
        className="cd-school-header"
        style={{ paddingTop: 24, paddingBottom: 8 }}
      >
        <div>
          <div
            className="mono"
            style={{
              fontSize: 11,
              color: "var(--ink-3)",
              letterSpacing: "0.08em",
              marginBottom: 12,
              textTransform: "uppercase",
            }}
          >
            <Link
              href="/schools"
              style={{
                color: "var(--ink-3)",
                textDecoration: "none",
              }}
            >
              SCHOOLS
            </Link>{" "}
            / <span style={{ color: "var(--ink)" }}>{name.toUpperCase()}</span>
          </div>
          <h1
            className="serif"
            style={{
              fontWeight: 400,
              fontSize: "clamp(40px, 6vw, 58px)",
              margin: 0,
              letterSpacing: "-0.02em",
              lineHeight: 1,
            }}
          >
            {tail ? (
              <>
                {head} <span style={{ fontStyle: "italic" }}>{tail}</span>
              </>
            ) : (
              name
            )}
          </h1>
          <div
            style={{
              display: "flex",
              flexWrap: "wrap",
              gap: 22,
              marginTop: 16,
              alignItems: "baseline",
              color: "var(--ink-2)",
              fontSize: 14,
            }}
          >
            {ipedsId && (
              <span
                className="mono"
                style={{
                  fontSize: 11.5,
                  color: "var(--ink-3)",
                  letterSpacing: "0.05em",
                }}
              >
                IPEDS {ipedsId}
              </span>
            )}
            {carnegieCode != null && (
              <span
                className="mono"
                style={{
                  fontSize: 11.5,
                  color: "var(--ink-3)",
                  letterSpacing: "0.05em",
                }}
              >
                CARNEGIE {carnegieCode}
              </span>
            )}
          </div>
        </div>

        <div className="cd-school-header__aside">
          <div className="meta cd-school-header__count">
            <span className="cd-school-header__glyph">§</span>
            <span>
              {docs.length} document{docs.length !== 1 ? "s" : ""} archived
            </span>
            {earliestYear && latestYear && earliestYear !== latestYear && (
              <span className="cd-school-header__years">
                {earliestYear}&ndash;{latestYear}
              </span>
            )}
          </div>
          {history.length > 1 && (
            <Sparkline data={history} w={120} h={26} color="var(--forest)" />
          )}
        </div>
      </header>

      <SchoolDocumentsLedger groups={groups} />

      {positioningSchool && (
        <PositioningCard
          school={positioningSchool}
          sourceHref={positioningSourceHref}
        />
      )}

      {admissionStrategySchool && (
        <AdmissionStrategyCard
          school={admissionStrategySchool}
          sourceHref={admissionStrategySourceHref}
        />
      )}

      {scorecard ? (
        <OutcomesSection scorecard={scorecard} />
      ) : ipedsId ? (
        <p
          className="mono"
          style={{
            marginTop: 56,
            fontSize: 12,
            color: "var(--ink-3)",
            letterSpacing: "0.05em",
          }}
        >
          FEDERAL OUTCOMES DATA NOT AVAILABLE FOR THIS INSTITUTION.
        </p>
      ) : null}

      {scorecard && (
        <div style={{ marginTop: 24 }}>
          <ScorecardVintageNote scorecard={scorecard} />
        </div>
      )}
    </div>
  );
}

// PRD 015 M5 — directory-only school page.
//
// Renders for in-scope institution_cds_coverage rows that have no
// cds_documents row yet (typically not_checked, no_public_cds_found,
// source_not_automatically_accessible, verified_absent). The page
// delivers on the search-promised result, gives federal Scorecard
// baseline data so the school still feels first-class, and invites a
// source submission when can_submit_source is true.
//
// M4 originally shipped this as a search-dead-end stub. M5 layers on
// the federal outcomes section + the Formspree-backed submission form.
async function DirectoryOnlySchoolPage({
  coverage,
  school_id,
}: {
  coverage: InstitutionCoverage;
  school_id: string;
}) {
  const scorecard = await fetchScorecardByIpedsId(coverage.ipeds_id);

  const { head, tail } = splitInstitutionalSuffix(coverage.school_name);
  const location = [coverage.city, coverage.state].filter(Boolean).join(", ");
  const lastChecked = coverage.last_checked_at
    ? new Date(coverage.last_checked_at).toLocaleDateString("en-US", {
        month: "long",
        year: "numeric",
      })
    : null;

  const jsonLd = {
    "@context": "https://schema.org",
    "@type": "CollegeOrUniversity",
    name: coverage.school_name,
    url: `https://www.collegedata.fyi/schools/${school_id}`,
    description: coverage.coverage_summary,
  };

  return (
    <div className="mx-auto max-w-5xl px-4 sm:px-6 py-8">
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{
          __html: JSON.stringify(jsonLd).replace(/</g, "\\u003c"),
        }}
      />

      <header style={{ paddingTop: 48, paddingBottom: 32 }}>
        <div className="meta" style={{ marginBottom: 16 }}>
          § Institution directory
        </div>
        <h1
          style={{
            fontFamily: "var(--serif)",
            fontWeight: 400,
            fontSize: "clamp(36px, 5.5vw, 56px)",
            lineHeight: 1.05,
            margin: 0,
            letterSpacing: "-0.02em",
          }}
        >
          {head}
          {tail && (
            <>
              {" "}
              <span style={{ fontStyle: "italic", color: "var(--ink-2)" }}>{tail}</span>
            </>
          )}
        </h1>
        {location && (
          <div
            className="mono"
            style={{ marginTop: 12, fontSize: 13, color: "var(--ink-3)" }}
          >
            {location}
            {coverage.undergraduate_enrollment != null && (
              <span style={{ marginLeft: 16 }}>
                {coverage.undergraduate_enrollment.toLocaleString()} undergraduates
              </span>
            )}
          </div>
        )}
      </header>

      <section
        className="cd-card"
        style={{ padding: "28px 32px", marginTop: 8 }}
      >
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: 12,
            flexWrap: "wrap",
            marginBottom: 16,
          }}
        >
          <CoverageBadge
            status={coverage.coverage_status}
            label={coverage.coverage_label}
          />
          {lastChecked && (
            <span
              className="mono"
              style={{ fontSize: 11, color: "var(--ink-3)", letterSpacing: "0.05em" }}
            >
              LAST CHECKED {lastChecked.toUpperCase()}
            </span>
          )}
        </div>
        <p
          style={{
            margin: 0,
            fontSize: 16,
            lineHeight: 1.55,
            color: "var(--ink)",
            maxWidth: 640,
          }}
        >
          {coverage.coverage_summary}
        </p>
        {coverage.website_url && (
          <p
            className="mono"
            style={{ marginTop: 20, fontSize: 12, color: "var(--ink-3)" }}
          >
            School website:{" "}
            <a
              href={coverage.website_url.startsWith("http")
                ? coverage.website_url
                : `https://${coverage.website_url}`}
              target="_blank"
              rel="noopener noreferrer"
            >
              {coverage.website_url.replace(/^https?:\/\//, "")}
            </a>
          </p>
        )}
      </section>

      {coverage.can_submit_source && (
        <SubmissionForm
          school_id={school_id}
          school_name={coverage.school_name}
          coverage_status={coverage.coverage_status}
        />
      )}

      {scorecard ? (
        <div style={{ marginTop: 56 }}>
          <OutcomesSection scorecard={scorecard} />
        </div>
      ) : (
        <p
          className="mono"
          style={{
            marginTop: 56,
            fontSize: 12,
            color: "var(--ink-3)",
            letterSpacing: "0.05em",
          }}
        >
          FEDERAL OUTCOMES DATA NOT AVAILABLE FOR THIS INSTITUTION.
        </p>
      )}

      {scorecard && (
        <div style={{ marginTop: 24 }}>
          <ScorecardVintageNote scorecard={scorecard} />
        </div>
      )}

      <p
        style={{
          marginTop: 40,
          fontSize: 14,
          color: "var(--ink-3)",
          maxWidth: 640,
        }}
      >
        We track every active, undergraduate-serving Title-IV institution
        and refresh CDS coverage every 15 minutes. Federal data above
        comes from College Scorecard. <Link href="/about">Read the method</Link>.
      </p>
    </div>
  );
}
