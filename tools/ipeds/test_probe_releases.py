from __future__ import annotations

import unittest
from datetime import date

from tools.ipeds.probe_releases import next_collection_year, summarize_probe


class IpedsReleaseProbeTests(unittest.TestCase):
    def test_next_collection_year_rolls_two_digit_suffix(self) -> None:
        self.assertEqual(next_collection_year("2024-25"), "2025-26")
        self.assertEqual(next_collection_year("2099-00"), "2100-01")

    def test_probe_noops_until_ten_month_due_date(self) -> None:
        loaded = [{
            "collection_year": "2024-25",
            "data_year": 2024,
            "release_type": "provisional",
            "release_date": "2026-03-01",
            "metadata_url": "https://example.test/IPEDS202425Tablesdoc.xlsx",
            "access_url": "https://example.test/IPEDS_2024-25_Provisional.zip",
        }]
        remote = [{
            "collection_year": "2025-26",
            "data_year": 2025,
            "release_type": "provisional",
            "release_date": "2027-01-01",
            "release_date_text": "January 2027",
            "metadata_url": "https://example.test/IPEDS202526Tablesdoc.xlsx",
            "access_url": "https://example.test/IPEDS_2025-26_Provisional.zip",
        }]
        summary = summarize_probe(loaded, remote, as_of=date(2026, 12, 31), probe_delay_months=10)
        self.assertEqual({target["status"] for target in summary["targets"]}, {"not_due"})

        summary = summarize_probe(loaded, remote, as_of=date(2027, 1, 1), probe_delay_months=10)
        by_key = {(target["collection_year"], target["release_type"]): target for target in summary["targets"]}
        self.assertEqual(by_key[("2025-26", "provisional")]["status"], "available")
        self.assertEqual(by_key[("2024-25", "final")]["status"], "not_available")

    def test_probe_marks_already_loaded_target(self) -> None:
        loaded = [
            {
                "collection_year": "2024-25",
                "data_year": 2024,
                "release_type": "provisional",
                "release_date": "2026-03-01",
            },
            {
                "collection_year": "2024-25",
                "data_year": 2024,
                "release_type": "final",
                "release_date": "2027-01-01",
            },
        ]
        summary = summarize_probe(loaded, [], as_of=date(2027, 1, 1), probe_delay_months=10)
        by_key = {(target["collection_year"], target["release_type"]): target for target in summary["targets"]}
        self.assertEqual(by_key[("2024-25", "final")]["status"], "loaded")


if __name__ == "__main__":
    unittest.main()
