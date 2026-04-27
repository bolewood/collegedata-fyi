from __future__ import annotations

import unittest

from tier4_cleaner import clean


class Tier4CleanerC1C2Test(unittest.TestCase):
    def test_c2_waitlist_policy_and_counts_from_layout(self):
        supplemental = """
C2   First-time, first-year wait-listed students
     Students who met admission requirements but whose final admission was contingent on space
     availability

                                                                       Yes          No
     Do you have a policy of placing students on a waiting list?        x

     If yes, please answer the questions below for Fall 2024 admissions:

                                WAITING LIST                                      TOTAL
     Number of qualified applicants offered a place on waiting list:               998
     Number accepting a place on the waiting list:                                 344
     Number of wait-listed students admitted:                                      157

C3   High school completion requirement
"""

        values = clean("", supplemental_text=supplemental)

        self.assertEqual(values["C.201"]["value"], "Yes")
        self.assertEqual(values["C.202"]["value"], "998")
        self.assertEqual(values["C.203"]["value"], "344")
        self.assertEqual(values["C.204"]["value"], "157")


if __name__ == "__main__":
    unittest.main()
