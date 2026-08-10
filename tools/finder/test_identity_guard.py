"""Regression tests for the shared schools.yaml/IPEDS identity guard."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

import yaml

from tools.finder.identity_guard import (
    DEFAULT_SCHOOLS_YAML,
    DEFAULT_SNAPSHOT,
    audit_school_identities,
    build_identity_snapshot,
    domains_related,
    load_identity_snapshot,
    load_school_claims,
    main as identity_guard_main,
    normalize_domain,
    normalize_name,
    school_claims_from_entries,
    unique_school_claim_slug_map,
    validated_unique_school_claim_slug_map,
)


def claim(**overrides):
    value = {
        "school_id": "tufts",
        "ipeds_id": "168148",
        "claimed_name": "Tufts University",
        "claimed_domain": "tufts.edu",
        "scrape_policy": "active",
    }
    value.update(overrides)
    return value


def official(**overrides):
    value = {
        "ipeds_id": "168148",
        "official_name": "Tufts University",
        "official_domain": "tufts.edu",
        "official_state": "MA",
        "active": "1",
        "new_ipeds_id": "",
    }
    value.update(overrides)
    return value


class NormalizationTests(unittest.TestCase):
    def test_name_normalizes_case_unicode_ampersand_and_punctuation(self):
        self.assertEqual(
            normalize_name("Texas A & M–University"),
            normalize_name("texas a and m university"),
        )

    def test_domain_normalizes_url_and_www(self):
        self.assertEqual(
            normalize_domain("https://www.TUFTS.edu/admissions/"),
            "tufts.edu",
        )
        self.assertTrue(domains_related("rutgers.edu", "newbrunswick.rutgers.edu"))


class IdentityAuditTests(unittest.TestCase):
    def test_original_tufts_claim_is_blocked(self):
        bad_claim = claim(ipeds_id="167987")
        umass = official(
            ipeds_id="167987",
            official_name="University of Massachusetts-Dartmouth",
            official_domain="umassd.edu",
        )
        audit = audit_school_identities([bad_claim], {"167987": umass})
        self.assertEqual([issue["kind"] for issue in audit["errors"]], ["identity_mismatch"])

    def test_correct_tufts_claim_passes(self):
        audit = audit_school_identities([claim()], {"168148": official()})
        self.assertEqual(audit["errors"], [])
        self.assertEqual(audit["matched"], 1)

    def test_curated_short_name_passes_when_domain_matches(self):
        harvard = claim(
            school_id="harvard",
            ipeds_id="166027",
            claimed_name="Harvard",
            claimed_domain="harvard.edu",
        )
        row = official(
            ipeds_id="166027",
            official_name="Harvard University",
            official_domain="www.harvard.edu",
        )
        audit = audit_school_identities([harvard], {"166027": row})
        self.assertEqual(audit["errors"], [])

    def test_exact_reviewed_exception_passes_and_stale_exception_fails(self):
        renamed = claim(
            school_id="legacy-college",
            ipeds_id="123456",
            claimed_name="Legacy College",
            claimed_domain="legacy.edu",
            scrape_policy="unknown",
        )
        current = official(
            ipeds_id="123456",
            official_name="Current University",
            official_domain="current.edu",
        )
        exception = {
            "school_id": "legacy-college",
            "ipeds_id": "123456",
            "claimed_name": "Legacy College",
            "claimed_domain": "legacy.edu",
            "official_name": "Current University",
            "official_domain": "current.edu",
            "reason": "Reviewed merger; retain the public legacy label.",
        }
        self.assertEqual(
            audit_school_identities([renamed], {"123456": current}, [exception])["errors"],
            [],
        )
        exception["official_domain"] = "wildcard.example"
        kinds = [
            issue["kind"]
            for issue in audit_school_identities(
                [renamed], {"123456": current}, [exception]
            )["errors"]
        ]
        self.assertEqual(kinds, ["identity_mismatch", "unused_or_stale_exception"])

    def test_missing_active_blocks_but_missing_nonactive_warns(self):
        active = audit_school_identities([claim()], {})
        self.assertEqual(active["errors"][0]["kind"], "missing_official_record")

        inactive = audit_school_identities(
            [claim(scrape_policy="removed")], {}
        )
        self.assertEqual(inactive["errors"], [])
        self.assertEqual(inactive["warnings"][0]["kind"], "missing_official_record")

    def test_malformed_school_claims_fail_closed(self):
        invalid_entries = [
            {"id": "missing-ipeds", "name": "Missing IPEDS"},
            {"id": "", "name": "Missing slug", "ipeds_id": "168148"},
            {"id": "malformed-ipeds", "ipeds_id": "not-a-unitid"},
            {"id": "zero-ipeds", "ipeds_id": "0"},
            {"id": "short-ipeds", "ipeds_id": "68148"},
            "not-a-mapping",
            {"id": "bad-alias-type", "ipeds_id": "168148", "retired_aliases": "old"},
            {"id": "blank-alias", "ipeds_id": "168148", "retired_aliases": [""]},
            {
                "id": "same-alias",
                "ipeds_id": "168148",
                "retired_aliases": ["same-alias"],
            },
        ]
        for entry in invalid_entries:
            with self.subTest(entry=entry), self.assertRaises(ValueError):
                school_claims_from_entries([entry])  # type: ignore[list-item]

        with tempfile.TemporaryDirectory() as temp_dir:
            schools = Path(temp_dir) / "schools.yaml"
            schools.write_text("schools: not-a-list\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "schools must be a list"):
                load_school_claims(schools)

    def test_duplicate_ipeds_claims_block(self):
        claims = [
            claim(),
            claim(school_id="tufts-duplicate"),
        ]
        audit = audit_school_identities(claims, {"168148": official()})
        self.assertEqual(audit["errors"][0]["kind"], "duplicate_ipeds_claim")

    def test_duplicate_slugs_are_omitted_from_the_unique_canonical_map(self):
        claims = [
            claim(ipeds_id="100001", school_id="shared"),
            claim(ipeds_id="100002", school_id="shared"),
            claim(ipeds_id="100003", school_id="unique"),
        ]

        self.assertEqual(
            unique_school_claim_slug_map(claims),
            {"100003": "unique"},
        )


class SnapshotAndCliTests(unittest.TestCase):
    @staticmethod
    def _write_snapshot(path: Path, *, ipeds_id: str = "167987") -> None:
        path.write_text(
            "# data_year=2024\n"
            "ipeds_id,official_name,official_domain,official_state,active,new_ipeds_id\n"
            f"{ipeds_id},University of Massachusetts-Dartmouth,umassd.edu,MA,1,\n",
            encoding="utf-8",
        )

    def test_snapshot_builder_writes_provenance_and_rejects_archives_without_csv(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source_zip = root / "HD2024.zip"
            output = root / "snapshot.csv"
            with zipfile.ZipFile(source_zip, "w") as archive:
                archive.writestr(
                    "HD2024.csv",
                    "UNITID,INSTNM,WEBADDR,STABBR,CYACTIVE,NEWID\n"
                    "168148,Tufts University,https://www.tufts.edu/,MA,1,\n",
                )

            self.assertEqual(build_identity_snapshot(source_zip, output, 2024), 1)
            metadata, records = load_identity_snapshot(output)
            self.assertEqual(metadata["data_year"], "2024")
            self.assertEqual(records["168148"]["official_domain"], "tufts.edu")

            invalid_zip = root / "invalid.zip"
            with zipfile.ZipFile(invalid_zip, "w") as archive:
                archive.writestr("README.txt", "no csv here")
            with self.assertRaisesRegex(ValueError, "No CSV"):
                build_identity_snapshot(invalid_zip, output, 2024)

    def test_validated_map_fails_closed_and_cli_json_returns_error(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            schools = root / "schools.yaml"
            snapshot = root / "snapshot.csv"
            exceptions = root / "exceptions.json"
            schools.write_text(
                "schools:\n"
                "  - id: tufts\n"
                "    name: Tufts University\n"
                "    domain: tufts.edu\n"
                "    ipeds_id: '167987'\n"
                "    scrape_policy: active\n",
                encoding="utf-8",
            )
            self._write_snapshot(snapshot)
            exceptions.write_text(json.dumps({"exceptions": []}), encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "Refusing canonical school slug map"):
                validated_unique_school_claim_slug_map(
                    schools_path=schools,
                    snapshot_path=snapshot,
                    exceptions_path=exceptions,
                )

            argv = [
                "identity_guard.py",
                "--schools-yaml",
                str(schools),
                "--snapshot",
                str(snapshot),
                "--exceptions",
                str(exceptions),
                "--json",
            ]
            with patch.object(sys, "argv", argv):
                self.assertEqual(identity_guard_main(), 2)

    def test_cli_build_snapshot_branch(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source_zip = root / "HD2024.zip"
            output = root / "snapshot.csv"
            with zipfile.ZipFile(source_zip, "w") as archive:
                archive.writestr(
                    "HD2024.csv",
                    "UNITID,INSTNM,WEBADDR,STABBR,CYACTIVE,NEWID\n"
                    "168148,Tufts University,tufts.edu,MA,1,\n",
                )
            argv = [
                "identity_guard.py",
                "--build-snapshot",
                str(source_zip),
                "--snapshot",
                str(output),
                "--data-year",
                "2024",
            ]
            with patch.object(sys, "argv", argv):
                self.assertEqual(identity_guard_main(), 0)
            self.assertTrue(output.exists())


class SchoolListBuilderGuardTests(unittest.TestCase):
    @staticmethod
    def _official_row(ipeds_id: str, name: str, domain: str) -> dict[str, str]:
        return {
            "UNITID": ipeds_id,
            "INSTNM": name,
            "WEBADDR": domain,
            "STABBR": "MA",
            "CONTROL": "2",
            "ICLEVEL": "1",
            "DEGGRANT": "1",
            "FIPS": "25",
            "CYACTIVE": "1",
            "NEWID": "",
        }

    def test_builder_writes_valid_identity_and_refuses_wrong_identity(self):
        from tools.finder import build_school_list

        tufts_row = self._official_row("168148", "Tufts University", "tufts.edu")
        tufts_entry = {
            "id": "tufts",
            "name": "Tufts University",
            "domain": "tufts.edu",
            "ipeds_id": "168148",
            "retired_aliases": ["tufts-university"],
            "scrape_policy": "active",
        }
        with (
            patch.object(build_school_list, "download_ipeds", return_value=[tufts_row]),
            patch.object(build_school_list, "load_existing", return_value={"168148": tufts_entry}),
            patch.object(build_school_list, "write_yaml") as write_yaml,
            patch.object(sys, "argv", ["build_school_list.py", "--dry-run"]),
        ):
            build_school_list.main()
        write_yaml.assert_called_once()
        merged_schools = write_yaml.call_args.args[0]
        self.assertEqual(
            next(row for row in merged_schools if row["id"] == "tufts")[
                "retired_aliases"
            ],
            ["tufts-university"],
        )

        umass_row = self._official_row(
            "167987",
            "University of Massachusetts-Dartmouth",
            "umassd.edu",
        )
        wrong_entry = {**tufts_entry, "ipeds_id": "167987"}
        with (
            patch.object(build_school_list, "download_ipeds", return_value=[umass_row]),
            patch.object(build_school_list, "load_existing", return_value={"167987": wrong_entry}),
            patch.object(build_school_list, "write_yaml") as write_yaml,
            patch.object(sys, "argv", ["build_school_list.py", "--dry-run"]),
            self.assertRaisesRegex(SystemExit, "Refusing to write schools.yaml"),
        ):
            build_school_list.main()
        write_yaml.assert_not_called()

    def test_writer_emits_retired_aliases(self):
        from tools.finder import build_school_list

        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir) / "schools.yaml"
            school = {
                "id": "tufts",
                "name": "Tufts University",
                "domain": "tufts.edu",
                "ipeds_id": "168148",
                "retired_aliases": ["tufts-university"],
                "scrape_policy": "active",
            }
            with patch.object(build_school_list, "SCHOOLS_YAML", output):
                build_school_list.write_yaml([school])

            rendered = output.read_text(encoding="utf-8")
            self.assertIn("retired_aliases:", rendered)
            self.assertIn("- tufts-university", rendered)


class RepositoryIdentityRegressionTests(unittest.TestCase):
    def test_checked_in_corpus_matches_official_snapshot(self):
        metadata, records = load_identity_snapshot(DEFAULT_SNAPSHOT)
        claims = load_school_claims(DEFAULT_SCHOOLS_YAML)
        audit = audit_school_identities(claims, records)

        self.assertEqual(metadata["data_year"], "2024")
        self.assertEqual(
            metadata["source_sha256"],
            "d98425c123d7c0e872aec6e83960dfb501884818bf17385c340790f3d1f28345",
        )
        self.assertEqual(audit["errors"], [])
        self.assertGreaterEqual(len(records), 6_000)

        by_slug = {row["school_id"]: row for row in claims}
        self.assertEqual(by_slug["tufts"]["ipeds_id"], "168148")
        self.assertNotEqual(by_slug["tufts"]["ipeds_id"], "167987")

        canonical_slugs = validated_unique_school_claim_slug_map()
        self.assertEqual(canonical_slugs["168148"], "tufts")
        self.assertNotIn("167987", canonical_slugs)

    def test_tufts_operational_inputs_use_the_canonical_slug(self):
        from tools.finder.playwright_collect import STARTING_URLS

        manual = yaml.safe_load(
            (DEFAULT_SCHOOLS_YAML.parent / "manual_urls.yaml").read_text()
        )
        self.assertIn("tufts", manual["schools"])
        self.assertNotIn("tufts-university", manual["schools"])
        self.assertIn("tufts", STARTING_URLS)
        self.assertNotIn("tufts-university", STARTING_URLS)


if __name__ == "__main__":
    unittest.main()
