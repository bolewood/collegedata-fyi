import unittest
from datetime import date

from tools.ops import directory_enqueue_autopilot as autopilot


class DirectoryEnqueueAutopilotTests(unittest.TestCase):
    def test_root_domain_from_url_normalizes_www(self):
        self.assertEqual(
            autopilot.root_domain_from_url("https://www.oregonstate.edu/"),
            "oregonstate.edu",
        )
        self.assertEqual(
            autopilot.root_domain_from_url("gmu.edu"),
            "gmu.edu",
        )

    def test_is_high_signal_prefers_large_enrollment(self):
        self.assertTrue(autopilot.is_high_signal({
            "school_name": "Large Regional College",
            "undergraduate_enrollment": 12000,
        }, 10000))
        self.assertFalse(autopilot.is_high_signal({
            "school_name": "Small College",
            "undergraduate_enrollment": 1800,
        }, 10000))

    def test_high_signal_scores_state_university_above_generic_college(self):
        state_university = {
            "school_name": "Savannah State University",
            "state": "GA",
            "undergraduate_enrollment": 2833,
        }
        generic_college = {
            "school_name": "Bismarck State College",
            "state": "ND",
            "undergraduate_enrollment": 2839,
        }

        self.assertGreater(
            autopilot.high_signal_score(state_university, 5000),
            autopilot.high_signal_score(generic_college, 5000),
        )

    def test_extract_document_candidates_picks_current_official_pdf(self):
        floor = autopilot.default_min_fresh_year()
        html = b"""
        <html><body>
          <a href="https://example.com/template.pdf">CDS template</a>
          <a href="/files/cds_2023-2024.pdf">2023-24</a>
          <a href="/files/cds_{floor}.pdf">{floor} Common Data Set</a>
        </body></html>
        """.replace(b"{floor}", floor.encode())

        def fake_fetch(url, *, read_bytes=0, timeout=20):
            return 200, {"content-type": "text/html"}, html

        old_fetch = autopilot.fetch_bytes
        try:
            autopilot.fetch_bytes = fake_fetch
            candidates = autopilot.extract_document_candidates(
                "https://example.edu/common-data-set",
                "example.edu",
            )
        finally:
            autopilot.fetch_bytes = old_fetch

        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0].url, f"https://example.edu/files/cds_{floor}.pdf")
        self.assertEqual(candidates[0].year, floor)

    def test_equal_scores_prefer_the_newer_year(self):
        html = b"""
        <a href="/files/cds_2019-20.pdf">2019-20 Common Data Set</a>
        <a href="/files/cds_2021-22.pdf">2021-22 Common Data Set</a>
        """

        def fake_fetch(url, *, read_bytes=0, timeout=20):
            return 200, {"content-type": "text/html"}, html

        old_fetch = autopilot.fetch_bytes
        try:
            autopilot.fetch_bytes = fake_fetch
            kept = autopilot.extract_document_candidates(
                "https://example.edu/cds", "example.edu",
            )
        finally:
            autopilot.fetch_bytes = old_fetch
        self.assertEqual(kept[0].year, "2021-22")

    def test_current_year_re_follows_the_freshness_floor(self):
        nov_2026 = autopilot.current_year_re(date(2026, 11, 24))
        for text in ("CDS 2025-26", "cds_2025-2026.pdf", "2025_26", "20252026", "2026-27"):
            self.assertTrue(nov_2026.search(text), text)
        for text in ("CDS 2024-25", "cds_2023-2024.pdf"):
            self.assertFalse(nov_2026.search(text), text)
        sep_2027 = autopilot.current_year_re(date(2027, 9, 1))
        self.assertTrue(sep_2027.search("CDS 2026-27"))
        self.assertTrue(sep_2027.search("CDS 2027-28"))
        self.assertFalse(sep_2027.search("CDS 2025-26"))

    def test_extract_document_candidates_reports_what_the_cap_dropped(self):
        html = b"""
        <a href="/files/cds_2025-26.pdf">2025-26 Common Data Set</a>
        <a href="/files/cds_2024-25.pdf">2024-25 Common Data Set</a>
        <a href="/files/cds_2023-24.pdf">2023-24 Common Data Set</a>
        """

        def fake_fetch(url, *, read_bytes=0, timeout=20):
            return 200, {"content-type": "text/html"}, html

        old_fetch = autopilot.fetch_bytes
        try:
            autopilot.fetch_bytes = fake_fetch
            dropped = {}
            kept = autopilot.extract_document_candidates(
                "https://example.edu/cds", "example.edu", max_docs=1, dropped=dropped,
            )
        finally:
            autopilot.fetch_bytes = old_fetch
        self.assertEqual(len(kept), 1)
        self.assertEqual(dropped["docs_capped"], 2)

    def test_extract_document_candidates_rejects_non_official_host(self):
        html = b"""
        <html><body>
          <a href="https://thirdparty.test/cds_2024-25.pdf">2024-25 Common Data Set</a>
        </body></html>
        """

        def fake_fetch(url, *, read_bytes=0, timeout=20):
            return 200, {"content-type": "text/html"}, html

        old_fetch = autopilot.fetch_bytes
        try:
            autopilot.fetch_bytes = fake_fetch
            candidates = autopilot.extract_document_candidates(
                "https://example.edu/common-data-set",
                "example.edu",
            )
        finally:
            autopilot.fetch_bytes = old_fetch

        self.assertEqual(candidates, [])


if __name__ == "__main__":
    unittest.main()
