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
  TABLE_TITLES,
  fallOf,
  aidCantCheckNote,
  federalDiffersNote,
  isDataQualityLaunched,
  isProjectedYear,
  liveCount,
  percent,
  qualityCsvPath,
  resolveYear,
  rowPercent,
  yearGlance,
  yearsNewestFirst,
  type QualityRow,
  type QualitySnapshot,
  type QualityTableId,
  type QualityYear,
  type SumOutcomes,
} from "@/lib/data-quality";
import { DATA_LICENSE_NAME, DATA_LICENSE_URL } from "@/lib/data-license";
import { formatLabel } from "@/lib/format-labels";

const DASH = "–";
const HAS_CDS_PRESET = "/coverage?status=cds_available_current,cds_available_stale";

const n = (v: number) => v.toLocaleString("en-US");
const pc = (v: number | null) => (v === null ? DASH : `${v}%`);

export function DataQualityView({ snapshot }: { snapshot: QualitySnapshot }) {
  const searchParams = useSearchParams();
  const year = resolveYear(snapshot, searchParams.get("year"));
  return <DataQualityBody snapshot={snapshot} year={year} />;
}

/** Split out so tests can render a chosen year without a router. */
export function DataQualityBody({ snapshot, year }: { snapshot: QualitySnapshot; year: QualityYear }) {
  const years = yearsNewestFirst(snapshot);
  return (
    <>
      <GlanceTable years={years} />

      <section aria-labelledby="dq-year-heading" style={sectionStyle}>
        <h2 id="dq-year-heading" className="meta" style={{ margin: "0 0 10px" }}>
          § Year
        </h2>
        <YearPicker years={years} selected={year.cds_year} />
      </section>

      <Notices year={year} />
      <ReportsTable year={year} snapshot={snapshot} />
      <FederalTable year={year} snapshot={snapshot} />
      <TotalsTable year={year} snapshot={snapshot} />
      <HowToRead />
    </>
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
 * Narrowest widths the tables can shrink to before they scroll sideways. The hint above each table is CSS only
 * (data-quality.css, a container query on these numbers minus one), so it needs no script and no measuring.
 */
export const TABLE_MIN_WIDTH = 640;
export const WIDE_TABLE_MIN_WIDTH = 820;

/** Horizontal scroller for a wide table: a labelled, focusable region with a hint that shows only when the table is narrower than it needs. */
function Scroll({ children, label, wide = false }: { children: ReactNode; label: string; wide?: boolean }) {
  return (
    <div className={wide ? "dq-scroll dq-scroll--wide" : "dq-scroll"}>
      <p className="dq-scroll-hint">Scroll sideways to see every column.</p>
      <div style={{ overflowX: "auto", WebkitOverflowScrolling: "touch" }} role="region" aria-label={label} tabIndex={0}>
        {children}
      </div>
    </div>
  );
}

const tableStyle: React.CSSProperties = {
  width: "100%",
  borderCollapse: "collapse",
  fontSize: 14,
  minWidth: TABLE_MIN_WIDTH,
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
        <table style={tableStyle} id="dq-glance">
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
        <table style={tableStyle} id="dq-table-a">
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
                <td style={tdStyle}>{n(row.status.published)}</td>
                <td style={tdStyle}>{n(row.status.set_aside)}</td>
                <td style={tdStyle}>{n(row.status.couldnt_read)}</td>
                <td style={tdStyle}>{n(row.status.not_read_yet)}</td>
                <td style={tdStyle}>{row.status.published > 0 ? n(row.fields_stored.median) : DASH}</td>
                <td style={tdStyle}>{row.status.published > 0 ? n(row.fields_stored.p10) : DASH}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </Scroll>
      <Note>
        {n(liveCount(year.total.status))} reports counted. Set aside:{" "}
        {n(reasons.blank_form)} blank form, {n(reasons.too_little_read)} too little read, {n(reasons.wrong_file)} wrong
        file. Not counted: {n(year.removed)} removed
        {year.no_file > 0 ? `, ${n(year.no_file)} with no file` : ""}.
      </Note>
      <Note>
        Fields stored counts the fields stored for the report as we publish it, including fields recorded as
        unreadable or “not applicable”. It measures how much of the form we reached, not how many usable answers we have.
        The {year.form.form_year} form has {n(year.form.questions)} questions.
        {year.other_form_numbering > 0
          ? ` The ${n(year.other_form_numbering)} reports numbered by a different year’s form have field numbers from that form, whose size differs.`
          : ""}
      </Note>
      {!isProjectedYear(year.cds_year) && (
        <Note id="dq-note-counting">
          {year.cds_year} is counted differently. From 2024-25 on, fields stored also includes values from a second
          reading of the same file. This year counts one reading, so it reads lower partly for that reason.
        </Note>
      )}
      <CsvButton table="reports" year={year} />
    </section>
  );
}

// ── Table B ──────────────────────────────────────────────────────

function FederalTable({ year, snapshot }: { year: QualityYear; snapshot: QualitySnapshot }) {
  const loaded = year.federal_fall_loaded;
  const left = year.federal_left_out;
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
      <Scroll label={`Table B, ${year.cds_year}`}>
        <table style={tableStyle} id="dq-table-b">
          <thead>
            <tr>
              <th scope="col" style={thLeft}>Format</th>
              <th scope="col" style={thStyle}>Reports checked</th>
              <th scope="col" style={thStyle}>Values (up to 3 per report)</th>
              <th scope="col" style={thStyle}>Matches</th>
              <th scope="col" style={thStyle}>No value</th>
              <th scope="col" style={thStyle}>Differs</th>
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
                  <td style={tdStyle}>{loaded ? n(f.reports) : DASH}</td>
                  <td style={tdStyle}>{loaded ? n(f.values) : DASH}</td>
                  <td style={tdStyle}>{loaded ? n(f.matches) : DASH}</td>
                  <td style={tdStyle}>{loaded ? n(f.no_value) : DASH}</td>
                  <td style={tdStyle}>{loaded ? n(f.differs) : DASH}</td>
                  <td style={tdStyle} title={small ? `Under ${MIN_REPORTS_FOR_RATE} reports: no rate` : undefined}>
                    {pc(rate)}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </Scroll>
      {loaded && (
        <Note>
          A value is compared only when the federal data has a positive figure for it, and matches means within 2%.
          Left out: {n(left.single_campus)} {left.single_campus === 1 ? "report" : "reports"} we’ve marked as
          filed for one campus or unit (federal data reports the whole institution) and {n(left.no_federal_figures)} whose school has no
          federal admissions figures.
        </Note>
      )}
      {loaded && (
        <>
        <Note>
          <strong>No value</strong> means no usable CDS number was available to compare. The school may have left it
          blank. We may have missed it, read it under a different year’s numbering, or set it aside because it
          failed a sanity check. On its own, this table can’t say which.
        </Note>
        <Note id="dq-note-differs">
          <strong>Differs</strong> isn’t always ours. Schools sometimes report different figures to the federal
          government than in their CDS, for example from a different count date. A differing value may be our
          misreading or a real difference between the two filings.
          {federalDiffersNote(year, snapshot) && <span id="dq-differs-sample"> {federalDiffersNote(year, snapshot)}</span>}
        </Note>
        </>
      )}
      {loaded && <CsvButton table="federal" year={year} />}
    </section>
  );
}

// ── Table C ──────────────────────────────────────────────────────

function OutcomeLines({
  lines,
  reports,
  force,
}: {
  lines: { label: string; count: number }[];
  reports: number;
  force: boolean;
}) {
  const showRate = force || reports >= MIN_REPORTS_FOR_RATE;
  return (
    <div style={{ display: "grid", gap: 2, textAlign: "left", minWidth: 150 }}>
      {lines.map((l) => (
        <div key={l.label} style={{ display: "flex", justifyContent: "space-between", gap: 10 }}>
          <span style={{ fontFamily: "var(--sans)", color: "var(--ink-3)", fontSize: 12.5 }}>{l.label}</span>
          <span>
            {n(l.count)}
            {showRate ? ` (${pc(percent(l.count, reports))})` : ""}
          </span>
        </div>
      ))}
    </div>
  );
}

const sumLines = (o: SumOutcomes) => [
  { label: "adds up", count: o.adds_up },
  { label: "off by under 2%", count: o.under_2pct },
  { label: "off by more", count: o.off_more },
  { label: "can’t check", count: o.cant_check },
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
        <table style={{ ...tableStyle, minWidth: WIDE_TABLE_MIN_WIDTH }} id="dq-table-c">
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
                  <td style={tdStyle}>{n(t.reports)}</td>
                  <td style={{ ...tdStyle, textAlign: "left", paddingLeft: 12 }}>
                    <OutcomeLines lines={sumLines(t.B1)} reports={t.reports} force={total} />
                  </td>
                  <td style={{ ...tdStyle, textAlign: "left" }}>
                    <OutcomeLines lines={sumLines(t.C1)} reports={t.reports} force={total} />
                  </td>
                  <td style={{ ...tdStyle, textAlign: "left" }}>
                    <OutcomeLines
                      lines={[
                        { label: "adds up", count: t.H1.adds_up },
                        { label: "doesn’t add up", count: t.H1.doesnt },
                        { label: "can’t check", count: t.H1.cant_check },
                      ]}
                      reports={t.reports}
                      force={total}
                    />
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </Scroll>
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
          <Link href={HAS_CDS_PRESET}>colleges we have a CDS for</Link>.
        </p>
      </div>
    </section>
  );
}
