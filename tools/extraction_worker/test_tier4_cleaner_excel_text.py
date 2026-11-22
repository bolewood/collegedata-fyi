"""A CDS workbook printed to PDF from Excel: its text layer.

Counts carry one decimal ("13,263.0"), and some files write every space as
U+00A0 and every hyphen as U+2010.
"""
from __future__ import annotations

import unittest
from pathlib import Path

from tier4_cleaner import SchemaIndex, _strip_whole_number_decimals, clean

REPO_ROOT = Path(__file__).resolve().parents[2]
SCHEMA_2023 = SchemaIndex(REPO_ROOT / "schemas" / "cds_schema_2023_24.json")


def _values(result: dict[str, dict]) -> dict[str, str]:
    return {qn: str(entry["value"]) for qn, entry in result.items()}


class WholeNumberDecimalsTest(unittest.TestCase):
    def test_text_without_the_signature_is_left_alone(self):
        text = "Total applied   1,204.0   88.0\nAverage GPA   3.0\n"

        self.assertEqual(_strip_whole_number_decimals(text), text)

    def test_cells_lose_the_decimal_and_keep_their_columns(self):
        text = (
            "Applied      3,721.0     5,030.0     0.0\n"
            "Admitted     3,183.0     4,377.0     0.0\n"
            "| Enrolled | 1,196.0 | 547.0 |\n"
        )

        out = _strip_whole_number_decimals(text)

        self.assertEqual(
            out,
            "Applied      3,721       5,030       0  \n"
            "Admitted     3,183       4,377       0  \n"
            "| Enrolled | 1,196   | 547   |\n",
        )
        self.assertEqual(len(out), len(text))

    def test_a_number_inside_a_sentence_and_other_decimals_stay(self):
        text = (
            "Applied   3,721.0   5,030.0   8,751.0\n"
            "Percent who had a GPA of 4.0 or higher     35.5\n"
            "Books and supplies:   1,160.00\n"
            "Average GPA   3.84\n"
        )

        out = _strip_whole_number_decimals(text)

        self.assertIn("GPA of 4.0 or higher     35.5", out)
        self.assertIn("1,160.00", out)
        self.assertIn("3.84", out)


C1_RESIDENCY_TEXT = """\
C1. Applications: First-time, First-year Students
                                                              In-State    Out-of-State    International       Total
 Total first-time, first-year (degree seeking) who applied      4,407.0         4,055.0           289.0     8,751.0
 Total first-time, first-year (degree seeking) who were admitted  3,828.0       3,612.0           120.0     7,560.0
 Total first-time, first-year (degree seeking) enrolled           682.0           493.0            21.0     1,196.0
C2. Applications: First-time, First-year Wait-Listed Students
"""


class ExcelTextLayerTest(unittest.TestCase):
    def _residency(self, text: str) -> dict[str, str]:
        values = _values(clean("", schema=SCHEMA_2023, supplemental_text=text))
        return {qn: values.get(qn) for qn in ("C.117", "C.118", "C.119", "C.120", "C.125", "C.128")}

    def test_counts_with_a_decimal_are_read_as_one_number_each(self):
        # "8,751.0" was split into 8,751 and 0: five numbers under four columns.
        self.assertEqual(
            self._residency(C1_RESIDENCY_TEXT),
            {"C.117": "8751", "C.118": "7560", "C.119": "1196",
             "C.120": "4407", "C.125": "493", "C.128": "21"},
        )

    def test_excel_spaces_and_hyphens_read_like_ascii(self):
        text = C1_RESIDENCY_TEXT.replace(" ", "\u00a0").replace("-", "\u2010")

        self.assertEqual(
            self._residency(text),
            {"C.117": "8751", "C.118": "7560", "C.119": "1196",
             "C.120": "4407", "C.125": "493", "C.128": "21"},
        )


if __name__ == "__main__":
    unittest.main()
