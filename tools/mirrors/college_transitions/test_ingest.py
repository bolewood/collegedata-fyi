"""Unit tests for canonical slug resolution in the College Transitions mirror."""

from __future__ import annotations

import json
import unittest
from unittest.mock import MagicMock, patch

from tools.finder.identity_guard import (
    load_school_claims,
    validated_canonical_alias_slug_map,
)
from tools.mirrors.college_transitions.fetch import build_catalog
from tools.mirrors.college_transitions.ingest import (
    DEFAULT_CATALOG,
    build_ingest_tasks,
    canonicalize_catalog_entries,
    fetch_existing_years,
    post_force_urls,
)


class CollegeTransitionsMirrorSlugTests(unittest.TestCase):
    def test_canonicalize_catalog_entries_resolves_alias_slugs_before_insert(self) -> None:
        raw_entries = [
            {
                "school_name_ct": "Virginia Polytechnic Institute and State University",
                "school_id": "virginia-polytechnic-institute-and-state-university",
                "school_name": "Virginia Polytechnic Institute and State University",
                "match_score": 1.0,
                "years": {
                    "2024-25": "https://drive.google.com/file/d/vt-2024-25/view",
                    "2023-24": "https://drive.google.com/file/d/vt-2023-24/view",
                },
            },
            {
                "school_name_ct": "California Institute of Technology",
                "school_id": "california-institute-of-technology",
                "school_name": "California Institute of Technology",
                "match_score": 1.0,
                "years": {
                    "2024-25": "https://drive.google.com/file/d/caltech-2024-25/view",
                },
            },
        ]
        entries = canonicalize_catalog_entries(raw_entries)
        self.assertEqual([e["school_id"] for e in entries], ["caltech", "virginia-tech"])

        tasks, stats = build_ingest_tasks(
            raw_entries,
            {"virginia-tech": {"2024-25"}},
        )
        self.assertEqual(stats["total_ct_pairs"], 3)
        self.assertEqual(stats["skipped_have"], 1)
        self.assertEqual(
            [(task["school_id"], task["year"]) for task in tasks],
            [("caltech", "2024-25"), ("virginia-tech", "2023-24")],
        )

    def test_fetch_existing_years_maps_alias_rows_to_canonical_slug(self) -> None:
        fake_sb = MagicMock()
        query = fake_sb.table.return_value.select.return_value.in_.return_value.is_.return_value.range.return_value
        query.execute.return_value.data = [
            {
                "school_id": "virginia-polytechnic-institute-and-state-university",
                "cds_year": "2023-24",
                "detected_year": None,
            },
            {
                "school_id": "virginia-tech",
                "cds_year": "2024-25",
                "detected_year": "2024-25",
            },
        ]
        have = fetch_existing_years(
            fake_sb,
            ["virginia-polytechnic-institute-and-state-university"],
            canonical_by_alias={
                "virginia-polytechnic-institute-and-state-university": "virginia-tech",
            },
        )
        self.assertEqual(have["virginia-tech"], {"2023-24", "2024-25"})

    def test_post_force_urls_resolves_alias_slug_before_posting(self) -> None:
        fake_requests = MagicMock()
        fake_response = MagicMock()
        fake_response.status_code = 200
        fake_response.json.return_value = {"outcome": {"action": "archived"}}
        fake_requests.post.return_value = fake_response
        fake_requests.Timeout = TimeoutError

        with patch("tools.mirrors.college_transitions.ingest.requests", fake_requests):
            result = post_force_urls(
                "https://project.supabase.co",
                "secret-key",
                "virginia-polytechnic-institute-and-state-university",
                "Virginia Polytechnic Institute and State University",
                [{"url": "https://drive.google.com/file/d/abc/view", "year": "2024-25"}],
                timeout=30,
                canonical_by_ipeds={"233921": "virginia-tech"},
                canonical_by_alias={
                    "virginia-polytechnic-institute-and-state-university": "virginia-tech",
                },
            )

        self.assertEqual(result["school_id"], "virginia-tech")
        posted_json = fake_requests.post.call_args.kwargs["json"]
        self.assertEqual(posted_json["school_id"], "virginia-tech")

    def test_build_catalog_emits_canonical_slug(self) -> None:
        rows = [
            {
                "school": "Virginia Tech",
                "years": {"2024-25": "https://drive.google.com/file/d/vt/view"},
            }
        ]

        def fake_match(_name: str):
            return (
                {
                    "id": "virginia-polytechnic-institute-and-state-university",
                    "ipeds_id": "233921",
                    "name": "Virginia Polytechnic Institute and State University",
                },
                1.0,
            )

        catalog = build_catalog(
            rows,
            fake_match,
            canonical_by_ipeds={"233921": "virginia-tech"},
            canonical_by_alias={
                "virginia-polytechnic-institute-and-state-university": "virginia-tech",
            },
        )
        self.assertEqual(catalog["entries"][0]["school_id"], "virginia-tech")

    def test_checked_in_catalog_uses_only_canonical_slugs(self) -> None:
        canonical_set = {claim["school_id"] for claim in load_school_claims()}
        canonical_by_alias = validated_canonical_alias_slug_map()
        catalog = json.loads(DEFAULT_CATALOG.read_text(encoding="utf-8"))
        for entry in catalog["entries"]:
            sid = entry["school_id"]
            self.assertNotIn(sid, canonical_by_alias)
            self.assertIn(sid, canonical_set)


if __name__ == "__main__":
    unittest.main()
