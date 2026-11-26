import { readdirSync, readFileSync, statSync } from "node:fs";
import { join, relative } from "node:path";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import { Footer } from "./Footer";
import { Wordmark } from "./Wordmark";

const VARIANTS = ["stamp", "corner", "bracket", "rule", "dotted", "monogram", "plain"] as const;

describe("wordmark", () => {
  // Guards a variant still printing the old `collegedata` + `.fyi` pair.
  it.each(VARIANTS)("%s shows QUADFILE and nothing of the old name", (variant) => {
    const html = renderToStaticMarkup(<Wordmark variant={variant} size={20} />);
    expect(html).toContain("QUADFILE");
    expect(html).not.toMatch(/collegedata|\.fyi/i);
  });

  // Guards the mark staying 4px at every size (the design-system page shows size 28).
  it("scales the four-square mark with size", () => {
    const px = (size: number) => /grid-template-columns:(\d+)px/.exec(renderToStaticMarkup(<Wordmark variant="dotted" size={size} />))?.[1];
    expect(px(20)).toBe("4");
    expect(px(28)).toBe("6");
  });
});

describe("footer", () => {
  it("names the owner of record and the former name in plain text", () => {
    const html = renderToStaticMarkup(<Footer />);
    expect(html).toContain("Quadfile is a project of Bolewood Group, LLC.");
    expect(html).toContain("Formerly collegedata.fyi.");
    // The former name is not a link or a logo.
    expect(html).not.toMatch(/<a[^>]*>[^<]*collegedata\.fyi/i);
  });
});

// The old name may appear in web/src only on a line that matches one of these, each with its
// reason. Anything else is user-visible, generated or documentation copy and must say Quadfile.
const ALLOWED_LINES: Array<[RegExp, string]> = [
  [/github\.com[/\\]+[^\s"'`)]*collegedata|bolewood\\?\/collegedata-fyi/i, "repository links and run-URL patterns (PR B owns them)"],
  [/api\.collegedata\.fyi|collegedata\\+\.fyi/i, "old API host and old site host: redirect and archive-URL compatibility"],
  [/x-collegedata-/i, "old client header, accepted until day +30"],
  [/collegedata:select-school/, "internal DOM event name"],
  [/bin\/collegedata(-mcp)?\.js/, "script path inside the repo (file names are unchanged)"],
  [/FORMER_NAME = /, "the footer's plain-text former name"],
  [/collegedata-fyi/, "Sentry project slug and other internal ids"],
  [/collegedata-sentry-verify|collegedata\.duckdb|collegedata-scholarships/, "internal diagnostic text and persisted artifact names"],
  [/AidAtlas|college-stats/, "third-party project links"],
  [/COLLEGEDATA-FYI-/, "Sentry issue ids in comments"],
];
const FORBIDDEN_SPELLINGS = /QuadFile|Quad File|QUAD-FILE|(?:api|www)\.Quadfile/;

function sourceFiles(dir: string): string[] {
  return readdirSync(dir).flatMap((name) => {
    const path = join(dir, name);
    if (statSync(path).isDirectory()) return sourceFiles(path);
    return /\.(tsx?|json|md)$/.test(name) && !/\.test\.tsx?$/.test(name) ? [path] : [];
  });
}

describe("brand spelling in web/src", () => {
  const root = join(process.cwd(), "src");
  const lines = sourceFiles(root).flatMap((f) =>
    readFileSync(f, "utf8")
      .split("\n")
      .map((text, i) => ({ where: `${relative(root, f)}:${i + 1}`, text })),
  );

  // Guards a bulk replace leaving the old name in copy, or an unlisted use creeping in.
  it("keeps the old name only on listed compatibility lines", () => {
    const offenders = lines
      .filter(({ text }) => /collegedata/i.test(text))
      .filter(({ text }) => !ALLOWED_LINES.some(([re]) => re.test(text)))
      .map(({ where, text }) => `${where}: ${text.trim().slice(0, 100)}`);
    expect(offenders).toEqual([]);
  });

  // Guards a replace that mangled a host or a name: QuadFile, Quad File, QUAD-FILE, api.Quadfile.
  it("never uses a wrong spelling of the new name", () => {
    const offenders = lines.filter(({ text }) => FORBIDDEN_SPELLINGS.test(text)).map(({ where }) => where);
    expect(offenders).toEqual([]);
  });
});
