#!/usr/bin/env python3
"""Unattended directory drain with conservative high-signal repair.

This is still an operator workflow, not CI/cron. It runs a sequence of small
directory-enqueue batches, waits for each batch to drain, audits only that
batch's high-value `no_pdfs_found` rows, and force-archives official CDS
documents when discovery is unambiguous.
"""

from __future__ import annotations

import argparse
import html.parser
import json
import os
import re
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.finder import probe_urls
from tools.ops import directory_enqueue_batches as batches


DOC_EXTENSIONS = (".pdf", ".xlsx", ".docx")
BAD_DOC_KEYWORDS = (
    "definition",
    "definitions",
    "template",
    "instruction",
    "instructions",
    "blank",
    "glossary",
)
CURRENT_YEAR_RE = re.compile(r"20(24|25)[-_ /]?(20)?(25|26)|2024-25|2025-26", re.I)
ANY_YEAR_RE = re.compile(r"(20\d{2})[-_/ ]?(?:20)?(\d{2})")


@dataclass(frozen=True)
class RepairOptions:
    min_enrollment: int
    max_per_batch: int
    rps: float
    school_budget_seconds: float
    bing_fallback: bool
    brave_fallback: bool
    extract_repaired: bool
    extraction_python: str
    extraction_limit: int


@dataclass(frozen=True)
class RepairCandidate:
    url: str
    year: str | None
    evidence: str


class LinkParser(html.parser.HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.links: list[dict[str, str]] = []
        self._current: dict[str, str] | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() == "a":
            self._current = {k: v or "" for k, v in attrs}
            self._current["text"] = ""

    def handle_data(self, data: str) -> None:
        if self._current is not None:
            self._current["text"] = self._current.get("text", "") + data

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "a" and self._current is not None:
            self.links.append(self._current)
            self._current = None


def root_domain_from_url(url: str | None) -> str | None:
    if not url:
        return None
    raw = url.strip()
    if not raw:
        return None
    if "://" not in raw:
        raw = f"https://{raw}"
    try:
        host = urllib.parse.urlparse(raw).netloc.lower()
    except ValueError:
        return None
    if host.startswith("www."):
        host = host[4:]
    parts = host.split(".")
    if len(parts) >= 2:
        return ".".join(parts[-2:])
    return host or None


def url_host(url: str) -> str:
    return urllib.parse.urlparse(url).netloc.lower()


def is_official_host(url: str, root_domain: str) -> bool:
    host = url_host(url)
    return host == root_domain or host.endswith(f".{root_domain}")


def is_high_signal(row: dict[str, Any], min_enrollment: int) -> bool:
    enrollment = row.get("undergraduate_enrollment")
    try:
        enrollment_int = int(enrollment)
    except (TypeError, ValueError):
        enrollment_int = 0
    if enrollment_int >= min_enrollment:
        return True
    name = str(row.get("school_name") or "").lower()
    state = str(row.get("state") or "")
    return (
        enrollment_int >= min_enrollment // 2
        and state
        and (" university" in name or "state university" in name)
    )


def infer_year(text: str) -> str | None:
    match = ANY_YEAR_RE.search(text)
    if not match:
        return None
    start = int(match.group(1))
    end = int(match.group(2))
    if 2000 <= start <= 2030 and 0 <= end <= 99:
        return f"{start}-{end:02d}"
    return None


def looks_like_bad_doc(url: str) -> bool:
    lower = url.lower()
    return any(keyword in lower for keyword in BAD_DOC_KEYWORDS)


def looks_like_doc_url(url: str) -> bool:
    path = urllib.parse.urlparse(url).path.lower()
    return path.endswith(DOC_EXTENSIONS)


def fetch_bytes(url: str, *, read_bytes: int = 0, timeout: int = 20) -> tuple[int, dict[str, str], bytes]:
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "collegedata-fyi-ops/0.1"},
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout, context=probe_urls._SSL_CTX) as response:
            headers = {k.lower(): v for k, v in response.getheaders()}
            body = response.read(read_bytes) if read_bytes else response.read()
            return response.status, headers, body
    except (urllib.error.URLError, OSError, ValueError):
        return -1, {}, b""


def classify_url(url: str) -> str:
    status, headers, body = fetch_bytes(url, read_bytes=4096)
    if status != 200:
        return "unreachable"
    content_type = headers.get("content-type", "").lower()
    if any(kind in content_type for kind in ("pdf", "spreadsheet", "excel", "wordprocessingml")):
        return "document"
    if looks_like_doc_url(url):
        return "document"
    if "html" in content_type and b"common data set" in body.lower():
        return "landing"
    return "other"


def extract_document_candidates(landing_url: str, root_domain: str, *, max_docs: int = 1) -> list[RepairCandidate]:
    status, headers, body = fetch_bytes(landing_url)
    if status != 200:
        return []
    content_type = headers.get("content-type", "").lower()
    if "html" not in content_type:
        return []

    parser = LinkParser()
    parser.feed(body.decode("utf-8", errors="replace"))
    scored: list[tuple[int, RepairCandidate]] = []
    for link in parser.links:
        href = link.get("href") or ""
        if not href:
            continue
        url = urllib.parse.urljoin(landing_url, href.split("#", 1)[0])
        if not is_official_host(url, root_domain):
            continue
        if looks_like_bad_doc(url):
            continue
        if not looks_like_doc_url(url):
            continue

        text = " ".join((link.get("text") or "").split())
        evidence = f"{text} {url}"
        lower_evidence = evidence.lower()
        if "common data set" not in lower_evidence and "cds" not in lower_evidence:
            continue

        score = 0
        if CURRENT_YEAR_RE.search(evidence):
            score += 100
        if url.lower().endswith(".pdf"):
            score += 20
        if "common data set" in lower_evidence:
            score += 10
        scored.append((score, RepairCandidate(url=url, year=infer_year(evidence), evidence=text or url)))

    scored.sort(key=lambda item: item[0], reverse=True)
    return [candidate for _, candidate in scored[:max_docs]]


def discover_repair_candidate(
    *,
    school_name: str,
    website_url: str,
    options: RepairOptions,
    brave_api_key: str | None,
) -> tuple[RepairCandidate | None, dict[str, Any]]:
    root_domain = root_domain_from_url(website_url)
    if not root_domain:
        return None, {"reason": "missing_domain"}

    attempts: list[dict[str, Any]] = []
    urls: list[tuple[str, str]] = []
    pattern_url, patterns_tried = probe_urls.probe_school(
        root_domain,
        options.rps,
        options.school_budget_seconds,
    )
    attempts.append({"method": "pattern", "url": pattern_url, "patterns_tried": patterns_tried})
    if pattern_url:
        urls.append(("pattern", pattern_url))

    if not urls and options.bing_fallback:
        found = probe_urls.bing_html_search(root_domain)
        attempts.append({"method": "bing_html", "url": found})
        if found:
            urls.append(("bing_html", found))

    if not urls and options.brave_fallback and brave_api_key:
        found = probe_urls.brave_search(root_domain, brave_api_key)
        attempts.append({"method": "brave", "url": found})
        if found:
            urls.append(("brave", found))

    for method, found_url in urls:
        if not is_official_host(found_url, root_domain):
            attempts.append({"method": method, "url": found_url, "rejected": "non_official_host"})
            continue
        kind = classify_url(found_url)
        attempts.append({"method": method, "url": found_url, "kind": kind})
        if kind == "document" and not looks_like_bad_doc(found_url):
            return RepairCandidate(found_url, infer_year(found_url), f"{method}: direct document"), {
                "domain": root_domain,
                "attempts": attempts,
            }
        if kind == "landing":
            docs = extract_document_candidates(found_url, root_domain)
            if docs:
                return docs[0], {"domain": root_domain, "attempts": attempts, "landing_url": found_url}

    return None, {
        "domain": root_domain,
        "school_name": school_name,
        "attempts": attempts,
        "reason": "no_unambiguous_document",
    }


def fetch_directory_rows_by_school_id(client: Any, school_ids: list[str]) -> dict[str, dict[str, Any]]:
    if not school_ids:
        return {}
    rows = client.rest_get(
        "institution_directory",
        {
            "select": "school_id,school_name,state,website_url,undergraduate_enrollment",
            "school_id": f"in.({','.join(school_ids)})",
            "order": "school_id.asc",
        },
    )
    return {str(row.get("school_id")): row for row in rows}


def post_force_urls(client: Any, school: dict[str, Any], candidate: RepairCandidate) -> dict[str, Any]:
    item: dict[str, str] = {"url": candidate.url}
    if candidate.year:
        item["year"] = candidate.year
    payload = {
        "school_id": school["school_id"],
        "school_name": school["school_name"],
        "urls": [item],
    }
    return client.post_function_json("archive-process", payload)


def run_extraction_for_school(
    *,
    supabase_url: str,
    service_key: str,
    school_id: str,
    python_bin: str,
    limit: int,
) -> dict[str, Any]:
    if not Path(python_bin).exists() and "/" in python_bin:
        return {"school_id": school_id, "skipped": True, "reason": f"{python_bin} does not exist"}
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False) as fh:
        fh.write(f"SUPABASE_URL={supabase_url}\n")
        fh.write(f"SUPABASE_SERVICE_ROLE_KEY={service_key}\n")
        env_path = fh.name
    try:
        command = [
            python_bin,
            "tools/extraction_worker/worker.py",
            "--env",
            env_path,
            "--school",
            school_id,
            "--limit",
            str(limit),
            "--include-failed",
        ]
        completed = subprocess.run(command, text=True, capture_output=True, timeout=900)
        return {
            "school_id": school_id,
            "returncode": completed.returncode,
            "stdout_tail": completed.stdout[-4000:],
            "stderr_tail": completed.stderr[-2000:],
        }
    finally:
        try:
            os.unlink(env_path)
        except OSError:
            pass


def repair_high_signal_failures(
    *,
    client: Any,
    supabase_url: str,
    service_key: str,
    queue_rows: list[dict[str, Any]],
    options: RepairOptions,
    logger: batches.JsonlLogger,
) -> dict[str, Any]:
    failed = [
        row for row in queue_rows
        if row.get("last_outcome") == "no_pdfs_found" and row.get("school_id")
    ]
    metadata = fetch_directory_rows_by_school_id(client, [str(row["school_id"]) for row in failed])
    high_signal = [
        metadata[str(row["school_id"])]
        for row in failed
        if str(row["school_id"]) in metadata and is_high_signal(metadata[str(row["school_id"])], options.min_enrollment)
    ][: options.max_per_batch]

    brave_api_key = os.environ.get("BRAVE_API_KEY")
    repaired: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    extraction: list[dict[str, Any]] = []

    for school in high_signal:
        candidate, evidence = discover_repair_candidate(
            school_name=str(school.get("school_name") or school["school_id"]),
            website_url=str(school.get("website_url") or ""),
            options=options,
            brave_api_key=brave_api_key,
        )
        if not candidate:
            record = {"school_id": school["school_id"], "school_name": school.get("school_name"), **evidence}
            skipped.append(record)
            logger.write("repair_skipped", **record)
            continue

        try:
            outcome = post_force_urls(client, school, candidate)
            record = {
                "school_id": school["school_id"],
                "school_name": school.get("school_name"),
                "url": candidate.url,
                "year": candidate.year,
                "evidence": candidate.evidence,
                "outcome": outcome,
            }
            repaired.append(record)
            logger.write("repair_force_urls", **record)
            if options.extract_repaired:
                extract_report = run_extraction_for_school(
                    supabase_url=supabase_url,
                    service_key=service_key,
                    school_id=str(school["school_id"]),
                    python_bin=options.extraction_python,
                    limit=options.extraction_limit,
                )
                extraction.append(extract_report)
                logger.write("repair_extraction", **extract_report)
        except Exception as exc:
            record = {
                "school_id": school["school_id"],
                "school_name": school.get("school_name"),
                "url": candidate.url,
                "error": str(exc),
            }
            skipped.append(record)
            logger.write("repair_failed", **record)

    if repaired or skipped:
        refresh = batches.refresh_coverage(client)
        logger.write("repair_refresh", refresh=refresh)
    else:
        refresh = None

    return {
        "considered_failed": len(failed),
        "high_signal": len(high_signal),
        "repaired": repaired,
        "skipped": skipped,
        "extraction": extraction,
        "refresh": refresh,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env", default=".env")
    parser.add_argument("--out-dir", default="scratch/directory-enqueue-runs")
    parser.add_argument("--batch-size", type=int, default=25)
    parser.add_argument("--max-batches", type=int, default=1)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--uniform-cooldown-days", type=int, default=1)
    parser.add_argument("--poll-interval-seconds", type=int, default=30)
    parser.add_argument("--timeout-minutes", type=int, default=360)
    parser.add_argument("--stall-timeout-minutes", type=int, default=20)
    parser.add_argument("--max-transient-rate", type=float, default=0.25)
    parser.add_argument("--max-permanent-other-rate", type=float, default=0.05)
    parser.add_argument("--stop-on-transient-gate", action="store_true")
    parser.add_argument("--repair-min-enrollment", type=int, default=10_000)
    parser.add_argument("--repair-max-per-batch", type=int, default=5)
    parser.add_argument("--repair-school-budget-seconds", type=float, default=45.0)
    parser.add_argument("--repair-rps", type=float, default=2.0)
    parser.add_argument("--repair-bing-fallback", action="store_true")
    parser.add_argument("--repair-brave-fallback", action="store_true")
    parser.add_argument("--no-repair", action="store_true")
    parser.add_argument("--extract-repaired", action="store_true")
    parser.add_argument("--extraction-python", default=".context/extraction-venv/bin/python")
    parser.add_argument("--extraction-limit", type=int, default=3)
    return parser


def main(argv: list[str] | None = None) -> int:
    batches.configure_output_buffering()
    args = build_parser().parse_args(argv)
    try:
        supabase_url, service_key = batches.require_supabase_credentials(Path(args.env))
        client = batches.SupabaseClient(supabase_url, service_key)
        logger = batches.JsonlLogger(Path(args.out_dir))
        enqueue_options = batches.DirectoryEnqueueOptions(
            uniform_cooldown_days=args.uniform_cooldown_days,
        )
        repair_options = RepairOptions(
            min_enrollment=args.repair_min_enrollment,
            max_per_batch=args.repair_max_per_batch,
            rps=args.repair_rps,
            school_budget_seconds=args.repair_school_budget_seconds,
            bing_fallback=args.repair_bing_fallback,
            brave_fallback=args.repair_brave_fallback,
            extract_repaired=args.extract_repaired,
            extraction_python=args.extraction_python,
            extraction_limit=args.extraction_limit,
        )

        print(f"Writing JSONL log to {logger.path}")
        reports: list[dict[str, Any]] = []
        for batch_number in range(1, args.max_batches + 1):
            print(f"\n## Autopilot batch {batch_number}/{args.max_batches}")
            report = batches.run_batch(
                client,
                limit=args.batch_size,
                apply=args.apply,
                options=enqueue_options,
                logger=logger,
                timeout_seconds=args.timeout_minutes * 60,
                poll_interval_seconds=args.poll_interval_seconds,
                stall_timeout_seconds=args.stall_timeout_minutes * 60,
                max_transient_rate=args.max_transient_rate,
                max_permanent_other_rate=args.max_permanent_other_rate,
                stop_on_transient_gate=args.stop_on_transient_gate,
            )

            repair_report = None
            if args.apply and not args.no_repair and report.get("applied"):
                run_id = str(report.get("enqueue", {}).get("run_id") or "")
                queue_rows = batches.fetch_queue_rows(client, run_id)
                repair_report = repair_high_signal_failures(
                    client=client,
                    supabase_url=supabase_url,
                    service_key=service_key,
                    queue_rows=queue_rows,
                    options=repair_options,
                    logger=logger,
                )
                batches.print_json("High-signal repair", repair_report)

            reports.append({"batch": report, "repair": repair_report})
            if not report.get("applied"):
                break

        logger.write("autopilot_completed", reports=reports)
        print(f"\nCompleted. JSONL log: {logger.path}")
        return 0
    except (batches.OpsError, TimeoutError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
