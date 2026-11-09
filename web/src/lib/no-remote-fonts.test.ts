import { readdirSync, readFileSync, statSync } from "node:fs";
import { join, relative } from "node:path";
import { describe, expect, it } from "vitest";

// Fonts are self-hosted in src/app/fonts/ and loaded with next/font/local.
// next/font/google downloads font files from Google on every build, and a
// failed download fails the whole Vercel build (v0.6.19.8). A Google Fonts
// stylesheet link does the same at runtime. Add new faces as local files
// instead; see src/app/fonts/README.md.

const SCANNED = /\.(ts|tsx|js|jsx|mjs|cjs|css)$/;
const REMOTE_FONT_PATTERNS: [RegExp, string][] = [
  [/from\s+["']next\/font\/google["']/, 'imports "next/font/google"'],
  [/(require|import)\(\s*["']next\/font\/google["']\s*\)/, 'imports "next/font/google"'],
  [/fonts\.(googleapis|gstatic)\.com/, "references Google Fonts"],
];

function sourceFiles(dir: string): string[] {
  return readdirSync(dir).flatMap((name) => {
    const path = join(dir, name);
    if (statSync(path).isDirectory()) return sourceFiles(path);
    return SCANNED.test(name) ? [path] : [];
  });
}

describe("fonts are self-hosted", () => {
  it("no source file loads fonts from Google", () => {
    const root = process.cwd();
    const files = [...sourceFiles(join(root, "src")), join(root, "next.config.ts")];
    const offenders = files.flatMap((file) => {
      const text = readFileSync(file, "utf8");
      return REMOTE_FONT_PATTERNS.filter(([pattern]) => pattern.test(text)).map(
        ([, what]) => `${relative(root, file)} ${what}`,
      );
    });
    expect(
      offenders,
      "Use next/font/local with a file in src/app/fonts/ (see its README).",
    ).toEqual([]);
  });

  it("the self-hosted font files are present", () => {
    const fonts = readdirSync(join(process.cwd(), "src/app/fonts"));
    expect(fonts.filter((name) => name.endsWith(".woff2")).length).toBeGreaterThanOrEqual(4);
  });
});
