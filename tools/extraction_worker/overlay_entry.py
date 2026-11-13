"""PRD 038 A5: the template-overlay worker entry point and its scoped CLI.

The overlay is its own entry point, not a hook after the Tier 4 insert: `_run_tier4` returns early on
`already_extracted` and `tier4_field_regression`, which is the state of every cohort document. It has its own
idempotency key (document id, producer, producer version, field-map version, source sha256).

Safety rules (the M3 "no production change on merge" rule):

* Nothing here is imported at the top level of `worker.py`. The overlay stack (cv2, pdfium, Tesseract) is
  imported lazily inside `run_overlay_for_document`, inside try/except, and only when the loop flag is on or the
  CLI is used. A broken or missing overlay package changes nothing about the daily drain.
* An overlay failure of any kind is logged and returned as an error result. It never changes a document's
  extraction_status, quality flag, ledger row, heartbeat or projection, and never calls the revalidation hook.
* The CLI neither writes a heartbeat or ledger row, nor refreshes the projection, nor notifies the web, in
  either mode. `--dry-run` (the default) writes nothing at all; `--write` inserts only the overlay artifact
  (`kind='cleaned'`, `producer='tier2_template_overlay'`; never `canonical`).
* The routine worker loop calls the overlay only when `OVERLAY_WORKER_ENABLED` is truthy (default off).

CLI (from the repo root, with the worker environment):

    python tools/extraction_worker/overlay_entry.py --document-ids <id>[,<id>...]            # dry run (default)
    python tools/extraction_worker/overlay_entry.py --document-ids <id>,<id> --write         # writes artifacts
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
from typing import Any, Mapping, Optional

_WORKER_DIR = Path(__file__).resolve().parent
_TOOLS_ROOT = _WORKER_DIR.parent
OVERLAY_PRODUCER = "tier2_template_overlay"
ENV_LOOP_FLAG = "OVERLAY_WORKER_ENABLED"
MIN_PAGES, MAX_PAGES = 30, 70            # A5 pre-filter page window (the overlay's own Stage 1 re-checks)
MAX_USABLE_ACROFORM_VALUES = 10          # more schema-mapped populated AcroForm values than this: Tier 2 reads the document


def overlay_loop_enabled(env: Optional[Mapping[str, str]] = None) -> bool:
    raw = (os.environ if env is None else env).get(ENV_LOOP_FLAG, "")
    return str(raw).strip().lower() in {"1", "true", "yes", "on"}


def idempotency_key(document_id: str, producer_version: str, field_map_version: str, source_sha256: str) -> tuple:
    return (str(document_id), OVERLAY_PRODUCER, str(producer_version), str(field_map_version), str(source_sha256))


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


# ---- the overlay artifact --------------------------------------------------------------------------------

# Keys of the overlay's own notes that are bulky per-widget lists; the artifact keeps their counts instead.
_DROP_NOTE_KEYS = {"withheld", "ocr_widgets", "unmapped_fields", "skipped_null_question_number", "ambiguous_radios"}


def build_artifact_notes(
    out: Mapping[str, Any],
    *,
    selection_note: Optional[Mapping[str, Any]] = None,
    tier4_base: Optional[Mapping[str, Any]] = None,
    hold_threshold: float,
) -> dict[str, Any]:
    """The `cds_artifacts.notes` of an overlay artifact: its values (all classes, with `emission_class`, `lane`
    and `derived_lanes`) and the audit fields. Which classes are served is decided at read time, not here."""
    sys.path.insert(0, str(_TOOLS_ROOT))
    from browser_backend import overlay_serving as serving

    inner = dict(out.get("notes") or {})
    values = dict(out.get("values") or {})
    notes: dict[str, Any] = {
        "producer": out.get("producer"),
        "producer_version": out.get("producer_version"),
        "schema_version": out.get("schema_version"),
        "extracted_at": out.get("extracted_at"),
        "stats": out.get("stats") or {},
        "values": values,
    }
    for key, value in inner.items():
        if key in _DROP_NOTE_KEYS or key in notes:
            continue
        notes[key] = value
    notes["withheld_count"] = len(inner.get("withheld") or [])
    notes["abstention_by_reason"] = dict(inner.get("withheld_by_reason") or {})
    stage1 = inner.get("stage1") or {}
    notes["rejected_pages"] = stage1.get("rejected_pages") or {}
    if selection_note:
        notes["source_selection"] = dict(selection_note)
    notes["value_count"] = len(values)
    notes["emission_class_counts"] = dict(inner.get("emission_class_counts") or {})
    # Decision 3 hold: share of the fields both producers populate on which they disagree.
    base_schema = (tier4_base or {}).get("schema_version")
    if tier4_base is not None and (not base_schema or str(base_schema) != str(out.get("schema_version"))):
        # Question ids are not comparable across numberings: no disagreement share can be computed (A13).
        notes["base_artifact_id"] = str(tier4_base.get("id")) if tier4_base.get("id") else None
        notes["base_producer_version"] = tier4_base.get("producer_version")
        notes["base_schema_version"] = base_schema
        notes["tier4_both_populated"] = notes["tier4_disagreeing"] = notes["tier4_disagreement_share"] = None
        notes["held"] = True
        notes["hold_reason"] = "tier4_schema_mismatch"
    elif tier4_base is not None:
        base_values = (tier4_base.get("notes") or {}).get("values") or {}
        summary = serving.disagreement_summary(base_values, values)
        notes["base_artifact_id"] = str(tier4_base.get("id")) if tier4_base.get("id") else None
        notes["base_producer_version"] = tier4_base.get("producer_version")
        notes["tier4_both_populated"] = summary["both_populated"]
        notes["tier4_disagreeing"] = summary["disagreeing"]
        notes["tier4_disagreement_share"] = summary["share"]
        notes["held"] = bool(summary["share"] > hold_threshold)
        notes["hold_reason"] = "tier4_disagreement_share_above_threshold" if notes["held"] else None
    else:
        notes["base_artifact_id"] = None
        notes["tier4_both_populated"] = None
        notes["tier4_disagreeing"] = None
        notes["tier4_disagreement_share"] = None
        notes["held"] = True                       # nothing to compare with: never served until re-run against a base
        notes["hold_reason"] = "no_tier4_base"
    notes["hold_threshold"] = hold_threshold
    if (inner.get("held") or {}).get("status"):
        notes["document_hold"] = inner["held"]       # Stage 1 held the document (no values then)
    return notes


# ---- the work ---------------------------------------------------------------------------------------------

def _make_lane2(state: dict[str, Any]):
    sys.path.insert(0, str(_TOOLS_ROOT / "tier2_extractor"))
    import lane2_ocr  # noqa: WPS433 (lazy on purpose)

    return lane2_ocr.make_hook(lane2_ocr.TesseractEngine(), state)


def extract_pdf(pdf_bytes: bytes, *, source_name: str, detected_year: Optional[str] = None, lane2: bool = True) -> dict[str, Any]:
    """Run the overlay on bytes. Lazy imports: only reached when the loop flag or the CLI asks for it."""
    sys.path.insert(0, str(_TOOLS_ROOT / "tier2_extractor"))
    sys.path.insert(0, str(_TOOLS_ROOT))
    import template_overlay  # noqa: WPS433 (lazy on purpose)

    state: dict[str, Any] = {}
    hook = _make_lane2(state) if lane2 else None
    return template_overlay.extract_overlay(pdf_bytes, detected_year=detected_year, source_name=source_name, lane2=hook)


def fetch_tier4_base(client: Any, document_id: str) -> Optional[dict[str, Any]]:
    rows = (
        client.table("cds_artifacts").select("id,producer_version,schema_version,created_at,notes")
        .eq("document_id", document_id).eq("kind", "canonical").eq("producer", "tier4_docling")
        .order("created_at", desc=True).limit(1).execute().data
    ) or []
    return rows[0] if rows else None


def overlay_already_written(client: Any, document_id: str, producer_version: str, field_map_version: str, source_sha256: str) -> bool:
    rows = (
        client.table("cds_artifacts").select("id,notes")
        .eq("document_id", document_id).eq("kind", "cleaned").eq("producer", OVERLAY_PRODUCER)
        .eq("producer_version", producer_version).order("created_at", desc=True).limit(20).execute().data
    ) or []
    for row in rows:
        notes = row.get("notes") or {}
        if notes.get("source_sha256") == source_sha256 and notes.get("field_map_version") == field_map_version:
            return True
    return False


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
    return {
        "value_count": notes.get("value_count"),
        "emission_class_counts": notes.get("emission_class_counts"),
        "lane_counts": notes.get("lane_counts"),
        "abstention_by_reason": notes.get("abstention_by_reason"),
        "rejected_fields": len(notes.get("rejected_fields") or []),
        "tier4_both_populated": notes.get("tier4_both_populated"),
        "tier4_disagreement_share": notes.get("tier4_disagreement_share"),
        "held": notes.get("held"),
        "hold_reason": notes.get("hold_reason"),
    }


def run_overlay_for_document(
    client: Any,
    doc: Mapping[str, Any],
    *,
    write: bool,
    lane2: bool = True,
    force: bool = False,
    hold_threshold: Optional[float] = None,
) -> OverlayResult:
    """One document, end to end. Never raises: any failure is an `error` result and a log line."""
    document_id = str(doc.get("id") or doc.get("document_id") or "")
    started = time.time()
    try:
        sys.path.insert(0, str(_TOOLS_ROOT))
        sys.path.insert(0, str(_WORKER_DIR))
        import worker                                       # lazy: the worker imports this module only lazily too
        from browser_backend import overlay_serving as serving

        threshold = serving.hold_threshold() if hold_threshold is None else hold_threshold
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
        out = extract_pdf(pdf_bytes, source_name=document_id, detected_year=doc.get("detected_year"), lane2=lane2)
        notes_in = out.get("notes") or {}
        if (notes_in.get("stage1") or {}).get("status") != "matched":
            st = notes_in.get("stage1") or {}
            return OverlayResult(document_id, "skipped", f"stage1_{st.get('status')}:{st.get('reason')}",
                                 seconds=time.time() - started)
        pv, fv = str(out.get("producer_version")), str(notes_in.get("field_map_version"))
        if not force and overlay_already_written(client, document_id, pv, fv, sha):
            return OverlayResult(document_id, "skipped", "already_overlaid", seconds=time.time() - started)
        base = fetch_tier4_base(client, document_id)
        notes = build_artifact_notes(out, selection_note=selection.selection_note, tier4_base=base, hold_threshold=threshold)
        if write:
            insert_overlay_artifact(client, document_id, notes)
        return OverlayResult(document_id, "written" if write else "dry_run", None, summarize(notes), notes,
                             seconds=time.time() - started)
    except Exception as exc:                                # an overlay failure never changes anything else
        message = (str(exc).splitlines() or [""])[0][:200]
        print(f"    overlay_error: document={document_id} {type(exc).__name__}: {message}", file=sys.stderr, flush=True)
        return OverlayResult(document_id, "error", f"{type(exc).__name__}: {exc}", seconds=time.time() - started)


def run_overlay_in_loop(client: Any, doc: Mapping[str, Any]) -> Optional[OverlayResult]:
    """Called by the routine worker loop after the Tier 4 outcome, only when OVERLAY_WORKER_ENABLED is on."""
    return run_overlay_for_document(client, doc, write=True)


# ---- CLI --------------------------------------------------------------------------------------------------

def _load_env_file(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, _, value = line.partition("=")
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


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
                notes = build_artifact_notes(out, tier4_base=None, hold_threshold=serving.hold_threshold())
                notes["hold_reason"] = "tier4_comparison_pending"          # filled in by the shadow report
                record = {"source_sha256": sha, "status": "dry_run", "notes": notes}
    except Exception as exc:
        record = {"source_sha256": sha, "status": "error", "reason": f"{type(exc).__name__}: {exc}",
                  "trace": traceback.format_exc()[-800:]}
    record["seconds"] = round(time.time() - started, 1)
    Path(out_dir, f"{sha}.json").write_text(json.dumps(record))
    return f"{sha[:12]} {record['status']} {record.get('reason') or ''} {record['seconds']}s"


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Run the PRD 038 template overlay alone (no Tier 4, no ledger, no projection).")
    parser.add_argument("--env", default=".env")
    parser.add_argument("--document-ids", default=None, help="Comma-separated cds_documents.id values (database mode).")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true", help="Extract and print a summary; write nothing (the default).")
    mode.add_argument("--write", action="store_true", help="Insert the overlay artifact (kind='cleaned'). Nothing else is written.")
    parser.add_argument("--force", action="store_true", help="Write even if the idempotency key already exists.")
    parser.add_argument("--no-lane2", action="store_true", help="Skip Lane 2 (numeric OCR); Lane 1 and Lane 3 only.")
    parser.add_argument("--json-out", type=Path, default=None, help="Write the per-document summaries to this JSON file.")
    parser.add_argument("--pdf-dir", type=Path, default=None, help="Local mode: PDFs named <sha256>.pdf; no database at all.")
    parser.add_argument("--out-dir", type=Path, default=None, help="Local mode: where <sha256>.json records go.")
    parser.add_argument("--only", default=None, help="Local mode: comma-separated sha256 (or 12-char prefixes).")
    parser.add_argument("--jobs", type=int, default=6, help="Local mode: parallel documents.")
    args = parser.parse_args(argv)

    if args.pdf_dir:
        if args.write:
            parser.error("--write needs the database mode (--document-ids); --pdf-dir is local and writes only --out-dir")
        if not args.out_dir:
            parser.error("--pdf-dir needs --out-dir")
        only = set(args.only.split(",")) if args.only else None
        return _run_pdf_dir(args.pdf_dir, args.out_dir, only, not args.no_lane2, args.jobs)

    if not args.document_ids:
        parser.error("--document-ids is required (or use --pdf-dir)")
    sys.path.insert(0, str(_TOOLS_ROOT))
    sys.path.insert(0, str(_WORKER_DIR))
    import worker                                              # noqa: WPS433
    env = {**worker.load_env(Path(args.env)), **os.environ}
    from supabase import create_client

    client = create_client(env["SUPABASE_URL"], env["SUPABASE_SERVICE_ROLE_KEY"])
    ids = [i.strip() for i in args.document_ids.split(",") if i.strip()]
    rows = (client.table("cds_documents").select("id,school_id,detected_year,cds_year,source_format").in_("id", ids).execute().data) or []
    found = {r["id"]: r for r in rows}
    results = []
    for document_id in ids:
        doc = found.get(document_id) or {"id": document_id}
        result = run_overlay_for_document(client, doc, write=bool(args.write), lane2=not args.no_lane2, force=args.force)
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
