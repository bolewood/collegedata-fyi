"""B2 on forms that print "B2. Enrollment by Racial/Ethnic Category" and
"International (nonresidents)" for the first row (issue #433)."""
import unittest

from tier4_cleaner import clean

_ROWS = """
International (nonresidents)                                    208                    794                  1,002
Hispanic/Latino                                                 283                  1,268                  1,551
Black or African American, non-Hispanic                         324                  1,306                  1,630
White, non-Hispanic                                           1,851                  8,718                 10,569
American Indian or Alaska Native, non-Hispanic                    2                     10                     12
Asian, non-Hispanic                                             735                  2,925                  3,660
Native Hawaiian or other Pacific Islander, non-
Hispanic                                                          1                      6                      7
Two or more races, non-Hispanic                                 228                    915                  1,143
Race and/or ethnicity unknown                                   356                  1,333                  1,689
   Total                                                      3,988                 17,275                 21,263
"""
_B2 = (
    "B2. Enrollment by Racial/Ethnic Category\n"
    "Provide numbers of undergraduate students for each of the following categories as of October 15, 2023.\n"
    + _ROWS
    + "  B3. Persistence / Degrees\n"
    "Total                                                             1                      2                      3\n"
)


class B2DottedHeadingTests(unittest.TestCase):
    def test_rows_under_a_dotted_heading_are_read(self):
        values = clean("", supplemental_text=_B2, canonical_year="2023-24")
        got = {qn: rec["value"] for qn, rec in values.items() if qn.startswith("B.2") and len(qn) == 5}
        self.assertEqual(len(got), 30)
        self.assertEqual([got["B.201"], got["B.211"], got["B.221"]], ["208", "794", "1002"])   # nonresidents
        self.assertEqual([got["B.207"], got["B.217"], got["B.227"]], ["1", "6", "7"])           # wrapped label
        self.assertEqual([got["B.210"], got["B.220"], got["B.230"]], ["3988", "17275", "21263"])

    def test_without_the_next_heading_nothing_is_read(self):
        # Unbounded, the block would run on and take any later "Total" line.
        open_ended = _B2.replace("  B3. Persistence / Degrees\n", "")
        values = clean("", supplemental_text=open_ended, canonical_year="2023-24")
        self.assertFalse([qn for qn in values if qn.startswith("B.2") and len(qn) == 5])

    def test_lines_after_the_next_heading_are_not_read(self):
        values = clean("", supplemental_text=_B2, canonical_year="2023-24")
        self.assertEqual(values["B.210"]["value"], "3988")
        self.assertEqual(values["B.230"]["value"], "21263")


if __name__ == "__main__":
    unittest.main()
