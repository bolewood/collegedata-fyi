import type { Metadata } from "next";
import { notFound } from "next/navigation";
import Link from "next/link";
import {
  fetchSchoolDocuments,
  fetchScorecardByIpedsId,
} from "@/lib/queries";
import { DocumentCard } from "@/components/DocumentCard";
import { OutcomesSection } from "@/components/OutcomesSection";
import { ScorecardVintageNote } from "@/components/ScorecardVintageNote";
import { Sparkline } from "@/components/Sparkline";
import { yearRange } from "@/lib/format";
import type { ManifestRow } from "@/lib/types";

export const revalidate = 3600;

export async function generateMetadata({
  params,
}: {
  params: Promise<{ school_id: string }>;
}): Promise<Metadata> {
  const { school_id } = await params;
  const docs = await fetchSchoolDocuments(school_id);
  if (docs.length === 0) return { title: "School Not Found" };

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
    notFound();
  }

  // Every cds_documents row for a school carries the same ipeds_id, so we
  // only need the first one. Scorecard data is per-school-per-vintage, not
  // per-document, so one query returns everything.
  const ipedsId = docs.find((d) => d.ipeds_id)?.ipeds_id ?? null;
  const scorecard = await fetchScorecardByIpedsId(ipedsId);

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
        style={{
          display: "grid",
          gridTemplateColumns: "1fr auto",
          gap: 32,
          alignItems: "end",
          paddingTop: 24,
          paddingBottom: 8,
        }}
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

        <div style={{ textAlign: "right" }}>
          <div className="meta" style={{ marginBottom: 6 }}>
            § {docs.length} document{docs.length !== 1 ? "s" : ""} archived
            {earliestYear && latestYear && earliestYear !== latestYear && (
              <> · {earliestYear} – {latestYear}</>
            )}
          </div>
          {history.length > 1 && (
            <Sparkline data={history} w={120} h={26} color="var(--forest)" />
          )}
        </div>
      </header>

      {/* Documents ledger */}
      <div className="rule-2" style={{ marginTop: 32, paddingTop: 20 }}>
        {groups.map((group, gi) => (
          <div key={group.label ?? "main"}>
            {group.label && (
              <h2
                className="serif"
                style={{
                  fontSize: 18,
                  margin: gi === 0 ? "0 0 8px" : "16px 0 8px",
                  letterSpacing: "-0.005em",
                }}
              >
                {group.label}
              </h2>
            )}
            {group.docs.map((doc, i) => (
              <DocumentCard
                key={doc.document_id}
                doc={doc}
                isLast={
                  gi === groups.length - 1 && i === group.docs.length - 1
                }
              />
            ))}
          </div>
        ))}
      </div>

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
