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


if __name__ == "__main__":
    unittest.main()
