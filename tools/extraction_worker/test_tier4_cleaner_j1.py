from __future__ import annotations

import unittest

from tier4_cleaner import clean


class Tier4CleanerJ1Test(unittest.TestCase):
    def test_j1_disciplines_and_total_row_when_other_merges(self):
        markdown = """
## J1 Degrees conferred between July 1, 2023 and June 30, 2024

| Category                                                                                    | Diploma/Certificates   | Associate   | Bachelor's   | CIP 2020 Categories to Include   |
|---------------------------------------------------------------------------------------------|------------------------|-------------|--------------|----------------------------------|
| Agriculture                                                                                 | 24%                    | 5%          | 1%           | 01                               |
| Communication/journalism                                                                    |                        |             | 3%           | 09                               |
| Computer and information sciences                                                           | 2%                     |             | 10%          | 11                               |
| Homeland Security, law enforcement, firefighting, Public administration and social services |                        | 7%          | 11%          | 43                               |
| Social sciences                                                                             |                        |             | 1%           | 45                               |
| Health professions and related programs                                                     | 35%                    | 13%         | 10%          | 51                               |
| Business/marketing                                                                          | 30%                    |             | 20%          | 52                               |
| Other TOTAL (should = 100%)                                                                 | 100.00%                | 100.00%     | 100.00%      |                                  |
"""

        values = clean(markdown)

        self.assertEqual(values["J.101"]["value"], "24")
        self.assertEqual(values["J.141"]["value"], "5")
        self.assertEqual(values["J.181"]["value"], "1")
        self.assertEqual(values["J.185"]["value"], "3")
        self.assertEqual(values["J.107"]["value"], "2")
        self.assertEqual(values["J.187"]["value"], "10")
        self.assertEqual(values["J.168"]["value"], "7")
        self.assertEqual(values["J.208"]["value"], "11")
        self.assertEqual(values["J.210"]["value"], "1")
        self.assertEqual(values["J.136"]["value"], "35")
        self.assertEqual(values["J.176"]["value"], "13")
        self.assertEqual(values["J.216"]["value"], "10")
        self.assertEqual(values["J.137"]["value"], "30")
        self.assertEqual(values["J.217"]["value"], "20")
        self.assertEqual(values["J.140"]["value"], "100.00")
        self.assertEqual(values["J.180"]["value"], "100.00")
        self.assertEqual(values["J.220"]["value"], "100.00")
        self.assertNotIn("J.139", values)
        self.assertNotIn("J.179", values)
        self.assertNotIn("J.219", values)


    def test_j1_header_in_first_row_under_a_subtitle_or_page_banner(self):
        # Ferris State 2023-24. The converter put the column names in the
        # first data row, made a heading of the subtitle under "J.", and made
        # another of the page banner above the half of the table that
        # continues on the next page. Neither heading names section J.
        markdown = """
## J. Disciplinary areas of DEGREES CONFERRED

## Degrees conferred between July 1, 2022 and June 30, 2023

For each of the following discipline areas, provide the percentage of diplomas/certificates, associate, and bachelor's degrees awarded.

| Category                           | Diploma/ Certificates   | Associate   | Bachelor's   | CIP 2020 Categories to Include   |
|------------------------------------|-------------------------|-------------|--------------|----------------------------------|
| Agriculture                        | 0.00                    | 0.00        | 0.00         | 01                               |
| Communication technologies         | 0.00                    | 1.90        | 4.51         | 10                               |
| Computer and information sciences  | 3.22                    | 1.10        | 4.00         | 11                               |
| Engineering technologies           | 25.70                   | 19.85       | 12.98        | 15                               |

## Common Data Set 2023-2024

| Category                                 | Diploma/ Certificates   | Associate   | Bachelor's   |   CIP 2020 Categories to Include |
|------------------------------------------|-------------------------|-------------|--------------|----------------------------------|
| Science technologies                     | 0.80                    | 0.79        | 0.00         |                               41 |
| Health professions and related programs  | 34.21                   | 41.26       | 14.29        |                               51 |
"""

        values = clean(markdown)

        self.assertEqual(values["J.101"]["value"], "0.00")
        self.assertEqual(values["J.146"]["value"], "1.90")
        self.assertEqual(values["J.186"]["value"], "4.51")
        self.assertEqual(values["J.107"]["value"], "3.22")
        self.assertEqual(values["J.147"]["value"], "1.10")
        self.assertEqual(values["J.187"]["value"], "4.00")
        self.assertEqual(values["J.111"]["value"], "25.70")
        self.assertEqual(values["J.126"]["value"], "0.80")
        self.assertEqual(values["J.166"]["value"], "0.79")
        self.assertEqual(values["J.136"]["value"], "34.21")
        self.assertEqual(values["J.176"]["value"], "41.26")
        self.assertEqual(values["J.216"]["value"], "14.29")
        # The CIP code column is never a value.
        self.assertNotIn("41", {v["value"] for k, v in values.items() if k.startswith("J.")})

    def test_first_row_naming_award_levels_without_cip_is_not_j1(self):
        # Outside section J, a header the converter moved into the first row
        # counts as J1's only when it also has the CIP column.
        markdown = """
## Common Data Set 2023-2024

| Category          | Diploma/ Certificates   | Associate   | Bachelor's   | Catalog 2020   |
|-------------------|-------------------------|-------------|--------------|----------------|
| Agriculture       | 3                       | 12          | 30           | 01             |
| Education         | 1                       | 5           | 9            | 13             |
"""

        values = clean(markdown)

        self.assertEqual([k for k in values if k.startswith("J.")], [])

    def test_first_row_naming_two_award_levels_and_cip_is_not_j1_without_heading(self):
        # Away from a section J heading the first row must name all three
        # award levels; two plus a CIP column is not enough.
        markdown = """
## Common Data Set 2023-2024

| Category          | Associate   | Bachelor's   | CIP 2020 Categories to Include   |
|-------------------|-------------|--------------|----------------------------------|
| Agriculture       | 12          | 30           | 01                               |
| Education         | 5           | 9            | 13                               |
"""

        values = clean(markdown)

        self.assertEqual([k for k in values if k.startswith("J.")], [])

    def test_award_level_merged_with_cip_column_is_not_read(self):
        # The converter merged the Bachelor's header with the CIP header, so
        # the cell under it may hold the code. Diploma and Associate are
        # still their own columns.
        markdown = """
## J1 Degrees conferred between July 1, 2022 and June 30, 2023

| Category          | Diploma/ Certificates   | Associate   | Bachelor's CIP 2020 Categories to Include   |
|-------------------|-------------------------|-------------|---------------------------------------------|
| Agriculture       | 4.00                    | 6.00        | 01                                          |
| Education         | 1.50                    | 2.50        | 13                                          |
"""

        values = clean(markdown)

        self.assertEqual(values["J.101"]["value"], "4.00")
        self.assertEqual(values["J.141"]["value"], "6.00")
        self.assertEqual(values["J.109"]["value"], "1.50")
        self.assertEqual(values["J.149"]["value"], "2.50")
        self.assertNotIn("J.181", values)
        self.assertNotIn("J.189", values)

    def test_j1_header_with_cip_and_year_printed_as_one_word(self):
        markdown = """
## Common Data Set 2023-2024

| Category          | Diploma/ Certificates   | Associate   | Bachelor's   | CIP2020 Categories to Include   |
|-------------------|-------------------------|-------------|--------------|---------------------------------|
| Agriculture       | 4.00                    | 6.00        | 8.00         | 01                              |
"""

        values = clean(markdown)

        self.assertEqual(values["J.181"]["value"], "8.00")

if __name__ == "__main__":
    unittest.main()
