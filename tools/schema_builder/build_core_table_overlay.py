"""
Build conservative canonical overlays for historical structural CDS schemas.

The 2019-20 through 2023-24 templates do not carry canonical question numbers
on their per-section tabs. This tool maps the high-value C1/C7/C9 rows back to
the current canonical schema where the semantics are clear enough to support a
cross-year table view.

The output is intentionally an overlay instead of a rewrite of the source
structural schema: unmatched rows stay visible for QA, and lossy mappings can
be reviewed independently.
"""

from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DEFAULT_YEARS = ("2019_20", "2020_21", "2021_22", "2022_23", "2023_24")
TARGET_SCHEMA_PATH = Path("schemas/cds_schema_2025_26.json")

C1_TARGETS = {
    ("Applied", "Males", "All", "All"): "C.101",
    ("Applied", "Females", "All", "All"): "C.102",
    ("Applied", "Unknown", "All", "All"): "C.103",
    ("Admitted", "Males", "All", "All"): "C.104",
    ("Admitted", "Females", "All", "All"): "C.105",
    ("Admitted", "Unknown", "All", "All"): "C.106",
    ("Enrolled", "Males", "All", "All"): "C.107",
    ("Enrolled", "Females", "All", "All"): "C.108",
    ("Enrolled", "Unknown", "All", "All"): "C.109",
    ("Enrolled", "Males", "FT", "All"): "C.110",
    ("Enrolled", "Males", "PT", "All"): "C.111",
    ("Enrolled", "Females", "FT", "All"): "C.112",
    ("Enrolled", "Females", "PT", "All"): "C.113",
    ("Enrolled", "Unknown", "FT", "All"): "C.114",
    ("Enrolled", "Unknown", "PT", "All"): "C.115",
    ("Applied", "All", "All", "All"): "C.116",
    ("Admitted", "All", "All", "All"): "C.117",
    ("Enrolled", "All", "All", "All"): "C.118",
    ("Applied", "All", "All", "In-State"): "C.119",
    ("Admitted", "All", "All", "In-State"): "C.120",
    ("Enrolled", "All", "All", "In-State"): "C.121",
    ("Applied", "All", "All", "Out-of-State"): "C.122",
    ("Admitted", "All", "All", "Out-of-State"): "C.123",
    ("Enrolled", "All", "All", "Out-of-State"): "C.124",
    ("Applied", "All", "All", "Nonresidents"): "C.125",
    ("Admitted", "All", "All", "Nonresidents"): "C.126",
    ("Enrolled", "All", "All", "Nonresidents"): "C.127",
    ("Applied", "All", "All", "Unknown"): "C.128",
    ("Admitted", "All", "All", "Unknown"): "C.129",
    ("Enrolled", "All", "All", "Unknown"): "C.130",
}

C7_TARGETS = {
    "rigor of secondary school record": "C.701",
    "class rank": "C.702",
    "academic gpa": "C.703",
    "standardized test scores": "C.704",
    "application essay": "C.705",
    "recommendation(s)": "C.706",
    "interview": "C.707",
    "extracurricular activities": "C.708",
    "talent/ability": "C.709",
    "character/personal qualities": "C.710",
    "first generation": "C.711",
    "alumni/ae relation": "C.712",
    "geographical residence": "C.713",
    "state residency": "C.714",
    "religious affiliation/commitment": "C.715",
    "volunteer work": "C.716",
    "work experience": "C.717",
    "level of applicant’s interest": "C.718",
}

C7_CHOICE_HEADERS = {
    "very important",
    "important",
    "considered",
    "not considered",
}

C9_SUBMISSION_TARGETS = {
    ("sat", "percent"): "C.901",
    ("act", "percent"): "C.902",
    ("sat", "number"): "C.903",
    ("act", "number"): "C.904",
}

C9_PERCENTILE_TARGETS = {
    "sat composite": {"25": "C.905", "50": "C.906", "75": "C.907"},
    "sat evidence": {"25": "C.908", "50": "C.909", "75": "C.910"},
    "sat math": {"25": "C.911", "50": "C.912", "75": "C.913"},
    "act composite": {"25": "C.914", "50": "C.915", "75": "C.916"},
    "act math": {"25": "C.917", "50": "C.918", "75": "C.919"},
    "act english": {"25": "C.920", "50": "C.921", "75": "C.922"},
    "act writing": {"25": "C.923", "50": "C.924", "75": "C.925"},
    "act science": {"25": "C.926", "50": "C.927", "75": "C.928"},
    "act reading": {"25": "C.929", "50": "C.930", "75": "C.931"},
}


def _norm(value: str | None) -> str:
    if not value:
        return ""
    return re.sub(r"\s+", " ", str(value).strip().lower())


def _target_index(target_schema: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {field["question_number"]: field for field in target_schema["fields"]}


def _category(label: str) -> str | None:
    if "applied" in label:
        return "Applied"
    if "admitted" in label or "admits" in label:
        return "Admitted"
    if "enrolled" in label or "enrollees" in label:
        return "Enrolled"
    return None


def _gender(label: str) -> str | None:
    if "another gender" in label:
        return "Another Gender"
    if "unknown" in label:
        return "Unknown"
    if re.search(r"\b(men|male|males)\b", label):
        return "Males"
    if re.search(r"\b(women|female|females)\b", label):
        return "Females"
    if "students who" in label or label.startswith("total first-time"):
        return "All"
    return None


def _unit_load(label: str) -> str:
    if "full-time" in label:
        return "FT"
    if "part-time" in label:
        return "PT"
    return "All"


def _residency(header: str | None) -> str:
    value = _norm(header)
    if value == "in-state":
        return "In-State"
    if value == "out-of-state":
        return "Out-of-State"
    if value == "international":
        return "Nonresidents"
    if value == "unknown":
        return "Unknown"
    return "All"


def _c1_mapping(question: dict[str, Any], column: dict[str, Any]) -> tuple[str | None, str]:
    label = _norm(question.get("row_label"))
    if not label:
        return None, "missing_label"
    if "first-time" not in label and "freshman" not in label and "freshmen" not in label:
        return None, "not_c1_value_row"

    category = _category(label)
    gender = _gender(label)
    if not category or not gender:
        return None, "not_c1_value_row"
    if gender == "Another Gender":
        return None, "no_2025_target_for_another_gender"

    residency = _residency(column.get("header"))
    if residency != "All":
        # Historical residency breakdowns are usually gender-specific columns.
        # The 2025 canonical schema only has all-student residency totals.
        if gender != "All":
            return None, "gender_specific_residency_not_in_2025_schema"
        unit_load = "All"
    else:
        unit_load = _unit_load(label)

    qnum = C1_TARGETS.get((category, gender, unit_load, residency))
    if qnum:
        return qnum, "rule:c1_category_gender_unit_load_residency"
    return None, "no_c1_target"


def _c7_mapping(question: dict[str, Any], column: dict[str, Any]) -> tuple[str | None, str]:
    label = _norm(question.get("row_label"))
    header = _norm(column.get("header"))
    if header not in C7_CHOICE_HEADERS:
        return None, "not_c7_importance_choice"
    if label in {"academic", "nonacademic"}:
        return None, "not_c7_factor_row"

    qnum = C7_TARGETS.get(label)
    if qnum:
        return qnum, "rule:c7_factor_importance_choice"
    if label == "racial/ethnic status":
        return None, "no_2025_target_for_c7_factor"
    return None, "not_c7_factor_row"


def _percentile_key(header: str | None) -> str | None:
    value = _norm(header)
    if "25" in value:
        return "25"
    if "50" in value:
        return "50"
    if "75" in value:
        return "75"
    return None


def _test_name(label: str) -> str | None:
    if "sat composite" in label:
        return "sat composite"
    if "sat evidence" in label or "evidence-based" in label:
        return "sat evidence"
    if "sat math" in label:
        return "sat math"
    if "act composite" in label:
        return "act composite"
    if "act math" in label:
        return "act math"
    if "act english" in label:
        return "act english"
    if "act writing" in label:
        return "act writing"
    if "act science" in label:
        return "act science"
    if "act reading" in label:
        return "act reading"
    return None


def _c9_mapping(question: dict[str, Any], column: dict[str, Any]) -> tuple[str | None, str]:
    label = _norm(question.get("row_label"))
    header = _norm(column.get("header"))

    if "submitting sat" in label or label == "percent submitting sat scores":
        if not header:
            return "C.901", "rule:c9_submission_percent_legacy"
        qnum = C9_SUBMISSION_TARGETS.get(("sat", header))
        return (qnum, "rule:c9_submission") if qnum else (None, "no_c9_submission_target")

    if "submitting act" in label or label == "percent submitting act scores":
        if not header:
            return "C.902", "rule:c9_submission_percent_legacy"
        qnum = C9_SUBMISSION_TARGETS.get(("act", header))
        return (qnum, "rule:c9_submission") if qnum else (None, "no_c9_submission_target")

    test_name = _test_name(label)
    pct = _percentile_key(header)
    if test_name and pct:
        qnum = C9_PERCENTILE_TARGETS[test_name].get(pct)
        return (qnum, "rule:c9_percentile") if qnum else (None, "no_c9_percentile_target")

    return None, "not_c9_core_value_row"


def build_overlay(source_schema: dict[str, Any], target_schema: dict[str, Any]) -> dict[str, Any]:
    target_fields = _target_index(target_schema)
    mappings: list[dict[str, Any]] = []
    unmapped: list[dict[str, Any]] = []

    for section in source_schema["sections"]:
        if section["section"] != "C":
            continue
        for subsection in section["subsections"]:
            if subsection["id"] not in {"C1", "C7", "C9"}:
                continue
            for question in subsection["questions"]:
                for column in question["columns"]:
                    if subsection["id"] == "C1":
                        target_qnum, method = _c1_mapping(question, column)
                    elif subsection["id"] == "C7":
                        target_qnum, method = _c7_mapping(question, column)
                    else:
                        target_qnum, method = _c9_mapping(question, column)

                    record = {
                        "subsection": subsection["id"],
                        "source_row": question["row"],
                        "row_label": question["row_label"],
                        "column_header": column.get("header"),
                        "cell_ref": column["cell_ref"],
                    }
                    if target_qnum:
                        target = target_fields[target_qnum]
                        mappings.append({
                            **record,
                            "canonical_question_number": target_qnum,
                            "canonical_question": target["question"],
                            "confidence": "high",
                            "method": method,
                            **(
                                {"source_choice_value": column.get("header")}
                                if subsection["id"] == "C7"
                                else {}
                            ),
                        })
                    elif method not in {
                        "not_c1_value_row",
                        "not_c7_factor_row",
                        "not_c7_importance_choice",
                        "not_c9_core_value_row",
                    }:
                        unmapped.append({**record, "reason": method})

    return {
        "schema_version": source_schema["schema_version"],
        "overlay_version": "core_table_v1",
        "target_canonical_schema_version": target_schema["schema_version"],
        "source_structural_schema": (
            f"cds_schema_{source_schema['schema_version'].replace('-', '_')}.structural.json"
        ),
        "scope": ["C1", "C7", "C9"],
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "mapping_count": len(mappings),
        "unmapped_count": len(unmapped),
        "mappings": mappings,
        "unmapped": unmapped,
    }


def _schema_path_for_year(year: str) -> Path:
    return Path(f"schemas/cds_schema_{year}.structural.json")


def _overlay_path_for_year(year: str) -> Path:
    return Path(f"schemas/cds_schema_{year}.core_table_overlay.json")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.strip().split("\n\n")[0])
    parser.add_argument(
        "--years",
        default=",".join(DEFAULT_YEARS),
        help="Comma-separated schema years, e.g. 2019_20,2020_21",
    )
    parser.add_argument(
        "--target-schema",
        type=Path,
        default=TARGET_SCHEMA_PATH,
        help="Canonical schema to map against",
    )
    args = parser.parse_args()

    target_schema = json.loads(args.target_schema.read_text())
    for year in [y.strip() for y in args.years.split(",") if y.strip()]:
        source_path = _schema_path_for_year(year)
        overlay_path = _overlay_path_for_year(year)
        source_schema = json.loads(source_path.read_text())
        overlay = build_overlay(source_schema, target_schema)
        overlay_path.write_text(json.dumps(overlay, indent=2) + "\n")
        print(
            f"wrote {overlay_path} "
            f"({overlay['mapping_count']} mappings, {overlay['unmapped_count']} unmapped)"
        )


if __name__ == "__main__":
    main()
