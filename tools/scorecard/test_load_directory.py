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
    build_directory_row,
    directory_refresh_delta,
    fetch_existing_directory_rows,
    load_schools_yaml,
    normalize_ipeds,
    previous_predominant_degrees,
    printable_refresh_delta,
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
        # PREDDEG=1 = predominantly certificate-granting — excluded by PRD 015.
        in_scope, reason = _scope_decision(self._row(predominant_degree=1))
        self.assertFalse(in_scope)
        self.assertEqual(reason, "non_degree_predominant")

    def test_graduate_predominant_with_undergrad_in_scope(self):
        # PREDDEG=4 (graduate) is allowed when UGDS > 0 (per PRD).
        in_scope, _ = _scope_decision(
            self._row(predominant_degree=4, undergraduate_enrollment=100)
        )
        self.assertTrue(in_scope)


class PredominantDegreeStabilizationTests(unittest.TestCase):
    @staticmethod
    def _raw(**overrides):
        row = {
            "UNITID": "123456",
            "INSTNM": "Example College",
            "CITY": "Example",
            "STABBR": "MI",
            "ZIP": "48000",
            "INSTURL": "example.edu",
            "UGDS": 100,
            "CONTROL": 2,
            "ICLEVEL": 1,
            "PREDDEG": 3,
            "HIGHDEG": 3,
            "CURROPER": 1,
            "MAIN": 1,
            "NUMBRANCH": 1,
            "LATITUDE": 42.0,
            "LONGITUDE": -83.0,
        }
        row.update(overrides)
        return row

    def test_stabilizes_spelman_one_release_regression(self):
        raw = self._raw(
            UNITID="141060",
            INSTNM="Spelman College",
            PREDDEG=1,
            HIGHDEG=3,
            UGDS=3414,
        )

        row = build_directory_row(raw, "2022-23", previous_predominant_degree=3)

        self.assertIsNotNone(row)
        self.assertEqual(row["predominant_degree"], 3)
        self.assertTrue(row["in_scope"])
        self.assertIsNone(row["exclusion_reason"])
        self.assertEqual(row["_current_predominant_degree"], 1)
        self.assertEqual(row["_previous_predominant_degree"], 3)

    def test_does_not_override_current_certificate_only_school(self):
        raw = self._raw(PREDDEG=1, HIGHDEG=1)

        row = build_directory_row(raw, "2022-23", previous_predominant_degree=3)

        self.assertIsNotNone(row)
        self.assertEqual(row["predominant_degree"], 1)
        self.assertFalse(row["in_scope"])
        self.assertNotIn("_previous_predominant_degree", row)

    def test_does_not_override_without_prior_degree_classification(self):
        raw = self._raw(PREDDEG=1, HIGHDEG=3)

        row = build_directory_row(raw, "2022-23", previous_predominant_degree=1)

        self.assertIsNotNone(row)
        self.assertEqual(row["predominant_degree"], 1)
        self.assertFalse(row["in_scope"])


class PreviousPredominantDegreeTests(unittest.TestCase):
    def test_normalizes_ids_and_skips_missing_values(self):
        class Frame:
            columns = ["UNITID", "PREDDEG"]

            @staticmethod
            def to_dict(orient):
                if orient != "records":
                    raise AssertionError(f"unexpected orientation: {orient}")
                return [
                    {"UNITID": "141060.0", "PREDDEG": "3"},
                    {"UNITID": "123", "PREDDEG": "NULL"},
                    {"UNITID": "", "PREDDEG": "2"},
                ]

        self.assertEqual(previous_predominant_degrees(Frame()), {"141060": 3})

    def test_requires_unitid_and_preddeg(self):
        class Frame:
            columns = ["UNITID"]

        with self.assertRaisesRegex(ValueError, "PREDDEG"):
            previous_predominant_degrees(Frame())


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


class DirectoryRefreshDeltaTests(unittest.TestCase):
    def _row(self, ipeds_id, name, *, in_scope, reason=None, preddeg=3, ugds=1000):
        return {
            "ipeds_id": ipeds_id,
            "school_name": name,
            "in_scope": in_scope,
            "exclusion_reason": reason,
            "predominant_degree": preddeg,
            "undergraduate_enrollment": ugds,
        }

    def test_reports_scope_transitions_new_and_missing_rows(self):
        existing = [
            self._row(
                "141060",
                "Spelman College",
                in_scope=False,
                reason="non_degree_predominant",
                preddeg=1,
                ugds=3414,
            ),
            self._row("000002", "Closing College", in_scope=True),
            self._row("000003", "Dropped College", in_scope=True),
        ]
        incoming = [
            self._row("141060", "Spelman College", in_scope=True, preddeg=3, ugds=3633),
            self._row(
                "000002",
                "Closing College",
                in_scope=False,
                reason="closed",
            ),
            self._row("000004", "New College", in_scope=True),
        ]

        delta = directory_refresh_delta(existing, incoming)

        self.assertEqual(delta["existing_rows"], 3)
        self.assertEqual(delta["incoming_rows"], 3)
        self.assertEqual(delta["entering_scope"], 1)
        self.assertEqual(delta["leaving_scope"], 1)
        self.assertEqual(delta["entering_scope_old_reasons"], {"non_degree_predominant": 1})
        self.assertEqual(delta["leaving_scope_new_reasons"], {"closed": 1})
        self.assertEqual(delta["new_ipeds_ids"], ["000004"])
        self.assertEqual(delta["missing_ipeds_ids"], ["000003"])
        self.assertEqual(delta["entering_scope_rows"][0]["ipeds_id"], "141060")
        self.assertEqual(
            delta["entering_scope_rows"][0]["new_predominant_degree"],
            3,
        )

    def test_printable_delta_keeps_counts_and_limits_samples(self):
        existing = [
            self._row(f"{i:06d}", f"Old College {i}", in_scope=True)
            for i in range(4)
        ]
        incoming = [
            self._row(f"{i + 10:06d}", f"New College {i}", in_scope=True)
            for i in range(4)
        ]

        report = printable_refresh_delta(
            directory_refresh_delta(existing, incoming),
            sample_size=2,
        )

        self.assertEqual(report["new_rows"], 4)
        self.assertEqual(report["missing_rows"], 4)
        self.assertEqual(len(report["new_ipeds_ids_sample"]), 2)
        self.assertEqual(len(report["missing_ipeds_ids_sample"]), 2)
        self.assertNotIn("new_ipeds_ids", report)
        self.assertNotIn("missing_ipeds_ids", report)

    def test_fetch_existing_directory_rows_pages_past_postgrest_limit(self):
        source_rows = [{"ipeds_id": f"{i:06d}"} for i in range(2501)]
        requested_ranges = []

        class Response:
            def __init__(self, data):
                self.data = data

        class Query:
            def __init__(self):
                self.start = 0
                self.end = 0

            def select(self, _columns):
                return self

            def order(self, _column):
                return self

            def range(self, start, end):
                self.start = start
                self.end = end
                requested_ranges.append((start, end))
                return self

            def execute(self):
                return Response(source_rows[self.start : self.end + 1])

        class Client:
            def table(self, name):
                if name != "institution_directory":
                    raise AssertionError(f"unexpected table: {name}")
                return Query()

        rows = fetch_existing_directory_rows(Client())

        self.assertEqual(len(rows), 2501)
        self.assertEqual(
            requested_ranges,
            [(0, 999), (1000, 1999), (2000, 2999)],
        )


if __name__ == "__main__":
    unittest.main()
