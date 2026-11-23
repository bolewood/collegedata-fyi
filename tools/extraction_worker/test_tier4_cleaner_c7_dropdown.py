"""C7 on forms that fill it from dropdown menus: the chosen level is printed
beside each factor in the text layer, with no grid of marks (issue #433)."""
import unittest

from tier4_cleaner import clean

_C7 = """
C7. Basis for Selection: Relative Importance of Factors in Admission Decisions
Please indicate the relative importance of each of the following academic and non-academic factors: select from the dropdown menus.
                                              ACADEMIC
Rigor of secondary school record                                        Very Important
Class rank                                                              Very Important
Academic Grade Point Average (GPA)                                      Very Important
Recommendations                                                         Important
Standardized test scores                                                Considered
Application essay                                                       Important
                                             NONACADEMIC
Interview                                                               Not Considered
Extracurriculuar activities                                             Important
Talent/ability                                                          Important
Character/personal qualities                                            Very Important
First generation                                                        Considered
Alumni/ae relation                                                      Considered
Geographical residence                                                  Considered
State residency                                                         Very Important
Religious affilitation/commitment                                       Not Considered
Volunteer work                                                          Considered
Work experience                                                         Considered
Level of applicant's interest                                           Not Considered
Please provide additional information if the importance of any specific academic or nonacademic factors differ by academic program:
C8. SAT and ACT Policies
Does your institution use applicants' test scores for academic advising?                      Important
"""

_GRID = """## C7. Basis for Selection

| Academic | Very Important | Important | Considered | Not Considered |
|---|---|---|---|---|
| Rigor of secondary school record |  | X |  |  |
| Class rank |  |  | X |  |
| Academic GPA | X |  |  |  |
"""


class C7DropdownTextTests(unittest.TestCase):
    def test_levels_printed_beside_factors_are_read(self):
        values = clean("", supplemental_text=_C7, canonical_year="2023-24")
        got = {qn: rec["value"] for qn, rec in values.items() if qn.startswith("C.7")}
        self.assertEqual(len(got), 18)
        self.assertEqual(got["C.701"], "Very Important")   # rigor
        self.assertEqual(got["C.703"], "Very Important")   # "Academic Grade Point Average (GPA)"
        self.assertEqual(got["C.704"], "Considered")       # standardized test scores
        self.assertEqual(got["C.707"], "Not Considered")   # interview
        self.assertEqual(got["C.708"], "Important")        # "Extracurriculuar activities"
        self.assertEqual(got["C.715"], "Not Considered")   # "Religious affilitation/commitment"
        self.assertEqual(got["C.718"], "Not Considered")   # level of applicant's interest

    def test_a_marked_grid_keeps_its_own_reading(self):
        # The grid says Important for rigor; the text lines must not replace it.
        text = _C7.replace("Rigor of secondary school record                                        Very Important",
                           "Rigor of secondary school record                                        Considered    ")
        values = clean(_GRID, supplemental_text=text, canonical_year="2023-24")
        self.assertEqual(values["C.701"]["value"], "Important")
        self.assertEqual(values["C.707"]["value"], "Not Considered")

    def test_a_marked_grid_wins_within_one_pass_too(self):
        # Both readings in the converted text itself: the grid still wins.
        lines = "\n".join(line for line in _C7.splitlines() if line.strip()).replace(
            "Rigor of secondary school record                                        Very Important",
            "Rigor of secondary school record                                        Considered    ")
        values = clean(_GRID + "\n" + lines, canonical_year="2023-24")
        self.assertEqual(values["C.701"]["value"], "Important")
        self.assertEqual(values["C.707"]["value"], "Not Considered")

    def test_a_level_printed_with_extra_spaces_is_read_whole(self):
        spaced = _C7.replace("Class rank                                                              Very Important",
                             "Class rank                                                              Very  Important")
        spaced = spaced.replace("Interview                                                               Not Considered",
                                "Interview                                                               Not   Considered")
        values = clean("", supplemental_text=spaced, canonical_year="2023-24")
        self.assertEqual(values["C.702"]["value"], "Very Important")
        self.assertEqual(values["C.707"]["value"], "Not Considered")

    def test_fewer_than_five_factor_lines_are_not_read(self):
        lines = _C7.splitlines()
        few = "\n".join(lines[:7] + lines[-3:])
        values = clean("", supplemental_text=few, canonical_year="2023-24")
        self.assertFalse([qn for qn in values if qn.startswith("C.7")])

    def test_lines_outside_c7_are_not_read(self):
        values = clean("", supplemental_text=_C7, canonical_year="2023-24")
        self.assertEqual(sum(1 for qn in values if qn.startswith("C.7")), 18)
        other = "Rigor of secondary school record        Very Important\n" * 6
        self.assertFalse([qn for qn in clean("", supplemental_text=other, canonical_year="2023-24") if qn.startswith("C.7")])


if __name__ == "__main__":
    unittest.main()
