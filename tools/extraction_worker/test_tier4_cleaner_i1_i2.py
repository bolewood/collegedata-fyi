from __future__ import annotations

import unittest

from tier4_cleaner import clean


class Tier4CleanerI1I2Test(unittest.TestCase):
    def test_i1_faculty_and_i2_ratio_from_markdown_table(self):
        markdown = """
## I-1.

|       |                                                        | Full-Time | Part-Time | Total |
| ----- | ------------------------------------------------------ | --------- | --------- | ----- |
| A     | Total number of instructional faculty                  | 298       | 518       | 816   |
| B     | Total number who are members of minority groups        | 90        | 110       | 200   |
| C     | Total number who are women                             | 152       | 241       | 393   |
| D     | Total number who are men                               | 146       | 277       | 423   |
| E     | Total number who are nonresidents (international)      | 3         | 0         | 3     |
| F     | Total number with doctorate, or other terminal degree  | 213       |           | 213   |
| G     | Total number whose highest degree is a master's        | 52        |           | 52    |

## I-2. Student to Faculty Ratio

Report the Fall 2024 ratio of full-time equivalent students to full-time equivalent
instructional faculty.

| Fall 2024 Student to Faculty ratio   | 18   | to   | (based on   |   8660 | students   |
| ------------------------------------ | ---- | ---- | ----------- | ------ | ---------- |
| and                                  | and  | and  | and         |    470 | faculty).  |
"""

        values = clean(markdown)

        self.assertEqual(values["I.101"]["value"], "298")
        self.assertEqual(values["I.111"]["value"], "518")
        self.assertEqual(values["I.121"]["value"], "816")
        self.assertEqual(values["I.105"]["value"], "3")
        self.assertEqual(values["I.115"]["value"], "0")
        self.assertEqual(values["I.125"]["value"], "3")
        self.assertEqual(values["I.201"]["value"], "18")
        self.assertEqual(values["I.202"]["value"], "8660")
        self.assertEqual(values["I.203"]["value"], "470")

    def test_i3_class_size_when_docling_shifts_label_to_last_cell(self):
        markdown = """
## I-3. Undergraduate Class Size

## Undergraduate Class Size (provide numbers)

| 2-9   |     | 10-19   | 20-29   | 30-39   | 40-49   | 50-99   | 100+   | Total               |
|-------|-----|---------|---------|---------|---------|---------|--------|---------------------|
| 53    | 323 | 669     | 224     | 59      | 3       |         | 1331   | CLASS SECTIONS      |
| 2-9   |     | 10-19   | 20-29   | 30-39   | 40-49   | 50-99   | 100+   | Total               |
| 83    | 123 | 132     |         |         |         |         | 338    | CLASS SUB- SECTIONS |
"""

        values = clean(markdown)

        self.assertEqual(values["I.301"]["value"], "53")
        self.assertEqual(values["I.302"]["value"], "323")
        self.assertEqual(values["I.303"]["value"], "669")
        self.assertEqual(values["I.304"]["value"], "224")
        self.assertEqual(values["I.305"]["value"], "59")
        self.assertEqual(values["I.306"]["value"], "3")
        self.assertNotIn("I.307", values)
        self.assertEqual(values["I.308"]["value"], "1331")
        self.assertEqual(values["I.309"]["value"], "83")
        self.assertEqual(values["I.310"]["value"], "123")
        self.assertEqual(values["I.311"]["value"], "132")
        self.assertNotIn("I.312", values)
        self.assertNotIn("I.313", values)
        self.assertNotIn("I.314", values)
        self.assertNotIn("I.315", values)
        self.assertEqual(values["I.316"]["value"], "338")

    def test_i2_layout_fallback_does_not_treat_fall_year_as_student_count(self):
        supplemental = """
I-2. Student to Faculty Ratio
     Report the Fall 2024 ratio of full-time equivalent students (full-time plus 1/3 part time)
     to full-time equivalent instructional faculty.

       Fall 2024 Student to Faculty ratio        18       to 1
       (based on      8660       students and       470       faculty).
"""

        values = clean(
            "## I-2. Student to Faculty Ratio\n\n"
            "Report the Fall 2024 ratio of full-time equivalent students.",
            supplemental_text=supplemental,
        )

        self.assertEqual(values["I.201"]["value"], "18")
        self.assertEqual(values["I.202"]["value"], "8660")
        self.assertEqual(values["I.203"]["value"], "470")


if __name__ == "__main__":
    unittest.main()
