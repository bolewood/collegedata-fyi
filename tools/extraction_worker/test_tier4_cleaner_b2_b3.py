from __future__ import annotations

import unittest

from tier4_cleaner import clean


class Tier4CleanerB2B3Test(unittest.TestCase):
    def test_b2_race_and_b3_degrees_with_blank_rows(self):
        supplemental = """
B2   Enrollment by Racial/Ethnic Category.

                                                                                             Degree-Seeking                 Total
                                                                       Degree-Seeking
                                                                                             Undergraduates         Undergraduates (both
                                                                         First-Time
                                                                                         (include first-time first- degree & non-degree-
                                                                          First Year
                                                                                                  year)                   seeking)
     Nonresidents                                                                  66                     283                     287
     Hispanic/Latino                                                              577                   2,876                   2,967
     Black or African American, non-Hispanic                                      226                   1,077                   1,141
     White, non-Hispanic                                                          616                   3,598                   3,762
     American Indian or Alaska Native, non-Hispanic                                 8                      36                      37
     Asian, non-Hispanic                                                          226                   1,266                   1,332

     Native Hawaiian or other Pacific Islander, non-Hispanic                         3                     23                     25
     Two or more races, non-Hispanic                                                93                    365                    372
     Race and/or ethnicity unknown                                                   7                     28                     84
     TOTAL                                                                       1,822                  9,552                 10,007

     Persistence
B3   Number of degrees awarded by your institution from July 1, 2023, to June 30, 2024.
     Certificate/diploma                            46
     Associate degrees                             237
     Bachelor's degrees                           1663
     Postbachelor's certificates
     Master's degrees                               10
     Post-Master's certificates
     Doctoral degrees - research/scholarship

     Doctoral degrees - professional practice
     Doctoral degrees - other
     B4-B21: Graduation Rates
"""

        values = clean("", supplemental_text=supplemental)

        self.assertEqual(values["B.201"]["value"], "66")
        self.assertEqual(values["B.210"]["value"], "1822")
        self.assertEqual(values["B.211"]["value"], "283")
        self.assertEqual(values["B.220"]["value"], "9552")
        self.assertEqual(values["B.221"]["value"], "287")
        self.assertEqual(values["B.230"]["value"], "10007")
        self.assertEqual(values["B.301"]["value"], "46")
        self.assertEqual(values["B.302"]["value"], "237")
        self.assertEqual(values["B.303"]["value"], "1663")
        self.assertNotIn("B.304", values)
        self.assertEqual(values["B.305"]["value"], "10")
        self.assertNotIn("B.306", values)
        self.assertNotIn("B.307", values)
        self.assertNotIn("B.308", values)
        self.assertNotIn("B.309", values)


if __name__ == "__main__":
    unittest.main()
