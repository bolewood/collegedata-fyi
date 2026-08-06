from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path


HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from audit_schema_alignment import schema_field_ids, summarize_alignment
from audit_tier6_version_contract import summarize as summarize_tier6
from probe_source_corpus import deterministic_pdf_sample, looks_like_html, latest_sources
from run_data_integrity_audit import (
    ContentRange,
    ReadOnlyPostgrest,
    archive_summary,
    finance_summary,
    parse_content_range,
    percentile,
)


class PaginationContractTests(unittest.TestCase):
    def test_parses_bounded_and_empty_content_ranges(self) -> None:
        self.assertEqual(parse_content_range("0-999/17044"), ContentRange(0, 999, 17044))
        self.assertEqual(parse_content_range("*/0"), ContentRange(None, None, 0))

    def test_rejects_missing_or_malformed_content_ranges(self) -> None:
        for value in (None, "", "0/10", "0-9/*x"):
            with self.subTest(value=value), self.assertRaises(RuntimeError):
                parse_content_range(value)

    def test_percentile_uses_linear_interpolation(self) -> None:
        self.assertEqual(percentile([1, 2, 3, 4], 0.5), 2.5)
        self.assertEqual(percentile([], 0.5), None)

    def test_empty_relation_is_a_valid_complete_page(self) -> None:
        class EmptyPostgrest(ReadOnlyPostgrest):
            def _get(self, *args, **kwargs):
                return [], "*/0", 200

        rows, evidence = EmptyPostgrest("https://example.test", "key").paginate(
            "empty.contract",
            "empty_relation",
            {"select": "id", "order": "id.asc"},
            unique_key=lambda row: row["id"],
        )

        self.assertEqual(rows, [])
        self.assertEqual(evidence["expected_rows"], 0)
        self.assertEqual(evidence["fetched_rows"], 0)
        self.assertEqual(evidence["page_count"], 1)


class EvidenceSummaryTests(unittest.TestCase):
    def test_archive_summary_uses_full_rows_not_first_page(self) -> None:
        rows = [
            {"school_id": "a", "status": "failed_permanent", "last_outcome": "no_pdfs_found"},
            {"school_id": "b", "status": "failed_permanent", "last_outcome": "no_pdfs_found"},
            {"school_id": "a", "status": "done", "last_outcome": None},
        ]
        summary = archive_summary(rows, rows[:1])
        self.assertEqual(summary["no_pdfs_found"]["rows"], 2)
        self.assertEqual(summary["no_pdfs_found"]["distinct_schools"], 2)
        self.assertEqual(summary["unpaged_first_1000_diagnostic"]["no_pdfs_found"], 1)

    def test_schema_alignment_distinguishes_zero_hits_and_outside_keys(self) -> None:
        result = summarize_alignment(
            {"A.001", "B.001"},
            [{"values": {"A.001": "x", "Z.999": "y"}}, {"values": {}}],
        )
        self.assertEqual(result["schema_fields_with_zero_hits"], 1)
        self.assertEqual(result["zero_hit_field_ids"], ["B.001"])
        self.assertEqual(result["outside_schema_field_ids"], {"Z.999": 1})
        self.assertEqual(result["empty_artifacts"], 1)

    def test_schema_declared_count_is_enforced(self) -> None:
        with self.assertRaises(ValueError):
            schema_field_ids({"field_count": 2, "fields": [{"question_number": "A.001"}]})

    def test_finance_sign_contract_is_stratified_by_release(self) -> None:
        rows = [
            {
                "release_id": "r1",
                "release_type": "final",
                "ipeds_id": "1",
                "data_year": 2024,
                "field_key": "endowment_spending_distribution",
                "value_numeric": "-5",
                "value_text": None,
                "value_label": None,
                "quality_flag": "reported",
                "source_table": "F1_F2",
                "source_variable": "F2H03C",
            }
        ]
        summary = finance_summary(rows)
        bucket = summary["sign_contract_by_release_field"][0]
        self.assertEqual(bucket["release_id"], "r1")
        self.assertEqual(bucket["negative_numeric_unlabeled"], 1)

    def test_tier6_summary_reads_both_supported_sha_locations(self) -> None:
        rows = [
            {"document_id": "a", "producer_version": "0.1.0", "notes": {"source_sha256": "x"}},
            {"document_id": "b", "producer_version": "0.1.0", "notes": {"source_artifact": {"sha256": "y"}}},
            {"document_id": "b", "producer_version": "0.1.0", "notes": {}},
        ]
        result = summarize_tier6(rows)
        self.assertEqual(result["artifacts_with_source_sha_provenance"], 2)
        self.assertEqual(result["artifacts_without_source_sha_provenance"], 1)
        self.assertEqual(result["documents"], 2)


class SourceProbeTests(unittest.TestCase):
    def test_html_detection_handles_bom_comments_and_limit(self) -> None:
        self.assertTrue(looks_like_html(b"\xef\xbb\xbf <!--x--> <html>", 64))
        self.assertFalse(looks_like_html(b"x" * 512 + b"<html>", 512))
        self.assertFalse(looks_like_html(b"prefix<html>", 64))

    def test_latest_source_is_deterministic(self) -> None:
        rows = [
            {"id": "a", "document_id": "d", "created_at": "2026-01-01T00:00:00Z"},
            {"id": "b", "document_id": "d", "created_at": "2026-01-01T00:00:00Z"},
        ]
        self.assertEqual(latest_sources(rows)["d"]["id"], "b")

    def test_pdf_sample_uses_observed_bytes_not_stale_declared_format(self) -> None:
        import probe_source_corpus

        original_size = probe_source_corpus.B1_SAMPLE_SIZE
        probe_source_corpus.B1_SAMPLE_SIZE = 1
        try:
            sources = {
                "actual-pdf": {"document_id": "actual-pdf", "sha256": "x"},
                "stale-pdf-label": {"document_id": "stale-pdf-label", "sha256": "y"},
            }
            heads = {
                "actual-pdf": {"data": b"%PDF-1.7"},
                "stale-pdf-label": {"data": b"PK\\x03\\x04"},
            }
            sample = deterministic_pdf_sample(sources, heads)
            self.assertEqual(sample[0]["document_id"], "actual-pdf")
        finally:
            probe_source_corpus.B1_SAMPLE_SIZE = original_size


if __name__ == "__main__":
    unittest.main()
