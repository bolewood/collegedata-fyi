import type { Metadata } from "next";
import { notFound, permanentRedirect } from "next/navigation";
import Link from "next/link";
import {
  fetchSchoolDocuments,
  fetchScorecardByIpedsId,
  fetchInstitutionCoverage,
  fetchBrowserRowBySchoolId,
  fetchAvgGpaBySchoolId,
  fetchAdmissionStrategyBySchoolId,
  fetchMeritProfileBySchoolId,
  fetchChangeEventsBySchoolId,
  fetchSchoolFederalFacts,
  fetchCanonicalSchoolId,
  fetchSchoolBrandColors,
} from "@/lib/queries";
import { OutcomesSection } from "@/components/OutcomesSection";
import { PositioningCard } from "@/components/PositioningCard";
import { AdmissionStrategyCard } from "@/components/AdmissionStrategyCard";
import { MeritProfileCard } from "@/components/MeritProfileCard";
import { WhatChangedCard } from "@/components/WhatChangedCard";
import { SchoolDocumentsLedger } from "@/components/SchoolDocumentsLedger";
import { ScorecardVintageNote } from "@/components/ScorecardVintageNote";
import { Sparkline } from "@/components/Sparkline";
import { CoverageBadge } from "@/components/CoverageBadge";
import { SubmissionForm } from "@/components/SubmissionForm";
import { FederalBaselineTable } from "@/components/FederalBaselineTable";
import { isCanonicalCdsYear, storageUrl, yearRange } from "@/lib/format";
import { archiveLead, directoryOnlyLead } from "@/lib/archive-lead";
import { ArchiveLead } from "@/components/ArchiveLead";
import { SchoolGlyph } from "@/components/SchoolGlyph";
import type { ManifestRow, InstitutionCoverage } from "@/lib/types";

export const revalidate = 3600;

export async function generateMetadata({
  params,
}: {
  params: Promise<{ school_id: string }>;
}): Promise<Metadata> {
  const { school_id } = await params;
  const resolvedSchoolId = (await fetchCanonicalSchoolId(school_id)) ?? school_id;
  const docs = await fetchSchoolDocuments(resolvedSchoolId);
  if (docs.length === 0) {
    // PRD 015 M4 — directory-only schools render a coverage stub.
    // Title reflects the school name (not "Not Found") so the browser
    // tab and OG share match what the user sees.
    const coverage = await fetchInstitutionCoverage(resolvedSchoolId);
    if (coverage) {
      const path = `/schools/${resolvedSchoolId}`;
      const title = `${coverage.school_name} Common Data Set`;
      const description = `We haven’t found a Common Data Set from this school. ${coverage.coverage_summary}`;
      return {
        title,
        description,
        alternates: { canonical: path },
        robots: { index: false, follow: true },
        openGraph: {
          url: path,
          title,
          description,
        },
      };
    }
    return { title: "School Not Found" };
  }

  const name = docs[0].school_name;
  const years = docs
    .map((d) => d.canonical_year)
    .filter(isCanonicalCdsYear)
    .sort();
  const path = `/schools/${resolvedSchoolId}`;
  const yearsOnFile = years.length > 0 ? yearRange(years[0], years[years.length - 1]) : "none";
  const description =
    `${name} Common Data Set — the yearly report the college publishes on admissions, cost, and aid, plus federal numbers. Years on file: ${yearsOnFile}. Download the original file.`;
  const title = `${name} Common Data Set`;

  return {
    title,
    description,
    alternates: {
      canonical: path,
      types: {
        "application/rss+xml": `/schools/${resolvedSchoolId}/feed.xml`,
      },
    },
    openGraph: { url: path, title, description },
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

function formatLocation(
  source: Pick<InstitutionCoverage, "city" | "state"> | null | undefined,
): string | null {
  if (!source) return null;
  const parts = [source.city, source.state].filter(Boolean);
  return parts.length > 0 ? parts.join(", ") : null;
}

// Ascending step series of the school's archived document count over time.
// Drives the small forest sparkline next to the count. One step per CDS
// year archived; if everything was added at once the line goes flat and
// the sparkline collapses to a baseline (which is fine).
function archiveHistory(docs: ManifestRow[]): number[] {
  const years = docs
    .map((d) => d.canonical_year)
    .filter(isCanonicalCdsYear)
    .sort();
  if (years.length === 0) return [];
  const series: number[] = [];
  for (let i = 0; i < years.length; i++) series.push(i + 1);
  return series.length === 1 ? [0, 1] : series;
}

export default async function SchoolDetailPage({ params }: {
  params: Promise<{ school_id: string }>;
}) {
  const { school_id } = await params;
  const canonicalSchoolId = await fetchCanonicalSchoolId(school_id);
  if (canonicalSchoolId && canonicalSchoolId !== school_id) {
    permanentRedirect(`/schools/${canonicalSchoolId}`);
  }
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
  const [
    scorecard,
    browserRow,
    gpaProfile,
    admissionStrategySchool,
    meritProfile,
    changeEvents,
    coverage,
    federalFacts,
    brandColors,
  ] = await Promise.all([
    fetchScorecardByIpedsId(ipedsId),
    fetchBrowserRowBySchoolId(school_id),
    fetchAvgGpaBySchoolId(school_id),
    fetchAdmissionStrategyBySchoolId(school_id),
    fetchMeritProfileBySchoolId(school_id),
    fetchChangeEventsBySchoolId(school_id),
    fetchInstitutionCoverage(school_id),
    fetchSchoolFederalFacts(school_id),
    fetchSchoolBrandColors(school_id),
  ]);
  const positioningSchool = browserRow
    ? { ...browserRow, ...gpaProfile }
    : null;

  const name = docs[0].school_name ?? "Unknown school";
  const { head, tail } = splitInstitutionalSuffix(name);
  const location = formatLocation(coverage);
  const years = docs
    .map((d) => d.canonical_year)
    .filter(isCanonicalCdsYear)
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
      description: `${docs.length} Common Data Set report${docs.length !== 1 ? "s" : ""} for ${name}${years.length > 0 ? `, ${yearRange(years[0], years[years.length - 1])}` : ""}.`,
      ...(coverage?.city || coverage?.state
        ? {
            address: {
              "@type": "PostalAddress",
              addressLocality: coverage.city ?? undefined,
              addressRegion: coverage.state ?? undefined,
            },
          }
        : {}),
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
      name: `${name} Common Data Set`,
      url: schoolUrl,
      description: `Every Common Data Set year we have for ${name}, as the school published it.`,
      creator: { "@type": "Organization", name, url: schoolUrl },
      provider: { "@type": "Organization", name: "collegedata.fyi", url: "https://www.collegedata.fyi" },
      isAccessibleForFree: true,
      license: "https://opensource.org/licenses/MIT",
      dataset: uniqueYears.map((year) => ({
        "@type": "Dataset",
        name: `${name} Common Data Set ${year}`,
        description: `Common Data Set ${year} for ${name}: admissions, cost, and aid as the school published them.`,
        url: `https://www.collegedata.fyi/schools/${school_id}/${year}`,
        creator: { "@type": "Organization", name },
        provider: { "@type": "Organization", name: "collegedata.fyi", url: "https://www.collegedata.fyi" },
        temporalCoverage: year,
        license: "https://opensource.org/licenses/MIT",
        isAccessibleForFree: true,
      })),
    },
  ];

  const history = archiveHistory(docs);
  const schoolLead = archiveLead({
    schoolId: school_id,
    schoolName: name,
    ipedsId,
    documents: docs,
  });
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
  const meritProfileSourceDoc = meritProfile
    ? docs.find((doc) => doc.canonical_year === meritProfile.cdsYear) ?? docs[0]
    : null;
  const meritProfileSourceHref =
    storageUrl(meritProfileSourceDoc?.source_storage_path ?? null) ??
    meritProfile?.archiveUrl ??
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
      <header className="cd-school-header">
        <div>
          <div
            className="mono"
            style={{
              fontSize: 11,
              letterSpacing: "0.08em",
              marginBottom: 12,
              textTransform: "uppercase",
            }}
          >
            <Link href="/schools" style={{ textDecoration: "none" }}>
              SCHOOLS
            </Link>{" "}
            /{" "}
            <span className="school-crumb-with-glyph">
              <SchoolGlyph size="lg" brandColors={brandColors} />
              <span>{name.toUpperCase()}</span>
            </span>
          </div>
          <div className="meta" style={{ marginBottom: 12 }}>
            Common Data Set
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
          {schoolLead ? <ArchiveLead lead={schoolLead} showHeading={false} /> : null}
          <div
            style={{
              display: "flex",
              flexWrap: "wrap",
              gap: 22,
              marginTop: 16,
              alignItems: "baseline",
              fontSize: 14,
            }}
          >
            {location && (
              <span
                className="mono"
                style={{
                  fontSize: 11.5,
                  letterSpacing: "0.05em",
                }}
              >
                {location.toUpperCase()}
              </span>
            )}
            {ipedsId && (
              <span
                className="mono"
                style={{
                  fontSize: 11.5,
                  letterSpacing: "0.05em",
                }}
              >
                IPEDS {ipedsId}
              </span>
            )}
            {carnegieCode != null && (
              <span
                className="mono"
                title="Federal College Scorecard Carnegie basic classification code"
                style={{
                  fontSize: 11.5,
                  letterSpacing: "0.05em",
                }}
              >
                CARNEGIE CLASS {carnegieCode}
              </span>
            )}
          </div>
        </div>

        <div className="cd-school-header__aside">
          <div className="meta cd-school-header__count">
            <span className="cd-school-header__glyph">§</span>
            <span>
              {docs.length} report{docs.length !== 1 ? "s" : ""}
            </span>
            {earliestYear && latestYear && earliestYear !== latestYear && (
              <span className="cd-school-header__years">
                {earliestYear}&ndash;{latestYear}
              </span>
            )}
          </div>
          {history.length > 1 && (
            <Sparkline data={history} w={120} h={26} color="currentColor" />
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

      {meritProfile && (
        <MeritProfileCard
          profile={meritProfile}
          sourceHref={meritProfileSourceHref}
        />
      )}

      <WhatChangedCard events={changeEvents} />

      <FederalBaselineTable facts={federalFacts} />

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
  const [scorecard, federalFacts] = await Promise.all([
    fetchScorecardByIpedsId(coverage.ipeds_id),
    fetchSchoolFederalFacts(school_id),
  ]);

  const { head, tail } = splitInstitutionalSuffix(coverage.school_name);
  const location = formatLocation(coverage);
  const lastChecked = coverage.last_checked_at
    ? new Date(coverage.last_checked_at).toLocaleDateString("en-US", {
        month: "long",
        year: "numeric",
      })
    : null;
  const hasFederal = Boolean(scorecard) || federalFacts.length > 0;
  const lead = directoryOnlyLead(hasFederal);

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

      <header className="cd-school-header">
        <div>
        <div className="meta" style={{ marginBottom: 16 }}>
          Common Data Set
        </div>
        <h1
          className="serif"
          style={{
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
              <span style={{ fontStyle: "italic" }}>{tail}</span>
            </>
          )}
        </h1>
        {location && (
          <div
            className="mono"
            style={{ marginTop: 12, fontSize: 13 }}
          >
            {location}
            {coverage.undergraduate_enrollment != null && (
              <span style={{ marginLeft: 16 }}>
                {coverage.undergraduate_enrollment.toLocaleString()} undergraduates
              </span>
            )}
          </div>
        )}
        </div>
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
          {lead}
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
        {coverage.can_submit_source && (
          <SubmissionForm
            compact
            school_id={school_id}
            school_name={coverage.school_name}
            coverage_status={coverage.coverage_status}
          />
        )}
      </section>

      <FederalBaselineTable facts={federalFacts} compact />

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
        We look for a public report from every U.S. college that takes
        federal student aid. Federal data above comes from NCES/IPEDS and
        College Scorecard when we have it.{" "}
        <Link href="/about">Read the method</Link>.
      </p>
    </div>
  );
}
