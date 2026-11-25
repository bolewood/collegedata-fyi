"use client";

// PRD 015 M6 — interactive accountability dashboard for the /coverage
// page. Receives all in-scope coverage rows server-side, then handles
// histogram + filters + virtualized table client-side so toggling
// filters is instant. URL search params persist filter state so any
// view (e.g. "no public CDS found in NY at schools >25K UGDS") is
// shareable.
//
// Renders ~2,900 rows total. Default filter is "missing-CDS only"
// (the schools the page exists to surface) but a one-click toggle
// shows all in-scope schools.
//
// Virtualization via @tanstack/react-virtual so only the visible
// rows mount in the DOM. Without it, scrolling 2,900 rows in a real
// <table> stutters; with it, scroll is silky and the table stays
// semantically correct for screen readers.

import { useEffect, useMemo, useRef, useState, useTransition } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { ListLink } from "./ListLink";
import { useVirtualizer } from "@tanstack/react-virtual";
import type { CoverageStatus, InstitutionCoverage } from "@/lib/types";
import { CoverageBadge } from "./CoverageBadge";
import { SchoolGlyph } from "./SchoolGlyph";
import {
  COVERAGE_STATUS_LABELS,
  DEFAULT_MISSING,
  ENROLLMENT_BANDS,
  HAS_CDS_HREF,
  HAS_CDS_STATUSES,
  RECENCY_OPTIONS,
  STATUS_ORDER,
  buildCoverageCsv,
  currentCdsYear,
  filterCoverageRows,
  latestYearBuckets,
  parseCoverageView,
  sameSet,
  weightedShare,
  type EnrollmentBandId,
  type RecencyId,
} from "@/lib/coverage-model";
import { compareYearsDesc, formatSnapshotDate, renewalTile, type Renewal } from "@/lib/data-quality";

/** The committed Data quality snapshot's renewal block, passed in by the server page (null before the first snapshot). */
export type RenewalProp = { renewal: Renewal; snapshotOf: string } | null;

type SortKey = "name" | "state" | "enrollment" | "status" | "numbers" | "found" | "checked";
type SortDir = "asc" | "desc";

const ROW_HEIGHT = 64;

export function CoverageDashboard({
  rows,
  renewal = null,
}: {
  rows: InstitutionCoverage[];
  renewal?: RenewalProp;
}) {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [, startTransition] = useTransition();

  // URL-driven filter state. We read on every render so back/forward
  // restores the filter; we write via router.replace so changes don't
  // pollute the history stack.
  const view = parseCoverageView(searchParams);
  const activeStatuses: Set<CoverageStatus> = view.statuses;
  const stateParam = view.state;
  const sizeParam = view.size;
  const checkedParam = view.checked;
  const showAllParam = view.all;
  const hasCdsActive = !showAllParam && sameSet(activeStatuses, new Set(HAS_CDS_STATUSES));

  // The search box is local state so typing stays responsive; it follows the
  // URL's `q` whenever that changes (back/forward, Reset).
  const [searchText, setSearchText] = useState(view.q);
  useEffect(() => setSearchText(view.q), [view.q]);

  const allStates = useMemo(() => {
    const set = new Set<string>();
    for (const r of rows) if (r.state) set.add(r.state);
    return Array.from(set).sort();
  }, [rows]);

  // Tile counts use the FULL row set (every tracked school) so the headline
  // doesn't lie when the user filters. The "showing X of Y" line above the
  // table reflects the filtered count.
  const histogram = useMemo(() => {
    const counts: Record<CoverageStatus, number> = {} as Record<CoverageStatus, number>;
    for (const s of STATUS_ORDER) counts[s] = 0;
    for (const r of rows) {
      if (r.coverage_status === "out_of_scope") continue;
      counts[r.coverage_status] = (counts[r.coverage_status] ?? 0) + 1;
    }
    return counts;
  }, [rows]);

  const total = rows.length;
  const share = useMemo(() => weightedShare(rows), [rows]);
  const currentYear = renewal?.renewal.current_year;
  const yearBuckets = useMemo(() => latestYearBuckets(rows, currentCdsYear(currentYear)), [rows, currentYear]);
  const tile = renewal ? renewalTile(renewal.renewal) : null;

  const [sortKey, setSortKey] = useState<SortKey>("name");
  const [sortDir, setSortDir] = useState<SortDir>("asc");

  const query = searchParams.toString();
  const filteredRows = useMemo(() => {
    const filtered = filterCoverageRows(rows, parseCoverageView(new URLSearchParams(query)));

    const dir = sortDir === "asc" ? 1 : -1;
    filtered.sort((a, b) => {
      switch (sortKey) {
        case "name":
          return a.school_name.localeCompare(b.school_name) * dir;
        case "state":
          return ((a.state ?? "").localeCompare(b.state ?? "")) * dir
            || a.school_name.localeCompare(b.school_name);
        case "enrollment": {
          const ae = a.undergraduate_enrollment;
          const be = b.undergraduate_enrollment;
          if (ae == null && be == null) return a.school_name.localeCompare(b.school_name);
          if (ae == null) return 1;
          if (be == null) return -1;
          return (ae - be) * dir;
        }
        case "status":
          return (
            (STATUS_ORDER.indexOf(a.coverage_status) - STATUS_ORDER.indexOf(b.coverage_status)) * dir
            || a.school_name.localeCompare(b.school_name)
          );
        case "numbers":
          // compareYearsDesc is newest-first, so flip it: ascending means oldest first.
          return -compareYearsDesc(a.latest_available_cds_year ?? "none", b.latest_available_cds_year ?? "none") * dir
            || a.school_name.localeCompare(b.school_name);
        case "found":
          return -compareYearsDesc(a.latest_found_cds_year ?? "none", b.latest_found_cds_year ?? "none") * dir
            || a.school_name.localeCompare(b.school_name);
        case "checked": {
          const ac = a.last_checked_at ? new Date(a.last_checked_at).getTime() : 0;
          const bc = b.last_checked_at ? new Date(b.last_checked_at).getTime() : 0;
          return (ac - bc) * dir || a.school_name.localeCompare(b.school_name);
        }
      }
    });
    return filtered;
  }, [rows, query, sortKey, sortDir]);

  // ── URL writers ──────────────────────────────────────────────────
  function updateParams(updater: (params: URLSearchParams) => void) {
    const params = new URLSearchParams(searchParams.toString());
    updater(params);
    startTransition(() => {
      const qs = params.toString();
      router.replace(qs ? `/coverage?${qs}` : "/coverage", { scroll: false });
    });
  }

  function toggleStatus(status: CoverageStatus) {
    const next = new Set(activeStatuses);
    if (next.has(status)) next.delete(status);
    else next.add(status);
    updateParams((p) => {
      p.delete("all");
      const arr = STATUS_ORDER.filter((s) => next.has(s));
      if (arr.length === 0 || sameSet(new Set(arr), new Set(DEFAULT_MISSING))) {
        p.delete("status");
      } else {
        p.set("status", arr.join(","));
      }
    });
  }

  function setShowAll(show: boolean) {
    updateParams((p) => {
      if (show) {
        p.set("all", "1");
        p.delete("status");
      } else {
        p.delete("all");
      }
    });
  }

  function setState(value: string) {
    updateParams((p) => {
      if (value) p.set("state", value);
      else p.delete("state");
    });
  }

  function setSize(value: EnrollmentBandId) {
    updateParams((p) => {
      if (value === "any") p.delete("size");
      else p.set("size", value);
    });
  }

  function setRecency(value: RecencyId) {
    updateParams((p) => {
      if (value === "any") p.delete("checked");
      else p.set("checked", value);
    });
  }

  function setQuery(value: string) {
    setSearchText(value);
    updateParams((p) => {
      if (value.trim()) p.set("q", value);
      else p.delete("q");
    });
  }

  function downloadRows(list: InstitutionCoverage[], scope: "view" | "all") {
    const day = new Date().toISOString().slice(0, 10);
    const blob = new Blob([buildCoverageCsv(list, day)], { type: "text/csv;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `collegedata-coverage-${scope === "all" ? "all-colleges" : "view"}-${day}.csv`;
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
  }

  function clearFilters() {
    startTransition(() => router.replace("/coverage", { scroll: false }));
  }

  function handleSort(key: SortKey) {
    if (sortKey === key) {
      setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    } else {
      setSortKey(key);
      setSortDir(key === "enrollment" || key === "checked" ? "desc" : "asc");
    }
  }

  // ── Virtualization ───────────────────────────────────────────────
  const parentRef = useRef<HTMLDivElement>(null);
  const virtualizer = useVirtualizer({
    count: filteredRows.length,
    getScrollElement: () => parentRef.current,
    estimateSize: () => ROW_HEIGHT,
    overscan: 8,
  });

  return (
    <>
      {/* Summary strip: renewal first, then colleges tracked, the weighted share, and the status tiles */}
      <section
        aria-label="Coverage summary"
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(160px, 1fr))",
          gap: 16,
          marginBottom: 20,
          paddingTop: 20,
          borderTop: "1px solid var(--rule-strong)",
        }}
      >
        {tile && renewal && (
          <StatCell
            label={"This year\u2019s reports on file"}
            value={`${tile.percent}%`}
            note={`${tile.sentence} Snapshot of ${formatSnapshotDate(renewal.snapshotOf)}.`}
            emphasis
            testId="renewal-tile"
          />
        )}
        <StatCell
          label="Colleges tracked"
          value={total}
          note="Accept federal aid and enroll undergraduates"
          emphasis
        />
        <StatCell
          label="Undergrads with CDS numbers"
          value={share.share === null ? "\u2013" : `${Math.round(share.share * 100)}%`}
          note={`Share of undergraduates at tracked colleges with CDS numbers on file. ${share.withoutEnrollment.toLocaleString("en-US")} ${share.withoutEnrollment === 1 ? "college has" : "colleges have"} no enrollment figure and ${share.withoutEnrollment === 1 ? "is" : "are"} left out of both sums.`}
          emphasis
          testId="weighted-share-tile"
        />
        {STATUS_ORDER.filter((s) => histogram[s] > 0).map((s) => (
          <StatCell
            key={s}
            label={COVERAGE_STATUS_LABELS[s]}
            value={histogram[s]}
            note={`${pct(histogram[s], total)}%`}
            active={activeStatuses.has(s) && !showAllParam}
            onClick={() => toggleStatus(s)}
          />
        ))}
      </section>

      {/* Latest year with numbers */}
      <section
        aria-label="Latest year with numbers"
        style={{
          display: "flex",
          flexWrap: "wrap",
          gap: 20,
          alignItems: "baseline",
          marginBottom: 32,
          paddingBottom: 16,
          borderBottom: "1px solid var(--rule)",
        }}
      >
        <span className="meta" style={{ color: "var(--ink-3)" }}>§ Latest year with numbers</span>
        {yearBuckets.map((b) => (
          <span key={b.id} className="mono nums" style={{ fontSize: 13, color: "var(--ink-2)" }}>
            {b.label} <strong style={{ color: "var(--ink)" }}>{b.count.toLocaleString("en-US")}</strong>
          </span>
        ))}
      </section>

      {/* Filter bar */}
      <section
        style={{
          display: "flex",
          flexWrap: "wrap",
          gap: 10,
          alignItems: "baseline",
          marginBottom: 14,
        }}
      >
        <span className="meta" style={{ color: "var(--ink-3)" }}>§ Filter</span>

        <input
          type="search"
          value={searchText}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Search name or IPEDS ID"
          aria-label="Search by school name or IPEDS ID"
          style={{ ...selectStyle, textTransform: "none", minWidth: 200 }}
        />

        <select
          value={stateParam ?? ""}
          onChange={(e) => setState(e.target.value)}
          style={selectStyle}
          aria-label="Filter by state"
        >
          <option value="">All states</option>
          {allStates.map((s) => (
            <option key={s} value={s}>
              {s}
            </option>
          ))}
        </select>

        <ButtonGroup
          options={ENROLLMENT_BANDS.map((b) => ({ id: b.id, label: b.label }))}
          value={sizeParam}
          onChange={(v) => setSize(v as EnrollmentBandId)}
        />

        <ButtonGroup
          options={RECENCY_OPTIONS.map((r) => ({ id: r.id, label: r.label }))}
          value={checkedParam}
          onChange={(v) => setRecency(v as RecencyId)}
        />

        <Link
          href={HAS_CDS_HREF}
          replace
          scroll={false}
          className="cd-chip"
          aria-current={hasCdsActive ? "true" : undefined}
          style={{
            textDecoration: "none",
            background: hasCdsActive ? "var(--ink)" : "transparent",
            color: hasCdsActive ? "var(--paper)" : "var(--ink-2)",
            borderColor: hasCdsActive ? "var(--ink)" : "var(--rule-strong)",
          }}
        >
          Has a CDS
        </Link>

        <button
          onClick={() => setShowAll(!showAllParam)}
          className="cd-chip"
          style={{
            cursor: "pointer",
            background: showAllParam ? "var(--ink)" : "transparent",
            color: showAllParam ? "var(--paper)" : "var(--ink-2)",
            borderColor: showAllParam ? "var(--ink)" : "var(--rule-strong)",
          }}
        >
          {showAllParam ? "Showing all tracked colleges" : "Showing missing only"}
        </button>

        <button
          onClick={clearFilters}
          className="cd-chip"
          style={{
            cursor: "pointer",
            background: "transparent",
            color: "var(--ink-3)",
            borderStyle: "dashed",
          }}
        >
          Reset
        </button>
      </section>

      <div
        className="mono"
        style={{ marginBottom: 8, fontSize: 12, color: "var(--ink-3)" }}
      >
        SHOWING {filteredRows.length.toLocaleString()} OF {total.toLocaleString()} INSTITUTIONS
      </div>

      <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginBottom: 12 }}>
        <button
          type="button"
          className="cd-chip"
          style={{ cursor: "pointer", background: "transparent" }}
          onClick={() => downloadRows(filteredRows, "view")}
        >
          Download this view (CSV)
        </button>
        <button
          type="button"
          className="cd-chip"
          style={{ cursor: "pointer", background: "transparent" }}
          onClick={() => downloadRows(rows, "all")}
        >
          Download all colleges (CSV)
        </button>
      </div>

      <div
        style={{
          overflowX: "auto",
          WebkitOverflowScrolling: "touch",
        }}
        role="table"
        aria-label="Coverage table"
        // Rows are virtualized, so give the full count and each row's index.
        aria-rowcount={filteredRows.length + 1}
      >
        <div
          role="presentation"
          style={{
            minWidth: TABLE_MIN_WIDTH,
          }}
        >
          {/* Sticky table header */}
          <div
            role="row"
            aria-rowindex={1}
            style={{
              display: "grid",
              gridTemplateColumns: TABLE_COLUMNS,
              columnGap: TABLE_COLUMN_GAP,
              alignItems: "baseline",
              padding: "12px 0",
              borderTop: "1px solid var(--rule-strong)",
              borderBottom: "1px solid var(--rule-strong)",
              fontFamily: "var(--mono)",
              fontSize: 11,
              letterSpacing: "0.06em",
              textTransform: "uppercase",
              color: "var(--ink-3)",
              background: "var(--paper)",
            }}
          >
            <SortHeader label="School" col="name" sortKey={sortKey} sortDir={sortDir} onSort={handleSort} />
            <SortHeader label="State" col="state" sortKey={sortKey} sortDir={sortDir} onSort={handleSort} />
            <SortHeader
              label="Undergrads"
              col="enrollment"
              sortKey={sortKey}
              sortDir={sortDir}
              onSort={handleSort}
              align="right"
            />
            <SortHeader label="Status" col="status" sortKey={sortKey} sortDir={sortDir} onSort={handleSort} />
            <SortHeader label="With numbers" col="numbers" sortKey={sortKey} sortDir={sortDir} onSort={handleSort} />
            <SortHeader label="Found" col="found" sortKey={sortKey} sortDir={sortDir} onSort={handleSort} />
            <SortHeader label="Last checked" col="checked" sortKey={sortKey} sortDir={sortDir} onSort={handleSort} />
            <span role="columnheader">Action</span>
          </div>

          {/* Virtualized table body */}
          <div
            ref={parentRef}
            role="rowgroup"
            style={{
              height: TABLE_VIEWPORT_HEIGHT,
              overflowY: "auto",
              borderBottom: "1px solid var(--rule-strong)",
            }}
          >
            <div
              role="presentation"
              style={{
                height: virtualizer.getTotalSize(),
                position: "relative",
                width: "100%",
              }}
            >
              {virtualizer.getVirtualItems().map((vi) => {
                const r = filteredRows[vi.index];
                return (
                  <div
                    key={r.school_id}
                    style={{
                      position: "absolute",
                      top: 0,
                      left: 0,
                      right: 0,
                      transform: `translateY(${vi.start}px)`,
                      height: ROW_HEIGHT,
                      display: "grid",
                      gridTemplateColumns: TABLE_COLUMNS,
                      columnGap: TABLE_COLUMN_GAP,
                      alignItems: "center",
                      padding: "0 0",
                      borderTop: vi.index === 0 ? "none" : "1px solid var(--rule)",
                    }}
                    role="row"
                    aria-rowindex={vi.index + 2}
                  >
                    <span role="cell" style={{ minWidth: 0 }}>
                      <ListLink
                        href={`/schools/${r.school_id}`}
                        className="school-name-with-glyph"
                        style={{
                          fontFamily: "var(--serif)",
                          fontSize: 16,
                          lineHeight: 1.25,
                          color: "var(--ink)",
                          textDecoration: "none",
                        }}
                      >
                        <SchoolGlyph size="sm" brandColors={r.brand_colors} />
                        {r.school_name}
                      </ListLink>
                    </span>
                    <span role="cell" className="mono" style={{ fontSize: 12, color: "var(--ink-2)" }}>
                      {r.state ?? "—"}
                    </span>
                    <span
                      role="cell"
                      className="mono nums"
                      style={{ fontSize: 13, color: "var(--ink-2)", textAlign: "right" }}
                    >
                      {r.undergraduate_enrollment != null
                        ? r.undergraduate_enrollment.toLocaleString()
                        : "—"}
                    </span>
                    <span role="cell" style={{ minWidth: 0 }}>
                      <CoverageBadge status={r.coverage_status} label={COVERAGE_STATUS_LABELS[r.coverage_status] ?? r.coverage_label} />
                    </span>
                    <span role="cell" className="mono nums" style={{ fontSize: 12, color: "var(--ink-2)" }}>
                      {yearOrDash(r.latest_available_cds_year)}
                    </span>
                    <span role="cell" className="mono nums" style={{ fontSize: 12, color: "var(--ink-2)" }}>
                      {yearOrDash(r.latest_found_cds_year)}
                    </span>
                    <span role="cell" className="mono" style={{ fontSize: 12, color: "var(--ink-3)" }}>
                      {formatChecked(r.last_checked_at)}
                    </span>
                    <span role="cell">
                      {r.can_submit_source ? (
                        <ListLink
                          href={`/schools/${r.school_id}#submit`}
                          className="mono"
                          style={{ fontSize: 12 }}
                        >
                          Send the link
                        </ListLink>
                      ) : (
                        <ListLink
                          href={`/schools/${r.school_id}`}
                          className="mono"
                          style={{ fontSize: 12, color: "var(--ink-3)" }}
                        >
                          Open
                        </ListLink>
                      )}
                    </span>
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      </div>

      {filteredRows.length === 0 && (
        <p
          className="mono"
          style={{
            padding: "32px 0",
            textAlign: "center",
            fontSize: 12,
            color: "var(--ink-3)",
          }}
        >
          NO INSTITUTIONS MATCH THESE FILTERS.
        </p>
      )}
    </>
  );
}

const TABLE_COLUMNS = "minmax(260px, 2fr) 56px 96px minmax(220px, 1fr) 100px 90px 130px 110px";
const TABLE_COLUMN_GAP = 18;
const TABLE_MIN_WIDTH = 1180;
const TABLE_VIEWPORT_HEIGHT = ROW_HEIGHT * 10;

function StatCell({
  label,
  value,
  note,
  emphasis,
  active,
  onClick,
  testId,
}: {
  label: string;
  value: number | string;
  note: string;
  emphasis?: boolean;
  active?: boolean;
  onClick?: () => void;
  testId?: string;
}) {
  const Tag = onClick ? "button" : "div";
  return (
    <Tag
      onClick={onClick}
      aria-pressed={onClick ? active : undefined}
      data-testid={testId}
      style={{
        textAlign: "left",
        padding: 0,
        background: "transparent",
        border: "none",
        font: "inherit",
        color: "inherit",
        cursor: onClick ? "pointer" : "default",
      }}
    >
      <div className="meta" style={{ marginBottom: 6, color: emphasis ? "var(--ink)" : "var(--ink-3)" }}>
        {label}
      </div>
      <div
        className="serif stat-num"
        style={{
          fontSize: emphasis ? 32 : 26,
          lineHeight: 1,
          letterSpacing: "-0.02em",
          color: active === false ? "var(--ink-3)" : "var(--ink)",
        }}
      >
        {typeof value === "number" ? value.toLocaleString() : value}
      </div>
      <div className="mono" style={{ fontSize: 11, color: "var(--ink-3)", marginTop: 4 }}>
        {note}
      </div>
    </Tag>
  );
}

function SortHeader({
  label,
  col,
  sortKey,
  sortDir,
  onSort,
  align,
}: {
  label: string;
  col: SortKey;
  sortKey: SortKey;
  sortDir: SortDir;
  onSort: (col: SortKey) => void;
  align?: "right";
}) {
  const active = sortKey === col;
  return (
    <span
      role="columnheader"
      aria-sort={active ? (sortDir === "asc" ? "ascending" : "descending") : undefined}
      style={{ textAlign: align === "right" ? "right" : "left" }}
    >
      <button
        onClick={() => onSort(col)}
        style={{
          textAlign: align === "right" ? "right" : "left",
          background: "transparent",
          border: "none",
          padding: 0,
          font: "inherit",
          color: active ? "var(--ink)" : "var(--ink-3)",
          cursor: "pointer",
          letterSpacing: "0.06em",
          textTransform: "uppercase",
        }}
      >
        {label}
        {active && (
          <span style={{ marginLeft: 6 }}>
            {sortDir === "asc" ? "▲" : "▼"}
          </span>
        )}
      </button>
    </span>
  );
}

function ButtonGroup<T extends string>({
  options,
  value,
  onChange,
}: {
  options: { id: T; label: string }[];
  value: T;
  onChange: (id: T) => void;
}) {
  return (
    <span style={{ display: "inline-flex", gap: 4, flexWrap: "wrap" }}>
      {options.map((opt) => {
        const selected = value === opt.id;
        return (
          <button
            key={opt.id}
            onClick={() => onChange(opt.id)}
            className="cd-chip"
            style={{
              cursor: "pointer",
              background: selected ? "var(--ink)" : "transparent",
              color: selected ? "var(--paper)" : "var(--ink-2)",
              borderColor: selected ? "var(--ink)" : "var(--rule-strong)",
            }}
          >
            {opt.label}
          </button>
        );
      })}
    </span>
  );
}

const selectStyle: React.CSSProperties = {
  padding: "4px 10px",
  fontFamily: "var(--mono)",
  fontSize: 11,
  letterSpacing: "0.06em",
  textTransform: "uppercase",
  border: "1px solid var(--rule-strong)",
  background: "transparent",
  borderRadius: 2,
  color: "var(--ink-2)",
};

function pct(n: number, total: number): string {
  if (total === 0) return "0";
  return ((100 * n) / total).toFixed(1);
}

function formatChecked(iso: string | null): string {
  if (!iso) return "Never";
  const d = new Date(iso);
  return d.toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });
}

function yearOrDash(year: string | null): string {
  return year && /^\d{4}-\d{2}$/.test(year) ? year : "\u2013";
}
