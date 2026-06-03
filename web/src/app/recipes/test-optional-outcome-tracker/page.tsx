import type { Metadata } from "next";
import type { ReactNode } from "react";
import Link from "next/link";
import { TrackedLink } from "@/components/TrackedLink";
import {
  fetchTestOptionalOutcomeTracker,
  type OutcomeValue,
  type TestingObservabilityRow,
  type UcOutcomeRow,
} from "@/lib/test-optional-outcome-tracker";

export const metadata: Metadata = {
  title: "Test-optional observability and outcome tracker",
  description:
    "A source-linked CollegeData.fyi check on what testing-policy changes made visible, and what coarse UC outcome data shows so far.",
  alternates: { canonical: "/recipes/test-optional-outcome-tracker" },
  openGraph: { url: "/recipes/test-optional-outcome-tracker" },
};

export const revalidate = 3600;

const API_PATH = "/api/recipes/test-optional-outcome-tracker";

function fmtCdsRate(value: number | null): string {
  if (value == null) return "n/a";
  return `${(value * 100).toFixed(value * 100 < 10 ? 1 : 0)}%`;
}

function fmtIpedsPercent(value: number | null): string {
  if (value == null) return "n/a";
  return `${value.toFixed(Number.isInteger(value) ? 0 : 1)}%`;
}

function fmtDelta(value: number | null): string {
  if (value == null) return "n/a";
  const sign = value > 0 ? "+" : "";
  return `${sign}${value.toFixed(Number.isInteger(value) ? 0 : 1)} pts`;
}

function fmtScore(value: number | null): string {
  return value == null ? "n/a" : value.toLocaleString("en-US");
}

function fmtDate(value: string | null | undefined): string {
  if (!value) return "n/a";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "n/a";
  return date.toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
  });
}

function statusLabel(status: TestingObservabilityRow["scoreBandStatus"]): string {
  switch (status) {
    case "reported":
      return "Bands reported";
    case "submit-rates-only":
      return "Submit rates only";
    case "no-cds-row":
      return "No CDS row";
    case "not-reported":
      return "Not reported";
  }
}

function statusChipClass(status: TestingObservabilityRow["scoreBandStatus"]): string {
  if (status === "reported") return "cd-chip cd-chip--forest";
  if (status === "submit-rates-only") return "cd-chip cd-chip--ochre";
  return "cd-chip";
}

function Cell({
  children,
  align = "left",
}: {
  children: ReactNode;
  align?: "left" | "right";
}) {
  return (
    <td
      style={{
        borderTop: "1px solid var(--rule)",
        color: "var(--ink-2)",
        padding: "10px 12px",
        textAlign: align,
        verticalAlign: "top",
      }}
    >
      {children}
    </td>
  );
}

function HeaderCell({
  children,
  align = "left",
}: {
  children: ReactNode;
  align?: "left" | "right";
}) {
  return (
    <th
      scope="col"
      style={{
        borderBottom: "1px solid var(--rule-strong)",
        color: "var(--ink)",
        fontFamily: "var(--mono)",
        fontSize: 10.5,
        fontWeight: 500,
        letterSpacing: "0.06em",
        padding: "10px 12px",
        textAlign: align,
        textTransform: "uppercase",
        whiteSpace: "nowrap",
      }}
    >
      {children}
    </th>
  );
}

function TableFrame({
  children,
  label,
  minWidth = 900,
}: {
  children: ReactNode;
  label: string;
  minWidth?: number;
}) {
  return (
    <div
      className="cd-card cd-reconstructed__table-wrap"
      aria-label={label}
      style={{ marginTop: 14, overflowX: "auto" }}
    >
      <table
        className="nums"
        style={{
          borderCollapse: "collapse",
          fontSize: 13,
          minWidth,
          width: "100%",
        }}
      >
        {children}
      </table>
    </div>
  );
}

function OutcomeCell({ value }: { value: OutcomeValue | undefined }) {
  const source =
    value?.sourceTable && value.sourceVariable
      ? `${value.sourceTable}.${value.sourceVariable}`
      : null;
  return (
    <span title={source ?? undefined}>
      {fmtIpedsPercent(value?.value ?? null)}
    </span>
  );
}

function TestingTable({ rows }: { rows: TestingObservabilityRow[] }) {
  return (
    <TableFrame label="Testing observability table" minWidth={1120}>
      <thead>
        <tr>
          <HeaderCell>School</HeaderCell>
          <HeaderCell>Panel</HeaderCell>
          <HeaderCell>CDS year</HeaderCell>
          <HeaderCell align="right">SAT submit</HeaderCell>
          <HeaderCell align="right">ACT submit</HeaderCell>
          <HeaderCell align="right">SAT 25/50/75</HeaderCell>
          <HeaderCell align="right">ACT 25/50/75</HeaderCell>
          <HeaderCell>Status</HeaderCell>
          <HeaderCell>Note</HeaderCell>
        </tr>
      </thead>
      <tbody>
        {rows.map((row) => (
          <tr key={row.schoolId}>
            <Cell>
              <Link href={`/schools/${row.schoolId}`} style={{ color: "var(--ink)" }}>
                {row.schoolName}
              </Link>
            </Cell>
            <Cell>{row.panel === "uc" ? "UC" : "News comparison"}</Cell>
            <Cell>
              {row.archiveUrl ? (
                <TrackedLink
                  external
                  href={row.archiveUrl}
                  analyticsEvent="recipe_source_opened"
                  analyticsProperties={{
                    recipe: "test-optional-outcome-tracker",
                    source: "cds_archive",
                    school_id: row.schoolId,
                  }}
                >
                  {row.latestCdsYear ?? "n/a"}
                </TrackedLink>
              ) : (
                row.latestCdsYear ?? "n/a"
              )}
            </Cell>
            <Cell align="right">{fmtCdsRate(row.satSubmitRate)}</Cell>
            <Cell align="right">{fmtCdsRate(row.actSubmitRate)}</Cell>
            <Cell align="right">
              {fmtScore(row.satCompositeP25)} / {fmtScore(row.satCompositeP50)} /{" "}
              {fmtScore(row.satCompositeP75)}
            </Cell>
            <Cell align="right">
              {fmtScore(row.actCompositeP25)} / {fmtScore(row.actCompositeP50)} /{" "}
              {fmtScore(row.actCompositeP75)}
            </Cell>
            <Cell>
              <span className={statusChipClass(row.scoreBandStatus)}>
                {statusLabel(row.scoreBandStatus)}
              </span>
            </Cell>
            <Cell>{row.note}</Cell>
          </tr>
        ))}
      </tbody>
    </TableFrame>
  );
}

function RetentionTable({
  rows,
  years,
}: {
  rows: UcOutcomeRow[];
  years: number[];
}) {
  return (
    <TableFrame label="UC first-year retention watchlist" minWidth={980}>
      <thead>
        <tr>
          <HeaderCell>UC campus</HeaderCell>
          {years.map((year) => (
            <HeaderCell key={year} align="right">
              {year}
            </HeaderCell>
          ))}
          <HeaderCell align="right">Delta</HeaderCell>
        </tr>
      </thead>
      <tbody>
        {rows.map((row) => (
          <tr key={row.schoolId}>
            <Cell>
              <Link href={`/schools/${row.schoolId}`} style={{ color: "var(--ink)" }}>
                {row.schoolName}
              </Link>
            </Cell>
            {years.map((year) => (
              <Cell key={year} align="right">
                <OutcomeCell value={row.retentionByYear[year]} />
              </Cell>
            ))}
            <Cell align="right">{fmtDelta(row.retentionDelta)}</Cell>
          </tr>
        ))}
      </tbody>
    </TableFrame>
  );
}

function CompletionTable({
  rows,
  latestYear,
}: {
  rows: UcOutcomeRow[];
  latestYear: number | null;
}) {
  return (
    <TableFrame label="UC completion and transfer-out baseline table" minWidth={900}>
      <thead>
        <tr>
          <HeaderCell>UC campus</HeaderCell>
          <HeaderCell align="right">{latestYear ?? "Latest"} retention</HeaderCell>
          <HeaderCell align="right">{latestYear ?? "Latest"} six-year grad</HeaderCell>
          <HeaderCell align="right">{latestYear ?? "Latest"} transfer-out</HeaderCell>
          <HeaderCell>Scorecard context</HeaderCell>
        </tr>
      </thead>
      <tbody>
        {rows.map((row) => (
          <tr key={row.schoolId}>
            <Cell>
              <Link href={`/schools/${row.schoolId}`} style={{ color: "var(--ink)" }}>
                {row.schoolName}
              </Link>
            </Cell>
            <Cell align="right">
              <OutcomeCell
                value={latestYear == null ? undefined : row.retentionByYear[latestYear]}
              />
            </Cell>
            <Cell align="right">
              <OutcomeCell
                value={latestYear == null ? undefined : row.graduationByYear[latestYear]}
              />
            </Cell>
            <Cell align="right">
              <OutcomeCell
                value={latestYear == null ? undefined : row.transferOutByYear[latestYear]}
              />
            </Cell>
            <Cell>
              {row.scorecard ? (
                <span>
                  Scorecard {row.scorecard.dataYear}: retention{" "}
                  {fmtCdsRate(row.scorecard.retentionRateFt)}, grad{" "}
                  {fmtCdsRate(row.scorecard.graduationRate6yr)}, transfer-out{" "}
                  {fmtCdsRate(row.scorecard.transferOutRate)}
                </span>
              ) : (
                "n/a"
              )}
            </Cell>
          </tr>
        ))}
      </tbody>
    </TableFrame>
  );
}

export default async function TestOptionalOutcomeTrackerPage() {
  const data = await fetchTestOptionalOutcomeTracker();
  const latestYear = data.methodology.latestIpedsDataYear;
  const latestRelease = data.methodology.latestIpedsRelease;

  return (
    <div className="mx-auto max-w-6xl px-4 sm:px-6 py-8">
      <header
        style={{
          display: "grid",
          gridTemplateColumns: "minmax(0, 1fr) auto",
          alignItems: "end",
          gap: 24,
          paddingTop: 16,
          paddingBottom: 8,
        }}
        className="test-optional-outcome-header"
      >
        <div>
          <div
            className="mono"
            style={{
              color: "var(--ink-3)",
              fontSize: 11,
              letterSpacing: "0.08em",
              textTransform: "uppercase",
            }}
          >
            <Link href="/recipes" style={{ color: "var(--ink-3)", textDecoration: "none" }}>
              RECIPES
            </Link>{" "}
            /{" "}
            <span style={{ color: "var(--ink)" }}>
              TEST-OPTIONAL OUTCOME TRACKER
            </span>
          </div>
          <h1
            className="serif"
            style={{
              fontSize: "clamp(34px, 5.4vw, 56px)",
              fontWeight: 400,
              letterSpacing: "-0.02em",
              lineHeight: 1,
              margin: "12px 0 0",
              maxWidth: 820,
            }}
          >
            What did test-optional policy make harder to see?
          </h1>
          <p
            style={{
              color: "var(--ink-2)",
              fontSize: 16,
              lineHeight: 1.6,
              marginTop: 14,
              maxWidth: 780,
            }}
          >
            WSJ is covering a real SAT policy debate. This tracker uses
            CollegeData.fyi source layers to separate what changed in public
            testing visibility from what coarse UC outcome measures show so far.
          </p>
        </div>
        <div
          style={{
            display: "flex",
            flexWrap: "wrap",
            gap: 8,
            justifyContent: "flex-end",
          }}
        >
          <span className="cd-chip">CDS C8/C9</span>
          <span className="cd-chip">IPEDS</span>
          <span className="cd-chip">Scorecard</span>
        </div>
      </header>

      <section
        className="rule-2 test-optional-outcome-stats"
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(4, minmax(0, 1fr))",
          gap: 14,
          marginTop: 28,
          paddingTop: 18,
        }}
      >
        <div className="cd-card" style={{ padding: 16 }}>
          <div className="meta">UC campuses</div>
          <div className="serif nums" style={{ fontSize: 34, lineHeight: 1, marginTop: 8 }}>
            {data.methodology.ucPanelSize}
          </div>
          <p style={{ color: "var(--ink-2)", fontSize: 13, lineHeight: 1.45, margin: "8px 0 0" }}>
            Undergraduate UC campuses in the outcome watchlist.
          </p>
        </div>
        <div className="cd-card" style={{ padding: 16 }}>
          <div className="meta">Latest IPEDS year</div>
          <div className="serif nums" style={{ fontSize: 34, lineHeight: 1, marginTop: 8 }}>
            {latestYear ?? "n/a"}
          </div>
          <p style={{ color: "var(--ink-2)", fontSize: 13, lineHeight: 1.45, margin: "8px 0 0" }}>
            Retention, completion, and transfer-out come from{" "}
            <code>ipeds_facts</code>.
          </p>
        </div>
        <div className="cd-card" style={{ padding: 16 }}>
          <div className="meta">Median latest retention</div>
          <div className="serif nums" style={{ fontSize: 34, lineHeight: 1, marginTop: 8 }}>
            {fmtIpedsPercent(data.summary.latestRetentionMedian)}
          </div>
          <p style={{ color: "var(--ink-2)", fontSize: 13, lineHeight: 1.45, margin: "8px 0 0" }}>
            High baseline retention leaves limited room for visible shock.
          </p>
        </div>
        <div className="cd-card" style={{ padding: 16 }}>
          <div className="meta">UC score bands hidden</div>
          <div className="serif nums" style={{ fontSize: 34, lineHeight: 1, marginTop: 8 }}>
            {data.summary.ucTestingRowsWithoutScoreBands}/{data.methodology.ucPanelSize}
          </div>
          <p style={{ color: "var(--ink-2)", fontSize: 13, lineHeight: 1.45, margin: "8px 0 0" }}>
            Current UC CDS serving rows with no reported SAT/ACT score bands.
          </p>
        </div>
      </section>

      <section
        className="cd-card cd-card--cut"
        style={{ marginTop: 28, padding: 20 }}
      >
        <div className="meta">Early read</div>
        <p style={{ color: "var(--ink-2)", fontSize: 16, lineHeight: 1.65, margin: "10px 0 0" }}>
          The primary signal is observability: when schools stop requiring or
          collecting scores, public score reporting gets thinner. UC first-year
          retention does not show an obvious institution-level collapse, but
          retention is coarse, ceiling-limited, and confounded by the pandemic
          era. Completion and transfer-out remain useful watchlist measures, but
          they are too lagged to fully evaluate post-2020 cohorts.
        </p>
      </section>

      <section style={{ marginTop: 44 }}>
        <div className="meta">§ Testing observability</div>
        <h2
          className="serif"
          style={{ fontSize: 30, lineHeight: 1.08, margin: "8px 0 0" }}
        >
          What is still visible in CDS testing rows?
        </h2>
        <p style={{ color: "var(--ink-2)", fontSize: 15, lineHeight: 1.6, marginTop: 10, maxWidth: 820 }}>
          This table uses current <code>school_browser_rows</code> values only.
          It does not infer formal policy from submit rates, and it treats UC
          missingness as an observability result rather than as a score result.
        </p>
        <TestingTable rows={data.testing} />
      </section>

      <section style={{ marginTop: 44 }}>
        <div className="meta">§ UC first-year retention watchlist</div>
        <h2
          className="serif"
          style={{ fontSize: 30, lineHeight: 1.08, margin: "8px 0 0" }}
        >
          Retention is basically flat, but it is a weak instrument.
        </h2>
        <p style={{ color: "var(--ink-2)", fontSize: 15, lineHeight: 1.6, marginTop: 10, maxWidth: 840 }}>
          First-year retention is the fastest public outcome check available in
          IPEDS. It is also institution-level, high-ceiling data. Flat retention
          is useful evidence against a broad retention shock, not proof that
          classroom preparedness concerns are false.
        </p>
        <RetentionTable rows={data.outcomes} years={data.years} />
      </section>

      <section style={{ marginTop: 44 }}>
        <div className="meta">§ Completion and transfer-out baseline</div>
        <h2
          className="serif"
          style={{ fontSize: 30, lineHeight: 1.08, margin: "8px 0 0" }}
        >
          Completion data is still mostly a baseline.
        </h2>
        <p style={{ color: "var(--ink-2)", fontSize: 15, lineHeight: 1.6, marginTop: 10, maxWidth: 840 }}>
          Six-year graduation and transfer-out are worth tracking, but in June
          2026 they are still too lagged to cleanly evaluate mature post-2020
          test-blind cohorts. Treat these as baseline context and refresh them
          when new IPEDS vintages land.
        </p>
        <CompletionTable rows={data.outcomes} latestYear={latestYear} />
      </section>

      <section
        className="rule-2 test-optional-outcome-methodology"
        style={{
          display: "grid",
          gridTemplateColumns: "minmax(0, 1fr) minmax(260px, 360px)",
          gap: 28,
          marginTop: 48,
          paddingTop: 22,
        }}
      >
        <div>
          <div className="meta">§ Methodology limits</div>
          <ul style={{ color: "var(--ink-2)", fontSize: 14, lineHeight: 1.65, margin: "10px 0 0", paddingLeft: 20 }}>
            <li>Formal test-policy labels require separately sourced URLs and verification dates.</li>
            <li>UC is a highly selected public system, not the national applicant pool.</li>
            <li>IPEDS retention is not course-level math readiness, DFW rates, GPA, or STEM persistence.</li>
            <li>COVID disruption and test-policy changes overlap, so this is descriptive, not causal.</li>
          </ul>
        </div>
        <div className="cd-card" style={{ padding: 18 }}>
          <div className="meta">Export</div>
          <p style={{ color: "var(--ink-2)", fontSize: 14, lineHeight: 1.55, margin: "8px 0 0" }}>
            The page and API use the same assembled dataset. Generated{" "}
            {fmtDate(data.generatedAt)} from public CollegeData.fyi tables.
          </p>
          <div style={{ display: "flex", flexWrap: "wrap", gap: 10, marginTop: 14 }}>
            <TrackedLink
              href={API_PATH}
              className="cd-btn cd-btn--ghost"
              analyticsEvent="recipe_api_opened"
              analyticsProperties={{ recipe: "test-optional-outcome-tracker", format: "json" }}
            >
              JSON
            </TrackedLink>
            <TrackedLink
              href={`${API_PATH}?format=csv`}
              className="cd-btn"
              analyticsEvent="download_clicked"
              analyticsProperties={{
                surface: "test_optional_outcome_tracker",
                file_type: "csv",
                item: "tracker_export",
              }}
            >
              Download CSV
            </TrackedLink>
          </div>
          <p className="mono" style={{ color: "var(--ink-3)", fontSize: 11, lineHeight: 1.45, marginTop: 12 }}>
            Latest IPEDS release: {latestRelease?.collection_year ?? "n/a"}{" "}
            {latestRelease?.release_type ?? ""} ({latestRelease?.release_date ?? "no date"}).
          </p>
        </div>
      </section>

      <style>{`
        @media (max-width: 900px) {
          .test-optional-outcome-header {
            grid-template-columns: 1fr !important;
          }
          .test-optional-outcome-header > div:last-child {
            justify-content: flex-start !important;
          }
        }
        @media (max-width: 820px) {
          .test-optional-outcome-stats {
            grid-template-columns: repeat(2, minmax(0, 1fr)) !important;
          }
          .test-optional-outcome-methodology {
            grid-template-columns: 1fr !important;
          }
        }
        @media (max-width: 560px) {
          .test-optional-outcome-stats {
            grid-template-columns: 1fr !important;
          }
        }
      `}</style>
    </div>
  );
}
