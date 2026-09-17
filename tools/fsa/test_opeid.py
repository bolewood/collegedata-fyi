"""Unit tests for OPEID padding and Excel restoration."""

from __future__ import annotations

import unittest

from tools.fsa.opeid import normalize_opeid8, opeid6_from_opeid8, restore_fsa_opeid


class NormalizeOpeid8Tests(unittest.TestCase):
    def test_keeps_eight_digit_campus_key(self):
        self.assertEqual(normalize_opeid8("00100201"), "00100201")
        self.assertEqual(normalize_opeid8(100201), "00100201")

    def test_does_not_use_six_pad_on_eight_digit_int(self):
        # normalize_opeid6 would turn this into 100201.
        self.assertEqual(normalize_opeid8(100201), "00100201")
        self.assertNotEqual(normalize_opeid8(100201), "100201")

    def test_rejects_empty(self):
        self.assertIsNone(normalize_opeid8(None))
        self.assertIsNone(normalize_opeid8(""))
        self.assertIsNone(normalize_opeid8("PrivacySuppressed"))


class RestoreFsaOpeidTests(unittest.TestCase):
    def test_text_six_digit_stays_six(self):
        self.assertEqual(restore_fsa_opeid("001002"), "001002")
        self.assertEqual(restore_fsa_opeid("001535"), "001535")

    def test_numeric_excel_six_digit_does_not_become_eight(self):
        self.assertEqual(restore_fsa_opeid(100201), "100201")
        self.assertEqual(restore_fsa_opeid(1535), "001535")
        self.assertNotEqual(restore_fsa_opeid(100201), "00100201")

    def test_eight_digit_numeric_stays_eight(self):
        self.assertEqual(restore_fsa_opeid(10020101), "10020101")
        self.assertEqual(restore_fsa_opeid("00100201"), "00100201")

    def test_opeid6_slice(self):
        self.assertEqual(opeid6_from_opeid8("00100201"), "001002")
        self.assertEqual(opeid6_from_opeid8("00153500"), "001535")


if __name__ == "__main__":
    unittest.main()
