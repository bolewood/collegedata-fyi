from __future__ import annotations

import unittest

from tier4_cleaner import clean


class Tier4CleanerC9Test(unittest.TestCase):
    def test_c9_submission_rates_decimal_table_without_headers(self):
        markdown = """
## C9 Percent and number of first-time, first-year students enrolled in Fall 2024 who submitted national standardized (SAT/ACT) test scores.

Submitting SAT Scores Submitting ACT Scores

| 50.3%   |   857 |
|---------|-------|
| 19.0%   |   324 |
"""

        values = clean(markdown)

        self.assertEqual(values["C.901"]["value"], "50.3")
        self.assertEqual(values["C.902"]["value"], "19.0")
        self.assertEqual(values["C.903"]["value"], "857")
        self.assertEqual(values["C.904"]["value"], "324")

    def test_c9_submission_rates_labels_separated_from_percent_table(self):
        markdown = """
## C9 Percent and number of first-time, first-year students enrolled in Fall 2025 who submitted national standardized (SAT/ACT) test scores.

Submitting SAT Scores Submitting ACT Scores

For each assessment listed below, report the score that represents the 25th percentile.

| Percent   | Number   |
|-----------|----------|
| 56%       | 1,022    |
| 21%       | 385      |
"""

        values = clean(markdown)

        self.assertEqual(values["C.901"]["value"], "56")
        self.assertEqual(values["C.902"]["value"], "21")
        self.assertEqual(values["C.903"]["value"], "1022")
        self.assertEqual(values["C.904"]["value"], "385")

    def test_c9_combined_submission_and_percentile_table(self):
        markdown = """
C9. Percent and number of first-time, first-year students enrolled in Fall 2024 who submitted national standardized (SAT/ACT) test scores.

|       | %Submitting   |   Number |                                        | Percentiles 25th   | 50th   | 75th   |
|-------|---------------|----------|----------------------------------------|--------------------|--------|--------|
| SAT I | 33%           |     1083 | SAT Evidence-Based Reading and Writing | 690                | 720    | 750    |
|       |               |          | SAT Math                               | 730                | 760    | 780    |
| ACT   | 10%           |      330 | SAT Composite                          | 1430               | 1470   | 1510   |
|       |               |          | ACT Composite                          | 32                 | 33     | 34     |
|       |               |          | ACT English                            | 33                 | 35     | 35     |
|       |               |          | ACT Math                               | 29                 | 32     | 35     |
"""

        values = clean(markdown)

        self.assertEqual(values["C.901"]["value"], "33")
        self.assertEqual(values["C.902"]["value"], "10")
        self.assertEqual(values["C.903"]["value"], "1083")
        self.assertEqual(values["C.904"]["value"], "330")
        self.assertEqual(values["C.905"]["value"], "1430")
        self.assertEqual(values["C.906"]["value"], "1470")
        self.assertEqual(values["C.907"]["value"], "1510")
        self.assertEqual(values["C.908"]["value"], "690")
        self.assertEqual(values["C.909"]["value"], "720")
        self.assertEqual(values["C.910"]["value"], "750")
        self.assertEqual(values["C.911"]["value"], "730")
        self.assertEqual(values["C.912"]["value"], "760")
        self.assertEqual(values["C.913"]["value"], "780")
        self.assertEqual(values["C.914"]["value"], "32")
        self.assertEqual(values["C.915"]["value"], "33")
        self.assertEqual(values["C.916"]["value"], "34")

    def test_c9_visual_ocr_layout_lines(self):
        markdown = """
C9. Percent and number of first-time, first-year students enrolled in Fall 2024 who submitted national standardized (SAT/ACT) test scores.

Percent Number
Submitting SAT Scores 11 1031
Submitting ACT Scores 18 1692

Assessment 25th Percentile 50th Percentile 75th Percentile
Score Score Score

SAT Composite 1130 1240 1340
Reading and Writing 560 620 670
SAT Math 560 620 680
ACT Composite 21 24 28
ACT Math 21 24 28
ACT English 20 24 29
ACT Science 21 24 27
ACT Reading 21 25 30
"""

        values = clean(markdown)

        self.assertEqual(values["C.901"]["value"], "11")
        self.assertEqual(values["C.902"]["value"], "18")
        self.assertEqual(values["C.903"]["value"], "1031")
        self.assertEqual(values["C.904"]["value"], "1692")
        self.assertEqual(values["C.905"]["value"], "1130")
        self.assertEqual(values["C.906"]["value"], "1240")
        self.assertEqual(values["C.907"]["value"], "1340")
        self.assertEqual(values["C.908"]["value"], "560")
        self.assertEqual(values["C.909"]["value"], "620")
        self.assertEqual(values["C.910"]["value"], "670")
        self.assertEqual(values["C.911"]["value"], "560")
        self.assertEqual(values["C.912"]["value"], "620")
        self.assertEqual(values["C.913"]["value"], "680")
        self.assertEqual(values["C.914"]["value"], "21")
        self.assertEqual(values["C.915"]["value"], "24")
        self.assertEqual(values["C.916"]["value"], "28")

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
