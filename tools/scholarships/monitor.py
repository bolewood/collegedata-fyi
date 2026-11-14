#!/usr/bin/env python3
"""Change monitor for the named scholarship directory (PRD 036 M4).

For every served version (`model.select_published`), fetch each source URL
through `PoliteFetcher` and write one row to `scholarship_version_checks`.
The monitor never edits the YAML, never publishes and never changes terms.
`needs_review` on the latest row is what flips the public freshness status.

Usage:
    python tools/scholarships/monitor.py                         # dry run: fetch, print, write nothing
    python tools/scholarships/monitor.py --apply                 # write check rows, refresh the cache
    python tools/scholarships/monitor.py --mode milestones       # only versions with a required/priority
                                                                 # dated milestone 30 or 7 days away
    python tools/scholarships/monitor.py --only some-program --limit 5
    python tools/scholarships/monitor.py --cache-file scratch/scholarships/fetch-cache.json \\
        --findings-json findings.json --findings-md findings.md

Rules (the report for M4 states the same):

* Two hashes per source: `raw_sha256` of the bytes and `text_sha256` of the
  normalized main text. A markup-only change moves the first, not the second,
  and is `unchanged`. Normalizer rule (NORMALIZER_VERSION below): see
  `normalize_page`. If the previous row used another normalizer version the
  text hashes are not compared; the row re-baselines (`normalizer_rebaseline`).
* Baseline = the previous check row for the version. No previous row: the row
  is `unchanged` with `baseline_only`. A YAML `content_sha256` is the raw-bytes
  baseline then: equal is `unchanged`; different cannot be split into markup or
  terms (no text baseline), so it is recorded with `raw_differs_from_yaml` and
  does not set `needs_review`.
* Each row stores per-source tokens (amounts, dates, years, selection words) so
  the next run can diff them: a hash alone cannot say what changed.
* Normalized text changed: `changed`, `needs_review`, and a deterministic diff of
  the tokens (empty diff still counts: "text changed, no amount, date, year or
  selection word changed").
* `needs_review` is carried forward from the previous row until a person clears
  it (runbook), so an unchanged re-check never silently restores the old status.
* Unreachable (robots block, robots unreachable, login/CAPTCHA, any HTTP error
  including 404) never sets `needs_review`; a 404 never implies the program ended.
  The previous baseline is carried through so the next good fetch still diffs.
* Result precedence for one version: changed > stale_signal > (carried review
  origin) > unreachable > unchanged. Every signal is listed in `detail`.
* The conditional-GET cache is a plain file given by --cache-file. It is
  written only after a successful --apply database write, never in a dry run,
  and entries for a URL with no baseline are dropped before the fetch.

Credentials: SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY (environment or .env).
A dry run uses them read-only when present, to diff against the stored
baselines; without them every source is treated as a first run, and says so.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import re
import sys
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import model  # noqa: E402
import validate  # noqa: E402

REPO_ROOT = validate.REPO_ROOT
sys.path.insert(0, str(REPO_ROOT))
from tools.common.polite_fetch import (  # noqa: E402
    NOT_MODIFIED,
    OK,
    PoliteFetcher,
)

NORMALIZER_VERSION = 1
PRODUCT_TOKEN = "scholarship-monitor"
SELECTION_WORDS = ("guaranteed", "automatic", "competitive", "considered", "required", "deadline", "no longer")
MILESTONE_DAYS = (30, 7)
MAX_FINDINGS_CHARS = 60_000
ARCHIVE_SAVE = "https://web.archive.org/save/"
TOKEN_KEYS = ("amounts", "dates", "years", "selection_words")

# ------------------------------------------------------------------ normalizer

_DROP_TAGS = ("script", "style", "noscript", "template", "svg", "iframe", "nav", "footer", "aside", "form")
_ZERO_WIDTH = re.compile("[​‌‍⁠﻿]")
_WS = re.compile(r"\s+")


def _clean(text: str) -> str:
    text = unicodedata.normalize("NFKC", text)
    text = _ZERO_WIDTH.sub("", text)
    return _WS.sub(" ", text).strip().lower()


def _decode(body: bytes, content_type: str) -> str:
    m = re.search(r"charset=([\w.-]+)", content_type or "", re.I)
    for enc in ([m.group(1)] if m else []) + ["utf-8"]:
        try:
            return body.decode(enc)
        except (LookupError, UnicodeDecodeError):
            continue
    return body.decode("utf-8", errors="replace")


@dataclass
class Page:
    text: Optional[str]  # None when the bytes cannot be read as text
    headings: List[str] = field(default_factory=list)


def normalize_page(body: bytes, content_type: str = "") -> Page:
    """Normalized main text of a fetched page. NORMALIZER_VERSION 1:

    HTML is parsed with html.parser; comments and script, style, noscript,
    template, svg, iframe, nav, footer, aside and form elements are dropped;
    the text of the first <main>, <article> or [role=main] (else <body>) is
    joined with single spaces, Unicode NFKC folded, zero-width characters
    removed, lower-cased and whitespace-collapsed. text_sha256 is SHA-256 of the
    UTF-8 text. Plain text gets the same folding. PDFs go through pypdf when it
    is installed; an unreadable PDF has text None (raw bytes only).
    Change any of this and bump NORMALIZER_VERSION.
    """
    ctype = (content_type or "").lower()
    if body[:5] == b"%PDF-" or "pdf" in ctype:
        return _normalize_pdf(body)
    raw = _decode(body, content_type)
    if "html" not in ctype and not re.search(r"<\s*(html|body|div|p|h1|main)\b", raw[:4096], re.I):
        return Page(_clean(raw))
    from bs4 import BeautifulSoup, Comment

    soup = BeautifulSoup(raw, "html.parser")
    for c in soup.find_all(string=lambda s: isinstance(s, Comment)):
        c.extract()
    for tag in soup.find_all(_DROP_TAGS):
        tag.decompose()
    root = soup.find("main") or soup.find("article") or soup.find(attrs={"role": "main"}) or soup.body or soup
    headings = [h for h in (_clean(t.get_text(" ")) for t in root.find_all(["h1", "h2", "h3"])) if h]
    return Page(_clean(root.get_text(" ")), headings)


def _normalize_pdf(body: bytes) -> Page:
    try:
        import io

        from pypdf import PdfReader

        reader = PdfReader(io.BytesIO(body))
        text = " ".join((p.extract_text() or "") for p in reader.pages)
    except Exception:
        return Page(None)
    cleaned = _clean(text)
    return Page(cleaned or None)


# ---------------------------------------------------------------------- tokens

_MONTHS = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}
_MON_NAMES = "|".join(
    ["jan(?:uary)?", "feb(?:ruary)?", "mar(?:ch)?", "apr(?:il)?", "may", "june?", "july?",
     "aug(?:ust)?", "sep(?:t(?:ember)?)?", "oct(?:ober)?", "nov(?:ember)?", "dec(?:ember)?"]
)
_AMOUNT_RE = re.compile(r"\$\s?(\d{1,3}(?:,\d{3})+|\d+)(?:\.(\d{1,2}))?(?:\s?(thousand|million|k|m)\b)?")
_DATE_NAMED_RE = re.compile(
    rf"\b({_MON_NAMES})\.?\s+(\d{{1,2}})(?!\d)(?:st|nd|rd|th)?(?:,?\s+(20\d\d)\b)?"
)
_DATE_MONTH_YEAR_RE = re.compile(rf"\b({_MON_NAMES})\.?,?\s+(20\d\d)\b")
_DATE_SLASH_RE = re.compile(r"\b(\d{1,2})/(\d{1,2})/(\d{4}|\d{2})\b")
_DATE_ISO_RE = re.compile(r"\b(20\d\d)-(\d\d)-(\d\d)\b")
_YEAR_RE = re.compile(r"\b(20[1-4]\d)\b")
_SEL_RE = re.compile(r"\b(guaranteed|automatic(?:ally)?|competitive|considered|required|deadline|no longer)\b")
_DEADLINE_WINDOW_RE = re.compile(
    r"\b(?:deadlines?|due|apply by|submitted by|postmarked by|closes?)\b[^.;]{0,80}", re.I
)
_MULT = {"k": 1_000, "thousand": 1_000, "m": 1_000_000, "million": 1_000_000}


def _mon(name: str) -> int:
    return _MONTHS[name[:3]]


def extract_tokens(text: str) -> Dict[str, List[Any]]:
    """Amounts, dates, years and selection words in already-normalized text,
    each sorted and unique. Amounts are dollars ("$12000"); dates are "mon d"
    or "mon d yyyy" or "mon yyyy"; years are four-digit years 2010-2049 that
    are not part of an amount."""
    amounts = set()
    for m in _AMOUNT_RE.finditer(text):
        n = float(m.group(1).replace(",", "") + ("." + m.group(2) if m.group(2) else ""))
        n *= _MULT.get(m.group(3) or "", 1)
        amounts.add("$" + (str(int(n)) if n == int(n) else f"{n:.2f}"))
    stripped = _AMOUNT_RE.sub(" ", text)

    dates = set()
    for m in _DATE_NAMED_RE.finditer(stripped):
        dates.add(f"{m.group(1)[:3]} {int(m.group(2))}" + (f" {m.group(3)}" if m.group(3) else ""))
    for m in _DATE_MONTH_YEAR_RE.finditer(stripped):
        dates.add(f"{m.group(1)[:3]} {m.group(2)}")
    for m in _DATE_SLASH_RE.finditer(stripped):
        mo, d, y = int(m.group(1)), int(m.group(2)), m.group(3)
        if 1 <= mo <= 12 and 1 <= d <= 31:
            y = y if len(y) == 4 else "20" + y
            dates.add(f"{list(_MONTHS)[mo - 1]} {d} {y}")
    for m in _DATE_ISO_RE.finditer(stripped):
        mo, d = int(m.group(2)), int(m.group(3))
        if 1 <= mo <= 12 and 1 <= d <= 31:
            dates.add(f"{list(_MONTHS)[mo - 1]} {d} {m.group(1)}")

    years = sorted({int(y) for y in _YEAR_RE.findall(stripped)})
    words = {("automatic" if w.startswith("automatic") else w) for w in _SEL_RE.findall(text)}
    return {
        "amounts": sorted(amounts, key=lambda a: (float(a[1:]), a)),
        "dates": sorted(dates),
        "years": years,
        "selection_words": sorted(words),
    }


def deadline_years(text: str) -> List[int]:
    """Years that appear within 80 characters after a deadline-ish word."""
    out = set()
    for m in _DEADLINE_WINDOW_RE.finditer(_AMOUNT_RE.sub(" ", text)):
        out.update(int(y) for y in _YEAR_RE.findall(m.group(0)))
    return sorted(out)


_HEAD_CLASS_OF = re.compile(r"\bclass of\s+(20\d\d)\b")
_HEAD_ACADEMIC = re.compile(r"\b(20\d\d)\s*[-–—/]\s*(?:20)?(\d\d)(?!\d)(?!-\d)")
_HEAD_FALL = re.compile(r"\b(?:fall|entering|entrants?|incoming)\b[^\d]{0,25}(20\d\d)\b")
_HEAD_YEAR_FIRST = re.compile(r"(?<!of )\b(20\d\d)\s+(?:entering|entrants?|incoming|applicants?|cycle)\b")


def heading_entry_years(headings: List[str]) -> List[int]:
    """Entering years named in headings. "Class of 2030" is entry year 2026; an
    academic year "2025-26" is entry year 2025; "fall 2026" and "2026 entering"
    are 2026."""
    out = set()
    for h in headings:
        out.update(int(y) - 4 for y in _HEAD_CLASS_OF.findall(h))
        out.update(int(a) for a, _ in _HEAD_ACADEMIC.findall(h))
        out.update(int(y) for y in _HEAD_FALL.findall(h))
        out.update(int(y) for y in _HEAD_YEAR_FIRST.findall(h))
    return sorted(out)


def diff_tokens(old: Dict[str, List[Any]], new: Dict[str, List[Any]]) -> Dict[str, Dict[str, List[Any]]]:
    """Deterministic added/removed per token category; empty categories omitted."""
    out: Dict[str, Dict[str, List[Any]]] = {}
    for key in TOKEN_KEYS:
        a, b = old.get(key) or [], new.get(key) or []
        added = [x for x in b if x not in a]
        removed = [x for x in a if x not in b]
        if added or removed:
            out[key] = {"added": added, "removed": removed}
    return out


# --------------------------------------------------------------------- staleness


def version_year(row: Dict[str, Any]) -> Optional[int]:
    return model.rank_year(row.get("entry_year"), row.get("cycle_through_date"), row.get("source_retrieved_at"))


def stale_signals(row: Dict[str, Any], sources: List[Dict[str, Any]], today: dt.date) -> List[Dict[str, Any]]:
    """Staleness signals for a version from the per-source facts. Skipped for a
    version already in a past cycle (the freshness rule covers it)."""
    year = version_year(row)
    if year is None or year < model.current_entry_year(today):
        return []
    out: List[Dict[str, Any]] = []
    all_years: List[int] = []
    have_facts = False
    for s in sources:
        facts = s.get("facts")
        if not facts:
            continue
        have_facts = True
        all_years.extend(facts.get("years") or [])
        heads = facts.get("heading_entry_years") or []
        if not heads:
            continue
        top = max(heads)
        if top < year:
            out.append({
                "code": "heading_year_older_than_cycle",
                "source_id": s["source_id"],
                "message": f"heading names entering year {top}; this version is for {year}",
            })
        bad = [y for y in (facts.get("deadline_years") or []) if y not in (top - 1, top)]
        if bad:
            out.append({
                "code": "heading_year_conflicts_with_deadline_years",
                "source_id": s["source_id"],
                "message": f"heading names entering year {top} but deadline text names {bad}",
            })
    dated = [m["date"] for m in _dated_milestones(row)]
    if have_facts and dated:
        try:
            all_past = all(dt.date.fromisoformat(d) < today for d in dated)
        except ValueError:
            all_past = False
        if all_past and not any(y >= year + 1 for y in all_years):
            out.append({
                "code": "all_milestones_past_no_next_cycle",
                "source_id": None,
                "message": f"every dated milestone is past and no page names {year + 1} or later",
            })
    return out


# ------------------------------------------------------------------- selection


def _dated_milestones(row: Dict[str, Any]) -> List[Dict[str, Any]]:
    app = (row.get("record") or {}).get("application") or {}
    return [m for m in (app.get("milestones") or []) if m.get("date")]


def milestone_due(row: Dict[str, Any], today: dt.date) -> bool:
    """A required or priority dated milestone exactly 30 or 7 days away."""
    for m in _dated_milestones(row):
        if m.get("requirement") not in ("required", "priority"):
            continue
        try:
            days = (dt.date.fromisoformat(m["date"]) - today).days
        except ValueError:
            continue
        if days in MILESTONE_DAYS:
            return True
    return False


def select_versions(
    ds: model.Dataset,
    mode: str,
    today: dt.date,
    only: Optional[List[str]] = None,
    limit: Optional[int] = None,
) -> List[Dict[str, Any]]:
    rows = model.select_published(ds)
    if only:
        rows = [r for r in rows if r["program_id"] in only]
    if mode == "milestones":
        rows = [r for r in rows if milestone_due(r, today)]
    if limit is not None:
        rows = rows[:limit]
    return rows


# ------------------------------------------------------------------------ store


class CheckStore:
    """The database operations the monitor needs. SupabaseCheckStore is the real one."""

    def known_versions(self) -> set:  # pragma: no cover
        """(program_id, version_id) pairs loaded into scholarship_program_versions."""
        raise NotImplementedError

    def latest(self, program_id: str, version_id: str) -> Optional[Dict[str, Any]]:  # pragma: no cover
        raise NotImplementedError

    def insert(self, rows: List[Dict[str, Any]]) -> None:  # pragma: no cover
        raise NotImplementedError

    def refresh(self) -> None:  # pragma: no cover
        raise NotImplementedError


class SupabaseCheckStore(CheckStore):
    def __init__(self, url: str, key: str) -> None:
        try:
            from supabase import create_client
        except ImportError as exc:  # pragma: no cover
            raise SystemExit("supabase package is required for the monitor") from exc
        self.client = create_client(url, key)

    @classmethod
    def from_env(cls, required: bool) -> Optional["SupabaseCheckStore"]:
        _load_env(REPO_ROOT / ".env")
        url, key = os.environ.get("SUPABASE_URL"), os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
        if not url or not key:
            if required:
                raise SystemExit("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY are required for --apply")
            return None
        return cls(url, key)

    def known_versions(self) -> set:
        out: set = set()
        start = 0
        while True:
            page = (
                self.client.table("scholarship_program_versions")
                .select("program_id,version_id")
                .order("program_id")
                .order("version_id")
                .range(start, start + 999)
                .execute()
                .data
            )
            out.update((r["program_id"], r["version_id"]) for r in page)
            if len(page) < 1000:
                return out
            start += 1000

    def latest(self, program_id: str, version_id: str) -> Optional[Dict[str, Any]]:
        res = (
            self.client.table("scholarship_version_checks")
            .select("program_id,version_id,checked_at,result,needs_review,detail")
            .eq("program_id", program_id)
            .eq("version_id", version_id)
            .order("checked_at", desc=True)
            .order("id", desc=True)
            .limit(1)
            .execute()
        )
        return res.data[0] if res.data else None

    def insert(self, rows: List[Dict[str, Any]]) -> None:
        for i in range(0, len(rows), 100):
            self.client.table("scholarship_version_checks").insert(rows[i : i + 100]).execute()

    def refresh(self) -> None:
        self.client.rpc("refresh_scholarship_directory_cache").execute()


def _load_env(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


# ----------------------------------------------------------------- source check

_CARRY = ("raw_sha256", "text_sha256", "normalizer_version", "tokens", "facts", "baseline_fetched_at")


def _prev_sources(prev: Optional[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    detail = (prev or {}).get("detail") or {}
    return {s["source_id"]: s for s in detail.get("sources", []) if isinstance(s, dict) and s.get("source_id")}


def _sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def check_source(
    src: Dict[str, Any], prev: Optional[Dict[str, Any]], fetcher: PoliteFetcher, now_iso: str
) -> Tuple[Dict[str, Any], Optional[Dict[str, Any]]]:
    """Fetch one source and compare it to its previous entry.

    Returns (entry for detail.sources, diff or None). `change` is one of
    baseline, none, markup_only, text_changed, raw_changed, normalizer_rebaseline.
    """
    url = src["url"]
    has_base = bool(prev and prev.get("raw_sha256"))
    if not has_base:
        fetcher.cache.pop(url, None)  # a 304 has no body to baseline from
    entry: Dict[str, Any] = {
        "source_id": src["source_id"],
        "url": url,
        "authority": src.get("authority"),
    }

    def carry() -> None:
        for k in _CARRY:
            if prev and k in prev:
                entry[k] = prev[k]

    res = fetcher.fetch(url)
    entry["fetch_status"] = res.status
    entry["http_status"] = res.http_status
    if res.status == NOT_MODIFIED and has_base:
        carry()
        entry.update({"fetched": False, "status": "not_modified", "change": "none"})
        return entry, None
    if res.status != OK:
        reason = res.reason or res.status
        if res.status == NOT_MODIFIED:
            reason = "304 Not Modified but no stored baseline"
        if res.http_status in (404, 410):
            reason += "; a missing page does not mean the program ended"
        carry()
        entry.update({"fetched": False, "status": "unreachable", "reason": reason, "change": "none"})
        return entry, None

    body = res.body or b""
    page = normalize_page(body, res.headers.get("content-type", ""))
    raw = _sha(body)
    text_sha = _sha(page.text.encode("utf-8")) if page.text is not None else None
    tokens = extract_tokens(page.text) if page.text is not None else None
    facts = {
        "years": (tokens or {}).get("years", []),
        "heading_entry_years": heading_entry_years(page.headings),
        "deadline_years": deadline_years(page.text) if page.text is not None else [],
    }
    entry.update({
        "fetched": True,
        "status": "ok",
        "raw_sha256": raw,
        "text_sha256": text_sha,
        "normalizer_version": NORMALIZER_VERSION,
        "tokens": tokens,
        "facts": facts,
        "baseline_fetched_at": now_iso,
    })
    if res.final_url and res.final_url != url:
        entry["final_url"] = res.final_url

    diff: Optional[Dict[str, Any]] = None
    if not has_base:
        entry["change"] = "baseline"
        yaml_sha = src.get("content_sha256")
        if yaml_sha:
            entry["yaml_content_sha256"] = "match" if yaml_sha == raw else "differs"
            if yaml_sha != raw:
                entry["raw_differs_from_yaml"] = True
    elif prev.get("normalizer_version") != NORMALIZER_VERSION and prev.get("text_sha256") is not None:
        entry["change"] = "none" if prev["raw_sha256"] == raw else "normalizer_rebaseline"
    elif text_sha is not None and prev.get("text_sha256") is not None:
        if text_sha == prev["text_sha256"]:
            entry["change"] = "none" if prev["raw_sha256"] == raw else "markup_only"
        else:
            entry["change"] = "text_changed"
            diff = diff_tokens(prev.get("tokens") or {}, tokens or {})
            entry["diff"] = diff
    else:  # no readable text on one side: raw bytes are all there is
        if prev["raw_sha256"] == raw:
            entry["change"] = "none"
        else:
            entry["change"] = "raw_changed"
            entry["diff"] = diff = {}
    return entry, diff


# ------------------------------------------------------------------ version check


@dataclass
class VersionCheck:
    row: Dict[str, Any]  # the scholarship_version_checks insert
    finding: Optional[Dict[str, Any]]  # None when there is nothing new to report


def check_version(
    version: Dict[str, Any],
    prev: Optional[Dict[str, Any]],
    fetcher: PoliteFetcher,
    today: dt.date,
    now: dt.datetime,
    mode: str = "full",
) -> VersionCheck:
    now_iso = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    prev_by_id = _prev_sources(prev)
    entries: List[Dict[str, Any]] = []
    changed: List[Dict[str, Any]] = []
    for src in version["record"]["sources"]:
        entry, _ = check_source(src, prev_by_id.get(src["source_id"]), fetcher, now_iso)
        entries.append(entry)
        if entry["change"] in ("text_changed", "raw_changed"):
            changed.append(entry)

    signals = stale_signals(version, entries, today)
    prev_detail = (prev or {}).get("detail") or {}
    prev_signal_keys = {(s.get("code"), s.get("source_id")) for s in prev_detail.get("stale_signals", [])}
    new_signals = [s for s in signals if (s["code"], s["source_id"]) not in prev_signal_keys]
    unreachable = [e for e in entries if e["status"] == "unreachable"]
    carried = bool(prev and prev.get("needs_review"))
    prev_review = prev_detail.get("review") or {}
    origin = prev_review.get("origin_result") or (prev or {}).get("result")
    if origin not in ("changed", "stale_signal"):
        origin = "changed"

    if changed:
        result = "changed"
    elif signals:
        result = "stale_signal"
    elif carried:
        result = origin
    elif unreachable:
        result = "unreachable"
    else:
        result = "unchanged"
    needs_review = bool(changed or signals or carried)

    detail: Dict[str, Any] = {
        "monitor": {"normalizer_version": NORMALIZER_VERSION, "mode": mode, "checked_on": today.isoformat()},
        "baseline_only": prev is None and not unreachable and all(e["change"] == "baseline" for e in entries),
        "sources": entries,
        "stale_signals": signals,
    }
    if prev is None:
        detail["first_run"] = True
    if any(e["change"] == "normalizer_rebaseline" for e in entries):
        detail["normalizer_rebaseline"] = True
    if needs_review:
        keep = carried and bool(prev_review) and not changed and not new_signals
        if keep:
            review = dict(prev_review)
        else:
            review = {"origin_result": "changed" if changed else "stale_signal", "origin_checked_at": now_iso}
        reasons = set()
        if changed:
            reasons.add("text_changed")
        reasons.update(s["code"] for s in signals)
        if keep and not reasons:
            reasons.update(prev_review.get("reasons") or ["carried_from_previous_check"])
        review["reasons"] = sorted(reasons)
        detail["review"] = review
        detail["needs_review_carried"] = bool(carried and not changed and not new_signals)

    row = {
        "program_id": version["program_id"],
        "version_id": version["version_id"],
        "checked_at": now_iso,
        "result": result,
        "needs_review": needs_review,
        "detail": detail,
    }
    finding = None
    if changed or new_signals:
        finding = {
            "program_id": version["program_id"],
            "version_id": version["version_id"],
            "kind": "changed" if changed else "stale_signal",
            "changed_sources": [
                {
                    "source_id": e["source_id"],
                    "url": e["url"],
                    "archive_save_url": ARCHIVE_SAVE + e["url"],
                    "diff": e.get("diff") or {},
                }
                for e in changed
            ],
            "stale_signals": new_signals,
        }
    return VersionCheck(row, finding)


# ------------------------------------------------------------------------- run


@dataclass
class RunResult:
    rows: List[Dict[str, Any]] = field(default_factory=list)
    findings: List[Dict[str, Any]] = field(default_factory=list)
    skipped: List[str] = field(default_factory=list)  # in the YAML, not loaded yet
    baseline_source: str = "none"


def run(
    versions: List[Dict[str, Any]],
    store: Optional[CheckStore],
    fetcher: PoliteFetcher,
    today: dt.date,
    now: dt.datetime,
    mode: str = "full",
) -> RunResult:
    out = RunResult(baseline_source="database" if store is not None else "none")
    # A check row has a foreign key to the loaded version; a version merged but not
    # yet loaded is not served, so it is skipped rather than failing the whole insert.
    known = store.known_versions() if store is not None else None
    for v in versions:
        if known is not None and (v["program_id"], v["version_id"]) not in known:
            out.skipped.append(f"{v['program_id']}/{v['version_id']}")
            continue
        prev = store.latest(v["program_id"], v["version_id"]) if store is not None else None
        vc = check_version(v, prev, fetcher, today, now, mode)
        out.rows.append(vc.row)
        if vc.finding:
            out.findings.append(vc.finding)
    return out


# ---------------------------------------------------------------------- output


def _fmt_diff(diff: Dict[str, Any]) -> List[str]:
    if not diff:
        return ["- Text changed; no amount, date, year or selection word changed."]
    lines = []
    for key in TOKEN_KEYS:
        d = diff.get(key)
        if not d:
            continue
        label = key.replace("_", " ")
        if d["added"]:
            lines.append(f"- {label} added: " + ", ".join(f"`{x}`" for x in d["added"]))
        if d["removed"]:
            lines.append(f"- {label} removed: " + ", ".join(f"`{x}`" for x in d["removed"]))
    return lines


def findings_markdown(findings: List[Dict[str, Any]], today: dt.date) -> str:
    if not findings:
        return f"No scholarship changes or stale signals on {today.isoformat()}.\n"
    parts = [
        f"Scholarship monitor, {today.isoformat()}: {len(findings)} version(s) need review. "
        "Nothing was published or edited; each is marked `needs_review` in `scholarship_version_checks`. "
        "Clear a flag only after re-verifying (docs/runbooks/scholarships-annual-review.md).\n"
    ]
    for f in findings:
        parts.append(f"### {f['program_id']} / {f['version_id']} ({f['kind']})\n")
        for s in f["changed_sources"]:
            parts.append(f"**{s['source_id']}** {s['url']}\n")
            parts.extend(_fmt_diff(s["diff"]))
            parts.append(f"- Save a snapshot: {s['archive_save_url']}\n")
        for sig in f["stale_signals"]:
            parts.append(f"- stale signal `{sig['code']}`: {sig['message']}")
        parts.append("")
    text = "\n".join(parts)
    if len(text) > MAX_FINDINGS_CHARS:
        text = text[:MAX_FINDINGS_CHARS].rsplit("\n", 1)[0] + "\n\n_Truncated; see the findings JSON artifact._\n"
    return text


def summary_lines(result: RunResult) -> List[str]:
    lines = []
    for r in result.rows:
        srcs = r["detail"]["sources"]
        reasons = [f"{s['source_id']}:{s['change']}" if s["status"] != "unreachable" else f"{s['source_id']}:unreachable ({s.get('reason')})" for s in srcs]
        lines.append(
            f"{r['program_id']}/{r['version_id']}  {r['result']}  needs_review={str(r['needs_review']).lower()}  "
            + "; ".join(reasons)
        )
    return lines


def load_cache(path: Optional[Path]) -> Dict[str, Dict[str, Any]]:
    if path is None:
        return {}
    try:
        data = json.loads(path.read_text())
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def save_cache(path: Path, cache: Dict[str, Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + f".{os.getpid()}.tmp")
    tmp.write_text(json.dumps(cache, indent=2, sort_keys=True))
    os.replace(tmp, path)


def main(
    argv: Optional[List[str]] = None,
    *,
    store: Optional[CheckStore] = None,
    fetcher: Optional[PoliteFetcher] = None,
    now: Optional[dt.datetime] = None,
) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("programs_dir", nargs="?", type=Path, default=validate.REPO_ROOT / "data" / "scholarships" / "programs")
    ap.add_argument("--apply", action="store_true", help="write check rows and refresh the directory cache (default: dry run)")
    ap.add_argument("--mode", choices=("full", "milestones"), default="full")
    ap.add_argument("--only", action="append", metavar="PROGRAM_ID")
    ap.add_argument("--limit", type=int)
    ap.add_argument("--cache-file", type=Path, help="conditional-GET cache; saved only after a successful --apply")
    ap.add_argument("--today", type=dt.date.fromisoformat, help="override today (tests, backfills)")
    ap.add_argument("--min-spacing", type=float, default=2.0)
    ap.add_argument("--findings-json", type=Path)
    ap.add_argument("--findings-md", type=Path)
    ap.add_argument("--show-rows", action="store_true", help="print the full rows that would be written")
    args = ap.parse_args(argv)

    now = now or dt.datetime.now(dt.timezone.utc)
    today = args.today or now.date()
    ds, issues = _load(args.programs_dir)
    if ds is None:
        for i in issues:
            print(i, file=sys.stderr)
        return 1
    versions = select_versions(ds, args.mode, today, args.only, args.limit)

    if store is None:
        store = SupabaseCheckStore.from_env(required=args.apply)
    cache = load_cache(args.cache_file)
    if fetcher is None:
        fetcher = PoliteFetcher(PRODUCT_TOKEN, cache=cache, min_spacing=args.min_spacing)
    else:
        cache = fetcher.cache  # type: ignore[assignment]

    print(f"{'APPLY' if args.apply else 'DRY RUN'}: mode={args.mode} versions={len(versions)} today={today}")
    result = run(versions, store, fetcher, today, now, args.mode)
    if result.baseline_source == "none":
        print("no database credentials: every source is treated as a first run (baseline only)")
    for line in summary_lines(result):
        print(line)
    for name in result.skipped:
        print(f"skipped (not loaded): {name}")
    if args.show_rows:
        print(json.dumps(result.rows, indent=2, sort_keys=True))
    md = findings_markdown(result.findings, today)
    if args.findings_json:
        args.findings_json.parent.mkdir(parents=True, exist_ok=True)
        args.findings_json.write_text(json.dumps(result.findings, indent=2, sort_keys=True))
    if args.findings_md:
        args.findings_md.parent.mkdir(parents=True, exist_ok=True)
        args.findings_md.write_text(md)
    print(f"findings: {len(result.findings)}")
    if result.findings and not args.findings_md:
        print(md)

    if not args.apply:
        print("dry run: nothing written (no rows, no cache refresh, no cache file)")
        return 0

    assert store is not None
    store.insert(result.rows)
    if args.cache_file:
        save_cache(args.cache_file, cache)  # only after the rows are in
    try:
        store.refresh()
    except Exception as exc:  # rows are written; the public view is stale until the next refresh
        print(f"rows written but refresh_scholarship_directory_cache() failed: {exc}", file=sys.stderr)
        return 1
    print(f"wrote {len(result.rows)} check rows and refreshed the directory cache")
    return 0


def _load(programs_dir: Path):
    issues = validate.validate_tree(programs_dir)
    if issues:
        return None, issues
    docs = {
        str(p): validate.load_yaml_text(p.read_text(encoding="utf-8"))
        for p in sorted(programs_dir.glob("*/*.yaml"))
    }
    return model.build_dataset(docs, root=REPO_ROOT), []


if __name__ == "__main__":
    raise SystemExit(main())
