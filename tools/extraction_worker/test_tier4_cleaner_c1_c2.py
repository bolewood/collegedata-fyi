from __future__ import annotations

import unittest
from pathlib import Path

from tier4_cleaner import SchemaIndex, clean

REPO_ROOT = Path(__file__).resolve().parents[2]


class Tier4CleanerC1C2Test(unittest.TestCase):
    def test_c1_compact_gender_columns(self):
        markdown = """
## C1. First-time, first-year students admissions statistics

|                    |    Men |   Women |   Another Gender |   Unknown |   Total |
|--------------------|--------|---------|------------------|-----------|---------|
| Applied            | 30,456 |  44,822 |            3,479 |        12 |  78,769 |
| Admitted           |  3,492 |   4,975 |              278 |         4 |   8,749 |
| Full-time enrolled |  1,267 |   1,887 |              113 |         1 |   3,268 |
| Part-time enrolled |      0 |       0 |                0 |         0 |       0 |
"""

        values = clean(
            markdown,
            schema=SchemaIndex(REPO_ROOT / "schemas" / "cds_schema_2024_25.json"),
        )

        self.assertEqual(values["C.101"]["value"], "30456")
        self.assertEqual(values["C.102"]["value"], "44822")
        self.assertEqual(values["C.103"]["value"], "3479")
        self.assertEqual(values["C.104"]["value"], "12")
        self.assertEqual(values["C.105"]["value"], "3492")
        self.assertEqual(values["C.106"]["value"], "4975")
        self.assertEqual(values["C.107"]["value"], "278")
        self.assertEqual(values["C.108"]["value"], "4")
        self.assertEqual(values["C.109"]["value"], "1267")
        self.assertEqual(values["C.111"]["value"], "1887")
        self.assertEqual(values["C.113"]["value"], "113")
        self.assertEqual(values["C.115"]["value"], "1")
        self.assertEqual(values["C.117"]["value"], "78769")
        self.assertEqual(values["C.118"]["value"], "8749")
        self.assertEqual(values["C.119"]["value"], "3268")

    def test_c1_visual_ocr_layout_lines(self):
        markdown = """
FIRST-TIME, FIRST-YEAR STUDENT APPLICANTS TOTAL
Total first-time, first-year men who applied 25635
Total first-time, first-year women who applied 32704
Total first-time, first-year of another gender who applied
Total first-time, first-year of unknown gender who applied

FIRST-TIME, FIRST-YEAR STUDENT ADMITS TOTAL
Total first-time, first-year men who were admitted 21436
Total first-time, first-year women who were admitted 28816

FIRST-TIME, FIRST-YEAR STUDENT ENROLLEES TOTAL
Total first-time, first-year men who enrolled 3714
Total first-time, first-year women who enrolled 5526

FIRST-TIME, FIRST-YEAR STUDENT ENROLLEES BY STATUS TOTAL
Total full-time, first-time, first-year men who enrolled 3528
Total part-time, first-time, first-year men who enrolled 186
Total full-time, first-time, first-year women who enrolled 5280
Total part-time, first-time, first-year women who enrolled 246

FIRST-TIME, FIRST-YEAR STUDENT APPLICANTS IN-STATE OUT.OF- INTERNATIONAL] UNKNOWN | TOTAL
Total first-time, first-year (degree-seeking) who applied 15064 34044 9231 58339
Total first-time, first-year (degree-seeking) who were admitted} 13619 31303 5330 50252
Total first-time, first-year (degree-seeking) enrolled 4983 3914 343 9240
"""

        values = clean(
            markdown,
            schema=SchemaIndex(REPO_ROOT / "schemas" / "cds_schema_2024_25.json"),
        )

        self.assertEqual(values["C.101"]["value"], "25635")
        self.assertEqual(values["C.102"]["value"], "32704")
        self.assertEqual(values["C.105"]["value"], "21436")
        self.assertEqual(values["C.106"]["value"], "28816")
        self.assertEqual(values["C.109"]["value"], "3528")
        self.assertEqual(values["C.110"]["value"], "186")
        self.assertEqual(values["C.111"]["value"], "5280")
        self.assertEqual(values["C.112"]["value"], "246")
        self.assertEqual(values["C.117"]["value"], "58339")
        self.assertEqual(values["C.118"]["value"], "50252")
        self.assertEqual(values["C.119"]["value"], "9240")
        self.assertEqual(values["C.120"]["value"], "15064")
        self.assertEqual(values["C.123"]["value"], "34044")
        self.assertEqual(values["C.126"]["value"], "9231")
        self.assertEqual(values["C.122"]["value"], "4983")
        self.assertEqual(values["C.125"]["value"], "3914")
        self.assertEqual(values["C.128"]["value"], "343")

    def test_c2_waitlist_policy_and_counts_from_layout(self):
        supplemental = """
C2   First-time, first-year wait-listed students
     Students who met admission requirements but whose final admission was contingent on space
     availability

                                                                       Yes          No
     Do you have a policy of placing students on a waiting list?        x

     If yes, please answer the questions below for Fall 2024 admissions:

                                WAITING LIST                                      TOTAL
     Number of qualified applicants offered a place on waiting list:               998
     Number accepting a place on the waiting list:                                 344
     Number of wait-listed students admitted:                                      157

C3   High school completion requirement
"""

        values = clean("", supplemental_text=supplemental)

        self.assertEqual(values["C.201"]["value"], "Yes")
        self.assertEqual(values["C.202"]["value"], "998")
        self.assertEqual(values["C.203"]["value"], "344")
        self.assertEqual(values["C.204"]["value"], "157")


if __name__ == "__main__":
    unittest.main()
