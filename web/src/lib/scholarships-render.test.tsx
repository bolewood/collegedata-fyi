import { describe, expect, it, vi } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";
import fixture from "./__fixtures__/scholarship-directory.json";
import { ScholarshipIndex } from "@/components/ScholarshipIndex";
import { ScholarshipProgramsCard } from "@/components/ScholarshipProgramsCard";
import { normalizeScholarshipRow, toIndexRow, type ScholarshipDirectoryRow } from "./scholarships";

vi.mock("next/link", () => ({
  default: ({ href, children, ...rest }: { href: string; children: React.ReactNode }) => (
    <a href={href} {...rest}>{children}</a>
  ),
}));

const ROWS = (fixture as unknown[]).map(normalizeScholarshipRow) as ScholarshipDirectoryRow[];
const TODAY = "2026-11-14";
const BANNED = /\b(verified|full ride|best|odds of winning|guaranteed to)\b/i;

const card = (programId: string, schoolId: string) => {
  const programs = ROWS.filter((r) => r.school_id === schoolId);
  return renderToStaticMarkup(
    <ScholarshipProgramsCard
      programs={programs}
      names={{ unc: "University of North Carolina at Chapel Hill", duke: "Duke University" }}
      schoolId={schoolId}
      today={TODAY}
    />,
  ).replace(/<[^>]+>/g, " ").replace(/\s+/g, " ");
};
const indexHtml = renderToStaticMarkup(
  <ScholarshipIndex rows={ROWS.map((r) => toIndexRow(r, r.school_id))} today={TODAY} />,
);
const indexText = indexHtml.replace(/<[^>]+>/g, " ").replace(/\s+/g, " ");

describe("every fixture row renders without banned words", () => {
  it("card text for every school and the whole index", () => {
    for (const id of new Set(ROWS.map((r) => r.school_id))) {
      // The school's own words, in quotation marks, may say anything (e.g. its label "full ride"); ours may not.
      const text = card("", id).replace(/“[^”]*”/g, "").replace(/&quot;.*?&quot;/g, "");
      const hit = BANNED.exec(text);
      expect(hit ? text.slice(Math.max(0, hit.index - 60), hit.index + 40).concat(' <<' + hit[0] + '>>') : null, id).toBeNull();
      expect(text, id).toMatch(/Data CC BY-SA 4\.0/);
    }
    expect(indexText).not.toMatch(BANNED);
  });
});

describe("card", () => {
  it("shows UMD's fee exclusions next to the fee line", () => {
    expect(card("", "umd")).toMatch(/Mandatory fees: the school says it covers all of it\. Not included: Miscellaneous fees/);
  });
  it("never prints a year for Tulsa's recurring deadline", () => {
    expect(card("", "university-of-tulsa")).toMatch(/Admission deadline: November 1 each year\. The page names no year/);
  });
  it("Vanderbilt Chancellor's says closed and has no 'Terms for ... entry' line", () => {
    const text = card("", "vanderbilt");
    expect(text).toMatch(/closed to new entrants/i);
    expect(text).not.toMatch(/No award terms listed for new entrants\. Terms below are kept/);
    const chancellor = text.slice(text.indexOf("Chancellor"), text.indexOf("Cornelius"));
    expect(chancellor).not.toMatch(/Terms for fall \d{4} entry/);
    expect(chancellor).not.toMatch(/Terms below are kept for reference/);
  });
  it("UGA Stamps links to the related program documented on the same page", () => {
    expect(renderToStaticMarkup(
      <ScholarshipProgramsCard programs={ROWS.filter((r) => r.school_id === "uga")} names={{}} schoolId="uga" today={TODAY} />,
    )).toMatch(/href="#scholarship-foundation-fellowship"/);
  });
  it("source links name the program for screen readers", () => {
    const html = renderToStaticMarkup(
      <ScholarshipProgramsCard programs={ROWS.filter((r) => r.school_id === "texas-am")} names={{}} schoolId="texas-am" today={TODAY} />,
    );
    expect(html).toMatch(/aria-label="National Merit Scholars[^"]*: Official page \(opens in a new tab\)"/);
  });
  it("renders nothing for a school with no programs", () => {
    expect(renderToStaticMarkup(<ScholarshipProgramsCard programs={[]} names={{}} schoolId="x" />)).toBe("");
  });
});

describe("index", () => {
  it("shows 'Varies by award' for Texas A&M, not 'Automatic if you qualify'", () => {
    const tamu = indexHtml.slice(indexHtml.indexOf("texas-am"), indexHtml.indexOf("</tr>", indexHtml.indexOf("texas-am")));
    expect(tamu).toContain("Varies by award");
    expect(tamu).not.toContain("Automatic if you qualify");
  });
  it("marks Vanderbilt Chancellor's closed and Georgia Tech's date passed", () => {
    expect(indexText, indexText.slice(indexText.indexOf('Chancellor') - 50, indexText.indexOf('Chancellor') + 200)).toMatch(/Chancellor.{1,8}s Scholarship \(retired\) Closed to new entrants/);
    expect(indexText).toContain("Oct 15, 2026 (passed)");
  });
  it("has table roles and per-program source labels, and the residency filter has Not stated", () => {
    expect(indexHtml).toContain('role="table"');
    expect(indexHtml).toContain('role="cell"');
    expect(indexHtml).toMatch(/aria-label="Johnson Scholarship: Official page \(opens in a new tab\)"/);
    expect(indexHtml).toMatch(/<option value="not_stated">Not stated<\/option>/);
  });
  it("does not ship offers or evidence to the browser", () => {
    expect(indexHtml.length).toBeGreaterThan(0);
    const slim = JSON.stringify(ROWS.map((r) => toIndexRow(r, r.school_id)));
    expect(slim).not.toContain("offer_id");
    expect(slim).not.toContain("field_path");
  });
});
