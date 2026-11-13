"""PRD 038 A5: the template-overlay worker entry point and its scoped CLI.

The overlay is its own entry point, not a hook after the Tier 4 insert: `_run_tier4` returns early on
`already_extracted` and `tier4_field_regression`, which is the state of every cohort document.

CONTRACT (PRD 038 A14). There is no database uniqueness on the overlay and none is added here. The tool is meant to be run by
ONE SERIAL WRITER at a time. Before extracting it looks for an existing overlay artifact with the same (document, producer
version, field-map version, source sha256, whether Lane 2 was requested) and skips the document when it finds one; the lookup pages
through every matching row. Two concurrent writers can both pass that check and both insert: that is harmless, because the
newest eligible overlay wins in every selector. It is a best-effort skip to save extraction time, not general idempotency.

Safety rules (the M3 "no production change on merge" rule):

* Nothing here is imported at the top level of `worker.py`. The overlay stack (cv2, pdfium, Tesseract) is
  imported lazily inside the entry point, inside try/except, and only when the loop flag is on or the
  CLI is used. A broken or missing overlay package changes nothing about the daily drain.
* An overlay failure of any kind (`BaseException` except `KeyboardInterrupt`) is logged and returned as an error result; the CLI
  continues with the next document. It never changes a document's extraction_status, quality flag, ledger row, heartbeat or
  projection, and never calls the revalidation hook.
* The CLI neither writes a heartbeat or ledger row, nor refreshes the projection, nor notifies the web, in
  either mode. `--dry-run` (the default) writes nothing at all; `--write` inserts only overlay artifacts
  (`kind='cleaned'`, `producer='tier2_template_overlay'`; never `canonical`).
* The routine worker loop calls the overlay only when `OVERLAY_WORKER_ENABLED` is truthy (default off).
* Raw artifact rows are publicly readable through the `cds_artifacts` API (owner decision pending); no selected-result consumer
  serves overlay values unless `OVERLAY_SERVE_CLASSES` names classes.

The hold (`held`) is computed at WRITE time from stored facts over the default served-candidate classes; `--rehold` recomputes it
from those stored facts under a different threshold or class set and appends a new artifact (no extraction).

CLI (from the repo root, with the worker environment; `--env FILE` values reach every setting the tool reads):

    python tools/extraction_worker/overlay_entry.py --document-ids <id>[,<id>...]            # dry run (default)
    python tools/extraction_worker/overlay_entry.py --document-ids <id>,<id> --write         # writes artifacts
    python tools/extraction_worker/overlay_entry.py --document-ids <id>,<id> --rehold --hold-threshold 0.10 [--write]
    python tools/extraction_worker/overlay_entry.py --pdf-dir scratch/prd038/pdfs --out-dir <dir>   # local, no database
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
import traceback
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Mapping, Optional

_WORKER_DIR = Path(__file__).resolve().parent
_TOOLS_ROOT = _WORKER_DIR.parent
OVERLAY_PRODUCER = "tier2_template_overlay"
ENV_LOOP_FLAG = "OVERLAY_WORKER_ENABLED"
MIN_PAGES, MAX_PAGES = 30, 70            # A5 pre-filter page window (the overlay's own Stage 1 re-checks)
MAX_USABLE_ACROFORM_VALUES = 10          # more schema-mapped populated AcroForm values than this: Tier 2 reads the document


def overlay_loop_enabled(env: Optional[Mapping[str, str]] = None) -> bool:
    raw = (os.environ if env is None else env).get(ENV_LOOP_FLAG, "")
    return str(raw).strip().lower() in {"1", "true", "yes", "on"}


def idempotency_key(document_id: str, producer_version: str, field_map_version: str, source_sha256: str, lane2_requested: bool = True) -> tuple:
    """The skip key: every dimension that makes a different artifact. Not a uniqueness guarantee (see the contract above)."""
    return (str(document_id), OVERLAY_PRODUCER, str(producer_version), str(field_map_version), str(source_sha256), bool(lane2_requested))


@dataclass
class OverlayResult:
    document_id: str
    status: str                      # written | dry_run | skipped | error
    reason: Optional[str] = None
    summary: dict[str, Any] = field(default_factory=dict)
    artifact_notes: Optional[dict[str, Any]] = None
    seconds: float = 0.0


_SCHEMA_TAGS: Optional[frozenset] = None


def schema_pdf_tags() -> frozenset:
    """Every `pdf_tag` of the canonical CDS schemas: the names a usable (schema-mapped) AcroForm field can have."""
    global _SCHEMA_TAGS
    if _SCHEMA_TAGS is None:
        tags: set[str] = set()
        for path in sorted((_TOOLS_ROOT.parent / "schemas").glob("cds_schema_????_??.json")):
            for f in json.loads(path.read_text()).get("fields") or []:
                if f.get("pdf_tag"):
                    tags.add(str(f["pdf_tag"]))
        _SCHEMA_TAGS = frozenset(tags)
    return _SCHEMA_TAGS


def stage1_prefilter(pdf_bytes: bytes, schema_tags: Optional[frozenset] = None) -> tuple[bool, Optional[str], dict[str, Any]]:
    """A5: a PDF of 30-70 pages with no usable AcroForm values (not `source_format` alone).

    "Usable" means schema-mapped: a populated field whose name is a `pdf_tag` of the CDS schema, the values Tier 2
    reads. A label-AcroForm PDF (many populated fields named by prompts, almost none mapped) reaches Tier 4 through
    `should_fallback_tier2_to_tier4` and is exactly the kind of document the overlay should still consider."""
    import io

    info: dict[str, Any] = {}
    if len(pdf_bytes) < 4 or pdf_bytes[:4] != b"%PDF":
        return False, "not_a_pdf", info
    import pypdf

    try:
        reader = pypdf.PdfReader(io.BytesIO(pdf_bytes))
        pages = len(reader.pages)
        info["page_count"] = pages
        if not (MIN_PAGES <= pages <= MAX_PAGES):
            return False, "page_count_out_of_range", info
        fields = reader.get_fields() or {}
    except Exception as exc:  # unreadable PDF: the overlay cannot help
        return False, f"unreadable_pdf:{type(exc).__name__}", info
    tags = schema_pdf_tags() if schema_tags is None else schema_tags
    populated = mapped = 0
    for name, f in fields.items():
        v = f.get("/V") if hasattr(f, "get") else None
        if v in (None, "", "/Off", "Off"):
            continue
        populated += 1
        leaf = str(name).split(".")[-1]
        if name in tags or leaf in tags:
            mapped += 1
    info["acroform_values"] = populated
    info["acroform_values_mapped"] = mapped
    if mapped > MAX_USABLE_ACROFORM_VALUES:
        return False, "usable_acroform_values", info
    return True, None, info


# ---- the comparison base, the facts and the hold --------------------------------------------------------------

_UNSET: Any = object()          # "take the threshold from the environment"
_LIGHT_BASE_COLUMNS = ("id,producer,producer_version,schema_version,created_at,"
                       "notes->source_sha256,notes->source_artifact,notes->schema_fallback_used,notes->stats")


def _notes_of(row: Mapping[str, Any]) -> dict[str, Any]:
    """A row's notes, whether the query returned the whole `notes` or json-path columns lifted to the top level."""
    notes = row.get("notes")
    if isinstance(notes, dict):
        return notes
    return {k: row[k] for k in ("source_sha256", "source_artifact", "schema_fallback_used", "stats", "field_map_version",
                                "lane2_requested", "lane2_ran", "lane2_disabled", "lane2_failed", "ocr_engine", "values") if k in row}


def choose_comparison_base(client: Any, document_id: str, overlay_sha: str, expected_schema: Optional[str]):
    """The base the PROJECTION would pick (`sort_base_candidates` order), restricted to bases whose recorded source sha equals
    the overlay's. Returns (base row with light notes | None, structural reason | None)."""
    sys.path.insert(0, str(_TOOLS_ROOT))
    from browser_backend import overlay_serving as serving
    from browser_backend import project_browser_data as pbd

    rows = (client.table("cds_artifacts").select(_LIGHT_BASE_COLUMNS)
            .eq("document_id", document_id).eq("kind", "canonical").execute().data) or []
    candidates = []
    for row in rows:
        if row.get("producer") not in pbd.BASE_PRODUCER_RANK:
            continue
        candidates.append({**row, "notes": _notes_of(row)})
    equal = [c for c in candidates if serving.recorded_source_sha(c) == overlay_sha]
    if not equal:
        return None, "no_tier4_base"
    best = pbd.sort_base_candidates(equal, expected_schema)[0]
    if best.get("producer") != serving.OVERLAY_BASE_PRODUCER:
        return best, "chosen_base_not_tier4"
    if not best.get("schema_version") or str(best["schema_version"]) != str(expected_schema):
        return best, "tier4_schema_mismatch"
    return best, None


def fetch_base_values(client: Any, artifact_id: str) -> dict[str, Any]:
    rows = client.table("cds_artifacts").select("id,notes->values").eq("id", artifact_id).execute().data or []
    if not rows:
        return {}
    values = _notes_of(rows[0]).get("values")
    return values if isinstance(values, dict) else {}


def tier4_only_class_map(year: str) -> dict[str, str]:
    """{question number: emission class} for the fields of a template year, used to say what class the fields Tier 4 populates
    and the overlay leaves empty belong to. Buttons are one `checkbox` bucket (box or boxless is only known when read)."""
    sys.path.insert(0, str(_TOOLS_ROOT / "tier2_extractor"))
    import template_overlay as to

    fmap = to.load_maps()[year].fmap["fields"]
    schema_by_tag = {f["pdf_tag"]: f for f in to._schema(year)["fields"] if f.get("pdf_tag")}
    out: dict[str, str] = {}
    for tag, f in fmap.items():
        qn = f.get("question_number")
        sf = schema_by_tag.get(tag)
        if not qn:
            continue
        if f["ft"] == "/Btn":
            out[qn] = "checkbox"
        else:
            et = to.effective_type(tag, (sf or {}).get("value_type"), f["ft"])
            out[qn] = to.emission_class_text(et, f["ft"])
    return out


# Keys of the overlay's own notes that are bulky per-widget lists; the artifact keeps their counts instead.
_DROP_NOTE_KEYS = {"withheld", "ocr_widgets", "unmapped_fields", "skipped_null_question_number", "ambiguous_radios"}


def lane2_ran_in(notes: Mapping[str, Any], requested: Optional[bool] = None) -> bool:
    """Whether Lane 2 actually ran for an artifact: requested, and neither `lane2_disabled` (probe failed or no second model)
    nor `lane2_failed` (the engine failed mid-run). A legacy row without the field ran Lane 2 only if it records an `ocr_engine`."""
    if "lane2_ran" in notes:
        return bool(notes["lane2_ran"])
    if requested is None:
        requested = bool(notes.get("lane2_requested", True)) and bool(notes.get("ocr_engine"))
    return bool(requested) and not notes.get("lane2_disabled") and not notes.get("lane2_failed")


def compute_hold(notes: dict[str, Any], threshold: Optional[float], classes: Iterable[str]) -> None:
    """Set `held`, `hold_reason`, `hold_basis` and `disagreement_held` on `notes` from its stored facts. `held` is true when a
    structural condition holds (a fact about the artifact) or the disagreement share over `classes` exceeds `threshold`
    (`None` = off disables only the disagreement part)."""
    sys.path.insert(0, str(_TOOLS_ROOT))
    from browser_backend import overlay_serving as serving

    structural = notes.get("structural_hold_reason")
    comparison = notes.get("comparison") or {}
    by_class = comparison.get("by_class")
    if by_class is not None and not structural:
        basis = serving.disagreement_hold(by_class, classes, threshold)
        disagreement = bool(basis["held"])
    else:
        basis = serving.disagreement_hold({}, classes, threshold)      # nothing to compare: the numbers are empty
        disagreement = False
    notes["hold_basis"] = {**basis, "base_artifact_id": comparison.get("base_artifact_id"),
                           "base_recorded_sha": comparison.get("base_recorded_sha")}
    notes["disagreement_held"] = disagreement
    notes["held"] = bool(structural) or disagreement
    notes["hold_reason"] = (f"structural:{structural}" if structural
                            else ("disagreement_share_above_threshold" if disagreement else None))


def build_artifact_notes(
    out: Mapping[str, Any],
    *,
    selection_note: Optional[Mapping[str, Any]] = None,
    base: Optional[Mapping[str, Any]] = None,
    base_values: Optional[Mapping[str, Any]] = None,
    base_reason: Optional[str] = None,
    hold_threshold: Optional[float] = None,
    hold_classes: Iterable[str] = (),
    lane2_requested: bool = True,
    tier4_only_class_of=None,
) -> dict[str, Any]:
    """The `cds_artifacts.notes` of an overlay artifact: its values (all classes, with `emission_class`, `lane`, `page_kind` and
    `derived_lanes`), the audit fields, and the FACTS the hold is computed from (so a later rule needs no re-extraction)."""
    sys.path.insert(0, str(_TOOLS_ROOT))
    from browser_backend import overlay_serving as serving

    inner = dict(out.get("notes") or {})
    values = dict(out.get("values") or {})
    notes: dict[str, Any] = {
        "producer": out.get("producer"), "producer_version": out.get("producer_version"),
        "schema_version": out.get("schema_version"), "extracted_at": out.get("extracted_at"),
        "stats": out.get("stats") or {}, "values": values,
    }
    for key, value in inner.items():
        if key in _DROP_NOTE_KEYS or key in notes:
            continue
        notes[key] = value
    notes["withheld_count"] = len(inner.get("withheld") or [])
    notes["abstention_by_reason"] = dict(inner.get("withheld_by_reason") or {})
    notes["rejected_pages"] = (inner.get("stage1") or {}).get("rejected_pages") or {}
    if selection_note:
        notes["source_selection"] = dict(selection_note)
    notes["value_count"] = len(values)
    notes["emission_class_counts"] = dict(inner.get("emission_class_counts") or {})
    notes["lane2_requested"] = bool(lane2_requested)
    notes["lane2_ran"] = lane2_ran_in(notes, lane2_requested)             # requested AND neither disabled nor failed
    if (inner.get("held") or {}).get("status"):
        notes["document_hold"] = inner["held"]                    # the producer held the document (no values then)

    structural = base_reason
    if notes.get("document_hold"):
        structural = structural or "document_hold"
    notes["base_artifact_id"] = str(base["id"]) if base and base.get("id") else None
    if base is not None and base_values is not None and not structural:
        facts = serving.comparison_facts(base_values, values, tier4_only_class_of)
        notes["comparison"] = {
            "base_artifact_id": notes["base_artifact_id"], "base_producer_version": base.get("producer_version"),
            "base_schema_version": base.get("schema_version"), "base_recorded_sha": serving.recorded_source_sha(base), **facts}
    else:
        notes["comparison"] = {"base_artifact_id": notes["base_artifact_id"], "by_class": None, "disagreeing": [],
                               "tier4_populated_overlay_empty": {}, "base_recorded_sha": serving.recorded_source_sha(base) if base else None}
    notes["structural_hold_reason"] = structural
    compute_hold(notes, hold_threshold, hold_classes)
    return notes


def rehold_notes(notes: Mapping[str, Any], threshold: Optional[float], classes: Iterable[str], of_artifact_id: Optional[str] = None) -> dict[str, Any]:
    """A copy of an overlay artifact's notes with `held` and `hold_basis` recomputed from the stored facts. Values are copied
    unchanged; nothing is extracted."""
    new = json.loads(json.dumps(notes))
    compute_hold(new, threshold, classes)
    new["rehold_of"] = of_artifact_id
    return new


# ---- the work ---------------------------------------------------------------------------------------------

def _make_lane2(state: dict[str, Any]):
    sys.path.insert(0, str(_TOOLS_ROOT / "tier2_extractor"))
    import lane2_ocr  # noqa: WPS433 (lazy on purpose)

    return lane2_ocr.make_hook(lane2_ocr.TesseractEngine(), state)


def overlay_constants() -> tuple[str, str]:
    """(producer version, field-map version) without extracting: module constants of the producer."""
    sys.path.insert(0, str(_TOOLS_ROOT / "tier2_extractor"))
    sys.path.insert(0, str(_TOOLS_ROOT))
    import template_overlay  # noqa: WPS433 (lazy on purpose)

    return str(template_overlay.PRODUCER_VERSION), str(template_overlay.FIELD_MAP_VERSION)


def extract_pdf(pdf_bytes: bytes, *, source_name: str, detected_year: Optional[str] = None, lane2: bool = True) -> dict[str, Any]:
    """Run the overlay on bytes. Lazy imports: only reached when the loop flag or the CLI asks for it."""
    sys.path.insert(0, str(_TOOLS_ROOT / "tier2_extractor"))
    sys.path.insert(0, str(_TOOLS_ROOT))
    import template_overlay  # noqa: WPS433 (lazy on purpose)

    state: dict[str, Any] = {}
    hook = _make_lane2(state) if lane2 else None
    return template_overlay.extract_overlay(pdf_bytes, detected_year=detected_year, source_name=source_name, lane2=hook)


_PAGE = 50


def overlay_already_written(client: Any, document_id: str, producer_version: str, field_map_version: str, source_sha256: str,
                            lane2_requested: bool = True) -> bool:
    """True when an overlay artifact that satisfies the whole key exists. The query filters on document, kind, producer, producer
    version and the sha in notes, then pages through EVERY matching row (no fixed window) checking the field-map version and
    whether Lane 2 RAN: a request with Lane 2 is satisfied only by an artifact where it ran (a failed or disabled Lane 2 is
    re-extracted on a plain rerun); a `--no-lane2` request is satisfied by an artifact that did not request it."""
    start = 0
    while True:
        rows = (
            client.table("cds_artifacts").select("id,created_at,notes->field_map_version,notes->lane2_requested,notes->lane2_ran,"
                                                 "notes->lane2_disabled,notes->lane2_failed,notes->ocr_engine")
            .eq("document_id", document_id).eq("kind", "cleaned").eq("producer", OVERLAY_PRODUCER)
            .eq("producer_version", producer_version).eq("notes->>source_sha256", source_sha256)
            .order("created_at", desc=True).range(start, start + _PAGE - 1).execute().data
        ) or []
        for row in rows:
            n = _notes_of(row)
            if str(n.get("field_map_version")) != str(field_map_version):
                continue
            ran = lane2_ran_in(n)
            if (lane2_requested and ran) or (not lane2_requested and not ran and not n.get("lane2_requested", True)):
                return True
        if len(rows) < _PAGE:
            return False
        start += _PAGE


def insert_overlay_artifact(client: Any, document_id: str, notes: dict[str, Any]) -> None:
    text = json.dumps(notes)
    if "\x00" in text or "\\u0000" in text:
        notes = json.loads(text.replace("\x00", "").replace("\\u0000", ""))
    sha = str(notes.get("source_sha256") or "")
    client.table("cds_artifacts").insert({
        "document_id": document_id,
        "kind": "cleaned",                      # never 'canonical': the newest-canonical readers must not see it (A1)
        "producer": OVERLAY_PRODUCER,
        "producer_version": notes["producer_version"],
        "schema_version": notes.get("schema_version"),
        "storage_path": f"cleaned-inline/{document_id}/{OVERLAY_PRODUCER}-{notes['producer_version']}-{sha[:12]}.json",
        "notes": notes,
    }).execute()


def summarize(notes: Mapping[str, Any]) -> dict[str, Any]:
    basis = notes.get("hold_basis") or {}
    return {
        "value_count": notes.get("value_count"), "emission_class_counts": notes.get("emission_class_counts"),
        "lane_counts": notes.get("lane_counts"), "abstention_by_reason": notes.get("abstention_by_reason"),
        "rejected_fields": len(notes.get("rejected_fields") or []),
        "compared_over_hold_classes": basis.get("compared"), "disagree_over_hold_classes": basis.get("disagree"),
        "share_over_hold_classes": basis.get("share"), "held": notes.get("held"), "hold_reason": notes.get("hold_reason"),
        "lane2_ran": notes.get("lane2_ran"), "lane2_disabled": notes.get("lane2_disabled"), "lane2_failed": notes.get("lane2_failed"),
    }


def run_overlay_for_document(
    client: Any,
    doc: Mapping[str, Any],
    *,
    write: bool,
    lane2: bool = True,
    force: bool = False,
    hold_threshold: Any = _UNSET,
    hold_classes: Iterable[str] = (),
) -> OverlayResult:
    """One document, end to end. Never raises (except KeyboardInterrupt): any failure is an `error` result and a log line.
    `hold_threshold` is a float, None (`off`), or unset (read `OVERLAY_HOLD_THRESHOLD` from the environment, which `--env` fills)."""
    document_id = str(doc.get("id") or doc.get("document_id") or "")
    started = time.time()
    try:
        sys.path.insert(0, str(_TOOLS_ROOT))
        sys.path.insert(0, str(_WORKER_DIR))
        import worker                                       # lazy: the worker imports this module only lazily too
        from browser_backend import overlay_serving as serving

        threshold = serving.hold_threshold() if hold_threshold is _UNSET else hold_threshold
        classes = tuple(hold_classes) or serving.HOLD_CANDIDATE_CLASSES
        latest = worker.fetch_latest_source_artifact(client, document_id)
        if not latest:
            return OverlayResult(document_id, "skipped", "no_source_artifact", seconds=time.time() - started)
        latest_bytes = worker.download_source(client, latest["storage_path"])
        selection = worker.select_source_for_extraction(client, document_id, latest, latest_bytes)   # PR #258 first
        pdf_bytes = selection.source_bytes
        ok, reason, info = stage1_prefilter(pdf_bytes)
        if not ok:
            return OverlayResult(document_id, "skipped", reason, summary=info, seconds=time.time() - started)
        sha = hashlib.sha256(pdf_bytes).hexdigest()
        pv, fv = overlay_constants()
        if not force and overlay_already_written(client, document_id, pv, fv, sha, lane2):       # before extracting
            return OverlayResult(document_id, "skipped", "already_overlaid", seconds=time.time() - started)
        out = extract_pdf(pdf_bytes, source_name=document_id, detected_year=doc.get("detected_year"), lane2=lane2)
        notes_in = out.get("notes") or {}
        stage1 = notes_in.get("stage1") or {}
        if stage1.get("status") != "matched":
            return OverlayResult(document_id, "skipped", f"stage1_{stage1.get('status')}:{stage1.get('reason')}",
                                 seconds=time.time() - started)
        base, base_reason = choose_comparison_base(client, document_id, sha, out.get("schema_version"))
        base_values = fetch_base_values(client, str(base["id"])) if base is not None and not base_reason else None
        notes = build_artifact_notes(
            out, selection_note=selection.selection_note, base=base, base_values=base_values, base_reason=base_reason,
            hold_threshold=threshold, hold_classes=classes, lane2_requested=lane2,
            tier4_only_class_of=tier4_only_class_map(str(out.get("schema_version"))).get)
        if write:
            insert_overlay_artifact(client, document_id, notes)
        return OverlayResult(document_id, "written" if write else "dry_run", None, summarize(notes), notes,
                             seconds=time.time() - started)
    except KeyboardInterrupt:
        raise
    except BaseException as exc:                            # an overlay failure never changes anything else
        message = (str(exc).splitlines() or [""])[0][:200]
        print(f"    overlay_error: document={document_id} {type(exc).__name__}: {message}", file=sys.stderr, flush=True)
        return OverlayResult(document_id, "error", f"{type(exc).__name__}: {exc}", seconds=time.time() - started)


def run_rehold_for_document(client: Any, document_id: str, *, threshold: Optional[float], classes: Iterable[str], write: bool) -> OverlayResult:
    """No extraction: recompute `held` for the newest overlay artifact from its stored facts and append a new artifact
    (values copied, new `held` and `hold_basis`) when the outcome or the basis changes. Newest wins in every selector."""
    started = time.time()
    try:
        rows = (client.table("cds_artifacts").select("*").eq("document_id", document_id).eq("kind", "cleaned")
                .eq("producer", OVERLAY_PRODUCER).order("created_at", desc=True).limit(1).execute().data) or []
        if not rows:
            return OverlayResult(document_id, "skipped", "no_overlay_artifact", seconds=time.time() - started)
        row = rows[0]
        notes = row.get("notes") or {}
        if (notes.get("comparison") or {}).get("by_class") is None and not notes.get("structural_hold_reason"):
            return OverlayResult(document_id, "skipped", "no_stored_facts", seconds=time.time() - started)
        classes = tuple(classes)
        new = rehold_notes(notes, threshold, classes, str(row.get("id")))
        old_basis = (notes.get("hold_basis") or {})
        same = (new["held"] == notes.get("held") and old_basis.get("threshold") == new["hold_basis"]["threshold"]
                and old_basis.get("classes") == new["hold_basis"]["classes"])
        summary = {**summarize(new), "was_held": notes.get("held")}
        if same:
            return OverlayResult(document_id, "skipped", "unchanged", summary, seconds=time.time() - started)
        if write:
            insert_overlay_artifact(client, document_id, new)
        return OverlayResult(document_id, "written" if write else "dry_run", None, summary, new, seconds=time.time() - started)
    except KeyboardInterrupt:
        raise
    except BaseException as exc:
        print(f"    rehold_error: document={document_id} {type(exc).__name__}", file=sys.stderr, flush=True)
        return OverlayResult(document_id, "error", f"{type(exc).__name__}: {exc}", seconds=time.time() - started)


def run_overlay_in_loop(client: Any, doc: Mapping[str, Any]) -> Optional[OverlayResult]:
    """Called by the routine worker loop after the Tier 4 outcome, only when OVERLAY_WORKER_ENABLED is on."""
    return run_overlay_for_document(client, doc, write=True)


# ---- CLI --------------------------------------------------------------------------------------------------

def apply_env_file(path: Path) -> dict[str, str]:
    """Load KEY=VALUE lines into the process environment (without overriding values already exported), so `--env` reaches every
    setting the tool reads: credentials, `OVERLAY_HOLD_THRESHOLD`, `CDS_TESSDATA_BEST`, ... Returns what the file held."""
    loaded: dict[str, str] = {}
    if not path.exists():
        return loaded
    for line in path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, _, value = line.partition("=")
            loaded[key.strip()] = value.strip().strip('"').strip("'")
    for key, value in loaded.items():
        os.environ.setdefault(key, value)
    return loaded


def _run_pdf_dir(pdf_dir: Path, out_dir: Path, only: Optional[set[str]], lane2: bool, jobs: int) -> int:
    """Local mode: PDFs named <sha256>.pdf, no database, nothing written except `<out_dir>/<sha>.json`."""
    from multiprocessing import Pool

    out_dir.mkdir(parents=True, exist_ok=True)
    files = sorted(pdf_dir.glob("*.pdf"))
    if only:
        files = [f for f in files if f.stem in only or f.stem[:12] in only]
    work = [(str(f), str(out_dir), lane2) for f in files]
    with Pool(jobs) as pool:
        for line in pool.imap_unordered(_local_job, work, chunksize=1):
            print(line, flush=True)
    return 0


def _local_job(args: tuple[str, str, bool]) -> str:
    pdf, out_dir, lane2 = args
    sys.path.insert(0, str(_TOOLS_ROOT))
    started = time.time()
    sha = Path(pdf).stem
    try:
        data = Path(pdf).read_bytes()
        ok, reason, info = stage1_prefilter(data)
        if not ok:
            record = {"source_sha256": sha, "status": "skipped", "reason": reason, "info": info}
        else:
            out = extract_pdf(data, source_name=sha, lane2=lane2)
            st = (out.get("notes") or {}).get("stage1") or {}
            if st.get("status") != "matched":
                record = {"source_sha256": sha, "status": "skipped", "reason": f"stage1_{st.get('status')}:{st.get('reason')}"}
            else:
                from browser_backend import overlay_serving as serving
                notes = build_artifact_notes(out, base=None, base_reason="tier4_comparison_pending", hold_threshold=serving.hold_threshold(),
                                             hold_classes=serving.HOLD_CANDIDATE_CLASSES, lane2_requested=lane2)
                record = {"source_sha256": sha, "status": "dry_run", "notes": notes}
    except KeyboardInterrupt:
        raise
    except BaseException as exc:
        record = {"source_sha256": sha, "status": "error", "reason": f"{type(exc).__name__}: {exc}",
                  "trace": traceback.format_exc()[-800:]}
    record["seconds"] = round(time.time() - started, 1)
    Path(out_dir, f"{sha}.json").write_text(json.dumps(record))
    return f"{sha[:12]} {record['status']} {record.get('reason') or ''} {record['seconds']}s"


def _parse_threshold_arg(raw: Optional[str]) -> Any:
    sys.path.insert(0, str(_TOOLS_ROOT))
    from browser_backend import overlay_serving as serving

    return _UNSET if raw is None else serving.parse_hold_threshold(raw)


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Run the PRD 038 template overlay alone (no Tier 4, no ledger, no projection). "
                                                 "One serial writer: there is no database uniqueness (see the module docstring).")
    parser.add_argument("--env", default=".env")
    parser.add_argument("--document-ids", default=None, help="Comma-separated cds_documents.id values (database mode).")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true", help="Extract and print a summary; write nothing (the default).")
    mode.add_argument("--write", action="store_true", help="Insert the overlay artifact (kind='cleaned'). Nothing else is written.")
    parser.add_argument("--rehold", action="store_true", help="No extraction: recompute `held` from the stored facts of each document's "
                        "newest overlay artifact under --hold-threshold/--hold-classes and (with --write) append a new artifact.")
    parser.add_argument("--hold-threshold", default=None, help="0..1, or `off`. Default: OVERLAY_HOLD_THRESHOLD from the environment or --env, else 0.05.")
    parser.add_argument("--hold-classes", default="numeric,choice,checkbox_box", help="Classes the disagreement hold is computed over.")
    parser.add_argument("--force", action="store_true", help="Write even if the skip key already exists.")
    parser.add_argument("--no-lane2", action="store_true", help="Skip Lane 2 (numeric OCR); Lane 1 and Lane 3 only.")
    parser.add_argument("--json-out", type=Path, default=None, help="Write the per-document summaries to this JSON file.")
    parser.add_argument("--pdf-dir", type=Path, default=None, help="Local mode: PDFs named <sha256>.pdf; no database at all.")
    parser.add_argument("--out-dir", type=Path, default=None, help="Local mode: where <sha256>.json records go.")
    parser.add_argument("--only", default=None, help="Local mode: comma-separated sha256 (or 12-char prefixes).")
    parser.add_argument("--jobs", type=int, default=6, help="Local mode: parallel documents.")
    args = parser.parse_args(argv)

    loaded_env = apply_env_file(Path(args.env))
    if args.pdf_dir:
        if args.write or args.rehold:
            parser.error("--write and --rehold need the database mode (--document-ids); --pdf-dir is local and writes only --out-dir")
        if not args.out_dir:
            parser.error("--pdf-dir needs --out-dir")
        only = set(args.only.split(",")) if args.only else None
        return _run_pdf_dir(args.pdf_dir, args.out_dir, only, not args.no_lane2, args.jobs)

    if not args.document_ids:
        parser.error("--document-ids is required (or use --pdf-dir)")
    sys.path.insert(0, str(_TOOLS_ROOT))
    sys.path.insert(0, str(_WORKER_DIR))
    from browser_backend import overlay_serving as serving
    from supabase import create_client

    client = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_ROLE_KEY"])
    ids = [i.strip() for i in args.document_ids.split(",") if i.strip()]
    threshold = _parse_threshold_arg(args.hold_threshold)
    if threshold is _UNSET:
        threshold = serving.hold_threshold()
    classes = tuple(c.strip() for c in args.hold_classes.split(",") if c.strip())
    if not classes or any(c not in serving.KNOWN_CLASSES for c in classes):
        parser.error("--hold-classes names an unknown class")
    rows = (client.table("cds_documents").select("id,school_id,detected_year,cds_year,source_format").in_("id", ids).execute().data) or []
    found = {r["id"]: r for r in rows}
    results = []
    for document_id in ids:
        try:
            if args.rehold:
                result = run_rehold_for_document(client, document_id, threshold=threshold, classes=classes, write=bool(args.write))
            else:
                result = run_overlay_for_document(client, found.get(document_id) or {"id": document_id}, write=bool(args.write),
                                                  lane2=not args.no_lane2, force=args.force, hold_threshold=threshold, hold_classes=classes)
        except KeyboardInterrupt:
            raise
        except BaseException as exc:                      # belt and braces: the loop always continues
            result = OverlayResult(document_id, "error", f"{type(exc).__name__}: {exc}")
        print(f"{document_id} {result.status} {result.reason or ''} {json.dumps(result.summary)} {result.seconds:.1f}s", flush=True)
        results.append({"document_id": document_id, "status": result.status, "reason": result.reason,
                        "summary": result.summary, "seconds": round(result.seconds, 1),
                        "notes": result.artifact_notes if args.json_out else None})
    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(json.dumps(results))
    return 1 if any(r["status"] == "error" for r in results) else 0


if __name__ == "__main__":
    sys.exit(main())
