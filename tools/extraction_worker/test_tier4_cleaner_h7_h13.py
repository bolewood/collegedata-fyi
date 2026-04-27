from __future__ import annotations

import unittest

from tier4_cleaner import clean


class Tier4CleanerH7H13Test(unittest.TestCase):
    def test_h7_h13_forms_deadlines_and_aid_types_from_layout(self):
        supplemental = """
H. FINANCIAL AID

      Total dollar amount of institutional financial aid awarded to undergraduate degree-seeking
      nonresidents:                                                                                    $43,780

H7    Check off all financial aid forms nonresident first-year financial aid applicants must submit:

      Institution's own financial aid form
      CSS/Financial Aid PROFILE
  x   Other (specify):

       F-1 students must provide a International Student Financial Form
      https://www.suny.edu/media/suny/content-
      assets/documents/international-student/FSA-4.pdf

      Process for First-Year Students
H8    Check off all financial aid forms domestic first-year financial aid applicants must submit:

  x   FAFSA
      Institution's own financial aid form
      CSS PROFILE
      State aid form
      Noncustodial PROFILE
      Business/Farm Supplement
      Other (specify):

H9    Indicate filing dates for first-year students:
         Priority date for filing required financial aid forms:      1-Apr

         Deadline for filing required financial aid forms:

         No deadline for filing required forms (applications
         processed on a rolling basis)

H10 Indicate notification dates for first-year students (answer a or b):

         a) Students notified on or about (date):

        b) Students notified on a rolling basis:
      x Yes
        No
        If yes, starting date:
        1-Mar

H11 Indicate reply dates:
    Students must reply by (date):
    or within _______ weeks of notification.

      Types of Aid Available
      Please check off all types of aid available to undergraduates at your institution:
H12 Loans

  x   Federal Direct Subsidized Loans
  x   Federal Direct Unsubsidized Loans
  x   Federal Direct PLUS Loans
      Federal Nursing Loans
      State Loans
      College/university loans from institutional funds
      Other (specify):

H13 Need Based Scholarships and Grants

  x   Federal Pell
  x   Federal SEOG
  x   State scholarships/grants
  x   Private scholarships

CDS-H
"""

        values = clean("", supplemental_text=supplemental)

        self.assertEqual(values["H.606"]["value"], "43780")
        self.assertEqual(values["H.703"]["value"], "X")
        self.assertIn("F-1 students", values["H.704"]["value"])
        self.assertIn("content-assets/documents", values["H.704"]["value"])
        self.assertEqual(values["H.801"]["value"], "X")
        self.assertNotIn("H.802", values)
        self.assertEqual(values["H.901"]["value"], "X")
        self.assertEqual(values["H.902"]["value"], "4")
        self.assertEqual(values["H.903"]["value"], "1")
        self.assertNotIn("H.904", values)
        self.assertNotIn("H.907", values)
        self.assertEqual(values["H.1004"]["value"], "X")
        self.assertEqual(values["H.1005"]["value"], "3")
        self.assertEqual(values["H.1006"]["value"], "1")
        self.assertEqual(values["H.1201"]["value"], "X")
        self.assertEqual(values["H.1202"]["value"], "X")
        self.assertEqual(values["H.1203"]["value"], "X")
        self.assertNotIn("H.1204", values)
        self.assertEqual(values["H.1301"]["value"], "X")
        self.assertEqual(values["H.1302"]["value"], "X")
        self.assertEqual(values["H.1303"]["value"], "X")
        self.assertEqual(values["H.1304"]["value"], "X")
        self.assertNotIn("H.1305", values)

    def test_kenyon_checked_forms_reply_date_and_institutional_loans(self):
        supplemental = """
H. FINANCIAL AID

H7    Check off all financial aid forms nonresident first-year financial aid applicants must submit:

  X   Institution's own financial aid form
  X   CSS/Financial Aid PROFILE
  X   Other (specify):
                    Either the institutional form OR the CSS Profile

      Process for First-Year Students
H8    Check off all financial aid forms domestic first-year financial aid applicants must submit:

  x   FAFSA
      Institution's own financial aid form
  x   CSS PROFILE
      State aid form
  x   Noncustodial PROFILE
      Business/Farm Supplement
      Other (specify):

H9    Indicate filing dates for first-year students:
         Priority date for filing required financial aid forms:        15-Jan

         Deadline for filing required financial aid forms:             15-Jan

H11 Indicate reply dates:
    Students must reply by (date):                                   5/1
    or within _______ weeks of notification.

H12 Loans

  x   Federal Direct Subsidized Loans
  x   Federal Direct Unsubsidized Loans
  x   Federal Direct PLUS Loans
      Federal Nursing Loans
      State Loans
  x   College/university loans from institutional funds
      Other (specify):

H13 Need Based Scholarships and Grants
"""

        values = clean("", supplemental_text=supplemental)

        self.assertEqual(values["H.701"]["value"], "X")
        self.assertEqual(values["H.702"]["value"], "X")
        self.assertEqual(values["H.703"]["value"], "X")
        self.assertEqual(values["H.704"]["value"], "Either the institutional form OR the CSS Profile")
        self.assertEqual(values["H.801"]["value"], "X")
        self.assertNotIn("H.802", values)
        self.assertEqual(values["H.803"]["value"], "X")
        self.assertEqual(values["H.805"]["value"], "X")
        self.assertEqual(values["H.904"]["value"], "X")
        self.assertEqual(values["H.905"]["value"], "1")
        self.assertEqual(values["H.906"]["value"], "15")
        self.assertEqual(values["H.1101"]["value"], "5")
        self.assertEqual(values["H.1102"]["value"], "1")
        self.assertEqual(values["H.1206"]["value"], "X")
        self.assertNotIn("H.1204", values)


if __name__ == "__main__":
    unittest.main()
