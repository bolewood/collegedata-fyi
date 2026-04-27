from __future__ import annotations

import unittest

from tier4_cleaner import clean


class Tier4CleanerG6Test(unittest.TestCase):
    def test_g6_per_credit_charges_after_page_footer(self):
        supplemental = """
G. ANNUAL EXPENSES

G6                Undergraduate per-credit-hour charges (tuition only):
                  PRIVATE INSTITUTIONS:

CDS-G                                                              Page 19

Common Data Set 2024-2025

     PUBLIC INSTITUTIONS:
     In-district:                                         $295.00
     In-state (out-of-district):                          $295.00
     Out-of-state:                                        $732.00
     NONRESIDENTS:                                        $732.00

CDS-G                                                              Page 20

H. FINANCIAL AID
"""

        values = clean("", supplemental_text=supplemental)

        self.assertEqual(values["G.602"]["value"], "295.00")
        self.assertEqual(values["G.603"]["value"], "295.00")
        self.assertEqual(values["G.604"]["value"], "732.00")
        self.assertEqual(values["G.605"]["value"], "732.00")
        self.assertNotIn("G.601", values)


if __name__ == "__main__":
    unittest.main()
