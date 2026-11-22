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

    def test_rows_with_the_last_sex_blank_are_read_when_its_total_is_zero(self):
        text = B1_HEADER + """\
    Degree-seeking, first-time, first-year       243           0            395           0
    students
    Other first-year, degree-seeking students     75           3             66           1
 Total degree-seeking undergraduate students   1,028          38          1,574          29            0           0
                 Total Undergraduate Students  1,031          56          1,576          39            0           0
B2. Enrollment by Racial/Ethnic Category
"""

        values = _values(clean("", schema=SCHEMA_2023, supplemental_text=text))

        self.assertEqual(values.get("B.101"), "243")
        self.assertEqual(values.get("B.102"), "395")
        self.assertEqual(values.get("B.125"), "0")
        self.assertEqual(values.get("B.126"), "0")
        self.assertEqual(values.get("B.105"), "75")
        self.assertEqual(values.get("B.130"), "1")
        self.assertEqual(values.get("B.122"), "1576")
        self.assertEqual(values.get("B.146"), "39")

    def test_short_rows_are_dropped_when_no_full_row_shows_the_last_sex_at_zero(self):
        text = B1_HEADER + """\
    Other first-year, degree-seeking students     75           3             66           1
                 Total Undergraduate Students  1,031          56          1,576          39            4           1
B2. Enrollment by Racial/Ethnic Category
"""

        values = _values(clean("", schema=SCHEMA_2023, supplemental_text=text))

        self.assertNotIn("B.105", values)
        self.assertNotIn("B.129", values)
        self.assertEqual(values.get("B.122"), "1576")
        self.assertEqual(values.get("B.123"), "4")

    def test_a_short_row_larger_than_the_total_above_it_is_dropped(self):
        # A women's college that leaves the men's cells blank: 395 and 0 are
        # the women's, not the men's, and the men's total says so.
        text = B1_HEADER + """\
    Degree-seeking, first-time, first-year                                   395           0             0           0
    students
                 Total Undergraduate Students      0           0          1,576          39            0           0
B2. Enrollment by Racial/Ethnic Category
"""

        values = _values(clean("", schema=SCHEMA_2023, supplemental_text=text))

        self.assertNotIn("B.101", values)
        self.assertNotIn("B.102", values)
        self.assertEqual(values.get("B.122"), "1576")

    def test_zeros_on_a_detail_row_do_not_vouch_for_a_short_row(self):
        # Only the total row says the last sex is empty.
        text = B1_HEADER + """\
    Degree-seeking, first-time, first-year       243           0            395           0            0           0
    students
    Other first-year, degree-seeking students     75           3             66           1
                 Total Undergraduate Students  1,031          56          1,576          39            4           1
B2. Enrollment by Racial/Ethnic Category
"""

        values = _values(clean("", schema=SCHEMA_2023, supplemental_text=text))

        self.assertEqual(values.get("B.101"), "243")
        self.assertNotIn("B.105", values)
        self.assertNotIn("B.130", values)

    def test_a_truncated_heading_and_excel_characters_do_not_hide_the_grid(self):
        text = (
            B1_FULL_ROWS.replace("Institutional Enrollment", "Institutional Enrollmen")
            .replace(" ", "\u00a0")
            .replace("-", "\u2010")
        )

        values = _values(clean("", schema=SCHEMA_2023, supplemental_text=text))

        self.assertEqual(values.get("B.122"), "10848")
        self.assertEqual(values.get("B.145"), "771")


B1_FOUR_SEXES_WRAPPED = """\
B1. Institutional Enrollment - Men and Women
Provide numbers of students for each of the following categories.
                                        MEN                   WOMEN              ANOTHER GENDER               UNKNOWN
                               Full Time   Part Time    Full Time   Part Time   Full Time   Part Time    Full Time   Part Time
                              Enrollment  Enrollment   Enrollment  Enrollment  Enrollment   Enrollment  Enrollment  Enrollment
                                                                              UNDERGRADUATE STUDENTS
Degree-seeking, first-time,      4,708         10         4,882         11           0           0           0            0
first-year students
Other first-year, degree-         343           4          266          14           0           0           0            0
seeking students
All other degree-seeking         13,436        422       13,370        338           0           0           2            0
students
Total degree-seeking            18,487        436        18,518        363           0           0           2            0
undergraduate students
All other undergraduates            68           82           52           81           0            0            0            4
enrolled in credit courses
Total undergraduate               18,555        518         18,570        444           0            0            2            4
students
Total of all undergraduate students enrolled                                                                                 38,093
                                                                                        GRADUATE STUDENTS
Degree-seeking, first-time         1,357         189         1,243        221           0            0            1            0
All other degree-seeking           2,033        1,553        1,905       1,678          0            0            0            0
Total graduate students            3,390        1,742        3,148       1,899          0            0            1            0
B2. Enrollment by Racial/Ethnic Category
"""


class WorkbookB1WrappedLabelTest(unittest.TestCase):
    """Indiana 2024-25: four sexes, and each label wraps under its numbers."""

    @classmethod
    def setUpClass(cls):
        schema = SchemaIndex(REPO_ROOT / "schemas" / "cds_schema_2024_25.json")
        cls.values = _values(
            clean("", schema=schema, supplemental_text=B1_FOUR_SEXES_WRAPPED)
        )

    def test_a_label_cut_mid_phrase_takes_the_line_below(self):
        # "Degree-seeking, first-time," alone is the graduate row's label.
        self.assertEqual(self.values.get("B.101"), "4708")
        self.assertEqual(self.values.get("B.102"), "4882")
        self.assertEqual(self.values.get("B.125"), "10")
        self.assertEqual(self.values.get("B.105"), "343")
        self.assertEqual(self.values.get("B.130"), "14")

    def test_a_label_that_names_no_row_takes_the_line_below(self):
        self.assertEqual(self.values.get("B.117"), "68")
        self.assertEqual(self.values.get("B.144"), "4")
        self.assertEqual(self.values.get("B.121"), "18555")
        self.assertEqual(self.values.get("B.146"), "444")
        self.assertEqual(self.values.get("B.124"), "2")

    def test_a_complete_label_does_not_take_the_next_rows_label(self):
        self.assertEqual(self.values.get("B.109"), "13436")
        self.assertEqual(self.values.get("B.113"), "18487")
        self.assertEqual(self.values.get("B.153"), "1357")
        self.assertEqual(self.values.get("B.157"), "2033")
        self.assertEqual(self.values.get("B.193"), "38093")


if __name__ == "__main__":
    unittest.main()
