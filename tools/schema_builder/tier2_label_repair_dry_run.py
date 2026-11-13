"""READ-ONLY dry run of the D5 label repair (PRD 038 follow-up). For each document id, run today's Tier 2 (with the checked-out, fixed schemas)
through the worker's own functions (source selection, year and schema resolution, run_tier2) and diff the values against the newest stored
tier2_acroform artifact: which documents change ONLY in the D5 labels, which also gain, lose or change other values, which route away from Tier 2.
Writes nothing to the database or storage; it only reads and downloads.

    python tools/schema_builder/tier2_label_repair_dry_run.py --ids-file ids.txt --out diff.json [--env .env]
(ids: comma- or newline-separated cds_documents.id values)"""
import json, os, sys
from pathlib import Path
import argparse
ap = argparse.ArgumentParser(); ap.add_argument("--ids-file", required=True); ap.add_argument("--out", required=True); ap.add_argument("--env", default=".env")
A = ap.parse_args()
DECODE = Path(__file__).resolve().parents[2]; OUT = Path(A.out); ENV = Path(A.env)
sys.path.insert(0, str(DECODE / "tools")); sys.path.insert(0, str(DECODE / "tools/extraction_worker"))
import worker
for k, v in worker.load_env(ENV).items(): os.environ.setdefault(k, v)
from supabase import create_client
client = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_ROLE_KEY"])
registry = worker.load_schema_registry()
ids = [x.strip() for x in open(A.ids_file).read().replace("\n", ",").split(",") if x.strip()]
TF = {"/TFER_RFS", "/TFER_ROS"}
results = []
for n, doc_id in enumerate(ids):
    r = {"document_id": doc_id}
    try:
        doc = client.table("cds_documents").select("id,school_id,cds_year,detected_year,source_format").eq("id", doc_id).execute().data[0]
        r.update(school=doc["school_id"], year=doc.get("detected_year") or doc.get("cds_year"), db_format=doc.get("source_format"))
        latest = worker.fetch_latest_source_artifact(client, doc_id)
        data = worker.download_source(client, latest["storage_path"])
        sel = worker.select_source_for_extraction(client, doc_id, latest, data)
        pdf = sel.source_bytes
        fmt, _ = worker.choose_source_format(doc.get("source_format"), pdf)
        r["format_now"] = fmt
        stored = client.table("cds_artifacts").select("id,created_at,producer_version,schema_version,notes->values,notes->source_sha256").eq("document_id", doc_id).eq("kind", "canonical").eq("producer", "tier2_acroform").order("created_at", desc=True).limit(1).execute().data[0]
        old = stored["values"] or {}
        r["stored_artifact"] = stored["id"]; r["stored_schema"] = stored["schema_version"]
        if fmt != "pdf_fillable":
            r["verdict"] = "routes_away_from_tier2"; results.append(r); continue
        detected = worker.detect_year_from_bytes(pdf)
        cy = worker.canonical_year_for_doc({**doc, "detected_year": detected or doc.get("detected_year")}, detected)
        res = worker.resolve_schema_for_year(cy, registry)
        r["schema_now"] = res.schema_version
        canonical = worker.run_tier2(pdf, res.schema)
        new = canonical["values"]
        r["fallback_to_tier4"] = bool(worker.should_fallback_tier2_to_tier4(canonical))
        d5_label, other = [], []
        for k in sorted(set(old) | set(new)):
            a, b = old.get(k), new.get(k)
            if a is None: other.append((k, "added", None, b.get("value") if isinstance(b, dict) else b)); continue
            if b is None: other.append((k, "lost", a.get("value") if isinstance(a, dict) else a, None)); continue
            av, bv = (a.get("value") if isinstance(a, dict) else a), (b.get("value") if isinstance(b, dict) else b)
            ad, bd = (a.get("value_decoded") if isinstance(a, dict) else None), (b.get("value_decoded") if isinstance(b, dict) else None)
            if av != bv: other.append((k, "value_changed", av, bv))
            elif ad != bd:
                (d5_label if av in TF else other).append((k, "decoded_changed", ad, bd))
        r.update(d5_label_changes=len(d5_label), other_changes=other[:40], other_count=len(other), old_n=len(old), new_n=len(new))
        r["verdict"] = "only_d5_labels" if not other and not r["fallback_to_tier4"] else ("falls_back_to_tier4" if r["fallback_to_tier4"] else "other_changes")
    except Exception as e:
        r["verdict"] = "error"; r["error"] = f"{type(e).__name__}: {str(e)[:150]}"
    results.append(r)
    print(n + 1, r["verdict"], r.get("school"), r.get("year"), r.get("d5_label_changes"), r.get("other_count"), flush=True)
json.dump(results, open(OUT, "w"), indent=1, default=str)
