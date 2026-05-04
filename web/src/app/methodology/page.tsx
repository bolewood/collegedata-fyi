import type { Metadata } from "next";
import Link from "next/link";

export const metadata: Metadata = {
  title: "Methodology",
  description:
    "How collegedata.fyi turns Common Data Set source documents into academic profile, admission strategy, and merit profile cards.",
  alternates: { canonical: "/methodology" },
  openGraph: { url: "/methodology" },
};

const METHODS = [
  {
    href: "/methodology/positioning",
    title: "Academic profile",
    body: "How SAT and ACT bands are read from the CDS and compared against a student-entered score.",
  },
  {
    href: "/methodology/admission-strategy",
    title: "Admission rounds",
    body: "How ED, EA, wait-list, yield, fee, and admissions-factor fields are derived from Section C.",
  },
  {
    href: "/methodology/merit-profile",
    title: "Merit and need aid",
    body: "How Section H merit-aid facts are combined with federal affordability and outcome context.",
  },
];

export default function MethodologyIndexPage() {
  return (
    <div className="mx-auto max-w-4xl px-4 py-12 sm:px-6">
      <div className="meta">§ Methodology</div>
      <h1 className="serif mt-3 leading-none" style={{ fontSize: "clamp(40px, 6vw, 64px)" }}>
        How the cards are built.
      </h1>
      <p className="mt-5 max-w-2xl text-[17px] leading-relaxed text-[var(--ink-2)]">
        These notes explain the source fields, derivations, and caveats behind
        the public cards on each school page. Every method starts from archived
        Common Data Set documents and keeps the source trail visible.
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
