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
    """Normalize gender terms for cross-year matching."""
    t = text.lower()
    t = re.sub(r'\bmales?\b', 'men', t)
    t = re.sub(r'\bfemales?\b', 'women', t)
    t = re.sub(r'\banother gender\b', 'unknown', t)
    t = re.sub(r'\bunknown gender\b', 'unknown', t)
    t = re.sub(r'\bunknown sex\b', 'unknown', t)
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
    t = re.sub(r'[,\-–—:;/]', ' ', t)
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

            # Parse header row.
            header_cells = [c.strip() for c in table_lines[0].split("|")[1:-1]]

            # Skip separator row (|---|---|)
            data_start = 1
            if data_start < len(table_lines) and re.match(
                r"^\|[\s\-:|]+\|$", table_lines[data_start]
            ):
                data_start = 2

            rows = []
            prev_label = ""
            for tl in table_lines[data_start:]:
                cells = [c.strip() for c in tl.split("|")[1:-1]]
                if not cells:
                    continue
                label = cells[0]
                values = cells[1:] if len(cells) > 1 else []

                # Continuation row: empty label with values inherits the
                # previous row's label. Common when Docling splits a merged
                # cell across two markdown rows (Harvard B1 pattern).
                if not label.strip() and any(v.strip() for v in values):
                    label = prev_label
                elif label.strip():
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
    ("degree-seeking, first-time, first-year students", "B.101", "men"),
    ("degree-seeking, first-time, first-year students", "B.126", "women"),
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
    # uniformly on both sides of the substring check.
    field_map_norm = [(_normalize_label(s), qn, ch) for s, qn, ch in _FIELD_MAP]
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
