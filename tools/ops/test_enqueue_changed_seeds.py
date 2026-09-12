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

    def test_duplicate_slugs_compare_by_ipeds_identity(self) -> None:
        before = [
            {
                "id": "bethel-university",
                "ipeds_id": "173160",
                "scrape_policy": "active",
                "discovery_seed_url": "https://www.bethel.edu/cds/",
            },
            {
                "id": "bethel-university",
                "ipeds_id": "219718",
                "scrape_policy": "active",
                "discovery_seed_url": "https://www.bethelu.edu/cds/",
            },
        ]
        after = [
            {
                "id": "bethel-university",
                "ipeds_id": "173160",
                "scrape_policy": "active",
                "discovery_seed_url": "https://www.bethel.edu/cds/",
            },
            {
                "id": "bethel-university",
                "ipeds_id": "219718",
                "scrape_policy": "active",
                "discovery_seed_url": "https://www.bethelu.edu/cds/",
            },
        ]
        self.assertEqual(changed_seed_ids(before, after), [])

    def test_duplicate_slugs_still_detect_actual_institution_change(self) -> None:
        before = [
            {
                "id": "westminster-college",
                "ipeds_id": "179946",
                "scrape_policy": "unknown",
            },
            {
                "id": "westminster-college",
                "ipeds_id": "216807",
                "scrape_policy": "active",
                "discovery_seed_url": "https://www.westminster.edu/old.pdf",
            },
        ]
        after = [
            {
                "id": "westminster-college",
                "ipeds_id": "179946",
                "scrape_policy": "active",
                "discovery_seed_url": "https://www.wcmo.edu/cds/",
            },
            {
                "id": "westminster-college",
                "ipeds_id": "216807",
                "scrape_policy": "active",
                "discovery_seed_url": "https://www.westminster.edu/old.pdf",
            },
        ]
        self.assertEqual(changed_seed_ids(before, after), ["westminster-college"])

    def test_duplicate_slug_changes_emit_one_archive_filter_token(self) -> None:
        before = [
            {
                "id": "bethel-university",
                "ipeds_id": ipeds_id,
                "scrape_policy": "active",
                "discovery_seed_url": f"https://old-{ipeds_id}.edu/cds/",
            }
            for ipeds_id in ("173160", "219718")
        ]
        after = [
            {
                "id": "bethel-university",
                "ipeds_id": ipeds_id,
                "scrape_policy": "active",
                "discovery_seed_url": f"https://new-{ipeds_id}.edu/cds/",
            }
            for ipeds_id in ("173160", "219718")
        ]
        self.assertEqual(changed_seed_ids(before, after), ["bethel-university"])

    def test_slug_change_enqueues_new_archive_filter_id(self) -> None:
        before = [
            {
                "id": "old-school-slug",
                "ipeds_id": "123456",
                "scrape_policy": "active",
                "discovery_seed_url": "https://example.edu/cds/",
            }
        ]
        after = [
            {
                "id": "new-school-slug",
                "ipeds_id": "123456",
                "scrape_policy": "active",
                "discovery_seed_url": "https://example.edu/cds/",
            }
        ]
        self.assertEqual(changed_seed_ids(before, after), ["new-school-slug"])

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

    def test_chunk_allows_duplicate_slug_to_match_multiple_school_rows(self) -> None:
        group = ["bethel-university"]
        self.assertIsNone(
            chunk_filter_error(
                {
                    "enqueued": 2,
                    "school_ids_requested": 1,
                    "school_ids_matched": 2,
                },
                group,
                expected_matches=2,
            )
        )
        self.assertIsNotNone(
            chunk_filter_error(
                {
                    "enqueued": 3,
                    "school_ids_requested": 1,
                    "school_ids_matched": 3,
                },
                group,
                expected_matches=2,
            )
        )


if __name__ == "__main__":
    unittest.main()
