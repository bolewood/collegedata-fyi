import type { Metadata } from "next";
import Link from "next/link";
import type { ReactNode } from "react";

const BASE = "https://api.collegedata.fyi";
const ANON_KEY =
  "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImlzZHV3bXlndm1kb3pocHZ6YWl4Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzYxMDk3NTksImV4cCI6MjA5MTY4NTc1OX0.fYZOIHyrOWzidgc-CVxWCY5Fe9pQk12-6YjDIS6y9qs";

export const metadata: Metadata = {
  title: "Admission Strategy Methodology",
  description:
    "How collegedata.fyi derives Early Decision, Early Action, yield, wait-list, and admission-factor context from Common Data Set fields.",
  alternates: { canonical: "/methodology/admission-strategy" },
  openGraph: { url: "/methodology/admission-strategy" },
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

export default function AdmissionStrategyMethodologyPage() {
  return (
    <main className="mx-auto max-w-3xl px-4 py-12 sm:px-6">
      <div className="meta">§ Methodology</div>
      <h1 className="serif mt-3 text-5xl leading-none">Admission strategy</h1>
      <p className="mt-5 text-lg leading-relaxed text-[var(--ink-2)]">
        The headline admit rate in most college guides is a weighted average across
        application rounds. This page explains what we surface from the Common Data Set,
        what those numbers mean, and what they do not prove.
      </p>

      <section className="mt-10">
        <h2 className="serif text-3xl">What we use</h2>
        <div className="mt-4">
          <FieldUse field="C.1" title="Total applicants and admits">
            C.1 gives the denominator for the overall admit rate and for residual
            calculations. The card uses applied and admitted counts from the latest
            2024-25 or newer primary CDS row.
          </FieldUse>
          <FieldUse field="C.21" title="Early Decision counts">
            C.21 reports whether the school offers Early Decision and, when present,
            the number of ED applicants and ED admits. We compute ED admit rate as
            admitted divided by applicants. If the school reports a second binding
            deadline, the displayed ED rate is still the combined CDS figure.
          </FieldUse>
          <FieldUse field="C.22" title="Early Action flags">
            C.22 reports whether Early Action is offered and whether it is restrictive.
            It does not publish EA applicant or admit counts, so we do not display an
            EA admit rate. Any EA rate requires a non-CDS source, usually a school press
            release or independent reporting.
          </FieldUse>
          <FieldUse field="C.2" title="Wait-list behavior">
            C.2 reports whether the school has a wait list and, when present, how many
            applicants were offered a spot, accepted the spot, and were admitted. The
            conditional rate, admitted off the wait list divided by accepted wait-list
            spots, is the actionable number; it is still noisy year to year.
          </FieldUse>
          <FieldUse field="C.7" title="Admission-factor importance">
            We surface factors marked Important or Very Important for first-generation
            status, legacy relation, geography, state residency, and demonstrated
            interest. Demonstrated interest is shown beside yield because the two
            signals should be read together.
          </FieldUse>
          <FieldUse field="C.13" title="Application fee and waiver">
            C.13 supplies the application fee and whether fee waivers are available.
            This is an operational planning input, not an admissions-strength signal.
          </FieldUse>
        </div>
      </section>

      <section className="mt-10 border-t border-[var(--rule-strong)] pt-6">
        <h2 className="serif text-3xl">Why "non-early residual"</h2>
        <p className="mt-4 text-sm leading-relaxed text-[var(--ink-2)]">
          We compute the residual as total admits minus ED admits, divided by total
          applicants minus ED applicants. We do not call this the regular-decision admit
          rate because deferred ED applicants can be reviewed later, and schools with EA
          fold applicants into the total without publishing EA counts in CDS.
        </p>
      </section>

      <section className="mt-10 border-t border-[var(--rule-strong)] pt-6">
        <h2 className="serif text-3xl">Read ED rates carefully</h2>
        <p className="mt-4 text-sm leading-relaxed text-[var(--ink-2)]">
          Published ED rates include recruited athletes, legacy applicants, and other
          institutional-priority applicants. We do not estimate a general-pool ED rate
          in v1 because CDS does not separate those applicant groups.
        </p>
        <p className="mt-3 text-sm leading-relaxed text-[var(--ink-2)]">
          For context, the NBER paper{" "}
          <a href="https://www.nber.org/papers/w26316" target="_blank" rel="noopener noreferrer">
            Legacy and Athlete Preferences at Harvard
          </a>{" "}
          documents the admissions weight attached to recruited-athlete and legacy
          preferences in one highly selective setting. That research is not used as
          school-level data on this site; it is methodological context for why the ED
          caveat is displayed inline.
        </p>
      </section>

      <section className="mt-10 border-t border-[var(--rule-strong)] pt-6">
        <h2 className="serif text-3xl">Yield and wait-list interpretation</h2>
        <p className="mt-4 text-sm leading-relaxed text-[var(--ink-2)]">
          Yield is the share of admitted students who enrolled. High yield can mean
          a school is a top-choice destination, or it can mean the school predicts
          interest carefully. When C.7 marks demonstrated interest as Important or
          Very Important, the card makes that connection explicit.
        </p>
        <p className="mt-3 text-sm leading-relaxed text-[var(--ink-2)]">
          Wait-list admits vary heavily by year. A high conditional admit rate in one
          CDS year should be read as a rough historical signal, not a promise about the
          next cycle.
        </p>
      </section>

      <section className="mt-10 border-t border-[var(--rule-strong)] pt-6">
        <h2 className="serif text-3xl">Legal context</h2>
        <p className="mt-4 text-sm leading-relaxed text-[var(--ink-2)]">
          Early Decision is presented by schools as a binding commitment. We take no
          legal position on ED. Readers who want legal context can inspect the public
          docket for{" "}
          <a
            href="https://dockets.justia.com/docket/massachusetts/madce/1%3A2025cv12221/287691"
            target="_blank"
            rel="noopener noreferrer"
          >
            D&apos;Amico et al v. Consortium on Financing Higher Education et al
          </a>
          , filed August 8, 2025 in the District of Massachusetts.
        </p>
      </section>

      <section className="mt-10 border-t border-[var(--rule-strong)] pt-6">
        <h2 className="serif text-3xl">What we do not capture</h2>
        <ul className="mt-4 grid gap-3 text-sm leading-relaxed text-[var(--ink-2)]">
          <li>EA admit rates, because CDS does not publish EA applicant or admit counts.</li>
          <li>ED-1 versus ED-2 count splits, because CDS reports one combined ED figure.</li>
          <li>Likely letters, athletic pre-reads, or informal recruiting channels.</li>
          <li>Major-level, program-level, or residency-stratified admit rates.</li>
          <li>Applicant recommendations. The card surfaces public data; it does not tell anyone where to apply ED.</li>
        </ul>
      </section>

      <section className="mt-10 border-t border-[var(--rule-strong)] pt-6">
        <h2 className="serif text-3xl">Sources and audit trail</h2>
        <p className="mt-4 text-sm leading-relaxed text-[var(--ink-2)]">
          Every school card links to the archived CDS source for the displayed year.
          The public serving table is <code>school_browser_rows</code>; PRD 016B adds
          columns to that resource, not a new API endpoint.
        </p>
        <CodeBlock>{`curl '${BASE}/rest/v1/school_browser_rows?school_id=eq.bowdoin&select=school_id,school_name,canonical_year,applied,admitted,ed_offered,ed_applicants,ed_admitted,ea_offered,ea_restrictive,wait_list_offered,wait_list_accepted,wait_list_admitted,admission_strategy_card_quality' \\
  -H 'apikey: ${ANON_KEY.slice(0, 24)}...' \\
  -H 'Authorization: Bearer ${ANON_KEY.slice(0, 24)}...'`}</CodeBlock>
        <p className="mt-3 text-sm leading-relaxed text-[var(--ink-2)]">
          Phase 0 measurement results are preserved in the repository&apos;s PRD
          findings note; the API page documents the public columns exposed by this card.
        </p>
      </section>
    </main>
  );
}
