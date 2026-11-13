"""PRD 038 M3/A14: the overlay worker entry point, its CLI rules, the artifact and its write-time facts, `--rehold`, the skip key,
and "production unchanged on merge"."""

from __future__ import annotations

import ast
import hashlib
import json
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
from browser_backend import overlay_serving as serving  # noqa: E402

FAKE_BYTES = b"%PDF-fake"
FAKE_SHA = hashlib.sha256(FAKE_BYTES).hexdigest()


# ---- a recording fake client that honours the filters the tool uses ------------------------------------------

def _get(row, key):
    if key.startswith("notes->>"):
        return (row.get("notes") or {}).get(key[len("notes->>"):])
    return row.get(key)


class FakeQuery:
    def __init__(self, client, table):
        self.client, self.table = client, table
        self.filters, self.neq_filters, self.in_filters, self.op, self.payload = {}, {}, {}, "select", None
        self.order_by, self.rng, self.lim = [], None, None

    def select(self, *_a, **_k):
        return self

    def eq(self, key, value):
        self.filters[key] = value
        return self

    def neq(self, key, value):
        self.neq_filters[key] = value
        return self

    def in_(self, key, values):
        self.in_filters[key] = list(values)
        return self

    def order(self, col, desc=False, **_k):
        self.order_by.append((col, desc))
        return self

    def range(self, a, b):
        self.rng = (a, b)
        return self

    def limit(self, n, *_a, **_k):
        self.lim = n
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
                if (all(_get(row, k) == v for k, v in self.filters.items())
                        and all(_get(row, k) != v for k, v in self.neq_filters.items())
                        and all(_get(row, k) in v for k, v in self.in_filters.items())):
                    rows.append(row)
            for col, desc in reversed(self.order_by):
                rows.sort(key=lambda r: str(_get(r, col) or ""), reverse=desc)
            if self.rng:
                rows = rows[self.rng[0]:self.rng[1] + 1]
            if self.lim is not None:
                rows = rows[:self.lim]
        elif self.op == "insert":
            self.client.tables.setdefault(self.table, []).append({**self.payload, "id": f"new-{len(self.client.tables.get(self.table, []))}",
                                                                   "created_at": f"2027-01-01T00:00:{len(self.client.calls):02d}+00:00"})
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

    def inserts(self):
        return [c for c in self.calls if c[1] == "insert"]


def _tier4(values, *, id="b1", sha=FAKE_SHA, schema="2025-26", producer="tier4_docling", created="2026-11-01T00:00:00+00:00", doc="d1"):
    return {"id": id, "document_id": doc, "kind": "canonical", "producer": producer, "producer_version": "0.3.17", "schema_version": schema,
            "created_at": created, "notes": {"source_sha256": sha, "values": values}}


def _extract_output(values, sha=FAKE_SHA, schema="2025-26", **notes):
    inner = {"producer_version": "0.7.0", "field_map_version": "1", "source_sha256": sha, "template_year": schema,
             "stage1": {"status": "matched", "rejected_pages": {"3": "x"}}, "matched_template_pages": 49, "page_map": {"0": 0},
             "lane_counts": {"text": 2, "ocr": 1}, "emission_class_counts": {"numeric": 1, "ocr_numeric": 1},
             "rejected_fields": [{"pdf_tag": "A"}], "withheld": [{"pdf_tag": "Q"}], "withheld_by_reason": {"low_confidence": 1},
             "ocr_engine": "tesseract 5.5.3", "ocr_models": {"fast": "7d43", "best": "8280"}}
    inner.update(notes)
    return {"producer": oe.OVERLAY_PRODUCER, "producer_version": "0.7.0", "schema_version": schema, "extracted_at": "t",
            "stats": {"schema_fields_populated": len(values)}, "values": values, "notes": inner}


VALUES = {
    "B.101": {"value": "100", "emission_class": "numeric", "lane": "text"},
    "B.102": {"value": "5", "emission_class": "numeric", "lane": "text"},
    "C.300": {"value": "7", "emission_class": "ocr_numeric", "lane": 2, "page_kind": "vector", "image_coverage": 0.0},
    "C.301": {"value": "X", "emission_class": "checkbox_boxless", "lane": "text"},
    "C.9": {"value": "free words", "emission_class": "free_text", "lane": "text"},
}
BASE_VALUES = {"B.101": {"value": "100"}, "B.102": {"value": "5"}, "C.300": {"value": "8"}, "C.9": {"value": "other words"}, "T.1": {"value": "only tier 4"}}


@pytest.fixture
def wired(monkeypatch):
    """worker functions faked so run_overlay_for_document runs without a database or a PDF stack."""
    monkeypatch.setattr(worker, "fetch_latest_source_artifact", lambda c, d: {"storage_path": "p", "sha256": FAKE_SHA})
    monkeypatch.setattr(worker, "download_source", lambda c, p: FAKE_BYTES)
    monkeypatch.setattr(worker, "select_source_for_extraction",
                        lambda c, d, a, b: SimpleNamespace(source_artifact=a, source_bytes=FAKE_BYTES, selection_note={"chosen_sha256": FAKE_SHA}, needs_review=False))
    monkeypatch.setattr(oe, "stage1_prefilter", lambda b: (True, None, {"page_count": 49}))
    monkeypatch.setattr(oe, "overlay_constants", lambda: ("0.7.0", "1"))
    monkeypatch.setattr(oe, "tier4_only_class_map", lambda year: {"T.1": "free_text", "B.101": "numeric"})
    calls = []
    monkeypatch.setattr(oe, "extract_pdf", lambda b, **k: (calls.append(k), _extract_output(VALUES))[1])
    for name in ("refresh_browser_projection", "notify_school_revalidation", "mark_extraction_status", "apply_extraction_quality_flag"):
        monkeypatch.setattr(worker, name, lambda *a, **k: pytest.fail("the overlay must not call " + name), raising=False)
    return calls


def _client(*extra, base=None):
    return FakeClient({"cds_artifacts": [base or _tier4(BASE_VALUES), *extra]})


# ---- entry point, dry run vs write ---------------------------------------------------------------------------

def test_dry_run_writes_nothing_and_write_inserts_only_the_overlay_artifact(wired):
    client = _client()
    dry = oe.run_overlay_for_document(client, {"id": "d1"}, write=False)
    assert dry.status == "dry_run" and client.writes() == []
    done = oe.run_overlay_for_document(client, {"id": "d1"}, write=True)
    assert done.status == "written"
    assert len(client.inserts()) == 1 and len(client.writes()) == 1 and client.inserts()[0][0] == "cds_artifacts"
    row = client.inserts()[0][3]
    assert row["kind"] == "cleaned" and row["producer"] == "tier2_template_overlay"
    assert {c[0] for c in client.calls} == {"cds_artifacts"}             # no heartbeat, ledger, status or projection table


def test_artifact_keeps_every_class_and_the_audit_fields(wired):
    notes = oe.run_overlay_for_document(_client(), {"id": "d1"}, write=False).artifact_notes
    assert set(notes["values"]) == set(VALUES)                          # numeric, ocr_numeric, boxless and free text all written
    assert notes["values"]["C.300"]["lane"] == 2 and notes["values"]["C.300"]["page_kind"] == "vector"
    for key in ("producer_version", "field_map_version", "template_year", "source_sha256", "matched_template_pages", "page_map",
                "lane_counts", "rejected_fields", "source_selection", "ocr_engine", "ocr_models", "abstention_by_reason",
                "rejected_pages", "base_artifact_id", "comparison", "hold_basis", "held", "hold_reason", "lane2_requested"):
        assert key in notes, key
    assert notes["abstention_by_reason"] == {"low_confidence": 1} and notes["rejected_pages"] == {"3": "x"}
    assert notes["source_selection"] == {"chosen_sha256": FAKE_SHA} and notes["base_artifact_id"] == "b1" and notes["lane2_requested"] is True


def test_the_stored_facts_are_per_class_with_ids_and_the_blind_spot(wired):
    notes = oe.run_overlay_for_document(_client(), {"id": "d1"}, write=False).artifact_notes
    cmp_ = notes["comparison"]
    assert cmp_["by_class"]["numeric"] == {"both": 2, "disagree": 0}
    assert cmp_["by_class"]["ocr_numeric"] == {"both": 1, "disagree": 1} and cmp_["by_class"]["free_text"] == {"both": 1, "disagree": 1}
    assert {"question": "C.300", "class": "ocr_numeric"} in cmp_["disagreeing"] and {"question": "C.9", "class": "free_text"} in cmp_["disagreeing"]
    assert cmp_["tier4_populated_overlay_empty"] == {"free_text": 1}      # T.1: Tier 4 has it, the overlay does not
    assert cmp_["base_artifact_id"] == "b1" and cmp_["base_recorded_sha"] == FAKE_SHA
    basis = notes["hold_basis"]
    assert basis["classes"] == ["checkbox_box", "choice", "numeric"] and basis["threshold"] == 0.05
    assert basis["compared"] == 2 and basis["disagree"] == 0 and notes["held"] is False   # free_text and ocr disagreements are outside the hold


def test_held_is_computed_over_the_candidate_classes_at_the_given_threshold(wired):
    base = _tier4({**BASE_VALUES, "B.101": {"value": "999"}})            # 1 of the 2 numeric fields disagree = 50%
    held = oe.run_overlay_for_document(_client(base=base), {"id": "d1"}, write=False).artifact_notes
    assert held["held"] is True and held["hold_reason"] == "disagreement_share_above_threshold" and held["hold_basis"]["share"] == 0.5
    assert held["structural_hold_reason"] is None and held["disagreement_held"] is True
    at = oe.run_overlay_for_document(_client(base=base), {"id": "d1"}, write=False, hold_threshold=0.5).artifact_notes
    assert at["held"] is False                                           # exactly at the threshold is not above it
    off = oe.run_overlay_for_document(_client(base=base), {"id": "d1"}, write=False, hold_threshold=None).artifact_notes
    assert off["held"] is False and off["hold_basis"]["threshold"] is None


def test_structural_holds_are_facts_about_the_artifact(wired):
    mismatch = _client(base=_tier4(BASE_VALUES, schema="2024-25"))
    m = oe.run_overlay_for_document(mismatch, {"id": "d1"}, write=False, hold_threshold=None).artifact_notes
    assert m["held"] is True and m["structural_hold_reason"] == "tier4_schema_mismatch" and m["hold_reason"] == "structural:tier4_schema_mismatch"
    none = oe.run_overlay_for_document(FakeClient({"cds_artifacts": []}), {"id": "d1"}, write=False, hold_threshold=None).artifact_notes
    assert none["held"] is True and none["structural_hold_reason"] == "no_tier4_base"
    other_sha = oe.run_overlay_for_document(_client(base=_tier4(BASE_VALUES, sha="not-the-overlays")), {"id": "d1"}, write=False).artifact_notes
    assert other_sha["structural_hold_reason"] == "no_tier4_base"        # a base built from other bytes is no comparison base


def test_the_comparison_base_is_chosen_like_the_projection_and_must_have_the_equal_sha(wired):
    # a NEWER Tier 4 built from other bytes must not be the base; the older one with the equal sha is
    newer_other = _tier4({"B.101": {"value": "0"}}, id="new-other", sha="other", created="2026-12-01T00:00:00+00:00")
    older_equal = _tier4(BASE_VALUES, id="old-equal", created="2026-10-01T00:00:00+00:00")
    notes = oe.run_overlay_for_document(FakeClient({"cds_artifacts": [newer_other, older_equal]}), {"id": "d1"}, write=False).artifact_notes
    assert notes["base_artifact_id"] == "old-equal" and notes["comparison"]["by_class"]["numeric"]["both"] == 2
    # the projection ranks Tier 2 above Tier 4 (sort_base_candidates): when it has the equal sha, it is the chosen base, so no Tier 4 comparison
    tier2 = _tier4(BASE_VALUES, id="t2", producer="tier2_acroform")
    t = oe.run_overlay_for_document(FakeClient({"cds_artifacts": [tier2, older_equal]}), {"id": "d1"}, write=False).artifact_notes
    assert t["structural_hold_reason"] == "chosen_base_not_tier4" and t["base_artifact_id"] == "t2"
    # a producer that is not a base candidate is ignored even with the equal sha and a later date
    llm = _tier4({"B.101": {"value": "0"}}, id="llm", producer="tier4_llm_fallback", created="2026-12-31T00:00:00+00:00")
    n = oe.run_overlay_for_document(FakeClient({"cds_artifacts": [llm, older_equal]}), {"id": "d1"}, write=False).artifact_notes
    assert n["base_artifact_id"] == "old-equal"
    only_llm = oe.run_overlay_for_document(FakeClient({"cds_artifacts": [llm]}), {"id": "d1"}, write=False).artifact_notes
    assert only_llm["structural_hold_reason"] == "no_tier4_base" and only_llm["base_artifact_id"] is None   # not a base candidate at all


# ---- the skip key: every dimension, no fixed window, before extraction ---------------------------------------

def _existing(**over):
    notes = {"source_sha256": FAKE_SHA, "field_map_version": "1", "lane2_requested": True, "lane2_ran": True}
    notes.update(over.pop("notes", {}))
    row = {"id": over.pop("id", "ov1"), "document_id": over.pop("document_id", "d1"), "kind": "cleaned", "producer": oe.OVERLAY_PRODUCER,
           "producer_version": over.pop("producer_version", "0.7.0"), "created_at": over.pop("created_at", "2026-11-05T00:00:00+00:00"), "notes": notes}
    row.update(over)
    return row


def test_the_skip_key_is_found_before_extraction_and_each_dimension_matters(wired):
    client = _client(_existing())
    skipped = oe.run_overlay_for_document(client, {"id": "d1"}, write=True)
    assert skipped.status == "skipped" and skipped.reason == "already_overlaid" and wired == [] and client.inserts() == []   # no extraction
    for name, row in {
        "producer_version": _existing(producer_version="0.6.0"),
        "field_map_version": _existing(notes={"field_map_version": "2"}),
        "source_sha": _existing(notes={"source_sha256": "other"}),
        "lane2": _existing(notes={"lane2_requested": False, "lane2_ran": False}),
        "document": _existing(document_id="d2"),
    }.items():
        c = _client(row)
        r = oe.run_overlay_for_document(c, {"id": "d1"}, write=True)
        assert r.status == "written", name                                # a different key dimension is not a duplicate


def test_a_failed_or_disabled_lane_2_is_re_extracted_and_no_lane2_artifacts_satisfy_no_lane2_requests(wired):
    for why in ({"lane2_ran": False, "lane2_failed": "RuntimeError: tesseract exited 1"},
                {"lane2_ran": False, "lane2_disabled": "tesseract_not_installed"}):
        client = _client(_existing(notes=why))
        r = oe.run_overlay_for_document(client, {"id": "d1"}, write=True)
        assert r.status == "written", why                                  # a plain rerun re-extracts: Lane 2 never arrived
        assert r.summary["lane2_ran"] is True
    plain = _client(_existing(notes={"lane2_requested": False, "lane2_ran": False}))
    skipped = oe.run_overlay_for_document(plain, {"id": "d1"}, write=True, lane2=False)
    assert skipped.status == "skipped" and skipped.reason == "already_overlaid"          # --no-lane2 satisfies --no-lane2
    assert oe.run_overlay_for_document(plain, {"id": "d1"}, write=True, lane2=True).status == "written"   # but not a Lane 2 request
    legacy_ran = _existing(notes={"ocr_engine": "tesseract 5.5.3"}); legacy_ran["notes"].pop("lane2_ran")
    legacy_none = _existing(notes={}); legacy_none["notes"].pop("lane2_ran")
    assert oe.overlay_already_written(_client(legacy_ran), "d1", "0.7.0", "1", FAKE_SHA, True) is True
    assert oe.overlay_already_written(_client(legacy_none), "d1", "0.7.0", "1", FAKE_SHA, True) is False


def test_the_artifact_records_whether_lane_2_ran_and_the_summary_shows_why_not(wired, monkeypatch):
    ok = oe.run_overlay_for_document(_client(), {"id": "d1"}, write=False)
    assert ok.artifact_notes["lane2_ran"] is True and ok.summary["lane2_failed"] is None
    monkeypatch.setattr(oe, "extract_pdf", lambda b, **k: _extract_output(VALUES, lane2_failed="TimeoutExpired: tesseract"))
    bad = oe.run_overlay_for_document(_client(), {"id": "d1"}, write=False)
    assert bad.artifact_notes["lane2_ran"] is False and bad.summary["lane2_failed"] == "TimeoutExpired: tesseract"
    monkeypatch.setattr(oe, "extract_pdf", lambda b, **k: _extract_output(VALUES, lane2_disabled="tesseract_not_installed"))
    off = oe.run_overlay_for_document(_client(), {"id": "d1"}, write=False)
    assert off.artifact_notes["lane2_ran"] is False and off.summary["lane2_disabled"] == "tesseract_not_installed"
    nolane = oe.run_overlay_for_document(_client(), {"id": "d1"}, write=False, lane2=False)
    assert nolane.artifact_notes["lane2_requested"] is False and nolane.artifact_notes["lane2_ran"] is False


def test_the_key_lookup_has_no_fixed_window(wired):
    filler = [_existing(id=f"x{i:03d}", created_at=f"2026-12-{(i % 28) + 1:02d}T00:00:{i % 60:02d}+00:00", notes={"field_map_version": "0"}) for i in range(130)]
    match = _existing(id="the-match", created_at="2026-01-01T00:00:00+00:00")          # the OLDEST row, behind 130 newer near-misses
    client = _client(*filler, match)
    assert oe.overlay_already_written(client, "d1", "0.7.0", "1", FAKE_SHA, True) is True
    assert oe.overlay_already_written(client, "d1", "0.7.0", "1", FAKE_SHA, False) is False
    assert oe.overlay_already_written(_client(*filler), "d1", "0.7.0", "1", FAKE_SHA, True) is False
    assert oe.run_overlay_for_document(client, {"id": "d1"}, write=True).reason == "already_overlaid"


def test_force_appends_and_the_contract_is_stated_honestly(wired):
    client = _client(_existing())
    assert oe.run_overlay_for_document(client, {"id": "d1"}, write=True, force=True).status == "written"
    doc = oe.__doc__
    assert "ONE SERIAL WRITER" in doc and "harmless" in doc and "newest eligible overlay wins" in doc and "not general idempotency" in doc
    assert oe.idempotency_key("d", "0.7.0", "1", "S", True) == ("d", "tier2_template_overlay", "0.7.0", "1", "S", True)
    assert oe.idempotency_key("d", "0.7.0", "1", "S", False) != oe.idempotency_key("d", "0.7.0", "1", "S", True)


# ---- failure isolation ---------------------------------------------------------------------------------------

@pytest.mark.parametrize("exc", [RuntimeError("injected"), SystemExit(3), GeneratorExit()])
def test_an_overlay_failure_of_any_kind_changes_nothing(wired, monkeypatch, exc):
    client = _client()
    monkeypatch.setattr(oe, "extract_pdf", lambda *a, **k: (_ for _ in ()).throw(exc))
    result = oe.run_overlay_for_document(client, {"id": "d1"}, write=True)
    assert result.status == "error"
    assert client.writes() == []                                          # no artifact, no status, no flag, no ledger row


def test_the_cli_continues_after_a_baseexception_on_one_document(wired, monkeypatch, tmp_path):
    client = FakeClient({"cds_artifacts": [_tier4(BASE_VALUES, doc="d1"), _tier4(BASE_VALUES, doc="d2", id="b2")],
                         "cds_documents": [{"id": "d1"}, {"id": "d2"}]})
    import os
    monkeypatch.setattr(os, "environ", os.environ.copy())
    seen = []

    def extract(b, **k):
        seen.append(1)
        if len(seen) == 1:
            raise SystemExit(7)
        return _extract_output(VALUES)

    monkeypatch.setattr(oe, "extract_pdf", extract)
    fake_supabase = SimpleNamespace(create_client=lambda url, key: client)
    monkeypatch.setitem(sys.modules, "supabase", fake_supabase)
    env = tmp_path / "e.env"
    env.write_text("SUPABASE_URL=http://x\nSUPABASE_SERVICE_ROLE_KEY=k\n")
    out_json = tmp_path / "out.json"
    rc = oe.main(["--env", str(env), "--document-ids", "d1,d2", "--json-out", str(out_json)])
    results = json.loads(out_json.read_text())
    assert [r["status"] for r in results] == ["error", "dry_run"] and rc == 1       # the second document still ran


def test_env_file_values_reach_every_setting_the_tool_reads(wired, monkeypatch, tmp_path):
    client = _client()
    client.tables["cds_documents"] = [{"id": "d1"}]
    import os
    monkeypatch.setattr(os, "environ", os.environ.copy())                  # isolate: apply_env_file mutates the environment
    captured = {}
    monkeypatch.setattr(oe, "run_overlay_for_document", lambda c, d, **kw: (captured.update(kw), oe.OverlayResult("d1", "dry_run"))[1])
    monkeypatch.setitem(sys.modules, "supabase", SimpleNamespace(create_client=lambda u, k: client))
    for k in ("OVERLAY_HOLD_THRESHOLD", "CDS_TESSDATA_BEST", "SUPABASE_URL", "SUPABASE_SERVICE_ROLE_KEY"):
        os.environ.pop(k, None)
    env = tmp_path / "e.env"
    env.write_text("SUPABASE_URL=http://x\nSUPABASE_SERVICE_ROLE_KEY=k\nOVERLAY_HOLD_THRESHOLD=0.8\nCDS_TESSDATA_BEST=/models/best\n")
    oe.main(["--env", str(env), "--document-ids", "d1"])
    assert captured["hold_threshold"] == 0.8                               # the hold threshold came from the env FILE
    assert os.environ["CDS_TESSDATA_BEST"] == "/models/best"              # and so do the Lane 2 settings
    os.environ["OVERLAY_HOLD_THRESHOLD"] = "0.2"                           # an exported value is not overridden by the file
    oe.main(["--env", str(env), "--document-ids", "d1"])
    assert captured["hold_threshold"] == 0.2
    oe.main(["--env", str(env), "--document-ids", "d1", "--hold-threshold", "off"])
    assert captured["hold_threshold"] is None                              # the flag wins, and `off` disables the disagreement hold


# ---- --rehold --------------------------------------------------------------------------------------------------

def _written_artifact(wired, base_values=None, **kw):
    client = _client(base=_tier4(base_values or {**BASE_VALUES, "B.101": {"value": "999"}}))
    oe.run_overlay_for_document(client, {"id": "d1"}, write=True, **kw)
    return client


def test_rehold_recomputes_from_stored_facts_without_extracting(wired, monkeypatch):
    client = _written_artifact(wired)
    first = client.inserts()[0][3]["notes"]
    assert first["held"] is True and first["hold_basis"]["share"] == 0.5
    n_extractions = len(wired)
    dry = oe.run_rehold_for_document(client, "d1", threshold=0.6, classes=oe.serving_classes() if hasattr(oe, "serving_classes") else ("numeric", "choice", "checkbox_box"), write=False)
    assert dry.status == "dry_run" and dry.artifact_notes["held"] is False and len(client.inserts()) == 1      # dry run appends nothing
    done = oe.run_rehold_for_document(client, "d1", threshold=0.6, classes=("numeric", "choice", "checkbox_box"), write=True)
    assert done.status == "written" and len(client.inserts()) == 2 and len(wired) == n_extractions               # no extraction
    new = client.inserts()[1][3]
    assert new["notes"]["values"] == first["values"]                      # values copied unchanged
    assert new["notes"]["held"] is False and new["notes"]["hold_basis"]["threshold"] == 0.6 and new["notes"]["rehold_of"]
    assert new["kind"] == "cleaned" and new["producer"] == oe.OVERLAY_PRODUCER


def test_rehold_newest_wins_unchanged_is_skipped_off_and_class_set_apply(wired):
    client = _written_artifact(wired)
    classes = ("numeric", "choice", "checkbox_box")
    assert oe.run_rehold_for_document(client, "d1", threshold=0.05, classes=classes, write=True).reason == "unchanged"
    assert len(client.inserts()) == 1                                      # same threshold, classes and outcome: nothing appended
    assert oe.run_rehold_for_document(client, "d1", threshold=None, classes=classes, write=True).status == "written"      # off
    newest = max(client.tables["cds_artifacts"][1:], key=lambda r: r["created_at"])
    assert newest["notes"]["held"] is False and newest["notes"]["hold_basis"]["threshold"] is None
    # a class set that excludes numeric sees no comparable field: not held
    assert oe.run_rehold_for_document(client, "d1", threshold=0.05, classes=("choice",), write=False).artifact_notes["held"] is False
    # structural holds survive a rehold
    s = _client(base=_tier4(BASE_VALUES, schema="2024-25"))
    oe.run_overlay_for_document(s, {"id": "d1"}, write=True, hold_threshold=None)
    r = oe.run_rehold_for_document(s, "d1", threshold=None, classes=classes, write=False)
    assert r.reason == "unchanged" and s.tables["cds_artifacts"][-1]["notes"]["held"] is True
    assert oe.run_rehold_for_document(_client(), "d1", threshold=0.05, classes=classes, write=True).reason == "no_overlay_artifact"


def test_the_selectors_pick_the_rehold_artifact_because_it_is_newest(wired):
    client = _written_artifact(wired)
    oe.run_rehold_for_document(client, "d1", threshold=None, classes=("numeric", "choice", "checkbox_box"), write=True)
    base = client.tables["cds_artifacts"][0]
    overlays = [dict(r, created_at=r.get("created_at") or "2027-01-01") for r in client.tables["cds_artifacts"] if r.get("producer") == oe.OVERLAY_PRODUCER]
    assert len(overlays) == 2
    picked = serving.pick_overlay(base, overlays)
    assert picked["notes"]["held"] is False and picked["notes"].get("rehold_of")        # the re-held artifact, not the held original


# ---- the routine loop: flag off, broken package, never under --dry-run --------------------------------------

def test_loop_flag_defaults_off(monkeypatch):
    monkeypatch.delenv("OVERLAY_WORKER_ENABLED", raising=False)
    assert oe.overlay_loop_enabled() is False
    for on in ("1", "true", "YES", "on"):
        assert oe.overlay_loop_enabled({"OVERLAY_WORKER_ENABLED": on}) is True
    assert oe.overlay_loop_enabled({"OVERLAY_WORKER_ENABLED": "0"}) is False


def test_flag_off_never_imports_or_calls_the_overlay(monkeypatch):
    monkeypatch.delenv("OVERLAY_WORKER_ENABLED", raising=False)
    monkeypatch.setitem(sys.modules, "overlay_entry", SimpleNamespace())     # any attribute access would raise AttributeError
    worker.maybe_run_overlay(FakeClient(), {"id": "d1"})


def test_flag_on_with_a_broken_overlay_package_is_logged_and_ignored(monkeypatch, capsys):
    monkeypatch.setenv("OVERLAY_WORKER_ENABLED", "1")
    monkeypatch.setitem(sys.modules, "overlay_entry", None)
    client = FakeClient()
    worker.maybe_run_overlay(client, {"id": "d1"})
    assert "overlay_error" in capsys.readouterr().err and client.calls == []
    monkeypatch.setitem(sys.modules, "overlay_entry", SimpleNamespace(run_overlay_in_loop=lambda c, d: (_ for _ in ()).throw(SystemExit(3))))
    worker.maybe_run_overlay(client, {"id": "d1"})                        # even SystemExit from a bad stack is contained


def test_the_loop_hook_is_skipped_under_dry_run():
    tree = ast.parse((HERE / "worker.py").read_text())
    hits = []
    for node in ast.walk(tree):
        if isinstance(node, ast.If):
            for call in ast.walk(ast.Module(body=node.body, type_ignores=[])):
                if isinstance(call, ast.Call) and getattr(call.func, "id", "") == "maybe_run_overlay":
                    hits.append(ast.unparse(node.test))
    assert hits == ["not args.dry_run"], hits                             # the only call is guarded by `not args.dry_run`


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
    assert oe.stage1_prefilter(_blank_pdf(50), tags)[:2] == (False, "usable_acroform_values")
    label = {f"What is your first name? ({i})": {"/V": "5"} for i in range(40)}
    monkeypatch.setattr(pypdf.PdfReader, "get_fields", lambda self, *a, **k: label)
    ok, reason, info = oe.stage1_prefilter(_blank_pdf(50), tags)
    assert ok is True and info["acroform_values"] == 40 and info["acroform_values_mapped"] == 0     # label AcroForm: considered (A5)
    empty = {f"TAG_{i}": {"/V": ""} for i in range(40)}
    monkeypatch.setattr(pypdf.PdfReader, "get_fields", lambda self, *a, **k: empty)
    assert oe.stage1_prefilter(_blank_pdf(50), tags)[0] is True


def test_the_real_schema_tags_load():
    tags = oe.schema_pdf_tags()
    assert len(tags) > 1000 and "ACAD_COA_TEXT" in tags


# ---- the CLI ----------------------------------------------------------------------------------------------

def test_cli_defaults_to_dry_run_and_never_touches_projection_ledger_or_web():
    tree = ast.parse((HERE / "overlay_entry.py").read_text())
    idents = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)} | {n.attr for n in ast.walk(tree) if isinstance(n, ast.Attribute)}
    for forbidden in ("notify_school_revalidation", "refresh_browser_projection", "record_extraction_ledger_payload",
                      "mark_extraction_status", "apply_extraction_quality_flag", "write_run_summary", "finalize_extraction_run"):
        assert forbidden not in idents, forbidden
    tables = {c.args[0].value for c in ast.walk(tree) if isinstance(c, ast.Call) and isinstance(c.func, ast.Attribute)
              and c.func.attr == "table" and c.args and isinstance(c.args[0], ast.Constant)}
    assert tables <= {"cds_artifacts", "cds_documents"}, tables
    parser_help = subprocess.run([sys.executable, str(HERE / "overlay_entry.py"), "--help"], capture_output=True, text=True).stdout
    parser_help = " ".join(parser_help.split())
    assert "--dry-run" in parser_help and "(the default)" in parser_help and "--write" in parser_help and "--rehold" in parser_help
    bad = subprocess.run([sys.executable, str(HERE / "overlay_entry.py"), "--pdf-dir", "x", "--out-dir", "y", "--write"], capture_output=True, text=True)
    assert bad.returncode != 0 and "--write" in bad.stderr


def test_write_flag_is_the_only_way_to_insert(wired):
    client = _client()
    oe.run_overlay_for_document(client, {"id": "d1"}, write=False)
    oe.run_rehold_for_document(client, "d1", threshold=0.05, classes=("numeric",), write=False)
    assert client.writes() == []
    src = (HERE / "overlay_entry.py").read_text()
    assert src.count("insert_overlay_artifact(client, document_id") == 2     # one per `if write:` (extraction and rehold)
    assert src.count("if write:\n            insert_overlay_artifact") == 2


# ---- A1: no newest-canonical reader can see the artifact ---------------------------------------------------

def test_no_newest_canonical_reader_sees_an_overlay_artifact():
    overlay_only = [{"document_id": "d1", "kind": "cleaned", "producer": oe.OVERLAY_PRODUCER, "sha256": "S",
                     "created_at": "2026-11-05T00:00:00+00:00",
                     "notes": {"stats": {"schema_fields_populated": 550}, "source_sha256": "S"}}]
    client = FakeClient({"cds_artifacts": overlay_only})
    assert worker.previous_canonical_field_count(client, "d1", "S") is None
    source = {"document_id": "d1", "kind": "source", "sha256": "S", "created_at": "2026-10-01T00:00:00+00:00"}
    client = FakeClient({"cds_artifacts": overlay_only + [source]})
    assert worker.has_canonical_for_current_bytes(client, "d1", "S") is False
    for rel in ("tools/data_quality/audit_manifest.py", "tools/data_quality/completeness_report.py",
                "tools/data_quality/audit_reclean_candidates.py", "tools/data_quality/audit_visual_ocr_candidates.py"):
        assert '"kind", "canonical"' in (ROOT / rel).read_text(), rel
    queries = (ROOT / "web/src/lib/queries.ts").read_text()
    assert queries.count('.eq("kind", "canonical")') >= 2
    manifest = "\n".join(p.read_text() for p in sorted((ROOT / "supabase/migrations").glob("*.sql")) if "latest_canonical_artifact_id" in p.read_text())
    assert "a.kind = 'canonical'" in manifest


def test_the_ledger_tier_handles_overlay_actions_explicitly():
    assert worker.extraction_ledger_tier("pdf_flat", "overlay_written") == "unknown"
    assert worker.extraction_ledger_tier("pdf_flat", "tier4_extracted") == "tier4"
