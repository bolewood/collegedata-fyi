from __future__ import annotations

import unittest

from tier4_cleaner import clean


class Tier4CleanerH1H2Test(unittest.TestCase):
    def test_h1_reporting_year_methodology_and_wrapped_work_study_row(self):
        markdown = """
## Aid Awarded to Enrolled Undergraduates

H1 Enter total dollar amounts awarded to enrolled full-time and less than full-time degree-seeking undergraduates.

2024-2025 estimated 2023-2024 Final

Estimated

- [x] x Federal methodology (FM)

Indicate the academic year for which data are reported for items H1, H2, H2A , and H6 below:

- [ ] Both FM and IM

Which needs-analysis methodology does your institution use in awarding institutional aid? (Formerly H3)

- [ ] Institutional methodology (IM)

| Aid Awarded | Need-based (Include non-need- based aid use to meet need.) | Non-need-based (Exclude non- need-based aid use to meet |
|---|---|---|
| Federal | $17,305,538 | $0 |
| Federal Work-Study | $390,705 | |
| State and other (e.g., institutional) work-study/employment (Note: | | |
| Excludes Federal Work-Study captured above.) | $288,205 | $523,943 |
"""

        values = clean(markdown)

        self.assertEqual(values["H.101"]["value"], "2024-2025 estimated")
        self.assertEqual(values["H.102"]["value"], "X")
        self.assertNotIn("H.103", values)
        self.assertNotIn("H.104", values)
        self.assertEqual(values["H.105"]["value"], "17305538")
        self.assertEqual(values["H.111"]["value"], "390705")
        self.assertEqual(values["H.112"]["value"], "288205")
        self.assertEqual(values["H.117"]["value"], "0")
        self.assertEqual(values["H.123"]["value"], "523943")

    def test_h2_less_than_full_time_column_is_not_claimed_as_full_time(self):
        markdown = """
|    | Number of Enrolled Students Awarded Aid | First-time Full- time First-year Students | Full-time Undergrad (Incl. First-Year) | Less Than Full-time Undergrad |
|----|-----------------------------------------|--------------------------------------------|-----------------------------------------|--------------------------------|
| A  | Number of degree-seeking undergraduate students (CDS Item B1 if reporting on Fall 2024 cohort) | 1603 | 7534 | 1583 |
| B  | Number of students in line a who applied for need-based financial aid | 1393 | 5576 | 739 |
| C  | Number of students in line b who were determined to have financial need | 1012 | 4301 | 570 |
| D  | Number of students in line c who were awarded any financial aid | 938 | 3923 | 453 |
| E  | Number of students in line d who were awarded any need-based scholarship or grant aid | 877 | 3519 | 346 |
| F  | Number of students in line d who were awarded any need-based self-help aid | 266 | 1381 | 208 |
| G  | Number of students in line d who were awarded any non- need-based scholarship or grant aid | 10 | 38 | 3 |
| H  | Number of students in line d whose need was fully met (exclude PLUS loans, unsubsidized loans, and private alternative loans) | 80 | 299 | 20 |
"""

        values = clean(markdown)

        self.assertEqual(values["H.201"]["value"], "1603")
        self.assertEqual(values["H.214"]["value"], "7534")
        self.assertEqual(values["H.227"]["value"], "1583")
        self.assertEqual(values["H.228"]["value"], "739")
        self.assertEqual(values["H.229"]["value"], "570")
        self.assertEqual(values["H.230"]["value"], "453")
        self.assertEqual(values["H.231"]["value"], "346")
        self.assertEqual(values["H.232"]["value"], "208")
        self.assertEqual(values["H.233"]["value"], "3")
        self.assertEqual(values["H.234"]["value"], "20")

    def test_h2a_less_than_full_time_column_is_not_claimed_as_full_time(self):
        markdown = """
|    | Number of Enrolled Students Awarded Non-need- based Scholarships and Grants | First-time Full-time First-year Students | Full-time Undergrad (Incl. First-year.) | Less Than Full-time Undergrad |
|----|--------------------------------------------------------------------------------|------------------------------------------|------------------------------------------|--------------------------------|
| N  | Number of students in line a who had no financial need and who were awarded institutional non-need-based scholarship or grant aid | 11 | 75 | 0 |
| O  | Average dollar amount of institutional non-need-based scholarship and grant aid awarded to students in line n | $ 2,000 | $ 1,556 | $ 0 |
"""

        values = clean(markdown)

        self.assertEqual(values["H.2A01"]["value"], "11")
        self.assertEqual(values["H.2A02"]["value"], "2000")
        self.assertEqual(values["H.2A05"]["value"], "75")
        self.assertEqual(values["H.2A06"]["value"], "1556")
        self.assertEqual(values["H.2A09"]["value"], "0")
        self.assertEqual(values["H.2A10"]["value"], "0")

    def test_h2_i_m_blank_header_continuation_table(self):
        markdown = """
| I   | On average, the percentage of need that was met of students who were awarded any need-based aid. | 59%     | 55%     | 39%     |
|-----|--------------------------------------------------------------------------------------------------|---------|---------|---------|
| J   | The average financial aid package of those in line d.                                            | $ 8,704 | $ 8,604 | $ 4,638 |
| K   | Average need-based scholarship and grant award of those in line e                                | $ 8,388 | $ 8,084 | $ 4,164 |
| L   | Average need-based self-help award of those in line f                                            | $ 2,894 | $ 3,747 | $ 3,348 |
| M   | Average need-based loan of those in line f who were awarded a need-based loan                    | $ 2,856 | $ 3,726 | $ 3,343 |
"""

        values = clean(markdown)

        self.assertEqual(values["H.209"]["value"], "59")
        self.assertEqual(values["H.210"]["value"], "8704")
        self.assertEqual(values["H.211"]["value"], "8388")
        self.assertEqual(values["H.212"]["value"], "2894")
        self.assertEqual(values["H.213"]["value"], "2856")
        self.assertEqual(values["H.222"]["value"], "55")
        self.assertEqual(values["H.223"]["value"], "8604")
        self.assertEqual(values["H.224"]["value"], "8084")
        self.assertEqual(values["H.225"]["value"], "3747")
        self.assertEqual(values["H.226"]["value"], "3726")
        self.assertEqual(values["H.235"]["value"], "39")
        self.assertEqual(values["H.236"]["value"], "4638")
        self.assertEqual(values["H.237"]["value"], "4164")
        self.assertEqual(values["H.238"]["value"], "3348")
        self.assertEqual(values["H.239"]["value"], "3343")

    def test_kenyon_layout_h1_h2_rows(self):
        supplemental = """
H. FINANCIAL AID

                                    Aid Awarded                                                       need.)
     Scholarships/Grants
     Federal                                                                           $1,782,596           $69,510
     State all states, not only the state in which your institution is located
                                                                                         $161,293           $78,725
     Institutional: Endowed scholarships, annual gifts and tuition funded
     grants, awarded by the college, excluding athletic aid and tuition
     waivers (which are reported below).                                             $49,567,760        $13,491,764
     Scholarships/grants from external sources (e.g. Kiwanis, National
     Merit) not awarded by the college                                                $1,765,285         $3,184,822
     Total Scholarships/Grants                                                        $53,276,934        $16,824,821
     Self-Help
     Student loans from all sources (excluding parent loans)                            $1,917,091        $3,358,563
     Federal Work-Study                                                                   $182,444
     State and other (e.g., institutional) work-study/employment (Note:
     Excludes Federal Work-Study captured above.)                                         $514,181              $692
     Total Self-Help                                                                    $2,613,716        $3,359,255
     Parent Loans                                                                         $207,467        $3,118,470
     Tuition Waivers
     Note: Reporting is optional. Report tuition waivers in this row if you
     choose to report them. Do not report tuition waivers elsewhere.                      $907,350        $1,646,822
     Athletic Awards                                                                            $0                $0

H2   Number of Enrolled Students Awarded Aid: List the number of degree-seeking full-time and less-than-
     full-time undergraduates who applied for and were awarded financial aid from any source.

     A Number of degree-seeking undergraduate students
       (CDS Item B1 if reporting on Fall 2024 cohort)                 439                1730
     B Number of students in line a who applied for need-
                                                                    293             1056
       based financial aid
     C Number of students in line b who were determined to
                                                                    220              848
       have financial need
     D Number of students in line c who were awarded any
                                                                    220              848
       financial aid
     E Number of students in line d who were awarded any
                                                                    220              848
       need-based scholarship or grant aid
     F Number of students in line d who were awarded any
                                                                    144              644
       need-based self-help aid
     G Number of students in line d who were awarded any
                                                                    126              343
       non-need-based scholarship or grant aid
     H Number of students in line d whose need was fully met
       (exclude PLUS loans, unsubsidized loans, and private         220              848
       alternative loans)
     I On average, the percentage of need that was met of
       students who were awarded any need-based aid.
                                                                  100.0%           100.0%
     J The average financial aid package of those in line d.
                                                                 $ 59,726         $ 61,444
     K Average need-based scholarship and grant award of
       those in line e
                                                                 $ 57,924         $ 59,041
     L Average need-based self-help award (excluding PLUS
       loans) of those in line f                                $ 2,752          $ 3,164
     M Average need-based loan of those in line f who were awarded a need-based loan
                                                                 $ 1,582          $ 2,101

H2A Number of Enrolled Students Awarded Non-need-based Scholarships and Grants:
"""

        values = clean("", supplemental_text=supplemental)

        self.assertEqual(values["H.115"]["value"], "907350")
        self.assertEqual(values["H.116"]["value"], "0")
        self.assertEqual(values["H.126"]["value"], "1646822")
        self.assertEqual(values["H.201"]["value"], "439")
        self.assertEqual(values["H.202"]["value"], "293")
        self.assertEqual(values["H.208"]["value"], "220")
        self.assertEqual(values["H.209"]["value"], "100.0")
        self.assertEqual(values["H.210"]["value"], "59726")
        self.assertEqual(values["H.214"]["value"], "1730")
        self.assertEqual(values["H.215"]["value"], "1056")
        self.assertEqual(values["H.221"]["value"], "848")
        self.assertEqual(values["H.222"]["value"], "100.0")
        self.assertEqual(values["H.223"]["value"], "61444")
        self.assertNotIn("H.227", values)


if __name__ == "__main__":
    unittest.main()
