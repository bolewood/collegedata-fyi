import type { Metadata } from "next";
import Link from "next/link";
import { ScholarshipIndex } from "@/components/ScholarshipIndex";
import { fetchScholarshipIndex } from "@/lib/scholarships-data";
import {
  CONTROL_LABEL,
  SCHOLARSHIP_LICENSE_LINE,
  countProgramsByControl,
  type SchoolControl,
} from "@/lib/scholarships";

export const revalidate = 3600;

export const metadata: Metadata = {
  title: "Scholarship programs",
  description:
    "A partial, hand-built list of named merit scholarships at U.S. colleges, each linked to the school's own page and dated. Not a ranking and not an estimate of your award.",
  alternates: { canonical: "/scholarships" },
  openGraph: { url: "/scholarships" },
};

export default async function ScholarshipsPage() {
  const { rows, controls } = await fetchScholarshipIndex();
  const programCount = new Set(rows.map((r) => r.program_id)).size;
  const schoolCount = new Set(rows.map((r) => r.school_id)).size;
  const byType = countProgramsByControl(rows, (id) => controls[id] ?? "unknown");
  const typeRows = (Object.keys(CONTROL_LABEL) as SchoolControl[]).filter((k) => byType[k] > 0);

  return (
    <div className="mx-auto max-w-6xl px-4 sm:px-6 py-8">
      <header style={{ paddingTop: 32, paddingBottom: 24 }}>
        <div className="meta" style={{ marginBottom: 12 }}>§ Scholarships</div>
        <h1
          style={{
            fontFamily: "var(--serif)",
            fontWeight: 400,
            fontSize: "clamp(36px, 5vw, 56px)",
            lineHeight: 1.05,
            margin: 0,
            letterSpacing: "-0.02em",
          }}
        >
          Named scholarships,{" "}
          <span style={{ fontStyle: "italic", color: "var(--forest-ink)" }}>as the schools published them.</span>
        </h1>
        <p
          className="serif"
          style={{ marginTop: 18, fontSize: 18, fontStyle: "italic", lineHeight: 1.55, color: "var(--ink-2)", maxWidth: 720 }}
        >
          This is a partial, hand-built list. A school that is not here has not been documented yet, which is
          different from having no named scholarships. Every program links to the school&rsquo;s own page.
        </p>
        <p className="mono" style={{ marginTop: 14, fontSize: 12, color: "var(--ink-3)" }}>
          {programCount} {programCount === 1 ? "program" : "programs"} at {schoolCount}{" "}
          {schoolCount === 1 ? "school" : "schools"} ·{" "}
          <Link href="/methodology/scholarships">Method</Link> ·{" "}
          <Link href="/methodology/scholarships#reuse">How to cite</Link>
        </p>
      </header>

      {typeRows.length > 0 ? (
        <section className="sch-types" aria-label="Programs by school type">
          <div className="meta">§ By school type</div>
          <ul className="sch-types__list">
            {typeRows.map((k) => (
              <li key={k}>
                <span className="serif stat-num sch-types__n">{byType[k]}</span>
                <span className="mono sch-types__label">{CONTROL_LABEL[k]}</span>
              </li>
            ))}
          </ul>
          <p className="sch-fine">
            Counted once per program, by its lead school. This list leans toward selective schools; it is not a
            sample of all colleges.
          </p>
        </section>
      ) : null}

      <ScholarshipIndex rows={rows} />

      <p className="sch-fine mono" style={{ marginTop: 28 }}>
        The data is open. Download or query it; credit is requested. See{" "}
        <Link href="/methodology/scholarships#reuse">Reuse and credit</Link> and <Link href="/api">the API</Link>.{" "}
        {SCHOLARSHIP_LICENSE_LINE.replace(" how to cite", "")}{" "}
        <Link href="/methodology/scholarships#reuse">how to cite</Link>
      </p>
    </div>
  );
}
