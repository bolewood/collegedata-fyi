from __future__ import annotations

import unittest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from tier4_cleaner import SchemaIndex, clean


class Tier4CleanerC1SchemaYearTest(unittest.TestCase):
    def test_2024_c1_gender_rows_use_2024_question_numbers(self):
        markdown = """
## C1 First-time, first-year students

| Applicants | Total |
|---|---:|
| Total first-time, first-year men who applied | 10 |
| Total first-time, first-year women who applied | 20 |
| Total first-time, first-year another gender who applied | 3 |
| Total first-time, first-year men who were admitted | 5 |
| Total first-time, first-year women who were admitted | 6 |
| Total first-time, first-year another gender who were admitted | 1 |
| Total first-time, first-year men who enrolled | 2 |
| Total first-time, first-year women who enrolled | 4 |
"""
        values = clean(
            markdown,
            schema=SchemaIndex(Path("schemas/cds_schema_2024_25.json")),
        )

        self.assertEqual(values["C.101"]["value"], "10")
        self.assertEqual(values["C.102"]["value"], "20")
        self.assertEqual(values["C.103"]["value"], "3")
        self.assertNotIn("C.104", values)
        self.assertEqual(values["C.105"]["value"], "5")
        self.assertEqual(values["C.106"]["value"], "6")
        self.assertEqual(values["C.107"]["value"], "1")
        self.assertEqual(values["C.109"]["value"], "2")
        self.assertEqual(values["C.111"]["value"], "4")


if __name__ == "__main__":
    unittest.main()
