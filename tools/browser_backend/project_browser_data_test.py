import unittest
import hashlib
from decimal import Decimal

from tools.browser_backend.project_browser_data import (
    DIRECT_METRIC_ALIASES,
    DIRECT_METRIC_DEFINITIONS,
    FieldDefinition,
    build_projection_rows,
    metric_field_ids_for_year,
    metric_alias_rows,
    parse_field_value,
    project_document_id,
    replace_projection_rows,
    select_extraction_result,
)


def defs():
    return {
        "2024-25": {
            "C.101": FieldDefinition("2024-25", "C.101", "Men applied", "Admission", "Applications", "Number"),
            "C.102": FieldDefinition("2024-25", "C.102", "Women applied", "Admission", "Applications", "Number"),
            "C.103": FieldDefinition("2024-25", "C.103", "Another gender applied", "Admission", "Applications", "Number"),
            "C.104": FieldDefinition("2024-25", "C.104", "Unknown gender applied", "Admission", "Applications", "Number"),
            "C.105": FieldDefinition("2024-25", "C.105", "Men admitted", "Admission", "Applications", "Number"),
            "C.106": FieldDefinition("2024-25", "C.106", "Women admitted", "Admission", "Applications", "Number"),
            "C.107": FieldDefinition("2024-25", "C.107", "Another gender admitted", "Admission", "Applications", "Number"),
            "C.108": FieldDefinition("2024-25", "C.108", "Unknown gender admitted", "Admission", "Applications", "Number"),
            "C.109": FieldDefinition("2024-25", "C.109", "Men full-time enrolled", "Admission", "Applications", "Number"),
            "C.110": FieldDefinition("2024-25", "C.110", "Men part-time enrolled", "Admission", "Applications", "Number"),
            "C.111": FieldDefinition("2024-25", "C.111", "Women full-time enrolled", "Admission", "Applications", "Number"),
            "C.112": FieldDefinition("2024-25", "C.112", "Women part-time enrolled", "Admission", "Applications", "Number"),
            "C.113": FieldDefinition("2024-25", "C.113", "Another gender full-time enrolled", "Admission", "Applications", "Number"),
            "C.114": FieldDefinition("2024-25", "C.114", "Another gender part-time enrolled", "Admission", "Applications", "Number"),
            "C.115": FieldDefinition("2024-25", "C.115", "Unknown gender full-time enrolled", "Admission", "Applications", "Number"),
            "C.116": FieldDefinition("2024-25", "C.116", "Unknown gender part-time enrolled", "Admission", "Applications", "Number"),
            "C.117": FieldDefinition("2024-25", "C.117", "Total applied", "Admission", "Applications", "Number"),
            "C.118": FieldDefinition("2024-25", "C.118", "Total admitted", "Admission", "Applications", "Number"),
            "C.119": FieldDefinition("2024-25", "C.119", "Total enrolled", "Admission", "Applications", "Number"),
            "C.201": FieldDefinition("2024-25", "C.201", "Wait list policy", "Admission", "Wait List", "YN"),
            "C.202": FieldDefinition("2024-25", "C.202", "Wait list offered", "Admission", "Wait List", "Number"),
            "C.203": FieldDefinition("2024-25", "C.203", "Wait list accepted", "Admission", "Wait List", "Number"),
            "C.204": FieldDefinition("2024-25", "C.204", "Wait list admitted", "Admission", "Wait List", "Number"),
            "C.2101": FieldDefinition("2024-25", "C.2101", "ED offered", "Admission", "Early Decision", "YN"),
            "C.2104": FieldDefinition("2024-25", "C.2104", "Other ED closing date", "Admission", "Early Decision", "MM-DD"),
            "C.2106": FieldDefinition("2024-25", "C.2106", "ED applicants", "Admission", "Early Decision", "Number"),
            "C.2107": FieldDefinition("2024-25", "C.2107", "ED admitted", "Admission", "Early Decision", "Number"),
            "C.2201": FieldDefinition("2024-25", "C.2201", "EA offered", "Admission", "Early Action", "YN"),
            "C.2206": FieldDefinition("2024-25", "C.2206", "EA restrictive", "Admission", "Early Action", "YN"),
            "C.711": FieldDefinition("2024-25", "C.711", "First generation", "Admission", "Factors", "Text"),
            "C.712": FieldDefinition("2024-25", "C.712", "Legacy", "Admission", "Factors", "Text"),
            "C.713": FieldDefinition("2024-25", "C.713", "Geography", "Admission", "Factors", "Text"),
            "C.714": FieldDefinition("2024-25", "C.714", "State residency", "Admission", "Factors", "Text"),
            "C.718": FieldDefinition("2024-25", "C.718", "Interest", "Admission", "Factors", "Text"),
            "C.1302": FieldDefinition("2024-25", "C.1302", "Application fee", "Admission", "Application", "Number"),
            "C.1305": FieldDefinition("2024-25", "C.1305", "Fee waiver", "Admission", "Application", "YN"),
            "C.901": FieldDefinition("2024-25", "C.901", "Submitting SAT Scores", "Admission", "Profile", "Whole Number or Round to Nearest Tenths"),
        },
        "2025-26": {
            "C.116": FieldDefinition("2025-26", "C.116", "Applied", "Admission", "Applications", "Number"),
            "C.117": FieldDefinition("2025-26", "C.117", "Admitted", "Admission", "Applications", "Number"),
            "C.118": FieldDefinition("2025-26", "C.118", "Enrolled", "Admission", "Applications", "Number"),
            "C.201": FieldDefinition("2025-26", "C.201", "Wait list policy", "Admission", "Wait List", "YesNo"),
            "C.202": FieldDefinition("2025-26", "C.202", "Wait list offered", "Admission", "Wait List", "Number"),
            "C.203": FieldDefinition("2025-26", "C.203", "Wait list accepted", "Admission", "Wait List", "Number"),
            "C.204": FieldDefinition("2025-26", "C.204", "Wait list admitted", "Admission", "Wait List", "Number"),
            "C.2101": FieldDefinition("2025-26", "C.2101", "ED offered", "Admission", "Early Decision", "YesNo"),
            "C.2106": FieldDefinition("2025-26", "C.2106", "Other ED closing month", "Admission", "Early Decision", "MM"),
            "C.2110": FieldDefinition("2025-26", "C.2110", "ED applicants", "Admission", "Early Decision", "Number"),
            "C.2111": FieldDefinition("2025-26", "C.2111", "ED admitted", "Admission", "Early Decision", "Number"),
            "C.2201": FieldDefinition("2025-26", "C.2201", "EA offered", "Admission", "Early Action", "YesNo"),
            "C.2206": FieldDefinition("2025-26", "C.2206", "EA restrictive", "Admission", "Early Action", "YesNo"),
            "C.711": FieldDefinition("2025-26", "C.711", "First generation", "Admission", "Factors", "Text"),
            "C.712": FieldDefinition("2025-26", "C.712", "Legacy", "Admission", "Factors", "Text"),
            "C.713": FieldDefinition("2025-26", "C.713", "Geography", "Admission", "Factors", "Text"),
            "C.714": FieldDefinition("2025-26", "C.714", "State residency", "Admission", "Factors", "Text"),
            "C.718": FieldDefinition("2025-26", "C.718", "Interest", "Admission", "Factors", "Text"),
            "C.1302": FieldDefinition("2025-26", "C.1302", "Application fee", "Admission", "Application", "Number"),
            "C.1305": FieldDefinition("2025-26", "C.1305", "Fee waiver", "Admission", "Application", "YesNo"),
            "C.901": FieldDefinition("2025-26", "C.901", "Percent Submitting SAT Scores", "Admission", "Profile", "Whole Number or Round to Nearest Tenth"),
            "C.902": FieldDefinition("2025-26", "C.902", "Percent Submitting ACT Scores", "Admission", "Profile", "Whole Number or Round to Nearest Tenth"),
            "C.905": FieldDefinition("2025-26", "C.905", "SAT Composite: 25th Percentile", "Admission", "Profile", "Whole Number or Round to Nearest Tenth"),
            "C.906": FieldDefinition("2025-26", "C.906", "SAT Composite: 50th Percentile", "Admission", "Profile", "Whole Number or Round to Nearest Tenth"),
            "C.907": FieldDefinition("2025-26", "C.907", "SAT Composite: 75th Percentile", "Admission", "Profile", "Whole Number or Round to Nearest Tenth"),
            "C.908": FieldDefinition("2025-26", "C.908", "SAT EBRW: 25th Percentile", "Admission", "Profile", "Whole Number or Round to Nearest Tenth"),
            "C.909": FieldDefinition("2025-26", "C.909", "SAT EBRW: 50th Percentile", "Admission", "Profile", "Whole Number or Round to Nearest Tenth"),
            "C.910": FieldDefinition("2025-26", "C.910", "SAT EBRW: 75th Percentile", "Admission", "Profile", "Whole Number or Round to Nearest Tenth"),
            "C.911": FieldDefinition("2025-26", "C.911", "SAT Math: 25th Percentile", "Admission", "Profile", "Whole Number or Round to Nearest Tenth"),
            "C.912": FieldDefinition("2025-26", "C.912", "SAT Math: 50th Percentile", "Admission", "Profile", "Whole Number or Round to Nearest Tenth"),
            "C.913": FieldDefinition("2025-26", "C.913", "SAT Math: 75th Percentile", "Admission", "Profile", "Whole Number or Round to Nearest Tenth"),
            "C.914": FieldDefinition("2025-26", "C.914", "ACT Composite: 25th Percentile", "Admission", "Profile", "Whole Number or Round to Nearest Tenth"),
            "C.915": FieldDefinition("2025-26", "C.915", "ACT Composite: 50th Percentile", "Admission", "Profile", "Whole Number or Round to Nearest Tenth"),
            "C.916": FieldDefinition("2025-26", "C.916", "ACT Composite: 75th Percentile", "Admission", "Profile", "Whole Number or Round to Nearest Tenth"),
            "B.2203": FieldDefinition("2025-26", "B.2203", "Retention percentage", "Enrollment", "Retention", "Whole Number or Round to Nearest Tenth"),
        }
    }


def doc(**overrides):
    base = {
        "document_id": "00000000-0000-0000-0000-000000000001",
        "school_id": "example",
        "school_name": "Example College",
        "sub_institutional": None,
        "ipeds_id": "123456",
        "canonical_year": "2024-25",
        "source_format": "pdf_fillable",
        "data_quality_flag": None,
    }
    base.update(overrides)
    return base


def artifact(
    producer="tier2_acroform",
    values=None,
    kind="canonical",
    created_at="2026-01-01T00:00:00Z",
    producer_version="0.1.0",
    notes_extra=None,
    schema_version="2025-26",
):
    notes = {"values": values or {}}
    if notes_extra:
        notes.update(notes_extra)
    return {
        "id": f"{producer}-{kind}",
        "document_id": "00000000-0000-0000-0000-000000000001",
        "kind": kind,
        "producer": producer,
        "producer_version": producer_version,
        "schema_version": schema_version,
        "created_at": created_at,
        "notes": notes,
    }


class FakeResult:
    def __init__(self, data=None):
        self.data = data


class FakeQuery:
    def __init__(self, data=None):
        self.data = data

    def select(self, *_args, **_kwargs):
        return self

    def eq(self, *_args, **_kwargs):
        return self

    def limit(self, *_args, **_kwargs):
        return self

    def execute(self):
        return FakeResult(self.data)


class FakeRpcClient:
    def __init__(self):
        self.calls = []

    def rpc(self, name, params):
        self.calls.append((name, params))
        return FakeQuery()


class FakeTableClient:
    def __init__(self, table_data):
        self.table_data = table_data

    def table(self, name):
        return FakeQuery(self.table_data.get(name, []))


class BrowserProjectionTests(unittest.TestCase):
    def test_direct_aliases_exclude_derived_metrics(self):
        aliases = metric_alias_rows(defs())
        names = {row["canonical_metric"] for row in aliases}
        self.assertEqual(names, set(DIRECT_METRIC_ALIASES))
        self.assertNotIn("acceptance_rate", names)
        self.assertNotIn("yield_rate", names)
        self.assertIn("sat_composite_p50", names)
        self.assertIn("act_composite_p75", names)

        fields, browser = build_projection_rows(
            doc(),
            [
                artifact(values={
                    "C.116": {"value": "100"},
                    "C.117": {"value": "20"},
                    "C.118": {"value": "10"},
                })
            ],
            defs(),
        )
        field_metrics = {row["canonical_metric"] for row in fields if row["canonical_metric"]}
        self.assertEqual(field_metrics, {"applied", "admitted", "first_year_enrolled"})
        self.assertEqual(browser["acceptance_rate"], "0.200000")
        self.assertEqual(browser["yield_rate"], "0.500000")

    def test_sat_act_promoted_fields_project_to_browser_columns(self):
        fields, browser = build_projection_rows(
            doc(),
            [
                artifact(values={
                    "C.901": {"value": "58%"},
                    "C.902": {"value": "31"},
                    "C.905": {"value": "1400"},
                    "C.906": {"value": "1450.0"},
                    "C.907": {"value": "1500"},
                    "C.914": {"value": "32"},
                    "C.915": {"value": "34"},
                    "C.916": {"value": "35"},
                })
            ],
            defs(),
        )
        metrics = {row["canonical_metric"]: row for row in fields if row["canonical_metric"]}
        self.assertEqual(metrics["sat_submit_rate"]["value_num"], "0.58")
        self.assertEqual(metrics["act_submit_rate"]["value_num"], "0.31")
        self.assertEqual(metrics["sat_composite_p50"]["value_num"], "1450.0")
        self.assertEqual(browser["sat_submit_rate"], "0.58")
        self.assertEqual(browser["act_submit_rate"], "0.31")
        self.assertEqual(browser["sat_composite_p25"], 1400)
        self.assertEqual(browser["sat_composite_p50"], 1450)
        self.assertEqual(browser["sat_composite_p75"], 1500)
        self.assertEqual(browser["act_composite_p25"], 32)
        self.assertEqual(browser["act_composite_p50"], 34)
        self.assertEqual(browser["act_composite_p75"], 35)

    def test_2024_admissions_metrics_derive_from_gender_split_fields(self):
        fields, browser = build_projection_rows(
            doc(canonical_year="2024-25"),
            [
                artifact(
                    schema_version="2024-25",
                    values={
                        "C.101": {"value": "10"},
                        "C.102": {"value": "20"},
                        "C.103": {"value": "3"},
                        "C.104": {"value": "2"},
                        "C.105": {"value": "5"},
                        "C.106": {"value": "10"},
                        "C.107": {"value": "1"},
                        "C.108": {"value": "1"},
                        "C.109": {"value": "2"},
                        "C.110": {"value": "1"},
                        "C.111": {"value": "4"},
                        "C.112": {"value": "1"},
                        "C.113": {"value": "1"},
                        "C.114": {"value": "0"},
                        "C.115": {"value": "1"},
                        "C.116": {"value": "0"},
                    },
                )
            ],
            defs(),
        )

        self.assertEqual(browser["applied"], 35)
        self.assertEqual(browser["admitted"], 17)
        self.assertEqual(browser["enrolled_first_year"], 10)
        self.assertEqual(browser["acceptance_rate"], "0.485714")
        self.assertEqual(browser["yield_rate"], "0.588235")
        by_field = {row["field_id"]: row for row in fields}
        self.assertEqual(by_field["C.103"]["equivalence_kind"], "unmapped")
        self.assertIsNone(by_field["C.103"]["canonical_field_id"])

    def test_2024_admissions_derived_metrics_treat_missing_split_components_as_zero(self):
        _fields, browser = build_projection_rows(
            doc(canonical_year="2024-25"),
            [
                artifact(
                    schema_version="2024-25",
                    values={
                        "C.101": {"value": "10"},
                        "C.102": {"value": "20"},
                        "C.105": {"value": "5"},
                        "C.106": {"value": "10"},
                        "C.109": {"value": "2"},
                        "C.111": {"value": "4"},
                    },
                )
            ],
            defs(),
        )

        self.assertEqual(browser["applied"], 30)
        self.assertEqual(browser["admitted"], 15)
        self.assertEqual(browser["enrolled_first_year"], 6)

    def test_2024_admissions_derived_metrics_use_total_fallback_when_available(self):
        _fields, browser = build_projection_rows(
            doc(canonical_year="2024-25"),
            [
                artifact(
                    schema_version="2024-25",
                    values={
                        "C.101": {"value": "10"},
                        "C.102": {"value": "20"},
                        "C.117": {"value": "35"},
                        "C.105": {"value": "5"},
                        "C.106": {"value": "10"},
                        "C.118": {"value": "17"},
                        "C.109": {"value": "2"},
                        "C.119": {"value": "10"},
                    },
                )
            ],
            defs(),
        )

        self.assertEqual(browser["applied"], 35)
        self.assertEqual(browser["admitted"], 17)
        self.assertEqual(browser["enrolled_first_year"], 10)

    def test_2024_direct_alias_uses_canonical_field_id(self):
        fields, browser = build_projection_rows(
            doc(canonical_year="2024-25"),
            [
                artifact(
                    schema_version="2024-25",
                    values={"C.901": {"value": "62"}},
                )
            ],
            defs(),
        )

        by_field = {row["field_id"]: row for row in fields}
        self.assertEqual(by_field["C.901"]["canonical_field_id"], "C.901")
        self.assertEqual(by_field["C.901"]["equivalence_kind"], "direct")
        self.assertEqual(by_field["C.901"]["canonical_metric"], "sat_submit_rate")
        self.assertEqual(browser["sat_submit_rate"], "0.62")

    def test_invalid_sat_act_values_are_parse_errors_and_not_browser_values(self):
        fields, browser = build_projection_rows(
            doc(),
            [
                artifact(values={
                    "C.905": {"value": "399"},
                    "C.906": {"value": "1450.5"},
                    "C.907": {"value": "1601"},
                    "C.914": {"value": "0"},
                    "C.915": {"value": "33.5"},
                    "C.916": {"value": "37"},
                })
            ],
            defs(),
        )
        by_field = {row["field_id"]: row for row in fields}
        for field_id in ("C.905", "C.906", "C.907", "C.914", "C.915", "C.916"):
            self.assertEqual(by_field[field_id]["value_status"], "parse_error")
            self.assertIsNone(by_field[field_id]["value_num"])
        self.assertIsNone(browser["sat_composite_p25"])
        self.assertIsNone(browser["sat_composite_p50"])
        self.assertIsNone(browser["sat_composite_p75"])
        self.assertIsNone(browser["act_composite_p25"])
        self.assertIsNone(browser["act_composite_p50"])
        self.assertIsNone(browser["act_composite_p75"])

    def test_admission_strategy_columns_project_from_2025_schema(self):
        _fields, browser = build_projection_rows(
            doc(canonical_year="2025-26"),
            [
                artifact(
                    schema_version="2025-26",
                    values={
                        "C.116": {"value": "1000"},
                        "C.117": {"value": "100"},
                        "C.118": {"value": "50"},
                        "C.2101": {"value": "Yes"},
                        "C.2106": {"value": "1"},
                        "C.2110": {"value": "200"},
                        "C.2111": {"value": "40"},
                        "C.2201": {"value": "Yes"},
                        "C.2206": {"value": "No"},
                        "C.201": {"value": "Yes"},
                        "C.202": {"value": "300"},
                        "C.203": {"value": "150"},
                        "C.204": {"value": "30"},
                        "C.711": {"value": "Important"},
                        "C.712": {"value": "Considered"},
                        "C.713": {"value": "Not Considered"},
                        "C.714": {"value": "Important"},
                        "C.718": {"value": "Very Important"},
                        "C.1302": {"value": "$85"},
                        "C.1305": {"value": "Yes"},
                    },
                )
            ],
            defs(),
        )

        self.assertEqual(browser["ed_offered"], True)
        self.assertEqual(browser["ed_applicants"], 200)
        self.assertEqual(browser["ed_admitted"], 40)
        self.assertEqual(browser["ed_has_second_deadline"], True)
        self.assertEqual(browser["ea_offered"], True)
        self.assertEqual(browser["ea_restrictive"], False)
        self.assertEqual(browser["wait_list_policy"], True)
        self.assertEqual(browser["wait_list_offered"], 300)
        self.assertEqual(browser["wait_list_accepted"], 150)
        self.assertEqual(browser["wait_list_admitted"], 30)
        self.assertEqual(browser["c711_first_gen_factor"], "Important")
        self.assertEqual(browser["c714_state_residency_factor"], "Important")
        self.assertEqual(browser["c718_demonstrated_interest_factor"], "Very Important")
        self.assertEqual(browser["app_fee_amount"], 85)
        self.assertEqual(browser["app_fee_waiver_offered"], True)
        self.assertEqual(browser["admission_strategy_card_quality"], "ok")

    def test_admission_strategy_quality_flags_ed_math(self):
        _fields, browser = build_projection_rows(
            doc(canonical_year="2025-26"),
            [
                artifact(
                    schema_version="2025-26",
                    values={
                        "C.116": {"value": "1000"},
                        "C.117": {"value": "100"},
                        "C.118": {"value": "50"},
                        "C.2101": {"value": "Yes"},
                        "C.2110": {"value": "40"},
                        "C.2111": {"value": "41"},
                    },
                )
            ],
            defs(),
        )

        self.assertEqual(browser["admission_strategy_card_quality"], "ed_math_inconsistent")

    def test_sub_institutional_is_preserved(self):
        fields, browser = build_projection_rows(
            doc(sub_institutional="general-studies"),
            [artifact(values={"C.116": {"value": "100"}})],
            defs(),
        )
        self.assertTrue(fields)
        self.assertEqual(fields[0]["sub_institutional"], "general-studies")
        self.assertEqual(browser["sub_institutional"], "general-studies")

    def test_percent_values_are_fractional(self):
        parsed = parse_field_value(
            {"value": "58%"},
            FieldDefinition("2025-26", "X.001", "Percent field", None, None, "Percent"),
        )
        self.assertEqual(parsed.value_kind, "percent")
        self.assertEqual(parsed.value_num, Decimal("0.58"))

        parsed_plain_percent = parse_field_value(
            {"value": "58"},
            FieldDefinition("2025-26", "B.2203", "Retention percentage", None, None, "Whole Number or Round to Nearest Tenth"),
        )
        self.assertEqual(parsed_plain_percent.value_kind, "percent")
        self.assertEqual(parsed_plain_percent.value_num, Decimal("0.58"))

    def test_percentile_is_not_treated_as_percent(self):
        parsed = parse_field_value(
            {"value": "1480"},
            FieldDefinition("2025-26", "C.905", "SAT 75th percentile", None, None, "Number"),
        )
        self.assertEqual(parsed.value_kind, "number")
        self.assertEqual(parsed.value_num, Decimal("1480"))

    def test_out_of_range_percent_is_parse_error(self):
        parsed = parse_field_value(
            {"value": "25457.5"},
            FieldDefinition("2025-26", "H.209", "Percentage of need met", None, None, "Nearest 1%"),
        )
        self.assertEqual(parsed.value_kind, "percent")
        self.assertEqual(parsed.value_status, "parse_error")
        self.assertIsNone(parsed.value_num)

    def test_tier4_fallback_overlay_fills_gaps_only(self):
        selected = select_extraction_result(
            "00000000-0000-0000-0000-000000000001",
            [
                artifact(
                    producer="tier4_docling",
                    producer_version="0.3.0",
                    values={
                        "C.116": {"value": "100"},
                        "C.117": {"value": "20"},
                    },
                    notes_extra={"markdown": "current markdown"},
                ),
                artifact(
                    producer="tier4_llm_fallback",
                    kind="cleaned",
                    values={
                        "C.117": {"value": "999"},
                        "C.118": {"value": "10"},
                    },
                    created_at="2026-01-02T00:00:00Z",
                    notes_extra={
                        "base_artifact_id": "tier4_docling-canonical",
                        "base_producer_version": "0.3.0",
                    },
                ),
            ],
        )
        self.assertIsNotNone(selected)
        assert selected is not None
        self.assertEqual(selected.values["C.117"]["value"], "20")
        self.assertEqual(selected.values["C.118"]["value"], "10")
        self.assertEqual(selected.value_sources["C.117"][0], "tier4_docling")
        self.assertEqual(selected.value_sources["C.118"][0], "tier4_llm_fallback")

    def test_tier4_fallback_overlay_requires_matching_schema_version(self):
        selected = select_extraction_result(
            "00000000-0000-0000-0000-000000000001",
            [
                artifact(
                    producer="tier4_docling",
                    producer_version="0.3.0",
                    values={"C.116": {"value": "100"}},
                    schema_version="2025-26",
                    notes_extra={"markdown": "current markdown"},
                ),
                artifact(
                    producer="tier4_llm_fallback",
                    kind="cleaned",
                    values={"C.118": {"value": "10"}},
                    created_at="2026-01-02T00:00:00Z",
                    schema_version="2024-25",
                    notes_extra={
                        "base_artifact_id": "tier4_docling-canonical",
                        "base_producer_version": "0.3.0",
                    },
                ),
            ],
        )

        self.assertIsNotNone(selected)
        assert selected is not None
        self.assertIsNone(selected.fallback_artifact_id)
        self.assertNotIn("C.118", selected.values)

    def test_selected_result_prefers_year_matched_non_fallback_artifact(self):
        selected = select_extraction_result(
            "00000000-0000-0000-0000-000000000001",
            [
                artifact(
                    values={"C.116": {"value": "999"}},
                    created_at="2026-01-03T00:00:00Z",
                    notes_extra={"schema_fallback_used": True},
                    schema_version="2025-26",
                ),
                artifact(
                    values={"C.101": {"value": "10"}},
                    created_at="2026-01-01T00:00:00Z",
                    schema_version="2024-25",
                ),
            ],
            expected_schema_version="2024-25",
        )

        self.assertIsNotNone(selected)
        assert selected is not None
        self.assertEqual(selected.schema_version, "2024-25")
        self.assertIn("C.101", selected.values)
        self.assertNotIn("C.116", selected.values)

    def test_tier4_fallback_overlay_ignores_stale_base(self):
        selected = select_extraction_result(
            "00000000-0000-0000-0000-000000000001",
            [
                artifact(
                    producer="tier4_docling",
                    producer_version="0.3.0",
                    values={"C.116": {"value": "100"}},
                    notes_extra={"markdown": "fresh v0.3 markdown"},
                ),
                artifact(
                    producer="tier4_llm_fallback",
                    kind="cleaned",
                    values={"C.118": {"value": "10"}},
                    created_at="2026-01-02T00:00:00Z",
                    notes_extra={
                        "markdown_sha256": "not-the-fresh-markdown-hash",
                        "cleaner_version": "0.2.0",
                    },
                ),
            ],
        )
        self.assertIsNotNone(selected)
        assert selected is not None
        self.assertIsNone(selected.fallback_artifact_id)
        self.assertNotIn("C.118", selected.values)

    def test_legacy_tier4_fallback_overlay_matches_markdown_hash(self):
        markdown = "legacy compatible markdown"
        selected = select_extraction_result(
            "00000000-0000-0000-0000-000000000001",
            [
                artifact(
                    producer="tier4_docling",
                    producer_version="0.3.0",
                    values={"C.116": {"value": "100"}},
                    notes_extra={"markdown": markdown},
                ),
                artifact(
                    producer="tier4_llm_fallback",
                    kind="cleaned",
                    values={"C.118": {"value": "10"}},
                    created_at="2026-01-02T00:00:00Z",
                    notes_extra={
                        "markdown_sha256": hashlib.sha256(markdown.encode("utf-8")).hexdigest(),
                        "cleaner_version": "0.3.0",
                    },
                ),
            ],
        )
        self.assertIsNotNone(selected)
        assert selected is not None
        self.assertEqual(selected.values["C.118"]["value"], "10")

    def test_derived_metric_formula_requires_explicit_schema_year(self):
        metric = DIRECT_METRIC_DEFINITIONS["applied"]

        self.assertEqual(metric_field_ids_for_year(metric, "2025-26"), ("C.116",))
        self.assertIsNone(metric_field_ids_for_year(metric, "2026-27"))

    def test_replace_projection_rows_uses_atomic_rpc(self):
        client = FakeRpcClient()
        field_rows = [{"document_id": "00000000-0000-0000-0000-000000000001"}]
        browser_row = {"document_id": "00000000-0000-0000-0000-000000000001"}

        replace_projection_rows(
            client,
            "00000000-0000-0000-0000-000000000001",
            field_rows,
            browser_row,
        )

        self.assertEqual(len(client.calls), 1)
        name, params = client.calls[0]
        self.assertEqual(name, "replace_browser_projection_for_document")
        self.assertEqual(params["p_document_id"], "00000000-0000-0000-0000-000000000001")
        self.assertEqual(params["p_field_rows"], field_rows)
        self.assertEqual(params["p_browser_row"], browser_row)

    def test_project_document_id_no_manifest_row_is_noop(self):
        client = FakeTableClient({"cds_manifest": []})

        count, has_browser_row = project_document_id(
            client,
            "00000000-0000-0000-0000-000000000001",
            defs(),
        )

        self.assertEqual(count, 0)
        self.assertFalse(has_browser_row)


if __name__ == "__main__":
    unittest.main()
