import type { Metadata } from "next";
import Link from "next/link";
import { AlignmentGapChart } from "@/components/AlignmentGapChart";
import { AlignmentGapMeritChart } from "@/components/AlignmentGapMeritChart";
import { TrackedLink } from "@/components/TrackedLink";
import { formatRecipeShare } from "@/lib/format";
import {
  formatUsd,
  type AlignmentGapMeritRow,
  type AlignmentGapRow,
} from "@/lib/alignment-gap-recipe-analysis";
import {
  ALIGNMENT_GAP_MERIT_META,
  ALIGNMENT_GAP_MERIT_SCHOOLS,
  ALIGNMENT_GAP_META,
  ALIGNMENT_GAP_SCHOOLS,
} from "@/lib/alignment-gap-recipe-data";

export const metadata: Metadata = {
  title: "Alignment gap",
  description:
    "Debt burden, aid, and financial resources — College Scorecard, CDS H2A merit aid, and IPEDS endowment in one comparison.",
  alternates: { canonical: "/recipes/alignment-gap" },
  openGraph: { url: "/recipes/alignment-gap" },
};

const COVERS_EXAMPLE_IDS = [
  "quincy-university",
  "depauw-university",
  "wabash-college",
  "beloit-college",
  "gettysburg-college",
  "the-college-of-wooster",
  "pratt-institute-main",
] as const;

const TRAPPED_EXAMPLE_IDS = [
  "university-of-the-incarnate-word",
  "kentucky-state-university",
  "hollins-university",
  "baker-college",
  "north-carolina-a-and-t-state-university",
  "point-park-university",
] as const;

const meritById = new Map(
  ALIGNMENT_GAP_MERIT_SCHOOLS.map((row) => [row.schoolId, row]),
);
const endowmentById = new Map(
  ALIGNMENT_GAP_SCHOOLS.map((row) => [row.schoolId, row]),
);

function requireMerit(id: string): AlignmentGapMeritRow {
  const row = meritById.get(id);
  if (!row) throw new Error(`merit join missing ${id}`);
  return row;
}

function requireEndowment(id: string): AlignmentGapRow {
  const row = endowmentById.get(id);
  if (!row) throw new Error(`endowment join missing ${id}`);
  return row;
}

function roundUsd(value: number, step: number): string {
  return formatUsd(Math.round(value / step) * step);
}

const COVERS_EXAMPLES = COVERS_EXAMPLE_IDS.map(requireMerit);
const TRAPPED_EXAMPLES = TRAPPED_EXAMPLE_IDS.map(requireMerit);
const quincy = requireMerit("quincy-university");
const hollins = requireEndowment("hollins-university");
const bennington = requireEndowment("bennington-college");
const bard = requireEndowment("bard-college");
const grinnell = requireEndowment("grinnell-college");
const ex = ALIGNMENT_GAP_MERIT_META.exclusions;
const medianEndowmentUsd = roundUsd(
  ALIGNMENT_GAP_META.medianEndowmentPerStudent,
  1000,
);
const hollinsEndowmentUsd = roundUsd(hollins.endowmentPerStudent, 1000);
const bardEndowmentUsd = roundUsd(bard.endowmentPerStudent, 100);
const grinnellEndowmentMillions = (grinnell.endowmentPerStudent / 1_000_000).toFixed(2);
const benningtonInstructionPct = Math.round(bennington.instructionShare * 100);

const REGIONS = [
  {
    num: "A",
    head: "Merit aid is larger than the gap",
    count: ALIGNMENT_GAP_MERIT_META.regions.covers,
    body: `Among the ${ALIGNMENT_GAP_MERIT_META.positiveGap} schools in this view with above-median debt burden, ${ALIGNMENT_GAP_MERIT_META.regions.covers} report average non-need merit aid per first-year student that is larger than their annual alignment gap. Quincy University is an especially visible example. It reports non-need merit aid for every full-time first-year student, averaging ${formatUsd(quincy.avgMeritGrant)}, compared with an average net price of ${formatUsd(quincy.avgNetPrice)} and an alignment gap of ${formatUsd(quincy.gap)} per year. That does not mean Quincy could simply move ${formatUsd(quincy.gap)} from one budget line to another. It does show that the scale of its existing merit discount is large relative to the debt adjustment represented by the gap.`,
  },
  {
    num: "B",
    head: "Merit aid is smaller than the gap",
    count: ALIGNMENT_GAP_MERIT_META.regions.constrained,
    body: "These schools also have above-median debt burden, but their reported non-need merit aid per first-year student is smaller than the alignment gap. Some award very little non-need merit aid at all. The University of the Incarnate Word, for example, reports $0 in this CDS measure while still showing a positive alignment gap. For these schools, Panel A provides less evidence that a large non-need merit program is part of the affordability picture. Other factors—price, need-based aid, student borrowing, graduate earnings, and the institution's broader finances—matter more.",
  },
  {
    num: "C",
    head: "Debt burden is at or below the median",
    count: ALIGNMENT_GAP_MERIT_META.regions.none,
    body: `These schools have no positive alignment gap under this definition because their debt burden is already at or below the ${formatRecipeShare(ALIGNMENT_GAP_META.medianBurden, 2)} median used for the comparison. They remain on the chart so the relationship between merit aid and debt burden can be seen across the full sample.`,
  },
];

const QUADRANTS = [
  {
    num: "I",
    head: "Higher debt burden · higher endowment",
    count: ALIGNMENT_GAP_META.quadrants.capacity,
    body: `These schools have debt burden above the sample median and endowment per undergraduate above the sample median. That combination does not tell us what a school should charge or how much of its endowment could be used for financial aid. It does tell us that the institution has relatively greater financial resources while its graduates still carry a relatively high federal-loan burden. Hollins University is near the outer edge of this group, with a ${formatRecipeShare(hollins.burden, 1)} debt burden and roughly ${hollinsEndowmentUsd} in endowment per undergraduate.`,
  },
  {
    num: "II",
    head: "Higher debt burden · lower endowment",
    count: ALIGNMENT_GAP_META.quadrants.constrained,
    body: `These schools also have above-median debt burden, but their endowment per undergraduate is below the median. That is an important distinction. Two colleges can produce a similar debt burden for graduates while having very different financial resources available to support students or subsidize the cost of instruction. Bennington College is one example: relatively high debt burden, a more modest endowment per student, and instructional spending equal to about ${benningtonInstructionPct}% of its average net price.`,
  },
  {
    num: "III",
    head: "Lower debt burden · higher endowment",
    count: ALIGNMENT_GAP_META.quadrants.absorbs,
    body: "These schools combine debt burden at or below the median with above-median endowment per undergraduate. This group includes Grinnell, Princeton, Stanford, and Wellesley. At a number of highly endowed colleges, reported instructional spending per student exceeds average net price. In other words, tuition and other payments from students are only part of what funds the educational program.",
  },
  {
    num: "IV",
    head: "Lower debt burden · lower endowment",
    count: ALIGNMENT_GAP_META.quadrants.earnings,
    body: "These schools keep debt burden at or below the median without an unusually large endowment per student. Graduate earnings can be an important part of that result because earnings are the denominator in the debt-burden calculation. Debt levels matter too. Bentley, Babson, and Santa Clara are examples in this part of the chart.",
  },
];

export default function AlignmentGapPage() {
  const corpusMedianBurden = formatRecipeShare(
    ALIGNMENT_GAP_META.medianBurden,
    2,
  );
  const sampleMedianBurden = formatRecipeShare(
    ALIGNMENT_GAP_MERIT_META.sampleMedianBurden,
    2,
  );

  return (
    <div className="mx-auto max-w-5xl px-4 sm:px-6 py-8">
      <header
        style={{
          display: "flex",
          flexWrap: "wrap",
          alignItems: "flex-end",
          justifyContent: "space-between",
          gap: 24,
          paddingTop: 16,
          paddingBottom: 8,
        }}
      >
        <div>
          <div
            className="mono"
            style={{
              fontSize: 11,
              color: "var(--ink-3)",
              letterSpacing: "0.08em",
              textTransform: "uppercase",
            }}
          >
            <Link href="/recipes" style={{ color: "var(--ink-3)", textDecoration: "none" }}>
              RECIPES
            </Link>{" "}
            / <span style={{ color: "var(--ink)" }}>ALIGNMENT GAP</span>
          </div>
          <h1
            className="serif"
            style={{
              fontWeight: 400,
              fontSize: "clamp(36px, 5.5vw, 52px)",
              margin: "12px 0 0",
              letterSpacing: "-0.02em",
              lineHeight: 1.05,
            }}
          >
            Debt burden, aid, and{" "}
            <span style={{ fontStyle: "italic" }}>financial resources</span>
          </h1>
        </div>
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap", justifyContent: "flex-end" }}>
          <span className="cd-chip">CDS H2A</span>
          <span className="cd-chip">College Scorecard</span>
          <span className="cd-chip">IPEDS</span>
        </div>
      </header>

      <div style={{ maxWidth: 760, marginTop: 16 }}>
        <p
          className="serif"
          style={{
            margin: 0,
            color: "var(--ink-2)",
            fontSize: 18,
            fontStyle: "italic",
            lineHeight: 1.55,
          }}
        >
          College affordability data lives in several different places.
        </p>
        <p style={{ fontSize: 16, lineHeight: 1.65, color: "var(--ink-2)", margin: "14px 0 0" }}>
          The College Scorecard tells us about student debt, loan payments,
          earnings, and net price. The Common Data Set tells us how colleges
          use non-need merit aid. IPEDS tells us about institutional finances,
          including endowment and instructional spending.
        </p>
        <p style={{ fontSize: 16, lineHeight: 1.65, color: "var(--ink-2)", margin: "14px 0 0" }}>
          This page joins those sources to look at them together.
        </p>
        <p style={{ fontSize: 16, lineHeight: 1.65, color: "var(--ink-2)", margin: "14px 0 0" }}>
          The starting point is <strong>debt burden</strong>: the share of
          median earnings that would go toward federal student-loan payments
          each year. We then calculate an <strong>alignment gap</strong> for
          each school: roughly how much less debt its graduates would need to
          carry, expressed per year of college, to reach the median debt burden
          in this group of schools.
        </p>
        <p style={{ fontSize: 16, lineHeight: 1.65, color: "var(--ink-2)", margin: "14px 0 0" }}>
          The gap is not a recommended tuition price or a claim that lowering
          price by exactly that amount would produce the same reduction in
          borrowing. It is a common yardstick that lets us compare the size of
          the debt burden with other financial measures from the college.
        </p>
      </div>

      <section
        className="endowment-recipe-ledger rule-2"
        style={{ marginTop: 28 }}
      >
        <div>
          <strong>{ALIGNMENT_GAP_MERIT_META.schoolCount.toLocaleString("en-US")}</strong>
          <small>Schools with usable merit-aid, debt, earnings, price, and endowment data</small>
        </div>
        <div>
          <strong>{ALIGNMENT_GAP_MERIT_META.positiveGap.toLocaleString("en-US")}</strong>
          <small>
            Debt burden above the {corpusMedianBurden} median used on this page
          </small>
        </div>
        <div>
          <strong>
            {ALIGNMENT_GAP_MERIT_META.regions.covers} of {ALIGNMENT_GAP_MERIT_META.positiveGap}
          </strong>
          <small>
            Schools where estimated non-need merit aid per first-year student is
            larger than the annual alignment gap
          </small>
        </div>
        <div>
          <strong>{ALIGNMENT_GAP_MERIT_META.zeroMeritCount.toLocaleString("en-US")}</strong>
          <small>Schools in this sample reporting no non-need merit aid</small>
        </div>
      </section>

      <section style={{ marginTop: 28 }}>
        <AlignmentGapMeritChart />
      </section>

      <section
        style={{
          marginTop: 48,
          display: "grid",
          gridTemplateColumns: "repeat(3, 1fr)",
          gap: 24,
        }}
        className="cd-recipe-regions"
      >
        {REGIONS.map((q) => (
          <div key={q.num} className="cd-card" style={{ padding: 20, display: "flex", gap: 16 }}>
            <div
              className="serif"
              style={{
                fontSize: 38,
                lineHeight: 0.9,
                color: "var(--forest)",
                fontStyle: "italic",
              }}
            >
              {q.num}.
            </div>
            <div>
              <div className="meta" style={{ marginBottom: 4, color: "var(--ink-3)" }}>
                {q.count} SCHOOLS
              </div>
              <div className="serif" style={{ fontSize: 20, letterSpacing: "-0.005em" }}>
                {q.head}
              </div>
              <div style={{ fontSize: 14, color: "var(--ink-2)", lineHeight: 1.55, marginTop: 6 }}>
                {q.body}
              </div>
            </div>
          </div>
        ))}
      </section>

      <section style={{ marginTop: 36, overflowX: "auto" }}>
        <div className="meta" style={{ marginBottom: 10 }}>
          Worked examples · merit aid larger than the gap
        </div>
        <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
          <thead>
            <tr className="meta" style={{ textAlign: "left", color: "var(--ink-3)" }}>
              <th style={{ padding: "8px 12px 8px 0" }}>School</th>
              <th style={{ padding: "8px 12px" }}>Gap/yr</th>
              <th style={{ padding: "8px 12px" }}>Merit spend / first-year</th>
              <th style={{ padding: "8px 12px" }}>Merit share</th>
              <th style={{ padding: "8px 12px" }}>Avg merit grant</th>
              <th style={{ padding: "8px 12px" }}>Net price</th>
            </tr>
          </thead>
          <tbody>
            {COVERS_EXAMPLES.map((row) => (
              <tr key={row.schoolId} style={{ borderTop: "1px solid var(--rule)" }}>
                <td style={{ padding: "8px 12px 8px 0" }}>{row.schoolName.replace("-Main", "")}</td>
                <td style={{ padding: "8px 12px" }}>{formatUsd(row.gap)}</td>
                <td style={{ padding: "8px 12px", fontWeight: 600 }}>{formatUsd(row.meritPerFirstYear)}</td>
                <td style={{ padding: "8px 12px" }}>{formatRecipeShare(row.meritShare, 0)}</td>
                <td style={{ padding: "8px 12px" }}>{formatUsd(row.avgMeritGrant)}</td>
                <td style={{ padding: "8px 12px" }}>{formatUsd(row.avgNetPrice)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>

      <section style={{ marginTop: 28, overflowX: "auto" }}>
        <div className="meta" style={{ marginBottom: 10 }}>
          Worked examples · merit aid smaller than the gap
        </div>
        <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
          <thead>
            <tr className="meta" style={{ textAlign: "left", color: "var(--ink-3)" }}>
              <th style={{ padding: "8px 12px 8px 0" }}>School</th>
              <th style={{ padding: "8px 12px" }}>Gap/yr</th>
              <th style={{ padding: "8px 12px" }}>Merit spend / first-year</th>
            </tr>
          </thead>
          <tbody>
            {TRAPPED_EXAMPLES.map((row) => (
              <tr key={row.schoolId} style={{ borderTop: "1px solid var(--rule)" }}>
                <td style={{ padding: "8px 12px 8px 0" }}>{row.schoolName}</td>
                <td style={{ padding: "8px 12px" }}>{formatUsd(row.gap)}</td>
                <td style={{ padding: "8px 12px" }}>{formatUsd(row.meritPerFirstYear)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>

      <section style={{ marginTop: 48, maxWidth: 760 }}>
        <h2 className="serif" style={{ fontSize: 28, margin: "0 0 12px", letterSpacing: "-0.015em" }}>
          Now add financial resources
        </h2>
        <p style={{ fontSize: 16, lineHeight: 1.65, color: "var(--ink-2)", margin: 0 }}>
          The merit-aid comparison only works for schools with usable CDS H2A
          data. Many colleges do not publish that field consistently.
        </p>
        <p style={{ fontSize: 16, lineHeight: 1.65, color: "var(--ink-2)", margin: "14px 0 0" }}>
          A second view uses a larger group of {ALIGNMENT_GAP_META.schoolCount}{" "}
          schools and asks a different question: <strong>how does graduate
          debt burden compare with the financial resources of the
          institution?</strong> Here we plot the same alignment gap against
          endowment per undergraduate.
        </p>
      </section>

      <section className="endowment-recipe-ledger rule-2" style={{ marginTop: 28 }}>
        <div>
          <strong>{ALIGNMENT_GAP_META.schoolCount.toLocaleString("en-US")}</strong>
          <small>Schools in the endowment comparison</small>
        </div>
        <div>
          <strong>{corpusMedianBurden}</strong>
          <small>Median debt burden in this group</small>
        </div>
        <div>
          <strong>{ALIGNMENT_GAP_META.aboveMedianBurden.toLocaleString("en-US")}</strong>
          <small>Debt burden above the median</small>
        </div>
        <div>
          <strong>{medianEndowmentUsd}</strong>
          <small>Median endowment per undergraduate</small>
        </div>
      </section>

      <section style={{ marginTop: 28 }}>
        <AlignmentGapChart />
      </section>

      <section
        style={{
          marginTop: 48,
          display: "grid",
          gridTemplateColumns: "repeat(2, 1fr)",
          gap: 24,
        }}
        className="cd-recipe-quadrants"
      >
        {QUADRANTS.map((q) => (
          <div key={q.num} className="cd-card" style={{ padding: 20, display: "flex", gap: 16 }}>
            <div
              className="serif"
              style={{
                fontSize: 38,
                lineHeight: 0.9,
                color: "var(--forest)",
                fontStyle: "italic",
              }}
            >
              {q.num}.
            </div>
            <div>
              <div className="meta" style={{ marginBottom: 4, color: "var(--ink-3)" }}>
                {q.count} SCHOOLS
              </div>
              <div className="serif" style={{ fontSize: 20, letterSpacing: "-0.005em" }}>
                {q.head}
              </div>
              <div style={{ fontSize: 14, color: "var(--ink-2)", lineHeight: 1.55, marginTop: 6 }}>
                {q.body}
              </div>
            </div>
          </div>
        ))}
      </section>

      <section style={{ marginTop: 48, maxWidth: 760 }}>
        <h2 className="serif" style={{ fontSize: 28, margin: "0 0 12px", letterSpacing: "-0.015em" }}>
          An example: Bard and Grinnell
        </h2>
        <p style={{ fontSize: 16, lineHeight: 1.65, color: "var(--ink-2)", margin: 0 }}>
          Bard and Grinnell illustrate why putting these datasets together can
          be useful.
        </p>
        <p style={{ fontSize: 16, lineHeight: 1.65, color: "var(--ink-2)", margin: "14px 0 0" }}>
          Their published median SAT scores are similar: {bard.satCompositeP50}{" "}
          for Bard and {grinnell.satCompositeP50} for Grinnell. But the financial
          picture in the joined data is very different.
        </p>
        <p style={{ fontSize: 16, lineHeight: 1.65, color: "var(--ink-2)", margin: "14px 0 0" }}>
          Grinnell&apos;s average net price is {formatUsd(grinnell.avgNetPrice)},
          compared with {formatUsd(bard.avgNetPrice)}{" "}at Bard. Grinnell&apos;s
          graduate debt burden is {formatRecipeShare(grinnell.burden, 1)},
          compared with {formatRecipeShare(bard.burden, 1)} at Bard. And Grinnell
          reports about ${grinnellEndowmentMillions} million in endowment per
          undergraduate, compared with about {bardEndowmentUsd} at Bard.
        </p>
        <p style={{ fontSize: 16, lineHeight: 1.65, color: "var(--ink-2)", margin: "14px 0 0" }}>
          Those numbers do <strong>not</strong> make Bard and Grinnell equivalent
          colleges, nor do they prove that the difference in endowment caused
          the difference in price or debt. Admissions alone make that clear:
          Grinnell admitted 1,416 of 9,758 applicants in 2024–25, or 14.5%.
        </p>
        <p style={{ fontSize: 16, lineHeight: 1.65, color: "var(--ink-2)", margin: "14px 0 0" }}>
          The comparison simply shows what becomes visible when data that
          normally sits in separate systems is placed side by side. Two
          colleges can enroll students with similar published test profiles
          while having very different prices, graduate debt burdens, and
          institutional resources.
        </p>
        <p style={{ fontSize: 16, lineHeight: 1.65, color: "var(--ink-2)", margin: "14px 0 0" }}>
          Neither Bard nor Grinnell appears in the first chart because neither
          has a usable H2A merit-aid row in this dataset. That is why the
          second chart uses the broader endowment comparison.
        </p>
        <p style={{ fontSize: 16, lineHeight: 1.65, color: "var(--ink-2)", margin: "14px 0 0" }}>
          For a student or family, that is the practical point of the exercise:
          sticker price, financial aid, debt, earnings, and a college&apos;s
          financial resources are usually presented separately. Looking at them
          together gives a more complete picture.
        </p>
      </section>

      <section style={{ marginTop: 48, maxWidth: 760 }}>
        <h2 className="serif" style={{ fontSize: 28, margin: "0 0 12px", letterSpacing: "-0.015em" }}>
          How the alignment gap is calculated
        </h2>
        <p style={{ fontSize: 16, lineHeight: 1.65, color: "var(--ink-2)", margin: 0 }}>
          The calculation starts with debt burden.
        </p>
        <p style={{ fontSize: 16, lineHeight: 1.65, color: "var(--ink-2)", margin: "14px 0 0" }}>
          <code>debt burden = median monthly federal loan payment × 12 ÷ median earnings 10 years after enrollment</code>
        </p>
        <p style={{ fontSize: 16, lineHeight: 1.65, color: "var(--ink-2)", margin: "14px 0 0" }}>
          A school with annual loan payments of $3,000 and median earnings of
          $60,000 would therefore have a debt burden of 5%.
        </p>
        <p style={{ fontSize: 16, lineHeight: 1.65, color: "var(--ink-2)", margin: "14px 0 0" }}>
          The median debt burden in the {ALIGNMENT_GAP_META.schoolCount}-school
          comparison on this page is <strong>{corpusMedianBurden}</strong>.
        </p>
        <p style={{ fontSize: 16, lineHeight: 1.65, color: "var(--ink-2)", margin: "14px 0 0" }}>
          For schools above that level, the alignment gap estimates how much
          lower median completer debt would need to be for the school to reach
          a {corpusMedianBurden} burden at its existing earnings level. We
          divide that amount by four so it can be read as an annual figure.
        </p>
        <p style={{ fontSize: 16, lineHeight: 1.65, color: "var(--ink-2)", margin: "14px 0 0" }}>
          <code>alignment gap = completer debt × (1 − median burden ÷ school burden) ÷ 4</code>
        </p>
        <p style={{ fontSize: 16, lineHeight: 1.65, color: "var(--ink-2)", margin: "14px 0 0" }}>
          A positive gap means debt burden is above the sample median. A zero
          or negative gap means it is at or below the median.
        </p>
        <p style={{ fontSize: 16, lineHeight: 1.65, color: "var(--ink-2)", margin: "14px 0 0" }}>
          Again, this is a comparison measure. It should not be read as a
          prediction that reducing annual net price by the same number would
          reduce student debt one-for-one.
        </p>
        <p style={{ fontSize: 16, lineHeight: 1.65, color: "var(--ink-2)", margin: "14px 0 0" }}>
          For the first chart, we also estimate non-need merit aid per
          full-time first-year student:
        </p>
        <p style={{ fontSize: 16, lineHeight: 1.65, color: "var(--ink-2)", margin: "14px 0 0" }}>
          <code>merit aid per first-year student = share receiving non-need merit aid × average non-need merit grant</code>
        </p>
        <p style={{ fontSize: 16, lineHeight: 1.65, color: "var(--ink-2)", margin: "14px 0 0" }}>
          For example, if 40% of first-year students receive non-need merit aid
          and the average grant among recipients is $20,000, the measure used
          here is $8,000 per first-year student.
        </p>
        <p style={{ fontSize: 16, lineHeight: 1.65, color: "var(--ink-2)", margin: "14px 0 0" }}>
          Both charts use the same {corpusMedianBurden} median debt burden so a
          school does not have a different benchmark depending on which chart
          you are viewing. The smaller merit-aid sample has a very similar
          median of {sampleMedianBurden}.
        </p>
      </section>

      <section style={{ marginTop: 48, maxWidth: 760 }}>
        <h2 className="serif" style={{ fontSize: 28, margin: "0 0 12px", letterSpacing: "-0.015em" }}>
          What is being joined
        </h2>
        <p style={{ fontSize: 16, lineHeight: 1.65, color: "var(--ink-2)", margin: 0 }}>
          Panel A combines three sources. College Scorecard supplies debt, loan
          payments, earnings, and net price. Common Data Set H2A supplies
          non-need merit-aid information for full-time first-year students.
          IPEDS supplies endowment information.
        </p>
        <p style={{ fontSize: 16, lineHeight: 1.65, color: "var(--ink-2)", margin: "14px 0 0" }}>
          After data-quality checks, {ALIGNMENT_GAP_MERIT_META.schoolCount}{" "}
          schools have enough usable information for this view.
        </p>
        <p style={{ fontSize: 16, lineHeight: 1.65, color: "var(--ink-2)", margin: "14px 0 0" }}>
          Panel B does not require H2A merit-aid data, so it can include many
          schools that are missing from Panel A. It uses College Scorecard
          debt, earnings, and net price; IPEDS endowment and instructional
          spending; and a recent CDS SAT midpoint to define the{" "}
          {ALIGNMENT_GAP_META.schoolCount}-school comparison group.
        </p>
        <p style={{ fontSize: 16, lineHeight: 1.65, color: "var(--ink-2)", margin: "14px 0 0" }}>
          The two samples overlap, but neither is simply a subset of the other.
        </p>
      </section>

      <section style={{ marginTop: 48, maxWidth: 760 }}>
        <h2 className="serif" style={{ fontSize: 28, margin: "0 0 12px", letterSpacing: "-0.015em" }}>
          Data limits
        </h2>
        <p style={{ fontSize: 16, lineHeight: 1.65, color: "var(--ink-2)", margin: 0 }}>
          This page combines institutional data from different systems and
          different years, so the numbers should not be read as if they
          describe one group of students moving through college at the same
          time.
        </p>
        <p style={{ fontSize: 16, lineHeight: 1.65, color: "var(--ink-2)", margin: "14px 0 0" }}>
          The College Scorecard figures used here are from{" "}
          {ALIGNMENT_GAP_META.scorecardYears.join(", ")}. Earnings data describe
          federally aided students from an earlier cohort, roughly a decade
          after they first enrolled. The CDS data are from 2024–25 or 2025–26.
          The join is by institution, not by individual student or graduating
          class.
        </p>
        <p style={{ fontSize: 16, lineHeight: 1.65, color: "var(--ink-2)", margin: "14px 0 0" }}>
          CDS H2A also has limits. It covers full-time first-year students and
          specifically reports non-need aid. Some awards that combine need and
          merit may not appear in the measure. It is best understood as a view
          of one part of a school&apos;s recruiting and tuition-discount strategy,
          not its total financial-aid budget.
        </p>
        <p style={{ fontSize: 16, lineHeight: 1.65, color: "var(--ink-2)", margin: "14px 0 0" }}>
          Federal student debt has limits as a measure of affordability as
          well. Median debt in this {ALIGNMENT_GAP_META.schoolCount}-school
          sample ranges from {formatUsd(ALIGNMENT_GAP_META.debtMin)} to{" "}
          {formatUsd(ALIGNMENT_GAP_META.debtMax)}, and           {formatUsd(ALIGNMENT_GAP_META.debtMode)}—the
          federal aggregate borrowing limit for many dependent undergraduates—is
          the most common value in the sample. Families may
          pay college costs with income, savings, parent borrowing, private
          loans, grants, or other resources that are not captured by this debt
          number.
        </p>
        <p style={{ fontSize: 16, lineHeight: 1.65, color: "var(--ink-2)", margin: "14px 0 0" }}>
          That is why this page does not use federal debt as a substitute for
          price. Net price remains the price measure. Debt burden tells us
          something different: how large federal loan payments are relative to
          later earnings.
        </p>
      </section>

      <section style={{ marginTop: 48, maxWidth: 760 }}>
        <h2 className="serif" style={{ fontSize: 28, margin: "0 0 12px", letterSpacing: "-0.015em" }}>
          Data-quality checks
        </h2>
        <p style={{ fontSize: 16, lineHeight: 1.65, color: "var(--ink-2)", margin: 0 }}>
          Panel A begins with {ex.universe.toLocaleString("en-US")} possible
          merit-profile rows. We keep {ALIGNMENT_GAP_MERIT_META.schoolCount} after
          requiring usable CDS merit-aid data and the Scorecard and IPEDS
          fields needed for the comparison.
        </p>
        <p style={{ fontSize: 16, lineHeight: 1.65, color: "var(--ink-2)", margin: "14px 0 0" }}>
          Rows are removed when the merit profile is too incomplete, required
          values are missing, or published values fall outside reasonable
          ranges. That includes {ex.rangeShare} reported merit-aid shares
          outside 0–100% and {ex.rangeGrant} average grant above $80,000. A
          legitimate published value of $0 is kept.
        </p>
        <p style={{ fontSize: 16, lineHeight: 1.65, color: "var(--ink-2)", margin: "14px 0 0" }}>
          {ALIGNMENT_GAP_MERIT_META.zeroMeritCount} schools in the final sample
          report no non-need merit aid. Four already have debt burden at or
          below the median. The University of the Incarnate Word has a positive
          alignment gap.
        </p>
        <p style={{ fontSize: 16, lineHeight: 1.65, color: "var(--ink-2)", margin: "14px 0 0" }}>
          The checks matter because joining datasets can make a bad source
          value look much more meaningful than it really is. The filters used
          for this page are part of the reproducible recipe rather than manual
          exclusions made after looking at the chart.
        </p>
      </section>

      <section style={{ marginTop: 48 }}>
        <h2 className="serif" style={{ fontSize: 28, margin: "0 0 12px", letterSpacing: "-0.015em" }}>
          Pull the data yourself
        </h2>
        <p style={{ fontSize: 16, lineHeight: 1.65, color: "var(--ink-2)", margin: "0 0 16px", maxWidth: 760 }}>
          The underlying data and calculations are public. The queries below
          reproduce the source rows used for the two panels. Panel B contains
          more rows than the API&apos;s 1,000-row response limit, so retrieve it
          in pages.
        </p>
        <pre
          style={{
            background: "var(--ink)",
            color: "var(--paper)",
            padding: "20px 24px",
            fontFamily: "var(--mono)",
            fontSize: 13,
            lineHeight: 1.55,
            margin: 0,
            borderRadius: 2,
            overflowX: "auto",
          }}
        >
{`# Panel A — CDS H2A merit × Scorecard (488 rows; under the 1,000-row cap)
curl 'https://api.collegedata.fyi/rest/v1/school_merit_profile?select=school_id,school_name,canonical_year,merit_profile_quality,non_need_aid_share_first_year_ft,avg_non_need_grant_first_year_ft,avg_need_grant_first_year_ft,earnings_10yr_median,median_debt_completers,median_debt_monthly_payment,avg_net_price&limit=1000' \\
  -H 'apikey: <anon key>' \\
  -H 'Authorization: Bearer <anon key>'

# Panel B — Scorecard + IPEDS endowment (2,158 matching rows)
# PostgREST max-rows is 1,000. limit=5000 and Range: 0-4999 are both capped
# at 1,000 with HTTP 206 / Content-Range: 0-999/2158 — no error body.
# Page with offset (or Range: 0-999, then 1000-1999, then 2000-2999):
curl 'https://api.collegedata.fyi/rest/v1/scorecard_summary?select=ipeds_id,earnings_10yr_median,median_debt_monthly_payment,median_debt_completers,avg_net_price,endowment_end,instructional_expenditure_fte,enrollment&earnings_10yr_median=gt.0&median_debt_monthly_payment=gt.0&avg_net_price=gt.0&endowment_end=gt.0&limit=1000&offset=0' \\
  -H 'apikey: <anon key>' \\
  -H 'Authorization: Bearer <anon key>'
curl 'https://api.collegedata.fyi/rest/v1/scorecard_summary?select=ipeds_id,earnings_10yr_median,median_debt_monthly_payment,median_debt_completers,avg_net_price,endowment_end,instructional_expenditure_fte,enrollment&earnings_10yr_median=gt.0&median_debt_monthly_payment=gt.0&avg_net_price=gt.0&endowment_end=gt.0&limit=1000&offset=1000' \\
  -H 'apikey: <anon key>' \\
  -H 'Authorization: Bearer <anon key>'
curl 'https://api.collegedata.fyi/rest/v1/scorecard_summary?select=ipeds_id,earnings_10yr_median,median_debt_monthly_payment,median_debt_completers,avg_net_price,endowment_end,instructional_expenditure_fte,enrollment&earnings_10yr_median=gt.0&median_debt_monthly_payment=gt.0&avg_net_price=gt.0&endowment_end=gt.0&limit=1000&offset=2000' \\
  -H 'apikey: <anon key>' \\
  -H 'Authorization: Bearer <anon key>'`}
        </pre>
        <p style={{ color: "var(--ink-2)", fontSize: 14, lineHeight: 1.55, margin: "16px 0 0" }}>
          For Panel A, keep non-need aid shares between 0 and 1, average
          non-need grants between $0 and $80,000, and merit profiles rated{" "}
          <code>strong</code> or <code>partial</code>. Keep{" "}
          <code>non_need_aid_share_first_year_ft</code> in [0, 1] and{" "}
          <code>avg_non_need_grant_first_year_ft</code> in [0, 80000]. A
          published $0 grant is kept.
        </p>
        <p style={{ color: "var(--ink-2)", fontSize: 14, lineHeight: 1.55, margin: "14px 0 0" }}>
          Panel A joins endowment from <code>scorecard_summary</code> and
          undergraduate enrollment from{" "}
          <code>school_browser_rows.undergrad_enrollment_scorecard</code>.
        </p>
        <p style={{ color: "var(--ink-2)", fontSize: 14, lineHeight: 1.55, margin: "14px 0 0" }}>
          Panel B joins undergraduate enrollment from{" "}
          <code>institution_directory.undergraduate_enrollment</code>, using
          Scorecard enrollment as a fallback, and keeps schools with a recent
          CDS SAT composite midpoint.
        </p>
        <p style={{ color: "var(--ink-2)", fontSize: 14, lineHeight: 1.55, margin: "14px 0 0" }}>
          Both panels then use the same calculations:
        </p>
        <p style={{ color: "var(--ink-2)", fontSize: 14, lineHeight: 1.55, margin: "14px 0 0" }}>
          <code>burden = monthly payment × 12 ÷ earnings</code>
        </p>
        <p style={{ color: "var(--ink-2)", fontSize: 14, lineHeight: 1.55, margin: "8px 0 0" }}>
          <code>gap = completer debt × (1 − median burden ÷ burden) ÷ 4</code>
        </p>
        <p style={{ color: "var(--ink-2)", fontSize: 14, lineHeight: 1.55, margin: "8px 0 0" }}>
          <code>merit per first-year = share receiving non-need aid × average non-need grant</code>
        </p>
        <p style={{ color: "var(--ink-2)", fontSize: 14, lineHeight: 1.55, margin: "14px 0 0" }}>
          The anonymous API key is available on the <Link href="/api">API page</Link>.
          To rebuild the checked-in dataset:{" "}
          <code>python3 tools/scorecard/build_alignment_gap_recipe.py</code>
        </p>
        <div style={{ marginTop: 14, display: "flex", gap: 16, flexWrap: "wrap", fontSize: 13 }}>
          <TrackedLink
            external
            href="https://github.com/bolewood/collegedata-fyi/blob/main/docs/recipes/alignment-gap.md"
            target="_blank"
            rel="noopener noreferrer"
            analyticsEvent="recipe_writeup_opened"
            analyticsProperties={{ surface: "recipe_detail", recipe: "alignment-gap" }}
          >
            Read the full write-up →
          </TrackedLink>
          <Link href="/recipes/acceptance-vs-yield">College Pricing Power</Link>
        </div>
      </section>
    </div>
  );
}
