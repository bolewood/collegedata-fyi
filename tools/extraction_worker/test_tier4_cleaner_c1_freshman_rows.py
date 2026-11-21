from __future__ import annotations

import unittest

from tier4_cleaner import _is_c1_residency_header, clean

# The C1 block of a 2004-05 file whose table Docling flattened into running
# text. The text layer keeps one row per line.
PROSE_MARKDOWN = """## C. FIRST-TIME, FIRST-YEAR (FRESHMAN) ADMISSION

- C1. First-time, first-year (freshman) students: Provide the number of degree-seeking, first-time, first-year students who applied, were admitted, and enrolled (full- or part-time) in fall 2003.

Total first-time, first-year (freshman) men who applied 1564 Total first-time, first-year (freshman) women who applied 2116 3,680 total

- C2. Freshman wait-listed students
"""

LAYOUT_ROWS = """C1.  First-time, first-year (freshman) students: Provide the number of degree-seeking, first-time, first-year students who
     applied, were admitted, and enrolled (full- or part-time) in fall 2003.

     Total first-time, first-year (freshman) men who applied                        1564
     Total first-time, first-year (freshman) women who applied                    2116          3,680 total

      Total first-time, first-year (freshman) men who were admitted                452
      Total first-time, first-year (freshman) women who were admitted            481           933 total (25% of Apps)

      Total full-time, first-time, first-year (freshman) men who enrolled           177
      Total part-time, first-time, first-year (freshman) men who enrolled            0

      Total full-time, first-time, first-year (freshman) women who enrolled       189     366 total (39% of Admits)
      Total part-time, first-time, first-year (freshman) women who enrolled         0

C2.  Freshman wait-listed students
"""

# G1's tuition rows followed by H1's instruction, as in the same file.
TUITION_THEN_H1 = """| PUBLIC INSTITUTIONS              |                  |
|----------------------------------|------------------|
| In-district:                     |                  |
| In-state (out-of-district):      |                  |
| Out-of-state:                    |                  |
| NONRESIDENT ALIENS:              |                  |

## Aid Awarded to Enrolled Undergraduates

H1. Enter total dollar amounts awarded to enrolled full-time and less than full-time degree-seeking undergraduates. (Note: If the data being reported are final figures for the 2003-2004 academic year (see the next item below), use the 2003-2004 academic year's CDS Question B1 cohort.)
"""

RESIDENCY_FIELDS = ("C.119", "C.120", "C.121", "C.122", "C.123", "C.124", "C.125",
                    "C.126", "C.127", "C.128", "C.129", "C.130")


def _values(result: dict[str, dict], *question_numbers: str) -> dict[str, str | None]:
    return {qn: result.get(qn, {}).get("value") for qn in question_numbers}


class FreshmanRowLabelTest(unittest.TestCase):
    def test_rows_labelled_freshman_are_read_from_the_text_layer(self):
        result = clean(PROSE_MARKDOWN, supplemental_text=LAYOUT_ROWS, canonical_year="2004-05")

        self.assertEqual(
            _values(result, "C.101", "C.102", "C.104", "C.105", "C.110", "C.111", "C.112", "C.113"),
            {"C.101": "1564", "C.102": "2116", "C.104": "452", "C.105": "481",
             "C.110": "177", "C.111": "0", "C.112": "189", "C.113": "0"},
        )

    def test_totals_are_the_sum_of_the_rows(self):
        result = clean(PROSE_MARKDOWN, supplemental_text=LAYOUT_ROWS, canonical_year="2004-05")

        self.assertEqual(
            _values(result, "C.116", "C.117", "C.118"),
            {"C.116": "3680", "C.117": "933", "C.118": "366"},
        )

    def test_rows_without_the_parenthetical_still_read(self):
        layout = LAYOUT_ROWS.replace(" (freshman)", "")

        result = clean(PROSE_MARKDOWN, supplemental_text=layout, canonical_year="2004-05")

        self.assertEqual(_values(result, "C.101", "C.105"), {"C.101": "1564", "C.105": "481"})

    def test_value_printed_before_its_label(self):
        layout = """C1      Total first-time, first-year (freshman) men who applied                                 9654
C1                                                                        10649Total first-time, first-year (freshman) women who applied

C1                                                                         4145Total first-time, first-year (freshman) men who were admitted
C1                                                                         4666Total first-time, first-year (freshman) women who were admitted
"""

        result = clean("", supplemental_text=layout, canonical_year="2019-20")

        self.assertEqual(
            _values(result, "C.101", "C.102", "C.104", "C.105", "C.116", "C.117"),
            {"C.101": "9654", "C.102": "10649", "C.104": "4145", "C.105": "4666",
             "C.116": "20303", "C.117": "8811"},
        )

    def test_number_that_is_not_alone_before_the_label_is_not_its_value(self):
        for prefix in ("Fall 2019 ", "CDS 2019-20", "B1 Degree-seeking men 345   "):
            layout = (
                f"{prefix}Total first-time, first-year (freshman) men who applied\n"
                "1564\n"
                "Total first-time, first-year (freshman) women who applied     2116\n"
            )

            result = clean("", supplemental_text=layout, canonical_year="2019-20")

            with self.subTest(prefix=prefix):
                self.assertEqual(
                    _values(result, "C.101", "C.102", "C.116"),
                    {"C.101": None, "C.102": "2116", "C.116": None},
                )

    def test_margin_tag_before_a_blank_row_is_not_its_value(self):
        layout = """C1                                                               317Total full-time, first-time, first-year (freshman) men who enrolled
C1     Total part-time, first-time, first-year (freshman) men who enrolled

C1                                                               521Total full-time, first-time, first-year (freshman) women who enrolled
C1     Total part-time, first-time, first-year (freshman) women who enrolled
"""

        result = clean("", supplemental_text=layout, canonical_year="2008-09")

        self.assertEqual(
            _values(result, "C.110", "C.111", "C.112", "C.113", "C.118"),
            {"C.110": "317", "C.111": None, "C.112": "521", "C.113": None, "C.118": "838"},
        )


class ResidencyBlockBoundsTest(unittest.TestCase):
    def test_tuition_row_is_not_a_residency_header(self):
        self.assertFalse(_is_c1_residency_header("in state out of district"))
        self.assertTrue(_is_c1_residency_header("total in state out of state international unknown"))

    def test_instruction_after_tuition_rows_is_not_a_c1_row(self):
        result = clean(TUITION_THEN_H1, canonical_year="2004-05")

        self.assertEqual(_values(result, *RESIDENCY_FIELDS), dict.fromkeys(RESIDENCY_FIELDS))

    def test_residency_table_ends_where_another_question_starts(self):
        layout = """                                             In-State   Out-of-State   International   Unknown   Total
Total first-time, first-year who applied        1,000        2,000           300          10      3,310
Total first-time, first-year who were admitted    500          600           100           5      1,205

H1. Enter total dollar amounts awarded to enrolled full-time and less than full-time degree-seeking undergraduates for the 2003-2004 academic year, or the 2003-2004 academic year's cohort, 2004.
"""

        result = clean("", supplemental_text=layout, canonical_year="2004-05")

        self.assertEqual(
            _values(result, "C.119", "C.122", "C.125", "C.128", "C.116"),
            {"C.119": "1000", "C.122": "2000", "C.125": "300", "C.128": "10", "C.116": "3310"},
        )
        # The school left the enrolled row out; H1's years are not it.
        enrolled = ("C.121", "C.124", "C.127", "C.130", "C.118")
        self.assertEqual(_values(result, *enrolled), dict.fromkeys(enrolled))

    def test_residency_table_ends_at_a_bare_question_tag(self):
        layout = """                                             In-State   Out-of-State   International   Unknown   Total
Total first-time, first-year who applied        1,000        2,000           300          10      3,310
C2
Degree-seeking students who enrolled from the 2003 list in 2004, 2005, 2006 and 2007.
"""

        result = clean("", supplemental_text=layout, canonical_year="2004-05")

        enrolled = ("C.121", "C.124", "C.127", "C.130", "C.118")
        self.assertEqual(_values(result, *enrolled), dict.fromkeys(enrolled))


if __name__ == "__main__":
    unittest.main()
