import tempfile
import unittest
from pathlib import Path

import openpyxl

from tools.schema_builder.build_from_xlsx import (
    build_schema,
    normalize_question_number,
)


class BuildFromXlsxTest(unittest.TestCase):
    def test_normalize_question_number(self):
        cases = {
            "A01": "A.001",
            "A511": "A.511",
            "B2101": "B.2101",
            "A0A": "A.0A",
            "C8G01": "C.8G01",
            "H2A01": "H.2A01",
            "C.916": "C.916",
        }

        for raw, expected in cases.items():
            with self.subTest(raw=raw):
                self.assertEqual(normalize_question_number(raw), expected)

    def test_build_schema_from_reduced_answer_sheet(self):
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Answer Sheet"
        ws.append(
            [
                "Question Number",
                "Question",
                "Answer",
                "Section",
                "Sub-Section",
                "Category",
                "Student Group",
                "Cohort",
                "Residency",
                "Unit load",
                "Gender",
                "Value type",
            ]
        )
        ws.append(
            [
                "A01",
                "Name:",
                "=A1",
                "General Information",
                "Respondent Information",
                "All",
                "All",
                "All",
                "All",
                "All",
                "All",
                "Text",
            ]
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "cds_2024-25_template.xlsx"
            wb.save(path)
            schema = build_schema(path)

        self.assertEqual(schema["schema_version"], "2024-25")
        self.assertEqual(schema["field_count"], 1)
        self.assertEqual(schema["fields"][0]["sort_order"], 1)
        self.assertEqual(schema["fields"][0]["question_number"], "A.001")
        self.assertIsNone(schema["fields"][0]["pdf_tag"])
        self.assertIsNone(schema["fields"][0]["word_tag"])
        self.assertFalse(schema["fields"][0]["computed"])


if __name__ == "__main__":
    unittest.main()
