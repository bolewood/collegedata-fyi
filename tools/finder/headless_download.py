"""
Headless-browser download + archive for WAF-blocked CDS URLs.

When a school's IR server rejects non-browser User-Agents (Notre Dame 404,
JHU/Fordham Cloudflare 403, NYU 405 on GET, Williams 403 on specific subpaths),
the standard Deno downloader in archive-process can't fetch the bytes.
Playwright's full browser navigation (with real TLS fingerprint + real
cookies) passes those WAFs.

This tool:
  1. For each (school_id, url, year) input, navigates a headless Chromium
     to the URL. Optionally pre-loads a landing page first to set cookies
     and a Referer header.
  2. Captures the response body.
  3. Computes sha256, detects extension from content-type + magic bytes.
  4. Uploads directly to Supabase Storage at
       sources/<school_id>/<year>/<sha256>.<ext>
  5. Inserts a cds_documents row (extraction_status=extraction_pending)
     matching the archive-process schema.

Idempotent: if sha256 already exists in cds_artifacts, skip.

Input:
  tools/finder/waf_blocked_urls.yaml (see bottom for shape)

Usage:
  tools/extraction_worker/.venv/bin/python tools/finder/headless_download.py
  ... --dry-run        # Don't upload; just print what would happen
  ... --only notre-dame  # Run for one school
"""

from __future__ import annotations

import argparse
import hashlib
import re
import sys
import time
import yaml
import zipfile
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from typing import Optional

_TOOLS_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_TOOLS_ROOT / "extraction_worker"))
from worker import load_env

from supabase import create_client

try:
    from playwright.sync_api import sync_playwright
except ModuleNotFoundError:  # pragma: no cover - exercised by operator envs
    sync_playwright = None


UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")

PDF_MAGIC = b"%PDF"
XLSX_MAGIC = b"PK\x03\x04"   # ZIP container; xlsx/docx both use this
DOCX_MAGIC = XLSX_MAGIC


def detect_ext(body: bytes, content_type: str, url: str) -> Optional[str]:
    """Same semantics as archive.ts extForResponse: bytes are authoritative."""
    byte_ext = sniff_ext_from_bytes(body)
    ct = (content_type or "").lower()
    url_ext = ext_from_url(url)

    # Cloudflare/WAF challenges often come back as HTML at a .pdf URL. Never
    # let the URL suffix turn those bytes into a source PDF.
    if byte_ext == "html":
        return None
    if byte_ext:
        return byte_ext

    if "application/pdf" in ct:
        return "pdf"
    if "officedocument.spreadsheetml.sheet" in ct:
        return "xlsx"
    if "officedocument.wordprocessingml.document" in ct:
        return "docx"
    return url_ext


def ext_from_url(url: str) -> Optional[str]:
    u = url.lower().split("?")[0].split("#")[0]
    if u.endswith(".pdf"):
        return "pdf"
    if u.endswith(".xlsx"):
        return "xlsx"
    if u.endswith(".docx"):
        return "docx"
    if u.endswith(".html") or u.endswith(".htm"):
        return "html"
    return None


def sniff_ext_from_bytes(body: bytes) -> Optional[str]:
    if body.startswith(PDF_MAGIC):
        return "pdf"
    if body.startswith(XLSX_MAGIC):
        try:
            names = zipfile.ZipFile(BytesIO(body)).namelist()
        except (zipfile.BadZipFile, ValueError, EOFError):
            return None
        has_word = any(n.startswith("word/") for n in names)
        has_xl = any(n.startswith("xl/") for n in names)
        if has_word and not has_xl:
            return "docx"
        if has_xl and not has_word:
            return "xlsx"
        return None
    head = body[:512].decode("utf-8", errors="ignore").lower().lstrip()
    if (
        head.startswith("<!doctype html")
        or head.startswith("<html")
        or head.startswith("<head")
        or (head.startswith("<?xml") and "<html" in head)
    ):
        return "html"
    return None


def normalize_year(s: str) -> Optional[str]:
    m = re.search(r"(20\d\d)[-_](20\d\d|\d\d)", s)
    if not m:
        return None
    y1, y2 = m.group(1), m.group(2)
    if len(y2) == 2:
        y2 = y1[:2] + y2
    return f"{y1[:4]}-{y2[-2:]}"


def download_via_page(
    browser_ctx,
    url: str,
    landing_url: Optional[str] = None,
    timeout_ms: int = 30_000,
) -> tuple[Optional[bytes], Optional[str], Optional[int], Optional[str]]:
    """Fetch `url` bytes. Strategy:
      1. Visit `landing_url` first to warm cookies + set Referer.
      2. Try `context.request.get(url)` — uses the browser's network stack
         (TLS fingerprint, HTTP/2, cookies) and returns bytes directly.
      3. Fall back to `page.expect_download()` — for servers that force
         Content-Disposition: attachment (Drive /uc, some IR sites).
      4. Last resort: response listener during `page.goto`."""
    page = browser_ctx.new_page()
    try:
        # Step 1: warm cookies via landing page.
        if landing_url:
            try:
                page.goto(landing_url, wait_until="domcontentloaded",
                          timeout=timeout_ms)
                page.wait_for_timeout(800)
            except Exception:
                pass

        # Step 2: try context API request (fastest, most reliable when WAF
        # accepts the browser's cookie jar + TLS fingerprint).
        try:
            headers = {}
            if landing_url:
                headers["Referer"] = landing_url
            resp = browser_ctx.request.get(
                url, headers=headers, timeout=timeout_ms,
                max_redirects=10,
            )
            body = resp.body()
            ct = resp.headers.get("content-type", "") or ""
            # Reject HTML (Drive virus-warning page, WAF challenge page).
            if (body and len(body) > 1024
                    and "text/html" not in ct.lower()
                    and not body.lstrip().startswith(b"<")):
                return (body, ct, resp.status, resp.url)
        except Exception:
            pass

        # Step 3: try expect_download for attachment-disposition URLs.
        try:
            with page.expect_download(timeout=timeout_ms) as dl_info:
                try:
                    page.goto(url, timeout=timeout_ms)
                except Exception:
                    pass
            download = dl_info.value
            dl_path = download.path()
            if dl_path:
                body = Path(dl_path).read_bytes()
                if body and len(body) > 0:
                    return (body, "application/octet-stream", 200,
                            download.url)
        except Exception:
            pass

        # Step 4: response listener during navigation (inline viewer path).
        captured: dict = {}

        def on_response(response):
            ct = response.headers.get("content-type", "").lower()
            if ("pdf" in ct or "officedocument" in ct
                    or response.url.split("?")[0].lower()
                    .endswith((".pdf", ".xlsx", ".docx"))):
                try:
                    b = response.body()
                    if b and len(b) > 1024:
                        captured["body"] = b
                        captured["ct"] = response.headers.get(
                            "content-type", "")
                        captured["status"] = response.status
                        captured["final_url"] = response.url
                except Exception:
                    pass

        page.on("response", on_response)
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
        except Exception:
            pass
        page.wait_for_timeout(1500)
        return (
            captured.get("body"),
            captured.get("ct"),
            captured.get("status"),
            captured.get("final_url", url),
        )
    finally:
        page.close()


def sha256_hex(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def upload_and_record(sb, school_id: str, year: str, body: bytes,
                       ext: str, content_type: str, source_url: str,
                       school_name: Optional[str] = None) -> dict:
    """Same logic as archive.ts archiveOneCandidate: SHA dedup, Storage
    upload, cds_documents row, cds_artifacts source row."""
    sha = sha256_hex(body)

    # Idempotency: if any cds_artifacts row already has this sha256 for
    # kind='source', skip (matches archive.ts behavior).
    r = sb.table("cds_artifacts").select("id,document_id")\
        .eq("sha256", sha).eq("kind", "source").limit(1).execute()
    if r.data:
        return {"action": "unchanged_verified", "sha256": sha,
                "document_id": r.data[0]["document_id"],
                "reason": "sha256 already in cds_artifacts"}

    storage_path = f"{school_id}/{year}/{sha}.{ext}"
    bucket = "sources"
    mime = {"pdf": "application/pdf",
            "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document"}[ext]

    # Upload bytes to Storage.
    upload_res = sb.storage.from_(bucket).upload(
        storage_path, body,
        file_options={"content-type": mime, "x-upsert": "true"},
    )
    # supabase-py returns different shapes on success; errors raise.

    # Upsert cds_documents row. Composite key (school_id, sub_institutional, cds_year);
    # sub_institutional is NULL for our top-100 schools.
    doc_row = {
        "school_id": school_id,
        "school_name": school_name or school_id,
        "cds_year": year,
        "source_url": source_url,
        "source_format": "pdf_flat" if ext == "pdf" else
                         ("xlsx" if ext == "xlsx" else "docx"),
        "extraction_status": "extraction_pending",
        "participation_status": "published",
        "last_verified_at": datetime.now(timezone.utc).strftime(
            "%Y-%m-%dT%H:%M:%SZ"),
    }
    doc_res = sb.table("cds_documents").upsert(
        doc_row, on_conflict="school_id,sub_institutional,cds_year"
    ).execute()
    if not doc_res.data:
        raise RuntimeError(f"cds_documents upsert returned no data: {doc_res}")
    document_id = doc_res.data[0]["id"]

    # Insert cds_artifacts row for the source file.
    art_row = {
        "document_id": document_id,
        "kind": "source",
        "producer": "headless_download",
        "producer_version": "0.1.0",
        "storage_path": storage_path,
        "sha256": sha,
        "notes": {"fetched_via": "playwright",
                  "content_type": content_type,
                  "byte_count": len(body)},
    }
    sb.table("cds_artifacts").insert(art_row).execute()

    return {"action": "inserted", "sha256": sha, "document_id": document_id,
            "storage_path": storage_path, "size": len(body)}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.strip().split("\n\n")[0])
    ap.add_argument("--input", type=Path,
                    default=Path("tools/finder/waf_blocked_urls.yaml"))
    ap.add_argument("--env", default=".env")
    ap.add_argument("--only", help="Process one school only")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    if not args.input.exists():
        print(f"error: {args.input} does not exist", file=sys.stderr)
        return 2
    doc = yaml.safe_load(args.input.read_text())
    schools = doc.get("schools", {})
    if args.only:
        schools = {args.only: schools.get(args.only, {})}
        if not schools[args.only]:
            print(f"no entry for {args.only}", file=sys.stderr)
            return 2

    env = load_env(Path(args.env))
    sb = create_client(env["SUPABASE_URL"], env["SUPABASE_SERVICE_ROLE_KEY"])
    if sync_playwright is None:
        print(
            "ERROR: playwright not installed. Run: pip install playwright && playwright install chromium",
            file=sys.stderr,
        )
        return 2

    total_attempted = 0
    total_inserted = 0
    total_unchanged = 0
    total_failed = 0

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(user_agent=UA, accept_downloads=True)
        for sid, school in schools.items():
            landing = school.get("landing_url")
            school_name = school.get("school_name") or sid
            items = school.get("urls", [])
            print(f"\n=== {sid} ({len(items)} urls, landing={landing}) ===",
                  file=sys.stderr)
            for item in items:
                url = item["url"] if isinstance(item, dict) else item
                year_hint = item.get("year") if isinstance(item, dict) else None
                total_attempted += 1

                body, ct, status, final_url = download_via_page(
                    ctx, url, landing_url=landing)
                if body is None:
                    print(f"  ✗  {url[:85]}  status={status}  no body captured",
                          file=sys.stderr)
                    total_failed += 1
                    continue
                ext = detect_ext(body, ct or "", final_url or url)
                if not ext:
                    print(f"  ✗  {url[:85]}  unknown ext (ct={ct}, "
                          f"size={len(body)}, magic={body[:4].hex()})",
                          file=sys.stderr)
                    total_failed += 1
                    continue
                year = year_hint or normalize_year(url) or \
                       normalize_year(final_url or "") or "unknown"

                if args.dry_run:
                    print(f"  DRY  {url[:80]}  {ext}  year={year}  "
                          f"size={len(body)}", file=sys.stderr)
                    continue

                try:
                    result = upload_and_record(
                        sb, sid, year, body, ext, ct or "",
                        final_url or url, school_name)
                    action = result["action"]
                    if action == "inserted":
                        total_inserted += 1
                    elif action == "unchanged_verified":
                        total_unchanged += 1
                    print(f"  ✓  {url[:80]}  {action}  year={year}  "
                          f"ext={ext}  {len(body)}B", file=sys.stderr)
                except Exception as e:
                    total_failed += 1
                    print(f"  ✗  {url[:80]}  UPLOAD FAILED {type(e).__name__}: "
                          f"{str(e)[:100]}", file=sys.stderr)
                time.sleep(0.5)
        browser.close()

    print(f"\n== Summary ==", file=sys.stderr)
    print(f"Attempted:  {total_attempted}", file=sys.stderr)
    print(f"Inserted:   {total_inserted}", file=sys.stderr)
    print(f"Unchanged:  {total_unchanged}", file=sys.stderr)
    print(f"Failed:     {total_failed}", file=sys.stderr)
    return 0 if total_failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
