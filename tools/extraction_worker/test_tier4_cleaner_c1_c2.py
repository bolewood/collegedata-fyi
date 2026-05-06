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

    def test_c1_visual_ocr_compact_gender_columns(self):
        markdown = """
Applications
C1. First-time, first-year (freshman) students:

Men Women _| Another Un- Total
Gender reported
Total first-time, first-year (freshman) who applied: 21,054 12,942 871 0 34,867
Total first-time, first-year (freshman) who were admitted: 2,140 1,628 91 0 3,859
Total full-time, first-time first-year (freshman) who enrolled: 1,060 700 44 0 1804
Total part-time, first-time first-year (freshman) who enrolled: 0 0 0 0 0
"""

        values = clean(
            markdown,
            schema=SchemaIndex(REPO_ROOT / "schemas" / "cds_schema_2025_26.json"),
        )

        self.assertEqual(values["C.101"]["value"], "21054")
        self.assertEqual(values["C.102"]["value"], "12942")
        self.assertEqual(values["C.103"]["value"], "0")
        self.assertEqual(values["C.104"]["value"], "2140")
        self.assertEqual(values["C.105"]["value"], "1628")
        self.assertEqual(values["C.106"]["value"], "0")
        self.assertEqual(values["C.110"]["value"], "1060")
        self.assertEqual(values["C.112"]["value"], "700")
        self.assertEqual(values["C.114"]["value"], "0")
        self.assertEqual(values["C.116"]["value"], "34867")
        self.assertEqual(values["C.117"]["value"], "3859")
        self.assertEqual(values["C.118"]["value"], "1804")

    def test_c1_application_data_line_stacks(self):
        markdown = """
Common Data Set
Section C. First-time Freshman Admissions
2024-2025
University of Kansas

Application Data by Sex
Men
Women
Total
Applications
9,927
12,436
22,363
Admits
9,166
11,739
20,905
Enrolled
2,336
2,987
5,323
Full-time
2,309
2,960
5,269
Part-time
27
27
54

Application Data by Residency
In-State
Out-of-State
International
Total
Applications
7,334
14,503
526
22,363
Admits
6,919
13,495
491
20,905
Enrolled
2,928
2,300
95
5,323
"""

        values = clean(
            markdown,
            schema=SchemaIndex(REPO_ROOT / "schemas" / "cds_schema_2024_25.json"),
        )

        self.assertEqual(values["C.101"]["value"], "9927")
        self.assertEqual(values["C.102"]["value"], "12436")
        self.assertEqual(values["C.105"]["value"], "9166")
        self.assertEqual(values["C.106"]["value"], "11739")
        self.assertEqual(values["C.109"]["value"], "2336")
        self.assertEqual(values["C.110"]["value"], "27")
        self.assertEqual(values["C.111"]["value"], "2987")
        self.assertEqual(values["C.112"]["value"], "27")
        self.assertEqual(values["C.117"]["value"], "22363")
        self.assertEqual(values["C.118"]["value"], "20905")
        self.assertEqual(values["C.119"]["value"], "5323")
        self.assertEqual(values["C.120"]["value"], "7334")
        self.assertEqual(values["C.123"]["value"], "14503")
        self.assertEqual(values["C.126"]["value"], "526")
        self.assertEqual(values["C.122"]["value"], "2928")
        self.assertEqual(values["C.125"]["value"], "2300")
        self.assertEqual(values["C.128"]["value"], "95")

    def test_c1_tableau_layout_block_2025_schema(self):
        markdown = """
Common Data Set

C. FIRST-TIME, FIRST-YEAR ADMISSION

C1. Applications

Category                                   Unit load                               Males                                Females                                Unknown
Applied                                    All                                     5365                                   7096                                     9
Admitted                                   All                                      418                                    471                                     1
Enrolled                                   Full-Time                                199                                    221                                     1
                                           Part-Time
                                           All                                      199                                    221                                     1

C2. First-time, first-year wait-listed students
"""

        values = clean(
            markdown,
            schema=SchemaIndex(REPO_ROOT / "schemas" / "cds_schema_2025_26.json"),
        )

        self.assertEqual(values["C.101"]["value"], "5365")
        self.assertEqual(values["C.102"]["value"], "7096")
        self.assertEqual(values["C.103"]["value"], "9")
        self.assertEqual(values["C.104"]["value"], "418")
        self.assertEqual(values["C.105"]["value"], "471")
        self.assertEqual(values["C.106"]["value"], "1")
        self.assertEqual(values["C.107"]["value"], "199")
        self.assertEqual(values["C.108"]["value"], "221")
        self.assertEqual(values["C.109"]["value"], "1")
        self.assertEqual(values["C.110"]["value"], "199")
        self.assertEqual(values["C.112"]["value"], "221")
        self.assertEqual(values["C.114"]["value"], "1")
        self.assertEqual(values["C.116"]["value"], "12470")
        self.assertEqual(values["C.117"]["value"], "890")
        self.assertEqual(values["C.118"]["value"], "421")

    def test_c1_tableau_layout_block_2024_schema(self):
        markdown = """
Common Data Set

C. FIRST-TIME, FIRST-YEAR ADMISSION

C1. First-time, first-year students

Category              Unit load                          Men                              Women                          Another Gender                         Unknown
Applied               All                               5283                                6956                                10                                  0
Admitted              All                                401                                466                                  1                                  0
Enrolled              Full-Time                          194                                242                                  0                                  0
                      Part-Time                            0                                  0                                  0                                  0

C2. First-time, first-year wait-listed students
"""

        values = clean(
            markdown,
            schema=SchemaIndex(REPO_ROOT / "schemas" / "cds_schema_2024_25.json"),
        )

        self.assertEqual(values["C.101"]["value"], "5283")
        self.assertEqual(values["C.102"]["value"], "6956")
        self.assertEqual(values["C.103"]["value"], "10")
        self.assertEqual(values["C.104"]["value"], "0")
        self.assertEqual(values["C.105"]["value"], "401")
        self.assertEqual(values["C.106"]["value"], "466")
        self.assertEqual(values["C.107"]["value"], "1")
        self.assertEqual(values["C.108"]["value"], "0")
        self.assertEqual(values["C.109"]["value"], "194")
        self.assertEqual(values["C.111"]["value"], "242")
        self.assertEqual(values["C.117"]["value"], "12249")
        self.assertEqual(values["C.118"]["value"], "868")
        self.assertEqual(values["C.119"]["value"], "436")

    def test_c1_compact_question_lines(self):
        markdown = """
## C. First-time, First-year Admission

C101 Total first-time, first-year men who applied 7,224
C102 Total first-time, first-year women who applied 8,044
C104 Total first-time, first-year men who were admitted 621
C105 Total first-time, first-year women who were admitted 654
C107 Total first-time, first-year men who enrolled 238
C108 Total first-time, first-year women who enrolled 306
C116 Total first-time, first-year students who applied 15,411
C117 Total first-time, first-year students who were admitted 1,272
C118 Total first-time, first-year students who enrolled 547
C201 Do you have a policy of placing students on a waiting list? Y
C202 Number of qualified applicants offered a place on waiting list: 2,303
C203 Number accepting a place on the waiting list: 858
C204 Number of wait-listed students admitted: 113
C802 SAT or ACT Not required for admission, but considered if submitted
"""

        values = clean(
            markdown,
            schema=SchemaIndex(REPO_ROOT / "schemas" / "cds_schema_2025_26.json"),
        )

        self.assertEqual(values["C.101"]["value"], "7224")
        self.assertEqual(values["C.102"]["value"], "8044")
        self.assertEqual(values["C.104"]["value"], "621")
        self.assertEqual(values["C.105"]["value"], "654")
        self.assertEqual(values["C.107"]["value"], "238")
        self.assertEqual(values["C.108"]["value"], "306")
        self.assertEqual(values["C.116"]["value"], "15411")
        self.assertEqual(values["C.117"]["value"], "1272")
        self.assertEqual(values["C.118"]["value"], "547")
        self.assertEqual(values["C.201"]["value"], "Y")
        self.assertEqual(values["C.202"]["value"], "2303")
        self.assertEqual(values["C.203"]["value"], "858")
        self.assertEqual(values["C.204"]["value"], "113")
        self.assertNotIn("C.802", values)

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
