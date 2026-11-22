from __future__ import annotations

import unittest

from tier4_cleaner import clean

# Swarthmore 2010-11 prints each head count with its share of the class.
# Docling can convert that as two columns under one repeated title, and can
# pull a value from the first data row into a title cell.
_SPLIT_WITH_ABSORBED_VALUE = """
B2. Enrollment by Racial/Ethnic Category.

|                                  | Degree-seeking First-time First year | Degree-seeking First-time First year | Degree-seeking Undergraduates (include first-time first-year) | Degree-seeking Undergraduates (include first-time first-year) | Total Undergraduates (both degree- and non- degree-seeking) * (7.3%) 111 | Total Undergraduates (both degree- and non- degree-seeking) * (7.3%) 111 |
|----------------------------------|------|-----|------|------|------|------|
| Nonresident aliens               | (9.5%) | 37 | (7.3%) | 110 |  |  |
| Hispanic                         | (12.6%) | 49 | (11.6%) | 175 | (11.5%) | 175 |
| Black or African American, non-Hispanic | (5.7%) | 22 | (6.4%) | 97 | (6.4%) | 97 |
| White, non-Hispanic              | (47.2%) | 183 | (45.0%) | 679 | (45.1%) | 687 |
| Total                            |  | 388 |  | 1509 |  | 1524 |

B3. Number of degrees awarded by your institution from July 1, 2009, to June 30, 2010.
"""

# The same shape with the shares printed without brackets.
_SPLIT_BARE_PERCENT = _SPLIT_WITH_ABSORBED_VALUE.replace("(", "").replace(")", "")

# Not a race table: one "Total" row under a first row that mentions
# degree-seeking students.
_NOT_B2 = """
C1. First-time, first-year students

|       | Total first-time, first-year (degree-seeking) men who applied | 1368 |
|-------|------|------|
| Total | 2000 | 5 |
"""


class Tier4CleanerB2SplitColumnsTest(unittest.TestCase):
    def test_reads_counts_when_a_title_cell_absorbed_a_value(self):
        values = clean(_SPLIT_WITH_ABSORBED_VALUE)

        # The count is read, not the share printed beside it.
        self.assertEqual(values["B.201"]["value"], "37")
        self.assertEqual(values["B.202"]["value"], "49")
        self.assertEqual(values["B.203"]["value"], "22")
        self.assertEqual(values["B.204"]["value"], "183")
        self.assertEqual(values["B.210"]["value"], "388")
        self.assertEqual(values["B.211"]["value"], "110")
        self.assertEqual(values["B.214"]["value"], "679")
        self.assertEqual(values["B.220"]["value"], "1509")
        self.assertEqual(values["B.222"]["value"], "175")
        self.assertEqual(values["B.224"]["value"], "687")
        self.assertEqual(values["B.230"]["value"], "1524")
        # The count that moved into the title cell is not guessed at.
        self.assertNotIn("B.221", values)


    def test_bare_percentage_is_not_read_as_a_count(self):
        values = clean(_SPLIT_BARE_PERCENT)

        self.assertEqual(values["B.201"]["value"], "37")
        self.assertEqual(values["B.202"]["value"], "49")
        self.assertEqual(values["B.211"]["value"], "110")
        self.assertEqual(values["B.212"]["value"], "175")
        self.assertEqual(values["B.222"]["value"], "175")
        self.assertEqual(values["B.230"]["value"], "1524")

    def test_lone_total_row_in_another_table_is_not_the_b2_total(self):
        values = clean(_NOT_B2)

        self.assertFalse([qn for qn in values if qn.startswith("B.2")])


if __name__ == "__main__":
    unittest.main()
