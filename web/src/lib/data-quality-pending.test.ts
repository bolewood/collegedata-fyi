import { describe, expect, it } from "vitest";
import { pendingYearScript } from "./data-quality-pending";

// The script runs in the browser before hydration, against a static page that shows the default year. It may only set
// attributes: changing text or removing elements would itself be a hydration mismatch.
function run(search: string, others: string[]) {
  const html = { attrs: {} as Record<string, string>, setAttribute(k: string, v: string) { this.attrs[k] = v; } };
  const body = { attrs: {} as Record<string, string>, setAttribute(k: string, v: string) { this.attrs[k] = v; } };
  const doc = { documentElement: html, getElementById: (id: string) => (id === "dq-body" ? body : null) };
  new Function("document", "location", "URLSearchParams", pendingYearScript(others))(doc, { search }, URLSearchParams);
  return { html: html.attrs, body: body.attrs };
}

describe("pendingYearScript", () => {
  it("marks the page pending for a direct link to another year", () => {
    const r = run("?year=2023-24", ["2024-25", "2023-24"]);
    expect(r.html["data-dq-pending"]).toBe("2023-24");
    expect(r.body["aria-busy"]).toBe("true");
  });
  it("does nothing for the default year, no year, or a year the page does not have", () => {
    for (const q of ["", "?year=2025-26", "?year=1999-00", "?other=1"]) {
      const r = run(q, ["2024-25", "2023-24"]);
      expect(r.html, q).toEqual({});
      expect(r.body, q).toEqual({});
    }
  });
});
