"""PRD 038 M3: the overlay worker entry point, its CLI rules, the artifact, and "production unchanged on merge"."""

from __future__ import annotations

import ast
import json
import re
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent))

import overlay_entry as oe  # noqa: E402
import worker  # noqa: E402


# ---- a recording fake client -------------------------------------------------------------------------------

class FakeQuery:
    def __init__(self, client, table):
        self.client, self.table, self.filters, self.op, self.payload = client, table, {}, "select", None

    def select(self, *_a, **_k):
        return self

    def eq(self, key, value):
        self.filters[key] = value
        return self

    def in_(self, key, values):
        self.filters[key] = list(values)
        return self

    def order(self, *_a, **_k):
        return self

    def limit(self, *_a, **_k):
        return self

    def insert(self, payload):
        self.op, self.payload = "insert", payload
        return self

    def update(self, payload):
        self.op, self.payload = "update", payload
        return self

    def upsert(self, payload, **_k):
        self.op, self.payload = "upsert", payload
        return self

    def execute(self):
        self.client.calls.append((self.table, self.op, dict(self.filters), self.payload))
        rows = []
        if self.op == "select":
            for row in self.client.tables.get(self.table, []):
                if all((row.get(k) in v) if isinstance(v, list) else (row.get(k) == v) for k, v in self.filters.items()):
                    rows.append(row)
        return SimpleNamespace(data=rows)


class FakeClient:
    def __init__(self, tables=None):
        self.tables, self.calls = tables or {}, []

    def table(self, name):
        return FakeQuery(self, name)

    def rpc(self, name, *_a, **_k):
        self.calls.append(("rpc", name, {}, None))
        return FakeQuery(self, "rpc")

    def writes(self):
        return [c for c in self.calls if c[1] != "select"]


def _tier4_base(values, sha="S"):
    return {"id": "b1", "document_id": "d1", "kind": "canonical", "producer": "tier4_docling", "producer_version": "0.3.17", "schema_version": "2025-26",
            "created_at": "2026-11-01T00:00:00+00:00", "notes": {"source_sha256": sha, "values": values}}


def _extract_output(values, sha="S"):
    return {
        "producer": oe.OVERLAY_PRODUCER, "producer_version": "0.6.0", "schema_version": "2025-26", "extracted_at": "t",
        "stats": {"schema_fields_populated": len(values)}, "values": values,
        "notes": {"producer_version": "0.6.0", "field_map_version": "1", "source_sha256": sha, "template_year": "2025-26",
                  "stage1": {"status": "matched", "rejected_pages": {"3": "x"}}, "matched_template_pages": 49, "page_map": {"0": 0},
                  "lane_counts": {"text": 2, "ocr": 1}, "emission_class_counts": {"numeric": 1, "ocr_numeric": 1},
                  "rejected_fields": [{"pdf_tag": "A"}], "withheld": [{"pdf_tag": "Q"}], "withheld_by_reason": {"low_confidence": 1},
                  "ocr_engine": {"tesseract": "5.5.3"}, "ocr_models": {"fast": "7d43", "best": "8280"}},
    }


VALUES = {
    "B.101": {"value": "100", "emission_class": "numeric", "lane": "text"},
    "C.300": {"value": "7", "emission_class": "ocr_numeric", "lane": 2},
    "C.301": {"value": "X", "emission_class": "checkbox_boxless", "lane": "text"},
}


@pytest.fixture
def wired(monkeypatch):
    """worker functions faked so run_overlay_for_document runs without a database or a PDF stack."""
    monkeypatch.setattr(worker, "fetch_latest_source_artifact", lambda c, d: {"storage_path": "p", "sha256": "S"})
    monkeypatch.setattr(worker, "download_source", lambda c, p: b"%PDF-fake")
    monkeypatch.setattr(worker, "select_source_for_extraction",
                        lambda c, d, a, b: SimpleNamespace(source_artifact=a, source_bytes=b"%PDF-fake", selection_note={"chosen_sha256": "S"}, needs_review=False))
    monkeypatch.setattr(oe, "stage1_prefilter", lambda b: (True, None, {"page_count": 49}))
    monkeypatch.setattr(oe, "extract_pdf", lambda b, **k: _extract_output(VALUES, sha=__import__("hashlib").sha256(b).hexdigest()))
    for name in ("refresh_browser_projection", "notify_school_revalidation", "mark_extraction_status", "apply_extraction_quality_flag"):
        monkeypatch.setattr(worker, name, lambda *a, **k: pytest.fail("the overlay must not call " + name), raising=False)


# ---- entry point, idempotency, dry run vs write -----------------------------------------------------------

def test_dry_run_writes_nothing_and_write_inserts_only_the_overlay_artifact(wired):
    client = FakeClient({"cds_artifacts": [_tier4_base({"B.101": {"value": "100"}})]})
    dry = oe.run_overlay_for_document(client, {"id": "d1"}, write=False)
    assert dry.status == "dry_run" and client.writes() == []
    done = oe.run_overlay_for_document(client, {"id": "d1"}, write=True)
    assert done.status == "written"
    writes = client.writes()
    assert len(writes) == 1 and writes[0][0] == "cds_artifacts" and writes[0][1] == "insert"
    row = writes[0][3]
    assert row["kind"] == "cleaned" and row["producer"] == "tier2_template_overlay" and row["kind"] != "canonical"
    assert {c[0] for c in client.calls} == {"cds_artifacts"}             # no heartbeat, ledger, status or projection table


def test_artifact_keeps_every_class_and_the_audit_fields(wired):
    client = FakeClient({"cds_artifacts": [_tier4_base({"B.101": {"value": "100"}})]})
    notes = oe.run_overlay_for_document(client, {"id": "d1"}, write=False).artifact_notes
    assert set(notes["values"]) == set(VALUES)                          # numeric, ocr_numeric and checkbox_boxless all written
    assert notes["values"]["C.300"]["lane"] == 2 and notes["values"]["C.300"]["emission_class"] == "ocr_numeric"
    for key in ("producer_version", "field_map_version", "template_year", "source_sha256", "matched_template_pages", "page_map",
                "lane_counts", "rejected_fields", "source_selection", "ocr_engine", "ocr_models", "abstention_by_reason",
                "rejected_pages", "base_artifact_id", "tier4_disagreement_share", "held"):
        assert key in notes, key
    assert notes["abstention_by_reason"] == {"low_confidence": 1} and notes["rejected_pages"] == {"3": "x"}
    assert notes["source_selection"] == {"chosen_sha256": "S"} and notes["base_artifact_id"] == "b1"
    assert notes["held"] is False and notes["tier4_disagreement_share"] == 0.0


def test_hold_when_tier4_disagrees_above_the_threshold_or_there_is_no_base(wired):
    disagree = FakeClient({"cds_artifacts": [_tier4_base({"B.101": {"value": "999"}})]})
    held = oe.run_overlay_for_document(disagree, {"id": "d1"}, write=False).artifact_notes
    assert held["held"] is True and held["tier4_disagreement_share"] == 1.0 and held["hold_reason"] == "tier4_disagreement_share_above_threshold"
    relaxed = oe.run_overlay_for_document(disagree, {"id": "d1"}, write=False, hold_threshold=1.0).artifact_notes
    assert relaxed["held"] is False                                       # the threshold is configurable
    mismatch = FakeClient({"cds_artifacts": [{**_tier4_base({"B.101": {"value": "100"}}), "schema_version": None}]})
    m = oe.run_overlay_for_document(mismatch, {"id": "d1"}, write=False).artifact_notes
    assert m["held"] is True and m["hold_reason"] == "tier4_schema_mismatch" and m["tier4_disagreement_share"] is None
    no_base = oe.run_overlay_for_document(FakeClient({"cds_artifacts": []}), {"id": "d1"}, write=False).artifact_notes
    assert no_base["held"] is True and no_base["hold_reason"] == "no_tier4_base"


def test_own_idempotency_key_skips_a_second_write(wired):
    client = FakeClient({"cds_artifacts": [_tier4_base({"B.101": {"value": "100"}})]})
    first = oe.run_overlay_for_document(client, {"id": "d1"}, write=True)
    row = client.writes()[0][3]
    client.tables["cds_artifacts"].append({**row, "id": "ov1", "document_id": "d1", "kind": "cleaned"})
    again = oe.run_overlay_for_document(client, {"id": "d1"}, write=True)
    assert first.status == "written" and again.status == "skipped" and again.reason == "already_overlaid"
    assert len(client.writes()) == 1
    forced = oe.run_overlay_for_document(client, {"id": "d1"}, write=True, force=True)
    assert forced.status == "written"
    assert oe.idempotency_key("d", "0.6.0", "1", "S") == ("d", "tier2_template_overlay", "0.6.0", "1", "S")


def test_an_injected_overlay_failure_changes_nothing(wired, monkeypatch):
    client = FakeClient({"cds_artifacts": [_tier4_base({"B.101": {"value": "100"}})]})

    def boom(*a, **k):
        raise RuntimeError("injected")

    monkeypatch.setattr(oe, "extract_pdf", boom)
    result = oe.run_overlay_for_document(client, {"id": "d1"}, write=True)
    assert result.status == "error" and "injected" in result.reason
    assert client.writes() == []                                          # no artifact, no status, no flag, no ledger row


# ---- the routine loop: flag off, broken package -----------------------------------------------------------

def test_loop_flag_defaults_off(monkeypatch):
    monkeypatch.delenv("OVERLAY_WORKER_ENABLED", raising=False)
    assert oe.overlay_loop_enabled() is False
    for on in ("1", "true", "YES", "on"):
        assert oe.overlay_loop_enabled({"OVERLAY_WORKER_ENABLED": on}) is True
    assert oe.overlay_loop_enabled({"OVERLAY_WORKER_ENABLED": "0"}) is False


def test_flag_off_never_imports_or_calls_the_overlay(monkeypatch):
    monkeypatch.delenv("OVERLAY_WORKER_ENABLED", raising=False)
    tripwire = SimpleNamespace()
    monkeypatch.setitem(sys.modules, "overlay_entry", tripwire)           # any attribute access would raise AttributeError
    worker.maybe_run_overlay(FakeClient(), {"id": "d1"})                  # returns without touching it


def test_flag_on_with_a_broken_overlay_package_is_logged_and_ignored(monkeypatch, capsys):
    monkeypatch.setenv("OVERLAY_WORKER_ENABLED", "1")
    monkeypatch.setitem(sys.modules, "overlay_entry", None)               # `from overlay_entry import ...` raises ImportError
    client = FakeClient()
    worker.maybe_run_overlay(client, {"id": "d1"})
    assert "overlay_error" in capsys.readouterr().err and client.calls == []
    monkeypatch.setitem(sys.modules, "overlay_entry", SimpleNamespace(run_overlay_in_loop=lambda c, d: (_ for _ in ()).throw(SystemExit(3))))
    worker.maybe_run_overlay(client, {"id": "d1"})                        # even SystemExit from a bad stack is contained


def test_the_daily_drain_imports_none_of_the_overlay_stack():
    code = (
        "import sys\n"
        f"sys.path.insert(0, {str(HERE.parent)!r}); sys.path.insert(0, {str(HERE)!r})\n"
        "import worker\n"
        "bad = [m for m in ('overlay_entry', 'template_overlay', 'lane2_ocr', 'cv2') if m in sys.modules]\n"
        "assert not bad, bad\n"
        "print('clean')\n"
    )
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
    assert out.returncode == 0 and "clean" in out.stdout, out.stderr[-600:]
    tree = ast.parse((HERE / "worker.py").read_text())
    top = [n for n in tree.body if isinstance(n, (ast.Import, ast.ImportFrom))]
    names = {a.name for n in top for a in n.names} | {n.module for n in top if isinstance(n, ast.ImportFrom) and n.module}
    assert not any("overlay" in str(x) for x in names)


# ---- A5 pre-filter ----------------------------------------------------------------------------------------

def _blank_pdf(pages):
    import io
    import pypdf
    writer = pypdf.PdfWriter()
    for _ in range(pages):
        writer.add_blank_page(width=612, height=792)
    buf = io.BytesIO()
    writer.write(buf)
    return buf.getvalue()


def test_prefilter_keys_on_pages_and_schema_mapped_acroform_values_not_source_format(monkeypatch):
    import pypdf
    tags = frozenset({f"TAG_{i}" for i in range(100)})
    assert oe.stage1_prefilter(_blank_pdf(50), tags)[0] is True
    assert oe.stage1_prefilter(_blank_pdf(10), tags)[:2] == (False, "page_count_out_of_range")
    assert oe.stage1_prefilter(b"<html>", tags)[:2] == (False, "not_a_pdf")
    mapped = {f"TAG_{i}": {"/V": "5"} for i in range(40)}
    monkeypatch.setattr(pypdf.PdfReader, "get_fields", lambda self, *a, **k: mapped)
    assert oe.stage1_prefilter(_blank_pdf(50), tags)[:2] == (False, "usable_acroform_values")       # Tier 2 reads this one
    label = {f"What is your first name? ({i})": {"/V": "5"} for i in range(40)}
    monkeypatch.setattr(pypdf.PdfReader, "get_fields", lambda self, *a, **k: label)
    ok, reason, info = oe.stage1_prefilter(_blank_pdf(50), tags)
    assert ok is True and info["acroform_values"] == 40 and info["acroform_values_mapped"] == 0     # label AcroForm: considered (A5)
    empty = {f"TAG_{i}": {"/V": ""} for i in range(40)}
    monkeypatch.setattr(pypdf.PdfReader, "get_fields", lambda self, *a, **k: empty)
    assert oe.stage1_prefilter(_blank_pdf(50), tags)[0] is True                                       # empty fields are not values


def test_the_real_schema_tags_load():
    tags = oe.schema_pdf_tags()
    assert len(tags) > 1000 and "ACAD_COA_TEXT" in tags


# ---- the CLI ----------------------------------------------------------------------------------------------

def test_cli_defaults_to_dry_run_and_never_touches_projection_ledger_or_web(monkeypatch):
    tree = ast.parse((HERE / "overlay_entry.py").read_text())
    idents = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)} | {n.attr for n in ast.walk(tree) if isinstance(n, ast.Attribute)}
    for forbidden in ("notify_school_revalidation", "refresh_browser_projection", "record_extraction_ledger_payload",
                      "mark_extraction_status", "apply_extraction_quality_flag", "write_run_summary", "finalize_extraction_run"):
        assert forbidden not in idents, forbidden
    tables = {c.args[0].value for c in ast.walk(tree) if isinstance(c, ast.Call) and isinstance(c.func, ast.Attribute)
              and c.func.attr == "table" and c.args and isinstance(c.args[0], ast.Constant)}
    assert tables <= {"cds_artifacts", "cds_documents"}, tables           # no heartbeat or ledger table
    parser_help = subprocess.run([sys.executable, str(HERE / "overlay_entry.py"), "--help"], capture_output=True, text=True).stdout
    parser_help = " ".join(parser_help.split())
    assert "--dry-run" in parser_help and "(the default)" in parser_help and "--write" in parser_help
    bad = subprocess.run([sys.executable, str(HERE / "overlay_entry.py"), "--pdf-dir", "x", "--out-dir", "y", "--write"], capture_output=True, text=True)
    assert bad.returncode != 0 and "--write" in bad.stderr


def test_cli_write_flag_is_the_only_way_to_insert(wired):
    client = FakeClient({"cds_artifacts": [_tier4_base({"B.101": {"value": "100"}})]})
    oe.run_overlay_for_document(client, {"id": "d1"}, write=False)
    assert client.writes() == []
    src = (HERE / "overlay_entry.py").read_text()
    assert len(re.findall(r"insert_overlay_artifact\(", src)) == 2          # the definition and the single `if write:` call
    assert "if write:\n            insert_overlay_artifact" in src


# ---- A1: no newest-canonical reader can see the artifact ---------------------------------------------------

def test_no_newest_canonical_reader_sees_an_overlay_artifact():
    overlay_only = [{"document_id": "d1", "kind": "cleaned", "producer": oe.OVERLAY_PRODUCER, "sha256": "S",
                     "created_at": "2026-11-05T00:00:00+00:00",
                     "notes": {"stats": {"schema_fields_populated": 550}, "source_sha256": "S"}}]
    client = FakeClient({"cds_artifacts": overlay_only})
    assert worker.previous_canonical_field_count(client, "d1", "S") is None          # the regression guard
    source = {"document_id": "d1", "kind": "source", "sha256": "S", "created_at": "2026-10-01T00:00:00+00:00"}
    client = FakeClient({"cds_artifacts": overlay_only + [source]})
    assert worker.has_canonical_for_current_bytes(client, "d1", "S") is False        # the reconcile pass
    # the remaining readers filter kind='canonical' in their query text (A1's list)
    for rel in ("tools/data_quality/audit_manifest.py", "tools/data_quality/completeness_report.py",
                "tools/data_quality/audit_reclean_candidates.py", "tools/data_quality/audit_visual_ocr_candidates.py"):
        assert '"kind", "canonical"' in (ROOT / rel).read_text(), rel
    queries = (ROOT / "web/src/lib/queries.ts").read_text()
    assert queries.count('.eq("kind", "canonical")') >= 2                           # fetchCanonicalArtifact and fetchExtract
    manifest = "\n".join(p.read_text() for p in sorted((ROOT / "supabase/migrations").glob("*.sql")) if "latest_canonical_artifact_id" in p.read_text())
    assert "a.kind = 'canonical'" in manifest


def test_the_ledger_tier_handles_overlay_actions_explicitly():
    assert worker.extraction_ledger_tier("pdf_flat", "overlay_written") == "unknown"
    assert worker.extraction_ledger_tier("pdf_flat", "tier4_extracted") == "tier4"        # unchanged
