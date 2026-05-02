from __future__ import annotations

from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))

from tier4_cleaner import SchemaIndex, clean


class Tier4CleanerC21C22Test(unittest.TestCase):
    def test_c21_c22_yes_no_from_multiline_layout_blocks(self):
        supplemental = """
C21              Early Decision
                                                                                                                                                                                                                                                       Yes                                          No
               Does your institution offer an early decision plan (an admission plan
               that permits students to apply and be notified of an admission
               decision well in advance of the regular notification date and that asks                                                                                                                                                                                  x
               students to commit to attending if accepted) for first-time, first-year
               applicants for fall enrollment?

C22              Early action
                                                                                                                                                                                                                             Yes                                      No
               Do you have a nonbinding early action plan whereby students are
               notified of an admission decision well in advance of the regular                                                                                                                                                                                         x
               notification date but do not have to commit to attending your college?

                                                                                                                                                  Yes                                                                                                                                     No
               Is your early action plan a “restrictive” plan under which you limit
               students from applying to other early plans?

D. TRANSFER ADMISSION
"""

        values = clean("", supplemental_text=supplemental)

        self.assertEqual(values["C.2101"]["value"], "No")
        self.assertEqual(values["C.2201"]["value"], "No")
        self.assertNotIn("C.2206", values)

    def test_c21_2024_25_ed_counts_and_second_deadline(self):
        supplemental = """
C21              Early Decision
                                                                                                                                                                                                                                                       Yes                                          No
               Does your institution offer an early decision plan (an admission plan
               that permits students to apply and be notified of an admission
               decision well in advance of the regular notification date and that asks                                                                 x
               students to commit to attending if accepted) for first-time, first-year
               applicants for fall enrollment?

               First or only early decision plan closing date                            11/1
               First or only early decision plan notification date                       12/15
               Other early decision plan closing date                                    1/1
               Other early decision plan notification date                               2/15
               Number of early decision applications received by your institution         2,345
               Number of applicants admitted under early decision plan                    612

C22              Early action
"""

        values = clean(
            "",
            supplemental_text=supplemental,
            schema=SchemaIndex(Path("schemas/cds_schema_2024_25.json")),
        )

        self.assertEqual(values["C.2101"]["value"], "Yes")
        self.assertEqual(values["C.2104"]["value"], "1/1")
        self.assertEqual(values["C.2105"]["value"], "2/15")
        self.assertEqual(values["C.2106"]["value"], "2345")
        self.assertEqual(values["C.2107"]["value"], "612")

    def test_c21_2025_26_ed_counts_and_month_day_deadline(self):
        supplemental = """
C21              Early Decision
                                                                                                                                                                                                                                                       Yes                                          No
               Does your institution offer an early decision plan (an admission plan
               that permits students to apply and be notified of an admission
               decision well in advance of the regular notification date and that asks                                                                 x
               students to commit to attending if accepted) for first-time, first-year
               applicants for fall enrollment?

               Other early decision plan closing date: Month                             Jan
               Other early decision plan closing date: Day                               2
               Other early decision plan notification date: Month                        Feb
               Other early decision plan notification date: Day                          14
               Number of early decision applications received by your institution         1,204
               Number of applicants admitted under early decision plan                    318

C22              Early action
"""

        values = clean(
            "",
            supplemental_text=supplemental,
            schema=SchemaIndex(Path("schemas/cds_schema_2025_26.json")),
        )

        self.assertEqual(values["C.2101"]["value"], "Yes")
        self.assertEqual(values["C.2106"]["value"], "1")
        self.assertEqual(values["C.2107"]["value"], "2")
        self.assertEqual(values["C.2108"]["value"], "2")
        self.assertEqual(values["C.2109"]["value"], "14")
        self.assertEqual(values["C.2110"]["value"], "1204")
        self.assertEqual(values["C.2111"]["value"], "318")

    def test_c21_2025_26_docling_value_only_layout(self):
        markdown = """
## C21-C22: Early Decision and Early Action Plans

- C21 Early Decision

Yes

11/1 12/15

4,461 1,245

## C22 Early action

Yes

x

11/1 2/15

Does your institution offer an early decision plan?
Number of applicants admitted under early decision plan
Number of early decision applications received by your institution
"""

        values = clean(
            markdown,
            schema=SchemaIndex(Path("schemas/cds_schema_2025_26.json")),
        )

        self.assertEqual(values["C.2101"]["value"], "Yes")
        self.assertEqual(values["C.2110"]["value"], "4461")
        self.assertEqual(values["C.2111"]["value"], "1245")
        self.assertNotIn("C.2106", values)

    def test_c21_docling_split_yes_x_no_means_yes(self):
        markdown = """
## C21 Early Decision

Does your institution offer an early decision plan?

Yes

X

No

6013

1042

## C22 Early action
"""

        values = clean(
            markdown,
            schema=SchemaIndex(Path("schemas/cds_schema_2024_25.json")),
        )

        self.assertEqual(values["C.2101"]["value"], "Yes")
        self.assertEqual(values["C.2106"]["value"], "6013")
        self.assertEqual(values["C.2107"]["value"], "1042")

    def test_c21_2025_26_docling_separate_count_lines(self):
        markdown = """
## C21 Early Decision

Yes or No

Yes

12/1

1/15

124

77

## C22 Early action
"""

        values = clean(
            markdown,
            schema=SchemaIndex(Path("schemas/cds_schema_2025_26.json")),
        )

        self.assertEqual(values["C.2101"]["value"], "Yes")
        self.assertEqual(values["C.2110"]["value"], "124")
        self.assertEqual(values["C.2111"]["value"], "77")

    def test_c21_docling_vertical_yes_no_checkmark_means_no(self):
        markdown = """
## C21 Early Decision

Yes

No

✔

## C22 Early action
"""

        values = clean(markdown)

        self.assertEqual(values["C.2101"]["value"], "No")

    def test_c21_docling_vertical_yes_no_x_means_no(self):
        markdown = """
## C21 Early Decision

Yes

No

X

## C22 Early action
"""

        values = clean(markdown)

        self.assertEqual(values["C.2101"]["value"], "No")

    def test_c21_na_means_ed_not_offered(self):
        markdown = """
## C21 Early Decision

Yes or No

n/a

## C22 Early action

Yes or No

Yes

11/1

1/31

Yes or No

No
"""

        values = clean(markdown)

        self.assertEqual(values["C.2101"]["value"], "No")
        self.assertEqual(values["C.2201"]["value"], "Yes")
        self.assertEqual(values["C.2206"]["value"], "No")

    def test_c21_bare_yes_no_labels_do_not_mean_ed_offered(self):
        markdown = """
## C21 Early Decision

Yes

No

Does your institution offer an early decision plan?

## C22 Early action
"""

        values = clean(markdown)

        self.assertNotIn("C.2101", values)

    def test_c21_counts_imply_ed_offered_when_checkbox_is_ambiguous(self):
        markdown = """
## C21 Early Decision

Yes

No

X

11/1

12/10

1/3

2/11

7028

825

## C22 Early action
"""

        values = clean(
            markdown,
            schema=SchemaIndex(Path("schemas/cds_schema_2024_25.json")),
        )

        self.assertEqual(values["C.2101"]["value"], "Yes")
        self.assertEqual(values["C.2106"]["value"], "7028")
        self.assertEqual(values["C.2107"]["value"], "825")

    def test_c21_value_only_counts_skip_schema_years(self):
        markdown = """
## C21 Early Decision

Yes

No

X

## EARLY DECISION

2024

2025

847

359

338

## C22 Early action
"""

        values = clean(
            markdown,
            schema=SchemaIndex(Path("schemas/cds_schema_2025_26.json")),
        )

        self.assertEqual(values["C.2110"]["value"], "847")
        self.assertEqual(values["C.2111"]["value"], "359")


if __name__ == "__main__":
    unittest.main()
