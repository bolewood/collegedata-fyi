"""
Subsection locator for Docling markdown output.

The Tier 4 LLM fallback targets subsection-scoped prompts (H5-H8, C13-C22,
D2-D16, G5, C11, C9). Docling renders these inconsistently across schools:

- Yale renders most as ``## H5.`` style H2 headers.
- Harvard collapses most into bullet lines like ``- C13 Application Fee``.
- Dartmouth sometimes flattens entire sections to paragraphs with no anchor.

A single-regex slicer is not enough. This module implements a layered
locator that tries strategies in order of specificity and reports which
strategy succeeded per subsection — the Phase 0 slicer-correctness report
uses that signal to catch docs where subsection scoping breaks down.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable


# ---------------------------------------------------------------------------
# Target subsections and anchor phrases.
#
# Anchor phrases are used by strategy 4 (row-label anchors) when the
# subsection code itself is missing from the markdown. Each phrase is a
# substring of the CDS question text that identifies the start of the
# subsection. Kept short and case-insensitive on match.
# ---------------------------------------------------------------------------

# Ordered set of subsection codes the fallback may attempt. Order matters
# for the bounded-window fallback: a locator for H5 uses H6 as its natural
# end boundary, so neighbours must be known.
TARGET_SUBSECTIONS: list[str] = [
    # Section B (mostly cleaner-owned; included for window boundaries)
    "B1", "B2", "B3", "B4", "B5", "B22",
    # Section C
    "C1", "C2", "C3", "C4", "C5", "C6", "C7", "C8", "C9",
    "C10", "C11", "C12", "C13", "C14", "C15", "C16", "C17",
    "C18", "C19", "C20", "C21", "C22",
    # Section D
    "D1", "D2", "D3", "D4", "D5", "D6", "D7", "D8", "D9", "D10",
    "D11", "D12", "D13", "D14", "D15", "D16",
    # Section G
    "G1", "G2", "G3", "G4", "G5", "G6",
    # Section H
    "H1", "H2", "H3", "H4", "H5", "H6", "H7", "H8", "H9", "H10",
    # Section I
    "I1", "I2", "I3",
    # Section J
    "J1", "J2", "J3",
]


# Lead-question anchor phrases for the target fallback subsections.
# Used when the subsection code does not appear in the markdown at all.
# Phrases are lowercased and matched as substrings; keep them distinctive.
ANCHOR_PHRASES: dict[str, list[str]] = {
    "C11": ["distribution of high school gpa", "high school grade point average"],
    "C13": ["application fee"],
    "C14": ["application closing date"],
    "C15": ["accepted for terms other than the fall"],
    "C16": ["notification to applicants of admission decision sent"],
    "C17": ["reply policy for admitted applicants"],
    "C18": ["deferred admission"],
    "C19": ["early admission of high school students"],
    "C21": ["early decision"],
    "C22": ["early action"],
    "D2": ["number of students who applied, were admitted, and enrolled as degree-seeking transfer"],
    "D13": ["maximum number of credits or courses that may be transferred from a two-year"],
    "D14": ["maximum number of credits or courses that may be transferred from a four-year"],
    "D15": ["transfers must complete at your institution to earn an associate degree"],
    "D16": ["transfers must complete at your institution to earn a bachelor"],
    "G5": ["provide the estimated expenses for a typical full-time undergraduate"],
    "H5": ["percent of students in class", "borrowing from federal, non-federal"],
    "H6": ["institutional scholarship and grant aid for undergraduate degree-seeking nonresidents"],
    "H7": ["financial aid forms nonresident first-year financial aid applicants"],
    "H8": ["financial aid forms domestic first-year financial aid applicants"],
}


# ---------------------------------------------------------------------------
# Locator strategies
# ---------------------------------------------------------------------------

_STRATEGY_NAMES = (
    "h2_code",          # ## H5.
    "h3_code",          # ### H5.
    "bullet_code",      # - H5. / - H5 / - **H5**
    "bold_code",        # **H5.** on its own line
    "anchor_phrase",    # lead-question substring match
    "bounded_window",   # forward-walk from nearest preceding section header
    "unresolved",       # none of the above — caller does not call the LLM
)


@dataclass
class LocatedSlice:
    """Result of locating and slicing one subsection from a markdown doc."""

    subsection: str
    strategy: str
    start_line: int | None
    end_line: int | None
    text: str

    def is_found(self) -> bool:
        return self.strategy != "unresolved" and self.text.strip() != ""


def _code_regex(code: str) -> re.Pattern[str]:
    """Code followed by end-of-string, whitespace, period, or colon.

    Handles stray whitespace like ``D14 . Maximum number...`` observed in
    Yale's output — we match ``D14`` and allow a subsequent space-dot.
    """
    return re.compile(rf"\b{re.escape(code)}\b(?:\s*[.:]|\s|$)", re.IGNORECASE)


def _strip_prefix_markers(line: str) -> str:
    """Strip leading ``##``, ``###``, ``- ``, ``**`` so we can match the code."""
    s = line.lstrip()
    for marker in ("### ", "## ", "# ", "- ", "* "):
        if s.startswith(marker):
            s = s[len(marker):].lstrip()
    # Trim leading bold markers.
    s = re.sub(r"^\*\*", "", s)
    return s


def _find_code_lines(lines: list[str], code: str) -> list[tuple[int, str]]:
    """Return all lines whose leading token (after markers) begins with the code.

    ``h2_code`` and ``bullet_code`` both reduce to "a line where the first
    token — ignoring ``##``/``-``/``**`` markers — is the subsection code".
    This helper returns all such hits; strategy selection decides which
    marker style is preferred.
    """
    code_re = _code_regex(code)
    hits: list[tuple[int, str]] = []
    for i, raw in enumerate(lines):
        stripped = _strip_prefix_markers(raw)
        # Must START with the code — not merely contain it, otherwise a
        # paragraph that references "C13" elsewhere would match.
        head = stripped[: len(code) + 8].strip()
        if code_re.match(head):
            hits.append((i, raw))
    return hits


def _find_anchor_line(lines: list[str], phrases: list[str]) -> int | None:
    for i, raw in enumerate(lines):
        lowered = raw.lower()
        for p in phrases:
            if p in lowered:
                return i
    return None


def _bounded_window_end(
    lines: list[str], start: int, next_codes: Iterable[str], max_span: int = 200
) -> int:
    """Find the end of a slice by scanning forward for the next subsection code.

    Any appearance of a subsequent target code — regardless of marker style —
    terminates the current slice. ``max_span`` caps a runaway window.
    """
    hard_stop = min(start + max_span, len(lines))
    next_regexes = [_code_regex(c) for c in next_codes]
    for j in range(start + 1, hard_stop):
        stripped = _strip_prefix_markers(lines[j])
        head = stripped[: 12].strip()
        for rx in next_regexes:
            if rx.match(head):
                return j
    return hard_stop


def _subsections_after(code: str) -> list[str]:
    """Return all target subsections that sort after ``code`` in TARGET_SUBSECTIONS."""
    try:
        idx = TARGET_SUBSECTIONS.index(code)
    except ValueError:
        return []
    return TARGET_SUBSECTIONS[idx + 1:]


def locate(markdown: str, code: str) -> LocatedSlice:
    """Locate one subsection's slice in ``markdown`` using layered strategies.

    Returns a LocatedSlice with ``strategy='unresolved'`` and empty text
    if no strategy succeeded.
    """
    lines = markdown.split("\n")
    next_codes = _subsections_after(code)

    # Strategy 1-4 funnel through _find_code_lines and then classify.
    code_hits = _find_code_lines(lines, code)
    if code_hits:
        # Pick the first hit, but prefer ## / ### / bullet / bold in that
        # order when multiple hits exist — the header style is a stronger
        # subsection-start signal than a bullet reference elsewhere.
        best_idx = _classify_and_rank(code_hits)
        start, raw = code_hits[best_idx]
        strategy = _classify_line(raw)
        end = _bounded_window_end(lines, start, next_codes)
        return LocatedSlice(
            subsection=code,
            strategy=strategy,
            start_line=start,
            end_line=end,
            text="\n".join(lines[start:end]),
        )

    # Strategy 5: row-label anchor.
    phrases = ANCHOR_PHRASES.get(code, [])
    if phrases:
        anchor = _find_anchor_line(lines, phrases)
        if anchor is not None:
            end = _bounded_window_end(lines, anchor, next_codes)
            return LocatedSlice(
                subsection=code,
                strategy="anchor_phrase",
                start_line=anchor,
                end_line=end,
                text="\n".join(lines[anchor:end]),
            )

    # Strategy 6: bounded-window from nearest preceding target code that we
    # *did* find. Walk backward through TARGET_SUBSECTIONS until we hit a
    # code that locate() can find, then take the window from its end to the
    # next code we can find.
    try:
        cur = TARGET_SUBSECTIONS.index(code)
    except ValueError:
        cur = -1
    if cur > 0:
        for prev_code in reversed(TARGET_SUBSECTIONS[:cur]):
            prev_hits = _find_code_lines(lines, prev_code)
            if not prev_hits:
                continue
            prev_start, _ = prev_hits[0]
            # End window at our code's next neighbours.
            end = _bounded_window_end(lines, prev_start, [code] + next_codes, max_span=400)
            # Only use the window if it's plausibly short enough to be our subsection.
            if 0 < end - prev_start < 250:
                return LocatedSlice(
                    subsection=code,
                    strategy="bounded_window",
                    start_line=prev_start,
                    end_line=end,
                    text="\n".join(lines[prev_start:end]),
                )
            break

    return LocatedSlice(
        subsection=code,
        strategy="unresolved",
        start_line=None,
        end_line=None,
        text="",
    )


def _classify_line(raw: str) -> str:
    """Tag a code-hit line with which marker-style matched."""
    stripped = raw.lstrip()
    if stripped.startswith("## "):
        return "h2_code"
    if stripped.startswith("### "):
        return "h3_code"
    if stripped.startswith("- ") or stripped.startswith("* "):
        return "bullet_code"
    if stripped.startswith("**"):
        return "bold_code"
    # Bare-code line (no marker): treat as bullet-equivalent for reporting.
    return "bullet_code"


def _classify_and_rank(hits: list[tuple[int, str]]) -> int:
    """Choose the index of the 'best' hit.

    Priority: h2 > h3 > bullet > bold > bare. Break ties by earliest line.
    """
    order = {"h2_code": 0, "h3_code": 1, "bullet_code": 2, "bold_code": 3}
    best = 0
    best_score = (99, 10**9)
    for idx, (line_no, raw) in enumerate(hits):
        cls = _classify_line(raw)
        score = (order.get(cls, 99), line_no)
        if score < best_score:
            best = idx
            best_score = score
    return best


def slice_all(markdown: str, codes: Iterable[str]) -> dict[str, LocatedSlice]:
    """Locate every requested subsection. Returns code → LocatedSlice."""
    return {c: locate(markdown, c) for c in codes}


# ---------------------------------------------------------------------------
# CLI — useful for eyeballing Phase 0 slicer behavior on one doc.
# ---------------------------------------------------------------------------


def _main() -> int:
    import argparse
    import sys

    ap = argparse.ArgumentParser(description=__doc__.strip().split("\n\n")[0])
    ap.add_argument("markdown_path", type=str)
    ap.add_argument(
        "--codes",
        default="H5,H6,H7,H8,C13,C14,C15,C16,C17,D2,D13,D14,D15,D16,G5",
        help="Comma-separated subsection codes to locate",
    )
    ap.add_argument("--show-text", action="store_true", help="Print slice text")
    args = ap.parse_args()

    from pathlib import Path

    md = Path(args.markdown_path).read_text()
    codes = [c.strip() for c in args.codes.split(",") if c.strip()]
    results = slice_all(md, codes)

    # Strategy-hit summary.
    from collections import Counter

    strategy_counts: Counter[str] = Counter()
    for code in codes:
        r = results[code]
        strategy_counts[r.strategy] += 1
        if r.is_found():
            lines = r.text.split("\n")
            first = lines[0][:100] if lines else ""
            print(f"  {code:5s}  {r.strategy:14s}  lines={r.start_line}-{r.end_line}  {first!r}")
        else:
            print(f"  {code:5s}  {r.strategy:14s}  NOT FOUND")

    print()
    for strat, n in sorted(strategy_counts.items(), key=lambda kv: -kv[1]):
        print(f"  {strat:14s}  {n}")

    if args.show_text:
        for code in codes:
            r = results[code]
            if r.is_found():
                print(f"\n===== {code} ({r.strategy}) =====")
                print(r.text)

    return 0


if __name__ == "__main__":
    import sys

    sys.exit(_main())
