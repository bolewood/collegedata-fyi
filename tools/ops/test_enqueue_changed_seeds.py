"""Tests for archive enqueue of changed finder seeds."""

from __future__ import annotations

import unittest

from tools.ops.enqueue_changed_seeds import (
    CANARY_SCHOOL_ID,
    canary_filter_error,
    changed_seed_ids,
    chunk_filter_error,
    chunked,
)


class ChangedSeedIdsTests(unittest.TestCase):
    def test_detects_url_change_and_unknown_to_active(self) -> None:
        before = [
            {"id": "a", "scrape_policy": "active", "discovery_seed_url": "https://a.edu/old.pdf"},
            {"id": "b", "scrape_policy": "unknown"},
            {"id": "c", "scrape_policy": "active", "discovery_seed_url": "https://c.edu/cds/"},
        ]
        after = [
            {"id": "a", "scrape_policy": "active", "discovery_seed_url": "https://a.edu/ir/cds/"},
            {"id": "b", "scrape_policy": "active", "discovery_seed_url": "https://b.edu/cds/"},
            {"id": "c", "scrape_policy": "active", "discovery_seed_url": "https://c.edu/cds/"},
        ]
        self.assertEqual(changed_seed_ids(before, after), ["a", "b"])

    def test_chunks_ids(self) -> None:
        self.assertEqual(chunked(["a", "b", "c", "d"], 2), [["a", "b"], ["c", "d"]])


class SchoolIdsCanaryTests(unittest.TestCase):
    def test_accepts_live_filter_echo(self) -> None:
        self.assertIsNone(
            canary_filter_error(
                {
                    "enqueued": 0,
                    "school_ids_requested": 1,
                    "school_ids_matched": 0,
                    "note": "schools.yaml has no archivable schools",
                }
            )
        )

    def test_rejects_missing_filter_echo(self) -> None:
        # Pre-#139 function, or a rollback: extra query params are ignored.
        self.assertIn(
            "not live",
            canary_filter_error(
                {"enqueued": 0, "note": "schools.yaml has no archivable schools"}
            )
            or "",
        )

    def test_rejects_corpus_match(self) -> None:
        self.assertIsNotNone(
            canary_filter_error(
                {
                    "enqueued": 0,
                    "school_ids_requested": 1,
                    "school_ids_matched": 1800,
                }
            )
        )

    def test_chunk_rejects_oversize_enqueue(self) -> None:
        group = ["a", "b"]
        self.assertIsNotNone(
            chunk_filter_error(
                {
                    "enqueued": 50,
                    "school_ids_requested": 2,
                    "school_ids_matched": 2,
                },
                group,
            )
        )
        self.assertIsNone(
            chunk_filter_error(
                {
                    "enqueued": 2,
                    "school_ids_requested": 2,
                    "school_ids_matched": 2,
                },
                group,
            )
        )
        self.assertEqual(CANARY_SCHOOL_ID, "__finder_seed_catchup_canary__")


if __name__ == "__main__":
    unittest.main()
