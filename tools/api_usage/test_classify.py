import unittest
from datetime import datetime, timezone

from tools.api_usage import classify as c

PRE = dict(before_t0=True)
POST = dict(before_t0=False)


class ClassifyTest(unittest.TestCase):
    def test_internal_signals_win(self):
        for signals in (
            c.Signals(role="service_role", client_info="collegedata-web/abc"),
            c.Signals(key_prefix="sb_secret_abc"),
            c.Signals(ua_internal=True, ua_browser=True),
            c.Signals(surface="edge_function", route_kind="archive-process"),
        ):
            self.assertEqual(c.classify(signals), (c.INTERNAL, False))

    def test_friendly_api_and_site_markers(self):
        self.assertEqual(
            c.classify(c.Signals(role="anon", client_info="collegedata-friendly-api/abc", **POST)),
            (c.FRIENDLY, False),
        )
        self.assertEqual(
            c.classify(c.Signals(role="anon", client_info="collegedata-web/abc", aws=True, **POST)),
            (c.FIRST_PARTY, False),
        )
        self.assertEqual(
            c.classify(c.Signals(referer_host="www.collegedata.fyi", ua_browser=True, surface="storage", **POST)),
            (c.FIRST_PARTY, False),
        )

    def test_lookalike_markers_are_third_party(self):
        self.assertEqual(
            c.classify(c.Signals(client_info="collegedata-scraper/1", **POST)),
            (c.THIRD_PARTY, False),
        )
        self.assertEqual(
            c.classify(c.Signals(referer_host="collegedata.fyi.evil.example", **POST)),
            (c.THIRD_PARTY, False),
        )

    def test_pre_t0_inference(self):
        node = c.Signals(role="anon", client_info="supabase-js-node/2.1", aws=True, **PRE)
        self.assertEqual(c.classify(node), (c.FIRST_PARTY, True))
        web = c.Signals(role="anon", client_info="supabase-js-web/2.1", ua_browser=True, **PRE)
        self.assertEqual(c.classify(web), (c.FIRST_PARTY, True))
        pdf = c.Signals(ua_browser=True, surface="storage", **PRE)
        self.assertEqual(c.classify(pdf), (c.BROWSER, True))
        off_aws = c.Signals(role="anon", client_info="supabase-js-node/2.1", aws=False, **PRE)
        self.assertEqual(c.classify(off_aws), (c.THIRD_PARTY, False))

    def test_post_t0_untagged_supabase_js_is_not_first_party(self):
        node = c.Signals(role="anon", client_info="supabase-js-node/2.1", aws=True, **POST)
        self.assertEqual(c.classify(node), (c.THIRD_PARTY, False))
        browser = c.Signals(ua_browser=True, surface="postgrest", **POST)
        self.assertEqual(c.classify(browser), (c.BROWSER, False))

    def test_t0_hour_counts_as_pre_tagging(self):
        t0 = datetime(2026, 10, 2, 14, 25, tzinfo=timezone.utc)
        self.assertTrue(c.is_before_t0(datetime(2026, 10, 2, 14, tzinfo=timezone.utc), t0))
        self.assertFalse(c.is_before_t0(datetime(2026, 10, 2, 15, tzinfo=timezone.utc), t0))
        self.assertTrue(c.is_before_t0(datetime(2030, 1, 1, tzinfo=timezone.utc), None))


class UserAgentTest(unittest.TestCase):
    CASES = [
        ("Mozilla/5.0 (Macintosh) AppleWebKit/605 Safari/605", True, "browser", None),
        ("Mozilla/5.0 (compatible; GPTBot/1.2; +https://openai.com/gptbot)", False, "ai_agent", "GPTBot"),
        ("Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko); compatible; ChatGPT-User/1.0; +https://openai.com/bot",
         False, "ai_agent", "ChatGPT-User"),
        ("Mozilla/5.0 (Windows NT 10.0) AppleWebKit/537.36 (KHTML, like Gecko) Claude/2.16 Chrome/152 Safari/537.36",
         False, "ai_agent", "Claude"),
        ("Claude-User (claude-code/2.1.284; +https://support.anthropic.com/)", False, "ai_agent", "Claude-User"),
        ("Mozilla/5.0 (Linux; Android 5.0) Mobile Safari/537.36 (compatible; Bytespider; spider-feedback@bytedance.com)",
         False, "declared_bot", "Bytespider"),
        ("Mozilla/5.0 (X11) Chrome/145 Safari/537.36 (compatible; meta-externalagent/1.1 "
         "(+https://developers.facebook.com/docs/sharing/webmasters/crawler))",
         False, "declared_bot", "meta-externalagent"),
        ("CollegeConnect-DataBot/1.0", False, "declared_bot", "CollegeConnect-DataBot"),
        ("msh-pdfmin/0.3", False, "integration", "msh-pdfmin"),
        ("node", False, "script", None),
        ("curl/8.7.1", False, "script", None),
        ("python-requests/2.32", False, "script", None),
        ("", False, "unknown", None),
    ]

    def test_family_and_name(self):
        for ua, browser, family, name in self.CASES:
            with self.subTest(ua=ua):
                self.assertEqual(c.ua_is_browser(ua), browser)
                self.assertEqual(c.client_family(ua), family)
                self.assertEqual(c.client_name_version(ua, family)[0], name)

    def test_supabase_sdk_client_is_integration(self):
        self.assertEqual(c.client_family("node", "supabase-js-node/2.50"), "integration")
        self.assertEqual(c.client_name_version("node", "integration", "supabase-js-node/2.50"), ("supabase-js-node", "2.50"))

    def test_internal_markers(self):
        self.assertTrue(c.ua_is_internal("collegedata-pipeline/cds-card-coverage"))
        self.assertFalse(c.ua_is_internal("python-requests/2.32"))


class RouteTest(unittest.TestCase):
    def test_edge_routes(self):
        self.assertEqual(c.edge_route("rest", "cds_documents", "", False, "GET"), ("postgrest", "cds_documents"))
        self.assertEqual(c.edge_route("rest", "rpc", "search_schools", False, "POST"), ("postgrest", "rpc:search_schools"))
        self.assertEqual(c.edge_route("rest", "", "", False, "GET"), ("postgrest", "root"))
        self.assertEqual(c.edge_route("rest", "Robert'); drop", "", False, "GET"), ("postgrest", "invalid"))
        self.assertEqual(c.edge_route("storage", "object", "public", True, "GET"), ("storage", "archive_file"))
        self.assertEqual(c.edge_route("storage", "object", "sign", False, "GET"), ("storage", "storage_other"))
        self.assertEqual(c.edge_route("rest", "schools", "", False, "OPTIONS"), ("postgrest", "options_preflight"))
        self.assertEqual(c.edge_route("admin", "", "", False, "GET"), ("other", "other"))

    def test_function_routes(self):
        self.assertEqual(c.function_route("/functions/v1/browser-search", "POST"), ("edge_function", "browser-search"))
        self.assertEqual(c.function_route("/archive-process", "POST"), ("edge_function", "archive-process"))

    def test_school_ids(self):
        self.assertEqual(c.school_id_from("harvard-university"), "harvard-university")
        self.assertIsNone(c.school_id_from("davenport+university"))
        self.assertIsNone(c.school_id_from("in.(a,b)"))
        self.assertIsNone(c.school_id_from(""))

    def test_status_class_and_host(self):
        self.assertEqual(c.status_class("206"), "2xx")
        self.assertEqual(c.status_class(404), "4xx")
        self.assertEqual(c.status_class(""), "other")
        self.assertEqual(c.normalize_host("API.collegedata.fyi"), "api.collegedata.fyi")
        self.assertEqual(c.normalize_host("evil.example"), "other")

    def test_client_hash_is_salted_and_short(self):
        salt_a, salt_b = "aa" * 32, "bb" * 32
        first = c.client_hash(salt_a, "203.0.113.7", "curl/8", "t13d")
        self.assertRegex(first, r"^[0-9a-f]{16}$")
        self.assertEqual(first, c.client_hash(salt_a, "203.0.113.7", "curl/8", "t13d"))
        self.assertNotEqual(first, c.client_hash(salt_b, "203.0.113.7", "curl/8", "t13d"))


if __name__ == "__main__":
    unittest.main()
