from __future__ import annotations

import unittest
from pathlib import Path

from tier4_cleaner import (
    SchemaIndex,
    _extract_i2_ratio_fields,
    _parse_markdown_tables,
    _remove_fill_in_blanks,
    clean,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
SCHEMA = SchemaIndex(REPO_ROOT / "schemas" / "cds_schema_2025_26.json")


class RemoveFillInBlanksTest(unittest.TestCase):
    def test_rule_wrapped_around_an_answer_is_removed(self):
        self.assertEqual(
            _remove_fill_in_blanks("| men who applied | ___2,446___ |").split("|")[2].strip(),
            "2,446",
        )
        self.assertEqual(_remove_fill_in_blanks("__1 year_____").strip(), "1 year")

    def test_left_rule_may_sit_one_space_from_the_answer(self):
        self.assertEqual(_remove_fill_in_blanks("plan ____ 141______").split(), ["plan", "141"])
        self.assertEqual(
            _remove_fill_in_blanks("closing date ___ Nov 15__").split(),
            ["closing", "date", "Nov", "15"],
        )

    def test_escaped_underscores_from_running_text(self):
        text = r"undergraduates: \_17,488\_\_\_\_ graduate: \_\_\_987\_\_\_\_\_ all: \_\_\_\_1524"

        self.assertEqual(
            _remove_fill_in_blanks(text).split(),
            ["undergraduates:", "17,488", "graduate:", "987", "all:", "1524"],
        )

    def test_number_between_two_single_underscores(self):
        self.assertEqual(
            _remove_fill_in_blanks(r"Bachelor's degrees \_364\_ Post").split(),
            ["Bachelor's", "degrees", "364", "Post"],
        )

    def test_unanswered_blank_stays(self):
        for text in (
            "| Percent of men who join fraternities | _____ | _____ |",
            r"maximum period of postponement: \_\_\_\_\_\_\_",
            r"\_\_\_ Yes, in full \_\_\_ Yes, in part \_\_\_\_ No",
            r"Deadline: \_\_\_\_\_\_\_ No deadline",
            # Attached to a label, not to an answer.
            r"Amount of housing deposit:\_\_\_\_\_\_\_ 7/15",
            r"maximum period of postponement:\_\_\_\_\_\_\_",
            r"Prior to admission\_\_\_\_After admission\_\_\_\_",
            r"\_\_\_\_Yes \_\_\_\_No",
            "| Other (specify):____ | ____Yes |",
        ):
            self.assertEqual(_remove_fill_in_blanks(text), text)

    def test_unanswered_blank_does_not_let_the_next_text_become_the_answer(self):
        markdown = r"""
C17. Deposit: Amount of housing deposit:\_\_\_\_\_\_\_ 7/15

C18. Deferred admission: If yes, maximum period of postponement:\_\_\_\_\_\_\_

Other: none
"""

        self.assertEqual(clean(markdown, schema=SCHEMA), {})

    def test_rule_beside_a_lone_x_is_removed(self):
        self.assertEqual(
            _remove_fill_in_blanks(r"\_\_X\_\_\_ Yes, in full \_\_\_\_ No").split()[:2],
            ["X", "Yes,"],
        )
        self.assertEqual(
            _remove_fill_in_blanks(r"X\_\_\_ Yes, in full").split(), ["X", "Yes,", "in", "full"]
        )

    def test_no_partial_run_is_left_behind(self):
        for text in (r"3/1\_\_\_\_Prior to admission", "___1___2___", r"7\_\_\_x"):
            out = _remove_fill_in_blanks(text)
            self.assertNotRegex(out, r"(?<![_\\])\\?_(?!\\?_)(?=[A-Za-z0-9])", msg=out)

    def test_underscores_inside_a_url_stay(self):
        for text in (
            "https://my.example.edu/ICS/Institutional_Effectiveness__Research/Common_Data_Set.jnz",
            r"http://ipa.example.edu/cds/cds\_toc.html",
        ):
            self.assertEqual(_remove_fill_in_blanks(text), text)

    def test_keep_width_preserves_column_positions(self):
        line = "C1   men who applied          ___2,446___    6,041 total"

        out = _remove_fill_in_blanks(line, keep_width=True)

        self.assertEqual(len(out), len(line))
        self.assertEqual(out.index("2,446"), line.index("2,446"))
        self.assertEqual(out.index("6,041"), line.index("6,041"))
        self.assertNotIn("_", out)

    def test_keep_width_with_escaped_leading_and_trailing_rules(self):
        for line in (
            r"GRAND TOTAL ALL STUDENTS: \_\_\_\_1524   next",
            r"Priority date: 3/1\_\_\_\_\_   next",
            r"Total: \_17,488\_\_\_\_   next",
            r"degrees \_364\_   next",
        ):
            out = _remove_fill_in_blanks(line, keep_width=True)
            self.assertEqual(len(out), len(line))
            self.assertEqual(out.index("next"), line.index("next"))
            self.assertNotIn("_", out)


class CleanWithFillInBlanksTest(unittest.TestCase):
    def test_c1_counts_typed_into_blanks_are_read(self):
        # Swarthmore 2010-11.
        markdown = """
C1. First-time, first-year (freshman) students: Provide the number of degree-seeking, first-time, first-year students who applied, were admitted, and enrolled (full- or part-time) in fall 2010.

| Total first-time, first-year (freshman) men who applied               | ___2,446___   |                             |
|-----------------------------------------------------------------------|---------------|-----------------------------|
| Total first-time, first-year (freshman) women who applied             | ___3,595___   | 6,041 total                 |
| Total first-time, first-year (freshman) men who were admitted         | ____460__     |                             |
| Total first-time, first-year (freshman) women who were admitted       | ____514___    | 974 total (16.1% of Apps)   |
"""

        values = clean(markdown, schema=SCHEMA)

        self.assertEqual(values["C.101"]["value"], "2446")
        self.assertEqual(values["C.102"]["value"], "3595")
        self.assertEqual(values["C.104"]["value"], "460")
        self.assertEqual(values["C.105"]["value"], "514")

    def test_empty_row_with_blank_rules_is_not_merged_into_the_next_row(self):
        markdown = """
| F1                                                 | First-time, first-year students | Undergraduates |
|----------------------------------------------------|---------------------------------|----------------|
| Percent of women who join sororities               | _____                           | _____          |
| Percent who live in college-owned housing          | 70.5%                           | 20.2%          |
"""

        (table,) = _parse_markdown_tables(_remove_fill_in_blanks(markdown))

        self.assertEqual(
            [row["label"] for row in table["rows"]],
            [
                "Percent of women who join sororities",
                "Percent who live in college-owned housing",
            ],
        )

    def test_out_of_state_row_is_not_read_as_the_nonresident_count(self):
        # Berklee 2020-21: the B2 counts are in parentheses and do not
        # parse, and F1's "exclude international/nonresident aliens" row
        # then supplied 90 (a percentage) as the nonresident count.
        markdown = """
| F1                                                                                                              | First-time, first-year (freshman) students | Undergraduates |
|-----------------------------------------------------------------------------------------------------------------|--------------------------------------------|----------------|
| Percent who are from out of state (exclude international/nonresident aliens from the numerator and denominator) | 90%                                        | 89%            |
| Percent of men who join fraternities                                                                            | 0%                                         | 0%             |
"""

        values = clean(markdown, schema=SCHEMA)

        self.assertNotIn("B.201", values)

    def test_nonresident_row_still_fills_the_nonresident_count(self):
        markdown = """
| B2                 | Degree-seeking First-time First-year | Degree-seeking Undergraduates | Total Undergraduates |
|--------------------|--------------------------------------|-------------------------------|----------------------|
| Nonresident aliens | 37                                   | 110                           | 111                  |
| Hispanic           | 49                                   | 170                           | 171                  |

| F1                                                                                                              | First-time, first-year (freshman) students | Undergraduates |
|-----------------------------------------------------------------------------------------------------------------|--------------------------------------------|----------------|
| Percent who are from out of state (exclude international/nonresident aliens from the numerator and denominator) | 87%                                        | 88%            |
"""

        values = clean(markdown, schema=SCHEMA)

        self.assertEqual(values["B.201"]["value"], "37")


class StudentFacultyRatioDecimalsTest(unittest.TestCase):
    def test_full_time_equivalent_counts_keep_their_whole_part(self):
        fields = _extract_i2_ratio_fields(
            "Fall 2010 Student to Faculty ratio: 8 to 1 (based on 1422.9 students and 180.5 faculty). "
            "NOTE: This ratio excludes 90 students and 1 faculty member engaged in study abroad."
        )

        self.assertEqual(fields["I.201"]["value"], "8")
        self.assertEqual(fields["I.202"]["value"], "1422.9")
        self.assertEqual(fields["I.203"]["value"], "180.5")

    def test_whole_number_counts_are_unchanged(self):
        fields = _extract_i2_ratio_fields(
            "Student to Faculty ratio: 12 to 1 (based on 3,915 students and 333 faculty)."
        )

        self.assertEqual(fields["I.202"]["value"], "3915")
        self.assertEqual(fields["I.203"]["value"], "333")


if __name__ == "__main__":
    unittest.main()
