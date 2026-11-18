"""Archive identity must resolve public slugs to IPEDS UNITIDs."""

from __future__ import annotations

import os
import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock

from tools.finder.archive_identity import (
    AmbiguousArchiveSchoolError,
    UnknownArchiveSchoolError,
    resolve_archive_identity,
)
from tools.finder.headless_archive import build_targets
from tools.finder.headless_download import upload_and_record


def _claim(slug: str, ipeds: str, domain: str) -> dict:
    return {
        "school_id": slug,
        "ipeds_id": ipeds,
        "claimed_name": slug.replace("-", " ").title(),
        "claimed_domain": domain,
    }


SHARED = {
    "bethel-university": [
        _claim("bethel-university", "150145", "betheluniversity.edu"),
        _claim("bethel-university", "173160", "bethel.edu"),
        _claim("bethel-university", "219718", "bethelu.edu"),
    ],
    "columbia-college": [
        _claim("columbia-college", "177065", "ccis.edu"),
        _claim("columbia-college", "217934", "columbiasc.edu"),
    ],
    "westminster-college": [
        _claim("westminster-college", "179946", "wcmo.edu"),
        _claim("westminster-college", "216807", "westminster.edu"),
    ],
    "university-of-st-thomas": [
        _claim("university-of-st-thomas", "174914", "stthomas.edu"),
        _claim("university-of-st-thomas", "227863", "stthom.edu"),
    ],
}


class ArchiveIdentityTests(unittest.TestCase):
    def test_uf_maps_to_university_of_florida_unitid(self) -> None:
        identity = resolve_archive_identity("uf")
        self.assertEqual(identity["school_id"], "uf")
        self.assertEqual(identity["school_name"], "University of Florida")
        self.assertEqual(identity["ipeds_id"], "134130")

    def test_shared_slug_is_refused_not_resolved_to_the_last_entry(self) -> None:
        # The old dict lookup kept the last row (Tennessee) for every caller.
        with self.assertRaises(AmbiguousArchiveSchoolError) as ctx:
            resolve_archive_identity("bethel-university", claims_by_school_id=SHARED)
        for unitid in ("150145", "173160", "219718"):
            self.assertIn(unitid, str(ctx.exception))

    def test_shared_slug_resolves_when_the_unitid_is_given(self) -> None:
        identity = resolve_archive_identity(
            "bethel-university", ipeds_id="173160", claims_by_school_id=SHARED
        )
        self.assertEqual(identity["ipeds_id"], "173160")
        with self.assertRaises(UnknownArchiveSchoolError):
            resolve_archive_identity(
                "bethel-university", ipeds_id="999999", claims_by_school_id=SHARED
            )

    def test_shared_slug_resolves_when_the_source_host_picks_one_entry(self) -> None:
        cases = [
            ("bethel-university", "https://www.bethel.edu/x/cds.xlsx", "173160"),
            ("columbia-college", "https://www.ccis.edu/_files/cds.pdf", "177065"),
            ("westminster-college", "https://www.wcmo.edu/cds.pdf", "179946"),
            ("university-of-st-thomas", "https://it.stthom.edu/cds.pdf", "227863"),
            (
                "westminster-college",
                "https://web.archive.org/web/20250101000000id_/https://www.wcmo.edu/cds.pdf",
                "179946",
            ),
        ]
        for slug, url, want in cases:
            identity = resolve_archive_identity(
                slug, source_url=url, claims_by_school_id=SHARED
            )
            self.assertEqual(identity["ipeds_id"], want, url)

    def test_shared_slug_with_no_or_unrelated_host_is_still_refused(self) -> None:
        for url in (None, "", "https://drive.google.com/file/d/x", "https://notstthom.edu/a.pdf"):
            with self.assertRaises(AmbiguousArchiveSchoolError, msg=str(url)):
                resolve_archive_identity(
                    "university-of-st-thomas", source_url=url, claims_by_school_id=SHARED
                )

    def test_a_slug_listed_twice_with_one_id_is_not_ambiguous(self) -> None:
        twice = {"uf": [_claim("uf", "134130", "ufl.edu"), _claim("uf", "134130", "ufl.edu")]}
        self.assertEqual(
            resolve_archive_identity("uf", claims_by_school_id=twice)["ipeds_id"], "134130"
        )

    def test_unknown_slug_is_rejected(self) -> None:
        with self.assertRaises(UnknownArchiveSchoolError):
            resolve_archive_identity("university-of-florida")

    def test_script_entry_imports_without_package_path(self) -> None:
        """Ops runs `python tools/finder/headless_archive.py`, not -m."""
        repo = Path(__file__).resolve().parents[2]
        env = os.environ.copy()
        env.pop("PYTHONPATH", None)
        proc = subprocess.run(
            [sys.executable, "tools/finder/headless_archive.py", "--help"],
            cwd=str(repo),
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("usage:", proc.stdout.lower() + proc.stderr.lower())


class HeadlessTargetIdentityTests(unittest.TestCase):
    def test_queue_extra_uses_official_name_not_slug(self) -> None:
        targets = build_targets(
            {},
            extra_school_ids=["uf"],
            seed_by_id={
                "uf": "https://ir.aa.ufl.edu/reports/cds-reports/",
            },
            starting_urls={},
            only=None,
            max_schools=20,
        )
        self.assertEqual(len(targets), 1)
        self.assertEqual(targets[0].school_id, "uf")
        self.assertEqual(targets[0].school_name, "University of Florida")


class UploadIdentityTests(unittest.TestCase):
    def test_upload_stamps_ipeds_and_refuses_slug_as_name(self) -> None:
        stored: dict = {}

        class _Table:
            def __init__(self, name: str) -> None:
                self.name = name
                self._payload: dict | None = None

            def select(self, *_args, **_kwargs):
                return self

            def eq(self, *_args, **_kwargs):
                return self

            def limit(self, *_args, **_kwargs):
                return self

            def execute(self):
                if self._payload is not None:
                    row = {"id": "doc-1", **self._payload}
                    return MagicMock(data=[row])
                return MagicMock(data=[])

            def upsert(self, row, **_kwargs):
                stored["doc"] = row
                self._payload = row
                return self

            def insert(self, row):
                stored.setdefault("artifacts", []).append(row)
                self._payload = row
                return self

        class _Storage:
            def from_(self, _bucket):
                return self

            def upload(self, *_args, **_kwargs):
                return MagicMock()

        sb = MagicMock()
        sb.table.side_effect = lambda name: _Table(name)
        sb.storage = _Storage()

        result = upload_and_record(
            sb,
            "uf",
            "unknown",
            b"%PDF-1.5 fake",
            "pdf",
            "application/pdf",
            "https://data-apps.ir.aa.ufl.edu/public/cds/cds1997-98.pdf",
            "uf",
        )
        self.assertEqual(result["action"], "inserted")
        self.assertEqual(stored["doc"]["school_id"], "uf")
        self.assertEqual(stored["doc"]["school_name"], "University of Florida")
        self.assertEqual(stored["doc"]["ipeds_id"], "134130")
        self.assertEqual(stored["doc"]["source_sha256"], result["sha256"])


if __name__ == "__main__":
    unittest.main()
