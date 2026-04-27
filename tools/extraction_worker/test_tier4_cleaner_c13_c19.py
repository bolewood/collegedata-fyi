from __future__ import annotations

import unittest

from tier4_cleaner import clean


class Tier4CleanerC13C19Test(unittest.TestCase):
    def test_c13_c19_admission_policies_from_layout(self):
        supplemental = """
Can it be waived for applicants with financial need?                                                                                                                                         x

      x          Same fee
                 Free
                 Reduced
                                                                                                                                                                                                          Yes                                           No
                 Can on-line application fee be waived for applicants                                                                                                                                         x
                 with financial need?

C14              Application closing date
                                                                                                                                                                                                          Yes                                           No
                 Does your institution have an application closing date?                                                                                                                                      x

                                                                                                                                                    Date
                 Application closing date (fall)                                                                                                      6/1
                 Priority Date                                                                                                                        1/3

                                                                                                                                                                                                                                                       Yes                                          No
C15                                                                                                                                                                                                                                                                                                                                                              xAre first-time, first-year students accepted for terms other than
                 the fall?

C16              Notification to applicants of admission decision sent (fill in one only)

      x          On a rolling basis beginning                                                                                                    15-Oct
                 By (date):
                 Other:

C17              Reply policy for admitted applicants (fill in one only)

                 Must reply by (date):
                 No set date
      x          Must reply by May 1st or within                                                                                                                                                                   4                                                                                                                     weeks if notified thereafter
                 Other:

                 Deadline for housing deposit (MMD                                                                                                  1-Jul
                 Amount of housing deposit:                                                                                                            50

                 Refundable if student does not enroll?

      x          Yes, in full
                 Yes, in part
                 No

C18              Deferred admission
                                                                                                                                                                                                                                                       Yes                                          No
                 Does your institution allow students to postpone enrollment after                                                                                                                                                                         x
                 admission?
                 If yes, maximum period of postponement:                                                                                                                                               1 year

C19              Early admission of high school students
                                                                                                                                                                                                                                                       Yes                                          No
                 Does your institution allow high school students to enroll as full-time,
                 first-time, first-year students one year or more before high school                                                                                                                                                                                                                  x
                 graduation?

C20              Common Application: Question removed from CDS.
"""

        values = clean("", supplemental_text=supplemental)

        self.assertEqual(values["C.1303"]["value"], "Yes")
        self.assertEqual(values["C.1304"]["value"], "X")
        self.assertEqual(values["C.1305"]["value"], "Yes")
        self.assertEqual(values["C.1401"]["value"], "Yes")
        self.assertEqual(values["C.1402"]["value"], "6")
        self.assertEqual(values["C.1403"]["value"], "1")
        self.assertEqual(values["C.1404"]["value"], "1")
        self.assertEqual(values["C.1405"]["value"], "3")
        self.assertEqual(values["C.1501"]["value"], "Yes")
        self.assertEqual(values["C.1601"]["value"], "X")
        self.assertEqual(values["C.1602"]["value"], "10")
        self.assertEqual(values["C.1603"]["value"], "15")
        self.assertEqual(values["C.1705"]["value"], "4")
        self.assertEqual(values["C.1709"]["value"], "7")
        self.assertEqual(values["C.1710"]["value"], "1")
        self.assertEqual(values["C.1711"]["value"], "50")
        self.assertEqual(values["C.1712"]["value"], "X")
        self.assertEqual(values["C.1801"]["value"], "Yes")
        self.assertEqual(values["C.1802"]["value"], "1 year")
        self.assertEqual(values["C.1901"]["value"], "No")


if __name__ == "__main__":
    unittest.main()
