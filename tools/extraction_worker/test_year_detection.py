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
        self.assertEqual(fallback_year_from_text("", "Common Data Set\nas of October 15 2023"), "2023-24")
        self.assertEqual(fallback_year_from_text("", "Common  Data Set\nAs of October\n15, 1999"), "1999-00")
        # A file that only ever says "CDS" (no title page).
        self.assertEqual(fallback_year_from_text("", "CDS responses: as of October 15, 2023"), "2023-24")

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
        text = "Common Data Set ... as of October 15, 2024 ... as of October 15, 2025"
        self.assertIsNone(fallback_year_from_text("", text))

    def test_an_october_15_deadline_is_not_the_reference_date(self):
        # C21 early-plan dates and aid deadlines fall on October 15 of the
        # year before the CDS year.
        text = "Common Data Set FY2026\nEarly action closing date: October 15, 2024\nPriority date: October 15, 2024"
        self.assertIsNone(fallback_year_from_text(text, text))
        text += "\n" + self.REFERENCE
        self.assertEqual(fallback_year_from_text(text, text), "2025-26")

    def test_a_document_that_never_names_the_common_data_set_gets_no_year(self):
        # An enrollment report with a census date.
        text = "Fall Enrollment Report\nHeadcount as of October 15, 2023." + " Fall 2023" * 8
        self.assertIsNone(fallback_year_from_text(text, text))

    def test_reference_date_that_disagrees_with_the_dominant_fall_term_is_refused(self):
        # A reused template with last year's date and no title span to
        # check it against.
        stale = "Common Data Set FY2026\nas of October 15, 2024." + " Fall 2025" * 6 + " Fall 2019" * 2
        self.assertIsNone(fallback_year_from_text(stale, stale))
        agrees = "Common Data Set FY2026\nas of October 15, 2025." + " Fall 2025" * 6 + " Fall 2019" * 2
        self.assertEqual(fallback_year_from_text(agrees, agrees), "2025-26")
        # No dominant fall term: the reference date stands.
        mixed = "Common Data Set FY2026\nas of October 15, 2025." + " Fall 2025" * 3 + " Fall 2024" * 3
        self.assertEqual(fallback_year_from_text(mixed, mixed), "2025-26")

    def test_reference_date_is_read_beyond_the_pages_the_title_patterns_read(self):
        self.assertEqual(
            fallback_year_from_text("A. General Information", "Common Data Set FY2026 page 14: " + self.REFERENCE),
            "2025-26",
        )

    def test_dominant_fall_term_picks_between_two_title_spans(self):
        strict = "Common Data Set 2022-2023\nCommon Data Set 2021-2022 definitions"
        text = strict + " Fall 2022" * 6 + " Fall 2016" * 3
        self.assertEqual(fallback_year_from_text(strict, text), "2022-23")

    def test_fall_term_never_gives_a_year_the_title_patterns_did_not_find(self):
        fall_only = " Fall 2022" * 9
        self.assertIsNone(fallback_year_from_text("", "Common Data Set" + fall_only))
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

    def test_the_documents_own_sub_institution_comes_from_its_row(self):
        # The drain's document dict has no sub_institutional key.
        rows = [_row("doc-1", "unknown", sub="law-school"), _row("doc-2", "2025-26", sub="law-school"), _row("doc-3", "2025-26")]
        self.assertTrue(school_has_document_for_year(_Client(rows), dict(self.DOC), "2025-26"))
        rows = [_row("doc-1", "unknown", sub="law-school"), _row("doc-3", "2025-26")]
        self.assertFalse(school_has_document_for_year(_Client(rows), dict(self.DOC), "2025-26"))

    def test_a_failure_leaves_the_document_without_a_year_and_does_not_raise(self):
        class _Broken:
            def table(self, _name):
                raise RuntimeError("connection reset")

        self.assertIsNone(fallback_year_for_unfiled_document(_Broken(), dict(self.DOC), b"%PDF"))

        def _boom(_data):
            raise IndexError("page 14")

        worker.detect_year_fallback_from_pdf_bytes = _boom
        self.assertIsNone(fallback_year_for_unfiled_document(_Client([]), dict(self.DOC), b"%PDF"))


class FallbackYearFromPdfBytesTest(unittest.TestCase):
    def _pdf(self, page_texts):
        """A minimal PDF with one line of Helvetica text per page."""
        pages = len(page_texts)
        objects = []
        kids = " ".join(f"{3 + 2 * i} 0 R" for i in range(pages))
        objects.append(b"<< /Type /Catalog /Pages 2 0 R >>")
        objects.append(f"<< /Type /Pages /Kids [{kids}] /Count {pages} >>".encode())
        font_obj = 3 + 2 * pages
        for i, text in enumerate(page_texts):
            stream = f"BT /F1 12 Tf 50 700 Td ({text}) Tj ET".encode()
            objects.append(
                f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
                f"/Contents {4 + 2 * i} 0 R /Resources << /Font << /F1 {font_obj} 0 R >> >> >>".encode()
            )
            objects.append(b"<< /Length %d >>\nstream\n" % len(stream) + stream + b"\nendstream")
        objects.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")
        out = bytearray(b"%PDF-1.4\n")
        offsets = []
        for n, body in enumerate(objects, start=1):
            offsets.append(len(out))
            out += f"{n} 0 obj\n".encode() + body + b"\nendobj\n"
        xref = len(out)
        out += f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode()
        for off in offsets:
            out += f"{off:010d} 00000 n \n".encode()
        out += f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
        return bytes(out)

    def test_reads_the_reference_date_past_page_ten_and_stops_at_page_twenty(self):
        pages = ["Rivertown State University Common Data Set FY2026"] + ["filler"] * 12
        found = pages + ["figures as of October 15, 2025"]
        self.assertEqual(worker.detect_year_fallback_from_pdf_bytes(self._pdf(found)), "2025-26")
        too_late = pages + ["filler"] * 8 + ["figures as of October 15, 2025"]
        self.assertIsNone(worker.detect_year_fallback_from_pdf_bytes(self._pdf(too_late)))

    def test_not_a_pdf_gives_no_year(self):
        self.assertIsNone(worker.detect_year_fallback_from_pdf_bytes(b"PK\x03\x04 Common Data Set as of October 15, 2025"))
        self.assertIsNone(worker.detect_year_fallback_from_pdf_bytes(b""))


if __name__ == "__main__":
    unittest.main()
