"""Pure unit tests for the scheduled Playwright archive worker.

No Playwright, no network. These cover target merge, landing resolution,
and year selection so CI can lock the worker without Chromium.
"""

from __future__ import annotations

import json
import os
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from tools.finder.headless_archive import (
    ArchiveCandidate,
    RunSummary,
    SchoolTarget,
    archive_school,
    exit_code_for,
    fetch_known_years,
    assert_fetch_has_no_service_role,
    build_targets,
    canonicalize_url,
    commit_fetched_files,
    crawl_candidates,
    is_waf_captcha_bytes,
    make_fetch_store,
    merge_candidates,
    merge_waf_school_entries,
    resolve_landing,
    run,
    select_candidates,
    should_crawl_landing,
    strip_challenge_query,
    write_plan_json,
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

    def test_nd_and_williams_starting_urls_are_listings(self) -> None:
        nd = STARTING_URLS["university-of-notre-dame"]
        self.assertIn("iris.nd.edu", nd)
        self.assertFalse(nd.lower().endswith(".pdf"))
        williams = STARTING_URLS["williams-college"]
        self.assertIn("common-data-set", williams)
        self.assertFalse(williams.lower().endswith(".pdf"))

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
        self.assertTrue(
            should_crawl_landing(
                "https://data.colorado.edu/reports/common-data-set"
            )
        )
        self.assertFalse(
            should_crawl_landing(
                "https://colorado.sharepoint.com/sites/IR/Shared%20Documents"
            )
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

    def test_only_comma_list_preserves_order(self) -> None:
        targets = build_targets(
            {
                "nyu": {"school_name": "NYU", "landing_url": "https://www.nyu.edu/factbook.html", "urls": [{"url": "https://e.edu/n.pdf", "year": "2025-26"}]},
                "caltech": {"school_name": "Caltech", "landing_url": "https://finance.caltech.edu/Resources/cds", "urls": []},
            },
            extra_school_ids=[],
            seed_by_id={},
            starting_urls={},
            only="caltech,new-york-university",
            max_schools=20,
        )
        self.assertEqual([t.school_id for t in targets], ["caltech", "nyu"])


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

    def test_fetch_store_counts_as_fetched(self) -> None:
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
        with TemporaryDirectory() as tmp:
            files_acc: list[dict] = []
            store = make_fetch_store(Path(tmp), files_acc)
            collect = MagicMock(return_value=SimpleNamespace(status="ok", anchors=[]))
            download = MagicMock(
                return_value=(b"%PDF-1.4 fake", "application/pdf", 200,
                              "https://www.nyu.edu/cds-2025-2026.pdf"),
            )
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
                upload_fn=store,
                detect_ext_fn=lambda *_args: "pdf",
            )
            self.assertEqual(row["fetched"], 1)
            self.assertEqual(row["inserted"], 0)
            self.assertEqual(len(files_acc), 1)
            self.assertTrue((Path(tmp) / files_acc[0]["relpath"]).is_file())


class PhaseSplitTests(unittest.TestCase):
    def test_fetch_refuses_service_role_env(self) -> None:
        with patch.dict(os.environ, {"SUPABASE_SERVICE_ROLE_KEY": "nope"}):
            with self.assertRaises(SystemExit) as ctx:
                assert_fetch_has_no_service_role()
        self.assertIn("must not receive", str(ctx.exception))

    def test_require_only_rejects_empty_targeting(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            waf = root / "waf.yaml"
            waf.write_text("schools: {}\n", encoding="utf-8")
            schools = root / "schools.yaml"
            schools.write_text("schools: []\n", encoding="utf-8")
            with self.assertRaises(SystemExit) as ctx:
                run(
                    waf_path=waf,
                    schools_yaml=schools,
                    env_path=root / "no.env",
                    only=None,
                    dry_run=True,
                    skip_known=True,
                    include_queue=False,
                    max_schools=20,
                    max_new=2,
                    min_year="2024-25",
                    json_out=None,
                    phase="fetch",
                    require_only=True,
                    artifact_dir=root / "artifact",
                    collect_fn=MagicMock(),
                    download_fn=MagicMock(),
                    browser_factory=MagicMock(),
                    upload_fn=None,
                )
        self.assertIn("require --only", str(ctx.exception))

    def test_over_cap_only_list_exits(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            waf = root / "waf.yaml"
            waf.write_text("schools: {}\n", encoding="utf-8")
            schools = root / "schools.yaml"
            schools.write_text("schools: []\n", encoding="utf-8")
            with self.assertRaises(SystemExit) as ctx:
                run(
                    waf_path=waf,
                    schools_yaml=schools,
                    env_path=root / "no.env",
                    only="a,b,c,d,e,f",
                    dry_run=True,
                    skip_known=True,
                    include_queue=False,
                    max_schools=20,
                    max_new=2,
                    min_year="2024-25",
                    json_out=None,
                    phase="fetch",
                    require_only=True,
                    artifact_dir=root / "artifact",
                    collect_fn=MagicMock(),
                    download_fn=MagicMock(),
                    browser_factory=MagicMock(),
                    upload_fn=None,
                )
        self.assertIn("cap is 5", str(ctx.exception))

    def test_plan_json_has_no_secret_keys(self) -> None:
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "plan.json"
            write_plan_json(path, known={"nyu": {"2025-26"}}, queue_school_ids=["nyu"])
            payload = json.loads(path.read_text())
        self.assertEqual(set(payload), {"known_years", "queue_school_ids"})
        blob = json.dumps(payload).lower()
        self.assertNotIn("service_role", blob)
        self.assertNotIn("supabase", blob)

    def test_commit_uploads_artifact_bytes(self) -> None:
        with TemporaryDirectory() as tmp:
            artifact = Path(tmp)
            files_acc: list[dict] = []
            store = make_fetch_store(artifact, files_acc)
            body = b"%PDF-1.4 test-bytes"
            store(
                "nyu", "2025-26", body, "pdf", "application/pdf",
                "https://example.edu/cds.pdf", "NYU",
            )
            (artifact / "manifest.json").write_text(json.dumps({
                "schools": [{"school_id": "nyu", "failed": 0}],
                "files": files_acc,
                "schools_attempted": 1,
                "crawled": 0,
                "discovered": 0,
                "skipped_known": 0,
                "failed": 0,
            }))
            seen: list[tuple] = []

            def upload(school_id, year, data, ext, content_type, source_url, school_name):
                seen.append((school_id, year, data, ext, source_url, school_name))
                return {"action": "inserted"}

            summary = commit_fetched_files(artifact, upload)
            self.assertEqual(summary.inserted, 1)
            self.assertEqual(summary.phase, "commit")
            self.assertEqual(seen[0][0], "nyu")
            self.assertEqual(seen[0][2], body)

    def test_commit_rejects_sha_mismatch(self) -> None:
        with TemporaryDirectory() as tmp:
            artifact = Path(tmp)
            rel = Path("files/nyu/2025-26/deadbeef.pdf")
            dest = artifact / rel
            dest.parent.mkdir(parents=True)
            dest.write_bytes(b"%PDF-1.4 other")
            (artifact / "manifest.json").write_text(json.dumps({
                "files": [{
                    "school_id": "nyu",
                    "school_name": "NYU",
                    "year": "2025-26",
                    "source_url": "https://example.edu/cds.pdf",
                    "ext": "pdf",
                    "content_type": "application/pdf",
                    "sha256": "0" * 64,
                    "relpath": rel.as_posix(),
                }],
            }))
            with self.assertRaises(SystemExit) as ctx:
                commit_fetched_files(artifact, MagicMock())
            self.assertIn("sha256 mismatch", str(ctx.exception))

    def test_run_fetch_does_not_open_supabase(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            waf = root / "waf.yaml"
            waf.write_text(
                "schools:\n  nyu:\n    school_name: NYU\n"
                "    landing_url: https://www.nyu.edu/factbook.html\n"
                "    urls:\n      - url: https://www.nyu.edu/cds-2025-2026.pdf\n"
                "        year: '2025-26'\n",
                encoding="utf-8",
            )
            schools = root / "schools.yaml"
            schools.write_text("schools: []\n", encoding="utf-8")
            artifact = root / "artifact"
            collect = MagicMock(return_value=SimpleNamespace(status="ok", anchors=[]))
            download = MagicMock(
                return_value=(b"%PDF-1.4 fake", "application/pdf", 200,
                              "https://www.nyu.edu/cds-2025-2026.pdf"),
            )

            def factory(callback):
                return callback(object(), object())

            with patch.dict(os.environ, {"SUPABASE_SERVICE_ROLE_KEY": ""}, clear=False):
                os.environ.pop("SUPABASE_SERVICE_ROLE_KEY", None)
                summary = run(
                    waf_path=waf,
                    schools_yaml=schools,
                    env_path=root / "missing.env",
                    only="nyu",
                    dry_run=False,
                    skip_known=True,
                    include_queue=False,
                    max_schools=20,
                    max_new=2,
                    min_year="2024-25",
                    json_out=None,
                    phase="fetch",
                    artifact_dir=artifact,
                    collect_fn=collect,
                    download_fn=download,
                    browser_factory=factory,
                    upload_fn=None,
                )
            self.assertEqual(summary.fetched, 1)
            self.assertEqual(summary.phase, "fetch")
            self.assertTrue((artifact / "manifest.json").is_file())
            manifest = json.loads((artifact / "manifest.json").read_text())
            self.assertEqual(len(manifest["files"]), 1)


class _FakeQuery:
    """Chainable stand-in for a supabase-py query that records its contract."""

    def __init__(self, rows, log, count_override=None, drop_count=False):
        self.rows = rows
        self.log = log
        self.count_override = count_override
        self.drop_count = drop_count
        self.lo, self.hi = 0, 10**9
        self.filters = []

    def select(self, cols, **kw):
        self.log["select"] = cols
        self.log["count"] = kw.get("count")
        return self

    def in_(self, col, ids):
        self.filters.append(lambda r: r.get(col) in set(ids))
        return self

    def is_(self, col, val):
        self.log.setdefault("is_", []).append((col, val))
        self.filters.append(lambda r: r.get(col) is None)
        return self

    def eq(self, col, val):
        self.log.setdefault("eq", []).append((col, val))
        self.filters.append(lambda r: r.get(col) == val)
        return self

    def order(self, col):
        self.log["order"] = col
        return self

    def range(self, lo, hi):
        self.lo, self.hi = lo, hi
        return self

    def execute(self):
        matched = [r for r in self.rows if all(f(r) for f in self.filters)]
        total = len(matched) if self.count_override is None else self.count_override
        return SimpleNamespace(
            data=matched[self.lo:self.hi + 1],
            count=None if self.drop_count else total,
        )


class _FakeSb:
    def __init__(self, rows, **kw):
        self.rows, self.kw, self.log = rows, kw, {}

    def table(self, name):
        self.log["table"] = name
        return _FakeQuery(self.rows, self.log, **self.kw)


def _doc(i, school="nyu", cds="2023-24", detected=None, status="published",
         removed=None):
    return {"id": f"{i:05d}", "school_id": school, "cds_year": cds,
            "detected_year": detected, "participation_status": status,
            "removed_at": removed}


class KnownYearsTests(unittest.TestCase):
    def test_query_contract_and_paging_past_one_thousand_rows(self) -> None:
        rows = [_doc(i) for i in range(1500)]
        rows.append(_doc(9000, cds="unknown", detected="2025-26"))
        rows.append(_doc(9001, cds="unknown"))
        sb = _FakeSb(rows)
        report: dict[str, int] = {}
        known = fetch_known_years(sb, ["nyu", "mit"], report=report)
        self.assertEqual(known["nyu"], {"2023-24", "2025-26"})
        self.assertEqual(known["mit"], set())
        self.assertEqual(report["years_unparseable_known"], 1)
        self.assertEqual(sb.log["table"], "cds_documents")
        self.assertIn("participation_status", sb.log["select"])
        self.assertIn("detected_year", sb.log["select"])
        self.assertEqual(sb.log["count"], "exact")
        self.assertEqual(sb.log["order"], "id")
        self.assertIn(("removed_at", "null"), sb.log["is_"])
        self.assertIn(("participation_status", "published"), sb.log["eq"])

    def test_canonical_year_is_detected_year_not_both(self) -> None:
        sb = _FakeSb([_doc(1, cds="2025-26", detected="2023-24")])
        known = fetch_known_years(sb, ["nyu"])
        self.assertEqual(known["nyu"], {"2023-24"})

    def test_removed_and_unpublished_documents_do_not_hide_a_year(self) -> None:
        rows = [
            _doc(1, cds="2025-26", removed="2026-11-01T00:00:00Z"),
            _doc(2, cds="2024-25", status="verified_absent"),
        ]
        self.assertEqual(fetch_known_years(_FakeSb(rows), ["nyu"])["nyu"], set())

    def test_short_read_raises_instead_of_returning_fewer_years(self) -> None:
        with self.assertRaises(RuntimeError):
            fetch_known_years(_FakeSb([_doc(1)], count_override=5), ["nyu"])

    def test_missing_count_raises(self) -> None:
        with self.assertRaises(RuntimeError):
            fetch_known_years(_FakeSb([_doc(1)], drop_count=True), ["nyu"])

    def test_run_summary_carries_unparseable_known(self) -> None:
        s = RunSummary()
        s.years_unparseable_known = 4
        self.assertEqual(s.as_heartbeat()["years_unparseable_known"], 4)


class DroppedWorkCountTests(unittest.TestCase):
    def test_select_candidates_counts_capped_below_min_and_unparseable(self) -> None:
        cands = [
            ArchiveCandidate("https://e.edu/1.pdf", "2025-26", "yaml"),
            ArchiveCandidate("https://e.edu/2.pdf", "2024-25", "yaml"),
            ArchiveCandidate("https://e.edu/3.pdf", "2023-24", "yaml"),
            ArchiveCandidate("https://e.edu/4.pdf", "2022-23", "yaml"),
            ArchiveCandidate("https://e.edu/5.pdf", "fall-2025", "yaml"),
        ]
        counts: dict[str, int] = {}
        selected, _ = select_candidates(
            cands, set(), skip_known=True, max_new=1, min_year="2024-25",
            counts=counts,
        )
        self.assertEqual([c.year for c in selected], ["2025-26"])
        self.assertEqual(counts["years_capped"], 1)
        # The two counts partition: the malformed year is not also "below min".
        self.assertEqual(counts["years_below_min"], 2)
        self.assertEqual(counts["years_unparseable"], 1)

    def test_candidate_with_no_year_is_counted_unparseable_and_kept(self) -> None:
        counts: dict[str, int] = {}
        selected, _ = select_candidates(
            [ArchiveCandidate("https://e.edu/x.pdf", None, "yaml")],
            set(), skip_known=True, max_new=5, min_year="2024-25", counts=counts,
        )
        self.assertEqual(len(selected), 1)
        self.assertEqual(counts["years_unparseable"], 1)
        self.assertNotIn("years_below_min", counts)

    def test_build_targets_counts_schools_over_the_cap(self) -> None:
        entries = {
            sid: {"school_name": sid, "landing_url": f"https://{sid}.edu/cds", "urls": []}
            for sid in ("nyu", "caltech", "emory")
        }
        counts: dict[str, int] = {}
        targets = build_targets(entries, [], {}, {}, None, 2, counts=counts)
        self.assertEqual(len(targets), 2)
        self.assertEqual(counts["schools_capped"], 1)


class ExitCodeTests(unittest.TestCase):
    def _summary(self, rows, targeted=None, **kw):
        s = RunSummary(**kw)
        s.schools = rows
        s.schools_attempted = len(rows)
        s.schools_targeted = len(rows) if targeted is None else targeted
        return s

    def test_targets_but_nothing_attempted_is_nonzero(self) -> None:
        self.assertEqual(exit_code_for(self._summary([], targeted=3)), 1)

    def test_every_school_failed_is_nonzero(self) -> None:
        rows = [
            {"failed": 2, "inserted": 0, "unchanged": 0, "fetched": 0},
            {"failed": 0, "crawl_status": "nav_error", "selected": 0},
        ]
        self.assertEqual(exit_code_for(self._summary(rows)), 1)

    def test_one_success_keeps_per_url_misses_non_fatal(self) -> None:
        rows = [
            {"failed": 2, "inserted": 0, "unchanged": 0, "fetched": 0},
            {"failed": 0, "inserted": 1, "unchanged": 0, "fetched": 0},
        ]
        self.assertEqual(exit_code_for(self._summary(rows)), 0)

    def test_all_known_years_is_not_a_failure(self) -> None:
        rows = [{"failed": 0, "crawl_status": "ok", "selected": 0}]
        self.assertEqual(exit_code_for(self._summary(rows)), 0)

    def test_dead_landing_with_known_years_is_not_a_failure(self) -> None:
        rows = [{"failed": 0, "crawl_status": "nav_error", "selected": 0,
                 "skipped_known": 1}]
        self.assertEqual(exit_code_for(self._summary(rows)), 0)

    def test_commit_with_work_but_nothing_committed_is_nonzero(self) -> None:
        s = RunSummary(phase="commit")
        s.files = [{"relpath": "a.pdf"}]
        self.assertEqual(exit_code_for(s), 1)
        s = RunSummary(phase="commit")
        s.failed = 2
        self.assertEqual(exit_code_for(s), 1)

    def test_commit_that_committed_something_or_had_no_work_is_zero(self) -> None:
        s = RunSummary(phase="commit")
        s.files = [{"relpath": "a.pdf"}, {"relpath": "b.pdf"}]
        s.inserted, s.failed = 1, 1
        self.assertEqual(exit_code_for(s), 0)
        self.assertEqual(exit_code_for(RunSummary(phase="commit")), 0)

    def test_main_returns_the_nonzero_code(self) -> None:
        from tools.finder import headless_archive

        dead = self._summary([], targeted=3)
        with TemporaryDirectory() as tmp:
            waf = Path(tmp) / "waf.yaml"
            waf.write_text("schools: {}\n", encoding="utf-8")
            with patch.object(headless_archive, "run", return_value=dead):
                self.assertEqual(headless_archive.main(["--input", str(waf)]), 1)

    def test_dry_run_and_no_targets_stay_zero(self) -> None:
        rows = [{"failed": 1, "inserted": 0, "unchanged": 0, "fetched": 0}]
        self.assertEqual(exit_code_for(self._summary(rows, dry_run=True)), 0)
        self.assertEqual(exit_code_for(self._summary([], targeted=0)), 0)


if __name__ == "__main__":
    unittest.main()
