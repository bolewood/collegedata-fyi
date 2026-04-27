from __future__ import annotations

import unittest

from tier4_cleaner import clean


class Tier4CleanerD1D9Test(unittest.TestCase):
    def test_d1_d9_transfer_admission_from_layout(self):
        supplemental = """
TRANSFER ADMISSION
                      D1-D2: Fall Applicants
                                                                                                                                                                                                                                                                          Yes                                                          No
 D1                                                                                                                                                                                                                                                                 xDoes your institution enroll transfer students? (If no,
                     please skip to Section E)
                     If yes, may transfer students earn advanced standing
                     credit by transferring credits earned from course work                                                                                                                                                                                                    x
                     completed at other colleges/universities?

 D2                  Provide the number of students who applied, were admitted, and enrolled as degree-seeking transfer
                     students in Fall 2024.

                     Transfer Admission                                                                                                      Applicants                                             Admitted                                                    Enrolled
                                                                                                                                                                                                Applicants                                                 Applicants
                     Men                                                                                                                       1,266                                                                                                                                    941                                                                                                                                                559
                     W omen                                                                                                                    1,060                                                                                                                                    713                                                                                                                                                394
                     Another Gender
                     Unknown
                     Total                                                                                                                     2,326                                                                                                                         1,654                                                                                                                                    953

                      D3-D11: Application for Admission
 D3                  Indicate terms for which transfers may enroll:

        x            Fall
                     W inter
        x            Spring
                     Summer
                                                                                                                                                                                                                                                                          Yes                                                          No
 D4                  Must a transfer applicant have a minimum number of
                     credits completed or else must apply as an entering first-                                                                                                                                                                                                                                                           x
                     year student?

 D5                  Indicate all items required of transfer students to apply for admission:
                     High school transcript                                                                                                                                                                                                                                                                                               x
                     College transcript(s)                                                                                                               x
                     Essay or personal                                                                                                                                                                                                                                                                                                                                                                x
                     Interview                                                                                                                                                                                                                                                                                                                                                                        x
                     Standardized test scores                                                                                                                                                                                                                                                                                                                                                         x
                     Statement of good
                     standing from prior                                                                                                                                                                                                                                                                                                                                                              x
                     institution(s)

 D7                  If a minimum college grade point average is required of
                     transfer applicants, specify (on a 4.0 scale):                                                                                                                                                                                                        2.5

 D8                  List any other application requirements specific to transfer applicants:
                     Certain programs may have higher minimum GPA requirements for transfer applicants; programs may
                     have specific deadlines. Please see https://www.farmingdale.edu/admissions/dates-deadlines.shtml for
                     additional information.

 D9                  List application priority, closing, notification, and candidate reply dates for transfer students.
 D9                                                                                                                                                                        Term                                                                                                                                                                            Priority Date                                                          Closing Date                                    Notification Date                                               Reply DateRolling
 D9                  Fall                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                           7/1                                                                                                                                                11/1                                                                                                                                                                                                                                                                                                                                                         x
 D9                  Spring                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                 1/20                                                                                                                                        9/15                                                                                                                                                                                                                                                                                                                                                         x
D10
"""

        values = clean("", supplemental_text=supplemental)

        self.assertEqual(values["D.101"]["value"], "Yes")
        self.assertEqual(values["D.102"]["value"], "Yes")
        self.assertEqual(values["D.201"]["value"], "1266")
        self.assertEqual(values["D.202"]["value"], "1060")
        self.assertEqual(values["D.204"]["value"], "2326")
        self.assertEqual(values["D.205"]["value"], "941")
        self.assertEqual(values["D.206"]["value"], "713")
        self.assertEqual(values["D.208"]["value"], "1654")
        self.assertEqual(values["D.209"]["value"], "559")
        self.assertEqual(values["D.210"]["value"], "394")
        self.assertEqual(values["D.212"]["value"], "953")
        self.assertNotIn("D.203", values)
        self.assertNotIn("D.207", values)
        self.assertNotIn("D.211", values)
        self.assertEqual(values["D.301"]["value"], "X")
        self.assertNotIn("D.302", values)
        self.assertEqual(values["D.303"]["value"], "X")
        self.assertNotIn("D.304", values)
        self.assertEqual(values["D.401"]["value"], "No")
        self.assertEqual(values["D.501"]["value"], "Required of Some")
        self.assertEqual(values["D.502"]["value"], "Required of All")
        self.assertEqual(values["D.503"]["value"], "Not Required")
        self.assertEqual(values["D.504"]["value"], "Not Required")
        self.assertEqual(values["D.505"]["value"], "Not Required")
        self.assertEqual(values["D.506"]["value"], "Not Required")
        self.assertEqual(values["D.701"]["value"], "2.5")
        self.assertIn("higher minimum GPA requirements", values["D.801"]["value"])
        self.assertEqual(values["D.909"]["value"], "7")
        self.assertEqual(values["D.910"]["value"], "1")
        self.assertEqual(values["D.917"]["value"], "11")
        self.assertEqual(values["D.918"]["value"], "1")
        self.assertEqual(values["D.933"]["value"], "X")
        self.assertEqual(values["D.913"]["value"], "1")
        self.assertEqual(values["D.914"]["value"], "20")
        self.assertEqual(values["D.921"]["value"], "9")
        self.assertEqual(values["D.922"]["value"], "15")
        self.assertEqual(values["D.935"]["value"], "X")

    def test_d_resolver_does_not_misread_b1_enrollment_table(self):
        markdown = """
## B1 Institutional Enrollment - Men and Women

| Undergraduate Students: Full-Time | Men | Women | Another Gender | Unknown |
| --- | ---: | ---: | ---: | ---: |
| All other undergraduates enrolled in credit courses | 39 | 16 | | |
| Total undergraduate Full-Time | | | 1 | 0 |
"""

        values = clean(markdown)

        self.assertFalse(any(qn.startswith("D.") for qn in values))


if __name__ == "__main__":
    unittest.main()
