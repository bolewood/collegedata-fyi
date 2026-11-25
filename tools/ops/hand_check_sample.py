#!/usr/bin/env python3
"""Draw 20 random schools for the monthly hand check (#461).

The pipeline cannot report what it never looks for. In 2026 it stopped
collecting new CDS years for about 150 schools while every job ran green. This
script measures the miss rate from outside the pipeline: once a month a person
opens 20 schools' own sites and answers one question, "has this school posted
a CDS newer than the one we hold?"

It runs every month of the year, not only in the posting season, because files
appear from March to November (of the 2024-25 files, 18% existed by February
and 81% by August; see docs/postmortems/2026-11-24-stale-discovery-seeds.md).

The draw is seeded by the month (YYYY-MM), so a rerun picks the same 20.
Years are compared as integers parsed from ``^\\d{4}-\\d{2}$``. The text
``unknown`` sorts above every real year, so it is never compared as text.

Usage:
    python tools/ops/hand_check_sample.py --month 2026-11
    python tools/ops/hand_check_sample.py --manifest-json snapshot.json \\
        --prev-body-file last-month.md --out issue.md

Live reads need SUPABASE_URL and SUPABASE_ANON_KEY (the public anon key).
"""

from __future__ import annotations

import argparse
import json
import os
import random
import re
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import quote_plus

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
SCHOOLS_YAML = REPO_ROOT / "tools" / "finder" / "schools.yaml"
SITE = "https://www.collegedata.fyi"
SAMPLE_SIZE = 20
PAGE_SIZE = 1000
YEAR_RE = re.compile(r"^(\d{4})-(\d{2})\Z")
MONTH_RE = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")

LABEL_MISS = "newer CDS on the school's site (a miss)"
LABEL_NONE = "nothing newer posted"
LABEL_UNSURE = "couldn't tell"
LABEL_FALSE_GREEN = "our newest-year file is not a full CDS (section only, change sheet, blank, wrong school)"
MARKER_RE = re.compile(r"<!--\s*hand-check-school:(\S+?)\s*-->")
MONTH_MARKER_RE = re.compile(r"<!--\s*hand-check-month:(\d{4}-\d{2})\s*-->")
BOX_RE = re.compile(r"^\s*-\s*\[( |x|X)\]\s*(.+?)\s*$")


def start_year(year: str | None) -> int | None:
    """Integer start year of a valid CDS year string, else None."""
    m = YEAR_RE.match(year or "")
    if not m:
        return None
    start = int(m.group(1))
    # "2025-2026" fails the regex; "2025-27" fails here: the suffix must be
    # the next year's last two digits.
    return start if int(m.group(2)) == (start + 1) % 100 else None


def newest_years(rows: Iterable[dict[str, Any]]) -> dict[str, str | None]:
    """school_id -> newest valid canonical_year, or None when only undated."""
    best: dict[str, tuple[int, str] | None] = {}
    for row in rows:
        sid = row["school_id"]
        best.setdefault(sid, None)
        y = row.get("canonical_year")
        n = start_year(y)
        if n is None:
            continue
        cur = best[sid]
        if cur is None or n > cur[0]:
            best[sid] = (n, y)
    return {sid: (v[1] if v else None) for sid, v in best.items()}


def pick_schools(newest: dict[str, str | None], month: str, k: int = SAMPLE_SIZE) -> list[str]:
    """Uniform random k schools, seeded by the month so reruns agree."""
    if not MONTH_RE.match(month):
        raise ValueError(f"month must be YYYY-MM, got {month!r}")
    ids = sorted(newest)
    if len(ids) < k:
        raise ValueError(f"only {len(ids)} schools with a live document; need {k}")
    return random.Random(f"hand-check-{month}").sample(ids, k)


def fetch_live_rows(base_url: str, anon_key: str) -> list[dict[str, Any]]:
    """Page through live published cds_manifest rows; raise on any shortfall."""
    query = (
        "select=school_id,school_name,canonical_year"
        "&removed_at=is.null&participation_status=eq.published&order=document_id"
    )
    rows: list[dict[str, Any]] = []
    total: int | None = None
    offset = 0
    while True:
        req = urllib.request.Request(
            f"{base_url.rstrip('/')}/rest/v1/cds_manifest?{query}",
            headers={
                "apikey": anon_key,
                "User-Agent": "collegedata-pipeline/hand-check",
                "Authorization": f"Bearer {anon_key}",
                "Prefer": "count=exact",
                "Range-Unit": "items",
                "Range": f"{offset}-{offset + PAGE_SIZE - 1}",
            },
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            content_range = resp.headers.get("Content-Range", "")
            page = json.loads(resp.read().decode("utf-8"))
        m = re.match(r"^(?:(\d+)-\d+|\*)/(\d+)$", content_range)
        if not m:
            raise RuntimeError(f"no usable Content-Range header: {content_range!r}")
        if page and (m.group(1) is None or int(m.group(1)) != offset):
            raise RuntimeError(f"page started at {m.group(1)}, expected {offset}: {content_range!r}")
        if total is not None and int(m.group(2)) != total:
            raise RuntimeError(f"total changed during paging: {total} -> {m.group(2)}")
        total = int(m.group(2))
        rows.extend(page)
        offset += len(page)
        if not page or len(rows) >= total:
            break
    if total is None or total == 0 or len(rows) != total:
        raise RuntimeError(f"manifest read returned {len(rows)} rows, expected {total}")
    return rows


def load_schools_yaml(path: Path = SCHOOLS_YAML) -> dict[str, dict[str, Any]]:
    doc = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return {s["id"]: s for s in doc.get("schools") or []}


def classify_box(text: str, school_id: str) -> str:
    """miss / none / unsure for a ticked box; raise on any other text.

    Matches stable tokens so a note appended after the label, or a curly
    apostrophe, does not drop the answer.
    """
    t = text.replace("\u2019", "'").replace("\u2018", "'").lower()
    if "(a miss)" in t:
        return "miss"
    if "nothing newer posted" in t:
        return "none"
    if "not a full cds" in t:
        return "false_green"
    if "couldn't tell" in t:
        return "unsure"
    raise ValueError(f"school {school_id} has a ticked box that matches no answer: {text!r}")


def month_of(body: str | None) -> str | None:
    m = MONTH_MARKER_RE.search(body or "")
    return m.group(1) if m else None


def split_issues(issues: list[dict[str, Any]], month: str) -> tuple[bool, str | None]:
    """(this month's issue exists, body of the newest earlier hand-check issue).

    Only issues carrying the month marker count, so an unrelated issue that
    happens to carry the label is never read as an answer sheet. `issues` is
    newest first, as `gh issue list` returns it.
    """
    exists = False
    prev: str | None = None
    for issue in issues:
        body = issue.get("body") or ""
        issue_month = month_of(body)
        if issue_month is None:
            continue
        if issue_month == month:
            exists = True
        elif issue_month < month and prev is None:
            prev = body
    return exists, prev


def count_answers(prev_body: str) -> tuple[int, int, int, int]:
    """(misses, answered, unanswered, false_greens) from last month's issue body.

    A school is answered when the "nothing newer" or "newer CDS" box is
    checked. "Couldn't tell" and no box at all both count as unanswered.
    The "not a full CDS" box is a separate tick that can go with any answer;
    it counts a false green (our newest file is not a full CDS).
    Raises when the body holds no school blocks, so a body the parser cannot
    read never shows up as "0 misses".
    """
    blocks: dict[str, list[tuple[bool, str]]] = {}
    current: str | None = None
    for line in prev_body.splitlines():
        m = MARKER_RE.search(line)
        if m:
            current = m.group(1)
            blocks.setdefault(current, [])
            continue
        box = BOX_RE.match(line)
        if box and current is not None:
            blocks[current].append((box.group(1).lower() == "x", box.group(2)))
    if not blocks:
        raise ValueError("previous issue body has no school blocks; cannot count answers")
    misses = answered = false_greens = 0
    for sid, boxes in blocks.items():
        kinds = {classify_box(text, sid) for on, text in boxes if on}
        if {"miss", "none"} <= kinds:
            raise ValueError(f"school {sid} has both 'a miss' and 'nothing newer' ticked")
        if "false_green" in kinds:
            false_greens += 1
        if "miss" in kinds:
            misses += 1
            answered += 1
        elif "none" in kinds:
            answered += 1
    return misses, answered, len(blocks) - answered, false_greens


def render_issue(
    picks: list[dict[str, Any]],
    month: str,
    prev_body: str | None = None,
    extra_section: str | None = None,
) -> str:
    lines: list[str] = []
    if prev_body is not None:
        misses, answered, unanswered, false_greens = count_answers(prev_body)
        lines += [
            f"Last month: {misses} misses of {answered} answered ({unanswered} unanswered), "
            f"{false_greens} false greens",
            "",
        ]
    else:
        lines += ["Last month: no earlier hand check to count.", ""]
    lines += [
        f"Hand check for {month}. For each school below, open the school's own "
        "site (not ours) and look for its Common Data Set page. Answer one "
        "question: has the school posted a CDS newer than our newest year? Tick "
        "exactly one answer per school, and also open our newest-year document and tick the last box if it "
        "is not a full CDS. A tick on \"a miss\" names a school to fix "
        "and a failure shape to sweep the rest of the corpus for. This runs "
        "every month of the year because schools post from March to November.",
        "",
    ]
    if extra_section and extra_section.strip():
        # Before the school blocks: count_answers reads only boxes after a school
        # marker, and this section has none.
        lines += [extra_section.strip(), ""]
    for p in picks:
        newest = p["newest_year"] or "undated only"
        lines += [f"### {p['name']}", f"<!-- hand-check-school:{p['school_id']} -->", ""]
        lines.append(f"Our newest year: {newest}")
        lines.append(f"- Our page: {SITE}/schools/{p['school_id']}")
        if p["newest_year"]:
            lines.append(f"- Our newest-year document: {SITE}/schools/{p['school_id']}/{p['newest_year']}")
        if p.get("domain"):
            domain = p["domain"]
            query = quote_plus(f'site:{domain} "common data set"')
            lines.append(f"- School site: https://{domain}")
            lines.append(f"- Search: https://www.google.com/search?q={query}")
        else:
            lines.append("- School site: no domain on file")
        lines.append(f"- Seed URL: {p.get('seed_url') or 'none on file'}")
        lines += ["", f"- [ ] {LABEL_MISS}", f"- [ ] {LABEL_NONE}", f"- [ ] {LABEL_UNSURE}", f"- [ ] {LABEL_FALSE_GREEN}", ""]
    lines.append(f"<!-- hand-check-month:{month} -->")
    return "\n".join(lines).rstrip() + "\n"


def build_picks(
    rows: list[dict[str, Any]],
    schools: dict[str, dict[str, Any]],
    month: str,
) -> list[dict[str, Any]]:
    newest = newest_years(rows)
    names = {r["school_id"]: r["school_name"] for r in rows if r.get("school_name")}
    picks = []
    for sid in pick_schools(newest, month):
        entry = schools.get(sid)
        if entry is None:
            raise RuntimeError(f"school {sid} has a live document but is not in schools.yaml")
        picks.append(
            {
                "school_id": sid,
                "name": names.get(sid) or entry.get("name") or sid,
                "newest_year": newest[sid],
                "domain": entry.get("domain"),
                "seed_url": entry.get("discovery_seed_url"),
            }
        )
    return picks


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--month", default=datetime.now(timezone.utc).strftime("%Y-%m"))
    ap.add_argument("--manifest-json", help="read rows from this file instead of the API")
    ap.add_argument("--prev-body-file", help="last month's issue body, to count its answers")
    ap.add_argument("--issues-json", help="gh issue list JSON (newest first) to find the previous issue")
    ap.add_argument("--exists-out", help="write true/false: does this month's issue already exist")
    ap.add_argument("--extra-section-file", help="markdown section to put before the school blocks (fetch failures)")
    ap.add_argument("--out", help="write the issue body here (default: stdout)")
    args = ap.parse_args()

    if args.manifest_json:
        rows = json.loads(Path(args.manifest_json).read_text(encoding="utf-8"))
        rows = [
            r for r in rows
            if r.get("removed_at") is None and r.get("participation_status") == "published"
        ]
        if not rows:
            raise SystemExit("manifest file has no live published rows")
    else:
        url = os.environ.get("SUPABASE_URL")
        key = os.environ.get("SUPABASE_ANON_KEY")
        if not url or not key:
            raise SystemExit("SUPABASE_URL and SUPABASE_ANON_KEY are required without --manifest-json")
        rows = fetch_live_rows(url, key)

    prev_body = None
    if args.prev_body_file:
        prev_body = Path(args.prev_body_file).read_text(encoding="utf-8")
        if not prev_body.strip():
            raise SystemExit("--prev-body-file is empty")

    if args.issues_json:
        exists, found = split_issues(json.loads(Path(args.issues_json).read_text(encoding="utf-8")), args.month)
        if found is not None:
            prev_body = found
        if args.exists_out:
            Path(args.exists_out).write_text("true" if exists else "false", encoding="utf-8")

    picks = build_picks(rows, load_schools_yaml(), args.month)
    extra = None
    if args.extra_section_file:
        extra = Path(args.extra_section_file).read_text(encoding="utf-8")
        if not extra.strip():
            raise SystemExit("--extra-section-file is empty")
    body = render_issue(picks, args.month, prev_body, extra)
    if args.out:
        Path(args.out).write_text(body, encoding="utf-8")
    else:
        sys.stdout.write(body)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
