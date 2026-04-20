"""
HTML → markdown normalizer for Tier 6 (PRD 008).

Converts CDS-shaped HTML into the pipe-delimited markdown shape that
tier4_cleaner.clean() already consumes. No schema awareness. No
question-number binding. Pure shape transformation so HTML sources
ride the existing Tier 4 extraction path without a bespoke parser.

Usage:
    from html_to_markdown import html_to_markdown
    md = html_to_markdown(html_bytes)

Size cap (MAX_HTML_BYTES) is enforced before parsing — CDS HTML pages
are well under 500 KB in practice; anything larger is almost certainly
a mis-archive.
"""

from __future__ import annotations

from io import StringIO

from bs4 import BeautifulSoup


MAX_HTML_BYTES = 5 * 1024 * 1024  # 5 MB

# Tags we drop outright. Scripts and styles never carry CDS content.
# <svg> and <noscript> are similarly noise. <iframe> and <head> likewise.
_DROP_TAGS = ("script", "style", "noscript", "svg", "iframe", "head",
              "nav", "footer", "aside", "form")


def _cell_text(cell) -> str:
    """Collapse a table cell into a single whitespace-normalized string."""
    return cell.get_text(" ", strip=True)


def _serialize_table(table) -> str:
    """Serialize a <table> as pipe-delimited markdown. Returns empty string
    for tables that look like layout (no <th>, single column) so the caller
    can skip them.
    """
    # Collect header cells. Prefer <thead> <th>; fall back to first row's
    # <th> cells; final fallback is first row treated as headers if no
    # <th> exists anywhere.
    headers: list[str] = []
    thead = table.find("thead")
    if thead is not None:
        headers = [_cell_text(c) for c in thead.find_all(["th", "td"])]

    # Collect body rows.
    body_rows: list[list[str]] = []
    tbody = table.find("tbody") or table
    for tr in tbody.find_all("tr"):
        # Skip rows that are actually the header row when thead was absent.
        cells = tr.find_all(["td", "th"])
        if not cells:
            continue
        row = [_cell_text(c) for c in cells]
        # If we still have no headers, promote the first all-<th> row to headers.
        if not headers and all(c.name == "th" for c in cells):
            headers = row
            continue
        body_rows.append(row)

    if not headers and not body_rows:
        return ""

    # If no <th> anywhere, promote first body row to headers. This is the
    # "header-less one-metric-per-row" tier4_cleaner already handles, but
    # giving it a real header line produces cleaner markdown.
    if not headers and body_rows:
        headers = body_rows[0]
        body_rows = body_rows[1:]

    # Layout-table heuristic: single-column tables with no <th> are
    # almost always spacing/layout. Skip them.
    max_cols = max(len(headers), max((len(r) for r in body_rows), default=0))
    if max_cols < 2:
        return ""

    # Pad every row to max_cols so pipe alignment survives.
    def _pad(row: list[str]) -> list[str]:
        return row + [""] * (max_cols - len(row))

    headers = _pad(headers)
    body_rows = [_pad(r) for r in body_rows]

    out = StringIO()
    out.write("| " + " | ".join(h.replace("|", r"\|") for h in headers) + " |\n")
    out.write("|" + "|".join([" --- "] * max_cols) + "|\n")
    for row in body_rows:
        out.write("| " + " | ".join(c.replace("|", r"\|") for c in row) + " |\n")
    out.write("\n")
    return out.getvalue()


def html_to_markdown(html_bytes: bytes) -> str:
    """Convert CDS-shaped HTML bytes to markdown the tier4 cleaner can consume.

    - Rejects > MAX_HTML_BYTES
    - BeautifulSoup with lxml; honors <meta charset> via from_encoding
    - Drops script/style/nav/footer/aside/svg/iframe/head/form/noscript
    - Emits <h1-6> as '### ' markdown headers (the cleaner's section regex
      anchors on the text, not heading level)
    - Emits <strong>-anchored <p> paragraphs (question anchors) as
      '**Anchor**' blocks so the cleaner's subsection detection fires
    - Serializes <table> as pipe-delimited markdown, skipping layout tables
    - Falls back to paragraph text otherwise
    """
    if len(html_bytes) > MAX_HTML_BYTES:
        raise ValueError(
            f"HTML payload {len(html_bytes)} bytes exceeds cap {MAX_HTML_BYTES}"
        )

    soup = BeautifulSoup(html_bytes, "lxml")

    # Drop noise tags in-place.
    for tag_name in _DROP_TAGS:
        for el in soup.find_all(tag_name):
            el.decompose()

    # Find the content root. WordPress pages commonly wrap content in
    # <main> or <article>; fall back to <body>.
    root = soup.find("main") or soup.find("article") or soup.body or soup

    out = StringIO()
    seen: set[int] = set()

    def _emit_heading(el) -> None:
        text = el.get_text(" ", strip=True)
        if text:
            out.write(f"### {text}\n\n")

    def _emit_paragraph(el) -> None:
        # Question-anchored paragraphs: when the first meaningful child
        # is a <strong>, emit as '**Anchor**' followed by body text. The
        # cleaner's subsection/inline patterns anchor on these.
        text = el.get_text(" ", strip=True)
        if not text:
            return
        first_strong = el.find("strong")
        if first_strong is not None and el.find(True).name == "strong":
            anchor = first_strong.get_text(" ", strip=True)
            rest = text[len(anchor):].lstrip(" :\u00a0")
            out.write(f"**{anchor}**")
            if rest:
                out.write(f" {rest}")
            out.write("\n\n")
        else:
            out.write(text + "\n\n")

    def _emit_table(el) -> None:
        md = _serialize_table(el)
        if md:
            out.write(md)

    def _walk(node) -> None:
        for child in node.find_all(
            ["h1", "h2", "h3", "h4", "h5", "h6", "p", "table",
             "ul", "ol", "li", "div"],
            recursive=True,
        ):
            cid = id(child)
            if cid in seen:
                continue
            # For tables, mark all descendants as seen so their inner
            # <p> tags don't get emitted separately.
            if child.name == "table":
                for d in child.find_all(True):
                    seen.add(id(d))
                seen.add(cid)
                _emit_table(child)
                continue
            # For <div>, only walk — don't emit container text twice.
            if child.name == "div":
                continue
            seen.add(cid)
            if child.name in ("h1", "h2", "h3", "h4", "h5", "h6"):
                _emit_heading(child)
            elif child.name == "p":
                _emit_paragraph(child)
            elif child.name in ("ul", "ol"):
                # Lists inside tables are handled by the table walk.
                items = child.find_all("li", recursive=False)
                for li in items:
                    seen.add(id(li))
                    t = li.get_text(" ", strip=True)
                    if t:
                        out.write(f"- {t}\n")
                out.write("\n")

    _walk(root)
    return out.getvalue()
