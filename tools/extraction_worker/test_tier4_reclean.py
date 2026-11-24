"""Tests for re-cleaning a stored Tier 4 conversion (worker --reclean).

``tier4_extractor.reclean`` builds an artifact from the markdown an earlier
artifact stored, reading the PDF again only for its text layer.
``worker.stored_tier4_conversion`` finds that earlier artifact, and
``worker._run_tier4`` takes this path when ``RECLEAN`` is set.
"""

from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import tier4_cleaner
import tier4_extractor
import worker

SHA = "sha-current"
EXTRACT_KEYS = {
    "producer", "producer_version", "schema_version", "schema_fallback_used", "docling_config",
    "source_pdf", "extracted_at", "stats", "markdown", "native_tables", "values",
}
CONVERSION = {
    "artifact_id": "artifact-a",
    "producer_version": "0.3.36",
    "converted_at": "2026-11-23T10:00:00Z",
    "markdown": "## C1\n| Total applied | 100 |",
    "native_tables": {"table_count": 2, "cell_count": 9, "tables": []},
    "docling_config": {"name": "production-fast-no-orphan-clusters", "package_versions": {"docling": "2.148.0"}},
    "page_count": 31,
}


class RecleanArtifact(unittest.TestCase):
    def reclean(self, *, needs_ocr=False, force_ocr=False, conversion=CONVERSION):
        calls = []

        def fake_clean(markdown, schema=None, supplemental_text=None):
            calls.append((markdown, supplemental_text))
            return {"C.117": {"value": "100"}, "C.118": {"value": "40"}}

        ocr = mock.Mock(return_value=("OCR TEXT", [12]))
        with mock.patch.object(tier4_cleaner, "clean", fake_clean), \
                mock.patch.object(tier4_extractor, "_extract_pdf_layout_text", return_value="LAYOUT TEXT"), \
                mock.patch.object(tier4_extractor, "_needs_visual_ocr_supplement", return_value=needs_ocr), \
                mock.patch.object(tier4_extractor, "_missing_visual_ocr_tools", return_value=[]), \
                mock.patch.object(tier4_extractor, "_extract_visual_ocr_text", ocr):
            artifact = tier4_extractor.reclean(
                Path("/tmp/source.pdf"), conversion, force_ocr=force_ocr,
                schema=None, schema_version="2024-25", schema_fallback_used=False,
            )
        return artifact, calls, ocr

    def test_reuses_the_conversion_and_reads_only_the_text_layer(self) -> None:
        artifact, calls, ocr = self.reclean()
        self.assertEqual(calls, [(CONVERSION["markdown"], "LAYOUT TEXT")])
        ocr.assert_not_called()
        self.assertEqual(set(artifact), EXTRACT_KEYS | {"conversion"})
        self.assertEqual(artifact["producer"], "tier4_docling")
        self.assertEqual(artifact["producer_version"], tier4_extractor.PRODUCER_VERSION)
        self.assertEqual(artifact["schema_version"], "2024-25")
        self.assertEqual(artifact["markdown"], CONVERSION["markdown"])
        self.assertEqual(artifact["native_tables"], CONVERSION["native_tables"])
        self.assertEqual(artifact["docling_config"], CONVERSION["docling_config"])
        self.assertEqual(artifact["conversion"], {
            "reused": True, "from_artifact_id": "artifact-a",
            "from_producer_version": "0.3.36", "converted_at": "2026-11-23T10:00:00Z",
        })
        self.assertEqual(artifact["stats"]["schema_fields_populated"], 2)
        self.assertEqual(artifact["stats"]["page_count"], 31)
        self.assertEqual(artifact["stats"]["native_table_count"], 2)
        self.assertEqual(artifact["stats"]["native_table_cell_count"], 9)
        self.assertEqual(artifact["stats"]["pdf_layout_text_length"], len("LAYOUT TEXT"))

    def test_ocr_supplement_runs_as_in_a_full_extraction(self) -> None:
        artifact, calls, ocr = self.reclean(needs_ocr=True, force_ocr=True)
        self.assertEqual([text for _, text in calls], ["LAYOUT TEXT", "OCR TEXT\n\nLAYOUT TEXT"])
        ocr.assert_called_once_with(Path("/tmp/source.pdf"), fallback_page_count=31)
        self.assertEqual(artifact["stats"]["visual_ocr_pages"], [12])
        self.assertEqual(artifact["stats"]["visual_ocr_text_length"], len("OCR TEXT"))

    def test_a_text_pdf_does_not_get_the_scanned_page_fallback(self) -> None:
        _, _, ocr = self.reclean(needs_ocr=True, force_ocr=False)
        ocr.assert_called_once_with(Path("/tmp/source.pdf"), fallback_page_count=None)

    def test_a_conversion_without_markdown_is_refused(self) -> None:
        with self.assertRaises(ValueError):
            self.reclean(conversion={**CONVERSION, "markdown": "  "})

    def test_extract_and_reclean_share_one_cleaning_step(self) -> None:
        # extract() must not grow a second copy of the supplement logic: the
        # two paths stay equal only while both call this helper.
        import inspect
        for function in (tier4_extractor.extract, tier4_extractor.reclean):
            self.assertIn("_clean_with_supplements(", inspect.getsource(function))


def _resolve(row, column):
    """One PostgREST select item against a stored row: `alias:notes->a->>b`."""
    alias, _, path = column.rpartition(":")
    parts = path.replace("->>", "->").split("->")
    value = row
    for part in parts:
        value = value.get(part) if isinstance(value, dict) else None
    return (alias or parts[-1]), value


class _Query:
    def __init__(self, client, rows):
        self.client, self.rows, self.filters, self.columns = client, rows, {}, []
        self.write = None

    def select(self, columns):
        self.columns = [c.strip() for c in columns.split(",")]
        return self

    def eq(self, column, value):
        self.filters[column] = value
        return self

    def in_(self, column, values):
        return self

    def is_(self, column, value):
        return self

    def limit(self, _):
        return self

    def insert(self, row):
        self.write = ("insert", row)
        return self

    def update(self, row):
        self.write = ("update", row)
        return self

    def execute(self):
        if self.write:
            self.client.writes.append((self.table, *self.write))
            return SimpleNamespace(data=[])
        rows = [r for r in self.rows if all(r.get(k) == v for k, v in self.filters.items())]
        return SimpleNamespace(data=[dict(_resolve(r, c) for c in self.columns) for r in rows])


class _Client:
    """Serves cds_artifacts rows as stored (columns plus a nested `notes`), so a
    wrong JSON path in a select returns nothing. Records every write."""

    def __init__(self, rows):
        self.rows, self.writes = rows, []

    def table(self, name):
        query = _Query(self, self.rows if name == "cds_artifacts" else [])
        query.table = name
        return query


CONFIG = {"name": tier4_extractor.DOCLING_CONFIG_NAME, "force_ocr": False}


def _artifact(artifact_id, created_at, *, source_sha=SHA, producer="tier4_docling", version="0.3.36",
              markdown="stored markdown", conversion=None, source_artifact_sha=None, config=CONFIG,
              values=None, schema_version="2024-25", fallback_used=None):
    notes = {
        "markdown": markdown, "native_tables": {"table_count": 1, "cell_count": 4},
        "docling_config": config, "stats": {"page_count": 20},
        "extracted_at": created_at.replace("+00:00", "Z"),
    }
    if source_sha:
        notes["source_sha256"] = source_sha
    if source_artifact_sha:
        notes["source_artifact"] = {"sha256": source_artifact_sha}
    if conversion:
        notes["conversion"] = conversion
    if values is not None:
        notes["values"] = values
    if fallback_used is not None:
        notes["schema_fallback_used"] = fallback_used
    return {"id": artifact_id, "document_id": "doc", "kind": "canonical", "producer": producer,
            "producer_version": version, "schema_version": schema_version, "created_at": created_at,
            "notes": notes}


class StoredConversion(unittest.TestCase):
    def find(self, rows, sha=SHA):
        return worker.stored_tier4_conversion(_Client(rows), "doc", sha)

    def test_newest_tier4_artifact_of_the_same_file(self) -> None:
        got = self.find([
            _artifact("old", "2026-05-01T00:00:00+00:00", version="0.3.11", markdown="old markdown"),
            _artifact("new", "2026-11-23T10:00:00+00:00"),
            _artifact("other-file", "2026-11-24T00:00:00+00:00", source_sha="sha-other"),
            _artifact("xlsx", "2026-11-25T00:00:00+00:00", producer="tier1_xlsx"),
        ])
        self.assertEqual(got["artifact_id"], "new")
        self.assertEqual(got["producer_version"], "0.3.36")
        self.assertEqual(got["converted_at"], "2026-11-23T10:00:00Z")
        self.assertEqual(got["markdown"], "stored markdown")
        self.assertEqual(got["page_count"], 20)
        self.assertEqual(got["native_tables"], {"table_count": 1, "cell_count": 4})
        self.assertEqual(got["docling_config"], CONFIG)

    def test_source_recorded_only_under_source_artifact(self) -> None:
        got = self.find([_artifact("a", "2026-11-01T00:00:00+00:00", source_sha=None, source_artifact_sha=SHA)])
        self.assertEqual(got["artifact_id"], "a")

    def test_an_artifact_that_records_no_source_is_not_reused(self) -> None:
        self.assertIsNone(self.find([_artifact("a", "2026-04-27T00:00:00+00:00", source_sha=None)]))

    def test_nothing_to_reuse(self) -> None:
        self.assertIsNone(self.find([]))
        self.assertIsNone(self.find([_artifact("a", "2026-11-01T00:00:00+00:00")], sha=None))
        self.assertIsNone(self.find([_artifact("a", "2026-11-01T00:00:00+00:00", markdown="")]))
        self.assertIsNone(self.find([_artifact("a", "2026-11-01T00:00:00+00:00", source_sha="sha-other")]))

    def test_a_recleaned_artifact_points_back_to_the_real_conversion(self) -> None:
        got = self.find([_artifact(
            "second", "2026-12-01T00:00:00+00:00", version="0.3.38",
            conversion={"reused": True, "from_artifact_id": "first", "from_producer_version": "0.3.36",
                        "converted_at": "2026-11-23T10:00:00Z"},
        )])
        self.assertEqual(
            (got["artifact_id"], got["producer_version"], got["converted_at"]),
            ("first", "0.3.36", "2026-11-23T10:00:00Z"),
        )


class RunTier4WithReclean(unittest.TestCase):
    RESOLUTION = SimpleNamespace(
        schema_version="2024-25", fallback_used=False, fallback_reason=None, canonical_year="2024-25")

    def setUp(self) -> None:
        patcher = mock.patch.object(worker, "RECLEAN", True)
        patcher.start()
        self.addCleanup(patcher.stop)

    def run_tier4(self, rows, *, source_format="pdf_flat", dry_run=True, client=None, **patches):
        client = client or _Client(rows)
        with mock.patch.multiple(tier4_extractor, **patches):
            outcome = worker._run_tier4(
                client, "doc", "example", b"%PDF", source_format, self.RESOLUTION, None,
                {"sha256": SHA, "storage_path": "example/2024-25/a.pdf"}, dry_run=dry_run,
            )
        return outcome

    def test_no_stored_conversion_skips_without_converting(self) -> None:
        convert, reclean = mock.Mock(), mock.Mock()
        outcome = self.run_tier4([], extract_from_bytes=convert, reclean_from_bytes=reclean)
        self.assertTrue(outcome.action.startswith("tier4_reclean_skipped ("))
        self.assertFalse(outcome.refresh_projection)
        convert.assert_not_called()
        reclean.assert_not_called()
        self.assertFalse(worker.is_failure_action(outcome.action))
        self.assertTrue(worker.is_reclean_skip(outcome.action))

    def test_a_conversion_made_with_other_settings_is_skipped(self) -> None:
        cases = [
            # A scanned PDF whose stored conversion ran without full-page OCR.
            ("pdf_scanned", CONFIG, "different OCR mode"),
            ("pdf_flat", {**CONFIG, "force_ocr": True}, "different OCR mode"),
            ("pdf_flat", {"name": "an-older-config", "force_ocr": False}, "other Docling settings"),
            ("pdf_flat", None, "other Docling settings"),
        ]
        for source_format, config, reason in cases:
            with self.subTest(source_format=source_format, config=config):
                convert, reclean = mock.Mock(), mock.Mock()
                outcome = self.run_tier4(
                    [_artifact("a", "2026-11-23T10:00:00+00:00", config=config)],
                    source_format=source_format, extract_from_bytes=convert, reclean_from_bytes=reclean,
                )
                self.assertTrue(worker.is_reclean_skip(outcome.action), outcome.action)
                self.assertIn(reason, outcome.action)
                convert.assert_not_called()
                reclean.assert_not_called()

    def test_a_scanned_pdf_is_recleaned_with_full_page_ocr_settings(self) -> None:
        artifact = {"producer": "tier4_docling", "producer_version": "9.9.9", "schema_version": "2024-25",
                    "stats": {"schema_fields_populated": 200}, "values": {}, "markdown": "m"}
        reclean = mock.Mock(return_value=artifact)
        self.run_tier4(
            [_artifact("a", "2026-11-23T10:00:00+00:00", config={**CONFIG, "force_ocr": True})],
            source_format="pdf_scanned", extract_from_bytes=mock.Mock(), reclean_from_bytes=reclean,
        )
        self.assertTrue(reclean.call_args.kwargs["force_ocr"])

    def test_a_recleaned_artifact_takes_the_guards_and_the_write_path(self) -> None:
        artifact = {"producer": "tier4_docling", "producer_version": "9.9.9", "schema_version": "2024-25",
                    "stats": {"schema_fields_populated": 321, "page_count": 20},
                    "values": {"C.117": {"value": "10"}}, "markdown": "stored markdown",
                    "conversion": {"reused": True, "from_artifact_id": "a"}}
        client = _Client([_artifact("a", "2026-11-23T10:00:00+00:00")])
        guards = {name: mock.Mock(return_value=None) for name in (
            "field_collapse_action", "field_regression_action", "headline_regression_action",
            "table_regression_action", "previous_canonical")}
        with mock.patch.multiple(worker, artifact_already_extracted=mock.Mock(return_value=False),
                                 extraction_quality_flag=mock.Mock(return_value=None), **guards):
            outcome = self.run_tier4(
                [], client=client, dry_run=False,
                extract_from_bytes=mock.Mock(), reclean_from_bytes=mock.Mock(return_value=artifact),
            )
        self.assertTrue(outcome.action.startswith("tier4_recleaned ("))
        self.assertTrue(outcome.refresh_projection)
        for name in ("field_collapse_action", "field_regression_action", "headline_regression_action",
                     "table_regression_action"):
            guards[name].assert_called_once()
        self.assertIs(guards["field_collapse_action"].call_args.args[3], artifact)
        # The count guard is handed the loader for the previous extraction,
        # and the two later guards share its one read.
        load_previous = guards["field_regression_action"].call_args.args[5]
        self.assertIs(load_previous(), guards["previous_canonical"].return_value)
        guards["previous_canonical"].assert_called_once()
        inserts = [w for w in client.writes if w[1] == "insert"]
        self.assertEqual(len(inserts), 1)
        self.assertEqual(inserts[0][0], "cds_artifacts")
        self.assertEqual(inserts[0][2]["notes"]["conversion"]["from_artifact_id"], "a")
        self.assertEqual(inserts[0][2]["notes"]["source_sha256"], SHA)
        self.assertEqual(inserts[0][2]["producer_version"], "9.9.9")

    def test_a_held_reclean_writes_no_artifact(self) -> None:
        artifact = {"producer": "tier4_docling", "producer_version": "9.9.9", "schema_version": "2024-25",
                    "stats": {"schema_fields_populated": 100}, "values": {}, "markdown": "stored markdown"}
        client = _Client([_artifact("a", "2026-11-23T10:00:00+00:00")])
        held = "tier4_field_regression (100 < 400 fields; kept)"
        with mock.patch.multiple(worker, artifact_already_extracted=mock.Mock(return_value=False),
                                 extraction_quality_flag=mock.Mock(return_value=None),
                                 field_collapse_action=mock.Mock(return_value=None),
                                 field_regression_action=mock.Mock(return_value=held)):
            outcome = self.run_tier4(
                [], client=client, dry_run=False,
                extract_from_bytes=mock.Mock(), reclean_from_bytes=mock.Mock(return_value=artifact),
            )
        self.assertEqual(outcome.action, held)
        self.assertEqual([w for w in client.writes if w[1] == "insert"], [])

    def test_a_stored_conversion_is_recleaned_not_converted(self) -> None:
        artifact = {"producer": "tier4_docling", "producer_version": "9.9.9", "schema_version": "2024-25",
                    "stats": {"schema_fields_populated": 321, "markdown_length": 15, "page_count": 20},
                    "values": {}, "markdown": "stored markdown"}
        convert, reclean = mock.Mock(), mock.Mock(return_value=artifact)
        outcome = self.run_tier4(
            [_artifact("a", "2026-11-23T10:00:00+00:00")],
            extract_from_bytes=convert, reclean_from_bytes=reclean,
        )
        convert.assert_not_called()
        self.assertEqual(reclean.call_args.args[1]["artifact_id"], "a")
        self.assertEqual(reclean.call_args.kwargs["schema_version"], "2024-25")
        self.assertEqual(outcome.action, "tier4_recleaned (321 fields, 15 chars, 20 pages)")
        self.assertEqual(artifact["source_sha256"], SHA)  # the same source metadata a conversion gets
        self.assertEqual(worker.parsed_field_count(outcome.action), 321)

    def test_a_failed_lookup_is_an_error_not_a_conversion(self) -> None:
        convert = mock.Mock()
        with mock.patch.object(worker, "stored_tier4_conversion", side_effect=RuntimeError("timeout")):
            outcome = self.run_tier4([], extract_from_bytes=convert, reclean_from_bytes=mock.Mock())
        self.assertEqual(outcome.action, "tier4_reclean_error: timeout")
        self.assertTrue(worker.is_failure_action(outcome.action))
        convert.assert_not_called()

    def test_without_the_switch_the_pdf_is_converted(self) -> None:
        artifact = {"producer": "tier4_docling", "producer_version": "9.9.9", "schema_version": "2024-25",
                    "stats": {"schema_fields_populated": 5}, "values": {}, "markdown": ""}
        convert, reclean = mock.Mock(return_value=artifact), mock.Mock()
        with mock.patch.object(worker, "RECLEAN", False):
            outcome = self.run_tier4(
                [_artifact("a", "2026-11-23T10:00:00+00:00")],
                extract_from_bytes=convert, reclean_from_bytes=reclean,
            )
        convert.assert_called_once()
        reclean.assert_not_called()
        self.assertTrue(outcome.action.startswith("tier4_extracted ("))


class RecleanUnchanged(unittest.TestCase):
    """A re-clean that reads what the stored extraction already holds writes nothing."""

    RESOLUTION = RunTier4WithReclean.RESOLUTION
    VALUES = {"C.117": {"value": "100", "source": "tier4_cleaner"},
              "C.118": {"value": "40", "source": "tier4_cleaner"}}

    def setUp(self) -> None:
        patcher = mock.patch.object(worker, "RECLEAN", True)
        patcher.start()
        self.addCleanup(patcher.stop)

    def run_tier4(self, stored_values, new_values, *, dry_run=False, stored_schema="2024-25", guards=None,
                  newer=()):
        new = {"producer": "tier4_docling", "producer_version": "9.9.9", "schema_version": "2024-25",
               "schema_fallback_used": False,
               "stats": {"schema_fields_populated": len(new_values), "markdown_length": 15, "page_count": 20},
               "values": new_values, "markdown": "stored markdown"}
        client = _Client([_artifact("a", "2026-11-23T10:00:00+00:00", values=stored_values,
                                    schema_version=stored_schema), *newer])
        guards = guards or {name: mock.Mock(return_value=None) for name in (
            "field_collapse_action", "field_regression_action", "headline_regression_action",
            "table_regression_action")}
        with mock.patch.multiple(worker, artifact_already_extracted=mock.Mock(return_value=False),
                                 extraction_quality_flag=mock.Mock(return_value="low_coverage"), **guards), \
                mock.patch.multiple(tier4_extractor, extract_from_bytes=mock.Mock(),
                                    reclean_from_bytes=mock.Mock(return_value=new)):
            outcome = worker._run_tier4(
                client, "doc", "example", b"%PDF", "pdf_flat", self.RESOLUTION, None,
                {"sha256": SHA, "storage_path": "example/2024-25/a.pdf"}, dry_run=dry_run,
                force_reextract=True,
            )
        return outcome, client, guards

    def test_the_same_values_write_no_artifact(self) -> None:
        outcome, client, guards = self.run_tier4(self.VALUES, dict(self.VALUES))
        self.assertEqual(
            outcome.action,
            "tier4_reclean_unchanged (2 fields; cleaner 9.9.9 reads what is stored)",
        )
        self.assertFalse(outcome.refresh_projection)
        self.assertEqual([w for w in client.writes if w[1] == "insert"], [])
        # The status is confirmed; the flag is left as it is, though the rule
        # would set one on this artifact.
        self.assertEqual([(w[0], sorted(w[2])) for w in client.writes], [
            ("cds_documents", ["extraction_status", "source_format"]),
            ("cds_documents", ["extracted_at"]),  # set only where it is still null
        ])
        self.assertEqual(client.writes[0][2]["extraction_status"], "extracted")
        self.assertTrue(all("data_quality_flag" not in w[2] for w in client.writes))
        for guard in guards.values():
            guard.assert_not_called()

    def test_any_difference_takes_the_guards_and_is_written(self) -> None:
        cases = {
            "a changed value": {**self.VALUES, "C.118": {"value": "41", "source": "tier4_cleaner"}},
            "an added field": {**self.VALUES, "C.119": {"value": "9", "source": "tier4_cleaner"}},
            "a removed field": {"C.117": self.VALUES["C.117"]},
            "a changed record": {**self.VALUES, "C.118": {"value": "40", "source": "tier4_text"}},
        }
        for name, new_values in cases.items():
            with self.subTest(name):
                outcome, client, guards = self.run_tier4(self.VALUES, new_values)
                self.assertTrue(outcome.action.startswith("tier4_recleaned ("), outcome.action)
                self.assertEqual(len([w for w in client.writes if w[1] == "insert"]), 1)
                guards["table_regression_action"].assert_called_once()

    def test_the_same_values_under_another_schema_are_written(self) -> None:
        outcome, client, _ = self.run_tier4(self.VALUES, dict(self.VALUES), stored_schema="2025-26")
        self.assertTrue(outcome.action.startswith("tier4_recleaned ("), outcome.action)
        self.assertEqual(len([w for w in client.writes if w[1] == "insert"]), 1)

    def test_the_same_values_from_an_artifact_that_ranks_differently_are_written(self) -> None:
        # The stored conversion is artifact "a"; the newest artifact of the
        # file holds the same values but would not rank as a new one would.
        cases = {
            "another producer": _artifact("b", "2026-11-24T10:00:00+00:00", producer="tier2_acroform",
                                          values=self.VALUES),
            "a fallback schema": _artifact("b", "2026-11-24T10:00:00+00:00", values=self.VALUES,
                                           fallback_used=True),
        }
        for name, newest in cases.items():
            with self.subTest(name):
                outcome, client, _ = self.run_tier4(self.VALUES, dict(self.VALUES), newer=[newest])
                self.assertTrue(outcome.action.startswith("tier4_recleaned ("), outcome.action)
                self.assertEqual(len([w for w in client.writes if w[1] == "insert"]), 1)
        same = _artifact("b", "2026-11-24T10:00:00+00:00", values=self.VALUES, fallback_used=False)
        outcome, client, _ = self.run_tier4(self.VALUES, dict(self.VALUES), newer=[same])
        self.assertTrue(worker.is_reclean_unchanged(outcome.action), outcome.action)

    def test_a_dry_run_reports_it_and_writes_nothing(self) -> None:
        outcome, client, _ = self.run_tier4(self.VALUES, dict(self.VALUES), dry_run=True)
        self.assertTrue(worker.is_reclean_unchanged(outcome.action))
        self.assertEqual(client.writes, [])
        outcome, client, _ = self.run_tier4(self.VALUES, {"C.117": self.VALUES["C.117"]}, dry_run=True)
        self.assertTrue(outcome.action.startswith("tier4_recleaned ("), outcome.action)
        self.assertEqual(client.writes, [])

    def test_a_conversion_with_the_same_values_is_still_written(self) -> None:
        # Only a re-clean is skipped: a fresh conversion carries new markdown.
        with mock.patch.object(worker, "RECLEAN", False):
            new = {"producer": "tier4_docling", "producer_version": "9.9.9", "schema_version": "2024-25",
                   "stats": {"schema_fields_populated": 2}, "values": dict(self.VALUES), "markdown": "new"}
            client = _Client([_artifact("a", "2026-11-23T10:00:00+00:00", values=self.VALUES)])
            guards = {name: mock.Mock(return_value=None) for name in (
                "field_collapse_action", "field_regression_action", "headline_regression_action",
                "table_regression_action")}
            with mock.patch.multiple(worker, artifact_already_extracted=mock.Mock(return_value=False),
                                     extraction_quality_flag=mock.Mock(return_value=None), **guards), \
                    mock.patch.multiple(tier4_extractor, extract_from_bytes=mock.Mock(return_value=new),
                                        reclean_from_bytes=mock.Mock()):
                outcome = worker._run_tier4(
                    client, "doc", "example", b"%PDF", "pdf_flat", self.RESOLUTION, None,
                    {"sha256": SHA, "storage_path": "example/2024-25/a.pdf"}, dry_run=False,
                    force_reextract=True,
                )
        self.assertTrue(outcome.action.startswith("tier4_extracted ("), outcome.action)
        self.assertEqual(len([w for w in client.writes if w[1] == "insert"]), 1)

    def test_values_are_compared_as_they_would_be_stored(self) -> None:
        stored = {"A.1": {"value": "ab", "source": "tier4_cleaner"}, "B.1": {"value": 3, "parts": [1, 2]}}
        # A null byte is stripped on the way in; a tuple is stored as a list.
        new = {"A.1": {"value": "a\x00b", "source": "tier4_cleaner"}, "B.1": {"value": 3, "parts": (1, 2)}}
        previous = worker.PreviousCanonical(("2024-25", stored))
        previous.producer = "tier4_docling"

        def same(previous, schema_version="2024-25", values=new):
            return worker.reclean_unchanged(
                previous, {"producer": "tier4_docling", "schema_version": schema_version, "values": values})

        self.assertTrue(same(previous))
        self.assertFalse(same(None))
        self.assertFalse(same(previous, schema_version="2023-24"))
        self.assertFalse(same(previous, values=None))
        self.assertFalse(same(previous, values={"A.1": {1, 2}}))
        # A bare pair names no producer, so it cannot be called the same.
        self.assertFalse(same(("2024-25", stored)))


class RunAccounting(unittest.TestCase):
    def test_an_unchanged_reclean_is_current_not_re_extracted(self) -> None:
        wrap = "tier2_label_acroform_fallback_"
        unchanged = "tier4_reclean_unchanged (412 fields; cleaner 0.3.42 reads what is stored)"
        for prefix in ("", wrap):
            action = prefix + unchanged
            self.assertTrue(worker.is_reclean_unchanged(action))
            self.assertFalse(worker.is_reclean_skip(action))
            self.assertFalse(worker.is_failure_action(action))
            self.assertEqual(worker.parsed_field_count(action), 412)
            self.assertEqual(worker.extraction_ledger_outcome(action, force_reextract=True), "already_current")
            self.assertEqual(worker.extraction_ledger_failure_code(action), "none")
        self.assertFalse(worker.is_reclean_unchanged("tier4_recleaned (412 fields, 15 chars, 20 pages)"))
        self.assertFalse(worker.is_reclean_unchanged("tier4_reclean_skipped (no stored conversion of the current file)"))

    def test_action_names_wrapped_by_the_fillable_pdf_fallback(self) -> None:
        wrap = "tier2_label_acroform_fallback_"
        skipped = "tier4_reclean_skipped (no stored conversion of the current file)"
        done = "tier4_recleaned (321 fields, 15 chars, 20 pages)"
        error = "tier4_reclean_error: timeout"
        for prefix in ("", wrap):
            self.assertTrue(worker.is_reclean_skip(prefix + skipped))
            self.assertFalse(worker.is_failure_action(prefix + skipped))
            self.assertFalse(worker.is_reclean_skip(prefix + done))
            self.assertFalse(worker.is_failure_action(prefix + done))
            self.assertEqual(worker.parsed_field_count(prefix + done), 321)
            self.assertEqual(worker.extraction_ledger_outcome(prefix + done, force_reextract=True), "re_extracted")
            self.assertTrue(worker.is_failure_action(prefix + error))
            self.assertFalse(worker.is_reclean_skip(prefix + error))
        self.assertFalse(worker.is_reclean_skip("tier4_extracted (10 fields, 5 chars, 1 pages)"))
        self.assertFalse(worker.is_reclean_skip("already_extracted"))

    def test_documents_are_kept_an_interval_apart(self) -> None:
        slept = []
        self.assertEqual(worker.reclean_pause(100.0, 8.0, sleep=slept.append, now=lambda: 101.5), 6.5)
        self.assertEqual(slept, [6.5])
        self.assertEqual(worker.reclean_pause(100.0, 8.0, sleep=slept.append, now=lambda: 140.0), 0.0)
        self.assertEqual(slept, [6.5])
        self.assertGreaterEqual(worker.RECLEAN_INTERVAL_SECONDS, 6)

    def test_reclean_needs_named_documents(self) -> None:
        result = subprocess.run(
            [sys.executable, str(Path(worker.__file__)), "--reclean", "--force-reextract"],
            capture_output=True, text=True, timeout=120,
        )
        self.assertEqual(result.returncode, 2)
        self.assertIn("--reclean needs --document-ids or --requeue-document-ids", result.stderr)


if __name__ == "__main__":
    unittest.main()
