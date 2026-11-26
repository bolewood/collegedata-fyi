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

// The old site name may appear in web/src only where it is a compatibility or
// history constant. Everything else is user-visible or generated copy.
const ALLOWED = new Set(["lib/client-info.ts", "lib/old-api-host.ts", "lib/site.ts"]);

function sourceFiles(dir: string): string[] {
  return readdirSync(dir).flatMap((name) => {
    const path = join(dir, name);
    if (statSync(path).isDirectory()) return sourceFiles(path);
    return /\.(tsx?|json|md)$/.test(name) && !/\.test\.tsx?$/.test(name) ? [path] : [];
  });
}

describe("old site name in web/src", () => {
  it("appears only in the compatibility and history constants", () => {
    const root = join(process.cwd(), "src");
    const offenders = sourceFiles(root)
      .filter((f) => /collegedata\.fyi/i.test(readFileSync(f, "utf8")))
      .map((f) => relative(root, f))
      .filter((f) => !ALLOWED.has(f));
    expect(offenders).toEqual([]);
  });
});
