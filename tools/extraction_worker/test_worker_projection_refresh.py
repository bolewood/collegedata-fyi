from __future__ import annotations

import unittest
from types import SimpleNamespace

from worker import (
    annotate_tier2_unmapped_fields,
    artifact_already_extracted,
    attach_source_metadata,
    extraction_quality_flag,
    is_single_section_source,
    extraction_no_project,
    extraction_run_exit_code,
    extraction_success,
    is_failure_action,
    headline_fields_lost,
    is_field_regression,
    low_field_quality_flag,
    mean_or_none,
    parsed_field_count,
    pending_doc_priority_key,
    select_drain_docs,
    drain_extraction_statuses,
    previous_canonical_field_count,
    previous_canonical_values,
    should_fallback_tier2_to_tier4,
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

    def order(self, _column, desc=False):
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
        self.assertTrue(is_failure_action("html_no_tables (0 fields)"))
        self.assertTrue(is_failure_action("tier1_no_cell_map schema_version=2025-26"))

    def test_field_regression_guard(self):
        # Sacramento State 2023-24: 274 -> 108 fields on an older Docling.
        self.assertTrue(is_field_regression(274, 108))
        self.assertTrue(is_failure_action("tier4_field_regression (108 < 274 fields)"))
        # Small drops and small documents are normal re-extraction noise.
        self.assertFalse(is_field_regression(441, 418))
        self.assertFalse(is_field_regression(80, 10))
        self.assertFalse(is_field_regression(None, 10))

    def test_previous_field_count_requires_same_source(self):
        client = _FakeClient([{"schema_fields_populated": 274, "source_sha256": "abc"}])
        self.assertEqual(previous_canonical_field_count(client, "doc", "abc"), 274)
        self.assertIsNone(previous_canonical_field_count(client, "doc", "new-pdf"))
        self.assertIsNone(previous_canonical_field_count(client, "doc", None))
        legacy = _FakeClient([{"schema_fields_populated": 300, "sha256": "abc"}])
        self.assertEqual(previous_canonical_field_count(legacy, "doc", "abc"), 300)

    def test_headline_loss_guard_counts_rows_whose_numbers_left_the_text(self):
        # SMU 2025-26: Docling stopped emitting the applicants and admits tables by sex.
        previous = {
            "C.101": {"value": "11148"}, "C.102": {"value": "12,905"},
            "C.104": {"value": "5217"}, "C.105": {"value": "6242"},
            "C.116": {"value": "24053"}, "C.117": {"value": "11459"},
        }
        new = {"C.116": {"value": "24053"}, "C.117": {"value": "11459"}}
        text = "| Total first-time, first-year (degree-seeking) who applied | 12254 | 9805 | 1767 | 227 | 24,053 |"
        self.assertEqual(headline_fields_lost(previous, new, "2025-26", text), ["C.101", "C.102", "C.104", "C.105"])
        self.assertTrue(is_failure_action(
            "tier4_headline_field_regression (lost C.101, C.102; the previous extraction of this file is kept)"
        ))

    def test_headline_loss_guard_lets_the_cleaner_drop_a_value_still_in_the_text(self):
        # Old Dominion 2024-25 read "2024" as its enrolled total, Eastern Connecticut a 9 and a 5 as its
        # applied and admitted totals. The numbers are still in the text; the cleaner no longer assigns them.
        previous = {"C.116": {"value": "9"}, "C.117": {"value": "5"}, "C.118": {"value": "2,024"}}
        text = "enrolled (full- or part-time) in Fall 2024. 9 of the 5 programs"
        self.assertEqual(headline_fields_lost(previous, {}, "2025-26", text), [])
        # The same values with nothing in the text are lost.
        self.assertEqual(headline_fields_lost(previous, {}, "2025-26", ""), ["C.116", "C.117", "C.118"])

    def test_headline_loss_guard_ignores_what_was_not_a_reported_count(self):
        previous = {
            "C.101": {"value": "0"},        # a zero row is not a lost count
            "C.102": {"value": ""},
            "C.104": {"value": "n/a"},
            "C.901": {"value": "55"},       # not a headline field
            "C.105": {"value": "372.0"},    # kept: present in the new extraction
        }
        new = {"C.105": {"value": "372"}}
        self.assertEqual(headline_fields_lost(previous, new, "2025-26", ""), [])
        self.assertEqual(headline_fields_lost(None, new, "2025-26", ""), [])
        # A year with no headline listing is never judged.
        self.assertEqual(headline_fields_lost({"C.101": {"value": "900"}}, {}, "2019-20", ""), [])
        # A blank new value is a lost one; "372.0" is looked for as 372.
        self.assertEqual(headline_fields_lost(previous, {"C.105": {"value": " "}}, "2025-26", "x 372 y"), [])
        self.assertEqual(headline_fields_lost(previous, {"C.105": {"value": " "}}, "2025-26", "x 3720 y"), ["C.105"])

    def test_previous_values_require_the_same_file_and_schema(self):
        class Client:
            """Returns the artifact list for the first query and the values for the by-id one."""

            def __init__(self, rows, values):
                self.rows, self.values, self.by_id = rows, values, False

            def table(self, _name):
                self.by_id = False
                return self

            def select(self, columns):
                self.by_id = columns == "notes->values"
                return self

            def eq(self, _column, _value):
                return self

            def limit(self, _count):
                return self

            def execute(self):
                return SimpleNamespace(data=[{"values": self.values}] if self.by_id else list(self.rows))

        values = {"C.101": {"value": "900"}}
        recorded = [
            {"id": "old", "kind": "canonical", "created_at": "2026-05-01T00:00:00+00:00", "schema_version": "2025-26", "source_sha": "other"},
            {"id": "new", "kind": "canonical", "created_at": "2026-06-01T00:00:00+00:00", "schema_version": "2025-26", "source_sha": "this"},
        ]
        self.assertEqual(previous_canonical_values(Client(recorded, values), "doc", "this", "2025-26"), values)
        self.assertIsNone(previous_canonical_values(Client(recorded, values), "doc", "this", "2026-27"))   # other numbering
        self.assertIsNone(previous_canonical_values(Client(recorded, values), "doc", "changed", "2025-26"))  # other file
        self.assertIsNone(previous_canonical_values(Client(recorded, values), "doc", None, "2025-26"))
        self.assertIsNone(previous_canonical_values(Client([], values), "doc", "this", "2025-26"))

        # An extraction that records no source is attributed to the file current when it was written.
        unrecorded = [
            {"id": "s1", "kind": "source", "sha256": "this", "created_at": "2026-04-01T00:00:00+00:00"},
            {"id": "c1", "kind": "canonical", "created_at": "2026-04-02T00:00:00+00:00", "schema_version": "2025-26"},
        ]
        self.assertEqual(previous_canonical_values(Client(unrecorded, values), "doc", "this", "2025-26"), values)
        unrecorded.insert(1, {"id": "s2", "kind": "source", "sha256": "other", "created_at": "2026-04-01T12:00:00+00:00"})
        self.assertIsNone(previous_canonical_values(Client(unrecorded, values), "doc", "this", "2025-26"))

    def test_extraction_run_fails_when_any_document_failed(self):
        self.assertEqual(extraction_run_exit_code(0), 0)
        self.assertEqual(extraction_run_exit_code(1), 1)

    def test_requeued_docs_drain_whatever_their_status(self):
        # A requeue must not flip served documents to pending (which hides
        # their admissions figures on the site) just to get them selected.
        rows = [
            {"id": "served", "extraction_status": "extracted"},
            {"id": "pending", "extraction_status": "extraction_pending"},
            {"id": "failed", "extraction_status": "failed"},
            {"id": "other-served", "extraction_status": "extracted"},
        ]
        picked = select_drain_docs(rows, drain_extraction_statuses(False), ["served", "failed"])
        self.assertEqual([r["id"] for r in picked], ["served", "pending", "failed"])
        picked = select_drain_docs(rows, drain_extraction_statuses(True), [])
        self.assertEqual([r["id"] for r in picked], ["pending", "failed"])

    def test_summary_mean_rounding(self):
        self.assertEqual(mean_or_none([1, 2, 4]), 2.33)
        self.assertIsNone(mean_or_none([]))

    def test_low_field_quality_flag(self):
        self.assertEqual(low_field_quality_flag(0), "blank_template")
        self.assertEqual(low_field_quality_flag(24), "low_coverage")
        self.assertIsNone(low_field_quality_flag(25))

    def test_extraction_quality_flags_missing_admissions_anchors(self):
        canonical = {
            "stats": {"schema_fields_populated": 43},
            "markdown": "C9. Percent and number\nSubmitting SAT Scores\nSubmitting ACT Scores",
            # C.1101 keeps this off the single-section rule so the C9
            # anchor check is what fires.
            "values": {"A.501": {"value": "X"}, "C.1101": {"value": "X"}},
        }

        self.assertFalse(is_single_section_source(canonical["values"], 43))
        self.assertEqual(extraction_quality_flag(canonical), "low_coverage")

    def test_extraction_quality_flags_sparse_long_documents(self):
        canonical = {
            "stats": {"schema_fields_populated": 87, "page_count": 40},
            "markdown": "",
            "values": {},
        }

        self.assertEqual(extraction_quality_flag(canonical), "low_coverage")

    def test_extraction_quality_flags_section_swallow(self):
        canonical = {
            "stats": {"schema_fields_populated": 43},
            "markdown": "",
            "values": {
                "H.1501": {
                    "value": "x" * 5001 + " I.INSTRUCTIONALFACULTYANDCLASSSIZE",
                },
                "B.101": {"value": "1"},
                "C.101": {"value": "1"},
            },
        }

        self.assertFalse(is_single_section_source(canonical["values"], 43))
        self.assertEqual(extraction_quality_flag(canonical), "low_coverage")

    def test_section_swallow_does_not_hide_full_documents(self):
        # UMass Lowell 2023-24: 617 good fields, Sections I-J swallowed into
        # H.1501. One polluted free-text answer must not hide the document.
        keys = [f"B.{100 + i}" for i in range(300)] + [f"C.{100 + i}" for i in range(317)]
        canonical = self._canonical_with_keys(keys)
        canonical["values"]["H.1501"] = {
            "value": "x" * 5001 + " I.INSTRUCTIONALFACULTYANDCLASSSIZE",
        }
        canonical["stats"]["schema_fields_populated"] = 617

        self.assertIsNone(extraction_quality_flag(canonical))

        canonical["stats"]["schema_fields_populated"] = 299
        self.assertEqual(extraction_quality_flag(canonical), "low_coverage")

    @staticmethod
    def _canonical_with_keys(keys):
        return {
            "stats": {"schema_fields_populated": len(keys)},
            "markdown": "",
            "values": {k: {"value": "1"} for k in keys},
        }

    def test_extraction_quality_flags_single_section_source(self):
        # Regent 2020-21 / Utah 2022-23: one CDS section archived as the
        # whole document. 30 Section A fields clears the 25-field floor.
        canonical = self._canonical_with_keys([f"A.{100 + i}" for i in range(30)])
        self.assertEqual(extraction_quality_flag(canonical), "low_coverage")

        f_only = self._canonical_with_keys([f"F.{100 + i}" for i in range(34)])
        self.assertEqual(extraction_quality_flag(f_only), "low_coverage")

    def test_extraction_quality_keeps_section_c_sources_visible(self):
        # Section C alone is the resolver's intentional admissions fallback;
        # B+C partial extractions still carry admissions data.
        c_only = self._canonical_with_keys([f"C.{100 + i}" for i in range(60)])
        self.assertIsNone(extraction_quality_flag(c_only))

        b_and_c = self._canonical_with_keys(
            [f"B.{100 + i}" for i in range(20)] + [f"C.{100 + i}" for i in range(20)]
        )
        self.assertIsNone(extraction_quality_flag(b_and_c))

    def test_extraction_quality_ignores_section_span_for_large_documents(self):
        many = self._canonical_with_keys([f"B.{100 + i}" for i in range(160)])
        self.assertIsNone(extraction_quality_flag(many))

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

    def test_artifact_idempotency_ignores_an_extraction_superseded_by_one_of_another_file(self):
        # This file was extracted, the document was pointed at another file and that was extracted, and it
        # was pointed back. The later extraction is what gets served, so a new one has to be written.
        mine = {"id": "mine", "created_at": "2026-04-20T00:00:00+00:00", "notes": {"source_sha256": "this-sha"}}
        later_other = {"id": "other", "created_at": "2026-05-03T00:00:00+00:00", "notes": {"source_sha256": "other-sha"}}
        earlier_other = {"id": "other", "created_at": "2026-04-01T00:00:00+00:00", "notes": {"source_sha256": "other-sha"}}
        later_same = {"id": "again", "created_at": "2026-05-03T00:00:00+00:00", "notes": {"source_sha256": "this-sha"}}
        later_unrecorded = {"id": "legacy", "created_at": "2026-05-03T00:00:00+00:00", "notes": {"stats": {}}}

        def already(rows):
            return artifact_already_extracted(_FakeClient(rows), "doc", "tier4_docling", "0.3.4", "2025-26", "this-sha")

        self.assertFalse(already([mine, later_other]))
        self.assertTrue(already([mine, earlier_other]))
        self.assertTrue(already([mine, later_same]))
        self.assertTrue(already([mine, later_unrecorded]))
        self.assertTrue(already([mine]))

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

    def test_tier2_label_acroform_falls_back_to_tier4(self):
        canonical = {
            "stats": {
                "acroform_fields_total": 581,
                "schema_fields_populated": 0,
                "unmapped_acroform_fields": 581,
            },
        }

        self.assertTrue(should_fallback_tier2_to_tier4(canonical))

    def test_tier2_partial_schema_match_does_not_fallback_to_tier4(self):
        canonical = {
            "stats": {
                "acroform_fields_total": 732,
                "schema_fields_populated": 576,
                "unmapped_acroform_fields": 156,
            },
        }

        self.assertFalse(should_fallback_tier2_to_tier4(canonical))

    def test_tier2_tiny_acroform_does_not_fallback_to_tier4(self):
        canonical = {
            "stats": {
                "acroform_fields_total": 1,
                "schema_fields_populated": 0,
                "unmapped_acroform_fields": 1,
            },
        }

        self.assertFalse(should_fallback_tier2_to_tier4(canonical))


if __name__ == "__main__":
    unittest.main()
