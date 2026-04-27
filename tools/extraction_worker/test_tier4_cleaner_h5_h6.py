from __future__ import annotations

import unittest

from tier4_cleaner import clean


class Tier4CleanerH5H6Test(unittest.TestCase):
    def test_h5_loans_and_h6_nonresident_aid_from_layout(self):
        supplemental = """
H. FINANCIAL AID

H5. Number and percent of students in class (defined in H4 above) borrowing from federal, non-federal, and any
loan sources, and the average (or mean) amount borrowed.

            Any loan program: Federal Perkins, Federal Stafford
            Subsidized and Unsubsidized, institutional, state, private
          A loans that your institution is aware of, etc. Include both         248                 34%                $20,441
            Federal Direct Student Loans and Federal Family
            Education Loans.

            Federal loan programs: Federal Perkins, Federal Stafford
            Subsidized and Unsubsidized. Include both Federal
          B                                                                    236                 33%                 $18,340
            Direct Student Loans and Federal Family Education
            Loans.

          C Institutional loan programs.

          D State loan programs.

          E Private student loans made by a bank or lender.                    31                  4%                  $23,905

          Aid to Undergraduate Degree-seeking Nonresidents
             *   Report numbers and dollar amounts for the same academic year checked in item H1

H6        Indicate your institution's policy regarding institutional scholarship and grant aid for undergraduate degree-seeking
          nonresidents:

    x     Institutional need-based scholarship or grant aid is available
    x     Institutional non-need-based scholarship or grant aid is available
          Institutional scholarship or grant aid is not available

          If institutional financial aid is available for undergraduate degree-seeking nonresidents, provide
          the number of undergraduate degree-seeking nonresidents who were awarded need-based or
          non-need-based aid:                                                                                            25

          Average dollar amount of institutional financial aid awarded to undergraduate degree-seeking
          nonresidents:                                                                                                $1,751

CDS-H
"""

        values = clean("", supplemental_text=supplemental)

        self.assertEqual(values["H.501"]["value"], "248")
        self.assertEqual(values["H.502"]["value"], "236")
        self.assertNotIn("H.503", values)
        self.assertNotIn("H.504", values)
        self.assertEqual(values["H.505"]["value"], "31")
        self.assertEqual(values["H.506"]["value"], "34")
        self.assertEqual(values["H.507"]["value"], "33")
        self.assertNotIn("H.508", values)
        self.assertNotIn("H.509", values)
        self.assertEqual(values["H.510"]["value"], "4")
        self.assertEqual(values["H.511"]["value"], "20441")
        self.assertEqual(values["H.512"]["value"], "18340")
        self.assertNotIn("H.513", values)
        self.assertNotIn("H.514", values)
        self.assertEqual(values["H.515"]["value"], "23905")
        self.assertEqual(values["H.601"]["value"], "X")
        self.assertEqual(values["H.602"]["value"], "X")
        self.assertNotIn("H.603", values)
        self.assertEqual(values["H.604"]["value"], "25")
        self.assertEqual(values["H.605"]["value"], "1751")
        self.assertNotIn("H.606", values)

    def test_h6_layout_average_overrides_markdown_total_misread(self):
        markdown = """
H6 Indicate your institution's policy regarding institutional scholarship and grant aid for undergraduate degree-seeking nonresidents:

Average dollar amount of institutional financial aid awarded to undergraduate degree-seeking nonresidents:

Institutional need-based scholarship or grant aid is available

$43,780
"""
        supplemental = """
H. FINANCIAL AID

H6        Indicate your institution's policy regarding institutional scholarship and grant aid for undergraduate degree-seeking
          nonresidents:

    x     Institutional need-based scholarship or grant aid is available
    x     Institutional non-need-based scholarship or grant aid is available

          If institutional financial aid is available for undergraduate degree-seeking nonresidents, provide
          the number of undergraduate degree-seeking nonresidents who were awarded need-based or
          non-need-based aid:                                                                                            25

          Average dollar amount of institutional financial aid awarded to undergraduate degree-seeking
          nonresidents:                                                                                                $1,751

CDS-H
"""

        values = clean(markdown, supplemental_text=supplemental)

        self.assertEqual(values["H.605"]["value"], "1751")

    def test_kenyon_h5_h6_layout_rows_and_hyphenated_total(self):
        supplemental = """
H. FINANCIAL AID

H5. Number and percent of students in class borrowing from federal, non-federal,
and any loan sources, and the average amount borrowed.

        A Any loan program: Federal Perkins, Federal Stafford
          Subsidized and Unsubsidized, institutional, state,
          private loans that your institution is aware of, etc.      137             37.00%           $24,612

        B Federal loan programs: Federal Perkins, Federal
          Stafford Subsidized and Unsubsidized.                      121             32.00%           $18,118

        C Institutional loan programs.                                60             16.00%            $6,695

        D State loan programs.                                             0            0.00%                $0

        E Private student loans made by a bank or lender.                 18            5.00%             $43,220

      Aid to Undergraduate Degree-seeking Nonresidents

H6    Indicate your institution's policy regarding institutional scholarship and grant aid for undergraduate degree-
      seeking nonresidents:

  x   Institutional need-based scholarship or grant aid is available
  x   Institutional non-need-based scholarship or grant aid is available

      If institutional financial aid is available for undergraduate degree-seeking nonresidents,
      provide the number of undergraduate degree-seeking nonresidents who were awarded
      need-based or non-need-based aid:                                                                   160

      Average dollar amount of institutional financial aid awarded to undergraduate degree-
      seeking nonresidents:                                                                             $67,659

      Total dollar amount of institutional financial aid awarded to undergraduate degree-
      seeking nonresidents:                                                                            $10,825,509
"""

        values = clean("", supplemental_text=supplemental)

        self.assertEqual(values["H.503"]["value"], "60")
        self.assertEqual(values["H.504"]["value"], "0")
        self.assertEqual(values["H.508"]["value"], "16.00")
        self.assertEqual(values["H.509"]["value"], "0.00")
        self.assertEqual(values["H.513"]["value"], "6695")
        self.assertEqual(values["H.514"]["value"], "0")
        self.assertEqual(values["H.604"]["value"], "160")
        self.assertEqual(values["H.605"]["value"], "67659")
        self.assertEqual(values["H.606"]["value"], "10825509")


if __name__ == "__main__":
    unittest.main()
