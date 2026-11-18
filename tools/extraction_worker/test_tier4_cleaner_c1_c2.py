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

    def test_c1_compact_gender_columns_without_another_or_unknown(self):
        markdown = """
C1 First-time, first-year students

Men Women Total
Total first-time, first-year students who applied 48,101 50,209 98,310
Total first-time, first-year students admitted 6,684 8,689 15,373
Total first-time, first-year students enrolled 3,199 4,079 7,278
Full-time, first-time, first-year students enrolled 3,188 4,064 7,252
Part-time, first-time, first-year students enrolled 11 15 26
"""

        values = clean(
            markdown,
            schema=SchemaIndex(REPO_ROOT / "schemas" / "cds_schema_2024_25.json"),
        )

        self.assertEqual(values["C.101"]["value"], "48101")
        self.assertEqual(values["C.102"]["value"], "50209")
        self.assertEqual(values["C.105"]["value"], "6684")
        self.assertEqual(values["C.106"]["value"], "8689")
        self.assertEqual(values["C.109"]["value"], "3188")
        self.assertEqual(values["C.110"]["value"], "11")
        self.assertEqual(values["C.111"]["value"], "4064")
        self.assertEqual(values["C.112"]["value"], "15")
        self.assertEqual(values["C.117"]["value"], "98310")
        self.assertEqual(values["C.118"]["value"], "15373")
        self.assertEqual(values["C.119"]["value"], "7278")

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

    def test_valdosta_visual_ocr_c1_lines(self):
        supplemental = """
C. FIRST-TIME, FIRST-YEAR ADMISSION
FIRST-TIME, FIRST-YEAR STUDENT APPLICANTS TOTAL
Total first-time, first-year men who applied 1655
Total first-time, first-year women who applied 3836
Total first-time, first-year unknown sex who applied 0
FIRST-TIME, FIRST-YEAR STUDENT ADMITS TOTAL
Total first-time, first-year men who were admitted 1232
Total first-time, first-year women who were admitted 3034
Total first-time, first-year unknown sex who were admitted 0
FIRST-TIME, FIRST-YEAR STUDENT ENROLLEES TOTAL
Total first-time, first-year men who enrolled 411
Total first-time, first-year women who enrolled 814
Total first-time, first-year unknown sex who enrolled 0
"""

        values = clean(
            "",
            supplemental_text=supplemental,
            schema=SchemaIndex(REPO_ROOT / "schemas" / "cds_schema_2025_26.json"),
        )

        self.assertEqual(values["C.101"]["value"], "1655")
        self.assertEqual(values["C.102"]["value"], "3836")
        self.assertEqual(values["C.104"]["value"], "1232")
        self.assertEqual(values["C.105"]["value"], "3034")
        self.assertEqual(values["C.116"]["value"], "5491")
        self.assertEqual(values["C.117"]["value"], "4266")
        self.assertEqual(values["C.118"]["value"], "1225")


SCHEMA_2024_25 = REPO_ROOT / "schemas" / "cds_schema_2024_25.json"
SCHEMA_2025_26 = REPO_ROOT / "schemas" / "cds_schema_2025_26.json"


class Tier4CleanerC1FunnelShapeTest(unittest.TestCase):
    """C1 failures that published admitted > applied (issue #281)."""

    def _clean_layout(self, layout: str, schema: Path = SCHEMA_2024_25) -> dict:
        return clean("", schema=SchemaIndex(schema), supplemental_text=layout)

    def test_sjsu_residency_rows_are_not_read_as_gender_columns(self):
        # San Jose State 2024-25 (pdf layout text). The residency table is
        # Total / In-State / Out-of-State / International with a blank Unknown
        # cell; the four numbers were read as men / women / another gender /
        # total, which put 31419 admits into C.105 (men admitted).
        layout = """
First-Time, First-Year Student Applicants                    Total
Total first-time, first-year men who applied
                                                             18545
Total first-time, first-year women who applied
                                                             18464
Total first-time, first-year men who were admitted           14560
Total first-time, first-year women who were admitted         16752

If available, please provide residency breakdowns for total applicants, admits, and enrolled students: Fall 2024
        First-Time, First-Year Student Applicants
                                                   Total        In-State          Out-of-State   International     Unknown
Total first-time, first-year who were admitted     31419        29918             929            572
Total first-time, first-year who enrolled          4604         4460              93             51
"""
        values = self._clean_layout(layout)
        self.assertEqual(values["C.105"]["value"], "14560")
        self.assertEqual(values["C.106"]["value"], "16752")
        self.assertEqual(values["C.118"]["value"], "31419")
        self.assertEqual(values["C.119"]["value"], "4604")
        self.assertEqual(values["C.121"]["value"], "29918")
        self.assertEqual(values["C.124"]["value"], "929")
        self.assertEqual(values["C.122"]["value"], "4460")

    def test_utep_wrapped_residency_header(self):
        # UTEP 2024-25: the header wraps ("Out-of-" / "State", "Interna" /
        # "tional"); the rows must still be read as residency columns.
        layout = """
Total first-time, first-year men who applied                       5631
Total first-time, first-year women who applied                     6365
 First-Time, First-Year Student Applicants                         Total                        Out-of-       Interna        Unkno
                                                                              In-State         State        tional          wn
 Total first-time, first-year who applied                          11996          11450             124           422
 Total first-time, first-year who were admitted                    11986          11447             124           415
"""
        values = self._clean_layout(layout)
        self.assertEqual(values["C.101"]["value"], "5631")
        self.assertEqual(values["C.117"]["value"], "11996")
        self.assertEqual(values["C.118"]["value"], "11986")
        self.assertNotIn("C.103", values)
        self.assertNotIn("C.107", values)

    def test_total_last_residency_header_with_blank_unknown(self):
        # Existing behaviour kept: Total in the last column, Unknown blank.
        layout = """
FIRST-TIME, FIRST-YEAR STUDENT APPLICANTS IN-STATE OUT-OF-STATE INTERNATIONAL UNKNOWN TOTAL
Total first-time, first-year (degree-seeking) who applied 15064 34044 9231 58339
"""
        values = self._clean_layout(layout)
        self.assertEqual(values["C.117"]["value"], "58339")
        self.assertEqual(values["C.120"]["value"], "15064")

    def test_partial_gender_rows_do_not_become_the_total(self):
        # Lenoir-Rhyne 2024-25: the text layer glues words ("men  whoapplied"),
        # so only the women row matched and its 2005 became "total applied".
        # The markdown table carries the real total (3661).
        layout = """
Total first-time,  first-year  men  whoapplied                       1656
Total first-time,  first-year  women  who  applied                    2005
"""
        markdown = """
## C1 First-time, first-year students

| First-Time, First-Year Student Applicants      |   Total | In-State   | Out-of-State International   | Unknown   |
|------------------------------------------------|---------|------------|------------------------------|-----------|
| Total first-time, first-year who applied       |    3661 |            |                              |           |
"""
        values = clean(
            markdown, schema=SchemaIndex(SCHEMA_2024_25), supplemental_text=layout
        )
        self.assertEqual(values["C.117"]["value"], "3661")
        only_women = self._clean_layout(
            "Total first-time, first-year women who applied  5849\n"
        )
        self.assertNotIn("C.117", only_women)
        self.assertEqual(only_women["C.102"]["value"], "5849")

    def test_complete_gender_rows_still_synthesize_the_total(self):
        layout = """
Total first-time, first-year men who applied                       5631
Total first-time, first-year women who applied                     6365
"""
        values = self._clean_layout(layout)
        self.assertEqual(values["C.117"]["value"], "11996")

    def test_total_first_residency_header_with_five_columns(self):
        # SUNY Canton 2024-25: Total, In-State, Out-of-State, International,
        # Unknown; the enrolled row was read with Unknown (0) as the total.
        layout = """
 FIRST-TIME, FIRST-YEAR STUDENT                               TOTAL            IN-        OUT-OF-          INTERNATIONAL    UNKNOWN
 Total first-time, first-year (degree-seeking) enrolled                539          515              15                        9                          0
"""
        values = self._clean_layout(layout)
        self.assertEqual(values["C.119"]["value"], "539")

    def test_residency_table_without_total_column_is_not_the_total(self):
        # UNC 2025-26: In-State / Out-of-State / International / Unknown with
        # no Total column. Column 0 (In-State enrolled 4,063) was published as
        # the total enrolled (C.118), then as 0.
        markdown = """
## C1 First-time, first-year students

| First-Time, First-Year Student Applicants      | In-State   | Out-of-State   | International   | Unknown   |
|------------------------------------------------|------------|----------------|-----------------|-----------|
| Total first-time, first-year who applied       |     17,846 |         48,645 |           9,756 |         0 |
| Total first-time, first-year who enrolled      |      4,063 |            728 |             300 |         0 |
"""
        values = clean(markdown, schema=SchemaIndex(SCHEMA_2025_26))
        self.assertNotIn("C.116", values)
        self.assertNotIn("C.118", values)
        self.assertEqual(values["C.119"]["value"], "17846")

    def test_residency_table_with_total_column_still_reads_the_total(self):
        markdown = """
## C1 First-time, first-year students

| First-Time, First-Year Student Applicants      | Total   | In-State   | Out-of-State   |
|------------------------------------------------|---------|------------|----------------|
| Total first-time, first-year who applied       |  76,247 |     17,846 |         48,645 |
"""
        values = clean(markdown, schema=SchemaIndex(SCHEMA_2025_26))
        self.assertEqual(values["C.116"]["value"], "76247")

    def test_single_gender_college_blank_rows_still_sum_the_total(self):
        # Barnard 2024-25: the men rows are blank; women 11836 applied.
        layout = """
Total first-time, first-year men who applied
Total first-time, first-year women who applied                     11836
Total first-time, first-year another gender who applied
Total first-time, first-year men who were admitted
Total first-time, first-year women who were admitted               1046
Total full-time, first-time, first-year men who enrolled
Total part-time, first-time, first-year men who enrolled
Total full-time, first-time, first-year women who enrolled          718
Total part-time, first-time, first-year women who enrolled
"""
        values = self._clean_layout(layout)
        self.assertEqual(values["C.117"]["value"], "11836")
        self.assertEqual(values["C.118"]["value"], "1046")
        self.assertEqual(values["C.119"]["value"], "718")

    def test_glued_gender_row_with_a_value_still_blocks_the_total(self):
        # Lenoir-Rhyne 2024-25: the men row has a number but its label is glued
        # ("whoapplied"), so it is unread; the women row alone is not the total.
        layout = """
Total first-time,  first-year  men  whoapplied                       1656
Total first-time,  first-year  women  who  applied                    2005
"""
        self.assertNotIn("C.117", self._clean_layout(layout))

    def test_label_with_its_value_on_the_next_line_is_not_a_blank_row(self):
        # San Jose State: the value sits on its own line below the label.
        layout = """
Total first-time, first-year men who applied
                                                             18545
Total first-time, first-year women who applied               18464
"""
        self.assertNotIn("C.117", self._clean_layout(layout))

    def test_header_with_total_in_the_row_label_is_total_last(self):
        layout = """
TOTAL APPLICANTS        IN-STATE    OUT-OF-STATE    INTERNATIONAL    UNKNOWN    TOTAL
Total first-time, first-year who applied    15064    34044    9231    0    58339
"""
        values = self._clean_layout(layout)
        self.assertEqual(values["C.117"]["value"], "58339")
        self.assertEqual(values["C.120"]["value"], "15064")

    def test_residency_row_with_a_blank_middle_cell_is_placed_by_position(self):
        # International is blank and Unknown is 0: the 0 must not slide left.
        layout = """
                                              Total      In-State     Out-of-State     International     Unknown
Total first-time, first-year who applied       500        450          50                                   0
"""
        values = self._clean_layout(layout)
        self.assertEqual(values["C.117"]["value"], "500")
        self.assertEqual(values["C.123"]["value"], "50")
        self.assertNotIn("C.126", values)  # International stays empty

    def test_residency_row_that_cannot_be_placed_is_skipped(self):
        layout = """
Total   In-State   Out-of-State   International   Unknown
Total first-time, first-year who applied 500 450 50 0
"""
        values = self._clean_layout(layout)
        self.assertNotIn("C.117", values)

    def test_degree_seeking_row_in_a_residency_block_is_still_read(self):
        layout = """
                                              Total      In-State     Out-of-State     International     Unknown
Degree-seeking who applied                     500        450          40               10                0
"""
        values = self._clean_layout(layout)
        self.assertEqual(values["C.117"]["value"], "500")

    def test_blank_part_time_rows_with_sidebar_text_still_sum_enrolled(self):
        # Skidmore 2024-25: the part-time rows are blank but a note from the
        # page margin shares their line.
        layout = """
Total full-time, first-time, first-year men who enrolled                  243
Total part-time, first-time, first-year men who enrolled                              *The total degree-seeking
Total full-time, first-time, first-year women who enrolled                425
Total part-time, first-time, first-year women who enrolled                            census date and may not
"""
        self.assertEqual(self._clean_layout(layout)["C.119"]["value"], "668")


if __name__ == "__main__":
    unittest.main()
