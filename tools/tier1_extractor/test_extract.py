from __future__ import annotations

import tempfile
import sys
import unittest
from pathlib import Path

import openpyxl

sys.path.insert(0, str(Path(__file__).resolve().parent))
from extract import extract


class Tier1ExtractTests(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
