from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from project_change_events import (
    FieldRule,
    build_events,
    classify_field_change,
    selectivity_band,
    school_year_coverage,
    write_report,
)


RULES = {
    "global": {"source_provenance_severity_cap": "watch"},
    "selectivity_bands": {
        "high_selectivity": {"max_admit_rate": 0.20},
        "selective": {"min_admit_rate": 0.20, "max_admit_rate": 0.50},
        "broad_access": {"min_admit_rate": 0.50},
        "unknown_selectivity": {},
    },
}


ACCEPTANCE = FieldRule(
    key="acceptance_rate",
    label="Admit rate",
    family="admissions_pressure",
    column="acceptance_rate",
    value_kind="rate",
    thresholds={
        "high_selectivity": {"notable_pp": 0.02, "major_pp": 0.03},
        "selective": {"notable_pp": 0.03, "major_pp": 0.06},
        "broad_access": {"notable_pp": 0.05, "major_pp": 0.10},
        "unknown_selectivity": {"notable_pp": 0.03, "major_pp": 0.06},
    },
)

SAT_P25 = FieldRule(
    key="sat_composite_p25",
    label="SAT composite 25th percentile",
    family="admissions_pressure",
    column="sat_composite_p25",
    value_kind="score_sat",
    thresholds={"default": {"notable_abs": 30, "major_abs": 80}},
)


def row(**overrides):
    base = {
        "document_id": "00000000-0000-0000-0000-000000000001",
        "school_id": "test-college",
        "school_name": "Test College",
        "ipeds_id": "123456",
        "canonical_year": "2024-25",
        "year_start": 2024,
        "source_format": "pdf_flat",
        "producer": "tier4_docling",
        "producer_version": "0.3.4",
        "source_provenance": "school_direct",
        "archive_url": "https://example.test/schools/test-college/2024-25",
        "source_url": "https://example.test/2024.pdf",
        "data_quality_flag": None,
        "acceptance_rate": 0.19,
    }
    base.update(overrides)
    return base


class ChangeEventClassificationTests(unittest.TestCase):
    def test_prior_year_selectivity_band_controls_threshold(self):
        prior = row(acceptance_rate=0.19)
        latest = row(
            document_id="00000000-0000-0000-0000-000000000002",
            canonical_year="2025-26",
            year_start=2025,
            acceptance_rate=0.24,
        )

        event = classify_field_change(prior, latest, ACCEPTANCE, RULES)

        self.assertIsNotNone(event)
        self.assertEqual(selectivity_band(prior["acceptance_rate"], RULES), "high_selectivity")
        self.assertEqual(event["severity"], "major")
        self.assertIn("high_selectivity", event["threshold_rule"])

    def test_producer_change_blocks_newly_missing_silence(self):
        prior = row(sat_composite_p25=1400)
        latest = row(
            document_id="00000000-0000-0000-0000-000000000002",
            canonical_year="2025-26",
            year_start=2025,
            producer="tier1_xlsx",
            producer_version="0.1.0",
            sat_composite_p25=None,
        )

        event = classify_field_change(prior, latest, SAT_P25, RULES)

        self.assertIsNotNone(event)
        self.assertEqual(event["event_type"], "producer_changed")
        self.assertEqual(event["severity"], "watch")
        self.assertIn("not classified as school-side silence", event["evidence_json"]["caveats"][0])

    def test_same_producer_missing_field_emits_review_candidate(self):
        prior = row(sat_composite_p25=1400)
        latest = row(
            document_id="00000000-0000-0000-0000-000000000002",
            canonical_year="2025-26",
            year_start=2025,
            sat_composite_p25=None,
        )

        event = classify_field_change(prior, latest, SAT_P25, RULES)

        self.assertIsNotNone(event)
        self.assertEqual(event["event_type"], "newly_missing")
        self.assertEqual(event["verification_status"], "candidate")

    def test_schema_rename_same_field_key_does_not_create_reporting_event(self):
        rows = [
            row(document_id="a", canonical_year="2024-25", year_start=2024, sat_composite_p25=1400),
            row(document_id="b", canonical_year="2025-26", year_start=2025, sat_composite_p25=1400),
        ]

        events = build_events(rows, RULES, {"sat_composite_p25": SAT_P25}, 2024, 2025)

        self.assertEqual(events, [])

    def test_source_provenance_crossing_caps_severity(self):
        prior = row(acceptance_rate=0.19, source_provenance="school_direct")
        latest = row(
            document_id="00000000-0000-0000-0000-000000000002",
            canonical_year="2025-26",
            year_start=2025,
            acceptance_rate=0.30,
            source_provenance="mirror_college_transitions",
        )

        event = classify_field_change(prior, latest, ACCEPTANCE, RULES)

        self.assertIsNotNone(event)
        self.assertEqual(event["severity"], "watch")
        self.assertIn("source provenance changed across compared years", event["evidence_json"]["caveats"])

    def test_quality_regression_blocks_material_delta(self):
        prior = row(sat_composite_p25=1400)
        latest = row(
            document_id="00000000-0000-0000-0000-000000000002",
            canonical_year="2025-26",
            year_start=2025,
            sat_composite_p25=None,
            data_quality_flag="low_coverage",
        )

        event = classify_field_change(prior, latest, SAT_P25, RULES)

        self.assertIsNotNone(event)
        self.assertEqual(event["event_type"], "quality_regression")

    def test_school_year_coverage_counts_pairable_watchlist_schools(self):
        rows = [
            row(school_id="a", year_start=2024, canonical_year="2024-25"),
            row(school_id="a", year_start=2025, canonical_year="2025-26"),
            row(school_id="b", year_start=2025, canonical_year="2025-26"),
        ]

        coverage = school_year_coverage(rows, {"a", "b", "c"}, 2024, 2025)

        self.assertEqual(coverage["watchlist_size"], 3)
        self.assertEqual(coverage["with_prior"], 1)
        self.assertEqual(coverage["with_latest"], 2)
        self.assertEqual(coverage["pairable"], 1)

    def test_write_report_includes_annual_seed_sections_and_caveats(self):
        prior = row(acceptance_rate=0.19)
        latest = row(
            document_id="00000000-0000-0000-0000-000000000002",
            canonical_year="2025-26",
            year_start=2025,
            acceptance_rate=0.24,
        )
        event = classify_field_change(prior, latest, ACCEPTANCE, RULES)
        assert event is not None

        with TemporaryDirectory() as d:
            path = Path(d) / "report.md"
            write_report([event], path, 2024, 2025, [prior, latest], {"test-college"})
            text = path.read_text()

        self.assertIn("## Freshness and coverage", text)
        self.assertIn("## Biggest admissions-pressure signals", text)
        self.assertIn("## Reporting gaps and silences worth reviewing", text)
        self.assertIn("CDS events describe what changed", text)
        self.assertIn("Test College", text)


if __name__ == "__main__":
    unittest.main()
