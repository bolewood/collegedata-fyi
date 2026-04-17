"""
Tier 4 schema-targeting cleaner: map Docling markdown → canonical question numbers.

Reads the raw markdown produced by tier4_extractor.py and extracts values
for canonical CDS fields by matching table row labels against the schema's
question text. The output is a dict keyed by question_number with the
extracted value, same shape as Tier 2's values dict.

The matching is fuzzy on gender terms (men/males, women/females) because
older CDS templates use men/women while the 2025-26 schema uses
males/females. All other matching is exact substring.

This cleaner handles the pipe-delimited markdown tables Docling emits.
Non-table content (checkboxes, free text) is not extracted in V1.
"""

from __future__ import annotations

import json
import re
from pathlib import Path


def _normalize_gender(text: str) -> str:
    """Normalize gender and year-cohort terms for cross-year matching.

    Also collapses "nonresident aliens" (pre-2020 CDS) → "nonresidents"
    (2020+ CDS), and "freshman/freshmen" → "first-year" (the 2019-20
    template change that switched to gender-neutral student terminology).
    Without these rewrites, the cleaner silently misses B1/C1 on every
    CDS filed before the rename — a large slice of the historical corpus.
    """
    t = text.lower()
    t = re.sub(r'\bmales?\b', 'men', t)
    t = re.sub(r'\bfemales?\b', 'women', t)
    t = re.sub(r'\banother gender\b', 'unknown', t)
    t = re.sub(r'\bunknown gender\b', 'unknown', t)
    t = re.sub(r'\bunknown sex\b', 'unknown', t)
    t = re.sub(r'\bnonresident aliens?\b', 'nonresidents', t)
    # Pre-2020 templates: "freshmen" → "first-year". Order matters —
    # "freshmen" before "freshman" because \bfreshman\b won't match "freshmen".
    t = re.sub(r'\bfreshmen\b', 'first-year', t)
    t = re.sub(r'\bfreshman\b', 'first-year', t)
    return t


def _normalize_label(text: str) -> str:
    """Normalize a row label or substring for tolerant matching.

    Applies gender normalization, then collapses punctuation (commas,
    hyphens, en/em dashes, colons) into single spaces so variants like
    "first-time, first-year" vs "first-time first-year" vs
    "first time, first year" all compare equal. OCR and schema drift
    between schools routinely produces these variants.
    """
    t = _normalize_gender(text)
    # Strip punctuation that might appear between words in table cell
    # labels. Parentheses matter because pre-2020 CDS templates sometimes
    # include parentheticals like "first-year (freshman)" that would
    # otherwise block substring matching of "first-year men".
    t = re.sub(r'[,\-–—:;/()]', ' ', t)
    t = re.sub(r'\s+', ' ', t).strip()
    return t


def _parse_markdown_tables(markdown: str) -> list[dict]:
    """Extract every markdown table as a list of {section, rows} dicts.

    Each row is {label: str, values: list[str]} where label is the first
    column and values are the remaining columns (stripped of whitespace).
    """
    tables = []
    current_section = ""
    lines = markdown.split("\n")
    i = 0
    while i < len(lines):
        line = lines[i].strip()

        # Track section headers.
        if line.startswith("## "):
            current_section = line.lstrip("# ").strip()
            i += 1
            continue

        # Detect table start: a line starting with |
        if line.startswith("|") and "|" in line[1:]:
            # Collect all contiguous table lines.
            table_lines = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                table_lines.append(lines[i].strip())
                i += 1

            if len(table_lines) < 2:
                continue

            # Parse the nominal header row, then decide whether it's really
            # a header or a data row. Aims-style CDS tables often omit a
            # proper header — every row is one metric (e.g. "C1 ... men who
            # applied | 1368"), with a separator row after the FIRST data
            # row. Heuristic: if any non-first cell in the nominal header
            # contains digits, treat it as a data row and use a synthetic
            # empty header so row parsing doesn't drop the first data row.
            nominal_header_cells = [
                c.strip() for c in table_lines[0].split("|")[1:-1]
            ]
            header_looks_like_data = any(
                re.search(r"\d", c) for c in nominal_header_cells[1:]
            )
            if header_looks_like_data:
                header_cells = [""] * len(nominal_header_cells)
                data_start = 0
            else:
                header_cells = nominal_header_cells
                data_start = 1

            # Skip the separator row (|---|---|) wherever it appears.
            if data_start < len(table_lines) and re.match(
                r"^\|[\s\-:|]+\|$", table_lines[data_start]
            ):
                data_start += 1

            rows = []
            prev_label = ""
            for tl in table_lines[data_start:]:
                cells = [c.strip() for c in tl.split("|")[1:-1]]
                if not cells:
                    continue
                label = cells[0]
                values = cells[1:] if len(cells) > 1 else []
                has_values = any(v.strip() for v in values)

                # Continuation row (Harvard B1 pattern): empty label with
                # values inherits the previous row's label. Common when
                # Docling splits a merged cell across two markdown rows.
                if not label.strip() and has_values:
                    label = prev_label
                    rows.append({"label": label, "values": values, "headers": header_cells})
                    continue

                # Wrapped-label row (Dartmouth B1 pattern): the previous
                # row had a label but empty values, and this row has a
                # label plus values. Docling wrapped a long label onto
                # two rows. Concatenate them into a single row.
                if (
                    label.strip() and has_values and rows
                    and rows[-1]["label"].strip()
                    and not any(v.strip() for v in rows[-1]["values"])
                ):
                    merged = rows[-1]["label"] + " " + label
                    rows[-1] = {"label": merged, "values": values, "headers": header_cells}
                    prev_label = merged
                    continue

                if label.strip():
                    prev_label = label
                rows.append({"label": label, "values": values, "headers": header_cells})

            tables.append({
                "section": current_section,
                "headers": header_cells,
                "rows": rows,
            })
        else:
            i += 1

    return tables


def _extract_number(value_str: str) -> str | None:
    """Extract a numeric value from a table cell string.

    Handles: "24951", "24,951", "$85", "61%", "4.21", empty strings.
    Returns the cleaned number as a string, or None if empty/non-numeric.
    """
    s = value_str.strip()
    if not s:
        return None
    # Remove $ and % and commas.
    s = s.replace("$", "").replace("%", "").replace(",", "").strip()
    if not s:
        return None
    # Check it looks numeric.
    try:
        float(s)
        return s
    except ValueError:
        return None


# Mapping from schema question text fragments to question numbers.
# Each entry is (substring, question_number, column_hint).
#
# Substrings are written in natural form — clean() normalizes both the
# substring and the row label via _normalize_label (which lowercases,
# rewrites "another gender"→"unknown" and "male/female"→"men/women",
# strips punctuation) before comparing. So commas, hyphens, dashes, and
# gender synonyms need not be exact.
#
# column_hint selects which column to read when the row has multiple
# value columns:
#   - int: positional index into row["values"]
#   - str: substring of a header cell (e.g. "men", "percent")
#
# This table covers the high-value fields from B1, C1, B3, C9. Additional
# fields can be added incrementally with score_tier4.py as the gate.

_FIELD_MAP: list[tuple[str, str, str | int]] = [
    # --- B1 Enrollment (full-time undergrad) ---
    # "students" trailing word dropped so the substring matches both the
    # 2020+ template ("first-time, first-year students") and the pre-2020
    # template ("first-time freshmen", after the freshmen→first-year
    # rewrite in _normalize_gender drops the "students" word).
    ("degree-seeking, first-time, first-year", "B.101", "men"),
    ("degree-seeking, first-time, first-year", "B.126", "women"),
    # B.151 picks up the 2024-25 "Another Gender" column (normalized to
    # "unknown"); header-first-match semantics cause col_hint "unknown" to
    # land on the Another Gender column when both it and Unknown are present.
    ("degree-seeking, first-time, first-year", "B.151", "unknown"),
    ("other first-year, degree-seeking", "B.102", "men"),
    ("other first-year, degree-seeking", "B.127", "women"),
    ("all other degree-seeking", "B.103", "men"),
    ("all other degree-seeking", "B.128", "women"),
    ("total degree-seeking undergraduate", "B.104", "men"),
    ("total degree-seeking undergraduate", "B.129", "women"),
    ("total undergraduate full-time students", "B.106", "men"),
    ("total undergraduate full-time students", "B.131", "women"),

    # --- C1 Applications (critical) ---
    # Gendered rows: single value column. "another gender" normalizes to
    # "unknown", matching both 2024-25 and 2025-26 CDS forms.
    ("first-year men who applied", "C.101", 0),
    ("first-year women who applied", "C.102", 0),
    ("first-year another gender who applied", "C.103", 0),
    ("first-year men who were admitted", "C.104", 0),
    ("first-year women who were admitted", "C.105", 0),
    ("first-year another gender who were admitted", "C.106", 0),
    ("first-year men who enrolled", "C.107", 0),
    ("first-year women who enrolled", "C.108", 0),
    ("full-time, first-time, first-year men who enrolled", "C.110", 0),
    ("full-time, first-time, first-year women who enrolled", "C.112", 0),
    # Genderless totals (row label lacks "men/women/another gender/unknown").
    ("total first-time, first-year who applied", "C.116", 0),
    ("total first-time, first-year who were admitted", "C.117", 0),
    ("total first-time, first-year who enrolled", "C.118", 0),

    # --- B2 Race/ethnicity (first-year column) ---
    # col_hint "first-time first-year" selects the first value column of the
    # B2 race/ethnicity table. It also scopes matches to that table because
    # no other table in a CDS has that phrase in a value-column header.
    # Row ordering in the standard CDS (Hispanic/Latino precedes the
    # "non-Hispanic" rows) means first-match-wins keeps "hispanic" from
    # leaking into the non-Hispanic rows below it.
    ("nonresident", "B.201", "first-time first-year"),
    ("hispanic", "B.202", "first-time first-year"),
    ("black or african", "B.203", "first-time first-year"),
    ("white", "B.204", "first-time first-year"),
    ("american indian", "B.205", "first-time first-year"),
    ("asian", "B.206", "first-time first-year"),
    ("native hawaiian", "B.207", "first-time first-year"),
    ("two or more races", "B.208", "first-time first-year"),
    ("total", "B.210", "first-time first-year"),

    # --- B3 Degrees ---
    ("certificate/diploma", "B.301", 0),
    ("associate degrees", "B.302", 0),
    ("bachelor's degrees", "B.303", 0),
    ("postbachelor", "B.304", 0),
    ("master's degrees", "B.305", 0),
    ("post-master", "B.306", 0),
    ("doctoral degrees – research/scholarship", "B.307", 0),
    ("doctoral degrees – professional practice", "B.308", 0),
    ("doctoral degrees – other", "B.309", 0),

    # --- C10 Class rank ---
    # Clean 2-column table: Assessment | Percent.
    ("top tenth", "C.1001", 0),
    ("top quarter", "C.1002", 0),
    ("top half", "C.1003", 0),
    ("bottom half", "C.1004", 0),
    ("bottom quarter", "C.1005", 0),
    ("submitted high school class rank", "C.1006", 0),

    # --- C9 Test scores ---
    # The "Submitting" block is a 2-column table with Percent / Number
    # headers. C.901/902 → Percent column, C.903/904 → Number column.
    ("submitting sat scores", "C.901", "percent"),
    ("submitting act scores", "C.902", "percent"),
    ("submitting sat scores", "C.903", "number"),
    ("submitting act scores", "C.904", "number"),
]

# Percentile table: matched by assessment name + column position.
_PERCENTILE_MAP: list[tuple[str, int, str]] = [
    # (row_label_substring, value_column_index, question_number)
    # Column order in C9 percentile table: 25th, 50th, 75th
    ("sat composite", 0, "C.905"),       # 25th
    ("sat composite", 1, "C.906"),       # 50th
    ("sat composite", 2, "C.907"),       # 75th
    ("sat evidence-based reading", 0, "C.908"),
    ("sat evidence-based reading", 1, "C.909"),
    ("sat evidence-based reading", 2, "C.910"),
    ("sat math", 0, "C.911"),
    ("sat math", 1, "C.912"),
    ("sat math", 2, "C.913"),
    ("act composite", 0, "C.914"),
    ("act composite", 1, "C.915"),
    ("act composite", 2, "C.916"),
    ("act math", 0, "C.917"),
    ("act math", 1, "C.918"),
    ("act math", 2, "C.919"),
    ("act english", 0, "C.920"),
    ("act english", 1, "C.921"),
    ("act english", 2, "C.922"),
]


# Inline-regex patterns for fields that aren't in table rows. Each entry is
# (anchor_regex, value_capture_regex, question_number). The cleaner looks
# for anchor_regex in the markdown, then searches the next ~300 chars for
# value_capture_regex. First match wins; first-match-wins across tables +
# inline patterns is preserved (table extractions run first).
#
# The window is wide enough to span Docling's paragraph splitting — Harvard
# emits the $85 fee a few paragraphs after the "Amount of application fee:"
# label, while Yale keeps it inline. Both match.

_INLINE_PATTERNS: list[tuple[str, str, str]] = [
    # C.1302 — Amount of application fee. "$N" or "N dollars".
    (r"amount of application fee", r"\$\s*(\d+)", "C.1302"),

    # C.901 — Percent Submitting SAT Scores. Fallback for Harvard-style
    # tables where the "Submitting SAT/ACT Scores" row labels are emitted
    # as free text rather than in the first table column, so the row-based
    # extractor can't find them. The anchor is the SAT label text, the
    # window captures the first N% that follows.
    (r"submitting sat scores", r"(\d+)\s*%", "C.901"),
]


def clean(markdown: str) -> dict[str, dict]:
    """Map Docling markdown to canonical question-number-keyed values.

    Returns {question_number: {"value": str, "source": "tier4_cleaner"}}
    for every field successfully extracted.
    """
    tables = _parse_markdown_tables(markdown)
    values: dict[str, dict] = {}

    # Pre-normalize the map substrings once so _FIELD_MAP / _PERCENTILE_MAP
    # entries can be written in natural form (e.g. "another gender",
    # "first-year", "research/scholarship") — normalization is applied
    # uniformly on both sides of the substring check. String col_hints are
    # normalized too since they are matched against normalized headers.
    def _norm_hint(ch):
        return _normalize_label(ch) if isinstance(ch, str) else ch
    field_map_norm = [(_normalize_label(s), qn, _norm_hint(ch)) for s, qn, ch in _FIELD_MAP]
    percentile_map_norm = [(_normalize_label(s), ci, qn) for s, ci, qn in _PERCENTILE_MAP]

    for table in tables:
        section_norm = _normalize_label(table["section"])

        for row in table["rows"]:
            label_norm = _normalize_label(row["label"])
            headers_norm = [_normalize_label(h) for h in row.get("headers", [])]

            # --- Standard field map ---
            for substr, qnum, col_hint in field_map_norm:
                if substr not in label_norm:
                    continue

                # Determine which column to read.
                val_str = None
                if isinstance(col_hint, int):
                    if col_hint < len(row["values"]):
                        val_str = row["values"][col_hint]
                elif isinstance(col_hint, str):
                    # Find column by header substring.
                    for ci, hdr in enumerate(headers_norm):
                        if col_hint in hdr:
                            # ci is header index; values are offset by 1
                            # (first header is the label column).
                            vi = ci - 1
                            if 0 <= vi < len(row["values"]):
                                val_str = row["values"][vi]
                                break

                if val_str is None:
                    continue
                num = _extract_number(val_str)
                if num is None:
                    continue

                # Don't overwrite a more specific match.
                if qnum not in values:
                    values[qnum] = {"value": num, "source": "tier4_cleaner"}

            # --- Percentile table ---
            for substr, col_idx, qnum in percentile_map_norm:
                if substr not in label_norm:
                    continue
                if col_idx < len(row["values"]):
                    num = _extract_number(row["values"][col_idx])
                    if num and qnum not in values:
                        values[qnum] = {"value": num, "source": "tier4_cleaner"}

    # --- Inline patterns (non-table fields) ---
    # Runs after table extraction so table matches take precedence.
    md_lower = markdown.lower()
    for anchor, value_re, qnum in _INLINE_PATTERNS:
        if qnum in values:
            continue
        m = re.search(anchor, md_lower)
        if not m:
            continue
        window = markdown[m.end(): m.end() + 300]
        vm = re.search(value_re, window, re.IGNORECASE)
        if vm:
            values[qnum] = {"value": vm.group(1), "source": "tier4_cleaner"}

    return values


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Map Docling markdown to canonical CDS fields")
    parser.add_argument("markdown", type=Path, help="Path to a Docling output.md file")
    parser.add_argument("--schema", type=Path, help="Path to cds_schema JSON (for field names)")
    args = parser.parse_args()

    md = args.markdown.read_text()
    result = clean(md)

    schema_lookup = {}
    if args.schema and args.schema.exists():
        schema = json.load(args.schema.open())
        schema_lookup = {f["question_number"]: f for f in schema["fields"]}

    print(f"Extracted {len(result)} fields:\n")
    for qnum in sorted(result):
        val = result[qnum]["value"]
        field = schema_lookup.get(qnum, {})
        label = field.get("question", "")[:50]
        print(f"  {qnum:12s} = {val:>10s}   {label}")


if __name__ == "__main__":
    main()
