"""PRD 038 Decision 4 / A4: the overlay producer in change intelligence, and the version suffix."""

from __future__ import annotations

import sys
import types
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "data_quality"))

if "dotenv" not in sys.modules:                      # python-dotenv is not in tools/ci-requirements.txt; the audit only needs the name
    try:
        import dotenv  # noqa: F401
    except ImportError:
        stub = types.ModuleType("dotenv")
        stub.load_dotenv = lambda *a, **k: False
        sys.modules["dotenv"] = stub

import audit_visual_ocr_candidates as ocr  # noqa: E402
import audit_watchlist_freshness as fresh  # noqa: E402
import project_change_events as pce  # noqa: E402
import test_project_change_events as base_tests  # noqa: E402


class OverlayProducerTests(unittest.TestCase):
    def test_overlay_is_listed_explicitly_in_the_tier2_family(self):
        self.assertEqual(pce.PRODUCER_FAMILY["tier2_template_overlay"], "tier2")
        self.assertEqual(pce.producer_family("tier2_template_overlay"), "tier2")

    def test_a_merged_year_and_a_tier4_only_year_are_not_comparable(self):
        plain = {"producer": "tier4_docling", "producer_version": "0.3.17"}
        merged = {"producer": "tier4_docling", "producer_version": "0.3.17+overlay.0.6.0"}
        self.assertFalse(pce.compatible_producer_version(plain, merged))
        self.assertTrue(pce.compatible_producer_version(merged, dict(merged)))
        self.assertFalse(pce.compatible_producer_version(merged, {**merged, "producer_version": "0.3.17+overlay.0.7.0"}))

    def test_structural_version_parsers_ignore_the_overlay_suffix(self):
        # These two audit scripts split producer_version on "."; without the suffix rule "0.3.17+overlay.0.6.0"
        # read as (0, 3, 0, 0, 6, 0), i.e. older than 0.3.17.
        self.assertEqual(fresh.version_tuple("0.3.17+overlay.0.6.0"), (0, 3, 17))
        self.assertEqual(ocr.version_tuple("0.3.17+overlay.0.6.0"), (0, 3, 17))
        self.assertEqual(fresh.version_tuple("0.3.17"), (0, 3, 17))


PLAIN = "0.3.17"
MERGED = "0.3.17+overlay.0.7.0/checkbox_box,choice,numeric"
MERGED_NARROW = "0.3.17+overlay.0.7.0/numeric"
MERGED_NEWER = "0.3.17+overlay.0.8.0/checkbox_box,choice,numeric"


def _pair(prior_version, latest_version, old, new, rule=None):
    prior = base_tests.row(producer_version=prior_version, sat_composite_p25=old)
    latest = base_tests.row(
        document_id="00000000-0000-0000-0000-000000000002", canonical_year="2025-26", year_start=2025,
        producer_version=latest_version, sat_composite_p25=new,
    )
    return pce.classify_field_change(prior, latest, rule or base_tests.SAT_P25, base_tests.RULES)


class OverlayGateEveryDirectionTests(unittest.TestCase):
    def _assert_extraction_change(self, event):
        self.assertIsNotNone(event)
        self.assertEqual(event["event_type"], "producer_changed")
        self.assertEqual(event["severity"], "watch")
        self.assertIn("not classified as school-side silence", event["evidence_json"]["caveats"][0])

    def test_recovered_value_is_an_extraction_change_not_newly_reported(self):
        self._assert_extraction_change(_pair(PLAIN, MERGED, None, 1400))
        self.assertEqual(_pair(PLAIN, PLAIN, None, 1400)["event_type"], "newly_reported")         # today's behaviour without an overlay

    def test_numeric_delta_is_an_extraction_change_not_material_delta(self):
        self._assert_extraction_change(_pair(PLAIN, MERGED, 1200, 1400))
        self.assertEqual(_pair(PLAIN, PLAIN, 1200, 1400)["event_type"], "material_delta")

    def test_disappearing_value_stays_an_extraction_change(self):
        self._assert_extraction_change(_pair(PLAIN, MERGED, 1400, None))
        self._assert_extraction_change(_pair(MERGED, PLAIN, 1400, None))

    def test_an_unchanged_value_emits_nothing_even_when_the_overlay_differs(self):
        self.assertIsNone(_pair(PLAIN, MERGED, 1400, 1400))

    def test_the_other_way_round_and_across_versions_and_served_sets(self):
        self._assert_extraction_change(_pair(MERGED, PLAIN, None, 1400))                          # overlay dropped
        self._assert_extraction_change(_pair(MERGED, MERGED_NEWER, 1200, 1400))                   # overlay version changed
        self._assert_extraction_change(_pair(MERGED, MERGED_NARROW, 1200, 1400))                  # served class set changed, version same
        self.assertEqual(_pair(MERGED, MERGED, 1200, 1400)["event_type"], "material_delta")        # same identity: school-side as before

    def test_reappeared_is_gated_too(self):
        prior = base_tests.row(producer_version=PLAIN, sat_composite_p25=None)
        latest = base_tests.row(document_id="00000000-0000-0000-0000-000000000002", canonical_year="2025-26", year_start=2025,
                                producer_version=MERGED, sat_composite_p25=1400)
        event = pce.classify_field_change(prior, latest, base_tests.SAT_P25, base_tests.RULES, had_earlier_reported=True)
        self._assert_extraction_change(event)

    def test_identity_is_read_through_one_helper(self):
        self.assertIsNone(pce.overlay_identity({"producer_version": PLAIN}))
        self.assertEqual(pce.overlay_identity({"producer_version": MERGED}), "0.7.0/checkbox_box,choice,numeric")
        self.assertTrue(pce.overlay_identity_differs({"producer_version": PLAIN}, {"producer_version": MERGED}))
        self.assertFalse(pce.overlay_identity_differs({"producer_version": PLAIN}, {"producer_version": "0.3.9"}))


def _col_pair(prior_ident, latest_ident, old, new):
    prior = base_tests.row(producer_version=PLAIN, overlay_producer_version=prior_ident, sat_composite_p25=old)
    latest = base_tests.row(document_id="00000000-0000-0000-0000-000000000002", canonical_year="2025-26", year_start=2025,
                            producer_version=PLAIN, overlay_producer_version=latest_ident, sat_composite_p25=new)
    return pce.classify_field_change(prior, latest, base_tests.SAT_P25, base_tests.RULES)


class OverlayIdentityColumnTests(unittest.TestCase):
    """PRD 038 A15: `producer_version` stays the plain Tier 4 version; the identity is the `overlay_producer_version` column."""

    def test_the_identity_is_read_from_the_column(self):
        row = {"producer_version": PLAIN, "overlay_producer_version": "0.7.0/checkbox_box,choice,numeric,ocr_numeric"}
        self.assertEqual(pce.overlay_identity(row), "0.7.0/checkbox_box,choice,numeric,ocr_numeric")
        self.assertIsNone(pce.overlay_identity({"producer_version": PLAIN, "overlay_producer_version": None}))
        self.assertIsNone(pce.overlay_identity({"producer_version": PLAIN}))
        self.assertEqual(pce.overlay_identity({"producer_version": MERGED}), "0.7.0/checkbox_box,choice,numeric")     # M3 suffix rows still read

    def test_every_direction_is_gated_through_classify_field_change(self):
        merged, other_set = "0.7.0/checkbox_box,choice,numeric,ocr_numeric", "0.7.0/numeric"
        for old, new in ((None, 1400), (1200, 1400), (1400, None)):
            event = _col_pair(None, merged, old, new)
            self.assertEqual(event["event_type"], "producer_changed", (old, new))
            self.assertIn("not classified as school-side silence", event["evidence_json"]["caveats"][0])
        self.assertEqual(_col_pair(merged, other_set, 1200, 1400)["event_type"], "producer_changed")       # same version, different served set
        self.assertEqual(_col_pair(merged, merged, 1200, 1400)["event_type"], "material_delta")             # same identity: school-side as before
        self.assertEqual(_col_pair(None, None, None, 1400)["event_type"], "newly_reported")                 # no overlay: today's output
        self.assertIsNone(_col_pair(None, merged, 1400, 1400))

    def test_fetch_browser_rows_falls_back_when_the_column_does_not_exist_yet(self):
        calls = []

        class Q:
            def __init__(self, cols):
                self.cols = cols

            def select(self, cols):
                self.cols = cols
                calls.append(cols)
                return self

            def __getattr__(self, name):
                return lambda *a, **k: self

            def execute(self):
                if "overlay_producer_version" in self.cols:
                    raise RuntimeError('column "overlay_producer_version" does not exist')
                return type("R", (), {"data": [{"document_id": "d", "school_id": "s"}]})()

        class C:
            def table(self, name):
                return Q("")

        orig = pce.enrich_rows_with_documents
        pce.enrich_rows_with_documents = lambda client, rows: rows
        try:
            rows = pce.fetch_browser_rows(C(), {}, None, 2024, 2026)
        finally:
            pce.enrich_rows_with_documents = orig
        self.assertEqual(len(rows), 1)
        self.assertIn("overlay_producer_version", calls[0])
        self.assertNotIn("overlay_producer_version", calls[1])


if __name__ == "__main__":
    unittest.main()
