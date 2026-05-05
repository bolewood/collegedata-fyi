from __future__ import annotations

import unittest

from tier4_cleaner import clean


class Tier4CleanerAGeneralTest(unittest.TestCase):
    def test_question_number_led_export_rows(self):
        markdown = """
## 2024-2025 Common Data Set Pittsburgh Campus
## A. GENERAL INFORMATION
| A1   | Address Information Address Information | Response Text Response Text |
|------|-----------------------------------------|-----------------------------|
| A101 | Name of College/University:             | University of Pittsburgh    |
| A102 | Mailing Address:                        | 4200 Fifth Avenue           |

| A2   | Source of institutional control (Check only one): | Response 'x' |
|------|---------------------------------------------------|--------------|
| A201 | Public                                            | X            |
| A202 | Private (nonprofit)                               |              |

"""

        values = clean(markdown)

        self.assertEqual(values["A.101"]["value"], "University of Pittsburgh")
        self.assertEqual(values["A.102"]["value"], "4200 Fifth Avenue")
        self.assertEqual(values["A.201"]["value"], "X")

    def test_page_one_general_information_from_layout_text(self):
        supplemental = """
A0   Respondent Information (Not for Publication)
     Name:                                        Sylvia E. Navarro Nicosia
     Title:                                       Institutional Research & Assessment Specialist
     Office:                                      Institutional Research & Effectiveness
     Mailing Address:                             2350 Broadhollow Road
     City/State/Zip/Country:                      Farmingdalele, NY 11735
     Phone:                                       934-420-5361
     Fax:
     E-mail Address:                              nicosise@farmingdale.edu

     Are your responses to the CDS posted for      x   Yes
     reference on your institution's Web site?         No

     If yes, please provide the URL of the corresponding Web page:
                        https://www.farmingdale.edu/institutional-research/publications.shtml

A0A We invite you to indicate if there are items on the CDS for which you cannot use the requested analytic
    convention, cannot provide data for the cohort requested, whose methodology is unclear, or about which
    you have questions or comments in general.

A1   Address Information
     Name of College/University:                        Farmingdale State College, State University of New
     Mailing Address:                                   2350 Broadhollow Road
     City/State/Zip/Country:                            Farmingdalle, NY 11735-1021
     Street Address (if different):
     City/State/Zip/Country:
     Main Phone Number:                                 934-420-2000
     WWW Home Page Address:                             https://www.farmingdale.edu/
     Admissions Phone Number:                           934-420-2200
     Admissions Toll-Free Phone Number:
     Admissions Office Mailing Address:
     City/State/Zip/Country:
     Admissions E-mail Address:                         admissions@farmingdale.edu
     If there is a separate URL for your school's online application, please specify:
     https://www.suny.edu/applysuny/

A2   Source of institutional control (Check only one):

 x   Public
     Private (nonprofit)
     Proprietary

A3   Classify your undergraduate institution:

 x   Coeducational college
     Men's college
     Women's college

A4   Academ  ic year calendar:

 x   Semester
     Quarter
     Trimester
     4-1-4
     Continuous
     Differs by program (describe):

A5   Degrees offered by your institution:

A6   Diversity, Equity, and Inclusion

     If you have a diversity, equity, and inclusion office or department, please provide the URL of the corresponding Web page:
     https://www.farmingdale.edu/equity-diversity/
"""

        values = clean("", supplemental_text=supplemental)

        self.assertEqual(values["A.001"]["value"], "Sylvia E. Navarro")
        self.assertEqual(values["A.002"]["value"], "Nicosia")
        self.assertEqual(values["A.003"]["value"], "Institutional Research & Assessment Specialist")
        self.assertEqual(values["A.004"]["value"], "Institutional Research & Effectiveness")
        self.assertEqual(values["A.005"]["value"], "2350 Broadhollow Road")
        self.assertEqual(values["A.008"]["value"], "Farmingdalele")
        self.assertEqual(values["A.009"]["value"], "NY")
        self.assertEqual(values["A.010"]["value"], "11735")
        self.assertEqual(values["A.012"]["value"], "934-420-5361")
        self.assertEqual(values["A.013"]["value"], "nicosise@farmingdale.edu")
        self.assertEqual(values["A.014"]["value"], "Yes")
        self.assertEqual(
            values["A.015"]["value"],
            "https://www.farmingdale.edu/institutional-research/publications.shtml",
        )
        self.assertEqual(
            values["A.101"]["value"],
            "Farmingdale State College, State University of New",
        )
        self.assertEqual(values["A.102"]["value"], "2350 Broadhollow Road")
        self.assertEqual(values["A.105"]["value"], "Farmingdalle")
        self.assertEqual(values["A.106"]["value"], "NY")
        self.assertEqual(values["A.107"]["value"], "11735-1021")
        self.assertEqual(values["A.109"]["value"], "934")
        self.assertEqual(values["A.110"]["value"], "420-2000")
        self.assertEqual(values["A.112"]["value"], "https://www.farmingdale.edu/")
        self.assertEqual(values["A.121"]["value"], "934")
        self.assertEqual(values["A.122"]["value"], "420-2200")
        self.assertEqual(values["A.127"]["value"], "admissions@farmingdale.edu")
        self.assertEqual(values["A.128"]["value"], "https://www.suny.edu/applysuny/")
        self.assertEqual(values["A.201"]["value"], "Public")
        self.assertEqual(values["A.301"]["value"], "Coeducational college")
        self.assertEqual(values["A.401"]["value"], "Semester")
        self.assertEqual(values["A.601"]["value"], "https://www.farmingdale.edu/equity-diversity/")

    def test_kenyon_layout_spacing_artifacts(self):
        supplemental = """
A0      Respondent Inform ation (Not for Publication)
        Name:                                                                                               Erika Farfan
        Title:                                                                                               A VP fo r  I R
        Offic e:                                                                                             Offic e of I R
        Mailing Address:                                                                                103 College Drive
        City/State/Zip/Country:                                                                                Gambier
        Phone:                                                                                                   Ohio
        F  a  x:                                                                                                43022
        E-mail Address:

        Are your responses to the CDS posted for                         X    Yes
        reference on your institution's W   eb site?                          No

        If yes, please provide the URL of the corresponding W   eb page:
                   https://www.kenyon.edu/offices-and-services/office-of-institutional-research/common-data-sets/

A0A     We invite you to indicate if there are items on the CDS.

A1                                        Address Inform ation
        Name of College/University:                                                                      Kenyon College
        Mailing Address:                                                                                103 Chase Ave
        City/State/Zip/Country:                                                                      Gambier, Ohio 43022
        WWW Home Page Address:                             kenyon.edu
        Admissions E-mail Address:                         admissions@kenyon.edu

A2   Source of institutional control (Check only one):
 X   Private (nonprofit)

A3   Classify your undergraduate institution:
 X   Coeducational college

A4   Academic year calendar:
 X   Semester

A5   Degrees offered by your institution:
 X   Bachelor's

A6   Diversity, Equity, and Inclusion
     If you have a diversity, equity, and inclusion office or department, please provide the URL of the corresponding Web page:
     https://www.kenyon.edu/campus-life/diversity-inclusion/odei/
"""

        values = clean("", supplemental_text=supplemental)

        self.assertEqual(values["A.001"]["value"], "Erika")
        self.assertEqual(values["A.002"]["value"], "Farfan")
        self.assertEqual(values["A.003"]["value"], "AVP for IR")
        self.assertEqual(values["A.004"]["value"], "Office of IR")
        self.assertEqual(values["A.005"]["value"], "103 College Drive")
        self.assertEqual(values["A.008"]["value"], "Gambier")
        self.assertEqual(values["A.009"]["value"], "Ohio")
        self.assertEqual(values["A.010"]["value"], "43022")
        self.assertNotIn("A.012", values)
        self.assertNotIn("A.013", values)
        self.assertEqual(values["A.014"]["value"], "Yes")
        self.assertEqual(
            values["A.015"]["value"],
            "https://www.kenyon.edu/offices-and-services/office-of-institutional-research/common-data-sets/",
        )
        self.assertEqual(values["A.101"]["value"], "Kenyon College")
        self.assertEqual(values["A.102"]["value"], "103 Chase Ave")
        self.assertEqual(values["A.105"]["value"], "Gambier")
        self.assertEqual(values["A.106"]["value"], "Ohio")
        self.assertEqual(values["A.107"]["value"], "43022")
        self.assertEqual(values["A.112"]["value"], "kenyon.edu")
        self.assertNotIn("A.110", values)
        self.assertEqual(values["A.127"]["value"], "admissions@kenyon.edu")


if __name__ == "__main__":
    unittest.main()
