#!/usr/bin/env python3
"""Operator CLI for uploading a CDS file to the archive.

Wraps the archive-upload edge function. Use when a file is behind a
Cloudflare WAF, an auth wall, a JS dropdown, or any other obstacle
that prevents the resolver from fetching it — you download it in your
browser, hand it to this tool, and it lands in the archive tagged with
source_provenance='operator_manual' (or whatever you override).

Usage:
    python tools/upload/upload.py <file> <school_id> <cds_year> [options]

Examples:
    # Simplest — archive a PDF you just downloaded
    python tools/upload/upload.py ~/Downloads/williams_cds_2023-2024.pdf williams 2023-24

    # Record where you got it (shows up in source_url)
    python tools/upload/upload.py ./ucla_cds_2024-25.pdf ucla 2024-25 \\
        --source-url https://apb.ucla.edu/file/9f8e7d6c-abcd

    # Override provenance (e.g., you downloaded from a mirror)
    python tools/upload/upload.py ./mystery.pdf school-x 2022-23 \\
        --source-provenance mirror_college_transitions

Return codes:
    0  inserted | unchanged_verified | unchanged_repaired | refreshed
    1  any error (shape validation, HTTP failure, server rejection)

Idempotent: uploading the same file twice yields unchanged_verified.
Uploading a DIFFERENT file for an existing (school, year) yields
refreshed (new file replaces old as the canonical source; the old
artifact row stays in cds_artifacts for audit).
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path

import requests
from dotenv import load_dotenv

ALLOWED_PROVENANCE = {
    "school_direct",
    "mirror_college_transitions",
    "operator_manual",
}

YEAR_RE = re.compile(r"^(20\d{2})-(\d{2})$")


def validate_year(year: str) -> bool:
    m = YEAR_RE.match(year)
    if not m:
        return False
    yyyy, yy = int(m.group(1)), int(m.group(2))
    # Academic year: yy should be (yyyy + 1) % 100
    expected_yy = (yyyy + 1) % 100
    return yy == expected_yy


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Upload a CDS file to the archive (operator-only).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("file", help="Path to the PDF/XLSX/DOCX to upload")
    parser.add_argument("school_id", help="schools.yaml slug (e.g., 'yale', 'williams')")
    parser.add_argument("cds_year", help="Academic year 'YYYY-YY' (e.g., '2024-25')")
    parser.add_argument("--source-url",
                        help="URL you downloaded this from (recorded in cds_documents.source_url)")
    parser.add_argument("--source-provenance", default="operator_manual",
                        help=f"Provenance tag. One of {sorted(ALLOWED_PROVENANCE)}. Default: operator_manual")
    parser.add_argument("--school-name",
                        help="School display name (looked up from schools.yaml if omitted)")
    parser.add_argument("--env", default=".env", help="Path to .env")
    parser.add_argument("--timeout", type=int, default=120,
                        help="HTTP timeout in seconds (default: 120)")
    args = parser.parse_args()

    # Local validation before we burn an HTTP call
    file_path = Path(args.file)
    if not file_path.exists():
        print(f"ERROR: file not found: {file_path}", file=sys.stderr)
        return 1
    size = file_path.stat().st_size
    if size == 0:
        print(f"ERROR: empty file: {file_path}", file=sys.stderr)
        return 1
    if size > 50 * 1024 * 1024:
        print(f"ERROR: file exceeds 50 MB bucket limit ({size:,} bytes): {file_path}",
              file=sys.stderr)
        return 1

    if not validate_year(args.cds_year):
        print(f"ERROR: cds_year must be 'YYYY-YY' where YY = YYYY+1, got {args.cds_year!r}",
              file=sys.stderr)
        print("       Examples: 2024-25, 2023-24, 2022-23", file=sys.stderr)
        return 1

    if args.source_provenance not in ALLOWED_PROVENANCE:
        print(f"ERROR: --source-provenance must be one of {sorted(ALLOWED_PROVENANCE)}",
              file=sys.stderr)
        return 1

    # Peek at the first bytes to give a quick sanity check before upload
    with open(file_path, "rb") as f:
        head = f.read(8)
    if head[:4] == b"%PDF":
        fmt = "PDF"
    elif head[:4] == b"PK\x03\x04":
        # XLSX / DOCX magic is the same (ZIP); the edge function distinguishes
        fmt = "XLSX/DOCX (ZIP)"
    else:
        print(f"WARNING: file does not start with PDF or ZIP magic bytes "
              f"(first 8: {head.hex()}).", file=sys.stderr)
        print("         The edge function will magic-byte-check and reject if "
              "it's not PDF/XLSX/DOCX.", file=sys.stderr)
        fmt = "unknown"

    load_dotenv(args.env)
    base_url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    if not base_url or not key:
        print("ERROR: SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be in .env",
              file=sys.stderr)
        return 1

    print(f"Uploading {file_path.name} ({size:,} bytes, {fmt})")
    print(f"  school_id:         {args.school_id}")
    print(f"  cds_year:          {args.cds_year}")
    print(f"  source_provenance: {args.source_provenance}")
    if args.source_url:
        print(f"  source_url:        {args.source_url}")

    with open(file_path, "rb") as fp:
        files = {"file": (file_path.name, fp, "application/octet-stream")}
        data = {
            "school_id": args.school_id,
            "cds_year": args.cds_year,
            "source_provenance": args.source_provenance,
        }
        if args.source_url:
            data["source_url"] = args.source_url
        if args.school_name:
            data["school_name"] = args.school_name

        try:
            resp = requests.post(
                f"{base_url}/functions/v1/archive-upload",
                headers={"Authorization": f"Bearer {key}"},
                files=files,
                data=data,
                timeout=args.timeout,
            )
        except requests.Timeout:
            print(f"ERROR: timeout after {args.timeout}s", file=sys.stderr)
            return 1
        except Exception as e:
            print(f"ERROR: request failed: {e}", file=sys.stderr)
            return 1

    try:
        body = resp.json()
    except Exception:
        body = {"raw": resp.text[:500]}

    if resp.status_code != 200:
        print(f"\nERROR: HTTP {resp.status_code}", file=sys.stderr)
        import json
        print(json.dumps(body, indent=2), file=sys.stderr)
        return 1

    print(f"\n✓ {body.get('action', '?').upper()}")
    print(f"  document_id:    {body.get('document_id')}")
    print(f"  source_sha256:  {body.get('source_sha256')}")
    print(f"  storage_path:   {body.get('storage_path')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
