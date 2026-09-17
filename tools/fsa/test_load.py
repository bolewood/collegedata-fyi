"""Loader fact-stamping tests (no live database)."""

from __future__ import annotations

import unittest

from tools.fsa.load import fact_records
from tools.fsa.match import DirectoryRow
from tools.fsa.parse import FsaRow, ParsedWorkbook
from datetime import date


def _parsed(*rows: FsaRow) -> ParsedWorkbook:
    return ParsedWorkbook(
        title="Nonpayment Rates by Institution (as of May 2026)",
        as_of_label="late May 2026",
        as_of_date=date(2026, 5, 31),
        cohort_window_start=date(2020, 1, 1),
        cohort_window_end=date(2025, 5, 31),
        data_run_note="",
        header_row=3,
        opeid_digit_length=6,
        opeid_storage="text",
        rate_scale="0-1",
        suppression_tokens=("<10%",),
        rows=rows,
        skipped_blank=0,
    )


class FactRecordTests(unittest.TestCase):
    def test_stamps_school_id_and_hides_unmatched(self):
        parsed = _parsed(
            FsaRow("001535", "UF", "PUBLIC", "FL", 11500, "11500", 0.05, "0.05", False, True),
            FsaRow("099999", "Ghost", "PUBLIC", "ZZ", 100, "100", 0.4, "0.4", False, True),
        )
        facts, summary = fact_records(
            parsed,
            [
                DirectoryRow("134130", "uf", "University of Florida", True, True, "00153500", "001535"),
            ],
        )
        by_opeid = {row["opeid"]: row for row in facts}
        self.assertEqual(by_opeid["001535"]["school_id"], "uf")
        self.assertTrue(by_opeid["001535"]["public_visible"])
        self.assertIsNone(by_opeid["099999"]["school_id"])
        self.assertFalse(by_opeid["099999"]["public_visible"])
        self.assertEqual(summary["matched"], 1)

    def test_suppressed_rate_not_public_even_when_matched(self):
        parsed = _parsed(
            FsaRow("001535", "UF", "PUBLIC", "FL", None, "<100", None, "<10%", True, False),
        )
        facts, _ = fact_records(
            parsed,
            [DirectoryRow("134130", "uf", "UF", True, True, "00153500", "001535")],
        )
        self.assertEqual(facts[0]["school_id"], "uf")
        self.assertFalse(facts[0]["public_visible"])
        self.assertIsNone(facts[0]["nonpayment_rate"])


if __name__ == "__main__":
    unittest.main()
