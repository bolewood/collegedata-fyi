"""Tests for the add-only data-quality flag backfill."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from backfill_quality_flags import plan_backfill  # noqa: E402


def _canonical(keys: list[str], producer: str = "tier1_xlsx") -> dict:
    return {
        "producer": producer,
        "stats": {"schema_fields_populated": len(keys)},
        "values": {k: {"value": "1"} for k in keys},
    }


class PlanBackfillTests(unittest.TestCase):
    def test_flags_low_field_and_single_section_documents(self):
        docs = [
            {"id": "few", "school_id": "a", "cds_year": "2024-25", "data_quality_flag": None},
            {"id": "section-a", "school_id": "regent", "cds_year": "2020-21", "data_quality_flag": None},
            {"id": "full", "school_id": "b", "cds_year": "2024-25", "data_quality_flag": None},
        ]
        canonical = {
            "few": _canonical([f"C.{100 + i}" for i in range(10)]),
            "section-a": _canonical([f"A.{100 + i}" for i in range(32)], "tier4_docling"),
            "full": _canonical(
                [f"{s}.{100 + i}" for s in "ABCDEFGHIJ" for i in range(30)], "tier4_docling"
            ),
        }
        planned = {row["document_id"]: row["flag"] for row in plan_backfill(docs, canonical)}
        self.assertEqual(planned, {"few": "low_coverage", "section-a": "low_coverage"})

    def test_never_touches_existing_flags_or_missing_canonicals(self):
        docs = [
            {"id": "wrong", "data_quality_flag": "wrong_file"},
            {"id": "already", "data_quality_flag": "low_coverage"},
            {"id": "no-canonical", "data_quality_flag": None},
        ]
        canonical = {
            "wrong": _canonical([]),
            "already": _canonical([]),
        }
        self.assertEqual(plan_backfill(docs, canonical), [])

    def test_does_not_retroactively_apply_swallow_or_sparse_rules(self):
        docs = [
            {"id": "swallow", "data_quality_flag": None},
            {"id": "sparse-long", "data_quality_flag": None},
        ]
        full_keys = [f"{s}.{100 + i}" for s in "ABCDEFGHIJ" for i in range(40)]
        swallow = _canonical(full_keys, "tier4_docling")
        swallow["values"]["H.1501"] = {"value": "x" * 5001 + " INSTRUCTIONALFACULTYANDCLASSSIZE"}
        sparse = _canonical([f"{s}.{100 + i}" for s in "BCD" for i in range(25)], "tier4_docling")
        sparse["stats"]["page_count"] = 40
        self.assertEqual(plan_backfill(docs, {"swallow": swallow, "sparse-long": sparse}), [])

    def test_zero_fields_is_blank_template(self):
        docs = [{"id": "empty", "data_quality_flag": None}]
        planned = plan_backfill(docs, {"empty": _canonical([])})
        self.assertEqual(planned[0]["flag"], "blank_template")


if __name__ == "__main__":
    unittest.main()
