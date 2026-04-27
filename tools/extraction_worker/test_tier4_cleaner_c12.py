from __future__ import annotations

import unittest

from tier4_cleaner import clean


class Tier4CleanerC12Test(unittest.TestCase):
    def test_c12_uses_layout_supplement_when_docling_displaces_values(self):
        markdown = """
- C12 Average high school GPA of all degree-seeking, first-time, first-year students who submitted GPA:

Percent of total first-time, first-year students who submitted high school GPA:

## C13-C20: Admission Policies

- C13 Application Fee

Amount of application fee:

$50

Yes

No

3.27

99%

x
"""
        supplemental = """
C12 Average high school GPA of all degree-seeking, first-time, first-year
    students who submitted GPA:                                                     3.27

     Percent of total first-time, first-year students who submitted high
                                                                                    99%
     school GPA:

     C13-C20: Admission Policies
"""

        values = clean(markdown, supplemental_text=supplemental)

        self.assertEqual(values["C.1201"]["value"], "3.27")
        self.assertEqual(values["C.1202"]["value"], "99")

    def test_c12_handles_pypdf_value_before_label_ordering(self):
        supplemental = """
                                                                                  3.27Average high school GPA of all degree-seeking, first-time, first-year
             students who submitted GPA:
             Percent of total first-time, first-year students who submitted high         99%
             school GPA:

             C13-C20: Admission Policies
"""

        values = clean("", supplemental_text=supplemental)

        self.assertEqual(values["C.1201"]["value"], "3.27")
        self.assertEqual(values["C.1202"]["value"], "99")


if __name__ == "__main__":
    unittest.main()
