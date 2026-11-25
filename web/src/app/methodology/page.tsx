import type { Metadata } from "next";
import Link from "next/link";
import { isDataQualityLaunched } from "@/lib/data-quality";

export const metadata: Metadata = {
  title: "Methodology",
  description:
    "How the cards on each school page read Common Data Set filings and federal data, covering academic profiles, admission rounds, financial aid, and scholarships.",
  alternates: { canonical: "/methodology" },
  openGraph: { url: "/methodology" },
};

const METHODS = [
  {
    href: "/methodology/positioning",
    title: "Academic profile",
    body: "How a student’s SAT or ACT score compares with the middle ranges each school published for enrolled first-years.",
  },
  {
    href: "/methodology/admission-strategy",
    title: "Admission rounds",
    body: "Early Decision, Early Action, waitlists, and yield from Section C, including what the Common Data Set does and does not let you calculate.",
  },
  {
    href: "/methodology/merit-profile",
    title: "Merit and need aid",
    body: "Need-based and non-need aid from Section H, paired with federal net-price and graduate outcome data.",
  },
  {
    href: "/methodology/scholarships",
    title: "Scholarship programs",
    body: "How we document named merit scholarships at selected schools, with source URLs and review dates for every term.",
  },
];

export default function MethodologyIndexPage() {
  return (
    <div className="mx-auto max-w-4xl px-4 py-12 sm:px-6">
      <div className="meta">§ Methodology</div>
      <h1 className="serif mt-3 leading-none" style={{ fontSize: "clamp(40px, 6vw, 64px)" }}>
        How the school-page cards work
      </h1>
      <p
        className="serif mt-5 max-w-2xl"
        style={{
          color: "var(--ink-2)",
          fontSize: 18,
          fontStyle: "italic",
          lineHeight: 1.55,
        }}
      >
        Each guide below documents the exact Common Data Set fields, formulas,
        and limits behind the cards on a school page. These summaries show what
        colleges reported; they do not predict admission decisions or
        financial-aid offers.
      </p>

      <div className="mt-10 grid gap-4 sm:grid-cols-2">
        {METHODS.map((method) => (
          <Link
            key={method.href}
            href={method.href}
            className="cd-card p-4 no-underline"
          >
            <span className="serif block text-xl leading-tight">
              {method.title}
            </span>
            <span className="mt-3 block text-sm leading-relaxed text-[var(--ink-2)]">
              {method.body}
            </span>
          </Link>
        ))}
      </div>

      {/* PRD 040: linked only once the Data quality launch gate opens. */}
      {isDataQualityLaunched() && (
        <p className="mt-10 max-w-2xl text-sm leading-relaxed text-[var(--ink-2)]">
          How well we read the reports behind these cards is on the{" "}
          <Link href="/data-quality">Data quality</Link> page.
        </p>
      )}
    </div>
  );
}
