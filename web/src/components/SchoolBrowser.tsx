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
import { trackDownload, trackEvent, trackSourceOpened } from "@/lib/analytics";
import { formatBadgeLabel, formatCurrency, formatPercent } from "@/lib/format";
import { SchoolGlyph } from "./SchoolGlyph";
import { externalLinkRel } from "@/lib/client-info";

type FilterState = {
  undergradMin: string;
  acceptanceMax: string;
  yieldMin: string;
  netPriceMax: string;
  retentionMin: string;
};

export type ColumnPreset = "overview" | "testing" | "cost" | "all";
export type RowDensity = "compact" | "standard";

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
  { label: "Highest retention", sort: { field: "retention_rate", direction: "desc" } },
  { label: "Highest SAT (75th)", sort: { field: "sat_composite_p75", direction: "desc" } },
  { label: "Highest ACT (75th)", sort: { field: "act_composite_p75", direction: "desc" } },
  { label: "Largest enrollment", sort: { field: "undergrad_enrollment_scorecard", direction: "desc" } },
  { label: "Lowest net price", sort: { field: "avg_net_price", direction: "asc" } },
  { label: "Highest Pell share", sort: { field: "pell_rate", direction: "desc" } },
];

const COLUMN_PRESETS: { id: ColumnPreset; label: string }[] = [
  { id: "overview", label: "Overview" },
  { id: "testing", label: "Testing & Academic" },
  { id: "cost", label: "Cost & Aid" },
  { id: "all", label: "All Columns" },
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

function formatScoreRange(p25: number | null, p75: number | null): string | null {
  if (p25 == null || p75 == null) return null;
  return `${Math.round(p25)}–${Math.round(p75)}`;
}

function formatSubmitTag(rate: number | null): string {
  if (rate == null) return "sub n/a";
  return `${Math.round(rate * 100)}% sub`;
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
    { key: "federal_baseline_available", label: "federal_baseline_available" },
    { key: "federal_source_mode", label: "federal_source_mode" },
    { key: "archive_url", label: "archive_url" },
  ];
  const body = rows.map((row) => columns.map((col) => csvEscape(row[col.key])).join(","));
  const csv = [columns.map((col) => col.label).join(","), ...body].join("\n");
  const blob = new Blob([csv], { type: "text/csv;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = "collegedata-compare.csv";
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

export function SchoolBrowser({
  brandColors,
}: {
  brandColors?: Record<string, string[]>;
}) {
  const [filters, setFilters] = useState<FilterState>(DEFAULT_FILTERS);
  const [sortIndex, setSortIndex] = useState(1);
  const [preset, setPreset] = useState<ColumnPreset>("overview");
  const [density, setDensity] = useState<RowDensity>("compact");
  const [inspectedDocId, setInspectedDocId] = useState<string | null>(null);
  const [page, setPage] = useState(1);
  const [rows, setRows] = useState<BrowserRow[]>([]);
  const [metadata, setMetadata] = useState<BrowserSearchMetadata | null>(null);
  const [loading, setLoading] = useState(true);
  const [exporting, setExporting] = useState(false);
  const [error, setError] = useState(null as string | null);

  const requestFilters = useMemo(() => buildFilters(filters), [filters]);
  const requiredLabels = metadata?.required_fields.map(metricLabel).join(", ") || "none";
  const activeSortField = SORT_OPTIONS[sortIndex]?.sort.field;

  const inspectedRow = useMemo(
    () => rows.find((r) => r.document_id === inspectedDocId) ?? null,
    [rows, inspectedDocId],
  );

  useEffect(() => {
    function onKeyDown(e: KeyboardEvent) {
      if (e.key === "Escape" && inspectedDocId) {
        setInspectedDocId(null);
      }
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [inspectedDocId]);

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

  function selectSortByField(field: BrowserField) {
    const idx = SORT_OPTIONS.findIndex((o) => o.sort.field === field);
    if (idx >= 0) {
      setPage(1);
      setSortIndex(idx);
      trackEvent("browser_sort_changed", {
        sort: SORT_OPTIONS[idx]?.sort.field,
        direction: SORT_OPTIONS[idx]?.sort.direction,
      });
    }
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
      trackDownload({
        surface: "school_browser",
        fileType: "csv",
        item: "browser_export",
        rowCount: response.rows.length,
      });
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

  const isCompact = density === "compact";
  const cellPad = isCompact ? "7px 10px" : "12px 10px";

  const showEnroll = preset === "overview" || preset === "cost" || preset === "all";
  const showRawCounts = preset === "all";
  const showAccept = true;
  const showYield = preset === "overview" || preset === "cost" || preset === "all";
  const showRetention = true;
  const showSatComp = preset === "overview" || preset === "testing" || preset === "all";
  const showSatSplit = preset === "testing";
  const showActComp = preset === "testing" || preset === "all";
  const showNetPrice = preset === "overview" || preset === "cost" || preset === "all";
  const showPell = preset === "cost" || preset === "all";

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
            label="Minimum undergrad enrollment"
            value={filters.undergradMin}
            onChange={(v) => updateFilter("undergradMin", v)}
            suffix="students"
          />
          <FilterInput
            label="Maximum acceptance rate"
            value={filters.acceptanceMax}
            onChange={(v) => updateFilter("acceptanceMax", v)}
            suffix="%"
          />
          <FilterInput
            label="Minimum yield"
            value={filters.yieldMin}
            onChange={(v) => updateFilter("yieldMin", v)}
            suffix="%"
          />
          <FilterInput
            label="Maximum average net price"
            value={filters.netPriceMax}
            onChange={(v) => updateFilter("netPriceMax", v)}
            suffix="$"
          />
          <FilterInput
            label="Minimum retention"
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
          <div style={{ display: "flex", alignItems: "center", gap: 14, flexWrap: "wrap" }}>
            <label style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <span className="meta">Sort</span>
              <select
                value={sortIndex}
                onChange={(e) => {
                  setPage(1);
                  setSortIndex(Number(e.target.value));
                  trackEvent("browser_sort_changed", {
                    sort: SORT_OPTIONS[Number(e.target.value)]?.sort.field,
                    direction: SORT_OPTIONS[Number(e.target.value)]?.sort.direction,
                  });
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

            <div
              role="group"
              aria-label="Column view preset"
              className="cd-segmented"
            >
              {COLUMN_PRESETS.map((p) => (
                <button
                  key={p.id}
                  type="button"
                  className="cd-segmented__btn"
                  data-active={preset === p.id ? "true" : "false"}
                  aria-pressed={preset === p.id}
                  onClick={() => {
                    setPreset(p.id);
                    trackEvent("browser_preset_changed", { preset: p.id });
                  }}
                >
                  {p.label}
                </button>
              ))}
            </div>

            <div
              role="group"
              aria-label="Row density"
              className="cd-segmented browser-density-toggle"
            >
              <button
                type="button"
                className="cd-segmented__btn"
                data-active={density === "compact" ? "true" : "false"}
                aria-pressed={density === "compact"}
                onClick={() => setDensity("compact")}
              >
                Compact
              </button>
              <button
                type="button"
                className="cd-segmented__btn"
                data-active={density === "standard" ? "true" : "false"}
                aria-pressed={density === "standard"}
                onClick={() => setDensity("standard")}
              >
                Standard
              </button>
            </div>
          </div>

          <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
            <button
              type="button"
              className="cd-btn cd-btn--ghost"
              onClick={() => {
                setPage(1);
                setFilters({ undergradMin: "", acceptanceMax: "", yieldMin: "", netPriceMax: "", retentionMin: "" });
                trackEvent("browser_filters_reset");
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
          <MetaStat label="Schools" value={metadata ? metadata.schools_in_scope.toLocaleString() : "..."} />
          <MetaStat label="Match your filters" value={metadata ? metadata.total_rows.toLocaleString() : "..."} />
          <MetaStat label="Have every number" value={metadata ? metadata.schools_with_required_fields.toLocaleString() : "..."} />
          <MetaStat label="Missing a number" value={metadata ? metadata.schools_missing_required_fields.toLocaleString() : "..."} />
        </div>
        <p className="meta" style={{ marginTop: 14, lineHeight: 1.55 }}>
          Latest reports, 2024-25+. Schools missing a number your filters need are counted above. Fields needed: {requiredLabels}.
          {metadata ? ` Filtered out by your criteria: ${metadata.schools_failing_filters.toLocaleString()}.` : ""}
          {" "}
          <Link href="/match">Building a list? Use Match.</Link>
        </p>
      </section>

      {error && (
        <div className="cd-card" style={{ padding: 16, borderColor: "var(--brick)", marginBottom: 18 }}>
          <div className="meta" style={{ color: "var(--brick)", marginBottom: 6 }}>Couldn&apos;t load</div>
          <p style={{ margin: 0, color: "var(--ink-2)", fontSize: 14 }}>Try again in a moment.</p>
        </div>
      )}

      <div className="browser-mobile-results" style={{ opacity: loading ? 0.62 : 1 }}>
        {rows.map((row) => (
          <BrowserResultCard
            key={row.document_id}
            row={row}
            brandColors={brandColors?.[row.school_id]}
            onInspect={() =>
              setInspectedDocId((cur) => (cur === row.document_id ? null : row.document_id))
            }
          />
        ))}
      </div>

      <div
        className="browser-table-wrap"
        tabIndex={0}
        role="region"
        aria-labelledby="browser-table-caption"
        style={{ overflowX: "auto", opacity: loading ? 0.62 : 1 }}
      >
        <table
          className="browser-table"
          data-density={density}
          style={{
            width: "100%",
            borderCollapse: "separate",
            borderSpacing: 0,
            minWidth: preset === "all" ? 1180 : 920,
            fontSize: isCompact ? 13.5 : 14,
          }}
        >
          <caption id="browser-table-caption" className="sr-only">
            Common Data Set school comparison table ({preset} view)
          </caption>
          <thead>
            <tr className="meta">
              <SortableTh
                label="School"
                field="school_name"
                activeField={activeSortField}
                align="left"
                stickyLeft
                onSelect={selectSortByField}
                style={{ padding: "9px 10px 9px 0", minWidth: 230, maxWidth: 280 }}
              />
              <th style={{ padding: "9px 10px", borderBottom: "1px solid var(--rule-strong)" }}>Year</th>
              {showEnroll && (
                <SortableTh
                  label="Enroll"
                  field="undergrad_enrollment_scorecard"
                  activeField={activeSortField}
                  onSelect={selectSortByField}
                />
              )}
              {showRawCounts && (
                <>
                  <th style={{ padding: "9px 10px", textAlign: "right", borderBottom: "1px solid var(--rule-strong)" }}>Applied</th>
                  <th style={{ padding: "9px 10px", textAlign: "right", borderBottom: "1px solid var(--rule-strong)" }}>Admitted</th>
                  <th style={{ padding: "9px 10px", textAlign: "right", borderBottom: "1px solid var(--rule-strong)" }}>First-yrs</th>
                </>
              )}
              {showAccept && (
                <SortableTh
                  label="Accept"
                  field="acceptance_rate"
                  activeField={activeSortField}
                  onSelect={selectSortByField}
                />
              )}
              {showYield && (
                <SortableTh
                  label="Yield"
                  field="yield_rate"
                  activeField={activeSortField}
                  onSelect={selectSortByField}
                />
              )}
              {showRetention && (
                <SortableTh
                  label="Retain"
                  field="retention_rate"
                  activeField={activeSortField}
                  onSelect={selectSortByField}
                />
              )}
              {showSatComp && (
                <SortableTh
                  label="SAT 25–75"
                  field="sat_composite_p75"
                  activeField={activeSortField}
                  onSelect={selectSortByField}
                />
              )}
              {showSatSplit && (
                <>
                  <th style={{ padding: "9px 10px", textAlign: "right", borderBottom: "1px solid var(--rule-strong)" }}>SAT EBRW</th>
                  <th style={{ padding: "9px 10px", textAlign: "right", borderBottom: "1px solid var(--rule-strong)" }}>SAT Math</th>
                </>
              )}
              {showActComp && (
                <SortableTh
                  label="ACT 25–75"
                  field="act_composite_p75"
                  activeField={activeSortField}
                  onSelect={selectSortByField}
                />
              )}
              {showNetPrice && (
                <SortableTh
                  label="Net price"
                  field="avg_net_price"
                  activeField={activeSortField}
                  onSelect={selectSortByField}
                />
              )}
              {showPell && (
                <SortableTh
                  label="Pell"
                  field="pell_rate"
                  activeField={activeSortField}
                  onSelect={selectSortByField}
                />
              )}
              <th style={{ padding: "9px 0 9px 10px", borderBottom: "1px solid var(--rule-strong)" }}>Source</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => {
              const isInspected = inspectedDocId === row.document_id;
              const satRange = formatScoreRange(row.sat_composite_p25, row.sat_composite_p75);
              const actRange = formatScoreRange(row.act_composite_p25, row.act_composite_p75);
              const ebrwRange = formatScoreRange(row.sat_ebrw_p25, row.sat_ebrw_p75);
              const mathRange = formatScoreRange(row.sat_math_p25, row.sat_math_p75);

              return (
                <tr
                  key={row.document_id}
                  className="browser-row"
                  data-inspected={isInspected ? "true" : "false"}
                >
                  <th
                    scope="row"
                    className="browser-row__school"
                    style={{
                      padding: isCompact ? "7px 12px 7px 0" : "12px 12px 12px 0",
                      textAlign: "left",
                      fontWeight: 400,
                    }}
                  >
                    <div
                      style={{
                        display: "flex",
                        alignItems: "baseline",
                        gap: 8,
                        flexWrap: isCompact ? "nowrap" : "wrap",
                      }}
                    >
                      <Link
                        href={`/schools/${row.school_id}`}
                        className="school-name-with-glyph"
                        style={{
                          fontFamily: "var(--serif)",
                          fontSize: isCompact ? 15.5 : 18,
                          lineHeight: 1.2,
                          whiteSpace: isCompact ? "nowrap" : "normal",
                          overflow: "hidden",
                          textOverflow: "ellipsis",
                          maxWidth: isCompact ? 230 : undefined,
                        }}
                        title={row.school_name}
                        onClick={() =>
                          trackEvent("browser_school_opened", {
                            surface: "table",
                            school_id: row.school_id,
                            cds_year: row.canonical_year,
                          })
                        }
                      >
                        <SchoolGlyph size="sm" brandColors={brandColors?.[row.school_id]} />
                        {row.school_name}
                      </Link>
                      {isCompact && row.sub_institutional && (
                        <span
                          className="meta"
                          title={row.sub_institutional}
                          style={{
                            fontSize: 9.5,
                            whiteSpace: "nowrap",
                            overflow: "hidden",
                            textOverflow: "ellipsis",
                            maxWidth: 90,
                          }}
                        >
                          · {row.sub_institutional}
                        </span>
                      )}
                      {isCompact && row.data_quality_flag && (
                        <span
                          className="cd-chip"
                          title={`Quality note: ${row.data_quality_flag.replaceAll("_", " ")}`}
                          style={{ padding: "0 4px", fontSize: 9 }}
                        >
                          !
                        </span>
                      )}
                    </div>
                    {!isCompact && row.sub_institutional && (
                      <div className="meta" style={{ marginTop: 3 }}>{row.sub_institutional}</div>
                    )}
                    {!isCompact && row.data_quality_flag && (
                      <div className="cd-chip" style={{ marginTop: 7 }}>{row.data_quality_flag.replaceAll("_", " ")}</div>
                    )}
                  </th>

                  <td className="nums" style={{ padding: cellPad, color: "var(--ink-2)", whiteSpace: "nowrap" }}>
                    {row.canonical_year}
                  </td>

                  {showEnroll && (
                    <NumberCell
                      value={row.undergrad_enrollment_scorecard}
                      padding={cellPad}
                      sorted={activeSortField === "undergrad_enrollment_scorecard"}
                    />
                  )}

                  {showRawCounts && (
                    <>
                      <NumberCell value={row.applied} padding={cellPad} />
                      <NumberCell value={row.admitted} padding={cellPad} />
                      <NumberCell value={row.enrolled_first_year} padding={cellPad} />
                    </>
                  )}

                  {showAccept && (
                    <td
                      className="nums"
                      data-sorted={activeSortField === "acceptance_rate" ? "true" : undefined}
                      style={{ padding: cellPad, textAlign: "right", whiteSpace: "nowrap" }}
                    >
                      <div>{formatPercent(row.acceptance_rate, 1) || "-"}</div>
                      {!isCompact && row.applied != null && row.admitted != null && (
                        <div className="mono" style={{ fontSize: 10, color: "var(--ink-3)", marginTop: 2 }}>
                          {Math.round(row.admitted).toLocaleString()}/{Math.round(row.applied).toLocaleString()}
                        </div>
                      )}
                    </td>
                  )}

                  {showYield && (
                    <td
                      className="nums"
                      data-sorted={activeSortField === "yield_rate" ? "true" : undefined}
                      style={{ padding: cellPad, textAlign: "right", whiteSpace: "nowrap" }}
                    >
                      {formatPercent(row.yield_rate, 1) || "-"}
                    </td>
                  )}

                  {showRetention && (
                    <td
                      className="nums"
                      data-sorted={activeSortField === "retention_rate" ? "true" : undefined}
                      style={{ padding: cellPad, textAlign: "right", whiteSpace: "nowrap" }}
                    >
                      {formatPercent(row.retention_rate, 0) || "-"}
                    </td>
                  )}

                  {showSatComp && (
                    <td
                      className="nums"
                      data-sorted={activeSortField === "sat_composite_p75" ? "true" : undefined}
                      style={{ padding: cellPad, textAlign: "right", whiteSpace: "nowrap" }}
                    >
                      {satRange ? (
                        <div>
                          <span>{satRange}</span>
                          <span
                            className="mono"
                            style={{
                              marginLeft: 6,
                              fontSize: 10,
                              color:
                                row.sat_submit_rate != null && row.sat_submit_rate < 0.35
                                  ? "var(--ochre)"
                                  : "var(--ink-3)",
                            }}
                            title="Share of enrolled first-years who submitted SAT scores (§C9)"
                          >
                            {formatSubmitTag(row.sat_submit_rate)}
                          </span>
                        </div>
                      ) : (
                        "-"
                      )}
                    </td>
                  )}

                  {showSatSplit && (
                    <>
                      <td className="nums" style={{ padding: cellPad, textAlign: "right", whiteSpace: "nowrap" }}>
                        {ebrwRange || "-"}
                      </td>
                      <td className="nums" style={{ padding: cellPad, textAlign: "right", whiteSpace: "nowrap" }}>
                        {mathRange || "-"}
                      </td>
                    </>
                  )}

                  {showActComp && (
                    <td
                      className="nums"
                      data-sorted={activeSortField === "act_composite_p75" ? "true" : undefined}
                      style={{ padding: cellPad, textAlign: "right", whiteSpace: "nowrap" }}
                    >
                      {actRange ? (
                        <div>
                          <span>{actRange}</span>
                          <span
                            className="mono"
                            style={{
                              marginLeft: 6,
                              fontSize: 10,
                              color:
                                row.act_submit_rate != null && row.act_submit_rate < 0.35
                                  ? "var(--ochre)"
                                  : "var(--ink-3)",
                            }}
                            title="Share of enrolled first-years who submitted ACT scores (§C9)"
                          >
                            {formatSubmitTag(row.act_submit_rate)}
                          </span>
                        </div>
                      ) : (
                        "-"
                      )}
                    </td>
                  )}

                  {showNetPrice && (
                    <td
                      className="nums"
                      data-sorted={activeSortField === "avg_net_price" ? "true" : undefined}
                      style={{ padding: cellPad, textAlign: "right", whiteSpace: "nowrap" }}
                    >
                      {formatCurrency(row.avg_net_price) || "-"}
                    </td>
                  )}

                  {showPell && (
                    <td
                      className="nums"
                      data-sorted={activeSortField === "pell_rate" ? "true" : undefined}
                      style={{ padding: cellPad, textAlign: "right", whiteSpace: "nowrap" }}
                    >
                      {formatPercent(row.pell_rate, 0) || "-"}
                    </td>
                  )}

                  <td style={{ padding: isCompact ? "7px 0 7px 10px" : "12px 0 12px 10px", whiteSpace: "nowrap" }}>
                    <div style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
                      <a
                        href={row.archive_url}
                        target="_blank"
                        rel={externalLinkRel(row.archive_url)}
                        className="cd-chip"
                        data-testid="browser-source-link"
                        onClick={() =>
                          trackSourceOpened({
                            surface: "school_browser_table",
                            schoolId: row.school_id,
                            cdsYear: row.canonical_year,
                            sourceFormat: row.source_format,
                            action: "open_archive",
                          })
                        }
                      >
                        {formatBadgeLabel(row.source_format)}
                      </a>
                      <button
                        type="button"
                        className="cd-chip browser-inspect-btn"
                        aria-label={`Inspect ${row.school_name}`}
                        aria-expanded={isInspected}
                        data-testid="browser-inspect-btn"
                        onClick={() =>
                          setInspectedDocId((cur) =>
                            cur === row.document_id ? null : row.document_id,
                          )
                        }
                        title="Open non-modal inspection drawer"
                      >
                        §
                      </button>
                    </div>
                  </td>
                </tr>
              );
            })}
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
            onClick={() => {
              trackEvent("browser_page_changed", {
                direction: "previous",
                current_page: page,
                total_pages: totalPages,
              });
              setPage((p) => Math.max(1, p - 1));
            }}
          >
            Previous
          </button>
          <button
            type="button"
            className="cd-btn cd-btn--ghost"
            disabled={page >= totalPages || loading}
            onClick={() => {
              trackEvent("browser_page_changed", {
                direction: "next",
                current_page: page,
                total_pages: totalPages,
              });
              setPage((p) => Math.min(totalPages, p + 1));
            }}
          >
            Next
          </button>
        </div>
      </div>

      {inspectedRow && (
        <BrowserInspectionDrawer
          row={inspectedRow}
          brandColors={brandColors?.[inspectedRow.school_id]}
          onClose={() => setInspectedDocId(null)}
        />
      )}

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
        .browser-mobile-results {
          display: none;
        }
        @media (max-width: 560px) {
          .browser-filter-grid,
          .browser-meta-grid {
            grid-template-columns: 1fr !important;
          }
          .browser-table-wrap,
          .browser-density-toggle {
            display: none !important;
          }
          .browser-mobile-results {
            display: grid;
            gap: 12px;
          }
        }
      `}</style>
    </div>
  );
}

function SortableTh({
  label,
  field,
  activeField,
  align = "right",
  stickyLeft = false,
  onSelect,
  style,
}: {
  label: string;
  field: BrowserField;
  activeField?: BrowserField;
  align?: "left" | "right";
  stickyLeft?: boolean;
  onSelect: (field: BrowserField) => void;
  style?: CSSProperties;
}) {
  const isSorted = activeField === field;
  return (
    <th
      scope="col"
      className={stickyLeft ? "browser-th--sticky" : undefined}
      data-sorted={isSorted ? "true" : undefined}
      style={{
        padding: "9px 10px",
        textAlign: align,
        borderBottom: "1px solid var(--rule-strong)",
        whiteSpace: "nowrap",
        ...style,
      }}
    >
      <button
        type="button"
        onClick={() => onSelect(field)}
        className="cd-th-sort"
        style={{
          background: "none",
          border: 0,
          padding: 0,
          font: "inherit",
          letterSpacing: "inherit",
          textTransform: "inherit",
          color: isSorted ? "var(--forest-ink)" : "inherit",
          fontWeight: isSorted ? 600 : 400,
          cursor: "pointer",
          display: "inline-flex",
          alignItems: "center",
          gap: 4,
        }}
      >
        <span>{label}</span>
        {isSorted && <span aria-hidden="true">↓</span>}
      </button>
    </th>
  );
}

function BrowserInspectionDrawer({
  row,
  brandColors,
  onClose,
}: {
  row: BrowserRow;
  brandColors?: string[] | null;
  onClose: () => void;
}) {
  const satRange = formatScoreRange(row.sat_composite_p25, row.sat_composite_p75);
  const actRange = formatScoreRange(row.act_composite_p25, row.act_composite_p75);
  const ebrwRange = formatScoreRange(row.sat_ebrw_p25, row.sat_ebrw_p75);
  const mathRange = formatScoreRange(row.sat_math_p25, row.sat_math_p75);

  return (
    <aside
      aria-label={`Inspect ${row.school_name}`}
      data-testid="browser-inspection-drawer"
      className="cd-browser-drawer cd-card"
    >
      <div className="cd-browser-drawer__head">
        <div style={{ minWidth: 0 }}>
          <div className="meta" style={{ marginBottom: 4 }}>
            § Quick inspect · {row.canonical_year} CDS
          </div>
          <Link
            href={`/schools/${row.school_id}`}
            className="school-name-with-glyph serif"
            style={{ fontSize: 22, lineHeight: 1.15, textDecoration: "none" }}
          >
            <SchoolGlyph brandColors={brandColors} />
            <span>{row.school_name}</span>
          </Link>
          {row.sub_institutional && (
            <div className="meta" style={{ marginTop: 4 }}>{row.sub_institutional}</div>
          )}
        </div>
        <button
          type="button"
          className="cd-chip"
          onClick={onClose}
          aria-label="Close inspection drawer"
          style={{ cursor: "pointer" }}
        >
          ESC ×
        </button>
      </div>

      <div className="cd-browser-drawer__section rule-2">
        <div className="meta" style={{ marginBottom: 8 }}>§C1 · First-year admissions funnel</div>
        <div className="cd-browser-drawer__grid">
          <DrawerStat label="Accept rate" value={formatPercent(row.acceptance_rate, 1) || "—"} />
          <DrawerStat label="Yield" value={formatPercent(row.yield_rate, 1) || "—"} />
          <DrawerStat label="Applied" value={row.applied != null ? Math.round(row.applied).toLocaleString() : "—"} />
          <DrawerStat label="Admitted" value={row.admitted != null ? Math.round(row.admitted).toLocaleString() : "—"} />
          <DrawerStat label="Enrolled 1st-yr" value={row.enrolled_first_year != null ? Math.round(row.enrolled_first_year).toLocaleString() : "—"} />
          <DrawerStat label="Retention" value={formatPercent(row.retention_rate, 0) || "—"} />
        </div>
      </div>

      <div className="cd-browser-drawer__section rule-d">
        <div className="meta" style={{ marginBottom: 8 }}>§C9 · Enrolled score bands (25th–75th)</div>
        <div className="cd-browser-drawer__grid">
          <DrawerStat
            label="SAT composite"
            value={satRange || "—"}
            sub={
              row.sat_composite_p50 != null
                ? `${formatSubmitTag(row.sat_submit_rate)} · med ${Math.round(row.sat_composite_p50)}`
                : formatSubmitTag(row.sat_submit_rate)
            }
          />
          <DrawerStat
            label="ACT composite"
            value={actRange || "—"}
            sub={
              row.act_composite_p50 != null
                ? `${formatSubmitTag(row.act_submit_rate)} · med ${Math.round(row.act_composite_p50)}`
                : formatSubmitTag(row.act_submit_rate)
            }
          />
          <DrawerStat label="SAT EBRW" value={ebrwRange || "—"} />
          <DrawerStat label="SAT Math" value={mathRange || "—"} />
        </div>
      </div>

      <div className="cd-browser-drawer__section rule-d">
        <div className="meta" style={{ marginBottom: 8 }}>§ Federal context (Scorecard / IPEDS)</div>
        <div className="cd-browser-drawer__grid">
          <DrawerStat label="Avg net price" value={formatCurrency(row.avg_net_price) || "—"} />
          <DrawerStat label="Pell share" value={formatPercent(row.pell_rate, 0) || "—"} />
          <DrawerStat
            label="Undergrad enroll"
            value={
              row.undergrad_enrollment_scorecard != null
                ? Math.round(row.undergrad_enrollment_scorecard).toLocaleString()
                : "—"
            }
          />
        </div>
      </div>

      <div className="cd-browser-drawer__actions rule-2">
        <Link href={`/schools/${row.school_id}`} className="cd-btn">
          School hub →
        </Link>
        <Link
          href={`/schools/${row.school_id}/${row.canonical_year}`}
          className="cd-btn cd-btn--ghost"
        >
          {row.canonical_year} report →
        </Link>
        <a
          href={row.archive_url}
          target="_blank"
          rel={externalLinkRel(row.archive_url)}
          className="cd-chip"
          style={{ marginLeft: "auto" }}
        >
          {formatBadgeLabel(row.source_format)} source ↗
        </a>
      </div>
    </aside>
  );
}

function DrawerStat({
  label,
  value,
  sub,
}: {
  label: string;
  value: string;
  sub?: string;
}) {
  return (
    <div>
      <div className="meta" style={{ fontSize: 10, marginBottom: 2 }}>{label}</div>
      <div className="nums" style={{ fontFamily: "var(--mono)", fontSize: 15, fontWeight: 500 }}>
        {value}
      </div>
      {sub && (
        <div className="mono" style={{ fontSize: 10, color: "var(--ink-3)", marginTop: 2 }}>
          {sub.toUpperCase()}
        </div>
      )}
    </div>
  );
}

function BrowserResultCard({
  row,
  brandColors,
  onInspect,
}: {
  row: BrowserRow;
  brandColors?: string[] | null;
  onInspect: () => void;
}) {
  const satRange = formatScoreRange(row.sat_composite_p25, row.sat_composite_p75);
  return (
    <article className="cd-card" style={{ padding: 14 }}>
      <div style={{ display: "flex", gap: 10, alignItems: "flex-start", justifyContent: "space-between" }}>
        <div style={{ minWidth: 0 }}>
          <Link
            href={`/schools/${row.school_id}`}
            className="school-name-with-glyph"
            style={{ fontFamily: "var(--serif)", fontSize: 19, lineHeight: 1.15 }}
            onClick={() =>
              trackEvent("browser_school_opened", {
                surface: "card",
                school_id: row.school_id,
                cds_year: row.canonical_year,
              })
            }
          >
            <SchoolGlyph brandColors={brandColors} />
            {row.school_name}
          </Link>
          {row.sub_institutional && (
            <div className="meta" style={{ marginTop: 4 }}>{row.sub_institutional}</div>
          )}
        </div>
        <span className="mono" style={{ flexShrink: 0, color: "var(--ink-3)", fontSize: 12 }}>
          {row.canonical_year}
        </span>
      </div>
      {row.data_quality_flag && (
        <div className="cd-chip" style={{ marginTop: 8 }}>{row.data_quality_flag.replaceAll("_", " ")}</div>
      )}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(2, minmax(0, 1fr))",
          gap: "10px 12px",
          marginTop: 14,
        }}
      >
        <CardMetric label="Enrollment" value={row.undergrad_enrollment_scorecard == null ? "-" : Math.round(row.undergrad_enrollment_scorecard).toLocaleString()} />
        <CardMetric label="Accept" value={formatPercent(row.acceptance_rate, 1) || "-"} />
        <CardMetric label="Yield" value={formatPercent(row.yield_rate, 1) || "-"} />
        <CardMetric label="Retention" value={formatPercent(row.retention_rate, 0) || "-"} />
        <CardMetric label="SAT 25–75" value={satRange || "-"} />
        <CardMetric label="Net price" value={formatCurrency(row.avg_net_price) || "-"} />
      </div>
      <div className="rule" style={{ marginTop: 12, paddingTop: 10, display: "flex", gap: 8, alignItems: "center" }}>
        <a
          href={row.archive_url}
          target="_blank"
          rel={externalLinkRel(row.archive_url)}
          className="cd-chip"
          data-testid="browser-source-link"
          onClick={() =>
            trackSourceOpened({
              surface: "school_browser_card",
              schoolId: row.school_id,
              cdsYear: row.canonical_year,
              sourceFormat: row.source_format,
              action: "open_archive",
            })
          }
        >
          {formatBadgeLabel(row.source_format)} source
        </a>
        <button
          type="button"
          className="cd-chip"
          onClick={onInspect}
          style={{ cursor: "pointer" }}
        >
          § Inspect
        </button>
      </div>
    </article>
  );
}

function CardMetric({ label, value }: { label: string; value: string }) {
  return (
    <div style={{ borderTop: "1px solid var(--rule)", paddingTop: 7 }}>
      <div className="meta" style={{ marginBottom: 4 }}>{label}</div>
      <div className="nums" style={{ fontFamily: "var(--serif)", fontSize: 20, lineHeight: 1 }}>{value}</div>
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

function NumberCell({
  value,
  padding = "12px 10px",
  sorted = false,
}: {
  value: number | null;
  padding?: string;
  sorted?: boolean;
}) {
  return (
    <td
      className="nums"
      data-sorted={sorted ? "true" : undefined}
      style={{ padding, textAlign: "right", whiteSpace: "nowrap" }}
    >
      {value == null ? "-" : Math.round(value).toLocaleString()}
    </td>
  );
}
