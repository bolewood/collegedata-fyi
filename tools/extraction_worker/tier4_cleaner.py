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

Scope: Tier 4 is optimized for 2024-25+ CDS templates. Older years are
best-effort via low-risk wording normalizations, not a separate
year-branched resolver contract.

Architecture (PRD 005):
  1. Hand-coded maps (_FIELD_MAP / _PERCENTILE_MAP / _INLINE_PATTERNS) —
     regression-safe baseline covering B1/B2/B3/C1/C9/C10/C13.
  2. SchemaIndex — lookup table built from cds_schema_2025_26.json that
     supports filtering by (section, subsection, question_norm) plus
     dimensional keys (gender, cohort, unit_load, student_group, residency,
     category). Lazy-loaded on first use.
  3. Section-family resolvers (_RESOLVERS) — each operates on the
     table slice for its section and only claims fields not already
     claimed by hand-coded maps or earlier resolvers.
"""

from __future__ import annotations

import html
import json
import re
from pathlib import Path
from typing import Any


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


_NO_WRAP_EMPTY_LABELS = {
    "sat composite",
    "sat evidence based reading and writing",
    "sat math",
    "act composite",
    "act math",
    "act english",
    "act writing",
    "act science",
    "act reading",
}


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
                    and _normalize_label(rows[-1]["label"]) not in _NO_WRAP_EMPTY_LABELS
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


# --- Schema index and section-family resolvers (PRD 005) ---

_SCHEMA_PATH = Path(__file__).resolve().parents[2] / "schemas" / "cds_schema_2025_26.json"


class SchemaIndex:
    """In-memory view of cds_schema_2025_26.json used by section-family resolvers.

    Fields are pre-normalized (_q_norm) so resolvers can match Docling row
    labels directly. Filter() is a thin keyword-driven row scan; the schema
    has only 1,105 fields so a loop is fast enough and keeps the code simple.
    """

    def __init__(self, schema_path: Path | None = None):
        path = schema_path or _SCHEMA_PATH
        data = json.loads(path.read_text())
        self.fields: list[dict[str, Any]] = data["fields"]
        for f in self.fields:
            f["_q_norm"] = _normalize_label(f.get("question", ""))

    def filter(
        self,
        *,
        section: str | None = None,
        subsection: str | None = None,
        question_norm: str | None = None,
        gender: str | None = None,
        cohort: str | None = None,
        unit_load: str | None = None,
        student_group: str | None = None,
        residency: str | None = None,
        category: str | None = None,
        pdf_tag_prefix: str | None = None,
    ) -> list[dict[str, Any]]:
        """Return schema fields matching every provided filter."""
        out = []
        for f in self.fields:
            if section is not None and f["section"] != section:
                continue
            if subsection is not None and f["subsection"] != subsection:
                continue
            if question_norm is not None and f["_q_norm"] != question_norm:
                continue
            if gender is not None and f["gender"] != gender:
                continue
            if cohort is not None and f["cohort"] != cohort:
                continue
            if unit_load is not None and f["unit_load"] != unit_load:
                continue
            if student_group is not None and f["student_group"] != student_group:
                continue
            if residency is not None and f["residency"] != residency:
                continue
            if category is not None and f["category"] != category:
                continue
            if pdf_tag_prefix is not None and not (f.get("pdf_tag") or "").startswith(pdf_tag_prefix):
                continue
            out.append(f)
        return out

    def lookup(self, **filters: Any) -> str | None:
        """Return the unique question_number matching filters, or None."""
        matches = self.filter(**filters)
        if len(matches) == 1:
            return matches[0]["question_number"]
        return None


# Module-level lazy singleton so resolvers in hot paths don't re-read the JSON.
_SCHEMA_SINGLETON: SchemaIndex | None = None


def _get_schema() -> SchemaIndex:
    global _SCHEMA_SINGLETON
    if _SCHEMA_SINGLETON is None:
        _SCHEMA_SINGLETON = SchemaIndex()
    return _SCHEMA_SINGLETON


# --- Resolver: A General Information ---

def _a_labeled_value(block: str, label: str) -> str | None:
    pattern = rf"(?im)^[ \t]*{re.escape(label)}:[ \t]*(.*?)[ \t]*$"
    match = re.search(pattern, block)
    if not match:
        target = _normalize_label(label).replace(" ", "")
        for line_match in re.finditer(r"(?m)^[ \t]*([^:\n]+):[ \t]*(.*?)[ \t]*$", block):
            line_label = _normalize_label(line_match.group(1)).replace(" ", "")
            if line_label == target:
                match = line_match
                break
        if not match:
            for line_match in re.finditer(
                rf"(?im)^[ \t]*{re.escape(label)}[ \t]{{2,}}(.+?)[ \t]*$",
                block,
            ):
                return _a_clean_value(line_match.group(1))
            spaced_label = r"\s+".join(re.escape(part) for part in label.split())
            for line_match in re.finditer(
                rf"(?im)^[ \t]*{spaced_label}[ \t]{{2,}}(.+?)[ \t]*$",
                block,
            ):
                return _a_clean_value(line_match.group(1))
            target = _normalize_label(label)
            for raw_line in block.splitlines():
                parts = re.split(r"\s{2,}", raw_line.strip(), maxsplit=1)
                if len(parts) != 2:
                    continue
                if _normalize_label(parts[0]) == target:
                    return _a_clean_value(parts[1])
            return None
    value = match.group(2 if match.lastindex and match.lastindex >= 2 else 1).strip()
    if value:
        return _a_clean_value(value)

    # Markdown exports often put the value on the next non-empty line.
    rest = block[match.end():]
    for line in rest.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if ":" in stripped:
            return None
        if stripped.lower().startswith("are your responses"):
            return None
        if stripped.startswith("- A") or stripped.startswith("## "):
            return None
        return _a_clean_value(stripped)
    return None


def _a_clean_value(value: str) -> str:
    value = html.unescape(value).strip()
    value = re.sub(r"\bA\s+VP\b", "AVP", value)
    value = re.sub(r"\bfo\s+r\b", "for", value)
    value = re.sub(r"\bI\s+R\b", "IR", value)
    value = re.sub(r"\bOffic\s+e\b", "Office", value)
    value = re.sub(r"\s+", " ", value).strip()
    return value


def _a_url_after(block: str, label_re: str) -> str | None:
    match = re.search(label_re, block, re.IGNORECASE)
    if not match:
        return None
    window = block[match.end(): match.end() + 500]
    url_match = re.search(r"https?://\S+", window)
    if not url_match:
        return None
    return url_match.group(0).rstrip(").,")


def _a_city_state_zip(value: str | None) -> tuple[str | None, str | None, str | None, str | None]:
    if not value:
        return None, None, None, None
    match = re.match(
        r"\s*(?P<city>.*?),\s*(?P<state>[A-Z]{2}|[A-Za-z .]+?)\s+"
        r"(?P<zip>\d{5}(?:-\d{4})?)(?:\s+(?P<country>.+))?\s*$",
        value,
    )
    if not match:
        return value.strip(), None, None, None
    return (
        match.group("city").strip(),
        match.group("state").strip(),
        match.group("zip").strip(),
        (match.group("country") or "").strip() or None,
    )


def _a_phone_parts(value: str | None) -> tuple[str | None, str | None, str | None]:
    if not value:
        return None, None, None
    match = re.search(
        r"(?P<area>\d{3})[-.\s]*(?P<prefix>\d{3})[-.\s]*(?P<line>\d{4})"
        r"(?:\s*(?:x|ext\.?)\s*(?P<ext>\d+))?",
        value,
        re.IGNORECASE,
    )
    if not match:
        return None, value.strip(), None
    return (
        match.group("area"),
        f"{match.group('prefix')}-{match.group('line')}",
        match.group("ext"),
    )


def _a_checked_option(block: str, options: list[str]) -> str | None:
    for raw_line in block.splitlines():
        line = raw_line.strip()
        line_norm = _normalize_label(line)
        if not re.search(r"(?<!\w)[xX](?!\w)|\[[xX]\]|[✔☒✓]", line):
            continue
        for option in options:
            if _normalize_label(option) in line_norm:
                return option
    return None


def _set_text(out: dict[str, dict], qn: str, value: str | None) -> None:
    if value is None:
        return
    value = html.unescape(value).strip()
    if value:
        out[qn] = {"value": value, "source": "tier4_cleaner"}


def resolve_a_general(
    tables: list[dict], markdown: str, schema: SchemaIndex
) -> dict[str, dict]:
    out: dict[str, dict] = {}

    a0_block = _section_between(
        markdown,
        r"\bA0\.?\s+Respondent\s+Inform\s*ation",
        r"\bA0A\b",
    )
    if a0_block:
        full_name = _a_labeled_value(a0_block, "Name")
        if full_name:
            parts = full_name.split()
            if len(parts) >= 2:
                _set_text(out, "A.001", " ".join(parts[:-1]))
                _set_text(out, "A.002", parts[-1])
            else:
                _set_text(out, "A.001", full_name)
        else:
            _set_text(out, "A.001", _a_labeled_value(a0_block, "First Name"))
            _set_text(out, "A.002", _a_labeled_value(a0_block, "Last Name"))
        _set_text(out, "A.003", _a_labeled_value(a0_block, "Title"))
        _set_text(out, "A.004", _a_labeled_value(a0_block, "Office"))
        _set_text(out, "A.005", _a_labeled_value(a0_block, "Mailing Address") or _a_labeled_value(a0_block, "Address"))
        city_state_zip = _a_labeled_value(a0_block, "City/State/Zip/Country")
        city, state, zip_code, country = _a_city_state_zip(city_state_zip)
        phone_value = _a_labeled_value(a0_block, "Phone")
        if not phone_value:
            area = _a_labeled_value(a0_block, "Phone Number")
            if area:
                phone_value = area
        fax_value = _a_labeled_value(a0_block, "Fax")
        if city_state_zip is None:
            city = _a_labeled_value(a0_block, "City")
            state = _a_labeled_value(a0_block, "State")
            zip_code = _a_labeled_value(a0_block, "Zip")
            country = _a_labeled_value(a0_block, "Country")
        if (
            city_state_zip
            and state is None
            and phone_value
            and re.fullmatch(r"[A-Za-z .]+", phone_value)
            and fax_value
            and re.fullmatch(r"\d{5}(?:-\d{4})?", fax_value)
        ):
            state = phone_value.strip()
            zip_code = fax_value.strip()
            phone_value = None
        _set_text(out, "A.008", city)
        _set_text(out, "A.009", state)
        _set_text(out, "A.010", zip_code)
        _set_text(out, "A.011", country)
        _set_text(out, "A.012", phone_value)
        _set_text(out, "A.013", _a_labeled_value(a0_block, "E-mail Address") or _a_labeled_value(a0_block, "Email Address"))
        yes_no = (
            _extract_yes_no_from_lines(_nonempty_lines(a0_block))
            or _a_checked_option(a0_block, ["Yes", "No"])
        )
        _set_text(out, "A.014", yes_no)

    _set_text(
        out,
        "A.015",
        _a_url_after(
            markdown,
            r"If yes,\s*please provide the URL of the corresponding W\s*eb page",
        ),
    )
    _set_text(
        out,
        "A.601",
        _a_url_after(
            markdown,
            r"diversity,\s*equity,\s*and inclusion office or department",
        ),
    )

    a1_block = _section_between(
        markdown,
        r"\bA1\.?\s+Address\s+Inform\s*ation",
        r"\bA2\b",
    )
    if a1_block:
        _set_text(out, "A.101", _a_labeled_value(a1_block, "Name of College/University"))
        _set_text(out, "A.102", _a_labeled_value(a1_block, "Mailing Address") or _a_labeled_value(a1_block, "Street Address"))
        city, state, zip_code, country = _a_city_state_zip(
            _a_labeled_value(a1_block, "City/State/Zip/Country")
        )
        if city is None:
            city = _a_labeled_value(a1_block, "City")
            state = _a_labeled_value(a1_block, "State")
            zip_code = _a_labeled_value(a1_block, "Zip")
            country = _a_labeled_value(a1_block, "Country")
        _set_text(out, "A.105", city)
        _set_text(out, "A.106", state)
        _set_text(out, "A.107", zip_code)
        _set_text(out, "A.108", country)
        area, main, ext = _a_phone_parts(
            _a_labeled_value(a1_block, "Main Phone Number")
            or _a_labeled_value(a1_block, "Main Institution Phone Number")
        )
        _set_text(out, "A.109", area)
        _set_text(out, "A.110", main)
        _set_text(out, "A.111", ext)
        _set_text(
            out,
            "A.112",
            _a_labeled_value(a1_block, "WWW Home Page Address")
            or _a_labeled_value(a1_block, "Main Institution Website")
            or _a_labeled_value(a1_block, "Main Institution Website"),
        )
        area, main, ext = _a_phone_parts(_a_labeled_value(a1_block, "Admissions Phone Number"))
        _set_text(out, "A.121", area)
        _set_text(out, "A.122", main)
        _set_text(out, "A.123", ext)
        _set_text(out, "A.127", _a_labeled_value(a1_block, "Admissions E-mail Address"))
        _set_text(
            out,
            "A.128",
            _a_url_after(
                a1_block,
                r"If there is a separate URL for your school.?s online application",
            ),
        )

    a2_block = _section_between(
        markdown,
        r"\bA2\b\s+Source of institutional control",
        r"\bA3\b",
    )
    _set_text(
        out,
        "A.201",
        _a_checked_option(a2_block, ["Public", "Private (nonprofit)", "Proprietary"]),
    )

    a3_block = _section_between(
        markdown,
        r"\bA3\b\s+Classify your undergraduate institution",
        r"\bA4\b",
    )
    _set_text(
        out,
        "A.301",
        _a_checked_option(a3_block, ["Coeducational college", "Men's college", "Women's college"]),
    )

    a4_block = _section_between(
        markdown,
        r"\bA4\b\s+Academ\s*ic year calendar",
        r"\bA5\b",
    )
    _set_text(
        out,
        "A.401",
        _a_checked_option(
            a4_block,
            ["Semester", "Quarter", "Trimester", "4-1-4", "Continuous"],
        ),
    )

    return out


# --- Resolver: J1 disciplines (120 fields) ---

# Column header fragments → J subsection name. Order matters for detection —
# the "TOTAL (should = 100%)" row confirms this is J1, not another table that
# happens to have "Bachelor" in a header cell.
_J_COL_TO_SUBSECTION = [
    ("diploma", "Diploma/Certificates"),
    ("associate", "Associate"),
    ("bachelor", "Bachelors"),
]


def resolve_j_disciplines(
    tables: list[dict], markdown: str, schema: SchemaIndex
) -> dict[str, dict]:
    """Map the J1 disciplines table: 40 rows × 3 value columns (Diploma,
    Associate, Bachelor's). Row label matches schema question exactly; the
    table column maps to the schema subsection.

    The CIP code column (rightmost) is ignored — integer values in the 01–60
    range would otherwise leak into the extracted output.
    """
    out: dict[str, dict] = {}

    # Pre-build per-subsection lookup: normalized question → question_number.
    section = "Disciplinary Areas of Degrees Conferred"
    lookup_by_sub = {
        sub: {f["_q_norm"]: f["question_number"]
              for f in schema.filter(section=section, subsection=sub)}
        for _, sub in _J_COL_TO_SUBSECTION
    }
    lookup_by_sub_category = {
        sub: {str(f["category"]).strip(): f["question_number"]
              for f in schema.filter(section=section, subsection=sub)}
        for _, sub in _J_COL_TO_SUBSECTION
    }
    layout_block = _section_between(
        markdown,
        r"J\.\s+Disciplinary\s+areas\s+of\s+DEGREES\s+CONFERRED|J1\b",
        r"(?:Common Data Set Definitions|CDS-J|$)",
    )
    if layout_block:
        for raw_line in layout_block.splitlines():
            line = raw_line.strip()
            if not line:
                continue
            cip_match = re.search(r"\s(?:\d{2}(?:\s+and\s+\d{2})?)\s*$", line)
            body = line[: cip_match.start()].rstrip() if cip_match else line
            nums = re.findall(r"\b\d+(?:\.\d+)?\b", body)
            if not nums:
                continue
            first_num = re.search(r"\b\d+(?:\.\d+)?\b", body)
            if not first_num:
                continue
            label_norm = _normalize_label(body[: first_num.start()])
            if not label_norm or "cip" in label_norm or "degrees conferred" in label_norm:
                continue
            if "total should" in label_norm:
                for sub, value in zip(
                    ("Diploma/Certificates", "Associate", "Bachelors"),
                    nums[-3:],
                ):
                    qn = _match_j_label(lookup_by_sub[sub], label_norm)
                    if qn:
                        out[qn] = {"value": value, "source": "tier4_cleaner"}
                continue
            if len(nums) == 1:
                qn = _match_j_label(lookup_by_sub["Bachelors"], label_norm)
                if qn:
                    out[qn] = {"value": nums[0], "source": "tier4_cleaner"}
            elif len(nums) == 2:
                qn = _match_j_label(lookup_by_sub["Diploma/Certificates"], label_norm)
                if qn:
                    out[qn] = {"value": nums[0], "source": "tier4_cleaner"}
                qn = _match_j_label(lookup_by_sub["Bachelors"], label_norm)
                if qn:
                    out[qn] = {"value": nums[1], "source": "tier4_cleaner"}

    for table in tables:
        section_norm = _normalize_label(table.get("section", ""))
        headers_norm = [_normalize_label(h) for h in table.get("headers", [])]

        # Detect J1. Two signals:
        #   (a) the section header contains "j1" or "disciplinary" — works
        #       when the markdown preserves the `## J1 ...` heading.
        #   (b) at least two of diploma/associate/bachelor tokens appear in
        #       the header row or the first data row (Docling sometimes
        #       flattens the real headers into row 0 because the CIP column
        #       contains a year like "CIP 2020", which our heuristic reads
        #       as data and thus strips the header).
        joined_hdr = " ".join(headers_norm)
        hits_hdr = sum(1 for tok, _ in _J_COL_TO_SUBSECTION if tok in joined_hdr)

        is_j_section = "j1" in section_norm or "disciplinary" in section_norm

        # If headers look empty, promote the first data row to a synthetic
        # header and skip it. Same treatment if the section flag matches —
        # that catches templates where the header/separator rows got absorbed
        # into the data rows.
        synthetic_skip = 0
        if (hits_hdr < 2 and is_j_section and table["rows"]):
            first_row = table["rows"][0]
            synthetic_cells = [first_row["label"]] + list(first_row["values"])
            synthetic_norm = [_normalize_label(c) for c in synthetic_cells]
            joined_syn = " ".join(synthetic_norm)
            hits_syn = sum(1 for tok, _ in _J_COL_TO_SUBSECTION if tok in joined_syn)
            if hits_syn >= 2:
                headers_norm = synthetic_norm
                synthetic_skip = 1
                # Also skip a follow-up separator row if present.
                if len(table["rows"]) > 1:
                    sep_label = table["rows"][1]["label"]
                    if sep_label and set(sep_label.strip()) <= {"-", ":"}:
                        synthetic_skip = 2

        if sum(1 for tok, _ in _J_COL_TO_SUBSECTION if tok in " ".join(headers_norm)) < 2:
            continue

        # Determine which value-column index maps to which subsection by
        # scanning each header. headers_norm[0] is the row-label column;
        # value index = header_index - 1.
        col_map: list[tuple[int, str]] = []
        for col_idx, hdr in enumerate(headers_norm[1:]):
            for tok, sub in _J_COL_TO_SUBSECTION:
                if tok in hdr:
                    col_map.append((col_idx, sub))
                    break
        if not col_map:
            continue

        for row in table["rows"][synthetic_skip:]:
            label_norm = _normalize_label(row["label"])
            if not label_norm:
                continue
            for col_idx, sub in col_map:
                if col_idx >= len(row["values"]):
                    continue
                num = _extract_number(row["values"][col_idx])
                if num is None:
                    continue
                qn = _match_j_cip_category(lookup_by_sub_category[sub], row)
                if qn is None:
                    qn = _match_j_label(lookup_by_sub[sub], label_norm)
                if qn and qn not in out:
                    out[qn] = {"value": num, "source": "tier4_cleaner"}

    return out


def _match_j_cip_category(lookup: dict[str, str], row: dict) -> str | None:
    """Use J1's CIP column as a row key when Docling duplicates or shifts the
    visible discipline label. Empty totals/Other rows intentionally fall back
    to label matching.
    """
    values = row.get("values", [])
    if not values:
        return None
    category = values[-1].strip()
    if not category:
        return None
    qn = lookup.get(category)
    if qn:
        return qn
    if category.isdigit():
        return lookup.get(category.zfill(2))
    return None


def _match_j_label(lookup: dict[str, str], label_norm: str) -> str | None:
    """Match a J1 row label against {question_norm: qn} in one subsection.

    Docling routinely truncates long discipline labels (e.g. J.128's
    "Homeland Security, law enforcement, firefighting, and protective services"
    gets cut at "firefighting, and"). Prefix match in either direction handles
    both truncation and schema-text-is-longer cases. Length guards prevent
    short labels like "other" from matching everything.
    """
    qn = lookup.get(label_norm)
    if qn:
        return qn
    # Blank "Other" rows can merge with the following total row in Docling's
    # markdown table parse, yielding labels like "other total should = 100%".
    # Treat those as the schema's total row; do not synthesize an Other value.
    if "total should" in label_norm:
        total_qn = lookup.get("total should = 100%")
        if total_qn:
            return total_qn
    MIN_PREFIX = 6
    if len(label_norm) < MIN_PREFIX:
        return None
    for q_norm, qn in lookup.items():
        if len(q_norm) < MIN_PREFIX:
            continue
        if q_norm.startswith(label_norm) or label_norm.startswith(q_norm):
            return qn
    return None


# --- Resolver: B2 race/ethnicity (30 fields) ---

# Column header fragments → (cohort, category) dimensional keys. Order matters:
# "total undergraduates" and "degree seeking undergraduates" are checked BEFORE
# "first time first year" because the second B2 column header in many CDS
# templates is "Degree-Seeking Undergraduates (include first-time first-year)"
# — which contains the first-year token as a parenthetical. Without this
# ordering, the second column gets mis-classified as the first-year cohort.
_B2_COLUMN_KEYS: list[tuple[str, dict[str, str]]] = [
    # Third column: total undergraduates (degree + non-degree).
    ("total undergraduates",
     {"cohort": "All", "category": "All"}),
    # Second column: degree-seeking undergraduates (includes first-year).
    ("degree seeking undergraduates",
     {"cohort": "All", "category": "Degree-seeking"}),
    # First column: degree-seeking first-time first-year.
    ("first time first year",
     {"cohort": "First-time, first-year", "category": "Degree-seeking"}),
]


def resolve_b2_race(
    tables: list[dict], markdown: str, schema: SchemaIndex
) -> dict[str, dict]:
    """Map the B2 race/ethnicity table. 10 race rows × 3 cohort columns.

    Row label matches schema `question` text (e.g. "Hispanic/Latino",
    "Two or more races, non-Hispanic"). Column header selects the dimensional
    key (cohort + category) which disambiguates the three 10-field blocks:
    B.201-B.210, B.211-B.220, B.221-B.230.
    """
    out: dict[str, dict] = {}

    section = "Enrollment And Persistence"
    subsection = "Enrollment by Racial/Ethnic Category"
    all_b2 = schema.filter(section=section, subsection=subsection)
    b2_block = _section_between(
        markdown,
        r"\bB2\b\s+Enrollment by Racial/Ethnic Category",
        r"\bB3\b\s+Number of degrees awarded",
    )
    if b2_block:
        b2_keys = [
            {"cohort": "First-time, first-year", "category": "Degree-seeking"},
            {"cohort": "All", "category": "Degree-seeking"},
            {"cohort": "All", "category": "All"},
        ]
        for raw_line in b2_block.splitlines():
            nums = re.findall(r"\b\d[\d,]*\b", raw_line)
            if len(nums) != 3:
                continue
            first_num = re.search(r"\b\d[\d,]*\b", raw_line)
            if not first_num:
                continue
            label_norm = _normalize_label(raw_line[:first_num.start()])
            qns = [_match_b2_label(all_b2, label_norm, key) for key in b2_keys]
            if not all(qns):
                continue
            for qn, raw_value in zip(qns, nums):
                value = _extract_number(raw_value)
                if qn and value is not None:
                    out[qn] = {"value": value, "source": "tier4_cleaner"}
        if out:
            return out

    for table in tables:
        headers_norm = [_normalize_label(h) for h in table.get("headers", [])]
        joined = " ".join(headers_norm)
        # Detect B2: header mentions "first-time first-year" AND race-table
        # hallmark words ("degree seeking" or "undergraduates").
        if "first time first year" not in joined and "degree seeking" not in joined:
            continue

        # Map each value column to (cohort, category) by the first matching
        # header fragment. value_index = header_index - 1.
        col_map: list[tuple[int, dict[str, str]]] = []
        for col_idx, hdr in enumerate(headers_norm[1:]):
            for frag, key in _B2_COLUMN_KEYS:
                if frag in hdr:
                    col_map.append((col_idx, key))
                    break
        if not col_map:
            continue

        # Build label → schema-field lookup scoped to this table's columns.
        # Each column has a distinct (cohort, category), so the question_norm
        # is the unique-within-column key.
        for row in table["rows"]:
            label_norm = _normalize_label(row["label"])
            if not label_norm:
                continue
            for col_idx, key in col_map:
                if col_idx >= len(row["values"]):
                    continue
                num = _extract_number(row["values"][col_idx])
                if num is None:
                    continue
                qn = _match_b2_label(all_b2, label_norm, key)
                if qn and qn not in out:
                    out[qn] = {"value": num, "source": "tier4_cleaner"}

    return out


def _match_b2_label(
    b2_fields: list[dict], label_norm: str, key: dict[str, str]
) -> str | None:
    """Find the schema field in b2_fields whose question matches the row
    label AND whose (cohort, category) matches the column key."""
    # Exact match first
    for f in b2_fields:
        if (f["_q_norm"] == label_norm
                and f["cohort"] == key["cohort"]
                and f["category"] == key["category"]):
            return f["question_number"]
    # Substring fallback — Docling sometimes drops ", non-Hispanic" suffix
    # or truncates long labels like "Native Hawaiian or other Pacific Islander".
    for f in b2_fields:
        if f["cohort"] != key["cohort"] or f["category"] != key["category"]:
            continue
        q = f["_q_norm"]
        if len(label_norm) >= 6 and (q.startswith(label_norm) or label_norm.startswith(q)):
            return f["question_number"]
    return None


# --- Resolver: B3 degrees awarded ---

_B3_LABEL_TO_QN = [
    ("certificate diploma", "B.301"),
    ("associate degrees", "B.302"),
    ("bachelor's degrees", "B.303"),
    ("bachelors degrees", "B.303"),
    ("postbachelor's certificates", "B.304"),
    ("postbachelors certificates", "B.304"),
    ("master's degrees", "B.305"),
    ("masters degrees", "B.305"),
    ("post master's certificates", "B.306"),
    ("post masters certificates", "B.306"),
    ("doctoral degrees research scholarship", "B.307"),
    ("doctoral degrees professional practice", "B.308"),
    ("doctoral degrees other", "B.309"),
]


def _match_b3_label(label_norm: str) -> str | None:
    matches = [(substr, qn) for substr, qn in _B3_LABEL_TO_QN if substr in label_norm]
    if len(matches) != 1:
        # Merged rows like "Postbachelor's certificates Master's degrees"
        # contain two schema labels but one value; the value belongs to one
        # row and cannot be assigned safely from markdown alone.
        return None
    return matches[0][1]


def resolve_b3_degrees(
    tables: list[dict], markdown: str, schema: SchemaIndex
) -> dict[str, dict]:
    out: dict[str, dict] = {}
    block = _section_between(
        markdown,
        r"\bB3\b\s+Number of degrees awarded",
        r"\bB4\b|\bB4-B21\b|Graduation Rates",
    )
    if block:
        for raw_line in block.splitlines():
            line = raw_line.strip()
            if not line:
                continue
            num_match = re.search(r"\b\d[\d,]*\b\s*$", line)
            if not num_match:
                continue
            label_norm = _normalize_label(line[:num_match.start()])
            qn = _match_b3_label(label_norm)
            if qn:
                out[qn] = {
                    "value": _extract_number(num_match.group(0)),
                    "source": "tier4_cleaner",
                }
        if out:
            return out

    for table in tables:
        section_norm = _normalize_label(table.get("section", ""))
        if "persistence" not in section_norm:
            continue
        for row in table["rows"]:
            label_norm = _normalize_label(row["label"])
            qn = _match_b3_label(label_norm)
            if not qn or not row["values"]:
                continue
            num = _extract_number(row["values"][0])
            if num is not None:
                out[qn] = {"value": num, "source": "tier4_cleaner"}
    return out


# --- Resolver: B12-B21 two-year graduation rates ---

_B_TWO_YEAR_ROW_TO_BASE = {
    "B12": 1201,
    "B13": 1301,
    "B14": 1401,
    "B15": 1501,
    "B16": 1601,
    "B17": 1701,
    "B18": 1801,
    "B19": 1901,
    "B20": 2001,
    "B21": 2101,
}


def resolve_b_two_year_rates(
    tables: list[dict], markdown: str, schema: SchemaIndex
) -> dict[str, dict]:
    out: dict[str, dict] = {}
    block = _section_between(markdown, r"For Two-Year Institutions", r"\bB22\b")
    if not block:
        return out

    for raw_line in block.splitlines():
        line = raw_line.strip()
        row_match = re.search(r"\b(B1[2-9]|B2[01])\b", line)
        if not row_match:
            continue
        row_code = row_match.group(1)
        base = _B_TWO_YEAR_ROW_TO_BASE[row_code]
        tail = line[row_match.end():]
        original_tail = tail
        if ":" in tail:
            tail = tail.rsplit(":", 1)[1]
        elif not re.search(r"\d", tail):
            continue
        # Ignore year labels in the header; values only count after the row
        # code. Blank rows remain absent.
        values = re.findall(r"(?<!\d)\d[\d,]*(?!\d)", tail)
        if not values:
            leading_values = re.match(
                r"^\s*(\d[\d,]*)(?:\s+(\d[\d,]*))?",
                original_tail,
            )
            if leading_values:
                values = [v for v in leading_values.groups() if v is not None]
        if not values:
            continue
        for offset, raw_value in enumerate(values[:2]):
            value = _extract_number(raw_value)
            if value is None:
                continue
            out[f"B.{base + offset}"] = {
                "value": value,
                "source": "tier4_cleaner",
            }

    return out


# --- Resolver: B22 retention rate (3 fields) ---

# B22 reports a single retention percentage. Some schools also fill the
# initial-cohort count (B.2201) and still-enrolled count (B.2202), but the
# 2024-25 template mostly collects just the percentage (B.2203). Docling
# renders this as free text, not a table — so we use anchored regex.

def resolve_b22_retention(
    tables: list[dict], markdown: str, schema: SchemaIndex
) -> dict[str, dict]:
    """Extract the B22 retention percentage from free-text markdown.

    The template anchor is "## B22. Retention Rates" or "- B22 For the
    cohort ...". The reported percentage appears within ~800 chars after
    either anchor (Docling places the value far below the anchor because
    intervening prose and notes are long).
    """
    out: dict[str, dict] = {}
    m = re.search(r"(?mi)^#+\s*B22\b|\bB22\b(?=[^\n]*retention|[^\n]*\bcohort\b)",
                  markdown)
    if not m:
        return out
    # Docling puts the retention % far below the anchor because the CDS
    # template interleaves long explanatory notes. Cap the window before
    # the next major section (## C.) to avoid capturing a C-section value.
    tail = markdown[m.end():]
    cap = re.search(r"(?m)^##\s", tail)
    window = tail[: (cap.start() if cap else 3000)]
    # Match a standalone percentage — either "98%" or "98.40%".
    pct = re.search(r"(\d{1,3}(?:\.\d+)?)\s*%", window)
    if pct:
        out["B.2203"] = {"value": pct.group(1), "source": "tier4_cleaner"}
    return out


# --- Resolver: B5 graduation rates (64 fields) ---
#
# B5 has two grid tables (Current Cohort and Previous Cohort) with:
#   8 rows (letters A-H, each a student_group)
#   4 value columns (Pell / Stafford / Neither / Total)
#
# Row letter → student_group dimension key:
_B5_ROW_LETTERS = {
    "A": "Initial Cohort",
    "B": "Did Not Persist",
    "C": "Final Cohort",
    "D": "Completers Less Than Four",
    "E": "Completers Less Than Five",
    "F": "Completers Less Than Six",
    "G": "Completers Total",
    "H": "Six Year Grad Rate",
}

# Fallback: some templates omit the letter prefix entirely (Dartmouth). Map
# row descriptions to letters so we can still resolve by label text. Order
# matters — "initial cohort" (A) must check before "cohort" alone, "six
# year graduation rate" (H) before "total" (G) etc.
_B5_LABEL_TO_LETTER: list[tuple[str, str]] = [
    ("six year graduation rate", "H"),
    ("total graduating within six years", "G"),
    ("completed the program in more than five years but in six", "F"),
    ("completed the program in more than four years but in five", "E"),
    ("completed the program in four years or less", "D"),
    ("final", "C"),
    ("did not persist", "B"),
    ("initial", "A"),
]

# Column index (0-3) → question-text fragment to match in schema
_B5_COL_QUESTIONS = [
    "recipients of a federal pell grant",
    "recipients of a subsidized stafford loan",
    "students who did not receive either",
    "total",
]


def _b5_layout_column_values(letter: str, values: list[str]) -> list[tuple[int, str]]:
    if len(values) >= 4:
        return list(enumerate(values[-4:]))
    if len(values) == 3 and letter == "B":
        # Some 2024 templates leave the Pell exclusions cell blank but show
        # Stafford, neither, and total. Preserve the blank instead of shifting
        # those zeros into the wrong columns.
        return [(1, values[0]), (2, values[1]), (3, values[2])]
    if len(values) == 1:
        return [(3, values[0])]
    return list(enumerate(values))


def _b5_layout_values(window: str) -> list[str]:
    best: list[str] = []
    for line in window.splitlines():
        nums = _h_spaced_numbers(line)
        if len(nums) >= 3:
            return nums
        if len(nums) > len(best):
            best = nums
    return best


def _b5_row_window(block: str, letter: str) -> str:
    lines = block.splitlines()
    start = None
    for idx, line in enumerate(lines):
        if re.match(rf"\s*{letter}(?:\s{{2,}}|$)", line):
            start = idx
            break
    if start is None:
        return ""
    end = len(lines)
    for idx in range(start + 1, len(lines)):
        if re.match(r"\s*[A-H](?:\s{2,}|$)", lines[idx]):
            end = idx
            break
    return "\n".join(lines[start:end])


def _resolve_b5_layout(markdown: str) -> dict[str, dict]:
    out: dict[str, dict] = {}
    cohort_matches = list(re.finditer(r"(?mi)^\s*Fall\s+20\d\d\s+Cohort\b", markdown))
    if not cohort_matches:
        return out

    for cohort_idx, match in enumerate(cohort_matches[:2]):
        base = 401 if cohort_idx == 0 else 501
        end = cohort_matches[cohort_idx + 1].start() if cohort_idx + 1 < len(cohort_matches) else len(markdown)
        block = markdown[match.end():end]
        if cohort_idx == 1:
            two_year = re.search(r"For Two-Year Institutions", block, re.IGNORECASE)
            if two_year:
                block = block[:two_year.start()]

        for row_idx, letter in enumerate("ABCDEFGH"):
            window = _b5_row_window(block, letter)
            if not window:
                continue
            nums = _b5_layout_values(window)
            if not nums:
                continue
            row_base = base + row_idx * 4
            for col_idx, value in _b5_layout_column_values(letter, nums):
                if col_idx > 3:
                    continue
                out[f"B.{row_base + col_idx}"] = {
                    "value": value,
                    "source": "tier4_cleaner",
                }

    return out


def _is_b5_grad_table(table: dict) -> bool:
    """Detect a Fall YYYY Cohort grad-rate table by section header."""
    section_norm = _normalize_label(table.get("section", ""))
    return "cohort" in section_norm and (
        "fall" in section_norm or re.search(r"\b20\d\d\b", section_norm) is not None
    )


def resolve_b5_graduation(
    tables: list[dict], markdown: str, schema: SchemaIndex
) -> dict[str, dict]:
    """Map Fall <year> Cohort grad-rate tables to B.4xx (current) and
    B.5xx (previous) question numbers.

    The first grad table seen in the markdown is the current cohort; the
    second is the previous cohort. Schools that report only one cohort get
    just the current (B.4xx) slot filled.

    Row/column handling absorbs two Docling layouts:
      1. label = "A" (letter only), values[0] = description, values[1-4] = data
      2. label = "A Initial 2018 cohort ...", values[0-3] = data
    """
    out: dict[str, dict] = _resolve_b5_layout(markdown)
    if out:
        return out

    grad_tables = [t for t in tables if _is_b5_grad_table(t)]
    if not grad_tables:
        return out

    # Build lookup: (cohort_key, student_group, col_q_fragment) → qn
    def _lookup(cohort_key: str, sg: str, col_q: str) -> str | None:
        for f in schema.filter(
            subsection="Graduation Rates",
            cohort=cohort_key,
            student_group=sg,
            category="Four Year",
        ):
            if col_q in f["_q_norm"]:
                return f["question_number"]
        return None

    # Only the first two grad tables count (current + previous). Others are
    # extra Docling fragments of the same table and get merged by position.
    # We track "which letters we've seen in this cohort" so continuation
    # tables can fill missing rows without double-writing.
    cohort_keys = ["Current Cohort", "Previous Cohort"]
    cohort_idx = 0
    seen_letters: set[str] = set()

    for table in grad_tables:
        if cohort_idx >= len(cohort_keys):
            break
        ckey = cohort_keys[cohort_idx]

        new_letters_in_table = 0
        for row in table["rows"]:
            label = row["label"].strip()
            label_norm = _normalize_label(label)
            letter = None
            value_offset = 0
            # Case 1: label is just a letter.
            if label in _B5_ROW_LETTERS:
                letter = label
                value_offset = 1  # values[0] is the description
            else:
                # Case 2: label starts with "A ", "B Of the ...", etc.
                m = re.match(r"^([A-H])\b", label)
                if m:
                    letter = m.group(1)
                    value_offset = 0
                else:
                    # Case 3 (Dartmouth): no letter prefix, identify by
                    # description text.
                    for frag, ltr in _B5_LABEL_TO_LETTER:
                        if frag in label_norm:
                            letter = ltr
                            value_offset = 0
                            break
                    if letter is None:
                        continue

            if letter in seen_letters:
                # Already recorded this row in an earlier fragment — skip
                # but don't advance cohort yet: we're still in the same one.
                continue

            sg = _B5_ROW_LETTERS[letter]
            for col_idx, col_q in enumerate(_B5_COL_QUESTIONS):
                val_idx = value_offset + col_idx
                if val_idx >= len(row["values"]):
                    continue
                num = _extract_number(row["values"][val_idx])
                if num is None:
                    continue
                qn = _lookup(ckey, sg, col_q)
                if qn and qn not in out:
                    out[qn] = {"value": num, "source": "tier4_cleaner"}
            seen_letters.add(letter)
            new_letters_in_table += 1

        # If this table added no new rows AND we already have at least one
        # letter from the current cohort, it's probably a continuation
        # fragment. Otherwise (we saw letter H, or we hit a new "Fall YYYY"
        # section), advance to the previous cohort.
        if "H" in seen_letters:
            cohort_idx += 1
            seen_letters = set()


    return out


# --- Resolver: B1 Institutional Enrollment (75 fields) ---
#
# One big table with sub-tables concatenated. Docling leaves the sub-table
# dividers as row labels ("Undergraduate Students: Full-Time") instead of
# new `##` headers, so the resolver must track (unit_load, student_group)
# context as rows are scanned.
#
# Column index (0-3) → gender:
#   0 = Males, 1 = Females, 2 = Unknown (from "Another Gender" column),
#   3 = ignored (second "Unknown" column duplicates data for Unknown gender
#       in the 2024-25 template; the schema collapses both into one field).
_B1_COL_GENDER = ["Males", "Females", "Unknown"]

# Context-change patterns. Order matters — longest match first so
# "undergraduate students full time" takes priority over "undergraduate
# students" alone.
_B1_CONTEXT_RULES: list[tuple[str, str, str]] = [
    # (label substring [normalized], unit_load, student_group)
    ("undergraduate students full time",  "FT",  "Undergraduates"),
    ("undergraduate students part time",  "PT",  "Undergraduates"),
    ("undergraduate students all",        "All", "Undergraduates"),
    ("graduate students full time",       "FT",  "Graduates"),
    ("graduate students part time",       "PT",  "Graduates"),
    ("graduate students all",             "All", "Graduates"),
    ("all students total",                "All", "All Students"),
    ("all students all",                  "All", "All Students"),
]

# Row-label → (cohort, category) map. Order matters: more-specific rules
# come first so that e.g. "degree seeking first time first year" isn't
# shadowed by the later "degree seeking first time" (graduate-specific).
_B1_ROW_RULES: list[tuple[str, str, str]] = [
    ("degree seeking first time first year", "First-time, first-year", "Degree-seeking"),
    ("other first year degree seeking",       "Other first-year",       "Degree-seeking"),
    ("all other degree seeking",              "All other",              "Degree-seeking"),
    ("total degree seeking",                  "Total",                  "Degree-seeking"),
    ("all other undergraduates enrolled",     "All other",              "Enrolled in Credit Courses"),
    ("all other graduates enrolled",          "All other",              "Enrolled in Credit Courses"),
    ("degree seeking first time",             "First-time",             "Degree-seeking"),  # graduates-only
    # Rollup totals. "Total" sums by unit_load are disambiguated by the
    # current context (FT / PT / All).
    ("total undergraduate full time students", "Total", "All"),
    ("total undergraduate part time students", "Total", "All"),
    ("total undergraduate students",           "Total", "All"),
    ("total graduate full time students",      "Total", "All"),
    ("total graduate part time students",      "Total", "All"),
    ("total graduate students",                "Total", "All"),
    ("total all students",                     "Total", "All"),
]


def _match_b1_row(label_norm: str) -> tuple[str, str] | None:
    """Pick the first row rule whose substring matches the label."""
    for substr, cohort, category in _B1_ROW_RULES:
        if substr in label_norm:
            return cohort, category
    return None


def _match_b1_context(label_norm: str) -> tuple[str, str] | None:
    """Pick the first context rule whose substring matches the label."""
    for substr, unit_load, student_group in _B1_CONTEXT_RULES:
        if substr in label_norm:
            return unit_load, student_group
    return None


def _b1_rollup_qn(label_norm: str) -> str | None:
    if "grand total all students" in label_norm:
        return "B.178"
    if "total all undergraduates" in label_norm:
        return "B.176"
    if "total all graduate" in label_norm:
        return "B.177"
    return None


def _resolve_b1_layout(markdown: str, schema: SchemaIndex) -> dict[str, dict]:
    """Layout-backed B1 parser.

    The pypdf layout text keeps B1's columns visually aligned even when
    Docling's markdown table wraps labels into separate rows or drops empty
    cells. We still resolve through schema.lookup so the mapping stays tied
    to the canonical B1 dimensions.
    """
    out: dict[str, dict] = {}
    block = _section_between(
        markdown,
        r"\bB1\b\s+Institutional Enrollment",
        r"\bB2\b\s+Enrollment by Racial/Ethnic Category",
    )
    if not block:
        return out

    unit_load: str | None = None
    student_group: str | None = None
    pending_label = ""

    for raw_line in block.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        line_norm = _normalize_label(line)

        ctx = _match_b1_context(line_norm)
        if ctx:
            unit_load, student_group = ctx
            pending_label = ""
            continue

        nums = re.findall(r"\b\d[\d,]*\b", line)
        if not nums:
            if unit_load is not None and (
                line_norm.startswith("degree seeking")
                or line_norm.startswith("all other")
                or line_norm.startswith("total")
                or line_norm.startswith("grand total")
                or line_norm in ("students", "courses")
            ):
                pending_label = f"{pending_label} {line}".strip()
            continue

        first_num = re.search(r"\b\d[\d,]*\b", line)
        if not first_num:
            continue
        label = line[:first_num.start()].strip()
        if pending_label:
            # Blank rows sometimes precede the next total row. If the next
            # numeric row is itself a total, the pending wrapped label had no
            # value and should not be merged into the total label.
            if _normalize_label(label).startswith(("total ", "grand total")):
                pending_label = ""
            else:
                label = f"{pending_label} {label}".strip()
            pending_label = ""
        label_norm = _normalize_label(label)

        rollup_qn = _b1_rollup_qn(label_norm)
        if rollup_qn and nums:
            out[rollup_qn] = {
                "value": _extract_number(nums[0]),
                "source": "tier4_cleaner",
            }
            continue

        if unit_load is None or student_group is None:
            continue
        row_rule = _match_b1_row(label_norm)
        if not row_rule:
            continue
        cohort, category = row_rule

        local_ul = unit_load
        local_sg = student_group
        if "total undergraduate full time" in label_norm:
            local_ul, local_sg = "FT", "Undergraduates"
        elif "total undergraduate part time" in label_norm:
            local_ul, local_sg = "PT", "Undergraduates"
        elif "total undergraduate students" in label_norm:
            local_ul, local_sg = "All", "Undergraduates"
        elif "total graduate full time" in label_norm:
            local_ul, local_sg = "FT", "Graduates"
        elif "total graduate part time" in label_norm:
            local_ul, local_sg = "PT", "Graduates"
        elif "total graduate students" in label_norm:
            local_ul, local_sg = "All", "Graduates"
        elif "total all students" in label_norm:
            local_ul, local_sg = "All", "All Students"

        col_values: list[tuple[str, str]] = []
        if len(nums) >= 1:
            col_values.append(("Males", nums[0]))
        if len(nums) >= 2:
            col_values.append(("Females", nums[1]))
        if len(nums) >= 3:
            # The 2024-25 table has both Another Gender and Unknown columns,
            # while the canonical schema has one Unknown bucket. Use the
            # Another Gender value when present; the fourth PDF column is only
            # a fallback in templates where the third column is absent.
            col_values.append(("Unknown", nums[2]))

        for gender, raw_value in col_values:
            num = _extract_number(raw_value)
            if num is None:
                continue
            qn = schema.lookup(
                subsection="Institutional Enrollment",
                gender=gender,
                unit_load=local_ul,
                student_group=local_sg,
                cohort=cohort,
                category=category,
            )
            if (
                qn is None
                and local_sg == "Undergraduates"
                and local_ul == "All"
                and cohort == "Total"
                and category == "All"
            ):
                qn = schema.lookup(
                    subsection="Institutional Enrollment",
                    gender=gender,
                    unit_load=local_ul,
                    student_group=local_sg,
                    cohort="Total understand",
                    category=category,
                )
            if (
                qn is None
                and local_sg == "Graduates"
                and local_ul == "FT"
                and cohort == "Total"
                and category == "All"
            ):
                qn = schema.lookup(
                    subsection="All",
                    gender=gender,
                    unit_load=local_ul,
                    student_group=local_sg,
                    cohort=cohort,
                    category="Full-Time",
                )
            if (
                qn is None
                and local_sg == "Undergraduates"
                and local_ul == "PT"
                and cohort == "All other"
                and category == "Enrolled in Credit Courses"
            ):
                # The 2025-26 schema labels the PT undergraduate credit-course
                # row's cohort as "All other undergraduates", while the FT row
                # uses "All other".
                qn = schema.lookup(
                    subsection="Institutional Enrollment",
                    gender=gender,
                    unit_load=local_ul,
                    student_group=local_sg,
                    cohort="All other undergraduates",
                    category=category,
                )
            if qn:
                out[qn] = {"value": num, "source": "tier4_cleaner"}

    return out


def resolve_b1_enrollment(
    tables: list[dict], markdown: str, schema: SchemaIndex
) -> dict[str, dict]:
    """Map the B1 institutional enrollment matrix.

    The table has 4 value columns (Men / Women / Another Gender / Unknown)
    and rows grouped into sub-tables separated by "XYZ Students: Full-Time"
    divider rows. A divider row updates (unit_load, student_group) context;
    data rows then resolve to a unique schema field using
    (gender, unit_load, student_group, cohort, category).

    Docling sometimes concatenates a divider with the next row's label
    (e.g. "Graduate Students: Full-Time Degree-seeking, first-time"). The
    resolver handles this by scanning for BOTH context and row rules on
    every label and using whichever fires.
    """
    out: dict[str, dict] = _resolve_b1_layout(markdown, schema)
    if "B.178" in out:
        return out

    # Detect B1 tables by section name or by gendered column headers.
    b1_tables: list[dict] = []
    for t in tables:
        section_norm = _normalize_label(t.get("section", ""))
        headers_norm = [_normalize_label(h) for h in t.get("headers", [])]
        joined_hdr = " ".join(headers_norm)
        if "b1" in section_norm or "institutional enrollment" in section_norm:
            b1_tables.append(t)
            continue
        if "men" in joined_hdr and "women" in joined_hdr and (
            "another gender" in joined_hdr or "unknown" in joined_hdr
        ):
            b1_tables.append(t)

    if not b1_tables:
        return out

    # The B1 data typically lives in the first qualifying table; subsequent
    # ones (e.g. a "Part-Time" fragment) are appended as continuations.
    unit_load: str | None = None
    student_group: str | None = None

    for table in b1_tables:
        # Section header or column headers may advertise the (unit_load,
        # student_group) context — some schools put each sub-table behind
        # its own `## Undergraduate Students: Full-Time` heading (Yale),
        # others concatenate everything into one table with divider rows
        # (Harvard). Check both.
        section_norm = _normalize_label(table.get("section", ""))
        sec_ctx = _match_b1_context(section_norm)
        if sec_ctx:
            unit_load, student_group = sec_ctx
        hdr_joined = " ".join(_normalize_label(h) for h in table.get("headers", []))
        hdr_ctx = _match_b1_context(hdr_joined)
        if hdr_ctx:
            unit_load, student_group = hdr_ctx

        for row in table["rows"]:
            label_norm = _normalize_label(row["label"])
            if not label_norm:
                continue

            # A row can carry context AND data simultaneously (Docling merges
            # the divider into the next line). Scan both.
            ctx = _match_b1_context(label_norm)
            if ctx:
                unit_load, student_group = ctx

            if unit_load is None or student_group is None:
                continue

            row_rule = _match_b1_row(label_norm)
            if not row_rule:
                continue
            cohort, category = row_rule

            # Some rollup "Total" rules imply a particular (unit_load,
            # student_group) themselves — overwrite the running context for
            # this row only so the schema lookup lands on the right field.
            local_ul = unit_load
            local_sg = student_group
            if "total undergraduate full time" in label_norm:
                local_ul, local_sg = "FT", "Undergraduates"
            elif "total undergraduate part time" in label_norm:
                local_ul, local_sg = "PT", "Undergraduates"
            elif "total undergraduate students" in label_norm:
                local_ul, local_sg = "All", "Undergraduates"
            elif "total graduate full time" in label_norm:
                local_ul, local_sg = "FT", "Graduates"
            elif "total graduate part time" in label_norm:
                local_ul, local_sg = "PT", "Graduates"
            elif "total graduate students" in label_norm:
                local_ul, local_sg = "All", "Graduates"
            elif "total all students" in label_norm:
                local_ul, local_sg = "All", "All Students"

            for col_idx, gender in enumerate(_B1_COL_GENDER):
                if col_idx >= len(row["values"]):
                    continue
                num = _extract_number(row["values"][col_idx])
                if num is None:
                    continue
                qn = schema.lookup(
                    subsection="Institutional Enrollment",
                    gender=gender,
                    unit_load=local_ul,
                    student_group=local_sg,
                    cohort=cohort,
                    category=category,
                )
                if qn and qn not in out:
                    out[qn] = {"value": num, "source": "tier4_cleaner"}

    return out


# --- Resolver: C1 Applications (30 fields) ---
#
# Four logical tables in Docling output:
#   1. Applicants (gender rows, single value column)
#   2. Admits (gender rows, single value column)
#   3. Enrollees by Status (FT/PT × gender rows, single value column)
#   4. Residency breakdown (applied/admitted/enrolled rows × In-State/
#      Out-of-State/International/Unknown/Total columns)
#
# Existing hand-coded _FIELD_MAP claims C.101-C.118 for the clean cases;
# this resolver adds the residency fields (C.119-C.130) and the PT/Unknown
# gendered enrolled cells that the hand-coded map doesn't cover.

_C1_RESIDENCY_COLS: list[tuple[str, str]] = [
    # Order matters for substring precedence: "out of state" before
    # "state", "international" isolated, etc. "total" is distinguished by
    # being the only one-word header so it ranks last to avoid swallowing
    # "total undergraduates" in other tables.
    ("in state",     "In-State"),
    ("out of state", "Out-of-State"),
    ("international", "Nonresidents"),
    ("unknown",      "Unknown"),
    ("total",        "All"),  # gender=All + residency=All dimension bundle
]

# Action keyword (extracted from row label) → question-text substring used
# to disambiguate applied/admitted/enrolled within a (gender, residency)
# bucket. The schema stores the action in the question text itself.
_C1_ACTIONS: list[tuple[str, str]] = [
    ("who were admitted", "admitted"),
    ("who applied",       "applied"),
    ("who enrolled",      "enrolled"),
]


def _c1_multiple_action_hits(label_norm: str) -> bool:
    """Detect Docling row-merge artefacts. A label with two "applied" or
    two "who enrolled" substrings has concatenated two rows — its single
    value column belongs to *one* of them but we can't tell which, so we
    skip rather than guess."""
    hits = sum(label_norm.count(kw) for kw, _ in _C1_ACTIONS)
    return hits > 1


def resolve_c1_applications(
    tables: list[dict], markdown: str, schema: SchemaIndex
) -> dict[str, dict]:
    out: dict[str, dict] = {}

    c1_fields = schema.filter(subsection="Applications")

    def _lookup(gender: str, residency: str, action: str,
                unit_load: str = "All") -> str | None:
        for f in c1_fields:
            if f["gender"] != gender:
                continue
            if f["residency"] != residency:
                continue
            if f["unit_load"] != unit_load:
                continue
            if action in f["_q_norm"]:
                return f["question_number"]
        return None

    for table in tables:
        headers_norm = [_normalize_label(h) for h in table.get("headers", [])]
        joined_hdr = " ".join(headers_norm)

        # --- Residency breakdown table detection ---
        is_residency = ("in state" in joined_hdr
                        and "out of state" in joined_hdr)

        # --- Gendered-row table detection ---
        gender_hits = 0
        for r in table["rows"][:10]:
            ln = _normalize_label(r["label"])
            if any(tok in ln for tok in ("men who", "women who",
                                          "another gender who",
                                          "unknown gender who")):
                gender_hits += 1
        is_gender_table = gender_hits >= 1

        if is_residency:
            # Map each value column index → residency key.
            col_to_res: list[tuple[int, str]] = []
            for ci, hdr in enumerate(headers_norm[1:]):
                for tok, res in _C1_RESIDENCY_COLS:
                    if tok in hdr:
                        col_to_res.append((ci, res))
                        break
            for row in table["rows"]:
                label_norm = _normalize_label(row["label"])
                if _c1_multiple_action_hits(label_norm):
                    continue
                action = None
                for kw, akey in _C1_ACTIONS:
                    if kw in label_norm:
                        action = akey
                        break
                if not action:
                    continue
                for col_idx, res in col_to_res:
                    if col_idx >= len(row["values"]):
                        continue
                    num = _extract_number(row["values"][col_idx])
                    if num is None:
                        continue
                    qn = _lookup("All", res, action)
                    if qn and qn not in out:
                        out[qn] = {"value": num, "source": "tier4_cleaner"}

        elif is_gender_table:
            for row in table["rows"]:
                label_norm = _normalize_label(row["label"])
                if _c1_multiple_action_hits(label_norm):
                    continue

                # Gender detection — use word boundaries so "women who"
                # doesn't match "men who".
                gender = None
                if re.search(r"\bmen who\b", label_norm):
                    gender = "Males"
                elif re.search(r"\bwomen who\b", label_norm):
                    gender = "Females"
                elif re.search(r"\b(another gender|unknown gender) who\b",
                                label_norm):
                    gender = "Unknown"
                if gender is None:
                    continue

                action = None
                for kw, akey in _C1_ACTIONS:
                    if kw in label_norm:
                        action = akey
                        break
                if not action:
                    continue

                # Determine unit_load for enrolled rows. For
                # applied/admitted the schema uses unit_load=All regardless
                # of any "full-time" wording — skip the FT/PT check there.
                unit_load = "All"
                if action == "enrolled":
                    if "full time" in label_norm:
                        unit_load = "FT"
                    elif "part time" in label_norm:
                        unit_load = "PT"
                    else:
                        # C.107-C.109 (gender-only, no FT/PT) — use All.
                        unit_load = "All"

                if not row["values"]:
                    continue
                num = _extract_number(row["values"][0])
                if num is None:
                    continue
                qn = _lookup(gender, "All", action, unit_load=unit_load)
                if qn and qn not in out:
                    out[qn] = {"value": num, "source": "tier4_cleaner"}

    return out


# --- Resolver: C2 Wait List ---
#
# C.201 is a Yes/No checkbox above the numeric waiting-list table. C.205-C.207
# are lower-page follow-ups and are handled separately when visible.

_C2_NUMERIC_ROW_RULES: list[tuple[str, str]] = [
    ("number of qualified applicants offered",  "C.202"),
    ("number accepting a place",                "C.203"),
    ("number of wait listed students admitted", "C.204"),
]


def resolve_c2_waitlist(
    tables: list[dict], markdown: str, schema: SchemaIndex
) -> dict[str, dict]:
    out: dict[str, dict] = {}

    waitlist_block = _section_between(
        markdown,
        r"\bC2\b\s+First-time,\s*first-year wait-listed students",
        r"(?m)^\s*(?:C3\b|C3-C5\b|##\s+C3)",
    )
    if waitlist_block:
        c201 = _extract_yes_no_by_layout(
            waitlist_block,
            r"Do you have a policy of placing students on a waiting list\?",
        )
        if not c201:
            c201 = _extract_yes_no_from_lines(_nonempty_lines(waitlist_block))
        if c201:
            out["C.201"] = {"value": c201, "source": "tier4_cleaner"}
        for line in waitlist_block.splitlines():
            label_norm = _normalize_label(line)
            for substr, qn in _C2_NUMERIC_ROW_RULES:
                if substr not in label_norm:
                    continue
                nums = re.findall(r"\b\d[\d,]*\b", line)
                if nums:
                    out.setdefault(
                        qn,
                        {
                            "value": _extract_number(nums[-1]),
                            "source": "tier4_cleaner",
                        },
                    )
                break

    for table in tables:
        headers_norm = [_normalize_label(h) for h in table.get("headers", [])]
        if "waiting list" not in " ".join(headers_norm):
            continue
        for row in table["rows"]:
            label_norm = _normalize_label(row["label"])
            for substr, qn in _C2_NUMERIC_ROW_RULES:
                if substr not in label_norm:
                    continue
                if not row["values"]:
                    continue
                num = _extract_number(row["values"][0])
                if num is None:
                    continue
                if qn not in out:
                    out[qn] = {"value": num, "source": "tier4_cleaner"}
                break
    return out


# --- Resolver: C5 Carnegie units (25 fields) ---
#
# Two-column table: Required | Recommended, keyed by subject row
# (English, Mathematics, ...). The schema's `category` dimension is
# "High School Units Required" vs "High School Units Recommended".

_C5_SUBJECTS = [
    # (row substring [normalized], question text in schema)
    ("total academic units",    "Total academic units"),
    ("english",                 "English"),
    ("mathematics",             "Mathematics"),
    ("foreign language",        "Foreign language"),
    ("computer science",        "Computer Science"),
    ("science",                 "Science"),
    ("units that must be lab",  "Of these, units that must be lab"),
    ("social studies",          "Social studies"),
    ("history",                 "History"),
    ("academic electives",      "Academic electives"),
    ("visual performing arts",  "Visual/Performing Arts"),
    ("other",                   "Other (specify)"),
]


def resolve_c5_carnegie_units(
    tables: list[dict], markdown: str, schema: SchemaIndex
) -> dict[str, dict]:
    """Map C5 distribution of high school units.

    Docling variants:
      (a) Two-column table with headers "Required" and "Recommended".
      (b) Single-column table with header "Units" — the school only fills
          one side (treat as required unless the markdown has a clear
          "recommended" context).
    """
    out: dict[str, dict] = {}

    req_fields = {_normalize_label(f["question"]): f["question_number"]
                  for f in schema.filter(category="High School Units Required")}
    rec_fields = {_normalize_label(f["question"]): f["question_number"]
                  for f in schema.filter(category="High School Units Recommended")}

    for table in tables:
        headers_norm = [_normalize_label(h) for h in table.get("headers", [])]
        joined_hdr = " ".join(headers_norm)
        # Detect C5: rows should include the hallmark subject labels.
        has_subjects = 0
        for row in table["rows"]:
            ln = _normalize_label(row["label"])
            for sub, _ in _C5_SUBJECTS[:4]:
                if sub in ln:
                    has_subjects += 1
                    break
        if has_subjects < 2:
            continue

        # Map each value column → category dimension.
        col_to_cat: list[tuple[int, str]] = []
        for ci, hdr in enumerate(headers_norm[1:]):
            if "required" in hdr:
                col_to_cat.append((ci, "Required"))
            elif "recommend" in hdr:
                col_to_cat.append((ci, "Recommended"))
            elif "units" in hdr and not col_to_cat:
                # Single-column layout — treat as Required unless surrounding
                # context says otherwise.
                col_to_cat.append((ci, "Required"))

        if not col_to_cat:
            continue

        for row in table["rows"]:
            label_norm = _normalize_label(row["label"])
            # Find the matching subject. Order matters: "science" must
            # check before "computer science" is seen, so the more
            # specific "computer science" rule wins via rule ordering.
            subject_q = None
            for sub, q in _C5_SUBJECTS:
                if sub in label_norm:
                    subject_q = q
                    break
            if not subject_q:
                continue
            subject_norm = _normalize_label(subject_q)
            for col_idx, cat_key in col_to_cat:
                if col_idx >= len(row["values"]):
                    continue
                num = _extract_number(row["values"][col_idx])
                if num is None:
                    continue
                target = req_fields if cat_key == "Required" else rec_fields
                qn = target.get(subject_norm)
                if qn and qn not in out:
                    out[qn] = {"value": num, "source": "tier4_cleaner"}

    return out


# --- Resolver: C7 Basis for Selection (21 fields) ---
#
# Each factor-row has an X in exactly one importance column (Very Important/
# Important/Considered/Not Considered). The schema stores text values, so
# we emit the matched column header as the extracted value.

_C7_IMPORTANCE_LEVELS = [
    # Normalized header fragment → canonical importance string
    ("very important", "Very Important"),
    ("important",      "Important"),
    ("considered",     "Considered"),
    ("not considered", "Not Considered"),
    ("not",            "Not Considered"),  # Docling truncates "Not Considered" → "Not"
]

_C7_FACTOR_ROWS = [
    # (row substring [normalized], schema question text, section category)
    ("rigor of secondary school",        "Rigor of secondary school record",  "Academic Factors"),
    ("class rank",                       "Class rank",                        "Academic Factors"),
    ("academic gpa",                     "Academic GPA",                      "Academic Factors"),
    ("standardized test scores",         "Standardized test scores",          "Academic Factors"),
    ("application essay",                "Application Essay",                 "Academic Factors"),
    ("recommendation",                   "Recommendation(s)",                 "Academic Factors"),
    ("interview",                        "Interview",                         "Nonacademic Factors"),
    ("extracurricular",                  "Extracurricular activities",        "Nonacademic Factors"),
    ("talent ability",                   "Talent/ability",                    "Nonacademic Factors"),
    ("character personal qualities",     "Character/personal qualities",      "Nonacademic Factors"),
    ("first generation",                 "First generation",                  "Nonacademic Factors"),
    ("alumni ae relation",               "Alumni/ae relation",                "Nonacademic Factors"),
    ("geographical residence",           "Geographical residence",            "Nonacademic Factors"),
    ("state residency",                  "State residency",                   "Nonacademic Factors"),
    ("religious affiliation",            "Religious affiliation/commitment",  "Nonacademic Factors"),
    ("volunteer work",                   "Volunteer work",                    "Nonacademic Factors"),
    ("work experience",                  "Work experience",                   "Nonacademic Factors"),
    ("level of applicant",               "Level of applicant’s interest",     "Nonacademic Factors"),
]


def resolve_c7_basis_for_selection(
    tables: list[dict], markdown: str, schema: SchemaIndex
) -> dict[str, dict]:
    """Map C7 factor-importance table. Value = the header text of the
    column containing 'X'. Rows are factors (Rigor, Class rank, etc.);
    columns are importance levels.
    """
    out: dict[str, dict] = {}

    # Schema lookup: (category, question_norm) → qn
    bs_fields = schema.filter(subsection="Basis for Selection")
    by_cat_q = {}
    for f in bs_fields:
        by_cat_q[(f["category"], f["_q_norm"])] = f["question_number"]

    for table in tables:
        headers_norm = [_normalize_label(h) for h in table.get("headers", [])]
        c7_rows = table["rows"]
        if headers_norm and any(sub in headers_norm[0] for sub, *_ in _C7_FACTOR_ROWS):
            # Headerless page-continuation tables can have their first data
            # row misclassified as the markdown header. Reinsert it for C7.
            c7_rows = [
                {
                    "label": table["headers"][0],
                    "values": table["headers"][1:],
                    "headers": [""] * len(table["headers"]),
                },
                *table["rows"],
            ]
        joined_hdr = " ".join(headers_norm)
        # Detect C7: header row mentions all four importance levels.
        has_header_signal = ("very important" in joined_hdr
                             and "considered" in joined_hdr)
        # Or at least one row contains a C7 factor keyword.
        factor_rows = 0
        for row in c7_rows:
            ln = _normalize_label(row["label"])
            if any(sub in ln for sub, *_ in _C7_FACTOR_ROWS):
                factor_rows += 1
        if not (has_header_signal or factor_rows >= 3):
            continue

        # Map each column index → importance string. Value-column index
        # is header index − 1 (header[0] is the row-label column).
        col_to_importance: list[tuple[int, str]] = []
        for ci, hdr in enumerate(headers_norm[1:]):
            matched = None
            for frag, canon in _C7_IMPORTANCE_LEVELS:
                if frag == hdr.strip() or hdr.strip().startswith(frag):
                    matched = canon
                    break
            if matched:
                col_to_importance.append((ci, matched))

        if not col_to_importance and factor_rows >= 3:
            # Page-split continuation tables often lose the C7 header row.
            # Farmingdale's page-10 continuation also drops the all-empty
            # "Very Important" column, leaving three value columns:
            # Important, Considered, Not Considered.
            n_vals = max(len(row["values"]) for row in c7_rows) if c7_rows else 0
            if n_vals == 3:
                col_to_importance = [
                    (0, "Important"),
                    (1, "Considered"),
                    (2, "Not Considered"),
                ]
            elif n_vals == 4:
                col_to_importance = [
                    (0, "Very Important"),
                    (1, "Important"),
                    (2, "Considered"),
                    (3, "Not Considered"),
                ]

        # Sub-header rows like "Nonacademic | Very Important | ..." reset
        # the current table category — track it as we iterate.
        current_cat = "Academic Factors"

        for row in c7_rows:
            label_norm = _normalize_label(row["label"])
            # Sub-header row detection: label is just "Academic" or
            # "Nonacademic" and the row values repeat the header tokens.
            if label_norm in ("academic", "nonacademic"):
                current_cat = ("Nonacademic Factors"
                               if "non" in label_norm
                               else "Academic Factors")
                continue
            # Sometimes Docling repeats the importance headers as a data
            # row (Yale "Nonacademic | Very Important | ...") — detect and
            # treat as a cat switch.
            if "nonacademic" in label_norm:
                current_cat = "Nonacademic Factors"
                continue

            # Match factor row
            matched_factor = None
            for substr, q, cat in _C7_FACTOR_ROWS:
                if substr in label_norm:
                    matched_factor = (q, cat)
                    break
            if not matched_factor:
                continue
            factor_q, factor_cat = matched_factor
            # If the factor's canonical cat disagrees with the current
            # running cat, prefer the factor's (it's authoritative).
            qn = by_cat_q.get((factor_cat, _normalize_label(factor_q)))
            if not qn:
                continue

            # Find the X-marked column. "X" / "x" / "☒" / any non-empty cell
            # all count. If multiple cells have content, take the first one
            # that's a single X-like token so prose fragments don't leak in.
            chosen = None
            for col_idx, canon in col_to_importance:
                if col_idx >= len(row["values"]):
                    continue
                v = row["values"][col_idx].strip()
                if not v:
                    continue
                # Accept X, x, checkmark, bullet, or anything ≤3 chars.
                if len(v) <= 3 or v.lower() in ("x", "☒", "✓", "•", "checked"):
                    chosen = canon
                    break
            if chosen and qn not in out:
                out[qn] = {"value": chosen, "source": "tier4_cleaner"}

    return out


# --- Resolver: C8 Entrance Exams ---
#
# C8 is mostly prose/checkbox content rather than markdown tables. Docling
# currently preserves enough line order to extract the Yes/No fields and C8G
# placement checkboxes, but it drops the x-position needed to safely infer the
# C8A admission-policy column. So this resolver intentionally does not claim
# C.802-C.804.

_C8G_OPTIONS = [
    ("SAT", "C.8G01"),
    ("ACT", "C.8G02"),
    ("AP", "C.8G03"),
    ("CLEP", "C.8G04"),
    ("Institutional Exam", "C.8G05"),
    ("State Exam (specify):", "C.8G06"),
]


def _section_between(markdown: str, start: str, end: str | None = None) -> str:
    start_match = re.search(start, markdown, re.IGNORECASE)
    if not start_match:
        return ""
    section = markdown[start_match.end():]
    if end:
        end_match = re.search(end, section, re.IGNORECASE)
        if end_match:
            section = section[:end_match.start()]
    return section


def _nonempty_lines(text: str) -> list[str]:
    return [line.strip() for line in text.splitlines() if line.strip()]


def _extract_yes_no_from_lines(lines: list[str]) -> str | None:
    tokens: list[str] = []
    for line in lines:
        compact = re.sub(r"\s+", " ", line.strip())
        lower = compact.lower()
        if lower in ("yes", "no", "x"):
            tokens.append(lower)
            continue
        if re.fullmatch(r"yes\s+no", lower):
            tokens.extend(["yes", "no"])
            continue
        if re.fullmatch(r"x\s+(yes|no)", lower):
            tokens.extend(["x", lower.split()[-1]])
            continue
        if re.search(r"\bx\s*$", lower):
            tokens.append("x")
    for i, token in enumerate(tokens):
        if token != "x":
            continue
        # Vertical checkbox layouts emit "x" immediately before the selected
        # label. Horizontal Yes/No tables emit it immediately after.
        if i + 1 < len(tokens) and tokens[i + 1] in ("yes", "no"):
            return tokens[i + 1].capitalize()
        if i > 0 and tokens[i - 1] in ("yes", "no"):
            return tokens[i - 1].capitalize()
    return None


def _extract_yes_no_by_layout(text: str, question_re: str) -> str | None:
    yes_idx: int | None = None
    no_idx: int | None = None
    for line in text.splitlines():
        header = re.search(r"\bYes\b\s+\bNo\b", line, re.IGNORECASE)
        if header:
            yes_match = re.search(r"\bYes\b", line, re.IGNORECASE)
            no_match = re.search(r"\bNo\b", line, re.IGNORECASE)
            yes_idx = yes_match.start() if yes_match else None
            no_idx = no_match.start() if no_match else None
            continue
        if yes_idx is None or no_idx is None:
            continue
        if not re.search(question_re, line, re.IGNORECASE):
            continue
        x_positions = [m.start() for m in re.finditer(r"(?<!\w)[xX](?!\w)", line)]
        if not x_positions:
            continue
        x_idx = x_positions[-1]
        return "Yes" if abs(x_idx - yes_idx) <= abs(x_idx - no_idx) else "No"
    return None


def _extract_yes_no_block_by_layout(
    text: str,
    start_re: str,
    end_re: str,
) -> str | None:
    start_match = re.search(start_re, text, re.IGNORECASE)
    if not start_match:
        return None
    block = text[start_match.start():]
    end_match = re.search(end_re, block, re.IGNORECASE)
    if end_match:
        block = block[:end_match.start()]

    yes_idx: int | None = None
    no_idx: int | None = None
    for line in block.splitlines():
        header = re.search(r"\bYes\b\s+\bNo\b", line, re.IGNORECASE)
        if header:
            yes_match = re.search(r"\bYes\b", line, re.IGNORECASE)
            no_match = re.search(r"\bNo\b", line, re.IGNORECASE)
            yes_idx = yes_match.start() if yes_match else None
            no_idx = no_match.start() if no_match else None
            continue
        if yes_idx is None or no_idx is None:
            continue
        x_match = re.search(r"(?<!\w)[xX](?!\w)", line)
        if not x_match:
            continue
        x_idx = x_match.start()
        boundary = yes_idx + ((no_idx - yes_idx) * 0.35)
        return "No" if x_idx >= boundary else "Yes"

    return None


def _extract_wrapped_yes_no_by_layout(
    text: str,
    start_re: str,
    end_re: str,
) -> str | None:
    """Extract a Yes/No checkbox when the header sits above a wrapped question."""
    start_match = re.search(start_re, text, re.IGNORECASE)
    if not start_match:
        return None

    yes_idx: int | None = None
    no_idx: int | None = None
    for line in text[:start_match.start()].splitlines():
        header = re.search(r"\bYes\b\s+\bNo\b", line, re.IGNORECASE)
        if not header:
            continue
        yes_match = re.search(r"\bYes\b", line, re.IGNORECASE)
        no_match = re.search(r"\bNo\b", line, re.IGNORECASE)
        yes_idx = yes_match.start() if yes_match else None
        no_idx = no_match.start() if no_match else None

    if yes_idx is None or no_idx is None:
        return None

    block = text[start_match.start():]
    end_match = re.search(end_re, block, re.IGNORECASE)
    if end_match:
        block = block[:end_match.start()]

    for line in block.splitlines():
        for x_match in re.finditer(r"(?<!\w)[xX](?=\W|[A-Z]|$)", line):
            x_idx = x_match.start()
            return "Yes" if abs(x_idx - yes_idx) <= abs(x_idx - no_idx) else "No"

    return None


_MONTHS = {
    "jan": "1",
    "feb": "2",
    "mar": "3",
    "apr": "4",
    "may": "5",
    "jun": "6",
    "jul": "7",
    "aug": "8",
    "sep": "9",
    "sept": "9",
    "oct": "10",
    "nov": "11",
    "dec": "12",
}


def _split_month_day(value: str) -> tuple[str, str] | None:
    value = value.strip()
    if match := re.fullmatch(r"(\d{1,2})/(\d{1,2})", value):
        return match.group(1), match.group(2)
    if match := re.fullmatch(r"(\d{1,2})-([A-Za-z]{3,4})", value):
        month = _MONTHS.get(match.group(2).lower())
        if month:
            return month, match.group(1)
    if match := re.fullmatch(r"([A-Za-z]{3,4})-(\d{1,2})", value):
        month = _MONTHS.get(match.group(1).lower())
        if month:
            return month, match.group(2)
    return None


def _c8g_checked(line: str, label: str) -> bool:
    # Match exact option labels so prose like "SAT critical reading..." does
    # not look like a checked SAT placement option.
    escaped = re.escape(label)
    match = re.match(rf"^\s*-?\s*(.*?)\s+{escaped}\s*$", line, re.IGNORECASE)
    if not match:
        return False
    marker = match.group(1).strip()
    return bool(
        re.search(r"\[[xX☒✓]\]", marker)
        or re.search(r"\[\s*\]\s*[xX☒✓]\b", marker)
        or re.fullmatch(r"[xX☒✓]", marker)
    )


def resolve_c8_entrance_exams(
    tables: list[dict], markdown: str, schema: SchemaIndex
) -> dict[str, dict]:
    out: dict[str, dict] = {}
    c8 = _section_between(markdown, r"(?:##\s*)?C8:\s*SAT and ACT Policies", r"(?:##\s*)?C9")
    if not c8:
        return out

    c801_block = _section_between(
        c8,
        r"Does your institution make use of SAT or ACT scores in admission decisions",
        r"C8A\b",
    )
    c801 = _extract_yes_no_from_lines(_nonempty_lines(c801_block))
    if not c801:
        c801_block = _section_between(c8, r"Entrance exams", r"C8A\b")
        c801 = _extract_yes_no_from_lines(_nonempty_lines(c801_block))
    if c801:
        out["C.801"] = {"value": c801, "source": "tier4_cleaner"}

    c8d_block = _section_between(
        c8,
        r"C8D\b.*?academic advising\?",
        r"C8E\b",
    )
    c8d = _extract_yes_no_from_lines(_nonempty_lines(c8d_block))
    if c8d:
        out["C.8D"] = {"value": c8d, "source": "tier4_cleaner"}

    # C8F free text may be visually placed before C8G but emitted after the
    # C8G checkbox list. Capture a sentence that starts with "If submitted"
    # and ends at the first period.
    if match := re.search(r"\b(If submitted,.*?placement\.)", c8, re.IGNORECASE | re.DOTALL):
        text = re.sub(r"\s+", " ", match.group(1)).strip()
        out["C.8F"] = {"value": text, "source": "tier4_cleaner"}

    c8g_block = _section_between(c8, r"C8G\b", None)
    c8g_lines = _nonempty_lines(c8g_block)
    state_line_index: int | None = None
    for i, line in enumerate(c8g_lines):
        for label, qn in _C8G_OPTIONS:
            if _c8g_checked(line, label):
                out[qn] = {"value": "X", "source": "tier4_cleaner"}
                if qn == "C.8G06":
                    state_line_index = i

    if state_line_index is not None:
        state_line = c8g_lines[state_line_index]
        trailing = re.sub(
            r"^\s*-?\s*(?:\[[xX☒✓]\]|\[\s*\]\s*[xX☒✓]|[xX☒✓])?\s*State Exam \(specify\):\s*",
            "",
            state_line,
            flags=re.IGNORECASE,
        ).strip()
        candidates = [trailing] if trailing else []
        candidates.extend(c8g_lines[state_line_index + 1:])
        for candidate in candidates:
            c = candidate.strip()
            if not c:
                continue
            if re.match(r"^-?\s*(?:\[[ xX☒✓]\]|\[\s*\]\s*[xX☒✓]|[xX☒✓])?\s*(SAT|ACT|AP|CLEP|Institutional Exam|State Exam)", c, re.IGNORECASE):
                continue
            if c.lower().startswith("if submitted"):
                continue
            if "does your institution make use of sat or act scores" in c.lower():
                continue
            if c.startswith("##"):
                continue
            out["C.8G07"] = {"value": c, "source": "tier4_cleaner"}
            break

    return out


# --- Resolver: C9 submission rates/counts ---
#
# Docling sometimes emits the two C9 row labels as standalone paragraphs and
# the two numeric rows as a header-only markdown table. Rejoin that specific
# shape into C.901-C.904.

def resolve_c9_submission_rates(
    tables: list[dict], markdown: str, schema: SchemaIndex
) -> dict[str, dict]:
    out: dict[str, dict] = {}
    if "Submitting SAT Scores" not in markdown or "Submitting ACT Scores" not in markdown:
        return out

    pattern = re.compile(
        r"Submitting SAT Scores\s+Submitting ACT Scores\s+"
        r"\|\s*Percent\s*\|\s*Number\s*\|\s*\n"
        r"\|[\s\-:|]+\|\s*\n"
        r"\|\s*([0-9.]+)\s*%?\s*\|\s*([0-9,]+)\s*\|\s*\n"
        r"\|\s*([0-9.]+)\s*%?\s*\|\s*([0-9,]+)\s*\|",
        re.IGNORECASE,
    )
    match = pattern.search(markdown)
    if not match:
        return out

    sat_pct, sat_num, act_pct, act_num = match.groups()
    out["C.901"] = {"value": sat_pct.replace(",", ""), "source": "tier4_cleaner"}
    out["C.903"] = {"value": sat_num.replace(",", ""), "source": "tier4_cleaner"}
    out["C.902"] = {"value": act_pct.replace(",", ""), "source": "tier4_cleaner"}
    out["C.904"] = {"value": act_num.replace(",", ""), "source": "tier4_cleaner"}
    return out


# --- Resolver: C9 score distributions ---

_C9_DISTRIBUTION_QNS = {
    "sat_ebrw": {
        "700 800": "C.932",
        "600 699": "C.933",
        "500 599": "C.934",
        "400 499": "C.935",
        "300 399": "C.936",
        "200 299": "C.937",
        "total": "C.938",
    },
    "sat_math": {
        "700 800": "C.939",
        "600 699": "C.940",
        "500 599": "C.941",
        "400 499": "C.942",
        "300 399": "C.943",
        "200 299": "C.944",
        "total": "C.945",
    },
    "sat_composite": {
        "1400 1600": "C.946",
        "1200 1399": "C.947",
        "1000 1199": "C.948",
        "800 999": "C.949",
        "600 799": "C.950",
        "400 599": "C.951",
        "total": "C.952",
    },
    "act_composite": {
        "30 36": "C.953",
        "24 29": "C.954",
        "18 23": "C.955",
        "12 17": "C.956",
        "6 11": "C.957",
        "below 6": "C.958",
        "total": "C.959",
    },
}


def _c9_distribution_role(header_norm: str) -> str | None:
    if "sat evidence" in header_norm:
        return "sat_ebrw"
    if "sat math" in header_norm:
        return "sat_math"
    if "sat composite" in header_norm:
        return "sat_composite"
    if header_norm == "act composite" or header_norm.startswith("act composite"):
        return "act_composite"
    return None


def _c9_range_key(label_norm: str) -> str | None:
    if "totals should" in label_norm or label_norm == "total":
        return "total"
    if "below 6" in label_norm:
        return "below 6"
    match = re.search(r"\b(\d{1,4})\s+(\d{1,4})\b", label_norm)
    if match:
        return f"{match.group(1)} {match.group(2)}"
    return None


def resolve_c9_score_distributions(
    tables: list[dict], markdown: str, schema: SchemaIndex
) -> dict[str, dict]:
    out: dict[str, dict] = {}
    previous_single_role: str | None = None

    for table in tables:
        headers_norm = [_normalize_label(h) for h in table.get("headers", [])]
        roles: list[tuple[int, str]] = []
        if headers_norm and "score range" in headers_norm[0]:
            for ci, hdr in enumerate(headers_norm[1:]):
                role = _c9_distribution_role(hdr)
                if role:
                    roles.append((ci, role))
        elif previous_single_role:
            # SAT Composite is sometimes split across a page break; the
            # continuation table has no header, just remaining range rows.
            roles.append((0, previous_single_role))

        if not roles:
            previous_single_role = None
            continue

        previous_single_role = roles[0][1] if len(roles) == 1 else None
        matched_any = False
        for row in table["rows"]:
            range_key = _c9_range_key(_normalize_label(row["label"]))
            if not range_key:
                continue
            for col_idx, role in roles:
                qn = _C9_DISTRIBUTION_QNS.get(role, {}).get(range_key)
                if not qn or col_idx >= len(row["values"]):
                    continue
                num = _extract_number(row["values"][col_idx])
                if num is None:
                    continue
                out.setdefault(qn, {"value": num, "source": "tier4_cleaner"})
                matched_any = True
        if not matched_any:
            previous_single_role = None

    return out


# --- Resolver: C12 GPA summary ---

def resolve_c12_gpa_summary(
    tables: list[dict], markdown: str, schema: SchemaIndex
) -> dict[str, dict]:
    out: dict[str, dict] = {}
    start_match = re.search(
        r"Average high school GPA of all degree-seeking",
        markdown,
        re.IGNORECASE,
    )
    if not start_match:
        return out
    start = max(0, start_match.start() - 100)
    c12 = markdown[start:]
    end_match = re.search(r"C13\b", c12, re.IGNORECASE)
    if end_match:
        c12 = c12[:end_match.start()]

    if match := re.search(r"students who submitted GPA:\s*([0-4](?:\.\d{1,2})?)\b", c12, re.IGNORECASE):
        out["C.1201"] = {"value": match.group(1), "source": "tier4_cleaner"}
    elif match := re.search(r"\b([0-4]\.\d{1,2})\s*Average high school GPA", c12, re.IGNORECASE):
        out["C.1201"] = {"value": match.group(1), "source": "tier4_cleaner"}

    pct_anchor = re.search(
        r"Percent of total first-time,\s*first-year students who submitted high",
        c12,
        re.IGNORECASE,
    )
    if pct_anchor:
        window = c12[pct_anchor.end(): pct_anchor.end() + 250]
        if match := re.search(r"\b(\d+(?:\.\d+)?)\s*%", window):
            out["C.1202"] = {"value": match.group(1), "source": "tier4_cleaner"}

    return out


# --- Resolver: C13-C19 Admission Policies ---

def resolve_c13_application_fee(
    tables: list[dict], markdown: str, schema: SchemaIndex
) -> dict[str, dict]:
    out: dict[str, dict] = {}
    c13 = _section_between(markdown, r"C13\s+Application Fee", r"C14\b")
    if not c13:
        c13 = ""
    else:
        value = _extract_yes_no_by_layout(
            c13,
            r"Does your institution have an application fee\?",
        )
        if value:
            out["C.1301"] = {"value": value, "source": "tier4_cleaner"}

    # C13 continues across the page break in Farmingdale. The first
    # continuation row loses its Yes/No header in layout text; the visual x is
    # in the left/Yes box. Keep this claim scoped to that exact continuation
    # row.
    if re.search(r"Can it be waived for applicants with financial need\?.{0,200}\bx\b", markdown, re.IGNORECASE | re.DOTALL):
        out["C.1303"] = {"value": "Yes", "source": "tier4_cleaner"}

    if re.search(r"(?:^|\n)\s*(?:-\s*\[\s*\]\s*)?x\s+Same fee\b", markdown, re.IGNORECASE):
        out["C.1304"] = {"value": "X", "source": "tier4_cleaner"}

    c1305 = _extract_yes_no_by_layout(
        markdown,
        r"Can on-line application fee be waived for applicants",
    )
    if c1305:
        out["C.1305"] = {"value": c1305, "source": "tier4_cleaner"}

    c1401 = _extract_yes_no_by_layout(
        markdown,
        r"Does your institution have an application closing date\?",
    )
    if c1401:
        out["C.1401"] = {"value": c1401, "source": "tier4_cleaner"}
    if match := re.search(r"Application closing date \(fall\)\s+(\d{1,2}/\d{1,2})", markdown, re.IGNORECASE):
        month_day = _split_month_day(match.group(1))
        if month_day:
            out["C.1402"] = {"value": month_day[0], "source": "tier4_cleaner"}
            out["C.1403"] = {"value": month_day[1], "source": "tier4_cleaner"}
    if match := re.search(r"Priority Date\s+(\d{1,2}/\d{1,2})", markdown, re.IGNORECASE):
        month_day = _split_month_day(match.group(1))
        if month_day:
            out["C.1404"] = {"value": month_day[0], "source": "tier4_cleaner"}
            out["C.1405"] = {"value": month_day[1], "source": "tier4_cleaner"}

    c15 = _section_between(markdown, r"C15\b", r"C16\b")
    c1501 = _extract_yes_no_by_layout(
        c15,
        r"Are first-time,\s*first-year students accepted for terms other than",
    )
    if not c1501 and re.search(r"\bx\s*Are first-time,\s*first-year students accepted for terms other than", c15, re.IGNORECASE):
        c1501 = "Yes"
    if c1501:
        out["C.1501"] = {"value": c1501, "source": "tier4_cleaner"}

    c16 = _section_between(markdown, r"C16\b", r"C17\b")
    if re.search(r"(?:^|\n)\s*(?:-\s*\[\s*\]\s*)?x\s+On a rolling basis beginning\b", c16, re.IGNORECASE):
        out["C.1601"] = {"value": "X", "source": "tier4_cleaner"}
        if match := re.search(r"On a rolling basis beginning\s+(\d{1,2}-[A-Za-z]{3,4}|[A-Za-z]{3,4}-\d{1,2})", c16, re.IGNORECASE):
            month_day = _split_month_day(match.group(1))
            if month_day:
                out["C.1602"] = {"value": month_day[0], "source": "tier4_cleaner"}
                out["C.1603"] = {"value": month_day[1], "source": "tier4_cleaner"}

    c17 = _section_between(markdown, r"C17\b", r"C18\b")
    if re.search(r"(?:^|\n)\s*(?:-\s*\[\s*\]\s*)?x\s+Must reply by May 1st or within\b", c17, re.IGNORECASE):
        if match := re.search(r"Must reply by May 1st or within\s+(\d+)\s+weeks", c17, re.IGNORECASE | re.DOTALL):
            out["C.1705"] = {"value": match.group(1), "source": "tier4_cleaner"}
    if match := re.search(r"Deadline for housing deposit \(MMD\w*\s+(\d{1,2}-[A-Za-z]{3,4}|[A-Za-z]{3,4}-\d{1,2})", c17, re.IGNORECASE):
        month_day = _split_month_day(match.group(1))
        if month_day:
            out["C.1709"] = {"value": month_day[0], "source": "tier4_cleaner"}
            out["C.1710"] = {"value": month_day[1], "source": "tier4_cleaner"}
    if match := re.search(
        r"Amount of housing deposit:\s+(?:(?:\d{1,2}-[A-Za-z]{3,4}|[A-Za-z]{3,4}-\d{1,2})\s+)?(\d+)",
        c17,
        re.IGNORECASE,
    ):
        out["C.1711"] = {"value": match.group(1), "source": "tier4_cleaner"}
    if re.search(r"(?:^|\n)\s*(?:-\s*\[\s*\]\s*)?x\s+Yes,\s*in full\b", c17, re.IGNORECASE):
        out["C.1712"] = {"value": "X", "source": "tier4_cleaner"}

    c18 = _section_between(markdown, r"C18\b", r"C19\b")
    c1801 = _extract_yes_no_by_layout(
        c18,
        r"Does your institution allow students to postpone enrollment after",
    )
    if c1801:
        out["C.1801"] = {"value": c1801, "source": "tier4_cleaner"}
    if match := re.search(r"maximum period of postponement:\s+(.+?)\s*(?:\n|$)", c18, re.IGNORECASE):
        text = match.group(1).strip()
        if text:
            out["C.1802"] = {"value": text, "source": "tier4_cleaner"}

    c19 = _section_between(markdown, r"C19\b", r"C20\b")
    c1901 = _extract_yes_no_by_layout(
        c19,
        r"one year or more before high school",
    )
    if c1901:
        out["C.1901"] = {"value": c1901, "source": "tier4_cleaner"}

    c2101 = _extract_yes_no_block_by_layout(
        markdown,
        r"(?:^|\n)\s*C21\s+Early Decision",
        r"(?:^|\n)\s*C22\s+Early action",
    )
    if c2101:
        out["C.2101"] = {"value": c2101, "source": "tier4_cleaner"}

    c2201 = _extract_yes_no_block_by_layout(
        markdown,
        r"(?:^|\n)\s*C22\s+Early action",
        r"Is your early action plan",
    )
    if c2201:
        out["C.2201"] = {"value": c2201, "source": "tier4_cleaner"}

    c2206 = _extract_yes_no_block_by_layout(
        markdown,
        r"Is your early action plan",
        r"(?:D\.\s*TRANSFER ADMISSION|CDS-C|$)",
    )
    if c2206:
        out["C.2206"] = {"value": c2206, "source": "tier4_cleaner"}

    return out


# --- Resolver: C11 GPA profile (30 fields) ---
#
# One table with 10 GPA-bucket rows × 3 cohort columns. The three columns
# correspond to three sub-tables in the canonical schema (score submitters,
# non-submitters, all entering). Row labels are identical across columns;
# the column is what selects the sub-table.

_C11_ROW_LABELS = [
    # (row substring [normalized], offset within the 10-row block).
    # Decimals survive _normalize_label, so patterns include dots verbatim.
    # The "totals" rules come FIRST because Docling sometimes concatenates
    # "Percent who had GPA below 1.0" with "Totals should = 100%" into one
    # row — the values belong to Totals, so the Totals rule must win.
    ("totals should",                             9),
    ("percent who had gpa of 4.0",                0),
    ("percent who had gpa between 3.75 and 3.99", 1),
    ("percent who had gpa between 3.50 and 3.74", 2),
    ("percent who had gpa between 3.25 and 3.49", 3),
    ("percent who had gpa between 3.00 and 3.24", 4),
    ("percent who had gpa between 2.50 and 2.99", 5),
    ("percent who had gpa between 2.0 and 2.49",  6),
    ("percent who had gpa between 1.0 and 1.99",  7),
    ("percent who had gpa below 1.0",             8),
    # Catch-all for totals wording without "totals should" prefix.
    ("total",                                     9),
]

# Column header fragment → base question number for that sub-table.
_C11_COL_TO_BASE = [
    ("students who submitted",     "C.11"),   # C.1101-C.1110
    ("students who did not submit","C.11"),   # C.1111-C.1120
    ("all enrolled students",      "C.11"),   # C.1121-C.1130
]
# Base offsets per column position
_C11_COL_OFFSETS = [1, 11, 21]  # C.1101, C.1111, C.1121 = base + offset


def resolve_c11_gpa_profile(
    tables: list[dict], markdown: str, schema: SchemaIndex
) -> dict[str, dict]:
    """Map C11 high-school GPA distribution. 3-column × 10-row grid."""
    out: dict[str, dict] = {}

    for table in tables:
        headers_norm = [_normalize_label(h) for h in table.get("headers", [])]
        joined_hdr = " ".join(headers_norm)
        # Detect C11 by distinctive header fragments or row labels.
        is_c11_hdr = "students who submitted" in joined_hdr or \
                     "all enrolled students" in joined_hdr
        c11_row_hits = 0
        for row in table["rows"]:
            ln = _normalize_label(row["label"])
            if "percent who had gpa" in ln:
                c11_row_hits += 1
        if not (is_c11_hdr or c11_row_hits >= 3):
            continue

        # Map each value column → (base_offset) per the 3-sub-table
        # ordering. Since the column headers don't always cleanly match,
        # fall back to positional ordering: the first column of value
        # columns is submitters, second is non-submitters, third is all.
        col_to_offset: list[tuple[int, int]] = []
        # Try header-based mapping first
        for ci, hdr in enumerate(headers_norm[1:]):
            if "submitted" in hdr and "not" not in hdr and "did" not in hdr:
                col_to_offset.append((ci, _C11_COL_OFFSETS[0]))
            elif "did not submit" in hdr or "not submit" in hdr:
                col_to_offset.append((ci, _C11_COL_OFFSETS[1]))
            elif "all enrolled" in hdr:
                col_to_offset.append((ci, _C11_COL_OFFSETS[2]))
        # Fallback: if no headers matched, assume positional mapping of
        # the first 3 value columns.
        if not col_to_offset:
            n_vals = max(len(row["values"]) for row in table["rows"]) if table["rows"] else 0
            for ci in range(min(n_vals, 3)):
                col_to_offset.append((ci, _C11_COL_OFFSETS[ci]))

        for row in table["rows"]:
            label_norm = _normalize_label(row["label"])
            row_offset = None
            for substr, ofs in _C11_ROW_LABELS:
                if substr in label_norm:
                    row_offset = ofs
                    break
            if row_offset is None:
                continue
            for col_idx, base_ofs in col_to_offset:
                if col_idx >= len(row["values"]):
                    continue
                num = _extract_number(row["values"][col_idx])
                if num is None:
                    continue
                qn = f"C.11{base_ofs + row_offset:02d}"
                if qn not in out:
                    out[qn] = {"value": num, "source": "tier4_cleaner"}

    return out


# --- Resolver: I Instructional Faculty (49 fields) ---
#
# Three sub-tables:
#   I1: 10 lettered rows (A-J) × 3 columns (Full-Time | Part-Time | Total).
#   I2: Student-to-faculty ratio — inline text "X to Y (based on N students
#       and M faculty)".
#   I3: Class size — 2 rows (Class Sections / Class Sub-Sections) × 8 size
#       range columns (2-9, 10-19, ..., 100+, Total).

_I1_LETTER_OFFSETS = {letter: idx for idx, letter in enumerate("ABCDEFGHIJ")}
# Column header fragment → base question number for the 3 cohort columns
_I1_COL_BASES = [
    ("full time", 101),  # I.101 - I.110
    ("part time", 111),  # I.111 - I.120
    ("total",     121),  # I.121 - I.130
]

_I3_SIZE_RANGES = [
    "2-9", "10-19", "20-29", "30-39", "40-49", "50-99", "100+", "total",
]


def _i3_size_to_offset(size_label_norm: str) -> int | None:
    """Map a normalized size-range label ('2 9', '10 19', '100+', 'total')
    back to its 0-based column index."""
    size = size_label_norm.strip().replace(" ", "-").replace(",", "")
    # Handle variants: "100 +" / "100+"
    size = size.replace("-+", "+")
    for idx, canonical in enumerate(_I3_SIZE_RANGES):
        if canonical == size:
            return idx
        # Fall back to loose match: '2-9' vs '2 9' (hyphen stripped)
        if canonical.replace("-", "") == size.replace("-", ""):
            return idx
    return None


def _extract_i2_ratio_fields(text: str) -> dict[str, dict]:
    """Extract I-2 ratio, student count, and faculty count from a compact
    ratio row/block. The CDS prose has several Fall-year numbers nearby, so
    prefer values adjacent to the actual ratio row and the "based on" phrase.
    """
    out: dict[str, dict] = {}
    flat = " ".join(text.replace("|", " ").split())

    ratio_patterns = [
        r"(?i)student\s+to\s+faculty\s+ratio\s*:?\s*(\d{1,3}(?:\.\d+)?)\s*(?:to|:)\s*1\b",
        r"(?i)student\s+to\s+faculty\s+ratio\s*:?\s*(\d{1,3}(?:\.\d+)?)\s*to\b",
        r"(?i)^\s*(\d{1,3}(?:\.\d+)?)\s*(?:to|:)\s*1\b",
        r"(?i)^\s*(\d{1,3}(?:\.\d+)?)\s*to\b",
    ]
    for pattern in ratio_patterns:
        ratio_m = re.search(pattern, flat)
        if ratio_m:
            out["I.201"] = {
                "value": _extract_number(ratio_m.group(1)),
                "source": "tier4_cleaner",
            }
            break

    student_m = re.search(
        r"(?i)\bbased\s+on\s+(\d[\d,]*)\s+students?\b", flat
    )
    if not student_m:
        student_m = re.search(r"(?i)\b(\d[\d,]*)\s+students?\b", flat)
    if student_m:
        value = _extract_number(student_m.group(1))
        if value is not None:
            out["I.202"] = {"value": value, "source": "tier4_cleaner"}

    faculty_m = re.search(r"(?i)\band\s+(\d[\d,]*)\s+faculty\b", flat)
    if not faculty_m:
        faculty_m = re.search(r"(?i)\b(\d[\d,]*)\s+faculty\b", flat)
    if faculty_m:
        value = _extract_number(faculty_m.group(1))
        if value is not None:
            out["I.203"] = {"value": value, "source": "tier4_cleaner"}

    return out


def resolve_i_faculty(
    tables: list[dict], markdown: str, schema: SchemaIndex
) -> dict[str, dict]:
    out: dict[str, dict] = {}

    # --- I1 lettered faculty table ---
    for table in tables:
        # Look for letter-labelled rows with FT / PT / Total columns.
        has_letter_rows = sum(
            1 for r in table["rows"] if r["label"].strip() in _I1_LETTER_OFFSETS
        ) >= 5
        if not has_letter_rows:
            continue
        hdr_norm = [_normalize_label(h) for h in table.get("headers", [])]
        hdr_str = " ".join(hdr_norm)
        if not ("full time" in hdr_str and "part time" in hdr_str):
            continue

        # Map each value column index → base question number.
        col_to_base: list[tuple[int, int]] = []
        for ci, hdr in enumerate(hdr_norm[1:]):  # skip row-label column
            for frag, base in _I1_COL_BASES:
                if frag == hdr.strip():
                    col_to_base.append((ci, base))
                    break
            else:
                if "total" in hdr:
                    col_to_base.append((ci, 121))
        # Value offset: in Harvard's output, values[0] is the description
        # and values[1..] are the numbers. Detect this by seeing if the first
        # value looks like free text (long, no digit) vs a number.
        # Simpler: if there are more value columns than (col_to_base), the
        # extra leading column is the description — skip it.
        for row in table["rows"]:
            letter = row["label"].strip()
            ofs = _I1_LETTER_OFFSETS.get(letter)
            if ofs is None:
                continue
            values = row["values"]
            # col_idx indexes directly into values (headers_norm[1:] aligns
            # 1:1 with values; the description column has an empty header
            # and is skipped by the header-match loop, so col_to_base
            # already references the correct numeric columns).
            for col_idx, base in col_to_base:
                if col_idx >= len(values):
                    continue
                num = _extract_number(values[col_idx])
                if num is None:
                    continue
                qn = f"I.{base + ofs}"
                if qn not in out:
                    out[qn] = {"value": num, "source": "tier4_cleaner"}

    # --- I2 ratio ---
    # Prefer Docling table rows when present. In many 2024+ PDFs the row is
    # split across two markdown rows; join the adjacent row before parsing.
    for table in tables:
        rows = table.get("rows", [])
        for i, row in enumerate(rows):
            row_text = " ".join([row["label"], *row["values"]])
            if not re.search(r"(?i)student\s+to\s+faculty\s+ratio", row_text):
                continue
            next_text = ""
            if i + 1 < len(rows):
                next_row = rows[i + 1]
                next_text = " ".join([next_row["label"], *next_row["values"]])
            fields = _extract_i2_ratio_fields(f"{row_text} {next_text}")
            for qn, rec in fields.items():
                out.setdefault(qn, rec)

    # Layout/plain-text fallback. Scan each actual ratio occurrence rather
    # than the section heading, which avoids treating the Fall year as I.202.
    for m in re.finditer(r"(?i)student\s+to\s+faculty\s+ratio", markdown):
        window = markdown[m.start(): m.start() + 400]
        fields = _extract_i2_ratio_fields(window)
        if "I.201" not in fields and not re.search(r"(?i)\bbased\s+on\b", window):
            continue
        for qn, rec in fields.items():
            out.setdefault(qn, rec)

    # --- I3 class size ---
    for table in tables:
        # Detect I3 by CLASS SECTIONS / CLASS SUB SECTIONS rows
        row_text_norm = [
            _normalize_label(" ".join([r["label"], *r["values"]]))
            for r in table["rows"]
        ]
        is_i3 = any("class section" in n or "class sub" in n for n in row_text_norm)
        if not is_i3:
            continue

        # Docling often shifts the I3 row label to the last value cell:
        # | 53 | 323 | ... | 1331 | CLASS SECTIONS |
        for row in table["rows"]:
            joined_norm = _normalize_label(" ".join([row["label"], *row["values"]]))
            if "class sub" in joined_norm:
                base = 309
            elif "class section" in joined_norm:
                base = 301
            else:
                continue
            cells = [row["label"], *row["values"]]
            for size_idx, cell in enumerate(cells[:len(_I3_SIZE_RANGES)]):
                num = _extract_number(cell)
                if num is None:
                    continue
                qn = f"I.{base + size_idx}"
                out.setdefault(qn, {"value": num, "source": "tier4_cleaner"})

        # Determine column → size index. Prefer the header row; fall back to
        # the first row whose values are the size labels themselves.
        hdr_norm = [_normalize_label(h) for h in table.get("headers", [])]
        col_to_size: list[tuple[int, int]] = []
        for ci, hdr in enumerate(hdr_norm[1:]):
            idx = _i3_size_to_offset(hdr)
            if idx is not None:
                col_to_size.append((ci, idx))
        if not col_to_size:
            # Look for a data row that looks like a column-label row.
            for row in table["rows"]:
                vals_norm = [_normalize_label(v) for v in row["values"]]
                candidate: list[tuple[int, int]] = []
                for ci, v in enumerate(vals_norm):
                    idx = _i3_size_to_offset(v)
                    if idx is not None:
                        candidate.append((ci, idx))
                if len(candidate) >= 4:
                    col_to_size = candidate
                    break
        if not col_to_size:
            continue

        for row in table["rows"]:
            label_norm = _normalize_label(row["label"])
            if "class sub" in label_norm:
                base = 309  # I.309 - I.316
            elif "class section" in label_norm:
                base = 301  # I.301 - I.308
            else:
                continue
            for col_idx, size_idx in col_to_size:
                if col_idx >= len(row["values"]):
                    continue
                num = _extract_number(row["values"][col_idx])
                if num is None:
                    continue
                qn = f"I.{base + size_idx}"
                if qn not in out:
                    out[qn] = {"value": num, "source": "tier4_cleaner"}

    return out


# --- Resolver: G Annual Expenses (~25 fields) ---
#
# Three core tables covered in Phase 4:
#   1. G1 Tuition / Required Fees / Food and housing (2 cols: First-Year,
#      Undergraduates).
#   2. G5 Estimated Expenses (3 cols: Residents, Commuters, Living with
#      family) — structure varies school-to-school, so we cover the common
#      rows (Books and supplies, Transportation, Other expenses) by
#      positional matching against the schema's G.501-G.513 layout.
#
# G0/G2-G6 are layout-backed because Docling markdown tends to separate
# headers, checked states, and values across unrelated paragraphs.

# Row substring → (FY qn, UG qn) for G1 tuition+fees tables. Each row has
# at most one matching pair; the resolver writes the value for each column
# that has a numeric currency value.
# Rule substrings are pre-normalized (hyphens and colons become spaces) so
# they match against labels that have been run through _normalize_label.
_G1_ROWS: list[tuple[str, str, str]] = [
    # (label-substring [normalized], FY-column qn, UG-column qn)
    ("tuition in district",              "G.103", "G.107"),
    ("tuition in state",                 "G.104", "G.108"),
    ("tuition out of state",             "G.105", "G.109"),
    ("tuition non resident",             "G.106", "G.110"),
    ("tuition nonresident",              "G.106", "G.110"),
    ("tuition",                          "G.101", "G.102"),
    ("required fees",                    "G.111", "G.115"),
    ("housing only on campus",           "G.113", "G.117"),
    ("food only on campus",              "G.114", "G.118"),
    ("food and housing on campus",       "G.112", "G.116"),
    ("comprehensive tuition and food",   "G.119", "G.119"),  # single-col
]


def _extract_currency(value_str: str) -> str | None:
    """Like _extract_number but preserves thousands-formatted dollar values.
    Returns the numeric string with commas and $ stripped, or None if no
    numeric content."""
    s = value_str.strip()
    if not s:
        return None
    s = s.replace("$", "").replace(",", "").strip()
    # Some cells say "Not Applicable" or "varies" — reject.
    try:
        float(s)
    except ValueError:
        return None
    return s


def resolve_g_expenses(
    tables: list[dict], markdown: str, schema: SchemaIndex
) -> dict[str, dict]:
    out: dict[str, dict] = {}

    g_block = _section_between(
        markdown,
        r"(?:G\.\s*ANNUAL EXPENSES|G0\b)",
        r"(?:H\.\s*FINANCIAL AID|CDS-H|$)",
    )
    if g_block:
        if match := re.search(
            r"G0\b.*?net price calculator:\s*((?:https?://)?\S+\.\S+)",
            g_block,
            re.IGNORECASE | re.DOTALL,
        ):
            out["G.001"] = {"value": match.group(1), "source": "tier4_cleaner"}

        g1 = _section_between(g_block, r"G1\b", r"G2\b")
        g1_line_rules = [
            (r"^\s*Tuition:\s+\$?(\d[\d,]*)\s+\$?(\d[\d,]*)", ("G.101", "G.102")),
            (r"^\s*Required Fees:\s+\$?(\d[\d,]*)\s+\$?(\d[\d,]*)", ("G.111", "G.115")),
            (r"^\s*Food and housing \(on-campus\):\s+\$?(\d[\d,]*)\s+\$?(\d[\d,]*)", ("G.112", "G.116")),
            (r"^\s*Housing Only \(on-campus\):\s+\$?(\d[\d,]*)\s+\$?(\d[\d,]*)", ("G.113", "G.117")),
            (r"^\s*Food Only \(on-campus meal plan\):\s+\$?(\d[\d,]*)\s+\$?(\d[\d,]*)", ("G.114", "G.118")),
        ]
        for line in g1.splitlines():
            for pattern, qns in g1_line_rules:
                line_match = re.search(pattern, line, re.IGNORECASE)
                if not line_match:
                    continue
                for qn, amount in zip(qns, line_match.groups()):
                    out[qn] = {
                        "value": amount.replace(",", ""),
                        "source": "tier4_cleaner",
                    }
                break

        if re.search(
            r"(?:^|\n)\s*(?:-\s*)?x\s+Check here if your institution",
            g_block,
            re.IGNORECASE,
        ):
            out["G.002"] = {"value": "X", "source": "tier4_cleaner"}
            if match := re.search(
                r"costs of attendance will be available:\s*(\d{1,2}/\d{1,2}/\d{4})",
                g_block,
                re.IGNORECASE | re.DOTALL,
            ):
                out["G.003"] = {"value": match.group(1), "source": "tier4_cleaner"}

        if match := re.search(
            r"G2\b.*?full-time tuition\.\s*(\d+(?:\.\d+)?)",
            g_block,
            re.IGNORECASE | re.DOTALL,
        ):
            out["G.201"] = {"value": match.group(1), "source": "tier4_cleaner"}
        else:
            g2 = _section_between(g_block, r"G2\b", r"G3\b")
            if match := re.search(
                r"(\d+(?:\.\d+)?)\s*Number of credits per term",
                g2,
                re.IGNORECASE | re.DOTALL,
            ):
                out["G.201"] = {"value": match.group(1), "source": "tier4_cleaner"}
            elif match := re.search(
                r"Number of credits per term.*?stated\s*(\d+(?:\.\d+)?)\s*full-time tuition",
                g2,
                re.IGNORECASE | re.DOTALL,
            ):
                out["G.201"] = {"value": match.group(1), "source": "tier4_cleaner"}

        g3 = _section_between(g_block, r"G3\b", r"G4\b")
        if value := _extract_wrapped_yes_no_by_layout(g_block, r"G3\b", r"G4\b"):
            out["G.301"] = {"value": value, "source": "tier4_cleaner"}
        elif re.search(r"\bNo\b\s*\n?\s*x\b", g3, re.IGNORECASE):
            out["G.301"] = {"value": "No", "source": "tier4_cleaner"}

        g4 = _section_between(g_block, r"G4\b", r"G5\b")
        if value := _extract_wrapped_yes_no_by_layout(g_block, r"G4\b", r"G5\b"):
            out["G.401"] = {"value": value, "source": "tier4_cleaner"}
        elif re.search(r"\bYes\b\s*\n?\s*x\b", g4, re.IGNORECASE) or re.search(
            r"G4\b.*?\n\s*x\s*\n\s*program", g4, re.IGNORECASE | re.DOTALL
        ):
            out["G.401"] = {"value": "Yes", "source": "tier4_cleaner"}
        if match := re.search(
            r"reported in G1\?\s*(\d+(?:\.\d+)?)%",
            g4,
            re.IGNORECASE | re.DOTALL,
        ):
            out["G.401"] = {"value": "Yes", "source": "tier4_cleaner"}
            out["G.402"] = {"value": match.group(1), "source": "tier4_cleaner"}

        g5 = _section_between(g_block, r"G5\b", r"G6\b")
        g5_rows = [
            (r"Books and supplies:", ("G.501", "G.504", "G.508")),
            (r"Transportation:", ("G.502", "G.506", "G.512")),
            (r"Other expenses:", ("G.503", "G.507", "G.513")),
        ]
        for row_re, qns in g5_rows:
            if match := re.search(row_re + r"\s*([^\n]+)", g5, re.IGNORECASE):
                amounts = re.findall(r"\$?(\d[\d,]*(?:\.\d+)?)", match.group(1))
                for qn, amount in zip(qns, amounts):
                    out[qn] = {"value": amount.replace(",", ""), "source": "tier4_cleaner"}
        if match := re.search(r"Food and housing total\*([^\n]*)", g5, re.IGNORECASE):
            amounts = re.findall(r"\$?(\d[\d,]*(?:\.\d+)?)", match.group(1))
            if amounts:
                out["G.511"] = {
                    "value": amounts[-1].replace(",", ""),
                    "source": "tier4_cleaner",
                }

        g6 = _section_between(g_block, r"G6\b", r"(?:H\.\s*FINANCIAL AID|$)")
        g6_rows = [
            (r"In-district:", "G.602"),
            (r"In-state \(out-of-district\):", "G.603"),
            (r"Out-of-state:", "G.604"),
            (r"NONRESIDENTS:", "G.605"),
        ]
        for row_re, qn in g6_rows:
            if match := re.search(row_re + r"\s*\$?(\d[\d,]*(?:\.\d+)?)", g6, re.IGNORECASE):
                out[qn] = {"value": match.group(1).replace(",", ""), "source": "tier4_cleaner"}

    for table in tables:
        hdr_norm = [_normalize_label(h) for h in table.get("headers", [])]
        hdr_str = " ".join(hdr_norm)
        rows = table["rows"]

        # --- G1 detection: header or rows mention First-Year + Undergraduates ---
        is_g1 = "first year" in hdr_str and "undergraduates" in hdr_str
        # Or: rows include "Tuition:" + "Required Fees"
        if not is_g1:
            row_text = " ".join(_normalize_label(r["label"]) for r in rows)
            is_g1 = "tuition" in row_text and "required fees" in row_text and (
                "food and housing" in row_text or "comprehensive" in row_text
            )

        if not is_g1:
            continue

        # Map each value column index → column role (FY or UG). Header-based
        # detection is most reliable; fallback to positional (col 0 = FY,
        # col 1 = UG).
        col_to_role: list[tuple[int, str]] = []
        for ci, hdr in enumerate(hdr_norm[1:]):
            if "first year" in hdr or "first-year" in hdr.replace(" ", "-"):
                col_to_role.append((ci, "FY"))
            elif "undergraduate" in hdr:
                col_to_role.append((ci, "UG"))
        if not col_to_role:
            col_to_role = [(0, "FY"), (1, "UG")]

        for row in rows:
            label_norm = _normalize_label(row["label"])
            # Walk _G1_ROWS in declared order so more-specific keys (e.g.
            # "tuition in district") win over the generic "tuition" rule.
            matched_pair = None
            for substr, fy_qn, ug_qn in _G1_ROWS:
                if substr in label_norm:
                    matched_pair = (fy_qn, ug_qn)
                    break
            if not matched_pair:
                continue
            fy_qn, ug_qn = matched_pair
            for col_idx, role in col_to_role:
                if col_idx >= len(row["values"]):
                    continue
                amt = _extract_currency(row["values"][col_idx])
                if amt is None:
                    continue
                qn = fy_qn if role == "FY" else ug_qn
                if qn and qn not in out:
                    out[qn] = {"value": amt, "source": "tier4_cleaner"}

    return out


# --- Resolver: H Financial Aid (~75 fields) ---
#
# H is the most complex section. We cover:
#   H1  Aid Awarded (23 fields) — 2-col need/non-need grid × 13 rows
#   H2  Students Awarded Aid (39 fields) — 13 lettered rows × 3 cohort cols
#   H2A Non-need-based Scholarships (12 fields) — rows N-Q × 3 cohort cols
#   H4  Bachelor's degree graduates count (1 field, inline)
#
# The H5 loan tables, H6 aid to nonresidents, H7 financial aid forms, and
# H8-H18 (scholarship availability / institutional aid) are deferred — they
# need checkbox detection or text extraction.

# Row letter offsets for H2 and H2A grids.
_H2_LETTER_OFFSETS = {letter: idx for idx, letter in enumerate("ABCDEFGHIJKLM")}
_H2A_LETTER_OFFSETS = {letter: idx for idx, letter in enumerate("NOPQ")}

# H2: header-fragment → base question number for the 3 cohort columns.
_H2_COL_BASES = [
    # (header fragment normalized, base offset for A→base+1)
    ("less than full time",             226),  # H.227..H.239
    ("first time full time first year", 200),  # H.201..H.213
    ("first time first year",           200),  # shorter templates
    ("full time undergrad",             213),  # H.214..H.226
]

# H2A: base offsets for N (offset 1) within each cohort column.
_H2A_COL_BASES = [
    ("less than full time",             "H.2A",  8),   # H.2A09-H.2A12
    ("first time full time first year", "H.2A",  0),   # H.2A01-H.2A04
    ("first time first year",           "H.2A",  0),
    ("full time undergrad",             "H.2A",  4),   # H.2A05-H.2A08
]

# H1: row substring → (need-based qn, non-need-based qn).
# Order matters. Institutional and External must check BEFORE tuition
# waivers because the Institutional row label includes
# "…excluding athletic aid and tuition waivers (reported below)" which
# otherwise gets claimed by the plain "tuition waivers" rule. Likewise
# the Total Scholarships row includes the word "scholarships" so it needs
# the explicit "total scholarships" rule to win over the plain federal/
# state/institutional fallbacks.
_H1_ROWS: list[tuple[str, str, str]] = [
    # Aggregate rows first
    ("total scholarships",                                    "H.109", "H.121"),
    ("total self help",                                       "H.113", "H.124"),
    # Work-study and detail rows (more specific than "federal")
    ("state and other",                                       "H.112", "H.123"),
    ("federal work study",                                    "H.111", ""),
    ("student loans from all sources",                        "H.110", "H.122"),
    # Institutional/External scholarship rows (must beat "tuition waivers")
    ("institutional endowed scholarships",                    "H.107", "H.119"),
    ("institutional",                                         "H.107", "H.119"),
    ("scholarships grants from external",                     "H.108", "H.120"),
    ("merit not awarded by the college",                      "H.108", "H.120"),
    # Single-term classifiers come last
    ("parent loans",                                          "H.114", "H.125"),
    ("tuition waivers",                                       "H.115", "H.126"),
    ("athletic awards",                                       "H.116", "H.127"),
    ("federal",                                               "H.105", "H.117"),
    ("state all states",                                      "H.106", "H.118"),
]


def _h_checked_option(block: str, label_re: str) -> bool:
    return bool(
        re.search(
            rf"(?:^|\n)\s*(?:-\s*\[[xX]\]\s*)?[xX]\s+{label_re}",
            block,
            re.IGNORECASE,
        )
    )


def _h_spaced_numbers(text: str) -> list[str]:
    """Extract right-aligned H-table values without claiming prose years."""
    values = re.findall(r"(?:^|\s{2,})(\$?\s*\d[\d,]*(?:\.\d+)?%?)", text)
    out: list[str] = []
    for value in values:
        num = _extract_number(value)
        if num is not None:
            out.append(num)
    return out


def _h_row_window(block: str, letter: str) -> str:
    lines = block.splitlines()
    start = None
    for idx, line in enumerate(lines):
        if re.match(rf"\s*{letter}(?:\s+|$)", line):
            start = idx
            break
    if start is None:
        return ""
    end = len(lines)
    for idx in range(start + 1, len(lines)):
        if re.match(r"\s*[A-Z](?:\s+|$)", lines[idx]) and lines[idx].strip()[0] in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
            end = idx
            break
    return "\n".join(lines[start:end])


def _h_layout_h1_rows(block: str) -> dict[str, dict]:
    out: dict[str, dict] = {}
    row_defs = [
        ("Total Scholarships/Grants", "H.109", "H.121"),
        ("Federal Work-Study", "H.111", ""),
        ("State and other", "H.112", "H.123"),
        ("Student loans from all sources", "H.110", "H.122"),
        ("State all states", "H.106", "H.118"),
        ("Scholarships/grants from external", "H.108", "H.120"),
        ("Total Self-Help", "H.113", "H.124"),
        ("Institutional:", "H.107", "H.119"),
        ("Parent Loans", "H.114", "H.125"),
        ("Tuition Waivers", "H.115", "H.126"),
        ("Athletic Awards", "H.116", "H.127"),
        ("Federal", "H.105", "H.117"),
    ]
    lines = block.splitlines()
    for idx, line in enumerate(lines):
        line_norm = _normalize_label(line)
        for label, need_qn, non_need_qn in row_defs:
            if _normalize_label(label) not in line_norm:
                continue
            window = "\n".join(lines[idx: idx + 6])
            amounts = [
                amount.replace(",", "")
                for amount in re.findall(r"\$\s*(\d[\d,]*(?:\.\d+)?)", window)
            ]
            if not amounts:
                continue
            if need_qn:
                out.setdefault(need_qn, {"value": amounts[0], "source": "tier4_cleaner"})
            if non_need_qn and len(amounts) > 1:
                out.setdefault(non_need_qn, {"value": amounts[1], "source": "tier4_cleaner"})
            break
    return out


def _h_layout_h2_rows(block: str) -> dict[str, dict]:
    out: dict[str, dict] = {}
    h2 = _section_between(block, r"H2\s+Number of Enrolled Students Awarded Aid", r"H2A\b")
    if not h2:
        return out
    for letter, offset in _H2_LETTER_OFFSETS.items():
        window = _h_row_window(h2, letter)
        nums = _h_spaced_numbers(window)
        if len(nums) >= 3:
            column_values = nums[-3:]
            bases = (200, 213, 226)
        elif len(nums) == 2:
            column_values = nums[-2:]
            bases = (200, 213)
        else:
            continue
        for value, base in zip(column_values, bases):
            out[f"H.{base + offset + 1}"] = {"value": value, "source": "tier4_cleaner"}
    return out


def resolve_h_financial_aid(
    tables: list[dict], markdown: str, schema: SchemaIndex
) -> dict[str, dict]:
    out: dict[str, dict] = {}

    h_block = _section_between(markdown, r"(?:H\.\s*FINANCIAL AID|H1\b)", r"(?:I\.\s*INSTRUCTIONAL FACULTY|CDS-I|$)")
    if h_block:
        if re.search(r"\bEstimated\b", h_block, re.IGNORECASE):
            if match := re.search(r"\b(\d{4}-\d{4})\s+estimated\b", h_block, re.IGNORECASE):
                out["H.101"] = {"value": f"{match.group(1)} estimated", "source": "tier4_cleaner"}
        if re.search(r"(?:^|\n)\s*(?:-\s*\[[xX]\]\s*)?x\s+Federal methodology \(FM\)", h_block, re.IGNORECASE):
            out["H.102"] = {"value": "X", "source": "tier4_cleaner"}

        h5 = _section_between(h_block, r"H5\b", r"(?:Aid to Undergraduate|H6\b|$)")
        h5_rows = {
            "A": ("H.501", "H.506", "H.511"),
            "B": ("H.502", "H.507", "H.512"),
            "C": ("H.503", "H.508", "H.513"),
            "D": ("H.504", "H.509", "H.514"),
            "E": ("H.505", "H.510", "H.515"),
        }
        for letter, qns in h5_rows.items():
            window = _h_row_window(h5, letter)
            values = _h_spaced_numbers(window)
            if len(values) >= 3:
                count_qn, percent_qn, average_qn = qns
                count, percent, average = values[-3:]
                out[count_qn] = {"value": count, "source": "tier4_cleaner"}
                out[percent_qn] = {"value": percent, "source": "tier4_cleaner"}
                out[average_qn] = {"value": average, "source": "tier4_cleaner"}

        h6 = _section_between(h_block, r"(?:^|\n)\s*H6\s+Indicate", r"(?:H7\b|CDS-H|$)")
        if re.search(r"(?:^|\n)\s*(?:-\s*\[\s*\]\s*)?x\s+Institutional need-based scholarship", h6, re.IGNORECASE):
            out["H.601"] = {"value": "X", "source": "tier4_cleaner"}
        if re.search(r"(?:^|\n)\s*(?:-\s*\[\s*\]\s*)?x\s+Institutional non-need-based scholarship", h6, re.IGNORECASE):
            out["H.602"] = {"value": "X", "source": "tier4_cleaner"}
        if match := re.search(
            r"non-need-based aid:\s*(\d[\d,]*)",
            h6,
            re.IGNORECASE | re.DOTALL,
        ):
            out["H.604"] = {"value": match.group(1).replace(",", ""), "source": "tier4_cleaner"}
        if match := re.search(
            r"Average dollar amount.*?nonresidents:\s*\$?\s*([\d,]+)",
            h6,
            re.IGNORECASE | re.DOTALL,
        ):
            out["H.605"] = {"value": match.group(1).replace(",", ""), "source": "tier4_cleaner"}
        if match := re.search(
            r"Total dollar amount of institutional financial aid awarded to undergraduate degree-?\s*seeking\s+nonresidents:\s*\$?\s*([\d,]+)",
            h_block,
            re.IGNORECASE | re.DOTALL,
        ):
            out["H.606"] = {"value": match.group(1).replace(",", ""), "source": "tier4_cleaner"}

        h7 = _section_between(h_block, r"H7\b", r"(?:Process for First-Year Students|H8\b|$)")
        for label, qn in [
            (r"Institution['’]s own financial aid form", "H.701"),
            (r"CSS/Financial Aid PROFILE", "H.702"),
        ]:
            if _h_checked_option(h7, label):
                out[qn] = {"value": "X", "source": "tier4_cleaner"}
        if _h_checked_option(h7, r"Other \(specify\):"):
            out["H.703"] = {"value": "X", "source": "tier4_cleaner"}
            if match := re.search(r"Other \(specify\):\s*(.+)", h7, re.IGNORECASE | re.DOTALL):
                text = re.sub(r"\s+", " ", match.group(1)).strip()
                text = re.sub(r"content-\s+assets", "content-assets", text)
                if text:
                    out["H.704"] = {"value": text, "source": "tier4_cleaner"}

        h8 = _section_between(h_block, r"H8\b", r"H9\b")
        for label, qn in [
            (r"FAFSA\b", "H.801"),
            (r"Institution['’]s own financial aid form", "H.802"),
            (r"CSS PROFILE", "H.803"),
            (r"State aid form", "H.804"),
            (r"Noncustodial PROFILE", "H.805"),
            (r"Business/Farm Supplement", "H.806"),
            (r"Other \(specify\):", "H.807"),
        ]:
            if _h_checked_option(h8, label):
                out[qn] = {"value": "X", "source": "tier4_cleaner"}

        h9 = _section_between(h_block, r"H9\b", r"H10\b")
        if match := re.search(
            r"Priority date for filing required financial aid forms:\s*([0-9]{1,2}-[A-Za-z]{3,4}|[A-Za-z]{3,4}-[0-9]{1,2}|\d{1,2}/\d{1,2})",
            h9,
            re.IGNORECASE,
        ):
            month_day = _split_month_day(match.group(1))
            if month_day:
                out["H.901"] = {"value": "X", "source": "tier4_cleaner"}
                out["H.902"] = {"value": month_day[0], "source": "tier4_cleaner"}
                out["H.903"] = {"value": month_day[1], "source": "tier4_cleaner"}
        if match := re.search(
            r"Deadline for filing required financial aid forms:\s*([0-9]{1,2}-[A-Za-z]{3,4}|[A-Za-z]{3,4}-[0-9]{1,2}|\d{1,2}/\d{1,2})",
            h9,
            re.IGNORECASE,
        ):
            month_day = _split_month_day(match.group(1))
            if month_day:
                out["H.904"] = {"value": "X", "source": "tier4_cleaner"}
                out["H.905"] = {"value": month_day[0], "source": "tier4_cleaner"}
                out["H.906"] = {"value": month_day[1], "source": "tier4_cleaner"}

        h10 = _section_between(h_block, r"H10\b", r"H11\b")
        if re.search(r"(?:^|\n)\s*(?:-\s*\[\s*\]\s*)?x\s+Yes\b", h10, re.IGNORECASE):
            out["H.1004"] = {"value": "X", "source": "tier4_cleaner"}
        if match := re.search(
            r"If yes, starting date:\s*([0-9]{1,2}-[A-Za-z]{3,4}|[A-Za-z]{3,4}-[0-9]{1,2}|\d{1,2}/\d{1,2})",
            h10,
            re.IGNORECASE,
        ):
            month_day = _split_month_day(match.group(1))
            if month_day:
                out["H.1005"] = {"value": month_day[0], "source": "tier4_cleaner"}
                out["H.1006"] = {"value": month_day[1], "source": "tier4_cleaner"}

        h11 = _section_between(h_block, r"H11\b", r"(?:Types of Aid Available|H12\b|$)")
        if match := re.search(
            r"Students must reply by \(date\):\s*([0-9]{1,2}-[A-Za-z]{3,4}|[A-Za-z]{3,4}-[0-9]{1,2}|\d{1,2}/\d{1,2})",
            h11,
            re.IGNORECASE,
        ):
            month_day = _split_month_day(match.group(1))
            if month_day:
                out["H.1101"] = {"value": month_day[0], "source": "tier4_cleaner"}
                out["H.1102"] = {"value": month_day[1], "source": "tier4_cleaner"}

        h12 = _section_between(h_block, r"H12\b", r"H13\b")
        for label, qn in [
            (r"Federal Direct Subsidized Loans", "H.1201"),
            (r"Federal Direct Unsubsidized Loans", "H.1202"),
            (r"Federal Direct PLUS Loans", "H.1203"),
            (r"Federal Nursing Loans", "H.1204"),
            (r"State Loans", "H.1205"),
            (r"College/university loans from institutional funds", "H.1206"),
        ]:
            if _h_checked_option(h12, label):
                out[qn] = {"value": "X", "source": "tier4_cleaner"}

        h13 = _section_between(h_block, r"H13\b", r"(?:CDS-H|H14\b|$)")
        for label, qn in [
            (r"Federal Pell", "H.1301"),
            (r"Federal SEOG", "H.1302"),
            (r"State scholarships/grants", "H.1303"),
            (r"Private scholarships", "H.1304"),
        ]:
            if re.search(r"(?:^|\n)\s*(?:-\s*\[\s*\]\s*)?x\s+" + label, h13, re.IGNORECASE):
                out[qn] = {"value": "X", "source": "tier4_cleaner"}
        if re.search(
            r"(?:^|\n)\s*(?:-\s*\[\s*\]\s*)?x\s+College/university scholarship or grant aid from institutional funds",
            h_block,
            re.IGNORECASE,
        ):
            out["H.1305"] = {"value": "X", "source": "tier4_cleaner"}

        h14 = _section_between(h_block, r"H14\b", r"H15\b")
        h14_rows = [
            (r"Academics", "H.1401", "H.1411"),
            (r"Alumni affiliation", "H.1402", "H.1412"),
            (r"Art", "H.1403", "H.1413"),
            (r"Athletics", "H.1404", "H.1414"),
            (r"Job skills", "H.1405", "H.1415"),
            (r"Leadership", "H.1407", "H.1416"),
            (r"Music/drama", "H.1408", "H.1417"),
            (r"State/district residency", "H.1410", "H.1419"),
        ]
        for label, non_need_qn, need_qn in h14_rows:
            if match := re.search(label + r"\s+x\s+x", h14, re.IGNORECASE):
                out[non_need_qn] = {"value": "X", "source": "tier4_cleaner"}
                out[need_qn] = {"value": "X", "source": "tier4_cleaner"}
            elif re.search(label + r"\s+x\s*(?:\n|$)", h14, re.IGNORECASE):
                out[non_need_qn] = {"value": "X", "source": "tier4_cleaner"}

        if match := re.search(
            r"H15\b.*?please\s+provide\s+details\s+below:\s*(.+?)\s*(?:CDS-H|I\.\s*INSTRUCTIONAL FACULTY|$)",
            h_block,
            re.IGNORECASE | re.DOTALL,
        ):
            text = re.sub(r"\s+", " ", match.group(1)).strip()
            text = text.replace("on- campus", "on-campus")
            text = re.sub(r"\bW e\b", "We", text)
            text = re.split(r"\s+(?:-\s+\[|Students must reply by|H1[234]\b|##\s+)", text, maxsplit=1)[0].strip()
            if (
                re.fullmatch(r"Common Data Set\s+20\d{2}-\s*20\d{2}", text, re.IGNORECASE)
                or "Non-Need Based" in text
                or "| |" in text
            ):
                text = ""
            if text:
                out["H.1501"] = {"value": text, "source": "tier4_cleaner"}

        h1_layout = _section_between(h_block, r"Aid Awarded", r"H2\b")
        for qn, rec in _h_layout_h1_rows(h1_layout).items():
            out.setdefault(qn, rec)
        for qn, rec in _h_layout_h2_rows(h_block).items():
            out.setdefault(qn, rec)

    # --- H1 Aid Awarded (need-based / non-need-based grid) ---
    for table in tables:
        hdr_norm = [_normalize_label(h) for h in table.get("headers", [])]
        joined_hdr = " ".join(hdr_norm)
        is_h1 = ("need based" in joined_hdr and "non need based" in joined_hdr)
        if not is_h1:
            continue
        # Map value columns: the left column is Need-based, right is
        # Non-need-based. Both headers can contain "non need" because the
        # need-based header often reads "Need-based (Include non-need-based
        # aid used to meet need)". Use startswith to disambiguate.
        col_to_kind: list[tuple[int, str]] = []
        for ci, hdr in enumerate(hdr_norm[1:]):
            h = hdr.strip()
            if h.startswith("non need"):
                col_to_kind.append((ci, "nn"))
            elif h.startswith("need"):
                col_to_kind.append((ci, "nb"))
        if not col_to_kind:
            continue

        for row in table["rows"]:
            label_norm = _normalize_label(row["label"])
            matched = None
            for substr, nb_qn, nn_qn in _H1_ROWS:
                if substr in label_norm:
                    matched = (nb_qn, nn_qn)
                    break
            if not matched:
                continue
            nb_qn, nn_qn = matched
            for col_idx, kind in col_to_kind:
                if col_idx >= len(row["values"]):
                    continue
                amt = _extract_currency(row["values"][col_idx])
                if amt is None:
                    continue
                qn = nb_qn if kind == "nb" else nn_qn
                if qn and qn not in out:
                    out[qn] = {"value": amt, "source": "tier4_cleaner"}

    # --- H2 Students Awarded Aid (letter rows × 3 cohort columns) ---
    # --- H2A Non-need-based (rows N-Q × 3 cohort columns) ---
    for table in tables:
        hdr_norm = [_normalize_label(h) for h in table.get("headers", [])]
        hdr_str = " ".join(hdr_norm)
        # Detect H2/H2A by header signatures
        is_h2_like = (
            ("first time" in hdr_str and "full time" in hdr_str)
            or ("undergrad" in hdr_str and "less than" in hdr_str)
        )
        rows = table["rows"]
        h2_continuation_rows = {
            r["label"].strip()
            for r in rows
            if r["label"].strip() in {"I", "J", "K", "L", "M"}
        }
        is_h2_continuation = bool(h2_continuation_rows) and not any(
            r["label"].strip() in set("ABCDEFGH") for r in rows
        )
        if not is_h2_like and not is_h2_continuation:
            continue

        # Map each value column index → (grid_kind, base_offset)
        #   grid_kind ∈ {"H2", "H2A"} — picked based on row letters present.
        col_to_h2_base: list[tuple[int, int]] = []
        col_to_h2a_offset: list[tuple[int, int]] = []
        for ci, hdr in enumerate(hdr_norm[1:]):
            # H2 bases
            for frag, base in _H2_COL_BASES:
                if frag in hdr:
                    col_to_h2_base.append((ci, base))
                    break
            # H2A bases
            for frag, prefix, ofs in _H2A_COL_BASES:
                if frag in hdr:
                    col_to_h2a_offset.append((ci, ofs))
                    break

        # Determine which grid this table is: if any row label is a letter
        # in A-M treat as H2; if N-Q treat as H2A. Some tables mix both
        # (tables occasionally concatenate rows).
        has_h2_rows = any(r["label"].strip() in _H2_LETTER_OFFSETS for r in rows)
        has_h2a_rows = any(r["label"].strip() in _H2A_LETTER_OFFSETS for r in rows)

        for row in rows:
            letter = row["label"].strip()
            values = row["values"]

            if letter in _H2_LETTER_OFFSETS and is_h2_continuation:
                ofs = _H2_LETTER_OFFSETS[letter] + 1
                # Docling emits the I-M continuation table with blank
                # headers and the prose label as the first value cell.
                for raw, base in zip(values[1:4], (200, 213, 226)):
                    num = _extract_number(raw)
                    if num is None:
                        continue
                    qn = f"H.{base + ofs}"
                    if qn not in out:
                        out[qn] = {"value": num, "source": "tier4_cleaner"}
            elif letter in _H2_LETTER_OFFSETS and has_h2_rows:
                ofs = _H2_LETTER_OFFSETS[letter] + 1  # A=1, B=2, …, M=13
                for col_idx, base in col_to_h2_base:
                    if col_idx >= len(values):
                        continue
                    num = _extract_number(values[col_idx])
                    if num is None:
                        continue
                    qn = f"H.{base + ofs}"
                    if qn not in out:
                        out[qn] = {"value": num, "source": "tier4_cleaner"}
            elif letter in _H2A_LETTER_OFFSETS and has_h2a_rows:
                ofs = _H2A_LETTER_OFFSETS[letter] + 1  # N=1, O=2, P=3, Q=4
                for col_idx, base_ofs in col_to_h2a_offset:
                    if col_idx >= len(values):
                        continue
                    num = _extract_number(values[col_idx])
                    if num is None:
                        continue
                    qn = f"H.2A{base_ofs + ofs:02d}"
                    if qn not in out:
                        out[qn] = {"value": num, "source": "tier4_cleaner"}

    # --- H4 Bachelor's degree graduates count (inline) ---
    # Anchor: the *actual* H4 question line, not the preceding prose that
    # mentions "H4 and H5". The distinctive phrase is "Exclude students who
    # transferred into your institution." — it terminates the H4 prompt.
    m = re.search(
        r"(?mi)Exclude students who transferred into your institution",
        markdown,
    )
    if m:
        # Value appears immediately after the prompt, before the H5 section.
        window = markdown[m.end(): m.end() + 400]
        num_m = re.search(r"\b(\d[\d,]*)\b", window)
        if num_m:
            val = _extract_number(num_m.group(1))
            if val and "H.401" not in out:
                out["H.401"] = {"value": val, "source": "tier4_cleaner"}

    return out


# --- Resolver: D Transfer Admission (partial) ---
#
# D2 Fall Applicants table: 3 rows (Applicants, Admitted, Enrolled) ×
# 5 columns (Men, Women, Another Gender, Unknown, Total). Schema collapses
# "Another Gender" + "Unknown" into a single Unknown-gender field, so we
# only emit values for the Men/Women/Unknown/Total columns.

_D2_ROW_BASES = [
    # (label substring, base offset for men=base+1)
    ("applicants", 200),   # D.201 (men), D.202 (women), D.203 (unknown), D.204 (total)
    ("admitted",   204),   # D.205-D.208
    ("enrolled",   208),   # D.209-D.212
]

# Column header fragment → gender slot index (1=men, 2=women, 3=unknown, 4=total)
_D2_COL_GENDERS = [
    ("another gender", 3),
    ("unknown",        3),
    ("men",            1),
    ("women",          2),
    ("total",          4),
]


def _extract_number_unit(text: str) -> tuple[str, str] | None:
    match = re.search(
        r"\b(\d+(?:\.\d+)?)\s+(credit|credits|course|courses)(?=\s|[A-Z]|$)",
        text,
        re.IGNORECASE,
    )
    if not match:
        return None
    unit = match.group(2).lower()
    if unit.endswith("s"):
        unit = unit[:-1]
    return match.group(1), unit


def resolve_d_transfer(
    tables: list[dict], markdown: str, schema: SchemaIndex
) -> dict[str, dict]:
    out: dict[str, dict] = {}

    d_full = _section_between(
        markdown,
        r"TRANSFER\s+ADMISSION",
        r"(?:E\.\s*ACADEMIC\s+OFFERINGS|CDS-E|$)",
    )
    d_block = _section_between(markdown, r"TRANSFER\s+ADMISSION", r"D10\b")
    if d_block:
        if (
            re.search(r"\bxDoes your institution enroll transfer students", d_block, re.IGNORECASE)
            or re.search(r"Does your institution enroll transfer\s+students\?.{0,80}[✔xX]\s*Yes", d_block, re.IGNORECASE | re.DOTALL)
        ):
            out["D.101"] = {"value": "Yes", "source": "tier4_cleaner"}
        if re.search(r"advanced standing credit by transferring credits earned from course work.{0,160}[✔xX]\s*Yes", d_block, re.IGNORECASE | re.DOTALL):
            out["D.102"] = {"value": "Yes", "source": "tier4_cleaner"}
        d102 = _extract_yes_no_by_layout(
            d_block,
            r"credit by transferring credits earned from course work",
        )
        if d102:
            out["D.102"] = {"value": d102, "source": "tier4_cleaner"}

        d2_rows = [
            (r"\bM\s*en\b", ("D.201", "D.205", "D.209")),
            (r"\bW\s*omen\b", ("D.202", "D.206", "D.210")),
            (r"\bAnother\s+Gender\b", ("D.203", "D.207", "D.211")),
            (r"\bTotal\b", ("D.204", "D.208", "D.212")),
        ]
        d2_section = _section_between(d_block, r"D2\b", r"D3-D11\b")
        for row_re, qns in d2_rows:
            match = re.search(
                row_re + r"\s+(\d[\d,]*)\s+(\d[\d,]*)\s+(\d[\d,]*)",
                d2_section,
                re.IGNORECASE,
            )
            if match:
                for qn, raw in zip(qns, match.groups()):
                    out[qn] = {"value": raw.replace(",", ""), "source": "tier4_cleaner"}

        if re.search(r"(?:^|\n)\s*[✔xX]\s+Fall\b", d_block, re.IGNORECASE):
            out["D.301"] = {"value": "X", "source": "tier4_cleaner"}
        if re.search(r"(?:^|\n)\s*[✔xX]\s+Winter\b", d_block, re.IGNORECASE):
            out["D.302"] = {"value": "X", "source": "tier4_cleaner"}
        if re.search(r"(?:^|\n)\s*[✔xX]\s+Spring\b", d_block, re.IGNORECASE):
            out["D.303"] = {"value": "X", "source": "tier4_cleaner"}
        if re.search(r"(?:^|\n)\s*[✔xX]\s+Summer\b", d_block, re.IGNORECASE):
            out["D.304"] = {"value": "X", "source": "tier4_cleaner"}

        d401 = _extract_wrapped_yes_no_by_layout(
            d_block,
            r"D4\b",
            r"D5\b",
        )
        if not d401:
            d401 = _extract_yes_no_by_layout(
                _section_between(d_block, r"D4\b", r"D5\b"),
                r"credits completed or else must apply as an entering first",
            )
        if not d401:
            d401 = _extract_yes_no_block_by_layout(
                _section_between(d_block, r"D4\b", r"D5\b"),
                r"Must a transfer applicant",
                r"If yes",
            )
        if not d401 and re.search(
            r"entering first-.{0,700}[✔xX].{0,120}No\b",
            d_block,
            re.IGNORECASE | re.DOTALL,
        ):
            d401 = "No"
        if d401:
            out["D.401"] = {"value": d401, "source": "tier4_cleaner"}

        d5_values = {
            r"High school transcript": ("D.501", "Required of Some"),
            r"College transcript\(s\)": ("D.502", "Required of All"),
            r"Essay or personal": ("D.503", "Not Required"),
            r"Interview": ("D.504", "Not Required"),
            r"Standardized test scores": ("D.505", "Not Required"),
            r"Statement of good": ("D.506", "Not Required"),
        }
        for row_re, (qn, value) in d5_values.items():
            if re.search(row_re + r".{0,520}[✔xX]", d_block, re.IGNORECASE | re.DOTALL):
                out[qn] = {"value": value, "source": "tier4_cleaner"}
        d5_section = _section_between(d_block, r"D5\.", r"D6\.")
        for raw_line in d5_section.splitlines():
            marker = re.search(r"[✔xX]", raw_line)
            if not marker:
                continue
            label_norm = _normalize_label(raw_line[:marker.start()])
            qn = None
            if "high school transcript" in label_norm:
                qn = "D.501"
            elif "college transcript" in label_norm:
                qn = "D.502"
            elif "essay or personal" in label_norm:
                qn = "D.503"
            elif "interview" in label_norm:
                qn = "D.504"
            elif "standardized test scores" in label_norm:
                qn = "D.505"
            elif "statement of good" in label_norm:
                qn = "D.506"
            if not qn:
                continue
            if marker.start() < 260:
                value = "Required of All"
            elif marker.start() < 500:
                value = "Required of Some"
            else:
                value = "Not Required"
            out[qn] = {"value": value, "source": "tier4_cleaner"}

        if match := re.search(r"D7\b.*?specify (?:on|\(on) a 4\.0 scale\)?:\s*([0-4](?:\.\d+)?)", d_block, re.IGNORECASE | re.DOTALL):
            out["D.701"] = {"value": match.group(1), "source": "tier4_cleaner"}

        if match := re.search(
            r"D8\b.*?specific to transfer applicants:\s*(.+?)\s*D9\b",
            d_block,
            re.IGNORECASE | re.DOTALL,
        ):
            text = re.sub(r"\s+", " ", match.group(1)).strip()
            if text and text not in {"-", "—"}:
                out["D.801"] = {"value": text, "source": "tier4_cleaner"}

        d9 = _section_between(d_block, r"D9\b", r"$")
        d9_rows = [
            ("Fall", "D.909", "D.910", "D.925", "D.926", "D.933"),
            ("Spring", "D.913", "D.914", "D.929", "D.930", "D.935"),
        ]
        for term, close_m_qn, close_d_qn, reply_m_qn, reply_d_qn, rolling_qn in d9_rows:
            line_match = re.search(rf"(?:^|\n)\s*(?:D9\s+)?{term}\b([^\n]*)", d9, re.IGNORECASE)
            if not line_match:
                continue
            line = line_match.group(1)
            dates = re.findall(r"\b\d{1,2}/\d{1,2}\b", line)
            if dates:
                month_day = _split_month_day(dates[0])
                if month_day:
                    out[close_m_qn] = {"value": month_day[0], "source": "tier4_cleaner"}
                    out[close_d_qn] = {"value": month_day[1], "source": "tier4_cleaner"}
                if len(dates) >= 2:
                    month_day = _split_month_day(dates[1])
                    if month_day:
                        notif_m_qn = "D.917" if term == "Fall" else "D.921"
                        notif_d_qn = "D.918" if term == "Fall" else "D.922"
                        out[notif_m_qn] = {"value": month_day[0], "source": "tier4_cleaner"}
                        out[notif_d_qn] = {"value": month_day[1], "source": "tier4_cleaner"}
            else:
                nums = re.findall(r"\b\d{1,2}\b", line)
                if len(nums) >= 2:
                    out[close_m_qn] = {"value": nums[0], "source": "tier4_cleaner"}
                    out[close_d_qn] = {"value": nums[1], "source": "tier4_cleaner"}
                if len(nums) >= 4:
                    out[reply_m_qn] = {"value": nums[-2], "source": "tier4_cleaner"}
                    out[reply_d_qn] = {"value": nums[-1], "source": "tier4_cleaner"}
            if re.search(r"(?<!\w)[xX](?!\w)\s*$", line):
                out[rolling_qn] = {"value": "X", "source": "tier4_cleaner"}

    d_tail = d_full or markdown
    if d_tail:
        d1001 = _extract_wrapped_yes_no_by_layout(
            d_tail,
            r"D10\s+.{0,300}open admission policy",
            r"D11\b",
        )
        if d1001:
            out["D.1001"] = {"value": d1001, "source": "tier4_cleaner"}

        if match := re.search(
            r"D11\b\s+Describe additional requirements for transfer admission, if applicable:\s*(.+?)\s*D12-D17\b",
            d_tail,
            re.IGNORECASE | re.DOTALL,
        ):
            text = re.sub(r"\s+", " ", match.group(1)).strip()
            if text:
                out["D.1101"] = {"value": text, "source": "tier4_cleaner"}

        if match := re.search(
            r"D12\b.*?course that may be transferred for credit:\s*(\d+(?:\.\d+)?)",
            d_tail,
            re.IGNORECASE | re.DOTALL,
        ):
            out["D.1201"] = {"value": match.group(1), "source": "tier4_cleaner"}

        for start, end, num_qn, unit_qn in [
            ("D13", "D14", "D.1301", "D.1302"),
            ("D14", "D15", "D.1401", "D.1402"),
            ("D19", "D20", "D.1901", "D.1902"),
            ("D20", "D21", "D.2001", "D.2002"),
        ]:
            block = _section_between(d_tail, rf"{start}\b", rf"{end}\b")
            if extracted := _extract_number_unit(block):
                out[num_qn] = {"value": extracted[0], "source": "tier4_cleaner"}
                out[unit_qn] = {"value": extracted[1], "source": "tier4_cleaner"}

        if match := re.search(
            r"D15\b.*?associate degree:\s*(\d+(?:\.\d+)?)",
            d_tail,
            re.IGNORECASE | re.DOTALL,
        ):
            out["D.1501"] = {"value": match.group(1), "source": "tier4_cleaner"}

        if match := re.search(
            r"D16\b.*?bachelor['’]s degree:\s*(\d+(?:\.\d+)?)",
            d_tail,
            re.IGNORECASE | re.DOTALL,
        ):
            out["D.1601"] = {"value": match.group(1), "source": "tier4_cleaner"}

        d18 = _section_between(d_tail, r"D18\b", r"D19\b")
        for row_re, qn in [
            (r"American Council on Education \(ACE\)", "D.1801"),
            (r"College Level Examination Program \(CLEP\)", "D.1802"),
            (r"DANTES Subject Standardized Tests \(DSST\)", "D.1803"),
        ]:
            value = _extract_yes_no_by_layout(d18, row_re)
            if value:
                out[qn] = {"value": value, "source": "tier4_cleaner"}

        d2101 = _extract_wrapped_yes_no_by_layout(
            d_tail,
            r"D21\s+.{0,300}military/veteran credit transfer policies",
            r"D22\b",
        )
        if d2101:
            out["D.2101"] = {"value": d2101, "source": "tier4_cleaner"}

        if match := re.search(
            r"If yes, please provide the URL where the policy can be located:\s*(https?://\S+)",
            d_tail,
            re.IGNORECASE,
        ):
            out["D.2102"] = {"value": match.group(1), "source": "tier4_cleaner"}

        if match := re.search(
            r"D22\b\s+Describe other military/veteran transfer credit policies unique to your institution:\s*(.+?)\s*(?:CDS-D|E\.\s*ACADEMIC OFFERINGS|$)",
            d_tail,
            re.IGNORECASE | re.DOTALL,
        ):
            text = re.sub(r"\s+", " ", match.group(1)).strip()
            if text:
                out["D.2201"] = {"value": text, "source": "tier4_cleaner"}

    for table in tables:
        hdr_norm = [_normalize_label(h) for h in table.get("headers", [])]
        hdr_str = " ".join(hdr_norm)
        # Detect D2 by header with gender column labels AND
        # row labels mentioning applicants/admitted/enrolled.
        has_gender_cols = "men" in hdr_str and "women" in hdr_str
        row_text = " ".join(_normalize_label(r["label"]) for r in table["rows"])
        has_transfer_rows = any(k in row_text for k in
                                ("applicant", "admitted", "enrolled"))
        # Narrow to transfer section: require "total" or "transfer" context
        # in the table's section name (C1 also has these but its section
        # starts with C1/First-time/C.).
        section_norm = _normalize_label(table.get("section", ""))
        is_d2 = (has_gender_cols and has_transfer_rows and (
            "transfer" in section_norm
            or "d1" in section_norm
            or "d2" in section_norm
        ))
        if not is_d2:
            continue

        # Map column headers → gender slot (1..4). Skip headers matching
        # multiple; first rule wins (order above picks "another gender"
        # before "unknown" which aliases to slot 3).
        col_to_slot: list[tuple[int, int]] = []
        for ci, hdr in enumerate(hdr_norm[1:]):
            for frag, slot in _D2_COL_GENDERS:
                if frag in hdr:
                    col_to_slot.append((ci, slot))
                    break

        if not col_to_slot:
            continue

        for row in table["rows"]:
            label_norm = _normalize_label(row["label"])
            matched_base = None
            for substr, base in _D2_ROW_BASES:
                if substr in label_norm:
                    matched_base = base
                    break
            if matched_base is None:
                continue
            for col_idx, slot in col_to_slot:
                if col_idx >= len(row["values"]):
                    continue
                num = _extract_number(row["values"][col_idx])
                if num is None:
                    continue
                qn = f"D.{matched_base + slot}"
                if qn not in out:
                    out[qn] = {"value": num, "source": "tier4_cleaner"}

    return out


# --- Resolver: Checkboxes (~78 fields) ---
#
# Scans markdown for checkbox-style lines and matches them against schema
# fields whose value_type is "x". Covers the 5 cleanest subsections whose
# row labels are globally unique:
#   Degrees Offered       (A.501-A.512, 12 fields)
#   Special Study Options (E.101-E.119, 19 fields)
#   Required Course Work  (E.201-E.213, 13 fields)
#   Activities Offered    (F.201-F.221, 21 fields)
#   Housing               (F.401-F.413, 13 fields)
#
# The 2024-25 Docling output has several checkbox dialects:
#   `- [x] Label`                 (canonical markdown)
#   `- [ ] X Label`               (Harvard — unchecked brackets, label
#                                  prefixed with literal X)
#   `- [x] ☒ Label`               (Yale)
#   `- X Label`                    (F2 activities — list marker + X)
#   `X\n\nLabel`                  (free-form paragraph groups; deferred)
#
# A match emits {"value": "X"} for checked; unchecked rows are simply
# omitted (binary fields default to "not checked" when missing).

_CHECKBOX_SUBSECTIONS = {
    "Degrees Offered",
    "Special Study Options",
    "Required Course Work",
    "Activities Offered",
    "Housing",
}


def resolve_checkboxes(
    tables: list[dict], markdown: str, schema: SchemaIndex
) -> dict[str, dict]:
    out: dict[str, dict] = {}

    # Build {normalized_question: qn}. Drop entries whose label would
    # collide with another checkbox field in a different subsection — the
    # generic "Other (specify):" row is the main offender and shouldn't
    # get mis-assigned.
    label_to_qn: dict[str, str] = {}
    ambiguous: set[str] = set()
    for f in schema.fields:
        if f["value_type"] != "x":
            continue
        if f["subsection"] not in _CHECKBOX_SUBSECTIONS:
            continue
        q_norm = f["_q_norm"]
        if q_norm in label_to_qn and label_to_qn[q_norm] != f["question_number"]:
            ambiguous.add(q_norm)
        else:
            label_to_qn[q_norm] = f["question_number"]
    for q in ambiguous:
        label_to_qn.pop(q, None)

    # Patterns that capture the checked-state and the label.
    checked_bracket = re.compile(r"-\s*\[[xX☒✓]\]\s*(?:[Xx☒✓]\s+)?(.+?)\s*$")
    bracket_with_marker = re.compile(r"-\s*\[\s*\]\s*[Xx☒✓]\s+(.+?)\s*$")
    bare_x_line = re.compile(r"^-\s+[Xx☒✓]\s+(.+?)\s*$")

    for raw_line in markdown.split("\n"):
        line = raw_line.strip()
        # Collect candidate (check, label) pairs for this line.
        candidates: list[str] = []
        if m := checked_bracket.match(line):
            candidates.append(m.group(1))
        elif m := bracket_with_marker.match(line):
            candidates.append(m.group(1))
        elif m := bare_x_line.match(line):
            candidates.append(m.group(1))
        # Also scan inside table rows for ☒/[x] prefixes. Yale emits
        # checkboxes inside pipe-delimited table cells (e.g.
        # "| ☒ Accelerated program | ☒ Honors program |").
        if line.startswith("|") and line.endswith("|"):
            for cell in line.strip("|").split("|"):
                c = cell.strip()
                if not c:
                    continue
                cm = re.match(r"^(?:☒|\[x\]|\[X\])\s*(.+)$", c)
                if cm:
                    candidates.append(cm.group(1))
        if not candidates:
            continue
        for label in candidates:
            label_norm = _normalize_label(label)
            qn = label_to_qn.get(label_norm)
            if qn and qn not in out:
                out[qn] = {"value": "X", "source": "tier4_cleaner"}

    return out


def resolve_e_academic_offerings(
    tables: list[dict], markdown: str, schema: SchemaIndex
) -> dict[str, dict]:
    out: dict[str, dict] = {}

    e_block = _section_between(
        markdown,
        r"(?:E\.\s*ACADEMIC\s+OFFERINGS\s+AND\s+POLICIES|E1\b)",
        r"(?:F\.\s*STUDENT\s+LIFE|CDS-E|$)",
    )
    if not e_block:
        return out

    e1 = _section_between(e_block, r"E1\b|Special study options", r"E2\b|E3\b")
    for qn, aliases in [
        ("E.101", ["Accelerated program"]),
        ("E.102", ["Comprehensive transition"]),
        ("E.103", ["Cross-registration"]),
        ("E.104", ["Distance learning"]),
        ("E.105", ["Double major"]),
        ("E.106", ["Dual enrollment"]),
        ("E.107", ["English as a Second Language", "ESL"]),
        ("E.108", ["Exchange student program"]),
        ("E.109", ["External degree program"]),
        ("E.110", ["Honors program"]),
        ("E.111", ["Independent study"]),
        ("E.112", ["Internships"]),
        ("E.113", ["Liberal arts/career combination"]),
        ("E.114", ["Student-designed major"]),
        ("E.115", ["Study abroad"]),
        ("E.116", ["Teacher certification program"]),
        ("E.117", ["Undergraduate Research"]),
        ("E.118", ["Weekend college"]),
    ]:
        if _layout_option_checked(e1, aliases):
            out[qn] = {"value": "X", "source": "tier4_cleaner"}

    if re.search(
        r"(?:^|\n)\s*x\s+Undergraduate Research\b|(?:^|\n)\s*x\s*\n\s*Undergraduate Research\b",
        e1,
        re.IGNORECASE,
    ):
        out["E.117"] = {"value": "X", "source": "tier4_cleaner"}

    other_specify_re = r"(?:^|\n)\s*(?:-\s*\[\s*\]\s*)?x\s+Other \(specify\):"
    if re.search(other_specify_re, e1, re.IGNORECASE):
        out["E.119"] = {"value": "X", "source": "tier4_cleaner"}
        if match := re.search(
            r"Other \(specify\):\s*(?:\n\s*)+([^\n]+)",
            e1,
            re.IGNORECASE,
        ):
            value = match.group(1).strip()
            if value:
                out["E.120"] = {"value": value, "source": "tier4_cleaner"}

    e3 = _section_between(e_block, r"E3\b|Areas in which", r"$")
    for qn, aliases in [
        ("E.301", ["Arts/fine arts"]),
        ("E.302", ["Computer literacy"]),
        ("E.303", ["English (including composition)", "English"]),
        ("E.304", ["Foreign languages"]),
        ("E.305", ["History"]),
        ("E.306", ["Physical Education"]),
        ("E.307", ["Humanities"]),
        ("E.308", ["Intensive writing"]),
        ("E.309", ["Mathematics"]),
        ("E.310", ["Philosophy"]),
        ("E.311", ["Sciences (biological or physical)", "Sciences"]),
        ("E.312", ["Social science"]),
    ]:
        if _layout_option_checked(e3, aliases):
            out[qn] = {"value": "X", "source": "tier4_cleaner"}

    other_describe_re = r"(?:^|\n)\s*(?:-\s*\[\s*\]\s*)?x\s+Other \(describe\):"
    if re.search(other_describe_re, e3, re.IGNORECASE):
        out["E.313"] = {"value": "X", "source": "tier4_cleaner"}
        if match := re.search(
            r"Other \(describe\):\s*(?:\n\s*)+([^\n]+)",
            e3,
            re.IGNORECASE,
        ):
            value = match.group(1).strip()
            if value:
                out["E.314"] = {"value": value, "source": "tier4_cleaner"}

    return out


def _layout_option_checked(block: str, aliases: list[str]) -> bool:
    markers = r"[xX✔☒✓]"
    for raw_line in block.splitlines():
        if not re.search(markers, raw_line):
            continue
        line_norm = _normalize_label(raw_line)
        for alias in aliases:
            alias_norm = _normalize_label(alias)
            if alias_norm in line_norm:
                before = raw_line[: raw_line.lower().find(alias.lower().split()[0])] if alias.split() else raw_line
                if re.search(markers, before[-20:]) or re.search(r"\[[xX]\]", raw_line):
                    return True
                if re.search(rf"{markers}\s+.*{re.escape(alias.split()[0])}", raw_line, re.IGNORECASE):
                    return True
    return False


def resolve_f_student_life(
    tables: list[dict], markdown: str, schema: SchemaIndex
) -> dict[str, dict]:
    out: dict[str, dict] = {}

    f_block = _section_between(
        markdown,
        r"(?:F\.\s*STUDENT LIFE|F1\b|F3\b|F4\b)",
        r"(?:G\.\s*ANNUAL EXPENSES|CDS-G|$)",
    )
    if not f_block:
        return out

    f2 = _section_between(f_block, r"F2\b|Activities offered", r"F3\b")
    for qn, aliases in [
        ("F.201", ["Campus Ministries"]),
        ("F.202", ["Choral groups"]),
        ("F.203", ["Concert band"]),
        ("F.204", ["Dance"]),
        ("F.205", ["Drama/theater"]),
        ("F.206", ["International Student Organization"]),
        ("F.207", ["Jazz band"]),
        ("F.208", ["Literary magazine"]),
        ("F.209", ["Marching band"]),
        ("F.210", ["Model UN"]),
        ("F.211", ["Music ensembles"]),
        ("F.212", ["Musical theater"]),
        ("F.213", ["Opera"]),
        ("F.214", ["Pep band"]),
        ("F.215", ["Radio station"]),
        ("F.216", ["Student government"]),
        ("F.217", ["Student newspaper"]),
        ("F.218", ["Student-run film society"]),
        ("F.219", ["Symphony orchestra"]),
        ("F.220", ["Television station"]),
        ("F.221", ["Yearbook"]),
    ]:
        if _layout_option_checked(f2, aliases):
            out[qn] = {"value": "X", "source": "tier4_cleaner"}

    f3 = _section_between(f_block, r"F3\b", r"F4\b")
    if f3:
        army = _section_between(f3, r"Army ROTC is offered:", r"Naval ROTC is offered:")
        if re.search(r"\bHofstra University\b", army, re.IGNORECASE):
            out["F.301"] = {"value": "At cooperating institution", "source": "tier4_cleaner"}
            out["F.302"] = {"value": "Hofstra University", "source": "tier4_cleaner"}

        # pypdf layout can wrap the Air Force cooperating institution name
        # across the preceding name-column line and the row itself.
        if re.search(r"\bManhattan\s+Air Force ROTC is offered:.*?\bCollege\b", f3, re.IGNORECASE | re.DOTALL):
            out["F.306"] = {"value": "At cooperating institution", "source": "tier4_cleaner"}
            out["F.307"] = {"value": "Manhattan College", "source": "tier4_cleaner"}
        if re.search(r"Air Force ROTC is offered:.{0,80}[✔xX]\s*(?:\n\s*)?On campus", f3, re.IGNORECASE | re.DOTALL):
            out["F.306"] = {"value": "On campus", "source": "tier4_cleaner"}

    f4 = _section_between(f_block, r"(?:F4\b|Housing:)", r"(?:CDS-F|G1\b|G\.\s*ANNUAL EXPENSES|$)")
    if re.search(r"(?:^|\n)\s*(?:-\s*\[\s*\]\s*)?x\s+Coed dorms\b", f4, re.IGNORECASE):
        out["F.401"] = {"value": "X", "source": "tier4_cleaner"}

    return out


# --- Resolver: F1 Percent Participating + Average Age (16 fields) ---
#
# One 2-column table: First-time, first-year | Undergraduates.
# Six percentage rows (F.101-F.106, F.109-F.114) + two age rows
# (F.107-F.108, F.115-F.116).

_F1_ROWS: list[tuple[str, str, str]] = [
    # (label substring [normalized], FY qn, UG qn)
    ("percent who are from out of state",        "F.101", "F.109"),
    ("percent of men who join fraternities",     "F.102", "F.110"),
    ("percent of women who join sororities",     "F.103", "F.111"),
    ("percent who live in college owned",        "F.104", "F.112"),
    ("percent who live off campus",              "F.105", "F.113"),
    ("percent of students age 25",               "F.106", "F.114"),
    ("average age of full time students",        "F.107", "F.115"),
    ("average age of all students",              "F.108", "F.116"),
]


def resolve_f1_participating(
    tables: list[dict], markdown: str, schema: SchemaIndex
) -> dict[str, dict]:
    out: dict[str, dict] = {}

    for table in tables:
        hdr_norm = [_normalize_label(h) for h in table.get("headers", [])]
        hdr_str = " ".join(hdr_norm)
        # Detect by signature: header contains "first-time" + "undergraduates"
        # AND at least one F1 row label appears.
        if not ("first time" in hdr_str and "undergraduate" in hdr_str):
            continue
        row_text = " ".join(_normalize_label(r["label"]) for r in table["rows"])
        if not any(k in row_text for k in (
                "percent who are from out of state",
                "percent who live in college",
                "average age",
        )):
            continue

        # Map each value column → role (FY or UG)
        col_to_role: list[tuple[int, str]] = []
        for ci, hdr in enumerate(hdr_norm[1:]):
            if "first" in hdr:
                col_to_role.append((ci, "FY"))
            elif "undergraduate" in hdr:
                col_to_role.append((ci, "UG"))
        if not col_to_role:
            continue

        for row in table["rows"]:
            label_norm = _normalize_label(row["label"])
            # Row-merge guard: Docling occasionally concatenates two
            # F-section rows (e.g. "Percent of women who join sororities
            # Percent who live in college-owned…"). The values then belong
            # to ONE of them — we can't tell which, so skip.
            hits = sum(1 for substr, *_ in _F1_ROWS if substr in label_norm)
            if hits > 1:
                continue
            matched = None
            for substr, fy_qn, ug_qn in _F1_ROWS:
                if substr in label_norm:
                    matched = (fy_qn, ug_qn)
                    break
            if not matched:
                continue
            fy_qn, ug_qn = matched
            for col_idx, role in col_to_role:
                if col_idx >= len(row["values"]):
                    continue
                num = _extract_number(row["values"][col_idx])
                if num is None:
                    continue
                qn = fy_qn if role == "FY" else ug_qn
                if qn and qn not in out:
                    out[qn] = {"value": num, "source": "tier4_cleaner"}

    return out


# Ordered list of resolvers. Each resolver only claims fields not already in
# `values`, so hand-coded maps take priority, and earlier resolvers take
# priority over later ones for overlapping claims.
_RESOLVERS = [
    resolve_a_general,
    resolve_j_disciplines,
    resolve_b2_race,
    resolve_b1_enrollment,
    resolve_b3_degrees,
    resolve_b_two_year_rates,
    resolve_b5_graduation,
    resolve_b22_retention,
    resolve_c1_applications,
    resolve_c2_waitlist,
    resolve_c5_carnegie_units,
    resolve_c7_basis_for_selection,
    resolve_c8_entrance_exams,
    resolve_c9_submission_rates,
    resolve_c9_score_distributions,
    resolve_c11_gpa_profile,
    resolve_c12_gpa_summary,
    resolve_c13_application_fee,
    resolve_i_faculty,
    resolve_g_expenses,
    resolve_h_financial_aid,
    resolve_d_transfer,
    resolve_checkboxes,
    resolve_e_academic_offerings,
    resolve_f_student_life,
    resolve_f1_participating,
]


def clean(
    markdown: str,
    schema: SchemaIndex | None = None,
    supplemental_text: str | None = None,
) -> dict[str, dict]:
    """Map Docling markdown to canonical question-number-keyed values.

    Returns {question_number: {"value": str, "source": "tier4_cleaner"}}
    for every field successfully extracted.

    If `schema` is None, a module-level SchemaIndex is lazy-loaded for the
    resolver stage. Pass a pre-built SchemaIndex to share it across many
    clean() calls (e.g. batch survey runs).
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
                    # Find column by header substring. When multiple headers
                    # match (e.g. "Full-Time Men" and "Part-Time Men" both
                    # contain "men"), prefer the one containing "full" since
                    # B.101-B.131 are the full-time enrollment block.
                    matches = []
                    for ci, hdr in enumerate(headers_norm):
                        if col_hint in hdr:
                            vi = ci - 1
                            if 0 <= vi < len(row["values"]):
                                matches.append((ci, vi, hdr))
                    if matches:
                        # Prefer "full-time" match, fall back to first match
                        best = next(
                            (m for m in matches if "full" in m[2]),
                            matches[0],
                        )
                        val_str = row["values"][best[1]]

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

    # --- Section-family resolvers (PRD 005) ---
    # Each resolver returns its own claims. We only accept a claim if the
    # field isn't already populated by an earlier resolver or hand-coded map.
    # This preserves the regression-safe ordering: hand-coded > resolvers.
    idx = schema if schema is not None else _get_schema()
    for resolver in _RESOLVERS:
        new = resolver(tables, markdown, idx)
        if resolver in (
            resolve_a_general,
            resolve_j_disciplines,
            resolve_b2_race,
            resolve_b1_enrollment,
            resolve_b3_degrees,
            resolve_b_two_year_rates,
            resolve_b5_graduation,
            resolve_c2_waitlist,
            resolve_c8_entrance_exams,
            resolve_c12_gpa_summary,
            resolve_c13_application_fee,
            resolve_i_faculty,
            resolve_g_expenses,
            resolve_h_financial_aid,
            resolve_d_transfer,
            resolve_e_academic_offerings,
            resolve_f_student_life,
        ) and supplemental_text:
            supplemental_new = resolver(tables, supplemental_text, idx)
            if resolver in (resolve_a_general, resolve_b1_enrollment) and supplemental_new:
                new = supplemental_new
                supplemental_new = {}
            for qn, rec in supplemental_new.items():
                if resolver in (
                    resolve_a_general,
                    resolve_j_disciplines,
                    resolve_b2_race,
                    resolve_b1_enrollment,
                    resolve_b3_degrees,
                    resolve_b_two_year_rates,
                    resolve_b5_graduation,
                    resolve_c2_waitlist,
                    resolve_c13_application_fee,
                    resolve_i_faculty,
                    resolve_d_transfer,
                    resolve_e_academic_offerings,
                    resolve_h_financial_aid,
                ):
                    new[qn] = rec
                else:
                    new.setdefault(qn, rec)
        for qn, rec in new.items():
            if resolver is resolve_b5_graduation and re.match(r"^B\.[45]\d{2}$", qn):
                values[qn] = rec
            elif qn not in values:
                values[qn] = rec

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
