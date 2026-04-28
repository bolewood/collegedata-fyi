import unittest
from decimal import Decimal

from tools.browser_backend.project_browser_data import (
    DIRECT_METRIC_ALIASES,
    FieldDefinition,
    build_projection_rows,
    metric_alias_rows,
    parse_field_value,
    select_extraction_result,
)


def defs():
    return {
        "2025-26": {
            "C.116": FieldDefinition("2025-26", "C.116", "Applied", "Admission", "Applications", "Number"),
            "C.117": FieldDefinition("2025-26", "C.117", "Admitted", "Admission", "Applications", "Number"),
            "C.118": FieldDefinition("2025-26", "C.118", "Enrolled", "Admission", "Applications", "Number"),
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


def artifact(producer="tier2_acroform", values=None, kind="canonical", created_at="2026-01-01T00:00:00Z"):
    return {
        "id": f"{producer}-{kind}",
        "document_id": "00000000-0000-0000-0000-000000000001",
        "kind": kind,
        "producer": producer,
        "producer_version": "0.1.0",
        "schema_version": "2025-26" if kind == "canonical" else None,
        "created_at": created_at,
        "notes": {"values": values or {}},
    }


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
                    values={
                        "C.116": {"value": "100"},
                        "C.117": {"value": "20"},
                    },
                ),
                artifact(
                    producer="tier4_llm_fallback",
                    kind="cleaned",
                    values={
                        "C.117": {"value": "999"},
                        "C.118": {"value": "10"},
                    },
                    created_at="2026-01-02T00:00:00Z",
                ),
            ],
        )
        self.assertIsNotNone(selected)
        assert selected is not None
        self.assertEqual(selected.values["C.117"]["value"], "20")
        self.assertEqual(selected.values["C.118"]["value"], "10")
        self.assertEqual(selected.value_sources["C.117"][0], "tier4_docling")
        self.assertEqual(selected.value_sources["C.118"][0], "tier4_llm_fallback")


if __name__ == "__main__":
    unittest.main()
