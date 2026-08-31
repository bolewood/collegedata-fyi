import type { Metadata } from "next";
import Link from "next/link";
import { AcceptanceYieldChart } from "@/components/AcceptanceYieldChart";
import { TrackedLink } from "@/components/TrackedLink";
import { YieldDebtBurdenChart } from "@/components/YieldDebtBurdenChart";
import {
  formatBurdenPercent,
  formatRatePercent,
  formatUsd,
  formatUsdCents,
  isPanelBSchool,
  panelBSchools,
  type PricingPowerPanelBSchool,
  type PricingPowerSchool,
} from "@/lib/pricing-power-recipe-analysis";
import {
  PRICING_POWER_ANNOTATION_SCHOOL_ID,
  PRICING_POWER_META,
  PRICING_POWER_SCHOOLS,
} from "@/lib/pricing-power-recipe-data";

export const metadata: Metadata = {
  title: "College Pricing Power",
  description: "Acceptance, yield, price, and student outcomes.",
  alternates: { canonical: "/recipes/acceptance-vs-yield" },
  openGraph: {
    url: "/recipes/acceptance-vs-yield",
    title: "College Pricing Power",
    description: "Acceptance, yield, price, and student outcomes.",
  },
};

const prose = {
  fontSize: 16,
  lineHeight: 1.65,
  color: "var(--ink-2)",
  margin: "14px 0 0",
} as const;

const proseFirst = { ...prose, margin: 0 } as const;

function requireSchool(id: string): PricingPowerSchool {
  const row = PRICING_POWER_SCHOOLS.find((school) => school.schoolId === id);
  if (!row) throw new Error(`pricing-power dataset missing ${id}`);
  return row;
}

function requirePanelB(id: string): PricingPowerPanelBSchool {
  const row = requireSchool(id);
  if (!isPanelBSchool(row)) {
    throw new Error(`pricing-power dataset missing Panel B fields for ${id}`);
  }
  return row;
}

const syracuse = requirePanelB(PRICING_POWER_ANNOTATION_SCHOOL_ID);
const fordham = requirePanelB("fordham-university");
const american = requirePanelB("american-university");
const smu = requirePanelB("southern-methodist-university");
const panelB = panelBSchools(PRICING_POWER_SCHOOLS);
const debtAt27000 = panelB.filter((row) => row.medianDebt === 27_000).length;
const scorecardYears = PRICING_POWER_META.scorecardYears.join(", ");
const annualPayment = syracuse.monthlyPayment * 12;
const medianAcceptancePct = formatRatePercent(
  PRICING_POWER_META.medianAcceptance,
  1,
);
const medianYieldPct = formatRatePercent(PRICING_POWER_META.medianYield, 1);
const medianYieldBPct = formatRatePercent(PRICING_POWER_META.medianYieldB, 1);
const medianBurdenPct = formatBurdenPercent(PRICING_POWER_META.medianBurden);
const panelACount = PRICING_POWER_META.panelACount.toLocaleString("en-US");
const panelBCount = PRICING_POWER_META.panelBCount.toLocaleString("en-US");

const QUADRANTS_A = [
  {
    num: "I",
    head: "Lower acceptance · higher yield",
    count: PRICING_POWER_META.quadrantsA.lowerAcceptanceHigherYield,
    body: `These schools admit a smaller share of applicants than the sample median and enroll a larger share of those they accept than the sample median. That combination can reflect student preference, binding Early Decision, geography, aid, athletics, or a self-selected applicant pool. The chart does not tell us which.`,
  },
  {
    num: "II",
    head: "Higher acceptance · higher yield",
    count: PRICING_POWER_META.quadrantsA.higherAcceptanceHigherYield,
    body: "These schools admit a larger share of applicants while still enrolling a relatively large share of those they accept. That can happen at public flagships, regional institutions, specialized colleges, or schools whose applicants are especially likely to enroll if admitted.",
  },
  {
    num: "III",
    head: "Lower acceptance · lower yield",
    count: PRICING_POWER_META.quadrantsA.lowerAcceptanceLowerYield,
    body: `These schools admit a smaller share of applicants than this sample's median (${medianAcceptancePct}) but enroll a smaller share of admits than the median (${medianYieldPct}). In this file, “below-median acceptance” still includes many colleges that admit 60% or 70% of applicants. Many of these schools compete for students who have several attractive alternatives. A below-median yield should not be read as evidence that the school is undesirable.`,
  },
  {
    num: "IV",
    head: "Higher acceptance · lower yield",
    count: PRICING_POWER_META.quadrantsA.higherAcceptanceLowerYield,
    body: "These schools admit a larger share of applicants and enroll a smaller share of those admitted. For enrollment teams, this combination can make class size harder to predict because more offers may be required to fill each seat.",
  },
];

const QUADRANTS_B = [
  {
    num: "I",
    head: "Higher yield · higher debt burden",
    count: PRICING_POWER_META.quadrantsB.higherYieldHigherBurden,
    body: "These schools enroll a relatively large share of the students they admit, while federal loan payments are also relatively high compared with later earnings. Higher yield means a larger share of admits enrolled. That is not the same thing as students preferring the school over every alternative. The debt measure asks a separate question about federal borrowing among federally aided students afterward.",
  },
  {
    num: "II",
    head: "Lower yield · higher debt burden",
    count: PRICING_POWER_META.quadrantsB.lowerYieldHigherBurden,
    body: "These schools enroll a smaller share of admitted students and also have above-median federal debt burden. That combination is worth looking at more closely: a smaller share of admits enrolled, and federal loan payments are also above the sample median relative to later earnings. It does not tell us why either condition exists — competition, aid design, applicant mix, earnings, or borrowing can each produce the same pair of numbers.",
  },
  {
    num: "III",
    head: "Higher yield · lower debt burden",
    count: PRICING_POWER_META.quadrantsB.higherYieldLowerBurden,
    body: "These schools combine relatively strong enrollment conversion with below-median federal debt burden. Both of these measures sit on the better-looking side of this sample’s medians. That says nothing by itself about academic quality, access, family wealth, or the experience of students who do not borrow.",
  },
  {
    num: "IV",
    head: "Lower yield · lower debt burden",
    count: PRICING_POWER_META.quadrantsB.lowerYieldLowerBurden,
    body: "These schools enroll a smaller share of admitted students, but federal loan payments are relatively modest compared with later earnings. This is an important reminder that a below-median yield in one admissions cycle does not mean a college produces poor federal-loan outcomes for the federally aided students in the Scorecard file.",
  },
];

export default function AcceptanceVsYieldPage() {
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
            / <span style={{ color: "var(--ink)" }}>COLLEGE PRICING POWER</span>
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
            College Pricing Power
          </h1>
        </div>
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap", justifyContent: "flex-end" }}>
          <span className="cd-chip">IPEDS</span>
          <span className="cd-chip">College Scorecard</span>
          <span className="cd-chip">CDS C1 (cross-check)</span>
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
          College prices tell only part of the story.
        </p>
        <p style={prose}>
          A school can publish a very high price and still offer enough grant aid
          that many students are billed much less than sticker. It can be highly
          selective but lose many of the students it admits to other colleges.
          And students at two similarly priced schools can leave with very
          different debt relative to what they later earn.
        </p>
        <p style={prose}>This page puts several of those measures together.</p>
        <p style={prose}>
          We start with <strong>acceptance rate and yield</strong>. Acceptance
          rate is the share of applicants a college admits. Yield is the share
          of admitted students who actually enroll.
        </p>
        <p style={prose}>
          Then we add financial outcomes. For schools with enough federal data,
          we compare yield with <strong>debt burden</strong>: annual federal
          student-loan payments as a share of median earnings 10 years after
          enrollment.
        </p>
        <p style={prose}>
          None of these measures, by itself, tells us whether a college is
          &ldquo;worth it.&rdquo; This page does not estimate how enrollment
          would change if a college changed its price. Together, the numbers
          show how broadly a school admits, how often admitted students enroll,
          what federally aided students pay after grant aid, and how federal
          loan payments compare with later earnings.
        </p>
      </div>

      <section className="endowment-recipe-ledger rule-2" style={{ marginTop: 28 }}>
        <div>
          <strong>{panelACount}</strong>
          <small>Schools with usable acceptance and yield data</small>
        </div>
        <div>
          <strong>{medianYieldPct}</strong>
          <small>Median yield in that sample</small>
        </div>
        <div>
          <strong>{panelBCount}</strong>
          <small>Schools in the joined yield and debt sample</small>
        </div>
        <div>
          <strong>{medianBurdenPct}</strong>
          <small>Median debt burden in the joined sample</small>
        </div>
      </section>

      <section style={{ marginTop: 48, maxWidth: 760 }}>
        <h2 className="serif" style={{ fontSize: 28, margin: "0 0 12px", letterSpacing: "-0.015em" }}>
          Acceptance and yield
        </h2>
        <p style={proseFirst}>
          The horizontal axis shows acceptance rate: the share of applicants a
          school admits.
        </p>
        <p style={prose}>
          The vertical axis shows yield: the share of admitted students who
          enroll.
        </p>
        <p style={prose}>
          A school toward the upper-left is below this sample&apos;s median
          acceptance rate and above its median yield. A school toward the
          lower-right is the reverse. Because the median school admits about{" "}
          {medianAcceptancePct}{" "}of applicants, &ldquo;below the median&rdquo; is
          not another way of saying highly selective.
        </p>
        <p style={prose}>
          Yield is useful, but it needs context. A high yield can reflect strong
          student demand, binding Early Decision, geography, price, financial
          aid, athletics, a specialized mission, or simply an applicant pool
          that already knows the school well. A low yield can reflect intense
          competition for students rather than weak academic quality.
        </p>
      </section>

      <section style={{ marginTop: 28 }}>
        <AcceptanceYieldChart />
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
        {QUADRANTS_A.map((q) => (
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
          Now add student outcomes
        </h2>
        <p style={proseFirst}>
          Acceptance and yield describe how a college fills a class: how many
          applicants it admits, and how many of those admits enroll. They do
          not tell us what happens financially to students who enroll.
        </p>
        <p style={prose}>
          For that, we can join admissions data to the College Scorecard.
        </p>
        <p style={prose}>
          The next chart keeps yield on one axis and adds{" "}
          <strong>debt burden</strong> on the other. Debt burden is the share
          of median 10-year earnings represented by one year of median federal
          student-loan payments.
        </p>
        <p style={prose}>
          This is not a measure of total college cost. It covers federal student
          debt, and many families pay for college with savings, current income,
          grants, parent borrowing, private loans, or other resources.
        </p>
        <p style={prose}>It answers a narrower question:</p>
        <p style={prose}>
          <strong>
            How large are median federal loan payments, as estimated from
            completer debt, relative to median earnings of federally aided
            students about 10 years after they first enrolled?
          </strong>
        </p>
        <p style={prose}>
          Figure 2 uses a smaller sample ({panelBCount} schools) because it
          requires Scorecard debt, earnings, net price, and instructional
          spending. Its yield median is {medianYieldBPct}, not the{" "}
          {medianYieldPct}{" "}used in Figure 1. A school can sit on different
          sides of &ldquo;higher yield&rdquo; in the two charts.
        </p>
      </section>

      <section className="endowment-recipe-ledger rule-2" style={{ marginTop: 28 }}>
        <div>
          <strong>{panelBCount}</strong>
          <small>Schools with yield and Scorecard debt, earnings, and net price</small>
        </div>
        <div>
          <strong>{medianYieldBPct}</strong>
          <small>Median yield in Figure 2</small>
        </div>
        <div>
          <strong>{medianBurdenPct}</strong>
          <small>Median debt burden in Figure 2</small>
        </div>
        <div>
          <strong>{PRICING_POWER_META.exclusions.missingNonpositiveScorecard}</strong>
          <small>Schools dropped from Figure 1 for missing Scorecard fields</small>
        </div>
      </section>

      <section style={{ marginTop: 28 }}>
        <YieldDebtBurdenChart />
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
        {QUADRANTS_B.map((q) => (
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
          Syracuse: high published price, ordinary federal-loan burden
        </h2>
        <p style={proseFirst}>
          Syracuse is a useful example of why these measures belong on the same
          page.
        </p>
        <p style={prose}>
          The Wall Street Journal&apos;s August 2026 account describes a 1.5%
          budget shortfall for the academic year that began in August 2026,
          late merit-aid offers for the fall 2025 class, and a published cost
          of attendance of $98,544. The admissions numbers on the charts are
          older: IPEDS ADM2024, the fall 2024 first-time class. They are not a
          picture of the shortfall year.
        </p>
        <p style={prose}>
          The admissions figures on this page are from the fall 2024 entering
          class, the most recent IPEDS ADM release. The Journal&apos;s account
          of late merit-aid offers describes recruiting for the fall 2025 class.
          The 1.5% budget shortfall, and the chancellor&apos;s wait-list
          remarks, refer to the academic year that began in August 2026. The
          charts do not depict the shortfall year, and the Scorecard debt and
          earnings figures describe earlier cohorts still.
        </p>
        <p style={prose}>
          Sticker price is important, but it is not the College Scorecard
          net-price figure. That figure averages what Title IV aid recipients
          paid after grant aid; it is not what a full-pay family is billed.
        </p>
        <p style={prose}>
          Federal student-debt data tell another part of the story.
        </p>
        <p style={prose}>
          Using the same College Scorecard methodology as the rest of this page,
          Syracuse&apos;s median annual federal-loan payment is about{" "}
          <strong>{formatUsd(annualPayment)}</strong> (
          {formatUsdCents(syracuse.monthlyPayment)} × 12), against median 10-year
          earnings of {formatUsd(syracuse.earnings10yr)}. That produces a debt
          burden of {formatBurdenPercent(syracuse.burden)}. The median for the
          schools in this comparison is {medianBurdenPct}. In the fall 2024
          admissions file, Syracuse admitted{" "}
          {syracuse.admitted.toLocaleString("en-US")} of{" "}
          {syracuse.applied.toLocaleString("en-US")} applicants (
          {formatRatePercent(syracuse.acceptanceRate, 2)}) and enrolled{" "}
          {syracuse.enrolled.toLocaleString("en-US")} (
          {formatRatePercent(syracuse.yieldRate, 2)} yield). Average net price
          for Title IV recipients is {formatUsd(syracuse.avgNetPrice)}. Median
          completer debt is {formatUsd(syracuse.medianDebt)}.
        </p>
        <p style={prose}>
          A published cost of attendance near $100,000 does not, in this
          federal-loan measure, come with unusually heavy payments relative to
          later earnings. The fall 2024 admissions file shows a high average
          net price for Title IV recipients and a yield near the middle of this
          sample. It does not show a federal-debt-burden outlier, and it does
          not depict the fall 2025 recruiting scramble or the fall 2026
          shortfall described by the Journal.
        </p>
        <p style={prose}>
          Syracuse is not the only college in this part of the chart.{" "}
          {fordham.name} ({formatRatePercent(fordham.yieldRate, 1)} yield,{" "}
          {formatBurdenPercent(fordham.burden)} burden,{" "}
          {formatUsd(fordham.avgNetPrice)} net price), {american.name} (
          {formatRatePercent(american.yieldRate, 1)},{" "}
          {formatBurdenPercent(american.burden)}, {formatUsd(american.avgNetPrice)}
          ), and {smu.name} ({formatRatePercent(smu.yieldRate, 1)},{" "}
          {formatBurdenPercent(smu.burden)}, {formatUsd(smu.avgNetPrice)}) also
          sit below both Panel B medians on yield and burden while posting
          above-median Title IV net prices. Northeastern, Boston University, and
          NYU — the Journal&apos;s full-pay comparison set — do not: each has a
          much higher fall 2024 yield.
        </p>
        <p style={prose}>
          Federal data for 2023–24, as reported by The Wall Street Journal,
          show 21% of Syracuse undergraduates paying full sticker price,
          compared with 40% at Northeastern, 49% at Boston University, and 58%
          at NYU. Those shares are NCES figures, not a Journal original survey.
          Those three schools are not yield peers in this file: each converted
          a much larger share of its fall 2024 admits than Syracuse did.
        </p>
        <p style={prose}>
          The Journal describes several forces that can lower enrollment without
          showing up as a federal-loan burden, and this page does not separate
          them: a 2025 drop of about half in international enrollment after visa
          disruption; Syracuse&apos;s location in a snowy, geographically
          isolated city; competition from cheaper public flagships, including
          Sun Belt campuses; weaker national sports visibility (men&apos;s
          basketball out of the NCAA tournament for five seasons; football
          mostly losing since 2000); admissions execution (slow
          regular-decision turnaround, little follow-up after the offer, late
          2025 merit-aid offers the chancellor says will not be repeated); the
          April 2026 choice largely not to take the wait list; housing (a 2022
          over-enrollment that put students in a Sheraton, then $458 million of
          dorm borrowing in 2025); and a falling number of 18- to 24-year-olds.
          The chancellor told the Journal the fall 2026 shortfall was not a
          lack of demand.
        </p>
        <p style={prose}>
          Syracuse&apos;s chancellor told the Journal that in April 2026 the
          university could have pulled from its wait list and largely decided
          not to, in order to maintain academic standards, and that the
          shortfall was not due to a lack of demand.
        </p>
      </section>

      <section style={{ marginTop: 48, maxWidth: 760 }}>
        <h2 className="serif" style={{ fontSize: 28, margin: "0 0 12px", letterSpacing: "-0.015em" }}>
          What we mean by pricing power
        </h2>
        <p style={proseFirst}>
          &ldquo;Pricing power&rdquo; is a shorthand for a cluster of related
          questions. It is not a number this page computes.
        </p>
        <p style={prose}>
          We are putting several published measures about the same college on
          one page: how broadly it admits, how often admits enroll, what Title
          IV recipients pay after grant aid, and how large federal loan payments
          are relative to later earnings.
        </p>
        <p style={prose}>
          Acceptance rate tells us how broadly a college admits.
        </p>
        <p style={prose}>
          Yield tells us how often an offer of admission becomes an enrollment.
        </p>
        <p style={prose}>
          Average net price tells us what undergraduates who received Title IV
          federal aid paid, on average, after grant and scholarship aid. It is
          not the bill for a full-pay family, and full-pay students are not in
          the average.
        </p>
        <p style={prose}>
          Debt burden adds a later outcome for federally aided students.
        </p>
        <p style={prose}>
          High yield is sometimes treated as a sign that a school could raise
          price without losing students. This page does not test that. It does
          not estimate elasticity, markups, or the price at which a class would
          fail to fill. A school can post a high yield because of binding Early
          Decision, generous aid, geography, athletics, a specialized mission,
          or an applicant pool that already planned to enroll.
        </p>
        <p style={prose}>
          Low yield does not prove a school needs to lower its price, and it
          does not measure how many students wanted to attend.
        </p>
        <p style={prose}>
          The point is to put the measures next to one another so those
          questions can be asked with better evidence.
        </p>
      </section>

      <section style={{ marginTop: 48, maxWidth: 760 }}>
        <h2 className="serif" style={{ fontSize: 28, margin: "0 0 12px", letterSpacing: "-0.015em" }}>
          How debt burden is calculated
        </h2>
        <p style={proseFirst}>
          Debt burden starts with two College Scorecard measures:
        </p>
        <p style={prose}>
          <code>
            debt burden = median monthly federal-loan payment × 12 ÷ median
            earnings 10 years after enrollment
          </code>
        </p>
        <p style={prose}>
          The monthly payment is a Scorecard estimate derived from median
          federal debt among completers, not the amount a typical alumnus is
          observed to send a servicer. Earnings are for federally aided students
          working and not enrolled, including people who did not complete. Debt
          and earnings are therefore not the same population.
        </p>
        <p style={prose}>
          For example, annual loan payments of $3,000 against median earnings of
          $60,000 would produce a debt burden of 5%.
        </p>
        <p style={prose}>The measure has important limits.</p>
        <p style={prose}>
          It covers federal student borrowing, not every way families finance
          college. Median earnings describe federally aided students from an
          earlier cohort, roughly a decade after enrollment. The admissions data
          on this page describe much more recent applicants.
        </p>
        <p style={prose}>
          The join is therefore <strong>institutional, not longitudinal</strong>.
          We are comparing different measures reported about the same college,
          not following one graduating class through time.
        </p>
      </section>

      <section style={{ marginTop: 48, maxWidth: 760 }}>
        <h2 className="serif" style={{ fontSize: 28, margin: "0 0 12px", letterSpacing: "-0.015em" }}>
          What is being joined
        </h2>
        <p style={proseFirst}>
          The two charts join different years. Acceptance and yield are IPEDS
          ADM2024 (first-time students entering fall 2024). Average net price,
          federal debt, estimated monthly payments, 10-year earnings, and
          instructional spending per FTE come from the College Scorecard{" "}
          {scorecardYears} file. Scorecard earnings describe federally aided
          students from a much earlier entering cohort, measured about 10 years
          after they first enrolled. Average net price is also from{" "}
          {scorecardYears}, not from the fall 2024 class. The join is by
          institution, not by one class of students moving through college.
        </p>
        <p style={prose}>
          After requiring positive applicant, admitted, and enrolled counts,
          with admitted no greater than applied and enrolled no greater than
          admitted, and after dropping institutions outside the public
          directory&apos;s in-scope set, {panelACount} schools remain for Figure
          1. {PRICING_POWER_META.exclusions.missingZeroCounts} rows are removed
          for missing or zero counts, and{" "}
          {PRICING_POWER_META.exclusions.outOfScope} are out of scope.
        </p>
        <p style={prose}>
          Figure 2 keeps the {panelBCount} of those schools that also have
          positive College Scorecard debt, earnings, net price, and
          instructional spending.{" "}
          {PRICING_POWER_META.exclusions.missingNonpositiveScorecard} schools
          drop at that join.
        </p>
        <p style={prose}>
          Where a school also has a complete Common Data Set C1 row for
          2024–25, the tooltip shows that acceptance and yield as a
          cross-check. In this build that is{" "}
          {PRICING_POWER_META.cdsAttachedCount.toLocaleString("en-US")} of{" "}
          {panelACount} schools. Syracuse has no CDS C1 row in the serving data.
          Plotted positions always use IPEDS ADM2024.
        </p>
      </section>

      <section style={{ marginTop: 48, maxWidth: 760 }}>
        <h2 className="serif" style={{ fontSize: 28, margin: "0 0 12px", letterSpacing: "-0.015em" }}>
          Data limits
        </h2>
        <p style={proseFirst}>
          This page combines institutional data from different systems and
          different years. The numbers should not be read as if they describe
          one group of students moving through college at the same time.
          Earnings are from federally aided students who enrolled about a
          decade before the Scorecard {scorecardYears} file. Fall 2024 admits
          are not those earners, and they are not the fall 2026 class in the
          Journal article.
        </p>
        <p style={prose}>
          Yield is not pure demand. It is affected by admissions strategy,
          binding Early Decision, financial aid, geography, applicant
          self-selection, athletics, and other factors. At most schools, yield
          has fallen by about half over two decades as students apply to about
          three times as many schools (federal data, as reported by the
          Journal).
        </p>
        <p style={prose}>
          Average net price is the College Scorecard figure for undergraduates
          who received Title IV federal aid. Full-pay students are not in that
          average, so the number is not what a typical full-pay family pays and
          is not an enrollment-weighted average of the whole undergraduate body.
        </p>
        <p style={prose}>
          Debt burden is incomplete. It covers federal student borrowing, not
          Parent PLUS, private loans, savings, cash payments, or students who
          did not borrow.
        </p>
        <p style={prose}>
          Median federal completer debt clusters at common federal loan limits.
          In this sample, {debtAt27000.toLocaleString("en-US")} schools report
          exactly $27,000. A lower debt burden at a high-price college can be
          high later earnings, not a smaller bill.
        </p>
        <p style={prose}>
          Some branch campuses inherit a parent College Scorecard record, so
          debt, earnings, and burden can repeat across related institutions.
          Those repeats are kept as reported. They do not include Syracuse.
        </p>
        <p style={prose}>
          The sample includes very small and special-mission institutions with
          near-100% yield. Those schools pull the mean yield up. Quadrants use
          medians so that tail does not set the middle of the chart.
        </p>
        <p style={prose}>
          Instructional spending per student divided by average net price is
          not a budget share. The two numbers come from different systems and
          describe different populations. Never read the remainder as
          administrative spending.
        </p>
        <p style={prose}>
          Correlation is not causation. These charts do not show that price
          caused yield, that debt caused yield, or that instructional spending
          caused either.
        </p>
      </section>

      <section style={{ marginTop: 48 }}>
        <h2 className="serif" style={{ fontSize: 28, margin: "0 0 12px", letterSpacing: "-0.015em" }}>
          Pull the data yourself
        </h2>
        <p style={{ ...proseFirst, maxWidth: 760, marginBottom: 16 }}>
          The underlying data and calculations are public. The queries below
          reproduce the source rows used for the two panels. Each IPEDS field
          and the Scorecard table contain more rows than the API&apos;s
          1,000-row response limit, so retrieve them in pages. Compute
          acceptance and yield from the raw counts; do not plot the
          integer-rounded <code>admit_rate_total</code> or{" "}
          <code>yield_rate_total</code> fields.
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
{`# Panel A — IPEDS ADM2024 counts from school_facts_unified (long format)
# Repeat for field_key=eq.admissions_total and field_key=eq.enrolled_total.
# PostgREST max-rows is 1,000. limit=5000 and Range: 0-4999 are both capped
# at 1,000 with HTTP 206. Page with offset:
curl 'https://api.collegedata.fyi/rest/v1/school_facts_unified?select=school_id,school_name,ipeds_id,in_scope,field_key,value_numeric,source_table,data_year,quality_flag&field_key=eq.applicants_total&source_table=eq.ADM2024&order=ipeds_id.asc&limit=1000&offset=0' \\
  -H 'apikey: <anon key>' \\
  -H 'Authorization: Bearer <anon key>'
curl 'https://api.collegedata.fyi/rest/v1/school_facts_unified?select=school_id,school_name,ipeds_id,in_scope,field_key,value_numeric,source_table,data_year,quality_flag&field_key=eq.applicants_total&source_table=eq.ADM2024&order=ipeds_id.asc&limit=1000&offset=1000' \\
  -H 'apikey: <anon key>' \\
  -H 'Authorization: Bearer <anon key>'

# Panel B — College Scorecard join fields
curl 'https://api.collegedata.fyi/rest/v1/scorecard_summary?select=ipeds_id,scorecard_data_year,earnings_10yr_median,median_debt_monthly_payment,median_debt_completers,avg_net_price,instructional_expenditure_fte&order=ipeds_id.asc&limit=1000&offset=0' \\
  -H 'apikey: <anon key>' \\
  -H 'Authorization: Bearer <anon key>'
curl 'https://api.collegedata.fyi/rest/v1/scorecard_summary?select=ipeds_id,scorecard_data_year,earnings_10yr_median,median_debt_monthly_payment,median_debt_completers,avg_net_price,instructional_expenditure_fte&order=ipeds_id.asc&limit=1000&offset=1000' \\
  -H 'apikey: <anon key>' \\
  -H 'Authorization: Bearer <anon key>'

# CDS C1 2024-25 tooltip cross-check (complete rows; under the 1,000-row cap)
curl 'https://api.collegedata.fyi/rest/v1/school_browser_rows?select=school_id,ipeds_id,canonical_year,sub_institutional,acceptance_rate,yield_rate&canonical_year=eq.2024-25&sub_institutional=is.null&acceptance_rate=not.is.null&yield_rate=not.is.null' \\
  -H 'apikey: <anon key>' \\
  -H 'Authorization: Bearer <anon key>'`}
        </pre>
        <p style={{ color: "var(--ink-2)", fontSize: 14, lineHeight: 1.55, margin: "16px 0 0" }}>
          Keep schools with positive applied, admitted, and enrolled counts;
          drop rows where admitted exceeds applied or enrolled exceeds admitted;
          keep the public directory&apos;s in-scope institutions. For Figure 2,
          also require positive{" "}
          <code>median_debt_monthly_payment</code>,{" "}
          <code>earnings_10yr_median</code>, <code>avg_net_price</code>, and{" "}
          <code>instructional_expenditure_fte</code>.
        </p>
        <p style={{ color: "var(--ink-2)", fontSize: 14, lineHeight: 1.55, margin: "14px 0 0" }}>
          Then:
        </p>
        <p style={{ color: "var(--ink-2)", fontSize: 14, lineHeight: 1.55, margin: "8px 0 0" }}>
          <code>acceptance = admitted ÷ applied</code>
        </p>
        <p style={{ color: "var(--ink-2)", fontSize: 14, lineHeight: 1.55, margin: "8px 0 0" }}>
          <code>yield = enrolled ÷ admitted</code>
        </p>
        <p style={{ color: "var(--ink-2)", fontSize: 14, lineHeight: 1.55, margin: "8px 0 0" }}>
          <code>burden = monthly payment × 12 ÷ earnings</code>
        </p>
        <p style={{ color: "var(--ink-2)", fontSize: 14, lineHeight: 1.55, margin: "8px 0 0" }}>
          <code>instruction / net price = instructional expenditure per FTE ÷ average net price</code>
        </p>
        <p style={{ color: "var(--ink-2)", fontSize: 14, lineHeight: 1.55, margin: "14px 0 0" }}>
          The anonymous API key is available on the <Link href="/api">API page</Link>.
          To rebuild the checked-in dataset:{" "}
          <code>python3 tools/ipeds/build_pricing_power_recipe.py</code>
        </p>
        <div style={{ marginTop: 14, display: "flex", gap: 16, flexWrap: "wrap", fontSize: 13 }}>
          <TrackedLink
            external
            href="https://github.com/bolewood/collegedata-fyi/blob/main/docs/recipes/acceptance-vs-yield.md"
            target="_blank"
            rel="noopener noreferrer"
            analyticsEvent="recipe_writeup_opened"
            analyticsProperties={{
              surface: "recipe_detail",
              recipe: "acceptance-vs-yield",
            }}
          >
            Read the full write-up →
          </TrackedLink>
          <TrackedLink
            external
            href="/recipes/acceptance-vs-yield-starter.xlsx"
            analyticsEvent="download_clicked"
            analyticsProperties={{
              surface: "recipe_detail",
              file_type: "xlsx",
              item: "acceptance_vs_yield_starter",
            }}
          >
            Download XLSX starter
          </TrackedLink>
        </div>
      </section>
    </div>
  );
}
