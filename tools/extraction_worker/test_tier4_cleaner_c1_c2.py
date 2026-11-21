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


    # Quincy 2024-25 (issue #363). The markdown tables are right. In the PDF's
    # layout text each table's heading is printed on its first row's line, so
    # every value sits one line below its label. Numbers here are invented.
    QUINCY_TABLES = """
| First-Time, First-Year Student Applicants               |   Total |
|---------------------------------------------------------|---------|
| Total first-time, first-year men who applied            |     900 |
| Total first-time, first-year women who applied          |     800 |
| Total first-time, first-year another gender who applied |       0 |
| Total first-time, first-year unknown gender who applied |       0 |

| First-Time, First-Year Student Admits                         |   Total |
|---------------------------------------------------------------|---------|
| Total first-time, first-year men who were admitted            |     500 |
| Total first-time, first-year women who were admitted          |     400 |
| Total first-time, first-year another gender who were admitted |       0 |
| Total first-time, first-year unknown gender who were admitted |       0 |

| First-Time, First-Year Student Enrollees by Status                  |   Total |
|---------------------------------------------------------------------|---------|
| Total full-time, first-time, first-year men who enrolled            |     170 |
| Total part-time, first-time, first-year men who enrolled            |       0 |
| Total full-time, first-time, first-year women who enrolled          |      96 |
| Total part-time, first-time, first-year women who enrolled          |       0 |
"""
    QUINCY_LAYOUT = """
                  First-Time, First-Year Student Applicants                                             Total
       Total first-time, first-year men who applied                                                             900
       Total first-time, first-year women who applied                                                           800
       Total first-time, first-year another gender who applied                                                   0
       Total first-time, first-year unknown gender who applied                                                   0
       Total first-time, first-year men who were admittedFirst-Time, First-Year Student Admits                 Total
       Total first-time, first-year women who were admitted                                                     500
       Total first-time, first-year another gender who were admitted                                            400
       Total first-time, first-year unknown gender who were admitted                                             0
                                                                                                                 0
       Total full-time, first-time, first-year men who enrolledFirst-Time, First-Year Student Enrollees by StatusTotal
       Total part-time, first-time, first-year men who enrolled                                                 170
       Total full-time, first-time, first-year women who enrolled                                                0
       Total part-time, first-time, first-year women who enrolled                                               96
                                                                                                                 0
"""

    def test_c1_table_whose_heading_is_printed_on_its_first_row_is_not_read_from_layout_text(self):
        values = clean(
            self.QUINCY_TABLES, schema=SchemaIndex(SCHEMA_2024_25), supplemental_text=self.QUINCY_LAYOUT
        )
        read = {qn: values[qn]["value"] for qn in ("C.101", "C.102", "C.105", "C.106", "C.107", "C.109", "C.110", "C.111", "C.112")}
        self.assertEqual(read, {
            "C.101": "900", "C.102": "800",                 # applied: its heading is on its own line, read as before
            "C.105": "500", "C.106": "400", "C.107": "0",   # admitted: men 500, women 400, not 500 / 500 / 400
            "C.109": "170", "C.110": "0", "C.111": "96", "C.112": "0",   # enrolled: not 170 / 170 / 0 / 96
        })

    def test_c1_shifted_layout_without_tables_publishes_no_shifted_rows(self):
        # With no table to fall back on, a shifted stage is left unread, not read one row off.
        values = clean("", schema=SchemaIndex(SCHEMA_2024_25), supplemental_text=self.QUINCY_LAYOUT)
        self.assertEqual((values["C.101"]["value"], values["C.102"]["value"]), ("900", "800"))
        for qn in ("C.105", "C.106", "C.107", "C.109", "C.110", "C.111", "C.112"):
            self.assertNotIn(qn, values)

    def test_c1_prose_about_degree_seeking_students_is_not_a_residency_row(self):
        # Quincy 2024-25's B22 retention sentence was read as the enrolled row by residency,
        # publishing 2024, 327, 2023 and 229 as counts.
        markdown = """
B22 For the cohort of all full-time bachelor's (or equivalent) degree-seeking undergraduate students who entered your institution as first-year students in Fall 2023 (or the preceding summer term), what percentage was enrolled at your institution as of the date your institution calculates its official enrollment in Fall 2024. 327 in Fall 2023 cohort 229 retained Fall 2024
"""
        values = clean(markdown, schema=SchemaIndex(SCHEMA_2024_25))
        for qn in ("C.119", "C.122", "C.125", "C.128", "C.131"):
            self.assertNotIn(qn, values)

        # A real row outside a residency table is still read.
        row = "Total first-time, first-year (degree-seeking) who enrolled 170 110 5 0 285"
        values = clean(row, schema=SchemaIndex(SCHEMA_2024_25))
        self.assertEqual(values["C.119"]["value"], "285")
        self.assertEqual(values["C.122"]["value"], "170")

    def test_c1_percentage_sentence_is_not_a_residency_row(self):
        # Wheaton (MA) 2025-26, an HTML CDS. The B22 sentence names the cohort
        # ("first-time", "degree-seeking") and has six numbers; it was read as
        # the enrolled row, so 3 was published as total enrolled and 2024, 2025
        # and 88 as residency counts, ahead of the real row further down.
        markdown = """
**88.3%** percentage of first-time, full-time bachelor's degree-seeking undergraduates from Fall 2024 who were enrolled in Fall 2025 was 88.3% .

| Category | In-state | Out-of-state | International | Unknown | Total |
| --- | --- | --- | --- | --- | --- |
| Total first-time, first-year (degree-seeking) who applied | 1,693 | 2,515 | 1,806 | 0 | 6,014 |
| Total first-time, first-year (degree-seeking) who were admitted | 1,395 | 2,074 | 309 | 0 | 3,778 |
| Total first-time, first-year (degree-seeking) who enrolled | 169 | 266 | 21 | 0 | 456 |
"""
        values = clean(markdown, schema=SchemaIndex(SCHEMA_2025_26))
        got = {qn: values[qn]["value"] for qn in ("C.118", "C.121", "C.124", "C.127", "C.130")}
        self.assertEqual(got, {"C.118": "456", "C.121": "169", "C.124": "266", "C.127": "21", "C.130": "0"})

        # The sentence alone gives no C1 value at all.
        values = clean(markdown.split("| Category")[0], schema=SchemaIndex(SCHEMA_2025_26))
        self.assertEqual([qn for qn in values if qn.startswith("C.1")], [])

    def test_c1_single_column_table_with_gender_unknown_and_total_rows(self):
        # MIT 2024-25, an HTML CDS (issue #363 item 7): the rows read "of
        # gender unknown who ..." and the totals sit under the rows by sex in
        # the same one-column table. Both were left out, so the published
        # totals were sums that missed the unknown-gender counts.
        markdown = """
| FIRST-TIME, FIRST YEAR STUDENT APPLICANTS | TOTAL |
| --- | --- |
| Total first-time, first-year men who applied | 17,210 |
| Total first-time, first-year women who applied | 8,975 |
| Total first-time, first-year of another gender who applied | 997 |
| Total first-time, first-year of gender unknown who applied | 1,050 |
| FIRST-TIME, FIRST-YEAR STUDENT ADMITS TOTAL | TOTAL |
| Total first-time, first-year men who were admitted | 606 |
| Total first-time, first-year women who were admitted | 612 |
| Total first-time, first-year of another gender who were admitted | 36 |
| Total first-time, first-year of gender unknown who were admitted | 30 |
| FIRST-TIME, FIRST-YEAR STUDENT ENROLLEES BY STATUS | TOTAL |
| Total full-time, first-time, first-year men who enrolled | 547 |
| Total part-time, first-time, first-year men who enrolled | 0 |
| Total full-time, first-time, first-year women who enrolled | 499 |
| Total part-time, first-time, first-year women who enrolled | 0 |
| Total full-time, first-time, first-year of another gender who enrolled | 34 |
| Total part-time, first-time, first-year of another gender who enrolled | 0 |
| Total full-time, first-time, first-year of gender unknown who enrolled | 26 |
| Total part-time, first-time, first-year of gender unknown who enrolled | 0 |
|  | TOTAL |
| Total first-time, first-year who applied | 28,300 |
| Total first-time, first-year who were admitted | 1,290 |
| Total first-time, first-year enrolled | 1,110 |
"""
        # (MIT prints 28,232 / 1,284 / 1,106, which are the sums of the rows
        # by sex. The totals here differ from those sums so the test shows the
        # printed rows are what is read.)
        values = clean(markdown, schema=SchemaIndex(SCHEMA_2024_25))
        got = {qn: v["value"] for qn, v in values.items() if qn.startswith("C.1")}
        self.assertEqual(got, {
            "C.101": "17210", "C.102": "8975", "C.103": "997", "C.104": "1050",
            "C.105": "606", "C.106": "612", "C.107": "36", "C.108": "30",
            "C.109": "547", "C.110": "0", "C.111": "499", "C.112": "0",
            "C.113": "34", "C.114": "0", "C.115": "26", "C.116": "0",
            "C.117": "28300", "C.118": "1290", "C.119": "1110",
        })

    def test_c1_total_row_is_not_read_from_a_table_with_several_value_columns(self):
        # With more than one value column the first may be In-State.
        markdown = """
| FIRST-TIME, FIRST YEAR STUDENT APPLICANTS | A | B |
| --- | --- | --- |
| Total first-time, first-year men who applied | 900 | 1 |
| Total first-time, first-year women who applied | 800 | 2 |
| Total first-time, first-year who applied | 400 | 1,700 |
"""
        values = clean(markdown, schema=SchemaIndex(SCHEMA_2024_25))
        self.assertNotIn("C.117", values)

    WHEATON_C1 = """
### C1. Applications, Admissions, and Enrollment

| Category | Men | Women | Another Gender | Unknown | Total |
| --- | --- | --- | --- | --- | --- |
| Applied | 2095 | 3697 | 0 | 43 | 5835 |
| Admitted | 1268 | 2668 | 0 | 16 | 3952 |
| Enrolled | 186 | 321 | 0 | 4 | 511 |

| Enrollment status | Men | Women | Another Gender | Unknown | Total |
| --- | --- | --- | --- | --- | --- |
| Full-time | 180 | 320 | 0 | 4 | 500 |
| Part-time | 6 | 1 | 0 | 0 | 5 |

| Category | In-state | Out-of-state | International | Unknown | Total |
| --- | --- | --- | --- | --- | --- |
| Applied | 1841 | 2706 | 1263 | 25 | 5835 |
| Admitted | 1500 | 2220 | 211 | 21 | 3952 |
| Enrolled | 212 | 279 | 20 | 0 | 511 |
"""

    def test_c1_one_row_per_stage_tables(self):
        # Wheaton (MA) publishes its CDS as HTML with one row per stage and one
        # column per sex, the full-time / part-time split in a table of its
        # own, and residency rows labelled by stage alone. (The full-time and
        # part-time figures here are changed from the file's 186/0 and 321/0 so
        # that each cell can only have come from its own row, and their Total
        # cells add up to 505: total enrolled is the Enrolled row's 511, not
        # that sum.)
        values = clean(self.WHEATON_C1, schema=SchemaIndex(SCHEMA_2024_25))
        got = {qn: v["value"] for qn, v in values.items() if qn.startswith("C.1")}
        self.assertEqual(got, {
            "C.101": "2095", "C.102": "3697", "C.103": "0", "C.104": "43",
            "C.105": "1268", "C.106": "2668", "C.107": "0", "C.108": "16",
            "C.109": "180", "C.110": "6", "C.111": "320", "C.112": "1",
            "C.113": "0", "C.114": "0", "C.115": "4", "C.116": "0",
            "C.117": "5835", "C.118": "3952", "C.119": "511",
            "C.120": "1841", "C.121": "1500", "C.122": "212",
            "C.123": "2706", "C.124": "2220", "C.125": "279",
            "C.126": "1263", "C.127": "211", "C.128": "20",
            "C.129": "25", "C.130": "21", "C.131": "0",
        })

    def test_c1_enrolled_row_by_sex_is_kept_only_where_the_template_has_it(self):
        # 2025-26 has a row for everyone of one sex who enrolled (C.107-C.109);
        # 2024-25 has only the full-time and part-time rows, and an
        # all-enrolled count is neither of those.
        markdown = self.WHEATON_C1.split("| Enrollment status")[0].replace(
            "| Another Gender ", "").replace("| 0 | 43 ", "| 43 ").replace(
            "| 0 | 16 ", "| 16 ").replace("| 0 | 4 ", "| 4 ")
        values = clean(markdown, schema=SchemaIndex(SCHEMA_2025_26))
        self.assertEqual(
            {qn: values[qn]["value"] for qn in ("C.107", "C.108", "C.109", "C.118")},
            {"C.107": "186", "C.108": "321", "C.109": "4", "C.118": "511"},
        )
        values = clean(self.WHEATON_C1.split("| Enrollment status")[0], schema=SchemaIndex(SCHEMA_2024_25))
        self.assertEqual(values["C.119"]["value"], "511")
        for qn in ("C.109", "C.110", "C.111", "C.112", "C.113", "C.114", "C.115", "C.116"):
            self.assertNotIn(qn, values)

    def test_enrollment_status_table_is_read_only_directly_under_a_c1_table(self):
        # The same shape elsewhere (an enrollment table by sex in section B)
        # is not C1.
        status_table = "| Enrollment status" + self.WHEATON_C1.split("| Enrollment status")[1].split("| Category")[0]
        values = clean(status_table, schema=SchemaIndex(SCHEMA_2024_25))
        self.assertEqual([qn for qn in values if qn.startswith("C.1")], [])

        # A table in between breaks the link.
        head, rest = self.WHEATON_C1.split("| Enrollment status")
        other = "| Measure | Total |\n| --- | --- |\n| Something else | 5 |\n\n"
        values = clean(head + other + "| Enrollment status" + rest, schema=SchemaIndex(SCHEMA_2024_25))
        for qn in ("C.109", "C.110", "C.111", "C.112"):
            self.assertNotIn(qn, values)

    C1_ROWS_BY_SEX = """
### C1. Applications

| FIRST-TIME, FIRST YEAR STUDENT APPLICANTS | TOTAL |
| --- | --- |
| Total first-time, first-year men who applied | 900 |
| Total first-time, first-year women who applied | 800 |
| Total first-time, first-year men who were admitted | 400 |
| Total first-time, first-year women who were admitted | 380 |
| Total full-time, first-time, first-year men who enrolled | 100 |
| Total part-time, first-time, first-year men who enrolled | 5 |
| Total full-time, first-time, first-year women who enrolled | 120 |
| Total part-time, first-time, first-year women who enrolled | 6 |
"""

    # Wheaton (MA) 2024-25's D2 table, and the same shapes for transfers.
    TRANSFER_TABLES = """
| Category | Men | Women | Unknown | Total |
| --- | --- | --- | --- | --- |
| Applied | 60 | 85 | 2 | 147 |
| Admitted | 22 | 34 | 1 | 57 |
| Enrolled | 9 | 17 | 1 | 27 |

| Enrollment status | Men | Women | Unknown | Total |
| --- | --- | --- | --- | --- |
| Full-time | 8 | 16 | 1 | 25 |
| Part-time | 1 | 1 | 0 | 2 |

| Category | In-state | Out-of-state | International | Total |
| --- | --- | --- | --- | --- |
| Applied | 40 | 100 | 7 | 147 |
| Admitted | 15 | 40 | 2 | 57 |
| Enrolled | 8 | 18 | 1 | 27 |
"""

    def _c1(self, values):
        return {qn: v["value"] for qn, v in values.items() if qn.startswith("C.1")}

    def test_transfer_tables_in_section_d_are_not_read_as_c1(self):
        # Section D has the same one-row-per-stage tables for transfer
        # students. With the section marked, nothing in it reaches C1, which
        # also stops its Applied and Admitted rows filling C1 cells that C1
        # itself left empty (the unknown-sex and total rows here).
        c1_only = self._c1(clean(self.C1_ROWS_BY_SEX, schema=SchemaIndex(SCHEMA_2025_26)))
        for heading in ("### Section D. Transfer Admission", "## D. TRANSFER ADMISSION", "**D1.** Does your institution enroll transfer students?", "D1-D2: Fall Applicants"):
            markdown = self.C1_ROWS_BY_SEX + "\n" + heading + "\n" + self.TRANSFER_TABLES
            self.assertEqual(self._c1(clean(markdown, schema=SchemaIndex(SCHEMA_2025_26))), c1_only, heading)
        self.assertEqual(c1_only["C.107"], "105")  # full-time plus part-time men
        self.assertNotIn("C.118", c1_only)

    def test_one_row_per_stage_tables_after_c1_was_already_read_add_no_enrolled_rows(self):
        # The same tables with no section D heading to go by. C1's applied row
        # was read from the rows by sex, so a later table with one row per
        # stage is not C1's: its Enrolled row, the full-time / part-time table
        # under it and its residency rows are left alone.
        values = self._c1(clean(self.C1_ROWS_BY_SEX + self.TRANSFER_TABLES, schema=SchemaIndex(SCHEMA_2025_26)))
        self.assertEqual(
            {qn: values.get(qn) for qn in ("C.107", "C.108", "C.110", "C.111", "C.112", "C.113")},
            {"C.107": "105", "C.108": "126", "C.110": "100", "C.111": "5", "C.112": "120", "C.113": "6"},
        )
        for qn in ("C.109", "C.114", "C.115", "C.118"):
            self.assertNotIn(qn, values)
        for qn in ("C.119", "C.120", "C.121", "C.122", "C.123", "C.124", "C.125", "C.126", "C.127"):
            self.assertNotIn(qn, values)

    def test_second_one_row_per_stage_table_does_not_add_enrolled_rows(self):
        # C1 as a compact table with full-time / part-time enrolled rows (a
        # layout read before this change), then a transfer table of the same
        # shape with an Enrolled row. The by-sex enrolled totals stay the sums
        # of C1's own rows.
        c1 = """
|                    | Men | Women | Unknown | Total |
|--------------------|-----|-------|---------|-------|
| Applied            | 900 | 800   | 3       | 1,703 |
| Admitted           | 400 | 380   | 1       | 781   |
| Full-time enrolled | 100 | 120   | 0       | 220   |
| Part-time enrolled | 5   | 6     | 0       | 11    |
"""
        values = self._c1(clean(c1 + self.TRANSFER_TABLES, schema=SchemaIndex(SCHEMA_2025_26)))
        self.assertEqual(
            {qn: values.get(qn) for qn in ("C.107", "C.108", "C.109", "C.118")},
            {"C.107": "105", "C.108": "126", "C.109": "0", "C.118": "231"},
        )
        self.assertEqual(values, self._c1(clean(c1, schema=SchemaIndex(SCHEMA_2025_26))))

    def test_stage_only_residency_rows_need_a_c1_table_just_above(self):
        residency = "| Category | In-state" + self.TRANSFER_TABLES.split("| Category | In-state")[1]
        self.assertEqual(self._c1(clean(residency, schema=SchemaIndex(SCHEMA_2025_26))), {})


if __name__ == "__main__":
    unittest.main()
