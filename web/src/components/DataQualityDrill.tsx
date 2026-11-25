"use client";

// PRD 040 "click a cell to list its reports". A count in Tables A, B, B2 and C is a button that opens a list of the
// reports it counts, under its table, with a link to each school's page for that year. The reports file is fetched on the
// first click (a static route, not part of the page's bundle) and kept for the rest of the visit.
// Keyboard: the button opens the list and moves focus into it; Escape or Close closes it and puts focus back on the button.

import Link from "next/link";
import { createContext, useCallback, useContext, useEffect, useReducer, useRef, type ReactNode } from "react";
import { cellKey, drillReducer, initialDrill, isOpen, type DrillState, type Load } from "@/lib/data-quality-drill";
import {
  cellLabel,
  cellRows,
  cellTitle,
  rowDetail,
  schoolHref,
  validateReports,
  type CellRef,
  type CellTable,
  type ReportsFile,
} from "@/lib/data-quality-reports";
import { formatLabel } from "@/lib/format-labels";

const reportsCache = new Map<string, Promise<ReportsFile>>();
const loadedReports = new Map<string, ReportsFile>();

/** Fetch and check the reports file once per URL; a failed fetch is not cached, so Retry fetches again. */
export function loadReports(url: string, fetcher: typeof fetch = fetch): Promise<ReportsFile> {
  let pending = reportsCache.get(url);
  if (!pending) {
    pending = fetcher(url).then(async (res) => {
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const reports = validateReports(await res.json(), url);
      loadedReports.set(url, reports);
      return reports;
    });
    reportsCache.set(url, pending);
    pending.catch(() => reportsCache.delete(url));
  }
  return pending;
}

/** The file if this visit has already loaded it, so a later click shows its list at once. */
export function cachedReports(url: string): ReportsFile | null {
  return loadedReports.get(url) ?? null;
}

type Drill = {
  state: DrillState;
  toggle: (cell: CellRef, year: string, count: number, trigger: HTMLElement) => void;
  close: () => void;
  retry: () => void;
};

const DrillContext = createContext<Drill | null>(null);

/**
 * Wrap the tables. With no `reportsUrl` (the page isn't launched, or this snapshot has no reports file) counts stay plain
 * text: the server decides, never the browser's clock.
 */
export function DrillProvider({ reportsUrl, year, children }: { reportsUrl: string | null; year: string; children: ReactNode }) {
  const [state, dispatch] = useReducer(drillReducer, initialDrill);
  const trigger = useRef<HTMLElement | null>(null);

  // Fetch when the list is waiting for the file; a response for an older request is ignored by the reducer.
  useEffect(() => {
    if (!reportsUrl || !state.open || state.load.status !== "loading") return;
    const request = state.request;
    loadReports(reportsUrl).then(
      (reports) => dispatch({ type: "loaded", request, reports }),
      (error: Error) => dispatch({ type: "failed", request, message: error.message }),
    );
  }, [reportsUrl, state.open, state.load.status, state.request]);

  // After a close by the user, focus goes back to the count that opened the list.
  const returns = useRef(state.focusReturns);
  useEffect(() => {
    if (state.focusReturns !== returns.current) {
      returns.current = state.focusReturns;
      if (trigger.current?.isConnected) trigger.current.focus();
    }
  }, [state.focusReturns]);

  useEffect(() => dispatch({ type: "year", year }), [year]);

  useEffect(() => {
    if (!state.open) return;
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") dispatch({ type: "escape" });
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [state.open]);

  const toggle = useCallback(
    (cell: CellRef, forYear: string, count: number, button: HTMLElement) => {
      trigger.current = button;
      dispatch({ type: "toggle", cell, year: forYear, count, cached: reportsUrl ? cachedReports(reportsUrl) : null });
    },
    [reportsUrl],
  );

  if (!reportsUrl) return <>{children}</>;
  return (
    <DrillContext.Provider value={{ state, toggle, close: () => dispatch({ type: "close" }), retry: () => dispatch({ type: "retry" }) }}>
      {children}
    </DrillContext.Provider>
  );
}

/** A count in a table: a button that lists its reports, or plain text when there is nothing to list (0) or there is no list to open. */
export function Count({ cell, year, value, text }: { cell: CellRef; year: string; value: number; text: string }) {
  const drill = useContext(DrillContext);
  if (!drill || value === 0) return <>{text}</>;
  const open = isOpen(drill.state, cell, year);
  return (
    <button
      type="button"
      className="dq-count"
      aria-expanded={open}
      aria-controls={open ? panelId(cell.table) : undefined}
      aria-label={cellLabel(cell, year, value)}
      onClick={(event) => drill.toggle(cell, year, value, event.currentTarget)}
    >
      {text}
    </button>
  );
}

const panelId = (table: CellTable) => `dq-drill-${table}`;

/** The open list for one table, rendered under that table (nothing when another table's cell is open). */
export function DrillPanel({ table, year }: { table: CellTable; year: string }) {
  const drill = useContext(DrillContext);
  const ref = useRef<HTMLElement>(null);
  const open = drill?.state.open;
  const shown = open && open.cell.table === table && open.year === year ? open : null;
  const key = shown ? cellKey(shown.cell, shown.year) : "";
  useEffect(() => {
    if (key) ref.current?.focus();
  }, [key]);
  if (!drill || !shown) return null;
  return (
    <DrillPanelView
      ref={ref}
      cell={shown.cell}
      year={shown.year}
      count={shown.count}
      load={drill.state.load}
      onClose={drill.close}
      onRetry={drill.retry}
    />
  );
}

/** The list itself, free of state so it can be rendered and tested in every state. */
export function DrillPanelView({
  cell,
  year,
  count,
  load,
  onClose,
  onRetry,
  ref,
}: {
  cell: CellRef;
  year: string;
  count: number;
  load: Load;
  onClose: () => void;
  onRetry: () => void;
  ref?: React.Ref<HTMLElement>;
}) {
  const headingId = `${panelId(cell.table)}-heading`;
  const rows = load.status === "ready" ? cellRows(load.reports, year, cell) : [];
  const values = rows.reduce((total, r) => total + r.weight, 0);
  // Reports of one school and year more than once (two documents): told apart in the list.
  const perSchool = new Map<string, number>();
  for (const { row } of rows) if (row.school) perSchool.set(row.school, (perSchool.get(row.school) ?? 0) + 1);
  const seen = new Map<string, number>();
  return (
    <section ref={ref} id={panelId(cell.table)} className="dq-drill cd-card" role="region" aria-labelledby={headingId} tabIndex={-1}>
      <div className="dq-drill-head">
        <h3 id={headingId} className="dq-drill-title">
          {cellTitle(cell, year, count)}
        </h3>
        <button type="button" className="cd-btn cd-btn--ghost dq-drill-close" onClick={onClose}>
          Close
        </button>
      </div>
      {/* The live region is always here, so a change from "Loading" to the count is announced. */}
      <div role="status" className="dq-drill-note">
        {load.status === "loading" && "Loading the list…"}
        {load.status === "ready" &&
          `${rows.length.toLocaleString("en-US")} ${rows.length === 1 ? "report" : "reports"}${
            values !== rows.length ? `, ${values.toLocaleString("en-US")} values (a report can hold up to three)` : ""
          }. Press Escape to close.`}
      </div>
      {load.status === "error" && (
        <p role="alert" className="dq-drill-note">
          We couldn’t load the list ({load.message}).{" "}
          <button type="button" className="dq-drill-link" onClick={onRetry}>
            Try again
          </button>
        </p>
      )}
      {load.status === "ready" && (
        <ul className="dq-drill-list" tabIndex={0} aria-label={`Reports in this list: ${cellTitle(cell, year, count)}`}>
          {rows.map(({ row, weight }) => {
            const name = row.school ? load.reports.schools[row.school] ?? row.school : null;
            const linked = row.school && !row.nopage;
            const many = row.school ? perSchool.get(row.school) ?? 0 : 0;
            const nth = row.school ? (seen.set(row.school, (seen.get(row.school) ?? 0) + 1), seen.get(row.school)!) : 0;
            const meta = [
              formatLabel(row.format),
              rowDetail(row, cell),
              weight > 1 ? `${weight} values` : null,
              many > 1 ? `document ${nth} of ${many}` : null,
              row.school ? null : `document ${row.id}`,
              row.school && row.nopage ? "no school page for this year" : null,
            ]
              .filter(Boolean)
              .join(", ");
            return (
              <li key={row.id}>
                {linked ? <Link href={schoolHref(row.school!, year)}>{name}</Link> : <span>{name ?? "School not recorded in this run"}</span>}{" "}
                <span className="dq-drill-meta" title={many > 1 ? `document ${row.id}` : undefined}>{meta}</span>
              </li>
            );
          })}
        </ul>
      )}
    </section>
  );
}
