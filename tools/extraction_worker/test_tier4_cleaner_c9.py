from __future__ import annotations

import unittest

from tier4_cleaner import clean


class Tier4CleanerC9Test(unittest.TestCase):
    def test_c9_split_submission_labels_and_blank_sat_composite(self):
        markdown = """
## C9 Percent and number of first-time, first-year students enrolled in Fall 2024 who submitted national standardized (SAT/ACT) test scores.

Submitting SAT Scores

Submitting ACT Scores

| Percent   |   Number |
|-----------|----------|
| 19%       |      340 |
| 2%        |       35 |

| Assessment                             |   25th Percentile |   50th Percentile |   75th Percentile |
|----------------------------------------|-------------------|-------------------|-------------------|
| SAT Composite                          |                   |                   |                   |
| SAT Evidence-Based Reading and Writing |               520 |               570 |               620 |
| SAT Math                               |               520 |               570 |               620 |
| ACT Composite                          |                20 |                25 |                28 |

| Score Range          | SAT Evidence- Based Reading and Writing   | SAT Math   |
|----------------------|-------------------------------------------|------------|
| 700-800              | 3%                                        | 4%         |
| 600-699              | 35%                                       | 31%        |
| 500-599              | 49%                                       | 51%        |
| 400-499              | 11%                                       | 12%        |
| 300-399              | 2%                                        | 2%         |
| 200-299              |                                           |            |
| Totals should = 100% | 100.00%                                   | 100.00%    |

| Score Range   | SAT Composite   |
|---------------|-----------------|
| 1400-1600     | 3%              |
| 1200-1399     | 31%             |
| 1000-1199     | 54%             |

| 800-999              | 11%     |
|----------------------|---------|
| 600-799              | 1%      |
| 400-599              |         |
| Totals should = 100% | 100.00% |

| Score Range          | ACT Composite   | ACT Math   |
|----------------------|-----------------|------------|
| 30-36                | 9%              |            |
| 24-29                | 46%             |            |
| 18-23                | 26%             |            |
| 12-17                | 17%             |            |
| 6-11                 | 3%              |            |
| Below 6              |                 |            |
| Totals should = 100% | 100.00%         | 0.00%      |
"""

        values = clean(markdown)

        self.assertEqual(values["C.901"]["value"], "19")
        self.assertEqual(values["C.902"]["value"], "2")
        self.assertEqual(values["C.903"]["value"], "340")
        self.assertEqual(values["C.904"]["value"], "35")
        self.assertNotIn("C.905", values)
        self.assertNotIn("C.906", values)
        self.assertNotIn("C.907", values)
        self.assertEqual(values["C.908"]["value"], "520")
        self.assertEqual(values["C.909"]["value"], "570")
        self.assertEqual(values["C.910"]["value"], "620")
        self.assertEqual(values["C.911"]["value"], "520")
        self.assertEqual(values["C.912"]["value"], "570")
        self.assertEqual(values["C.913"]["value"], "620")
        self.assertEqual(values["C.914"]["value"], "20")
        self.assertEqual(values["C.915"]["value"], "25")
        self.assertEqual(values["C.916"]["value"], "28")
        self.assertEqual(values["C.932"]["value"], "3")
        self.assertEqual(values["C.933"]["value"], "35")
        self.assertEqual(values["C.938"]["value"], "100.00")
        self.assertEqual(values["C.939"]["value"], "4")
        self.assertEqual(values["C.940"]["value"], "31")
        self.assertEqual(values["C.945"]["value"], "100.00")
        self.assertEqual(values["C.946"]["value"], "3")
        self.assertEqual(values["C.947"]["value"], "31")
        self.assertEqual(values["C.948"]["value"], "54")
        self.assertEqual(values["C.949"]["value"], "11")
        self.assertEqual(values["C.950"]["value"], "1")
        self.assertNotIn("C.951", values)
        self.assertEqual(values["C.952"]["value"], "100.00")
        self.assertEqual(values["C.953"]["value"], "9")
        self.assertEqual(values["C.954"]["value"], "46")
        self.assertEqual(values["C.955"]["value"], "26")
        self.assertEqual(values["C.956"]["value"], "17")
        self.assertEqual(values["C.957"]["value"], "3")
        self.assertNotIn("C.958", values)
        self.assertEqual(values["C.959"]["value"], "100.00")

    def test_c9_percentile_table_uses_header_order(self):
        markdown = """
## C9 Percent and number of first-time, first-year students enrolled in Fall 2024 who submitted national standardized (SAT/ACT) test scores.

| Assessment    | 25th Percentile | 75th Percentile | 50th Percentile | Average (Mean) |
|---------------|-----------------|-----------------|-----------------|----------------|
| SAT Composite | 1310            | 1490            | 1410            | 1388           |
| ACT Composite | 28              | 33              | 32              | 31             |
"""

        values = clean(markdown)

        self.assertEqual(values["C.905"]["value"], "1310")
        self.assertEqual(values["C.906"]["value"], "1410")
        self.assertEqual(values["C.907"]["value"], "1490")
        self.assertEqual(values["C.914"]["value"], "28")
        self.assertEqual(values["C.915"]["value"], "32")
        self.assertEqual(values["C.916"]["value"], "33")

    def test_c9_percentile_schema_fixed_lines_skip_totals(self):
        markdown = """
## C9 First-time, first-year students submitted test scores

C905 SAT Composite: 25th Percentile 1410
C906 SAT Composite: 50th Percentile 1450
C907 SAT Composite: 75th Percentile 1490
C914 ACT Composite: 25th Percentile 32
C915 ACT Composite: 50th Percentile 33
C916 ACT Composite: 75th Percentile 34
C917 ACT Math: 25th Percentile 100.00
"""

        values = clean(markdown)

        self.assertEqual(values["C.905"]["value"], "1410")
        self.assertEqual(values["C.906"]["value"], "1450")
        self.assertEqual(values["C.907"]["value"], "1490")
        self.assertEqual(values["C.914"]["value"], "32")
        self.assertEqual(values["C.915"]["value"], "33")
        self.assertEqual(values["C.916"]["value"], "34")
        self.assertNotIn("C.917", values)

    def test_c9_percentile_layout_rows_without_codes(self):
        markdown = """
## C9 Percent and number of first-time, first-year students enrolled in Fall 2024 who submitted national standardized (SAT/ACT) test scores.

Assessment 25th Percentile 50th Percentile 75th Percentile
SAT Composite (400 - 1600) 1370 1440 1500
ACT Composite (0 - 36) 31 32 34
"""

        values = clean(markdown)

        self.assertEqual(values["C.905"]["value"], "1370")
        self.assertEqual(values["C.906"]["value"], "1440")
        self.assertEqual(values["C.907"]["value"], "1500")
        self.assertEqual(values["C.914"]["value"], "31")
        self.assertEqual(values["C.915"]["value"], "32")
        self.assertEqual(values["C.916"]["value"], "34")

    def test_c9_percentile_layout_rows_use_single_line_header_order(self):
        markdown = """
## C9 Percent and number of first-time, first-year students enrolled in Fall 2024 who submitted national standardized (SAT/ACT) test scores.

Assessment 25th Percentile 75th Percentile 50th Percentile Average (Mean)
SAT Composite 1310 1490 1410 1388
ACT Composite 28 33 32 31
"""

        values = clean(markdown)

        self.assertEqual(values["C.905"]["value"], "1310")
        self.assertEqual(values["C.906"]["value"], "1410")
        self.assertEqual(values["C.907"]["value"], "1490")
        self.assertEqual(values["C.914"]["value"], "28")
        self.assertEqual(values["C.915"]["value"], "32")
        self.assertEqual(values["C.916"]["value"], "33")


if __name__ == "__main__":
    unittest.main()
