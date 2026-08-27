import type { Metadata } from "next";
import Link from "next/link";

export const metadata: Metadata = {
  title: "Methodology",
  description:
    "How the school-page cards read Common Data Set filings — academic profile, admission rounds, merit and need aid. What they use, what they skip, what they do not predict.",
  alternates: { canonical: "/methodology" },
  openGraph: { url: "/methodology" },
};

const METHODS = [
  {
    href: "/methodology/positioning",
    title: "Academic profile",
    body: "Where a student’s SAT or ACT lands in the score bands the school published for enrolled first-years. Not a chance-me.",
  },
  {
    href: "/methodology/admission-strategy",
    title: "Admission rounds",
    body: "ED, EA, wait-list, and yield from Section C — including what CDS will not let you compute.",
  },
  {
    href: "/methodology/merit-profile",
    title: "Merit and need aid",
    body: "What the school reported in Section H, plus federal net-price and outcome context. Not a package estimate.",
  },
];

export default function MethodologyIndexPage() {
  return (
    <div className="mx-auto max-w-4xl px-4 py-12 sm:px-6">
      <div className="meta">§ Methodology</div>
      <h1 className="serif mt-3 leading-none" style={{ fontSize: "clamp(40px, 6vw, 64px)" }}>
        How the cards are <span style={{ fontStyle: "italic" }}>built.</span>
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
        The trail behind the school-page cards. Each note names the CDS fields,
        the derivation, and the caveat. Nothing here predicts an admissions
        decision or a financial-aid package.
      </p>

      <div className="mt-10 grid gap-4 sm:grid-cols-3">
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
    </div>
  );
}
