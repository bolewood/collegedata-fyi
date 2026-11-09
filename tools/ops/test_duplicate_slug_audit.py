"""Unit tests for tools/ops/duplicate_slug_audit.py."""

from __future__ import annotations

import io
import json
import os
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

from tools.ops import duplicate_slug_audit as audit


CROSSWALK_FIXTURE = [
    {
        "alias": "virginia-tech",
        "school_id": "virginia-tech",
        "ipeds_id": "233921",
        "is_primary": True,
        "alias_type": "canonical",
    },
    {
        "alias": "virginia-polytechnic-institute-and-state-university",
        "school_id": "virginia-tech",
        "ipeds_id": "233921",
        "is_primary": False,
        "alias_type": "retired_slug",
    },
    {
        "alias": "caltech",
        "school_id": "caltech",
        "ipeds_id": "110404",
        "is_primary": True,
        "alias_type": "canonical",
    },
    {
        "alias": "california-institute-of-technology",
        "school_id": "caltech",
        "ipeds_id": "110404",
        "is_primary": False,
        "alias_type": "retired_slug",
    },
    {
        "alias": "tulane-university",
        "school_id": "tulane-university",
        "ipeds_id": "160755",
        "is_primary": True,
        "alias_type": "canonical",
    },
    {
        "alias": "tulane-university-of-louisiana",
        "school_id": "tulane-university",
        "ipeds_id": "160755",
        "is_primary": False,
        "alias_type": "retired_slug",
    },
    {
        "alias": "uchicago",
        "school_id": "uchicago",
        "ipeds_id": "144050",
        "is_primary": True,
        "alias_type": "canonical",
    },
    {
        "alias": "university-of-chicago",
        "school_id": "uchicago",
        "ipeds_id": "144050",
        "is_primary": False,
        "alias_type": "retired_slug",
    },
    # Shared nickname collision with no unique primary should not guess
    {
        "alias": "ambiguous-alias",
        "school_id": "school-a",
        "ipeds_id": "100001",
        "is_primary": False,
        "alias_type": "nickname",
    },
    {
        "alias": "ambiguous-alias",
        "school_id": "school-b",
        "ipeds_id": "100002",
        "is_primary": False,
        "alias_type": "nickname",
    },
]


class FakeClient:
    def __init__(self, crosswalk_rows, document_rows) -> None:
        self.crosswalk_rows = list(crosswalk_rows)
        self.document_rows = list(document_rows)
        self.calls = []

    def rest_get(self, table: str, params: dict[str, str], *, page=None):
        self.calls.append((table, params, page))
        if table == "institution_slug_crosswalk":
            return self.crosswalk_rows
        if table == "cds_documents":
            return self.document_rows
        raise AssertionError(f"Unexpected table {table}")


class DuplicateSlugAuditTests(unittest.TestCase):
    def test_build_alias_to_canonical_map_excludes_canonicals_and_ambiguous_aliases(self) -> None:
        alias_map = audit.build_alias_to_canonical_map(CROSSWALK_FIXTURE)
        self.assertEqual(
            alias_map,
            {
                "california-institute-of-technology": "caltech",
                "tulane-university-of-louisiana": "tulane-university",
                "university-of-chicago": "uchicago",
                "virginia-polytechnic-institute-and-state-university": "virginia-tech",
            },
        )

    def test_classify_alias_documents_distinguishes_same_year_and_same_sha256(self) -> None:
        documents = [
            # Canonical Virginia Tech 2024-25 document
            {
                "id": "vt-canon-2024",
                "school_id": "virginia-tech",
                "cds_year": "2024-25",
                "detected_year": "2024-25",
                "sub_institutional": None,
                "source_sha256": "sha-vt-2024",
                "source_provenance": "school_direct",
                "extraction_status": "extracted",
            },
            # 1) Exact duplicate under alias (same year + same sha256)
            {
                "id": "vt-alias-2024",
                "school_id": "virginia-polytechnic-institute-and-state-university",
                "cds_year": "2024-25",
                "detected_year": "2024-25",
                "sub_institutional": None,
                "source_sha256": "sha-vt-2024",
                "source_provenance": "mirror_college_transitions",
                "extraction_status": "extracted",
            },
            # Canonical Caltech 2024-25 document with different sha256
            {
                "id": "caltech-canon-2024",
                "school_id": "caltech",
                "cds_year": "2024-25",
                "detected_year": "2024-25",
                "sub_institutional": None,
                "source_sha256": "sha-caltech-direct",
                "source_provenance": "school_direct",
                "extraction_status": "extracted",
            },
            # 2) Same year, different sha256
            {
                "id": "caltech-alias-2024",
                "school_id": "california-institute-of-technology",
                "cds_year": "2024-25",
                "detected_year": "2024-25",
                "sub_institutional": None,
                "source_sha256": "sha-caltech-mirror",
                "source_provenance": "mirror_college_transitions",
                "extraction_status": "extracted",
            },
            # Canonical Tulane 2024-25 document with same sha256 but alias filed under 2023-24
            {
                "id": "tulane-canon-2024",
                "school_id": "tulane-university",
                "cds_year": "2024-25",
                "detected_year": "2024-25",
                "sub_institutional": None,
                "source_sha256": "sha-tulane-shared",
                "source_provenance": "school_direct",
                "extraction_status": "extracted",
            },
            # 3) Different year, same sha256
            {
                "id": "tulane-alias-2023",
                "school_id": "tulane-university-of-louisiana",
                "cds_year": "2023-24",
                "detected_year": "2023-24",
                "sub_institutional": None,
                "source_sha256": "sha-tulane-shared",
                "source_provenance": "mirror_college_transitions",
                "extraction_status": "extracted",
            },
            # 4) Alias-only year (canonical uchicago has no 2018-19 doc)
            {
                "id": "uchicago-alias-2018",
                "school_id": "university-of-chicago",
                "cds_year": "2018-19",
                "detected_year": "2018-19",
                "sub_institutional": None,
                "source_sha256": "sha-uchicago-2018",
                "source_provenance": "mirror_college_transitions",
                "extraction_status": "extracted",
            },
        ]

        report = audit.classify_alias_documents(documents, CROSSWALK_FIXTURE)
        self.assertEqual(report["duplicate_count"], 4)
        self.assertEqual(
            report["by_classification"],
            {
                "alias_only_year": 1,
                "exact_duplicate": 1,
                "same_sha256_different_year": 1,
                "same_year_different_sha256": 1,
            },
        )
        by_id = {item["document_id"]: item for item in report["findings"]}

        self.assertEqual(by_id["vt-alias-2024"]["canonical_school_id"], "virginia-tech")
        self.assertTrue(by_id["vt-alias-2024"]["same_year"])
        self.assertTrue(by_id["vt-alias-2024"]["same_source_sha256"])
        self.assertEqual(by_id["vt-alias-2024"]["classification"], "exact_duplicate")

        self.assertEqual(by_id["caltech-alias-2024"]["canonical_school_id"], "caltech")
        self.assertTrue(by_id["caltech-alias-2024"]["same_year"])
        self.assertFalse(by_id["caltech-alias-2024"]["same_source_sha256"])
        self.assertEqual(
            by_id["caltech-alias-2024"]["classification"],
            "same_year_different_sha256",
        )

        self.assertEqual(
            by_id["tulane-alias-2023"]["canonical_school_id"], "tulane-university"
        )
        self.assertFalse(by_id["tulane-alias-2023"]["same_year"])
        self.assertTrue(by_id["tulane-alias-2023"]["same_source_sha256"])
        self.assertEqual(
            by_id["tulane-alias-2023"]["classification"],
            "same_sha256_different_year",
        )

        self.assertEqual(by_id["uchicago-alias-2018"]["canonical_school_id"], "uchicago")
        self.assertFalse(by_id["uchicago-alias-2018"]["same_year"])
        self.assertFalse(by_id["uchicago-alias-2018"]["same_source_sha256"])
        self.assertEqual(
            by_id["uchicago-alias-2018"]["classification"], "alias_only_year"
        )

    def test_main_exits_zero_when_clean_and_nonzero_when_duplicates_found(self) -> None:
        clean_docs = [
            {
                "id": "vt-canon-2024",
                "school_id": "virginia-tech",
                "cds_year": "2024-25",
                "detected_year": "2024-25",
                "sub_institutional": None,
                "source_sha256": "sha-vt-2024",
                "source_provenance": "school_direct",
                "extraction_status": "extracted",
            }
        ]
        dirty_docs = clean_docs + [
            {
                "id": "vt-alias-2024",
                "school_id": "virginia-polytechnic-institute-and-state-university",
                "cds_year": "2024-25",
                "detected_year": "2024-25",
                "sub_institutional": None,
                "source_sha256": "sha-vt-2024",
                "source_provenance": "mirror_college_transitions",
                "extraction_status": "extracted",
            }
        ]

        env = {
            "SUPABASE_URL": "https://project.supabase.co",
            "SUPABASE_SERVICE_ROLE_KEY": "service-role-key",
        }
        with (
            patch.dict(os.environ, env, clear=False),
            patch(
                "tools.ops.duplicate_slug_audit.SupabaseClient",
                return_value=FakeClient(CROSSWALK_FIXTURE, clean_docs),
            ),
            redirect_stdout(io.StringIO()) as clean_out,
        ):
            self.assertEqual(audit.main(["--json"]), 0)
        self.assertEqual(json.loads(clean_out.getvalue())["duplicate_count"], 0)

        with (
            patch.dict(os.environ, env, clear=False),
            patch(
                "tools.ops.duplicate_slug_audit.SupabaseClient",
                return_value=FakeClient(CROSSWALK_FIXTURE, dirty_docs),
            ),
            redirect_stdout(io.StringIO()) as dirty_out,
        ):
            self.assertEqual(audit.main(["--json"]), 1)
        self.assertEqual(json.loads(dirty_out.getvalue())["duplicate_count"], 1)


if __name__ == "__main__":
    unittest.main()
