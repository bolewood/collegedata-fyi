from __future__ import annotations

import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import worker
from worker import (
    extraction_ledger_failure_code,
    extraction_ledger_item,
    extraction_ledger_outcome,
    extraction_ledger_tier,
    finalize_extraction_run,
    replay_extraction_ledger,
    sanitize_pipeline_run_url,
)


class FakeRpcClient:
    def __init__(
        self,
        *,
        error: Exception | None = None,
        failures_before_success: int | None = None,
    ):
        self.calls: list[tuple[str, dict]] = []
        self.error = error
        self.failures_before_success = failures_before_success

    def rpc(self, name: str, payload: dict):
        self.calls.append((name, payload))

        def execute():
            should_fail = self.error and (
                self.failures_before_success is None
                or len(self.calls) <= self.failures_before_success
            )
            if should_fail:
                raise self.error
            return SimpleNamespace(data=True)

        return SimpleNamespace(execute=execute)


class FakeDocumentsQuery:
    def __init__(self, docs: list[dict]):
        self.docs = docs

    def select(self, *_args, **_kwargs):
        return self

    def eq(self, *_args, **_kwargs):
        return self

    def in_(self, *_args, **_kwargs):
        return self

    def order(self, *_args, **_kwargs):
        return self

    def execute(self):
        return SimpleNamespace(data=self.docs)


class FakeMainClient:
    def __init__(self, docs: list[dict]):
        self.docs = docs

    def table(self, name: str):
        if name != "cds_documents":
            raise AssertionError(f"unexpected table: {name}")
        return FakeDocumentsQuery(self.docs)


class ExtractionLedgerNormalizationTests(unittest.TestCase):
    def test_outcomes_distinguish_first_reextract_reconcile_and_failure(self) -> None:
        self.assertEqual(
            extraction_ledger_outcome(
                "tier4_extracted (120 fields)",
                force_reextract=False,
            ),
            "extracted",
        )
        self.assertEqual(
            extraction_ledger_outcome(
                "tier4_extracted (120 fields)",
                force_reextract=True,
            ),
            "re_extracted",
        )
        self.assertEqual(
            extraction_ledger_outcome("already_extracted", force_reextract=False),
            "already_current",
        )
        self.assertEqual(
            extraction_ledger_outcome(
                "tier2_label_acroform_fallback_already_extracted",
                force_reextract=True,
            ),
            "already_current",
        )
        self.assertEqual(
            extraction_ledger_outcome("reconciled", force_reextract=False),
            "reconciled",
        )
        self.assertEqual(
            extraction_ledger_outcome(
                "download_error: signed URL expired",
                force_reextract=False,
            ),
            "failed",
        )

    def test_failure_codes_are_closed_and_drop_raw_error_text(self) -> None:
        cases = {
            "no_source_artifact": "source_missing",
            "download_error: signed URL expired": "source_download_failed",
            "stub_docx": "unsupported_format",
            "tier1_no_cell_map (0 fields)": "schema_failed",
            "tier6_html_error: parser secret": "extraction_failed",
            "tier4_low_fields (2 fields)": "low_coverage",
            "artifact_insert_error: database detail": "artifact_write_failed",
            (
                "tier2_label_acroform_fallback_"
                "artifact_insert_error: database detail"
            ): "artifact_write_failed",
            "worker_error: RuntimeError: private path": "worker_failed",
        }
        for action, expected in cases.items():
            with self.subTest(action=action):
                self.assertEqual(extraction_ledger_failure_code(action), expected)

    def test_tier_mapping_includes_fillable_fallback(self) -> None:
        self.assertEqual(extraction_ledger_tier("xlsx", "tier1_extracted"), "tier1")
        self.assertEqual(
            extraction_ledger_tier("pdf_scanned", "tier4_extracted"),
            "tier4_ocr",
        )
        self.assertEqual(
            extraction_ledger_tier(
                "pdf_fillable",
                "tier2_label_acroform_fallback_tier4_extracted (80 fields)",
            ),
            "tier4_fallback",
        )
        self.assertEqual(
            extraction_ledger_tier("html", "tier6_extracted"),
            "tier6",
        )
        self.assertEqual(
            extraction_ledger_tier("unknown", "reconciled"),
            "reconciliation",
        )

    def test_item_payload_contains_only_closed_writer_contract(self) -> None:
        item = extraction_ledger_item(
            {
                "id": "00000000-0000-0000-0000-000000000001",
                "school_id": "private-school-slug",
                "source_format": "pdf_flat",
                "source_sha256": "do-not-log",
                "source_url": "https://private.example/source.pdf",
            },
            "tier4_error: /private/path secret-token",
            ordinal=3,
            force_reextract=False,
            occurred_at="2026-09-12T12:00:00+00:00",
        )
        self.assertEqual(
            set(item),
            {
                "ordinal",
                "document_id",
                "school_id",
                "school_name",
                "canonical_year",
                "occurred_at",
                "outcome",
                "source_format",
                "extraction_tier",
                "field_count",
                "failure_code",
            },
        )
        serialized = json.dumps(item)
        self.assertIn("private-school-slug", serialized)
        for forbidden in (
            "do-not-log",
            "private.example",
            "/private/path",
            "secret-token",
        ):
            self.assertNotIn(forbidden, serialized)

    def test_run_url_is_allowlisted_before_replay_artifact_storage(self) -> None:
        valid = "https://github.com/bolewood/collegedata-fyi/actions/runs/123"
        self.assertEqual(sanitize_pipeline_run_url(valid), valid)
        self.assertIsNone(
            sanitize_pipeline_run_url(f"{valid}?token=private"),
        )
        self.assertIsNone(
            sanitize_pipeline_run_url("https://evil.example/actions/runs/123"),
        )


class ExtractionLedgerWriterTests(unittest.TestCase):
    def summary(self) -> dict:
        return {
            "started_at": "2026-09-12T12:00:00+00:00",
            "finished_at": "2026-09-12T12:01:00+00:00",
            "dry_run": False,
            "stopped_reason": "cap",
            "pending_remaining": 7,
        }

    def test_finalize_writes_summary_and_normalized_rpc(self) -> None:
        client = FakeRpcClient()
        item = {
            "ordinal": 1,
            "document_id": "00000000-0000-0000-0000-000000000001",
            "school_id": "harvey-mudd-college",
            "school_name": "Harvey Mudd College",
            "canonical_year": "2025-26",
            "occurred_at": "2026-09-12T12:00:30+00:00",
            "outcome": "extracted",
            "source_format": "pdf_flat",
            "extraction_tier": "tier4",
            "field_count": 120,
            "failure_code": "none",
        }
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "summary.json"
            ok = finalize_extraction_run(
                client,  # type: ignore[arg-type]
                run_id="00000000-0000-0000-0000-000000000099",
                trigger="dispatch",
                run_url=(
                    "https://github.com/bolewood/collegedata-fyi/"
                    "actions/runs/123"
                ),
                summary_path=path,
                summary=self.summary(),
                ledger_items=[item],
                run_error_code="none",
            )
            written = json.loads(path.read_text())

        self.assertTrue(ok)
        self.assertEqual(written["pending_remaining"], 7)
        self.assertEqual(len(client.calls), 1)
        name, payload = client.calls[0]
        self.assertEqual(name, "record_pipeline_extraction_run")
        self.assertEqual(payload["p_trigger"], "dispatch")
        self.assertEqual(payload["p_items"], [item])
        self.assertNotIn("action", payload["p_items"][0])

    def test_ledger_failure_is_visible_but_summary_survives(self) -> None:
        client = FakeRpcClient(error=RuntimeError("RPC denied"))
        item = {
            "ordinal": 1,
            "document_id": "00000000-0000-0000-0000-000000000001",
            "school_id": "harvey-mudd-college",
            "school_name": "Harvey Mudd College",
            "canonical_year": "2025-26",
            "occurred_at": "2026-09-12T12:00:30+00:00",
            "outcome": "extracted",
            "source_format": "pdf_flat",
            "extraction_tier": "tier4",
            "field_count": 120,
            "failure_code": "none",
        }
        with tempfile.TemporaryDirectory() as tmp, patch(
            "worker.time.sleep",
        ):
            path = Path(tmp) / "summary.json"
            ok = finalize_extraction_run(
                client,  # type: ignore[arg-type]
                run_id="00000000-0000-0000-0000-000000000099",
                trigger="schedule",
                run_url=(
                    "https://github.com/bolewood/collegedata-fyi/"
                    "actions/runs/123?token=private"
                ),
                summary_path=path,
                summary=self.summary(),
                ledger_items=[item],
                run_error_code="none",
            )
            self.assertTrue(path.exists())
            replay = json.loads((path.parent / "ledger-replay.json").read_text())
        self.assertFalse(ok)
        self.assertEqual(len(client.calls), 3)
        self.assertEqual(replay["p_items"], [item])
        self.assertIsNone(replay["p_run_url"])

    def test_transient_writer_failure_retries_same_run_payload(self) -> None:
        client = FakeRpcClient(
            error=RuntimeError("temporary outage"),
            failures_before_success=2,
        )
        with patch("worker.time.sleep"):
            ok = finalize_extraction_run(
                client,  # type: ignore[arg-type]
                run_id="00000000-0000-0000-0000-000000000099",
                trigger="schedule",
                run_url=None,
                summary_path=None,
                summary=self.summary(),
                ledger_items=[],
                run_error_code="none",
            )
        self.assertTrue(ok)
        self.assertEqual(len(client.calls), 3)
        self.assertEqual(
            {json.dumps(payload, sort_keys=True) for _name, payload in client.calls},
            {json.dumps(client.calls[0][1], sort_keys=True)},
        )

    def test_summary_write_failure_happens_after_durable_rpc(self) -> None:
        client = FakeRpcClient()
        with patch("worker.write_run_summary", side_effect=OSError("disk full")):
            ok = finalize_extraction_run(
                client,  # type: ignore[arg-type]
                run_id="00000000-0000-0000-0000-000000000099",
                trigger="schedule",
                run_url=None,
                summary_path=Path("/unwritable/summary.json"),
                summary=self.summary(),
                ledger_items=[],
                run_error_code="none",
            )
        self.assertFalse(ok)
        self.assertEqual(len(client.calls), 1)

    def test_replay_rejects_unknown_keys_before_rpc(self) -> None:
        client = FakeRpcClient()
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "ledger-replay.json"
            path.write_text(json.dumps({"p_run_id": "x", "action": "raw"}))
            with self.assertRaises(ValueError):
                replay_extraction_ledger(client, path)  # type: ignore[arg-type]
        self.assertEqual(client.calls, [])


class ExtractionLedgerMainIntegrationTests(unittest.TestCase):
    def run_main(self, docs: list[dict], *extra_args: str):
        client = FakeMainClient(docs)
        finalized: list[dict] = []

        def capture_finalize(_client, **kwargs):
            finalized.append(kwargs)
            return True

        with tempfile.TemporaryDirectory() as tmp:
            with (
                patch(
                    "sys.argv",
                    ["worker.py", "--env", f"{tmp}/.env", *extra_args],
                ),
                patch.object(
                    worker,
                    "load_env",
                    return_value={
                        "SUPABASE_URL": "https://example.supabase.co",
                        "SUPABASE_SERVICE_ROLE_KEY": "test-role",
                    },
                ),
                patch.object(worker, "create_client", return_value=client),
                patch.object(
                    worker,
                    "load_schema_registry",
                    return_value={
                        "2025-26": (
                            Path(tmp) / "schema.json",
                            {"schema_version": "2025-26", "fields": []},
                        )
                    },
                ),
                patch.object(
                    worker,
                    "build_cell_maps_for_schemas",
                    return_value={},
                ),
                patch.object(worker, "count_extraction_pending", return_value=0),
                patch.object(
                    worker,
                    "finalize_extraction_run",
                    side_effect=capture_finalize,
                ),
            ):
                return worker.main(), finalized

    def test_empty_run_is_still_finalized(self) -> None:
        returncode, finalized = self.run_main([], "--skip-projection-refresh")
        self.assertEqual(returncode, 0)
        self.assertEqual(len(finalized), 1)
        self.assertEqual(finalized[0]["ledger_items"], [])
        self.assertEqual(finalized[0]["summary"]["stopped_reason"], "complete")
        self.assertEqual(finalized[0]["trigger"], "operator")

    def test_force_reextract_run_records_normalized_file_outcome(self) -> None:
        doc = {
            "id": "00000000-0000-0000-0000-000000000001",
            "school_id": "harvey-mudd-college",
            "cds_year": "2025-26",
            "detected_year": "2025-26",
            "source_format": "pdf_flat",
            "extraction_status": "extraction_pending",
            "discovered_at": "2026-09-12T00:00:00+00:00",
            "source_sha256": "private-hash",
        }
        def corrected_extract(_client, selected_doc, *_args, **_kwargs):
            selected_doc["source_format"] = "html"
            return worker.extraction_success("tier6_extracted (42 fields)")

        with patch.object(worker, "extract_one", side_effect=corrected_extract):
            returncode, finalized = self.run_main(
                [doc],
                "--skip-projection-refresh",
                "--force-reextract",
                "--trigger",
                "dispatch",
                "--run-url",
                "https://github.com/bolewood/collegedata-fyi/actions/runs/123",
            )
        self.assertEqual(returncode, 0)
        item = finalized[0]["ledger_items"][0]
        self.assertEqual(item["outcome"], "re_extracted")
        self.assertEqual(item["field_count"], 42)
        self.assertEqual(item["source_format"], "html")
        self.assertEqual(item["extraction_tier"], "tier6")
        self.assertNotIn("source_sha256", item)
        self.assertEqual(finalized[0]["trigger"], "dispatch")

    def test_ledger_item_prefers_detected_year_over_archive_sentinel(self) -> None:
        item = extraction_ledger_item(
            {
                "id": "00000000-0000-0000-0000-000000000001",
                "school_id": "harvey-mudd-college",
                "cds_year": "unknown",
                "detected_year": "2025-26",
                "source_format": "pdf_flat",
            },
            "tier4_extracted (10 fields)",
            ordinal=1,
            force_reextract=False,
        )
        self.assertEqual(item["canonical_year"], "2025-26")

    def test_reconcile_projection_failure_finalizes_red_run(self) -> None:
        doc = {
            "id": "00000000-0000-0000-0000-000000000001",
            "school_id": "harvey-mudd-college",
            "cds_year": "2025-26",
            "detected_year": "2025-26",
            "source_format": "pdf_flat",
            "extraction_status": "extraction_pending",
            "discovered_at": "2026-09-12T00:00:00+00:00",
            "source_sha256": "private-hash",
        }
        with patch.object(
            worker,
            "reconcile_pending_documents",
            return_value=(
                {doc["id"]},
                worker.Counter({"reconciled": 1, "projection_errors": 1}),
            ),
        ):
            returncode, finalized = self.run_main(
                [doc],
                "--skip-projection-refresh",
                "--reconcile-pending",
            )
        self.assertEqual(returncode, 2)
        self.assertEqual(finalized[0]["summary"]["stopped_reason"], "error")
        self.assertEqual(finalized[0]["run_error_code"], "projection_error")
        self.assertEqual(
            finalized[0]["ledger_items"][0]["outcome"],
            "reconciled",
        )

    def test_reconcile_then_extract_uses_contiguous_ordinals(self) -> None:
        reconciled_a = {
            "id": "00000000-0000-0000-0000-000000000001",
            "school_id": "harvey-mudd-college",
            "school_name": "Harvey Mudd College",
            "cds_year": "2025-26",
            "detected_year": "2025-26",
            "source_format": "pdf_flat",
            "extraction_status": "extraction_pending",
            "discovered_at": "2026-09-12T00:00:00+00:00",
        }
        reconciled_b = {
            **reconciled_a,
            "id": "00000000-0000-0000-0000-000000000002",
            "cds_year": "2024-25",
            "detected_year": "2024-25",
        }
        leftover = {
            **reconciled_a,
            "id": "00000000-0000-0000-0000-000000000003",
            "school_id": "pomona-college",
            "school_name": "Pomona College",
        }
        with (
            patch.object(
                worker,
                "reconcile_pending_documents",
                return_value=(
                    {reconciled_a["id"], reconciled_b["id"]},
                    worker.Counter({"reconciled": 2}),
                ),
            ),
            patch.object(
                worker,
                "extract_one",
                return_value=worker.extraction_success("tier4_extracted (10 fields)"),
            ),
        ):
            returncode, finalized = self.run_main(
                [reconciled_a, reconciled_b, leftover],
                "--skip-projection-refresh",
                "--reconcile-pending",
            )
        self.assertEqual(returncode, 0)
        ordinals = [item["ordinal"] for item in finalized[0]["ledger_items"]]
        self.assertEqual(ordinals, [1, 2, 3])
        self.assertEqual(
            [item["outcome"] for item in finalized[0]["ledger_items"]],
            ["reconciled", "reconciled", "extracted"],
        )

    def test_document_failure_is_normalized_and_returns_failure_exit(self) -> None:
        doc = {
            "id": "00000000-0000-0000-0000-000000000001",
            "school_id": "harvey-mudd-college",
            "cds_year": "2025-26",
            "detected_year": "2025-26",
            "source_format": "pdf_flat",
            "extraction_status": "extraction_pending",
            "discovered_at": "2026-09-12T00:00:00+00:00",
            "source_sha256": "private-hash",
        }
        with patch.object(
            worker,
            "extract_one",
            return_value=worker.extraction_no_project(
                "download_error: private signed URL expired",
            ),
        ):
            returncode, finalized = self.run_main(
                [doc],
                "--skip-projection-refresh",
            )
        self.assertEqual(returncode, 1)
        item = finalized[0]["ledger_items"][0]
        self.assertEqual(item["outcome"], "failed")
        self.assertEqual(item["failure_code"], "source_download_failed")
        self.assertNotIn("private signed URL", json.dumps(item))

    def test_deadline_stop_finalizes_without_opening_unprocessed_item(self) -> None:
        doc = {
            "id": "00000000-0000-0000-0000-000000000001",
            "school_id": "harvey-mudd-college",
            "cds_year": "2025-26",
            "detected_year": "2025-26",
            "source_format": "pdf_flat",
            "extraction_status": "extraction_pending",
            "discovered_at": "2026-09-12T00:00:00+00:00",
            "source_sha256": "private-hash",
        }
        start = datetime(2026, 9, 12, 12, 0, tzinfo=timezone.utc)
        with patch.object(
            worker,
            "utc_now",
            side_effect=[
                start,
                start,
                start + timedelta(minutes=1),
                start + timedelta(minutes=1),
            ],
        ):
            returncode, finalized = self.run_main(
                [doc],
                "--skip-projection-refresh",
                "--deadline-minutes",
                "0.5",
            )
        self.assertEqual(returncode, 0)
        self.assertEqual(finalized[0]["summary"]["stopped_reason"], "deadline")
        self.assertEqual(finalized[0]["ledger_items"], [])


if __name__ == "__main__":
    unittest.main()
