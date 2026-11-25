"""Judge what the monthly stuck-seed re-probe actually achieved.

The re-probe replaces the seed of schools whose seed is one old file. A school
is only fixed when its new seed can reach a year newer than the archive holds
(or is a listing page that is current, because the school has not posted yet).
A single file older than the current year is not a fix: on 2026-11-02 the
station said `ok` while 71 of 78 schools stayed stuck, 46 of them with another
old single file.

Outcomes, per originally flagged school:

- ``fixed_newer_year``: the new seed reaches a year newer than the archive's
  newest. A document seed is read from its URL (academic_year.py); a listing
  page from the CDS years its links show.
- ``fixed_listing_matches``: the new seed is a listing page whose newest CDS
  year equals the archive's newest (the school has not posted yet).
- ``listing_unverified``: the new seed is a listing page we could not verify
  (fetch failed, no years on it, or its newest year is behind the archive).
- ``still_one_file``: still a document seed that is not newer than the archive.
- ``unchanged``: the seed did not change.

Only the two ``fixed_*`` outcomes count as fixed. ``still_stuck`` is flagged
minus fixed.

Usage:
    python tools/finder/reprobe_outcome.py \\
        --flagged finder-probe/stuck.json \\
        --schools-yaml tools/finder/schools.yaml \\
        --probe-summary finder-probe/stuck-probe-summary.json \\
        --out-json finder-probe/reprobe-outcome.json \\
        --out-md finder-probe/reprobe-outcome.md \\
        --out-heartbeat finder-probe/stuck-heartbeat.json
"""

from __future__ import annotations

import argparse
import http.client
import json
import sys
import urllib.error
import urllib.request
from html.parser import HTMLParser
from pathlib import Path
from typing import Callable
from urllib.parse import unquote, urlparse

try:  # run as a script or as tools.finder.reprobe_outcome
    from academic_year import normalize_academic_year
    from playwright_collect import is_cds_like
    from stuck_pdf_seeds import (
        is_direct_doc_seed,
        is_section_seed,
        load_schools,
        year_start,
    )
except ImportError:  # pragma: no cover - package import path
    from tools.finder.academic_year import normalize_academic_year
    from tools.finder.playwright_collect import is_cds_like
    from tools.finder.stuck_pdf_seeds import (
        is_direct_doc_seed,
        is_section_seed,
        load_schools,
        year_start,
    )

FIXED = ("fixed_newer_year", "fixed_listing_matches")
OUTCOMES = FIXED + ("listing_unverified", "still_one_file", "unchanged")

USER_AGENT = "collegedata-pipeline/stuck-pdf-verify"
FETCH_TIMEOUT_SEC = 15
MAX_PAGES = 250
MAX_PAGE_BYTES = 2_000_000


class _Links(HTMLParser):
    """Collect (href, link text) pairs from a page."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.links: list[tuple[str, str]] = []
        self._href: str | None = None
        self._buf: list[str] = []

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag == "a":
            self._href = dict(attrs).get("href") or ""
            self._buf = []

    def handle_data(self, data: str) -> None:
        if self._href is not None:
            self._buf.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag == "a" and self._href is not None:
            self.links.append((self._href, " ".join("".join(self._buf).split())))
            self._href = None


def has_cds_evidence(href: str, text: str) -> bool:
    """True when a link's URL or text names the Common Data Set.

    Uses the finder's own test (playwright_collect.is_cds_like). Separators in
    the URL are spaces for the match, so `irp_cds_2025.pdf` counts; a calendar,
    factbook, catalog or IPEDS report does not, whatever year it carries.
    """
    plain = unquote(href).replace("_", " ").replace("-", " ").replace("+", " ")
    return is_cds_like(href, text) or is_cds_like(plain, text)


def newest_year_in_html(html: str) -> str | None:
    """Newest CDS year among links that name the CDS, else None.

    A year on an unrelated link ("Academic calendar 2025-26") is ignored.
    """
    parser = _Links()
    parser.feed(html)
    parser.close()
    years = set()
    for href, text in parser.links:
        if not has_cds_evidence(href, text):
            continue
        year = normalize_academic_year(text) or normalize_academic_year(unquote(href))
        if year:
            years.add(year)
    if not years:
        return None
    return max(years, key=lambda y: year_start(y) or 0)


def newest_year_from_document_url(url: str) -> str | None:
    """Year in a document seed's filename, falling back to its path."""
    path = unquote(urlparse(url).path)
    return normalize_academic_year(path.rsplit("/", 1)[-1]) or normalize_academic_year(path)


def fetch_page(url: str, *, opener=urllib.request.urlopen) -> str | None:
    """Bounded, single-attempt fetch. None on any failure (-> unverified)."""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        with opener(req, timeout=FETCH_TIMEOUT_SEC) as resp:
            ctype = resp.headers.get("Content-Type", "")
            if "html" not in ctype.lower() and ctype:
                return None
            return resp.read(MAX_PAGE_BYTES).decode("utf-8", errors="replace")
    except (urllib.error.URLError, http.client.HTTPException, OSError, ValueError):
        return None


def _newer(
    candidate: str | None, archive_latest: str | None, floor: str | None = None
) -> bool:
    """True when ``candidate`` is newer than the archive AND current.

    ``floor`` is the freshness floor (the current CDS cycle). A single file
    older than the current year is not a fix, even when the archive holds
    nothing newer (#463).
    """
    c = year_start(candidate)
    if c is None:
        return False
    f = year_start(floor)
    if f is not None and c < f:
        return False
    a = year_start(archive_latest)
    return a is None or c > a


def classify_outcome(
    flagged: dict,
    new_seed: str | None,
    *,
    fetch: Callable[[str], str | None] = fetch_page,
) -> dict:
    """Outcome for one originally flagged school."""
    old_seed = flagged.get("seed") or ""
    archive_latest = flagged.get("latest")
    floor = flagged.get("min_fresh_year")
    if year_start(floor) is None:
        raise ValueError(f"flagged row has no usable min_fresh_year: {flagged.get('id')!r}")
    base = {
        "id": flagged.get("id"),
        "old_seed": old_seed,
        "new_seed": new_seed or "",
        "archive_latest": archive_latest,
        "seed_year": None,
    }
    if not new_seed or new_seed == old_seed:
        return {**base, "outcome": "unchanged"}
    if is_direct_doc_seed(new_seed):
        year = newest_year_from_document_url(new_seed)
        # A section file, or a document that does not name the CDS (a
        # factbook, catalog or IPEDS report), is never a fix, whatever year
        # its URL carries.
        counts = (
            not is_section_seed(new_seed)
            and has_cds_evidence(unquote(urlparse(new_seed).path), "")
            and _newer(year, archive_latest, floor)
        )
        return {**base, "outcome": "fixed_newer_year" if counts else "still_one_file", "seed_year": year}
    html = fetch(new_seed)
    year = newest_year_in_html(html) if html else None
    if year is None:
        return {**base, "outcome": "listing_unverified"}
    if _newer(year, archive_latest, floor):
        return {**base, "outcome": "fixed_newer_year", "seed_year": year}
    if year == archive_latest:
        return {**base, "outcome": "fixed_listing_matches", "seed_year": year}
    return {**base, "outcome": "listing_unverified", "seed_year": year}


def classify_all(
    flagged_rows: list[dict],
    seeds_now: dict[str, str],
    *,
    fetch: Callable[[str], str | None] = fetch_page,
    max_pages: int = MAX_PAGES,
) -> list[dict]:
    """Outcome for every flagged school; listing fetches are capped."""
    results = []
    fetched = 0

    def capped_fetch(url: str) -> str | None:
        nonlocal fetched
        if fetched >= max_pages:
            return None
        fetched += 1
        return fetch(url)

    for row in flagged_rows:
        results.append(
            classify_outcome(row, seeds_now.get(row.get("id") or ""), fetch=capped_fetch)
        )
    if len(results) != len(flagged_rows):
        raise RuntimeError("an outcome went missing for a flagged school")
    return results


def summarize(
    outcomes: list[dict],
    counts: dict[str, int],
    *,
    reprobed: int,
) -> dict[str, int]:
    """Heartbeat summary. ``still_stuck`` = flagged - fixed."""
    tally = {name: 0 for name in OUTCOMES}
    for row in outcomes:
        tally[row["outcome"]] += 1
    fixed = sum(tally[name] for name in FIXED)
    flagged = len(outcomes)
    if flagged != counts.get("flagged", flagged):
        raise RuntimeError(
            f"{flagged} outcomes but the classifier flagged {counts.get('flagged')}"
        )
    return {
        "stuck": flagged,
        "reprobed": reprobed,
        "still_stuck": flagged - fixed,
        "total": counts.get("total", 0),
        "fresh": counts.get("fresh", 0),
        "skipped": counts.get("skipped", 0),
        "fixed": fixed,
        "listing_unverified": tally["listing_unverified"],
    }


def render_markdown(outcomes: list[dict], summary: dict[str, int]) -> str:
    tally = {name: 0 for name in OUTCOMES}
    for row in outcomes:
        tally[row["outcome"]] += 1
    lines = [
        "# Re-probe outcome",
        "",
        f"Flagged: **{summary['stuck']}**. Fixed: **{summary['fixed']}**. "
        f"Still stuck: **{summary['still_stuck']}**. "
        f"Re-probed: {summary['reprobed']}.",
        "",
        "| outcome | schools |",
        "|---|---|",
    ]
    for name in OUTCOMES:
        lines.append(f"| `{name}` | {tally[name]} |")
    lines += ["", "| school_id | outcome | archive newest | seed year | new seed |", "|---|---|---|---|---|"]
    for row in outcomes:
        if row["outcome"] == "unchanged":
            continue
        seed = row["new_seed"].replace("|", "\\|")
        lines.append(
            f"| `{row['id']}` | {row['outcome']} | {row['archive_latest'] or 'none'} | "
            f"{row['seed_year'] or '-'} | `{seed}` |"
        )
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.strip().split("\n\n")[0])
    ap.add_argument("--flagged", type=Path, required=True,
                    help="stuck.json written by stuck_pdf_seeds.py before the re-probe")
    ap.add_argument("--schools-yaml", type=Path, required=True,
                    help="schools.yaml after the re-probe and landing-hint rewrite")
    ap.add_argument("--probe-summary", type=Path,
                    help="probe_urls.py --summary-json (for `reprobed`)")
    ap.add_argument("--out-json", type=Path)
    ap.add_argument("--out-md", type=Path)
    ap.add_argument("--out-heartbeat", type=Path)
    ap.add_argument("--max-pages", type=int, default=MAX_PAGES)
    args = ap.parse_args()

    before = json.loads(args.flagged.read_text())
    flagged_rows = before.get("stuck") or []
    counts = before.get("counts") or {}
    seeds_now = {
        s.get("id"): (s.get("discovery_seed_url") or s.get("cds_url_hint") or "")
        for s in load_schools(args.schools_yaml)
    }
    reprobed = 0
    if args.probe_summary and args.probe_summary.exists():
        reprobed = int(json.loads(args.probe_summary.read_text()).get("probed", 0))
    elif flagged_rows:
        # Loud: schools were flagged but the re-probe left no summary, so it
        # did not run (or died). "reprobed 0" would read as a quiet success.
        raise SystemExit(
            f"{len(flagged_rows)} schools were flagged but the re-probe wrote no "
            f"summary ({args.probe_summary}); the re-probe did not run"
        )

    outcomes = classify_all(flagged_rows, seeds_now, max_pages=args.max_pages)
    summary = summarize(outcomes, counts, reprobed=reprobed)
    print(
        "reprobe_outcome " + "  ".join(f"{k} {v}" for k, v in summary.items()),
        file=sys.stderr,
    )
    if args.out_json:
        args.out_json.parent.mkdir(parents=True, exist_ok=True)
        args.out_json.write_text(
            json.dumps({"summary": summary, "outcomes": outcomes}, indent=2) + "\n"
        )
    if args.out_md:
        args.out_md.parent.mkdir(parents=True, exist_ok=True)
        args.out_md.write_text(render_markdown(outcomes, summary))
    if args.out_heartbeat:
        args.out_heartbeat.parent.mkdir(parents=True, exist_ok=True)
        args.out_heartbeat.write_text(json.dumps(summary) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
