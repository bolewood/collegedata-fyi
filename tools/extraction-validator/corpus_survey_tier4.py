"""
Read-only corpus survey: how well does the current Tier 4 cleaner perform
against already-extracted Docling markdown in the cds_artifacts table?

Pulls every cds_artifacts row with kind='canonical' and producer='tier4_docling',
re-runs the latest tier4_cleaner.clean() against the stored notes.markdown,
and reports:

  - Distribution of fields_populated per doc (histogram + percentiles)
  - Delta between stored stats.schema_fields_populated and current cleaner
    (shows how much each phase improves things)
  - Per-question-number coverage (which fields extract reliably vs never)
  - Per-section-family coverage (PRD 005): mean fields populated per section
    (A, B1, B2, B3, C1, …, J) vs expected total per section, so each phase
    can be validated against its targeted section.
  - The 10 lowest-coverage docs, for manual inspection

Safe to run while the extraction worker is writing new rows — this script
performs reads only and never mutates the DB.

Usage:
    # Live DB survey (requires SUPABASE_URL + SUPABASE_SERVICE_ROLE_KEY):
    tools/extraction_worker/.venv/bin/python \\
        tools/extraction-validator/corpus_survey_tier4.py --limit 200

    # Benchmark slice from local markdown files (no DB required):
    tools/extraction_worker/.venv/bin/python \\
        tools/extraction-validator/corpus_survey_tier4.py \\
        --markdown-glob 'tools/extraction-validator/runs/*/baseline/output.md'
"""

from __future__ import annotations

import argparse
import glob
import json
import re
import statistics
import sys
from collections import Counter
from pathlib import Path

# Import the cleaner and load_env helper.
_REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO_ROOT / "tools" / "extraction_worker"))
from tier4_cleaner import clean  # noqa: E402


# --- Section family map for PRD 005 coverage reporting ---

# Maps a question number (e.g. "C.1102") to a coarse section family bucket
# (e.g. "C11"). The bucket naming follows CDS convention (B1, B2, C1, … J).
# Expected totals are from cds_schema_2025_26.json; they let the survey show
# "D/J populated" as "actual/expected" instead of bare counts.
# Sections whose fields cleanly divide into CDS-style sub-tables keyed by
# "letter + digit(s)" (e.g. B1/B2/B3, C1/C5/C11). For these we bucket by
# parsing the numeric prefix. Other sections (A, D, E, F, G, H, I, J) are
# treated as single buckets because their question numbers aren't organized
# by table-within-section.
_MULTI_TABLE_SECTIONS = {"B", "C"}


def _section_bucket(qn: str) -> str:
    """Map 'B.201' → 'B2', 'B.2201' → 'B22', 'C.1302' → 'C13', 'J.181' → 'J'.

    Letters not in _MULTI_TABLE_SECTIONS always collapse to the bare letter.
    Schema also contains alphabetic-suffixed fields (e.g. 'C.8E01', 'A.0A');
    those bucket into their top-level letter too.
    """
    m = re.match(r"^([A-Z])\.(\d+)$", qn)
    if not m:
        # Alphabetic suffix (e.g. C.8E01, A.0A): bucket by leading letter.
        letter_match = re.match(r"^([A-Z])\.", qn)
        return letter_match.group(1) if letter_match else "?"
    prefix, digits = m.group(1), m.group(2)
    if prefix not in _MULTI_TABLE_SECTIONS:
        return prefix
    if len(digits) <= 3:
        return f"{prefix}{digits[:1]}"
    return f"{prefix}{digits[:2]}"


def _load_section_totals(schema_path: Path) -> dict[str, int]:
    """Count expected fields per bucket from the schema JSON."""
    data = json.loads(schema_path.read_text())
    counts: Counter[str] = Counter()
    for f in data["fields"]:
        counts[_section_bucket(f["question_number"])] += 1
    return dict(counts)


# Local-markdown mode doesn't need Supabase; import lazily.
def _lazy_supabase():
    from worker import load_env  # noqa: WPS433
    from supabase import create_client  # noqa: WPS433
    return load_env, create_client


def fetch_tier4_artifacts(client, limit: int | None):
    """Page through cds_artifacts where producer=tier4_docling."""
    page_size = 500
    offset = 0
    out = []
    while True:
        q = (
            client.table("cds_artifacts")
            .select("id,document_id,created_at,notes")
            .eq("producer", "tier4_docling")
            .eq("kind", "canonical")
            .order("created_at", desc=False)
            .range(offset, offset + page_size - 1)
        )
        res = q.execute()
        rows = res.data or []
        if not rows:
            break
        out.extend(rows)
        if limit and len(out) >= limit:
            out = out[:limit]
            break
        if len(rows) < page_size:
            break
        offset += page_size
    return out


def fetch_fallback_values(
    client, document_ids: list[str]
) -> dict[str, dict[str, dict]]:
    """Return {document_id: {qn: value_dict}} from the latest tier4_llm_fallback
    artifact for each document.

    Returns empty dict for docs without a fallback artifact. Newest artifact
    wins on dedup (same producer/doc pair rarely has more than one row).
    """
    out: dict[str, dict[str, dict]] = {}
    for i in range(0, len(document_ids), 200):
        batch = document_ids[i : i + 200]
        res = (
            client.table("cds_artifacts")
            .select("document_id,created_at,notes")
            .eq("producer", "tier4_llm_fallback")
            .in_("document_id", batch)
            .order("created_at", desc=True)
            .execute()
        )
        for row in res.data or []:
            did = row["document_id"]
            if did in out:
                continue  # newest already seen
            vals = (row.get("notes") or {}).get("values") or {}
            out[did] = vals
    return out


def fetch_doc_names(client, document_ids: list[str]) -> dict[str, str]:
    """Batch-fetch school_id + cds_year for the document_ids we surveyed."""
    out: dict[str, str] = {}
    for i in range(0, len(document_ids), 200):
        batch = document_ids[i : i + 200]
        res = (
            client.table("cds_documents")
            .select("id,school_id,cds_year,detected_year")
            .in_("id", batch)
            .execute()
        )
        for row in res.data or []:
            year = row.get("detected_year") or row.get("cds_year") or "?"
            out[row["id"]] = f"{row['school_id']} / {year}"
    return out


def histogram(values: list[int], buckets: list[tuple[int, int | None]]) -> list[tuple[str, int, str]]:
    rows = []
    total = len(values)
    for lo, hi in buckets:
        if hi is None:
            count = sum(1 for v in values if v >= lo)
            label = f">= {lo}"
        else:
            count = sum(1 for v in values if lo <= v < hi)
            label = f"{lo}-{hi - 1}"
        bar = "█" * int(40 * count / total) if total else ""
        rows.append((label, count, bar))
    return rows


def _survey_local(paths: list[Path]) -> tuple[list[dict], Counter, dict]:
    """Run the cleaner against local markdown files (benchmark-slice mode).

    Returns (results, field_coverage, doc_names) in the same shape as the
    DB-mode path, so the reporting code below can consume either.
    """
    results = []
    field_coverage: Counter[str] = Counter()
    doc_names: dict[str, str] = {}
    for p in paths:
        md = p.read_text()
        values = clean(md)
        for qn in values:
            field_coverage[qn] += 1
        # Identity keys mirror DB rows so the reporting code is shared.
        doc_id = str(p)
        try:
            rel = p.resolve().relative_to(_REPO_ROOT)
            doc_names[doc_id] = str(rel)
        except ValueError:
            doc_names[doc_id] = doc_id
        results.append({
            "artifact_id": str(p),
            "document_id": doc_id,
            "created_at": "",
            "md_length": len(md),
            "stored_fields": 0,
            "current_fields": len(values),
            "delta": 0,
        })
    return results, field_coverage, doc_names


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.strip().split("\n\n")[0])
    ap.add_argument("--env", default=str(_REPO_ROOT / ".env"))
    ap.add_argument("--limit", type=int, default=None,
                    help="Cap artifacts surveyed (useful for quick runs)")
    ap.add_argument("--markdown-glob", default=None,
                    help="Survey local markdown files matching this glob "
                         "instead of hitting the DB. Example: "
                         "tools/extraction-validator/runs/*/baseline/output.md")
    ap.add_argument("--schema",
                    default=str(_REPO_ROOT / "schemas" / "cds_schema_2025_26.json"),
                    help="Schema JSON used to compute per-section totals")
    ap.add_argument("--json", action="store_true",
                    help="Emit full results as JSON")
    ap.add_argument("--include-fallback", action="store_true",
                    help="Also load tier4_llm_fallback artifacts and report "
                         "cleaner-only vs cleaner+fallback coverage delta per "
                         "section family and per question (PRD 006 Phase 1).")
    args = ap.parse_args()

    section_totals = _load_section_totals(Path(args.schema))

    # --- Data acquisition: local-markdown mode vs DB mode ---
    if args.markdown_glob:
        paths = sorted(Path(p) for p in glob.glob(args.markdown_glob))
        if not paths:
            print(f"error: no markdown files matched {args.markdown_glob!r}",
                  file=sys.stderr)
            return 2
        print(f"Surveying {len(paths)} local markdown files…\n")
        results, field_coverage, doc_names = _survey_local(paths)
        stored_counts = [0] * len(results)
        current_counts = [r["current_fields"] for r in results]
    else:
        load_env, create_client = _lazy_supabase()
        env = load_env(Path(args.env))
        url = env.get("SUPABASE_URL")
        key = env.get("SUPABASE_SERVICE_ROLE_KEY")
        if not url or not key:
            print("error: missing SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY",
                  file=sys.stderr)
            return 2
        client = create_client(url, key)

        print(f"Fetching tier4_docling canonical artifacts (limit={args.limit or 'all'})…")
        artifacts = fetch_tier4_artifacts(client, args.limit)
        print(f"  got {len(artifacts)} artifacts\n")

        if not artifacts:
            print("No tier4 artifacts in DB yet.")
            return 0

        # Re-run cleaner against each stored markdown.
        results = []
        field_coverage = Counter()
        stored_counts = []
        current_counts = []

        for a in artifacts:
            notes = a.get("notes") or {}
            md = notes.get("markdown") or ""
            stored_stats = notes.get("stats") or {}
            stored_n = stored_stats.get("schema_fields_populated", 0)
            if not md:
                continue
            current_values = clean(md)
            current_n = len(current_values)
            for qn in current_values:
                field_coverage[qn] += 1
            stored_counts.append(stored_n)
            current_counts.append(current_n)
            results.append({
                "artifact_id": a["id"],
                "document_id": a["document_id"],
                "created_at": a["created_at"],
                "md_length": len(md),
                "stored_fields": stored_n,
                "current_fields": current_n,
                "delta": current_n - stored_n,
            })

        # Pull document names for low-coverage inspection.
        doc_ids = [r["document_id"] for r in results]
        doc_names = fetch_doc_names(client, doc_ids)

        # Optional: pull tier4_llm_fallback artifacts and merge per Mode B.
        fallback_coverage: Counter[str] = Counter()
        fallback_by_doc: dict[str, dict[str, dict]] = {}
        if args.include_fallback:
            fallback_by_doc = fetch_fallback_values(client, doc_ids)
            # Apply fill_gaps merge per doc, then tally coverage from the
            # merged view (cleaner wins; fallback fills blanks).
            for a in artifacts:
                did = a["document_id"]
                cleaner_vals = clean((a.get("notes") or {}).get("markdown") or "")
                fb_vals = fallback_by_doc.get(did, {})
                merged_qns = set(cleaner_vals.keys())
                for qn in fb_vals:
                    merged_qns.add(qn)
                for qn in merged_qns:
                    fallback_coverage[qn] += 1
            # Annotate each result with fallback counts.
            for r in results:
                fb = fallback_by_doc.get(r["document_id"], {})
                # How many new qns did the fallback add (beyond what cleaner had)?
                cleaner_qns = set()
                for a in artifacts:
                    if a["document_id"] == r["document_id"]:
                        cleaner_qns = set(clean((a.get("notes") or {}).get("markdown") or "").keys())
                        break
                new_from_fb = len([qn for qn in fb if qn not in cleaner_qns])
                r["fallback_fields_added"] = new_from_fb
                r["merged_fields"] = r["current_fields"] + new_from_fb

    n = len(results)
    if n == 0:
        print("All artifacts had empty markdown.")
        return 0

    if args.json:
        payload = {
            "n_artifacts": n,
            "results": results,
            "field_coverage": dict(field_coverage),
            "doc_names": doc_names,
        }
        if args.include_fallback:
            payload["fallback_coverage"] = dict(fallback_coverage)
        print(json.dumps(payload, indent=2))
        return 0

    # ---------- Summary ----------
    print(f"Surveyed {n} Tier 4 artifacts\n")

    print("Distribution of fields_populated (current cleaner):")
    for label, count, bar in histogram(
        current_counts,
        buckets=[(0, 10), (10, 20), (20, 30), (30, 40), (40, 50), (50, None)],
    ):
        pct = 100 * count / n
        print(f"  {label:<8} {count:>4}  ({pct:>4.1f}%)  {bar}")
    print()

    cur = current_counts
    print(f"Percentiles (current): p10={_pct(cur,10)}  p50={_pct(cur,50)}  "
          f"p90={_pct(cur,90)}  mean={statistics.mean(cur):.1f}  max={max(cur)}  min={min(cur)}")

    stored_nonzero = [s for s in stored_counts if s > 0]
    if stored_nonzero:
        deltas = [r["delta"] for r in results]
        print(f"Delta vs stored (positive = current cleaner better): "
              f"mean={statistics.mean(deltas):.1f}  median={statistics.median(deltas):.0f}  "
              f"max=+{max(deltas)}  min={min(deltas)}")
    print()

    # ---------- Per-section-family coverage (PRD 005) ----------
    # For each bucket, sum the number of (doc × unique question) hits observed
    # and divide by (n docs × expected fields in bucket). This is the
    # population rate per section — how "filled-in" a typical doc is for
    # that section's schema slice. Each phase should move the bucket it
    # targets toward 100% while leaving unchanged buckets flat.
    section_hits: Counter[str] = Counter()
    for qn, count in field_coverage.items():
        section_hits[_section_bucket(qn)] += count
    # Optional: merged (cleaner + fallback) per-bucket tally.
    merged_section_hits: Counter[str] = Counter()
    if args.include_fallback and 'fallback_coverage' in dir():
        for qn, count in fallback_coverage.items():
            merged_section_hits[_section_bucket(qn)] += count

    print("Per-section-family coverage:")
    if args.include_fallback:
        print(f"  {'bucket':<8} {'cleaner%':>9}  {'merged%':>8}  {'delta':>6}  {'expected':>9}")
    else:
        print(f"  {'bucket':<8} {'fill%':>7}  {'fields_observed':>16}  {'expected':>9}")
    buckets_sorted = sorted(
        set(section_hits) | set(section_totals),
        key=lambda b: (b[0], b[1:].zfill(2)),
    )
    for bucket in buckets_sorted:
        expected = section_totals.get(bucket, 0)
        observed = section_hits.get(bucket, 0)
        denom = n * expected
        fill = (100 * observed / denom) if denom else 0.0
        if args.include_fallback:
            merged_obs = merged_section_hits.get(bucket, observed)
            merged_fill = (100 * merged_obs / denom) if denom else 0.0
            delta = merged_fill - fill
            bar = "█" * int(20 * merged_fill / 100)
            print(f"  {bucket:<8} {fill:>8.1f}%  {merged_fill:>7.1f}%  {delta:>+5.1f}%  {expected:>9}  {bar}")
        else:
            bar = "█" * int(20 * fill / 100)
            print(f"  {bucket:<8} {fill:>6.1f}%  {observed:>16}  {expected:>9}  {bar}")
    print()

    # ---------- Per-field coverage ----------
    print(f"Per-question-number coverage ({n} docs):")
    print(f"  {'QN':<8} {'pct':>6}  {'count':>6}")
    sorted_fields = sorted(field_coverage.items(), key=lambda kv: (-kv[1], kv[0]))
    for qn, count in sorted_fields[:60]:
        pct = 100 * count / n
        bar = "█" * int(20 * count / n)
        print(f"  {qn:<8} {pct:>5.1f}%  {count:>6}  {bar}")
    print()

    # ---------- Low-coverage docs ----------
    low = sorted(results, key=lambda r: r["current_fields"])[:15]
    print(f"15 lowest-coverage docs (for manual inspection):")
    print(f"  {'current':>7} {'stored':>6}  {'md_len':>7}  school / year")
    for r in low:
        name = doc_names.get(r["document_id"], r["document_id"])
        print(f"  {r['current_fields']:>7} {r['stored_fields']:>6}  {r['md_length']:>7}  {name}")

    return 0


def _pct(values: list[int], p: int) -> int:
    if not values:
        return 0
    sorted_v = sorted(values)
    k = (len(sorted_v) - 1) * p / 100
    f = int(k)
    c = min(f + 1, len(sorted_v) - 1)
    if f == c:
        return sorted_v[f]
    return int(sorted_v[f] + (sorted_v[c] - sorted_v[f]) * (k - f))


if __name__ == "__main__":
    sys.exit(main())
