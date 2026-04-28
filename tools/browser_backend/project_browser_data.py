#!/usr/bin/env python3
"""Project selected CDS extraction results into queryable browser tables.

This is the materialization worker for PRD 010:

  - cds_field_definitions
  - cds_metric_aliases
  - cds_fields
  - school_browser_rows

The canonical source of truth remains cds_artifacts.notes.values. This
script selects one extraction result per document using producer precedence,
merges the Tier 4 fallback cleaned overlay when applicable, parses typed
field values, and upserts the two public projection tables.

Usage:
    python tools/browser_backend/project_browser_data.py --full-rebuild --apply
    python tools/browser_backend/project_browser_data.py --document-id <uuid> --apply

Env:
    SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY in .env at repo root.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from functools import lru_cache
from pathlib import Path
from typing import Any, Optional, Tuple, Union


REPO_ROOT = Path(__file__).resolve().parents[2]
SCHEMA_DIR = REPO_ROOT / "schemas"
SITE_BASE_URL = "https://www.collegedata.fyi"
DEFAULT_SCHEMA_VERSION = "2025-26"
MIN_YEAR_START = 2024

BASE_PRODUCER_RANK = {
    "tier1_xlsx": 1,
    "tier2_acroform": 2,
    "tier6_html": 3,
    "tier4_docling": 4,
}
FALLBACK_PRODUCER = "tier4_llm_fallback"

NOT_APPLICABLE_VALUES = {
    "n/a",
    "na",
    "not applicable",
    "not-applicable",
    "not required",
    "not offered",
}


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _fallback_matches_base(
    base: dict[str, Any],
    base_notes: dict[str, Any],
    fallback: dict[str, Any],
) -> bool:
    fallback_notes = fallback.get("notes") or {}
    if not isinstance(fallback_notes, dict):
        return False

    base_schema_version = artifact_schema_version(base)
    fallback_schema_version = artifact_schema_version(fallback)
    if not base_schema_version or fallback_schema_version != base_schema_version:
        return False

    base_artifact_id = fallback_notes.get("base_artifact_id")
    if base_artifact_id:
        return (
            str(base_artifact_id) == str(base.get("id"))
            and (fallback_notes.get("base_producer_version") in (None, base.get("producer_version")))
        )

    markdown = base_notes.get("markdown")
    markdown_sha256 = fallback_notes.get("markdown_sha256")
    if not isinstance(markdown, str) or not markdown_sha256:
        return False

    return (
        str(markdown_sha256) == _sha256_text(markdown)
        and str(fallback_notes.get("cleaner_version") or "") == str(base.get("producer_version") or "")
    )


@dataclass(frozen=True)
class FieldDefinition:
    schema_version: str
    field_id: str
    field_label: str
    section: Optional[str]
    subsection: Optional[str]
    value_kind_hint: Optional[str]


@dataclass(frozen=True)
class DirectAlias:
    field_id: str


@dataclass(frozen=True)
class DerivedFormula:
    per_year_formulas: dict[str, Tuple[str, ...]]


SourceSpec = Union[DirectAlias, DerivedFormula]


@dataclass(frozen=True)
class MetricDefinition:
    canonical_metric: str
    source_spec: SourceSpec
    value_kind: str
    mvp_certified: bool
    notes: str
    browser_column: Optional[str] = None
    min_value: Optional[Decimal] = None
    max_value: Optional[Decimal] = None
    integer_only: bool = False


@dataclass(frozen=True)
class SelectedExtractionResult:
    document_id: str
    schema_version: str
    base_artifact_id: str
    base_producer: str
    base_producer_version: Optional[str]
    fallback_artifact_id: Optional[str]
    fallback_producer_version: Optional[str]
    values: dict[str, Any]
    value_sources: dict[str, Tuple[str, Optional[str]]]


@dataclass(frozen=True)
class ParsedValue:
    value_text: Optional[str]
    value_num: Optional[Decimal]
    value_bool: Optional[bool]
    value_kind: str
    value_status: str


DIRECT_METRIC_DEFINITIONS = {
    "applied": MetricDefinition(
        "applied",
        DerivedFormula({
            "2024-25": ("C.101", "C.102", "C.103", "C.104"),
            "2025-26": ("C.116",),
        }),
        "number",
        True,
        "PRD 014 derived admissions metric; 2024-25 is gender-split, 2025-26 uses a total field.",
        "applied",
    ),
    "admitted": MetricDefinition(
        "admitted",
        DerivedFormula({
            "2024-25": ("C.105", "C.106", "C.107", "C.108"),
            "2025-26": ("C.117",),
        }),
        "number",
        True,
        "PRD 014 derived admissions metric; 2024-25 is gender-split, 2025-26 uses a total field.",
        "admitted",
    ),
    "first_year_enrolled": MetricDefinition(
        "first_year_enrolled",
        DerivedFormula({
            "2024-25": ("C.109", "C.110", "C.111", "C.112", "C.113", "C.114", "C.115", "C.116"),
            "2025-26": ("C.118",),
        }),
        "number",
        True,
        "PRD 014 derived admissions metric; 2024-25 is gender and unit-load split, 2025-26 uses a total field.",
        "enrolled_first_year",
    ),
    "sat_submit_rate": MetricDefinition(
        "sat_submit_rate", DirectAlias("C.901"), "percent", True,
        "PRD 012 direct field alias; stored fractionally and paired with SAT score interpretation.",
        "sat_submit_rate",
    ),
    "act_submit_rate": MetricDefinition(
        "act_submit_rate", DirectAlias("C.902"), "percent", True,
        "PRD 012 direct field alias; stored fractionally and paired with ACT score interpretation.",
        "act_submit_rate",
    ),
    "sat_composite_p25": MetricDefinition(
        "sat_composite_p25", DirectAlias("C.905"), "number", True,
        "PRD 012 direct SAT Composite 25th percentile field.",
        "sat_composite_p25", Decimal("400"), Decimal("1600"), True,
    ),
    "sat_composite_p50": MetricDefinition(
        "sat_composite_p50", DirectAlias("C.906"), "number", True,
        "PRD 012 direct SAT Composite 50th percentile field.",
        "sat_composite_p50", Decimal("400"), Decimal("1600"), True,
    ),
    "sat_composite_p75": MetricDefinition(
        "sat_composite_p75", DirectAlias("C.907"), "number", True,
        "PRD 012 direct SAT Composite 75th percentile field.",
        "sat_composite_p75", Decimal("400"), Decimal("1600"), True,
    ),
    "sat_ebrw_p25": MetricDefinition(
        "sat_ebrw_p25", DirectAlias("C.908"), "number", True,
        "PRD 012 direct SAT EBRW 25th percentile field.",
        "sat_ebrw_p25", Decimal("200"), Decimal("800"), True,
    ),
    "sat_ebrw_p50": MetricDefinition(
        "sat_ebrw_p50", DirectAlias("C.909"), "number", True,
        "PRD 012 direct SAT EBRW 50th percentile field.",
        "sat_ebrw_p50", Decimal("200"), Decimal("800"), True,
    ),
    "sat_ebrw_p75": MetricDefinition(
        "sat_ebrw_p75", DirectAlias("C.910"), "number", True,
        "PRD 012 direct SAT EBRW 75th percentile field.",
        "sat_ebrw_p75", Decimal("200"), Decimal("800"), True,
    ),
    "sat_math_p25": MetricDefinition(
        "sat_math_p25", DirectAlias("C.911"), "number", True,
        "PRD 012 direct SAT Math 25th percentile field.",
        "sat_math_p25", Decimal("200"), Decimal("800"), True,
    ),
    "sat_math_p50": MetricDefinition(
        "sat_math_p50", DirectAlias("C.912"), "number", True,
        "PRD 012 direct SAT Math 50th percentile field.",
        "sat_math_p50", Decimal("200"), Decimal("800"), True,
    ),
    "sat_math_p75": MetricDefinition(
        "sat_math_p75", DirectAlias("C.913"), "number", True,
        "PRD 012 direct SAT Math 75th percentile field.",
        "sat_math_p75", Decimal("200"), Decimal("800"), True,
    ),
    "act_composite_p25": MetricDefinition(
        "act_composite_p25", DirectAlias("C.914"), "number", True,
        "PRD 012 direct ACT Composite 25th percentile field.",
        "act_composite_p25", Decimal("1"), Decimal("36"), True,
    ),
    "act_composite_p50": MetricDefinition(
        "act_composite_p50", DirectAlias("C.915"), "number", True,
        "PRD 012 direct ACT Composite 50th percentile field.",
        "act_composite_p50", Decimal("1"), Decimal("36"), True,
    ),
    "act_composite_p75": MetricDefinition(
        "act_composite_p75", DirectAlias("C.916"), "number", True,
        "PRD 012 direct ACT Composite 75th percentile field.",
        "act_composite_p75", Decimal("1"), Decimal("36"), True,
    ),
}

DIRECT_METRIC_ALIASES = {
    metric: definition.source_spec.field_id
    for metric, definition in DIRECT_METRIC_DEFINITIONS.items()
    if isinstance(definition.source_spec, DirectAlias)
}

DERIVED_METRIC_DEFINITIONS = {
    metric: definition
    for metric, definition in DIRECT_METRIC_DEFINITIONS.items()
    if isinstance(definition.source_spec, DerivedFormula)
}


def load_env(env_path: Path = REPO_ROOT / ".env") -> dict[str, str]:
    env: dict[str, str] = {}
    if not env_path.exists():
        return env
    for line in env_path.read_text().splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
            value = value[1:-1]
        env[key] = value
    return env


def parse_year_start(canonical_year: Optional[str]) -> Optional[int]:
    if not canonical_year:
        return None
    match = re.match(r"^((?:19|20)\d{2})-\d{2}$", canonical_year)
    if not match:
        return None
    return int(match.group(1))


def archive_url(school_id: str, canonical_year: str) -> str:
    return f"{SITE_BASE_URL}/schools/{school_id}/{canonical_year}"


def load_schema_definitions(schema_dir: Path = SCHEMA_DIR) -> dict[str, dict[str, FieldDefinition]]:
    definitions: dict[str, dict[str, FieldDefinition]] = {}
    for path in sorted(schema_dir.glob("cds_schema_*.json")):
        if "-to-" in path.name or path.name.endswith(".structural.json"):
            continue
        with path.open() as f:
            schema = json.load(f)
        schema_version = schema.get("schema_version")
        if not schema_version:
            continue
        by_field: dict[str, FieldDefinition] = {}
        for field in schema.get("fields", []):
            field_id = field.get("question_number")
            if not field_id:
                continue
            by_field[field_id] = FieldDefinition(
                schema_version=schema_version,
                field_id=field_id,
                field_label=field.get("question") or field_id,
                section=field.get("section"),
                subsection=field.get("subsection"),
                value_kind_hint=field.get("value_type"),
            )
        definitions[schema_version] = by_field
    return definitions


def field_definition_rows(definitions: dict[str, dict[str, FieldDefinition]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for fields in definitions.values():
        for definition in fields.values():
            rows.append({
                "schema_version": definition.schema_version,
                "field_id": definition.field_id,
                "field_label": definition.field_label,
                "section": definition.section,
                "subsection": definition.subsection,
                "value_kind_hint": definition.value_kind_hint,
            })
    return rows


def metric_alias_rows(definitions: dict[str, dict[str, FieldDefinition]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for schema_version, fields in definitions.items():
        for metric in DIRECT_METRIC_DEFINITIONS.values():
            if not isinstance(metric.source_spec, DirectAlias):
                continue
            if metric.source_spec.field_id not in fields:
                continue
            rows.append({
                "canonical_metric": metric.canonical_metric,
                "schema_version": schema_version,
                "field_id": metric.source_spec.field_id,
                "value_kind": metric.value_kind,
                "mvp_certified": metric.mvp_certified,
                "notes": metric.notes,
            })
    return rows


def canonical_field_equivalence_rows(
    definitions: dict[str, dict[str, FieldDefinition]],
) -> list[dict[str, Any]]:
    rows_by_key: dict[tuple[str, str], dict[str, Any]] = {}

    for schema_version, fields in definitions.items():
        for field_id in fields:
            rows_by_key[(schema_version, field_id)] = {
                "schema_version": schema_version,
                "field_id": field_id,
                "canonical_field_id": field_id,
                "equivalence_kind": "direct",
                "derivation_formula": None,
            }

    for (schema_version, field_id), (canonical_field_id, kind) in load_field_equivalences().items():
        rows_by_key[(schema_version, field_id)] = {
            "schema_version": schema_version,
            "field_id": field_id,
            "canonical_field_id": canonical_field_id,
            "equivalence_kind": kind,
            "derivation_formula": None,
        }

    for metric in DERIVED_METRIC_DEFINITIONS.values():
        assert isinstance(metric.source_spec, DerivedFormula)
        for schema_version, field_ids in metric.source_spec.per_year_formulas.items():
            rows_by_key[(schema_version, metric.canonical_metric)] = {
                "schema_version": schema_version,
                "field_id": metric.canonical_metric,
                "canonical_field_id": field_ids[0],
                "equivalence_kind": "derived",
                "derivation_formula": " + ".join(field_ids),
            }

    return list(rows_by_key.values())


def _created_at_key(row: dict[str, Any]) -> str:
    return str(row.get("created_at") or "")


def artifact_schema_version(row: dict[str, Any]) -> Optional[str]:
    notes = row.get("notes") or {}
    if not isinstance(notes, dict):
        notes = {}
    schema_version = row.get("schema_version") or notes.get("schema_version")
    return str(schema_version) if schema_version else None


def artifact_schema_fallback_used(row: dict[str, Any]) -> bool:
    notes = row.get("notes") or {}
    if not isinstance(notes, dict):
        return False
    return bool(notes.get("schema_fallback_used"))


def sort_base_candidates(
    candidates: list[dict[str, Any]],
    expected_schema_version: Optional[str] = None,
) -> list[dict[str, Any]]:
    sorted_candidates = sorted(
        candidates,
        key=lambda row: (_created_at_key(row), str(row.get("id") or "")),
        reverse=True,
    )
    sorted_candidates = sorted(
        sorted_candidates,
        key=lambda row: BASE_PRODUCER_RANK.get(str(row.get("producer")), 99),
    )
    sorted_candidates = sorted(
        sorted_candidates,
        key=lambda row: 1 if artifact_schema_fallback_used(row) else 0,
    )
    if expected_schema_version:
        sorted_candidates = sorted(
            sorted_candidates,
            key=lambda row: 0 if artifact_schema_version(row) == expected_schema_version else 1,
        )
    return sorted_candidates


def select_extraction_result(
    document_id: str,
    artifacts: list[dict[str, Any]],
    fallback_schema_version: str = DEFAULT_SCHEMA_VERSION,
    expected_schema_version: Optional[str] = None,
) -> Optional[SelectedExtractionResult]:
    base_candidates = [
        artifact for artifact in artifacts
        if artifact.get("kind") == "canonical"
        and artifact.get("producer") in BASE_PRODUCER_RANK
    ]
    if not base_candidates:
        return None

    base = sort_base_candidates(base_candidates, expected_schema_version)[0]

    base_notes = base.get("notes") or {}
    if not isinstance(base_notes, dict):
        base_notes = {}
    base_values = _values_dict(base_notes)

    schema_version = artifact_schema_version(base) or fallback_schema_version

    merged_values: dict[str, Any] = dict(base_values)
    value_sources = {
        field_id: (str(base.get("producer")), base.get("producer_version"))
        for field_id in base_values
    }

    fallback_artifact: Optional[dict[str, Any]] = None
    if base.get("producer") == "tier4_docling":
        fallback_candidates = [
            artifact for artifact in artifacts
            if artifact.get("kind") == "cleaned"
            and artifact.get("producer") == FALLBACK_PRODUCER
        ]
        compatible_fallbacks = [
            artifact for artifact in fallback_candidates
            if _fallback_matches_base(base, base_notes, artifact)
        ]
        if compatible_fallbacks:
            fallback_artifact = sorted(
                compatible_fallbacks,
                key=lambda row: (_created_at_key(row), str(row.get("id") or "")),
                reverse=True,
            )[0]
            fallback_notes = fallback_artifact.get("notes") or {}
            if not isinstance(fallback_notes, dict):
                fallback_notes = {}
            for field_id, value in _values_dict(fallback_notes).items():
                if field_id in merged_values:
                    continue
                merged_values[field_id] = value
                value_sources[field_id] = (
                    str(fallback_artifact.get("producer")),
                    fallback_artifact.get("producer_version"),
                )

    return SelectedExtractionResult(
        document_id=document_id,
        schema_version=str(schema_version),
        base_artifact_id=str(base.get("id")),
        base_producer=str(base.get("producer")),
        base_producer_version=base.get("producer_version"),
        fallback_artifact_id=(
            str(fallback_artifact.get("id")) if fallback_artifact else None
        ),
        fallback_producer_version=(
            fallback_artifact.get("producer_version") if fallback_artifact else None
        ),
        values=merged_values,
        value_sources=value_sources,
    )


def _values_dict(notes: dict[str, Any]) -> dict[str, Any]:
    values = notes.get("values") or {}
    return values if isinstance(values, dict) else {}


def display_value(record: Any) -> Optional[str]:
    if isinstance(record, dict):
        raw = record.get("value_decoded")
        if raw is None:
            raw = record.get("value")
    else:
        raw = record
    if raw is None:
        return None
    text = str(raw).strip()
    return text if text else None


def _record_hint(record: Any, definition: Optional[FieldDefinition]) -> str:
    if isinstance(record, dict):
        value_type = record.get("value_type")
        question = record.get("question")
    else:
        value_type = None
        question = None
    parts = [
        str(value_type or ""),
        str(definition.value_kind_hint if definition else ""),
        str(question or ""),
        str(definition.field_label if definition else ""),
    ]
    return " ".join(parts).lower()


def infer_value_kind(record: Any, definition: Optional[FieldDefinition], text: Optional[str]) -> str:
    hint = _record_hint(record, definition)
    lower = (text or "").strip().lower()
    if lower in NOT_APPLICABLE_VALUES:
        return "not_applicable"
    if (
        re.search(r"\b(percent|percentage|rate)\b", hint)
        and "percentile" not in hint
    ) or (text and "%" in text):
        return "percent"
    if "currency" in hint or "dollar" in hint or (text and text.strip().startswith("$")):
        return "currency"
    if "yesno" in hint or "yes/no" in hint or lower in {"yes", "no", "true", "false"}:
        return "yesno"
    if lower in {"☒", "☑", "✓", "x", "/yes", "/x", "checked", "unchecked", "☐"}:
        return "checkbox"
    if "number" in hint or "nearest tenth" in hint:
        return "number"
    if text is None:
        return "unknown"
    return "text"


def parse_field_value(
    record: Any,
    definition: Optional[FieldDefinition] = None,
    metric: Optional[MetricDefinition] = None,
) -> ParsedValue:
    text = display_value(record)
    kind = infer_value_kind(record, definition, text)
    if metric and metric.value_kind == "percent":
        kind = "percent"
    elif metric and metric.value_kind == "number" and kind == "unknown":
        kind = "number"

    if text is None:
        return ParsedValue(None, None, None, kind, "missing")

    lower = text.strip().lower()
    if kind == "not_applicable" or lower in NOT_APPLICABLE_VALUES:
        return ParsedValue(text, None, None, "not_applicable", "not_applicable")

    if kind in {"yesno", "checkbox"}:
        bool_value = parse_bool(text)
        return ParsedValue(
            text,
            None,
            bool_value,
            kind,
            "reported" if bool_value is not None else "parse_error",
        )

    if kind in {"number", "percent", "currency"}:
        parsed = parse_numeric(text)
        if parsed is None:
            return ParsedValue(text, None, None, kind, "parse_error")
        if kind == "percent":
            parsed = normalize_fractional_percent(parsed, text)
            if parsed < 0 or parsed > 1:
                return ParsedValue(text, None, None, kind, "parse_error")
        if metric and not metric_value_is_valid(parsed, metric):
            return ParsedValue(text, None, None, kind, "parse_error")
        return ParsedValue(text, parsed, None, kind, "reported")

    return ParsedValue(text, None, None, kind, "reported")


def metric_value_is_valid(value: Decimal, metric: MetricDefinition) -> bool:
    if metric.integer_only and value != value.to_integral_value():
        return False
    if metric.min_value is not None and value < metric.min_value:
        return False
    if metric.max_value is not None and value > metric.max_value:
        return False
    return True


def parse_bool(text: str) -> Optional[bool]:
    lower = text.strip().lower()
    if lower in {"yes", "true", "y", "☒", "☑", "✓", "x", "/yes", "/x", "checked"}:
        return True
    if lower in {"no", "false", "n", "☐", "/off", "unchecked"}:
        return False
    return None


def parse_numeric(text: str) -> Optional[Decimal]:
    stripped = text.strip()
    if re.search(r"\d\s*[-–—]\s*\d", stripped):
        return None
    if stripped.startswith("~"):
        return None
    cleaned = stripped.replace(",", "").replace("$", "").replace("%", "").strip()
    if not re.fullmatch(r"[+-]?\d+(?:\.\d+)?", cleaned):
        return None
    try:
        return Decimal(cleaned)
    except InvalidOperation:
        return None


def normalize_fractional_percent(value: Decimal, source_text: str) -> Decimal:
    # Percent/rate storage is always fractional 0..1. A source "58%" and a
    # schema-known percent cell containing "58" both become 0.58; already
    # fractional values like "0.58" remain unchanged.
    if "%" in source_text or value > 1:
        return value / Decimal("100")
    return value


def quantize_rate(value: Any) -> Optional[Decimal]:
    if value is None:
        return None
    decimal = Decimal(str(value))
    return decimal.quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP)


def decimal_to_json(value: Optional[Decimal]) -> Optional[str]:
    if value is None:
        return None
    return format(value, "f")


def int_from_decimal(value: Optional[Decimal]) -> Optional[int]:
    if value is None:
        return None
    try:
        return int(value)
    except (ValueError, OverflowError):
        return None


@lru_cache(maxsize=1)
def load_field_equivalences(schema_dir: Path = SCHEMA_DIR) -> dict[tuple[str, str], tuple[Optional[str], str]]:
    equivalences: dict[tuple[str, str], tuple[Optional[str], str]] = {}

    # Identity mappings for canonical schemas in this checkout.
    for schema_version, fields in load_schema_definitions(schema_dir).items():
        for field_id in fields:
            equivalences[(schema_version, field_id)] = (field_id, "direct")

    for path in sorted(schema_dir.glob("cds_schema_*-to-*.diff.json")):
        try:
            diff = json.loads(path.read_text())
        except json.JSONDecodeError:
            continue
        source_version = diff.get("source_schema_version")
        if not source_version:
            continue
        for record in diff.get("fields", []):
            field_id = record.get("field_id")
            kind = record.get("equivalence_kind")
            if not field_id or not kind:
                continue
            equivalences[(str(source_version), str(field_id))] = (
                record.get("canonical_field_id"),
                str(kind),
            )

    return equivalences


def field_equivalence(
    schema_version: str,
    field_id: str,
) -> tuple[Optional[str], str]:
    return load_field_equivalences().get((schema_version, field_id), (field_id, "direct"))


def direct_metrics_by_canonical_field() -> dict[str, MetricDefinition]:
    out = {}
    for metric in DIRECT_METRIC_DEFINITIONS.values():
        if isinstance(metric.source_spec, DirectAlias):
            out[metric.source_spec.field_id] = metric
    return out


def metric_field_ids_for_year(metric: MetricDefinition, schema_version: str) -> Optional[Tuple[str, ...]]:
    if isinstance(metric.source_spec, DirectAlias):
        return (metric.source_spec.field_id,)
    return metric.source_spec.per_year_formulas.get(schema_version)


def parse_metric_component(
    field_id: str,
    selected: SelectedExtractionResult,
    schema_defs: dict[str, FieldDefinition],
    metric: MetricDefinition,
) -> Optional[Decimal]:
    if field_id not in selected.values:
        return None
    definition = schema_defs.get(field_id)
    parsed = parse_field_value(selected.values[field_id], definition, metric)
    if parsed.value_status != "reported" or parsed.value_num is None:
        return None
    return parsed.value_num


def evaluate_metric(
    metric: MetricDefinition,
    selected: SelectedExtractionResult,
    schema_defs: dict[str, FieldDefinition],
) -> Optional[Decimal]:
    field_ids = metric_field_ids_for_year(metric, selected.schema_version)
    if not field_ids:
        return None
    values = [
        parse_metric_component(field_id, selected, schema_defs, metric)
        for field_id in field_ids
    ]
    if any(value is None for value in values):
        return None
    return sum(values, Decimal("0"))


def build_projection_rows(
    document: dict[str, Any],
    artifacts: list[dict[str, Any]],
    definitions: dict[str, dict[str, FieldDefinition]],
    scorecard: Optional[dict[str, Any]] = None,
) -> Tuple[list[dict[str, Any]], Optional[dict[str, Any]]]:
    canonical_year = document.get("canonical_year")
    year_start = parse_year_start(canonical_year)
    if year_start is None or year_start < MIN_YEAR_START:
        return [], None

    selected = select_extraction_result(
        str(document["document_id"]),
        artifacts,
        DEFAULT_SCHEMA_VERSION,
        expected_schema_version=str(canonical_year) if canonical_year else None,
    )
    if selected is None:
        return [], None

    schema_defs = definitions.get(selected.schema_version) or definitions.get(DEFAULT_SCHEMA_VERSION) or {}
    direct_metrics = direct_metrics_by_canonical_field()
    derived_formula_single_fields = {}
    for metric in DERIVED_METRIC_DEFINITIONS.values():
        field_ids = metric_field_ids_for_year(metric, selected.schema_version)
        if field_ids and len(field_ids) == 1:
            derived_formula_single_fields[field_ids[0]] = metric

    field_rows: list[dict[str, Any]] = []
    metric_values: dict[str, Decimal] = {}

    for field_id, record in sorted(selected.values.items()):
        definition = schema_defs.get(field_id)
        canonical_field_id, equivalence_kind = field_equivalence(selected.schema_version, field_id)
        metric = (
            direct_metrics.get(canonical_field_id or "")
            or derived_formula_single_fields.get(field_id)
        )
        parsed = parse_field_value(record, definition, metric)
        source_producer, source_version = selected.value_sources.get(
            field_id,
            (selected.base_producer, selected.base_producer_version),
        )
        canonical_metric = metric.canonical_metric if metric else None
        row = {
            "document_id": document["document_id"],
            "school_id": document["school_id"],
            "school_name": document["school_name"],
            "sub_institutional": document.get("sub_institutional"),
            "ipeds_id": document.get("ipeds_id"),
            "canonical_year": canonical_year,
            "year_start": year_start,
            "schema_version": selected.schema_version,
            "field_id": field_id,
            "canonical_field_id": canonical_field_id,
            "equivalence_kind": equivalence_kind,
            "canonical_metric": canonical_metric,
            "value_text": parsed.value_text,
            "value_num": decimal_to_json(parsed.value_num),
            "value_bool": parsed.value_bool,
            "value_kind": parsed.value_kind,
            "value_status": parsed.value_status,
            "source_format": document.get("source_format"),
            "producer": source_producer,
            "producer_version": source_version,
            "data_quality_flag": document.get("data_quality_flag"),
            "archive_url": archive_url(str(document["school_id"]), str(canonical_year)),
        }
        field_rows.append(row)
        if canonical_metric and parsed.value_status == "reported" and parsed.value_num is not None:
            metric_values[canonical_metric] = parsed.value_num

    for metric in DERIVED_METRIC_DEFINITIONS.values():
        value = evaluate_metric(metric, selected, schema_defs)
        if value is not None:
            metric_values[metric.canonical_metric] = value

    browser_row = build_browser_row(document, selected, metric_values, scorecard)
    return field_rows, browser_row


def build_browser_row(
    document: dict[str, Any],
    selected: SelectedExtractionResult,
    metric_values: dict[str, Decimal],
    scorecard: Optional[dict[str, Any]] = None,
) -> Optional[dict[str, Any]]:
    if document.get("data_quality_flag") == "wrong_file":
        return None

    canonical_year = str(document["canonical_year"])
    applied = int_from_decimal(metric_values.get("applied"))
    admitted = int_from_decimal(metric_values.get("admitted"))
    enrolled = int_from_decimal(metric_values.get("first_year_enrolled"))

    acceptance_rate = None
    if applied and admitted is not None and applied > 0:
        acceptance_rate = quantize_rate(Decimal(admitted) / Decimal(applied))

    yield_rate = None
    if admitted and enrolled is not None and admitted > 0:
        yield_rate = quantize_rate(Decimal(enrolled) / Decimal(admitted))

    scorecard = scorecard or {}
    has_scorecard_values = any(
        scorecard.get(key) is not None
        for key in ("enrollment", "retention_rate_ft", "avg_net_price", "pell_grant_rate")
    )

    return {
        "document_id": document["document_id"],
        "school_id": document["school_id"],
        "school_name": document["school_name"],
        "sub_institutional": document.get("sub_institutional"),
        "ipeds_id": document.get("ipeds_id"),
        "canonical_year": canonical_year,
        "year_start": parse_year_start(canonical_year),
        "schema_version": selected.schema_version,
        "source_format": document.get("source_format"),
        "producer": selected.base_producer,
        "producer_version": selected.base_producer_version,
        "data_quality_flag": document.get("data_quality_flag"),
        "archive_url": archive_url(str(document["school_id"]), canonical_year),
        "applied": applied,
        "admitted": admitted,
        "enrolled_first_year": enrolled,
        "acceptance_rate": decimal_to_json(acceptance_rate),
        "yield_rate": decimal_to_json(yield_rate),
        "undergrad_enrollment_scorecard": scorecard.get("enrollment"),
        "scorecard_data_year": scorecard.get("scorecard_data_year") if has_scorecard_values else None,
        "retention_rate": decimal_to_json(quantize_rate(scorecard.get("retention_rate_ft"))),
        "avg_net_price": scorecard.get("avg_net_price"),
        "pell_rate": decimal_to_json(quantize_rate(scorecard.get("pell_grant_rate"))),
        "sat_submit_rate": decimal_to_json(metric_values.get("sat_submit_rate")),
        "act_submit_rate": decimal_to_json(metric_values.get("act_submit_rate")),
        "sat_composite_p25": int_from_decimal(metric_values.get("sat_composite_p25")),
        "sat_composite_p50": int_from_decimal(metric_values.get("sat_composite_p50")),
        "sat_composite_p75": int_from_decimal(metric_values.get("sat_composite_p75")),
        "sat_ebrw_p25": int_from_decimal(metric_values.get("sat_ebrw_p25")),
        "sat_ebrw_p50": int_from_decimal(metric_values.get("sat_ebrw_p50")),
        "sat_ebrw_p75": int_from_decimal(metric_values.get("sat_ebrw_p75")),
        "sat_math_p25": int_from_decimal(metric_values.get("sat_math_p25")),
        "sat_math_p50": int_from_decimal(metric_values.get("sat_math_p50")),
        "sat_math_p75": int_from_decimal(metric_values.get("sat_math_p75")),
        "act_composite_p25": int_from_decimal(metric_values.get("act_composite_p25")),
        "act_composite_p50": int_from_decimal(metric_values.get("act_composite_p50")),
        "act_composite_p75": int_from_decimal(metric_values.get("act_composite_p75")),
    }


def seed_metadata(client: Any, definitions: dict[str, dict[str, FieldDefinition]], apply: bool) -> None:
    def_rows = field_definition_rows(definitions)
    alias_rows = metric_alias_rows(definitions)
    equivalence_rows = canonical_field_equivalence_rows(definitions)
    print(
        f"metadata: {len(def_rows)} field definitions, "
        f"{len(alias_rows)} metric aliases, "
        f"{len(equivalence_rows)} field equivalences"
    )
    if not apply:
        return
    _upsert_chunks(client, "cds_field_definitions", def_rows, "schema_version,field_id")
    _upsert_chunks(client, "cds_metric_aliases", alias_rows, "canonical_metric,schema_version,field_id")
    _upsert_chunks(
        client,
        "cds_canonical_field_equivalence",
        equivalence_rows,
        "schema_version,field_id",
    )


def project_document(
    client: Any,
    document: dict[str, Any],
    definitions: dict[str, dict[str, FieldDefinition]],
    apply: bool,
) -> tuple[int, bool]:
    document_id = document["document_id"]
    artifacts = fetch_artifacts(client, str(document_id))
    scorecard = fetch_scorecard(client, document.get("ipeds_id"))
    field_rows, browser_row = build_projection_rows(document, artifacts, definitions, scorecard)

    print(
        f"{document.get('school_id')} {document.get('canonical_year')} "
        f"{document_id}: {len(field_rows)} fields, browser_row={'yes' if browser_row else 'no'}"
    )

    if not apply:
        return len(field_rows), bool(browser_row)

    replace_projection_rows(client, str(document_id), field_rows, browser_row)
    return len(field_rows), bool(browser_row)


def replace_projection_rows(
    client: Any,
    document_id: str,
    field_rows: list[dict[str, Any]],
    browser_row: Optional[dict[str, Any]],
) -> None:
    """Atomically replace the public projection rows for one document."""
    client.rpc(
        "replace_browser_projection_for_document",
        {
            "p_document_id": document_id,
            "p_field_rows": field_rows,
            "p_browser_row": browser_row,
        },
    ).execute()


def project_document_id(
    client: Any,
    document_id: str,
    definitions: dict[str, dict[str, FieldDefinition]],
    apply: bool = True,
) -> tuple[int, bool]:
    """Refresh projection rows for one cds_documents row.

    This is the incremental API used by the extraction worker. It reuses the
    same selected-result and row-building logic as the full rebuild command so
    document-level refreshes cannot drift from batch projection semantics.
    """
    docs = fetch_documents(client, document_id)
    if not docs:
        print(f"{document_id}: no cds_manifest row found for projection")
        return 0, False
    return project_document(client, docs[0], definitions, apply)


def clear_projection_tables(client: Any) -> None:
    client.table("cds_fields").delete().gte("year_start", MIN_YEAR_START).execute()
    client.table("school_browser_rows").delete().gte("year_start", MIN_YEAR_START).execute()


def fetch_artifacts(client: Any, document_id: str) -> list[dict[str, Any]]:
    result = (
        client.table("cds_artifacts")
        .select("*")
        .eq("document_id", document_id)
        .in_("kind", ["canonical", "cleaned"])
        .execute()
    )
    return result.data or []


def fetch_scorecard(client: Any, ipeds_id: Optional[str]) -> Optional[dict[str, Any]]:
    if not ipeds_id:
        return None
    result = (
        client.table("scorecard_summary")
        .select("ipeds_id,scorecard_data_year,enrollment,retention_rate_ft,avg_net_price,pell_grant_rate")
        .eq("ipeds_id", ipeds_id)
        .limit(1)
        .execute()
    )
    rows = result.data or []
    return rows[0] if rows else None


def fetch_documents(client: Any, document_id: Optional[str] = None) -> list[dict[str, Any]]:
    select_cols = (
        "document_id,school_id,school_name,sub_institutional,ipeds_id,"
        "canonical_year,source_format,extraction_status,data_quality_flag"
    )
    if document_id:
        result = (
            client.table("cds_manifest")
            .select(select_cols)
            .eq("document_id", document_id)
            .limit(1)
            .execute()
        )
        return result.data or []

    page_size = 1000
    offset = 0
    rows: list[dict[str, Any]] = []
    while True:
        result = (
            client.table("cds_manifest")
            .select(select_cols)
            .eq("extraction_status", "extracted")
            .gte("canonical_year", "2024-25")
            .range(offset, offset + page_size - 1)
            .execute()
        )
        batch = result.data or []
        rows.extend(batch)
        if len(batch) < page_size:
            break
        offset += page_size
    return rows


def _upsert_chunks(client: Any, table: str, rows: list[dict[str, Any]], on_conflict: str, size: int = 500) -> None:
    for start in range(0, len(rows), size):
        chunk = rows[start:start + size]
        if chunk:
            client.table(table).upsert(chunk, on_conflict=on_conflict).execute()


def make_client() -> Any:
    try:
        from supabase import create_client
    except ImportError as exc:
        raise SystemExit("Missing dependency: pip install supabase") from exc

    env = {**load_env(), **dict(__import__("os").environ)}
    url = env.get("SUPABASE_URL")
    key = env.get("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key:
        raise SystemExit("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY are required")
    return create_client(url, key)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.strip().split("\n\n")[0])
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--full-rebuild", action="store_true")
    group.add_argument("--document-id")
    parser.add_argument("--apply", action="store_true", help="Write to Supabase; default is dry-run")
    parser.add_argument(
        "--skip-metadata",
        action="store_true",
        help="Do not upsert field definitions and metric aliases first",
    )
    args = parser.parse_args()

    definitions = load_schema_definitions()
    if not definitions:
        raise SystemExit(f"No schema definitions found under {SCHEMA_DIR}")

    client = make_client()
    if not args.skip_metadata:
        seed_metadata(client, definitions, args.apply)

    if args.full_rebuild and args.apply:
        print(f"clearing existing {MIN_YEAR_START}+ projection rows")
        clear_projection_tables(client)

    docs = fetch_documents(client, args.document_id)
    total_fields = 0
    total_browser_rows = 0
    for document in docs:
        count, has_browser_row = project_document(client, document, definitions, args.apply)
        total_fields += count
        total_browser_rows += int(has_browser_row)

    mode = "applied" if args.apply else "dry-run"
    print(f"{mode}: projected {total_fields} fields and {total_browser_rows} browser rows from {len(docs)} documents")
    return 0


if __name__ == "__main__":
    sys.exit(main())
