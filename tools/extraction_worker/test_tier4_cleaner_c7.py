from __future__ import annotations

import unittest

from tier4_cleaner import clean


class Tier4CleanerC7Test(unittest.TestCase):
    def test_c7_page_split_continuation_without_header(self):
        markdown = """
## C6-C7: Basis for Selection

| Academic                         | Very Important   | Important   | Considered   | Not Considered   |
|----------------------------------|------------------|-------------|--------------|------------------|
| Rigor of secondary school record |                  | x           |              |                  |
| Nonacademic                      | Very Important   | Important   | Considered   | Not Considered   |
| Talent/ability                   |                  |             | x            |                  |

<!-- image -->

| Character/personal qualities     |    | x   |    |
|----------------------------------|----|-----|----|
| First generation                 |    | x   |    |
| Alumni/ae relation               |    | x   |    |
| Geographical residence           |    |     | x  |
| State residency                  |    |     | x  |
| Religious affiliation/commitment |    |     | x  |
| Volunteer work                   |    | x   |    |
| Work experience                  |    | x   |    |
| Level of applicant's interest    | x  |     |    |
"""

        values = clean(markdown)

        self.assertEqual(values["C.701"]["value"], "Important")
        self.assertEqual(values["C.709"]["value"], "Considered")
        self.assertEqual(values["C.710"]["value"], "Considered")
        self.assertEqual(values["C.711"]["value"], "Considered")
        self.assertEqual(values["C.712"]["value"], "Considered")
        self.assertEqual(values["C.713"]["value"], "Not Considered")
        self.assertEqual(values["C.714"]["value"], "Not Considered")
        self.assertEqual(values["C.715"]["value"], "Not Considered")
        self.assertEqual(values["C.716"]["value"], "Considered")
        self.assertEqual(values["C.717"]["value"], "Considered")
        self.assertEqual(values["C.718"]["value"], "Important")


if __name__ == "__main__":
    unittest.main()
