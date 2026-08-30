"""Pure unit tests for the scheduled Playwright archive worker.

No Playwright, no network. These cover target merge, landing resolution,
and year selection so CI can lock the worker without Chromium.
"""

from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock

from tools.finder.headless_archive import (
    ArchiveCandidate,
    SchoolTarget,
    archive_school,
    build_targets,
    canonicalize_url,
    crawl_candidates,
    is_waf_captcha_bytes,
    merge_candidates,
    merge_waf_school_entries,
    resolve_landing,
    select_candidates,
    should_crawl_landing,
    strip_challenge_query,
    yaml_candidates,
)
from tools.finder.playwright_collect import STARTING_URLS, AnchorResult


class UrlHygieneTests(unittest.TestCase):
    def test_strips_expired_challenge_tokens(self) -> None:
        url = (
            "https://www.nyu.edu/employees/resources-and-services/"
            "administrative-services/institutional-research/"
            "self-service-reporting-resources/factbook.html"
            "?challenge=d06e90d7-4d8f-4b88-9d8c-10b73beb60f1"
        )
        cleaned = strip_challenge_query(url)
        self.assertNotIn("challenge=", cleaned)
        self.assertTrue(cleaned.endswith("factbook.html"))

    def test_starting_urls_nyu_has_no_challenge_token(self) -> None:
        self.assertIn("nyu", STARTING_URLS)
        self.assertIn("new-york-university", STARTING_URLS)
        for key in ("nyu", "new-york-university"):
            self.assertNotIn("challenge=", STARTING_URLS[key], key)
            self.assertTrue(STARTING_URLS[key].endswith("factbook.html"))

    def test_canonicalize_drops_fragment(self) -> None:
        self.assertEqual(
            canonicalize_url("https://example.edu/cds.pdf#page=2"),
            "https://example.edu/cds.pdf",
        )

    def test_detects_aws_waf_captcha_html(self) -> None:
        html = (
            b"<!DOCTYPE html><title>Human Verification</title>"
            b"<script src='https://captcha.awswaf.com/challenge.js'></script>"
            b"<div id='amzn-captcha-verify-button'>Begin</div>"
        )
        self.assertTrue(is_waf_captcha_bytes(html, "text/html"))
        self.assertFalse(is_waf_captcha_bytes(b"%PDF-1.4 school cds", "application/pdf"))


class WafMergeTests(unittest.TestCase):
    def test_collapses_alias_keys_and_unions_urls(self) -> None:
        merged = merge_waf_school_entries({
            "new-york-university": {
                "school_name": "NYU",
                "landing_url": None,
                "urls": [{"url": "https://example.edu/a.pdf", "year": "2024-25"}],
            },
            "nyu": {
                "school_name": "New York University",
                "landing_url": "https://www.nyu.edu/factbook.html",
                "urls": [
                    {"url": "https://example.edu/a.pdf", "year": "2024-25"},
                    {"url": "https://example.edu/b.pdf", "year": "2025-26"},
                ],
            },
        })
        self.assertEqual(list(merged), ["nyu"])
        self.assertEqual(
            merged["nyu"]["landing_url"],
            "https://www.nyu.edu/factbook.html",
        )
        years = {item["year"] for item in merged["nyu"]["urls"]}
        self.assertEqual(years, {"2024-25", "2025-26"})


class LandingTests(unittest.TestCase):
    def test_prefers_html_yaml_landing_over_pdf_seed(self) -> None:
        landing = resolve_landing(
            {"landing_url": "https://www.nyu.edu/factbook.html"},
            "nyu",
            {"nyu": "https://www.nyu.edu/cds-2020-21.pdf"},
            {},
        )
        self.assertEqual(landing, "https://www.nyu.edu/factbook.html")

    def test_uses_seed_when_yaml_landing_is_null(self) -> None:
        landing = resolve_landing(
            {"landing_url": None, "urls": []},
            "caltech",
            {"caltech": "https://finance.caltech.edu/Resources/cds"},
            {},
        )
        self.assertEqual(landing, "https://finance.caltech.edu/Resources/cds")

    def test_does_not_crawl_drive_or_missing_landings(self) -> None:
        self.assertFalse(should_crawl_landing(None))
        self.assertFalse(
            should_crawl_landing(
                "https://drive.google.com/drive/folders/abc"
            )
        )
        self.assertTrue(
            should_crawl_landing("https://www.nyu.edu/factbook.html")
        )


class CandidateTests(unittest.TestCase):
    def test_yaml_and_crawl_merge_discovers_new_year(self) -> None:
        entry = {
            "urls": [
                {
                    "url": "https://www.nyu.edu/cds-2024-2025.pdf",
                    "year": "2024-25",
                }
            ]
        }
        yaml_cands = yaml_candidates(entry)
        crawled = crawl_candidates([
            AnchorResult(
                url="https://www.nyu.edu/cds-2024-2025.pdf",
                text="CDS 2024-25",
                year="2024-25",
                is_document=True,
            ),
            AnchorResult(
                url="https://www.nyu.edu/content/dam/nyu/institutionalResearch/"
                    "documents/cds-2025-2026/CDS%202025-2026%20FINAL%20(no%20G).pdf",
                text="Common Data Set 2025-2026",
                year="2025-26",
                is_document=True,
            ),
            AnchorResult(
                url="https://www.nyu.edu/about.html",
                text="About NYU",
                year=None,
                is_document=False,
            ),
        ])
        merged = merge_candidates(yaml_cands, crawled)
        years = {c.year for c in merged}
        self.assertEqual(years, {"2024-25", "2025-26"})
        self.assertTrue(any(c.source == "crawl" and c.year == "2025-26" for c in merged))

    def test_select_skips_known_years_and_caps_newest(self) -> None:
        cands = [
            ArchiveCandidate("https://e.edu/a.pdf", "2023-24", "yaml"),
            ArchiveCandidate("https://e.edu/b.pdf", "2024-25", "yaml"),
            ArchiveCandidate("https://e.edu/c.pdf", "2025-26", "crawl"),
        ]
        selected, skipped = select_candidates(
            cands,
            {"2024-25"},
            skip_known=True,
            max_new=1,
            min_year="2024-25",
        )
        self.assertEqual(skipped, 1)
        self.assertEqual([c.year for c in selected], ["2025-26"])

    def test_min_year_drops_historical_drive_files(self) -> None:
        cands = [
            ArchiveCandidate("https://drive.google.com/uc?id=old", "2010-11", "yaml"),
            ArchiveCandidate("https://drive.google.com/uc?id=new", "2025-26", "yaml"),
        ]
        selected, skipped = select_candidates(
            cands, set(), skip_known=True, max_new=5, min_year="2024-25",
        )
        self.assertEqual(skipped, 0)
        self.assertEqual([c.year for c in selected], ["2025-26"])


class TargetBuildTests(unittest.TestCase):
    def test_only_alias_resolves_to_canonical(self) -> None:
        targets = build_targets(
            {"nyu": {"school_name": "NYU", "landing_url": "https://www.nyu.edu/factbook.html", "urls": [{"url": "https://e.edu/x.pdf", "year": "2025-26"}]}},
            extra_school_ids=["caltech"],
            seed_by_id={"caltech": "https://finance.caltech.edu/Resources/cds"},
            starting_urls={},
            only="new-york-university",
            max_schools=20,
        )
        self.assertEqual([t.school_id for t in targets], ["nyu"])
        self.assertIn("factbook.html", targets[0].landing_url or "")

    def test_queue_school_uses_seed_when_not_in_yaml(self) -> None:
        targets = build_targets(
            {},
            extra_school_ids=["emory"],
            seed_by_id={"emory": "https://provost.emory.edu/cds.html"},
            starting_urls={},
            only=None,
            max_schools=20,
        )
        self.assertEqual(len(targets), 1)
        self.assertEqual(targets[0].school_id, "emory")
        self.assertEqual(targets[0].landing_url, "https://provost.emory.edu/cds.html")


class ArchiveSchoolTests(unittest.TestCase):
    def test_dry_run_selects_crawled_year_without_upload(self) -> None:
        target = SchoolTarget(
            school_id="nyu",
            school_name="New York University",
            landing_url="https://www.nyu.edu/factbook.html",
            entry={"urls": [], "landing_url": "https://www.nyu.edu/factbook.html"},
        )
        collect = MagicMock(return_value=SimpleNamespace(
            status="ok",
            anchors=[
                AnchorResult(
                    url="https://www.nyu.edu/cds-2025-2026.pdf",
                    text="CDS 2025-26",
                    year="2025-26",
                    is_document=True,
                )
            ],
        ))
        download = MagicMock()
        upload = MagicMock()
        row = archive_school(
            target=target,
            known_years=set(),
            skip_known=True,
            max_new=2,
            min_year="2024-25",
            dry_run=True,
            page=object(),
            browser_ctx=object(),
            collect_fn=collect,
            download_fn=download,
            upload_fn=upload,
        )
        collect.assert_called_once()
        download.assert_not_called()
        upload.assert_not_called()
        self.assertEqual(row["discovered"], 1)
        self.assertEqual(row["actions"][0]["year"], "2025-26")
        self.assertEqual(row["actions"][0]["action"], "dry_run")

    def test_skips_crawl_for_drive_only_yaml(self) -> None:
        target = SchoolTarget(
            school_id="university-of-notre-dame",
            school_name="Notre Dame",
            landing_url=None,
            entry={
                "urls": [{
                    "url": "https://drive.google.com/uc?export=download&id=abc",
                    "year": "2025-26",
                }]
            },
        )
        collect = MagicMock()
        row = archive_school(
            target=target,
            known_years=set(),
            skip_known=True,
            max_new=2,
            min_year="2024-25",
            dry_run=True,
            page=object(),
            browser_ctx=object(),
            collect_fn=collect,
            download_fn=MagicMock(),
            upload_fn=MagicMock(),
        )
        collect.assert_not_called()
        self.assertEqual(row["crawl_status"], "skipped")
        self.assertEqual(row["selected"], 1)

    def test_upload_path_records_inserted(self) -> None:
        target = SchoolTarget(
            school_id="nyu",
            school_name="New York University",
            landing_url="https://www.nyu.edu/factbook.html",
            entry={
                "urls": [{
                    "url": "https://www.nyu.edu/cds-2025-2026.pdf",
                    "year": "2025-26",
                }],
                "landing_url": "https://www.nyu.edu/factbook.html",
            },
        )
        collect = MagicMock(return_value=SimpleNamespace(status="ok", anchors=[]))
        download = MagicMock(return_value=(b"%PDF-1.4 fake", "application/pdf", 200, "https://www.nyu.edu/cds-2025-2026.pdf"))
        upload = MagicMock(return_value={"action": "inserted", "document_id": "doc-1"})
        row = archive_school(
            target=target,
            known_years=set(),
            skip_known=True,
            max_new=2,
            min_year="2024-25",
            dry_run=False,
            page=object(),
            browser_ctx=object(),
            collect_fn=collect,
            download_fn=download,
            upload_fn=upload,
            detect_ext_fn=lambda *_args: "pdf",
        )
        download.assert_called_once()
        upload.assert_called_once()
        self.assertEqual(row["inserted"], 1)
        self.assertEqual(row["failed"], 0)

    def test_captcha_html_is_labeled_not_unknown_ext(self) -> None:
        target = SchoolTarget(
            school_id="nyu",
            school_name="New York University",
            landing_url="https://www.nyu.edu/factbook.html",
            entry={
                "urls": [{
                    "url": "https://www.nyu.edu/cds-2025-2026.pdf",
                    "year": "2025-26",
                }],
                "landing_url": "https://www.nyu.edu/factbook.html",
            },
        )
        html = (
            b"<!DOCTYPE html><title>Human Verification</title>"
            b"<script src='https://captcha.awswaf.com/x'></script>"
        )
        collect = MagicMock(return_value=SimpleNamespace(status="ok", anchors=[]))
        download = MagicMock(return_value=(html, "text/html; charset=UTF-8", 405, "https://www.nyu.edu/cds-2025-2026.pdf"))
        row = archive_school(
            target=target,
            known_years=set(),
            skip_known=True,
            max_new=2,
            min_year="2024-25",
            dry_run=False,
            page=SimpleNamespace(wait_for_function=MagicMock(side_effect=TimeoutError()), content=lambda: html.decode()),
            browser_ctx=object(),
            collect_fn=collect,
            download_fn=download,
            upload_fn=MagicMock(),
            detect_ext_fn=lambda *_args: None,
        )
        self.assertEqual(row["failed"], 1)
        self.assertEqual(row["actions"][0]["error"], "waf_captcha")


if __name__ == "__main__":
    unittest.main()
