import io
import json
import tempfile
import unittest
from datetime import date
from unittest import mock
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from tools.ops import discovery_renewal as dr
from tools.ops import same_year_duplicates as sd


def doc(i, school="a-college", year="2024-25", url=None, sha=None, **extra):
    row = {
        "id": f"{i:08d}-0000-0000-0000-000000000000",
        "school_id": school,
        "sub_institutional": None,
        "cds_year": year,
        "detected_year": year,
        "source_url": url if url is not None else f"https://x.edu/f{i}.pdf",
        "source_sha256": sha if sha is not None else f"sha{i}",
        "source_format": "pdf",
    }
    row.update(extra)
    return row


class FindGroupsTests(unittest.TestCase):
    def test_two_doc_group_is_found(self):
        report = sd.find_groups([doc(1), doc(2), doc(3, school="other")])
        self.assertEqual(report.count, 1)
        self.assertEqual(report.groups[0].school_id, "a-college")
        self.assertEqual(report.summary()["same_year_duplicates"], 1)

    def test_one_doc_per_year_is_not_a_group(self):
        report = sd.find_groups([doc(1, year="2023-24"), doc(2, year="2024-25")])
        self.assertEqual(report.count, 0)

    def test_unknown_group_is_reported_separately_not_mixed_in(self):
        rows = [
            doc(1, year="unknown", detected_year=None),
            doc(2, year="unknown", detected_year=None),
            doc(3, year="unknown", detected_year=None),
            doc(4, school="b-college"),
            doc(5, school="b-college"),
        ]
        report = sd.find_groups(rows)
        self.assertEqual(report.count, 1)
        self.assertEqual(report.groups[0].school_id, "b-college")
        self.assertEqual([g.school_id for g in report.undated], ["a-college"])
        self.assertEqual(report.summary()["undated_duplicates"], 1)
        self.assertEqual(sum(report.by_class.values()), 1)

    def test_invalid_year_shapes_are_undated(self):
        rows = [doc(1, year="2024-26", detected_year=None), doc(2, year="2024-26", detected_year=None)]
        report = sd.find_groups(rows)
        self.assertEqual(report.count, 0)
        self.assertEqual(len(report.undated), 1)

    def test_removed_and_unpublished_are_ignored(self):
        rows = [
            doc(1),
            doc(2, removed_at="2026-11-01T00:00:00Z"),
            doc(3, participation_status="withdrawn"),
        ]
        self.assertEqual(sd.find_groups(rows).count, 0)

    def test_sub_institutional_is_its_own_program(self):
        rows = [doc(1), doc(2, sub_institutional="general-studies")]
        self.assertEqual(sd.find_groups(rows).count, 0)

    def test_year_is_detected_year_then_cds_year(self):
        rows = [doc(1, year="2024-25", detected_year=None), doc(2, year="2024-25")]
        self.assertEqual(sd.find_groups(rows).count, 1)

    def test_missing_school_id_raises(self):
        with self.assertRaises(sd.DuplicatesError):
            sd.find_groups([doc(1, school="")])


class ClassifyTests(unittest.TestCase):
    def one(self, rows):
        report = sd.find_groups(rows)
        self.assertEqual(report.count, 1)
        return report.groups[0]

    def test_misfiled_by_url_year(self):
        g = self.one([
            doc(1, url="https://x.edu/CDS_2024-25.pdf"),
            doc(2, url="https://x.edu/CDS_2025-26.pdf"),
        ])
        self.assertEqual(g.cls, "misfiled_year")
        self.assertIn("2025-26", g.evidence)

    def test_filename_year_beats_folder_year(self):
        self.assertEqual(sd.url_year("https://x.edu/2025-26/CDS_2024-25.pdf"), "2024-25")
        self.assertEqual(sd.url_year("https://x.edu/2025-26/cds.pdf"), "2025-26")
        self.assertIsNone(sd.url_year("https://x.edu/cds.pdf"))
        self.assertIsNone(sd.url_year(None))

    def test_year_conflict_when_content_and_resolver_differ(self):
        g = self.one([doc(1), doc(2, cds_year="2025-26", detected_year="2024-25")])
        self.assertEqual(g.cls, "year_conflict")
        self.assertIn("content says 2024-25 but its URL/resolver says 2025-26", g.evidence)
        self.assertIn("#455", g.evidence)

    def test_year_conflict_in_the_other_direction_has_no_stale_title_note(self):
        g = self.one([doc(1), doc(2, cds_year="2023-24", detected_year="2024-25")])
        self.assertEqual(g.cls, "year_conflict")
        self.assertNotIn("#455", g.evidence)

    def test_content_override_is_not_called_misfiled_even_if_url_names_the_resolver_year(self):
        g = self.one([
            doc(1),
            doc(2, cds_year="2025-26", detected_year="2024-25", url="https://x.edu/CDS_2025-26.pdf"),
        ])
        self.assertEqual(g.cls, "year_conflict")

    def test_refiled_document_is_not_flagged_when_it_is_the_only_one_in_its_year(self):
        # A #455 re-filed document: detected 2025-26, resolver said 2024-25.
        # Its school's other 2024-25 document is not a collision.
        rows = [doc(1, year="2024-25"), doc(2, cds_year="2024-25", detected_year="2025-26")]
        self.assertEqual(sd.find_groups(rows).count, 0)

    def test_unknown_cds_year_with_detected_year_is_not_misfiled(self):
        g = self.one([doc(1, sha="s1"), doc(2, cds_year="unknown", detected_year="2024-25", sha="s2")])
        self.assertEqual(g.cls, "duplicate")

    def test_section_split(self):
        g = self.one([
            doc(1, url="https://x.edu/CDS_2024-25.pdf"),
            doc(2, url="https://x.edu/CDS_2024-25-D.pdf"),
        ])
        self.assertEqual(g.cls, "section_split")
        self.assertIn("CDS_2024-25-D.pdf", g.evidence)

    def test_same_file(self):
        g = self.one([doc(1, sha="same"), doc(2, sha="same")])
        self.assertEqual(g.cls, "same_file")

    def test_missing_sha_is_never_same_file(self):
        g = self.one([doc(1, sha=""), doc(2, sha="")])
        self.assertEqual(g.cls, "duplicate")
        g = self.one([doc(1, source_sha256=None), doc(2, source_sha256=None)])
        self.assertEqual(g.cls, "duplicate")

    def test_duplicate(self):
        g = self.one([doc(1), doc(2)])
        self.assertEqual(g.cls, "duplicate")

    def test_misfiled_wins_over_section_and_same_file(self):
        g = self.one([
            doc(1, url="https://x.edu/CDS_2024-25-D.pdf", sha="same"),
            doc(2, url="https://x.edu/CDS_2025-26.pdf", sha="same"),
        ])
        self.assertEqual(g.cls, "misfiled_year")

    def test_by_class_counts_every_class(self):
        rows = [
            doc(1, school="s1"), doc(2, school="s1"),
            doc(3, school="s2", sha="x"), doc(4, school="s2", sha="x"),
            doc(5, school="s3", url="https://x.edu/CDS_2024-25-D.pdf"), doc(6, school="s3"),
            doc(7, school="s4", url="https://x.edu/CDS_2025-26.pdf"), doc(8, school="s4"),
        ]
        self.assertEqual(
            sd.find_groups(rows).by_class,
            {"misfiled_year": 1, "year_conflict": 0, "section_split": 1, "same_file": 1, "duplicate": 1},
        )


class RenderTests(unittest.TestCase):
    def test_markdown_lists_groups_and_escapes_pipes(self):
        report = sd.find_groups([doc(1, url="https://x.edu/a|b.pdf"), doc(2)])
        text = sd.render_markdown(report)
        self.assertIn("## Two documents in one year", text)
        self.assertIn("a-college", text)
        self.assertIn("Undated duplicates (0)", text)

    def test_markdown_empty(self):
        text = sd.render_markdown(sd.find_groups([doc(1)]))
        self.assertIn("0 school-years", text)
        self.assertIn("None.", text)


def make_get(rows, *, total=None, page_size=2, content_range=True):
    """Fake http_json serving `rows` in pages."""

    def get(url, headers):
        offset = int(url.rsplit("offset=", 1)[1])
        page = rows[offset:offset + page_size]
        t = len(rows) if total is None else total
        hdr = {"content-range": f"{offset}-{offset + len(page) - 1}/{t}"} if content_range else {}
        return page, hdr

    return get


class FetchTests(unittest.TestCase):
    def setUp(self):
        self._page = sd.PAGE_SIZE
        sd.PAGE_SIZE = 2

    def tearDown(self):
        sd.PAGE_SIZE = self._page

    def test_reads_every_page(self):
        rows = [doc(i, school=f"s{i}") for i in range(5)]
        got = sd.fetch_live_documents("https://api", "k", get=make_get(rows))
        self.assertEqual(len(got), 5)

    def test_short_read_raises(self):
        rows = [doc(i, school=f"s{i}") for i in range(4)]
        with self.assertRaises(sd.DuplicatesError):
            sd.fetch_live_documents("https://api", "k", get=make_get(rows, total=9))

    def test_zero_rows_raises(self):
        with self.assertRaises(sd.DuplicatesError):
            sd.fetch_live_documents("https://api", "k", get=make_get([]))

    def test_missing_content_range_raises(self):
        with self.assertRaises(sd.DuplicatesError):
            sd.fetch_live_documents("https://api", "k", get=make_get([doc(1)], content_range=False))

    def test_query_filters_live_published(self):
        self.assertIn("removed_at=is.null", sd.DOCUMENTS_QUERY)
        self.assertIn("participation_status=eq.published", sd.DOCUMENTS_QUERY)
        for col in sd.REQUIRED_KEYS:
            self.assertIn(col, sd.DOCUMENTS_QUERY)

    def test_small_total_raises(self):
        with self.assertRaises(sd.DuplicatesError):
            sd.check_rows([doc(1), doc(2)])

    def test_missing_column_raises(self):
        row = doc(1)
        del row["source_sha256"]
        with self.assertRaises(sd.DuplicatesError):
            sd.check_rows([row], enforce_min=False)


class CliTests(unittest.TestCase):
    def run_cli(self, rows):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "docs.json"
            path.write_text(json.dumps(rows))
            out, err = io.StringIO(), io.StringIO()
            with redirect_stdout(out), redirect_stderr(err):
                code = sd.main(["--from-json", str(path)])
        return code, out.getvalue(), err.getvalue()

    def test_data_error_exits_one(self):
        code, _, err = self.run_cli([doc(1)])
        self.assertEqual(code, 1)
        self.assertIn("ERROR", err)

    def test_duplicates_found_still_exits_zero(self):
        rows = [doc(i, school=f"s{i}") for i in range(sd.MIN_DOCUMENTS)] + [doc(5000, school="s0")]
        code, out, _ = self.run_cli(rows)
        self.assertEqual(code, 0)
        self.assertIn("1 school-years", out)

    def test_no_anon_key_exits_one(self):
        err = io.StringIO()
        with redirect_stderr(err), redirect_stdout(io.StringIO()):
            code = sd.main(["--anon-key", ""])
        self.assertEqual(code, 1)


def renewal_rows():
    rows = []
    for i in range(400):
        rows.append({"school_id": f"s{i}", "canonical_year": "2024-25",
                     "participation_status": "published", "removed_at": None,
                     "discovered_at": "2026-01-01T00:00:00+00:00"})
    return rows


class RenewalWiringTests(unittest.TestCase):
    """The renewal job reports the same classifier's count."""

    def report(self):
        return sd.find_groups([doc(1), doc(2), doc(3, school="b", cds_year="2023-24", detected_year="2023-24")])

    def test_summary_carries_the_count_and_is_null_when_not_computed(self):
        result = dr.compute(renewal_rows(), date(2026, 11, 24))
        self.assertEqual(dr.summary_dict(result, same_year_duplicates=3)["same_year_duplicates"], 3)
        self.assertIsNone(dr.summary_dict(result)["same_year_duplicates"])

    def test_report_has_the_section_only_when_computed(self):
        result = dr.compute(renewal_rows(), date(2026, 11, 24))
        with_it = dr.render_report(result, [], duplicates=self.report())
        self.assertIn("## Two documents in one year", with_it)
        self.assertIn("a-college", with_it)
        self.assertNotIn("Two documents in one year", dr.render_report(result, []))

    def run_main(self, dup_run):
        with tempfile.TemporaryDirectory() as tmp, \
                mock.patch.object(dr, "fetch_live_manifest", return_value=renewal_rows()), \
                mock.patch.object(dr, "fetch_sql_floor", return_value="2025-26"), \
                mock.patch.object(sd, "run", dup_run), \
                redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            out = Path(tmp) / "summary.json"
            code = dr.main([
                "--anon-key", "k", "--as-of", "2026-11-24", "--test-mode",
                "--out-summary", str(out), "--out-report", str(Path(tmp) / "r.md"),
            ])
            return code, (json.loads(out.read_text()) if out.exists() else None)

    def test_job_writes_the_count_to_the_summary(self):
        code, summary = self.run_main(lambda api, key: self.report())
        self.assertEqual(code, 0)
        self.assertEqual(summary["same_year_duplicates"], 1)

    def test_a_data_error_in_the_duplicate_check_fails_the_job(self):
        def boom(api, key):
            raise sd.DuplicatesError("short read")

        code, summary = self.run_main(boom)
        self.assertEqual(code, 1)
        self.assertIsNone(summary)


if __name__ == "__main__":
    unittest.main()
