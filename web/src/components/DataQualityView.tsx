"use client";

// PRD 040 M1: the body of /data-quality. Everything below the lede is driven by
// one URL parameter (?year=2024-25), read on every render so back and forward
// restore the selected year. The numbers come from the committed snapshot the
// server component passes in; nothing here queries anything.

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import type { ReactNode } from "react";
import {
  MIN_REPORTS_FOR_RATE,
  SECTION_NAMES,
  TABLE_TITLES,
  fallOf,
  aidCantCheckNote,
  federalDiffersNote,
  hasDifferenceSplit,
  hasFederalChecks,
  ipedsTuitionTable,
  hasSections,
  isDataQualityLaunched,
  isProjectedYear,
  liveCount,
  percent,
  qualityCsvPath,
  resolveYear,
  rowPercent,
  sectionUsableShare,
  yearGlance,
  yearsNewestFirst,
  type CheckName,
  type QualityRow,
  type QualitySnapshot,
  type QualityTableId,
  type QualityYear,
  type SumOutcomes,
} from "@/lib/data-quality";
import { DATA_LICENSE_NAME, DATA_LICENSE_URL } from "@/lib/data-license";
import { HAS_CDS_HREF } from "@/lib/coverage-model";
import { formatLabel } from "@/lib/format-labels";
import { Count, DrillPanel, DrillProvider } from "./DataQualityDrill";
import { cohortChanges, lineRuns, pointLabel, renewalRow, seriesStarts, trendRows, type TrendPoint, type TrendRow } from "@/lib/data-quality-trend";
import type { CellTable } from "@/lib/data-quality-reports";

const DASH = "–";

const n = (v: number) => v.toLocaleString("en-US");
const pc = (v: number | null) => (v === null ? DASH : `${v}%`);

export function DataQualityView({ snapshot, reportsUrl = null, trend }: { snapshot: QualitySnapshot; reportsUrl?: string | null; trend: TrendPoint[] }) {
  const searchParams = useSearchParams();
  const year = resolveYear(snapshot, searchParams.get("year"));
  return <DataQualityBody snapshot={snapshot} year={year} reportsUrl={reportsUrl} trend={trend} />;
}

/** Split out so tests can render a chosen year without a router. */
export function DataQualityBody({ snapshot, year, reportsUrl = null, trend }: { snapshot: QualitySnapshot; year: QualityYear; reportsUrl?: string | null; trend: TrendPoint[] }) {
  assertTrendMatches(trend, snapshot);
  const years = yearsNewestFirst(snapshot);
  return (
    <DrillProvider reportsUrl={reportsUrl} year={year.cds_year}>
      <GlanceTable years={years} />

      <section aria-labelledby="dq-year-heading" style={sectionStyle}>
        <h2 id="dq-year-heading" className="meta" style={{ margin: "0 0 10px" }}>
          § Year
        </h2>
        <YearPicker years={years} selected={year.cds_year} />
      </section>

      <Notices year={year} />
      <TrendSection points={trend} year={year.cds_year} />
      <ReportsTable year={year} snapshot={snapshot} />
      <SectionsTable year={year} />
      <FederalTable year={year} snapshot={snapshot} />
      <FederalChecks year={year} />
      <TotalsTable year={year} snapshot={snapshot} />
      <HowToRead />
    </DrillProvider>
  );
}

// ── Shared pieces ────────────────────────────────────────────────

const sectionStyle: React.CSSProperties = { marginTop: 48 };

function SectionHead({ id, label, title, sentence }: { id: string; label: string; title: string; sentence: ReactNode }) {
  return (
    <header style={{ marginBottom: 14 }}>
      <div className="meta" style={{ marginBottom: 8 }}>{label}</div>
      <h2 id={id} className="serif" style={{ fontSize: 26, lineHeight: 1.15, margin: 0, fontWeight: 400 }}>
        {title}
      </h2>
      <p style={{ margin: "8px 0 0", maxWidth: 720, fontSize: 15, lineHeight: 1.6, color: "var(--ink-2)" }}>
        {sentence}
      </p>
    </header>
  );
}

/**
 * Horizontal scroller for a wide table: a labelled, focusable region. The table's minimum widths, the column
 * sizes that put the scroll cut on a column edge, and the hint's breakpoints are all in data-quality.css, so
 * nothing here needs a script or a measurement. `hint` is false for a table with nothing to read (all dashes).
 */
function Scroll({ children, label, wide = false, hint = true }: { children: ReactNode; label: string; wide?: boolean; hint?: boolean }) {
  return (
    <div className={wide ? "dq-scroll dq-scroll--wide" : "dq-scroll"}>
      {hint && (
        <p className="dq-scroll-hint acc-table-hint" aria-hidden="true">
          Scroll sideways to see every column.
        </p>
      )}
      <div style={{ overflowX: "auto", WebkitOverflowScrolling: "touch" }} role="region" aria-label={label} tabIndex={0}>
        {children}
      </div>
    </div>
  );
}

/** One sized column per table column (data-quality.css sizes them by position on a phone). */
function Cols({ n: count }: { n: number }) {
  return (
    <colgroup>
      {Array.from({ length: count }, (_, i) => (
        <col key={i} />
      ))}
    </colgroup>
  );
}

const tableStyle: React.CSSProperties = {
  borderCollapse: "collapse",
  fontSize: 14,
};
const thStyle: React.CSSProperties = {
  textAlign: "right",
  padding: "10px 12px 10px 0",
  fontFamily: "var(--mono)",
  fontSize: 11,
  letterSpacing: "0.06em",
  textTransform: "uppercase",
  fontWeight: 400,
  color: "var(--ink-3)",
  borderTop: "1px solid var(--rule-strong)",
  borderBottom: "1px solid var(--rule-strong)",
  verticalAlign: "bottom",
};
const thLeft: React.CSSProperties = { ...thStyle, textAlign: "left" };
const tdStyle: React.CSSProperties = {
  textAlign: "right",
  padding: "10px 12px 10px 0",
  borderBottom: "1px solid var(--rule)",
  fontFamily: "var(--mono)",
  verticalAlign: "top",
};
const tdLeft: React.CSSProperties = { ...tdStyle, textAlign: "left", fontFamily: "var(--sans)", whiteSpace: "nowrap" };
/** Sentences under a download or at the top of the page: small, normal case. `.meta` is for labels. */
const smallPrint: React.CSSProperties = { margin: "8px 0 0", maxWidth: 720, fontSize: 13, lineHeight: 1.5, color: "var(--ink-3)" };
const totalRow: React.CSSProperties = { fontWeight: 600, background: "var(--paper-2)" };

function Note({ children, id }: { children: ReactNode; id?: string }) {
  return (
    <p id={id} style={{ margin: "12px 0 0", maxWidth: 720, fontSize: 13.5, lineHeight: 1.6, color: "var(--ink-2)" }}>
      {children}
    </p>
  );
}

// ── All years at a glance ────────────────────────────────────────

function GlanceTable({ years }: { years: QualityYear[] }) {
  return (
    <section aria-labelledby="dq-glance-heading" style={{ marginTop: 40 }}>
      <SectionHead
        id="dq-glance-heading"
        label="§ All years at a glance"
        title="All years at a glance"
        sentence="One row per year, newest first. Rates are shares of that year’s published reports, except the admissions match rate, which is a share of values compared."
      />
      <Scroll label="All years at a glance">
        <table className="dq-table dq-table--glance" style={tableStyle} id="dq-glance">
          <Cols n={9} />
          <thead>
            <tr>
              <th scope="col" style={thLeft}>Year</th>
              <th scope="col" style={thStyle}>Published</th>
              <th scope="col" style={thStyle}>Set aside</th>
              <th scope="col" style={thStyle}>Couldn’t read</th>
              <th scope="col" style={thStyle}>Not read yet</th>
              <th scope="col" style={thStyle}>Admissions match rate</th>
              <th scope="col" style={thStyle}>Enrollment adds up</th>
              <th scope="col" style={thStyle}>Admissions adds up</th>
              <th scope="col" style={thStyle}>Financial aid adds up</th>
            </tr>
          </thead>
          <tbody>
            {years.map((y) => {
              const g = yearGlance(y);
              return (
                <tr key={y.cds_year}>
                  <th scope="row" style={{ ...tdLeft, fontWeight: 500 }}>{y.cds_year}</th>
                  <td style={tdStyle}>{n(g.status.published)}</td>
                  <td style={tdStyle}>{n(g.status.set_aside)}</td>
                  <td style={tdStyle}>{n(g.status.couldnt_read)}</td>
                  <td style={tdStyle}>{n(g.status.not_read_yet)}</td>
                  <td style={tdStyle}>{pc(g.matchRate)}</td>
                  <td style={tdStyle}>{pc(g.b1)}</td>
                  <td style={tdStyle}>{pc(g.c1)}</td>
                  <td style={tdStyle}>{pc(g.h1)}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </Scroll>
      <Note>
        Fields stored is left out here because 2023-24 is counted differently; see Table A.
      </Note>
    </section>
  );
}

// ── Over time ────────────────────────────────────────────────────

/** The trend is oldest first and ends at the snapshot the tables show; anything else is a bug in the caller, so fail loudly. */
export function assertTrendMatches(trend: TrendPoint[], snapshot: QualitySnapshot): void {
  if (trend.length === 0) return;
  for (let i = 1; i < trend.length; i++) {
    if (Date.parse(trend[i].snapshot_of) <= Date.parse(trend[i - 1].snapshot_of)) {
      throw new Error(`The trend is not oldest first: ${trend[i - 1].snapshot_of} is followed by ${trend[i].snapshot_of}`);
    }
  }
  if (trend[trend.length - 1].snapshot_of !== snapshot.snapshot_of) {
    throw new Error(`The trend ends at ${trend[trend.length - 1].snapshot_of}, not at the snapshot shown, ${snapshot.snapshot_of}`);
  }
}

/**
 * The page's main numbers by snapshot. With one snapshot there is nothing to compare, so the page shows that snapshot's numbers
 * and says a trend appears with the second; no line or axis is drawn for a single point. From two on, each row gets a small
 * line, spaced by snapshot date, beside its table values, which are the accessible form of every point (the lines are hidden
 * from assistive technology). A line breaks at a missing value and starts again where the school years that renewal compares
 * change. Renewal is archive-wide, not per CDS year, so it has its own small table.
 */
function TrendSection({ points, year }: { points: TrendPoint[]; year: string }) {
  if (points.length === 0) return null;
  const rows = trendRows(points, year);
  const renewal = renewalRow(points);
  const many = points.length > 1;
  const first = pointLabel(points[0]);
  const starts = seriesStarts(rows);
  const changes = cohortChanges(renewal);
  return (
    <section aria-labelledby="dq-trend-heading" style={sectionStyle}>
      <SectionHead
        id="dq-trend-heading"
        label="§ Over time"
        title="Over time"
        sentence={
          many
            ? `The numbers for ${year} in each of ${points.length} snapshots, from ${first} to ${pointLabel(points[points.length - 1])}.`
            : `The numbers for ${year} in the first snapshot, ${first}. A trend appears here once there are two snapshots.`
        }
      />
      <TrendTable id="dq-trend" caption={many ? `${year} by snapshot, oldest first` : `${year}, first snapshot`} rows={rows} points={points} />
      {starts.length > 0 && (
        <Note id="dq-trend-starts">
          {starts
            .map((g) => `${g.labels.join(", ")} ${g.labels.length === 1 ? "starts" : "start"} at the ${pointLabel(points[g.index])} snapshot; earlier snapshots don’t have ${g.labels.length === 1 ? "it" : "them"}.`)
            .join(" ")}
        </Note>
      )}
      <Note id="dq-trend-note">
        {many
          ? "A change between snapshots can come from reports added to the archive, from fixes to how we read them, or both. Each value is that snapshot’s own number, and each line is spaced by snapshot date."
          : `Each value is the first snapshot’s own number. These six rows come from the ${year} row of “All years at a glance”, above.`}
      </Note>
      <h3 className="serif" id="dq-renewal-heading" style={{ fontSize: 20, margin: "28px 0 10px", fontWeight: 400 }}>
        Current-year renewal
      </h3>
      <TrendTable id="dq-trend-renewal" caption={many ? "All schools, by snapshot, oldest first" : "All schools, first snapshot"} rows={[renewal]} points={points} cohortLabel />
      {changes.length > 0 && (
        <Note id="dq-renewal-cohorts">
          {changes
            .map((c) => `At the ${pointLabel(points[c.index])} snapshot the comparison moved from ${c.from} to ${c.to}, so a new series starts there.`)
            .join(" ")}
        </Note>
      )}
      <Note id="dq-renewal-note">
        Renewal is for the whole archive, not one year: of the schools with a report for the year before the current one, the share that also has one for the current year. It is the headline figure on the Coverage page.
      </Note>
    </section>
  );
}

/** One trend table: a row per measure, a column per snapshot (dated, with its run), and from two snapshots a line column. */
function TrendTable({ id, caption, rows, points, cohortLabel = false }: { id: string; caption: string; rows: TrendRow[]; points: TrendPoint[]; cohortLabel?: boolean }) {
  const many = points.length > 1;
  return (
    <Scroll label={caption} hint={many}>
      <table className="dq-table dq-table--trend" style={{ ...tableStyle, ["--dq-snapshots" as string]: points.length, ["--dq-line" as string]: many ? 1 : 0 }} id={id}>
        <Cols n={points.length + 1 + (many ? 1 : 0)} />
        <caption className="meta" style={{ textAlign: "left", paddingBottom: 8 }}>{caption}</caption>
        <thead>
          <tr>
            <th scope="col" style={thLeft}>Measure</th>
            {points.map((p) => (
              <th key={p.snapshot_of} scope="col" style={thStyle}>
                {many ? "" : "First snapshot, "}
                {pointLabel(p)}
                <br />
                <span className="dq-trend-run" style={{ textTransform: "none", letterSpacing: 0, fontWeight: 400 }}>{p.run}</span>
              </th>
            ))}
            {/* The lines repeat what the table says, so the column is hidden from assistive technology, header included. */}
            {many && <th scope="col" aria-hidden="true" style={thLeft}>Shape</th>}
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.key}>
              {/* Row labels wrap (tdLeft is nowrap, which ran a long label over its own value on a phone). */}
              <th scope="row" style={{ ...tdLeft, whiteSpace: "normal" }}>{r.label}</th>
              {r.values.map((v, i) => (
                <td key={points[i].snapshot_of} style={tdStyle}>
                  {v === null ? DASH : r.unit === "percent" ? `${v}%` : n(v)}
                  {cohortLabel && r.cohorts?.[i] && (
                    <>
                      <br />
                      <span style={{ fontFamily: "var(--sans)", fontSize: 12, color: "var(--ink-3)" }}>{r.cohorts[i]}</span>
                    </>
                  )}
                </td>
              ))}
              {many && (
                <td aria-hidden="true" style={{ ...tdStyle, textAlign: "left" }}>
                  <TrendLine row={r} points={points} />
                </td>
              )}
            </tr>
          ))}
        </tbody>
      </table>
    </Scroll>
  );
}

/** The line for a row (see `lineRuns` for how it breaks and is scaled); a dash when no run has two points. */
function TrendLine({ row, points }: { row: TrendRow; points: TrendPoint[] }) {
  const w = 72;
  const h = 22;
  const runs = lineRuns(row, points, w, h);
  if (!runs.some((run) => run.length >= 2)) return <>{DASH}</>;
  return (
    <svg width={w} height={h} viewBox={`0 0 ${w} ${h}`} aria-hidden="true" style={{ verticalAlign: "middle" }}>
      {runs.map((run) =>
        run.length >= 2 ? (
          <path
            key={run[0].index}
            d={run.map((p, k) => `${k === 0 ? "M" : "L"}${p.x.toFixed(1)},${p.y.toFixed(1)}`).join(" ")}
            stroke="var(--chart-ink, var(--ink))"
            strokeWidth="1.25"
            fill="none"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        ) : null,
      )}
      {runs.flat().map((p) => (
        <circle key={p.index} cx={p.x} cy={p.y} r="1.8" fill="var(--forest)" />
      ))}
    </svg>
  );
}

// ── Year picker ──────────────────────────────────────────────────

export function YearPicker({ years, selected }: { years: QualityYear[]; selected: string }) {
  return (
    <div role="group" aria-label="Choose a year" style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
      {years.map((y) => {
        const on = y.cds_year === selected;
        return (
          <Link
            key={y.cds_year}
            href={`/data-quality?year=${y.cds_year}`}
            scroll={false}
            aria-current={on ? "true" : undefined}
            className="cd-chip"
            style={{
              textDecoration: "none",
              background: on ? "var(--ink)" : "transparent",
              color: on ? "var(--paper)" : "var(--ink-2)",
              borderColor: on ? "var(--ink)" : "var(--rule-strong)",
            }}
          >
            {y.cds_year}
          </Link>
        );
      })}
    </div>
  );
}

// ── Notices ──────────────────────────────────────────────────────

export function yearNotices(year: QualityYear): string[] {
  const out: string[] = [];
  if (year.other_form_numbering > 0) {
    out.push(
      `${n(year.other_form_numbering)} of the ${n(year.total.status.published)} published ${year.cds_year} reports are numbered by a different year’s form. Some question numbers in them point at a different question than the ${year.form.form_year} form’s.`,
    );
  }
  if (!year.federal_fall_loaded) {
    out.push(`No federal admissions figures for fall ${fallOf(year.cds_year)} yet.`);
  }
  if (!year.form.full_field_schema) {
    out.push("Older form: tables mapped, not every question.");
  }
  return out;
}

function Notices({ year }: { year: QualityYear }) {
  const notices = yearNotices(year);
  if (notices.length === 0) return null;
  return (
    <aside aria-label={`Notices for ${year.cds_year}`} style={{ marginTop: 24 }}>
      {notices.map((text) => (
        <p
          key={text}
          className="cd-card"
          style={{ margin: "0 0 10px", padding: "12px 16px", maxWidth: 720, fontSize: 14, lineHeight: 1.55 }}
        >
          {text}
        </p>
      ))}
    </aside>
  );
}

// ── CSV ──────────────────────────────────────────────────────────

function CsvButton({ table, year }: { table: QualityTableId; year: QualityYear }) {
  // Gated with the page.
  if (!isDataQualityLaunched()) return null;
  return (
    <div style={{ marginTop: 14 }}>
      <a href={qualityCsvPath(table, year.cds_year)} download className="cd-btn cd-btn--ghost" style={{ display: "inline-block" }}>
        Download {year.cds_year} table as CSV
      </a>
      <p style={smallPrint}>
        This table is licensed{" "}
        <a href={DATA_LICENSE_URL} style={{ textDecoration: "underline" }}>
          {DATA_LICENSE_NAME}
        </a>
        . Credit collegedata.fyi.
      </p>
    </div>
  );
}

// ── Table A ──────────────────────────────────────────────────────

function allRows(year: QualityYear): { key: string; name: string; row: QualityRow; total: boolean }[] {
  return [
    ...year.rows.map((r) => ({ key: r.format, name: formatLabel(r.format), row: r as QualityRow, total: false })),
    { key: "__total", name: "All formats", row: year.total, total: true },
  ];
}

/** A count that lists its reports when clicked. `rowKey` is a format key or "__total" (the All formats row). */
function K({ year, table, rowKey, column, value }: { year: QualityYear; table: CellTable; rowKey: string; column: string; value: number }) {
  return <Count cell={{ table, row: rowKey === "__total" ? "total" : rowKey, column }} year={year.cds_year} value={value} text={n(value)} />;
}

function ReportsTable({ year, snapshot }: { year: QualityYear; snapshot: QualitySnapshot }) {
  const reasons = year.set_aside_reasons;
  return (
    <section aria-labelledby="dq-a-heading" style={sectionStyle}>
      <SectionHead
        id="dq-a-heading"
        label="§ Table A"
        title="Reports and fields stored"
        sentence={`How many ${year.cds_year} reports are published with numbers, set aside, couldn’t be read or not read yet, and how much of each form we stored.`}
      />
      <Scroll label={`Table A, ${year.cds_year}`}>
        <table className="dq-table dq-table--a" style={tableStyle} id="dq-table-a">
          <Cols n={7} />
          <thead>
            <tr>
              <th scope="col" style={thLeft}>Format</th>
              <th scope="col" style={thStyle}>Published</th>
              <th scope="col" style={thStyle}>Set aside</th>
              <th scope="col" style={thStyle}>Couldn’t read</th>
              <th scope="col" style={thStyle}>Not read yet</th>
              <th scope="col" style={thStyle}>Fields stored: median</th>
              <th scope="col" style={thStyle}>Lowest 10%</th>
            </tr>
          </thead>
          <tbody>
            {allRows(year).map(({ key, name, row, total }) => (
              <tr key={key} style={total ? totalRow : undefined}>
                <th scope="row" style={{ ...tdLeft, fontWeight: total ? 600 : 400 }}>{name}</th>
                <td style={tdStyle}><K year={year} table="status" rowKey={key} column="published" value={row.status.published} /></td>
                <td style={tdStyle}><K year={year} table="status" rowKey={key} column="set_aside" value={row.status.set_aside} /></td>
                <td style={tdStyle}><K year={year} table="status" rowKey={key} column="couldnt_read" value={row.status.couldnt_read} /></td>
                <td style={tdStyle}><K year={year} table="status" rowKey={key} column="not_read_yet" value={row.status.not_read_yet} /></td>
                <td style={tdStyle}>{row.status.published > 0 ? n(row.fields_stored.median) : DASH}</td>
                <td style={tdStyle}>{row.status.published > 0 ? n(row.fields_stored.p10) : DASH}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </Scroll>
      <DrillPanel table="status" year={year.cds_year} />
      <Note>
        {n(liveCount(year.total.status))} reports counted. Set aside:{" "}
        {n(reasons.blank_form)} blank form, {n(reasons.too_little_read)} too little read, {n(reasons.wrong_file)} wrong
        file. Not counted: {n(year.removed)} removed
        {year.no_file > 0 ? `, ${n(year.no_file)} with no file` : ""}.
      </Note>
      <Note>
        Fields stored counts the fields stored for the report as we publish it, including fields recorded as
        unreadable or “not applicable”. It measures how much of the form we reached, not how many usable answers we have.
        The {year.form.form_year} form has {n(year.form.questions)} questions.{" "}
        {year.other_form_numbering > 0
          ? ` The ${n(year.other_form_numbering)} reports numbered by a different year’s form have field numbers from that form, whose size differs.`
          : ""}
      </Note>
      {!isProjectedYear(year.cds_year) && <CountingNote id="dq-note-counting" year={year} />}
      <CsvButton table="reports" year={year} />
    </section>
  );
}

function CountingNote({ id, year }: { id: string; year: QualityYear }) {
  return (
    <Note id={id}>
      {year.cds_year} is counted differently. From 2024-25 on, fields stored also includes values from a second
      reading of the same file. This year counts one reading, so it reads lower partly for that reason.
    </Note>
  );
}

// ── Table A, by section ──────────────────────────────────────────

/** Table A's second half: one row per CDS section. Absent for a snapshot without `sections` (public_format 1 and 2). */
function SectionsTable({ year }: { year: QualityYear }) {
  if (!hasSections(year)) return null;
  const block = year.sections!;
  const none = block.reports === 0;
  return (
    <section aria-labelledby="dq-sections-heading" style={sectionStyle}>
      <SectionHead
        id="dq-sections-heading"
        label="§ Table A, by section"
        title="Fields stored and usable answers by section"
        sentence={`For each part of the ${year.form.form_year} form, how many questions it has and how many fields and usable answers a typical report has, counting the ${n(block.reports)} published ${year.cds_year} ${block.reports === 1 ? "report" : "reports"} numbered by that form.`}
      />
      <Scroll label={`Table A by section, ${year.cds_year}`} hint={!none}>
        <table className="dq-table dq-table--s" style={tableStyle} id="dq-table-sections">
          <Cols n={5} />
          <thead>
            <tr>
              <th scope="col" style={thLeft}>Section</th>
              <th scope="col" style={thStyle}>Questions on the form</th>
              <th scope="col" style={thStyle}>Fields stored: median</th>
              <th scope="col" style={thStyle}>Usable answers: median</th>
              <th scope="col" style={thStyle}>Usable, as a share of questions</th>
            </tr>
          </thead>
          <tbody>
            {block.rows.map((r) => {
              const share = sectionUsableShare(r, block.reports);
              return (
                <tr key={r.section}>
                  <th scope="row" style={tdLeft}>{r.section} {SECTION_NAMES[r.section]}</th>
                  <td style={tdStyle}>{n(r.questions)}</td>
                  <td style={tdStyle}>{none ? DASH : n(r.stored_median)}</td>
                  <td style={tdStyle}>{none ? DASH : n(r.usable_median)}</td>
                  <td style={tdStyle} title={!none && share === null ? `Under ${MIN_REPORTS_FOR_RATE} reports: no share` : undefined}>
                    {none ? DASH : pc(share)}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </Scroll>
      <Note id="dq-note-usable">
        A usable answer is a value a reader can use. Fields recorded as unreadable or as “not applicable” are stored
        but not counted as usable; counting “not applicable” would raise some sections, transfer admission especially. The medians are per report and per section, so they don’t add up to a
        report’s total, and not every question applies to every school, so a share of 100% isn’t the goal. A low
        number can mean the school left a section blank, that we didn’t reach it, or both; this table can’t say
        which.
      </Note>
      {block.reports > 0 && block.reports < MIN_REPORTS_FOR_RATE && (
        <Note id="dq-note-sections-small">
          Fewer than {MIN_REPORTS_FOR_RATE} reports, so no share is shown.
        </Note>
      )}
      {year.other_form_numbering > 0 && (
        <Note id="dq-note-sections-left-out">
          Left out: {n(year.other_form_numbering)} {year.other_form_numbering === 1 ? "report" : "reports"} numbered by
          a different year’s form, whose field numbers belong to that form.
        </Note>
      )}
      {!isProjectedYear(year.cds_year) && <CountingNote id="dq-note-counting-sections" year={year} />}
      <CsvButton table="sections" year={year} />
    </section>
  );
}

// ── Table B ──────────────────────────────────────────────────────

function FederalTable({ year, snapshot }: { year: QualityYear; snapshot: QualitySnapshot }) {
  const loaded = year.federal_fall_loaded;
  const left = year.federal_left_out;
  // public_format 2 snapshots split "Differs" by size; format 1 snapshots have no split to show.
  const split = hasDifferenceSplit(year);
  return (
    <section aria-labelledby="dq-b-heading" style={sectionStyle}>
      <SectionHead
        id="dq-b-heading"
        label="§ Table B"
        title="Admissions against federal figures"
        sentence="Applicants, admits and enrolled first-year students in each published report (CDS C1), compared with the federal figures for the same fall."
      />
      {!loaded && (
        <p id="dq-no-federal" style={{ margin: "0 0 14px", maxWidth: 720, fontSize: 15, lineHeight: 1.6, color: "var(--ink-2)" }}>
          No federal admissions figures for fall {fallOf(year.cds_year)} yet.
        </p>
      )}
      <Scroll label={`Table B, ${year.cds_year}`} hint={loaded}>
        <table className={`dq-table dq-table--b${split ? " dq-table--b-split" : ""}`} style={tableStyle} id="dq-table-b">
          <Cols n={split ? 9 : 7} />
          <thead>
            <tr>
              <th scope="col" style={thLeft}>Format</th>
              <th scope="col" style={thStyle}>Reports checked</th>
              <th scope="col" style={thStyle}>Values (up to 3 per report)</th>
              <th scope="col" style={thStyle}>Matches</th>
              <th scope="col" style={thStyle}>No value</th>
              <th scope="col" style={thStyle}>Differs</th>
              {split && <th scope="col" style={thStyle}>Differs by over 2% to 10%</th>}
              {split && <th scope="col" style={thStyle}>Differs by over 10%</th>}
              <th scope="col" style={thStyle}>Match rate</th>
            </tr>
          </thead>
          <tbody>
            {allRows(year).map(({ key, name, row, total }) => {
              const f = row.federal;
              const rate = loaded
                ? total
                  ? percent(f.matches, f.values)
                  : rowPercent(f.matches, f.values, f.reports)
                : null;
              const small = loaded && !total && f.reports < MIN_REPORTS_FOR_RATE;
              return (
                <tr key={key} style={total ? totalRow : undefined}>
                  <th scope="row" style={{ ...tdLeft, fontWeight: total ? 600 : 400 }}>{name}</th>
                  <td style={tdStyle}>{loaded ? <K year={year} table="federal" rowKey={key} column="reports" value={f.reports} /> : DASH}</td>
                  <td style={tdStyle}>{loaded ? <K year={year} table="federal" rowKey={key} column="values" value={f.values} /> : DASH}</td>
                  <td style={tdStyle}>{loaded ? <K year={year} table="federal" rowKey={key} column="matches" value={f.matches} /> : DASH}</td>
                  <td style={tdStyle}>{loaded ? <K year={year} table="federal" rowKey={key} column="no_value" value={f.no_value} /> : DASH}</td>
                  <td style={tdStyle}>{loaded ? <K year={year} table="federal" rowKey={key} column="differs" value={f.differs} /> : DASH}</td>
                  {split && <td style={tdStyle}>{loaded ? <K year={year} table="federal" rowKey={key} column="differs_2_to_10pct" value={f.differs_2_to_10pct!} /> : DASH}</td>}
                  {split && <td style={tdStyle}>{loaded ? <K year={year} table="federal" rowKey={key} column="differs_over_10pct" value={f.differs_over_10pct!} /> : DASH}</td>}
                  <td style={tdStyle} title={small ? `Under ${MIN_REPORTS_FOR_RATE} reports: no rate` : undefined}>
                    {pc(rate)}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </Scroll>
      <DrillPanel table="federal" year={year.cds_year} />
      {loaded && (
        <Note id="dq-note-left-out">
          A value is compared only when the federal data has a positive figure for it, and matches means within 2%.
          Left out: {n(left.single_campus)} {left.single_campus === 1 ? "report" : "reports"} we’ve marked as
          filed for one campus or unit (federal data reports the whole institution) and {n(left.no_federal_figures)} whose school has no
          federal admissions figures.
        </Note>
      )}
      {loaded && (
        <>
        <Note id="dq-note-no-value">
          <strong>No value</strong> means no usable CDS number was available to compare. The school may have left it
          blank. We may have missed it, read it under a different year’s numbering, or set it aside because it
          failed a sanity check. On its own, this table can’t say which.
        </Note>
        <Note id="dq-note-differs">
          <strong>Differs</strong> isn’t always ours. Schools sometimes report different figures to the federal
          government than in their CDS, for example from a different count date. A differing value may be our
          misreading or a real difference between the two filings.{" "}
          {federalDiffersNote(year, snapshot) && <span id="dq-differs-sample"> {federalDiffersNote(year, snapshot)}</span>}
        </Note>
        {split && (
          <Note id="dq-note-differs-size">
            <strong>Size of the gap</strong> is the difference as a share of the federal figure, counted by value. A gap
            of 2% or less is a match. “Differs by over 2% to 10%” and “Differs by over 10%” split the rest, and exactly
            10% counts in “over 2% to 10%”. A gap of over 2% to 10% may come from a different count date. A gap over
            10% may be a real difference between the two filings, a scope mismatch such as one campus against the whole
            institution, a misread column, or our misreading; the size alone can’t say which.
          </Note>
        )}
        </>
      )}
      {loaded && <CsvButton table="federal" year={year} />}
    </section>
  );
}

// ── Table B, more checks ─────────────────────────────────────────

const academicYear = (start: number) => `${start}-${String((start + 1) % 100).padStart(2, "0")}`;

/** The release facts the snapshot does not record, and the rule the scoreboard applies (`fetch_federal`: final beats provisional). */
const RELEASE_NOTE = "This snapshot doesn’t record which IPEDS release (final or provisional), release date or imputation flag each figure came from. Where a final and a provisional release both have a figure, the final one is used. A school’s page shows the release and imputation for its latest federal figures, which can be a later year than the one compared here.";

/** What each extra check compares, in the page's words. The IPEDS table and variable follow the data year. */
function checkCopy(check: CheckName, dataYear: number, otherNumbered: number, otherNoValue: number) {
  if (check === "enrollment") {
    return {
      heading: "Undergraduate enrollment (CDS B1)",
      missing: `No federal fall ${dataYear} undergraduate enrollment figures yet.`,
      noFigure: "federal undergraduate enrollment figure",
      note: (
        <>
          <strong>Undergraduate enrollment</strong> compares the total of all undergraduates in the report (CDS B1:
          degree-seeking and not, full-time and part-time) with the federal fall undergraduate enrollment (IPEDS table
          DRVEF{dataYear}, variable EFUG, fall {dataYear}). Both count undergraduates on a fall census date, and the
          dates can differ. A school may also count a different group of students in each.{" "}
          {otherNoValue > 0 &&
            `${n(otherNumbered)} published ${otherNumbered === 1 ? "report is" : "reports are"} numbered by a different year’s form, where the B1 total can be harder for us to find.`}
        </>
      ),
    };
  }
  return {
    heading: "Tuition (CDS G1)",
    missing: `No federal tuition figures for the ${academicYear(dataYear)} academic year yet.`,
    noFigure: "federal tuition figure",
    note: (
      <>
        <strong>Tuition</strong> compares the report’s tuition for all undergraduates (CDS G1: the in-state figure when
        the school gives one, else the single private figure) with the federal in-state average tuition for full-time
        undergraduates (IPEDS table {ipedsTuitionTable(dataYear)},
        variable TUITION2, academic year {academicYear(dataYear)}). The CDS form for {academicYear(dataYear - 1)} asks
        for that following year’s tuition. Neither includes required fees,
        which each lists separately. A report can differ for reasons that aren’t errors: per-credit or program-specific
        pricing, a figure for a different year or group of students, or a school with several rates reporting one of them.
        Out-of-state and first-year tuition aren’t compared.
      </>
    ),
  };
}

/** Table B's two further checks, from public_format 4: enrollment (B1) and tuition (G1) against the federal figures. */
function FederalChecks({ year }: { year: QualityYear }) {
  if (!hasFederalChecks(year)) return null;
  return (
    <section aria-labelledby="dq-b2-heading" style={sectionStyle}>
      <SectionHead
        id="dq-b2-heading"
        label="§ Table B, more checks"
        title="Enrollment and tuition against federal figures"
        sentence="Two more checks of what a published report says: its total undergraduates (CDS B1) and its tuition (CDS G1), each compared with the federal figure."
      />
      <CheckTable year={year} check="enrollment" />
      <CheckTable year={year} check="tuition" />
      {(year.federal_checks!.enrollment.loaded || year.federal_checks!.tuition.loaded) && (
        <Note id="dq-note-b2-shared">
          A value is compared only when the federal data has a positive figure for it. Matches means within 2%; differs by
          over 2% to 10% and differs by over 10% split the rest, and exactly 10% counts in the first. {RELEASE_NOTE}
        </Note>
      )}
    </section>
  );
}

function CheckTable({ year, check }: { year: QualityYear; check: CheckName }) {
  const info = year.federal_checks![check];
  const loaded = info.loaded;
  const copy = checkCopy(check, info.data_year, year.other_form_numbering, year.other_form_numbering > 0 ? year.total.checks![check].no_value : 0);
  const id = `dq-table-${check}`;
  return (
    <div style={{ marginTop: 28 }}>
      <h3 className="serif" style={{ fontSize: 20, margin: "0 0 10px", fontWeight: 400 }} id={`dq-${check}-heading`}>
        {copy.heading}
      </h3>
      {!loaded && (
        <p id={`dq-no-${check}`} style={{ margin: "0 0 14px", maxWidth: 720, fontSize: 15, lineHeight: 1.6, color: "var(--ink-2)" }}>
          {copy.missing}
        </p>
      )}
      <Scroll label={`${copy.heading}, ${year.cds_year}`} hint={loaded}>
        <table className="dq-table dq-table--x" style={tableStyle} id={id} aria-labelledby={`dq-${check}-heading`}>
          <Cols n={8} />
          <thead>
            <tr>
              <th scope="col" style={thLeft}>Format</th>
              <th scope="col" style={thStyle}>Reports checked</th>
              <th scope="col" style={thStyle}>Matches</th>
              <th scope="col" style={thStyle}>No value</th>
              <th scope="col" style={thStyle}>Differs</th>
              <th scope="col" style={thStyle}>Differs by over 2% to 10%</th>
              <th scope="col" style={thStyle}>Differs by over 10%</th>
              <th scope="col" style={thStyle}>Match rate</th>
            </tr>
          </thead>
          <tbody>
            {allRows(year).map(({ key, name, row, total }) => {
              const c = row.checks![check];
              const rate = loaded ? rowPercent(c.matches, c.reports, c.reports) : null;
              const small = loaded && c.reports < MIN_REPORTS_FOR_RATE;
              return (
                <tr key={key} style={total ? totalRow : undefined}>
                  <th scope="row" style={{ ...tdLeft, fontWeight: total ? 600 : 400 }}>{name}</th>
                  <td style={tdStyle}>{loaded ? <K year={year} table={check} rowKey={key} column="reports" value={c.reports} /> : DASH}</td>
                  <td style={tdStyle}>{loaded ? <K year={year} table={check} rowKey={key} column="matches" value={c.matches} /> : DASH}</td>
                  <td style={tdStyle}>{loaded ? <K year={year} table={check} rowKey={key} column="no_value" value={c.no_value} /> : DASH}</td>
                  <td style={tdStyle}>{loaded ? <K year={year} table={check} rowKey={key} column="differs" value={c.differs} /> : DASH}</td>
                  <td style={tdStyle}>{loaded ? <K year={year} table={check} rowKey={key} column="differs_2_to_10pct" value={c.differs_2_to_10pct} /> : DASH}</td>
                  <td style={tdStyle}>{loaded ? <K year={year} table={check} rowKey={key} column="differs_over_10pct" value={c.differs_over_10pct} /> : DASH}</td>
                  <td style={tdStyle} title={small ? `Under ${MIN_REPORTS_FOR_RATE} reports: no rate` : undefined}>
                    {pc(rate)}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </Scroll>
      <DrillPanel table={check} year={year.cds_year} />
      {loaded && (
        <>
          <Note id={`dq-note-${check}`}>{copy.note}</Note>
          <Note id={`dq-note-${check}-left-out`}>
            Left out: {n(info.single_campus)} {info.single_campus === 1 ? "report" : "reports"} we’ve marked as filed for
            one campus or unit and {n(info.no_federal_figures)} whose school has no {copy.noFigure}. <strong>No value</strong>{" "}
            means no usable CDS number was available to compare: the school may have left it blank, or we may have missed
            it or set it aside. <strong>Differs</strong> isn’t always ours.
          </Note>
          <CsvButton table={check} year={year} />
        </>
      )}
    </div>
  );
}

// ── Table C ──────────────────────────────────────────────────────

function OutcomeLines({
  lines,
  reports,
  force,
  year,
  rowKey,
}: {
  lines: { label: string; count: number; column: string }[];
  reports: number;
  force: boolean;
  year: QualityYear;
  rowKey: string;
}) {
  const showRate = force || reports >= MIN_REPORTS_FOR_RATE;
  return (
    <div style={{ display: "grid", gap: 2, textAlign: "left", minWidth: 150 }}>
      {lines.map((l) => (
        <div key={l.label} style={{ display: "flex", justifyContent: "space-between", gap: 10 }}>
          <span style={{ fontFamily: "var(--sans)", color: "var(--ink-3)", fontSize: 12.5 }}>{l.label}</span>
          <span>
            <K year={year} table="totals" rowKey={rowKey} column={l.column} value={l.count} />
            {showRate ? ` (${pc(percent(l.count, reports))})` : ""}
          </span>
        </div>
      ))}
    </div>
  );
}

const sumLines = (table: "B1" | "C1", o: SumOutcomes) => [
  { label: "adds up", count: o.adds_up, column: `${table}.adds_up` },
  { label: "off by under 2%", count: o.under_2pct, column: `${table}.under_2pct` },
  { label: "off by more", count: o.off_more, column: `${table}.off_more` },
  { label: "can’t check", count: o.cant_check, column: `${table}.cant_check` },
];

function TotalsTable({ year, snapshot }: { year: QualityYear; snapshot: QualitySnapshot }) {
  return (
    <section aria-labelledby="dq-c-heading" style={sectionStyle}>
      <SectionHead
        id="dq-c-heading"
        label="§ Table C"
        title="Do the printed totals add up?"
        sentence="Whether the totals printed in each published report equal the sum of their own rows. The three tables are never averaged together."
      />
      <Scroll label={`Table C, ${year.cds_year}`} wide>
        <table className="dq-table dq-table--c" style={tableStyle} id="dq-table-c">
          <Cols n={5} />
          <thead>
            <tr>
              <th scope="col" style={thLeft}>Format</th>
              <th scope="col" style={thStyle}>Reports</th>
              <th scope="col" style={{ ...thLeft, paddingLeft: 12 }}>Enrollment (B1)</th>
              <th scope="col" style={thLeft}>Admissions (C1)</th>
              <th scope="col" style={thLeft}>Financial aid (H1)</th>
            </tr>
          </thead>
          <tbody>
            {allRows(year).map(({ key, name, row, total }) => {
              const t = row.totals;
              return (
                <tr key={key} style={total ? totalRow : undefined}>
                  <th scope="row" style={{ ...tdLeft, fontWeight: total ? 600 : 400 }}>{name}</th>
                  <td style={tdStyle}><K year={year} table="totals" rowKey={key} column="reports" value={t.reports} /></td>
                  <td style={{ ...tdStyle, textAlign: "left", paddingLeft: 12 }}>
                    <OutcomeLines lines={sumLines("B1", t.B1)} reports={t.reports} force={total} year={year} rowKey={key} />
                  </td>
                  <td style={{ ...tdStyle, textAlign: "left" }}>
                    <OutcomeLines lines={sumLines("C1", t.C1)} reports={t.reports} force={total} year={year} rowKey={key} />
                  </td>
                  <td style={{ ...tdStyle, textAlign: "left" }}>
                    <OutcomeLines
                      lines={[
                        { label: "adds up", count: t.H1.adds_up, column: "H1.adds_up" },
                        { label: "doesn’t add up", count: t.H1.doesnt, column: "H1.doesnt" },
                        { label: "can’t check", count: t.H1.cant_check, column: "H1.cant_check" },
                      ]}
                      reports={t.reports}
                      force={total}
                      year={year}
                      rowKey={key}
                    />
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </Scroll>
      <DrillPanel table="totals" year={year.cds_year} />
      <Note>
        <strong>Enrollment</strong> checks that undergraduates by sex sum to the total, and that undergraduate plus
        graduate sum to the grand total. <strong>Admissions</strong> checks that applicants, admits and enrolled by
        sex sum to their totals. <strong>Financial aid</strong> checks grant and self-help totals, and need-based and
        non-need-based, within $5; rows we didn’t read count as zero once at least one row is read.
      </Note>
      <Note>
        <strong>Adds up</strong> means at least one of the table’s sums could be checked and none failed.{" "}
        <strong>Off by under 2%</strong> (enrollment, admissions) means at least one sum missed, but every miss was
        under 2% of its printed total. <strong>Off by more</strong>, or <strong>doesn’t add up</strong> for
        financial aid, means at least one sum missed by more. <strong>Can’t check</strong> means no sum could be
        checked: the rows or the total a sum needs weren’t read, or the printed total is zero beside non-zero
        rows.
      </Note>
      <Note>
        Off by under 2% is usually the school’s file: it mostly means a small cell, such as students of unknown
        sex, left out of the rows while the total includes it. Off by more isn’t always ours either, because
        some printed totals don’t add up in the school’s own file, but it is where our reading errors show.
        Can’t check can be a blank in the school’s file, an unfilled automatic total, a miss on our side,
        or a different year’s numbering.
      </Note>
      {aidCantCheckNote(year) && <Note id="dq-note-aid-sample">{aidCantCheckNote(year)}</Note>}
      <CsvButton table="totals" year={year} />
    </section>
  );
}

// ── How to read this ─────────────────────────────────────────────

function HowToRead() {
  return (
    <section aria-labelledby="dq-how-heading" style={sectionStyle}>
      <div className="meta" style={{ marginBottom: 8 }}>§ How to read this</div>
      <h2 id="dq-how-heading" className="serif" style={{ fontSize: 26, lineHeight: 1.15, margin: "0 0 12px", fontWeight: 400 }}>
        How to read this
      </h2>
      <div style={{ display: "grid", gap: 12, maxWidth: 720, fontSize: 15, lineHeight: 1.65, color: "var(--ink-2)" }}>
        <p style={{ margin: 0 }}>
          Some of what looks like an error is the school’s. A school may leave a cell blank, print a total that
          doesn’t add up, or report different figures to the federal government. Some is ours: we may misread a
          cell or map it under the wrong year’s numbering. These tables can’t always tell which, so each
          one says what its weak spots are.
        </p>
        <p style={{ margin: 0 }}>
          Some school files disagree with themselves, for example a residency table whose totals differ from the
          table by sex. For admissions counts we use the rows by sex when both men and women were read, and the printed total otherwise.
        </p>
        <p style={{ margin: 0 }}>
          A format with fewer than {MIN_REPORTS_FOR_RATE} reports in a table shows its counts but no percentage,
          because a rate over so few reports isn’t meaningful. Year totals always show in full.
        </p>
        <p style={{ margin: 0 }}>
          If a number on a school’s page looks wrong, open that school’s page and{" "}
          <Link href="/feedback">tell us</Link>.
        </p>
        <p style={{ margin: 0 }}>
          Related: <Link href="/methodology">methodology</Link>, <Link href="/api">the API</Link>, and the{" "}
          <Link href={HAS_CDS_HREF}>colleges we have a CDS for</Link>.
        </p>
      </div>
    </section>
  );
}
