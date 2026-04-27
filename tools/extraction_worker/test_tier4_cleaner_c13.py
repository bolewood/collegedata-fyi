from __future__ import annotations

import unittest

from tier4_cleaner import clean


class Tier4CleanerC13Test(unittest.TestCase):
    def test_c1301_reads_yes_no_from_layout_columns(self):
        supplemental = """
C13          Application Fee
             If your institution has waived its application fee for the Fall 2026 admission cycle please select no.

                                                                                                                                                               Yes                                  No
             Does your institution have an application fee?                                                                                                        x

             Amount of application fee:                                                                                                                                    $50

             C14 Application closing date
"""

        values = clean("", supplemental_text=supplemental)

        self.assertEqual(values["C.1301"]["value"], "Yes")


if __name__ == "__main__":
    unittest.main()
