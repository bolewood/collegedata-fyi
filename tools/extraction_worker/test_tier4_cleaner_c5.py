from __future__ import annotations

import unittest

from tier4_cleaner import clean


class Tier4CleanerC5Test(unittest.TestCase):
    def test_c5_truncated_recommended_header_and_wrapped_lab_row(self):
        markdown = """
| Distribution of high school units | Required | Recommende |
| --- | ---: | ---: |
| Total academic units | 15 | |
| English | 4 | |
| Mathematics | 3 | |
| Science | 3 | |
| Of these, units that must be lab | | |
| Foreign language | | 1 |
| Social studies | 4 | |
"""

        values = clean(markdown)

        self.assertEqual(values["C.501"]["value"], "15")
        self.assertEqual(values["C.502"]["value"], "4")
        self.assertEqual(values["C.503"]["value"], "3")
        self.assertEqual(values["C.504"]["value"], "3")
        self.assertEqual(values["C.507"]["value"], "4")
        self.assertEqual(values["C.518"]["value"], "1")
        self.assertNotIn("C.517", values)


if __name__ == "__main__":
    unittest.main()
