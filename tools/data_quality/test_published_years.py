"""Published-year coverage reads: canonical year, live rows only, no short pages."""

from __future__ import annotations

import unittest
from types import SimpleNamespace

from tools.data_quality.published_years import (
    canonical_year,
    fetch_all_rows,
    fetch_published_years,
    fetch_year_byte_coverage,
)


class _Query:
    def __init__(self, rows, count_override=None, drop_count=False):
        self.rows = rows
        self.count_override = count_override
        self.drop_count = drop_count
        self.filters = []
        self.lo, self.hi = 0, 10**9
        self.ordered = False

    def select(self, *_a, **_k):
        return self

    def or_(self, _expr):
        # The server narrows by year; the client re-checks canonical year, so
        # the fake can let every row through.
        return self

    def is_(self, col, _val):
        self.filters.append(lambda r: r.get(col) is None)
        return self

    def eq(self, col, val):
        self.filters.append(lambda r: r.get(col) == val)
        return self

    def in_(self, col, vals):
        self.filters.append(lambda r: r.get(col) in set(vals))
        return self

    def order(self, *_a):
        self.ordered = True
        return self

    def range(self, lo, hi):
        self.lo, self.hi = lo, hi
        return self

    def execute(self):
        assert self.ordered, "paged reads must carry a stable order"
        matched = [r for r in self.rows if all(f(r) for f in self.filters)]
        total = len(matched) if self.count_override is None else self.count_override
        return SimpleNamespace(
            data=matched[self.lo:self.hi + 1],
            count=None if self.drop_count else total,
        )


class _Sb:
    def __init__(self, tables, **kw):
        self.tables, self.kw = tables, kw

    def table(self, name):
        return _Query(self.tables[name], **self.kw)


def _doc(i, school="nyu", cds_year="2025-26", detected_year=None,
         status="published", removed_at=None, sha="abc"):
    return {
        "id": f"{i:06d}", "school_id": school, "cds_year": cds_year,
        "detected_year": detected_year, "participation_status": status,
        "removed_at": removed_at, "source_sha256": sha,
    }


class CanonicalYearTests(unittest.TestCase):
    def test_detected_year_wins_and_unknown_is_never_a_year(self) -> None:
        self.assertEqual(canonical_year({"cds_year": "unknown", "detected_year": "2025-26"}), "2025-26")
        self.assertEqual(canonical_year({"cds_year": "2025-26", "detected_year": "2023-24"}), "2023-24")
        self.assertEqual(canonical_year({"cds_year": "2024-25", "detected_year": None}), "2024-25")
        self.assertIsNone(canonical_year({"cds_year": "unknown", "detected_year": None}))


class FetchPublishedYearsTests(unittest.TestCase):
    def test_doc_filed_unknown_but_dated_counts_under_its_detected_year(self) -> None:
        sb = _Sb({"cds_documents": [_doc(1, cds_year="unknown", detected_year="2025-26")]})
        have = fetch_published_years(sb, ["nyu"], ["2025-26", "2024-25"])
        self.assertEqual(have["nyu"], {"2025-26"})

    def test_filed_year_does_not_count_when_the_document_is_dated_earlier(self) -> None:
        sb = _Sb({"cds_documents": [_doc(1, cds_year="2025-26", detected_year="2023-24")]})
        have = fetch_published_years(sb, ["nyu"], ["2025-26"])
        self.assertEqual(have["nyu"], set())

    def test_removed_documents_do_not_count(self) -> None:
        sb = _Sb({"cds_documents": [_doc(1, removed_at="2026-11-01T00:00:00Z")]})
        have = fetch_published_years(sb, ["nyu"], ["2025-26"])
        self.assertEqual(have["nyu"], set())

    def test_reads_past_one_thousand_rows(self) -> None:
        rows = [_doc(i, school="other", cds_year="2024-25") for i in range(1500)]
        rows.append(_doc(9999, school="nyu", cds_year="2025-26"))
        have = fetch_published_years(_Sb({"cds_documents": rows}), ["nyu"], ["2025-26"])
        self.assertEqual(have["nyu"], {"2025-26"})

    def test_short_read_raises_instead_of_reporting_no_coverage(self) -> None:
        sb = _Sb({"cds_documents": [_doc(1)]}, count_override=5)
        with self.assertRaises(RuntimeError):
            fetch_published_years(sb, ["nyu"], ["2025-26"])

    def test_missing_count_raises(self) -> None:
        sb = _Sb({"cds_documents": [_doc(1)]}, drop_count=True)
        with self.assertRaises(RuntimeError):
            fetch_all_rows(lambda: sb.table("cds_documents").order("id"))


class ByteCoverageTests(unittest.TestCase):
    def test_removed_and_unknown_dated_docs_follow_the_same_rules(self) -> None:
        docs = [
            _doc(1, cds_year="unknown", detected_year="2025-26"),
            _doc(2, school="mit", cds_year="2025-26", removed_at="2026-11-01T00:00:00Z"),
        ]
        arts = [{"id": "a1", "document_id": "000001", "storage_path": "p", "kind": "source"}]
        sb = _Sb({"cds_documents": docs, "cds_artifacts": arts})
        cov = fetch_year_byte_coverage(sb, ["nyu", "mit"], ["2025-26"])
        self.assertTrue(cov["nyu"]["2025-26"]["has_bytes"])
        self.assertFalse(cov["mit"]["2025-26"]["published"])


if __name__ == "__main__":
    unittest.main()
