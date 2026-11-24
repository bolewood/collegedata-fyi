"""Five layouts that cleaner 0.3.39 to 0.3.42 read wrongly where 0.3.38 read
them rightly (issue #450). The first test of each class is cut from the
document that showed it; the others pin what the fix must not change.
"""
from __future__ import annotations

import unittest

from tier4_cleaner import _h_row_window, clean

SEXES = ("Men", "Women", "Another Gender")


def _header(banner: str) -> str:
    cells = [""] + [
        f"{sex} - {load} Time Enrollment - {banner}" for sex in SEXES for load in ("Full", "Part")
    ]
    return "| " + " | ".join(cells) + " |\n|" + "---|" * len(cells) + "\n"


def _row(label: str, *cells: str) -> str:
    return "| " + " | ".join((label,) + cells) + " |\n"


def _undergraduates(first_year: tuple[str, ...], other: tuple[str, ...], rest: tuple[str, ...],
                    degree: tuple[str, ...], credit: tuple[str, ...], total: tuple[str, ...]) -> str:
    return (
        _header("UNDERGRADUATE STUDENTS")
        + _row("Degree-seeking, first-time, first-year students", *first_year)
        + _row("Other first-year, degree-seeking students", *other)
        + _row("All other degree-seeking undergraduate students", *rest)
        + _row("Total degree-seeking undergraduate students", *degree)
        + _row("All other undergraduates enrolled in credit courses", *credit)
        + _row("Total Undergraduate Students", *total)
    )


# One file, two campuses' forms one after the other. The first is the school
# the document is filed under. The second prints an "Another Gender" count
# where the first leaves the cell blank.
_FIRST_CAMPUS = _undergraduates(
    ("4,708", "10", "4,882", "11", "", ""),
    ("343", "4", "266", "14", "", ""),
    ("13,436", "422", "13,370", "338", "", ""),
    ("18,487", "436", "18,518", "363", "", ""),
    ("68", "82", "52", "81", "", ""),
    ("18,555", "518", "18,570", "444", "", ""),
)
_SECOND_CAMPUS = _undergraduates(
    ("209", "23", "426", "26", "1", ""),
    ("81", "29", "115", "54", "", ""),
    ("579", "273", "950", "405", "", ""),
    ("869", "325", "1,491", "485", "1", ""),
    ("14", "123", "6", "219", "", ""),
    ("883", "448", "1,497", "704", "1", ""),
)
_TWO_FORMS = (
    "## B1. Institutional Enrollment\n\n" + _FIRST_CAMPUS
    + "\n## B2. Enrollment by Racial/Ethnic Category\n\nNot reported.\n\n"
    + "## B1. Institutional Enrollment\n\n" + _SECOND_CAMPUS
    + "\n## B2. Enrollment by Racial/Ethnic Category\n"
)


class SecondFormInOneFileTest(unittest.TestCase):
    """Indiana University 2024-25: seven campuses in one PDF."""

    def test_b1_is_read_from_the_first_form(self):
        for year in ("2023-24", "2024-25"):
            with self.subTest(year=year):
                values = clean(_TWO_FORMS, canonical_year=year)
                got = {qn: str(rec["value"]) for qn, rec in values.items()}
                # Full-time men, full-time women, part-time men, part-time women.
                self.assertEqual((got["B.101"], got["B.102"]), ("4708", "4882"))
                self.assertEqual((got["B.113"], got["B.114"]), ("18487", "18518"))
                self.assertEqual((got["B.121"], got["B.122"]), ("18555", "18570"))
                self.assertNotIn("209", got.values())
                self.assertNotIn("883", got.values())

    def test_a_cell_only_the_second_form_fills_stays_empty(self):
        values = clean(_TWO_FORMS, canonical_year="2023-24")
        # First-time, first-year, full-time, another gender.
        self.assertNotIn("B.103", values)

    def test_the_same_table_printed_again_is_read(self):
        # The first copy is cut before its total rows; the reprint is whole.
        cut = "".join(_FIRST_CAMPUS.splitlines(keepends=True)[:5])
        twice = (
            "## B1. Institutional Enrollment\n\n" + cut + "\n" + _FIRST_CAMPUS
            + "\n## B2. Enrollment by Racial/Ethnic Category\n"
        )
        values = clean(twice, canonical_year="2023-24")
        got = {qn: str(rec["value"]) for qn, rec in values.items()}
        self.assertEqual((got["B.101"], got["B.102"]), ("4708", "4882"))
        self.assertEqual((got["B.113"], got["B.114"]), ("18487", "18518"))
        self.assertEqual((got["B.121"], got["B.122"]), ("18555", "18570"))

    def test_a_first_copy_that_does_not_add_up_does_not_block_the_reprint(self):
        garbled = _FIRST_CAMPUS.replace("| 13,370 |", "| 1,370 |")
        twice = (
            "## B1. Institutional Enrollment\n\n" + garbled + "\n" + _FIRST_CAMPUS
            + "\n## B2. Enrollment by Racial/Ethnic Category\n"
        )
        values = clean(twice, canonical_year="2023-24")
        got = {qn: str(rec["value"]) for qn, rec in values.items()}
        self.assertEqual((got["B.101"], got["B.102"]), ("4708", "4882"))
        self.assertEqual((got["B.113"], got["B.114"]), ("18487", "18518"))

    def test_one_form_alone_is_still_read(self):
        alone = "## B1. Institutional Enrollment\n\n" + _SECOND_CAMPUS + "\n## B2. Enrollment by Racial/Ethnic Category\n"
        values = clean(alone, canonical_year="2023-24")
        self.assertEqual(str(values["B.101"]["value"]), "209")
        self.assertEqual(str(values["B.103"]["value"]), "1")


# The H2 heading closes one page; the table opens the next, under the page's
# section banner.
_H2_AFTER_A_PAGE_BREAK = """\
                                                                                 H. FINANCIAL AID

H2     Number of Enrolled Students Awarded Aid: List the number of degree-seeking full-time and less-than-full-time
       undergraduates who applied for and were awarded financial aid from any source.

CDS Tab H

                                                                                      Rice University
                                                                            Common Data Set 2025 - 2026

                                                                                 H. FINANCIAL AID

                                                                            First-time Full-                                              Less Than
             Number of Enrolled Students Awarded Aid                        time First-year        Full-time Undergrad                     Full-time
                                                                                Students              (Incl. First-Year)                 Undergrad

       A   Number of degree-seeking undergraduate
           students (CDS Item B1 if reporting on Fall 2025                         1263                          4793
           cohort)
       B   Number of students in line a who applied for                             979                          3325
           need-based financial aid
       C   Number of students in line b    who were                                 571                          2145
           determined to have financial need
       D   Number of students in line c who were awarded                            570                          2133
           any financial aid
       E   Number of students in line d    who were awarded                         561                          2113
           any need-based scholarship or grant aid
       F   Number of students in line d    who were awarded                         273                          1260
           any need-based self-help aid
       G   Number of students in line d    who were awarded                         66                            214
           any non-need-based scholarship or grant aid
       H   Number of students in line d    whose need was
           fully met (exclude PLUS loans, unsubsidized                              568                          2130
           loans, and private alternative loans)
       I   On average, the percentage of need that was
           met of students who were awarded any need-
           based aid. Exclude any aid that was awarded in
           excess of need as well as any resources that                          100.0%                     100.0%
           were awarded to replace EFC (PLUS loans,
           unsubsidized loans, and private alternative
           loans)
       J   The average financial aid package of those in
           line d. Exclude any resources that were
           awarded to replace EFC (PLUS loans,                                  $   75,643                 $   73,489
           unsubsidized loans, and private alternative
           loans)
       K   Average need-based scholarship and grant                             $   73,663                 $   69,521
           award of those in line e
       L   Average need-based self-help award (excluding
           PLUS loans, unsubsidized loans, and private                          $   2,552                   $   2,636
           alternative loans) of those in line f
       M   Average need-based loan (excluding PLUS
           loans, unsubsidized loans, and private                               $   3,015                   $   4,099
           alternative loans) of those in line f who were
           awarded a need-based loan


H2A    Number of Enrolled Students Awarded Non-need-based Scholarships and Grants: List the number of degree-
       seeking full-time and less-than-full-time undergraduates who had no financial need.
"""


class SectionBannerIsNotRowHTest(unittest.TestCase):
    """Rice 2025-26 and Tennessee Tech 2024-25."""

    def test_row_h_window_starts_at_row_h(self):
        window = _h_row_window(_H2_AFTER_A_PAGE_BREAK, "H")
        self.assertTrue(window.lstrip().startswith("H   Number of students in line d"))
        self.assertNotIn("FINANCIAL AID", window)
        self.assertNotIn("4,099", window)

    def test_need_fully_met_is_not_the_loan_averages(self):
        values = clean("", supplemental_text=_H2_AFTER_A_PAGE_BREAK, canonical_year="2025-26")
        self.assertEqual((values["H.208"]["value"], values["H.221"]["value"]), ("568", "2130"))
        self.assertNotIn("H.234", values)
        # The rows whose amounts row H used to take are still read.
        self.assertEqual((values["H.213"]["value"], values["H.226"]["value"]), ("3015", "4099"))

    def test_a_row_label_in_capitals_is_a_row(self):
        capitals = "H. NUMBER OF STUDENTS IN LINE D WHOSE NEED WAS FULLY MET\n      568      2130      90\nI. NEXT ROW\n"
        self.assertTrue(_h_row_window(capitals, "H").startswith("H. NUMBER OF STUDENTS"))
        self.assertTrue(_h_row_window("A. NUMBER OF DEGREE-SEEKING STUDENTS\n  10  20\n", "A").startswith("A. NUMBER"))

    def test_a_title_case_banner_is_not_row_h(self):
        titled = _H2_AFTER_A_PAGE_BREAK.replace("H. FINANCIAL AID", "H. Financial Aid")
        self.assertTrue(_h_row_window(titled, "H").lstrip().startswith("H   Number of students in line d"))

    def test_a_dotted_row_h_is_still_a_row(self):
        dotted = "H. Number of students in line d whose need was fully met      109      396      8\nI. Next row\n"
        self.assertTrue(_h_row_window(dotted, "H").startswith("H. Number of students"))


_GRADUATION_HEADER = (
    "|  | Recipients of a Federal Pell Grant | Recipients of a Subsidized Stafford Loan who did not receive a Pell Grant "
    "| Students who did not receive either a Pell Grant or a subsidized Stafford Loan | Total (sum of 3 columns to the left) |\n"
    "|---|---|---|---|---|\n"
)
# Docling moved the end of row B's label into row C's cell in the first
# table, and pushed each label one row down in the second.
_GRADUATION = (
    "## B4-B21. Graduation Rates\n\n## For Bachelor's or Equivalent Programs Fall 2019 Cohort\n\n"
    + _GRADUATION_HEADER
    + "| A. Initial 2019 cohort of first-time, full-time, bachelor's (or equivalent) degree-seeking undergraduate students | 528 | 498 | 2,130 | 3,156 |\n"
    "| B. Of the initial 2019 cohort, how many did not persist and did not graduate for the following reasons: • Deceased • Permanently Disabled • Armed Forces | 0 | 1 | 11 | 12 |\n"
    "| • Report Total Allowable Exclusions C. Final 2019 cohort, after adjusting for allowable exclusions | 528 | 497 | 2,119 | 3,144 |\n"
    "| D. Of the initial 2019 cohort, how many completed the program in four years or less (by Aug. 31, 2023) | 435 | 417 | 1,714 | 2,566 |\n"
    "| E. Of the initial 2019 cohort, how many completed the program in more than four years but in five years or less (after Aug. 31, 2023 and by Aug. 31, 2024) | 47 | 25 | 136 | 208 |\n"
    "| F. Of the initial 2019 cohort, how many completed the program in more than five years but in six years or less (after Aug. 31, 2024 and by Aug. 31, 2025) | 3 | 5 | 33 | 41 |\n"
    "| G. Total graduating within six years (sum of lines D, E, and F) | 485 | 447 | 1,883 | 2,815 |\n"
    "| H. Six-year graduation rate for 2019 cohort (G divided by C) | 92% | 90% | 89% | 90% |\n"
    "\n## Fall 2018 Cohort\n\n"
    + _GRADUATION_HEADER
    + "| A. Initial 2018 cohort of first-time, full-time, bachelor's (or equivalent) degree-seeking undergraduate students | 629 | 597 | 2,385 | 3,611 |\n"
    "| B. Of the initial 2018 cohort, how many did not persist and did not graduate for the following reasons: • Deceased • Permanently Disabled • Armed Forces | 2 | 0 | 10 | 12 |\n"
    "| C. Final 2018 cohort, after adjusting for allowable exclusions D. Of the initial 2018 cohort, how many completed the | 627 | 597 | 2,375 | 3,599 |\n"
    "| program in four years or less (by Aug. 31, 2022) E. Of the initial 2018 cohort, how many completed the | 516 | 509 | 1,884 | 2,909 |\n"
    "| program in more than four years but in five years or | 31 | 22 | 172 | 225 |\n"
    "| less (after Aug. 31, 2022 and by Aug. 31, 2023) F. Of the initial 2018 cohort, how many completed the program in more than five years but in six years or less (after | 11 | 5 | 41 | 57 |\n"
    "| G. Total graduating within six years (sum of lines D, E, and | 558 | 536 | 2,097 | 3,191 |\n"
    "| H. Six-year graduation rate for 2018 cohort (G divided by C) | 89% | 90% | 88% | 89% |\n"
    "\n## B22. Retention Rates\n"
)


class GraduationRowWithoutItsLetterTest(unittest.TestCase):
    """Boston University 2025-26."""

    def setUp(self):
        self.values = clean(_GRADUATION, canonical_year="2025-26")

    def _row(self, first: int) -> list[str | None]:
        return [
            str(self.values[qn]["value"]) if (qn := f"B.{first + i}") in self.values else None for i in range(4)
        ]

    def test_lettered_rows(self):
        self.assertEqual(self._row(401), ["528", "498", "2130", "3156"])
        self.assertEqual(self._row(413), ["435", "417", "1714", "2566"])

    def test_final_cohort_row_keeps_its_four_columns(self):
        self.assertEqual(self._row(409), ["528", "497", "2119", "3144"])

    def test_rows_of_the_previous_cohort_without_a_letter(self):
        self.assertEqual(self._row(509), ["627", "597", "2375", "3599"])   # C
        # The row labelled with the end of E and the start of F is F. (Rows
        # D and E, whose labels name no row of their own, are not read.)
        self.assertEqual(self._row(521), ["11", "5", "41", "57"])


class UnsplitGraduationTableTest(unittest.TestCase):
    def test_a_blank_first_cell_is_a_blank_in_a_table_that_was_not_split(self):
        # Letters without a full stop are not split from their labels, so a
        # row with no letter and an empty first cell has a blank, not a
        # description cell. The table carries a fifth, trailing column.
        table = (
            "## B4-B21. Graduation Rates\n\n## Fall 2019 Cohort\n\n"
            + _GRADUATION_HEADER.replace(" |\n|---|---|---|---|---|\n", " | Notes |\n|---|---|---|---|---|---|\n")
            + "| A Initial 2019 cohort of first-time, full-time, bachelor's (or equivalent) degree-seeking undergraduate students | 528 | 498 | 2,130 | 3,156 | |\n"
            "| B Of the initial 2019 cohort, how many did not persist and did not graduate | 0 | 1 | 11 | 12 | |\n"
            "| Final 2019 cohort, after adjusting for allowable exclusions | | 497 | 2,119 | 3,144 | |\n"
            "\n## B22. Retention Rates\n"
        )
        values = clean(table, canonical_year="2025-26")
        self.assertNotIn("B.409", values)
        self.assertEqual([str(values[qn]["value"]) for qn in ("B.410", "B.411", "B.412")], ["497", "2119", "3144"])


_B2 = """\
B2. Enrollment by Racial/Ethnic Category
Provide numbers of undergraduate students for each of the following categories as of the institution's official fall reporting date.
                                                                          Degree-seeking                Degree-seeking              Total Undergraduates
Nonresidents                                                                          152                             808                           C or t
Hispanic/Latino                                                                       480                           1,541                               C or t
Black or African American, non-Hispanic                                       298                           1,111                               C or t
White, non-Hispanic                                                                      3,345                               12,    818                              C or t
Asian, non-Hispanic                                                                       991                           3,240                               C or t
Race and/or ethnicity unknown                                                       281                             631                               C or t
Total                                                                                 5,876                               21,    222                              C or t
  B3. Number of degrees awarded
"""


class NumberPrintedWithAGapTest(unittest.TestCase):
    """University of Pittsburgh 2025-26."""

    def test_a_gap_after_the_comma_does_not_make_two_cells(self):
        values = clean("", supplemental_text=_B2, canonical_year="2025-26")
        for qn in ("B.214", "B.224", "B.220", "B.230"):
            self.assertNotIn(qn, values)

    def test_three_columns_with_one_number_broken_are_read(self):
        three = _B2.replace("C or t", "").replace("12,    818 ", "12,    818      13,902").replace(
            "21,    222 ", "21,    222      23,450"
        )
        values = clean("", supplemental_text=three, canonical_year="2025-26")
        self.assertEqual([values[qn]["value"] for qn in ("B.204", "B.214", "B.224")], ["3345", "12818", "13902"])
        self.assertEqual([values[qn]["value"] for qn in ("B.210", "B.220", "B.230")], ["5876", "21222", "23450"])


_TOTALS_MARKDOWN = (
    "## B1 Institutional Enrollment\n\n"
    "| All Students: Total | Males | Females | Unknown |\n|---|---|---|---|\n"
    "| Total Full-Time Students | 8,602 | 9,954 | 0 |\n"
    "| Total Part-Time Students | 4,966 | 6,309 | 0 |\n"
    "| Total All students | 13,568 | 16,263 | 0 |\n\n"
    "Total all undergraduates\n\nTotal all graduate\n\nGRAND TOTAL ALL\n\nSTUDENTS\n\n{numbers}\n\n"
    "## B2 Enrollment by Racial/Ethnic Category.\n"
)
_TOTALS_LAYOUT = """\
B1        Institutional Enrollment - Men and Women
          All Students: Total                    Males          Females           Unknown
          Total Full-Time                            8,602            9,954                     0
          Students
          Total Part-Time                            4,966            6,309                     0
          Students
          Total All students                       13,568            16,263                     0

          Total all undergraduates                 26,629
          Total all graduate                         3,202
          GRAND TOTAL ALL                          29,831
          STUDENTS
B2        Enrollment by Racial/Ethnic Category.
"""


class GrandTotalKeptFromMarkdownTest(unittest.TestCase):
    """Utah State 2025-26: the markdown prints the three total labels, then
    two of the three numbers."""

    def _totals(self, numbers: str) -> dict[str, str]:
        values = clean(
            _TOTALS_MARKDOWN.format(numbers=numbers), supplemental_text=_TOTALS_LAYOUT, canonical_year="2025-26"
        )
        return {qn: str(values[qn]["value"]) for qn in ("B.176", "B.177", "B.178") if qn in values}

    def test_the_undergraduate_total_is_not_kept_as_the_grand_total(self):
        got = self._totals("26,629\n\n29,831")
        self.assertEqual(got, {"B.176": "26629", "B.177": "3202"})

    def test_a_grand_total_only_the_markdown_reads_is_kept(self):
        # Each total on its label's line; the text layer has lost the grand
        # total and misreads the graduate one.
        markdown = _TOTALS_MARKDOWN.replace(
            "Total all undergraduates\n\nTotal all graduate\n\nGRAND TOTAL ALL\n\nSTUDENTS\n\n{numbers}",
            "Total all undergraduates 26,629\n\nTotal all graduate 3,202\n\nGRAND TOTAL ALL STUDENTS 29,831",
        )
        layout = _TOTALS_LAYOUT.replace("3,202", "3,302").replace(
            "          GRAND TOTAL ALL                          29,831\n          STUDENTS\n", ""
        )
        values = clean(markdown, supplemental_text=layout, canonical_year="2025-26")
        self.assertEqual(str(values["B.178"]["value"]), "29831")


if __name__ == "__main__":
    unittest.main()
