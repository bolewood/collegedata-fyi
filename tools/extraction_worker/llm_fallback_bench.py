"""
Tier 4 LLM fallback — Phase 0 benchmark CLI (PRD 006).

Standalone benchmark harness. Reads existing ``tier4_docling`` canonical
artifacts from the DB, runs section-scoped LLM prompts, validates the
responses deterministically, and writes a single JSON report to disk.

Does NOT write to the database. This is the Phase 0 decision-gate tool: it
produces cost/coverage numbers before any production-shaped infrastructure
(worker, migration, artifact writes) gets built.

Usage:

    cd tools/extraction_worker
    source .venv/bin/activate        # requires anthropic + supabase + python-dotenv
    pip install anthropic python-dotenv  # one-time

    # Smoke test — one school, one subsection
    ANTHROPIC_API_KEY=sk-ant-... python llm_fallback_bench.py \\
        --school yale --year 2024-25 --subsections H5 \\
        --out-dir ../../scratch/llm-bench/

    # Phase 0 benchmark — three GT schools, priority subsections
    ANTHROPIC_API_KEY=sk-ant-... python llm_fallback_bench.py \\
        --school harvard,yale,dartmouth --year 2024-25 \\
        --subsections H5,H6,H7,H8,C13,C14,C15,C16,C17,D13,D14,D15,D16,G5 \\
        --max-cost-per-doc 0.05 \\
        --out-dir ../../scratch/llm-bench/
"""

from __future__ import annotations

import argparse
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

from tier4_cleaner import SchemaIndex, clean  # noqa: E402
from subsection_slicer import slice_all, LocatedSlice  # noqa: E402
from tier4_llm_fallback import (  # noqa: E402
    build_cached_head,
    build_uncached_tail,
    validate_response,
    hash_markdown,
    STRATEGY_NAME,
    STRATEGY_VERSION,
    PROMPT_VERSION,
    PRODUCER_NAME,
    PRODUCER_VERSION,
)


def _load_env(env_path: Path) -> dict[str, str]:
    """Minimal .env reader matching worker.py's load_env semantics."""
    env: dict[str, str] = {}
    if not env_path.exists():
        return env
    for line in env_path.read_text().splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
            value = value[1:-1]
        env[key.strip()] = value.strip()
    return env


def _fetch_artifact(client, school_id: str, year: str | None) -> dict[str, Any] | None:
    """Return {doc, artifact} or None."""
    q = client.table("cds_documents").select(
        "id,school_id,cds_year,detected_year,source_sha256"
    ).eq("school_id", school_id)
    if year:
        q = q.eq("cds_year", year)
    docs = q.execute().data or []
    if not docs:
        return None
    doc = docs[0]

    arts = (
        client.table("cds_artifacts")
        .select("id,notes,created_at,producer,producer_version")
        .eq("document_id", doc["id"])
        .eq("producer", "tier4_docling")
        .eq("kind", "canonical")
        .order("created_at", desc=True)
        .limit(1)
        .execute()
    ).data or []
    if not arts:
        return None

    return {"doc": doc, "artifact": arts[0]}


def _already_extracted(notes: dict[str, Any]) -> dict[str, Any]:
    return (notes or {}).get("values") or {}


def _run_one_subsection(
    *,
    school_id: str,
    cds_year: str,
    subsection_code: str,
    slice_result: LocatedSlice,
    full_markdown: str,
    already: dict[str, Any],
    schema: SchemaIndex,
    schema_version: str,
    model: str,
    dry_run: bool,
) -> dict[str, Any]:
    """Run one subsection end-to-end: prompt → LLM → validate. No DB writes."""
    out: dict[str, Any] = {
        "subsection": subsection_code,
        "slicer_strategy": slice_result.strategy,
        "slice_line_range": [slice_result.start_line, slice_result.end_line],
        "slice_chars": len(slice_result.text),
        "fields_attempted": 0,
        "fields_accepted": 0,
        "fields_rejected": 0,
        "rejected_reasons": {},
        "cost_usd": 0.0,
        "input_tokens": 0,
        "cache_write_tokens": 0,
        "cache_read_tokens": 0,
        "output_tokens": 0,
        "status": "ok",
        "error": None,
    }

    if not slice_result.is_found():
        out["status"] = "unresolved"
        return out

    cached_head = build_cached_head(
        subsection_code=subsection_code,
        schema=schema,
        schema_version=schema_version,
    )
    uncached_tail = build_uncached_tail(
        school_id=school_id,
        cds_year=cds_year,
        subsection_code=subsection_code,
        section_markdown=slice_result.text,
        already_extracted=already,
    )

    if dry_run:
        out["status"] = "dry_run"
        out["dry_run_chars"] = {
            "head": sum(len(b) for b in cached_head),
            "tail": len(uncached_tail),
        }
        return out

    from llm_client import call_structured
    from tier4_llm_fallback import SYSTEM_PROMPT

    try:
        t0 = time.time()
        resp = call_structured(
            system=SYSTEM_PROMPT,
            cached_head_blocks=cached_head,
            uncached_tail=uncached_tail,
            model=model,
        )
        elapsed = time.time() - t0
    except Exception as e:
        out["status"] = "call_failed"
        out["error"] = f"{type(e).__name__}: {e}"
        return out

    out["elapsed_s"] = round(elapsed, 2)
    out["input_tokens"] = resp.input_tokens
    out["cache_write_tokens"] = resp.cache_write_tokens
    out["cache_read_tokens"] = resp.cache_read_tokens
    out["output_tokens"] = resp.output_tokens
    out["cost_usd"] = round(resp.estimated_cost_usd, 6)

    vr = validate_response(
        response=resp.parsed,
        schema=schema,
        subsection_code=subsection_code,
        section_markdown=slice_result.text,
        full_markdown=full_markdown,
        already_extracted=already,
    )

    out["fields_attempted"] = len(resp.parsed.get("values") or {})
    out["fields_accepted"] = len(vr.accepted)
    out["fields_rejected"] = len(vr.rejected)
    reasons: dict[str, int] = {}
    for r in vr.rejected:
        reasons[r.reason] = reasons.get(r.reason, 0) + 1
    out["rejected_reasons"] = reasons
    out["document_mismatch"] = vr.document_mismatch
    out["accepted_values"] = vr.accepted
    return out


def _run_one_doc(
    *,
    client,
    school_id: str,
    year: str | None,
    subsections: list[str],
    schema: SchemaIndex,
    schema_version: str,
    model: str,
    max_cost_per_doc: float,
    dry_run: bool,
) -> dict[str, Any]:
    """Run the benchmark on a single document. Returns a per-doc report."""
    doc_report: dict[str, Any] = {
        "school_id": school_id,
        "requested_year": year,
        "status": "pending",
        "subsections": [],
    }

    found = _fetch_artifact(client, school_id, year)
    if not found:
        doc_report["status"] = "artifact_not_found"
        return doc_report

    doc, art = found["doc"], found["artifact"]
    notes = art.get("notes") or {}
    markdown = notes.get("markdown") or ""
    already = _already_extracted(notes)

    doc_report["document_id"] = doc["id"]
    doc_report["cds_year"] = doc["cds_year"]
    doc_report["detected_year"] = doc.get("detected_year")
    doc_report["artifact_id"] = art["id"]
    doc_report["markdown_sha256"] = hash_markdown(markdown)
    doc_report["source_sha256"] = doc.get("source_sha256")
    doc_year = doc.get("detected_year") or doc.get("cds_year")
    doc_report["schema_version_used"] = schema_version
    doc_report["schema_year_proxy_for"] = doc_year if schema_version != doc_year else None
    doc_report["already_extracted_count"] = len(already)

    slices = slice_all(markdown, subsections)

    cumulative_cost = 0.0
    per_sub_results: list[dict[str, Any]] = []
    for code in subsections:
        if cumulative_cost >= max_cost_per_doc:
            per_sub_results.append({
                "subsection": code,
                "status": "budget_exhausted",
                "cost_usd": 0.0,
            })
            continue

        sr = _run_one_subsection(
            school_id=school_id,
            cds_year=doc.get("cds_year") or "",
            subsection_code=code,
            slice_result=slices[code],
            full_markdown=markdown,
            already=already,
            schema=schema,
            schema_version=schema_version,
            model=model,
            dry_run=dry_run,
        )
        cumulative_cost += float(sr.get("cost_usd") or 0.0)
        per_sub_results.append(sr)

    doc_report["subsections"] = per_sub_results
    doc_report["status"] = "complete"
    doc_report["total_cost_usd"] = round(cumulative_cost, 6)
    doc_report["total_fields_accepted"] = sum(
        sr.get("fields_accepted", 0) for sr in per_sub_results
    )
    doc_report["total_fields_rejected"] = sum(
        sr.get("fields_rejected", 0) for sr in per_sub_results
    )
    return doc_report


def _aggregate(per_doc_reports: list[dict[str, Any]]) -> dict[str, Any]:
    from collections import Counter

    strategy_counter: Counter[str] = Counter()
    total_cost = 0.0
    total_accepted = 0
    total_rejected = 0
    docs_complete = 0

    for r in per_doc_reports:
        if r.get("status") != "complete":
            continue
        docs_complete += 1
        total_cost += float(r.get("total_cost_usd") or 0.0)
        total_accepted += int(r.get("total_fields_accepted") or 0)
        total_rejected += int(r.get("total_fields_rejected") or 0)
        for sr in r.get("subsections") or []:
            strategy_counter[sr.get("slicer_strategy", "unknown")] += 1

    median_cost = 0.0
    if docs_complete:
        costs = sorted(
            float(r.get("total_cost_usd") or 0.0)
            for r in per_doc_reports
            if r.get("status") == "complete"
        )
        median_cost = costs[len(costs) // 2]

    return {
        "docs_complete": docs_complete,
        "docs_total": len(per_doc_reports),
        "total_cost_usd": round(total_cost, 6),
        "median_cost_per_doc_usd": round(median_cost, 6),
        "total_fields_accepted": total_accepted,
        "total_fields_rejected": total_rejected,
        "slicer_strategy_counts": dict(strategy_counter),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--env", default=str(_REPO_ROOT / ".env"))
    ap.add_argument("--school", required=True,
                    help="Comma-separated school_id values (e.g. 'harvard,yale,dartmouth')")
    ap.add_argument("--year", default=None, help="cds_year (optional)")
    ap.add_argument("--subsections", required=True,
                    help="Comma-separated subsection codes (e.g. 'H5,C13,D14')")
    ap.add_argument("--schema-version", default="2025-26",
                    help="Schema version to use (PRD 006: 2025-26 as near-year proxy for benchmark)")
    ap.add_argument("--schema-path", default=None,
                    help="Override schema JSON path (default: schemas/cds_schema_2025_26.json)")
    ap.add_argument("--model", default=os.environ.get("TIER4_FALLBACK_MODEL", "claude-haiku-4-5"))
    ap.add_argument("--max-cost-per-doc", type=float, default=0.05,
                    help="Stop attempting subsections for a doc once it costs this much USD")
    ap.add_argument("--out-dir", type=Path,
                    default=_REPO_ROOT / "scratch" / "llm-bench",
                    help="Directory for per-doc + aggregate JSON reports")
    ap.add_argument("--dry-run", action="store_true",
                    help="Build prompts but do not call the LLM (prints token-char counts)")
    args = ap.parse_args()

    schools = [s.strip() for s in args.school.split(",") if s.strip()]
    subsections = [s.strip() for s in args.subsections.split(",") if s.strip()]

    env = _load_env(Path(args.env))
    # Merge into os.environ so child modules (llm_client) see ANTHROPIC_API_KEY.
    for k, v in env.items():
        os.environ.setdefault(k, v)

    schema_path = Path(args.schema_path) if args.schema_path else None
    schema = SchemaIndex(schema_path=schema_path)

    from supabase import create_client
    client = create_client(
        os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_ROLE_KEY"]
    )

    args.out_dir.mkdir(parents=True, exist_ok=True)
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_dir = args.out_dir / f"run-{run_id}"
    run_dir.mkdir(exist_ok=True)

    print(f"Run dir: {run_dir}")
    print(f"Model: {args.model}")
    print(f"Schools: {schools}")
    print(f"Subsections: {subsections}")
    print(f"Schema version: {args.schema_version}")
    print()

    per_doc: list[dict[str, Any]] = []
    for school in schools:
        print(f"--- {school} ---")
        report = _run_one_doc(
            client=client,
            school_id=school,
            year=args.year,
            subsections=subsections,
            schema=schema,
            schema_version=args.schema_version,
            model=args.model,
            max_cost_per_doc=args.max_cost_per_doc,
            dry_run=args.dry_run,
        )
        (run_dir / f"{school}.json").write_text(json.dumps(report, indent=2))
        per_doc.append(report)

        _print_doc_summary(report)
        print()

    aggregate = _aggregate(per_doc)
    manifest = {
        "run_id": run_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "cli_args": vars(args) | {"out_dir": str(args.out_dir)},
        "strategy": STRATEGY_NAME,
        "strategy_version": STRATEGY_VERSION,
        "prompt_version": PROMPT_VERSION,
        "producer": PRODUCER_NAME,
        "producer_version": PRODUCER_VERSION,
        "aggregate": aggregate,
        "schools": schools,
        "subsections": subsections,
    }
    (run_dir / "_manifest.json").write_text(json.dumps(manifest, indent=2))

    print("=== AGGREGATE ===")
    print(json.dumps(aggregate, indent=2))
    return 0


def _print_doc_summary(report: dict[str, Any]) -> None:
    if report.get("status") != "complete":
        print(f"  status: {report.get('status')}")
        return
    print(f"  doc_id: {report.get('document_id')}  year: {report.get('cds_year')}")
    print(f"  total cost: ${report.get('total_cost_usd'):.4f}  "
          f"accepted: {report.get('total_fields_accepted')}  "
          f"rejected: {report.get('total_fields_rejected')}")
    for sr in report.get("subsections") or []:
        sub = sr.get("subsection")
        status = sr.get("status", "ok")
        strat = sr.get("slicer_strategy", "-")
        acc = sr.get("fields_accepted", 0)
        rej = sr.get("fields_rejected", 0)
        cost = sr.get("cost_usd", 0.0)
        print(f"    {sub:5s}  {status:16s}  slicer={strat:12s}  acc={acc:3d}  rej={rej:3d}  ${cost:.4f}")


if __name__ == "__main__":
    sys.exit(main())
