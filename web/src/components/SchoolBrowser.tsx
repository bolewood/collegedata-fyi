"use client";

import { useEffect, useMemo, useState } from "react";
import type { CSSProperties } from "react";
import Link from "next/link";
import {
  searchBrowserRows,
  type BrowserField,
  type BrowserFilter,
  type BrowserRow,
  type BrowserSearchMetadata,
  type BrowserSort,
} from "@/lib/browser-search";
import { formatBadgeLabel, formatCurrency, formatPercent } from "@/lib/format";

type FilterState = {
  undergradMin: string;
  acceptanceMax: string;
  yieldMin: string;
  netPriceMax: string;
  retentionMin: string;
};

const PAGE_SIZE = 50;

const DEFAULT_FILTERS: FilterState = {
  undergradMin: "3000",
  acceptanceMax: "10",
  yieldMin: "",
  netPriceMax: "",
  retentionMin: "",
};

const SORT_OPTIONS: { label: string; sort: BrowserSort }[] = [
  { label: "School name", sort: { field: "school_name", direction: "asc" } },
  { label: "Lowest acceptance rate", sort: { field: "acceptance_rate", direction: "asc" } },
  { label: "Highest yield", sort: { field: "yield_rate", direction: "desc" } },
  { label: "Largest enrollment", sort: { field: "undergrad_enrollment_scorecard", direction: "desc" } },
  { label: "Lowest net price", sort: { field: "avg_net_price", direction: "asc" } },
];

function percentInputToFraction(value: string): number | null {
  if (value.trim() === "") return null;
  const n = Number(value);
  return Number.isFinite(n) ? n / 100 : null;
}

function numericInput(value: string): number | null {
  if (value.trim() === "") return null;
  const n = Number(value);
  return Number.isFinite(n) ? n : null;
}

function buildFilters(filters: FilterState): BrowserFilter[] {
  const out: BrowserFilter[] = [];
  const undergradMin = numericInput(filters.undergradMin);
  const acceptanceMax = percentInputToFraction(filters.acceptanceMax);
  const yieldMin = percentInputToFraction(filters.yieldMin);
  const netPriceMax = numericInput(filters.netPriceMax);
  const retentionMin = percentInputToFraction(filters.retentionMin);

  if (undergradMin != null) {
    out.push({ field: "undergrad_enrollment_scorecard", op: ">=", value: undergradMin });
  }
  if (acceptanceMax != null) {
    out.push({ field: "acceptance_rate", op: "<=", value: acceptanceMax });
  }
  if (yieldMin != null) {
    out.push({ field: "yield_rate", op: ">=", value: yieldMin });
  }
  if (netPriceMax != null) {
    out.push({ field: "avg_net_price", op: "<=", value: netPriceMax });
  }
  if (retentionMin != null) {
    out.push({ field: "retention_rate", op: ">=", value: retentionMin });
  }
  return out;
}

function inputStyle(width: string | number = "100%"): CSSProperties {
  return {
    width,
    border: "1px solid var(--rule-strong)",
    borderRadius: 2,
    background: "#faf6ec",
    color: "var(--ink)",
    padding: "9px 10px",
    fontSize: 14,
  };
}

function metricLabel(field: string): string {
  switch (field) {
    case "undergrad_enrollment_scorecard":
      return "undergrad enrollment";
    case "acceptance_rate":
      return "acceptance rate";
    case "yield_rate":
      return "yield";
    case "avg_net_price":
      return "net price";
    case "retention_rate":
      return "retention";
    default:
      return field.replaceAll("_", " ");
  }
}

function csvEscape(value: unknown): string {
  if (value == null) return "";
  const text = String(value);
  return /[",\n]/.test(text) ? `"${text.replaceAll('"', '""')}"` : text;
}

function downloadCsv(rows: BrowserRow[]) {
  const columns: { key: keyof BrowserRow; label: string }[] = [
    { key: "school_name", label: "school_name" },
    { key: "canonical_year", label: "canonical_year" },
    { key: "sub_institutional", label: "sub_institutional" },
    { key: "undergrad_enrollment_scorecard", label: "undergrad_enrollment_scorecard" },
    { key: "applied", label: "applied" },
    { key: "admitted", label: "admitted" },
    { key: "enrolled_first_year", label: "enrolled_first_year" },
    { key: "acceptance_rate", label: "acceptance_rate_fraction" },
    { key: "yield_rate", label: "yield_rate_fraction" },
    { key: "retention_rate", label: "retention_rate_fraction" },
    { key: "avg_net_price", label: "avg_net_price" },
    { key: "pell_rate", label: "pell_rate_fraction" },
    { key: "sat_submit_rate", label: "sat_submit_rate_fraction" },
    { key: "act_submit_rate", label: "act_submit_rate_fraction" },
    { key: "sat_composite_p25", label: "sat_composite_p25" },
    { key: "sat_composite_p50", label: "sat_composite_p50" },
    { key: "sat_composite_p75", label: "sat_composite_p75" },
    { key: "sat_ebrw_p25", label: "sat_ebrw_p25" },
    { key: "sat_ebrw_p50", label: "sat_ebrw_p50" },
    { key: "sat_ebrw_p75", label: "sat_ebrw_p75" },
    { key: "sat_math_p25", label: "sat_math_p25" },
    { key: "sat_math_p50", label: "sat_math_p50" },
    { key: "sat_math_p75", label: "sat_math_p75" },
    { key: "act_composite_p25", label: "act_composite_p25" },
    { key: "act_composite_p50", label: "act_composite_p50" },
    { key: "act_composite_p75", label: "act_composite_p75" },
    { key: "source_format", label: "source_format" },
    { key: "data_quality_flag", label: "data_quality_flag" },
    { key: "archive_url", label: "archive_url" },
  ];
  const body = rows.map((row) => columns.map((col) => csvEscape(row[col.key])).join(","));
  const csv = [columns.map((col) => col.label).join(","), ...body].join("\n");
  const blob = new Blob([csv], { type: "text/csv;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = "collegedata-browser-export.csv";
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

export function SchoolBrowser() {
  const [filters, setFilters] = useState<FilterState>(DEFAULT_FILTERS);
  const [sortIndex, setSortIndex] = useState(1);
  const [page, setPage] = useState(1);
  const [rows, setRows] = useState<BrowserRow[]>([]);
  const [metadata, setMetadata] = useState<BrowserSearchMetadata | null>(null);
  const [loading, setLoading] = useState(true);
  const [exporting, setExporting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const requestFilters = useMemo(() => buildFilters(filters), [filters]);
  const requiredLabels = metadata?.required_fields.map(metricLabel).join(", ") || "none";

  useEffect(() => {
    const controller = new AbortController();
    const timer = window.setTimeout(async () => {
      setLoading(true);
      setError(null);
      try {
        const response = await searchBrowserRows({
          mode: "latest_per_school",
          variant_scope: "primary_only",
          min_year_start: 2024,
          filters: requestFilters,
          sort: SORT_OPTIONS[sortIndex].sort,
          page,
          page_size: PAGE_SIZE,
        });
        if (!controller.signal.aborted) {
          setRows(response.rows);
          setMetadata(response.metadata);
        }
      } catch (e) {
        if (!controller.signal.aborted) {
          setError((e as Error).message);
          setRows([]);
          setMetadata(null);
        }
      } finally {
        if (!controller.signal.aborted) setLoading(false);
      }
    }, 180);

    return () => {
      controller.abort();
      window.clearTimeout(timer);
    };
  }, [page, requestFilters, sortIndex]);

  function updateFilter(key: keyof FilterState, value: string) {
    setPage(1);
    setFilters((current) => ({ ...current, [key]: value }));
  }

  async function handleExport() {
    setExporting(true);
    setError(null);
    try {
      const response = await searchBrowserRows({
        mode: "latest_per_school",
        variant_scope: "primary_only",
        min_year_start: 2024,
        filters: requestFilters,
        sort: SORT_OPTIONS[sortIndex].sort,
        page: 1,
        page_size: 500,
      });
      downloadCsv(response.rows);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setExporting(false);
    }
  }

  const totalRows = metadata?.total_rows ?? 0;
  const totalPages = Math.max(1, Math.ceil(totalRows / PAGE_SIZE));
  const visibleStart = totalRows === 0 ? 0 : (page - 1) * PAGE_SIZE + 1;
  const visibleEnd = Math.min(page * PAGE_SIZE, totalRows);

  return (
    <div>
      <section className="cd-card" style={{ padding: 18, marginBottom: 22 }}>
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(5, minmax(130px, 1fr))",
            gap: 12,
          }}
          className="browser-filter-grid"
        >
          <FilterInput
            label="Enrollment at least"
            value={filters.undergradMin}
            onChange={(v) => updateFilter("undergradMin", v)}
            suffix="students"
          />
          <FilterInput
            label="Acceptance at most"
            value={filters.acceptanceMax}
            onChange={(v) => updateFilter("acceptanceMax", v)}
            suffix="%"
          />
          <FilterInput
            label="Yield at least"
            value={filters.yieldMin}
            onChange={(v) => updateFilter("yieldMin", v)}
            suffix="%"
          />
          <FilterInput
            label="Net price at most"
            value={filters.netPriceMax}
            onChange={(v) => updateFilter("netPriceMax", v)}
            suffix="$"
          />
          <FilterInput
            label="Retention at least"
            value={filters.retentionMin}
            onChange={(v) => updateFilter("retentionMin", v)}
            suffix="%"
          />
        </div>

        <div
          className="rule"
          style={{
            marginTop: 16,
            paddingTop: 14,
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            gap: 12,
            flexWrap: "wrap",
          }}
        >
          <label style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <span className="meta">Sort</span>
            <select
              value={sortIndex}
              onChange={(e) => {
                setPage(1);
                setSortIndex(Number(e.target.value));
              }}
              style={inputStyle(220)}
            >
              {SORT_OPTIONS.map((option, index) => (
                <option key={option.label} value={index}>
                  {option.label}
                </option>
              ))}
            </select>
          </label>
          <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
            <button
              type="button"
              className="cd-btn cd-btn--ghost"
              onClick={() => {
                setPage(1);
                setFilters({ undergradMin: "", acceptanceMax: "", yieldMin: "", netPriceMax: "", retentionMin: "" });
              }}
            >
              Reset
            </button>
            <button type="button" className="cd-btn" onClick={handleExport} disabled={exporting || loading}>
              {exporting ? "Preparing CSV" : "Export CSV"}
            </button>
          </div>
        </div>
      </section>

      <section className="rule-2" style={{ paddingTop: 18, marginBottom: 20 }}>
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(4, 1fr)",
            gap: 18,
          }}
          className="browser-meta-grid"
        >
          <MetaStat label="Schools in scope" value={metadata ? metadata.schools_in_scope.toLocaleString() : "..."} />
          <MetaStat label="Matching filters" value={metadata ? metadata.total_rows.toLocaleString() : "..."} />
          <MetaStat label="With required fields" value={metadata ? metadata.schools_with_required_fields.toLocaleString() : "..."} />
          <MetaStat label="Missing fields" value={metadata ? metadata.schools_missing_required_fields.toLocaleString() : "..."} />
        </div>
        <p className="meta" style={{ marginTop: 14 }}>
          Latest primary school-year rows, 2024-25+. Required for answerability: {requiredLabels}.
          {metadata ? ` Failed active filters: ${metadata.schools_failing_filters.toLocaleString()}.` : ""}
        </p>
      </section>

      {error && (
        <div className="cd-card" style={{ padding: 16, borderColor: "var(--brick)", marginBottom: 18 }}>
          <div className="meta" style={{ color: "var(--brick)", marginBottom: 6 }}>Browser query failed</div>
          <p style={{ margin: 0, color: "var(--ink-2)", fontSize: 14 }}>{error}</p>
        </div>
      )}

      <div style={{ overflowX: "auto", opacity: loading ? 0.62 : 1 }}>
        <table style={{ width: "100%", borderCollapse: "collapse", minWidth: 940, fontSize: 14 }}>
          <thead>
            <tr className="meta" style={{ textAlign: "left", borderBottom: "1px solid var(--rule-strong)" }}>
              <th style={{ padding: "9px 10px 9px 0", width: 240 }}>School</th>
              <th style={{ padding: "9px 10px" }}>Year</th>
              <th style={{ padding: "9px 10px", textAlign: "right" }}>Enroll</th>
              <th style={{ padding: "9px 10px", textAlign: "right" }}>Applied</th>
              <th style={{ padding: "9px 10px", textAlign: "right" }}>Admitted</th>
              <th style={{ padding: "9px 10px", textAlign: "right" }}>First-years</th>
              <th style={{ padding: "9px 10px", textAlign: "right" }}>Accept</th>
              <th style={{ padding: "9px 10px", textAlign: "right" }}>Yield</th>
              <th style={{ padding: "9px 10px", textAlign: "right" }}>Net price</th>
              <th style={{ padding: "9px 0 9px 10px" }}>Source</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.document_id} className="rule">
                <td style={{ padding: "12px 10px 12px 0" }}>
                  <Link href={`/schools/${row.school_id}`} style={{ fontFamily: "var(--serif)", fontSize: 18 }}>
                    {row.school_name}
                  </Link>
                  {row.sub_institutional && (
                    <div className="meta" style={{ marginTop: 3 }}>{row.sub_institutional}</div>
                  )}
                  {row.data_quality_flag && (
                    <div className="cd-chip" style={{ marginTop: 7 }}>{row.data_quality_flag.replaceAll("_", " ")}</div>
                  )}
                </td>
                <td className="nums" style={{ padding: "12px 10px", color: "var(--ink-2)" }}>{row.canonical_year}</td>
                <NumberCell value={row.undergrad_enrollment_scorecard} />
                <NumberCell value={row.applied} />
                <NumberCell value={row.admitted} />
                <NumberCell value={row.enrolled_first_year} />
                <td className="nums" style={{ padding: "12px 10px", textAlign: "right" }}>
                  {formatPercent(row.acceptance_rate, 1) || "-"}
                </td>
                <td className="nums" style={{ padding: "12px 10px", textAlign: "right" }}>
                  {formatPercent(row.yield_rate, 1) || "-"}
                </td>
                <td className="nums" style={{ padding: "12px 10px", textAlign: "right" }}>
                  {formatCurrency(row.avg_net_price) || "-"}
                </td>
                <td style={{ padding: "12px 0 12px 10px" }}>
                  <a href={row.archive_url} target="_blank" rel="noopener noreferrer" className="cd-chip">
                    {formatBadgeLabel(row.source_format)}
                  </a>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {!loading && rows.length === 0 && !error && (
        <p style={{ textAlign: "center", color: "var(--ink-3)", padding: "40px 0" }}>
          No schools match the current filters.
        </p>
      )}

      <div
        className="rule"
        style={{
          marginTop: 18,
          paddingTop: 14,
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          gap: 12,
          flexWrap: "wrap",
        }}
      >
        <p className="meta" style={{ margin: 0 }}>
          Showing {visibleStart.toLocaleString()}-{visibleEnd.toLocaleString()} of {totalRows.toLocaleString()}
        </p>
        <div style={{ display: "flex", gap: 8 }}>
          <button
            type="button"
            className="cd-btn cd-btn--ghost"
            disabled={page <= 1 || loading}
            onClick={() => setPage((p) => Math.max(1, p - 1))}
          >
            Previous
          </button>
          <button
            type="button"
            className="cd-btn cd-btn--ghost"
            disabled={page >= totalPages || loading}
            onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
          >
            Next
          </button>
        </div>
      </div>

      <style>{`
        .cd-theme button:disabled {
          cursor: not-allowed;
          opacity: 0.45;
        }
        @media (max-width: 900px) {
          .browser-filter-grid,
          .browser-meta-grid {
            grid-template-columns: repeat(2, minmax(0, 1fr)) !important;
          }
        }
        @media (max-width: 560px) {
          .browser-filter-grid,
          .browser-meta-grid {
            grid-template-columns: 1fr !important;
          }
        }
      `}</style>
    </div>
  );
}

function FilterInput({
  label,
  value,
  onChange,
  suffix,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  suffix: string;
}) {
  return (
    <label style={{ display: "block" }}>
      <span className="meta" style={{ display: "block", marginBottom: 6 }}>{label}</span>
      <span style={{ display: "flex", alignItems: "center", gap: 6 }}>
        {suffix === "$" && <span className="mono" style={{ color: "var(--ink-3)" }}>$</span>}
        <input
          inputMode="decimal"
          value={value}
          onChange={(e) => onChange(e.target.value)}
          style={{ ...inputStyle(), flex: 1, minWidth: 0 }}
        />
        {suffix !== "$" && <span className="mono" style={{ color: "var(--ink-3)", minWidth: 18 }}>{suffix}</span>}
      </span>
    </label>
  );
}

function MetaStat({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <div className="meta" style={{ marginBottom: 4 }}>{label}</div>
      <div className="stat-num" style={{ fontFamily: "var(--serif)", fontSize: 30, lineHeight: 1 }}>
        {value}
      </div>
    </div>
  );
}

function NumberCell({ value }: { value: number | null }) {
  return (
    <td className="nums" style={{ padding: "12px 10px", textAlign: "right" }}>
      {value == null ? "-" : Math.round(value).toLocaleString()}
    </td>
  );
}
