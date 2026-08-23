"""Tests for archive enqueue of changed finder seeds."""

from __future__ import annotations

import unittest

from tools.ops.enqueue_changed_seeds import changed_seed_ids, chunked


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


if __name__ == "__main__":
    unittest.main()
