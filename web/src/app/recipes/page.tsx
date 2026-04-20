import type { Metadata } from "next";
import Link from "next/link";

export const metadata: Metadata = {
  title: "Recipes",
  description:
    "Worked examples of what you can do with the collegedata.fyi Common Data Set archive: interactive charts seeded with hand-verified data, extendable to the full corpus via the public API.",
  alternates: { canonical: "/recipes" },
  openGraph: { url: "/recipes" },
};

type Recipe = {
  slug: string;
  title: string;
  tagline: string;
  audience: string;
  demoPath: string;
  writeupUrl: string;
  sections: string;
  extras?: { label: string; path: string }[];
};

const RECIPES: Recipe[] = [
  {
    slug: "acceptance-vs-yield",
    title: "Acceptance rate vs. yield",
    tagline:
      "Scatter plot of how selective a school looks on paper (acceptance rate) against how selective it actually is in practice (yield). Four quadrants with teeth: selective-and-desired, loved-despite-openness, selective-but-second-choice, accessible-and-optional.",
    audience:
      "Students and parents building a target list; counselors calibrating reach/match/safety.",
    demoPath: "/recipes/acceptance-vs-yield-demo.html",
    writeupUrl:
      "https://github.com/bolewood/collegedata-fyi/blob/main/docs/recipes/acceptance-vs-yield.md",
    sections: "C1, B1, B22",
    extras: [
      {
        label: "XLSX starter",
        path: "/recipes/acceptance-vs-yield-starter.xlsx",
      },
    ],
  },
  {
    slug: "test-optional-tracker",
    title: "Test-optional tracker",
    tagline:
      "Line chart of SAT submission percentage over time for seven well-documented schools (Yale 2009\u20132024, Caltech 2002\u20132020, MIT, Princeton, Stanford, Harvard, Wake Forest). Uses the submission rate as an honest proxy for effective test-optional policy \u2014 written disclosures lie, enrollment numbers don't.",
    audience:
      "Students deciding whether a school's \u201ctest-optional\u201d is real; reporters tracking the post-COVID reversion.",
    demoPath: "/recipes/test-optional-tracker-demo.html",
    writeupUrl:
      "https://github.com/bolewood/collegedata-fyi/blob/main/docs/recipes/test-optional-tracker.md",
    sections: "C8, C9",
  },
];

export default function RecipesPage() {
  return (
    <div className="mx-auto max-w-3xl px-4 py-12 text-gray-800">
      <h1 className="text-3xl font-bold text-gray-900">Recipes</h1>
      <p className="mt-3 text-base leading-relaxed text-gray-600">
        Worked examples of what you can do with the archive. Each recipe pairs
        a short write-up with an interactive artifact seeded from
        hand-verified data, and a copy-pasteable API query you can use to
        scale it to the full corpus. If you want to contribute one,{" "}
        <a
          className="text-blue-700 underline hover:text-blue-900"
          href="https://github.com/bolewood/collegedata-fyi/blob/main/CONTRIBUTING.md"
          target="_blank"
          rel="noopener noreferrer"
        >
          PRs welcome
        </a>
        .
      </p>

      <div className="mt-8 space-y-5">
        {RECIPES.map((r) => (
          <article
            key={r.slug}
            className="rounded-lg border border-gray-200 bg-white p-5 shadow-sm"
          >
            <div className="flex items-baseline justify-between gap-3">
              <h2 className="text-lg font-semibold text-gray-900">
                <a
                  href={r.demoPath}
                  className="hover:text-blue-700"
                >
                  {r.title}
                </a>
              </h2>
              <span className="whitespace-nowrap text-xs text-gray-500">
                CDS {r.sections}
              </span>
            </div>
            <p className="mt-2 text-sm leading-relaxed text-gray-700">
              {r.tagline}
            </p>
            <p className="mt-2 text-xs text-gray-500">
              <span className="font-medium text-gray-700">For:</span>{" "}
              {r.audience}
            </p>
            <div className="mt-3 flex flex-wrap items-center gap-3 text-sm">
              <a
                href={r.demoPath}
                className="rounded-md bg-blue-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-blue-700"
              >
                Open demo →
              </a>
              <a
                href={r.writeupUrl}
                target="_blank"
                rel="noopener noreferrer"
                className="text-xs text-blue-700 underline hover:text-blue-900"
              >
                Read write-up
              </a>
              {r.extras?.map((x) => (
                <a
                  key={x.path}
                  href={x.path}
                  className="text-xs text-blue-700 underline hover:text-blue-900"
                >
                  {x.label}
                </a>
              ))}
            </div>
          </article>
        ))}
      </div>

      <div className="mt-10 rounded-lg border border-dashed border-gray-300 bg-gray-50 p-5">
        <h3 className="text-sm font-semibold text-gray-900">
          Ideas we haven&apos;t built yet
        </h3>
        <ul className="mt-2 list-disc space-y-1 pl-5 text-sm text-gray-700 marker:text-gray-400">
          <li>
            Net-price-by-income-bracket (H2A, H4) — the single most-asked
            question in college search.
          </li>
          <li>
            Realistic/reach/safety calibration from the published C9/C11
            distributions.
          </li>
          <li>
            Recruited athlete × program strength (Section F × Section J).
          </li>
          <li>
            &ldquo;Has this school changed?&rdquo; — longitudinal view of
            one school&apos;s selectivity, yield, and aid generosity over 5+
            years.
          </li>
        </ul>
        <p className="mt-3 text-xs text-gray-500">
          Want to build one of these?{" "}
          <a
            className="text-blue-700 underline hover:text-blue-900"
            href="https://github.com/bolewood/collegedata-fyi/blob/main/docs/recipes/README.md"
            target="_blank"
            rel="noopener noreferrer"
          >
            See the recipes guide
          </a>
          .
        </p>
      </div>

      <div className="mt-10 border-t border-gray-200 pt-6 text-sm text-gray-500">
        Looking for the data directly? Head to the{" "}
        <Link
          href="/api"
          className="text-blue-700 underline hover:text-blue-900"
        >
          public API
        </Link>{" "}
        or browse every school in the{" "}
        <Link
          href="/schools"
          className="text-blue-700 underline hover:text-blue-900"
        >
          directory
        </Link>
        .
      </div>
    </div>
  );
}
