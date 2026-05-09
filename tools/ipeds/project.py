"""Project raw IPEDS table rows into public long-form facts."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any

from .mappings import FactMapping
from .metadata import IpedsColumn, IpedsValueLabel

NEGATIVE_STATUS_WORDS = {
    "not_applicable": ("not applicable", "not in universe", "not offered"),
    "suppressed": ("suppressed", "privacy", "confidential"),
    "missing": ("not reported", "not available", "missing", "unknown"),
}


def normalize_unitid(value: Any) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(float(str(value).strip()))
    except (TypeError, ValueError):
        return None


def coerce_decimal(value: Any) -> Decimal | None:
    if value in (None, ""):
        return None
    text = str(value).strip().replace(",", "")
    if text.lower() in {"null", "privacysuppressed"}:
        return None
    try:
        return Decimal(text)
    except (InvalidOperation, ValueError):
        return None


def label_lookup(labels: list[IpedsValueLabel]) -> dict[tuple[str, str, str], str]:
    return {
        (label.table_name.upper(), label.var_name.upper(), label.code_value.strip()): label.value_label or ""
        for label in labels
    }


def column_lookup(columns: list[IpedsColumn]) -> dict[tuple[str, str], IpedsColumn]:
    return {(column.table_name.upper(), column.var_name.upper()): column for column in columns}


def project_rows_to_facts(
    rows_by_table: dict[str, list[dict[str, Any]]],
    mappings: list[FactMapping] | tuple[FactMapping, ...],
    columns: list[IpedsColumn],
    labels: list[IpedsValueLabel],
    *,
    release_id: str | None,
    collection_year: str,
    data_year: int,
    release_type: str,
    school_id_by_unitid: dict[int, str] | None = None,
) -> list[dict[str, Any]]:
    facts: list[dict[str, Any]] = []
    by_label = label_lookup(labels)
    by_column = column_lookup(columns)
    school_ids = school_id_by_unitid or {}

    for mapping in mappings:
        table_name = mapping.table_name.upper()
        var_name = mapping.var_name.upper()
        column = by_column.get((table_name, var_name))
        imputation_var = (column.imputation_var if column else None) or f"X{var_name}"
        for row in rows_by_table.get(table_name, []):
            unitid = normalize_unitid(row.get("UNITID") or row.get("unitid"))
            if unitid is None:
                continue
            fact = project_fact(
                row,
                mapping,
                column,
                by_label,
                imputation_var=imputation_var,
                unitid=unitid,
                release_id=release_id,
                collection_year=collection_year,
                data_year=data_year,
                release_type=release_type,
                school_id=school_ids.get(unitid),
            )
            if fact is not None:
                facts.append(fact)
    return facts


def project_fact(
    row: dict[str, Any],
    mapping: FactMapping,
    column: IpedsColumn | None,
    labels: dict[tuple[str, str, str], str],
    *,
    imputation_var: str | None,
    unitid: int,
    release_id: str | None,
    collection_year: str,
    data_year: int,
    release_type: str,
    school_id: str | None,
) -> dict[str, Any] | None:
    table_name = mapping.table_name.upper()
    var_name = mapping.var_name.upper()
    raw_value = _row_value(row, var_name)
    if raw_value in (None, ""):
        return None

    text_value = str(raw_value).strip()
    value_numeric: Decimal | None = None
    value_text: str | None = None
    value_label = labels.get((table_name, var_name, text_value))
    quality_flag = quality_from_label(value_label) if value_label else "reported"

    numeric = coerce_decimal(text_value)
    if numeric is not None and numeric < 0 and value_label:
        return _status_fact(
            mapping,
            column,
            unitid,
            release_id,
            collection_year,
            data_year,
            release_type,
            school_id,
            text_value,
            value_label,
            quality_flag,
            imputation_var,
            row,
        )

    if mapping.value_kind == "number":
        if numeric is None:
            return None
        value_numeric = numeric
    elif mapping.value_kind == "label":
        value_label = value_label or text_value
        value_text = text_value
    else:
        value_text = text_value

    imputation_flag = _row_value(row, imputation_var) if imputation_var else None
    imputation_label = (
        labels.get((table_name, imputation_var.upper(), str(imputation_flag).strip()))
        if imputation_flag not in (None, "") and imputation_var
        else None
    )
    imputation_quality = quality_from_label(imputation_label) if imputation_label else None
    if imputation_quality == "imputed":
        quality_flag = "imputed"

    return {
        "release_id": release_id,
        "unitid": unitid,
        "school_id": school_id,
        "collection_year": collection_year,
        "data_year": data_year,
        "field_key": mapping.field_key,
        "field_label": mapping.field_label,
        "value_numeric": str(value_numeric) if value_numeric is not None else None,
        "value_text": value_text,
        "value_label": value_label,
        "unit": mapping.unit,
        "cohort": mapping.cohort,
        "population": mapping.population,
        "source_table": table_name,
        "source_variable": var_name,
        "source_title": column.var_title if column else None,
        "release_type": release_type,
        "imputation_flag": str(imputation_flag).strip() if imputation_flag not in (None, "") else None,
        "imputation_label": imputation_label,
        "quality_flag": quality_flag,
        "definition_alignment": mapping.definition_alignment,
        "definition_note": mapping.definition_note,
        "display_group": mapping.display_group,
        "public_visible": mapping.public_visible,
    }


def quality_from_label(label: str | None) -> str:
    if not label:
        return "reported"
    normalized = label.lower()
    if "imput" in normalized:
        return "imputed"
    for status, words in NEGATIVE_STATUS_WORDS.items():
        if any(word in normalized for word in words):
            return status
    return "reported"


def _row_value(row: dict[str, Any], key: str | None) -> Any:
    if not key:
        return None
    return row.get(key) if key in row else row.get(key.upper()) if key.upper() in row else row.get(key.lower())


def _status_fact(
    mapping: FactMapping,
    column: IpedsColumn | None,
    unitid: int,
    release_id: str | None,
    collection_year: str,
    data_year: int,
    release_type: str,
    school_id: str | None,
    raw_value: str,
    value_label: str,
    quality_flag: str,
    imputation_var: str | None,
    row: dict[str, Any],
) -> dict[str, Any]:
    return {
        "release_id": release_id,
        "unitid": unitid,
        "school_id": school_id,
        "collection_year": collection_year,
        "data_year": data_year,
        "field_key": mapping.field_key,
        "field_label": mapping.field_label,
        "value_numeric": None,
        "value_text": raw_value,
        "value_label": value_label,
        "unit": mapping.unit,
        "cohort": mapping.cohort,
        "population": mapping.population,
        "source_table": mapping.table_name.upper(),
        "source_variable": mapping.var_name.upper(),
        "source_title": column.var_title if column else None,
        "release_type": release_type,
        "imputation_flag": str(_row_value(row, imputation_var)).strip() if imputation_var and _row_value(row, imputation_var) not in (None, "") else None,
        "imputation_label": None,
        "quality_flag": quality_flag,
        "definition_alignment": mapping.definition_alignment,
        "definition_note": mapping.definition_note,
        "display_group": mapping.display_group,
        "public_visible": mapping.public_visible,
    }
