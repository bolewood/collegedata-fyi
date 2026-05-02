import type { Metadata } from "next";
import Link from "next/link";
import type { ReactNode } from "react";

const BASE = "https://api.collegedata.fyi";
const ANON_KEY =
  "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImlzZHV3bXlndm1kb3pocHZ6YWl4Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzYxMDk3NTksImV4cCI6MjA5MTY4NTc1OX0.fYZOIHyrOWzidgc-CVxWCY5Fe9pQk12-6YjDIS6y9qs";

export const metadata: Metadata = {
  title: "Academic Positioning Methodology",
  description:
    "How collegedata.fyi compares student scores to a school's published Common Data Set admitted-class bands.",
  alternates: { canonical: "/methodology/positioning" },
  openGraph: { url: "/methodology/positioning" },
};

function CodeBlock({ children }: { children: string }) {
  return (
    <pre className="overflow-x-auto border border-[var(--rule)] bg-[#faf6ec] px-4 py-3 text-xs leading-relaxed">
      <code>{children}</code>
    </pre>
  );
}

function FieldUse({
  field,
  title,
  children,
}: {
  field: string;
  title: string;
  children: ReactNode;
}) {
  return (
    <section className="border-t border-[var(--rule)] py-5">
      <div className="meta">§ {field}</div>
      <h2 className="serif mt-2 text-2xl leading-tight">{title}</h2>
      <div className="mt-2 text-sm leading-relaxed text-[var(--ink-2)]">{children}</div>
    </section>
  );
}

export default function PositioningMethodologyPage() {
  return (
    <main className="mx-auto max-w-3xl px-4 py-12 sm:px-6">
      <div className="meta">§ Methodology</div>
      <h1 className="serif mt-3 text-5xl leading-none">Academic positioning</h1>
      <p className="mt-5 text-lg leading-relaxed text-[var(--ink-2)]">
        This page shows where your scores would land in a school&apos;s admitted-class
        numbers. It is not a chance-me, and it does not predict admissions decisions.
      </p>

      <section className="mt-10">
        <h2 className="serif text-3xl">What we use</h2>
        <div className="mt-4">
          <FieldUse field="C.7" title="Relative importance of admission factors">
            We use C.7 as context only. If a school marks test scores or GPA as not
            considered, the positioning card still shows published bands when available,
            but the methodology treats them as descriptive data rather than decision weights.
          </FieldUse>
          <FieldUse field="C.8" title="Test policies and score-use context">
            We use C.8 to frame whether score bands represent all admitted students or only
            the subset who submitted scores. At test-optional schools, the card repeats the
            submitter-only caveat inline with the SAT and ACT ranges.
          </FieldUse>
          <FieldUse field="C.9" title="SAT and ACT score bands">
            C.9 provides the 25th, 50th, and 75th percentile anchors. For Bowdoin College,
            the 2025-26 CDS row in our public API reports SAT composite 1470 / 1510 / 1540,
            with 34.76% of enrolled first-year students submitting SAT scores. A student
            SAT of 1500 is therefore inside the published middle 50%, not a prediction of
            admission.
          </FieldUse>
          <FieldUse field="C.11" title="High-school class rank">
            C.11 can describe class-rank distribution where schools publish it. v1 does not
            score rank because many schools omit rank or receive it from too small a subset
            of applicants to compare responsibly across institutions.
          </FieldUse>
          <FieldUse field="C.12" title="High-school GPA">
            C.12 provides average high-school GPA and the percent submitting GPA. v1 displays
            the school average beside your entered GPA, but GPA never contributes to a tier
            because weighted and unweighted scales are not consistently documented.
          </FieldUse>
          <FieldUse field="C.1 / C.2" title="Applicant, admitted, and enrolled counts">
            C.1 and C.2 supply applicant and admit counts. The serving layer derives admit
            rate as admitted divided by applied, then stores that rate as a fraction from
            0 to 1 in <code>school_browser_rows</code>.
          </FieldUse>
        </div>
      </section>

      <section className="mt-10">
        <h2 className="serif text-3xl">What we don&apos;t use</h2>
        <ul className="mt-4 grid gap-3 text-sm leading-relaxed text-[var(--ink-2)]">
          <li>Legacy status, because CDS does not publish it as a score-band adjustment.</li>
          <li>Athletic recruitment, because recruited-athlete admissions pools are not separated in CDS C.9.</li>
          <li>Geographic balance, because CDS does not publish state or region score bands.</li>
          <li>Demonstrated interest, because C.7 is school-level policy context, not an applicant-level measurement.</li>
          <li>Intended major, because CDS does not publish major-level academic bands.</li>
          <li>In-state and out-of-state stratification, because most CDS files do not split C.9 by residency.</li>
          <li>Essays, recommendations, and timing, because those are not machine-readable CDS percentile fields.</li>
        </ul>
      </section>

      <section className="mt-10 border-t border-[var(--rule-strong)] pt-6">
        <h2 className="serif text-3xl">Why this isn&apos;t a chance-me</h2>
        <p className="mt-4 text-sm leading-relaxed text-[var(--ink-2)]">
          A position compares your numbers with published admitted-class bands. A
          prediction estimates the probability that an applicant with many hidden traits
          will be admitted. The Common Data Set supports the first task and does not
          support the second.
        </p>
        <p className="mt-3 text-sm leading-relaxed text-[var(--ink-2)]">
          Test-optional reporting makes the distinction sharper. A school can publish a
          high SAT middle 50% while only a minority of enrolled students submitted SAT
          scores. That means the range describes submitters, not the full admitted class.
        </p>
        <p className="mt-3 text-sm leading-relaxed text-[var(--ink-2)]">
          Selective admissions also include institutional priorities that are absent from
          CDS. When an admit rate is under 15% and a score is inside the middle 50%, the
          card suppresses the tier label because a small numeric edge would overstate what
          the public data can say.
        </p>
        <p className="mt-3 text-sm leading-relaxed text-[var(--ink-2)]">
          Current cards read 2024-25 or newer CDS rows. If a future card uses a CDS
          year more than three years old, the scoring result carries a stale-data caveat.
        </p>
      </section>

      <section className="mt-10 border-t border-[var(--rule-strong)] pt-6">
        <h2 className="serif text-3xl">Sources and audit trail</h2>
        <p className="mt-4 text-sm leading-relaxed text-[var(--ink-2)]">
          Every card links back to the archived CDS source for that school year. The
          worked example above uses{" "}
          <Link href="/schools/bowdoin/2025-26">Bowdoin College&apos;s 2025-26 archived CDS</Link>
          {" "}and the public <code>school_browser_rows</code> serving table.
        </p>
        <CodeBlock>{`curl '${BASE}/rest/v1/school_browser_rows?school_id=eq.bowdoin&select=school_id,school_name,canonical_year,acceptance_rate,sat_submit_rate,act_submit_rate,sat_composite_p25,sat_composite_p50,sat_composite_p75,act_composite_p25,act_composite_p50,act_composite_p75' \\
  -H 'apikey: ${ANON_KEY.slice(0, 24)}...' \\
  -H 'Authorization: Bearer ${ANON_KEY.slice(0, 24)}...'`}</CodeBlock>
        <p className="mt-3 text-sm leading-relaxed text-[var(--ink-2)]">
          The endpoint is the same public PostgREST resource documented on the{" "}
          <Link href="/api">API page</Link>; PRD 016 does not add a new API resource.
        </p>
      </section>
    </main>
  );
}
