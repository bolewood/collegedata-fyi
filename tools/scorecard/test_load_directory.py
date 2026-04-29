"""Unit tests for PRD 015 M1's institution-directory loader. Covers
the deterministic pure functions: UNITID normalization, in-scope
filter, base slug generation, collision resolution, schools.yaml
preservation, and crosswalk row construction.

Run from repo root:
    python -m unittest tools.scorecard.test_load_directory
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tools.scorecard.load_directory import (  # noqa: E402
    DEFAULT_SCHOOLS_YAML,
    _scope_decision,
    assign_slugs,
    base_slug,
    build_crosswalk_rows,
    load_schools_yaml,
    normalize_ipeds,
)


class NormalizeIpedsTests(unittest.TestCase):
    def test_zero_pads_to_six(self):
        self.assertEqual(normalize_ipeds("1234"), "001234")
        self.assertEqual(normalize_ipeds("211440"), "211440")

    def test_handles_float_string(self):
        self.assertEqual(normalize_ipeds("211440.0"), "211440")

    def test_passes_through_seven_digit(self):
        # Some branch campuses exceed 6 digits; do not truncate.
        self.assertEqual(normalize_ipeds("1234567"), "1234567")

    def test_returns_none_for_invalid(self):
        self.assertIsNone(normalize_ipeds(None))
        self.assertIsNone(normalize_ipeds(""))
        self.assertIsNone(normalize_ipeds("abc"))
        self.assertIsNone(normalize_ipeds("0"))
        self.assertIsNone(normalize_ipeds("-5"))


class ScopeDecisionTests(unittest.TestCase):
    def _row(self, **overrides):
        base = dict(
            currently_operating=True,
            undergraduate_enrollment=5000,
            institution_level=1,
            predominant_degree=3,
        )
        base.update(overrides)
        return base

    def test_default_in_scope(self):
        in_scope, reason = _scope_decision(self._row())
        self.assertTrue(in_scope)
        self.assertIsNone(reason)

    def test_closed_institution_excluded(self):
        in_scope, reason = _scope_decision(self._row(currently_operating=False))
        self.assertFalse(in_scope)
        self.assertEqual(reason, "closed")

    def test_zero_undergrad_excluded(self):
        in_scope, reason = _scope_decision(self._row(undergraduate_enrollment=0))
        self.assertFalse(in_scope)
        self.assertEqual(reason, "no_undergraduate_enrollment")

    def test_null_undergrad_excluded(self):
        in_scope, reason = _scope_decision(self._row(undergraduate_enrollment=None))
        self.assertFalse(in_scope)
        self.assertEqual(reason, "no_undergraduate_enrollment")

    def test_iclevel_3_excluded(self):
        # ICLEVEL=3 is "less than two-year" — excluded from MVP.
        in_scope, reason = _scope_decision(self._row(institution_level=3))
        self.assertFalse(in_scope)
        self.assertEqual(reason, "not_two_or_four_year")

    def test_certificate_only_excluded(self):
        # PREDDEG=1 = certificate-only — excluded.
        in_scope, reason = _scope_decision(self._row(predominant_degree=1))
        self.assertFalse(in_scope)
        self.assertEqual(reason, "non_degree_predominant")

    def test_graduate_predominant_with_undergrad_in_scope(self):
        # PREDDEG=4 (graduate) is allowed when UGDS > 0 (per PRD).
        in_scope, _ = _scope_decision(
            self._row(predominant_degree=4, undergraduate_enrollment=100)
        )
        self.assertTrue(in_scope)


class BaseSlugTests(unittest.TestCase):
    def test_lowercases_and_hyphenates(self):
        self.assertEqual(base_slug("Harvard University"), "harvard-university")

    def test_collapses_runs_of_punctuation(self):
        self.assertEqual(base_slug("St. Olaf College"), "st-olaf-college")
        self.assertEqual(
            base_slug("Texas A&M University-Kingsville"),
            "texas-a-m-university-kingsville",
        )

    def test_strips_leading_trailing_hyphens(self):
        self.assertEqual(base_slug("---Quirky Name---"), "quirky-name")

    def test_empty_input_raises(self):
        with self.assertRaises(ValueError):
            base_slug("...")
        with self.assertRaises(ValueError):
            base_slug("")

    def test_deterministic(self):
        # Same INSTNM → same slug, always.
        self.assertEqual(base_slug("Yale University"), base_slug("Yale University"))


class AssignSlugsTests(unittest.TestCase):
    def _row(self, ipeds, name, state="NY", city="New York"):
        return {
            "ipeds_id": ipeds,
            "school_name": name,
            "state": state,
            "city": city,
            "in_scope": True,
        }

    def test_no_collisions_uses_base_slug(self):
        rows = [
            self._row("000001", "Harvard University"),
            self._row("000002", "Yale University"),
        ]
        assigned, collisions = assign_slugs(rows, {})
        self.assertEqual(assigned["000001"], "harvard-university")
        self.assertEqual(assigned["000002"], "yale-university")
        self.assertEqual(collisions, [])

    def test_state_tier_resolves_same_name_different_state(self):
        rows = [
            self._row("000001", "Lincoln College", state="IL", city="Lincoln"),
            self._row("000002", "Lincoln College", state="CA", city="Oakland"),
        ]
        assigned, collisions = assign_slugs(rows, {})
        self.assertEqual(assigned["000001"], "lincoln-college-il")
        self.assertEqual(assigned["000002"], "lincoln-college-ca")
        self.assertEqual({c["tier"] for c in collisions}, {"state"})

    def test_city_tier_resolves_same_name_state_different_city(self):
        rows = [
            self._row("000001", "Community College", state="CA", city="San Diego"),
            self._row("000002", "Community College", state="CA", city="Los Angeles"),
        ]
        assigned, _ = assign_slugs(rows, {})
        self.assertEqual(assigned["000001"], "community-college-ca-san-diego")
        self.assertEqual(assigned["000002"], "community-college-ca-los-angeles")

    def test_ipeds_tier_resolves_identical_name_state_city(self):
        # Pathological — two rows with literally the same INSTNM, state,
        # city. Should still resolve uniquely.
        rows = [
            self._row("000001", "Same Same", state="NY", city="Albany"),
            self._row("000002", "Same Same", state="NY", city="Albany"),
        ]
        assigned, _ = assign_slugs(rows, {})
        self.assertEqual(assigned["000001"], "same-same-ny-albany-000001")
        self.assertEqual(assigned["000002"], "same-same-ny-albany-000002")

    def test_schools_yaml_slug_preserved(self):
        # The Scorecard row's INSTNM would generate "harvard-university"
        # but schools.yaml has it pinned to "harvard". Preserve.
        rows = [self._row("000001", "Harvard University")]
        assigned, _ = assign_slugs(rows, {"000001": "harvard"})
        self.assertEqual(assigned["000001"], "harvard")

    def test_schools_yaml_self_collision_picks_largest_ugds(self):
        # Three schools.yaml entries claim the same slug across different
        # IPEDS — pre-existing data bug we have to handle (e.g. three
        # bethel-university entries in tools/finder/schools.yaml).
        # Winner is the largest-UGDS row; losers fall through to
        # auto-slug + state-tier disambiguation.
        rows = [
            {**self._row("000001", "Bethel University", state="IN"),
             "undergraduate_enrollment": 1008},
            {**self._row("000002", "Bethel University", state="MN"),
             "undergraduate_enrollment": 1871},
            {**self._row("000003", "Bethel University", state="TN"),
             "undergraduate_enrollment": 1547},
        ]
        yaml_map = {
            "000001": "bethel-university",
            "000002": "bethel-university",
            "000003": "bethel-university",
        }
        assigned, collisions = assign_slugs(rows, yaml_map)
        # Largest UGDS (000002, MN) wins the canonical slug.
        self.assertEqual(assigned["000002"], "bethel-university")
        # Losers fall through to state-tier auto-slug — the demoted
        # yaml slug "bethel-university" is in claimed, so even though
        # their auto-base might match, escalation kicks in.
        self.assertEqual(assigned["000001"], "bethel-university-in")
        self.assertEqual(assigned["000003"], "bethel-university-tn")
        # The yaml_self_collision tier shows up in the report.
        kinds = {c["tier"] for c in collisions}
        self.assertIn("yaml_self_collision", kinds)

    def test_schools_yaml_blocks_unrelated_scorecard_collision(self):
        # schools.yaml claims "harvard-university" via a curated slug.
        # A separate Scorecard row whose INSTNM also normalizes to
        # "harvard-university" must NOT steal that slug — it escalates
        # to the state tier instead.
        rows = [
            self._row("000001", "Harvard University", state="MA"),
            self._row("000002", "Harvard University", state="WA"),
        ]
        assigned, _ = assign_slugs(rows, {"000001": "harvard-university"})
        self.assertEqual(assigned["000001"], "harvard-university")
        # The non-yaml row must escalate; without yaml, it would have
        # tied with row 1 and gone to -wa anyway, so this confirms the
        # claim was respected.
        self.assertNotEqual(assigned["000002"], "harvard-university")
        self.assertEqual(assigned["000002"], "harvard-university-wa")


class BuildCrosswalkRowsTests(unittest.TestCase):
    def test_one_primary_per_directory_row(self):
        rows = [
            {"ipeds_id": "000001", "school_id": "harvard", "school_name": "Harvard University"},
            {"ipeds_id": "000002", "school_id": "yale-university", "school_name": "Yale University"},
        ]
        cw = build_crosswalk_rows(rows, {"000001": "harvard"})
        primaries = [r for r in cw if r["is_primary"]]
        self.assertEqual(len(primaries), 2)
        self.assertEqual({r["alias"] for r in primaries}, {"harvard", "yale-university"})

    def test_yaml_slug_emits_auto_alias_when_different(self):
        # schools.yaml uses "harvard"; auto would compute "harvard-university".
        # Both should appear in the crosswalk so search by INSTNM tokens
        # finds the row.
        rows = [
            {"ipeds_id": "000001", "school_id": "harvard", "school_name": "Harvard University"},
        ]
        cw = build_crosswalk_rows(rows, {"000001": "harvard"})
        aliases = sorted({(r["alias"], r["is_primary"], r["source"]) for r in cw})
        self.assertEqual(
            aliases,
            [
                ("harvard", True, "schools_yaml"),
                ("harvard-university", False, "scorecard"),
            ],
        )

    def test_yaml_slug_matching_auto_emits_only_one_alias(self):
        # When the yaml slug equals what the loader would auto-generate,
        # don't double-write the same alias row.
        rows = [
            {"ipeds_id": "000001", "school_id": "yale-university",
             "school_name": "Yale University"},
        ]
        cw = build_crosswalk_rows(rows, {"000001": "yale-university"})
        self.assertEqual(len(cw), 1)
        self.assertTrue(cw[0]["is_primary"])

    def test_scorecard_only_row_emits_single_primary(self):
        # No schools.yaml entry → just the primary, no alias.
        rows = [
            {"ipeds_id": "000003", "school_id": "tiny-college",
             "school_name": "Tiny College"},
        ]
        cw = build_crosswalk_rows(rows, {})
        self.assertEqual(len(cw), 1)
        self.assertEqual(cw[0]["alias"], "tiny-college")
        self.assertTrue(cw[0]["is_primary"])
        self.assertEqual(cw[0]["source"], "scorecard")


class SchoolsYamlRegressionTests(unittest.TestCase):
    def test_launch_critical_ipeds_ids_match_nces(self):
        # These two IDs were stale in schools.yaml and caused CDS-backed
        # rows to miss the Scorecard directory join before launch.
        claims = load_schools_yaml(DEFAULT_SCHOOLS_YAML)
        self.assertEqual(claims["211291"], "bucknell")
        self.assertEqual(claims["212054"], "drexel")
        self.assertNotIn("211158", claims)
        self.assertNotIn("212160", claims)


if __name__ == "__main__":
    unittest.main()
