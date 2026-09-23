import type { Metadata } from "next";
import Link from "next/link";
import { notFound, permanentRedirect } from "next/navigation";
import { fetchCanonicalSchoolId, fetchSchoolBrandColors } from "@/lib/queries";
import { fetchAcceptanceHistory } from "@/lib/acceptance-history-data";
import {
  acceptancePageDecision,
  acceptanceRatePath,
  acceptanceRobots,
  headerAccentReadable,
  isAcceptancePilotSchool,
} from "@/lib/acceptance-pilot";
import {
  KICKER,
  acceptanceDescription,
  acceptanceTitle,
  degradedNote,
  leadSentences,
  relatedLinks,
  sectionHeading,
  sourceNote,
  spanLabel,
} from "@/lib/acceptance-rate-copy";
import { deriveInks } from "@/lib/derive-inks";
import { SchoolGlyph } from "@/components/SchoolGlyph";
import { AcceptanceRateTable, acceptanceTableRows } from "@/components/AcceptanceRateTable";
import { AcceptanceRateChart } from "@/components/AcceptanceRateChart";

export const revalidate = 3600;

type Params = { school_id: string };

const SITE = "https://www.collegedata.fyi";

async function loadServedPage(schoolId: string) {
  if (!isAcceptancePilotSchool(schoolId)) return null;
  const { schoolName, documents, history } = await fetchAcceptanceHistory(schoolId);
  const decision = acceptancePageDecision(schoolId, history);
  if (decision.kind === "not-found" || !schoolName) return null;
  return { schoolName, documents, history, decision };
}

export async function generateMetadata({
  params,
}: {
  params: Promise<Params>;
}): Promise<Metadata> {
  const { school_id } = await params;
  const schoolId = (await fetchCanonicalSchoolId(school_id)) ?? school_id;
  const page = await loadServedPage(schoolId);
  if (!page) return { title: "Page not found", robots: { index: false, follow: true } };

  const path = acceptanceRatePath(schoolId);
  const title = acceptanceTitle(page.schoolName, page.history);
  const description = acceptanceDescription(page.schoolName, page.history);
  return {
    title,
    description,
    alternates: { canonical: path },
    robots: acceptanceRobots(),
    openGraph: { url: path, title, description },
  };
}

export default async function AcceptanceRatePage({ params }: { params: Promise<Params> }) {
  const { school_id } = await params;
  const canonicalSchoolId = await fetchCanonicalSchoolId(school_id);
  if (canonicalSchoolId && canonicalSchoolId !== school_id) {
    permanentRedirect(acceptanceRatePath(canonicalSchoolId));
  }
  const [page, brandColors] = await Promise.all([
    loadServedPage(school_id),
    isAcceptancePilotSchool(school_id) ? fetchSchoolBrandColors(school_id) : null,
  ]);
  if (!page) notFound();

  const { schoolName, history, documents, decision } = page;
  const rows = acceptanceTableRows(history, documents);
  const lead = leadSentences(schoolName, history).join(" ");
  const latest = history.years[0];
  const hubPath = `/schools/${school_id}`;
  const pageUrl = `${SITE}${acceptanceRatePath(school_id)}`;
  const span = spanLabel(history);
  const related = relatedLinks(schoolName, latest?.year ?? null);
  const accentReadable = headerAccentReadable(deriveInks(brandColors));

  const jsonLd = {
    "@context": "https://schema.org",
    "@type": "BreadcrumbList",
    itemListElement: [
      { "@type": "ListItem", position: 1, name: "Schools", item: `${SITE}/schools` },
      { "@type": "ListItem", position: 2, name: schoolName, item: `${SITE}${hubPath}` },
      { "@type": "ListItem", position: 3, name: "Acceptance rate", item: pageUrl },
    ],
  };

  return (
    <div className="mx-auto max-w-5xl px-4 sm:px-6 py-8">
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd).replace(/</g, "\\u003c") }}
      />
      <header className="cd-school-header" data-accent={accentReadable ? "ink-b" : "paper"}>
        <div>
          <nav
            aria-label="Breadcrumb"
            className="mono"
            style={{ fontSize: 11, letterSpacing: "0.08em", textTransform: "uppercase", marginBottom: 12 }}
          >
            <Link href="/schools">Schools</Link>
            {" / "}
            <span className="school-crumb-with-glyph">
              <SchoolGlyph size="lg" brandColors={brandColors} />
              <Link href={hubPath}>{schoolName}</Link>
            </span>
            {" / "}
            <span aria-current="page">Acceptance rate</span>
          </nav>
          <div className="meta" style={{ marginBottom: 12 }}>
            {KICKER}
          </div>
          <h1
            className="serif"
            style={{
              fontWeight: 400,
              fontSize: "clamp(36px, 5.5vw, 54px)",
              margin: 0,
              letterSpacing: "-0.02em",
              lineHeight: 1.02,
            }}
          >
            {schoolName} <span style={{ fontStyle: "italic" }}>acceptance rate</span>
          </h1>
          <div className="cd-archive-lead acc-lead">
            {lead ? <p>{lead}</p> : null}
            {decision.kind === "serve-degraded" ? <p>{degradedNote()}</p> : null}
          </div>
        </div>
        {span ? (
          <div className="cd-school-header__aside">
            <div className="meta cd-school-header__count">{span}</div>
          </div>
        ) : null}
      </header>

      <section aria-labelledby="acceptance-by-year" className="acc-section">
        <h2 id="acceptance-by-year" className="serif acc-section__title">
          {sectionHeading(schoolName, history)}
        </h2>
        <AcceptanceRateChart schoolName={schoolName} rows={rows} />
        <AcceptanceRateTable schoolId={school_id} schoolName={schoolName} rows={rows} />
        <p className="acc-note">{sourceNote(schoolName)}</p>
      </section>

      <nav aria-label={`More on ${schoolName}`} className="acc-related">
        <Link href={hubPath}>{related.hub}</Link>
        {latest && related.latest ? (
          <Link href={`/schools/${school_id}/${latest.year}`}>{related.latest}</Link>
        ) : null}
      </nav>
    </div>
  );
}
