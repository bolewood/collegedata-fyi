"""
Tier 4 LLM fallback: prompt builder, validator, and merge policy.

Implements the repair layer described in PRD 006 §What-to-build. Consumes
the ``tier4_docling`` canonical artifact's markdown and current values, and
produces a structured output in the same shape as the existing cleaner.

This module is transport-agnostic. It builds prompts and validates responses
but does not call the model; the benchmark CLI and the future worker wire
this up to ``llm_client.call_structured``.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# Reuse the existing schema index + numeric helpers from the cleaner to
# keep normalization identical across cleaner and fallback output.
_HERE = Path(__file__).resolve().parent
import sys
sys.path.insert(0, str(_HERE))
from tier4_cleaner import (  # noqa: E402
    SchemaIndex,
    _extract_number,
    _extract_currency,
    _normalize_label,
)


STRATEGY_NAME = "markdown_section_fill_gaps"
STRATEGY_VERSION = "0.1.0"
PROMPT_VERSION = "0.1.0"

PRODUCER_NAME = "tier4_llm_fallback"
PRODUCER_VERSION = "0.1.0"


# ---------------------------------------------------------------------------
# Subsection → pdf_tag_prefix disambiguation table.
#
# Covers the 14 of 20 irreducibly ambiguous fields that pdf_tag prefixes
# can resolve. The remaining six (D.13-D.16 position-in-row, C.16/C.17
# surrounding-anchor) get narrative prompt guidance instead — see
# SPECIAL_SUBSECTION_HINTS below.
# ---------------------------------------------------------------------------
PDF_TAG_HINTS: dict[str, dict[str, str]] = {
    "C11": {
        "FRSH_GPA_SUBMIT_": "Use when the GPA row is under the 'Score submitters' sub-table",
        "FRSH_GPA_NO_SUB_": "Use when the GPA row is under the 'Non-score submitters' sub-table",
        "EN_FRSH_GPA_":     "Use when the GPA row is under the 'All entering first-year' sub-table",
    },
    "H2A": {
        "UG_FT_": "Full-time undergraduate column",
        "UG_PT_": "Part-time (less-than-full-time) undergraduate column",
    },
}


# Narrative hints for subsections where pdf_tag prefixes do not apply.
SPECIAL_SUBSECTION_HINTS: dict[str, list[str]] = {
    "D13": [
        "D.13 and D.14 each have TWO columns per row: 'Maximum credits' (Number) "
        "and 'Unit type' (Text, e.g. 'semester hours'). Return BOTH columns per "
        "row; do not merge or pick one.",
    ],
    "D14": [
        "Same as D.13: return Number and Unit type as separate fields.",
    ],
    "D15": [
        "Single value: minimum credits for an associate degree (Number).",
    ],
    "D16": [
        "Single value: minimum credits for a bachelor's degree (Number).",
    ],
    "C16": [
        "C.16 has two Date fields (Month, Day) for the notification-date context. "
        "Return each date tied to its nearest preceding deadline-label anchor "
        "(e.g. 'Other (please specify):'). Do not merge multiple deadlines into "
        "one date pair.",
    ],
    "C17": [
        "C.17 has two Date fields (Month, Day) for the reply-date context. Same "
        "rule as C.16: disambiguate by the nearest preceding deadline label.",
    ],
}


# Canonical known hints — the deterministic heuristics from PRD 005 that
# matter across many sections. Included in every uncached tail.
KNOWN_HINTS: list[str] = [
    "Templates may use 'men/women' for gender, but the schema uses 'males/females' — treat as synonyms.",
    "Pre-2020 CDS templates use 'freshman/freshmen' where the current schema uses 'first-year'. Treat as synonyms.",
    "'Nonresident aliens' (older templates) and 'nonresidents' (current) are the same dimension.",
    "If a row label matches TWO OR MORE known field names at once, it is ambiguous — flag it, do not guess.",
    "Do not synthesize totals, ratios, or percentages. If the school did not fill a 'Total' cell, return null for that field.",
    "The school may have left fields blank. Return null rather than inferring a value from neighbouring rows.",
    "Every extracted value MUST include an `evidence_text` that is a verbatim substring of the input section markdown.",
]


# The seven Docling failure modes from learnings §2, presented to the
# model so it recognizes them in the input.
DOCLING_FAILURE_MODES: str = """\
The section markdown was produced by Docling from a flattened PDF. Expect
any of these failure modes in the input:

1. Table → paragraphs: the pipe-delimited table is gone; you see an
   ordered stream of cell labels interleaved with cell values, with no
   header row.
2. Row merge: two label rows collapse into one table row; the value
   array may belong to only one of them.
3. Header promoted to data: a header cell whose text contains digits
   (e.g. "CIP 2020 Categories") is parsed as a data row; the actual
   header cell is blank.
4. Header concatenation: "CLASS SUB- SECTIONS" in the PDF becomes
   "CLASS SUB- SECTIONS" in one cell when wrapped across newlines.
5. Values rendered as prose: a fill-value may appear many lines after
   the subsection header, past definitions and footnotes.
6. Checkbox dialects — the SAME document may mix any of these:
   - `- [x] Label`    (canonical markdown checked)
   - `- [ ] X Label`  (unchecked brackets, literal X prefix)
   - `| ☒ Label |`    (unicode glyph inside a table cell)
   - `- X Label`      (bullet + literal X)
7. Wrong-file/blank-template: the PDF may not be this school's CDS at
   all, or may be an empty template. If the markdown has no concrete
   filled values anywhere in the section, return an empty values dict
   and a `document_mismatch: true` flag in your response.
"""


# ---------------------------------------------------------------------------
# Prompt construction
# ---------------------------------------------------------------------------


SYSTEM_PROMPT = """\
You are a strict CDS (Common Data Set) extraction assistant. Your single
job is to extract field values from a subsection of Docling-produced
markdown and return them in the exact JSON shape requested. You never
invent values, never compute sums, never infer across rows, and always
cite verbatim evidence text.
"""


def _schema_fields_for_subsection(
    schema: SchemaIndex, subsection_code: str
) -> list[dict[str, Any]]:
    """Return the schema fields that belong to the given subsection code.

    ``subsection_code`` is the CDS subsection abbreviation (e.g. "H5", "C13").
    The schema stores subsection as a free-text label ("H5", "H5.01", or a
    human-readable string) so we match by prefix on the code.
    """
    matches: list[dict[str, Any]] = []
    for f in schema.fields:
        sub = str(f.get("subsection") or "")
        # Accept exact match or prefix-with-dot-or-space match. The schema
        # uses "H5" as subsection; we also want to catch any records that
        # store "H5.01" or "H5 — ...".
        if sub == subsection_code:
            matches.append(f)
            continue
        if sub.startswith(subsection_code + "."):
            matches.append(f)
            continue
        # Fall back to question_number prefix (e.g. H.5xx → H5).
        qn = str(f.get("question_number") or "")
        if _qn_matches_subsection(qn, subsection_code):
            matches.append(f)
    return matches


def _qn_matches_subsection(qn: str, subsection: str) -> bool:
    """Question numbers like ``H.501`` map to subsection ``H5``."""
    m = re.match(r"^([A-Z])\.?(\d+)", qn)
    if not m:
        return False
    letter, digits = m.group(1), m.group(2)
    sub_m = re.match(r"^([A-Z])(\d+)$", subsection)
    if not sub_m:
        return False
    sub_letter, sub_num = sub_m.group(1), int(sub_m.group(2))
    if letter != sub_letter:
        return False
    # H.501 → 501/100 = 5 → H5; H.2201 → 22; H.2A201 is ambiguous (see below).
    try:
        qn_int = int(digits)
    except ValueError:
        return False
    # Subsection number is the first one or two digits, matching against the
    # shorter prefix. E.g. 501 → "5" matches H5; 2201 → "22" matches H22.
    for width in (len(str(sub_num)),):
        if qn_int // (10 ** (len(digits) - width)) == sub_num:
            return True
    return False


def _field_prompt_payload(f: dict[str, Any], subsection_code: str) -> dict[str, Any]:
    """Compact field payload for the prompt. Keep small to save tokens."""
    payload: dict[str, Any] = {
        "qn": f["question_number"],
        "q": f.get("question", ""),
        "type": f.get("value_type", "Text"),
    }
    dims: dict[str, str] = {}
    for key in ("gender", "cohort", "unit_load", "student_group", "residency", "category"):
        v = f.get(key)
        if v and v != "All":
            dims[key] = v
    if dims:
        payload["dims"] = dims
    # Surface pdf_tag only when the subsection has a known disambiguation map.
    if subsection_code in PDF_TAG_HINTS:
        tag = f.get("pdf_tag")
        if tag:
            payload["pdf_tag"] = tag
    return payload


def build_cached_head(
    *, subsection_code: str, schema: SchemaIndex, schema_version: str
) -> list[str]:
    """Build the prompt prefix.

    Returns two-position list: ``[stable_glossary, subsection_specific]``.
    The caller attaches cache_control ONLY to the stable_glossary block so
    the same cache entry is reused across every subsection and every
    document. The subsection-specific block varies per call but is small
    enough that paying uncached rates on it is fine; the heavy
    extraction-rulebook material is the glossary, which is cached.
    """
    fields = _schema_fields_for_subsection(schema, subsection_code)
    if not fields:
        raise ValueError(
            f"No schema fields found for subsection {subsection_code!r} "
            f"in schema {schema_version!r}"
        )

    # Stable across all subsections and docs — one cache entry serves all calls.
    stable_glossary = "\n\n".join([
        _extraction_instructions_generic(),
        DOCLING_FAILURE_MODES,
        _output_json_schema_text(),
        KNOWN_HINTS_BLOCK,
        COMMON_MISTAKES_BLOCK,
    ])

    # Subsection-specific, varies per call. NOT cached.
    per_subsection_parts = [
        f"# Target subsection: {subsection_code}\n",
        _pdf_tag_block(subsection_code),
        _special_hints_block(subsection_code),
        _fields_list_text(subsection_code, fields),
    ]
    subsection_specific = "\n".join(p for p in per_subsection_parts if p)

    return [stable_glossary, subsection_specific]


def _extraction_instructions_generic() -> str:
    """Subsection-agnostic instructions. Safe to cache across all subsections."""
    return (
        "# Task\n\n"
        "You will receive:\n"
        "- A target subsection code (e.g. H5, C13, D14)\n"
        "- The schema field list for that subsection (question numbers, "
        "question text, value types, dimensional metadata)\n"
        "- A slice of markdown produced by Docling from a flattened CDS PDF\n"
        "- A list of question numbers the deterministic cleaner has already "
        "extracted — DO NOT re-extract those\n\n"
        "Extract values for each listed field that is actually filled in\n"
        "the markdown. Omit any field whose value cannot be verified with\n"
        "verbatim evidence from the markdown slice.\n\n"
        "NEVER:\n"
        "- Invent, guess, infer, or synthesize a value.\n"
        "- Compute totals, ratios, or percentages. If the school left a\n"
        "  'Total' row blank, return null (omit the field).\n"
        "- Use values from neighbouring rows to fill a blank row.\n"
        "- Cite paraphrased or reconstructed evidence — only verbatim substrings.\n"
        "- Extract a field already in already_extracted_question_numbers.\n"
    )


# Pre-built at import time so it's identical across every call.
KNOWN_HINTS_BLOCK: str = (
    "# Known normalization rules\n\n"
    + "\n".join(f"- {h}" for h in KNOWN_HINTS)
    + "\n"
)


# Concrete examples of correct vs incorrect extraction behavior. Identical
# across every call, so it lives in the cached glossary.
COMMON_MISTAKES_BLOCK: str = """\
# Common mistakes to avoid

## 1. Paraphrased evidence

BAD:
  {
    "H.501": {
      "value": "50",
      "evidence_text": "About half of students borrow federal loans"
    }
  }

GOOD:
  {
    "H.501": {
      "value": "50",
      "evidence_text": "| A. Any loan program ... | 50 | 48 | ..."
    }
  }

The `evidence_text` must appear verbatim in the section markdown. If the
exact string isn't present, omit the field.

## 2. Guessing blanks from context

BAD: "Harvard C.501 is probably Required since Harvard is selective."
GOOD: Omit C.501 entirely if the markdown shows no checkmark.

A school leaving a field blank is a data point, not a failure of
extraction. Omit, don't infer.

## 3. Synthesized totals

If the CDS shows rows A, B, C with values 10, 20, 30 and a "Total" row
that's blank, DO NOT return Total=60. The school failed to fill it; that's
the school's data. Return the individual rows only.

## 4. Checkbox dialects

All four of these mean "checked":
  - `- [x] Yes`
  - `| ☒ Yes |`
  - `- X Yes`         (literal X, space, label)
  - `[X] Yes`

All four of these mean "unchecked":
  - `- [ ] Yes`
  - `- [ ] X Yes`     (unchecked brackets — the literal X is NOT a tick)
  - `| ☐ Yes |`
  - `[  ] Yes`

When a checkbox field is checked, return `value: "x"` and cite the
checkbox line verbatim as evidence. When unchecked, omit the field.

## 5. Row-merge detection

Docling sometimes merges two rows into one:

  `| Percent below 1.0 Totals should = 100% | 0.00% | 100.00% |`

The label contains TWO distinct schema questions ("Percent below 1.0"
and "Totals should = 100%"). The value array is ambiguous. DO NOT guess
which label the values belong to. Omit both fields and let the
deterministic layer handle it.

## 6. Currency and percentage formatting

The `value` field is a digit-only string. Strip `$`, `%`, commas, and
spaces. Preserve decimals.

  "$59,320" → "59320"
  "61%"     → "61"
  "4.21"    → "4.21"
  "1,753"   → "1753"

If the cell says "Not Applicable", "varies", "n/a", or similar
non-numeric text in a Number or $ field, omit the field.

## 7. Dates

MM and DD are each their own field. Return them as digit-only strings:

  "August 1" → MM: "8", DD: "1"
  "12/15"    → MM: "12", DD: "15"

If the deadline is "rolling" or "no closing date", omit the MM/DD
fields. Do not try to encode the rolling nature as a number.

## 8. Wrapped labels across rows

Docling sometimes breaks a long cell label across multiple table rows:

  `| Number of students borrowing |   |   |   |`
  `| from federal loans           | 50 | 48 | 47 |`

The value array belongs to the concatenated label. Treat this as one
logical row: "Number of students borrowing from federal loans" with
values 50/48/47. The evidence_text should include both markdown rows
verbatim.

## 9. Header row promoted to data

When the first table row contains text that parses like data (e.g.
"CIP 2020 Categories"), Docling loses the header. The first data row
becomes the de facto header. For J1 you will typically see this
pattern on every school. When identifying columns, read the FIRST
data row as if it were a header.

## 10. Footnotes and explanatory text within a section

CDS subsections frequently contain multi-paragraph definitions and
footnotes. For example, H5 often has several hundred characters of
text defining "aid recipients" before the actual data table. Ignore
the prose; extract only from the filled data cells. The prose is for
human readers, not for extraction.

## 11. Section boundaries drift

The section you were given is the subsection you must target, but
Docling sometimes splices neighbouring sections together. If you see
content that clearly belongs to a different subsection (e.g., H6 text
at the bottom of an H5 slice), ignore it. Only extract fields whose
context in the markdown is unambiguously the target subsection.

## 12. Dollar values in G5

G5 (estimated expenses) uses `$` followed by thousands-formatted
integers: `$59,320`. Return them as digit-only strings: `"59320"`.
The CDS template groups expenses into rows: Tuition and fees, Books
and supplies, Room and board (or separately Housing + Food), Transport,
Other expenses. Columns split by Residents / Commuters / Living with
family. Match rows × columns carefully — G5 is where row/column
confusion is most common.

## 13. When the section is legitimately empty

If a subsection shows only its label and no filled data (e.g. D15 on
schools that don't report transfer-to-associate credit minimums), do
NOT set `document_mismatch: true` — that signal is reserved for wrong
school or blank-entire-template cases. Just return an empty `values`
object. An empty section is a valid extraction outcome.
"""


def build_uncached_tail(
    *,
    school_id: str,
    cds_year: str,
    subsection_code: str,
    section_markdown: str,
    already_extracted: dict[str, Any],
    extra_hints: list[str] | None = None,
) -> str:
    """Doc-specific portion of the prompt. Never cached."""
    hints = list(KNOWN_HINTS)
    if extra_hints:
        hints.extend(extra_hints)

    payload = {
        "school_id": school_id,
        "cds_year": cds_year,
        "subsection_code": subsection_code,
        "already_extracted_question_numbers": sorted(already_extracted.keys()),
        "known_hints": hints,
    }

    return (
        "# Document context\n\n"
        f"```json\n{json.dumps(payload, indent=2)}\n```\n\n"
        "# Section markdown (verbatim; your evidence_text MUST appear here)\n\n"
        "```\n"
        f"{section_markdown}\n"
        "```\n"
    )


def _extraction_instructions(subsection_code: str) -> str:
    return (
        f"# Task\n\n"
        f"Extract values for CDS subsection **{subsection_code}** from the "
        f"document markdown you will receive in a following message.\n\n"
        f"- Extract ONLY the fields listed under `schema_fields` below.\n"
        f"- Skip any field whose value is not clearly filled in the markdown.\n"
        f"- Do NOT duplicate fields already listed in `already_extracted_question_numbers`.\n"
        f"- Every returned value MUST include `evidence_text` that is a verbatim\n"
        f"  substring of the section markdown.\n"
        f"- Do NOT synthesize totals, ratios, or percentages — if the cell is\n"
        f"  blank, return null (i.e. omit the field from your output).\n"
    )


def _output_json_schema_text() -> str:
    return (
        "# Required output\n\n"
        "Your entire response MUST be a single valid JSON object and NOTHING else.\n"
        "Do NOT wrap the JSON in markdown code fences. Do NOT add any prose,\n"
        "explanation, rationale, or commentary before or after the JSON. The\n"
        "first character of your response must be `{` and the last must be `}`.\n\n"
        "Shape:\n\n"
        "{\n"
        '  "document_mismatch": false,\n'
        '  "values": {\n'
        '    "<question_number>": {\n'
        '      "value": "<string>",\n'
        '      "evidence_text": "<verbatim substring of the section markdown>",\n'
        '      "confidence": <float in [0, 1]>\n'
        "    }\n"
        "  }\n"
        "}\n\n"
        "Rules for each returned field:\n\n"
        "- `value` is a string. Numbers, percents, and dollar amounts are\n"
        "  returned as digit-only strings: `45`, `3.2`, `85.5`, `59320`.\n"
        "  Do not include `%`, `$`, commas, or any other formatting.\n"
        "- `evidence_text` MUST be a verbatim substring of the section\n"
        "  markdown you were given. Not paraphrased, not summarized,\n"
        "  not reconstructed. If you cannot find a verbatim substring\n"
        "  that proves the value, omit the field entirely.\n"
        "- `confidence` is your subjective score in [0.0, 1.0].\n"
        "- Omit any field whose cell is blank, N/A, or unfilled. An omitted\n"
        "  field is ALWAYS safer than a guessed one.\n\n"
        "Worked example of the only allowed response format:\n\n"
        "{\n"
        '  "document_mismatch": false,\n'
        '  "values": {\n'
        '    "H.501": {\n'
        '      "value": "50",\n'
        '      "evidence_text": "| A. Any loan program | 50 | ... |",\n'
        '      "confidence": 0.95\n'
        "    },\n"
        '    "H.502": {\n'
        '      "value": "48",\n'
        '      "evidence_text": "| B. Federal loan programs | 48 | ... |",\n'
        '      "confidence": 0.9\n'
        "    }\n"
        "  }\n"
        "}\n\n"
        "Set `document_mismatch: true` only if the markdown plainly is not\n"
        "this school's CDS section (wrong school, blank template, garbage\n"
        "OCR). If some fields are blank but the section structure is\n"
        "clearly this school's real CDS, set `document_mismatch: false`\n"
        "and return the fields that ARE filled.\n"
    )


def _fields_list_text(subsection_code: str, fields: list[dict[str, Any]]) -> str:
    payloads = [_field_prompt_payload(f, subsection_code) for f in fields]
    body = json.dumps(payloads, indent=2)
    return (
        f"# schema_fields for {subsection_code} "
        f"({len(fields)} fields)\n\n"
        f"```json\n{body}\n```\n"
    )


def _pdf_tag_block(subsection_code: str) -> str:
    mapping = PDF_TAG_HINTS.get(subsection_code)
    if not mapping:
        return ""
    lines = [
        "# pdf_tag disambiguation",
        "",
        "Several fields in this subsection share the same question text but live",
        "in different sub-tables. Use the `pdf_tag` prefix on each field to pick",
        "the correct one:",
        "",
    ]
    for prefix, desc in mapping.items():
        lines.append(f"- `{prefix}`: {desc}")
    return "\n".join(lines) + "\n"


def _special_hints_block(subsection_code: str) -> str:
    hints = SPECIAL_SUBSECTION_HINTS.get(subsection_code)
    if not hints:
        return ""
    return (
        f"# Subsection-specific hints for {subsection_code}\n\n"
        + "\n".join(f"- {h}" for h in hints)
        + "\n"
    )


# ---------------------------------------------------------------------------
# Validator layer
# ---------------------------------------------------------------------------


@dataclass
class ValidationIssue:
    question_number: str
    reason: str


@dataclass
class ValidationResult:
    accepted: dict[str, dict[str, Any]] = field(default_factory=dict)
    rejected: list[ValidationIssue] = field(default_factory=list)
    document_mismatch: bool = False

    def as_notes(self) -> dict[str, Any]:
        return {
            "values": self.accepted,
            "rejected": [{"qn": r.question_number, "reason": r.reason} for r in self.rejected],
            "document_mismatch": self.document_mismatch,
        }


def validate_response(
    *,
    response: dict[str, Any],
    schema: SchemaIndex,
    subsection_code: str,
    section_markdown: str,
    full_markdown: str,
    already_extracted: dict[str, Any],
) -> ValidationResult:
    """Apply deterministic validation to a model response.

    Implements the six-check layer from PRD 006 Step 6:
    1. Type check via value_type and _extract_number / _extract_currency.
    2. Evidence check: evidence_text must be a substring of the full
       markdown (not just the slice — Docling sometimes renders the anchor
       in a different section and prose value in another).
    3. Section-local sanity checks (MM 1-12, DD 1-31, % 0-100, etc.).
    4. Cross-field consistency (basic: counts non-negative).
    5. Row-merge guard (≥2 distinct field names in the evidence span).
    6. No-clobber: drop any qn already in already_extracted.
    """
    result = ValidationResult(document_mismatch=bool(response.get("document_mismatch")))
    values_in = response.get("values") or {}

    if result.document_mismatch:
        return result

    # Build a lookup keyed by question_number for the fields belonging to
    # this subsection. Any qn the model returned that isn't in this set is
    # dropped; hallucinating field IDs is an invalid move.
    fields_by_qn = {
        f["question_number"]: f
        for f in _schema_fields_for_subsection(schema, subsection_code)
    }

    for qn, v in values_in.items():
        if not isinstance(v, dict):
            result.rejected.append(ValidationIssue(qn, "value_entry_not_object"))
            continue

        if qn in already_extracted:
            # fill_gaps mode: deterministic value wins.
            result.rejected.append(ValidationIssue(qn, "already_extracted_by_cleaner"))
            continue

        f = fields_by_qn.get(qn)
        if not f:
            result.rejected.append(ValidationIssue(qn, "qn_outside_subsection_scope"))
            continue

        raw_value = v.get("value")
        evidence = str(v.get("evidence_text") or "")

        # 1. Type check.
        typed_value = _type_check(raw_value, f.get("value_type", "Text"))
        if typed_value is None:
            result.rejected.append(ValidationIssue(qn, "type_check_failed"))
            continue

        # 2. Evidence substring check (against FULL markdown, since Docling
        #    sometimes splits the label/value across the slice boundary).
        if not evidence or not _evidence_present(evidence, full_markdown):
            result.rejected.append(ValidationIssue(qn, "evidence_not_in_markdown"))
            continue

        # 2b. For numeric types, the value itself must appear in the
        # evidence text. Catches cases where the model cited a label-only
        # evidence string but fabricated or guessed the number.
        if not _value_in_evidence(typed_value, evidence, f.get("value_type", "Text")):
            result.rejected.append(ValidationIssue(qn, "value_not_in_evidence"))
            continue

        # 3. Section-local sanity.
        sane, reason = _sanity_check(typed_value, f)
        if not sane:
            result.rejected.append(ValidationIssue(qn, f"sanity_failed:{reason}"))
            continue

        # 5. Row-merge guard.
        if _evidence_spans_multiple_labels(evidence, schema):
            result.rejected.append(ValidationIssue(qn, "row_merge_suspected"))
            continue

        accepted: dict[str, Any] = {
            "value": typed_value,
            "source": PRODUCER_NAME,
            "evidence_text": evidence,
            "verification": "exact_substring",
            "confidence": float(v.get("confidence") or 0.0),
        }
        result.accepted[qn] = accepted

    return result


def _type_check(value: Any, value_type: str) -> str | None:
    """Return the canonical string form of ``value`` if it matches ``value_type``.

    Returns None on type mismatch (field should be rejected).
    """
    if value is None or value == "":
        return None
    s = str(value).strip()
    vt = (value_type or "Text").strip()

    if vt == "Number":
        return _extract_number(s)
    if vt == "Nearest $1":
        return _extract_currency(s)
    if vt == "MM":
        n = _extract_number(s)
        if n is None:
            return None
        i = int(float(n))
        if not 1 <= i <= 12:
            return None
        return str(i)
    if vt == "DD":
        n = _extract_number(s)
        if n is None:
            return None
        i = int(float(n))
        if not 1 <= i <= 31:
            return None
        return str(i)
    if vt == "YesNo":
        low = s.lower()
        if low in ("yes", "y", "true", "1"):
            return "Yes"
        if low in ("no", "n", "false", "0"):
            return "No"
        return None
    if vt == "x":
        # Checkbox — only the literal "x" (or equivalent) counts.
        if s.lower() in ("x", "checked", "yes", "true", "1", "☒"):
            return "x"
        return None
    # Text, dates, and unknown types: accept any non-empty string.
    return s


def _value_in_evidence(value: str, evidence: str, value_type: str) -> bool:
    """Ensure the extracted value actually appears in its evidence text.

    Applies to numeric and checkbox types. For Text/unknown types we skip —
    text values may be paraphrased in ways the substring check can't capture.
    """
    if not value:
        return False
    vt = (value_type or "Text").strip()
    # Text fields are not numeric-grounded — skip.
    if vt in ("Text", ""):
        return True
    # Checkbox: evidence must contain the bracket/glyph markers.
    if vt == "x":
        lowered = evidence.lower()
        return any(tok in lowered for tok in ("[x]", "☒", "[X]"))
    # YesNo: value (Yes/No) must appear in evidence.
    if vt == "YesNo":
        return value.lower() in evidence.lower()
    # Numeric-ish: value digits must appear in evidence (ignoring commas/etc).
    ev_norm = re.sub(r"[,\s]", "", evidence)
    val_norm = str(value).strip()
    # Allow "8" to match "8.00" in evidence or vice versa.
    if val_norm in ev_norm:
        return True
    try:
        num = float(val_norm)
        # Match on various string forms the number might take in the source.
        candidates = [
            str(int(num)) if num == int(num) else str(num),
            f"{num:.0f}",
            f"{num:.1f}",
            f"{num:.2f}",
        ]
        return any(c in ev_norm for c in candidates)
    except ValueError:
        return False


def _evidence_present(evidence: str, markdown: str) -> bool:
    """Return True if evidence appears in markdown, exact or bounded fuzzy.

    Exact first; fall back to whitespace-collapsed match for evidence text
    that includes artifacts Docling introduced (extra newlines, odd
    whitespace).
    """
    if not evidence.strip():
        return False
    if evidence in markdown:
        return True
    collapsed_ev = re.sub(r"\s+", " ", evidence).strip()
    collapsed_md = re.sub(r"\s+", " ", markdown)
    return collapsed_ev in collapsed_md


def _sanity_check(typed_value: str, field: dict[str, Any]) -> tuple[bool, str]:
    """Section-local sanity checks.

    Percentages in 0-100; counts non-negative; MM/DD already range-checked
    in _type_check so those pass through.
    """
    q = (field.get("question") or "").lower()
    vt = field.get("value_type", "")

    try:
        n = float(typed_value)
    except (ValueError, TypeError):
        # Non-numeric value — nothing to check at this layer.
        return True, ""

    # Percentage hint in question text.
    if "percent" in q or "%" in q:
        if not 0.0 <= n <= 100.0:
            return False, "percent_out_of_range"

    # Number fields: non-negative.
    if vt == "Number" and n < 0:
        return False, "negative_count"

    # Currency non-negative.
    if vt == "Nearest $1" and n < 0:
        return False, "negative_currency"

    return True, ""


def _evidence_spans_multiple_labels(evidence: str, schema: SchemaIndex) -> bool:
    """Row-merge guard.

    If the evidence text normalization matches two or more distinct
    schema question normalizations, the evidence is probably a Docling
    row-merge and we should reject.
    """
    norm_ev = _normalize_label(evidence)
    if not norm_ev:
        return False

    # Count matches against the normalized question texts. Short matches
    # (< 15 chars) are too noisy to flag — ignore them.
    matches = 0
    seen: set[str] = set()
    for f in schema.fields:
        qn = f.get("_q_norm") or ""
        if len(qn) < 15:
            continue
        if qn and qn in norm_ev and qn not in seen:
            matches += 1
            seen.add(qn)
            if matches >= 2:
                return True
    return False


# ---------------------------------------------------------------------------
# Cache-key helpers
# ---------------------------------------------------------------------------


def cache_key(
    *,
    source_sha256: str,
    markdown_sha256: str,
    section_name: str,
    schema_version: str,
    model_name: str,
    prompt_version: str = PROMPT_VERSION,
    strategy_version: str = STRATEGY_VERSION,
    cleaner_version: str = "",
    missing_fields: list[str],
) -> dict[str, str]:
    """Build the cache key columns for cds_llm_cache.

    Caller writes these columns directly. Returning a dict (not a tuple)
    keeps the column order decision where the migration lives.
    """
    mf_hash = hashlib.sha256(
        "\n".join(sorted(missing_fields)).encode("utf-8")
    ).hexdigest()
    return {
        "source_sha256": source_sha256,
        "markdown_sha256": markdown_sha256,
        "section_name": section_name,
        "schema_version": schema_version,
        "model_name": model_name,
        "prompt_version": prompt_version,
        "strategy_version": strategy_version,
        "cleaner_version": cleaner_version,
        "missing_fields_sha256": mf_hash,
    }


def hash_markdown(markdown: str) -> str:
    return hashlib.sha256(markdown.encode("utf-8")).hexdigest()
