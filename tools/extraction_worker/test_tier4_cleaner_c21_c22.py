from __future__ import annotations

import unittest

from tier4_cleaner import clean


class Tier4CleanerC21C22Test(unittest.TestCase):
    def test_c21_c22_yes_no_from_multiline_layout_blocks(self):
        supplemental = """
C21              Early Decision
                                                                                                                                                                                                                                                       Yes                                          No
               Does your institution offer an early decision plan (an admission plan
               that permits students to apply and be notified of an admission
               decision well in advance of the regular notification date and that asks                                                                                                                                                                                  x
               students to commit to attending if accepted) for first-time, first-year
               applicants for fall enrollment?

C22              Early action
                                                                                                                                                                                                                             Yes                                      No
               Do you have a nonbinding early action plan whereby students are
               notified of an admission decision well in advance of the regular                                                                                                                                                                                         x
               notification date but do not have to commit to attending your college?

                                                                                                                                                  Yes                                                                                                                                     No
               Is your early action plan a “restrictive” plan under which you limit
               students from applying to other early plans?

D. TRANSFER ADMISSION
"""

        values = clean("", supplemental_text=supplemental)

        self.assertEqual(values["C.2101"]["value"], "No")
        self.assertEqual(values["C.2201"]["value"], "No")
        self.assertNotIn("C.2206", values)


if __name__ == "__main__":
    unittest.main()
