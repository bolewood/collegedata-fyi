from __future__ import annotations

import unittest

from tier4_cleaner import clean


class Tier4CleanerE1E3Test(unittest.TestCase):
    def test_e1_e3_layout_checkboxes_and_other_text(self):
        supplemental = """
                   E. ACADEMIC OFFERINGS AND POLICIES
E1   Special study options: Identify those programs available at your institution.
     Refer to the glossary for definitions.

     Accelerated program
     Comprehensive transition and postsecondary program for students with intellectual disabilities
 x   Cross-registration
 x   Distance learning
 x   Double major
 x   Dual enrollment
     English as a Second Language (ESL)
     Exchange student program (domestic)
     External degree program
 x   Honors Program
 x   Independent study
 x   Internships
     Liberal arts/career combination
     Student-designed major
 x   Study abroad
     Teacher certification program
 x   Undergraduate Research
     Weekend college
 x   Other (specify):
     Microcredentials

E2   Has been removed from the CDS.

E3   Areas in which all or most students are required to complete some course
     work prior to graduation:
 x   Arts/fine arts
 x   Computer literacy
 x   English (including composition)
 x   Foreign languages
 x   History
     Physical Education
 x   Humanities
 x   Intensive writing
 x   Mathematics
     Philosophy
 x   Sciences (biological or physical)
 x   Social science
 x   Other (describe):
     Communications

CDS-E
"""

        values = clean("", supplemental_text=supplemental)

        self.assertEqual(values["E.117"]["value"], "X")
        self.assertEqual(values["E.119"]["value"], "X")
        self.assertEqual(values["E.120"]["value"], "Microcredentials")
        self.assertEqual(values["E.313"]["value"], "X")
        self.assertEqual(values["E.314"]["value"], "Communications")
        self.assertNotIn("E.101", values)
        self.assertNotIn("E.116", values)
        self.assertNotIn("E.118", values)
        self.assertNotIn("E.306", values)
        self.assertNotIn("E.310", values)

    def test_e1_split_marker_from_docling_markdown(self):
        markdown = """
- E1 Special study options: Identify those programs available at your institution.

x

Undergraduate Research

- [ ] x Other (specify):

Microcredentials

- E2 Has been removed from the CDS.
"""

        values = clean(markdown)

        self.assertEqual(values["E.117"]["value"], "X")
        self.assertEqual(values["E.120"]["value"], "Microcredentials")


if __name__ == "__main__":
    unittest.main()
