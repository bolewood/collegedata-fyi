from __future__ import annotations

import unittest

from tier4_cleaner import clean


class Tier4CleanerC8Test(unittest.TestCase):
    def test_c8_yes_no_policy_text_and_placement_checkboxes(self):
        markdown = """
## C8: SAT and ACT Policies

## Entrance exams

Does your institution make use of SAT or ACT scores in admission decisions for first-time, first-year, degree-seeking applicants?

Yes

No

x

- C8A If yes, place check marks in the appropriate boxes below to reflect your institution's policies for use in admission for students applying for Fall 2026.

SAT or ACT

x

ACT Only

x

SAT Only

x

- C8D In addition, does your institution use applicants' test scores for academic advising?

Yes

x

No

- C8E Latest date by which SAT or ACT scores must be received for fall-term admission

- C8F If necessary, use this space to clarify your test policies (e.g., if tests are recommended for some students, or if tests are not required of some students due to differences by academic program, student academic background, or if other examinations may be considered in lieu of the SAT and ACT):

- C8G Please indicate which tests your institution uses for placement (e.g., state tests):

- [x] x SAT

- [ ] x ACT

- [ ] AP

- [ ] CLEP

- [ ] x Institutional Exam

- [ ] x State Exam (specify):

If submitted, SAT critical reading and Essays components or ACT Writing components will be used for placement.

NYS Regents Exam for Mathematics and English.

## C9-C12: First-time, first-year Profile
"""

        values = clean(markdown)

        self.assertEqual(values["C.801"]["value"], "No")
        self.assertEqual(values["C.8D"]["value"], "No")
        self.assertEqual(
            values["C.8F"]["value"],
            "If submitted, SAT critical reading and Essays components or ACT Writing components will be used for placement.",
        )
        self.assertEqual(values["C.8G01"]["value"], "X")
        self.assertEqual(values["C.8G02"]["value"], "X")
        self.assertNotIn("C.8G03", values)
        self.assertNotIn("C.8G04", values)
        self.assertEqual(values["C.8G05"]["value"], "X")
        self.assertEqual(values["C.8G06"]["value"], "X")
        self.assertEqual(
            values["C.8G07"]["value"],
            "NYS Regents Exam for Mathematics and English.",
        )
        self.assertNotIn("C.802", values)
        self.assertNotIn("C.803", values)
        self.assertNotIn("C.804", values)

    def test_c801_uses_entrance_exams_block_when_docling_moves_question(self):
        markdown = """
## C8: SAT and ACT Policies

## Entrance exams

Yes

No

x

- C8A If yes, place check marks in the appropriate boxes below to reflect your institution's policies for use in admission for students applying for Fall 2026.

- C8G Please indicate which tests your institution uses for placement (e.g., state tests):

Does your institution make use of SAT or ACT scores in admission decisions for first-time, first-year, degree-seeking applicants?

## C9-C12: First-time, first-year Profile
"""

        values = clean(markdown)

        self.assertEqual(values["C.801"]["value"], "No")

    def test_c8_uses_supplemental_layout_text_when_docling_drops_labels(self):
        markdown = """
## C8: SAT and ACT Policies

## Entrance exams

x

- C8A If yes, place check marks in the appropriate boxes below to reflect your institution's policies for use in admission for students applying for Fall 2026.

- C8D In addition, does your institution use applicants' test scores for academic advising?

- C8E Latest date by which SAT or ACT scores must be received for fall-term admission

## C9-C12: First-time, first-year Profile
"""
        supplemental = """
C8: SAT and ACT Policies
Entrance exams
Yes No
Does your institution make use of SAT or ACT scores in admission
decisions for first-time, first-year, degree-seeking applicants? x
C8A If yes, place check marks in the appropriate boxes below.
C8D In addition, does your institution use applicants' test scores for academic advising?
Yes
x No
C8E Latest date by which SAT or ACT scores must be received for fall-term admission
C9-C12: First-time, first-year Profile
"""

        values = clean(markdown, supplemental_text=supplemental)

        self.assertEqual(values["C.801"]["value"], "No")
        self.assertEqual(values["C.8D"]["value"], "No")


if __name__ == "__main__":
    unittest.main()
