from __future__ import annotations

import unittest

from tier4_cleaner import clean


class Tier4CleanerF3F4Test(unittest.TestCase):
    def test_f3_f4_rotc_and_housing_from_layout(self):
        supplemental = """
                                                     F. STUDENT LIFE
F3 ROTC (program offered in cooperation with Reserve Officers' Training Corps)
                                                                                                                                                                                                                                                                                                                                                              Name of
                                                                 Programs                                                                                                                                                                                                                                 Marine Option (for Naval ROTC)                                                On Campus                                                               At Cooperating InstitutionCooperating
                                                                                                                                                                                                                                                                                                                                                          Institution

               Army ROTC is offered:                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                         Hofstra University
               Naval ROTC is offered:
                                                                                                                                                                                                                                                                                                                                                           Manhattan
               Air Force ROTC is offered:                                                                                                                                                                                                                                                                                                                      College

F4 Housing: Check all types of college-owned, -operated, or -affiliated housing available for undergraduates at your institution.

     x         Coed dorms
               Men's dorms
               W omen's dorms
               Apartments for married students
               Apartments for single students
               Special housing for disabled students
               Special housing for international students
               Fraternity/sorority housing
               Cooperative housing
               Theme housing
               W ellness housing
               Living Learning Communities
               Other housing options (specify):

CDS-F
"""

        values = clean("", supplemental_text=supplemental)

        self.assertEqual(values["F.301"]["value"], "At cooperating institution")
        self.assertEqual(values["F.302"]["value"], "Hofstra University")
        self.assertNotIn("F.303", values)
        self.assertNotIn("F.304", values)
        self.assertNotIn("F.305", values)
        self.assertEqual(values["F.306"]["value"], "At cooperating institution")
        self.assertEqual(values["F.307"]["value"], "Manhattan College")
        self.assertEqual(values["F.401"]["value"], "X")
        self.assertNotIn("F.402", values)
        self.assertNotIn("F.413", values)

    def test_f4_coed_dorms_docling_markdown_alias(self):
        markdown = """
- F4 Housing: Check all types of college-owned, -operated, or -affiliated housing available for undergraduates at your institution.

- [ ] x Coed dorms

- [ ] Men's dorms
"""

        values = clean(markdown)

        self.assertEqual(values["F.401"]["value"], "X")
        self.assertNotIn("F.402", values)


if __name__ == "__main__":
    unittest.main()
