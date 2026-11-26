import type { Metadata } from "next";
import Link from "next/link";
import type { ReactNode } from "react";
import { SCHOLARSHIP_ATTRIBUTION, SCHOLARSHIP_CORRECTION_URL } from "@/lib/scholarships";
import { APEX_HOST, API_ORIGIN, SITE_NAME } from "@/lib/site";

const BASE = API_ORIGIN;

export const metadata: Metadata = {
  title: "Scholarship programs methodology",
  description:
    "How named scholarship programs are recorded: sourcing rules, field definitions, what the freshness lines mean, what not to infer, and how to credit the data.",
  alternates: { canonical: "/methodology/scholarships" },
  openGraph: { url: "/methodology/scholarships" },
};

function CodeBlock({ children }: { children: string }) {
  return (
    <pre className="overflow-x-auto border border-[var(--rule)] bg-[#faf6ec] px-4 py-3 text-xs leading-relaxed">
      <code>{children}</code>
    </pre>
  );
}

function Section({ id, title, children }: { id?: string; title: string; children: ReactNode }) {
  return (
    <section id={id} className="mt-10 border-t border-[var(--rule-strong)] pt-6">
      <h2 className="serif text-3xl">{title}</h2>
      <div className="mt-4 grid gap-3 text-sm leading-relaxed text-[var(--ink-2)]">{children}</div>
    </section>
  );
}

function Term({ lead, children }: { lead: string; children: ReactNode }) {
  return (
    <p>
      <strong className="text-[var(--ink)]">{lead}</strong> {children}
    </p>
  );
}

const APA = `${SITE_NAME}. (2026). Scholarship program data [Data set]. https://${APEX_HOST}/scholarships. CC BY-SA 4.0.`;
const BIBTEX = `@misc{collegedatafyi2026scholarships,
  author       = {{${SITE_NAME}}},
  title        = {Scholarship program data},
  year         = {2026},
  howpublished = {\\url{https://${APEX_HOST}/scholarships}},
  note         = {CC BY-SA 4.0. Terms as published by each school.}
}`;

export default function ScholarshipMethodologyPage() {
  return (
    <main className="mx-auto max-w-3xl px-4 py-12 sm:px-6">
      <div className="meta">§ Methodology</div>
      <h1 className="serif mt-3 text-5xl leading-none">
        Scholarship <span style={{ fontStyle: "italic" }}>programs.</span>
      </h1>
      <p
        className="serif mt-5"
        style={{ color: "var(--ink-2)", fontSize: 18, fontStyle: "italic", lineHeight: 1.55 }}
      >
        How named scholarship programs are recorded: what we read, what each field means, and what you should
        not infer from any of it.
      </p>

      <Section title="Sourcing rules">
        <p>
          Every fact comes from the school’s own pages, or from the page of a foundation the school is tied
          to (named as such). Third-party scholarship lists are used only to find programs, never as a source of
          terms. We read the page, record what it says with a locator, and note the date we read it. We do not
          copy the school’s text; we paraphrase it and quote at most 25 words.
        </p>
      </Section>

      <Section title="Field definitions">
        <Term lead="Program.">A named award or package, kept under one stable id across years and renamings.</Term>
        <Term lead="Entering class.">
          The class a version of the terms applies to, when the school’s page names it. Many pages give
          deadlines only, and then we do not guess the class.
        </Term>
        <Term lead="Offer.">
          A variant inside a program: resident or nonresident, or a tier. A tier lists only what it adds, so we
          say what it builds on.
        </Term>
        <Term lead="Benefit.">
          One component, such as tuition, housing, or a stipend, with how much of it the school says it covers
          and any cap or condition.
        </Term>
        <Term lead="Considered is not guaranteed.">
          “Considered” means the program looks at your application. “Automatic” appears
          only when the school’s page promises the award to everyone who meets the stated requirements.
        </Term>
        <Term lead="A waiver is not a scholarship.">
          A waiver is always named as a waiver. A waiver of the out-of-state differential is never counted as
          tuition covered. A waiver of all tuition is counted as full tuition, because the student is charged
          none.
        </Term>
        <Term lead="We do not add up totals.">
          We never sum components, multiply a yearly amount, or turn “up to” into a promise. If the
          school quotes a total, we show it as a quote with the scope the school gave.
        </Term>
        <Term lead="Separate application.">
          Whether the program needs its own form, as the school describes it. “Not stated” means the
          page does not say.
        </Term>
        <Term lead="Deadlines.">
          The school’s own dates. A date that recurs each year without a year is shown as recurring and is
          never turned into a dated deadline. Confirm every date on the official page.
        </Term>
        <Term lead="Renewal and stacking.">
          What the school says about keeping the award and combining it with other aid. Blank means not
          documented; it does not mean none.
        </Term>
        <Term lead="Counts.">
          Numbers a school publishes about how many awards it makes, labeled as a target or as reported. They
          are not odds.
        </Term>
      </Section>

      <Section title="What the freshness lines mean">
        <Term lead="Terms for a stated entering class.">
          The page names the class. We print it and the date we read the page.
        </Term>
        <Term lead="Dates, but no stated class.">
          The page gives dated deadlines but does not name the entering class. We print the month the dates run
          through and do not guess the class.
        </Term>
        <Term lead="The page names no year.">
          The page gives neither a class nor a dated deadline. We print the date we read it. After the next July 1
          we show it as a past cycle.
        </Term>
        <Term lead="Past cycle (amber).">
          The dates or class on the page have passed, or the school marks the program as an earlier cycle. We
          never carry last year’s dates forward.
        </Term>
        <Term lead="Pages disagree (amber).">
          The school’s own pages give different figures. We say what differs and send you to the official
          page.
        </Term>
        <Term lead="Not re-read for this cycle.">
          A change was flagged and has not been reviewed yet.
        </Term>
      </Section>

      <Section title="What not to infer">
        <ul className="grid gap-3">
          <li>A missing field is not a no. “Not stated” means the page did not say.</li>
          <li>This is not a list of the best scholarships, and sorting is never by generosity.</li>
          <li>Award counts are not odds. A program that offers “up to 44” does not tell you your chance of receiving one.</li>
          <li>A named award does not explain the CDS merit figures. The two are documented separately, with their own years.</li>
          <li>The list is partial and leans toward selective schools. A school not listed has not been documented yet.</li>
          <li>Nothing here is a personalized estimate of cost or award.</li>
        </ul>
      </Section>

      <Section title="Report a correction">
        <p>
          Found a figure that does not match the school’s page? Open a correction. We ask for the official
          page URL and what differs. We do not ask for your name, email, or any information about a student.
        </p>
        <p>
          <a href={SCHOLARSHIP_CORRECTION_URL} className="underline" target="_blank" rel="noopener noreferrer">
            Open a correction ↗
          </a>
        </p>
      </Section>

      <Section id="reuse" title="Reuse and credit">
        <p>
          The data is free to read, query and download. If you use it, credit it with this line:
        </p>
        <blockquote className="border-l-2 border-[var(--rule-strong)] pl-4 mono text-xs text-[var(--ink)]">
          {SCHOLARSHIP_ATTRIBUTION}
        </blockquote>
        <p>
          CC BY-SA 4.0 also asks that anything you build from our descriptions and record format be shared under
          the same license. That is the share-alike part: you may adapt the data, and you pass the same terms on.
        </p>
        <p>
          What the license does not cover: the schools’ own pages, their trademarks, and short quoted
          excerpts. Those stay with the schools.
        </p>
        <h3 className="serif text-xl text-[var(--ink)]">Cite this dataset</h3>
        <p className="meta">APA</p>
        <CodeBlock>{APA}</CodeBlock>
        <p className="meta">BibTeX</p>
        <CodeBlock>{BIBTEX}</CodeBlock>
      </Section>

      <Section title="Sources and API">
        <p>
          The public view is <code>scholarship_directory</code>: one row per program per participating school,
          with <code>license</code> and <code>attribution</code> columns on every row. The broader API is
          documented at{" "}
          <Link href="/api" className="underline">/api</Link>.
        </p>
        <CodeBlock>{`curl '${BASE}/rest/v1/scholarship_directory?school_id=eq.university-of-tulsa&select=official_name,entry_year,freshness_status,key_deadline,sources,attribution' \\
  -H 'apikey: <anon key>' \\
  -H 'Authorization: Bearer <anon key>'`}</CodeBlock>
        <p>
          The list is documented by hand and is partial. See{" "}
          <Link href="/scholarships" className="underline">all documented programs</Link>.
        </p>
      </Section>
    </main>
  );
}
