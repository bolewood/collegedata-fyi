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


if __name__ == "__main__":
    unittest.main()
