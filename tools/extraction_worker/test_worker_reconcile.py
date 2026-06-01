"""Tests for the cheap, extraction-free pending-status reconcile pass.

These cover the gate that decides whether a document is *actually* extracted
(``has_canonical_for_current_bytes``) and the pass that flips such documents
out of ``extraction_pending`` without re-running Docling
(``reconcile_pending_documents``). This is the durable fix for documents that
serve real data yet show "pending/processing" in cds_manifest.
"""

from __future__ import annotations

import unittest
from types import SimpleNamespace

from worker import (
    has_canonical_for_current_bytes,
    reconcile_pending_documents,
)

CUR = "sha-current"
OLD = "sha-old"


def _src(sha, created_at):
    return {"kind": "source", "sha256": sha, "created_at": created_at}


def _canon(created_at):
    return {"kind": "canonical", "sha256": "art-sha", "created_at": created_at}


class _ArtifactQuery:
    """Stands in for client.table('cds_artifacts').select(...).eq(...).execute()."""

    def __init__(self, rows):
        self._rows = rows

    def select(self, _cols):
        return self

    def eq(self, _col, _val):
        return self

    def execute(self):
        return SimpleNamespace(data=list(self._rows))


class _DocUpdateQuery:
    """Records cds_documents update(...).eq(...)[.in_(...)].execute() calls."""

    def __init__(self, sink, payload):
        self._sink = sink
        self._payload = payload

    def eq(self, _col, value):
        self._sink.append((value, self._payload))
        return self

    def in_(self, _col, _values):
        return self

    def execute(self):
        return SimpleNamespace(data=[])


class _FakeClient:
    def __init__(self, artifacts_by_doc):
        self._artifacts_by_doc = artifacts_by_doc
        self.updates: list[tuple[str, dict]] = []
        self._last_doc_id = None

    def table(self, name):
        self._table = name
        return self

    # cds_artifacts path
    def select(self, _cols):
        return self

    # shared eq: artifacts query filters by document_id; remember which doc
    def eq(self, col, value):
        if self._table == "cds_artifacts" and col == "document_id":
            rows = self._artifacts_by_doc.get(value, [])
            return _ArtifactQuery(rows)
        return self

    def update(self, payload):
        return _DocUpdateQuery(self.updates, payload)


class HasCanonicalForCurrentBytesTests(unittest.TestCase):
    def _client(self, rows):
        return _FakeClient({"doc": rows})

    def test_canonical_after_current_source_is_extracted(self):
        rows = [_src(CUR, "2026-04-14T00:00:00+00:00"), _canon("2026-05-11T00:00:00+00:00")]
        self.assertTrue(has_canonical_for_current_bytes(self._client(rows), "doc", CUR))

    def test_canonical_predating_current_source_is_stale(self):
        # Source republished after the only extraction -> not extracted yet.
        rows = [
            _canon("2026-04-20T00:00:00+00:00"),
            _src(OLD, "2026-04-14T00:00:00+00:00"),
            _src(CUR, "2026-05-01T00:00:00+00:00"),
        ]
        self.assertFalse(has_canonical_for_current_bytes(self._client(rows), "doc", CUR))

    def test_no_canonical_is_not_extracted(self):
        rows = [_src(CUR, "2026-04-14T00:00:00+00:00")]
        self.assertFalse(has_canonical_for_current_bytes(self._client(rows), "doc", CUR))

    def test_no_source_row_matching_current_sha_is_conservative(self):
        rows = [_src(OLD, "2026-04-14T00:00:00+00:00"), _canon("2026-05-11T00:00:00+00:00")]
        self.assertFalse(has_canonical_for_current_bytes(self._client(rows), "doc", CUR))

    def test_missing_source_sha_returns_false(self):
        rows = [_canon("2026-05-11T00:00:00+00:00")]
        self.assertFalse(has_canonical_for_current_bytes(self._client(rows), "doc", None))


class ReconcilePendingDocumentsTests(unittest.TestCase):
    def test_flips_only_current_bytes_docs_and_excludes_them(self):
        artifacts = {
            "extracted-doc": [
                _src(CUR, "2026-04-14T00:00:00+00:00"),
                _canon("2026-05-11T00:00:00+00:00"),
            ],
            "stale-doc": [
                _canon("2026-04-20T00:00:00+00:00"),
                _src(CUR, "2026-05-01T00:00:00+00:00"),
            ],
            "fresh-doc": [_src(CUR, "2026-04-14T00:00:00+00:00")],
        }
        client = _FakeClient(artifacts)
        docs = [
            {"id": "extracted-doc", "source_sha256": CUR},
            {"id": "stale-doc", "source_sha256": CUR},
            {"id": "fresh-doc", "source_sha256": CUR},
        ]

        reconciled, counts = reconcile_pending_documents(
            client, docs, projection_definitions=None,
            projection_enabled=False, dry_run=False,
        )

        self.assertEqual(reconciled, {"extracted-doc"})
        self.assertEqual(counts["reconciled"], 1)
        # exactly one document flipped to extracted
        extracted_updates = [
            doc_id for doc_id, payload in client.updates
            if payload.get("extraction_status") == "extracted"
        ]
        self.assertEqual(extracted_updates, ["extracted-doc"])

    def test_dry_run_classifies_without_writing(self):
        artifacts = {
            "extracted-doc": [
                _src(CUR, "2026-04-14T00:00:00+00:00"),
                _canon("2026-05-11T00:00:00+00:00"),
            ],
        }
        client = _FakeClient(artifacts)
        docs = [{"id": "extracted-doc", "source_sha256": CUR}]

        reconciled, counts = reconcile_pending_documents(
            client, docs, projection_definitions=None,
            projection_enabled=False, dry_run=True,
        )

        self.assertEqual(reconciled, {"extracted-doc"})
        self.assertEqual(counts["reconciled"], 1)
        self.assertEqual(client.updates, [])  # no writes in dry run


if __name__ == "__main__":
    unittest.main()
