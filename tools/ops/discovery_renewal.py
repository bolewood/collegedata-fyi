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
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Iterable

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import yaml  # noqa: E402

from tools.finder.stuck_pdf_seeds import is_direct_doc_seed  # noqa: E402

DEFAULT_API = "https://api.collegedata.fyi"
# PRD 033: pipeline traffic to the public API identifies itself.
USER_AGENT = "collegedata-pipeline/discovery-renewal"
DEFAULT_SCHOOLS_YAML = REPO_ROOT / "tools" / "finder" / "schools.yaml"
SCHOOL_PAGE_URL = "https://www.collegedata.fyi/schools/{school_id}"
PAGE_SIZE = 1000
HTTP_TIMEOUT_SEC = 60
MANIFEST_QUERY = (
    "select=school_id,canonical_year,discovered_at,removed_at,participation_status,"
    "data_quality_flag,sub_institutional,extraction_status"
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

# Arrivals check: a total stop (no new documents at all) barely moves the
# renewal percentages for weeks, so count the schools that gained a document
# for the current or next year in the last 30 days and compare with what the
# posting curve expects for a month.
ARRIVALS_WINDOW_DAYS = 30
# From about December to February the curve expects under 10 arrivals a month,
# so a 30-day window cannot judge. It then looks over 60 days (still needing
# 10 expected; otherwise the check says it was not made, and why).
ARRIVALS_LONG_WINDOW_DAYS = 60
ARRIVALS_MIN_EXPECTED = 10.0  # below this the curve says too little arrives to judge
ARRIVALS_FLOOR_SHARE = 0.25  # alarm when arrivals fall under this share of expected

VALID_PARTICIPATION = "published"
# A current-year document with one of these flags is not a usable renewal: the
# file is the wrong school's, an empty template, or mostly unread. It does not
# count in the numerator (it still counts as having filed that year in a
# denominator, so a school is not dropped for posting a bad file).
UNCOUNTED_FLAGS = frozenset({"wrong_file", "blank_template", "low_coverage"})


def is_flagged(row: dict[str, Any]) -> bool:
    """True when the document carries any data-quality flag. This fails
    closed: UNCOUNTED_FLAGS lists the values known today, but a new value (a
    flag added later) also keeps a document from counting as a renewal, and the
    report lists every flag value with its count so a new one is seen."""
    flag = row.get("data_quality_flag")
    return flag is not None and str(flag).strip() != ""
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


def school_years(
    rows: Iterable[dict[str, Any]], *, exclude_flagged: bool = False
) -> dict[str, set[int]]:
    """Valid filed start years per school from live published documents.

    With `exclude_flagged`, documents whose `data_quality_flag` is in
    any flag are left out: the years a school usefully renewed.
    """
    out: dict[str, set[int]] = defaultdict(set)
    for row in rows:
        if row.get("removed_at"):
            continue
        if row.get("participation_status") != VALID_PARTICIPATION:
            continue
        school_id = row.get("school_id")
        if not school_id:
            continue
        if row.get("sub_institutional"):
            # A sub-program's filing (a college within a university) must not
            # mask a missing main-campus CDS.
            continue
        year = parse_year(row.get("canonical_year"))
        if year is None:
            continue
        if exclude_flagged and is_flagged(row):
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


def renewal(
    years_by_school: dict[str, set[int]],
    year: int,
    good_years: dict[str, set[int]] | None = None,
) -> Renewal:
    """Schools with `year - 1` (denominator) that also have `year`.

    A school with only `year` is not in the denominator. `good_years` (the
    years without a flagged document) decides the numerator when given.
    """
    good = years_by_school if good_years is None else good_years
    prev = {s for s, ys in years_by_school.items() if (year - 1) in ys}
    renewed = {s for s in prev if year in good.get(s, ())}
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
    year_checks: dict[int, "YearCheck"]
    flagged_docs: list[dict[str, str]]
    sub_institutional_excluded: int = 0
    arrivals: Arrivals | None = None
    unextracted_current_docs: int = 0

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


@dataclass
class Arrivals:
    """Schools that gained a usable current- or next-year document recently."""

    count: int  # in the window that was judged
    expected: float
    schools: set[str]
    window_days: int = ARRIVALS_WINDOW_DAYS
    count_30: int | None = None
    expected_30: float | None = None
    count_60: int | None = None
    expected_60: float | None = None

    @property
    def checked(self) -> bool:
        """False when even the longest window expects too few to judge."""
        return self.expected >= ARRIVALS_MIN_EXPECTED

    @property
    def below_floor(self) -> bool:
        return self.checked and self.count < ARRIVALS_FLOOR_SHARE * self.expected


@dataclass
class YearCheck:
    """Both checks for one CDS year, with the floors that apply to it today.

    A floor of None means the check is not tracked (the next year before
    March; the next year's two-year check, which is too noisy to alarm on)."""

    year: int
    one: Renewal
    one_floor: float | None
    two: Renewal
    two_floor: float | None
    is_next: bool

    @staticmethod
    def _below(renewal_: Renewal, floor: float | None) -> bool:
        pct = renewal_.pct
        return floor is not None and pct is not None and pct < round(floor, 1)

    @property
    def one_below(self) -> bool:
        return self._below(self.one, self.one_floor)

    @property
    def two_below(self) -> bool:
        return self._below(self.two, self.two_floor)


YEARS_BACK = 3  # years before the current one that still get evaluated


def year_checks(
    by_school: dict[str, set[int]],
    good: dict[str, set[int]],
    current: int,
    as_of: date,
    floor_override_pct: float | None = None,
) -> dict[int, YearCheck]:
    """Checks for every year an alarm issue could be about: from `current - 3`
    to the next year. A year past the September switch is judged by its own
    months since fall, which is the curve's flat end (88% less the margin)."""
    out: dict[int, YearCheck] = {}
    for y in range(current - YEARS_BACK, current + 2):
        months = months_since_fall(y, as_of)
        one = renewal(by_school, y, good)
        two = two_year_renewal(by_school, y, good)
        if y == current + 1:
            floor = next_year_floor_pct(months) if next_year_is_active(months) else None
            out[y] = YearCheck(y, one, floor, two, None, True)
            continue
        floor = current_year_floor_pct(months)
        if y == current and floor_override_pct is not None:
            floor = float(floor_override_pct)
        out[y] = YearCheck(y, one, floor, two, max(0.0, floor - TWO_YEAR_MARGIN_PTS), False)
    return out


def year_summary(check: YearCheck, arrivals: "Arrivals | None" = None) -> dict[str, Any]:
    """One year's checks in the shape of the heartbeat summary (as the
    "current" year), so titles and descriptors work for any year. The arrivals
    check belongs to the current year's issue; pass it for that year only."""
    out = {
        "current_year": format_year(check.year),
        "is_next_year": check.is_next,
        "renewed": len(check.one.renewed),
        "prev_schools": len(check.one.prev_schools),
        "renewal_pct": check.one.pct,
        "floor_pct": None if check.one_floor is None else round(check.one_floor, 1),
        "below_floor": check.one_below,
        "two_year_renewed": len(check.two.renewed),
        "two_year_prev_schools": len(check.two.prev_schools),
        "two_year_renewal_pct": check.two.pct,
        "two_year_floor_pct": None if check.two_floor is None else round(check.two_floor, 1),
        "two_year_below_floor": check.two_below,
    }
    if arrivals is not None:
        out.update(arrivals_keys(arrivals))
    return out


def arrivals_keys(arrivals: Arrivals) -> dict[str, Any]:
    def pick(value: Any, fallback: Any) -> Any:
        return fallback if value is None else value

    return {
        "arrivals_30d": pick(arrivals.count_30, arrivals.count),
        "arrivals_expected_30d": round(pick(arrivals.expected_30, arrivals.expected), 1),
        "arrivals_60d": pick(arrivals.count_60, arrivals.count),
        "arrivals_expected_60d": round(pick(arrivals.expected_60, arrivals.expected), 1),
        "arrivals_window_days": arrivals.window_days,
        "arrivals_checked": arrivals.checked,
        "arrivals_below_floor": arrivals.below_floor,
    }


def two_year_renewal(
    years_by_school: dict[str, set[int]],
    year: int,
    good_years: dict[str, set[int]] | None = None,
) -> Renewal:
    """Schools with `year - 1` or `year - 2` (denominator) that also have `year`.

    The one-year check's denominator shrinks as schools miss a year: a school
    that missed `year - 1` is gone from it, so a permanent loss looks like
    recovery. This check keeps those schools for one more year.
    """
    good = years_by_school if good_years is None else good_years
    prev = {s for s, ys in years_by_school.items() if (year - 1) in ys or (year - 2) in ys}
    renewed = {s for s in prev if year in good.get(s, ())}
    return Renewal(year=year, prev_schools=prev, renewed=renewed)


def count_sub_institutional(rows: Iterable[dict[str, Any]]) -> int:
    """Live published rows left out of every check because they belong to a
    sub-institution."""
    return sum(
        1
        for row in rows
        if row.get("sub_institutional")
        and not row.get("removed_at")
        and row.get("participation_status") == VALID_PARTICIPATION
    )


def compute_arrivals(
    rows: Iterable[dict[str, Any]],
    checks: dict[int, "YearCheck"],
    current: int,
    as_of: date,
) -> Arrivals:
    """Distinct schools that gained a live, unflagged, valid-year document
    filed under the current or next year with `discovered_at` in the last
    ARRIVALS_WINDOW_DAYS days, against what the posting curve expects in a
    month: for each of the two years, its previous-year cohort times the curve's
    gain over the last month. When that expects under ARRIVALS_MIN_EXPECTED
    (December to February), the same is judged over 60 days and two months.

    A school gained a year when the earliest such document it has for that
    year is inside the window; a school that already had the year (an undated
    document counts as old) does not count again for a second file."""
    wanted = {current, current + 1}
    earliest: dict[tuple[str, int], datetime | None] = {}
    for row in rows:
        if row.get("removed_at") or row.get("participation_status") != VALID_PARTICIPATION:
            continue
        if row.get("sub_institutional") or is_flagged(row):
            continue
        school = row.get("school_id")
        year = parse_year(row.get("canonical_year"))
        if not school or year not in wanted:
            continue
        key = (school, year)
        ts = _parse_ts(row.get("discovered_at"))
        if ts is None:
            earliest[key] = datetime.min.replace(tzinfo=timezone.utc)  # old, undated
        elif key not in earliest or ts < earliest[key]:  # type: ignore[operator]
            earliest[key] = ts

    def window(days: int) -> tuple[set[str], float]:
        start = datetime.combine(
            as_of - timedelta(days=days), datetime.min.time(), tzinfo=timezone.utc
        )
        gained = {school for (school, _y), ts in earliest.items() if ts is not None and ts >= start}
        expected = 0.0
        span = days / ARRIVALS_WINDOW_DAYS  # months of the curve the window covers
        for year in wanted:
            months = months_since_fall(year, as_of)
            gain = expected_pct(months) - expected_pct(months - span)
            expected += len(checks[year].one.prev_schools) * gain / 100.0
        return gained, expected

    gained_30, expected_30 = window(ARRIVALS_WINDOW_DAYS)
    gained_60, expected_60 = window(ARRIVALS_LONG_WINDOW_DAYS)
    use_long = expected_30 < ARRIVALS_MIN_EXPECTED
    gained, expected = (gained_60, expected_60) if use_long else (gained_30, expected_30)
    return Arrivals(
        count=len(gained),
        expected=expected,
        schools=gained,
        window_days=ARRIVALS_LONG_WINDOW_DAYS if use_long else ARRIVALS_WINDOW_DAYS,
        count_30=len(gained_30),
        expected_30=expected_30,
        count_60=len(gained_60),
        expected_60=expected_60,
    )


def unextracted_current_docs(rows: Iterable[dict[str, Any]], year: int) -> int:
    """Live published documents filed under `year` that are not extracted yet.
    Report only: they count as filed (see issue #477)."""
    return sum(
        1
        for row in rows
        if not row.get("removed_at")
        and row.get("participation_status") == VALID_PARTICIPATION
        and not row.get("sub_institutional")
        and parse_year(row.get("canonical_year")) == year
        and "extraction_status" in row
        and row["extraction_status"] != "extracted"
    )


def flagged_current_docs(rows: Iterable[dict[str, Any]], year: int) -> list[dict[str, str]]:
    """Live published documents filed under `year` that carry an uncounted
    flag: they do not count as renewing."""
    out = []
    for row in rows:
        if row.get("removed_at") or row.get("participation_status") != VALID_PARTICIPATION:
            continue
        if row.get("sub_institutional"):
            continue
        if parse_year(row.get("canonical_year")) != year:
            continue
        flag = row.get("data_quality_flag")
        if is_flagged(row) and row.get("school_id"):
            out.append({"school_id": row["school_id"], "flag": flag})
    return sorted(out, key=lambda d: (d["school_id"], d["flag"]))


def compute(
    rows: list[dict[str, Any]],
    as_of: date,
    *,
    floor_override_pct: float | None = None,
    enforce_min_prev: bool = True,
) -> Result:
    by_school = school_years(rows)
    good = school_years(rows, exclude_flagged=True)
    year = parse_year(cds_freshness_floor(as_of))
    assert year is not None
    checks = year_checks(by_school, good, year, as_of, floor_override_pct)
    cur = checks[year].one
    two = checks[year].two
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
    nxt = checks[year + 1].one
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
        year_checks=checks,
        flagged_docs=flagged_current_docs(rows, year),
        sub_institutional_excluded=count_sub_institutional(rows),
        arrivals=compute_arrivals(rows, checks, year, as_of),
        unextracted_current_docs=unextracted_current_docs(rows, year),
    )


def outstanding_years(result: Result) -> list[str]:
    """The CDS years, current or next, with a check below its floor now. The
    alarm step replaces this with the years that have an open alarm issue,
    which also covers an earlier year that is still short."""
    arrivals_short = result.arrivals is not None and result.arrivals.below_floor
    return [
        format_year(y)
        for y, c in sorted(result.year_checks.items())
        if y >= result.current_year
        and (c.one_below or c.two_below or (arrivals_short and y == result.current_year))
    ]


def summary_dict(
    result: Result,
    *,
    run_url: str | None = None,
    same_year_duplicates: int | None = None,
    seed_summary: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """The heartbeat summary. Flat keys, shared with the web and migration work.
    The `below_floor` and `two_year_below_floor` values are always real
    booleans; `next_below_floor` is null while the next year is untracked."""
    seed_keys = seed_summary_keys(seed_summary)
    return {
        **seed_keys,
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
        # School-years with two or more live documents (tools/ops/same_year_duplicates.py).
        # null when the run read a saved manifest and did not look.
        "same_year_duplicates": same_year_duplicates,
        "outstanding_below_floor": bool(outstanding_years(result)),
        "outstanding_years": ",".join(outstanding_years(result)),
        **arrivals_keys(result.arrivals if result.arrivals is not None else Arrivals(0, 0.0, set())),
        "unextracted_current_docs": result.unextracted_current_docs,
        "flagged_current_docs": len(result.flagged_docs),
        "sub_institutional_excluded": result.sub_institutional_excluded,
        "floor_overridden": result.floor_overridden,
        "alarm_issue": None,
        "run_url": run_url,
    }


CHECKS = ("current", "two_year", "next")


def seed_summary_keys(seed_summary: dict[str, Any] | None) -> dict[str, Any]:
    """Flat heartbeat keys from `seed_age.summarize()` (#462); null when not computed."""
    if seed_summary is None:
        return {
            "seeds_with_seed": None,
            "seeds_without_new_year": None,
            "seeds_without_new_year_one_file": None,
            "seeds_without_new_year_listing_page": None,
        }
    kinds = seed_summary["by_kind"]
    return {
        "seeds_with_seed": seed_summary["seeds"],
        "seeds_without_new_year": seed_summary["seeds_without_new_year"],
        "seeds_without_new_year_one_file": kinds["one_file"]["behind"],
        "seeds_without_new_year_listing_page": kinds["listing_page"]["behind"],
    }


def lead_check(summary: dict[str, Any]) -> str | None:
    """The check an alarm leads with, or None when nothing is below its floor.
    The current year first, then the two-year, then the (noisier) next year."""
    if summary.get("below_floor") is True:
        return "current"
    if summary.get("two_year_below_floor") is True:
        return "two_year"
    if summary.get("next_below_floor") is True:
        return "next"
    if summary.get("arrivals_below_floor") is True:
        return "arrivals"
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
    if kind == "arrivals":
        # No percentages: `renewed` is the schools that arrived, `total` what
        # the curve expected (rounded); the alarm words this check itself.
        window = summary.get("arrivals_window_days", ARRIVALS_WINDOW_DAYS)
        return {"kind": kind, "name": "arrivals", "prev": prev, "year": summary["current_year"],
                "renewed": summary[f"arrivals_{window}d"],
                "total": round(summary[f"arrivals_expected_{window}d"]),
                "window": window, "pct": None, "floor": None}
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
    result: Result,
    schools: dict[str, dict[str, Any]],
    kind: str = "current",
    year: int | None = None,
) -> list[dict[str, Any]]:
    """Schools missing for the given check: one-year, two-year or next-year.
    With `year`, that year's own check (`kind` is then "current" or
    "two_year"); the default is the current year."""
    if kind == "arrivals":
        kind = "current"  # the schools still missing the current year
    if year is not None and year != result.current_year:
        yc = result.year_checks[year]
        renewal_for = yc.two if kind == "two_year" else yc.one
    else:
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


def _arrivals_line(s: dict[str, Any], cur: str, nxt: str) -> list[str]:
    window = s["arrivals_window_days"]
    got, expected = s[f"arrivals_{window}d"], s[f"arrivals_expected_{window}d"]
    if not s["arrivals_checked"]:
        return [
            f"- Arrivals: not checked. The posting curve expects about {expected:.0f} new "
            f"{cur} or {nxt} documents in {window} days, under the {ARRIVALS_MIN_EXPECTED:.0f} "
            "needed to judge."
        ]
    verdict = "below its floor" if s["arrivals_below_floor"] else "above its floor"
    return [
        f"- Arrivals: {got} schools gained a {cur} or {nxt} document in the last {window} "
        f"days; the curve expects about {expected:.0f}, {verdict}."
    ]


def _notes_lines(result: Result, schools: dict[str, dict[str, Any]] | None) -> list[str]:
    """What the count left out: flagged current-year documents and
    sub-institution rows."""
    lines: list[str] = []
    if result.flagged_docs:
        names = []
        for doc in result.flagged_docs:
            school = (schools or {}).get(doc["school_id"]) or {}
            link = f"[{school.get('name') or doc['school_id']}]({SCHOOL_PAGE_URL.format(school_id=doc['school_id'])})"
            names.append(f"{link} ({doc['flag']})")
        lines += [
            f"{len(result.flagged_docs)} current-year documents not counted (flagged): "
            + ", ".join(names) + ".",
            "",
            "Flag values among them: " + ", ".join(
                f"{flag} {count}" + ("" if flag in UNCOUNTED_FLAGS else " (a new value: any flag "
                                     "keeps a document from counting)")
                for flag, count in sorted(Counter(d["flag"] for d in result.flagged_docs).items())
            ) + ".",
            "",
        ]
    if result.sub_institutional_excluded:
        lines += [
            f"{result.sub_institutional_excluded} sub-institution documents are left out of "
            "every check, so a sub-program's filing cannot hide a missing main-campus file.",
            "",
        ]
    return lines


def _worklist_lines(worklist: list[dict[str, Any]]) -> list[str]:
    lines: list[str] = []
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
    return lines


def _cap(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 200].rsplit("\n", 1)[0] + (
        "\n\n(List cut to fit the issue size limit. The full list is in the "
        "workflow artifact.)\n"
    )


def render_year_report(
    result: Result,
    year: int,
    worklist: list[dict[str, Any]],
    *,
    schools: dict[str, dict[str, Any]] | None = None,
    run_url: str | None = None,
    max_chars: int = 60000,
) -> str:
    """The issue body for a CDS year other than today's current one: the next
    year (early curve) or an earlier year (flat mature floor)."""
    yc = result.year_checks[year]
    ys = year_summary(yc)
    lead = lead_check(ys) or "current"
    d = check_descriptor(ys, lead)
    below = {"current": ys["below_floor"], "two_year": ys["two_year_below_floor"]}
    ystr = format_year(year)
    if yc.is_next:
        context = (
            f"{ystr} is the next CDS year. Its floor is {NEXT_YEAR_FLOOR_FACTOR:.0%} of the share "
            "of files the posting curve expects by now, because the early curve is noisy."
        )
    else:
        context = (
            f"{ystr} is an earlier CDS year. Its floor is the flat end of the posting curve "
            f"({expected_pct(99):.0f}%) less {CURRENT_YEAR_MARGIN_PTS:.0f} points "
            f"(two-year: less {TWO_YEAR_MARGIN_PTS:.0f} more)."
        )
    lines = [
        f"# Discovery renewal for {ystr}, {result.as_of.isoformat()}",
        "",
        f"**{d['renewed']} of {d['total']} schools ({_pct(d['pct'])}) that have {d['prev']} also "
        f"have {d['year']}.** The {d['name']} floor today is {_pct(d['floor'])}. "
        + ("It is below the floor." if below[lead] else "It is above the floor."),
        "",
        context,
        "",
        f"- One-year: {_check_line(check_descriptor(ys, 'current'), below['current'])}.",
        f"- Two-year: {_check_line(check_descriptor(ys, 'two_year'), below['two_year'] if yc.two_floor is not None else None)}.",
        "",
        *(_notes_lines(result, schools) if year == result.current_year else []),
        f"## Schools missing for the {d['name']} check ({len(worklist)})",
        "",
        *_worklist_lines(worklist),
    ]
    if run_url:
        lines += [f"Run: {run_url}", ""]
    return _cap("\n".join(lines), max_chars)


def render_report(
    result: Result,
    worklist: list[dict[str, Any]],
    *,
    run_url: str | None = None,
    max_chars: int = 60000,
    lead: str | None = None,
    duplicates: Any = None,
    seeds_section: str | None = None,
    schools: dict[str, dict[str, Any]] | None = None,
) -> str:
    """`duplicates` is a `same_year_duplicates.Report` or None (not computed)."""
    s = summary_dict(result)
    lead = lead or lead_check(s) or "current"
    d = check_descriptor(s, lead)
    cur = format_year(result.current_year)
    prev = format_year(result.current_year - 1)
    below = {"current": s["below_floor"], "two_year": s["two_year_below_floor"],
             "next": s["next_below_floor"], "arrivals": s["arrivals_below_floor"]}
    why = {
        "arrivals": (
            f"the schools that gained a usable {cur} or {format_year(result.current_year + 1)} "
            f"document in the last {s['arrivals_window_days']} days, against about what the "
            f"posting curve expects in that time. Fewer than {ARRIVALS_FLOOR_SHARE:.0%} of that means new "
            "documents have nearly stopped arriving, even if the renewal percentages still look "
            "fine."
        ),
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
    if lead == "arrivals":
        headline = (
            f"**Only {d['renewed']} schools gained a {cur} or "
            f"{format_year(result.current_year + 1)} document in the last "
            f"{d['window']} days; the posting curve expects about {d['total']}.** "
            f"The alarm fires under {ARRIVALS_FLOOR_SHARE:.0%} of that."
        )
    else:
        headline = (
            f"**{d['renewed']} of {d['total']} schools ({_pct(d['pct'])}) that have {d['prev']} also "
            f"have {d['year']}.** The {d['name']} floor today is {_pct(d['floor'])}"
            + (" (overridden for a test)" if result.floor_overridden and lead == "current" else "")
            + ". "
            + ("It is below the floor." if below[lead] else "It is above the floor.")
        )
    lines = [
        f"# Discovery renewal, {result.as_of.isoformat()}",
        "",
        headline,
        "",
        f"What the {d['name']} number is: {why}",
        "",
        "All checks today:",
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
        *_arrivals_line(s, cur, format_year(result.current_year + 1)),
        "",
        *(
            [f"{s['unextracted_current_docs']} current-year documents are filed but not extracted "
             "yet; they count as renewed (see #477).", ""]
            if s["unextracted_current_docs"] else []
        ),
        f"Schools that already missed a year: {s['lapsed_schools']} have a live "
        f"document filed under {prev} or {format_year(result.current_year - 2)} but none "
        f"under {cur}.",
        "",
        *_notes_lines(result, schools),
    ]
    if duplicates is not None:
        from tools.ops.same_year_duplicates import render_markdown

        lines += [render_markdown(duplicates).rstrip("\n"), ""]
    lines += [
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
    # The seed section is capped by its renderer and comes after the worklist;
    # the worklist is what gets cut when the report is too long, never this.
    tail_lines = [seeds_section.rstrip("\n"), ""] if seeds_section else []
    if run_url:
        tail_lines += [f"Run: {run_url}", ""]
    tail = "\n".join(tail_lines)
    text = "\n".join(lines)
    budget = max_chars - len(tail) - 1
    if len(text) > budget:
        text = text[: budget - 200].rsplit("\n", 1)[0] + (
            "\n\n(List cut to fit the issue size limit. The full list is in the "
            "workflow artifact.)\n"
        )
    text = text + "\n" + tail if tail else text
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
    return {
        "apikey": anon_key,
        "Authorization": f"Bearer {anon_key}",
        "Accept": "application/json",
        "User-Agent": USER_AGENT,
        **extra,
    }


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
    parser.add_argument("--out-seed-ages", type=Path, help="every seed's age as JSON (artifact)")
    parser.add_argument("--out-worklist", type=Path, help="full worklist as JSON (artifact)")
    parser.add_argument("--out-year-reports", type=Path,
                        help="directory for one issue body per CDS year, <year>.md")
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
    duplicates = None
    if not args.manifest_json:
        # Imported here: same_year_duplicates imports this module.
        from tools.ops.same_year_duplicates import run as find_same_year_duplicates

        duplicates = find_same_year_duplicates(args.api_url, args.anon_key)
        print(f"same-year duplicates: {duplicates.count} ({duplicates.documents_read} live documents)")
    # Imported here: seed_age imports this module for the shared mechanism.
    from tools.finder import seed_age

    ages, seed_summary = seed_age.run_seed_age(schools, rows, as_of)
    summary = summary_dict(
        result,
        run_url=args.run_url or None,
        same_year_duplicates=duplicates.count if duplicates is not None else None,
        seed_summary=seed_summary,
    )
    lead = lead_check(summary)
    years = {
        format_year(y): year_summary(c, result.arrivals if y == result.current_year else None)
        for y, c in sorted(result.year_checks.items())
    }
    year_reports: dict[str, str] = {}
    for y, check in sorted(result.year_checks.items()):
        ys = year_summary(check, result.arrivals if y == result.current_year else None)
        kind = lead_check(ys) or "current"
        wl = missing_worklist(result, schools, kind, y)
        if y == result.current_year:
            year_reports[format_year(y)] = render_report(
                result, wl, run_url=args.run_url or None, lead=kind, schools=schools,
                duplicates=duplicates,
                seeds_section=seed_age.render_section(ages, cds_freshness_floor(as_of)))
        else:
            year_reports[format_year(y)] = render_year_report(
                result, y, wl, schools=schools, run_url=args.run_url or None)
    cur_str = format_year(result.current_year)
    next_str = format_year(result.current_year + 1)
    worklist = missing_worklist(result, schools, lead_check(years[cur_str]) or "current")
    report = year_reports[cur_str]
    if years[next_str]["below_floor"]:
        report += "\n\n---\n\n" + year_reports[next_str]
    if args.out_year_reports:
        args.out_year_reports.mkdir(parents=True, exist_ok=True)
        for ystr, text in year_reports.items():
            (args.out_year_reports / f"{ystr}.md").write_text(text, encoding="utf-8")

    write_json(args.out_summary, summary)
    write_json(args.out_worklist, worklist)
    write_json(args.out_seed_ages, [asdict(a) for a in ages])
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
            "years": years,
            "current_year": cur_str,
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
    # Run as a script this module is `__main__`; seed_age imports it by its
    # package name. Alias it so both see one RenewalError (main() catches it).
    sys.modules.setdefault("tools.ops.discovery_renewal", sys.modules[__name__])
    raise SystemExit(main())
