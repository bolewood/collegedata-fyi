from __future__ import annotations

import unittest

from tier4_cleaner import clean


class Tier4CleanerBGraduationTest(unittest.TestCase):
    def test_two_year_grid_only_populates_visible_values(self):
        supplemental = """
      For Two-Year Institutions

      Please provide data for the 2021 cohort if available. If 2021 cohort data are not available, provide data for the 2020 cohort.

                                                                                                                 2021 Cohort           2020 Cohort
B12 Initial cohort, total of first-time, full-time degree/certificate-seeking students:

B13 Of the initial cohort, how many did not persist and did not graduate for the following reasons:
      - Death
      - Permanently Disability
      - Service in the armed forces,
      - Foreign aid service of the federal government
      - Official church missions
      - Report total allowable exclusions

B14 Final cohort, after adjusting for allowable exclusions:                                                                     0                    0
B15 Completers of programs of less than two years duration (total):
B16 Completers of programs of less than two years within 150 percent of normal time:
B17 Completers of programs of at least two but less than four years (total):
B18 Completers of programs of at least two but less than four-years within 150 percent of normal time:
B19 Total transfers-out (within three years) to other institutions:
B20 Total transfers to two-year institutions:
B21 Total transfers to four-year institutions:
      B22. Retention Rates
"""

        values = clean("", supplemental_text=supplemental)

        self.assertNotIn("B.1201", values)
        self.assertNotIn("B.1202", values)
        self.assertNotIn("B.1301", values)
        self.assertNotIn("B.1302", values)
        self.assertEqual(values["B.1401"]["value"], "0")
        self.assertEqual(values["B.1402"]["value"], "0")
        self.assertNotIn("B.1501", values)
        self.assertNotIn("B.1502", values)
        self.assertNotIn("B.2101", values)
        self.assertNotIn("B.2102", values)

    def test_two_year_grid_handles_layout_text_value_glued_to_label(self):
        supplemental = """
For Two-Year Institutions
                                                                                                                 2021 Cohort           2020 Cohort
 B14                                                                                                                                                                           0                    0Final cohort, after adjusting for allowable exclusions:
      B22. Retention Rates
"""

        values = clean("", supplemental_text=supplemental)

        self.assertEqual(values["B.1401"]["value"], "0")
        self.assertEqual(values["B.1402"]["value"], "0")

    def test_kenyon_bachelor_grad_rate_layout(self):
        supplemental = """
For Bachelor's or Equivalent Programs

                                                               Fall 2018 Cohort

A
     Initial 2018 cohort of first-time, full-time,
     bachelor's (or equivalent) degree-seeking           53                 51                        435                      539
     undergraduate students

B
     Of the initial 2018 cohort, how many did not
     persist and did not graduate for the following
     reasons:
     - Deceased
     - Permanently Disabled                                                 0                         0                        0

C     Final 2018 cohort, after adjusting for allowable
                                                            53                   51                    435                  539
      exclusions
D
      Of the initial 2018 cohort, how many completed
      the program in four years or less (by Aug. 31,        35                   33                    291                  359
      2022)

E
      Of the initial 2018 cohort, how many completed
      the program in more than four years but in five
                                                            8                    8                     64                   80

F
      Of the initial 2018 cohort, how many completed
      the program in more than five years but in six
                                                            0                    0                     4                    4

G
      Total graduating within six years (sum of lines D,
      E, and F)
                                                         43                      41                    359                  443

H
      Six-year graduation rate for 2018 cohort (G
                                                            0.811320755          0.803921569           0.825287356          0.821892393
      divided by C)

                                                                    Fall 2017 Cohort

      Initial 2017 cohort of first-time, full-time,
A     bachelor's (or equivalent) degree-seeking                                                                                      0
      undergraduate students

B     - Permanently Disabled                                                                                                         0

C                                                                     0                     0                   0                    0
      exclusions

G
      E, and F)
                                                                      0                     0                   0                    0

For Two-Year Institutions
"""

        values = clean("", supplemental_text=supplemental)

        self.assertEqual(values["B.401"]["value"], "53")
        self.assertEqual(values["B.402"]["value"], "51")
        self.assertEqual(values["B.403"]["value"], "435")
        self.assertEqual(values["B.404"]["value"], "539")
        self.assertNotIn("B.405", values)
        self.assertEqual(values["B.406"]["value"], "0")
        self.assertEqual(values["B.407"]["value"], "0")
        self.assertEqual(values["B.408"]["value"], "0")
        self.assertEqual(values["B.429"]["value"], "0.811320755")
        self.assertEqual(values["B.432"]["value"], "0.821892393")
        self.assertNotIn("B.501", values)
        self.assertEqual(values["B.504"]["value"], "0")
        self.assertEqual(values["B.512"]["value"], "0")
        self.assertEqual(values["B.525"]["value"], "0")
        self.assertEqual(values["B.528"]["value"], "0")


if __name__ == "__main__":
    unittest.main()
