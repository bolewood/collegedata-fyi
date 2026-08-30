"""WAF worklist keys must be canonical schools.yaml ids."""

from __future__ import annotations

import unittest
from pathlib import Path

import yaml

from tools.finder.waf_school_ids import (
    WAF_SCHOOL_ID_ALIASES,
    canonical_waf_school_id,
    parse_only_ids,
    select_waf_schools,
    validate_only_ids,
)

ROOT = Path(__file__).resolve().parents[2]


def _school_ids() -> set[str]:
    doc = yaml.safe_load((ROOT / "tools/finder/schools.yaml").read_text())
    return {row["id"] for row in doc["schools"] if "id" in row}


def _waf_schools() -> dict:
    doc = yaml.safe_load((ROOT / "tools/finder/waf_blocked_urls.yaml").read_text())
    return doc.get("schools") or {}


class WafBlockedUrlTests(unittest.TestCase):
    def test_yaml_keys_are_canonical_or_known_aliases(self) -> None:
        known = _school_ids()
        for raw_sid in _waf_schools():
            canonical = canonical_waf_school_id(raw_sid)
            self.assertIn(
                canonical,
                known,
                f"waf_blocked_urls.yaml key {raw_sid!r} maps to {canonical!r}, "
                "which is not a schools.yaml id",
            )

    def test_nyu_entry_uses_canonical_id_and_includes_2025_26(self) -> None:
        schools = _waf_schools()
        self.assertIn("nyu", schools)
        self.assertNotIn("new-york-university", schools)
        years = {
            item.get("year")
            for item in schools["nyu"].get("urls", [])
            if isinstance(item, dict)
        }
        self.assertIn("2025-26", years)

    def test_alias_remap(self) -> None:
        self.assertEqual(canonical_waf_school_id("nyu"), "nyu")
        self.assertEqual(canonical_waf_school_id("new-york-university"), "nyu")
        self.assertEqual(
            WAF_SCHOOL_ID_ALIASES["johns-hopkins-university"], "johns-hopkins"
        )

    def test_select_accepts_canonical_or_alias(self) -> None:
        schools = {
            "nyu": {"urls": [{"year": "2025-26"}]},
            "johns-hopkins-university": {"urls": [{"year": "2025-26"}]},
        }
        self.assertEqual(list(select_waf_schools(schools, "nyu")), ["nyu"])
        self.assertEqual(
            list(select_waf_schools(schools, "new-york-university")), ["nyu"]
        )
        self.assertEqual(
            list(select_waf_schools(schools, "johns-hopkins")),
            ["johns-hopkins-university"],
        )
        self.assertEqual(select_waf_schools(schools, "missing"), {})

    def test_parse_only_comma_list_and_aliases(self) -> None:
        self.assertEqual(parse_only_ids("nyu"), ["nyu"])
        self.assertEqual(
            parse_only_ids("new-york-university,caltech,nyu"),
            ["nyu", "caltech"],
        )
        self.assertEqual(parse_only_ids(" , , "), [])
        self.assertEqual(parse_only_ids(None), [])

    def test_validate_only_rejects_empty_and_over_cap(self) -> None:
        self.assertEqual(validate_only_ids(["nyu"], require=True, cap=5), ["nyu"])
        with self.assertRaises(SystemExit):
            validate_only_ids([], require=True, cap=5)
        with self.assertRaises(SystemExit):
            validate_only_ids(["a", "b", "c", "d", "e", "f"], cap=5)


if __name__ == "__main__":
    unittest.main()
