"""
Read-only: pull a single Tier 4 doc's stored markdown from cds_artifacts
and dump a slice or the whole thing for manual inspection.

Useful for understanding why a specific doc has low cleaner coverage.

Usage:
    tools/extraction_worker/.venv/bin/python \\
        tools/extraction-validator/inspect_tier4_doc.py \\
        --school california-polytechnic-state-university-san-luis-obispo
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO_ROOT / "tools" / "extraction_worker"))
from tier4_cleaner import clean  # noqa: E402
from worker import load_env  # noqa: E402

from supabase import create_client  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.strip().split("\n\n")[0])
    ap.add_argument("--env", default=str(_REPO_ROOT / ".env"))
    ap.add_argument("--school", required=True, help="school_id to look up")
    ap.add_argument("--year", help="cds_year (optional)")
    ap.add_argument("--save", type=Path, help="write full markdown to this path")
    ap.add_argument("--slice", type=str, default="B1,B2,C1,C9",
                    help="comma-separated section prefixes to dump")
    args = ap.parse_args()

    env = load_env(Path(args.env))
    client = create_client(env["SUPABASE_URL"], env["SUPABASE_SERVICE_ROLE_KEY"])

    # Find the document.
    q = client.table("cds_documents").select("id,school_id,cds_year,detected_year").eq("school_id", args.school)
    if args.year:
        q = q.eq("cds_year", args.year)
    docs = q.execute().data or []
    if not docs:
        print(f"no document for school={args.school} year={args.year}")
        return 1
    print(f"Matching docs: {len(docs)}")
    for d in docs:
        print(f"  id={d['id']}  year={d['cds_year']}  detected={d.get('detected_year')}")
    doc = docs[0]

    # Pull the canonical tier4 artifact.
    arts = (
        client.table("cds_artifacts")
        .select("id,notes,created_at")
        .eq("document_id", doc["id"])
        .eq("producer", "tier4_docling")
        .eq("kind", "canonical")
        .order("created_at", desc=True)
        .limit(1)
        .execute()
    ).data or []
    if not arts:
        print("no tier4 artifact for that doc")
        return 1
    md = (arts[0].get("notes") or {}).get("markdown") or ""
    print(f"Markdown length: {len(md)} bytes, {md.count(chr(10))} lines\n")

    if args.save:
        args.save.write_text(md)
        print(f"Saved to {args.save}")

    values = clean(md)
    print(f"Cleaner extracted {len(values)} fields: {sorted(values.keys())}\n")

    # Dump requested section slices.
    import re
    sections = [s.strip() for s in args.slice.split(",")]
    lines = md.split("\n")
    for sec in sections:
        pattern = re.compile(rf"^##\s+{re.escape(sec)}[\s.:]", re.IGNORECASE)
        start = None
        for i, line in enumerate(lines):
            if pattern.search(line):
                start = i
                break
        if start is None:
            print(f"--- {sec}: not found ---\n")
            continue
        # read until next H2 heading or +80 lines
        end = len(lines)
        for j in range(start + 1, min(start + 80, len(lines))):
            if lines[j].startswith("## "):
                end = j
                break
        print(f"--- {sec} (lines {start}-{end}) ---")
        for line in lines[start:end]:
            print(line)
        print()

    return 0


if __name__ == "__main__":
    sys.exit(main())
