import type { Metadata } from "next";
import Link from "next/link";
import { notFound, permanentRedirect } from "next/navigation";
import { fetchCanonicalSchoolId, fetchSchoolBrandColors } from "@/lib/queries";
import { fetchAcceptanceHistory } from "@/lib/acceptance-history-data";
import { earlyDecisionPageDecision, earlyDecisionPath } from "@/lib/early-decision-pilot";
import { gpaPageDecision, gpaPath, gpaRobots, isGpaSchool } from "@/lib/gpa-pilot";
import { headerAccentReadable } from "@/lib/acceptance-pilot";
import { acceptanceRatePath } from "@/lib/acceptance-pilot";
import {
  GPA_KICKER,
  gpaDescription,
  gpaHeading,
  gpaLeadSentences,
  gpaSourceNote,
  gpaTitle,
  possessive,
} from "@/lib/gpa-copy";
import { degradedNote, relatedLinks } from "@/lib/acceptance-rate-copy";
import { deriveInks } from "@/lib/derive-inks";
import { SchoolGlyph } from "@/components/SchoolGlyph";
import { GpaChart } from "@/components/GpaChart";
import { GpaTable, gpaTableRows } from "@/components/GpaTable";

export const revalidate = 3600;

type Params = { school_id: string };

const SITE = "https://www.collegedata.fyi";

async function loadServedPage(schoolId: string) {
  if (!isGpaSchool(schoolId)) return null;
  const { schoolName, documents, history, gpa } = await fetchAcceptanceHistory(schoolId);
  const decision = gpaPageDecision(schoolId, gpa);
  if (decision.kind === "not-found" || !schoolName) return null;
  return { schoolName, documents, history, gpa, decision };
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

  const path = gpaPath(schoolId);
  const title = gpaTitle(page.schoolName, page.gpa);
  const description = gpaDescription(page.schoolName, page.gpa);
  return {
    title,
    description,
    alternates: { canonical: path },
    robots: gpaRobots(),
    openGraph: { url: path, title, description },
  };
}

export default async function GpaPage({ params }: { params: Promise<Params> }) {
  const { school_id } = await params;
  const canonicalSchoolId = await fetchCanonicalSchoolId(school_id);
  if (canonicalSchoolId && canonicalSchoolId !== school_id) {
    permanentRedirect(gpaPath(canonicalSchoolId));
  }
  const [page, brandColors] = await Promise.all([
    loadServedPage(school_id),
    isGpaSchool(school_id) ? fetchSchoolBrandColors(school_id) : null,
  ]);
  if (!page) notFound();

  const { schoolName, gpa, history, documents, decision } = page;
  const rows = gpaTableRows(gpa, documents);
  const reportYears = new Set(
    documents.filter((doc) => doc.sub_institutional == null).map((doc) => doc.canonical_year ?? ""),
  );
  const lead = gpaLeadSentences(schoolName, gpa, reportYears).join(" ");
  const latest = gpa.years[0];
  const hubPath = `/schools/${school_id}`;
  const pageUrl = `${SITE}${gpaPath(school_id)}`;
  const related = relatedLinks(schoolName, latest?.year ?? null);
  const accentReadable = headerAccentReadable(deriveInks(brandColors));

  const jsonLd = {
    "@context": "https://schema.org",
    "@type": "BreadcrumbList",
    itemListElement: [
      { "@type": "ListItem", position: 1, name: "Schools", item: `${SITE}/schools` },
      { "@type": "ListItem", position: 2, name: schoolName, item: `${SITE}${hubPath}` },
      { "@type": "ListItem", position: 3, name: "GPA", item: pageUrl },
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
            <span aria-current="page">GPA</span>
          </nav>
          <div className="meta" style={{ marginBottom: 12 }}>
            {GPA_KICKER}
          </div>
          <h1
            className="serif acc-title"
            style={{
              fontWeight: 400,
              fontSize: "clamp(36px, 5.5vw, 54px)",
              margin: 0,
              letterSpacing: "-0.02em",
              lineHeight: 1.02,
            }}
          >
            <span className="acc-title__name">{schoolName}</span>{" "}
            <span style={{ fontStyle: "italic" }}>enrolled first-year GPA</span>
          </h1>
          <div className="cd-archive-lead acc-lead">
            {lead ? <p>{lead}</p> : null}
            {decision.kind === "serve-degraded" ? <p>{degradedNote()}</p> : null}
          </div>
        </div>
      </header>

      <section aria-labelledby="gpa-by-year" className="acc-section">
        <h2 id="gpa-by-year" className="serif acc-section__title">
          {gpaHeading(schoolName, gpa)}
        </h2>
        <GpaChart schoolName={schoolName} history={gpa} rows={rows} />
        <GpaTable schoolId={school_id} schoolName={schoolName} rows={rows} />
        <p className="acc-note">{gpaSourceNote(schoolName)}</p>
      </section>

      <nav aria-label={`More on ${schoolName}`} className="acc-related">
        <Link href={hubPath}>{related.hub}</Link>
        <Link href={acceptanceRatePath(school_id)}>{possessive(schoolName)} acceptance rate</Link>
        {earlyDecisionPageDecision(school_id, history).kind !== "not-found" ? (
          <Link href={earlyDecisionPath(school_id)}>{possessive(schoolName)} early decision rate</Link>
        ) : null}
        {latest && related.latest ? (
          <Link href={`/schools/${school_id}/${latest.year}`}>{related.latest}</Link>
        ) : null}
      </nav>
    </div>
  );
}
