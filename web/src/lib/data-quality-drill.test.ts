import { describe, expect, it } from "vitest";
import { cellKey, drillReducer, initialDrill, isOpen, type DrillAction, type DrillState } from "./data-quality-drill";
import type { CellRef, ReportsFile } from "./data-quality-reports";

const FILE = { reports_format: 1, snapshot_of: "x", scoreboard_run: "x", codes: {}, schools: {}, years: {} } as ReportsFile;
const A: CellRef = { table: "status", row: "total", column: "published" };
const B: CellRef = { table: "totals", row: "pdf_flat", column: "H1.adds_up" };
const run = (...actions: DrillAction[]): DrillState => actions.reduce(drillReducer, initialDrill);
const toggle = (cell: CellRef, year = "2024-25", cached: ReportsFile | null = null, count = 5): DrillAction => ({ type: "toggle", cell, year, count, cached });

describe("the list's state", () => {
  it("starts closed", () => {
    expect(initialDrill.open).toBeNull();
    expect(isOpen(initialDrill, A, "2024-25")).toBe(false);
  });

  it("opens a cell and waits for the file when there is none yet", () => {
    const s = run(toggle(A));
    expect(s.open).toEqual({ cell: A, year: "2024-25", count: 5 });
    expect(s.load).toEqual({ status: "loading" });
    expect(s.request).toBe(1);
    expect(isOpen(s, A, "2024-25")).toBe(true);
    expect(isOpen(s, A, "2023-24")).toBe(false);
    expect(isOpen(s, B, "2024-25")).toBe(false);
  });

  it("shows a file it already has at once, with no loading state and no new request", () => {
    const s = run(toggle(A, "2024-25", FILE));
    expect(s.load).toEqual({ status: "ready", reports: FILE });
    expect(s.request).toBe(0);
    // And once a list has loaded, the next cell opens ready too, even if the cache is not passed.
    const next = run(toggle(A), { type: "loaded", request: 1, reports: FILE }, toggle(B));
    expect(next.load.status).toBe("ready");
    expect(next.request).toBe(1);
    expect(next.open!.cell).toEqual(B);
  });

  it("takes the response of the request it is waiting for, and ignores a late or stale one", () => {
    const s = run(toggle(A), { type: "loaded", request: 1, reports: FILE });
    expect(s.load).toEqual({ status: "ready", reports: FILE });
    expect(run(toggle(A), { type: "loaded", request: 0, reports: FILE }).load.status).toBe("loading");
    expect(run(toggle(A), { type: "loaded", request: 2, reports: FILE }).load.status).toBe("loading");
    // A second response after the first changes nothing.
    expect(drillReducer(s, { type: "loaded", request: 1, reports: { ...FILE, snapshot_of: "later" } })).toBe(s);
    expect(drillReducer(s, { type: "failed", request: 1, message: "late" })).toBe(s);
  });

  it("closing the open cell by toggling it asks for focus to go back, and clicking it again reopens", () => {
    const open = run(toggle(A, "2024-25", FILE));
    const closed = drillReducer(open, toggle(A, "2024-25", FILE));
    expect(closed.open).toBeNull();
    expect(closed.focusReturns).toBe(1);
    expect(drillReducer(closed, toggle(A, "2024-25", FILE)).open).not.toBeNull();
  });

  it("switches to another cell without closing, and without asking for focus to return", () => {
    const s = run(toggle(A, "2024-25", FILE), toggle(B, "2024-25", FILE, 9));
    expect(s.open).toEqual({ cell: B, year: "2024-25", count: 9 });
    expect(s.focusReturns).toBe(0);
    // The same cell in another year is another cell.
    const other = run(toggle(A, "2024-25", FILE), toggle(A, "2023-24", FILE));
    expect(other.open!.year).toBe("2023-24");
    expect(cellKey(A, "2024-25")).not.toBe(cellKey(A, "2023-24"));
  });

  it("Close and Escape close an open list and return focus; with nothing open they change nothing", () => {
    const open = run(toggle(A, "2024-25", FILE));
    for (const type of ["close", "escape"] as const) {
      const s = drillReducer(open, { type });
      expect(s.open).toBeNull();
      expect(s.focusReturns).toBe(1);
      expect(drillReducer(s, { type })).toBe(s);
    }
    expect(drillReducer(initialDrill, { type: "escape" })).toBe(initialDrill);
  });

  it("closes when the year changes, leaves focus alone, and ignores a change to the same year", () => {
    const open = run(toggle(A, "2024-25", FILE));
    const s = drillReducer(open, { type: "year", year: "2023-24" });
    expect(s.open).toBeNull();
    expect(s.focusReturns).toBe(0);
    expect(drillReducer(open, { type: "year", year: "2024-25" })).toBe(open);
    expect(drillReducer(initialDrill, { type: "year", year: "2023-24" })).toBe(initialDrill);
  });

  it("shows an error for the request that failed, and Retry asks again with a new request", () => {
    const failed = run(toggle(A), { type: "failed", request: 1, message: "HTTP 503" });
    expect(failed.load).toEqual({ status: "error", message: "HTTP 503" });
    const retried = drillReducer(failed, { type: "retry" });
    expect(retried.load).toEqual({ status: "loading" });
    expect(retried.request).toBe(2);
    // The failed request's late duplicate no longer matches; the new one does.
    expect(drillReducer(retried, { type: "failed", request: 1, message: "old" })).toBe(retried);
    expect(drillReducer(retried, { type: "loaded", request: 2, reports: FILE }).load.status).toBe("ready");
    // Retry only applies to an error on an open list.
    expect(drillReducer(initialDrill, { type: "retry" })).toBe(initialDrill);
    expect(drillReducer(run(toggle(A)), { type: "retry" }).request).toBe(1);
  });

  it("opening another cell after an error asks again instead of showing the error", () => {
    const s = run(toggle(A), { type: "failed", request: 1, message: "x" }, toggle(B));
    expect(s.load).toEqual({ status: "loading" });
    expect(s.request).toBe(2);
  });

  it("a response that arrives after the list was closed still fills the cache path: the next open is ready", () => {
    const s = run(toggle(A), drillReducerClose(), { type: "loaded", request: 1, reports: FILE }, toggle(B));
    expect(s.load.status).toBe("ready");
  });
});

function drillReducerClose(): DrillAction {
  return { type: "close" };
}
