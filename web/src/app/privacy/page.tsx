import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Privacy",
  description:
    "Privacy policy for collegedata.fyi: no accounts, no student profiles, and only anonymous aggregate analytics.",
  alternates: { canonical: "/privacy" },
  openGraph: { url: "/privacy" },
};

export default function PrivacyPage() {
  return (
    <div className="mx-auto max-w-2xl px-4 py-12" style={{ color: "var(--ink-2)" }}>
      <h1
        style={{
          fontFamily: "var(--serif)",
          fontWeight: 400,
          fontSize: 48,
          lineHeight: 1.05,
          letterSpacing: "-0.02em",
          color: "var(--ink)",
          margin: 0,
        }}
      >
        Privacy Policy
      </h1>

      <div className="mt-8 space-y-5 text-base leading-relaxed">
        <p>
          <strong style={{ fontWeight: 600, color: "var(--ink)" }}>Effective date:</strong>{" "}
          October 2, 2026
        </p>

        <p>
          collegedata.fyi is designed to work without accounts, logins, or
          saved student profiles. You can browse school pages, read source
          documents, use the public API, and use the current planning tools
          without submitting personal information to us.
        </p>

        <h2 style={{ fontFamily: "var(--serif)", fontWeight: 500, fontSize: 26, letterSpacing: "-0.01em", color: "var(--ink)", marginTop: 40 }}>
          What we collect
        </h2>

        <p>
          We use Vercel Analytics to understand anonymous, aggregate site
          usage: things like page views, referrers, browser type, device type,
          general location, and which site features are used, such as school
          search, source links, downloads, copy buttons, and recipe controls.
          This helps us see which pages are useful and whether the site is
          performing reliably.
        </p>

        <p>
          Vercel Analytics does not give us a list of named visitors, and we do
          not send locally entered GPA, test scores, intended majors, search
          terms, or share codes as analytics properties. We do not use analytics
          to build student profiles or sell audience data.
        </p>

        <h2 style={{ fontFamily: "var(--serif)", fontWeight: 500, fontSize: 26, letterSpacing: "-0.01em", color: "var(--ink)", marginTop: 40 }}>
          What we do not collect
        </h2>

        <ul className="ml-6 list-disc space-y-2 marker:text-gray-400">
          <li>No account information, because there are no accounts.</li>
          <li>No student profile database.</li>
          <li>No application lists, grades, test scores, essays, or financial details.</li>
          <li>No sale of personal data to schools, lenders, advertisers, or data brokers.</li>
        </ul>

        <h2 style={{ fontFamily: "var(--serif)", fontWeight: 500, fontSize: 26, letterSpacing: "-0.01em", color: "var(--ink)", marginTop: 40 }}>
          Public API and server logs
        </h2>

        <p>
          Requests to the website and public API may create ordinary hosting,
          database, and security logs. We use those logs to operate the site,
          debug problems, and protect the service from abuse. We do not use
          them to identify students or build marketing profiles.
        </p>

        <p>
          We also count how the archive and API are used, from the logs our
          database host keeps for 90 days. A scheduled job reads those logs
          and stores only totals: requests per hour by type of client, and
          unique downloads per school per day. To count a download once per
          visitor, the job matches IP address and browser user agent inside
          the log query. It does not store IP addresses or full user agents.
        </p>

        <p>
          For automated API clients (scripts and bots, not browsers), we keep
          a short code made from the IP address and user agent with a random
          key that changes every day and is deleted two days later, so the
          code can&apos;t be traced back or linked across days. Next to it we
          keep the client&apos;s self-declared name, the network it came from
          (such as a cloud provider), and its country. We keep these hourly
          client counts for 400 days to spot abuse and heavy users.
        </p>

        <p>
          We publish only aggregate counts from this data, such as total
          downloads per day and per school per month. Small per-school
          numbers are hidden. We never publish anything about an individual
          visitor or client.
        </p>

        <h2 style={{ fontFamily: "var(--serif)", fontWeight: 500, fontSize: 26, letterSpacing: "-0.01em", color: "var(--ink)", marginTop: 40 }}>
          Questions
        </h2>

        <p>
          This project is open source. If you have a privacy question or want
          to report an issue, please open an issue on the{" "}
          <a
            style={{ textDecorationColor: "var(--rule-strong)", textUnderlineOffset: 3 }}
            href="https://github.com/bolewood/collegedata-fyi"
            target="_blank"
            rel="noopener noreferrer"
          >
            GitHub repository
          </a>
          .
        </p>
      </div>
    </div>
  );
}
