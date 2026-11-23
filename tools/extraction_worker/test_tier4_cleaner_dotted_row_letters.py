"""Forms that print the row letter with a full stop inside the label cell:
"A. Number of degree-seeking undergraduate students" (issue #433).

The lettered-row readers expect the letter alone, in its own cell or at the
start of a text line. In this layout H2, I1, H5 and the graduation-rate
tables were skipped whole.
"""
import unittest

from tier4_cleaner import (
    _b5_exclusions_by_column,
    _b5_rows_that_add_up,
    _parse_markdown_tables,
    _split_letter_description_column,
    clean,
)

_H2 = """## H2. Number of Enrolled Students Awarded Aid

|  | Full-Time, First-Time, First-Year | Full-Time Undergrad. (Include Freshman) | Less Than Full-Time Undergrad. |
|---|---|---|---|
| A. Number of degree-seeking undergraduate students (CDS Item B1 if reporting on Fall 2023 cohort) | 3965 | 16720 | 555 |
| B. Number of students in line (A) who applied for need-based financial aid | 3004 | 10470 | 474 |
| C. Number of students in line (B) who were determined to have financial need | 1454 | 5712 | 300 |
| D. Number of students in line (C) who were awarded any financial aid | 1454 | 5712 | 300 |
| E. Number of students in line (D) who were awarded any need-based scholarship or grant aid | 1372 | 5277 | 263 |
| F. Number of students in line (D) who were awarded any need-based self-help aid | 740 | 2,972 | 141 |
"""

_I1 = """## I1. Instructional Faculty

|  | Full-Time | Part-Time | Total |
|---|---|---|---|
| A. Total number of instructional faculty | 1641 | 65 | 1706 |
| B. Total number who are members of minority groups | 391 | 6 | 397 |
| C. Total number who are women | 704 | 38 | 742 |
| D. Total number who are men | 937 | 27 | 964 |
| E. Total number who are international (non-residents) | 68 | 1 | 69 |
"""

# The school lettered both the F and the G row "F."; the values are in order.
_GRADUATION = """
B4 - B21. Graduation Rates

For Bachelor's or Equivalent Programs: Please provide data for the Fall                                                2017 COHORT (AY - 7)
2017 cohort if available. If Fall 2017 cohort data are not available,                                                Recipients of         Students
provide data for the Fall 2016 cohort.                                                                               a Subsidized        who did not

A. Initial 2017 cohort of first-time, full-time, bachelor's (or equivalent)                             509                    533                  2,746                    3,788
degree-seeking undergraduate students
B. Of the Initial 2017 cohort, how many did not persist and did not
graduate for any of the following reasons: (report total allowable
exclusions)
- Deceased                                                                                                0                        0                        1                      1
- Armed Forces
C. Final 2017 cohort, after adjusting for allowable exclusions                                          509                    533                  2,745                    3,787

D. Of the initial 2017 cohort, how many completed the program in                                        455                      498                  2,526                    3,479
four years or less (by Aug. 31, 2021)?
E. Of the initial 2017 cohort, how many completed the program in
more than four years but in five years or less (after Aug. 31, 2021 and                                  17                        11                      83                     111
by Aug. 31, 2022)?
F. Of the initial 2017 cohort, how many completed the program in
more than five years but in six years or less (after Aug. 31, 2022 and by                                 2                        5                       12                    19
Aug. 31, 2023)?
F. Of the initial 2017 cohort, how many completed the program in
more than five years but in six years or less (after Aug. 31, 2022 and by                               474                      514                  2,621                    3,609
Aug. 31, 2023)?

                                      H. Six-year graduation rate for 2017 cohort                      93.1%                       96.4%               95.5%                     95.3%
                                                                          (G. divided by C.)

For Bachelor's or Equivalent Programs: Please provide data for the Fall                                                2016 COHORT (AY - 8)

A. Initial 2016 cohort of first-time, full-time, bachelor's (or equivalent)                             448                    481                  2,753                    3,682
C. Final 2016 cohort, after adjusting for allowable exclusions                                          448                    481                  2,753                    3,682
D. Of the initial 2016 cohort, how many completed the program in                                        388                      430                  2,523                    3,341
E. Of the initial 2016 cohort, how many completed the program in                                         17                        23                      98                     138
F. Of the initial 2016 cohort, how many completed the program in                                          5                         2                      18                      25
G. Total graduating within six years (Sum of D., E., F.)                                                410                      455                  2,639                    3,504
H. Six-year graduation rate for 2016 cohort (G. divided by C.)                                        91.5%                     94.6%               95.9%                     95.2%

                              Two-Year Institutions - Graduation, Completion Counts
B22. Retention Rates
"""

_H5 = """
                                                                                   H. FINANCIAL AID
H5. Number/Percent Borrowers and Average Borrowed Amount
Provide the number and percent of students in class (defined in H4 above) borrowing from federal, non-federal, and any loan sources.

                          A. Any loan program: Federal Perkins, Federal
                          Stafford Subsidized and Unsubsidized, institutional,
                          state, private loans that your institution is aware of,                       1,158                             32%                               $27,302
                          etc. Include both Federal Direct Student Loans and
                          Federal Family Education Loans.

                          B. Federal loan programs: Federal Perkins, Federal
                          Stafford Subsidized and Unsubsidized. Include both                            1,108                             30%                               $16,464
                          Federal Direct Student Loans and Federal Family
                          Education Loans.

                          C. Institutional loan program                                                  245                              7%                                 $6,249

                          D. State loan programs                                                           0                              0%                                   $0

                          E. Private student loans made by a bank or lender                              236                              6%                                $50,181

H6. Aid to Undergraduate Degree-seeking Nonresidents
"""


class DottedRowLetterTests(unittest.TestCase):
    def test_dotted_letter_is_split_from_its_label(self):
        lines = [line for line in _I1.splitlines() if line.startswith("|")]
        split = _split_letter_description_column(lines)
        self.assertEqual(split[0], "|  |  | Full-Time | Part-Time | Total |")
        self.assertEqual(split[2], "| A | Total number of instructional faculty | 1641 | 65 | 1706 |")
        # A row with no letter keeps its text as the label, one cell further in.
        noted = lines + ["| (excluding those in line F above) | 10 | 20 | 30 |"]
        rows = _parse_markdown_tables("\n".join(noted))[0]["rows"]
        self.assertEqual(rows[-1]["label"], "(excluding those in line F above)")
        self.assertEqual(rows[-1]["values"], ["", "10", "20", "30"])

    def test_tables_without_five_dotted_rows_are_left_alone(self):
        lines = [line for line in _I1.splitlines() if line.startswith("|")]
        self.assertEqual(_split_letter_description_column(lines[:6]), lines[:6])
        prose = [
            "| Policy | Answer |", "|---|---|",
            "| A. B. degree offered | Yes |", "| Open admission | No |", "| U.S. citizens only | No |",
            "| Wait list | Yes |", "| Deferred admission | Yes |", "| Early decision | No |",
        ]
        self.assertEqual(_split_letter_description_column(prose), prose)

    def test_h2_with_dotted_letters_is_read(self):
        values = clean(_H2, canonical_year="2023-24")
        self.assertEqual(values["H.201"]["value"], "3965")
        self.assertEqual(values["H.214"]["value"], "16720")
        self.assertEqual(values["H.227"]["value"], "555")
        self.assertEqual(values["H.206"]["value"], "740")
        self.assertEqual(values["H.219"]["value"], "2972")

    def test_i1_with_dotted_letters_is_read(self):
        values = clean(_I1, canonical_year="2023-24")
        self.assertEqual(values["I.101"]["value"], "1641")
        self.assertEqual(values["I.105"]["value"], "68")
        self.assertEqual(values["I.123"]["value"], "742")

    def test_h5_text_rows_with_dotted_letters_are_read(self):
        values = clean("", supplemental_text=_H5, canonical_year="2023-24")
        self.assertEqual(values["H.501"]["value"], "1158")
        self.assertEqual(values["H.506"]["value"], "32")
        self.assertEqual(values["H.511"]["value"], "27302")
        self.assertEqual(values["H.504"]["value"], "0")
        self.assertEqual(values["H.515"]["value"], "50181")

    def test_h5_last_row_does_not_take_footer_numbers(self):
        footer = _H5.replace(
            "H6. Aid to Undergraduate", "Common Data Set 2023-2024                    2024-04-23                    46\n", 1
        )
        values = clean("", supplemental_text=footer, canonical_year="2023-24")
        self.assertEqual([values[qn]["value"] for qn in ("H.505", "H.510", "H.515")], ["236", "6", "50181"])

    def test_h5_row_letter_with_no_space_after_the_full_stop(self):
        tight = _H5.replace("C. Institutional loan program ", "C.Institutional loan program  ")
        values = clean("", supplemental_text=tight, canonical_year="2023-24")
        self.assertEqual([values[qn]["value"] for qn in ("H.502", "H.507", "H.512")], ["1108", "30", "16464"])
        self.assertEqual([values[qn]["value"] for qn in ("H.503", "H.508", "H.513")], ["245", "7", "6249"])


class ColumnCohortGraduationTests(unittest.TestCase):
    def test_rows_are_assigned_in_order_when_the_total_column_adds_up(self):
        values = clean("", supplemental_text=_GRADUATION, canonical_year="2023-24")
        # Current cohort (2017). Row B has values; the second "F." row is G.
        self.assertEqual([values[f"B.{n}"]["value"] for n in (401, 402, 403, 404)], ["509", "533", "2746", "3788"])
        self.assertEqual([values[f"B.{n}"]["value"] for n in (405, 408)], ["0", "1"])
        self.assertEqual(values["B.412"]["value"], "3787")
        self.assertEqual(values["B.424"]["value"], "19")
        self.assertEqual(values["B.428"]["value"], "3609")
        self.assertEqual(values["B.432"]["value"], "95.3")
        # Previous cohort (2016) prints no exclusions row at all.
        self.assertEqual(values["B.504"]["value"], "3682")
        self.assertNotIn("B.505", values)
        self.assertEqual(values["B.512"]["value"], "3682")
        self.assertEqual(values["B.528"]["value"], "3504")
        self.assertEqual(values["B.529"]["value"], "91.5")

    def test_the_later_cohort_is_current_whichever_is_printed_first(self):
        parts = _GRADUATION.split("\nFor Bachelor's")
        swapped = parts[0] + "\nFor Bachelor's" + parts[2].split("\n                              Two-Year")[0] + "\nFor Bachelor's" + parts[1] + "\nB22. Retention Rates\n"
        values = clean("", supplemental_text=swapped, canonical_year="2023-24")
        self.assertEqual(values["B.404"]["value"], "3788")
        self.assertEqual(values["B.504"]["value"], "3682")

    def test_a_cohort_that_does_not_add_up_is_not_read(self):
        wrong = _GRADUATION.replace("3,609", "3,709")
        values = clean("", supplemental_text=wrong, canonical_year="2023-24")
        # The other cohort still checks out and stays in its own slot.
        self.assertFalse([qn for qn in values if qn.startswith("B.4")])
        self.assertEqual(values["B.504"]["value"], "3682")

    def test_short_exclusions_row_is_placed_by_initial_less_final(self):
        # Printed: Pell 1, Stafford blank, neither 1, total 2.
        self.assertEqual(
            _b5_exclusions_by_column(["1", "1", "2"], ["100", "200", "300", "600"], ["99", "200", "299", "598"]),
            [(0, "1"), (2, "1"), (3, "2")],
        )
        short = _GRADUATION.replace(
            "- Deceased                                                                                                0                        0                        1                      1",
            "- Deceased                                                                                                                                                  1                      1",
        )
        values = clean("", supplemental_text=short, canonical_year="2023-24")
        self.assertEqual(values["B.404"]["value"], "3788")
        self.assertFalse([qn for qn in ("B.405", "B.406", "B.407", "B.408") if qn in values])
        # Three zeros beside four columns that lost nothing: which cell is
        # blank cannot be told, so the row is left out.
        self.assertEqual(_b5_exclusions_by_column(["0", "0", "0"], ["5", "5", "5", "15"], ["5", "5", "5", "15"]), [])
        # Values that match no placement are left out too.
        self.assertEqual(_b5_exclusions_by_column(["4", "4", "4"], ["5", "5", "5", "15"], ["5", "5", "4", "14"]), [])

    def test_a_lone_previous_cohort_keeps_the_previous_slot(self):
        only_2016 = "\nFor Bachelor's" + _GRADUATION.split("\nFor Bachelor's")[2]
        values = clean("", supplemental_text=only_2016, canonical_year="2023-24")
        self.assertEqual(values["B.504"]["value"], "3682")
        self.assertFalse([qn for qn in values if qn.startswith("B.4")])
        only_2017 = _GRADUATION.split("\nFor Bachelor's")[0] + "\nFor Bachelor's" + _GRADUATION.split("\nFor Bachelor's")[1]
        values = clean("", supplemental_text=only_2017 + "\nB22. Retention Rates\n", canonical_year="2023-24")
        self.assertEqual(values["B.404"]["value"], "3788")

    def test_arithmetic_gate(self):
        rows = [
            "A   100   200   300   600", "B   0   0   0   0", "C   100   200   300   600",
            "D   50   100   150   300", "E   10   20   30   60", "F   5   10   15   30",
            "G   65   130   195   390", "H   65%   65%   65%   65%",
        ]
        self.assertEqual(sorted(_b5_rows_that_add_up("\n".join(rows))), list("ABCDEFGH"))
        # Six rows, a wrong total, a rate that is not G / C, a row short of a value.
        self.assertIsNone(_b5_rows_that_add_up("\n".join(rows[:6])))
        self.assertIsNone(_b5_rows_that_add_up("\n".join(rows[:6] + ["G   65   130   195   400", rows[7]])))
        self.assertIsNone(_b5_rows_that_add_up("\n".join(rows[:7] + ["H   65%   65%   65%   85%"])))
        self.assertIsNone(_b5_rows_that_add_up("\n".join(rows[:3] + ["D   50   100   300"] + rows[4:])))
        # Markdown table lines are not text rows.
        self.assertIsNone(_b5_rows_that_add_up("\n".join("| " + r for r in rows)))


if __name__ == "__main__":
    unittest.main()
