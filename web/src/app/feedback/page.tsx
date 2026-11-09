import type { Metadata } from "next";
import { FeedbackForm } from "@/components/FeedbackForm";
import { TrackedLink } from "@/components/TrackedLink";
import { safeKind, safeSource, FEEDBACK_EMAIL } from "@/lib/community-feedback";
import { fetchCanonicalSchoolId, fetchSchoolDocuments } from "@/lib/queries";
export const metadata: Metadata = {
  title: "Feedback",
  robots: { index: false, follow: true },
  description:
    "Tell us what helped, what needs fixing, or how you use collegedata.fyi. No account required. Email is optional unless you'd like to discuss being featured.",
  alternates: { canonical: "/feedback" },
  openGraph: { url: "/feedback" },
  referrer: "strict-origin-when-cross-origin",
};
export default async function FeedbackPage({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const query = await searchParams;
  const kind = safeKind(query.kind);
  const from = safeSource(query.from);
  let school = "";
  let year = "";
  // Only known canonical/alias school context, never arbitrary URL text or Referer.
  if (
    kind === "data_issue" &&
    ["school", "school_year"].includes(from) &&
    typeof query.school === "string" &&
    /^[a-z0-9-]{1,100}$/.test(query.school)
  ) {
    try {
      const canonical = await fetchCanonicalSchoolId(query.school);
      if (canonical) {
        const docs = await fetchSchoolDocuments(canonical);
        if (docs.length) {
          school = (docs[0].school_name ?? canonical).slice(0, 150);
          if (
            typeof query.year === "string" &&
            docs.some((d) => d.cds_year === query.year)
          )
            year = query.year;
        }
      }
    } catch {
      /* Context is optional; email and ordinary feedback stay available. */
    }
  }
  return (
    <div className="mx-auto max-w-2xl px-4 py-12">
      <div className="meta">Feedback</div>
      <h1 className="serif mt-3 text-5xl">A note to the maintainer.</h1>
      <p className="mt-5 text-lg leading-relaxed">
        Tell us what helped, what was confusing, or what you&apos;re doing with
        the data. A sentence is enough. No account needed.
      </p>
      <FeedbackForm
        endpoint={
          process.env.NEXT_PUBLIC_FEEDBACK_FORMSPREE_ENDPOINT ||
          process.env.NEXT_PUBLIC_FORMSPREE_ENDPOINT
        }
        kind={kind}
        from={from}
        school={school}
        year={year}
      />
      <p className="my-5">
        Prefer email?{" "}
        <TrackedLink
          external
          href={FEEDBACK_EMAIL}
          analyticsEvent="community_cta_clicked"
          analyticsProperties={{
            action: "email",
            surface: from,
            placement: "form",
          }}
        >
          contact@bolewood.com
        </TrackedLink>
      </p>
      <p className="text-sm">
        You can also{" "}
        <TrackedLink
          external
          href="https://github.com/bolewood/collegedata-fyi/issues/new?template=report-extraction-error.yml"
          analyticsEvent="community_cta_clicked"
          analyticsProperties={{
            action: "github_issue",
            surface: from,
            placement: "form",
          }}
        >
          report a data problem on GitHub
        </TrackedLink>
        . GitHub issues are public and require an account.
      </p>
    </div>
  );
}
