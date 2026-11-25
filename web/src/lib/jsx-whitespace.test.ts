import { readdirSync, readFileSync, statSync } from "node:fs";
import { join, relative, resolve } from "node:path";
import ts from "typescript";
import { describe, expect, it } from "vitest";

// Two ways a space between words disappears in rendered copy, both seen on the live site:
//
// 1. An HTML entity (&rsquo;, &apos;, &amp; ...) in a JSX text run that follows an inline element or a {expression}.
//    Next 16's compiler drops the run's leading space ("Not checked yet</em>means"). Vitest compiles JSX
//    differently and keeps the space, so a render test can't see it. Write the character instead of the entity.
// 2. A line break at the edge of a JSX text run. JSX trims whitespace that contains a newline, so
//    "<code>400</code>" + newline + "instead of" renders "400instead of" (and "See" + newline + "<Link>" renders
//    "SeeLink text"). Put {" "} at that edge.
//
// Both are found from the syntax tree (the TypeScript compiler API), not from lines of text, so every element type
// (span, components, TrackedLink), every expression and both directions are covered, in every component and page
// (dynamic routes too).

const SRC = resolve(__dirname, "..");

function tsxFiles(dir: string): string[] {
  return readdirSync(dir).flatMap((name) => {
    const p = join(dir, name);
    if (statSync(p).isDirectory()) return tsxFiles(p);
    return p.endsWith(".tsx") && !/\.test\.tsx$/.test(p) ? [p] : [];
  });
}

/** A boundary where the author meant no space, or CSS supplies it. Each needs a reason. Matched by file and the text run. */
type Allowed = { file: string; text: string; reason: string };
export const ALLOWED: Allowed[] = [
  {
    file: "app/usage/page.tsx",
    text: "Browser",
    reason: "Legend swatch: the <i> is a CSS line with margin-right: 6px (.usage-key i), so the label needs no space.",
  },
  { file: "app/usage/page.tsx", text: "Machine", reason: "Same legend swatch as above." },
  { file: "app/usage/page.tsx", text: "Bots and crawlers", reason: "Same legend swatch as above." },
  {
    file: "app/usage/page.tsx",
    text: "In",
    reason: "The footnote's label span (class meta) is display: block (.usage-footnote .meta), so the sentence starts on its own line.",
  },
  {
    file: "components/FeedbackForm.tsx",
    text: "I'm interested in being featured",
    reason: "The checkbox and its text sit in a flex label with gap-3, so the gap is the space.",
  },
  ...["AcceptanceYieldChart", "AlignmentGapChart", "AlignmentGapMeritChart", "YieldDebtBurdenChart"].map((c) => ({
    file: `components/${c}.tsx`,
    text: "Find a school",
    reason: "A label laid out as a flex column (gap 4): the caption sits above its input, so no space is wanted.",
  })),
  {
    file: "components/FieldsView.tsx",
    text: "TABLE",
    reason: 'A plural suffix: "{n} TABLE" + {n === 1 ? "" : "S"} is meant to read TABLES, not TABLE S.',
  },
];

/** What a node renders at its edge ("start" or "end"), as the possible strings, so a space can be seen inside an expression. */
function edgeStrings(n: ts.Node, edge: "start" | "end", source: string): string[] {
  if (ts.isJsxExpression(n)) return n.expression ? edgeStrings(n.expression, edge, source) : [];
  if (ts.isParenthesizedExpression(n)) return edgeStrings(n.expression, edge, source);
  if (ts.isStringLiteral(n) || ts.isNoSubstitutionTemplateLiteral(n)) return n.text === "" ? [] : [n.text];
  if (ts.isTemplateExpression(n)) {
    const piece = edge === "start" ? n.head.text : n.templateSpans[n.templateSpans.length - 1].literal.text;
    return piece === "" ? [] : [piece];
  }
  if (ts.isConditionalExpression(n)) return [...edgeStrings(n.whenTrue, edge, source), ...edgeStrings(n.whenFalse, edge, source)];
  if (ts.isBinaryExpression(n)) return edgeStrings(n.right, edge, source);
  if (ts.isJsxElement(n) || ts.isJsxFragment(n)) {
    // Comments and whitespace-only runs that contain a newline render nothing.
    const kids = n.children.filter(
      (c) => !(ts.isJsxExpression(c) && !c.expression) && !(ts.isJsxText(c) && c.containsOnlyTriviaWhiteSpaces && /\n/.test(source.slice(c.pos, c.end))),
    );
    const kid = edge === "start" ? kids[0] : kids[kids.length - 1];
    if (!kid) return [];
    if (ts.isJsxText(kid)) {
      const raw = source.slice(kid.pos, kid.end);
      // JSX trims a newline edge; a space edge on the same line survives.
      const rendered = edge === "start" ? raw.replace(/^\s*\n\s*/, "") : raw.replace(/\s*\n\s*$/, "");
      return rendered === "" ? [] : [rendered];
    }
    return edgeStrings(kid, edge, source);
  }
  return [];
}

const isLineBreak = (n: ts.Node | undefined) => !!n && ts.isJsxSelfClosingElement(n) && n.tagName.getText() === "br";

/** `{/* comment *​/}` renders nothing, so look past it for the real neighbour. */
const isEmptyExpression = (n: ts.Node) => ts.isJsxExpression(n) && !n.expression;

type Problem = { where: string; kind: "entity" | "lost space before" | "lost space after"; text: string };

export function findProblems(file: string, source: string): Problem[] {
  const sf = ts.createSourceFile(file, source, ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX);
  const out: Problem[] = [];
  const where = (n: ts.Node) => `${relative(SRC, file)}:${sf.getLineAndCharacterOfPosition(n.getStart(sf)).line + 1}`;

  const visit = (node: ts.Node) => {
    if (ts.isJsxElement(node) || ts.isJsxFragment(node)) {
      const kids = node.children.filter((c) => !isEmptyExpression(c));
      kids.forEach((kid, i) => {
        if (!ts.isJsxText(kid)) return;
        // getText() skips leading whitespace; the raw run is what JSX trims, so slice it from the full text.
        const raw = source.slice(kid.pos, kid.end);
        const label = raw.trim().replace(/\s+/g, " ").slice(0, 60);
        if (/&(?:[a-zA-Z][a-zA-Z0-9]*|#[0-9]+|#x[0-9a-fA-F]+);/.test(raw)) out.push({ where: where(kid), kind: "entity", text: label });
        if (kid.containsOnlyTriviaWhiteSpaces) return;
        const prev = kids[i - 1];
        const next = kids[i + 1];
        const isNode = (n: ts.Node | undefined) => !!n && !ts.isJsxText(n) && !isLineBreak(n);
        // The neighbour renders its own space, or punctuation that attaches to the word before it.
        const spaceAfterPrev = (n: ts.Node) => edgeStrings(n, "end", source).some((t) => /\s$/.test(t));
        const spaceBeforeNext = (n: ts.Node) => edgeStrings(n, "start", source).some((t) => /^[\s.,;:!?)\]}’”%]/.test(t));
        const trimmed = raw.trim();
        // Prose punctuation attaches to the word before it: "</a>" + newline + "." is meant to read "link.", and
        // "(" + newline + "<Link>" is meant to read "(Link". Only a boundary between two words loses a space.
        const startsWithClosingPunctuation = /^[.,;:!?)\]}’”%]/.test(trimmed);
        const endsWithOpeningPunctuation = /[(\[{“‘]$/.test(trimmed);
        if (/^\s*\n/.test(raw) && isNode(prev) && !spaceAfterPrev(prev!) && !startsWithClosingPunctuation) {
          out.push({ where: where(kid), kind: "lost space before", text: label });
        }
        if (/\n\s*$/.test(raw) && isNode(next) && !spaceBeforeNext(next!) && !endsWithOpeningPunctuation) {
          out.push({ where: where(kid), kind: "lost space after", text: label });
        }
      });
    }
    ts.forEachChild(node, visit);
  };
  visit(sf);
  return out.filter((p) => !ALLOWED.some((a) => p.where.startsWith(a.file + ":") && p.text.includes(a.text)));
}

const describeProblems = (ps: Problem[]) => ps.map((p) => `${p.where} ${p.kind}: ${p.text}`);

describe("JSX copy keeps the spaces between words", () => {
  const FILES = tsxFiles(SRC);

  it("finds the source files", () => {
    expect(FILES.length).toBeGreaterThan(50);
  });

  it("has no HTML entity in JSX text and no lost space at a line break, anywhere under src", () => {
    const problems = FILES.flatMap((f) => findProblems(f, readFileSync(f, "utf8")));
    expect(describeProblems(problems)).toEqual([]);
  });

  describe("the checker itself catches each shape", () => {
    const check = (jsx: string) => describeProblems(findProblems("/x/src/app/t.tsx", `export const T = () => (\n${jsx}\n);`));

    it("closing inline element, then prose on the next line", () => {
      expect(check(`<p>\n  Use <TrackedLink href="/a">the API</TrackedLink>\n  to fetch rows.\n</p>`)).toHaveLength(1);
      expect(check(`<p>\n  Use <code>a</code>\n  to fetch rows.\n</p>`)).toHaveLength(1);
    });

    it("an expression, then a word on the next line", () => {
      expect(check(`<p>\n  {n.toLocaleString("en-US")}\n  schools\n</p>`)).toHaveLength(1);
    });

    it("prose ending a line, then an element on the next (the other direction)", () => {
      expect(check(`<p>\n  See\n  <Link href="/a">the page</Link>\n</p>`)).toHaveLength(1);
      expect(check(`<p>\n  See\n  {name}\n</p>`)).toHaveLength(1);
    });

    it("a continuation line that starts with a word like 'for'", () => {
      expect(check(`<p>\n  <code>233921</code>\n  for Virginia Tech\n</p>`)).toHaveLength(1);
    });

    it("an entity in text", () => {
      expect(check(`<p>It&rsquo;s here</p>`)).toHaveLength(1);
      expect(check(`<p>Fish &amp; chips</p>`)).toHaveLength(1);
      expect(check(`<p>It&#8217;s &#x2019; here</p>`)).toHaveLength(1);
    });

    it("passes when the space is explicit, on the same line, or there is no neighbour", () => {
      expect(check(`<p>\n  Use <code>a</code>{" "}\n  to fetch.\n</p>`)).toEqual([]);
      expect(check(`<p>\n  See{" "}\n  <Link href="/a">the page</Link>\n</p>`)).toEqual([]);
      expect(check(`<p>\n  {n}{" "}\n  schools\n</p>`)).toEqual([]);
      expect(check(`<p>Use <code>a</code> to fetch.</p>`)).toEqual([]);
      expect(check(`<p>\n  Plain prose on two\n  lines with no element.\n</p>`)).toEqual([]);
      expect(check(`<p>\n  <code>a</code>\n  <code>b</code>\n</p>`)).toEqual([]);
      expect(check(`<p>Use {"it’s"} here</p>`)).toEqual([]);
    });
  });
});
