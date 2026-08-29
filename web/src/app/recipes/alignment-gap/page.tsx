import type { Metadata } from "next";
import Link from "next/link";
import { AlignmentGapChart } from "@/components/AlignmentGapChart";
import { AlignmentGapMeritChart } from "@/components/AlignmentGapMeritChart";
import { TrackedLink } from "@/components/TrackedLink";
import { formatRecipeShare } from "@/lib/format";
import {
  formatEndowmentPerStudent,
  formatUsd,
  type AlignmentGapMeritRow,
} from "@/lib/alignment-gap-recipe-analysis";
import {
  ALIGNMENT_GAP_MERIT_META,
  ALIGNMENT_GAP_MERIT_SCHOOLS,
  ALIGNMENT_GAP_META,
} from "@/lib/alignment-gap-recipe-data";

export const metadata: Metadata = {
  title: "Alignment gap",
  description:
    "Whether a school is already spending its alignment gap on non-need merit aid, plotted against College Scorecard debt burden and IPEDS endowment.",
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
  "kentucky-state-university",
  "hollins-university",
  "baker-college",
  "north-carolina-a-and-t-state-university",
  "point-park-university",
] as const;

const meritById = new Map(
  ALIGNMENT_GAP_MERIT_SCHOOLS.map((row) => [row.schoolId, row]),
);

function requireMerit(id: string): AlignmentGapMeritRow {
  const row = meritById.get(id);
  if (!row) throw new Error(`merit join missing ${id}`);
  return row;
}

const COVERS_EXAMPLES = COVERS_EXAMPLE_IDS.map(requireMerit);
const TRAPPED_EXAMPLES = TRAPPED_EXAMPLE_IDS.map(requireMerit);
const ex = ALIGNMENT_GAP_MERIT_META.exclusions;
const coversPct = formatRecipeShare(ALIGNMENT_GAP_MERIT_META.coversShare, 0);

const REGIONS = [
  {
    num: "A",
    head: "Already spending it",
    count: ALIGNMENT_GAP_MERIT_META.regions.covers,
    body: `${ALIGNMENT_GAP_MERIT_META.regions.covers} of ${ALIGNMENT_GAP_MERIT_META.positiveGap} — ${coversPct} — spend more per first-year student on non-need merit aid than their entire annual alignment gap. Quincy is the discounting model in one row: every first-year gets merit aid averaging $27,587 against a $20,359 net price.`,
  },
  {
    num: "B",
    head: "Genuinely constrained",
    count: ALIGNMENT_GAP_MERIT_META.regions.constrained,
    body: "Positive gap, merit spend below it. This list is mostly regional publics and HBCUs. It is the control group, not a target list — schools whose discount is already spoken for, or was never large enough to close the gap.",
  },
  {
    num: "C",
    head: "No gap to close",
    count: ALIGNMENT_GAP_MERIT_META.regions.none,
    body: "Burden at or below this merit sample’s median. The money question does not arise. They stay on the chart so the diagonal has a below as well as an above.",
  },
];

const QUADRANTS = [
  {
    num: "I",
    head: "Capacity exists",
    count: ALIGNMENT_GAP_META.quadrants.capacity,
    body: "Burden above the median, and endowment above it too. If price and outcome are out of line here, the money to close the gap is on the balance sheet. Hollins sits furthest out: an 8.6% burden against about $457k per student.",
  },
  {
    num: "II",
    head: "Constrained",
    count: ALIGNMENT_GAP_META.quadrants.constrained,
    body: "The same elevated burden, without the endowment to buy the price down. Bennington lives here — high burden on a modest per-student endowment, and the lowest instruction-to-net-price ratio of its peer group at 0.76.",
  },
  {
    num: "III",
    head: "Endowment absorbs it",
    count: ALIGNMENT_GAP_META.quadrants.absorbs,
    body: "Grinnell, Princeton, Stanford, Wellesley — low burden next to large per-student wealth. Instruction often exceeds net price — at these endowment levels, tuition is not what pays for the classroom.",
  },
  {
    num: "IV",
    head: "Earnings do the work",
    count: ALIGNMENT_GAP_META.quadrants.earnings,
    body: "No unusual wealth, low burden anyway, because graduates earn enough to carry the debt. Bentley, Babson, and Santa Clara sit here.",
  },
];

export default function AlignmentGapPage() {
  const meritMedianBurden = formatRecipeShare(
    ALIGNMENT_GAP_MERIT_META.medianBurden,
    2,
  );
  const endowmentMedianBurden = formatRecipeShare(
    ALIGNMENT_GAP_META.medianBurden,
    2,
  );
  const medianEndowment = formatEndowmentPerStudent(
    ALIGNMENT_GAP_META.medianEndowmentPerStudent,
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
              lineHeight: 1,
            }}
          >
            What a school charges, against what it{" "}
            <span style={{ fontStyle: "italic" }}>delivers.</span>
          </h1>
          <p
            className="serif"
            style={{
              maxWidth: 740,
              marginTop: 12,
              color: "var(--ink-2)",
              fontSize: 18,
              fontStyle: "italic",
              lineHeight: 1.55,
            }}
          >
            Debt burden is the share of median 10-year earnings that goes to
            federal loan payments each year. The alignment gap is the completer
            debt a school would have to shed to reach the corpus median burden
            at its own earnings, expressed per year of enrollment. Panel A asks
            whether the school is already spending that money on students who
            did not demonstrate need. Panel B asks whether the endowment could
            close it.
          </p>
        </div>
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap", justifyContent: "flex-end" }}>
          <span className="cd-chip">CDS H2A</span>
          <span className="cd-chip">Scorecard</span>
          <span className="cd-chip">IPEDS</span>
        </div>
      </header>

      <section
        className="endowment-recipe-ledger rule-2"
        style={{ marginTop: 28 }}
      >
        <div>
          <span className="meta">Merit join</span>
          <strong>{ALIGNMENT_GAP_MERIT_META.schoolCount.toLocaleString("en-US")}</strong>
          <small>CDS H2A × Scorecard × IPEDS, after range guards</small>
        </div>
        <div>
          <span className="meta">Already spending it</span>
          <strong>
            {ALIGNMENT_GAP_MERIT_META.regions.covers} of {ALIGNMENT_GAP_MERIT_META.positiveGap}
          </strong>
          <small>
            {coversPct} of schools with a positive gap — merit sample
          </small>
        </div>
        <div>
          <span className="meta">Genuinely constrained</span>
          <strong>{ALIGNMENT_GAP_MERIT_META.regions.constrained.toLocaleString("en-US")}</strong>
          <small>Positive gap, merit spend below it — merit sample</small>
        </div>
        <div>
          <span className="meta">Median burden</span>
          <strong>{meritMedianBurden}</strong>
          <small>Merit sample of {ALIGNMENT_GAP_MERIT_META.schoolCount} — Panel A</small>
        </div>
      </section>

      <p
        className="serif"
        style={{
          maxWidth: 760,
          marginTop: 28,
          fontSize: 20,
          lineHeight: 1.45,
          color: "var(--ink)",
        }}
      >
        {ALIGNMENT_GAP_MERIT_META.regions.covers} of {ALIGNMENT_GAP_MERIT_META.positiveGap} — {coversPct} — spend more per first-year student on non-need merit aid than their entire annual alignment gap. For nearly two-thirds of the schools whose graduates carry an above-median debt burden, the money to close that gap is already leaving the building. It is going to students who don&apos;t need it.
      </p>

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
          Worked examples · already spending it
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
          Worked examples · genuinely constrained
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

      <section className="endowment-recipe-ledger rule-2" style={{ marginTop: 48 }}>
        <div>
          <span className="meta">Endowment join</span>
          <strong>{ALIGNMENT_GAP_META.schoolCount.toLocaleString("en-US")}</strong>
          <small>SAT midpoint, Scorecard, net price, endowment — Panel B</small>
        </div>
        <div>
          <span className="meta">Median debt burden</span>
          <strong>{endowmentMedianBurden}</strong>
          <small>Endowment sample of {ALIGNMENT_GAP_META.schoolCount} — Panel B</small>
        </div>
        <div>
          <span className="meta">Above that burden</span>
          <strong>{ALIGNMENT_GAP_META.aboveMedianBurden.toLocaleString("en-US")}</strong>
          <small>Schools whose graduates carry more than the Panel B median</small>
        </div>
        <div>
          <span className="meta">Median endowment</span>
          <strong>{medianEndowment}</strong>
          <small>Per undergraduate — the vertical divider</small>
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
        <p style={{ fontSize: 16, lineHeight: 1.65, color: "var(--ink-2)", margin: 0 }}>
          Bard and Grinnell enroll students with almost identical median SATs — 1510
          and 1490 — and both land far below what those scores predict for earnings.
          Grinnell charges $17,648 net; Bard charges $34,649. Grinnell&apos;s graduates
          carry a 3.5% debt burden, Bard&apos;s 6.6%. Grinnell also holds $1.54M in
          endowment per undergraduate against Bard&apos;s $69.5k — 22 times as much.
          Same students, same outcomes, opposite prices, and the reason is on the
          balance sheet rather than in the admissions office.
        </p>
        <p style={{ fontSize: 16, lineHeight: 1.65, color: "var(--ink-2)", margin: "14px 0 0" }}>
          The pair shows the mechanism, not the choice set. Grinnell admitted 14.5%
          of applicants in 2024–25 — 1,416 of 9,758 — so most students choosing Bard
          were never choosing between the two. Neither school appears in Panel A:
          they file no usable H2A row. That is why Panel B stays.
        </p>
        <p style={{ fontSize: 16, lineHeight: 1.65, color: "var(--ink-2)", margin: "14px 0 0" }}>
          A 17-year-old comparing these two schools is choosing between a 3.5% debt
          burden and a 6.6% one. Neither school publishes that number. Both publish a
          sticker price. Whether a school <em>should</em> price to its outcomes is
          arguable — whether an applicant should be able to see both numbers before
          signing is not.
        </p>
      </section>

      <section style={{ marginTop: 48, maxWidth: 760 }}>
        <div className="meta" style={{ marginBottom: 8 }}>
          § How the gap is computed
        </div>
        <h2 className="serif" style={{ fontSize: 28, margin: "0 0 12px", letterSpacing: "-0.015em" }}>
          Burden first, then a price movement.
        </h2>
        <p style={{ fontSize: 16, lineHeight: 1.65, color: "var(--ink-2)", margin: 0 }}>
          Burden is <code>median_debt_monthly_payment × 12 ÷ earnings_10yr_median</code>.
          The alignment gap is the completer debt a school would have to shed to
          reach the corpus median burden at its own earnings, expressed per year
          of enrollment:{" "}
          <code>gap = completer_debt × (1 − median_burden / burden) / 4</code>.
          Merit spend per first-year is{" "}
          <code>non_need_aid_share_first_year_ft × avg_non_need_grant_first_year_ft</code>.
          Each panel uses the median burden of the sample it plots: {meritMedianBurden} on
          the {ALIGNMENT_GAP_MERIT_META.schoolCount}-school merit join (Panel A),{" "}
          {endowmentMedianBurden} on the {ALIGNMENT_GAP_META.schoolCount}-school
          endowment join (Panel B). Hover any dot — not only the labeled ones — for
          the school name.
        </p>
        <p style={{ fontSize: 16, lineHeight: 1.65, color: "var(--ink-2)", margin: "14px 0 0" }}>
          Panel A is the join that makes the eyebrow true. The vertical axis is
          College Scorecard. The horizontal axis is CDS H2A. Color is IPEDS
          endowment per undergraduate. Panel B keeps the full corpus — including
          Bard, Grinnell, Bennington, Sarah Lawrence, Oberlin, and Earlham, which
          have no usable H2A — with IPEDS endowment on x and instruction ÷ net
          price in color. Panel B still requires a CDS SAT midpoint, which is why
          its n is larger than the merit sample rather than a superset of it.
        </p>
        <p style={{ fontSize: 16, lineHeight: 1.65, color: "var(--ink-2)", margin: "14px 0 0" }}>
          n = {ALIGNMENT_GAP_MERIT_META.schoolCount} on Panel A after data guards,
          from {ex.universe.toLocaleString("en-US")} rows in{" "}
          <code>school_merit_profile</code>. Dropped: quality limited ({ex.qualityLimited})
          or missing ({ex.qualityMissing}); missing H2A share or average grant ({ex.missingH2a});
          share outside 0–100% ({ex.rangeShare}, including Cal State Chico at 12,087%
          and Dickinson at 104.5%); average grant outside (0, $80,000] ({ex.rangeGrant});
          and rows without Scorecard earnings, debt, net price, and endowment ({ex.missingScorecard}).
          The quality flag said strong on every range violation. The guards are in
          the recipe query; they are not optional.
        </p>
        <p style={{ fontSize: 16, lineHeight: 1.65, color: "var(--ink-2)", margin: "14px 0 0" }}>
          CDS H2A excludes some mixed-need merit awards and can understate total
          merit availability. It also covers first-year full-time students only, so
          it describes the discount a school uses to recruit, not its whole aid
          budget.
        </p>
        <p style={{ fontSize: 16, lineHeight: 1.65, color: "var(--ink-2)", margin: "14px 0 0" }}>
          Median federal debt in the {ALIGNMENT_GAP_META.schoolCount}-school endowment
          join spans {formatUsd(ALIGNMENT_GAP_META.debtMin)} to {formatUsd(ALIGNMENT_GAP_META.debtMax)},
          and {formatUsd(ALIGNMENT_GAP_META.debtMode)} — the federal aggregate borrowing
          limit for dependent undergraduates — is the single most common value,
          shared by {ALIGNMENT_GAP_META.debtModeCount} schools. Debt cannot measure
          how expensive a school is. It measures burden. Net price is the price
          variable. Scorecard earnings cover federally aided students and describe
          a cohort that enrolled about a decade before the CDS row joined to it.
          The join is institutional, not longitudinal. Figures here are{" "}
          {ALIGNMENT_GAP_META.scorecardYears.join(", ")} College Scorecard against
          2024–26 CDS. Instructional expenditure per FTE and endowment are IPEDS
          figures surfaced through the Scorecard join.
        </p>
      </section>

      <section style={{ marginTop: 48 }}>
        <div className="meta" style={{ marginBottom: 10 }}>
          § Pull the join yourself
        </div>
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
{`# Panel A — CDS H2A merit × Scorecard
curl 'https://api.collegedata.fyi/rest/v1/school_merit_profile?select=school_id,school_name,canonical_year,merit_profile_quality,non_need_aid_share_first_year_ft,avg_non_need_grant_first_year_ft,avg_need_grant_first_year_ft,earnings_10yr_median,median_debt_completers,median_debt_monthly_payment,avg_net_price&limit=1000' \\
  -H 'apikey: <anon key>' \\
  -H 'Authorization: Bearer <anon key>'

# Panel B — Scorecard + IPEDS endowment
curl 'https://api.collegedata.fyi/rest/v1/scorecard_summary?select=ipeds_id,earnings_10yr_median,median_debt_monthly_payment,median_debt_completers,avg_net_price,endowment_end,instructional_expenditure_fte,enrollment&earnings_10yr_median=gt.0&median_debt_monthly_payment=gt.0&avg_net_price=gt.0&endowment_end=gt.0' \\
  -H 'apikey: <anon key>' \\
  -H 'Authorization: Bearer <anon key>'`}
        </pre>
        <p style={{ color: "var(--ink-2)", fontSize: 14, lineHeight: 1.55, margin: "16px 0 0" }}>
          Keep <code>non_need_aid_share_first_year_ft</code> in [0, 1] and{" "}
          <code>avg_non_need_grant_first_year_ft</code> in (0, 80000]; require{" "}
          <code>merit_profile_quality</code> in <code>strong</code> or{" "}
          <code>partial</code>. Join endowment from <code>scorecard_summary</code>{" "}
          and undergraduate enrollment from <code>school_browser_rows</code>. Then{" "}
          <code>burden = monthly × 12 / earnings</code>,{" "}
          <code>gap = completer_debt × (1 − median_burden / burden) / 4</code>, and{" "}
          <code>merit_per_fy = share × avg_non_need_grant</code>. The anon key is
          on the <Link href="/api">API page</Link>. Rebuild the checked-in dataset
          with <code>python3 tools/scorecard/build_alignment_gap_recipe.py</code>.
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
          <Link href="/recipes/acceptance-vs-yield">Acceptance rate vs. yield</Link>
        </div>
      </section>
    </div>
  );
}
