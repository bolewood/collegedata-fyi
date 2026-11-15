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
    python tools/scholarships/monitor.py --findings-json findings.json --findings-md findings.md

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
* Only a detected change in terms sets `needs_review`: the normalized main text
  changed AND the change touches an amount, date, year or selection word (a
  token diff). Any other text change (banners, wording that moves no token) is
  recorded as `text_changed_no_terms`, moves the baseline and does not flag.
  Stale signals, unreachable sources, suspect pages, unreadable text and raw-only
  PDF changes are reported in the issue and never change public status.
* `needs_review` set by a change is carried forward from the previous row until a
  person clears it (runbook), so an unchanged re-check never silently restores
  the old status.
* Unreachable (robots block, robots unreachable, login/CAPTCHA, any HTTP error
  including 404, a suspect page) never sets `needs_review`; a 404 never implies
  the program ended. The previous baseline is carried through.
* Result precedence for one version: changed > stale_signal > unreachable >
  unchanged. Every signal is listed in `detail`.
* Browser fallback (`--browser-fallback`, see polite_fetch.BROWSER_FALLBACK_RULES):
  a page the plain client is refused (403/404/406) is read once through headless
  Chromium, which loads only that document and runs no other script, so it does not
  get past bot challenges; robots Disallow, logins and CAPTCHAs are never bypassed.
  A source whose baseline is `http` asks for plain HTTP first (`prefer_http`), so its
  transport does not depend on which other URL on the host needed the browser. Each
  source's `detail` entry records `transport` ("http" or "browser"; a row with no
  `transport` is "http"). A rendered DOM is not byte-stable, so for a browser fetch
  `raw_sha256` drives nothing: only the normalized text hash and the tokens are
  compared. If the previous baseline used the other transport: equal text is `none`;
  no token difference re-baselines (`transport_rebaseline`); a token difference
  keeps the previous baseline (`transport_flip_diff`) and is reported as information,
  never as `needs_review` (a rendered DOM can differ in tokens a script injects).
* Each distinct URL is fetched once per run and compared with every baseline that
  cites it. Conditional-GET validators are stored in each source's own `detail`
  entry (never in a shared URL cache), so a baseline only ever sends its own
  validators. A host that throttles (429, retries exhausted) is skipped for the
  rest of the run. Each version's row is inserted as soon as it is checked.

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
from urllib.parse import urlsplit
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import model  # noqa: E402
import validate  # noqa: E402

REPO_ROOT = validate.REPO_ROOT
sys.path.insert(0, str(REPO_ROOT))
from tools.common.polite_fetch import (  # noqa: E402
    HTTP_ERROR,
    NOT_MODIFIED,
    OK,
    FetchResult,
    PoliteFetcher,
)

NORMALIZER_VERSION = 3  # 3: thresholds token
MIN_TEXT_CHARS = 200  # shorter normalized text is treated as unreadable (JS shell, error page)
PRODUCT_TOKEN = "scholarship-monitor"
SELECTION_WORDS = (
    "not guaranteed", "not automatic", "not required", "non-renewable", "guaranteed", "automatic",
    "competitive", "considered", "required", "deadline", "no longer", "renewable", "semifinalist",
    "finalist", "commended",
)
MILESTONE_MARKS = (30, 7)
MAX_FINDINGS_CHARS = 60_000
ARCHIVE_SAVE = "https://web.archive.org/save/"
TOKEN_KEYS = ("amounts", "dates", "years", "selection_words", "thresholds")

# ------------------------------------------------------------------ normalizer

# aside is kept: deadline callouts often live in a sidebar box.
_DROP_TAGS = ("script", "style", "noscript", "template", "svg", "iframe", "nav", "footer", "header", "form")
_DROP_ROLES = {"banner", "navigation", "contentinfo"}
_CHURN_CLASS_RE = re.compile(r"news|related|alert|banner|carousel|breadcrumb", re.I)
_CHURN_MAX_CHARS = 1500  # a teaser block is short; a long block with such a class is content
_SUSPECT_RE = re.compile(
    r"captcha|cf-chl|cf-turnstile|just a moment|attention required|are you a robot|verify you are human|"
    r"page not found|404 not found|not be found|under maintenance|down for maintenance|"
    r"temporarily unavailable|access denied|service unavailable",
)
_ZERO_WIDTH = re.compile("[​‌‍⁠﻿]")
_WS = re.compile(r"\s+")


def _clean(text: str) -> str:
    text = unicodedata.normalize("NFKC", text)
    text = _ZERO_WIDTH.sub("", text)
    return _WS.sub(" ", text).strip().lower()


_UPDATED_RE = None  # compiled after the month pattern below


def _strip_updated(text: str) -> str:
    return _WS.sub(" ", _UPDATED_RE.sub(" ", text)).strip()


def parser_fingerprint() -> str:
    """Versions of the parsers behind the normalizer. A change re-baselines."""
    try:
        import bs4

        b = bs4.__version__
    except ImportError:  # pragma: no cover
        b = "none"
    try:
        import pypdf

        p = pypdf.__version__
    except ImportError:  # pragma: no cover
        p = "none"
    return f"bs4={b};pypdf={p}"


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

    HTML is parsed with html.parser. Comments and script, style, noscript, template,
    svg, iframe, nav, footer, header, form elements, [role=banner|navigation|
    contentinfo] and short blocks (<= 1500 chars) whose class or id matches
    news|related|alert|banner|carousel|breadcrumb are dropped; aside is kept. The
    root is the first <main> or [role=main], else the <article> with the most text,
    else <body>. Its text is joined with single spaces, NFKC folded, zero-width
    characters removed, lower-cased, whitespace-collapsed, and "last|page
    updated|modified|reviewed <date>" phrases are removed. text_sha256 is SHA-256 of
    the UTF-8 text. PDFs go through pypdf; an unreadable PDF has text None (raw
    bytes only). Bump NORMALIZER_VERSION when this rule changes; a pypdf or bs4
    release change re-baselines through parser_fingerprint instead of flagging.
    """
    ctype = (content_type or "").lower()
    if body[:5] == b"%PDF-" or "pdf" in ctype:
        return _normalize_pdf(body)
    raw = _decode(body, content_type)
    if "html" not in ctype and not re.search(r"<\s*(html|body|div|p|h1|main)\b", raw[:4096], re.I):
        return Page(_strip_updated(_clean(raw)))
    from bs4 import BeautifulSoup, Comment

    soup = BeautifulSoup(raw, "html.parser")
    for c in soup.find_all(string=lambda s: isinstance(s, Comment)):
        c.extract()
    for tag in soup.find_all(_DROP_TAGS):
        tag.decompose()
    for el in soup.find_all(True):
        if getattr(el, "decomposed", False) or el.name in ("html", "body", "main", "article"):
            continue
        if el.find("main") or el.find(attrs={"role": "main"}):
            continue  # a wrapper around the content
        marker = " ".join(el.get("class") or []) + " " + (el.get("id") or "")
        if (el.get("role") in _DROP_ROLES) or (
            _CHURN_CLASS_RE.search(marker) and len(el.get_text(" ")) <= _CHURN_MAX_CHARS
        ):
            el.decompose()
    root = soup.find("main") or soup.find(attrs={"role": "main"})
    if root is None:
        articles = soup.find_all("article")
        root = max(articles, key=lambda a: len(a.get_text(" ")), default=None)
    root = root or soup.body or soup
    headings = [h for h in (_clean(t.get_text(" ")) for t in root.find_all(["h1", "h2", "h3"])) if h]
    return Page(_strip_updated(_clean(root.get_text(" "))), headings)


def _normalize_pdf(body: bytes) -> Page:
    try:
        import io

        from pypdf import PdfReader

        reader = PdfReader(io.BytesIO(body))
        text = " ".join((p.extract_text() or "") for p in reader.pages)
    except Exception:
        return Page(None)
    cleaned = _strip_updated(_clean(text))
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
_UPDATED_RE = re.compile(
    rf"\b(?:last|page)\s+(?:updated|modified|reviewed|revised)\b[:\s]*(?:on\s+)?"
    rf"(?:(?:{_MON_NAMES})\.?\s+\d{{1,2}}(?:st|nd|rd|th)?(?:,?\s+20\d\d)?|\d{{1,2}}/\d{{1,2}}/\d{{2,4}}|20\d\d-\d\d-\d\d)"
)
_AMOUNT_RE = re.compile(r"\$\s?(\d{1,3}(?:,\d{3})+|\d+)(?:\.(\d{1,2}))?(?:\s?(thousand|million|k|m)\b)?")
_DATE_NAMED_RE = re.compile(
    rf"\b({_MON_NAMES})\.?\s+(\d{{1,2}})(?!\d)(?:st|nd|rd|th)?(?:,?\s+(20\d\d)\b)?"
)
_DATE_MONTH_YEAR_RE = re.compile(rf"\b({_MON_NAMES})\.?,?\s+(20\d\d)\b")
_DATE_SLASH_RE = re.compile(r"\b(\d{1,2})/(\d{1,2})/(\d{4}|\d{2})\b")
_DATE_ISO_RE = re.compile(r"\b(20\d\d)-(\d\d)-(\d\d)\b")
_YEAR_RE = re.compile(r"\b(20[1-4]\d)\b")
_SEL_RE = re.compile(
    r"\b(not guaranteed|not automatic(?:ally)?|not required|non-renewable|guaranteed|automatic(?:ally)?|"
    r"competitive|considered|required|deadline|no longer|renewable|semifinalist|finalist|commended)\b"
)
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
    words = {w.replace("automatically", "automatic") for w in _SEL_RE.findall(text)}
    return {
        "thresholds": threshold_tokens(stripped),
        "amounts": sorted(amounts, key=lambda a: (float(a[1:]), a)),
        "dates": sorted(dates),
        "years": years,
        "selection_words": sorted(words),
    }


_THRESHOLD_WORDS = {
    "gpa": "gpa", "grade": "gpa", "sat": "sat", "act": "act", "credit": "credit", "credits": "credit",
    "hour": "hours", "hours": "hours", "semester": "semester", "semesters": "semester",
    "recipients": "recipients", "scholars": "scholars", "awards": "awards",
}
_THRESHOLD_WINDOW = 4
_NUM_RE = re.compile(r"^\d+(?:\.\d+)?$")


def threshold_tokens(text: str) -> List[str]:
    """Numbers within four words of GPA / grade point, SAT, ACT, credit(s), hour(s),
    semester(s), recipients, scholars or awards, as "keyword number" ("gpa 3.2").
    Amounts, dates and years are removed first; a phone number or a visitor count
    far from those words is not a threshold."""
    cleaned = _DATE_ISO_RE.sub(" ", _DATE_SLASH_RE.sub(" ", _DATE_MONTH_YEAR_RE.sub(" ", _DATE_NAMED_RE.sub(" ", text))))
    cleaned = _YEAR_RE.sub(" ", cleaned)
    words = [w.strip(".,;:()[]\"'!?") for w in cleaned.split()]
    kws = [(_THRESHOLD_WORDS.get(w)) for w in words]
    out = set()
    for i, w in enumerate(words):
        num = w.replace(",", "")
        if not _NUM_RE.match(num):
            continue
        lo, hi = max(0, i - _THRESHOLD_WINDOW), min(len(words), i + _THRESHOLD_WINDOW + 1)
        near = [(abs(j - i), kws[j]) for j in range(lo, hi) if kws[j] and j != i]
        if near:
            out.add(f"{min(near)[1]} {num}")
    return sorted(out)


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


def milestone_due(row: Dict[str, Any], today: dt.date, last_checked: Optional[dt.date] = None) -> bool:
    """A required or priority dated milestone is due a recheck when it is 0-30 days
    away and the version has not been checked since its 30-day mark (or, within 7
    days, its 7-day mark). The daily run normally hits the marks exactly; a missed
    or failed run is caught up the next day instead of being lost."""
    for m in _dated_milestones(row):
        if m.get("requirement") not in ("required", "priority"):
            continue
        try:
            due = dt.date.fromisoformat(m["date"])
        except ValueError:
            continue
        days = (due - today).days
        if not 0 <= days <= MILESTONE_MARKS[0]:
            continue
        mark = MILESTONE_MARKS[1] if days <= MILESTONE_MARKS[1] else MILESTONE_MARKS[0]
        if last_checked is None or last_checked < due - dt.timedelta(days=mark):
            return True
    return False


def select_versions(
    ds: model.Dataset,
    mode: str,
    today: dt.date,
    only: Optional[List[str]] = None,
    limit: Optional[int] = None,
    store: Optional["CheckStore"] = None,
) -> List[Dict[str, Any]]:
    rows = model.select_published(ds)
    if only:
        rows = [r for r in rows if r["program_id"] in only]
    if mode == "milestones":
        picked = []
        for r in rows:
            last = store.latest(r["program_id"], r["version_id"]) if store is not None else None
            checked = dt.date.fromisoformat(last["checked_at"][:10]) if last and last.get("checked_at") else None
            if milestone_due(r, today, checked):
                picked.append(r)
        rows = picked
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

_CARRY = (
    "raw_sha256", "text_sha256", "normalizer_version", "parsers", "tokens", "facts",
    "text_len", "text_unreadable", "baseline_fetched_at", "validators", "transport",
)
_SHRINK_RATIO = 0.3


def _prev_sources(prev: Optional[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    detail = (prev or {}).get("detail") or {}
    return {s["source_id"]: s for s in detail.get("sources", []) if isinstance(s, dict) and s.get("source_id")}


def _sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def _token_count(tokens: Optional[Dict[str, List[Any]]]) -> int:
    return sum(len(v) for v in (tokens or {}).values())


def _tokens_kept(old: Optional[Dict[str, List[Any]]], new: Optional[Dict[str, List[Any]]]) -> float:
    total = _token_count(old)
    kept = sum(len(set(v) & set((new or {}).get(k) or [])) for k, v in (old or {}).items())
    return kept / total if total else 1.0


class RunFetcher:
    """Fetching for one run.

    * A URL cited by several (version, source) pairs is fetched once, without
      validators, and the body is compared with every baseline. A 304 can only be
      used by the baseline whose validators were sent.
    * Validators come from the source's own previous entry, never from a shared
      URL cache, so one baseline cannot swallow another's change.
    * A host that throttles (429, retries exhausted, Retry-After over the cap) or
      keeps failing is skipped for the rest of the run.
    """

    def __init__(self, fetcher: PoliteFetcher, shared_urls: Optional[set] = None):
        self.fetcher = fetcher
        self.shared = shared_urls or set()
        self.memo: Dict[str, FetchResult] = {}
        self.dead_hosts: Dict[str, str] = {}

    def fetch(self, url: str, validators: Optional[Dict[str, Any]] = None, prefer_http: bool = False) -> FetchResult:
        host = (urlsplit(url).hostname or "").lower()
        if host in self.dead_hosts:
            return FetchResult(HTTP_ERROR, url, reason=f"host skipped for the rest of this run: {self.dead_hosts[host]}")
        if url in self.shared:
            if url in self.memo:
                return self.memo[url]
            validators = None
        cache = self.fetcher.cache
        cache.pop(url, None)
        if validators:
            cache[url] = dict(validators)
        res = self.fetcher.fetch(url, prefer_http=prefer_http)
        cache.pop(url, None)
        if url in self.shared:
            self.memo[url] = res
        if res.status == HTTP_ERROR and (
            res.http_status == 429
            or any(k in res.reason for k in ("retries exhausted", "exceeds cap", "network error"))
        ):
            self.dead_hosts[host] = res.reason
        return res


def _entry_base(src: Dict[str, Any]) -> Dict[str, Any]:
    return {"source_id": src["source_id"], "url": src["url"], "authority": src.get("authority")}


def check_source(
    src: Dict[str, Any], prev: Optional[Dict[str, Any]], fetcher: Any, now_iso: str
) -> Tuple[Dict[str, Any], Optional[Dict[str, Any]]]:
    """Fetch one source and compare it to its previous entry.

    Returns (entry for detail.sources, token diff or None). `change` is one of
    baseline, none, markup_only, text_changed (flags), text_changed_no_terms,
    raw_changed, normalizer_rebaseline, transport_rebaseline. Only text_changed
    sets needs_review.
    """
    if not isinstance(fetcher, RunFetcher):
        fetcher = RunFetcher(fetcher)
    url = src["url"]
    has_base = bool(prev and prev.get("raw_sha256"))
    entry = _entry_base(src)

    def carry() -> None:
        for k in _CARRY:
            if prev and k in prev:
                entry[k] = prev[k]

    def unreachable(reason: str, res: FetchResult) -> Tuple[Dict[str, Any], None]:
        carry()
        entry.update({"fetched": False, "status": "unreachable", "reason": reason, "change": "none"})
        return entry, None

    prev_transport = (prev or {}).get("transport") or "http"  # rows written before the fallback existed are http
    res = fetcher.fetch(url, (prev or {}).get("validators") if has_base else None, prefer_http=has_base and prev_transport == "http")
    entry["fetch_status"] = res.status
    entry["http_status"] = res.http_status
    entry["attempt_transport"] = res.transport
    browser = res.transport == "browser"
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
        return unreachable(reason, res)

    body = res.body or b""
    page = normalize_page(body, res.headers.get("content-type", ""))
    text = page.text
    text_len = len(text) if text is not None else 0
    tokens = extract_tokens(text) if text is not None else None
    unreadable = text is None or text_len < MIN_TEXT_CHARS or _token_count(tokens) == 0

    # A 200 that is not the page: challenge, maintenance, soft 404, or a page that
    # lost most of its baseline content. Never baseline it, never flag it.
    if text is not None and text_len < 1500 and _SUSPECT_RE.search(text):
        return unreachable("suspect page: error, maintenance or challenge text served with HTTP 200", res)
    if has_base and not prev.get("text_unreadable") and prev.get("text_sha256"):
        shrunk = prev.get("text_len") and text_len < _SHRINK_RATIO * prev["text_len"]
        lost = _token_count(prev.get("tokens")) >= 4 and _tokens_kept(prev.get("tokens"), tokens) < _SHRINK_RATIO
        if unreadable or shrunk or lost:
            return unreachable("suspect page: most of the baseline content is missing", res)

    raw = _sha(body)
    facts = {} if unreadable else {
        "years": (tokens or {}).get("years", []),
        "heading_entry_years": heading_entry_years(page.headings),
        "deadline_years": deadline_years(text or ""),
    }
    entry.update({
        "fetched": True,
        "status": "ok",
        "raw_sha256": raw,
        "text_sha256": None if unreadable else _sha(text.encode("utf-8")),
        "normalizer_version": NORMALIZER_VERSION,
        "transport": res.transport,
        "parsers": parser_fingerprint(),
        "tokens": None if unreadable else tokens,
        "facts": facts,
        "text_len": text_len,
        "baseline_fetched_at": now_iso,
    })
    if unreadable:
        entry["text_unreadable"] = True
    if res.etag or res.last_modified:
        entry["validators"] = {"etag": res.etag, "last_modified": res.last_modified, "final_url": res.final_url or url}
    if res.final_url and res.final_url != url:
        entry["final_url"] = res.final_url

    diff: Optional[Dict[str, Any]] = None
    if not has_base:
        entry["change"] = "baseline"
        yaml_sha = src.get("content_sha256")
        if yaml_sha and browser:
            entry["yaml_content_sha256"] = "not_comparable_browser"  # a rendered DOM never matches the file's bytes
        elif yaml_sha:
            entry["yaml_content_sha256"] = "match" if yaml_sha == raw else "differs"
            if yaml_sha != raw:
                entry["raw_differs_from_yaml"] = True
    elif prev_transport != res.transport:
        # The two transports' bytes are not comparable; compare text and tokens instead.
        if entry["text_sha256"] is not None and entry["text_sha256"] == prev.get("text_sha256"):
            entry["change"] = "none"
        elif entry["text_sha256"] is None or prev.get("text_sha256") is None:
            entry["change"] = "transport_rebaseline"
        else:
            diff = diff_tokens(prev.get("tokens") or {}, tokens or {})
            if not diff:
                entry["change"] = "transport_rebaseline"
            else:
                # A flip that moved a token: keep the previous baseline, never flag (a rendered DOM
                # can differ in tokens), and report the diff so a person sees it.
                for k in _CARRY:
                    if k in prev:
                        entry[k] = prev[k]
                    else:
                        entry.pop(k, None)
                entry.pop("text_unreadable", None)
                if prev.get("text_unreadable"):
                    entry["text_unreadable"] = True
                entry["change"] = "transport_flip_diff"
                entry["diff"] = diff
                entry["flip_transport"] = res.transport
    elif (
        prev.get("normalizer_version") != NORMALIZER_VERSION or prev.get("parsers") != entry["parsers"]
    ) and prev.get("text_sha256") is not None:
        entry["change"] = "none" if (prev["raw_sha256"] == raw and not browser) else "normalizer_rebaseline"
    elif entry["text_sha256"] is not None and prev.get("text_sha256") is not None:
        if entry["text_sha256"] == prev["text_sha256"]:
            entry["change"] = "none" if (browser or prev["raw_sha256"] == raw) else "markup_only"
        else:
            diff = diff_tokens(prev.get("tokens") or {}, tokens or {})
            if diff:
                entry["change"] = "text_changed"
                entry["diff"] = diff
            else:  # wording moved, no amount/date/year/selection word did
                entry["change"] = "text_changed_no_terms"
    else:  # no usable text on one side: report a raw-bytes change, never flag it
        entry["change"] = "none" if (browser or prev["raw_sha256"] == raw) else "raw_changed"
    return entry, diff


# ------------------------------------------------------------------ version check


@dataclass
class VersionCheck:
    row: Dict[str, Any]  # the scholarship_version_checks insert
    finding: Optional[Dict[str, Any]]  # None when there is nothing to report


def _source_ref(e: Dict[str, Any], **extra: Any) -> Dict[str, Any]:
    out = {"source_id": e["source_id"], "url": e["url"], "archive_save_url": ARCHIVE_SAVE + e["url"]}
    out.update(extra)
    return out


def check_version(
    version: Dict[str, Any],
    prev: Optional[Dict[str, Any]],
    fetcher: Any,
    today: dt.date,
    now: dt.datetime,
    mode: str = "full",
) -> VersionCheck:
    now_iso = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    prev_by_id = _prev_sources(prev)
    entries: List[Dict[str, Any]] = []
    for src in version["record"]["sources"]:
        entry, _ = check_source(src, prev_by_id.get(src["source_id"]), fetcher, now_iso)
        entries.append(entry)
    changed = [e for e in entries if e["change"] == "text_changed"]

    signals = stale_signals(version, entries, today)
    prev_detail = (prev or {}).get("detail") or {}
    prev_signal_keys = {(s.get("code"), s.get("source_id")) for s in prev_detail.get("stale_signals", [])}
    new_signals = [s for s in signals if (s["code"], s["source_id"]) not in prev_signal_keys]
    unreachable = [e for e in entries if e["status"] == "unreachable"]
    new_unreachable = [e for e in unreachable if (prev_by_id.get(e["source_id"]) or {}).get("status") != "unreachable"]
    unreadable_new = [e for e in entries if e.get("text_unreadable") and not (prev_by_id.get(e["source_id"]) or {}).get("text_unreadable")]
    raw_changed = [e for e in entries if e["change"] == "raw_changed"]
    flip_diffs = [e for e in entries if e["change"] == "transport_flip_diff"]

    # Only a detected change in terms flags a version, and the flag is carried until a person clears it.
    prev_review = prev_detail.get("review") or {}
    carried = bool(
        prev and prev.get("needs_review") and (prev_review.get("origin_result") or prev.get("result")) == "changed"
    )
    needs_review = bool(changed) or carried

    if needs_review:
        result = "changed"
    elif signals:
        result = "stale_signal"
    elif unreachable:
        result = "unreachable"
    else:
        result = "unchanged"

    detail: Dict[str, Any] = {
        "monitor": {
            "normalizer_version": NORMALIZER_VERSION,
            "parsers": parser_fingerprint(),
            "mode": mode,
            "checked_on": today.isoformat(),
        },
        "baseline_only": prev is None and not unreachable and all(e["change"] == "baseline" for e in entries),
        "sources": entries,
        "stale_signals": signals,
    }
    if prev is None:
        detail["first_run"] = True
    if any(e["change"] == "normalizer_rebaseline" for e in entries):
        detail["normalizer_rebaseline"] = True
    if any(e["change"] == "transport_rebaseline" for e in entries):
        detail["transport_rebaseline"] = True
    if needs_review:
        if changed or not prev_review:
            review = {"origin_result": "changed", "origin_checked_at": now_iso}
        else:
            review = dict(prev_review)
        review["reasons"] = ["terms_changed"] if changed else (prev_review.get("reasons") or ["carried_from_previous_check"])
        detail["review"] = review
        detail["needs_review_carried"] = not changed

    row = {
        "program_id": version["program_id"],
        "version_id": version["version_id"],
        "checked_at": now_iso,
        "result": result,
        "needs_review": needs_review,
        "detail": detail,
    }
    finding = None
    if needs_review or new_signals or new_unreachable or unreadable_new or raw_changed or flip_diffs:
        finding = {
            "program_id": version["program_id"],
            "version_id": version["version_id"],
            "kind": "changed" if needs_review else "info",
            "new": bool(changed),  # False: still flagged from an earlier run
            "changed_sources": [_source_ref(e, diff=e.get("diff") or {}) for e in changed],
            "stale_signals": new_signals,
            "unreachable_sources": [_source_ref(e, reason=e.get("reason")) for e in new_unreachable],
            "unreadable_sources": [_source_ref(e) for e in unreadable_new],
            "raw_changed_sources": [_source_ref(e) for e in raw_changed],
            "transport_flip_sources": [_source_ref(e, diff=e.get("diff") or {}, transport=e.get("flip_transport")) for e in flip_diffs],
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
    sink: Optional[Callable[[Dict[str, Any]], None]] = None,
    out: Optional[RunResult] = None,
) -> RunResult:
    """Check every version. `sink` receives each row as soon as it is built (the
    apply path inserts it there); `out` lets the caller keep partial results if a
    later version raises."""
    out = out if out is not None else RunResult()
    out.baseline_source = "database" if store is not None else "none"
    # A check row has a foreign key to the loaded version; a version merged but not
    # yet loaded is not served, so it is skipped rather than failing the insert.
    known = store.known_versions() if store is not None else None
    counts: Dict[str, int] = {}
    for v in versions:
        for src in v["record"]["sources"]:
            counts[src["url"]] = counts.get(src["url"], 0) + 1
    rf = RunFetcher(fetcher, {u for u, n in counts.items() if n > 1})
    for v in versions:
        if known is not None and (v["program_id"], v["version_id"]) not in known:
            out.skipped.append(f"{v['program_id']}/{v['version_id']}")
            continue
        prev = store.latest(v["program_id"], v["version_id"]) if store is not None else None
        vc = check_version(v, prev, rf, today, now, mode)
        out.rows.append(vc.row)
        if vc.finding:
            out.findings.append(vc.finding)
        if sink is not None:
            sink(vc.row)
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
        return f"No scholarship changes or notices on {today.isoformat()}.\n"
    flagged = [f for f in findings if f["kind"] == "changed"]
    info = [f for f in findings if f["kind"] != "changed"]
    parts = [
        f"Scholarship monitor, {today.isoformat()}. Nothing was published or edited. "
        "Only a detected change in terms is marked `needs_review` (which changes the public status); "
        "everything else below is for information. Clear a flag only after re-verifying "
        "(docs/runbooks/scholarships-annual-review.md).\n"
    ]
    if flagged:
        parts.append(f"## Needs review ({len(flagged)})\n")
    for f in flagged:
        parts.append(f"### {f['program_id']} / {f['version_id']} ({'new' if f['new'] else 'still flagged'})\n")
        for s in f["changed_sources"]:
            parts.append(f"**{s['source_id']}** {s['url']}\n")
            parts.extend(_fmt_diff(s["diff"]))
            parts.append(f"- Save a snapshot: {s['archive_save_url']}\n")
        parts.extend(_info_lines(f))
        parts.append("")
    if info:
        parts.append(f"## For information ({len(info)})\n")
    for f in info:
        parts.append(f"### {f['program_id']} / {f['version_id']}\n")
        parts.extend(_info_lines(f))
        parts.append("")
    text = "\n".join(parts)
    if len(text) > MAX_FINDINGS_CHARS:
        text = text[:MAX_FINDINGS_CHARS].rsplit("\n", 1)[0] + "\n\n_Truncated; see the findings JSON artifact._\n"
    return text


def _info_lines(f: Dict[str, Any]) -> List[str]:
    lines = []
    for sig in f["stale_signals"]:
        lines.append(f"- stale signal `{sig['code']}`: {sig['message']}")
    for s in f["unreachable_sources"]:
        lines.append(f"- unreachable {s['url']}: {s['reason']} (no status change; {s['archive_save_url']})")
    for s in f["unreadable_sources"]:
        lines.append(f"- {s['url']} has little or no readable text (script-rendered page or scan); needs a manual check")
    for s in f["raw_changed_sources"]:
        lines.append(f"- {s['url']} changed as raw bytes but has no readable text to compare; check by hand ({s['archive_save_url']})")
    for s in f.get("transport_flip_sources", []):
        lines.append(
            f"- {s['url']} was read {'through the browser' if s['transport'] == 'browser' else 'over plain HTTP'} this run, not as before, and its terms differ "
            "from the baseline (kept; not flagged because a rendered page can differ). Check by hand:"
        )
        lines.extend("  " + ln for ln in _fmt_diff(s["diff"]))
    return lines


def summary_lines(result: RunResult) -> List[str]:
    lines = []
    for r in result.rows:
        srcs = r["detail"]["sources"]
        reasons = [
            f"{s['source_id']}:{s['change']}" if s["status"] != "unreachable"
            else f"{s['source_id']}:unreachable ({s.get('reason')})"
            for s in srcs
        ]
        lines.append(
            f"{r['program_id']}/{r['version_id']}  {r['result']}  needs_review={str(r['needs_review']).lower()}  "
            + "; ".join(reasons)
        )
    return lines


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
    ap.add_argument("--today", type=dt.date.fromisoformat, help="override today (tests, backfills)")
    ap.add_argument("--min-spacing", type=float, default=2.0)
    ap.add_argument("--findings-json", type=Path)
    ap.add_argument("--findings-md", type=Path)
    ap.add_argument("--browser-fallback", action="store_true",
                    help="retry pages the plain client is refused (403/404/406) through headless Chromium; "
                         "needs tools/scholarships/monitor-requirements.txt")
    ap.add_argument("--show-rows", action="store_true", help="print the full rows that would be written")
    args = ap.parse_args(argv)

    now = now or dt.datetime.now(dt.timezone.utc)
    today = args.today or now.date()
    ds, issues = _load(args.programs_dir)
    if ds is None:
        for i in issues:
            print(i, file=sys.stderr)
        return 1

    if store is None:
        store = SupabaseCheckStore.from_env(required=args.apply)
    versions = select_versions(ds, args.mode, today, args.only, args.limit, store)
    if fetcher is None:
        browser = None
        if args.browser_fallback:
            from tools.common.browser_transport import BrowserTransport

            browser = BrowserTransport()
        fetcher = PoliteFetcher(PRODUCT_TOKEN, min_spacing=args.min_spacing, browser_fallback=browser)

    print(f"{'APPLY' if args.apply else 'DRY RUN'}: mode={args.mode} versions={len(versions)} today={today}")
    result = RunResult()
    written = 0

    def sink(row: Dict[str, Any]) -> None:
        nonlocal written
        assert store is not None
        store.insert([row])  # one row at a time: a later failure cannot lose earlier results
        written += 1

    refresh_failed = False
    try:
        run(versions, store, fetcher, today, now, args.mode, sink if args.apply else None, result)
    finally:
        fetcher.close()
        # Findings first (the workflow reads them even after a failure), then refresh
        # whatever was written so the public view never lags the stored flags.
        if args.findings_json:
            args.findings_json.parent.mkdir(parents=True, exist_ok=True)
            args.findings_json.write_text(json.dumps(result.findings, indent=2, sort_keys=True))
        if args.findings_md:
            args.findings_md.parent.mkdir(parents=True, exist_ok=True)
            args.findings_md.write_text(findings_markdown(result.findings, today))
        if args.apply and written:
            try:
                store.refresh()
            except Exception as exc:  # rows are written; the public view is stale until the next refresh
                print(f"rows written but refresh_scholarship_directory_cache() failed: {exc}", file=sys.stderr)
                refresh_failed = True

    if result.baseline_source == "none":
        print("no database credentials: every source is treated as a first run (baseline only)")
    for line in summary_lines(result):
        print(line)
    for name in result.skipped:
        print(f"skipped (not loaded): {name}")
    if args.show_rows:
        print(json.dumps(result.rows, indent=2, sort_keys=True))
    print(f"findings: {len(result.findings)}")
    if result.findings and not args.findings_md:
        print(findings_markdown(result.findings, today))

    if not args.apply:
        print("dry run: nothing written (no rows, no cache refresh)")
        return 0
    if refresh_failed:
        return 1
    print(f"wrote {written} check rows and refreshed the directory cache")
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
