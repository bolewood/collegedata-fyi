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

    def test_omitted_after_collapse_hides_both_rollups(self):
        parsed = _parsed(
            FsaRow("001535", "A", "PUBLIC", "FL", 100, "100", 0.1, "0.1", False, True),
            FsaRow("001536", "B", "PUBLIC", "FL", 200, "200", 0.2, "0.2", False, True),
        )
        facts, summary = fact_records(
            parsed,
            [
                DirectoryRow("134130", "uf", "UF", True, True, "00153500", "001535"),
                DirectoryRow("134131", "uf", "UF", True, True, "00153600", "001536"),
            ],
        )
        self.assertEqual(summary["omitted_after_collapse"], ["uf"])
        self.assertTrue(all(row["school_id"] is None for row in facts))
        self.assertTrue(all(not row["public_visible"] for row in facts))


class ApplyReleaseTests(unittest.TestCase):
    def test_same_sha_reload_is_one_rpc(self):
        from tools.fsa.load import apply_release

        parsed = _parsed(
            FsaRow("001535", "UF", "PUBLIC", "FL", 100, "100", 0.05, "0.05", False, True),
        )
        facts, _ = fact_records(
            parsed,
            [DirectoryRow("134130", "uf", "UF", True, True, "00153500", "001535")],
        )

        class FakeClient:
            def __init__(self):
                self.calls: list[tuple[str, dict]] = []

            def rpc(self, name, args):
                self.calls.append((name, args))

                class Chain:
                    def execute(_self):
                        class Result:
                            data = "rel-1"

                        return Result()

                return Chain()

        client = FakeClient()
        first = apply_release(
            client,
            parsed,
            facts,
            source_url="https://example.test/nonpayment-rates.xlsx",
            source_sha256="abc",
            announcement_url=None,
        )
        second = apply_release(
            client,
            parsed,
            facts,
            source_url="https://example.test/nonpayment-rates.xlsx",
            source_sha256="abc",
            announcement_url=None,
        )
        self.assertEqual(first, "rel-1")
        self.assertEqual(second, "rel-1")
        self.assertEqual(len(client.calls), 2)
        for name, args in client.calls:
            self.assertEqual(name, "apply_fsa_nonpayment_release")
            self.assertEqual(args["release"]["source_sha256"], "abc")
            self.assertEqual(len(args["facts"]), 1)
            self.assertEqual(args["facts"][0]["opeid"], "001535")


class ScorecardOpeidTests(unittest.TestCase):
    def test_opeid6_mismatch_keeps_eight_digit_opeid(self):
        import tempfile
        from pathlib import Path

        from tools.fsa.load import read_scorecard_opeids

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "scorecard.csv"
            path.write_text(
                "UNITID,OPEID,OPEID6,INSTNM\n"
                "458973,10145901,001459,Strayer University-Texas\n",
                encoding="utf-8",
            )
            rows = read_scorecard_opeids(path)
        self.assertEqual(rows["458973"]["OPEID"], "10145901")
        self.assertEqual(rows["458973"]["OPEID6"], "101459")


if __name__ == "__main__":
    unittest.main()
