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
                qn = _match_j_label(lookup_by_sub[sub], label_norm)
                if qn and qn not in out:
                    out[qn] = {"value": num, "source": "tier4_cleaner"}

    return out


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
    out: dict[str, dict] = {}

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
    out: dict[str, dict] = {}

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


# --- Resolver: C2 Wait List (3 numeric fields) ---
#
# The YesNo fields (C.201, C.205-207) require checkbox detection and are
# deferred to the Phase 6 generic checkbox resolver. Here we capture only
# the three number-valued rows in the "WAITING LIST" table.

_C2_NUMERIC_ROW_RULES: list[tuple[str, str]] = [
    ("number of qualified applicants offered",  "C.202"),
    ("number accepting a place",                "C.203"),
    ("number of wait listed students admitted", "C.204"),
]


def resolve_c2_waitlist(
    tables: list[dict], markdown: str, schema: SchemaIndex
) -> dict[str, dict]:
    out: dict[str, dict] = {}
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
    ("science",                 "Science"),
    ("units that must be lab",  "Of these, units that must be lab"),
    ("foreign language",        "Foreign language"),
    ("social studies",          "Social studies"),
    ("history",                 "History"),
    ("academic electives",      "Academic electives"),
    ("computer science",        "Computer Science"),
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
            elif "recommended" in hdr:
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
        joined_hdr = " ".join(headers_norm)
        # Detect C7: header row mentions all four importance levels.
        has_header_signal = ("very important" in joined_hdr
                             and "considered" in joined_hdr)
        # Or at least one row contains a C7 factor keyword.
        factor_rows = 0
        for row in table["rows"]:
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

        # Sub-header rows like "Nonacademic | Very Important | ..." reset
        # the current table category — track it as we iterate.
        current_cat = "Academic Factors"

        for row in table["rows"]:
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

    # --- I2 ratio (inline) ---
    # Pattern: "ratio ... X to Y" plus "(based on N students and M faculty)".
    m = re.search(r"(?i)student[- ]to[- ]faculty ratio", markdown)
    if m:
        window = markdown[m.start(): m.start() + 600]
        # Ratio itself — often "8:1" or "X to Y". Prefer "N:1" form.
        ratio_m = re.search(r"\b(\d{1,3})\s*:\s*(\d{1,3})\b", window)
        if not ratio_m:
            # "X to 1" or "X  to Y" — two separate numbers with 'to' between
            ratio_m = re.search(r"\b(\d{1,3})\s*to\s*(\d{1,3})\b", window,
                                 re.IGNORECASE)
        if ratio_m and "I.201" not in out:
            out["I.201"] = {"value": f"{ratio_m.group(1)}:{ratio_m.group(2)}",
                            "source": "tier4_cleaner"}
        # Student count and faculty count
        s_m = re.search(r"(\d[\d,]*)\s*students?", window, re.IGNORECASE)
        f_m = re.search(r"(\d[\d,]*)\s*faculty", window, re.IGNORECASE)
        if s_m and "I.202" not in out:
            n = _extract_number(s_m.group(1))
            if n:
                out["I.202"] = {"value": n, "source": "tier4_cleaner"}
        if f_m and "I.203" not in out:
            n = _extract_number(f_m.group(1))
            if n:
                out["I.203"] = {"value": n, "source": "tier4_cleaner"}

    # --- I3 class size ---
    for table in tables:
        # Detect I3 by CLASS SECTIONS / CLASS SUB SECTIONS rows
        rows_norm = [_normalize_label(r["label"]) for r in table["rows"]]
        is_i3 = any("class section" in n or "class sub" in n for n in rows_norm)
        if not is_i3:
            continue

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
# Per-Credit-Hour, Tuition Policies (YesNo), and G0 URL are deferred.

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
    ("food and housing on campus",       "G.112", "G.116"),
    ("housing only on campus",           "G.113", "G.117"),
    ("food only on campus",              "G.114", "G.118"),
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
    ("first time full time first year", 200),  # H.201..H.213
    ("first time first year",           200),  # shorter templates
    ("full time undergrad",             213),  # H.214..H.226
    ("less than full time",             226),  # H.227..H.239
]

# H2A: base offsets for N (offset 1) within each cohort column.
_H2A_COL_BASES = [
    ("first time full time first year", "H.2A",  0),   # H.2A01-H.2A04
    ("first time first year",           "H.2A",  0),
    ("full time undergrad",             "H.2A",  4),   # H.2A05-H.2A08
    ("less than full time",             "H.2A",  8),   # H.2A09-H.2A12
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
    ("federal work study",                                    "H.111", ""),
    ("state and other",                                       "H.112", "H.123"),
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


def resolve_h_financial_aid(
    tables: list[dict], markdown: str, schema: SchemaIndex
) -> dict[str, dict]:
    out: dict[str, dict] = {}

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
        if not is_h2_like:
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
        rows = table["rows"]
        has_h2_rows = any(r["label"].strip() in _H2_LETTER_OFFSETS for r in rows)
        has_h2a_rows = any(r["label"].strip() in _H2A_LETTER_OFFSETS for r in rows)

        for row in rows:
            letter = row["label"].strip()
            values = row["values"]

            if letter in _H2_LETTER_OFFSETS and has_h2_rows:
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


def resolve_d_transfer(
    tables: list[dict], markdown: str, schema: SchemaIndex
) -> dict[str, dict]:
    out: dict[str, dict] = {}

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
            or "d " in (" " + section_norm)
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
    resolve_j_disciplines,
    resolve_b2_race,
    resolve_b1_enrollment,
    resolve_b5_graduation,
    resolve_b22_retention,
    resolve_c1_applications,
    resolve_c2_waitlist,
    resolve_c5_carnegie_units,
    resolve_c7_basis_for_selection,
    resolve_c11_gpa_profile,
    resolve_i_faculty,
    resolve_g_expenses,
    resolve_h_financial_aid,
    resolve_d_transfer,
    resolve_checkboxes,
    resolve_f1_participating,
]


def clean(markdown: str, schema: SchemaIndex | None = None) -> dict[str, dict]:
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
        for qn, rec in new.items():
            if qn not in values:
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
