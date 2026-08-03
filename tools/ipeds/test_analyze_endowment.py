from __future__ import annotations

import json
import sys
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

from tools.ipeds.analyze_endowment import (
    DEFAULT_FIXTURE_UNITIDS,
    FIXTURE_SCHOOL_NAMES,
    analyze_endowment_rows,
    draw_rate_distribution,
    find_finance_source,
    infer_data_year,
    main as analyze_endowment_main,
    parse_unitids,
)


class AnalyzeEndowmentTests(unittest.TestCase):
    def test_corpus_audit_preserves_signs_and_checks_identities(self) -> None:
        rows = [
            {
                "UNITID": "100001",
                "F2H01": "100",
                "F2H02": "110",
                "F2H03A": "5",
                "F2H03B": "20",
                "F2H03C": "-5",
                "F2H03D": "-10",
                "XF2H03C": "R",
            },
            {
                "UNITID": "100002",
                "F2H01": "100",
                "F2H02": "90",
                "F2H03A": "0",
                "F2H03B": "0",
                "F2H03C": "10",
                "F2H03D": "-20",
                "XF2H03C": "R",
            },
            {"UNITID": "100003", "XF2H03C": "A"},
        ]

        report = analyze_endowment_rows(
            rows,
            source_table="F2223_F2",
            fixture_unitids=[100001, 100003, 999999],
        )

        self.assertEqual(report["data_year"], 2023)
        self.assertEqual(report["spending_sign_counts"]["negative"], 1)
        self.assertEqual(report["spending_sign_counts"]["positive"], 1)
        self.assertEqual(report["accounting_identity"]["matching"], 2)
        self.assertEqual(
            report["accounting_identity"]["formula"],
            "(F2H02 - F2H01) = F2H03A + F2H03B + F2H03C + F2H03D",
        )
        self.assertEqual(report["draw_rate_distribution"]["above_5pct"]["count"], 1)
        self.assertEqual(report["rows_with_mapped_part_h_values"], 2)
        self.assertEqual(report["rows_without_mapped_part_h_values"], 1)
        self.assertEqual(report["fixtures"][0]["values"]["F2H03C"], -5)
        self.assertTrue(report["fixtures"][1]["found"])
        self.assertFalse(report["fixtures"][2]["found"])

    def test_infer_data_year_uses_finance_pair_end_year(self) -> None:
        self.assertEqual(infer_data_year("F1920_F2"), 2020)
        self.assertEqual(infer_data_year("F2021_F2"), 2021)
        self.assertIsNone(infer_data_year("HD2024"))

    def test_accounting_identity_report_records_source_residual(self) -> None:
        rows = [{
            "UNITID": "155070",
            "F2H01": "100",
            "F2H02": "101",
            "F2H03A": "0",
            "F2H03B": "0",
            "F2H03C": "0",
            "F2H03D": "0",
        }]

        report = analyze_endowment_rows(
            rows,
            source_table="F2223_F2",
            fixture_unitids=[155070],
        )

        self.assertEqual(report["accounting_identity"]["matching"], 0)
        self.assertEqual(
            report["accounting_identity"]["mismatch_samples"][0]["residual"],
            1,
        )
        self.assertEqual(report["fixtures"][0]["accounting_identity_residual"], 1)

    def test_finance_source_discovery_and_unitid_validation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_dir = Path(tmp)
            with self.assertRaisesRegex(SystemExit, "release.json is required"):
                find_finance_source(data_dir)

            manifest_path = data_dir / "release.json"
            manifest_path.write_text(
                json.dumps({"downloaded_tables": [], "access_exported_tables": []}),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(SystemExit, "lists no F####_F2"):
                find_finance_source(data_dir)

            source = data_dir / "F2223_F2.csv"
            source.touch()
            manifest_path.write_text(
                json.dumps({
                    "downloaded_tables": [],
                    "access_exported_tables": ["F2223_F2"],
                }),
                encoding="utf-8",
            )
            self.assertEqual(find_finance_source(data_dir), source)

            (data_dir / "F2122_F2.zip").touch()  # Stale and absent from inventory.
            self.assertEqual(find_finance_source(data_dir), source)
            manifest_path.write_text(
                json.dumps({
                    "downloaded_tables": ["F2122_F2"],
                    "access_exported_tables": ["F2223_F2"],
                }),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(SystemExit, "Expected one Finance F2 source"):
                find_finance_source(data_dir)

        self.assertEqual(parse_unitids("201195, ,148131"), [201195, 148131])
        with self.assertRaisesRegex(SystemExit, "Invalid UNITID"):
            parse_unitids("not-a-unitid")

        fixture_unitids = parse_unitids(DEFAULT_FIXTURE_UNITIDS)
        self.assertEqual(
            fixture_unitids,
            [201195, 148131, 231420, 203580, 152080],
        )
        self.assertNotIn(206349, fixture_unitids)
        self.assertNotIn(231688, fixture_unitids)
        self.assertEqual(FIXTURE_SCHOOL_NAMES[148131], "Quincy University")
        self.assertEqual(FIXTURE_SCHOOL_NAMES[231420], "Averett University")

    def test_main_records_manifest_provenance_and_fails_missing_fixture(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_dir = Path(tmp)
            source = data_dir / "F2223_F2.csv"
            source.write_text(
                "UNITID,F2H01,F2H02,F2H03A,F2H03B,F2H03C,F2H03D\n"
                "152080,100,101,1,1,-1,0\n",
                encoding="utf-8",
            )
            (data_dir / "release.json").write_text(
                json.dumps({
                    "collection_year": "2023-24",
                    "data_year": 2023,
                    "release_type": "final",
                    "release_date": "2026-03-01",
                    "release_date_text": "March 2026",
                    "metadata_url": "https://example.test/tables.xlsx",
                    "access_url": "https://example.test/access.zip",
                    "source_mode": "access",
                    "downloaded_tables": [],
                    "access_exported_tables": ["F2223_F2"],
                }),
                encoding="utf-8",
            )
            report_path = data_dir / "report.json"
            argv = [
                "analyze_endowment.py",
                "--data-dir", str(data_dir),
                "--unitids", "152080,148131",
                "--out", str(report_path),
            ]
            with patch.object(sys, "argv", argv):
                self.assertEqual(analyze_endowment_main(), 2)

            report = json.loads(report_path.read_text(encoding="utf-8"))
            self.assertEqual(report["release"]["release_type"], "final")
            self.assertEqual(report["release"]["source_mode"], "access")
            self.assertEqual(len(report["source_sha256"]), 64)

    def test_draw_rate_distribution_handles_empty_singleton_and_interpolation(self) -> None:
        empty = draw_rate_distribution([])
        self.assertEqual(empty["eligible"], 0)
        self.assertIsNone(empty["median"])
        self.assertIsNone(empty["above_5pct"]["share"])

        singleton = draw_rate_distribution([Decimal("0.20")])
        self.assertEqual(singleton["median"], 0.2)
        self.assertEqual(singleton["above_15pct"], {"count": 1, "share": 1})

        interpolated = draw_rate_distribution([Decimal("0.02"), Decimal("0.10")])
        self.assertEqual(interpolated["median"], 0.06)

    def test_incomplete_identity_is_ineligible_and_fixture_draw_rate_is_absent(self) -> None:
        report = analyze_endowment_rows(
            [{"UNITID": "201195", "F2H01": "100", "XF2H01": "A"}],
            source_table="F2223_F2",
            fixture_unitids=[201195],
        )

        self.assertEqual(report["accounting_identity"]["eligible"], 0)
        self.assertEqual(report["draw_rate_distribution"]["eligible"], 0)
        self.assertEqual(report["status_counts_by_variable"]["F2H01"], {"A": 1})
        self.assertIsNone(report["fixtures"][0]["draw_rate"])
        self.assertIsNone(report["fixtures"][0]["end_minus_begin_equals_components"])


if __name__ == "__main__":
    unittest.main()
