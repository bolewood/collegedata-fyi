import json
import unittest
from pathlib import Path

from tools.schema_builder.build_core_table_overlay import build_overlay


ROOT = Path(__file__).resolve().parents[2]


class BuildCoreTableOverlayTest(unittest.TestCase):
    def test_2019_maps_legacy_c1_and_c9_percentiles(self):
        source = json.loads((ROOT / "schemas/cds_schema_2019_20.structural.json").read_text())
        target = json.loads((ROOT / "schemas/cds_schema_2025_26.json").read_text())

        overlay = build_overlay(source, target)
        by_source = {
            (m["row_label"], m["column_header"]): m["canonical_question_number"]
            for m in overlay["mappings"]
        }

        self.assertEqual(
            by_source[("Total first-time, first-year (freshman) men who applied", None)],
            "C.101",
        )
        self.assertEqual(
            by_source[("Total part-time, first-time, first-year (freshman) women who enrolled", None)],
            "C.113",
        )
        self.assertEqual(
            by_source[("Percent submitting SAT scores", None)],
            "C.901",
        )
        self.assertEqual(
            by_source[("SAT Composite", "75th Percentile")],
            "C.907",
        )

    def test_2023_keeps_another_gender_and_gender_residency_unmapped(self):
        source = json.loads((ROOT / "schemas/cds_schema_2023_24.structural.json").read_text())
        target = json.loads((ROOT / "schemas/cds_schema_2025_26.json").read_text())

        overlay = build_overlay(source, target)
        unmapped_reasons = {
            (u["row_label"], u["column_header"]): u["reason"]
            for u in overlay["unmapped"]
        }

        self.assertEqual(
            unmapped_reasons[("Total first-time, first-year another gender who applied", None)],
            "no_2025_target_for_another_gender",
        )
        self.assertEqual(
            unmapped_reasons[("Total first-time, first-year men who applied", "In-State")],
            "gender_specific_residency_not_in_2025_schema",
        )

    def test_2023_maps_c7_factor_choices_and_keeps_removed_factor_unmapped(self):
        source = json.loads((ROOT / "schemas/cds_schema_2022_23.structural.json").read_text())
        target = json.loads((ROOT / "schemas/cds_schema_2025_26.json").read_text())

        overlay = build_overlay(source, target)
        by_source = {
            (m["row_label"], m["column_header"]): m
            for m in overlay["mappings"]
        }
        unmapped_reasons = {
            (u["row_label"], u["column_header"]): u["reason"]
            for u in overlay["unmapped"]
        }

        mapped = by_source[("Academic GPA", "Very Important")]
        self.assertEqual(mapped["canonical_question_number"], "C.703")
        self.assertEqual(mapped["source_choice_value"], "Very Important")
        self.assertEqual(
            unmapped_reasons[("Racial/ethnic status", "Very Important")],
            "no_2025_target_for_c7_factor",
        )


if __name__ == "__main__":
    unittest.main()
