from __future__ import annotations

import unittest

from tier4_cleaner import clean


class Tier4CleanerB1Test(unittest.TestCase):
    def test_b1_layout_preserves_wrapped_rows_and_gender_columns(self):
        supplemental = """
B1   Institutional Enrollment - Men and Women
     Undergraduate Students: Full-Time                   Men              Women           Another Gender           Unknown
     Degree-seeking, first-time first-year
     students                                                  1053                705
     Other first-year, degree-seeking                           454                305
     All other degree-seeking                                 3,204              2,210                     1
     Total degree-seeking                                     4,711              3,220                     1                    0
     All other undergraduates enrolled in credit
     courses                                                     39                 16
     Total undergraduate Full-Time Students                   4,750              3,236                     1                    0

     Undergraduate Students: Part-Time                   Men              Women           Another Gender           Unknown
     Degree-seeking, first-time first-year
     students                                                     40                24
     Other first-year, degree-seeking                           105                 89
     All other degree-seeking                                   790                572
     Total degree-seeking                                       935                685                     0                    0
     All other undergraduates enrolled in credit
     courses                                                    161                239
     Total undergraduate Part-Time Students                   1,096                924                     0                    0

     Undergraduate Students: All                         Men              Women           Another Gender           Unknown
     Total undergraduate Students                           5,846            4,160                     1                        0

     Graduate Students: Full-Time
     Degree-seeking, first-time                                    1
     All other degree-seeking                                      3
     All other graduates enrolled in credit
     courses
     Total graduate Full-Time Students                             4                  0                     0                    0

     Graduate Students: Part-Time
     Degree-seeking, first-time                                    5                  2
     All other degree-seeking                                     17                  2
     All other graduates enrolled in credit
     courses                                                       2
     Total graduate Part-Time Students                            24                  4                     0                    0

     Graduate Students: All                              Men              Women           Another Gender           Unknown
     Total Graduate Students                                      28                  4                     0                   0

     All Students: Total                                 Men              Women           Another Gender           Unknown
     Total all students                                     5,874            4,164                     1                        0

     Total all undergraduates                               10,007
     Total all graduate                                          32
     GRAND TOTAL ALL STUDENTS                               10,039

B2   Enrollment by Racial/Ethnic Category.
"""

        values = clean("", supplemental_text=supplemental)

        self.assertEqual(values["B.101"]["value"], "1053")
        self.assertEqual(values["B.126"]["value"], "705")
        self.assertEqual(values["B.103"]["value"], "3204")
        self.assertEqual(values["B.128"]["value"], "2210")
        self.assertEqual(values["B.153"]["value"], "1")
        self.assertEqual(values["B.106"]["value"], "4750")
        self.assertEqual(values["B.131"]["value"], "3236")
        self.assertEqual(values["B.156"]["value"], "1")
        self.assertEqual(values["B.111"]["value"], "161")
        self.assertEqual(values["B.136"]["value"], "239")
        self.assertEqual(values["B.113"]["value"], "5846")
        self.assertEqual(values["B.138"]["value"], "4160")
        self.assertEqual(values["B.163"]["value"], "1")
        self.assertEqual(values["B.117"]["value"], "4")
        self.assertEqual(values["B.142"]["value"], "0")
        self.assertEqual(values["B.167"]["value"], "0")
        self.assertNotIn("B.116", values)
        self.assertNotIn("B.141", values)
        self.assertEqual(values["B.118"]["value"], "5")
        self.assertEqual(values["B.143"]["value"], "2")
        self.assertEqual(values["B.119"]["value"], "17")
        self.assertEqual(values["B.144"]["value"], "2")
        self.assertNotIn("B.169", values)
        self.assertEqual(values["B.120"]["value"], "2")
        self.assertEqual(values["B.121"]["value"], "24")
        self.assertEqual(values["B.146"]["value"], "4")
        self.assertEqual(values["B.122"]["value"], "28")
        self.assertEqual(values["B.147"]["value"], "4")
        self.assertEqual(values["B.125"]["value"], "5874")
        self.assertEqual(values["B.150"]["value"], "4164")
        self.assertEqual(values["B.175"]["value"], "1")
        self.assertEqual(values["B.176"]["value"], "10007")
        self.assertEqual(values["B.177"]["value"], "32")
        self.assertEqual(values["B.178"]["value"], "10039")


if __name__ == "__main__":
    unittest.main()
