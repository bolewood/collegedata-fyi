"""B1 rollup rows of older forms cite IPEDS inside the label."""
from __future__ import annotations

import unittest

from tier4_cleaner import clean


def _values(result: dict[str, dict]) -> dict[str, str]:
    return {qn: str(entry["value"]) for qn, entry in result.items()}


class RollupWithIpedsCitationTest(unittest.TestCase):
    def test_a_rollup_count_follows_the_ipeds_citation_in_its_label(self):
        text = (
            "B1. Institutional Enrollment - Men and Women\n"
            "Total all undergraduates (2002 IPEDS sum of lines 8 and 22, cols. 15 and 16):      14,270\n"
            "Total all graduate and professional students (2002 IPEDS sum of lines 14 and 28,    3,315\n"
            "GRAND TOTAL ALL STUDENTS (2002 IPEDS line 29, sum of cols. 15 and 16):             17,585\n"
            "B2. Enrollment by Racial/Ethnic Category\n"
        )

        values = _values(clean("", supplemental_text=text))

        self.assertEqual(values.get("B.176"), "14270")
        self.assertEqual(values.get("B.177"), "3315")
        self.assertEqual(values.get("B.178"), "17585")

    def test_a_rollup_count_is_the_one_right_after_the_citation(self):
        # Cal Poly 1999-00: two rollups share a line.
        text = (
            "B1. Institutional Enrollment - Men and Women\n"
            "Total all undergraduates (IPEDS sum of lines 8 and 22, cols. 15 and 16): 15,503 "
            "Total all graduate and professional students (IPEDS sum of lines 14 and 28, cols. 15 and 16): 967\n"
            "GRAND TOTAL ALL STUDENTS (IPEDS line 29, sum of cols. 15 and 16): 16,470\n"
            "B2. Enrollment by Racial/Ethnic Category\n"
        )

        values = _values(clean("", supplemental_text=text))

        self.assertEqual(values.get("B.176"), "15503")
        self.assertEqual(values.get("B.178"), "16470")

    def test_a_bracket_after_the_count_is_not_a_citation(self):
        # Williams 2025-26 prints an FTE note to the right of each rollup.
        text = (
            "B1. Institutional Enrollment - Men and Women\n"
            "Total all undergraduates      2,101      Undergraduate FTE (FT 2078 + 1/3 PT)\n"
            "Total all graduate               49      Total FTE (Undergraduate 2127)\n"
            "GRAND TOTAL ALL STUDENTS      2,150\n"
            "B2. Enrollment by Racial/Ethnic Category\n"
        )

        values = _values(clean("", supplemental_text=text))

        self.assertEqual(values.get("B.176"), "2101")
        self.assertEqual(values.get("B.177"), "49")
        self.assertEqual(values.get("B.178"), "2150")

    def test_a_citation_after_the_count_leaves_the_count(self):
        for line in (
            "Total all undergraduates: 14,270 (2002 IPEDS line 8)",
            "Total all undergraduates   14,270   (excludes 120 auditors)",
            "Total all undergraduates   14,270   1,000 (see note 2)",
        ):
            text = (
                "B1. Institutional Enrollment - Men and Women\n"
                f"{line}\n"
                "B2. Enrollment by Racial/Ethnic Category\n"
            )
            with self.subTest(line=line):
                self.assertEqual(
                    _values(clean("", supplemental_text=text)).get("B.176"), "14270"
                )


if __name__ == "__main__":
    unittest.main()
