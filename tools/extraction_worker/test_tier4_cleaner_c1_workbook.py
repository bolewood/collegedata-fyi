"""C1 in the 2023-24 CDS workbook: one column per sex with sentence row
labels, and a residency table whose third row is labelled "enrolled".
"""
from __future__ import annotations

import unittest
from pathlib import Path

from tier4_cleaner import SchemaIndex, clean

REPO_ROOT = Path(__file__).resolve().parents[2]
SCHEMA_2023 = SchemaIndex(REPO_ROOT / "schemas" / "cds_schema_2023_24.json")


def _values(result: dict[str, dict]) -> dict[str, str]:
    return {qn: str(entry["value"]) for qn, entry in result.items()}


C1_TABLES = """
## C1. Applications: First-time, First-year Students

|                                                                  |     Men |   Women |   Another Gender |
|------------------------------------------------------------------|---------|---------|------------------|
| Total first-time, first-year students who applied in Fall 2023   | 3,721.0 | 5,030.0 |              0.0 |
| Total first-time, first-year students admitted in Fall 2023      | 3,183.0 | 4,377.0 |              0.0 |
| Total first-time, first-year students enrolled in Fall 2023      |   547.0 |   649.0 |              0.0 |
| Full-time, first-time, first-year students enrolled in Fall 2023 |   545.0 |   648.0 |              0.0 |
| Part-time, first-time, first-year students enrolled in Fall 2023 |     2.0 |     1.0 |              0.0 |

|                                                                 |   In-State |   Out-of-State |   International |   Total |
|-----------------------------------------------------------------|------------|----------------|-----------------|---------|
| Total first-time, first-year (degree seeking) who applied       |    4,407.0 |        4,055.0 |           289.0 | 8,751.0 |
| Total first-time, first-year (degree seeking) who were admitted |    3,828.0 |        3,612.0 |           120.0 | 7,560.0 |
| Total first-time, first-year (degree seeking) enrolled          |      682.0 |          493.0 |            21.0 | 1,196.0 |

## C2. Applications: First-time, First-year Wait-Listed Students
"""


class WorkbookC1Test(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.values = _values(clean(C1_TABLES, schema=SCHEMA_2023))

    def test_applied_and_admitted_by_sex(self):
        self.assertEqual(self.values.get("C.101"), "3721")
        self.assertEqual(self.values.get("C.102"), "5030")
        self.assertEqual(self.values.get("C.103"), "0")
        self.assertEqual(self.values.get("C.105"), "3183")
        self.assertEqual(self.values.get("C.106"), "4377")

    def test_enrolled_by_sex_uses_the_full_time_and_part_time_rows(self):
        # The 2023-24 form has no row for everyone of one sex who enrolled.
        self.assertEqual(self.values.get("C.109"), "545")
        self.assertEqual(self.values.get("C.110"), "2")
        self.assertEqual(self.values.get("C.111"), "648")
        self.assertEqual(self.values.get("C.112"), "1")

    def test_residency_rows_include_the_enrolled_row(self):
        self.assertEqual(self.values.get("C.117"), "8751")
        self.assertEqual(self.values.get("C.118"), "7560")
        self.assertEqual(self.values.get("C.119"), "1196")
        self.assertEqual(self.values.get("C.122"), "682")
        self.assertEqual(self.values.get("C.125"), "493")
        self.assertEqual(self.values.get("C.128"), "21")

    def test_the_total_applied_is_not_a_column_of_the_table_by_sex(self):
        self.assertNotIn(self.values.get("C.117"), {"3721", "5030"})


class ResidencyTableRowsTest(unittest.TestCase):
    def test_the_enrolled_row_is_read_past_a_blank_unknown_cell(self):
        # The text reader cannot place three numbers under five columns.
        markdown = """
## C1. Applications

| FIRST-TIME, FIRST-YEAR STUDENT APPLICANTS                       |   IN-STATE |   OUT-OF- STATE |   INTERNATIONAL | UNKNOWN   |   TOTAL |
|-----------------------------------------------------------------|------------|-----------------|-----------------|-----------|---------|
| Total first-time, first-year (degree-seeking) who applied       |     30,147 |           2,557 |           1,203 |           |  33,907 |
| Total first-time, first-year (degree-seeking) who were admitted |     27,156 |           2,190 |           1,152 |           |  30,498 |
| Total first-time, first-year (degree-seeking) enrolled          |      7,649 |             152 |             394 |           |   8,195 |

## C2. Wait list
"""
        schema = SchemaIndex(REPO_ROOT / "schemas" / "cds_schema_2024_25.json")

        values = _values(clean(markdown, schema=schema))

        self.assertEqual(values.get("C.128"), "394")

    def test_a_zero_total_over_blank_cells_is_not_a_count(self):
        markdown = """
## C1. Applications

|                                                                 | In-State   | Out-of-State   | International   |   Total |
|-----------------------------------------------------------------|------------|----------------|-----------------|---------|
| Total first-time, first-year (degree seeking) who applied       |            |                |                 |       0 |
| Total first-time, first-year (degree seeking) who were admitted | C or t     | C or t         | C or t          |       0 |
| Total first-time, first-year (degree seeking) enrolled          |            |                |                 |       0 |

## C2. Wait list
"""

        values = _values(clean(markdown, schema=SCHEMA_2023))

        for qn in ("C.117", "C.118", "C.119"):
            self.assertNotIn(qn, values)

    def test_a_row_of_real_zeros_is_kept(self):
        markdown = """
## C1. Applications

|                                                           | In-State   | Out-of-State   | International   |   Total |
|-----------------------------------------------------------|------------|----------------|-----------------|---------|
| Total first-time, first-year (degree seeking) who applied |          0 |              0 |               0 |       0 |

## C2. Wait list
"""

        self.assertEqual(_values(clean(markdown, schema=SCHEMA_2023)).get("C.117"), "0")


if __name__ == "__main__":
    unittest.main()
