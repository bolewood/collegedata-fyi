import type { Metadata } from "next";
import Link from "next/link";
import { AlignmentGapChart } from "@/components/AlignmentGapChart";
import { TrackedLink } from "@/components/TrackedLink";
import { formatRecipeShare } from "@/lib/format";
import { formatEndowmentPerStudent } from "@/lib/alignment-gap-recipe-analysis";
import { ALIGNMENT_GAP_META } from "@/lib/alignment-gap-recipe-data";

export const metadata: Metadata = {
  title: "Alignment gap",
  description:
    "The net-price change that would put a school's graduates at the corpus median debt burden, plotted against endowment per undergraduate.",
  alternates: { canonical: "/recipes/alignment-gap" },
  openGraph: { url: "/recipes/alignment-gap" },
};

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
    body: "The same elevated burden, without the endowment to buy the price down. Bennington lives here — high burden on a modest per-student endowment, already spending most of net price on instruction.",
  },
  {
    num: "III",
    head: "Endowment absorbs it",
    count: ALIGNMENT_GAP_META.quadrants.absorbs,
    body: "Grinnell, Princeton, Stanford, Wellesley — low burden next to large per-student wealth. Instruction often exceeds net price because the endowment, not tuition, is paying for the classroom.",
  },
  {
    num: "IV",
    head: "Earnings do the work",
    count: ALIGNMENT_GAP_META.quadrants.earnings,
    body: "No unusual wealth, low burden anyway, because graduates earn enough to carry the debt. Bentley, Babson, and Santa Clara sit here.",
  },
];

export default function AlignmentGapPage() {
  const medianBurden = formatRecipeShare(ALIGNMENT_GAP_META.medianBurden, 2);
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
            federal loan payments each year. The alignment gap turns that into a
            price: how much net price would have to fall — or could rise — per
            year of college, to put that school&apos;s graduates at this
            corpus&apos;s median burden. The other axis is endowment per
            undergraduate: whether the school has the balance sheet to close it.
            The same gap means opposite things on either side of the vertical
            line.
          </p>
        </div>
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap", justifyContent: "flex-end" }}>
          <span className="cd-chip">CDS C9</span>
          <span className="cd-chip">Scorecard</span>
          <span className="cd-chip">IPEDS</span>
        </div>
      </header>

      <section
        className="endowment-recipe-ledger rule-2"
        style={{ marginTop: 28 }}
      >
        <div>
          <span className="meta">Schools joined</span>
          <strong>{ALIGNMENT_GAP_META.schoolCount.toLocaleString("en-US")}</strong>
          <small>SAT midpoint, Scorecard earnings and debt, net price, endowment</small>
        </div>
        <div>
          <span className="meta">Median debt burden</span>
          <strong>{medianBurden}</strong>
          <small>Annual debt service as a share of median 10-year earnings</small>
        </div>
        <div>
          <span className="meta">Above that burden</span>
          <strong>{ALIGNMENT_GAP_META.aboveMedianBurden.toLocaleString("en-US")}</strong>
          <small>Schools whose graduates carry more than the median</small>
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
        <div className="meta" style={{ marginBottom: 8 }}>
          § How the gap is computed
        </div>
        <h2 className="serif" style={{ fontSize: 28, margin: "0 0 12px", letterSpacing: "-0.015em" }}>
          Burden first, then a price movement.
        </h2>
        <p style={{ fontSize: 16, lineHeight: 1.65, color: "var(--ink-2)", margin: 0 }}>
          Burden is <code>median_debt_monthly_payment × 12 ÷ earnings_10yr_median</code>.
          The alignment gap is the completer debt a school would have to shed to
          reach the corpus median burden at its own earnings, divided across four
          years so it reads as dollars per year of net price. Hover any dot — not
          only the labeled ones — for the school, the gap, endowment per student,
          and instruction as a share of net price.
        </p>
        <p style={{ fontSize: 16, lineHeight: 1.65, color: "var(--ink-2)", margin: "14px 0 0" }}>
          Median federal debt in this join spans a narrow band and piles against
          the federal borrowing cap, so debt cannot measure how expensive a school
          is. It measures burden. Net price is the price variable. Scorecard
          earnings cover federally aided students and describe a cohort that
          enrolled about a decade before the CDS SAT row joined to it. The join is
          institutional, not longitudinal. Figures here are{" "}
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
{`curl 'https://api.collegedata.fyi/rest/v1/scorecard_summary?select=ipeds_id,earnings_10yr_median,median_debt_monthly_payment,median_debt_completers,avg_net_price,endowment_end,instructional_expenditure_fte,enrollment&earnings_10yr_median=gt.0&median_debt_monthly_payment=gt.0&avg_net_price=gt.0&endowment_end=gt.0' \\
  -H 'apikey: <anon key>' \\
  -H 'Authorization: Bearer <anon key>'`}
        </pre>
        <p style={{ color: "var(--ink-2)", fontSize: 14, lineHeight: 1.55, margin: "16px 0 0" }}>
          Join to <code>institution_directory</code> on <code>ipeds_id</code> for
          undergraduate enrollment, and to <code>school_browser_rows</code> for a
          2024-25 or 2025-26 SAT composite midpoint. Then{" "}
          <code>burden = monthly × 12 / earnings</code> and{" "}
          <code>gap = completer_debt × (1 − median_burden / burden) / 4</code>. The
          anon key is on the <Link href="/api">API page</Link>. Rebuild the checked-in
          dataset with{" "}
          <code>python3 tools/scorecard/build_alignment_gap_recipe.py</code>.
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
