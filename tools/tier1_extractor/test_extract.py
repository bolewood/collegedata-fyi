from __future__ import annotations

import tempfile
import sys
import unittest
from pathlib import Path

import openpyxl

sys.path.insert(0, str(Path(__file__).resolve().parent))
from extract import extract


class Tier1ExtractTests(unittest.TestCase):
    def test_uses_short_section_tab_aliases_for_template_cell_map(self):
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "A"
        ws["D4"] = "Alias University"

        with tempfile.NamedTemporaryFile(suffix=".xlsx") as tmp:
            wb.save(tmp.name)
            schema = {
                "schema_version": "2025-26",
                "fields": [{
                    "question_number": "A.101",
                    "word_tag": "institution_name",
                    "question": "Name of College/University:",
                    "section": "General Information",
                    "subsection": "Institutional Contact Information",
                    "value_type": "Text",
                }],
            }
            result = extract(
                Path(tmp.name),
                schema,
                {"A.101": ("CDS-A", "D4")},
            )

        self.assertEqual(result["stats"]["extraction_layout"], "template_cell_map")
        self.assertEqual(result["stats"]["schema_fields_populated"], 1)
        self.assertEqual(result["values"]["A.101"]["value"], "Alias University")
        self.assertEqual(result["stats"]["missing_sheets"], [])

    def test_uses_descriptive_section_tab_aliases_for_c9_recovery(self):
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Admissions"
        ws["B10"] = "Percent and number of first-time, first-year students enrolled in Fall 2025 who submitted national standardized (SAT/ACT) test scores."
        ws["B13"] = "Submitting SAT Scores"
        ws["C13"] = 0.55
        ws["D13"] = 2833
        ws["B18"] = "SAT Composite"
        ws["C18"] = 1140
        ws["D18"] = 1250
        ws["E18"] = 1350

        schema = {
            "schema_version": "2025-26",
            "fields": [
                {
                    "question_number": qnum,
                    "word_tag": None,
                    "question": qnum,
                    "section": "First-Time, First-Year Admission",
                    "subsection": "First-time, first-year Profile",
                    "value_type": "Number",
                }
                for qnum in ("C.901", "C.903", "C.905", "C.906", "C.907")
            ],
        }

        with tempfile.NamedTemporaryFile(suffix=".xlsx") as tmp:
            wb.save(tmp.name)
            result = extract(
                Path(tmp.name),
                schema,
                {"C.901": ("CDS-C", "C99")},
            )

        self.assertEqual(result["values"]["C.901"]["value"], "0.55")
        self.assertEqual(result["values"]["C.903"]["value"], "2833")
        self.assertEqual(result["values"]["C.905"]["value"], "1140")
        self.assertEqual(result["values"]["C.907"]["value"], "1350")

    def test_falls_back_to_embedded_answer_columns(self):
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "CDS-C"
        ws["AA1"] = "Question Number"
        ws["AB1"] = "Question"
        ws["AC1"] = "Answer"
        ws["AA2"] = "C.101"
        ws["AB2"] = "Total first-time, first-year males who applied"
        ws["AC2"] = 1234

        with tempfile.NamedTemporaryFile(suffix=".xlsx") as tmp:
            wb.save(tmp.name)
            schema = {
                "schema_version": "2025-26",
                "fields": [{
                    "question_number": "C.101",
                    "word_tag": "c1_male_applicants",
                    "question": "Total first-time, first-year males who applied",
                    "section": "First-Time, First-Year Admission",
                    "subsection": "Applications",
                    "value_type": "Number",
                }],
            }
            result = extract(
                Path(tmp.name),
                schema,
                {"C.101": ("CDS-C", "D4")},
            )

        self.assertEqual(result["stats"]["extraction_layout"], "embedded_answer_columns")
        self.assertEqual(result["stats"]["schema_fields_populated"], 1)
        self.assertEqual(result["values"]["C.101"]["value"], "1234")

    def test_recovers_shifted_c9_academic_profile_rows_by_label(self):
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "CDS-C"
        ws["B10"] = "Percent and number of first-time, first-year students enrolled in Fall 2024 who submitted national standardized (SAT/ACT) test scores."
        ws["C12"] = "Percent"
        ws["D12"] = "Number"
        ws["B13"] = "Submitting SAT Scores"
        ws["C13"] = 0.043
        ws["D13"] = 299
        ws["B14"] = "Submitting ACT Scores"
        ws["C14"] = 0.002
        ws["D14"] = 13
        ws["B17"] = "Assessment"
        ws["C17"] = "25th Percentile"
        ws["D17"] = "50th Percentile"
        ws["E17"] = "75th Percentile"
        ws["B18"] = "SAT Composite"
        ws["C18"] = 860
        ws["D18"] = 950
        ws["E18"] = 1050
        ws["B19"] = "SAT Evidence-Based Reading and Writing"
        ws["C19"] = 450
        ws["D19"] = 490
        ws["E19"] = 540
        ws["B20"] = "SAT Math"
        ws["C20"] = 410
        ws["D20"] = 470
        ws["E20"] = 530
        ws["B21"] = "ACT Composite"
        ws["C21"] = 21.5
        ws["D21"] = 25
        ws["E21"] = 29
        ws["A30"] = "C14"
        ws["B30"] = "Application closing date (fall)"
        ws["C30"] = "2025-11-30 00:00:00"

        schema = {
            "schema_version": "2024-25",
            "fields": [
                {
                    "question_number": f"C.{i}",
                    "word_tag": None,
                    "question": f"C.{i}",
                    "section": "First-Time, First-Year Admission",
                    "subsection": "First-time, first-year Profile",
                    "value_type": "Number",
                }
                for i in range(901, 917)
            ],
        }
        cell_map = {
            "C.911": ("CDS-C", "C30"),
            "C.912": ("CDS-C", "C30"),
        }

        with tempfile.NamedTemporaryFile(suffix=".xlsx") as tmp:
            wb.save(tmp.name)
            result = extract(Path(tmp.name), schema, cell_map)

        self.assertEqual(result["values"]["C.901"]["value"], "0.043")
        self.assertEqual(result["values"]["C.903"]["value"], "299")
        self.assertEqual(result["values"]["C.911"]["value"], "410")
        self.assertEqual(result["values"]["C.912"]["value"], "470")
        self.assertEqual(result["values"]["C.916"]["value"], "29")
        self.assertEqual(result["stats"]["academic_profile_fields_recovered"], 16)

    def test_recovers_freshman_c9_header_and_clears_blank_visible_rows(self):
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "CDS-C"
        ws["B10"] = "Percent and number of first-time, first-year (freshman) students enrolled in Fall 2024 who submitted national standardized (SAT/ACT) test scores."
        ws["B13"] = "SAT Evidence-Based Reading and Writing"
        ws["C13"] = 600
        ws["D13"] = 660
        ws["E13"] = 720
        ws["B14"] = "SAT Math"
        ws["B20"] = "C10: Class Rank"
        ws["C30"] = "2025-05-01 00:00:00"
        ws["D30"] = 60

        schema = {
            "schema_version": "2024-25",
            "fields": [
                {
                    "question_number": f"C.{i}",
                    "word_tag": None,
                    "question": f"C.{i}",
                    "section": "First-Time, First-Year Admission",
                    "subsection": "First-time, first-year Profile",
                    "value_type": "Number",
                }
                for i in range(908, 914)
            ],
        }
        cell_map = {
            "C.910": ("CDS-C", "D30"),
            "C.911": ("CDS-C", "C30"),
            "C.912": ("CDS-C", "C30"),
        }

        with tempfile.NamedTemporaryFile(suffix=".xlsx") as tmp:
            wb.save(tmp.name)
            result = extract(Path(tmp.name), schema, cell_map)

        self.assertEqual(result["values"]["C.908"]["value"], "600")
        self.assertEqual(result["values"]["C.909"]["value"], "660")
        self.assertEqual(result["values"]["C.910"]["value"], "720")
        self.assertNotIn("C.911", result["values"])
        self.assertNotIn("C.912", result["values"])
        self.assertNotIn("C.913", result["values"])
        self.assertEqual(result["stats"]["academic_profile_fields_recovered"], 5)


if __name__ == "__main__":
    unittest.main()
