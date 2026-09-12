"""Tests for CDS URL discovery helpers in probe_urls.py."""

from __future__ import annotations

import io
import json
import sys
import unittest
from types import SimpleNamespace
from unittest import mock

import yaml

from tools.finder.probe_urls import (
    _get_bounded,
    _save_yaml,
    AUDITABLE_ARCHIVE_OUTCOMES,
    VALIDATION_INVALID,
    VALIDATION_UNVERIFIABLE,
    VALIDATION_VALID,
    SCHOOLS_YAML,
    audit_active_html_seeds,
    brave_cds_candidates,
    brave_search,
    fetch_latest_terminal_archive_rows,
    host_belongs_to_domain,
    html_has_cds_content_or_anchors,
    is_cds_page,
    looks_like_search_junk,
    may_mark_active,
    process_school,
    select_brave_cds_url,
    should_replace_seed,
    should_skip,
    dedupe_identical_seeds,
    validate_cds_url,
    write_probe_summary,
)


class SelectBraveCdsUrlTests(unittest.TestCase):
    def test_prefers_html_listing_over_year_specific_pdf(self) -> None:
        results = [
            {
                "url": "https://www.ou.edu/content/dam/irr/docs/CDS%202023-2024%20Combined.pdf",
                "title": "CDS 2023-2024 Combined.pdf",
                "description": "Common Data Set 2023-2024",
            },
            {
                "url": "https://www.ou.edu/irr/other-reports",
                "title": "Other Reports | Institutional Research & Reporting",
                "description": "Facts at a Glance, the Factbook, and the Common Data Set (CDS).",
            },
        ]
        self.assertEqual(
            select_brave_cds_url(results),
            "https://www.ou.edu/irr/other-reports",
        )

    def test_falls_back_to_pdf_when_no_listing_mentions_cds(self) -> None:
        results = [
            {
                "url": "https://example.edu/ir/cds-2023-2024.pdf",
                "title": "CDS 2023-2024",
                "description": "Common Data Set",
            },
            {
                "url": "https://example.edu/ir/",
                "title": "Institutional Research",
                "description": "Enrollment dashboards and fact books.",
            },
        ]
        self.assertEqual(
            select_brave_cds_url(results),
            "https://example.edu/ir/cds-2023-2024.pdf",
        )

    def test_rejects_definitions_pdf_and_listing(self) -> None:
        results = [
            {
                "url": "https://example.edu/cds-definitions.pdf",
                "title": "Common Data Set Definitions",
                "description": "Common Data Set definitions",
            },
            {
                "url": "https://example.edu/cds-template.pdf",
                "title": "CDS template",
                "description": "Common Data Set",
            },
        ]
        self.assertIsNone(select_brave_cds_url(results))

    def test_rejects_off_domain_and_search_junk_paths(self) -> None:
        results = [
            {
                "url": "https://search.elms.edu/=327/krespectf/stanford+common+data+set.pdf",
                "title": "Common Data Set",
                "description": "Common Data Set",
            },
            {
                "url": "https://other.edu/ir/common-data-set/",
                "title": "Common Data Set",
                "description": "Common Data Set",
            },
            {
                "url": "https://www.elms.edu/ir/common-data-set/",
                "title": "Common Data Set",
                "description": "Common Data Set",
            },
        ]
        self.assertEqual(
            select_brave_cds_url(results, "elms.edu"),
            "https://www.elms.edu/ir/common-data-set/",
        )
        self.assertTrue(looks_like_search_junk(results[0]["url"]))
        self.assertTrue(host_belongs_to_domain(results[2]["url"], "elms.edu"))
        self.assertFalse(host_belongs_to_domain(results[1]["url"], "elms.edu"))

    def test_rejects_blog_slugs_that_are_not_cds_paths(self) -> None:
        from tools.finder.probe_urls import looks_like_article_slug

        self.assertTrue(
            looks_like_article_slug(
                "https://www.continents.us/does-harvard-accept-2-9-gpa/"
            )
        )
        self.assertTrue(
            looks_like_article_slug(
                "https://www.continents.us/does-harvard-accept-2-9-gpa/5/"
            )
        )
        self.assertFalse(
            looks_like_article_slug(
                "https://www.albion.edu/offices/registrar/institutional-data/"
            )
        )
        self.assertFalse(
            looks_like_article_slug(
                "https://provost.tufts.edu/institutionalresearch/wp-content/uploads/sites/5/CDS_2024-2025-1.pdf"
            )
        )

    def test_select_brave_rejects_paginated_blog_slug(self) -> None:
        results = [
            {
                "url": "https://www.continents.us/does-harvard-accept-2-9-gpa/5/",
                "title": "Common Data Set",
                "description": "Common Data Set",
            }
        ]
        self.assertIsNone(select_brave_cds_url(results, "continents.us"))

    def test_rejects_news_pages_and_non_cds_pdfs(self) -> None:
        from tools.finder.probe_urls import (
            looks_like_news_or_blog,
            looks_like_non_cds_document,
        )

        self.assertTrue(
            looks_like_news_or_blog("https://www.widener.edu/news/noteworthy?page=2")
        )
        self.assertTrue(
            looks_like_news_or_blog(
                "https://www.bakeru.edu/about-baker/careers-baker"
            )
        )
        self.assertTrue(
            looks_like_news_or_blog(
                "https://faculty.nps.edu/ncrowe/oldstudents/jshaver_thesis.htm"
            )
        )
        self.assertTrue(
            looks_like_non_cds_document(
                "https://www.csuci.edu/budget/documents/otp-budget-presentation-fy17-18.pdf"
            )
        )
        self.assertFalse(
            looks_like_non_cds_document(
                "https://example.edu/ir/CDS_2023-2024.pdf"
            )
        )

    def test_candidate_order_keeps_all_listings_before_pdf_fallback(self) -> None:
        results = [
            {
                "url": "https://example.edu/ir/cds-2024.pdf",
                "title": "Common Data Set 2024",
                "description": "Common Data Set",
            },
            {
                "url": "https://example.edu/mission",
                "title": "Common Data Set",
                "description": "Institutional research",
            },
            {
                "url": "https://example.edu/ir/reports",
                "title": "Reports",
                "description": "Common Data Set reports",
            },
        ]
        self.assertEqual(
            brave_cds_candidates(results, "example.edu"),
            [
                "https://example.edu/mission",
                "https://example.edu/ir/reports",
                "https://example.edu/ir/cds-2024.pdf",
            ],
        )

    def test_brave_fetch_validation_continues_to_pdf_fallback(self) -> None:
        results = {
            "web": {
                "results": [
                    {
                        "url": "https://example.edu/mission",
                        "title": "Common Data Set",
                        "description": "Common Data Set",
                    },
                    {
                        "url": "https://example.edu/ir/cds-2024.pdf",
                        "title": "CDS 2024",
                        "description": "Common Data Set",
                    },
                ]
            }
        }
        with (
            mock.patch(
                "tools.finder.probe_urls._get_full",
                return_value=(200, {}, json.dumps(results).encode()),
            ),
            mock.patch(
                "tools.finder.probe_urls.validate_cds_url",
                side_effect=[
                    (VALIDATION_INVALID, "html_without_cds_content_or_anchors"),
                    (VALIDATION_VALID, "pdf_magic"),
                ],
            ) as validate,
        ):
            selected = brave_search("example.edu", "test-key")
        self.assertEqual(selected, "https://example.edu/ir/cds-2024.pdf")
        self.assertEqual(validate.call_count, 2)

    def test_brave_returns_none_when_unique_candidates_are_not_valid(self) -> None:
        results = {
            "web": {
                "results": [
                    {
                        "url": "https://example.edu/mission",
                        "title": "Common Data Set",
                        "description": "Common Data Set",
                    },
                    {
                        "url": "https://example.edu/mission",
                        "title": "Duplicate",
                        "description": "Common Data Set",
                    },
                    {
                        "url": "https://example.edu/cds.pdf",
                        "title": "CDS",
                        "description": "Common Data Set",
                    },
                ]
            }
        }
        with (
            mock.patch(
                "tools.finder.probe_urls._get_full",
                return_value=(200, {}, json.dumps(results).encode()),
            ),
            mock.patch(
                "tools.finder.probe_urls.validate_cds_url",
                side_effect=[
                    (VALIDATION_INVALID, "html_without_cds_content_or_anchors"),
                    (VALIDATION_UNVERIFIABLE, "http_403"),
                ],
            ) as validate,
        ):
            self.assertIsNone(brave_search("example.edu", "test-key"))
        self.assertEqual(validate.call_count, 2)


class IsCdsPageTests(unittest.TestCase):
    def test_mixed_ir_hub_cds_heading_below_5kb_still_matches(self) -> None:
        prefix = ("x" * 6000).encode()
        body = prefix + b"<h2>Common Data Set (CDS)</h2>"
        self.assertTrue(is_cds_page(body, "text/html; charset=utf-8"))


class FetchedCandidateValidationTests(unittest.TestCase):
    def test_validation_fetch_is_bounded(self) -> None:
        class FakeResponse(io.BytesIO):
            status = 200

            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

            def getheaders(self):
                return [("Content-Type", "text/html")]

            def geturl(self):
                return "https://example.edu/cds"

        response = FakeResponse(b"x" * 100)
        with mock.patch("urllib.request.urlopen", return_value=response):
            status, _headers, body, _final_url, truncated = _get_bounded(
                "https://example.edu/cds",
                max_bytes=16,
            )
        self.assertEqual(status, 200)
        self.assertEqual(len(body), 16)
        self.assertTrue(truncated)

    def test_validation_fetch_enforces_wall_clock_deadline(self) -> None:
        class SlowResponse:
            status = 200

            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

            def getheaders(self):
                return [("Content-Type", "text/html")]

            def geturl(self):
                return "https://example.edu/cds"

            def read1(self, _size):
                return b"x"

            def read(self, _size):
                return b"x"

        with (
            mock.patch("urllib.request.urlopen", return_value=SlowResponse()),
            mock.patch(
                "tools.finder.probe_urls.time.monotonic",
                side_effect=[0.0, 0.0, 16.0],
            ),
        ):
            status, _headers, body, _final_url, truncated = _get_bounded(
                "https://example.edu/cds",
                timeout=15,
            )
        self.assertEqual(status, -1)
        self.assertEqual(body, b"")
        self.assertFalse(truncated)

    def test_html_requires_real_cds_anchor(self) -> None:
        valid = b"""
        <html><h1>Common Data Set</h1>
        <a href="/files/CDS_2024-2025.pdf">2024-25 Common Data Set</a></html>
        """
        false_page = b"""
        <html><h1>IRAE Mission</h1>
        <nav>Common Data Set</nav><p>Our mission is institutional excellence.</p></html>
        """
        self.assertTrue(html_has_cds_content_or_anchors(valid))
        self.assertFalse(html_has_cds_content_or_anchors(false_page))

    def test_navigation_only_cds_committee_link_is_not_content(self) -> None:
        false_page = b"""
        <html><nav>
        <a href="/about/cds-committee">CDS committee</a>
        <a href="/common-data-set-faq">Common Data Set FAQ</a>
        <a href="/about/committee">CDS committee</a>
        <a href="/about?topic=common-data-set-faq">FAQ</a>
        </nav>
        <p>Institutional research home page.</p></html>
        """
        self.assertFalse(html_has_cds_content_or_anchors(false_page))

    def test_policy_directory_can_contain_legitimate_cds_landing_link(self) -> None:
        valid = b"""
        <html><nav>
        <a href="/institutional-policy/common-data-set/">Common Data Set</a>
        </nav></html>
        """
        self.assertTrue(html_has_cds_content_or_anchors(valid))

    def test_common_data_phrase_plus_unrelated_documents_is_not_enough(self) -> None:
        false_page = b"""
        <html><p>A Common Data Set was cited in this article.</p>
        <a href="/jobs/application.pdf">Application</a>
        <a href="/research/thesis.pdf">Thesis</a></html>
        """
        self.assertFalse(html_has_cds_content_or_anchors(false_page))

    def test_pdf_magic_is_valid_even_for_opaque_url(self) -> None:
        with mock.patch(
            "tools.finder.probe_urls._get_bounded",
            return_value=(
                200,
                {"content-type": "application/octet-stream"},
                b"%PDF-1.7\n...",
                "https://example.edu/download?id=123",
                False,
            ),
        ):
            self.assertEqual(
                validate_cds_url("https://example.edu/download?id=123"),
                (VALIDATION_VALID, "pdf_magic"),
            )

    def test_successful_false_html_is_definitively_invalid(self) -> None:
        with mock.patch(
            "tools.finder.probe_urls._get_bounded",
            return_value=(
                200,
                {"content-type": "text/html"},
                b"<html><h1>IRAE Mission</h1><p>Common Data Set</p></html>",
                "https://example.edu/mission",
                False,
            ),
        ):
            self.assertEqual(
                validate_cds_url("https://example.edu/mission"),
                (
                    VALIDATION_INVALID,
                    "html_without_cds_content_or_anchors",
                ),
            )

    def test_truncated_html_without_early_cds_anchor_is_unverifiable(self) -> None:
        with mock.patch(
            "tools.finder.probe_urls._get_bounded",
            return_value=(
                200,
                {"content-type": "text/html"},
                b"<html><h1>Institutional research</h1>",
                "https://example.edu/reports",
                True,
            ),
        ):
            self.assertEqual(
                validate_cds_url("https://example.edu/reports"),
                (
                    VALIDATION_UNVERIFIABLE,
                    "html_validation_window_exhausted",
                ),
            )

    def test_contextual_page_path_is_invalid_even_with_form_terms(self) -> None:
        with mock.patch(
            "tools.finder.probe_urls._get_bounded",
            return_value=(
                200,
                {"content-type": "text/html"},
                (
                    b"<html>Common Data Set applicants enrolled tuition "
                    b"degrees conferred</html>"
                ),
                "https://example.edu/careers-baker",
                False,
            ),
        ):
            self.assertEqual(
                validate_cds_url("https://example.edu/careers-baker"),
                (VALIDATION_INVALID, "contextual_page_path"),
            )

    def test_office_magic_with_spreadsheet_content_type_is_valid(self) -> None:
        with mock.patch(
            "tools.finder.probe_urls._get_bounded",
            return_value=(
                200,
                {
                    "content-type": (
                        "application/vnd.openxmlformats-officedocument."
                        "spreadsheetml.sheet"
                    )
                },
                b"PK\x03\x04...",
                "https://example.edu/download?id=123",
                False,
            ),
        ):
            self.assertEqual(
                validate_cds_url("https://example.edu/download?id=123"),
                (VALIDATION_VALID, "office_magic"),
            )

    def test_transient_and_access_failures_are_unverifiable(self) -> None:
        for status in (-1, 403, 405, 429, 500, 503):
            with self.subTest(status=status), mock.patch(
                "tools.finder.probe_urls._get_bounded",
                return_value=(status, {}, b"", "https://example.edu/cds", False),
            ):
                validation, _reason = validate_cds_url("https://example.edu/cds")
                self.assertEqual(validation, VALIDATION_UNVERIFIABLE)

    def test_404_is_definitively_invalid(self) -> None:
        with mock.patch(
            "tools.finder.probe_urls._get_bounded",
            return_value=(404, {}, b"", "https://example.edu/missing", False),
        ):
            self.assertEqual(
                validate_cds_url("https://example.edu/missing"),
                (VALIDATION_INVALID, "http_404"),
            )


class ActiveHtmlAuditTests(unittest.TestCase):
    def test_archive_lookup_excludes_school_with_newer_active_queue_row(self) -> None:
        terminal_rows = [
            {
                "school_id": "eligible",
                "processed_at": "2026-09-10T00:00:00Z",
                "last_outcome": "no_pdfs_found",
                "cds_url_hint": "https://eligible.edu/cds/",
                "status": "done",
                "active_work": False,
            },
            {
                "school_id": "processing",
                "processed_at": "2026-09-10T00:00:00Z",
                "last_outcome": "wrong_content_type",
                "cds_url_hint": "https://processing.edu/cds/",
                "status": "done",
                "active_work": True,
            },
        ]

        class FakeCommand:
            def __init__(self, data):
                self.data = data

            def execute(self):
                return SimpleNamespace(data=self.data)

        class FakeClient:
            def rpc(self, _name, _params):
                return FakeCommand(terminal_rows)

            def table(self, _name):
                raise AssertionError("active-work check must stay inside the RPC")

        schools = [
            {
                "id": "eligible",
                "scrape_policy": "active",
                "discovery_seed_url": "https://eligible.edu/cds/",
            },
            {
                "id": "processing",
                "scrape_policy": "active",
                "discovery_seed_url": "https://processing.edu/cds/",
            },
            {
                "id": "direct-document",
                "scrape_policy": "active",
                "discovery_seed_url": "https://example.edu/CDS_2024.pdf",
            },
        ]
        fake_module = SimpleNamespace(create_client=lambda _url, _key: FakeClient())
        with mock.patch.dict(sys.modules, {"supabase": fake_module}):
            rows = fetch_latest_terminal_archive_rows(
                schools,
                supabase_url="https://example.supabase.co",
                service_role_key="test-key",
            )
        self.assertEqual([row["school_id"] for row in rows], ["eligible"])
        self.assertEqual(rows[0]["status"], "done")

    def test_terminal_content_failure_and_invalid_live_page_demotes(self) -> None:
        school = {
            "id": "west-virginia-state-university",
            "scrape_policy": "active",
            "discovery_seed_url": "https://wvstateu.edu/mission/",
            "probe_state": {"last_result": "found"},
        }
        rows = [
            {
                "school_id": school["id"],
                "status": "failed_permanent",
                "last_outcome": "no_pdfs_found",
                "processed_at": "2026-09-10T00:00:00Z",
                "cds_url_hint": school["discovery_seed_url"],
            }
        ]
        with mock.patch(
            "tools.finder.probe_urls.validate_cds_url",
            return_value=(
                VALIDATION_INVALID,
                "html_without_cds_content_or_anchors",
            ),
        ):
            results = audit_active_html_seeds([school], rows)
        self.assertTrue(results[0]["demoted"])
        self.assertEqual(school["scrape_policy"], "unknown")
        self.assertNotIn("discovery_seed_url", school)
        self.assertEqual(school["probe_state"]["last_method"], "active_html_audit")

    def test_403_does_not_demote_existing_seed(self) -> None:
        school = {
            "id": "blocked-school",
            "scrape_policy": "active",
            "discovery_seed_url": "https://blocked.edu/common-data-set/",
        }
        rows = [
            {
                "school_id": school["id"],
                "status": "failed_permanent",
                "last_outcome": "no_pdfs_found",
                "cds_url_hint": school["discovery_seed_url"],
            }
        ]
        with mock.patch(
            "tools.finder.probe_urls.validate_cds_url",
            return_value=(VALIDATION_UNVERIFIABLE, "http_403"),
        ):
            results = audit_active_html_seeds([school], rows)
        self.assertFalse(results[0]["demoted"])
        self.assertEqual(school["scrape_policy"], "active")
        self.assertIn("discovery_seed_url", school)

    def test_failure_for_obsolete_seed_cannot_demote_current_seed(self) -> None:
        school = {
            "id": "changed-school",
            "scrape_policy": "active",
            "discovery_seed_url": "https://example.edu/new-common-data-set/",
        }
        rows = [
            {
                "school_id": school["id"],
                "status": "done",
                "last_outcome": "no_pdfs_found",
                "processed_at": "2026-09-10T00:00:00Z",
                "cds_url_hint": "https://example.edu/old-mission/",
            }
        ]
        with mock.patch("tools.finder.probe_urls.validate_cds_url") as validate:
            self.assertEqual(audit_active_html_seeds([school], rows), [])
        validate.assert_not_called()
        self.assertEqual(school["scrape_policy"], "active")
        self.assertEqual(
            school["discovery_seed_url"],
            "https://example.edu/new-common-data-set/",
        )

    def test_active_work_started_during_validation_blocks_demotion(self) -> None:
        school = {
            "id": "racing-school",
            "scrape_policy": "active",
            "discovery_seed_url": "https://example.edu/mission/",
        }
        rows = [
            {
                "school_id": school["id"],
                "status": "done",
                "last_outcome": "no_pdfs_found",
                "processed_at": "2026-09-10T00:00:00Z",
                "cds_url_hint": school["discovery_seed_url"],
            }
        ]
        with mock.patch(
            "tools.finder.probe_urls.validate_cds_url",
            return_value=(VALIDATION_INVALID, "http_404"),
        ):
            results = audit_active_html_seeds(
                [school],
                rows,
                active_recheck=lambda ids: set(ids),
            )
        self.assertFalse(results[0]["demoted"])
        self.assertEqual(results[0]["reason"], "active_work_started")
        self.assertEqual(school["scrape_policy"], "active")
        self.assertIn("discovery_seed_url", school)

    def test_nonterminal_or_transient_archive_result_is_not_audited(self) -> None:
        base = {
            "id": "example",
            "scrape_policy": "active",
            "discovery_seed_url": "https://example.edu/common-data-set/",
        }
        rows = [
            {
                "school_id": "example",
                "status": "processing",
                "last_outcome": "no_pdfs_found",
                "processed_at": "2026-09-11T00:00:00Z",
                "cds_url_hint": base["discovery_seed_url"],
            }
        ]
        with mock.patch("tools.finder.probe_urls.validate_cds_url") as validate:
            self.assertEqual(audit_active_html_seeds([dict(base)], rows), [])
            rows[0]["status"] = "failed_permanent"
            rows[0]["last_outcome"] = "transient"
            self.assertEqual(audit_active_html_seeds([dict(base)], rows), [])
        validate.assert_not_called()
        self.assertNotIn("transient", AUDITABLE_ARCHIVE_OUTCOMES)

    def test_direct_document_seeds_are_out_of_scope(self) -> None:
        school = {
            "id": "example",
            "scrape_policy": "active",
            "discovery_seed_url": "https://example.edu/CDS_2024.pdf",
        }
        rows = [
            {
                "school_id": "example",
                "status": "failed_permanent",
                "last_outcome": "wrong_content_type",
                "cds_url_hint": school["discovery_seed_url"],
            }
        ]
        with mock.patch("tools.finder.probe_urls.validate_cds_url") as validate:
            self.assertEqual(audit_active_html_seeds([school], rows), [])
        validate.assert_not_called()

    def test_newest_terminal_row_controls_audit_and_dry_run_preserves_seed(self) -> None:
        school = {
            "id": "example",
            "scrape_policy": "active",
            "discovery_seed_url": "https://example.edu/mission",
        }
        rows = [
            {
                "school_id": "example",
                "status": "done",
                "last_outcome": "no_pdfs_found",
                "processed_at": "2026-09-10T00:00:00Z",
                "cds_url_hint": school["discovery_seed_url"],
            },
            {
                "school_id": "example",
                "status": "done",
                "last_outcome": "transient",
                "processed_at": "2026-09-11T00:00:00Z",
                "cds_url_hint": school["discovery_seed_url"],
            },
        ]
        with mock.patch("tools.finder.probe_urls.validate_cds_url") as validate:
            self.assertEqual(audit_active_html_seeds([school], rows), [])
            validate.assert_not_called()

        rows[1]["last_outcome"] = "dead_url"
        with mock.patch(
            "tools.finder.probe_urls.validate_cds_url",
            return_value=(VALIDATION_INVALID, "http_404"),
        ):
            results = audit_active_html_seeds([school], rows, dry_run=True)
        self.assertTrue(results[0]["demoted"])
        self.assertEqual(school["scrape_policy"], "active")
        self.assertIn("discovery_seed_url", school)


class SeedReplaceTests(unittest.TestCase):
    def test_listing_replaces_pdf(self) -> None:
        self.assertTrue(
            should_replace_seed(
                "https://example.edu/cds-2023.pdf",
                "https://example.edu/ir/cds/",
            )
        )

    def test_pdf_does_not_replace_listing(self) -> None:
        self.assertFalse(
            should_replace_seed(
                "https://example.edu/ir/cds/",
                "https://example.edu/cds-2024.pdf",
            )
        )

    def test_pdf_does_not_replace_other_pdf(self) -> None:
        self.assertFalse(
            should_replace_seed(
                "https://example.edu/cds-2023.pdf",
                "https://example.edu/cds-2024.pdf",
            )
        )


class SkipAndDedupeTests(unittest.TestCase):
    def test_found_skips_until_reprobe(self) -> None:
        school = {"probe_state": {"last_result": "found", "last_probed_at": "2026-04-14T00:00:00Z"}}
        self.assertTrue(should_skip(school, 30))
        self.assertFalse(should_skip(school, 30, reprobe_found=True))

    def test_shared_parent_stays_skipped(self) -> None:
        school = {"probe_state": {"last_result": "shared_parent_seed"}}
        self.assertTrue(should_skip(school, 30))

    def test_dedupe_keeps_main_campus(self) -> None:
        url = "https://www.ohio.edu/instres/commondataset.pdf"
        schools = [
            {"id": "ohio-university-chillicothe-campus", "discovery_seed_url": url, "scrape_policy": "active"},
            {"id": "ohio-university-main-campus", "discovery_seed_url": url, "scrape_policy": "active"},
        ]
        cleared = dedupe_identical_seeds(schools)
        self.assertEqual(cleared, [("ohio-university-chillicothe-campus", "ohio-university-main-campus")])
        self.assertNotIn("discovery_seed_url", schools[0])
        self.assertEqual(schools[0]["probe_state"]["last_result"], "shared_parent_seed")
        self.assertEqual(schools[1]["discovery_seed_url"], url)


class CheckpointHelpersTests(unittest.TestCase):
    def test_save_yaml_helper_still_exists(self) -> None:
        self.assertTrue(callable(_save_yaml))

    def test_write_probe_summary_does_not_touch_schools_yaml(self) -> None:
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "summary.json"
            write_probe_summary(
                path,
                probed=12,
                found=3,
                replaced=2,
                budget_remaining=17,
                still_stuck=9,
            )
            payload = json.loads(path.read_text())
        self.assertEqual(payload["probed"], 12)
        self.assertEqual(payload["found"], 3)
        self.assertEqual(payload["replaced"], 2)
        self.assertEqual(payload["still_stuck"], 9)

    def test_save_yaml_writes_checkpoint(self) -> None:
        import tempfile
        from pathlib import Path
        from unittest import mock

        import tools.finder.probe_urls as probe_urls

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "schools.yaml"
            with mock.patch.object(probe_urls, "SCHOOLS_YAML", path):
                probe_urls._save_yaml({"schools": [{"id": "x", "name": "Xavier"}]})
            text = path.read_text()
        self.assertIn("id: x", text)
        self.assertIn("Xavier", text)


class SeedRepairTests(unittest.TestCase):
    def test_confirmed_contextual_false_positive_seeds_stay_demoted(self) -> None:
        schools = {
            school["id"]: school
            for school in yaml.safe_load(SCHOOLS_YAML.read_text())["schools"]
        }
        repaired_ids = {
            "baker-university",
            "cornell-college",
            "dalton-state-college",
            "dickinson-state-university",
            "eastern-new-mexico-university-main-campus",
            "johnson-and-wales-university-charlotte",
            "johnson-and-wales-university-providence",
            "naval-postgraduate-school",
            "pennsylvania-college-of-health-sciences",
            "university-of-valley-forge",
            "university-of-wisconsin-stevens-point",
            "west-virginia-state-university",
        }
        for school_id in repaired_ids:
            with self.subTest(school_id=school_id):
                school = schools[school_id]
                self.assertEqual(school["scrape_policy"], "unknown")
                self.assertNotIn("discovery_seed_url", school)


class IdentityActivateTests(unittest.TestCase):
    def test_missing_official_record_cannot_become_active(self) -> None:
        school = {
            "id": "the-continents-states-university",
            "ipeds_id": "492087",
            "scrape_policy": "unknown",
        }
        self.assertFalse(may_mark_active(school, {}))
        self.assertTrue(
            may_mark_active(
                {**school, "ipeds_id": "168148"},
                {"168148": {"official_name": "Tufts University"}},
            )
        )
        self.assertTrue(may_mark_active(school, None))

    def test_process_school_rejects_candidate_missing_from_identity_snapshot(
        self,
    ) -> None:
        school = {
            "id": "missing-school",
            "name": "Missing School",
            "domain": "missing.edu",
            "ipeds_id": "999999",
            "scrape_policy": "unknown",
        }
        args = SimpleNamespace(
            search_only=False,
            rps=1,
            school_budget_sec=1,
            bing_fallback=False,
            brave_fallback=False,
            google_fallback=False,
            dry_run=False,
        )
        with mock.patch(
            "tools.finder.probe_urls.probe_school",
            return_value=("https://missing.edu/common-data-set/", 1),
        ):
            result = process_school(school, args, {"official_records": {}})
        self.assertIsNone(result["url"])
        self.assertEqual(school["scrape_policy"], "unknown")
        self.assertEqual(school["probe_state"]["last_result"], "not_found")
        self.assertNotIn("discovery_seed_url", school)


if __name__ == "__main__":
    unittest.main()
