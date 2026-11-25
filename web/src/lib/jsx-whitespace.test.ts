import { readdirSync, readFileSync, statSync } from "node:fs";
import { join, relative, resolve } from "node:path";
import ts from "typescript";
import { describe, expect, it } from "vitest";

// Two ways a space between words disappears in rendered copy, both seen on the live site:
//
// 1. An HTML entity (&rsquo;, &apos;, &amp; ...) in JSX text after an inline element or a {expression}. Next 16's
//    compiler drops the run's leading space ("Not checked yet</em>means"). Vitest compiles JSX differently and keeps
//    the space, so a render test can't see it. Write the character. An entity in a string literal is worse: it is
//    never decoded, so the reader sees "aren&apos;t".
// 2. A line break at the edge of a JSX text run, or between two inline pieces. JSX trims whitespace that contains a
//    newline, so "<code>400</code>" + newline + "instead of" renders "400instead of".
//
// Both are found from the syntax tree (the TypeScript compiler API), in every component and page (dynamic routes too).
//
// The rule is deliberately strict and has no inference. At a line break, an edge is safe ONLY if it is
//   - text (JSX keeps the space inside a text run on the same line), or
//   - a {" "}-style string literal (or a template literal with no substitutions) whose own first or last character is
//     a space, or
//   - punctuation that attaches to its word ("." after "</a>", "(" before "<Link>"), or a <br />, or
//   - one exact boundary on the allow-list below.
// ANY other expression (a conditional, `||`, `+`, a call, an identifier, a template with substitutions) counts as
// having no space, even if one of its branches starts with one.

const SRC = resolve(__dirname, "..");

function tsxFiles(dir: string): string[] {
  return readdirSync(dir).flatMap((name) => {
    const p = join(dir, name);
    if (statSync(p).isDirectory()) return tsxFiles(p);
    return p.endsWith(".tsx") && !/\.test\.tsx$/.test(p) ? [p] : [];
  });
}

type Kind = "entity" | "entity in string" | "newline-boundary";
type Problem = { where: string; file: string; kind: Kind; left: string; right: string; insertAt?: number };

/** One exact boundary where the author meant no space, or CSS supplies it. `left` and `right` are the full, whitespace-normalised source on each side. Never an entity. */
type Allowed = { file: string; kind: "newline-boundary"; left: string; right: string; reason: string };
export const ALLOWED: Allowed[] = [
  {
    file: "app/recipes/page.tsx",
    kind: "newline-boundary",
    left: "<span className=\"meta\" style={{ marginRight: 6 }}>For</span>",
    right: "{r.audience}",
    reason: "The label span carries its own gap (margin-right: 6px), so the audience text follows without a space.",
  },
  {
    file: "app/usage/page.tsx",
    kind: "newline-boundary",
    left: "<i style={{ borderColor: \"var(--browser)\", borderTopWidth: 3 }} />",
    right: "Browser",
    reason: "Legend swatch: the i element is a CSS line with margin-right: 6px (.usage-key i), so the label needs no space.",
  },
  {
    file: "app/usage/page.tsx",
    kind: "newline-boundary",
    left: "<i style={{ borderColor: \"var(--ink)\", borderTopWidth: 1.25 }} />",
    right: "Machine",
    reason: "Same legend swatch as above (.usage-key i margin-right: 6px).",
  },
  {
    file: "app/usage/page.tsx",
    kind: "newline-boundary",
    left: "<i style={{ borderColor: \"var(--ink-4)\", borderTopStyle: \"dashed\" }} />",
    right: "Bots and crawlers",
    reason: "Same legend swatch as above (.usage-key i margin-right: 6px).",
  },
  {
    file: "app/usage/page.tsx",
    kind: "newline-boundary",
    left: "<span className=\"meta\">Our own serving load</span>",
    right: "In",
    reason: "The footnote label span (class meta) is display: block (.usage-footnote .meta), so the sentence starts on its own line.",
  },
  {
    file: "components/DataQualityView.tsx",
    kind: "newline-boundary",
    left: "removed",
    right: "{year.no_file > 0 ? `, ${n(year.no_file)} with no file` : \"\"}",
    reason: "The template starts with a comma (', N with no file') and must attach to 'removed'; a space would print 'removed , N'.",
  },
  {
    file: "components/FieldsView.tsx",
    kind: "newline-boundary",
    left: "TABLE",
    right: "{sec.subsections.length === 1 ? \"\" : \"S\"}",
    reason: "A plural suffix: the number and TABLE, then S or nothing, must read TABLES, not TABLE S.",
  },
  {
    file: "components/ScholarshipProgramsCard.tsx",
    kind: "newline-boundary",
    left: "”",
    right: "{t.scope ? <> ({t.scope})</> : null}",
    reason: "The conditional fragment supplies its own leading space (' (scope)') and renders nothing otherwise; a space here would leave a stray space before the full stop.",
  },
];

const norm = (s: string) => s.replace(/\s+/g, " ").trim();

/** Inline elements: HTML phrasing tags and the link components. A block element next to another is layout, not prose. */
const INLINE = new Set(["a", "abbr", "b", "cite", "code", "em", "i", "kbd", "mark", "q", "small", "span", "strong", "sub", "sup", "u", "Link", "TrackedLink", "ListLink"]);
const tagOf = (n: ts.Node) => (ts.isJsxElement(n) ? n.openingElement.tagName.getText() : ts.isJsxSelfClosingElement(n) ? n.tagName.getText() : "");
const isInlineElement = (n: ts.Node) => (ts.isJsxElement(n) || ts.isJsxSelfClosingElement(n)) && INLINE.has(tagOf(n));
/**
 * Elements whose children are running prose. Two inline pieces split across a line break are only a problem here:
 * inside a div, nav, button or flex row they are layout (CSS gap, margin or `display: block` spaces them).
 */
const PROSE_PARENT = new Set(["p", "li", "td", "th", "dd", "dt", "caption", "figcaption", "blockquote", "h1", "h2", "h3", "h4", "h5", "h6", "label", "summary"]);
const isLineBreak = (n: ts.Node) => ts.isJsxSelfClosingElement(n) && tagOf(n) === "br";

/** `{" "}` and its kin: a string (or substitution-free template) literal whose own edge character is a space. */
const isSpaceLiteral = (n: ts.Node, edge: "start" | "end"): boolean => {
  if (!ts.isJsxExpression(n) || !n.expression) return false;
  const e = n.expression;
  if (!ts.isStringLiteral(e) && !ts.isNoSubstitutionTemplateLiteral(e)) return false;
  return e.text !== "" && (edge === "start" ? /^\s/.test(e.text) : /\s$/.test(e.text));
};
const isComment = (n: ts.Node) => ts.isJsxExpression(n) && !n.expression;
const ENTITY = /&(?:[a-zA-Z][a-zA-Z0-9]*|#[0-9]+|#x[0-9a-fA-F]+);/;

export function findProblems(file: string, source: string): Problem[] {
  const sf = ts.createSourceFile(file, source, ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX);
  const rel = relative(SRC, file);
  const out: Problem[] = [];
  const at = (n: ts.Node) => `${rel}:${sf.getLineAndCharacterOfPosition(n.getStart(sf)).line + 1}`;
  const textOf = (n: ts.Node) => (ts.isJsxText(n) ? norm(source.slice(n.pos, n.end)) : norm(n.getText(sf)));
  const boundary = (at_: ts.Node, left: ts.Node, right: ts.Node) =>
    out.push({
      where: at(at_),
      file: rel,
      kind: "newline-boundary",
      left: textOf(left),
      right: textOf(right),
      // Where {" "} goes to fix it: the end of the left piece's content.
      insertAt: ts.isJsxText(left) ? left.pos + source.slice(left.pos, left.end).trimEnd().length : left.end,
    });

  const visit = (node: ts.Node) => {
    // Entities in string literals the reader can see: JSX expressions and attribute values.
    if (ts.isStringLiteral(node) || ts.isNoSubstitutionTemplateLiteral(node) || ts.isTemplateHead(node) || ts.isTemplateMiddle(node) || ts.isTemplateTail(node)) {
      if (ENTITY.test(node.text)) out.push({ where: at(node), file: rel, kind: "entity in string", left: "", right: norm(node.text).slice(0, 80) });
    }
    if (ts.isJsxElement(node) || ts.isJsxFragment(node)) {
      const kids = node.children.filter((c) => !isComment(c));
      kids.forEach((kid, i) => {
        const prev = kids[i - 1];
        const next = kids[i + 1];
        if (ts.isJsxText(kid)) {
          const raw = source.slice(kid.pos, kid.end);
          if (ENTITY.test(raw)) out.push({ where: at(kid), file: rel, kind: "entity", left: "", right: norm(raw).slice(0, 80) });
          if (kid.containsOnlyTriviaWhiteSpaces) {
            // Two pieces side by side across a newline, nothing between them: inline next to inline or to an expression.
            if (!/\n/.test(raw) || !prev || !next || isLineBreak(prev) || isLineBreak(next)) return;
            if (!ts.isJsxElement(node) || !PROSE_PARENT.has(tagOf(node))) return;
            const proseSide = (a: ts.Node) => isInlineElement(a);
            const exprSide = (a: ts.Node) => ts.isJsxExpression(a);
            const leftSafe = isSpaceLiteral(prev, "end");
            const rightSafe = isSpaceLiteral(next, "start");
            if (leftSafe || rightSafe) return;
            // Element next to element is almost always cell or row layout; element next to an expression is where a
            // sentence gets built ("</strong>" newline "{message}"), so only that is flagged.
            if ((proseSide(prev) && exprSide(next)) || (exprSide(prev) && proseSide(next))) boundary(prev, prev, next);
            return;
          }
          const trimmed = raw.trim();
          // Prose punctuation attaches to the word before it, or after it.
          const closing = /^[.,;:!?)\]}’”%]/.test(trimmed);
          const opening = /[(\[{“‘]$/.test(trimmed);
          if (/^\s*\n/.test(raw) && prev && !ts.isJsxText(prev) && !isLineBreak(prev) && !isSpaceLiteral(prev, "end") && !closing) boundary(kid, prev, kid);
          if (/\n\s*$/.test(raw) && next && !ts.isJsxText(next) && !isLineBreak(next) && !isSpaceLiteral(next, "start") && !opening) boundary(kid, kid, next);
        }
      });
    }
    ts.forEachChild(node, visit);
  };
  visit(sf);
  return out.filter(
    (p) => p.kind !== "newline-boundary" || !ALLOWED.some((a) => a.file === p.file && a.kind === p.kind && a.left === p.left && a.right === p.right),
  );
}

export const describeProblems = (ps: Problem[]) => ps.map((p) => `${p.where} ${p.kind}: [${p.left}] || [${p.right}]`);

if (process.env.JSX_WS_DUMP) {
  // Scratch aid: dump every problem as JSON to the named file (used to build the allow-list).
  const fs = require("node:fs");
  fs.writeFileSync(
    process.env.JSX_WS_DUMP,
    JSON.stringify(tsxFiles(SRC).flatMap((f) => findProblems(f, readFileSync(f, "utf8"))), null, 1),
  );
}

describe("JSX copy keeps the spaces between words", () => {
  const FILES = tsxFiles(SRC);

  it("finds the source files", () => {
    expect(FILES.length).toBeGreaterThan(50);
  });

  it("has no entity, no entity in a string, and no unspaced line break between prose pieces, anywhere under src", () => {
    const problems = FILES.flatMap((f) => findProblems(f, readFileSync(f, "utf8")));
    expect(describeProblems(problems)).toEqual([]);
  });

  it("allow-list entries are exact boundaries that still exist, never entities", () => {
    const seen = new Set<string>();
    for (const a of ALLOWED) {
      expect(a.kind).toBe("newline-boundary");
      expect(a.reason.length).toBeGreaterThan(20);
      expect(a.left.length + a.right.length).toBeGreaterThan(0);
      const key = `${a.file}|${a.left}|${a.right}`;
      expect(seen.has(key)).toBe(false);
      seen.add(key);
    }
    // Every entry must still match a real boundary, so a stale entry can't hide a future one.
    const all = FILES.flatMap((f) => {
      const saved = ALLOWED.splice(0, ALLOWED.length);
      try {
        return findProblems(f, readFileSync(f, "utf8"));
      } finally {
        ALLOWED.push(...saved);
      }
    });
    for (const a of ALLOWED) expect(all.some((p) => p.file === a.file && p.left === a.left && p.right === a.right), `${a.file}: ${a.left} || ${a.right}`).toBe(true);
  });

  describe("the checker itself", () => {
    const check = (jsx: string, file = join(SRC, "app/t.tsx")) => describeProblems(findProblems(file, `export const T = () => (\n${jsx}\n);`));

    it("flags a closing inline element, then prose on the next line (any element type)", () => {
      expect(check(`<p>\n  Use <TrackedLink href="/a">the API</TrackedLink>\n  to fetch rows.\n</p>`)).toHaveLength(1);
      expect(check(`<p>\n  Use <code>a</code>\n  to fetch rows.\n</p>`)).toHaveLength(1);
      expect(check(`<p>\n  Use <Badge>a</Badge>\n  to fetch rows.\n</p>`)).toHaveLength(1);
    });

    it("flags an expression, then a word on the next line, and the other direction", () => {
      expect(check(`<p>\n  {n.toLocaleString("en-US")}\n  schools\n</p>`)).toHaveLength(1);
      expect(check(`<p>\n  See\n  <Link href="/a">the page</Link>\n</p>`)).toHaveLength(1);
      expect(check(`<p>\n  See\n  {name}\n</p>`)).toHaveLength(1);
      expect(check(`<p>\n  <code>233921</code>\n  for Virginia Tech\n</p>`)).toHaveLength(1);
    });

    it("counts every expression that is not a plain space literal as having no space (no inference through branches)", () => {
      expect(check(`<p>\n  First sentence.\n  {c ? "a " : "b"}\n</p>`)).toHaveLength(1);
      expect(check(`<p>\n  First sentence.\n  {c ? " a" : ""}\n</p>`)).toHaveLength(1);
      expect(check(`<p>\n  First sentence.\n  {a || " b"}\n</p>`)).toHaveLength(1);
      expect(check(`<p>\n  {label + " "}\n  rest of the line\n</p>`)).toHaveLength(1);
      expect(check(`<p>\n  {\`\${label} \`}\n  rest of the line\n</p>`)).toHaveLength(1);
      expect(check(`<p>\n  {fn()}\n  rest of the line\n</p>`)).toHaveLength(1);
      // The vanishing middle conditional: when it renders nothing, the two words touch.
      expect(check(`<p>\n  before\n  {c ? <b>x</b> : null}\n  after\n</p>`)).toHaveLength(2);
      expect(check(`<p>\n  before\n  {c && <b>x</b>}\n  after\n</p>`)).toHaveLength(2);
    });

    it("accepts a {\" \"}-style literal at the edge, in either position", () => {
      expect(check(`<p>\n  Use <code>a</code>{" "}\n  to fetch.\n</p>`)).toEqual([]);
      expect(check(`<p>\n  See{" "}\n  <Link href="/a">the page</Link>\n</p>`)).toEqual([]);
      expect(check(`<p>\n  {n}{" "}\n  schools\n</p>`)).toEqual([]);
      expect(check(`<p>\n  Sentence.\n  {" in 2025"}\n</p>`)).toEqual([]);
      expect(check("<p>\n  Sentence.\n  {` in 2025`}\n</p>")).toEqual([]);
      expect(check(`<p>\n  Sentence.{" "}\n  {c ? "a" : "b"}\n</p>`)).toEqual([]);
    });

    it("accepts same-line text, plain prose, attached punctuation and a line break element", () => {
      expect(check(`<p>Use <code>a</code> to fetch.</p>`)).toEqual([]);
      expect(check(`<p>\n  Plain prose on two\n  lines with no element.\n</p>`)).toEqual([]);
      expect(check(`<p>\n  See <a href="/a">the page</a>\n  .\n</p>`)).toEqual([]);
      expect(check(`<p>\n  Call (\n  <code>x</code>\n  )\n</p>`)).toEqual([]);
      expect(check(`<p>\n  Line one,\n  <br />\n  line two.\n</p>`)).toEqual([]);
    });

    it("flags an inline element next to an expression, inside prose, across a newline with no text between", () => {
      expect(check(`<p>\n  <strong>Note:</strong>\n  {message}\n</p>`)).toHaveLength(1);
      expect(check(`<p>\n  {message}\n  <strong>Note</strong>\n</p>`)).toHaveLength(1);
      expect(check(`<p>\n  <Link href="/a">a</Link>\n  {b}\n</p>`)).toHaveLength(1);
      // Layout is not prose: element next to element, block elements, expression next to expression, an inline pair
      // inside a div, and an explicit space are all left alone.
      expect(check(`<p>\n  <code>a</code>\n  <code>b</code>\n</p>`)).toEqual([]);
      expect(check(`<div>\n  <strong>Note:</strong>\n  {message}\n</div>`)).toEqual([]);
      expect(check(`<div>\n  <div>a</div>\n  <div>b</div>\n</div>`)).toEqual([]);
      expect(check(`<ul>\n  {a}\n  {b}\n</ul>`)).toEqual([]);
      expect(check(`<p>\n  <strong>Note:</strong>{" "}\n  {message}\n</p>`)).toEqual([]);
    });

    it("flags an entity in text, in a string literal child and in an attribute value", () => {
      expect(check(`<p>It&rsquo;s here</p>`)).toHaveLength(1);
      expect(check(`<p>Fish &amp; chips</p>`)).toHaveLength(1);
      expect(check(`<p>It&#8217;s &#x2019; here</p>`)).toHaveLength(1);
      expect(check(`<p>{"They aren&apos;t here"}</p>`)).toEqual([expect.stringContaining("entity in string")]);
      expect(check(`<p>{c ? "aren&apos;t" : null}</p>`)).toHaveLength(1);
      expect(check("<p>{`aren&apos;t ${n}`}</p>")).toHaveLength(1);
      expect(check(`<input aria-label="Don&apos;t" />`)).toHaveLength(1);
      expect(check(`<p>Use {"it’s"} here</p>`)).toEqual([]);
    });

    it("allow-list entries match one exact boundary, and never an entity", () => {
      const jsx = `<p>\n  Use <code>a</code>\n  to fetch.\n</p>`;
      const file = join(SRC, "app/t.tsx");
      const entry = { file: "app/t.tsx", kind: "newline-boundary" as const, left: "<code>a</code>", right: "to fetch.", reason: "Test only: this exact boundary is intended." };
      const run = () => describeProblems(findProblems(file, `export const T = () => (\n${jsx}\n);`));
      expect(run()).toHaveLength(1);
      ALLOWED.push(entry);
      try {
        expect(run()).toEqual([]);
        // A substring or a different boundary in the same file is not covered.
        ALLOWED.splice(0, ALLOWED.length, { ...entry, right: "to fetch" });
        expect(run()).toHaveLength(1);
        ALLOWED.splice(0, ALLOWED.length, { ...entry, left: "code" });
        expect(run()).toHaveLength(1);
        ALLOWED.splice(0, ALLOWED.length, { ...entry, file: "app/other.tsx" });
        expect(run()).toHaveLength(1);
        // An entity can't be allow-listed.
        ALLOWED.splice(0, ALLOWED.length, { ...entry, kind: "newline-boundary", left: "", right: "It&rsquo;s here" });
        expect(describeProblems(findProblems(file, `export const T = () => (\n<p>It&rsquo;s here</p>\n);`))).toHaveLength(1);
      } finally {
        ALLOWED.splice(0, ALLOWED.length);
      }
    });
  });
});
