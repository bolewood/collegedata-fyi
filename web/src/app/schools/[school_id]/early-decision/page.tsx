import type { Metadata } from "next";
import Link from "next/link";
import { notFound, permanentRedirect } from "next/navigation";
import { fetchCanonicalSchoolId, fetchSchoolBrandColors } from "@/lib/queries";
import { fetchAcceptanceHistory } from "@/lib/acceptance-history-data";
import { asEdSeries, latestOwnEdNote } from "@/lib/acceptance-history";
import {
  earlyDecisionPageDecision,
  earlyDecisionPath,
  earlyDecisionRobots,
  isEarlyDecisionSchool,
} from "@/lib/early-decision-pilot";
import { gpaPageDecision, gpaPath } from "@/lib/gpa-pilot";
import { headerAccentReadable } from "@/lib/acceptance-pilot";
import { acceptanceRatePath } from "@/lib/acceptance-pilot";
import {
  ED_KICKER,
  earlyDecisionDescription,
  earlyDecisionHeading,
  earlyDecisionNoteAttribution,
  earlyDecisionSourceNote,
  earlyDecisionTitle,
  edLeadSentences,
  possessive,
} from "@/lib/early-decision-copy";
import { degradedNote, relatedLinks } from "@/lib/acceptance-rate-copy";
import { deriveInks } from "@/lib/derive-inks";
import { SchoolGlyph } from "@/components/SchoolGlyph";
import { AcceptanceRateChart } from "@/components/AcceptanceRateChart";
import { acceptanceTableRows } from "@/components/AcceptanceRateTable";
import { EarlyDecisionTable } from "@/components/EarlyDecisionTable";

export const revalidate = 3600;

type Params = { school_id: string };

const SITE = "https://www.collegedata.fyi";

async function loadServedPage(schoolId: string) {
  if (!isEarlyDecisionSchool(schoolId)) return null;
  const { schoolName, documents, history, gpa } = await fetchAcceptanceHistory(schoolId);
  const decision = earlyDecisionPageDecision(schoolId, history);
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

  const path = earlyDecisionPath(schoolId);
  const title = earlyDecisionTitle(page.schoolName, page.history);
  const description = earlyDecisionDescription(page.schoolName, page.history);
  return {
    title,
    description,
    alternates: { canonical: path },
    robots: earlyDecisionRobots(),
    openGraph: { url: path, title, description },
  };
}

export default async function EarlyDecisionPage({ params }: { params: Promise<Params> }) {
  const { school_id } = await params;
  const canonicalSchoolId = await fetchCanonicalSchoolId(school_id);
  if (canonicalSchoolId && canonicalSchoolId !== school_id) {
    permanentRedirect(earlyDecisionPath(canonicalSchoolId));
  }
  const [page, brandColors] = await Promise.all([
    loadServedPage(school_id),
    isEarlyDecisionSchool(school_id) ? fetchSchoolBrandColors(school_id) : null,
  ]);
  if (!page) notFound();

  const { schoolName, history, gpa, documents, decision } = page;
  const series = asEdSeries(history);
  const rows = acceptanceTableRows(series, documents);
  const reportYears = new Set(
    documents.filter((doc) => doc.sub_institutional == null).map((doc) => doc.canonical_year ?? ""),
  );
  const lead = edLeadSentences(schoolName, history, reportYears).join(" ");
  const latest = series.years[0];
  const hubPath = `/schools/${school_id}`;
  const pageUrl = `${SITE}${earlyDecisionPath(school_id)}`;
  const related = relatedLinks(schoolName, latest?.year ?? null);
  const ownNote = latestOwnEdNote(history);
  const accentReadable = headerAccentReadable(deriveInks(brandColors));

  const jsonLd = {
    "@context": "https://schema.org",
    "@type": "BreadcrumbList",
    itemListElement: [
      { "@type": "ListItem", position: 1, name: "Schools", item: `${SITE}/schools` },
      { "@type": "ListItem", position: 2, name: schoolName, item: `${SITE}${hubPath}` },
      { "@type": "ListItem", position: 3, name: "Early decision", item: pageUrl },
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
            <span aria-current="page">Early decision</span>
          </nav>
          <div className="meta" style={{ marginBottom: 12 }}>
            {ED_KICKER}
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
            <span style={{ fontStyle: "italic" }}>early decision acceptance rate</span>
          </h1>
          <div className="cd-archive-lead acc-lead">
            {lead ? <p>{lead}</p> : null}
            {decision.kind === "serve-degraded" ? <p>{degradedNote()}</p> : null}
          </div>
        </div>
      </header>

      <section aria-labelledby="early-decision-by-year" className="acc-section">
        <h2 id="early-decision-by-year" className="serif acc-section__title">
          {earlyDecisionHeading(schoolName, history)}
        </h2>
        <AcceptanceRateChart schoolName={schoolName} rows={rows} series="early-decision" />
        <EarlyDecisionTable schoolId={school_id} schoolName={schoolName} rows={rows} />
        {ownNote ? (
          <aside className="acc-ed-note">
            <p className="acc-ed-note__from">{earlyDecisionNoteAttribution(ownNote.year)}</p>
            <p>{ownNote.note}</p>
          </aside>
        ) : null}
        <p className="acc-note">{earlyDecisionSourceNote(schoolName)}</p>
      </section>

      <nav aria-label={`More on ${schoolName}`} className="acc-related">
        <Link href={hubPath}>{related.hub}</Link>
        <Link href={acceptanceRatePath(school_id)}>{possessive(schoolName)} acceptance rate</Link>
        {gpaPageDecision(school_id, gpa).kind !== "not-found" ? (
          <Link href={gpaPath(school_id)}>{possessive(schoolName)} enrolled first-year GPA</Link>
        ) : null}
        {latest && related.latest ? (
          <Link href={`/schools/${school_id}/${latest.year}`}>{related.latest}</Link>
        ) : null}
      </nav>
    </div>
  );
}
