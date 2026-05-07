import tempfile
import unittest
from pathlib import Path

import openpyxl

from tools.schema_builder.build_from_tabs import build_structural_schema


class BuildFromTabsTest(unittest.TestCase):
    def test_row_metadata_sheet_preserves_canonical_question_numbers(self):
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "CDS-C"
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
                "C101",
                "Total first-time, first-year men who applied",
                None,
                "First-Time, First-Year Admission",
                "Applications",
                "Applied",
                "Undergraduates",
                "First-time, first-year",
                "All",
                "All",
                "Men",
                "Number",
            ]
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "cds_2024-25_template.xlsx"
            wb.save(path)
            schema = build_structural_schema(path)

        self.assertEqual(schema["schema_version"], "2024-25")
        self.assertEqual(schema["section_count"], 1)
        self.assertEqual(schema["subsection_count"], 1)
        question = schema["sections"][0]["subsections"][0]["questions"][0]
        self.assertEqual(question["canonical_question_number"], "C.101")
        self.assertEqual(question["columns"][0]["cell_ref"], "CDS-C!C2")
        self.assertEqual(question["category"], "Applied")


if __name__ == "__main__":
    unittest.main()
