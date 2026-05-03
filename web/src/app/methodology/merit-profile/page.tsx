import type { Metadata } from "next";
import Link from "next/link";
import type { ReactNode } from "react";

const BASE = "https://api.collegedata.fyi";
const ANON_KEY =
  "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImlzZHV3bXlndm1kb3pocHZ6YWl4Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzYxMDk3NTksImV4cCI6MjA5MTY4NTc1OX0.fYZOIHyrOWzidgc-CVxWCY5Fe9pQk12-6YjDIS6y9qs";

export const metadata: Metadata = {
  title: "Merit Profile Methodology",
  description:
    "How collegedata.fyi derives merit-aid, need-aid, net-price, and outcome context from Common Data Set Section H and College Scorecard data.",
  alternates: { canonical: "/methodology/merit-profile" },
  openGraph: { url: "/methodology/merit-profile" },
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

export default function MeritProfileMethodologyPage() {
  return (
    <main className="mx-auto max-w-3xl px-4 py-12 sm:px-6">
      <div className="meta">§ Methodology</div>
      <h1 className="serif mt-3 text-5xl leading-none">Merit profile</h1>
      <p className="mt-5 text-lg leading-relaxed text-[var(--ink-2)]">
        The merit profile combines source-reported CDS Section H aid facts with
        federal College Scorecard affordability and outcome context. It is built
        to answer what a school says it awarded, not to predict any applicant&apos;s
        financial-aid package.
      </p>

      <section className="mt-10">
        <h2 className="serif text-3xl">What we use</h2>
        <div className="mt-4">
          <FieldUse field="H.2" title="Need-aid recipients and average aid packages">
            H.2 gives first-year and all-undergraduate counts for degree-seeking
            full-time students, aid recipients, average aid packages, average
            need-based grants, and average self-help aid. We use the first-year
            full-time values for the school-page headline because they are closest
            to the entering-student decision.
          </FieldUse>
          <FieldUse field="H.2A" title="Non-need institutional scholarships and grants">
            H.2A reports students who had no financial need and received
            institutional non-need scholarship or grant aid. The section excludes
            athletic awards and tuition benefits. We display both recipient count
            and average non-need grant when reported.
          </FieldUse>
          <FieldUse field="H.6" title="Aid for nonresidents">
            H.6 records whether institutional need-based or non-need-based aid is
            available to students who are not U.S. citizens or permanent residents,
            and the average aid package for those students when the school reports it.
          </FieldUse>
          <FieldUse field="H.14" title="Institutional merit-aid categories">
            H.14 is a checkbox list of non-need scholarship and grant bases. We
            surface academics when the school checks it for either full-time
            first-year students or all undergraduates.
          </FieldUse>
          <FieldUse field="College Scorecard" title="Net price, outcomes, and debt">
            Scorecard fields provide federal context: average net price, net price
            by income band, graduation rate, retention, federal-loan use, debt,
            and median earnings. These are joined by IPEDS UNITID.
          </FieldUse>
        </div>
      </section>

      <section className="mt-10 border-t border-[var(--rule-strong)] pt-6">
        <h2 className="serif text-3xl">What H2A does and does not mean</h2>
        <p className="mt-4 text-sm leading-relaxed text-[var(--ink-2)]">
          H2A is the closest CDS-standard field for merit-aid prevalence: students
          with no financial need who still received institutional non-need
          scholarship or grant aid. It does not include students who had financial
          need and also received merit aid inside a mixed package, so it can
          understate the full footprint of merit awards.
        </p>
        <p className="mt-3 text-sm leading-relaxed text-[var(--ink-2)]">
          We compute the displayed no-need recipient share as H.2A01 divided by
          H.201 for first-year full-time students. When either field is absent or
          the denominator is zero, the share is left blank.
        </p>
      </section>

      <section className="mt-10 border-t border-[var(--rule-strong)] pt-6">
        <h2 className="serif text-3xl">Missing data policy</h2>
        <p className="mt-4 text-sm leading-relaxed text-[var(--ink-2)]">
          Missing CDS fields stay missing. We do not impute merit awards from peer
          schools, marketing copy, or third-party scholarship pages. After the
          May 3, 2026 Tier 4 redrain, direct H.2A02 answerability was 244 of 365
          latest primary 2024+ schools (66.8%), and effective first-year merit
          answerability was 252 of 365 (69.0%).
        </p>
      </section>

      <section className="mt-10 border-t border-[var(--rule-strong)] pt-6">
        <h2 className="serif text-3xl">What we do not capture</h2>
        <ul className="mt-4 grid gap-3 text-sm leading-relaxed text-[var(--ink-2)]">
          <li>Applicant-level scholarship probability or final price.</li>
          <li>Major-level, residency-level, or honors-college award splits.</li>
          <li>Automatic scholarship grids unless they also appear in CDS fields.</li>
          <li>Appeal behavior, negotiation, or one-off institutional exceptions.</li>
          <li>Non-CDS press-release counts for merit scholarships.</li>
        </ul>
      </section>

      <section className="mt-10 border-t border-[var(--rule-strong)] pt-6">
        <h2 className="serif text-3xl">Sources and API</h2>
        <p className="mt-4 text-sm leading-relaxed text-[var(--ink-2)]">
          The public serving view is <code>school_merit_profile</code>, one latest
          primary 2024-25+ row per school. The school page links to the archived CDS
          document used for the displayed Section H fields. For field-level audits,
          query <code>cds_fields</code> directly.
        </p>
        <CodeBlock>{`curl '${BASE}/rest/v1/school_merit_profile?school_id=eq.bowdoin&select=school_id,school_name,canonical_year,first_year_ft_students,non_need_aid_recipients_first_year_ft,avg_non_need_grant_first_year_ft,non_need_aid_share_first_year_ft,avg_net_price,graduation_rate_6yr,earnings_10yr_median' \\
  -H 'apikey: ${ANON_KEY.slice(0, 24)}...' \\
  -H 'Authorization: Bearer ${ANON_KEY.slice(0, 24)}...'`}</CodeBlock>
        <p className="mt-3 text-sm leading-relaxed text-[var(--ink-2)]">
          The broader public API is documented at{" "}
          <Link href="/api" className="underline">
            /api
          </Link>
          .
        </p>
      </section>
    </main>
  );
}
