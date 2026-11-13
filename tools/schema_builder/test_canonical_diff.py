import unittest

from tools.schema_builder.canonical_diff import build_diff


def field(question_number, question, pdf_tag=None, **overrides):
    data = {
        "question_number": question_number,
        "question": question,
        "pdf_tag": pdf_tag,
        "section": "First-Time, First-Year Admission",
        "subsection": "Applications",
        "category": "All",
        "student_group": "Undergraduates",
        "cohort": "First-time, first-year",
        "residency": "All",
        "unit_load": "All",
        "gender": "All",
        "value_type": "Number",
    }
    data.update(overrides)
    return data


class CanonicalDiffTest(unittest.TestCase):
    def test_academic_profile_minor_wording_drift_is_direct(self):
        source = {
            "schema_version": "2024-25",
            "fields": [
                field(
                    "C.901",
                    "Submitting SAT scores",
                    gender="All",
                    value_type="Whole Number or Round to Nearest Tenths",
                )
            ],
        }
        target = {
            "schema_version": "2025-26",
            "fields": [
                field(
                    "C.901",
                    "Percent Submitting SAT Scores",
                    "SUBMIT_SAT1_P",
                    gender="All",
                    value_type="Whole Number or Round to Nearest Tenths",
                )
            ],
        }

        diff = build_diff(source, target, {"SUBMIT_SAT1_P"})

        self.assertEqual(diff["fields"][0]["equivalence_kind"], "direct")
        self.assertEqual(diff["fields"][0]["canonical_field_id"], "C.901")
        self.assertEqual(diff["fields"][0]["pdf_tag"], "SUBMIT_SAT1_P")

    def test_another_gender_field_is_unmapped(self):
        source = {
            "schema_version": "2024-25",
            "fields": [
                field(
                    "C.103",
                    "Total first-time, first-year another gender who applied",
                    gender="Another Gender",
                )
            ],
        }
        target = {
            "schema_version": "2025-26",
            "fields": [
                field(
                    "C.103",
                    "Total first-time, first-year students of unknown sex who applied",
                    "AP_RECD_1ST_UNK_N",
                    gender="Unknown",
                )
            ],
        }

        diff = build_diff(source, target, {"AP_RECD_1ST_UNK_N"})

        self.assertEqual(diff["fields"][0]["equivalence_kind"], "unmapped")
        self.assertIsNone(diff["fields"][0]["canonical_field_id"])
        self.assertIsNone(diff["fields"][0]["pdf_tag"])

    def test_admissions_metric_formulas_are_recorded(self):
        diff = build_diff(
            {"schema_version": "2024-25", "fields": []},
            {"schema_version": "2025-26", "fields": []},
            set(),
        )

        metrics = {m["canonical_metric"]: m for m in diff["derived_metrics"]}
        self.assertEqual(
            metrics["applied"]["per_year_formulas"]["2024-25"],
            "C.101 + C.102 + C.103 + C.104",
        )
        self.assertEqual(metrics["applied"]["per_year_formulas"]["2025-26"], "C.116")


class RotcCooperatingInstitutionTagTest(unittest.TestCase):
    """The 2024-25 Answer Sheet labels all three ROTC text rows category Army."""

    def _fields(self, categories, version_fields):
        return [
            field(qn, "Name of Cooperating Institution", section="Student Life",
                  subsection="ROTC", category=cat, value_type="Text", pdf_tag=tag)
            for (qn, tag), cat in zip(version_fields, categories)
        ]

    def test_mislabelled_army_rows_get_their_own_pdf_tags(self):
        source = {"schema_version": "2024-25", "fields": self._fields(
            ["Army", "Army", "Army"], [("F.303", None), ("F.307", None), ("F.310", None)])}
        target = {"schema_version": "2025-26", "fields": self._fields(
            ["Army", "Navy", "Airforce"],
            [("F.302", "ROTC_ARMY_TEXT"), ("F.305", "ROTC_NAVY_TEXT"), ("F.307", "ROTC_AF_TEXT")])}
        diff = build_diff(source, target, {"ROTC_ARMY_TEXT", "ROTC_NAVY_TEXT", "ROTC_AF_TEXT"})
        tags = {r["field_id"]: r["pdf_tag"] for r in diff["fields"]}
        self.assertEqual(tags, {"F.303": "ROTC_ARMY_TEXT", "F.307": "ROTC_NAVY_TEXT", "F.310": "ROTC_AF_TEXT"})

    def test_committed_schemas_give_each_rotc_text_tag_once(self):
        import json
        from pathlib import Path
        root = Path(__file__).resolve().parents[2] / "schemas"
        for year in ("2023_24", "2024_25"):
            fields = json.loads((root / f"cds_schema_{year}.json").read_text())["fields"]
            tags = {f["question_number"]: f["pdf_tag"] for f in fields
                    if f["question_number"] in ("F.303", "F.307", "F.310")}
            self.assertEqual(tags, {"F.303": "ROTC_ARMY_TEXT", "F.307": "ROTC_NAVY_TEXT", "F.310": "ROTC_AF_TEXT"})


if __name__ == "__main__":
    unittest.main()
