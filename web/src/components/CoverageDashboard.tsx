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

import { useMemo, useRef, useState, useTransition } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import Link from "next/link";
import { useVirtualizer } from "@tanstack/react-virtual";
import type { CoverageStatus, InstitutionCoverage } from "@/lib/types";
import { CoverageBadge } from "./CoverageBadge";

// Display order for both the histogram and the status filter chips.
// Mirrors PRD line 309 (most-positive → least-positive → never-checked).
const STATUS_ORDER: CoverageStatus[] = [
  "cds_available_current",
  "cds_available_stale",
  "cds_found_processing",
  "latest_found_extract_failed_with_prior_available",
  "extract_failed",
  "source_not_automatically_accessible",
  "no_public_cds_found",
  "verified_absent",
  "not_checked",
];

// "Missing CDS" preset — the default landing view. Everything except
// schools where we already have current data. Matches PRD's "Missing-
// CDS table" framing for the coverage page.
const DEFAULT_MISSING: CoverageStatus[] = STATUS_ORDER.filter(
  (s) => s !== "cds_available_current" && s !== "verified_absent",
);

const ENROLLMENT_BANDS = [
  { id: "any", label: "Any size" },
  { id: "u2k", label: "<2K", test: (n: number | null) => n != null && n < 2000 },
  { id: "2k-10k", label: "2–10K", test: (n: number | null) => n != null && n >= 2000 && n < 10000 },
  { id: "10k-25k", label: "10–25K", test: (n: number | null) => n != null && n >= 10000 && n < 25000 },
  { id: "25k+", label: "25K+", test: (n: number | null) => n != null && n >= 25000 },
] as const;

type EnrollmentBandId = (typeof ENROLLMENT_BANDS)[number]["id"];

const RECENCY_OPTIONS = [
  { id: "any", label: "Any time" },
  { id: "30d", label: "Last 30 days", days: 30 },
  { id: "90d", label: "Last 90 days", days: 90 },
  { id: "older", label: "Older than 90 days", olderThan: 90 },
  { id: "never", label: "Never checked" },
] as const;

type RecencyId = (typeof RECENCY_OPTIONS)[number]["id"];

type SortKey = "name" | "state" | "enrollment" | "status" | "checked";
type SortDir = "asc" | "desc";

const ROW_HEIGHT = 56;

export function CoverageDashboard({ rows }: { rows: InstitutionCoverage[] }) {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [, startTransition] = useTransition();

  // URL-driven filter state. We read on every render so back/forward
  // restores the filter; we write via router.replace so changes don't
  // pollute the history stack.
  const statusParam = searchParams.get("status");
  const stateParam = searchParams.get("state");
  const sizeParam = (searchParams.get("size") as EnrollmentBandId | null) ?? "any";
  const checkedParam = (searchParams.get("checked") as RecencyId | null) ?? "any";
  const showAllParam = searchParams.get("all") === "1";

  const activeStatuses: Set<CoverageStatus> = useMemo(() => {
    if (showAllParam) return new Set(STATUS_ORDER);
    if (statusParam) {
      const parts = statusParam.split(",").filter(Boolean) as CoverageStatus[];
      return new Set(parts.length > 0 ? parts : DEFAULT_MISSING);
    }
    return new Set(DEFAULT_MISSING);
  }, [statusParam, showAllParam]);

  const allStates = useMemo(() => {
    const set = new Set<string>();
    for (const r of rows) if (r.state) set.add(r.state);
    return Array.from(set).sort();
  }, [rows]);

  // Histogram counts use the FULL row set (every in-scope school) so
  // the headline doesn't lie when the user filters. The "showing X
  // of Y" line above the table reflects the filtered count.
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

  const [sortKey, setSortKey] = useState<SortKey>("name");
  const [sortDir, setSortDir] = useState<SortDir>("asc");

  const filteredRows = useMemo(() => {
    const enrollmentBand = ENROLLMENT_BANDS.find((b) => b.id === sizeParam);
    const recency = RECENCY_OPTIONS.find((r) => r.id === checkedParam);
    const now = Date.now();
    const filtered = rows.filter((r) => {
      if (!activeStatuses.has(r.coverage_status)) return false;
      if (stateParam && r.state !== stateParam) return false;
      if (enrollmentBand && "test" in enrollmentBand && !enrollmentBand.test(r.undergraduate_enrollment)) {
        return false;
      }
      if (recency && recency.id !== "any") {
        const ts = r.last_checked_at ? new Date(r.last_checked_at).getTime() : null;
        if (recency.id === "never") {
          if (ts != null) return false;
        } else if ("days" in recency) {
          if (ts == null || now - ts > recency.days * 86_400_000) return false;
        } else if ("olderThan" in recency) {
          if (ts == null) return false;
          if (now - ts <= recency.olderThan * 86_400_000) return false;
        }
      }
      return true;
    });

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
        case "checked": {
          const ac = a.last_checked_at ? new Date(a.last_checked_at).getTime() : 0;
          const bc = b.last_checked_at ? new Date(b.last_checked_at).getTime() : 0;
          return (ac - bc) * dir || a.school_name.localeCompare(b.school_name);
        }
      }
    });
    return filtered;
  }, [rows, activeStatuses, stateParam, sizeParam, checkedParam, sortKey, sortDir]);

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
      {/* Histogram banner */}
      <section
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(140px, 1fr))",
          gap: 12,
          marginBottom: 32,
          paddingTop: 20,
          borderTop: "1px solid var(--rule-strong)",
        }}
      >
        <StatCell label="In-scope total" value={total} note="Title-IV, undergrad-serving" emphasis />
        {STATUS_ORDER.filter((s) => histogram[s] > 0).map((s) => (
          <StatCell
            key={s}
            label={LABEL_BY_STATUS[s]}
            value={histogram[s]}
            note={`${pct(histogram[s], total)}%`}
            active={activeStatuses.has(s) && !showAllParam}
            onClick={() => toggleStatus(s)}
          />
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
          {showAllParam ? "Showing all statuses" : "Showing missing only"}
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

      {/* Sticky table header */}
      <div
        role="row"
        style={{
          display: "grid",
          gridTemplateColumns: TABLE_COLUMNS,
          alignItems: "baseline",
          padding: "10px 0",
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
          label="UGDS"
          col="enrollment"
          sortKey={sortKey}
          sortDir={sortDir}
          onSort={handleSort}
          align="right"
        />
        <SortHeader label="Status" col="status" sortKey={sortKey} sortDir={sortDir} onSort={handleSort} />
        <SortHeader label="Last checked" col="checked" sortKey={sortKey} sortDir={sortDir} onSort={handleSort} />
        <span>Action</span>
      </div>

      {/* Virtualized table body */}
      <div
        ref={parentRef}
        style={{
          height: 600,
          overflowY: "auto",
          borderBottom: "1px solid var(--rule-strong)",
        }}
      >
        <div
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
                  alignItems: "center",
                  padding: "0 0",
                  borderTop: vi.index === 0 ? "none" : "1px solid var(--rule)",
                }}
                role="row"
              >
                <Link
                  href={`/schools/${r.school_id}`}
                  style={{
                    fontFamily: "var(--serif)",
                    fontSize: 16,
                    color: "var(--ink)",
                    textDecoration: "none",
                  }}
                >
                  {r.school_name}
                </Link>
                <span className="mono" style={{ fontSize: 12, color: "var(--ink-2)" }}>
                  {r.state ?? "—"}
                </span>
                <span
                  className="mono nums"
                  style={{ fontSize: 13, color: "var(--ink-2)", textAlign: "right" }}
                >
                  {r.undergraduate_enrollment != null
                    ? r.undergraduate_enrollment.toLocaleString()
                    : "—"}
                </span>
                <CoverageBadge status={r.coverage_status} label={r.coverage_label} />
                <span className="mono" style={{ fontSize: 12, color: "var(--ink-3)" }}>
                  {formatChecked(r.last_checked_at)}
                </span>
                {r.can_submit_source ? (
                  <Link
                    href={`/schools/${r.school_id}#submit`}
                    className="mono"
                    style={{ fontSize: 12 }}
                  >
                    Send the link
                  </Link>
                ) : (
                  <Link
                    href={`/schools/${r.school_id}`}
                    className="mono"
                    style={{ fontSize: 12, color: "var(--ink-3)" }}
                  >
                    Open
                  </Link>
                )}
              </div>
            );
          })}
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

const TABLE_COLUMNS = "minmax(220px, 2fr) 56px 88px 220px 130px 110px";

const LABEL_BY_STATUS: Record<CoverageStatus, string> = {
  cds_available_current: "CDS available",
  cds_available_stale: "Older CDS",
  cds_found_processing: "Processing",
  latest_found_extract_failed_with_prior_available: "Latest extract failed",
  extract_failed: "Extract failed",
  source_not_automatically_accessible: "Source blocked",
  no_public_cds_found: "No public CDS",
  verified_absent: "Verified absent",
  not_checked: "Not checked",
  out_of_scope: "Out of scope",
};

function StatCell({
  label,
  value,
  note,
  emphasis,
  active,
  onClick,
}: {
  label: string;
  value: number;
  note: string;
  emphasis?: boolean;
  active?: boolean;
  onClick?: () => void;
}) {
  const Tag = onClick ? "button" : "div";
  return (
    <Tag
      onClick={onClick}
      style={{
        textAlign: "left",
        padding: 0,
        background: "transparent",
        border: "none",
        font: "inherit",
        color: "inherit",
        cursor: onClick ? "pointer" : "default",
        opacity: onClick && active === false ? 0.55 : 1,
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
        {value.toLocaleString()}
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

function sameSet<T>(a: Set<T>, b: Set<T>): boolean {
  if (a.size !== b.size) return false;
  for (const v of a) if (!b.has(v)) return false;
  return true;
}
