import { readdirSync, readFileSync, statSync } from "node:fs";
import { join, relative, resolve } from "node:path";
import { describe, expect, it } from "vitest";

// Two ways a space between words disappears in rendered copy, both seen on the live site:
//
// 1. An HTML entity (&rsquo;, &apos;, &amp; ...) in a JSX text run that follows an inline element or a {expression}.
//    Next 16's compiler drops the run's leading space ("Not checked yet</em>means"). Vitest compiles JSX differently
//    and renders the space, so a render test can't see it. Write the character instead of the entity.
// 2. An inline element or {expression} at the end of a line, with the text continuing on the next line. JSX trims
//    whitespace that contains a newline ("<code>400</code>instead of"). Add {" "} at the end of the line.
//
// This reads the source of every component and page, so dynamic routes are covered too.

const SRC = resolve(__dirname, "..");

function tsxFiles(dir: string): string[] {
  return readdirSync(dir).flatMap((name) => {
    const p = join(dir, name);
    if (statSync(p).isDirectory()) return tsxFiles(p);
    return p.endsWith(".tsx") && !/\.test\.tsx$/.test(p) ? [p] : [];
  });
}

const FILES = tsxFiles(SRC);

describe("JSX copy keeps the spaces between words", () => {
  it("finds the source files", () => {
    expect(FILES.length).toBeGreaterThan(50);
  });

  it("writes characters, not HTML entities, in components and pages", () => {
    const hits: string[] = [];
    for (const f of FILES) {
      readFileSync(f, "utf8").split("\n").forEach((line, i) => {
        if (/^\s*(\/\/|\*|\/\*)/.test(line)) return;
        if (/&(?:[a-zA-Z]+|#x?[0-9a-fA-F]+);/.test(line)) hits.push(`${relative(SRC, f)}:${i + 1}: ${line.trim().slice(0, 80)}`);
      });
    }
    expect(hits).toEqual([]);
  });

  it("puts {\" \"} where an inline element or {expression} ends a line and text continues on the next", () => {
    const inlineEnd = /<\/(?:code|em|strong|a|b|i|abbr|small|sup|u|mark|kbd|Link|ListLink)>\s*$/;
    const exprEnd = /[A-Za-z0-9.,:;)]\s*\{[A-Za-z_][^{}"=]*\}$/;
    const hits: string[] = [];
    for (const f of FILES) {
      const lines = readFileSync(f, "utf8").split("\n");
      for (let i = 0; i < lines.length - 1; i++) {
        const a = lines[i].trim();
        const b = lines[i + 1].trim();
        const ends = inlineEnd.test(a) || (a.endsWith("}") && !a.endsWith('{" "}') && exprEnd.test(a));
        if (!ends || !b || !/^[A-Za-z0-9(“‘'"$%]/.test(b)) continue;
        if (/^[\w-]+=/.test(b) || /[=;]\s*$|=>|^(import|export|const|let|return|if|for|type|else|case)\b/.test(b)) continue;
        // A block label followed by text is fine when CSS makes it a block (the usage footnote); name it here.
        if (a.includes('className="meta">Our own serving load')) continue;
        hits.push(`${relative(SRC, f)}:${i + 1}: …${a.slice(-50)} || ${b.slice(0, 40)}`);
      }
    }
    expect(hits).toEqual([]);
  });
});
