from __future__ import annotations

import unittest

from tier4_cleaner import SchemaIndex, clean, schema_path_for_year

H1 = """
## H1. Aid Awarded to Enrolled Undergraduates

- [x] x Federal methodology (FM)

|                                                                          | Need-based (Include non-need-based aid use to meet need.) | Non-need-based (Exclude non-need-based aid use to meet need.) |
|--------------------------------------------------------------------------|-----------------------------------------------------------|---------------------------------------------------------------|
| Federal                                                                  | $938,221                                                  | $1,000                                                        |
| State all states, not only the state in which your institution is located | $484,409                                                  | $2,000                                                        |
| Total Scholarships/Grants                                                | $22,510,625                                               | $364,847                                                      |
| Parent Loans                                                             | $108,260                                                  | $1,395,525                                                    |
| Tuition Waivers                                                          | $166,040                                                  | $468,322                                                      |
| Athletic Awards                                                          | $5,000                                                    | $6,000                                                        |

## H2. Number of Enrolled Students Awarded Aid
"""


def values_for(year: str) -> dict[str, str]:
    schema = SchemaIndex(schema_path_for_year(year))
    return {qn: rec["value"] for qn, rec in clean(H1, schema=schema).items()}


class Tier4CleanerH1TemplateYearTest(unittest.TestCase):
    def test_2025_26_numbering_is_unchanged(self):
        values = values_for("2025-26")
        self.assertEqual(values["H.105"], "938221")
        self.assertEqual(values["H.117"], "1000")
        self.assertEqual(values["H.106"], "484409")
        self.assertEqual(values["H.109"], "22510625")
        self.assertEqual(values["H.114"], "108260")
        self.assertEqual(values["H.116"], "5000")
        self.assertEqual(values["H.127"], "6000")

    def test_2024_25_and_2023_24_number_every_h1_row_one_higher(self):
        # In these forms H.105 is the "Both FM and IM" option and Federal
        # need-based aid is H.106; the last row, Athletic Awards non-need, is
        # H.128.
        for year in ("2024-25", "2023-24"):
            with self.subTest(year=year):
                values = values_for(year)
                self.assertEqual(values["H.106"], "938221")
                self.assertEqual(values["H.118"], "1000")
                self.assertEqual(values["H.107"], "484409")
                self.assertEqual(values["H.119"], "2000")
                self.assertEqual(values["H.110"], "22510625")
                self.assertEqual(values["H.115"], "108260")
                self.assertEqual(values["H.126"], "1395525")
                self.assertEqual(values["H.116"], "166040")
                self.assertEqual(values["H.117"], "5000")
                self.assertEqual(values["H.128"], "6000")
                # Nothing is left on the methodology option.
                self.assertNotIn("H.105", values)

    def test_reporting_year_text_is_not_written_to_a_tick_box(self):
        markdown = H1.replace(
            "- [x] x Federal methodology (FM)",
            "2023-2024 Estimated\n\n- [x] x Federal methodology (FM)",
        )
        newer = clean(markdown, schema=SchemaIndex(schema_path_for_year("2025-26")))
        self.assertEqual(newer["H.101"]["value"], "2023-2024 estimated")
        older = clean(markdown, schema=SchemaIndex(schema_path_for_year("2024-25")))
        self.assertNotIn("H.101", older)

    def test_methodology_tick_moves_with_its_question(self):
        self.assertEqual(values_for("2025-26").get("H.102"), "X")
        older = values_for("2024-25")
        self.assertEqual(older.get("H.103"), "X")
        self.assertNotIn("H.102", older)


if __name__ == "__main__":
    unittest.main()
