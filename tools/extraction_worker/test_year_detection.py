"""Year-detection unit tests (ADR 0007).

Uses invented plain-text only. Do not add real CDS bytes, school names
from the live corpus, or archived PDF/DOCX fixtures here.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

WORKER_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(WORKER_DIR))

from worker import (  # noqa: E402
    collect_year_spans_from_text,
    detect_year_from_text,
    unique_detected_year,
    _normalize_year_span,
)


class NormalizeYearSpanTest(unittest.TestCase):
    def test_four_digit_end_year(self):
        self.assertEqual(_normalize_year_span("2026", "2027"), "2026-27")

    def test_two_digit_end_year(self):
        self.assertEqual(_normalize_year_span("2025", "26"), "2025-26")

    def test_rejects_non_adjacent_span(self):
        self.assertIsNone(_normalize_year_span("2024", "2026"))

    def test_rejects_far_future_start(self):
        self.assertIsNone(_normalize_year_span("2036", "37"))


class AdjacentTitlePatternsTest(unittest.TestCase):
    def test_common_data_set_same_line(self):
        text = "Rivertown State University\nCommon Data Set 2024-2025\nA1. Address Information"
        self.assertEqual(detect_year_from_text(text), "2024-25")

    def test_cds_abbreviation(self):
        self.assertEqual(detect_year_from_text("CDS 2025-26 First-year Admission"), "2025-26")

    def test_en_dash_year(self):
        self.assertEqual(detect_year_from_text("Common Data Set 2023–2024"), "2023-24")

    def test_year_on_next_line_without_section_heading(self):
        text = "Common Data Set\n2025-2026\nA1. Address Information"
        self.assertEqual(detect_year_from_text(text), "2025-26")


class SectionTitleThenYearTest(unittest.TestCase):
    def test_title_section_year_on_following_lines(self):
        text = (
            "Rivertown State University Factbook\n"
            "Common Data Set\n"
            "Section A1. General Information\n"
            "2026-2027\n"
            "A1. Address Information\n"
            "Name of College/University: Rivertown State University\n"
        )
        self.assertEqual(detect_year_from_text(text), "2026-27")

    def test_optional_school_name_line_between_section_and_year(self):
        text = (
            "Common Data Set\n"
            "Section C. First-time, First-year Admission\n"
            "Northbridge College of the Arts\n"
            "2025-2026\n"
        )
        self.assertEqual(detect_year_from_text(text), "2025-26")

    def test_section_j_heading_still_needs_cds_prefix(self):
        text = (
            "Common Data Set\n"
            "Section J. Degrees conferred\n"
            "2024-2025\n"
            "Bachelor's degrees awarded in 2006-07 for comparison\n"
        )
        self.assertEqual(detect_year_from_text(text), "2024-25")


class MissDontCorruptTest(unittest.TestCase):
    def test_bare_reference_year_is_ignored(self):
        # American University-style trap: a lone 2006-07 in section J
        # must not become the document year.
        text = (
            "Expenses for first-year students\n"
            "See figures reported for 2006-07 in the prior survey.\n"
            "Total: 41200\n"
        )
        self.assertIsNone(detect_year_from_text(text))

    def test_invalid_span_is_ignored(self):
        self.assertIsNone(detect_year_from_text("Common Data Set 2024-2026"))

    def test_two_distinct_valid_spans_are_ambiguous(self):
        text = (
            "Common Data Set 2023-2024\n"
            "Common Data Set\n"
            "Section A1. General Information\n"
            "2024-2025\n"
        )
        self.assertIsNone(detect_year_from_text(text))
        self.assertEqual(
            collect_year_spans_from_text(text),
            {"2023-24", "2024-25"},
        )

    def test_repeated_same_span_is_unique(self):
        text = (
            "Common Data Set 2025-2026\n"
            "Common Data Set\n"
            "Section B1. Enrollment\n"
            "2025-2026\n"
        )
        self.assertEqual(detect_year_from_text(text), "2025-26")
        self.assertEqual(collect_year_spans_from_text(text), {"2025-26"})

    def test_no_year_returns_none(self):
        self.assertIsNone(detect_year_from_text("General Information\nAddress Information"))

    def test_unique_helper_treats_empty_and_many_as_none(self):
        self.assertIsNone(unique_detected_year(set()))
        self.assertIsNone(unique_detected_year({"2024-25", "2025-26"}))
        self.assertEqual(unique_detected_year({"2024-25"}), "2024-25")


if __name__ == "__main__":
    unittest.main()
