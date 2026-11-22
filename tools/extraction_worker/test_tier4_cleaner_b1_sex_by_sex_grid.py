"""B1 printed as a grid with one pair of full-time / part-time columns per
sex: the 2023-24 CDS workbook (three sexes) and its 2024-25 successor (four).
"""
from __future__ import annotations

import unittest
from pathlib import Path

from tier4_cleaner import SchemaIndex, _b1_gender_major_columns, clean

REPO_ROOT = Path(__file__).resolve().parents[2]
SCHEMA_2023 = SchemaIndex(REPO_ROOT / "schemas" / "cds_schema_2023_24.json")


def _values(result: dict[str, dict]) -> dict[str, str]:
    return {qn: str(entry["value"]) for qn, entry in result.items()}


B1_HEADER = """\
B1. Institutional Enrollment
Provide numbers of students for each of the following categories.
                                                    Men                     Women                Another Gender
                                          Full Time     Part Time     Full Time     Part Time     Full Time    Part Time
                                         Enrollment    Enrollment    Enrollment    Enrollment    Enrollment   Enrollment
                                                              UNDERGRADUATE STUDENTS
"""

B1_FULL_ROWS = B1_HEADER + """\
    Degree-seeking, first-time, first-year
    students                                 3,100.0        48.0        2,694.0        17.0          0.0         0.0
    Other first-year, degree-seeking students  718.0        32.0          539.0        25.0          0.0         0.0
    All other degree-seeking undergraduate
    students                                 9,413.0       606.0        7,574.0       267.0          0.0         0.0
 Total degree-seeking undergraduate students  13,231.0     686.0       10,807.0       309.0          0.0         0.0
    All other undergraduates enrolled in credit
    courses                                     32.0        85.0           41.0       141.0          0.0         0.0
                 Total Undergraduate Students  13,263.0    771.0       10,848.0       450.0          0.0         0.0
                          Total of all undergraduate students enrolled                         25,332.0
                                                    Men                     Women                Another Gender
                                          Full Time     Part Time     Full Time     Part Time     Full Time    Part Time
                                         Enrollment    Enrollment    Enrollment    Enrollment    Enrollment   Enrollment
                                                                GRADUATE STUDENTS
    Degree-seeking, first-time                 497.0       151.0          531.0       148.0          0.0         0.0
    All other degree-seeking                 1,053.0       724.0        1,117.0       624.0          0.0         0.0
                      Total Graduate Students  1,550.0     875.0        1,648.0       772.0          0.0         0.0
                          Total of all graduate  students enrolled                              4,845.0
B2. Enrollment by Racial/Ethnic Category
"""


class WorkbookB1GridTest(unittest.TestCase):
    def test_column_sexes_come_from_the_header_above_the_load_line(self):
        self.assertEqual(
            _b1_gender_major_columns(B1_HEADER),
            ["Males", "Females", "Another Gender"],
        )

    def test_a_load_first_grid_is_not_taken_for_the_workbook(self):
        block = "B1\nFULL-TIME PART-TIME\nMen Women Men Women\n"

        self.assertEqual(_b1_gender_major_columns(block), [])

    def test_the_section_title_is_not_the_line_of_sexes(self):
        block = (
            "B1. Institutional Enrollment - Men and Women\n"
            "          Undergraduate              Graduate\n"
            "     Full-Time  Part-Time      Full-Time  Part-Time\n"
        )

        self.assertEqual(_b1_gender_major_columns(block), [])

    def test_each_sex_has_a_full_time_and_a_part_time_column(self):
        values = _values(clean("", schema=SCHEMA_2023, supplemental_text=B1_FULL_ROWS))

        expected = {
            # full-time men, women; part-time men, women
            "B.101": "3100", "B.102": "2694", "B.125": "48", "B.126": "17",
            "B.105": "718", "B.106": "539", "B.129": "32", "B.130": "25",
            "B.109": "9413", "B.110": "7574", "B.133": "606", "B.134": "267",
            "B.113": "13231", "B.114": "10807", "B.137": "686", "B.138": "309",
            "B.117": "32", "B.118": "41", "B.141": "85", "B.142": "141",
            "B.121": "13263", "B.122": "10848", "B.145": "771", "B.146": "450",
            "B.123": "0", "B.147": "0",
            "B.153": "497", "B.154": "531", "B.169": "151", "B.170": "148",
            "B.165": "1550", "B.166": "1648", "B.181": "875", "B.182": "772",
            "B.193": "25332", "B.194": "4845",
        }
        for qn, value in expected.items():
            self.assertEqual(values.get(qn), value, qn)

    def test_blank_rows_above_a_total_do_not_lend_it_their_labels(self):
        # A school with no graduate students leaves the rows blank; the sum
        # cells print 0.0 even though nothing else in the file has a decimal.
        text = B1_HEADER + """\
                 Total Undergraduate Students    445          14            471          18            0           0
                                                    Men                     Women                Another Gender
                                          Full Time     Part Time     Full Time     Part Time     Full Time    Part Time
                                                                GRADUATE STUDENTS
    Degree-seeking, first-time
    All other degree-seeking
    All other graduates enrolled in credit
    courses
                      Total Graduate Students    0.0         0.0           0.0         0.0          0.0         0.0
B2. Enrollment by Racial/Ethnic Category
"""

        values = _values(clean("", schema=SCHEMA_2023, supplemental_text=text))

        self.assertEqual(values.get("B.165"), "0")
        self.assertEqual(values.get("B.182"), "0")
        self.assertNotIn("B.161", values)
        self.assertNotIn("B.177", values)
        self.assertEqual(values.get("B.122"), "471")

    def test_a_truncated_heading_and_excel_characters_do_not_hide_the_grid(self):
        text = (
            B1_FULL_ROWS.replace("Institutional Enrollment", "Institutional Enrollmen")
            .replace(" ", "\u00a0")
            .replace("-", "\u2010")
        )

        values = _values(clean("", schema=SCHEMA_2023, supplemental_text=text))

        self.assertEqual(values.get("B.122"), "10848")
        self.assertEqual(values.get("B.145"), "771")


if __name__ == "__main__":
    unittest.main()
