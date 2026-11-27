import { readdirSync, readFileSync, statSync } from "node:fs";
import { join, relative } from "node:path";
import { fileURLToPath } from "node:url";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import { Footer } from "./Footer";
import { Wordmark } from "./Wordmark";

const VARIANTS = ["stamp", "corner", "bracket", "rule", "dotted", "monogram", "plain"] as const;

// Removes every element marked aria-hidden (they never nest in the wordmark), then the tags,
// leaving what a screen reader would read.
function accessibleText(html: string): string {
  let out = html;
  for (;;) {
    const start = out.indexOf('<span aria-hidden="true"');
    if (start < 0) break;
    let depth = 0;
    let end = start;
    const tag = /<(\/?)span\b[^>]*>/g;
    tag.lastIndex = start;
    for (let m = tag.exec(out); m; m = tag.exec(out)) {
      depth += m[1] ? -1 : 1;
      if (depth === 0) {
        end = tag.lastIndex;
        break;
      }
    }
    out = out.slice(0, start) + out.slice(end);
  }
  return out.replace(/<[^>]+>/g, "");
}

describe("wordmark", () => {
  // Guards a variant still printing the old `collegedata` + `.fyi` pair.
  it.each(VARIANTS)("%s shows the name in caps by CSS and nothing of the old name", (variant) => {
    const html = renderToStaticMarkup(<Wordmark variant={variant} size={20} />);
    expect(html).toContain("text-transform:uppercase");
    expect(html).not.toMatch(/collegedata|\.fyi/i);
  });

  // Guards a screen reader hearing "Q-U-A-D-F-I-L-E" or "section Quadfile": the name is real text
  // and every glyph is hidden.
  it.each(VARIANTS)("%s reads as Quadfile to assistive technology", (variant) => {
    const html = renderToStaticMarkup(<Wordmark variant={variant} size={20} />);
    expect(accessibleText(html)).toBe("Quadfile");
    expect(html).not.toContain("QUADFILE");
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

// The old name or a `.fyi` host may appear in web/src only on a line allowed here, scoped to the
// file that needs it, with the reason. Anything else is user-visible, generated or documentation
// copy and must say Quadfile.
const SRC = fileURLToPath(new URL("../", import.meta.url));
const PUBLIC = fileURLToPath(new URL("../../public/", import.meta.url));

const ALLOWED: Array<{ file: RegExp; line: RegExp; why: string }> = [
  { file: /^lib\/pipeline-observation\.ts$/, line: /bolewood\\\/\(\?:collegedata-fyi\|quadfile\)/, why: "run-URL pattern accepts both repo names (stored heartbeats keep the old one)" },
  { file: /^lib\/site\.ts$/, line: /FORMER_NAME = "collegedata\.fyi"/, why: "the footer's plain-text former name" },
  { file: /^lib\/(old-api-host|old-site-redirect|client-info)\.ts$/, line: /collegedata/i, why: "old hosts: redirect and archive-URL compatibility" },
  { file: /^proxy\.ts$/, line: /api\\\\\.collegedata\\\\\.fyi/, why: "old API host in the proxy matcher" },
  { file: /^lib\/api-usage\.ts$/, line: /x-collegedata-|x-collegedata/, why: "old client header, accepted until day +30" },
  { file: /^(app\/api\/page|app\/privacy\/page|lib\/llms-txt)\.tsx?$/, line: /X-CollegeData-Client/, why: "docs name the old header that still works" },
  { file: /^app\/api\/page\.tsx$/, line: /bin\/collegedata(-mcp)?\.js/, why: "script path inside the repo (file names are unchanged)" },
  { file: /^components\/AlignmentGap\w*\.tsx$/, line: /collegedata:select-school/, why: "internal DOM event name" },
  { file: /^lib\/discovery\/content\/README\.md$/, line: /cd \/path\/to\/collegedata-fyi/, why: "local checkout directory name" },
  { file: /^lib\/sentry\.ts$/, line: /"collegedata-fyi"/, why: "Sentry project slug" },
  { file: /^lib\/queries\.ts$/, line: /COLLEGEDATA-FYI-[A-Z0-9]+/, why: "Sentry issue id in a comment" },
  { file: /^app\/api\/sentry-verify\/route\.ts$/, line: /collegedata-sentry-verify/, why: "internal diagnostic text" },
  { file: /^lib\/snapshot-data\.ts$/, line: /collegedata\.duckdb/, why: "still answers the old snapshot file name" },
  { file: /^data\/community\/projects\.ts$/, line: /AidAtlas\/blob\/main\/backend\/app\/services\/collegedata\.py|college-stats\/blob\/main\/release-notes\/cds-urls-collegedata\.md/, why: "third-party project links" },
];

function sourceFiles(dir: string, extensions: RegExp, skipTests: boolean): string[] {
  return readdirSync(dir).flatMap((name) => {
    const path = join(dir, name);
    if (statSync(path).isDirectory()) return sourceFiles(path, extensions, skipTests);
    if (skipTests && /\.test\.tsx?$/.test(name)) return [];
    return extensions.test(name) ? [path] : [];
  });
}

function linesOf(root: string, files: string[]) {
  return files.flatMap((f) =>
    readFileSync(f, "utf8")
      .split("\n")
      .map((text, i) => ({ file: relative(root, f), where: `${relative(root, f)}:${i + 1}`, text })),
  );
}

describe("brand spelling in web/src", () => {
  const lines = linesOf(SRC, sourceFiles(SRC, /\.(tsx?|json|md)$/, true));

  // Guards a bulk replace leaving the old name (or a `.fyi` host) in copy, and an unlisted use creeping in.
  it("keeps the old name and `.fyi` only on allowed lines", () => {
    const offenders = lines
      .filter(({ text }) => /collegedata|\.fyi/i.test(text))
      .filter(({ file, text }) => !ALLOWED.some((a) => a.file.test(file) && a.line.test(text)))
      .map(({ where, text }) => `${where}: ${text.trim().slice(0, 100)}`);
    expect(offenders).toEqual([]);
  });

  // Guards a replace that mangled a host or a name: QuadFile, Quad File, QUAD-FILE, quadfile.fyi, api.Quadfile.
  it("never uses a wrong spelling of the new name", () => {
    const wrong = [/quad[- ]file/i, /quadfile\.fyi/i, /QuadFile/, /\b(?:api|www)\.Quadfile/];
    const offenders = lines.filter(({ text }) => wrong.some((re) => re.test(text))).map(({ where }) => where);
    expect(offenders).toEqual([]);
  });

  // The all-caps name belongs to the Open Graph images, which cannot use CSS; the wordmark uses CSS.
  it("keeps the all-caps QUADFILE to the image generators", () => {
    const offenders = lines
      .filter(({ text }) => /QUADFILE(?!_)/.test(text))
      .filter(({ file }) => !/(^|\/)opengraph-image\.tsx$/.test(file))
      .map(({ where }) => where);
    expect(offenders).toEqual([]);
  });
});

describe("brand spelling in static pages under web/public", () => {
  const lines = linesOf(PUBLIC, sourceFiles(join(PUBLIC, "design-system"), /\.html$/, false));

  // Guards the static design-system page keeping the old wordmark or host.
  it("has no old name, .fyi host or wrong spelling in the design-system page", () => {
    expect(lines.length).toBeGreaterThan(50);
    const offenders = lines
      .filter(({ text }) => /collegedata|\.fyi|quad[- ]file|quadfile\.fyi/i.test(text) || /QuadFile/.test(text))
      .map(({ where, text }) => `${where}: ${text.trim().slice(0, 100)}`);
    expect(offenders).toEqual([]);
  });
});
