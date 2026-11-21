from __future__ import annotations

import unittest

from tier4_cleaner import _parse_markdown_tables, _starts_its_own_row, clean


def _rows(markdown: str) -> list[tuple[str, list[str]]]:
    (table,) = _parse_markdown_tables(markdown)
    return [(row["label"], [v for v in row["values"] if v]) for row in table["rows"]]


# College of Southern Idaho 2017-18, B1: the school left "Other first-year,
# degree-seeking" empty.
B1_WITH_A_BLANK_ROW = """## B1

|                                     | FULL-TIME - Men | FULL-TIME - Women | PART-TIME - Men | PART-TIME - Women |
|-------------------------------------|-----------------|-------------------|-----------------|-------------------|
| Undergraduates                      |                 |                   |                 |                   |
| Degree-seeking, first-time freshmen | 298             | 309               | 106             | 159               |
| Other first-year, degree-seeking    |                 |                   |                 |                   |
| All other degree-seeking            | 512             | 768               | 478             | 1,066             |
| Total degree-seeking                | 810             | 1,077             | 584             | 1,225             |
"""


class BlankRowIsNotAWrappedLabelTest(unittest.TestCase):
    def test_blank_row_keeps_its_own_label(self):
        rows = dict(_rows(B1_WITH_A_BLANK_ROW))

        self.assertEqual(rows["Other first-year, degree-seeking"], [])
        self.assertEqual(rows["All other degree-seeking"], ["512", "768", "478", "1,066"])

    def test_blank_row_does_not_take_the_next_rows_numbers(self):
        result = clean(B1_WITH_A_BLANK_ROW, canonical_year="2017-18")

        self.assertNotIn("B.102", result)  # other first-year, men
        self.assertNotIn("B.127", result)  # other first-year, women
        self.assertEqual(result["B.103"]["value"], "512")
        self.assertEqual(result["B.128"]["value"], "768")

    def test_blank_race_row_above_the_total(self):
        rows = _rows(
            "| | Degree-seeking First-Time First Year | Degree-seeking Undergraduates |\n"
            "|---|---|---|\n"
            "| Native Hawaiian or other Pacific Islander, non-Hispanic | | |\n"
            "| Two or more races, non-Hispanic | 10 | 41 |\n"
            "| Race and/or ethnicity unknown | | |\n"
            "| TOTAL | 356 | 1,340 |\n"
        )

        self.assertEqual(
            rows,
            [
                ("Native Hawaiian or other Pacific Islander, non-Hispanic", []),
                ("Two or more races, non-Hispanic", ["10", "41"]),
                ("Race and/or ethnicity unknown", []),
                ("TOTAL", ["356", "1,340"]),
            ],
        )

    def test_question_tag_inside_the_label_cell(self):
        self.assertTrue(
            _starts_its_own_row("H1 Self-Help", "H1 Student loans from all sources (excluding parent loans)")
        )

    def test_two_form_lines_that_both_end_in_a_colon(self):
        self.assertTrue(_starts_its_own_row("Naval ROTC is offered:", "Air Force ROTC is offered:"))

    def test_cell_id_inside_the_label_cell(self):
        self.assertTrue(_starts_its_own_row("Total Self-Help", "H115 Parent Loans"))

    def test_question_that_ends_in_a_colon_above_one_that_does_not(self):
        self.assertTrue(
            _starts_its_own_row(
                "Number accepting a place on the waiting list:",
                "Number of wait-listed students admitted",
            )
        )

    def test_row_wording_from_an_earlier_years_form(self):
        self.assertTrue(_starts_its_own_row("Post-bachelors certificates:", "Masters degrees:"))


class WrappedLabelStillJoinsTest(unittest.TestCase):
    def test_label_split_between_two_words(self):
        rows = _rows(
            "| | Need-based | Non-need-based |\n"
            "|---|---|---|\n"
            "| Parent Loans | $30,731 | |\n"
            "| Athletic | | |\n"
            "| Awards | | $687,175 |\n"
        )

        self.assertEqual(rows[-1], ("Athletic Awards", ["$687,175"]))

    def test_heading_that_ends_in_a_colon(self):
        rows = _rows(
            "| | First-Year | Undergraduates |\n"
            "|---|---|---|\n"
            "| Tuition: | | |\n"
            "| In-district | $6,520 | $6,520 |\n"
        )

        self.assertEqual(rows, [("Tuition: In-district", ["$6,520", "$6,520"])])

    def test_continuation_in_lower_case_or_parentheses(self):
        self.assertFalse(_starts_its_own_row("Degree-seeking, first-time", "freshmen"))
        self.assertFalse(_starts_its_own_row("ROOM AND BOARD:", "(on-campus)"))

    def test_label_that_breaks_off_mid_phrase(self):
        self.assertFalse(
            _starts_its_own_row("Percent who live in college-owned, -operated, or", "Total housing")
        )
        self.assertFalse(
            _starts_its_own_row("Room and board total (if your college cannot provide separate room and", "Total")
        )

    def test_second_label_that_is_not_a_form_question(self):
        self.assertFalse(_starts_its_own_row("Institutional", "Scholarships awarded this year"))


if __name__ == "__main__":
    unittest.main()
