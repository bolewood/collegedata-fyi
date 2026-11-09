"""Unit tests for revalidate_notify (HTTP mocked)."""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import revalidate_notify as rn  # noqa: E402

ENV = {rn.URL_ENV: "https://example.test/api/revalidate", rn.SECRET_ENV: "s3cret"}


class FakeResponse:
    def __init__(self, status=200):
        self.status = status

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class Recorder:
    def __init__(self, status=200, exc=None):
        self.calls = []
        self.status = status
        self.exc = exc

    def __call__(self, request, timeout=None):
        self.calls.append((request, timeout))
        if self.exc:
            raise self.exc
        return FakeResponse(self.status)


class NotifyTests(unittest.TestCase):
    def test_noop_without_env(self):
        rec = Recorder()
        for env in ({}, {rn.URL_ENV: "https://x"}, {rn.SECRET_ENV: "s"}):
            out = rn.notify_school_revalidation(["a"], env, opener=rec)
            self.assertFalse(out["enabled"])
        self.assertEqual(rec.calls, [])

    def test_posts_deduped_sorted_ids_with_auth(self):
        rec = Recorder()
        out = rn.notify_school_revalidation(["b", "a", "b", None, " "], ENV, opener=rec)
        self.assertEqual(out["sent"], 2)
        (request, timeout), = rec.calls
        self.assertEqual(json.loads(request.data), {"school_ids": ["a", "b"]})
        self.assertEqual(request.get_header("Authorization"), "Bearer s3cret")
        self.assertEqual(request.get_method(), "POST")
        self.assertEqual(timeout, rn.TIMEOUT_SECONDS)

    def test_batches(self):
        rec = Recorder()
        ids = [f"s{i:04d}" for i in range(rn.BATCH_SIZE * 2 + 1)]
        out = rn.notify_school_revalidation(ids, ENV, opener=rec)
        self.assertEqual(len(rec.calls), 3)
        self.assertEqual(out["sent"], len(ids))

    def test_no_ids_no_call(self):
        rec = Recorder()
        rn.notify_school_revalidation([], ENV, opener=rec)
        self.assertEqual(rec.calls, [])

    def test_stops_after_transport_failure(self):
        rec = Recorder(exc=OSError("timeout"))
        ids = [f"s{i:04d}" for i in range(rn.BATCH_SIZE * 3)]
        out = rn.notify_school_revalidation(ids, ENV, opener=rec)
        self.assertEqual(len(rec.calls), 1)
        self.assertEqual(out["errors"], 1)

    def test_errors_never_raise(self):
        out = rn.notify_school_revalidation(["a"], ENV, opener=Recorder(exc=OSError("boom")))
        self.assertEqual(out["errors"], 1)
        out = rn.notify_school_revalidation(["a"], ENV, opener=Recorder(status=401))
        self.assertEqual(out["errors"], 1)


if __name__ == "__main__":
    unittest.main()
