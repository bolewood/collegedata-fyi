#!/usr/bin/env python3
"""PRD 038 M3: download the sources the overlay will run on, and write the source-sha file the shadow report needs.

READ-ONLY: Supabase table SELECTs and storage downloads only. For each document id it takes the same source the overlay takes (the
newest source artifact, through the worker's PR #258 selection) and writes `<sha256>.pdf` into --out-dir plus one
comma-separated line of those shas into --shas-out (which `fetch_tier4.sh` and `shadow_report.py --cohort-shas` read).

    python tools/tier2_extractor/fetch_cohort_sources.py --env .env --document-ids-file scratch/prd038/m3/cohort_doc_ids.txt \\
        --out-dir scratch/prd038/pdfs --shas-out scratch/prd038/m3/cohort_shas.txt

PDFs are school documents: they stay under scratch/ (gitignored) and are never committed."""
import argparse
import hashlib
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "tools" / "extraction_worker"))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--env", default=".env")
    ap.add_argument("--document-ids-file", type=Path, required=True, help="comma-separated or one per line")
    ap.add_argument("--out-dir", type=Path, required=True)
    ap.add_argument("--shas-out", type=Path, required=True)
    args = ap.parse_args()

    import worker
    from supabase import create_client

    for key, value in worker.load_env(Path(args.env)).items():
        os.environ.setdefault(key, value)
    client = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_ROLE_KEY"])
    ids = [x.strip() for x in args.document_ids_file.read_text().replace("\n", ",").split(",") if x.strip()]
    args.out_dir.mkdir(parents=True, exist_ok=True)
    shas: list[str] = []
    failed = 0
    for document_id in ids:
        try:
            latest = worker.fetch_latest_source_artifact(client, document_id)
            data = worker.download_source(client, latest["storage_path"])
            selection = worker.select_source_for_extraction(client, document_id, latest, data)
            pdf = selection.source_bytes
            sha = hashlib.sha256(pdf).hexdigest()
            (args.out_dir / f"{sha}.pdf").write_bytes(pdf)
            shas.append(sha)
            print(f"{document_id} {sha[:12]} {len(pdf)} bytes", flush=True)
        except Exception as exc:  # report and continue: the shadow report fails hard on any missing cohort document
            failed += 1
            print(f"{document_id} FAILED {type(exc).__name__}: {str(exc)[:120]}", file=sys.stderr, flush=True)
    args.shas_out.parent.mkdir(parents=True, exist_ok=True)
    args.shas_out.write_text(",".join(shas) + "\n")
    print(f"{len(shas)} sources written to {args.out_dir}; {failed} failed; shas in {args.shas_out}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
