from __future__ import annotations

import unittest

from tier4_cleaner import clean, trim_h15_spill


class Tier4CleanerH13H15Test(unittest.TestCase):
    def test_h13_h15_continuation_page(self):
        supplemental = """
H. FINANCIAL AID

H13 Need Based Scholarships and Grants

  x   Federal Pell
  x   Federal SEOG
  x   State scholarships/grants
  x   Private scholarships

CDS-H

Common Data Set 2024-2025

  x   College/university scholarship or grant aid from institutional funds
      United Negro College Fund
      Federal Nursing Scholarship
      Other (specify):

H14 Check off criteria used in awarding institutional aid. Check all that apply.
                                                                Non-Need Based          Need-Based
      Academics                                                        x                     x
      Alumni affiliation                                               x                     x
      Art
      Athletics
      Job skills                                                       x                     x
      ROTC
      Leadership
      Music/drama
      Religious affiliation
      State/district residency                                         x                     x

H15
      If your institution has recently implemented any major financial aid policy, program, or initiative
      to make your institution more affordable to incoming students such as replacing loans with
      grants, or waiving costs for families below a certain income level please provide details below:
      SUNY will now match in state tuition for students coming from specific states if lower than our
      out-of-state tuition charges. W e offer a Residence Assistance Program grant for out-of-state
      students who reside in on- campus housing.

CDS-H
"""

        values = clean("", supplemental_text=supplemental)

        self.assertEqual(values["H.1305"]["value"], "X")
        self.assertNotIn("H.1306", values)
        self.assertNotIn("H.1307", values)
        self.assertEqual(values["H.1401"]["value"], "X")
        self.assertEqual(values["H.1402"]["value"], "X")
        self.assertNotIn("H.1403", values)
        self.assertNotIn("H.1404", values)
        self.assertEqual(values["H.1405"]["value"], "X")
        self.assertEqual(values["H.1410"]["value"], "X")
        self.assertEqual(values["H.1411"]["value"], "X")
        self.assertEqual(values["H.1412"]["value"], "X")
        self.assertEqual(values["H.1415"]["value"], "X")
        self.assertEqual(values["H.1419"]["value"], "X")
        self.assertIn("SUNY will now match", values["H.1501"]["value"])
        self.assertIn("We offer a Residence Assistance Program", values["H.1501"]["value"])
        self.assertIn("on-campus housing", values["H.1501"]["value"])

    def test_kenyon_single_column_h14_and_h15_markdown_pollution(self):
        markdown = """
H15 If your institution has recently implemented any major financial aid policy, program, or
initiative to make your institution more affordable to incoming students such as replacing
loans with grants, or waiving costs for families below a certain income level please
provide details below:
Automatic Scholarship for Ohio Residents - [ ] Other (specify): - [x] Private scholarships Students must reply by (date):
"""
        supplemental = """
H. FINANCIAL AID

H14 Check off criteria used in awarding institutional aid. Check all that apply.
                                                              Non-Need Based       Need-Based
      Academics                                                       X
      Alumni affiliation
      Art                                                             X
      Athletics
      Job skills
      ROTC
      Leadership                                                      X
      Music/drama                                                     X
      Religious affiliation
      State/district residency                                        X

H15 If your institution has recently implemented any major financial aid policy, program, or
    initiative to make your institution more affordable to incoming students such as replacing
    loans with grants, or waiving costs for families below a certain income level please
    provide details below:
                              Automatic Scholarship for Ohio Residents

CDS-H
"""

        values = clean(markdown, supplemental_text=supplemental)

        self.assertEqual(values["H.1401"]["value"], "X")
        self.assertEqual(values["H.1403"]["value"], "X")
        self.assertEqual(values["H.1407"]["value"], "X")
        self.assertEqual(values["H.1408"]["value"], "X")
        self.assertEqual(values["H.1410"]["value"], "X")
        self.assertNotIn("H.1411", values)
        self.assertEqual(values["H.1501"]["value"], "Automatic Scholarship for Ohio Residents")

    def test_h15_empty_value_stops_before_compact_section_i(self):
        markdown = """
H15. If your institution has recently implemented any major financial aid policy, program, or initiative to make your
institution more affordable to incoming students such as replacing loans with grants, or waiving costs for families
below a certain income level please provide details below:
I.INSTRUCTIONALFACULTYANDCLASSSIZE I-1. Please report the number of instructional faculty members
J.DisciplinaryareasofDEGREESCONFERRED
"""

        values = clean(markdown)

        self.assertNotIn("H.1501", values)

    def test_h15_letter_spaced_section_i_does_not_swallow(self):
        # Penn State 2025-26 shape: the literal "INSTRUCTIONAL FACULTY"
        # cutoff misses the letter-spaced heading, and Sections I-J used to
        # land in H.1501.
        markdown = (
            "H. FINANCIAL AID\n"
            "H15. If your institution has recently implemented any major financial aid policy, "
            "program, or initiative to make your institution more affordable to incoming students "
            "such as replacing loans with grants, or waiving costs for families below a certain "
            "income level please provide details below:\n"
            "Our Promise grant covers tuition for families earning under $75,000.\n"
            "END OF SECT ION H CDS 2025-2026 I. INST RUCT IONAL FACULT Y AND CLASS SIZE I- 1 . "
            + _SECTION_I_BODY
        )

        values = clean(markdown)

        self.assertEqual(
            values["H.1501"]["value"],
            "Our Promise grant covers tuition for families earning under $75,000.",
        )


# Real Section I opening text, repeated to the length of a swallowed value.
_SECTION_I_BODY = (
    "Please report the number of instructional faculty members in each category for "
    "Fall 2025. Include faculty who are on your institution's payroll on the census date "
    "your institution uses for IPEDS/AAUP. "
) * 40


class TrimH15SpillTest(unittest.TestCase):
    """Real H.1501 values from prod artifacts (whitespace collapsed)."""

    def test_spill_only_values_drop_to_empty(self):
        cases = {
            "umass-lowell": "Are these policies related to the COVID-19 pandemic? Yes No "
            "I.IN STRUCTIONAL FACULTY AND CLASS SIZE I-1. ",
            "penn-state": "END OF SECT ION H CDS 2025-2026 I. INST RUCT IONAL FACULT Y AND "
            "CLASS SIZE I- 1 . ",
            "upitt": "I. INSTRUCTIONAL FACU LTY AND CLASS SIZE I1. ",
            "west-chester": " Are these policies related to the COVID-19 pandemic? "
            "Section I: INSTRUCTIONAL FACULTY AND CLASS SIZE I1. ",
            "texas-am": "&RPPRQ\x03'DWD\x036HW\x03 I. INSTRUCTIONAL FACULTY AND CLASS SIZE I-1. ",
            "uva": "Are these policies related to the COVID-19 pandemic? Yes No "
            "INSTRUCTIONAL I. FACULTY AND CLASS SIZE I-1. ",
            "rice": "CDS-H Rice University Common Data Set 2015‐16 J. DEGREES CONFERRED J1 ",
            "harvard": "CDS_2015-2016_Final.xlsx CDS_2015-2016_Final.xlsx I. INSTRUCTIONAL "
            "FACULTY AND CLASS SIZE ",
            "uic": "N/A " + "_" * 80 + " Common Data Set 2019-2020 " + "_" * 22
            + " Common Data Set Definitions i All definitions related to the financial aid ",
        }
        for school, head in cases.items():
            with self.subTest(school=school):
                self.assertEqual(trim_h15_spill(head + _SECTION_I_BODY), "")

    def test_real_answers_survive_with_footer_removed(self):
        cases = {
            "gonzaga": (
                "Gonzaga provides grant and scholarship aid to cover the cost of tuition for "
                "first-year students. Are these policies related to the COVID-19 pandemic? "
                "տ Yes տտ ✔No &RPPRQ\x03'DWD\x036HW\x03 I. INSTRUCTIONAL "
                "FACULTY AND CLASS SIZE I-1. ",
                "Gonzaga provides grant and scholarship aid to cover the cost of tuition for "
                "first-year students.",
            ),
            "ferris": (
                "Ferris Launch covers cost of tuition for students with zero EFC and GPA of 3.0 "
                "or higher. &RPPRQ\x03'DWD\x036HW\x03 I. INST RUCTIONAL FACULT Y AND CLASS "
                "SIZEI.INST RUCTIONALFACULT YANDCLASSSIZE I-1. ",
                "Ferris Launch covers cost of tuition for students with zero EFC and GPA of 3.0 "
                "or higher.",
            ),
            "weber": (
                "Beginning fall semester 2014, the Dream Weber program provides free tuition and "
                "general student fees to students whose annual household income is $40,000 or "
                "less. I: Instructional Faculty and Class Size I1 ",
                "Beginning fall semester 2014, the Dream Weber program provides free tuition and "
                "general student fees to students whose annual household income is $40,000 or "
                "less.",
            ),
        }
        for school, (raw, expected) in cases.items():
            with self.subTest(school=school):
                self.assertEqual(trim_h15_spill(raw + _SECTION_I_BODY), expected)

    def test_clean_answer_is_unchanged(self):
        text = "SUNY will now match in state tuition for students coming from specific states."
        self.assertEqual(trim_h15_spill(text), text)

    def test_footer_words_inside_an_answer_are_kept(self):
        for text in (
            "Our net price guarantee is explained in full. See page 12 of our aid guide for details",
            "These figures match what we report in the Common Data Set for each year since 2019",
        ):
            with self.subTest(text=text):
                self.assertEqual(trim_h15_spill(text), text)

    def test_answer_between_footers_is_kept(self):
        # Hendrix 2020-21: the answer sits between two page footers.
        raw = (
            "CDS-A Page 29 Common Data Set 2020-2021 tuition reset for new students entering "
            "2021 Are these policies related to the COVID-19 pandemic? Yes X No CDS-A Page 30 "
            "Common Data Set 2020-2021"
        )
        self.assertIn("tuition reset for new students entering 2021", trim_h15_spill(raw))

    def test_footer_only_values_drop_to_empty(self):
        for raw in (
            "CDS-H Page 25 Common Data Set 2009-10",
            "Are these policies related to the COVID-19 pandemic? Yes No",
            "N:\\SURVEYS\\CDS\\2019-20\\CDS 2019-20 FINAL.xlsx Page 27 The University of "
            "Alabama: Common Data Set 2019-20",
        ):
            with self.subTest(raw=raw):
                self.assertEqual(trim_h15_spill(raw), "")

    def test_footer_after_answer_is_removed(self):
        raw = (
            "These programs are last-dollar financial aid awards. Rutgers University - New "
            "Brunswick - July 2023 Page 26 Common Data Set 2022-2023 RUTGERS UNIVERSITY – NEW "
            "BRUNSWICK"
        )
        self.assertEqual(
            trim_h15_spill(raw),
            "These programs are last-dollar financial aid awards. Rutgers University - New "
            "Brunswick - July 2023",
        )


if __name__ == "__main__":
    unittest.main()
