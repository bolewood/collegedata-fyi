from __future__ import annotations

import unittest

from tier4_cleaner import _parse_markdown_tables, _strip_fused_question_tag, clean

# College of Southern Idaho 2011-12 prints the question tag in the margin of
# every row. Docling joins it to the row label; the text layer keeps it in
# front of the label and wraps the longest one.
_TABLE = """
B2 Enrollment by Racial/Ethnic Category.

| B2 under "Two or more races." | Degree-Seeking First-Time First Year | Degree-Seeking Undergraduates (include first-time first-year) | Total Undergraduates (both degree- and non-degree- seeking) |
|---|---|---|---|
| B2 Nonresident aliens | 26 | 65 | 74 |
| B2 Hispanic | 356 | 1,041 | 1,243 |
| B2 Black or African American, non-Hispanic | 25 | 58 | 68 |
| B2 Native Hawaiian or other Pacific Islander, non- Hispanic | 14 | 58 | 383 |
| B2 TOTAL | 1,510 | 5,909 | 9,085 |

## B3 Number of degrees awarded from July 1, 2010 to June 30, 2011
"""

_TEXT_LAYER = """
B2   Enrollment by Racial/Ethnic Category. Provide numbers of undergraduate students.
B2   under "Two or more races."                                                  Total
                                                  Degree-Seeking
B2   Nonresident aliens                                  26            65            74
B2   Hispanic                                           356         1,041         1,243
B2   Black or African American, non-Hispanic             25            58            68
B2   Native Hawaiian or other Pacific Islander, non-
     Hispanic                                            14            58           383
B2   Two or more races, non-Hispanic                     22            72            80
B2   TOTAL                                            1,510         5,909         9,085

B3   Number of degrees awarded from July 1, 2010 to June 30, 2011
"""


# UNC 2024-25: the table converts correctly, and the text layer wraps the
# longest label so its second line looks like the Hispanic row.
_PLAIN_TABLE = """
B2 Enrollment by Racial/Ethnic Category.

|  | Degree-Seeking First-Time First-Year | Degree-Seeking Undergraduates (include first-time first-year) | Total Undergraduates (both degree- and non-degree-seeking) |
|---|---|---|---|
| Nonresidents | 274 | 1,165 | 1,351 |
| Hispanic/Latino | 410 | 2,019 | 2,023 |
| Native Hawaiian or other Pacific Islander, non-Hispanic | 4 | 9 | 9 |
| TOTAL | 4,640 | 20,777 | 21,075 |

## B3 Number of degrees awarded by your institution
"""

_PLAIN_TEXT_LAYER = """
B2 Enrollment by Racial/Ethnic Category.
        Nonresidents                                         274        1,165        1,351
        Hispanic/Latino                                      410        2,019        2,023
        Native Hawaiian or other Pacific Islander, non-
        Hispanic                                               4            9            9
                                              TOTAL        4,640       20,777       21,075

B3 Number of degrees awarded by your institution
"""


# Lines that end open but are not the first half of a row label.
_WRAPPED_COLUMN_TITLE = """
B2 Enrollment by Racial/Ethnic Category.
        Total Undergraduates (both degree- and non-
        Nonresidents                                         274        1,165        1,351
        Hispanic/Latino                                      410        2,019        2,023
        Total                                              4,640       20,777       21,075

B3 Number of degrees awarded by your institution
"""

_WRAPPED_INSTRUCTION = """
B2 Enrollment by Racial/Ethnic Category.
        Hispanic/Latino line, not under any race, and
        Nonresidents                                         274        1,165        1,351
        Hispanic/Latino                                      410        2,019        2,023

B3 Number of degrees awarded by your institution
"""


class Tier4CleanerB2RowTagsTest(unittest.TestCase):
    def assert_b2(self, values):
        expected = {
            "B.201": "26", "B.211": "65", "B.221": "74",
            "B.202": "356", "B.212": "1041", "B.222": "1243",
            "B.203": "25", "B.213": "58", "B.223": "68",
            "B.207": "14", "B.217": "58", "B.227": "383",
            "B.210": "1510", "B.220": "5909", "B.230": "9085",
        }
        for qn, value in expected.items():
            self.assertEqual(values[qn]["value"], value, qn)

    def test_table_rows_that_start_with_the_question_tag(self):
        self.assert_b2(clean(_TABLE))

    def test_text_layer_rows_with_tag_and_a_wrapped_label(self):
        values = clean("", supplemental_text=_TEXT_LAYER)

        self.assert_b2(values)
        self.assertEqual(values["B.208"]["value"], "22")

    def test_table_and_text_layer_together(self):
        self.assert_b2(clean(_TABLE, supplemental_text=_TEXT_LAYER))

    def test_wrapped_label_does_not_replace_the_hispanic_row(self):
        values = clean(_PLAIN_TABLE, supplemental_text=_PLAIN_TEXT_LAYER)

        self.assertEqual(values["B.202"]["value"], "410")
        self.assertEqual(values["B.212"]["value"], "2019")
        self.assertEqual(values["B.222"]["value"], "2023")
        self.assertEqual(values["B.207"]["value"], "4")
        self.assertEqual(values["B.217"]["value"], "9")
        self.assertEqual(values["B.227"]["value"], "9")

    def test_wrapped_column_title_does_not_capture_the_next_row(self):
        values = clean("", supplemental_text=_WRAPPED_COLUMN_TITLE)

        self.assertEqual(values["B.201"]["value"], "274")
        self.assertEqual(values["B.211"]["value"], "1165")
        self.assertEqual(values["B.210"]["value"], "4640")
        self.assertEqual(values["B.220"]["value"], "20777")
        self.assertEqual(values["B.230"]["value"], "21075")

    def test_wrapped_instruction_line_does_not_capture_the_next_row(self):
        values = clean("", supplemental_text=_WRAPPED_INSTRUCTION)

        self.assertEqual(values["B.201"]["value"], "274")
        self.assertEqual(values["B.202"]["value"], "410")
        self.assertEqual(values["B.212"]["value"], "2019")
        self.assertEqual(values["B.222"]["value"], "2023")

    def test_tag_is_removed_from_labels_and_reported(self):
        table = _parse_markdown_tables(_TABLE)[0]

        self.assertEqual(table["question_tag"], "B2")
        self.assertEqual(table["rows"][0]["label"], "Nonresident aliens")
        self.assertEqual(table["rows"][-1]["label"], "TOTAL")

    def test_labels_that_only_sometimes_start_with_a_tag_are_kept(self):
        mixed = [
            "| C1 applicants | 10 |",
            "|---|---|",
            "| C2 wait list | 5 |",
            "| C1 admits | 4 |",
        ]
        two_rows = ["| B2 Hispanic | 1 |", "|---|---|", "| B2 TOTAL | 2 |"]
        partial = ["| B2 Hispanic | 1 |", "|---|---|", "| White | 2 |", "| B2 TOTAL | 3 |"]

        for lines in (mixed, two_rows, partial):
            self.assertEqual(_strip_fused_question_tag(lines), (lines, None))


if __name__ == "__main__":
    unittest.main()
