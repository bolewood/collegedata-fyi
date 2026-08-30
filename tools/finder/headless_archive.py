"""Scheduled Playwright archive worker for WAF/JS-gated CDS landings.

Edge `archive-process` uses Deno fetch. Hosts that reject non-browser GET
(NYU Akamai 405, JHU/Fordham Cloudflare, Williams 403) never yield bytes
there. This worker:

  1. Targets schools in `waf_blocked_urls.yaml` plus `archive_queue` rows
     whose last outcome is `bot_challenge`.
  2. Opens each HTML landing in Chromium, collects CDS document anchors
     (new years the YAML does not list yet), and unions them with the
     YAML URL fallback.
  3. Downloads with the browser network stack and uploads through
     `headless_download.upload_and_record` (SHA-idempotent).

Deno `force_urls` is the wrong ingest path for these hosts — it 405s the
same way archive-process does.

Usage:
  python tools/finder/headless_archive.py --only nyu
  python tools/finder/headless_archive.py --dry-run --max-schools 5

Residential (spoke-ops) split — fetch has no Supabase credentials:
  python tools/finder/headless_archive.py --phase plan --plan-json plan.json --only nyu
  python tools/finder/headless_archive.py --phase fetch --plan-json plan.json \\
      --artifact-dir ops-artifact --only nyu --no-queue
  python tools/finder/headless_archive.py --phase commit --artifact-dir ops-artifact
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

import yaml

_TOOLS_ROOT = Path(__file__).resolve().parents[1]
_REPO_ROOT = _TOOLS_ROOT.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))

try:
    from tools.finder.waf_school_ids import (
        WAF_SCHOOL_ID_ALIASES,
        canonical_waf_school_id,
    )
except ImportError:  # python tools/finder/headless_archive.py
    from waf_school_ids import (  # type: ignore
        WAF_SCHOOL_ID_ALIASES,
        canonical_waf_school_id,
    )

try:
    from tools.finder.playwright_collect import (
        DOCUMENT_EXT_RE,
        STARTING_URLS,
        AnchorResult,
        collect_for_school,
        normalize_year,
    )
except ImportError:
    from playwright_collect import (  # type: ignore
        DOCUMENT_EXT_RE,
        STARTING_URLS,
        AnchorResult,
        collect_for_school,
        normalize_year,
    )

DRIVE_HOST_RE = re.compile(
    r"(drive\.google\.com|docs\.google\.com|box\.com|dropbox\.com|"
    r"onedrive\.live\.com|sharepoint\.com)",
    re.I,
)
YEAR_RE = re.compile(r"(20\d{2})-(\d{2})")
WAF_CAPTCHA_MARKERS = (
    "human verification",
    "awswaf.com",
    "amzn-captcha",
    "let's confirm you are human",
    "x-amzn-waf-action",
    "captcha.awswaf.com",
)


def is_waf_captcha_bytes(body: bytes | None, content_type: str = "") -> bool:
    """True when the response is an AWS WAF / Cloudflare visual captcha page.

    Silent JS challenges that set a cookie and reload are not this — those
    we wait out. Visual puzzles (Choose all the hats) cannot be a scheduled
    ingest step.
    """
    if not body:
        return False
    head = body[:6000].decode("utf-8", errors="ignore").lower()
    ct = (content_type or "").lower()
    if "text/html" in ct or head.lstrip().startswith("<!doctype") or "<html" in head[:200]:
        return any(marker in head for marker in WAF_CAPTCHA_MARKERS)
    return any(marker in head for marker in WAF_CAPTCHA_MARKERS)


def wait_for_waf_pass(page, timeout_ms: int = 12_000) -> bool:
    """Wait for a silent bot-challenge page to navigate away.

    Returns True if the title is no longer a verification interstitial.
    Visual captchas stay on 'Human Verification' and return False.
    """
    try:
        page.wait_for_function(
            """() => {
              const t = (document.title || '').toLowerCase();
              return !t.includes('human verification')
                && !t.includes('just a moment')
                && !t.includes('attention required');
            }""",
            timeout=timeout_ms,
        )
        return True
    except Exception:
        return False


def strip_challenge_query(url: str) -> str:
    """Drop one-shot WAF `challenge=` tokens that expire and 403 later."""
    if not url:
        return url
    parsed = urlparse(url)
    if not parsed.query:
        return url
    pairs = [
        (k, v)
        for k, v in parse_qsl(parsed.query, keep_blank_values=True)
        if k.lower() != "challenge"
    ]
    return urlunparse(parsed._replace(query=urlencode(pairs)))


def canonicalize_url(url: str) -> str:
    stripped = strip_challenge_query((url or "").strip())
    parsed = urlparse(stripped)
    return urlunparse(parsed._replace(fragment=""))


def item_url(item: Any) -> str:
    if isinstance(item, dict):
        return canonicalize_url(item.get("url") or "")
    return canonicalize_url(str(item or ""))


def merge_waf_school_entries(raw: dict) -> dict[str, dict]:
    """Collapse alias YAML keys onto canonical school_id; union URLs."""
    out: dict[str, dict] = {}
    for raw_sid, entry in (raw or {}).items():
        sid = canonical_waf_school_id(raw_sid)
        block = entry or {}
        landing = block.get("landing_url")
        name = block.get("school_name")
        urls = list(block.get("urls") or [])
        prev = out.get(sid)
        if prev is None:
            out[sid] = {
                "school_name": name or sid,
                "landing_url": landing,
                "urls": urls,
            }
            continue
        if landing and not prev.get("landing_url"):
            prev["landing_url"] = landing
        if name and prev.get("school_name") in (None, sid):
            prev["school_name"] = name
        seen = {item_url(u) for u in prev["urls"]}
        for url_item in urls:
            key = item_url(url_item)
            if key and key not in seen:
                prev["urls"].append(url_item)
                seen.add(key)
    return out


def load_seed_urls(schools_yaml: Path) -> dict[str, str]:
    doc = yaml.safe_load(schools_yaml.read_text(encoding="utf-8")) or {}
    out: dict[str, str] = {}
    for row in doc.get("schools") or []:
        sid = row.get("id")
        url = row.get("discovery_seed_url") or row.get("cds_url_hint")
        if sid and url:
            out[sid] = url
    return out


def starting_url_for(school_id: str, starting_urls: dict[str, str]) -> str | None:
    if school_id in starting_urls:
        return starting_urls[school_id]
    for alias, canon in WAF_SCHOOL_ID_ALIASES.items():
        if canon == school_id and alias in starting_urls:
            return starting_urls[alias]
    return None


def resolve_landing(
    entry: dict,
    school_id: str,
    seed_by_id: dict[str, str],
    starting_urls: dict[str, str],
) -> str | None:
    """Prefer an HTML listing; fall back to a direct-doc hint for walk-up."""
    candidates = [
        (entry or {}).get("landing_url"),
        seed_by_id.get(school_id),
        starting_url_for(school_id, starting_urls),
    ]
    html: list[str] = []
    docs: list[str] = []
    for raw in candidates:
        if not raw:
            continue
        url = strip_challenge_query(raw)
        if DOCUMENT_EXT_RE.search(url) or DRIVE_HOST_RE.search(url):
            docs.append(url)
        else:
            html.append(url)
    if html:
        return html[0]
    if docs:
        return docs[0]
    return None


def should_crawl_landing(landing: str | None) -> bool:
    if not landing:
        return False
    if DRIVE_HOST_RE.search(landing):
        return False
    return True


@dataclass(frozen=True)
class ArchiveCandidate:
    url: str
    year: str | None
    source: str  # yaml | crawl


def yaml_candidates(entry: dict) -> list[ArchiveCandidate]:
    out: list[ArchiveCandidate] = []
    seen: set[str] = set()
    for item in (entry or {}).get("urls") or []:
        url = item_url(item)
        if not url or url in seen:
            continue
        seen.add(url)
        year = None
        if isinstance(item, dict):
            year = item.get("year") or normalize_year(url)
        else:
            year = normalize_year(url)
        out.append(ArchiveCandidate(url=url, year=year, source="yaml"))
    return out


def crawl_candidates(anchors: list[AnchorResult]) -> list[ArchiveCandidate]:
    out: list[ArchiveCandidate] = []
    seen: set[str] = set()
    for anchor in anchors:
        url = canonicalize_url(anchor.url)
        if not url or url in seen:
            continue
        if not (anchor.is_document or DRIVE_HOST_RE.search(url)):
            continue
        seen.add(url)
        year = anchor.year or normalize_year(url + " " + (anchor.text or ""))
        out.append(ArchiveCandidate(url=url, year=year, source="crawl"))
    return out


def merge_candidates(*groups: list[ArchiveCandidate]) -> list[ArchiveCandidate]:
    """Dedupe by URL. YAML year wins when both sources saw the same file."""
    by_url: dict[str, ArchiveCandidate] = {}
    for group in groups:
        for cand in group:
            key = canonicalize_url(cand.url)
            if not key:
                continue
            prev = by_url.get(key)
            if prev is None:
                by_url[key] = cand
                continue
            if prev.year is None and cand.year:
                by_url[key] = ArchiveCandidate(
                    url=prev.url, year=cand.year, source=prev.source,
                )
            elif cand.source == "yaml" and cand.year and prev.source != "yaml":
                by_url[key] = ArchiveCandidate(
                    url=prev.url, year=cand.year, source="yaml",
                )
    return list(by_url.values())


def year_sort_key(year: str | None) -> tuple[int, int]:
    if not year:
        return (0, 0)
    match = YEAR_RE.fullmatch(year.strip())
    if not match:
        return (0, 0)
    return (int(match.group(1)), int(match.group(2)))


def year_at_least(year: str | None, min_year: str | None) -> bool:
    if not min_year:
        return True
    if not year:
        return True
    return year_sort_key(year) >= year_sort_key(min_year)


def select_candidates(
    candidates: list[ArchiveCandidate],
    known_years: set[str],
    *,
    skip_known: bool,
    max_new: int,
    min_year: str | None,
) -> tuple[list[ArchiveCandidate], int]:
    """Newest first. Skip years we already archive unless skip_known is false."""
    skipped = 0
    eligible: list[ArchiveCandidate] = []
    for cand in candidates:
        if not year_at_least(cand.year, min_year):
            continue
        if skip_known and cand.year and cand.year in known_years:
            skipped += 1
            continue
        eligible.append(cand)
    eligible.sort(key=lambda c: year_sort_key(c.year), reverse=True)
    if max_new > 0:
        eligible = eligible[:max_new]
    return eligible, skipped


@dataclass
class SchoolTarget:
    school_id: str
    school_name: str
    landing_url: str | None
    entry: dict


def build_targets(
    waf_entries: dict[str, dict],
    extra_school_ids: list[str],
    seed_by_id: dict[str, str],
    starting_urls: dict[str, str],
    only: str | None,
    max_schools: int,
) -> list[SchoolTarget]:
    merged = dict(waf_entries)
    for raw in extra_school_ids:
        sid = canonical_waf_school_id(raw)
        merged.setdefault(sid, {"school_name": sid, "landing_url": None, "urls": []})
    if only:
        want = canonical_waf_school_id(only)
        merged = {sid: entry for sid, entry in merged.items() if sid == want}
        if only in waf_entries and want not in merged:
            merged[want] = waf_entries[only]
        if not merged and want:
            merged[want] = {"school_name": want, "landing_url": None, "urls": []}
    targets: list[SchoolTarget] = []
    for sid, entry in merged.items():
        landing = resolve_landing(entry, sid, seed_by_id, starting_urls)
        name = entry.get("school_name") or sid
        if not landing and not (entry.get("urls") or []):
            continue
        targets.append(SchoolTarget(
            school_id=sid,
            school_name=name,
            landing_url=landing,
            entry=entry,
        ))
    if max_schools > 0:
        targets = targets[:max_schools]
    return targets


def supabase_creds(env_path: Path) -> tuple[str, str]:
    values: dict[str, str] = {}
    if env_path.exists():
        for raw in env_path.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            values[key.strip()] = value.strip().strip('"').strip("'")
    url = os.environ.get("SUPABASE_URL") or values.get("SUPABASE_URL") or ""
    key = (
        os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
        or values.get("SUPABASE_SERVICE_ROLE_KEY")
        or ""
    )
    return url, key


def fetch_bot_challenge_ids(sb, limit: int) -> list[str]:
    if limit <= 0:
        return []
    try:
        result = (
            sb.table("archive_queue")
            .select("school_id")
            .eq("last_outcome", "bot_challenge")
            .limit(limit)
            .execute()
        )
    except Exception as exc:  # noqa: BLE001 — queue is optional enrichment
        print(f"warn: archive_queue bot_challenge query failed: {exc}", file=sys.stderr)
        return []
    ids: list[str] = []
    seen: set[str] = set()
    for row in result.data or []:
        sid = canonical_waf_school_id(row.get("school_id") or "")
        if sid and sid not in seen:
            seen.add(sid)
            ids.append(sid)
    return ids


def fetch_known_years(sb, school_ids: list[str]) -> dict[str, set[str]]:
    known: dict[str, set[str]] = {sid: set() for sid in school_ids}
    if not school_ids:
        return known
    try:
        result = (
            sb.table("cds_documents")
            .select("school_id,cds_year")
            .in_("school_id", school_ids)
            .execute()
        )
    except Exception as exc:  # noqa: BLE001
        print(f"warn: cds_documents year query failed: {exc}", file=sys.stderr)
        return known
    for row in result.data or []:
        sid = row.get("school_id")
        year = row.get("cds_year")
        if sid in known and year:
            known[sid].add(year)
    return known


@dataclass
class RunSummary:
    schools_attempted: int = 0
    inserted: int = 0
    unchanged: int = 0
    failed: int = 0
    fetched: int = 0
    crawled: int = 0
    discovered: int = 0
    skipped_known: int = 0
    dry_run: bool = False
    phase: str = "all"
    schools: list[dict] = field(default_factory=list)
    files: list[dict] = field(default_factory=list)

    def as_heartbeat(self) -> dict[str, Any]:
        return {
            "schools_attempted": self.schools_attempted,
            "inserted": self.inserted,
            "unchanged": self.unchanged,
            "failed": self.failed,
            "fetched": self.fetched,
            "crawled": self.crawled,
            "discovered": self.discovered,
            "skipped_known": self.skipped_known,
            "dry_run": self.dry_run,
            "phase": self.phase,
        }

    def as_json(self) -> dict[str, Any]:
        payload = self.as_heartbeat()
        payload["schools"] = self.schools
        payload["files"] = self.files
        payload["finished_at"] = datetime.now(timezone.utc).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        )
        return payload


PHASES = ("all", "plan", "fetch", "commit")

CollectFn = Callable[..., Any]
DownloadFn = Callable[..., tuple]
UploadFn = Callable[..., dict]
DetectExtFn = Callable[[bytes, str, str], str | None]


def assert_fetch_has_no_service_role() -> None:
    """Fail closed if a fetch job was given production write credentials."""
    if os.environ.get("SUPABASE_SERVICE_ROLE_KEY"):
        raise SystemExit(
            "fetch phase must not receive SUPABASE_SERVICE_ROLE_KEY "
            "(residential runner is secretless)"
        )


def known_years_from_plan(plan: dict[str, Any]) -> dict[str, set[str]]:
    raw = plan.get("known_years") or {}
    return {
        str(school_id): {str(year) for year in (years or [])}
        for school_id, years in raw.items()
    }


def load_plan_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_plan_json(
    path: Path, *, known: dict[str, set[str]], queue_school_ids: list[str]
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "known_years": {sid: sorted(years) for sid, years in known.items()},
        "queue_school_ids": list(queue_school_ids),
    }
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def make_fetch_store(artifact_dir: Path, files_acc: list[dict[str, Any]]) -> UploadFn:
    """Write bytes to the artifact dir instead of uploading to Supabase."""

    def store(
        school_id: str,
        year: str,
        body: bytes,
        ext: str,
        content_type: str,
        source_url: str,
        school_name: str,
    ) -> dict[str, Any]:
        sha = hashlib.sha256(body).hexdigest()
        rel = Path("files") / school_id / year / f"{sha}.{ext}"
        dest = artifact_dir / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(body)
        rec = {
            "school_id": school_id,
            "school_name": school_name,
            "year": year,
            "source_url": source_url,
            "ext": ext,
            "content_type": content_type,
            "sha256": sha,
            "relpath": rel.as_posix(),
            "byte_count": len(body),
        }
        files_acc.append(rec)
        return {"action": "fetched", "sha256": sha, "relpath": rec["relpath"]}

    return store


def require_supabase(env_path: Path):
    url, key = supabase_creds(env_path)
    if not url or not key:
        raise SystemExit("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY are required")
    from supabase import create_client

    return create_client(url, key)


def _load_download_helpers():
    """Lazy import so unit tests do not pull extraction_worker/worker.py."""
    try:
        from tools.finder.headless_download import (
            UA,
            detect_ext,
            download_via_page,
            upload_and_record,
            normalize_year as download_normalize_year,
        )
    except ImportError:
        from headless_download import (  # type: ignore
            UA,
            detect_ext,
            download_via_page,
            upload_and_record,
            normalize_year as download_normalize_year,
        )
    return UA, detect_ext, download_via_page, upload_and_record, download_normalize_year


def archive_school(
    *,
    target: SchoolTarget,
    known_years: set[str],
    skip_known: bool,
    max_new: int,
    min_year: str | None,
    dry_run: bool,
    page,
    browser_ctx,
    collect_fn: CollectFn,
    download_fn: DownloadFn,
    upload_fn: UploadFn | None,
    detect_ext_fn: DetectExtFn | None = None,
    year_from_url: Callable[[str], str | None] | None = None,
) -> dict[str, Any]:
    yaml_cands = yaml_candidates(target.entry)
    crawled: list[ArchiveCandidate] = []
    crawl_status = "skipped"
    if should_crawl_landing(target.landing_url) and page is not None:
        try:
            wait_for_waf_pass(page, timeout_ms=8_000)
            result = collect_fn(page, target.school_id, target.landing_url)
            crawled = crawl_candidates(result.anchors)
            crawl_status = result.status
            try:
                html = page.content().encode("utf-8", errors="ignore")
            except Exception:
                html = b""
            if crawl_status in {"no_anchors", "nav_error"} and is_waf_captcha_bytes(html):
                crawl_status = "waf_captcha"
        except Exception as exc:  # noqa: BLE001 — YAML fallback still runs
            crawl_status = "nav_error"
            print(
                f"  warn: crawl {target.school_id} failed: {type(exc).__name__}: {exc}"[:200],
                file=sys.stderr,
            )
    yaml_urls = {c.url for c in yaml_cands}
    discovered = [c for c in crawled if c.url not in yaml_urls]
    merged = merge_candidates(yaml_cands, crawled)
    selected, skipped = select_candidates(
        merged,
        known_years,
        skip_known=skip_known,
        max_new=max_new,
        min_year=min_year,
    )
    actions: list[dict[str, Any]] = []
    inserted = unchanged = failed = fetched = 0
    for cand in selected:
        if dry_run:
            actions.append({
                "url": cand.url, "year": cand.year, "source": cand.source,
                "action": "dry_run",
            })
            continue
        try:
            body, content_type, status, final_url = download_fn(
                browser_ctx, cand.url, landing_url=target.landing_url,
            )
        except Exception as exc:  # noqa: BLE001
            failed += 1
            actions.append({
                "url": cand.url, "year": cand.year, "source": cand.source,
                "action": "failed", "error": f"download {type(exc).__name__}: {exc}"[:180],
            })
            continue
        if body is None:
            failed += 1
            actions.append({
                "url": cand.url, "year": cand.year, "source": cand.source,
                "action": "failed", "error": f"no body status={status}",
            })
            continue
        ext = (detect_ext_fn or _load_download_helpers()[1])(
            body, content_type or "", final_url or cand.url,
        )
        if not ext:
            failed += 1
            error = (
                "waf_captcha"
                if is_waf_captcha_bytes(body, content_type or "")
                else f"unknown ext ct={content_type} size={len(body)}"
            )
            actions.append({
                "url": cand.url, "year": cand.year, "source": cand.source,
                "action": "failed",
                "error": error,
            })
            continue
        year_fn = year_from_url or normalize_year
        year = (
            cand.year
            or year_fn(cand.url)
            or year_fn(final_url or "")
            or "unknown"
        )
        try:
            result = upload_fn(
                target.school_id, year, body, ext, content_type or "",
                final_url or cand.url, target.school_name,
            )
        except Exception as exc:  # noqa: BLE001
            failed += 1
            actions.append({
                "url": cand.url, "year": year, "source": cand.source,
                "action": "failed", "error": f"upload {type(exc).__name__}: {exc}"[:180],
            })
            continue
        action = result.get("action") or "inserted"
        if action == "inserted":
            inserted += 1
        elif action == "unchanged_verified":
            unchanged += 1
        elif action == "fetched":
            fetched += 1
        actions.append({
            "url": cand.url, "year": year, "source": cand.source, "action": action,
            "relpath": result.get("relpath"),
            "sha256": result.get("sha256"),
        })
        time.sleep(0.5)
    return {
        "school_id": target.school_id,
        "landing_url": target.landing_url,
        "crawl_status": crawl_status,
        "crawled_anchors": len(crawled),
        "discovered": len(discovered),
        "selected": len(selected),
        "skipped_known": skipped,
        "inserted": inserted,
        "unchanged": unchanged,
        "failed": failed,
        "fetched": fetched,
        "actions": actions,
    }


def commit_fetched_files(
    artifact_dir: Path,
    upload_fn: UploadFn,
) -> RunSummary:
    manifest_path = artifact_dir / "manifest.json"
    if not manifest_path.exists():
        raise SystemExit(f"no fetch manifest at {manifest_path}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    summary = RunSummary(phase="commit")
    summary.schools = list(manifest.get("schools") or [])
    summary.schools_attempted = int(manifest.get("schools_attempted") or len(summary.schools))
    summary.crawled = int(manifest.get("crawled") or 0)
    summary.discovered = int(manifest.get("discovered") or 0)
    summary.skipped_known = int(manifest.get("skipped_known") or 0)
    summary.failed = int(manifest.get("failed") or 0)

    for rec in manifest.get("files") or []:
        rel = rec.get("relpath") or ""
        path = artifact_dir / rel
        if not path.is_file():
            summary.failed += 1
            print(f"  missing artifact file {rel}", file=sys.stderr)
            continue
        body = path.read_bytes()
        sha = hashlib.sha256(body).hexdigest()
        expected = rec.get("sha256") or ""
        if expected and sha != expected:
            raise SystemExit(f"sha256 mismatch for {rel}")
        try:
            result = upload_fn(
                rec["school_id"],
                rec["year"],
                body,
                rec["ext"],
                rec.get("content_type") or "",
                rec.get("source_url") or "",
                rec.get("school_name") or rec["school_id"],
            )
        except Exception as exc:  # noqa: BLE001
            summary.failed += 1
            print(
                f"  upload {rec.get('school_id')} {rec.get('year')} "
                f"failed: {type(exc).__name__}: {exc}"[:200],
                file=sys.stderr,
            )
            continue
        action = result.get("action") or "inserted"
        if action == "inserted":
            summary.inserted += 1
        elif action == "unchanged_verified":
            summary.unchanged += 1
        print(
            f"  {action} {rec.get('school_id')} {rec.get('year')} {rel}",
            file=sys.stderr,
        )
    return summary


def run(
    *,
    waf_path: Path,
    schools_yaml: Path,
    env_path: Path,
    only: str | None,
    dry_run: bool,
    skip_known: bool,
    include_queue: bool,
    max_schools: int,
    max_new: int,
    min_year: str | None,
    json_out: Path | None,
    phase: str = "all",
    artifact_dir: Path | None = None,
    plan_json: Path | None = None,
    collect_fn: CollectFn | None = None,
    download_fn: DownloadFn | None = None,
    upload_fn: UploadFn | None = None,
    browser_factory: Callable | None = None,
) -> RunSummary:
    if phase not in PHASES:
        raise SystemExit(f"phase must be one of {', '.join(PHASES)}")
    if phase == "fetch":
        assert_fetch_has_no_service_role()

    if phase == "commit":
        if artifact_dir is None:
            raise SystemExit("commit phase requires --artifact-dir")
        if upload_fn is None:
            sb = require_supabase(env_path)
            _ua, _detect, _dl, upload_and_record, _year = _load_download_helpers()

            def default_upload(
                school_id, year, body, ext, content_type, source_url, school_name,
            ):
                return upload_and_record(
                    sb, school_id, year, body, ext, content_type, source_url,
                    school_name,
                )

            upload_fn = default_upload
        summary = commit_fetched_files(artifact_dir, upload_fn)
        if json_out:
            json_out.parent.mkdir(parents=True, exist_ok=True)
            json_out.write_text(json.dumps(summary.as_json(), indent=2) + "\n")
        print("\n== Summary ==", file=sys.stderr)
        print(json.dumps(summary.as_heartbeat(), indent=2), file=sys.stderr)
        return summary

    waf_doc = yaml.safe_load(waf_path.read_text(encoding="utf-8")) or {}
    waf_entries = merge_waf_school_entries(waf_doc.get("schools") or {})
    seed_by_id = load_seed_urls(schools_yaml) if schools_yaml.exists() else {}

    sb = None
    extra: list[str] = []
    known: dict[str, set[str]] = {}
    plan_path = plan_json

    if phase in {"all", "plan"}:
        sb = require_supabase(env_path)
        if include_queue:
            extra = fetch_bot_challenge_ids(sb, limit=40)
            if extra:
                print(
                    f"queue bot_challenge schools: {', '.join(extra[:20])}",
                    file=sys.stderr,
                )
    elif phase == "fetch" and plan_path and plan_path.exists():
        plan = load_plan_json(plan_path)
        extra = list(plan.get("queue_school_ids") or [])
        known = known_years_from_plan(plan)

    targets = build_targets(
        waf_entries, extra, seed_by_id, STARTING_URLS, only, max_schools,
    )
    if only and not targets:
        raise SystemExit(f"no target for {only}")

    if phase in {"all", "plan"} and sb is not None:
        known = fetch_known_years(sb, [t.school_id for t in targets])

    if phase == "plan":
        if plan_path is None:
            raise SystemExit("plan phase requires --plan-json")
        write_plan_json(plan_path, known=known, queue_school_ids=extra)
        summary = RunSummary(phase="plan", dry_run=dry_run)
        summary.schools_attempted = len(targets)
        summary.skipped_known = sum(len(years) for years in known.values())
        if json_out:
            json_out.parent.mkdir(parents=True, exist_ok=True)
            payload = summary.as_json()
            payload["plan_json"] = str(plan_path)
            json_out.write_text(json.dumps(payload, indent=2) + "\n")
        print("\n== Summary ==", file=sys.stderr)
        print(json.dumps(summary.as_heartbeat(), indent=2), file=sys.stderr)
        return summary

    summary = RunSummary(dry_run=dry_run, phase=phase)
    files_acc: list[dict[str, Any]] = []

    collect = collect_fn or collect_for_school
    need_helpers = (
        download_fn is None or upload_fn is None or browser_factory is None
    )
    ua, detect_ext, download_via_page, upload_and_record, _year = (
        _load_download_helpers() if need_helpers else (None, None, None, None, None)
    )
    download = download_fn or download_via_page

    if upload_fn is None and phase == "fetch":
        if artifact_dir is None:
            raise SystemExit("fetch phase requires --artifact-dir")
        artifact_dir.mkdir(parents=True, exist_ok=True)
        upload_fn = make_fetch_store(artifact_dir, files_acc)
    elif upload_fn is None:
        if sb is None:
            sb = require_supabase(env_path)
            _ua, detect_ext, download_via_page, upload_and_record, _year = (
                _load_download_helpers()
            )
            download = download_fn or download_via_page

        def default_upload(
            school_id, year, body, ext, content_type, source_url, school_name,
        ):
            return upload_and_record(
                sb, school_id, year, body, ext, content_type, source_url,
                school_name,
            )

        upload_fn = default_upload

    upload = upload_fn

    def with_browser(callback):
        if browser_factory:
            return browser_factory(callback)
        try:
            from playwright.sync_api import sync_playwright
        except ModuleNotFoundError as exc:
            raise SystemExit(
                "playwright not installed. "
                "pip install -r tools/finder/requirements-headless.txt "
                "&& python -m playwright install chromium"
            ) from exc
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            ctx = browser.new_context(
                user_agent=ua,
                accept_downloads=True,
                viewport={"width": 1280, "height": 900},
            )
            page = ctx.new_page()
            try:
                return callback(page, ctx)
            finally:
                browser.close()

    def work(page, ctx):
        for i, target in enumerate(targets):
            print(
                f"\n=== {target.school_id} ({i + 1}/{len(targets)}) "
                f"landing={target.landing_url} ===",
                file=sys.stderr,
            )
            row = archive_school(
                target=target,
                known_years=known.get(target.school_id, set()),
                skip_known=skip_known,
                max_new=max_new,
                min_year=min_year,
                dry_run=dry_run,
                page=page,
                browser_ctx=ctx,
                collect_fn=collect,
                download_fn=download,
                upload_fn=None if dry_run else upload,
                detect_ext_fn=detect_ext,
            )
            summary.schools_attempted += 1
            summary.inserted += row["inserted"]
            summary.unchanged += row["unchanged"]
            summary.failed += row["failed"]
            summary.fetched += row.get("fetched", 0)
            summary.crawled += row["crawled_anchors"]
            summary.discovered += row["discovered"]
            summary.skipped_known += row["skipped_known"]
            summary.schools.append(row)
            print(
                f"  crawl={row['crawl_status']} anchors={row['crawled_anchors']} "
                f"discovered={row['discovered']} selected={row['selected']} "
                f"inserted={row['inserted']} unchanged={row['unchanged']} "
                f"fetched={row.get('fetched', 0)} "
                f"failed={row['failed']} skipped_known={row['skipped_known']}",
                file=sys.stderr,
            )
            time.sleep(1.5)
        return summary

    if targets:
        with_browser(work)

    summary.files = files_acc
    if phase == "fetch" and artifact_dir is not None:
        artifact_dir.mkdir(parents=True, exist_ok=True)
        manifest = summary.as_json()
        (artifact_dir / "manifest.json").write_text(
            json.dumps(manifest, indent=2) + "\n", encoding="utf-8",
        )

    if json_out:
        json_out.parent.mkdir(parents=True, exist_ok=True)
        json_out.write_text(json.dumps(summary.as_json(), indent=2) + "\n")
    print("\n== Summary ==", file=sys.stderr)
    print(json.dumps(summary.as_heartbeat(), indent=2), file=sys.stderr)
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.strip().split("\n\n")[0])
    parser.add_argument(
        "--input",
        type=Path,
        default=_REPO_ROOT / "tools/finder/waf_blocked_urls.yaml",
    )
    parser.add_argument(
        "--schools-yaml",
        type=Path,
        default=_REPO_ROOT / "tools/finder/schools.yaml",
    )
    parser.add_argument("--env", type=Path, default=Path(".env"))
    parser.add_argument("--only", help="Canonical or alias school_id")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--include-existing",
        action="store_true",
        help="Re-fetch years already in cds_documents (default: skip them)",
    )
    parser.add_argument(
        "--no-queue",
        action="store_true",
        help="Do not add archive_queue bot_challenge schools",
    )
    parser.add_argument("--max-schools", type=int, default=20)
    parser.add_argument("--max-new-per-school", type=int, default=2)
    parser.add_argument("--min-year", default="2024-25")
    parser.add_argument("--json-out", type=Path)
    parser.add_argument(
        "--phase",
        choices=PHASES,
        default="all",
        help="all = hosted crawl+upload; plan/fetch/commit = secretless Mac split",
    )
    parser.add_argument(
        "--artifact-dir",
        type=Path,
        help="Fetch writes files here; commit reads them (no secrets on fetch)",
    )
    parser.add_argument(
        "--plan-json",
        type=Path,
        help="Plan phase writes known years; fetch phase reads them",
    )
    args = parser.parse_args(argv)

    if not args.input.exists() and args.phase != "commit":
        print(f"error: {args.input} does not exist", file=sys.stderr)
        return 2

    try:
        summary = run(
            waf_path=args.input,
            schools_yaml=args.schools_yaml,
            env_path=args.env,
            only=args.only,
            dry_run=args.dry_run,
            skip_known=not args.include_existing,
            include_queue=not args.no_queue,
            max_schools=args.max_schools,
            max_new=args.max_new_per_school,
            min_year=args.min_year or None,
            json_out=args.json_out,
            phase=args.phase,
            artifact_dir=args.artifact_dir,
            plan_json=args.plan_json,
        )
    except SystemExit as exc:
        if isinstance(exc.code, str):
            print(f"error: {exc.code}", file=sys.stderr)
            return 2
        raise
    # Infrastructure ran. Per-URL misses stay in the summary so a single
    # 403 does not red the daily job (and hide the schools that did ingest).
    return 0 if summary.schools_attempted >= 0 else 1


if __name__ == "__main__":
    sys.exit(main())
