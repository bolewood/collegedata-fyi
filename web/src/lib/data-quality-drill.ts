// The state of the "list the reports behind this count" panel, as a pure reducer so every transition is unit-tested without
// a browser: opening, closing, toggling the same cell, switching to another cell, a year change, a retry, a cached file, and
// a late response for a list that has since been closed or replaced.

import type { CellRef, ReportsFile } from "./data-quality-reports";

export type Load = { status: "loading" } | { status: "error"; message: string } | { status: "ready"; reports: ReportsFile };
export type Open = { cell: CellRef; year: string; count: number };

export type DrillState = {
  open: Open | null;
  load: Load;
  /** Identifies the fetch the page is waiting for, so a late response for an older request is ignored. */
  request: number;
  /** Counts user closes (Close, Escape, toggling the open cell): the page returns focus to the count each time it grows. */
  focusReturns: number;
};

export type DrillAction =
  | { type: "toggle"; cell: CellRef; year: string; count: number; cached: ReportsFile | null }
  | { type: "loaded"; request: number; reports: ReportsFile }
  | { type: "failed"; request: number; message: string }
  | { type: "retry" }
  | { type: "close" }
  | { type: "escape" }
  | { type: "year"; year: string };

export const initialDrill: DrillState = { open: null, load: { status: "loading" }, request: 0, focusReturns: 0 };

export const cellKey = (cell: CellRef, year: string) => `${year}|${cell.table}|${cell.row}|${cell.column}`;

export function isOpen(state: DrillState, cell: CellRef, year: string): boolean {
  return !!state.open && cellKey(state.open.cell, state.open.year) === cellKey(cell, year);
}

const closed = (state: DrillState, returnFocus: boolean): DrillState => ({
  ...state,
  open: null,
  focusReturns: state.focusReturns + (returnFocus ? 1 : 0),
});

export function drillReducer(state: DrillState, action: DrillAction): DrillState {
  switch (action.type) {
    case "toggle": {
      if (isOpen(state, action.cell, action.year)) return closed(state, true);
      // A file we already have is shown at once, with no loading state; otherwise the list waits for the fetch.
      const have = action.cached ?? (state.load.status === "ready" ? state.load.reports : null);
      const open = { cell: action.cell, year: action.year, count: action.count };
      return have
        ? { ...state, open, load: { status: "ready", reports: have } }
        : { ...state, open, load: { status: "loading" }, request: state.request + 1 };
    }
    case "loaded":
      return action.request === state.request && state.load.status === "loading" ? { ...state, load: { status: "ready", reports: action.reports } } : state;
    case "failed":
      return action.request === state.request && state.load.status === "loading" ? { ...state, load: { status: "error", message: action.message } } : state;
    case "retry":
      return state.open && state.load.status === "error" ? { ...state, load: { status: "loading" }, request: state.request + 1 } : state;
    case "close":
    case "escape":
      return state.open ? closed(state, true) : state;
    case "year":
      // A list belongs to the year it was opened for; changing year closes it and leaves focus where the picker put it.
      return state.open && state.open.year !== action.year ? closed(state, false) : state;
  }
}
