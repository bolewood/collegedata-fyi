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
