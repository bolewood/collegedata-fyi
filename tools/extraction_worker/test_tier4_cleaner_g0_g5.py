from __future__ import annotations

import unittest

from tier4_cleaner import clean


class Tier4CleanerG0G5Test(unittest.TestCase):
    def test_g0_g5_annual_expenses_from_layout(self):
        supplemental = """
                                           G. ANNUAL EXPENSES
G0 Please provide the URL of your institution’s net price calculator:
                            https://www.suny.edu/howmuch/netpricecalculator.xhtml

 x Check here if your institution's 2025-2026 academic year costs of attendance are not available at this time
   and provide an approximate date (i.e., month/day) when your institution's final 2025-2026 academic year
   costs of attendance will be available:
   6/30/2025

G1 Undergraduate full-time tuition, required fees, food and housing

G1 PRIVATE INSTITUTIONS                           First-Year          Undergraduates
   Tuition:

    PUBLIC INSTITUTIONS                           First-Year          Undergraduates
    Tuition: In-district                            $7,070                $7,070
    Tuition: In-state (out-of-district):            $7,070                $7,070
    Tuition: Out-of-state:                         $17,560               $17,560
    Tuition: Non-resident                          $17,560               $17,560

    FOR ALL INSTITUTIONS                          First-Year          Undergraduates
    Required Fees:                                  $1,556                $1,556
    Food and housing (on-campus):                  $16,182               $16,182
    Housing Only (on-campus):
    Food Only (on-campus meal plan):

                                                                          Minimum                Maximum
G2 Number of credits per term a student can take for the stated
                                                                             12
   full-time tuition.

                                                                             Yes                    No
G3 Do tuition and fees vary by year of study (e.g., sophomore,
                                                                                                     x
   junior, senior)?
G4 Do tuition and fees vary by undergraduate instructional
                                                                              x
   program?
   If yes, what percentage of full-time undergraduates pay more
   than the tuition and fees reported in G1?                               1.89%

G5 Provide the estimated expenses for a typical full-time undergraduate student:
                                                                         Commuters             Commuters
                                                  Residents
                                                                      (living at home)     (not living at home)
    Books and supplies:                             $1,300                  $1,300                 $1,300
    Housing only:                               Not Applicable          Not Applicable
    Food only:                                  Not Applicable
    Food and housing total*                     Not Applicable          Not Applicable            $29,018
    Transportation:                                  $700                   $1,850                 $1,850
    Other expenses:                                 $1,300                  $1,300                 $1,300

G6 Undergraduate per-credit-hour charges (tuition only):
CDS-G
"""

        values = clean("", supplemental_text=supplemental)

        self.assertEqual(values["G.001"]["value"], "https://www.suny.edu/howmuch/netpricecalculator.xhtml")
        self.assertEqual(values["G.002"]["value"], "X")
        self.assertEqual(values["G.003"]["value"], "6/30/2025")
        self.assertEqual(values["G.201"]["value"], "12")
        self.assertNotIn("G.202", values)
        self.assertEqual(values["G.301"]["value"], "No")
        self.assertEqual(values["G.401"]["value"], "Yes")
        self.assertEqual(values["G.402"]["value"], "1.89")
        self.assertEqual(values["G.501"]["value"], "1300")
        self.assertEqual(values["G.502"]["value"], "700")
        self.assertEqual(values["G.503"]["value"], "1300")
        self.assertEqual(values["G.504"]["value"], "1300")
        self.assertNotIn("G.505", values)
        self.assertEqual(values["G.506"]["value"], "1850")
        self.assertEqual(values["G.507"]["value"], "1300")
        self.assertEqual(values["G.508"]["value"], "1300")
        self.assertNotIn("G.509", values)
        self.assertNotIn("G.510", values)
        self.assertEqual(values["G.511"]["value"], "29018")
        self.assertEqual(values["G.512"]["value"], "1850")
        self.assertEqual(values["G.513"]["value"], "1300")

    def test_kenyon_private_layout_and_merged_housing_label(self):
        supplemental = """
                                           G. ANNUAL EXPENSES
G0 Please provide the URL of your institution’s net price calculator:
                                          npc.collegeboard.org/app/kenyon

G1 Undergraduate full-time tuition, required fees, food and housing
G1 PRIVATE INSTITUTIONS                            First-Year          Undergraduates
   Tuition:                                         $71,870               $71,870

    FOR ALL INSTITUTIONS                           First-Year          Undergraduates
    Required Fees:                                    $350                  $350
    Food and housing (on-campus):
    Housing Only (on-campus):                        $7,600                 $7,600
    Food Only (on-campus meal plan):                 $9,780                 $9,780

G2 Number of credits per term a student can take for the stated
   full-time tuition.

G3 Do tuition and fees vary by year of study (e.g., sophomore,
   junior, senior)?
G4 Do tuition and fees vary by undergraduate instructional
   program?

G5 Provide the estimated expenses for a typical full-time undergraduate student:
                                                   Residents             Commuters               Commuters
    Books and supplies:                              $1,900
    Food and housing total*                      Not Applicable         Not Applicable
    Transportation:                                   $900
    Other expenses:                                  $1,490

G6 Undergraduate per-credit-hour charges (tuition only):
"""

        markdown = """
| PUBLIC INSTITUTIONS | First-Year | Undergraduates |
| --- | --- | --- |
| Required Fees: | $350 | $350 |
| Food and housing (on-campus): Housing Only (on-campus): | $7,600 | $7,600 |
| Food Only (on-campus meal plan): | $9,780 | $9,780 |
"""

        values = clean(markdown, supplemental_text=supplemental)

        self.assertEqual(values["G.001"]["value"], "npc.collegeboard.org/app/kenyon")
        self.assertEqual(values["G.101"]["value"], "71870")
        self.assertEqual(values["G.102"]["value"], "71870")
        self.assertEqual(values["G.111"]["value"], "350")
        self.assertEqual(values["G.115"]["value"], "350")
        self.assertNotIn("G.112", values)
        self.assertNotIn("G.116", values)
        self.assertEqual(values["G.113"]["value"], "7600")
        self.assertEqual(values["G.117"]["value"], "7600")
        self.assertEqual(values["G.114"]["value"], "9780")
        self.assertEqual(values["G.118"]["value"], "9780")
        self.assertEqual(values["G.501"]["value"], "1900")
        self.assertEqual(values["G.502"]["value"], "900")
        self.assertEqual(values["G.503"]["value"], "1490")
        self.assertNotIn("G.511", values)


if __name__ == "__main__":
    unittest.main()
