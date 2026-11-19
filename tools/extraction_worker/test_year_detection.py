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

import worker  # noqa: E402
from worker import (  # noqa: E402
    collect_year_spans_from_text,
    fallback_year_for_unfiled_document,
    fallback_year_from_text,
    school_has_document_for_year,
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



class FallbackYearFromTextTest(unittest.TestCase):
    """Signals used only for a document the archive filed without a year."""

    REFERENCE = "figures as of the official fall reporting date or as of October 15, 2025."

    def test_reference_date_alone_gives_the_year(self):
        text = "Rivertown State University Common Data Set FY2026\n" + self.REFERENCE
        self.assertEqual(fallback_year_from_text(text, text), "2025-26")

    def test_reference_date_without_a_comma_or_across_a_line_break(self):
        self.assertEqual(fallback_year_from_text("", "as of October 15 2023"), "2023-24")
        self.assertEqual(fallback_year_from_text("", "as of October\n15, 1999"), "1999-00")

    def test_reference_date_picks_between_two_title_spans(self):
        text = "Common Data Set 2025-2026\nCommon Data Set 2024-2025 definitions\n" + self.REFERENCE
        self.assertEqual(collect_year_spans_from_text(text), {"2024-25", "2025-26"})
        self.assertEqual(fallback_year_from_text(text, text), "2025-26")

    def test_reference_date_that_contradicts_the_title_spans_is_refused(self):
        # A reused template with last year's date in it.
        text = "Common Data Set 2025-2026\nCommon Data Set 2024-2025 definitions\nas of October 15, 2022"
        self.assertIsNone(fallback_year_from_text(text, text))
        single = "Common Data Set 2008-2009\nas of October 15, 2007"
        self.assertIsNone(fallback_year_from_text(single, single))

    def test_two_reference_dates_give_no_year(self):
        text = "as of October 15, 2024 ... as of October 15, 2025"
        self.assertIsNone(fallback_year_from_text("", text))

    def test_reference_date_is_read_beyond_the_pages_the_title_patterns_read(self):
        self.assertEqual(fallback_year_from_text("A. General Information", "page 14: " + self.REFERENCE), "2025-26")

    def test_dominant_fall_term_picks_between_two_title_spans(self):
        strict = "Common Data Set 2022-2023\nCommon Data Set 2021-2022 definitions"
        text = strict + " Fall 2022" * 6 + " Fall 2016" * 3
        self.assertEqual(fallback_year_from_text(strict, text), "2022-23")

    def test_fall_term_never_gives_a_year_the_title_patterns_did_not_find(self):
        fall_only = " Fall 2022" * 9
        self.assertIsNone(fallback_year_from_text("", fall_only))
        one_span = "Common Data Set 2021-2022"
        self.assertIsNone(fallback_year_from_text(one_span, one_span + fall_only))
        other_spans = "Common Data Set 2019-2020\nCommon Data Set 2020-2021"
        self.assertIsNone(fallback_year_from_text(other_spans, other_spans + fall_only))

    def test_fall_term_needs_a_clear_majority(self):
        strict = "Common Data Set 2022-2023\nCommon Data Set 2021-2022 definitions"
        self.assertIsNone(fallback_year_from_text(strict, strict + " Fall 2022" * 4))
        self.assertIsNone(fallback_year_from_text(strict, strict + " Fall 2022" * 6 + " Fall 2021" * 4))

    def test_no_signal_gives_no_year(self):
        self.assertIsNone(fallback_year_from_text("", "A. General Information"))
        self.assertIsNone(fallback_year_from_text("", ""))


class _Query:
    def __init__(self, rows):
        self.rows = rows
        self.filters = []

    def select(self, *_args, **_kwargs):
        return self

    def eq(self, column, value):
        self.filters.append((column, value))
        self.rows = [r for r in self.rows if r.get(column) == value]
        return self

    def is_(self, column, value):
        assert value == "null"
        self.rows = [r for r in self.rows if r.get(column) is None]
        return self

    def execute(self):
        return type("Result", (), {"data": self.rows})()


class _Client:
    def __init__(self, rows):
        self.rows = rows

    def table(self, name):
        assert name == "cds_documents"
        return _Query(list(self.rows))


def _row(doc_id, year, detected=None, school="rivertown", sub=None, removed=None):
    return {"id": doc_id, "school_id": school, "cds_year": year, "detected_year": detected,
            "sub_institutional": sub, "removed_at": removed}


class FallbackYearForUnfiledDocumentTest(unittest.TestCase):
    DOC = {"id": "doc-1", "school_id": "rivertown", "cds_year": "unknown", "detected_year": None}

    def setUp(self):
        self._real = worker.detect_year_fallback_from_pdf_bytes
        worker.detect_year_fallback_from_pdf_bytes = lambda _data: "2025-26"

    def tearDown(self):
        worker.detect_year_fallback_from_pdf_bytes = self._real

    def test_unfiled_document_gets_the_fallback_year(self):
        client = _Client([_row("doc-1", "unknown"), _row("doc-2", "2024-25")])
        self.assertEqual(fallback_year_for_unfiled_document(client, dict(self.DOC), b"%PDF"), "2025-26")

    def test_a_document_with_a_year_is_left_alone(self):
        client = _Client([_row("doc-1", "2023-24")])
        self.assertIsNone(fallback_year_for_unfiled_document(client, {**self.DOC, "cds_year": "2023-24"}, b"%PDF"))
        self.assertIsNone(fallback_year_for_unfiled_document(client, {**self.DOC, "detected_year": "2023-24"}, b"%PDF"))

    def test_a_year_another_document_already_has_is_not_given_twice(self):
        for other in (_row("doc-2", "2025-26"), _row("doc-2", "2019-20", detected="2025-26")):
            client = _Client([_row("doc-1", "unknown"), other])
            self.assertIsNone(fallback_year_for_unfiled_document(client, dict(self.DOC), b"%PDF"))

    def test_removed_documents_other_schools_and_other_sub_institutions_do_not_block(self):
        rows = [
            _row("doc-1", "unknown"),
            _row("doc-2", "2025-26", removed="2026-11-01T00:00:00Z"),
            _row("doc-3", "2025-26", school="lakeside"),
            _row("doc-4", "2025-26", sub="law-school"),
        ]
        client = _Client(rows)
        self.assertTrue(not school_has_document_for_year(client, dict(self.DOC), "2025-26"))
        self.assertEqual(fallback_year_for_unfiled_document(client, dict(self.DOC), b"%PDF"), "2025-26")

    def test_no_fallback_year_means_no_year(self):
        worker.detect_year_fallback_from_pdf_bytes = lambda _data: None
        self.assertIsNone(fallback_year_for_unfiled_document(_Client([]), dict(self.DOC), b"%PDF"))


if __name__ == "__main__":
    unittest.main()
