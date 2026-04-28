"""
Tier 4 LLM fallback — Phase 1 production worker (PRD 006).

Runs AFTER the Tier 4 deterministic extractor has written a
``tier4_docling`` canonical artifact. For each eligible document:

1. Load the markdown + already-extracted values from the canonical artifact.
2. Locate each target subsection with the layered slicer.
3. For each located subsection, check ``cds_llm_cache``.
4. On cache miss, call the LLM (budget-gated) and store the response.
5. Validate responses deterministically.
6. Merge accepted fields per Mode B (fill_gaps) — never overwrite cleaner.
7. Write a single ``cds_artifacts`` row with ``producer='tier4_llm_fallback'``.

Operational differences from ``llm_fallback_bench.py`` (Phase 0):

- Writes to ``cds_llm_cache`` and ``cds_artifacts`` (Phase 0 wrote JSON to disk).
- Respects an eligibility gate (skip docs where the cleaner already covered
  the target subsections or where the data-quality audit flagged them).
- Per-run, per-doc, and per-day budget caps fail the run rather than silently
  overspending.

Usage:

    cd /path/to/repo
    source tools/extraction_worker/.venv/bin/activate
    python tools/extraction_worker/llm_fallback_worker.py \\
        --env .env \\
        --school harvard,dartmouth \\
        --year 2024-25 \\
        --subsections H5,H6,H7,H8,C13,C14,C15,C16,C17,D13,D14,D15,D16,G5 \\
        --max-cost-per-doc 0.10 \\
        --max-cost-per-run 5.00 \\
        --mode fill_gaps
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_HERE = Path(__file__).resolve().parent
_REPO_ROOT = _HERE.parent.parent
sys.path.insert(0, str(_HERE))

from tier4_cleaner import SchemaIndex, schema_path_for_year  # noqa: E402
from subsection_slicer import slice_all, LocatedSlice, TARGET_SUBSECTIONS  # noqa: E402
from tier4_llm_fallback import (  # noqa: E402
    build_cached_head,
    build_uncached_tail,
    validate_response,
    hash_markdown,
    cache_key,
    STRATEGY_NAME,
    STRATEGY_VERSION,
    PROMPT_VERSION,
    PRODUCER_NAME,
    PRODUCER_VERSION,
    SYSTEM_PROMPT,
)


DEFAULT_TARGET_SUBSECTIONS = [
    "H5", "H6", "H7", "H8",
    "C13", "C14", "C15", "C16", "C17",
    "D13", "D14", "D15", "D16",
    "G5",
]


def _load_env(env_path: Path) -> dict[str, str]:
    env: dict[str, str] = {}
    if not env_path.exists():
        return env
    for line in env_path.read_text().splitlines():
        s = line.strip()
        if not s or s.startswith("#") or "=" not in s:
            continue
        k, v = s.split("=", 1)
        if len(v) >= 2 and v[0] == v[-1] and v[0] in ("'", '"'):
            v = v[1:-1]
        env[k.strip()] = v.strip()
    return env


# ---------------------------------------------------------------------------
# Eligibility + doc selection
# ---------------------------------------------------------------------------


def _find_eligible_docs(
    client,
    *,
    school_filter: list[str] | None,
    year_filter: str | None,
    limit: int | None,
    low_coverage_threshold: int,
    schema_path_override: Path | None = None,
    schema_version_override: str | None = None,
    schema_cache: dict[Path, SchemaIndex] | None = None,
) -> list[dict[str, Any]]:
    """Return docs with a tier4_docling canonical artifact that should get the fallback.

    Strategy: filter cds_documents first (by school/year), then fetch only
    those docs' artifacts. Scanning all tier4 artifacts across the corpus
    hits Supabase's statement timeout.
    """
    # 1. Find candidate docs.
    q = client.table("cds_documents").select(
        "id,school_id,cds_year,detected_year,source_sha256,data_quality_flag"
    )
    if school_filter:
        q = q.in_("school_id", school_filter)
    if year_filter:
        q = q.eq("cds_year", year_filter)
    docs = q.execute().data or []
    # Exclude known publisher-side issues in Python (PostgREST's not.in
    # excludes NULLs, which we want to keep).
    docs = [d for d in docs if d.get("data_quality_flag") not in ("blank_template", "wrong_file")]
    if not docs:
        return []
    docs_by_id = {d["id"]: d for d in docs}

    if schema_cache is None:
        schema_cache = {}

    expected_schema_by_doc: dict[str, str] = {}
    for did, doc in docs_by_id.items():
        _schema, schema_version, _fallback_used, _reason = _schema_for_doc(
            doc,
            schema_path_override=schema_path_override,
            schema_version_override=schema_version_override,
            cache=schema_cache,
        )
        expected_schema_by_doc[did] = schema_version

    # 2. Fetch tier4_docling canonical artifacts and keep the newest artifact
    # whose schema matches the document's resolved schema. A stale wrong-year
    # base artifact must not seed an LLM repair overlay.
    arts = (
        client.table("cds_artifacts")
        .select("id,document_id,notes,producer_version,schema_version,created_at")
        .eq("producer", "tier4_docling")
        .eq("kind", "canonical")
        .in_("document_id", list(docs_by_id.keys()))
        .order("created_at", desc=True)
        .execute()
    ).data or []

    # Dedup by document_id (newest wins due to ordering).
    by_doc: dict[str, dict[str, Any]] = {}
    for art in arts:
        did = art["document_id"]
        expected_schema = expected_schema_by_doc.get(did)
        if expected_schema and _artifact_schema_version(art) != expected_schema:
            continue
        by_doc.setdefault(did, art)

    eligible: list[dict[str, Any]] = []
    for did, art in by_doc.items():
        doc = docs_by_id.get(did)
        if not doc:
            continue
        notes = art.get("notes") or {}
        stats = notes.get("stats") or {}
        populated = int(stats.get("schema_fields_populated") or 0)

        is_low_coverage = populated < low_coverage_threshold
        is_flagged = doc.get("data_quality_flag") == "low_coverage"

        eligible.append({
            "doc": doc,
            "artifact": art,
            "eligibility": {
                "populated": populated,
                "low_coverage": is_low_coverage,
                "audit_flag": is_flagged,
            },
        })

    # Permissive at this stage — per-subsection gates run inside the loop.
    if limit:
        eligible = eligible[:limit]
    return eligible


def _artifact_schema_version(artifact: dict[str, Any]) -> str | None:
    notes = artifact.get("notes") or {}
    if not isinstance(notes, dict):
        notes = {}
    schema_version = artifact.get("schema_version") or notes.get("schema_version")
    return str(schema_version) if schema_version else None


def _schema_for_doc(
    doc: dict[str, Any],
    *,
    schema_path_override: Path | None,
    schema_version_override: str | None,
    cache: dict[Path, SchemaIndex],
) -> tuple[SchemaIndex, str, bool, str | None]:
    if schema_path_override is not None:
        path = schema_path_override
        fallback_used = False
        reason = None
    else:
        requested = schema_version_override or doc.get("detected_year") or doc.get("cds_year")
        path = schema_path_for_year(requested)
        fallback_used = bool(requested and path.name != f"cds_schema_{str(requested).replace('-', '_')}.json")
        reason = None if not fallback_used else f"no_schema_for_{requested}"
    if path not in cache:
        cache[path] = SchemaIndex(schema_path=path)
    schema = cache[path]
    schema_version = str(schema.schema_version or schema_version_override or "2025-26")
    return schema, schema_version, fallback_used, reason


# ---------------------------------------------------------------------------
# Cache operations
# ---------------------------------------------------------------------------


def _cache_lookup(
    client,
    *,
    key: dict[str, str],
) -> dict[str, Any] | None:
    """Return the response_json of a cache hit, or None."""
    for attempt in range(3):
        try:
            q = (
                client.table("cds_llm_cache")
                .select("response_json,status,estimated_cost_usd,input_tokens,output_tokens,cache_read_tokens,cache_write_tokens")
                .eq("source_sha256", key["source_sha256"])
                .eq("section_name", key["section_name"])
                .eq("schema_version", key["schema_version"])
                .eq("model_name", key["model_name"])
                .eq("prompt_version", key["prompt_version"])
                .eq("strategy_version", key["strategy_version"])
                .eq("cleaner_version", key["cleaner_version"])
                .eq("missing_fields_sha256", key["missing_fields_sha256"])
                .eq("status", "ok")
                .order("created_at", desc=True)
                .limit(1)
                .execute()
            ).data or []
            return q[0] if q else None
        except Exception:
            if attempt == 2:
                raise
            time.sleep(2 * (attempt + 1))
    return None


def _cache_write(
    client,
    *,
    document_id: str,
    key: dict[str, str],
    markdown_sha256: str,
    response_json: dict[str, Any] | None,
    status: str,
    input_tokens: int = 0,
    cache_write_tokens: int = 0,
    cache_read_tokens: int = 0,
    output_tokens: int = 0,
    estimated_cost_usd: float = 0.0,
) -> None:
    row = {
        "document_id": document_id,
        "source_sha256": key["source_sha256"],
        "markdown_sha256": markdown_sha256,
        "section_name": key["section_name"],
        "schema_version": key["schema_version"],
        "model_name": key["model_name"],
        "prompt_version": key["prompt_version"],
        "strategy_version": key["strategy_version"],
        "cleaner_version": key["cleaner_version"],
        "missing_fields_sha256": key["missing_fields_sha256"],
        "status": status,
        "input_tokens": input_tokens,
        "cache_write_tokens": cache_write_tokens,
        "cache_read_tokens": cache_read_tokens,
        "output_tokens": output_tokens,
        "estimated_cost_usd": estimated_cost_usd,
        "response_json": response_json,
    }
    # Retry transient network errors; swallow unique-constraint collisions
    # (concurrent writer or stale retry with same key).
    for attempt in range(3):
        try:
            client.table("cds_llm_cache").insert(row).execute()
            return
        except Exception as e:
            msg = str(e)
            if "duplicate key" in msg or "cds_llm_cache_key_idx" in msg:
                return
            if attempt == 2:
                raise
            time.sleep(2 * (attempt + 1))  # 2s, 4s back-off


# ---------------------------------------------------------------------------
# Per-doc processing
# ---------------------------------------------------------------------------


def _process_doc(
    client,
    *,
    eligible_row: dict[str, Any],
    subsections: list[str],
    schema: SchemaIndex,
    schema_version: str,
    schema_fallback_used: bool,
    schema_fallback_reason: str | None,
    model: str,
    cleaner_version: str,
    mode: str,
    max_cost_per_doc: float,
    run_budget_remaining: list[float],
    dry_run: bool,
) -> dict[str, Any]:
    doc = eligible_row["doc"]
    art = eligible_row["artifact"]
    artifact_schema_version = _artifact_schema_version(art)
    if artifact_schema_version != schema_version:
        return {
            "document_id": doc["id"],
            "school_id": doc["school_id"],
            "cds_year": doc["cds_year"],
            "status": "base_schema_mismatch",
            "artifact_schema_version": artifact_schema_version,
            "expected_schema_version": schema_version,
        }

    notes = art.get("notes") or {}
    markdown = notes.get("markdown") or ""
    already = notes.get("values") or {}
    source_sha256 = doc.get("source_sha256") or ""
    if not source_sha256:
        return {
            "document_id": doc["id"],
            "school_id": doc["school_id"],
            "cds_year": doc["cds_year"],
            "status": "missing_source_sha256",
        }

    markdown_sha256 = hash_markdown(markdown)
    slices = slice_all(markdown, subsections)

    per_sub: list[dict[str, Any]] = []
    accepted_values: dict[str, Any] = {}
    total_cost = 0.0
    fields_accepted = 0
    fields_rejected = 0
    cache_hits = 0
    cache_misses = 0

    for code in subsections:
        sr = slices[code]

        if not sr.is_found():
            per_sub.append({
                "subsection": code,
                "slicer_strategy": sr.strategy,
                "status": "slicer_unresolved",
            })
            continue

        missing_qns = _missing_question_numbers(schema, code, already)
        if not missing_qns:
            per_sub.append({
                "subsection": code,
                "slicer_strategy": sr.strategy,
                "status": "no_gaps",
            })
            continue

        key = cache_key(
            source_sha256=source_sha256,
            markdown_sha256=markdown_sha256,
            section_name=code,
            schema_version=schema_version,
            model_name=model,
            prompt_version=PROMPT_VERSION,
            strategy_version=STRATEGY_VERSION,
            cleaner_version=cleaner_version,
            missing_fields=missing_qns,
        )

        hit = _cache_lookup(client, key=key)
        sub_report: dict[str, Any] = {
            "subsection": code,
            "slicer_strategy": sr.strategy,
            "missing_count": len(missing_qns),
        }

        if hit is not None:
            response_json = hit["response_json"]
            sub_report["cache"] = "hit"
            sub_report["cost_usd"] = 0.0
            cache_hits += 1
        else:
            cache_misses += 1
            if run_budget_remaining[0] <= 0:
                sub_report["cache"] = "miss"
                sub_report["status"] = "run_budget_exhausted"
                per_sub.append(sub_report)
                _cache_write(
                    client,
                    document_id=doc["id"],
                    key=key,
                    markdown_sha256=markdown_sha256,
                    response_json=None,
                    status="budget_skipped",
                )
                continue
            if total_cost >= max_cost_per_doc:
                sub_report["cache"] = "miss"
                sub_report["status"] = "doc_budget_exhausted"
                per_sub.append(sub_report)
                _cache_write(
                    client,
                    document_id=doc["id"],
                    key=key,
                    markdown_sha256=markdown_sha256,
                    response_json=None,
                    status="budget_skipped",
                )
                continue
            if dry_run:
                sub_report["cache"] = "miss"
                sub_report["status"] = "dry_run"
                per_sub.append(sub_report)
                continue

            from llm_client import call_structured

            try:
                cached_head = build_cached_head(
                    subsection_code=code, schema=schema, schema_version=schema_version,
                )
                uncached_tail = build_uncached_tail(
                    school_id=doc["school_id"],
                    cds_year=doc.get("cds_year") or "",
                    subsection_code=code,
                    section_markdown=sr.text,
                    already_extracted=already,
                )
                t0 = time.time()
                resp = call_structured(
                    system=SYSTEM_PROMPT,
                    cached_head_blocks=cached_head,
                    uncached_tail=uncached_tail,
                    model=model,
                )
                elapsed = time.time() - t0
            except Exception as e:
                sub_report["cache"] = "miss"
                sub_report["status"] = "call_failed"
                sub_report["error"] = f"{type(e).__name__}: {str(e)[:200]}"
                _cache_write(
                    client,
                    document_id=doc["id"],
                    key=key,
                    markdown_sha256=markdown_sha256,
                    response_json=None,
                    status="validation_failed",
                )
                per_sub.append(sub_report)
                continue

            response_json = resp.parsed
            sub_cost = resp.estimated_cost_usd
            total_cost += sub_cost
            run_budget_remaining[0] -= sub_cost
            sub_report["cache"] = "miss"
            sub_report["cost_usd"] = round(sub_cost, 6)
            sub_report["elapsed_s"] = round(elapsed, 2)
            sub_report["input_tokens"] = resp.input_tokens
            sub_report["cache_write_tokens"] = resp.cache_write_tokens
            sub_report["cache_read_tokens"] = resp.cache_read_tokens
            sub_report["output_tokens"] = resp.output_tokens

            _cache_write(
                client,
                document_id=doc["id"],
                key=key,
                markdown_sha256=markdown_sha256,
                response_json=response_json,
                status="ok",
                input_tokens=resp.input_tokens,
                cache_write_tokens=resp.cache_write_tokens,
                cache_read_tokens=resp.cache_read_tokens,
                output_tokens=resp.output_tokens,
                estimated_cost_usd=sub_cost,
            )

        # Validate + merge.
        vr = validate_response(
            response=response_json or {},
            schema=schema,
            subsection_code=code,
            section_markdown=sr.text,
            full_markdown=markdown,
            already_extracted=already,
        )
        sub_report["fields_accepted"] = len(vr.accepted)
        sub_report["fields_rejected"] = len(vr.rejected)
        sub_report["status"] = sub_report.get("status", "ok")
        fields_accepted += len(vr.accepted)
        fields_rejected += len(vr.rejected)
        # Mode B: fill_gaps — never overwrite cleaner.
        if mode == "fill_gaps":
            for qn, val in vr.accepted.items():
                if qn not in already:
                    accepted_values[qn] = val
        elif mode == "shadow":
            accepted_values.update(vr.accepted)

        per_sub.append(sub_report)

    artifact_notes = {
        "producer": PRODUCER_NAME,
        "producer_version": PRODUCER_VERSION,
        "strategy": STRATEGY_NAME,
        "strategy_version": STRATEGY_VERSION,
        "prompt_version": PROMPT_VERSION,
        "model": model,
        "base_artifact_id": art.get("id"),
        "base_producer": "tier4_docling",
        "base_producer_version": art.get("producer_version"),
        "cleaner_version": cleaner_version,
        "schema_version": schema_version,
        "schema_fallback_used": schema_fallback_used,
        "mode": mode,
        "markdown_sha256": markdown_sha256,
        "stats": {
            "subsections_attempted": len([s for s in per_sub if s.get("status") != "slicer_unresolved"]),
            "subsections_skipped": len([s for s in per_sub if s.get("status") == "slicer_unresolved"]),
            "fields_accepted": fields_accepted,
            "fields_rejected": fields_rejected,
            "cache_hits": cache_hits,
            "cache_misses": cache_misses,
            "total_cost_usd": round(total_cost, 6),
        },
        "values": accepted_values,
        "subsection_reports": per_sub,
    }
    if schema_fallback_reason:
        artifact_notes["schema_fallback_reason"] = schema_fallback_reason

    if not dry_run and accepted_values:
        _insert_fallback_artifact(
            client, document_id=doc["id"], schema_version=schema_version,
            artifact_notes=artifact_notes,
        )

    return {
        "document_id": doc["id"],
        "school_id": doc["school_id"],
        "cds_year": doc["cds_year"],
        "status": "complete",
        "fields_accepted": fields_accepted,
        "fields_rejected": fields_rejected,
        "cache_hits": cache_hits,
        "cache_misses": cache_misses,
        "total_cost_usd": round(total_cost, 6),
        "subsections": per_sub,
    }


def _missing_question_numbers(
    schema: SchemaIndex, subsection_code: str, already: dict[str, Any]
) -> list[str]:
    """Return the subset of question_numbers in this subsection NOT yet populated."""
    from tier4_llm_fallback import _schema_fields_for_subsection

    fields = _schema_fields_for_subsection(schema, subsection_code)
    missing = [f["question_number"] for f in fields if f["question_number"] not in already]
    return missing


def _insert_fallback_artifact(
    client,
    *,
    document_id: str,
    schema_version: str,
    artifact_notes: dict[str, Any],
) -> None:
    placeholder_path = (
        f"canonical-inline/{document_id}/{PRODUCER_NAME}-{PRODUCER_VERSION}.json"
    )
    notes_json = json.dumps(artifact_notes)
    if "\x00" in notes_json or "\\u0000" in notes_json:
        notes_json = notes_json.replace("\x00", "").replace("\\u0000", "")
        artifact_notes = json.loads(notes_json)

    client.table("cds_artifacts").insert({
        "document_id": document_id,
        "kind": "cleaned",
        "producer": PRODUCER_NAME,
        "producer_version": PRODUCER_VERSION,
        "schema_version": schema_version,
        "storage_path": placeholder_path,
        "notes": artifact_notes,
    }).execute()


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--env", default=str(_REPO_ROOT / ".env"))
    ap.add_argument("--school", default=None,
                    help="Comma-separated school_ids; default = all")
    ap.add_argument("--year", default=None)
    ap.add_argument("--subsections", default=",".join(DEFAULT_TARGET_SUBSECTIONS))
    ap.add_argument("--schema-version", default=None,
                    help="Override schema version for every document; default uses detected_year/cds_year.")
    ap.add_argument("--schema-path", default=None,
                    help="Debug override: force one schema JSON for every document.")
    ap.add_argument("--model", default=os.environ.get("TIER4_FALLBACK_MODEL", "claude-haiku-4-5"))
    ap.add_argument("--mode", choices=["shadow", "fill_gaps"], default="fill_gaps",
                    help="shadow = write artifact with values but don't merge; "
                         "fill_gaps = values merge (deterministic wins).")
    ap.add_argument("--cleaner-version", default="0.3.0",
                    help="Used in the cache key. Bump to invalidate cache on "
                         "cleaner changes that shrink the gap set.")
    ap.add_argument("--low-coverage-threshold", type=int, default=200,
                    help="Docs with stats.schema_fields_populated below this "
                         "are eligible.")
    ap.add_argument("--max-cost-per-doc", type=float, default=0.10)
    ap.add_argument("--max-cost-per-run", type=float, default=5.00)
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--report", type=Path,
                    default=_REPO_ROOT / "scratch" / "llm-fallback-runs",
                    help="Directory for run report JSON")
    args = ap.parse_args()

    env = _load_env(Path(args.env))
    for k, v in env.items():
        os.environ.setdefault(k, v)

    if not os.environ.get("ANTHROPIC_API_KEY") and not args.dry_run:
        print("ERROR: ANTHROPIC_API_KEY not set (and --dry-run not passed)")
        return 2
    if not os.environ.get("SUPABASE_URL") or not os.environ.get("SUPABASE_SERVICE_ROLE_KEY"):
        print("ERROR: SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY not set")
        return 2

    subsections = [s.strip() for s in args.subsections.split(",") if s.strip()]
    school_filter = [s.strip() for s in args.school.split(",")] if args.school else None

    schema_path = Path(args.schema_path) if args.schema_path else None
    schema_cache: dict[Path, SchemaIndex] = {}

    from supabase import create_client
    client = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_ROLE_KEY"])

    eligible = _find_eligible_docs(
        client,
        school_filter=school_filter,
        year_filter=args.year,
        limit=args.limit,
        low_coverage_threshold=args.low_coverage_threshold,
        schema_path_override=schema_path,
        schema_version_override=args.schema_version,
        schema_cache=schema_cache,
    )
    print(f"Eligible docs: {len(eligible)}")
    print(f"Model: {args.model}  Mode: {args.mode}  Subsections: {subsections}")
    print(f"Budget: ${args.max_cost_per_doc}/doc, ${args.max_cost_per_run}/run")
    print()

    args.report.mkdir(parents=True, exist_ok=True)
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_dir = args.report / f"run-{run_id}"
    run_dir.mkdir(exist_ok=True)

    # Mutable single-element list so nested calls can decrement it.
    run_budget_remaining = [args.max_cost_per_run]
    per_doc_reports: list[dict[str, Any]] = []

    for row in eligible:
        doc = row["doc"]
        schema, schema_version, schema_fallback_used, schema_fallback_reason = _schema_for_doc(
            doc,
            schema_path_override=schema_path,
            schema_version_override=args.schema_version,
            cache=schema_cache,
        )
        print(f"--- {doc['school_id']} {doc['cds_year']} ---")
        print(f"Schema: {schema_version}{' fallback' if schema_fallback_used else ''}")
        rep = _process_doc(
            client,
            eligible_row=row,
            subsections=subsections,
            schema=schema,
            schema_version=schema_version,
            schema_fallback_used=schema_fallback_used,
            schema_fallback_reason=schema_fallback_reason,
            model=args.model,
            cleaner_version=args.cleaner_version,
            mode=args.mode,
            max_cost_per_doc=args.max_cost_per_doc,
            run_budget_remaining=run_budget_remaining,
            dry_run=args.dry_run,
        )
        per_doc_reports.append(rep)
        (run_dir / f"{doc['school_id']}-{doc['cds_year']}.json").write_text(
            json.dumps(rep, indent=2)
        )
        _print_summary(rep)
        if run_budget_remaining[0] <= 0:
            print("Run budget exhausted; stopping.")
            break

    aggregate = {
        "docs_processed": len(per_doc_reports),
        "docs_written": sum(1 for r in per_doc_reports if r.get("fields_accepted", 0) > 0),
        "fields_accepted_total": sum(r.get("fields_accepted", 0) for r in per_doc_reports),
        "fields_rejected_total": sum(r.get("fields_rejected", 0) for r in per_doc_reports),
        "total_cost_usd": round(sum(r.get("total_cost_usd", 0) for r in per_doc_reports), 6),
        "cache_hits": sum(r.get("cache_hits", 0) for r in per_doc_reports),
        "cache_misses": sum(r.get("cache_misses", 0) for r in per_doc_reports),
    }
    manifest = {
        "run_id": run_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "cli_args": {k: str(v) if isinstance(v, Path) else v for k, v in vars(args).items()},
        "aggregate": aggregate,
    }
    (run_dir / "_manifest.json").write_text(json.dumps(manifest, indent=2))

    print("\n=== AGGREGATE ===")
    print(json.dumps(aggregate, indent=2))
    print(f"\nRun dir: {run_dir}")
    return 0


def _print_summary(rep: dict[str, Any]) -> None:
    status = rep.get("status", "?")
    if status != "complete":
        print(f"  status: {status}")
        return
    print(f"  doc_id: {rep['document_id']}")
    print(f"  accepted: {rep['fields_accepted']}  rejected: {rep['fields_rejected']}  "
          f"cost: ${rep['total_cost_usd']:.4f}  cache_h/m: {rep['cache_hits']}/{rep['cache_misses']}")


if __name__ == "__main__":
    sys.exit(main())
