"""Regression tests for the retired school redirect manifest guard."""

from __future__ import annotations

import unittest

from tools.finder.school_redirect_guard import audit_redirect_manifest, expected_redirects


class SchoolRedirectGuardTests(unittest.TestCase):
    def test_extracts_retired_aliases_from_identity_claims(self):
        claims = [
            {
                "school_id": "tufts",
                "retired_aliases": ["tufts-university"],
            }
        ]
        self.assertEqual(
            expected_redirects(claims), {"tufts-university": "tufts"}
        )

    def test_reports_missing_wrong_and_unexpected_redirects(self):
        claims = [
            {
                "school_id": "tufts",
                "retired_aliases": ["tufts-university"],
            }
        ]
        errors = audit_redirect_manifest(
            claims,
            {
                "tufts-university": "wrong-school",
                "stale-school": "stale",
            },
        )
        self.assertEqual(len(errors), 3)
        self.assertTrue(any("missing redirect" in error for error in errors))
        self.assertTrue(any("unexpected redirect 'tufts-university'" in error for error in errors))
        self.assertTrue(any("unexpected redirect 'stale-school'" in error for error in errors))

    def test_rejects_ambiguous_retired_aliases(self):
        with self.assertRaisesRegex(ValueError, "maps to both"):
            expected_redirects(
                [
                    {"school_id": "one", "retired_aliases": ["shared"]},
                    {"school_id": "two", "retired_aliases": ["shared"]},
                ]
            )

    def test_rejects_aliases_that_hijack_a_canonical_school(self):
        with self.assertRaisesRegex(ValueError, "collides with a canonical"):
            expected_redirects(
                [
                    {"school_id": "tufts", "retired_aliases": ["mit"]},
                    {"school_id": "mit", "retired_aliases": []},
                ]
            )

    def test_rejects_ambiguous_destinations_and_redirect_chains(self):
        with self.assertRaisesRegex(ValueError, "not a unique canonical"):
            expected_redirects(
                [
                    {"school_id": "shared", "retired_aliases": ["old"]},
                    {"school_id": "shared", "retired_aliases": []},
                ]
            )
        # A redirect chain necessarily retires another canonical destination,
        # so the canonical-collision check rejects it before it can ship.
        with self.assertRaisesRegex(ValueError, "collides with a canonical"):
            expected_redirects(
                [
                    {"school_id": "one", "retired_aliases": ["old-one"]},
                    {"school_id": "two", "retired_aliases": ["one"]},
                ]
            )


if __name__ == "__main__":
    unittest.main()
