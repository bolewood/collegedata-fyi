import unittest

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

    def test_extract_document_candidates_picks_current_official_pdf(self):
        html = b"""
        <html><body>
          <a href="https://example.com/template.pdf">CDS template</a>
          <a href="/files/cds_2023-2024.pdf">2023-24</a>
          <a href="/files/cds_2024-25.pdf">2024-25 Common Data Set</a>
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

        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0].url, "https://example.edu/files/cds_2024-25.pdf")
        self.assertEqual(candidates[0].year, "2024-25")

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
