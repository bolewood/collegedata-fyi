import type { Metadata } from "next";
import Link from "next/link";
import { EndowmentDrawRateExplorer } from "@/components/EndowmentDrawRateExplorer";
import { TrackedLink } from "@/components/TrackedLink";
import {
  ENDOWMENT_DRAW_RATE_META,
  ENDOWMENT_DRAW_RATE_YEAR_SUMMARIES,
} from "@/lib/endowment-draw-rate-recipe-data";

const latest = ENDOWMENT_DRAW_RATE_YEAR_SUMMARIES.at(-1)!;
const fiscalYearCount = ENDOWMENT_DRAW_RATE_META.maxYear - ENDOWMENT_DRAW_RATE_META.minYear + 1;
const fiscalYearRange = `FY${ENDOWMENT_DRAW_RATE_META.minYear}–FY${ENDOWMENT_DRAW_RATE_META.maxYear}`;

function titleCase(value: string): string {
  return value.charAt(0).toUpperCase() + value.slice(1);
}

export const metadata: Metadata = {
  title: "Endowment draw-rate tracker",
  description: `An independent estimate of private nonprofit college endowment draw rates from public IPEDS Finance data, fiscal years ${ENDOWMENT_DRAW_RATE_META.minYear} through ${ENDOWMENT_DRAW_RATE_META.maxYear}.`,
  alternates: { canonical: "/recipes/endowment-draw-rate" },
  openGraph: { url: "/recipes/endowment-draw-rate" },
};

function formatPct(value: number | null): string {
  return value == null ? "n/a" : `${(value * 100).toFixed(1)}%`;
}

export default function EndowmentDrawRatePage() {
  return (
    <div className="endowment-recipe-page">
      <header className="endowment-recipe-hero">
        <div className="endowment-recipe-breadcrumb mono">
          <Link href="/recipes">RECIPES</Link> / ENDOWMENT DRAW-RATE TRACKER
        </div>
        <div className="endowment-recipe-hero-grid">
          <div>
            <h1>
              How much of the endowment is being <span>spent?</span>
            </h1>
            <p>
              {fiscalYearCount} years of federal finance filings, turned into an estimated
              endowment spending rate for private nonprofit colleges. This is an estimate
              from federal filings. A high draw rate is a reason to look closer, not proof a
              school is in trouble.
            </p>
          </div>
          <div className="endowment-recipe-chips">
            <span className="cd-chip">IPEDS Finance F2</span>
            <span className="cd-chip">Part H</span>
            <span className="cd-chip cd-chip--forest">{fiscalYearRange}</span>
          </div>
        </div>
      </header>

      <section className="endowment-recipe-ledger rule-2">
        <div>
          <span className="meta">Latest median</span>
          <strong>{formatPct(latest.median)}</strong>
          <small>FY{latest.year}, {latest.releaseType}</small>
        </div>
        <div>
          <span className="meta">Above 7%</span>
          <strong>{formatPct(latest.above7Share)}</strong>
          <small>{latest.above7Count.toLocaleString()} of {latest.eligible.toLocaleString()} eligible schools</small>
        </div>
        <div>
          <span className="meta">Rows</span>
          <strong>{ENDOWMENT_DRAW_RATE_META.rowCount.toLocaleString()}</strong>
          <small>
            {ENDOWMENT_DRAW_RATE_META.schoolCount.toLocaleString()} schools,{" "}
            {fiscalYearRange}
          </small>
        </div>
        <div>
          <span className="meta">Latest status</span>
          <strong className="endowment-release-word">{titleCase(latest.releaseType)}</strong>
          <small>
            FY{latest.year}{latest.releaseType === "provisional"
              ? " will be updated when the final release is published"
              : " is the latest final release"}
          </small>
        </div>
      </section>

      <EndowmentDrawRateExplorer />

      <section className="endowment-method-section rule-2">
        <div className="endowment-method-grid">
          <div>
            <div className="meta">§ What the threshold means</div>
            <h2>How to read the 7% line</h2>
            <p>
              Typical endowment payout policies often target roughly 4–5%. Some states&apos;
              versions of UPMIFA include a presumption above 7%. That test uses a multi-year
              average value and applies only in a minority of states. This recipe divides one
              year&apos;s reported spending distribution by that year&apos;s beginning value. Crossing
              7% here does not establish a UPMIFA violation.
            </p>
          </div>
          <div className="cd-card cd-card--cut">
            <div className="meta">Coverage note</div>
            <p>
              {ENDOWMENT_DRAW_RATE_META.schoolsWithoutCurrentPage.toLocaleString()}{" "}
              schools in this dataset have no current public school page. This can include
              colleges that later closed or left the current directory. Their histories still
              appear here.
            </p>
          </div>
        </div>
      </section>

      <section className="endowment-query-section">
        <div className="meta">§ Pull the fields yourself</div>
        <pre tabIndex={0}>
{`curl 'https://api.collegedata.fyi/rest/v1/ipeds_facts?ipeds_id=eq.152080&field_key=in.(endowment_value_begin,endowment_value_end,endowment_new_gifts,endowment_investment_return,endowment_spending_distribution,endowment_other_change)&data_year=gte.${ENDOWMENT_DRAW_RATE_META.minYear}&data_year=lte.${ENDOWMENT_DRAW_RATE_META.maxYear}&select=ipeds_id,data_year,field_key,value_numeric,quality_flag,source_table,source_variable,release_type&order=data_year.asc,field_key.asc' \\
  -H 'apikey: <anon key>' \\
  -H 'Authorization: Bearer <anon key>'`}
        </pre>
        <p>
          Then compute <code>abs(endowment_spending_distribution) / endowment_value_begin</code>
          after retaining reported rows with a positive beginning value and verifying the Part H
          component identity.
        </p>
        <div className="endowment-recipe-links">
          <TrackedLink
            external
            href="https://github.com/bolewood/collegedata-fyi/blob/main/docs/recipes/endowment-draw-rate.md"
            target="_blank"
            rel="noopener noreferrer"
            analyticsEvent="recipe_writeup_opened"
            analyticsProperties={{
              surface: "recipe_detail",
              recipe: "endowment-draw-rate",
            }}
          >
            Read the methodology →
          </TrackedLink>
          <Link href="/api">Explore the API →</Link>
        </div>
      </section>
    </div>
  );
}
