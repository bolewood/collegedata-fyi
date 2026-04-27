from __future__ import annotations

import unittest

from tier4_cleaner import clean


class Tier4CleanerD10D22Test(unittest.TestCase):
    def test_d10_d22_transfer_credit_policies_from_layout(self):
        supplemental = """
TRANSFER ADMISSION
                                                                                                                                                                                                                                        Yes                                                  No
 D10                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                               xDoes an open admission policy, if reported, apply to
                   transfer students?

 D11               Describe additional requirements for transfer admission, if applicable:
                   Certain programs may have higher minimum GPA requirements for transfer applicants; programs may
                   have specific deadlines. Please see https://www.farmingdale.edu/admissions/dates-deadlines.shtml for
                   additional information.

                   D12-D17: Transfer Credit Policies
 D12               Report the lowest grade earned for any
                   course that may be transferred for credit:                                                                                                                      2.00

                                                                                                                                                                                                                                 Number                                           Unit Type
 D13                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                         90                                                                                                                                             creditMaximum number of credits or courses that may be
                   transferred from a two-year institution:

                                                                                                                                                                                                                                 Number                                           Unit Type
 D14                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                         90                                                                                                                                             creditMaximum number of credits or courses that may be
                   transferred from a four-year institution:

 D15               Minimum number of credits that transfers must complete
                   at your institution to earn an associate degree:                                                                                                                                                                  30.00

 D16               Minimum number of credits that transfers must complete
                   at your institution to earn a bachelor’s degree:                                                                                                                                                                  30.00

 D17               Describe other transfer credit policies:

                   D18-D22: Military Service Transfer Credit Policies
 D18               Does your institution accept the following military/veteran transfer credits:

                                                                                                                                                                                                                                        Yes                                                  No
                   American Council on Education (ACE)                                                                                                                                                                                      x
                   College Level Examination Program (CLEP)                                                                                                                                                                                 x
                   DANTES Subject Standardized Tests (DSST)                                                                                                                                                                                 x

                                                                                                                                                                                                                                 Number                                           Unit Type
 D19               Maximum number of credits or courses that may be
                   transferred based on military education evaluated by the                                                                                                                                                               90                                                                                                                                           credit
                   American Council on Education (ACE):

                                                                                                                                                                                                                                 Number                                           Unit Type
 D20              Maximum number of credits or courses that may be transferred
                  based on Department of Defense supported prior learning                                                                                                                                                                 90                                                                                                                                           credit
                  assessments (College Level Examination Program (CLEP) or
                  DANTES Subject Standardized Tests (DSST)):

                                                                                                                                                                                                                                        Yes                                                  No
 D21              Are the military/veteran credit transfer policies published on your                                                                                                                                                       x
                  website?

                   If yes, please provide the URL where the policy can be located:
                                https://www.farmingdale.edu/transfer-services/transfer-course-equivalencies.shtml

 D22               Describe other military/veteran transfer credit policies unique to your institution:
                   Military credits may be granted on a case-by-case basis based upon review of a JST
                   (formerly Military Smart) or Community College of the Air Force transcript.

CDS-D
"""

        values = clean("", supplemental_text=supplemental)

        self.assertEqual(values["D.1001"]["value"], "No")
        self.assertIn("higher minimum GPA requirements", values["D.1101"]["value"])
        self.assertEqual(values["D.1201"]["value"], "2.00")
        self.assertEqual(values["D.1301"]["value"], "90")
        self.assertEqual(values["D.1302"]["value"], "credit")
        self.assertEqual(values["D.1401"]["value"], "90")
        self.assertEqual(values["D.1402"]["value"], "credit")
        self.assertEqual(values["D.1501"]["value"], "30.00")
        self.assertEqual(values["D.1601"]["value"], "30.00")
        self.assertNotIn("D.1701", values)
        self.assertEqual(values["D.1801"]["value"], "Yes")
        self.assertEqual(values["D.1802"]["value"], "Yes")
        self.assertEqual(values["D.1803"]["value"], "Yes")
        self.assertEqual(values["D.1901"]["value"], "90")
        self.assertEqual(values["D.1902"]["value"], "credit")
        self.assertEqual(values["D.2001"]["value"], "90")
        self.assertEqual(values["D.2002"]["value"], "credit")
        self.assertEqual(values["D.2101"]["value"], "Yes")
        self.assertEqual(
            values["D.2102"]["value"],
            "https://www.farmingdale.edu/transfer-services/transfer-course-equivalencies.shtml",
        )
        self.assertIn("case-by-case basis", values["D.2201"]["value"])


if __name__ == "__main__":
    unittest.main()
