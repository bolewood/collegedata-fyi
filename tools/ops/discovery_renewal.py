#!/usr/bin/env python3
"""Current-year renewal: is the archive keeping up with what schools publish?

Definition (docs/postmortems/2026-11-24-stale-discovery-seeds.md, "The
headline number"): of the schools with a live document whose filed year
(`canonical_year`) is the previous CDS year, the share that also have one
whose filed year is the current CDS year. The current CDS year is
`cds_freshness_floor()`. Undated (`unknown`) documents do not count.

The result is compared with a floor read off the posting curve by months
since the CDS year's fall. The same number is computed for the next CDS
year, once the early part of the curve applies.

This script fails loudly. A short page of rows, an empty result, a small
denominator, or a freshness floor that disagrees with the database is an
error and exits nonzero. Being below the floor is not an error: it exits 0
and says so in the outputs, and `renewal_alarm.py` acts on it.
"""

from __future__ import annotations

import argparse
import calendar
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import yaml  # noqa: E402

from tools.finder.stuck_pdf_seeds import is_direct_doc_seed  # noqa: E402

DEFAULT_API = "https://api.collegedata.fyi"
DEFAULT_SCHOOLS_YAML = REPO_ROOT / "tools" / "finder" / "schools.yaml"
SCHOOL_PAGE_URL = "https://www.collegedata.fyi/schools/{school_id}"
PAGE_SIZE = 1000
HTTP_TIMEOUT_SEC = 60
MANIFEST_QUERY = (
    "select=school_id,canonical_year,removed_at,participation_status"
    "&removed_at=is.null&order=document_id.asc"
)

# A previous-year denominator below this means the data is not what we think
# it is (an empty page, a filter that dropped rows), not that few schools renew.
# The 2026-11-24 value was 479 (536 for the two-year check).
MIN_PREV_SCHOOLS = 350

# Posting curve: share of a CDS year's files produced, by months since Sept 1
# of the year the CDS describes (fall Y for the CDS year Y-(Y+1)). From the
# postmortem table "When schools post" (2024-25 files with a production date):
# December 3%, February 18%, April 46%, June 68%, August 81%, November 88% of
# the following year. (0, 0) anchors the early part. Linear in between, flat
# after the last point.
# Issue #460 plans to replace this with a curve measured from our own
# snapshots once a year of snapshots exists.
POSTING_CURVE: tuple[tuple[float, float], ...] = (
    (0.0, 0.0),
    (4.0, 3.0),
    (6.0, 18.0),
    (8.0, 46.0),
    (10.0, 68.0),
    (12.0, 81.0),
    (15.0, 88.0),
)

# The current year's floor is the curve less this many percentage points.
CURRENT_YEAR_MARGIN_PTS = 5.0
# The next year is only tracked once the curve says at least this share exists
# (from the end of February), and its floor is the curve times this factor:
# the early curve is noisy.
NEXT_YEAR_ACTIVE_FROM_PCT = 18.0
NEXT_YEAR_FLOOR_FACTOR = 0.75

# The two-year check (schools with either of the two previous years that have the
# current one) uses the one-year floor less this many more points. Mature values
# as held today: 2021 84%, 2022 85%, 2023 82%, 2024 80%; 2025 now 70% (377 of
# 536). The one-year number alone cannot see a permanent loss: a school that
# misses a year leaves its denominator.
TWO_YEAR_MARGIN_PTS = 8.0

VALID_PARTICIPATION = "published"
YEAR_RE = re.compile(r"^(\d{4})-(\d{2})$")


class RenewalError(RuntimeError):
    """The check could not be trusted. Exit nonzero."""


# ---------------------------------------------------------------- years


def parse_year(value: Any) -> int | None:
    """Start year of a valid CDS year string, else None.

    Valid means `YYYY-YY` where the suffix is the next year's last two
    digits (`1999-00` is valid). `unknown`, `2024-26` and `2024` are not.
    Years are compared by this integer, never as text: `unknown` sorts
    above every real year.
    """
    if not isinstance(value, str):
        return None
    match = YEAR_RE.match(value)
    if not match:
        return None
    start = int(match.group(1))
    if int(match.group(2)) != (start + 1) % 100:
        return None
    return start


def format_year(start: int) -> str:
    return f"{start}-{(start + 1) % 100:02d}"


def cds_freshness_floor(as_of: date) -> str:
    """Python copy of the SQL `cds_freshness_floor(p_as_of)`.

    From September: the previous academic year (Sep 2026 -> 2025-26).
    Before September: the prior complete cycle (Aug 2026 -> 2024-25).
    """
    start = as_of.year - 1 if as_of.month >= 9 else as_of.year - 2
    return format_year(start)


def months_since_fall(year_start: int, as_of: date) -> float:
    """Fractional months from Sept 1 of `year_start` to `as_of`."""
    whole = (as_of.year - year_start) * 12 + (as_of.month - 9)
    days_in_month = calendar.monthrange(as_of.year, as_of.month)[1]
    return whole + (as_of.day - 1) / days_in_month


def expected_pct(months: float) -> float:
    """Share (percent) of a CDS year's files expected `months` after its fall."""
    curve = POSTING_CURVE
    if months <= curve[0][0]:
        return curve[0][1]
    if months >= curve[-1][0]:
        return curve[-1][1]
    for (m0, p0), (m1, p1) in zip(curve, curve[1:]):
        if m0 <= months <= m1:
            return p0 + (p1 - p0) * (months - m0) / (m1 - m0)
    raise AssertionError("unreachable")


def current_year_floor_pct(months: float) -> float:
    return max(0.0, expected_pct(months) - CURRENT_YEAR_MARGIN_PTS)


def next_year_is_active(months_next: float) -> bool:
    return expected_pct(months_next) >= NEXT_YEAR_ACTIVE_FROM_PCT


def next_year_floor_pct(months_next: float) -> float:
    return expected_pct(months_next) * NEXT_YEAR_FLOOR_FACTOR


# ---------------------------------------------------------------- computing


def school_years(rows: Iterable[dict[str, Any]]) -> dict[str, set[int]]:
    """Valid filed start years per school from live published documents."""
    out: dict[str, set[int]] = defaultdict(set)
    for row in rows:
        if row.get("removed_at"):
            continue
        if row.get("participation_status") != VALID_PARTICIPATION:
            continue
        school_id = row.get("school_id")
        if not school_id:
            continue
        year = parse_year(row.get("canonical_year"))
        if year is None:
            continue
        out[school_id].add(year)
    return dict(out)


@dataclass
class Renewal:
    year: int
    prev_schools: set[str]
    renewed: set[str]

    @property
    def pct(self) -> float | None:
        if not self.prev_schools:
            return None
        return round(100.0 * len(self.renewed) / len(self.prev_schools), 1)

    @property
    def missing(self) -> set[str]:
        return self.prev_schools - self.renewed


def renewal(years_by_school: dict[str, set[int]], year: int) -> Renewal:
    """Schools with `year - 1` (denominator) that also have `year`.

    A school with only `year` is not in the denominator.
    """
    prev = {s for s, ys in years_by_school.items() if (year - 1) in ys}
    renewed = {s for s in prev if year in years_by_school[s]}
    return Renewal(year=year, prev_schools=prev, renewed=renewed)


def lapsed_schools(years_by_school: dict[str, set[int]], year: int) -> set[str]:
    """Schools with a live document in either of the two years before `year`
    and none in `year`. Renewal cannot see a school that already missed a
    year: it leaves the denominator the September after."""
    return {
        s
        for s, ys in years_by_school.items()
        if year not in ys and ((year - 1) in ys or (year - 2) in ys)
    }


@dataclass
class Result:
    as_of: date
    current_year: int
    months_since_fall: float
    current: Renewal
    floor_pct: float
    floor_overridden: bool
    next: Renewal
    next_active: bool
    next_floor_pct: float | None
    two_year: Renewal
    two_year_floor_pct: float
    lapsed: set[str]
    years_by_school: dict[str, set[int]]

    @property
    def below_floor(self) -> bool:
        pct = self.current.pct
        return pct is not None and pct < round(self.floor_pct, 1)

    @property
    def next_below_floor(self) -> bool | None:
        if not self.next_active or self.next_floor_pct is None:
            return None
        pct = self.next.pct
        return pct is not None and pct < round(self.next_floor_pct, 1)

    @property
    def two_year_below_floor(self) -> bool:
        pct = self.two_year.pct
        return pct is not None and pct < round(self.two_year_floor_pct, 1)


def two_year_renewal(years_by_school: dict[str, set[int]], year: int) -> Renewal:
    """Schools with `year - 1` or `year - 2` (denominator) that also have `year`.

    The one-year check's denominator shrinks as schools miss a year: a school
    that missed `year - 1` is gone from it, so a permanent loss looks like
    recovery. This check keeps those schools for one more year.
    """
    prev = {s for s, ys in years_by_school.items() if (year - 1) in ys or (year - 2) in ys}
    renewed = {s for s in prev if year in years_by_school[s]}
    return Renewal(year=year, prev_schools=prev, renewed=renewed)


def compute(
    rows: list[dict[str, Any]],
    as_of: date,
    *,
    floor_override_pct: float | None = None,
    enforce_min_prev: bool = True,
) -> Result:
    by_school = school_years(rows)
    year = parse_year(cds_freshness_floor(as_of))
    assert year is not None
    cur = renewal(by_school, year)
    two = two_year_renewal(by_school, year)
    if enforce_min_prev:
        for label, count in (("one-year", len(cur.prev_schools)), ("two-year", len(two.prev_schools))):
            if count < MIN_PREV_SCHOOLS:
                raise RenewalError(
                    f"only {count} schools in the {label} denominator for {format_year(year)} "
                    f"(minimum {MIN_PREV_SCHOOLS}); the data does not look complete"
                )
    months = months_since_fall(year, as_of)
    floor = current_year_floor_pct(months)
    overridden = floor_override_pct is not None
    if overridden:
        floor = float(floor_override_pct)  # type: ignore[arg-type]
    nxt = renewal(by_school, year + 1)
    months_next = months_since_fall(year + 1, as_of)
    active = next_year_is_active(months_next)
    if active and enforce_min_prev and len(nxt.prev_schools) < MIN_PREV_SCHOOLS:
        raise RenewalError(
            f"only {len(nxt.prev_schools)} schools have a live {format_year(year)} "
            f"document (minimum {MIN_PREV_SCHOOLS}); the next-year check is not trustworthy"
        )
    return Result(
        as_of=as_of,
        current_year=year,
        months_since_fall=months,
        current=cur,
        floor_pct=floor,
        floor_overridden=overridden,
        next=nxt,
        next_active=active,
        next_floor_pct=next_year_floor_pct(months_next) if active else None,
        two_year=two,
        two_year_floor_pct=max(0.0, floor - TWO_YEAR_MARGIN_PTS),
        lapsed=lapsed_schools(by_school, year),
        years_by_school=by_school,
    )


def summary_dict(result: Result, *, run_url: str | None = None) -> dict[str, Any]:
    """The heartbeat summary. Flat keys, shared with the web and migration work.
    The `below_floor` and `two_year_below_floor` values are always real
    booleans; `next_below_floor` is null while the next year is untracked."""
    return {
        "current_year": format_year(result.current_year),
        "renewed": len(result.current.renewed),
        "prev_schools": len(result.current.prev_schools),
        "renewal_pct": result.current.pct,
        "floor_pct": round(result.floor_pct, 1),
        "months_since_fall": round(result.months_since_fall, 1),
        "below_floor": result.below_floor,
        "next_year": format_year(result.current_year + 1),
        "next_renewed": len(result.next.renewed),
        "next_prev_schools": len(result.next.prev_schools),
        "next_renewal_pct": result.next.pct,
        "next_floor_pct": (
            round(result.next_floor_pct, 1) if result.next_floor_pct is not None else None
        ),
        "next_below_floor": result.next_below_floor,
        "two_year_renewed": len(result.two_year.renewed),
        "two_year_prev_schools": len(result.two_year.prev_schools),
        "two_year_renewal_pct": result.two_year.pct,
        "two_year_floor_pct": round(result.two_year_floor_pct, 1),
        "two_year_below_floor": result.two_year_below_floor,
        "lapsed_schools": len(result.lapsed),
        "floor_overridden": result.floor_overridden,
        "alarm_issue": None,
        "run_url": run_url,
    }


CHECKS = ("current", "two_year", "next")


def lead_check(summary: dict[str, Any]) -> str | None:
    """The check an alarm leads with, or None when nothing is below its floor.
    The current year first, then the two-year, then the (noisier) next year."""
    if summary.get("below_floor") is True:
        return "current"
    if summary.get("two_year_below_floor") is True:
        return "two_year"
    if summary.get("next_below_floor") is True:
        return "next"
    return None


def check_descriptor(summary: dict[str, Any], kind: str) -> dict[str, Any]:
    """Numbers and wording of one check, for titles, posts and the report."""
    cur = parse_year(summary["current_year"])
    assert cur is not None
    prev, prev2 = format_year(cur - 1), format_year(cur - 2)
    if kind == "current":
        return {"kind": kind, "name": "one-year", "prev": prev, "year": summary["current_year"],
                "renewed": summary["renewed"], "total": summary["prev_schools"],
                "pct": summary["renewal_pct"], "floor": summary["floor_pct"]}
    if kind == "two_year":
        return {"kind": kind, "name": "two-year", "prev": f"{prev} or {prev2}",
                "year": summary["current_year"],
                "renewed": summary["two_year_renewed"], "total": summary["two_year_prev_schools"],
                "pct": summary["two_year_renewal_pct"], "floor": summary["two_year_floor_pct"]}
    if kind == "next":
        return {"kind": kind, "name": "next-year", "prev": summary["current_year"],
                "year": summary["next_year"],
                "renewed": summary["next_renewed"], "total": summary["next_prev_schools"],
                "pct": summary["next_renewal_pct"], "floor": summary["next_floor_pct"]}
    raise ValueError(kind)


# ---------------------------------------------------------------- seeds / worklist


def load_schools(path: Path) -> dict[str, dict[str, Any]]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    schools = data.get("schools") if isinstance(data, dict) else None
    if not schools:
        raise RenewalError(f"no schools found in {path}")
    return {s["id"]: s for s in schools if isinstance(s, dict) and s.get("id")}


def seed_for(school: dict[str, Any] | None) -> tuple[str, str]:
    """(seed URL, seed kind) with kind one_file, listing_page or no_seed."""
    if not school:
        return "", "no_seed"
    url = str(school.get("discovery_seed_url") or school.get("cds_url_hint") or "").strip()
    if not url:
        return "", "no_seed"
    return url, "one_file" if is_direct_doc_seed(url) else "listing_page"


SEED_KIND_ORDER = ("one_file", "listing_page", "no_seed")
SEED_KIND_HEADINGS = {
    "one_file": "Seed is one file (a single-file seed cannot see a new year on its own)",
    "listing_page": "Seed is a listing page (check the page for a new year, or the fetcher)",
    "no_seed": "No seed (needs a seed before discovery can find anything)",
}


def missing_worklist(
    result: Result, schools: dict[str, dict[str, Any]], kind: str = "current"
) -> list[dict[str, Any]]:
    """Schools missing for the given check: one-year, two-year or next-year."""
    renewal_for = {"current": result.current, "two_year": result.two_year, "next": result.next}[kind]
    out = []
    for school_id in sorted(renewal_for.missing):
        school = schools.get(school_id)
        url, seed_kind = seed_for(school)
        newest = max(result.years_by_school[school_id])
        out.append(
            {
                "school_id": school_id,
                "name": (school or {}).get("name") or school_id,
                "newest_year": format_year(newest),
                "seed_url": url,
                "seed_kind": seed_kind,
            }
        )
    return out


# ---------------------------------------------------------------- report


def _pct(value: float | None) -> str:
    return "n/a" if value is None else f"{value:.1f}%"


def _check_line(d: dict[str, Any], below: bool | None) -> str:
    state = "not tracked yet" if below is None else ("below its floor" if below else "above its floor")
    return (
        f"{d['renewed']} of {d['total']} schools ({_pct(d['pct'])}) with {d['prev']} "
        f"have {d['year']}; floor {_pct(d['floor'])}, {state}"
    )


def render_report(
    result: Result,
    worklist: list[dict[str, Any]],
    *,
    run_url: str | None = None,
    max_chars: int = 60000,
    lead: str | None = None,
) -> str:
    s = summary_dict(result)
    lead = lead or lead_check(s) or "current"
    d = check_descriptor(s, lead)
    cur = format_year(result.current_year)
    prev = format_year(result.current_year - 1)
    below = {"current": s["below_floor"], "two_year": s["two_year_below_floor"],
             "next": s["next_below_floor"]}
    why = {
        "current": (
            f"of the schools with a live document filed under {prev}, the share that also "
            f"have one filed under {cur}. `unknown` years do not count, and a school that has "
            "only the newer year is not counted."
        ),
        "two_year": (
            f"of the schools with a live document filed under {prev} or "
            f"{format_year(result.current_year - 2)}, the share that also have one filed under "
            f"{cur}. The one-year number drops a school once it misses a year, so a permanent "
            "loss can look like recovery there; this one keeps it for a year more."
        ),
        "next": (
            f"of the schools with a live document filed under {cur}, the share that also have "
            f"one filed under {format_year(result.current_year + 1)}, which is the early curve "
            "for the newest year."
        ),
    }[lead]
    lines = [
        f"# Discovery renewal, {result.as_of.isoformat()}",
        "",
        f"**{d['renewed']} of {d['total']} schools ({_pct(d['pct'])}) that have {d['prev']} also "
        f"have {d['year']}.** The {d['name']} floor today is {_pct(d['floor'])}"
        + (" (overridden for a test)" if result.floor_overridden and lead == "current" else "")
        + ". "
        + ("It is below the floor." if below[lead] else "It is above the floor."),
        "",
        f"What the {d['name']} number is: {why}",
        "",
        "All three checks today:",
        "",
        f"- One-year: {_check_line(check_descriptor(s, 'current'), below['current'])}"
        + (f" (floor overridden for a test)" if result.floor_overridden else "")
        + f". It is {result.months_since_fall:.1f} months after the fall of {result.current_year}; "
        f"the floor is the share of a year's files that exist by now (the 2024-25 posting "
        f"curve), less {CURRENT_YEAR_MARGIN_PTS:.0f} points.",
        f"- Two-year: {_check_line(check_descriptor(s, 'two_year'), below['two_year'])} "
        f"(the one-year floor less {TWO_YEAR_MARGIN_PTS:.0f} points).",
        f"- Next year: {_check_line(check_descriptor(s, 'next'), below['next'])}"
        + ("" if result.next_active else
           f" (the curve says under {NEXT_YEAR_ACTIVE_FROM_PCT:.0f}% of files exist this early)")
        + ".",
        "",
        f"Schools that already missed a year: {s['lapsed_schools']} have a live "
        f"document filed under {prev} or {format_year(result.current_year - 2)} but none "
        f"under {cur}.",
        "",
        f"## Schools missing for the {d['name']} check ({len(worklist)})",
        "",
    ]
    for kind in SEED_KIND_ORDER:
        group = [w for w in worklist if w["seed_kind"] == kind]
        if not group:
            continue
        lines += [f"### {SEED_KIND_HEADINGS[kind]} ({len(group)})", ""]
        for w in group:
            link = f"[{w['name']}]({SCHOOL_PAGE_URL.format(school_id=w['school_id'])})"
            seed = f" · seed: {w['seed_url']}" if w["seed_url"] else ""
            lines.append(f"- {link} · newest {w['newest_year']}{seed}")
        lines.append("")
    if run_url:
        lines += [f"Run: {run_url}", ""]
    text = "\n".join(lines)
    if len(text) > max_chars:
        text = text[: max_chars - 200].rsplit("\n", 1)[0] + (
            "\n\n(List cut to fit the issue size limit. The full list is in the "
            "workflow artifact.)\n"
        )
    return text


# ---------------------------------------------------------------- fetching


Fetcher = Callable[[str, dict[str, str], str], tuple[Any, dict[str, str]]]


def http_json(
    url: str, headers: dict[str, str], method: str = "GET", body: bytes | None = None
) -> tuple[Any, dict[str, str]]:
    request = urllib.request.Request(url, data=body, method=method, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=HTTP_TIMEOUT_SEC) as response:
            payload = json.loads(response.read().decode("utf-8"))
            return payload, {k.lower(): v for k, v in response.headers.items()}
    except urllib.error.HTTPError as exc:
        raise RenewalError(f"HTTP {exc.code} from {urllib.parse.urlsplit(url).path}") from None
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise RenewalError(f"request to {urllib.parse.urlsplit(url).path} failed: {type(exc).__name__}") from None


def _headers(anon_key: str, **extra: str) -> dict[str, str]:
    return {"apikey": anon_key, "Authorization": f"Bearer {anon_key}", "Accept": "application/json", **extra}


def parse_content_range_total(value: str | None) -> int:
    """Total from `0-999/6048`. `*` totals (count not honoured) are an error."""
    if not value or "/" not in value:
        raise RenewalError(f"missing Content-Range total (got {value!r})")
    total = value.rsplit("/", 1)[1]
    if not total.isdigit():
        raise RenewalError(f"Content-Range has no exact total (got {value!r})")
    return int(total)


def fetch_live_manifest(
    api_url: str,
    anon_key: str,
    *,
    get: Callable[..., tuple[Any, dict[str, str]]] = http_json,
) -> list[dict[str, Any]]:
    """All live `cds_manifest` rows, paged. Raises unless every row arrived."""
    rows: list[dict[str, Any]] = []
    total: int | None = None
    while total is None or len(rows) < total:
        offset = len(rows)
        url = f"{api_url.rstrip('/')}/rest/v1/cds_manifest?{MANIFEST_QUERY}&limit={PAGE_SIZE}&offset={offset}"
        page, headers = get(url, _headers(anon_key, Prefer="count=exact"))
        page_total = parse_content_range_total(headers.get("content-range"))
        if total is None:
            total = page_total
            if total == 0:
                raise RenewalError("cds_manifest returned zero live rows")
        elif page_total != total:
            raise RenewalError(f"row count changed while paging ({total} -> {page_total})")
        if not isinstance(page, list):
            raise RenewalError("cds_manifest page was not a list")
        if not page:
            break
        rows.extend(page)
    if total is None or len(rows) != total:
        raise RenewalError(f"short read: fetched {len(rows)} rows, Content-Range total {total}")
    return rows


def fetch_sql_floor(
    api_url: str,
    anon_key: str,
    as_of: date,
    *,
    get: Callable[..., tuple[Any, dict[str, str]]] = http_json,
) -> str:
    url = f"{api_url.rstrip('/')}/rest/v1/rpc/cds_freshness_floor"
    body = json.dumps({"p_as_of": as_of.isoformat()}).encode("utf-8")
    value, _ = get(url, _headers(anon_key, **{"Content-Type": "application/json"}), "POST", body)
    if not isinstance(value, str):
        raise RenewalError(f"cds_freshness_floor returned {value!r}")
    return value


def check_floor_agrees(python_floor: str, sql_floor: str) -> None:
    if python_floor != sql_floor:
        raise RenewalError(
            f"freshness floor disagrees: Python says {python_floor}, "
            f"cds_freshness_floor() says {sql_floor}"
        )


# ---------------------------------------------------------------- backtest


def parse_month_range(spec: str) -> list[date]:
    """`2026-05..2026-11` -> last day of each month, inclusive."""
    match = re.fullmatch(r"(\d{4})-(\d{2})\.\.(\d{4})-(\d{2})", spec)
    if not match:
        raise RenewalError(f"bad --backtest-month-ends {spec!r}; use YYYY-MM..YYYY-MM")
    y, m, y2, m2 = (int(g) for g in match.groups())
    if not (1 <= m <= 12 and 1 <= m2 <= 12) or (y, m) > (y2, m2):
        raise RenewalError(f"bad --backtest-month-ends {spec!r}")
    out = []
    while (y, m) <= (y2, m2):
        out.append(date(y, m, calendar.monthrange(y, m)[1]))
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    return out


_FRACTION_RE = re.compile(r"\.(\d+)")


def _parse_ts(value: Any) -> datetime | None:
    """Parse an ISO timestamp with a fraction of any length (Python before 3.11
    accepts only 3 or 6 digits). Empty is None; anything else that does not
    parse raises, because a silently ignored date would count the row as
    always present or never removed."""
    if value is None or value == "":
        return None
    text = str(value).strip().replace("Z", "+00:00")
    text = _FRACTION_RE.sub(lambda m: "." + m.group(1)[:6].ljust(6, "0"), text, count=1)
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        raise RenewalError(f"unparseable timestamp {value!r}") from None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def rows_as_of(rows: list[dict[str, Any]], day: date) -> list[dict[str, Any]]:
    """Rows present at the end of `day`: discovered by then (null counts as
    always present) and not yet removed. `removed_at` is cleared in the copy
    so the live filter in `school_years` does not drop rows removed later."""
    end = datetime.combine(day, datetime.max.time(), tzinfo=timezone.utc)
    out = []
    for row in rows:
        discovered = _parse_ts(row.get("discovered_at"))
        if discovered is not None and discovered > end:
            continue
        removed = _parse_ts(row.get("removed_at"))
        if removed is not None and removed <= end:
            continue
        out.append({**row, "removed_at": None})
    return out


def backtest(rows: list[dict[str, Any]], days: list[date]) -> list[dict[str, Any]]:
    out = []
    for day in days:
        # The denominator minimum is a production guard; a replay of an early
        # month can legitimately have few rows, so it is reported, not raised.
        result = compute(rows_as_of(rows, day), day, enforce_min_prev=False)
        out.append(
            {
                "date": day.isoformat(),
                "current_year": format_year(result.current_year),
                "renewed": len(result.current.renewed),
                "prev": len(result.current.prev_schools),
                "pct": result.current.pct,
                "floor": round(result.floor_pct, 1),
                "below": result.below_floor,
                "next_year": format_year(result.current_year + 1),
                "next_renewed": len(result.next.renewed),
                "next_prev": len(result.next.prev_schools),
                "next_pct": result.next.pct,
                "next_floor": (
                    round(result.next_floor_pct, 1) if result.next_floor_pct is not None else None
                ),
                "next_below": result.next_below_floor,
            }
        )
    return out


def render_backtest(table: list[dict[str, Any]], null_discovered: int) -> str:
    def cell(v: Any) -> str:
        if v is None:
            return "-"
        if isinstance(v, bool):
            return "BELOW" if v else "ok"
        return f"{v:.1f}" if isinstance(v, float) else str(v)

    head = (
        "date        | cur year | renewed/prev | pct   | floor | below | "
        "next year | renewed/prev | pct   | floor | below"
    )
    lines = [head, "-" * len(head)]
    for r in table:
        lines.append(
            f"{r['date']} | {r['current_year']:<8} | {r['renewed']:>4}/{r['prev']:<7} | "
            f"{cell(r['pct']):>5} | {cell(r['floor']):>5} | {cell(r['below']):>5} | "
            f"{r['next_year']:<9} | {r['next_renewed']:>4}/{r['next_prev']:<7} | "
            f"{cell(r['next_pct']):>5} | {cell(r['next_floor']):>5} | {cell(r['next_below']):>5}"
        )
    lines.append("")
    lines.append(f"Rows with a null discovered_at (counted as always present): {null_discovered}")
    return "\n".join(lines)


# ---------------------------------------------------------------- CLI


def write_json(path: Path | None, data: Any) -> None:
    if path is None:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--api-url", default=os.environ.get("CDS_API_URL", DEFAULT_API))
    parser.add_argument("--anon-key", default=os.environ.get("SUPABASE_ANON_KEY", ""))
    parser.add_argument("--as-of", help="YYYY-MM-DD; default today (UTC)")
    parser.add_argument("--manifest-json", type=Path, help="compute from a local snapshot, no network")
    parser.add_argument("--schools-yaml", type=Path, default=DEFAULT_SCHOOLS_YAML)
    parser.add_argument("--floor-override-pct", type=float, help="test only (needs --test-mode): replaces the current-year floor")
    parser.add_argument("--test-mode", action="store_true", help="this is a test run; allows --floor-override-pct")
    parser.add_argument("--backtest-month-ends", help="e.g. 2026-05..2026-11 (needs --manifest-json)")
    parser.add_argument("--run-url", default=os.environ.get("PIPELINE_RUN_URL", ""))
    parser.add_argument("--out-summary", type=Path)
    parser.add_argument("--out-report", type=Path)
    parser.add_argument("--out-state", type=Path)
    parser.add_argument("--out-worklist", type=Path, help="full worklist as JSON (artifact)")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return run(args)
    except RenewalError as exc:
        print(f"::error::discovery renewal: {exc}", file=sys.stderr)
        return 1


def run(args: argparse.Namespace) -> int:
    if args.floor_override_pct is not None and not args.test_mode:
        raise RenewalError("--floor-override-pct is for test runs only; pass --test-mode (or drop it)")
    as_of = date.fromisoformat(args.as_of) if args.as_of else datetime.now(timezone.utc).date()

    if args.backtest_month_ends:
        if not args.manifest_json:
            raise RenewalError("--backtest-month-ends needs --manifest-json")
        rows = json.loads(args.manifest_json.read_text(encoding="utf-8"))
        nulls = sum(1 for r in rows if not r.get("discovered_at"))
        table = backtest(rows, parse_month_range(args.backtest_month_ends))
        print(render_backtest(table, nulls))
        return 0

    if args.manifest_json:
        rows = json.loads(args.manifest_json.read_text(encoding="utf-8"))
        rows = [r for r in rows if not r.get("removed_at")]
    else:
        if not args.anon_key:
            raise RenewalError("no anon key: set SUPABASE_ANON_KEY or pass --anon-key")
        rows = fetch_live_manifest(args.api_url, args.anon_key)
        check_floor_agrees(
            cds_freshness_floor(as_of), fetch_sql_floor(args.api_url, args.anon_key, as_of)
        )
        print(f"fetched {len(rows)} live manifest rows; floor {cds_freshness_floor(as_of)} agrees with SQL")

    result = compute(rows, as_of, floor_override_pct=args.floor_override_pct)
    schools = load_schools(args.schools_yaml)
    summary = summary_dict(result, run_url=args.run_url or None)
    lead = lead_check(summary)
    worklist = missing_worklist(result, schools, lead or "current")
    report = render_report(result, worklist, run_url=args.run_url or None, lead=lead)

    write_json(args.out_summary, summary)
    write_json(args.out_worklist, worklist)
    if args.out_report:
        args.out_report.parent.mkdir(parents=True, exist_ok=True)
        args.out_report.write_text(report, encoding="utf-8")
    write_json(
        args.out_state,
        {
            "below_floor": lead is not None,
            "lead_check": lead,
            "current_below_floor": summary["below_floor"],
            "next_below_floor": summary["next_below_floor"],
            "two_year_below_floor": summary["two_year_below_floor"],
            "summary": summary,
        },
    )
    print(json.dumps(summary, indent=2, sort_keys=True))
    print(
        f"missing by seed kind: "
        + ", ".join(
            f"{k}={sum(1 for w in worklist if w['seed_kind'] == k)}" for k in SEED_KIND_ORDER
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
