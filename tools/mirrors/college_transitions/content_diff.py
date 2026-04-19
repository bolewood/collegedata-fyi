#!/usr/bin/env python3
"""Content-level diff of two CDS PDFs (our archive vs CT).

Prints page count, file size, and a per-page text diff so we can see
whether the hash mismatch is structural (different content) or
cosmetic (same content, different PDF re-save / added cover page).

Usage:
    python tools/data_quality/ct_content_diff.py --school-id university-of-north-carolina-asheville --year 2021-22
"""

from __future__ import annotations

import argparse
import difflib
import hashlib
import os
import sys
from io import BytesIO
from pathlib import Path

import requests
from dotenv import load_dotenv
from pypdf import PdfReader
from supabase import create_client


def drive_download_url(share_url: str) -> str | None:
    import re
    m = re.search(r"/file/d/([a-zA-Z0-9_-]{10,})", share_url)
    if m:
        return f"https://drive.google.com/uc?export=download&id={m.group(1)}"
    # usercontent.google.com direct form — use as-is
    if "drive.usercontent.google.com/download" in share_url:
        return share_url
    return None


def download(url: str, timeout: int = 60) -> bytes:
    r = requests.get(url, allow_redirects=True, timeout=timeout)
    r.raise_for_status()
    return r.content


def pdf_summary(bytes_: bytes) -> dict:
    reader = PdfReader(BytesIO(bytes_))
    meta = reader.metadata or {}
    pages_text = []
    for p in reader.pages:
        try:
            pages_text.append(p.extract_text() or "")
        except Exception:
            pages_text.append("")
    # Try AcroForm detection
    try:
        fields = reader.get_fields() or {}
    except Exception:
        fields = {}
    return {
        "size_bytes": len(bytes_),
        "sha256": hashlib.sha256(bytes_).hexdigest(),
        "page_count": len(reader.pages),
        "title": (meta.get("/Title") or "").strip(),
        "producer": (meta.get("/Producer") or "").strip(),
        "creator": (meta.get("/Creator") or "").strip(),
        "creation_date": str(meta.get("/CreationDate") or ""),
        "mod_date": str(meta.get("/ModDate") or ""),
        "acroform_fields": len(fields),
        "pages_text": pages_text,
    }


def summarize_header(label: str, s: dict) -> None:
    print(f"--- {label} ---")
    print(f"  bytes:         {s['size_bytes']:,}")
    print(f"  sha256:        {s['sha256']}")
    print(f"  page_count:    {s['page_count']}")
    print(f"  title:         {s['title']!r}")
    print(f"  producer:      {s['producer']!r}")
    print(f"  creator:       {s['creator']!r}")
    print(f"  creation_date: {s['creation_date']}")
    print(f"  mod_date:      {s['mod_date']}")
    print(f"  acroform_flds: {s['acroform_fields']}")


def page_text_diff(our: list[str], ct: list[str]) -> None:
    """Side-by-side per-page diff. Aligns by index; if page counts differ, notes it."""
    max_pages = max(len(our), len(ct))
    print(f"\n=== Per-page text diff (max {max_pages} pages) ===\n")
    for i in range(max_pages):
        our_p = our[i] if i < len(our) else ""
        ct_p = ct[i] if i < len(ct) else ""
        our_snip = (our_p[:120] or "(empty)").replace("\n", " ")
        ct_snip = (ct_p[:120] or "(empty)").replace("\n", " ")
        if our_p == ct_p:
            marker = "identical"
        elif our_p.strip() == ct_p.strip():
            marker = "whitespace-only"
        else:
            # Compute text similarity
            ratio = difflib.SequenceMatcher(None, our_p, ct_p).ratio()
            marker = f"differ (similarity={ratio:.2f})"
        print(f"  page {i+1}: {marker}")
        if marker != "identical" and (our_p or ct_p):
            print(f"    ours: {our_snip!r}")
            print(f"    ct:   {ct_snip!r}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Content diff two CDS PDFs (ours vs CT)")
    parser.add_argument("--env", default=".env")
    parser.add_argument("--school-id", required=True)
    parser.add_argument("--year", required=True)
    args = parser.parse_args()

    load_dotenv(args.env)
    sb = create_client(
        os.environ["SUPABASE_URL"],
        os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ["SUPABASE_ANON_KEY"],
    )

    # Fetch our record
    doc = sb.table("cds_documents").select("id, source_url, source_sha256").eq(
        "school_id", args.school_id
    ).eq("cds_year", args.year).execute().data
    if not doc:
        print(f"no cds_documents row for {args.school_id} {args.year}")
        return 1
    our_source_url = doc[0]["source_url"]
    our_db_sha = doc[0]["source_sha256"]
    print(f"Our source URL: {our_source_url}")
    print(f"Our DB sha256:  {our_db_sha}")

    # Load CT entry for this pair
    import json
    with open(".playwright-mcp/ct-repository-full.json") as f:
        ct_wrapper = json.load(f)
    ct_data = ct_wrapper["data"] if "data" in ct_wrapper else ct_wrapper

    # Fuzzy match school id → CT name
    from difflib import SequenceMatcher
    our_name_low = args.school_id.replace("-", " ")
    best = None
    best_score = 0
    for row in ct_data:
        r = SequenceMatcher(None, row["school"].lower(), our_name_low).ratio()
        if r > best_score:
            best = row
            best_score = r
    if not best or args.year not in best["years"]:
        print(f"no CT entry for {args.school_id} {args.year} (best match: {best['school']!r} @ {best_score:.2f})")
        return 1
    ct_share_url = best["years"][args.year]
    ct_direct = drive_download_url(ct_share_url)
    print(f"CT share URL:  {ct_share_url}")
    print(f"CT direct URL: {ct_direct}\n")

    # Download both
    print("Downloading ours...")
    our_bytes = download(our_source_url)
    print("Downloading CT...")
    ct_bytes = download(ct_direct)

    # Summarize + diff
    our_sum = pdf_summary(our_bytes)
    ct_sum = pdf_summary(ct_bytes)

    print()
    summarize_header("OURS", our_sum)
    print()
    summarize_header("CT", ct_sum)

    page_text_diff(our_sum["pages_text"], ct_sum["pages_text"])

    # Final verdict
    print("\n=== Verdict ===")
    if our_sum["sha256"] == ct_sum["sha256"]:
        print("  Bit-for-bit identical.")
    elif our_sum["page_count"] != ct_sum["page_count"]:
        print(f"  Page counts differ: ours={our_sum['page_count']}, ct={ct_sum['page_count']}")
        print("  Likely structural difference (cover page added/removed, different version).")
    else:
        same_content = all(
            our_sum["pages_text"][i] == ct_sum["pages_text"][i]
            for i in range(our_sum["page_count"])
        )
        if same_content:
            print("  Same page count AND identical extracted text per page.")
            print("  Hash differs only due to PDF re-save (metadata, xref table, timestamp).")
            print("  Content is the same document. Data fields would extract identically.")
        else:
            whitespace_only = all(
                our_sum["pages_text"][i].strip() == ct_sum["pages_text"][i].strip()
                for i in range(our_sum["page_count"])
            )
            if whitespace_only:
                print("  Same page count; text differs only in whitespace.")
                print("  Almost certainly same content, different PDF renderer.")
            else:
                print("  Same page count but text differs.")
                print("  Either different CDS version for this year OR one source is mislabeled.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
