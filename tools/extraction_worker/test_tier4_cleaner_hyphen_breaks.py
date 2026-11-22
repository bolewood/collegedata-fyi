from __future__ import annotations

import unittest

from tier4_cleaner import _join_hyphen_breaks, clean

# Bluefield State 2012-13: the text layer has a space after each hyphen, and
# Docling's table for C1 came out with labels only.
_TEXT_LAYER = """
C1. First-time, first-year (freshman) students: Provide the number of degree  -seeking, first-time, first- year students who
     applied, were admitted, and enrolled (full- or part-time) in Fall  2012.

     Total first- time, first- year (freshman) men who applied                      __394__
     Total first- time, first- year (freshman) women who applied                 __632__

     Total first- time, first- year (freshman) men who were admitted           __178__
     Total first- time, first- year (freshman) women who were admitted        __302__

     Total full-  time, first- time, first- year (freshman) men who enrolled     __111__
     Total part- time, first- time, first- year (freshman) men who enrolled    __2    ____

     Total full-  time, first- time, first- year (freshman) women who enrolled __184__
     Total part- time, first- time, first- year (freshman) women who enrolled __5    ____

C2. Freshman wait-listed students (students who met admission requirements but whose final admission was
     contingent on space availability)
"""


class Tier4CleanerHyphenBreaksTest(unittest.TestCase):
    def test_c1_rows_with_a_space_after_each_hyphen(self):
        values = clean("", supplemental_text=_TEXT_LAYER, canonical_year="2012-13")

        expected = {
            "C.101": "394", "C.102": "632",
            "C.104": "178", "C.105": "302",
            "C.110": "111", "C.111": "2",
            "C.112": "184", "C.113": "5",
        }
        for qn, value in expected.items():
            self.assertEqual(values[qn]["value"], value, qn)

    def test_join_keeps_the_value_in_its_column(self):
        line = "     Total full-  time, first- time, first- year (freshman) men who enrolled     __111__"

        joined = _join_hyphen_breaks(line)

        self.assertIn("full-time, first-time, first-year (freshman) men", joined)
        self.assertEqual(len(joined), len(line))
        self.assertEqual(joined.index("__111__"), line.index("__111__"))

    def test_two_labels_on_one_line_each_keep_their_value_column(self):
        line = "Full- time   120      Part- time    30"

        joined = _join_hyphen_breaks(line)

        self.assertEqual(joined, "Full-time    120      Part-time     30")
        self.assertEqual(joined.index("120"), line.index("120"))
        self.assertEqual(joined.index("30"), line.index("30"))

    def test_line_without_a_gap_gets_shorter(self):
        self.assertEqual(_join_hyphen_breaks("Total first- time men 394"), "Total first-time men 394")

    def test_other_hyphens_are_left_alone(self):
        for line in (
            "Degree- seeking students who applied  12",
            "first- generation students  40",
            "Pre- time and post- year notes",
            "full-time, first-time, first-year men who enrolled  111",
        ):
            self.assertEqual(_join_hyphen_breaks(line), line)


if __name__ == "__main__":
    unittest.main()
