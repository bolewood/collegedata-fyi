"""Tests for replaying finder probe logs onto schools.yaml."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from tools.finder.apply_probe_log import (
    apply_hit,
    apply_logs,
    parse_probe_log,
    write_school_updates,
)
from tools.finder.merge_schools_yaml import merge_school_lists


SAMPLE_LOG = """
Probing 3 schools with 4 workers (rps=1.0 per worker)
[    1/3] Albion College (albion.edu) ... [brave] FOUND: https://www.albion.edu/offices/registrar/institutional-data/
[    2/3] Elms College (elms.edu) ... [brave] FOUND: https://search.elms.edu/=327/krespectf/stanford+common+data+set.pdf
[    3/3] Agora University (agora.edu) ... not found
"""

YAML_FIXTURE = """\
schools:
- id: albion-college
  name: Albion College
  domain: albion.edu
  scrape_policy: active
  probe_state:
    last_probed_at: '2026-04-14T13:16:34Z'
    last_result: found
    last_method: brave
  discovery_seed_url: https://www.albion.edu/wp-content/uploads/cds-2023.pdf
- id: elms-college
  name: Elms College
  domain: elms.edu
  scrape_policy: active
  probe_state:
    last_probed_at: '2026-04-14T13:16:34Z'
    last_result: found
    last_method: brave
  discovery_seed_url: https://www.elms.edu/old.pdf
- id: agora-university
  name: Agora University
  domain: agora.edu
  scrape_policy: unknown
  probe_state:
    last_probed_at: '2026-04-14T13:16:34Z'
    last_result: not_found
    last_method: brave
"""


class ParseLogTests(unittest.TestCase):
    def test_parses_found_junk_and_miss(self) -> None:
        hits = parse_probe_log(SAMPLE_LOG)
        self.assertEqual(len(hits), 3)
        self.assertEqual(hits[0].url, "https://www.albion.edu/offices/registrar/institutional-data/")
        self.assertTrue(hits[1].found)
        self.assertFalse(hits[2].found)


class ApplyHitTests(unittest.TestCase):
    def test_listing_replaces_pdf(self) -> None:
        school = {
            "id": "albion-college",
            "discovery_seed_url": "https://www.albion.edu/old.pdf",
            "scrape_policy": "active",
        }
        hit = parse_probe_log(SAMPLE_LOG)[0]
        self.assertEqual(apply_hit(school, hit, "2026-08-21T22:51:00Z"), "replaced")
        self.assertEqual(
            school["discovery_seed_url"],
            "https://www.albion.edu/offices/registrar/institutional-data/",
        )

    def test_search_junk_is_skipped(self) -> None:
        school = {
            "id": "elms-college",
            "domain": "elms.edu",
            "discovery_seed_url": "https://www.elms.edu/old.pdf",
        }
        hit = parse_probe_log(SAMPLE_LOG)[1]
        self.assertEqual(apply_hit(school, hit, "2026-08-21T22:51:00Z"), "skipped_junk")
        self.assertEqual(school["discovery_seed_url"], "https://www.elms.edu/old.pdf")

    def test_paginated_blog_slug_is_skipped_junk(self) -> None:
        school = {
            "id": "the-continents-states-university",
            "domain": "continents.us",
            "ipeds_id": "492087",
            "scrape_policy": "unknown",
        }
        hit = parse_probe_log(
            "[    1/1] The Continents States University (continents.us) ... "
            "[brave] FOUND: https://www.continents.us/does-harvard-accept-2-9-gpa/5/\n"
        )[0]
        self.assertEqual(apply_hit(school, hit, "2026-09-02T17:59:07Z"), "skipped_junk")
        self.assertNotIn("discovery_seed_url", school)
        self.assertEqual(school["scrape_policy"], "unknown")

    def test_missing_official_record_does_not_flip_active(self) -> None:
        school = {
            "id": "the-continents-states-university",
            "domain": "continents.us",
            "ipeds_id": "492087",
            "scrape_policy": "unknown",
        }
        hit = parse_probe_log(
            "[    1/1] The Continents States University (continents.us) ... "
            "[brave] FOUND: https://www.continents.us/institutional-research/common-data-set/\n"
        )[0]
        self.assertEqual(
            apply_hit(school, hit, "2026-09-02T17:59:07Z", official_records={}),
            "replaced",
        )
        self.assertEqual(school["scrape_policy"], "unknown")
        self.assertTrue(school["discovery_seed_url"].endswith("common-data-set/"))


class WriteYamlTests(unittest.TestCase):
    def test_rewrites_seed_policy_and_probe_state(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "schools.yaml"
            path.write_text(YAML_FIXTURE)
            log_path = Path(tmp) / "probe.log"
            log_path.write_text(SAMPLE_LOG)
            counts = apply_logs(
                path,
                [log_path],
                probed_at="2026-08-21T22:51:00Z",
            )
            text = path.read_text()
        self.assertEqual(counts["replaced"], 1)
        self.assertEqual(counts["skipped_junk"], 1)
        self.assertEqual(counts["not_found"], 1)
        self.assertIn(
            "https://www.albion.edu/offices/registrar/institutional-data/",
            text,
        )
        self.assertIn("https://www.elms.edu/old.pdf", text)
        self.assertIn("last_probed_at: '2026-08-21T22:51:00Z'", text)
        self.assertIn("scrape_policy: unknown", text)

    def test_explicit_seed_deletion_removes_existing_yaml_line(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "schools.yaml"
            path.write_text(YAML_FIXTURE)
            schools = [
                {
                    "id": "albion-college",
                    "name": "Albion College",
                    "domain": "albion.edu",
                    "scrape_policy": "unknown",
                    "probe_state": {
                        "last_probed_at": "2026-09-12T00:00:00Z",
                        "last_result": "not_found",
                        "last_method": "active_html_audit",
                    },
                }
            ]
            write_school_updates(path, schools, {"albion-college"})
            text = path.read_text()
        self.assertNotIn("https://www.albion.edu/wp-content/uploads/cds-2023.pdf", text)
        self.assertNotIn("discovery_seed_url:", text.split("- id: elms-college")[0])
        self.assertIn("scrape_policy: unknown", text)
        self.assertIn("last_method: active_html_audit", text)


class MergeListsTests(unittest.TestCase):
    def test_overlays_only_schools_the_probe_changed(self) -> None:
        base = [
            {"id": "a", "discovery_seed_url": "https://a.edu/old.pdf", "scrape_policy": "active"},
            {"id": "b", "discovery_seed_url": "https://b.edu/cds/", "scrape_policy": "active"},
        ]
        main = [
            {"id": "a", "discovery_seed_url": "https://a.edu/old.pdf", "scrape_policy": "active", "notes": "keep"},
            {"id": "b", "discovery_seed_url": "https://b.edu/iea/", "scrape_policy": "active"},
        ]
        probed = [
            {"id": "a", "discovery_seed_url": "https://a.edu/ir/cds/", "scrape_policy": "active"},
            {"id": "b", "discovery_seed_url": "https://b.edu/cds/", "scrape_policy": "active"},
        ]
        merged, changed = merge_school_lists(base, main, probed)
        self.assertEqual(changed, ["a"])
        self.assertEqual(merged[0]["discovery_seed_url"], "https://a.edu/ir/cds/")
        self.assertEqual(merged[0]["notes"], "keep")
        self.assertEqual(merged[1]["discovery_seed_url"], "https://b.edu/iea/")

    def test_probe_state_only_does_not_revert_main_listing(self) -> None:
        base = [
            {
                "id": "ohio-university-main-campus",
                "discovery_seed_url": "https://www.ohio.edu/instres/commondataset.pdf",
                "scrape_policy": "active",
                "probe_state": {"last_result": "found", "last_probed_at": "2026-04-14T00:00:00Z"},
            }
        ]
        main = [
            {
                "id": "ohio-university-main-campus",
                "discovery_seed_url": "https://www.ohio.edu/iea/university-data",
                "scrape_policy": "active",
                "probe_state": {"last_result": "found", "last_probed_at": "2026-04-14T00:00:00Z"},
            }
        ]
        probed = [
            {
                "id": "ohio-university-main-campus",
                "discovery_seed_url": "https://www.ohio.edu/instres/commondataset.pdf",
                "scrape_policy": "active",
                "probe_state": {
                    "last_result": "not_found",
                    "last_probed_at": "2026-09-02T14:18:00Z",
                    "last_method": "brave",
                },
            }
        ]
        merged, changed = merge_school_lists(base, main, probed)
        self.assertEqual(changed, ["ohio-university-main-campus"])
        self.assertEqual(
            merged[0]["discovery_seed_url"],
            "https://www.ohio.edu/iea/university-data",
        )
        self.assertEqual(merged[0]["probe_state"]["last_result"], "not_found")
        self.assertEqual(merged[0]["probe_state"]["last_probed_at"], "2026-09-02T14:18:00Z")

    def test_probe_seed_deletion_wins_over_current_main(self) -> None:
        base = [
            {
                "id": "bad-seed",
                "discovery_seed_url": "https://example.edu/mission",
                "cds_url_hint": "https://example.edu/legacy-mission",
                "scrape_policy": "active",
            }
        ]
        main = [
            {
                "id": "bad-seed",
                "discovery_seed_url": "https://example.edu/mission",
                "cds_url_hint": "https://example.edu/legacy-mission",
                "scrape_policy": "active",
                "notes": "preserve me",
            }
        ]
        probed = [
            {
                "id": "bad-seed",
                "scrape_policy": "unknown",
                "probe_state": {
                    "last_result": "not_found",
                    "last_probed_at": "2026-09-12T00:00:00Z",
                    "last_method": "active_html_audit",
                },
            }
        ]
        merged, changed = merge_school_lists(base, main, probed)
        self.assertEqual(changed, ["bad-seed"])
        self.assertNotIn("discovery_seed_url", merged[0])
        self.assertNotIn("cds_url_hint", merged[0])
        self.assertEqual(merged[0]["scrape_policy"], "unknown")
        self.assertEqual(merged[0]["notes"], "preserve me")


if __name__ == "__main__":
    unittest.main()
