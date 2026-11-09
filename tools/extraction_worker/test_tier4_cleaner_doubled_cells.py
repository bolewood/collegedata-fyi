from __future__ import annotations

import unittest

from tier4_cleaner import _collapse_doubled_cells, clean

# TCU 2022-23 (and RIT / Houston Christian 2025-26) are flattened forms whose
# text layer carries every typed value twice, so Docling 2.148 emits cells
# like "113 113". Rows copied from the stored TCU markdown.
_TCU_B2 = """\
## B2. Enrollment by Racial/Ethnic Category.

|                                                         | Degree-seeking First-time First year   | Degree-seeking Undergraduates (include first-time first-year)   | Total Undergraduates (both degree- and non-degree- seeking)   |
|---------------------------------------------------------|----------------------------------------|-----------------------------------------------------------------|---------------------------------------------------------------|
| Nonresidents                                            | 113 113                                | 508 508                                                         | 509 509                                                       |
| Hispanic/Latino                                         | 434 434                                | 1781 1781                                                       | 1783 1783                                                     |
| Black or African American, non-Hispanic                 | 104 104                                | 451 451                                                         | 452 452                                                       |
| White, non-Hispanic                                     | 1624 1624                              | 6885 6885                                                       | 6888 6888                                                     |
| Asian, non-Hispanic                                     | 60 60                                  | 238 238                                                         | 238 238                                                       |
"""

_TCU_C9 = """\
## C9. First-time, first-year profile

| Assessment                             | 25th Percentile Score   | 50th Percentile Score   | 75th Percentile Score   |
|----------------------------------------|-------------------------|-------------------------|-------------------------|
| SAT Composite                          | 1140 1140               | 1260 1242               | 1360 1360               |
| SAT Evidence-Based Reading and Writing | 580 580                 | 630 620                 | 680 680                 |
| SAT Math                               | 560 560                 | 630 623                 | 680 680                 |
"""


def _values(markdown: str, year: str = "2022-23") -> dict[str, str]:
    return {k: v["value"] for k, v in clean(markdown, canonical_year=year).items()}


class DoubledCellTest(unittest.TestCase):
    def test_doubled_b2_cells_parse_as_single_values(self):
        values = _values(_TCU_B2)
        self.assertEqual(values.get("B.201"), "113")
        self.assertEqual(values.get("B.202"), "434")
        self.assertEqual(values.get("B.212"), "1781")
        self.assertEqual(values.get("B.214"), "6885")

    def test_doubled_c9_percentiles_stay_in_their_columns(self):
        values = _values(_TCU_B2 + "\n" + _TCU_C9)
        self.assertEqual(values.get("C.908"), "580")
        self.assertEqual(values.get("C.910"), "680")
        self.assertEqual(values.get("C.911"), "560")
        self.assertEqual(values.get("C.913"), "680")

    def test_isolated_repeat_in_a_normal_document_is_left_alone(self):
        markdown = (
            "| Label | A | B |\n|---|---|---|\n"
            + "".join(f"| row {i} | {i} | {i + 1} |\n" for i in range(20))
            + "| odd | 10 10 | 5 |\n"
        )
        self.assertEqual(_collapse_doubled_cells(markdown), markdown)

    def test_doubled_text_cells_collapse_when_document_is_doubled(self):
        markdown = _TCU_B2 + "| Note | 1 year 1 year | x |\n"
        self.assertIn("| 1 year |", _collapse_doubled_cells(markdown))


class C1EnrolledBySexTest(unittest.TestCase):
    def test_full_time_row_does_not_fill_enrolled_total(self):
        # RIT 2025-26: the plain "men who enrolled" row's verb is in a
        # shifted font ("HQUROOHG"), so only the full-time row matches.
        markdown = """\
## C1. Applications

| FIRST-TIME, FIRST-YEAR STUDENT ENROLLEES                   | TOTAL |
|------------------------------------------------------------|-------|
| Total first-time, first-year men who HQUROOHG              | 1899  |
| Total full-time, first-time, first-year men who enrolled   | 1897  |
| Total part-time, first-time, first-year men who enrolled   | 2     |
| Total full-time, first-time, first-year women who enrolled | 1046  |
"""
        values = _values(markdown, year="2025-26")
        self.assertEqual(values.get("C.110"), "1897")
        self.assertEqual(values.get("C.112"), "1046")
        # Total men enrolled = full-time + part-time (the PDF prints 1899).
        self.assertEqual(values.get("C.107"), "1899")
        # Women have no part-time row here, so the total stays unknown.
        self.assertIsNone(values.get("C.108"))


if __name__ == "__main__":
    unittest.main()
