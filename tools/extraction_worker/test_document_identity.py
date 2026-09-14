"""Extraction queue must stamp directory identity before the public ledger."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

WORKER_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(WORKER_DIR))

from worker import (  # noqa: E402
    document_identity_needs_repair,
    extraction_ledger_item,
    stamp_document_identity,
)


class _DirectoryClient:
    def __init__(self, directory_row: dict | None, *, update_error: Exception | None = None):
        self.directory_row = directory_row
        self.update_error = update_error
        self.updates: list[dict] = []

    def table(self, name: str):
        if name == "institution_directory":
            query = MagicMock()
            query.select.return_value = query
            query.eq.return_value = query
            query.limit.return_value = query
            query.execute.return_value = SimpleNamespace(
                data=[self.directory_row] if self.directory_row else [],
            )
            return query
        if name == "cds_documents":
            query = MagicMock()
            query.update.side_effect = self._update
            return query
        raise AssertionError(f"unexpected table {name}")

    def _update(self, patch: dict):
        if self.update_error:
            raise self.update_error
        self.updates.append(patch)
        query = MagicMock()
        query.eq.return_value = query
        query.execute.return_value = SimpleNamespace(data=[patch])
        return query


class DocumentIdentityTests(unittest.TestCase):
    def test_slug_as_name_without_unitid_needs_repair(self) -> None:
        self.assertTrue(
            document_identity_needs_repair(
                {"school_id": "uf", "school_name": "uf", "ipeds_id": None}
            )
        )
        self.assertFalse(
            document_identity_needs_repair(
                {
                    "school_id": "uf",
                    "school_name": "University of Florida",
                    "ipeds_id": "134130",
                }
            )
        )

    def test_stamps_directory_name_and_unitid(self) -> None:
        client = _DirectoryClient(
            {
                "school_id": "uf",
                "school_name": "University of Florida",
                "ipeds_id": "134130",
            }
        )
        doc = {
            "id": "0936dc34-2477-468d-a50d-2c1640c2a9a8",
            "school_id": "uf",
            "school_name": "uf",
            "ipeds_id": None,
            "cds_year": "unknown",
        }
        stamped = stamp_document_identity(client, doc)
        self.assertEqual(stamped["school_name"], "University of Florida")
        self.assertEqual(stamped["ipeds_id"], "134130")
        self.assertEqual(
            client.updates,
            [{"ipeds_id": "134130", "school_name": "University of Florida"}],
        )
        item = extraction_ledger_item(
            stamped, "tier4_extracted (106 fields)", ordinal=1, force_reextract=False,
        )
        self.assertEqual(item["school_name"], "University of Florida")
        self.assertEqual(item["school_id"], "uf")

    def test_leaves_complete_rows_alone(self) -> None:
        client = _DirectoryClient(
            {
                "school_id": "uf",
                "school_name": "University of Florida",
                "ipeds_id": "134130",
            }
        )
        doc = {
            "id": "already-good",
            "school_id": "uf",
            "school_name": "University of Florida",
            "ipeds_id": "134130",
        }
        stamp_document_identity(client, doc)
        self.assertEqual(client.updates, [])


if __name__ == "__main__":
    unittest.main()
