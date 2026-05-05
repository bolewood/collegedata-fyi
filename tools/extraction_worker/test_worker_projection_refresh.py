from __future__ import annotations

import unittest
from types import SimpleNamespace

from worker import (
    annotate_tier2_unmapped_fields,
    artifact_already_extracted,
    attach_source_metadata,
    extraction_no_project,
    extraction_success,
    is_failure_action,
    low_field_quality_flag,
    mean_or_none,
    parsed_field_count,
    pending_doc_priority_key,
)


class _FakeArtifactQuery:
    def __init__(self, rows):
        self.rows = rows

    def select(self, _columns):
        return self

    def eq(self, _column, _value):
        return self

    def limit(self, _count):
        return self

    def execute(self):
        return SimpleNamespace(data=self.rows)


class _FakeClient:
    def __init__(self, rows):
        self.rows = rows

    def table(self, _name):
        return _FakeArtifactQuery(self.rows)


class WorkerProjectionRefreshTests(unittest.TestCase):
    def test_projection_refresh_is_structured_not_action_prefix_based(self):
        self.assertTrue(extraction_success("tier3_extracted (123 fields)").refresh_projection)
        self.assertTrue(extraction_success("custom_success_name").refresh_projection)
        self.assertFalse(extraction_no_project("already_extracted").refresh_projection)
        self.assertFalse(extraction_no_project("tier4_error: boom").refresh_projection)

    def test_summary_field_count_parser_handles_worker_actions(self):
        self.assertEqual(parsed_field_count("tier4_extracted (289 fields, 48 pages)"), 289)
        self.assertEqual(parsed_field_count("extracted (576/812 fields, 156 unmapped)"), 576)
        self.assertIsNone(parsed_field_count("already_extracted"))

    def test_summary_failure_classifier_ignores_already_extracted(self):
        self.assertFalse(is_failure_action("already_extracted"))
        self.assertFalse(is_failure_action("tier4_extracted (289 fields, 48 pages)"))
        self.assertTrue(is_failure_action("tier4_error: boom"))
        self.assertTrue(is_failure_action("stub_docx"))
        self.assertTrue(is_failure_action("tier1_low_fields (0 fields)"))
        self.assertTrue(is_failure_action("no_source_artifact"))

    def test_summary_mean_rounding(self):
        self.assertEqual(mean_or_none([1, 2, 4]), 2.33)
        self.assertIsNone(mean_or_none([]))

    def test_low_field_quality_flag(self):
        self.assertEqual(low_field_quality_flag(0), "blank_template")
        self.assertEqual(low_field_quality_flag(24), "low_coverage")
        self.assertIsNone(low_field_quality_flag(25))

    def test_attach_source_metadata_records_latest_source(self):
        canonical = {}

        attach_source_metadata(canonical, {
            "sha256": "abc123",
            "storage_path": "upitt/2025-26/abc123.pdf",
        })

        self.assertEqual(canonical["source_sha256"], "abc123")
        self.assertEqual(canonical["source_storage_path"], "upitt/2025-26/abc123.pdf")
        self.assertEqual(canonical["source_artifact"]["sha256"], "abc123")

    def test_artifact_idempotency_requires_matching_source_sha_when_known(self):
        client = _FakeClient([
            {"id": "old", "notes": {"source_sha256": "old-sha"}},
            {"id": "new", "notes": {"source_artifact": {"sha256": "new-sha"}}},
        ])

        self.assertTrue(artifact_already_extracted(
            client, "doc", "tier4_docling", "0.3.4", "2025-26", "new-sha",
        ))
        self.assertFalse(artifact_already_extracted(
            client, "doc", "tier4_docling", "0.3.4", "2025-26", "missing-sha",
        ))

    def test_artifact_idempotency_treats_legacy_notes_as_stale_when_source_known(self):
        client = _FakeClient([{"id": "legacy", "notes": {"stats": {}}}])

        self.assertFalse(artifact_already_extracted(
            client, "doc", "tier4_docling", "0.3.4", "2025-26", "current-sha",
        ))
        self.assertTrue(artifact_already_extracted(
            client, "doc", "tier4_docling", "0.3.4", "2025-26",
        ))

    def test_pending_doc_priority_prefers_recent_cds_year(self):
        rows = [
            {"school_id": "aaa-old", "cds_year": "2019-20", "discovered_at": "2026-05-03T00:00:00Z"},
            {"school_id": "zzz-current", "cds_year": "2025-26", "discovered_at": "2026-04-01T00:00:00Z"},
            {"school_id": "mid-prior", "detected_year": "2024-25", "cds_year": "2023-24", "discovered_at": "2026-05-01T00:00:00Z"},
        ]

        ordered = sorted(rows, key=pending_doc_priority_key)

        self.assertEqual([row["school_id"] for row in ordered], [
            "zzz-current",
            "mid-prior",
            "aaa-old",
        ])

    def test_pending_doc_priority_prefers_newer_discovery_within_year(self):
        rows = [
            {"school_id": "yale", "cds_year": "2025-26", "discovered_at": "2026-05-01T02:11:14Z"},
            {"school_id": "brown", "cds_year": "2025-26", "discovered_at": "2026-05-01T02:14:44Z"},
            {"school_id": "uw", "cds_year": "2025-26", "discovered_at": "2026-04-15T00:34:39Z"},
        ]

        ordered = sorted(rows, key=pending_doc_priority_key)

        self.assertEqual([row["school_id"] for row in ordered], [
            "brown",
            "yale",
            "uw",
        ])

    def test_tier2_unmapped_fields_get_quality_warning(self):
        canonical = {
            "stats": {"unmapped_acroform_fields": 2},
            "unmapped_fields": [
                {"pdf_tag": "custom_field_1", "value": "x"},
                {"pdf_tag": "legacy_tag", "value": "y"},
            ],
        }

        count = annotate_tier2_unmapped_fields(canonical)

        self.assertEqual(count, 2)
        self.assertEqual(canonical["quality_warnings"][0]["code"], "tier2_unmapped_acroform_fields")
        self.assertEqual(canonical["quality_warnings"][0]["sample_pdf_tags"], [
            "custom_field_1",
            "legacy_tag",
        ])

    def test_tier2_unmapped_fields_noops_when_clean(self):
        canonical = {"stats": {"unmapped_acroform_fields": 0}}

        count = annotate_tier2_unmapped_fields(canonical)

        self.assertEqual(count, 0)
        self.assertNotIn("quality_warnings", canonical)


if __name__ == "__main__":
    unittest.main()
