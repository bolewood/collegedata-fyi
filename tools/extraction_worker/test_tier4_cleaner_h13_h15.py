from __future__ import annotations

import unittest

from tier4_cleaner import clean


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


if __name__ == "__main__":
    unittest.main()
