#!/usr/bin/env python3
"""Open, update and close the discovery-renewal alarm issues.

Reads the state (and the per-scope issue bodies) written by
`discovery_renewal.py`. There are two kinds of scope, each with its own issue:

- `renewal:<Y>`: the renewal numbers of CDS year Y (one-year, two-year, and for
  the next year the early-curve check), against their floors. Earlier years are
  judged against the flat mature floor.
- `arrivals:<Y>`: how many schools gained a usable document for Y in the last
  30 days (60 in winter), against what the posting curve expects. It exists for
  the current year and the next year only.

For every scope:

- Below its floor and no open issue for it: open a new issue assigned to the
  owner and post to Discord #alerts. The renewal and arrivals issues of one
  year are separate, so a stop in arrivals is announced as its own issue even
  while the renewal issue is open.
- Below its floor and its issue is open: replace its title and body. Never
  comment, never post again (a count added to a standing issue is a log, not an
  alarm, #136), except to retry a Discord post that failed, and except when the
  issue has gone stale (next point).
- Still below after RENOTIFY_AFTER_DAYS days (renewal also: the gap to the floor
  grew by RENOTIFY_GAP_GROWTH points since it opened): supersede it. Open a new
  assigned issue, post to Discord, and close the old one with "Superseded by
  #N: still behind".
- Back above its floor and its issue is open: close it with one comment that
  states the recovered number, and post a recovery to Discord. An arrivals
  issue closes only when that year's own 30-day arrivals are back (see
  ARRIVALS_RECOVER_SHARE): a change of window or an unchecked window never
  closes it.
- A scope that is no longer tracked (a renewal year two or more cycles old, an
  arrivals year that is no longer current or next) has its issue closed with
  "No longer tracked" and never counts as outstanding.

An issue's scope is kept in a hidden marker, `alarm-scope: renewal:<Y>` or
`arrivals:<Y>`; the older `year:<Y>`, `current:<Y>` and `two_year:<Y>` markers
read as `renewal:<Y>`. If the marker is gone or edited, an arrivals title or the
year in a renewal title is used, else the current year, with a warning, so an
edit never silently re-scopes an alarm.

Issues are found by LABEL, never by title search (search lags), through the
REST issues list. Test runs use a different label and a `[test] ` title
prefix, are not assigned to anyone, and can never touch a real alarm issue.
A failed `gh` call is an error and exits nonzero: an alarm that cannot
deliver must not look like a quiet day. So is a failed Discord post when the
webhook is set, after the issue action has been done. A missing webhook is a
warning only. Either way the issue records `discord-posted: false` and a later
run retries the post.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.ops import notify_discord  # noqa: E402
from tools.ops.discovery_renewal import (  # noqa: E402
    ARRIVALS_FLOOR_SHARE,
    check_descriptor,
    lead_check,
)

ALARM_LABEL = "alarm:discovery-renewal"
TEST_LABEL = "alarm:discovery-renewal-test"
TEST_TITLE_PREFIX = "[test] "
DEFAULT_ASSIGNEE = "santhonys"
LABEL_COLOR = "D73A4A"
LABEL_DESCRIPTION = "Discovery renewal or arrivals is below its floor (one open issue per scope)"
SCOPE_RE = re.compile(r"<!-- alarm-scope: ([a-z_]+):(\d{4}-\d{2}) -->")
DISCORD_RE = re.compile(r"<!-- discord-posted: (true|false) -->")
GAP_RE = re.compile(r"<!-- alarm-gap: (-?\d+(?:\.\d+)?) -->")
# An arrivals issue closes only when that year's own 30-day count is back above
# max(ARRIVALS_RECOVER_MIN, ARRIVALS_RECOVER_SHARE x expected). The share is
# higher than the 0.4 that opens it (ARRIVALS_FLOOR_SHARE) so a count sitting on
# the boundary cannot open and close the issue every day.
ARRIVALS_RECOVER_MIN = 3
ARRIVALS_RECOVER_SHARE = 0.5
# Marker: this arrivals issue has been judged on the 60-day window. Its recovery
# then also needs the 60-day count back (the same hysteresis on that window).
WINDOW60_MARKER = "<!-- alarm-window: 60 -->"
# Written by the previous model (#499), where arrivals were part of the renewal
# issue. A renewal issue that still carries it is kept open until that year's
# arrivals recover under the current rule, unless the arrivals scope opens its
# own issue for it.
LEGACY_ARRIVALS_MARKER = "<!-- alarm-arrivals: open -->"
# A current year whose posting curve has run out cannot be checked any more
# (expected ~0 a month, so "not checked" for good); its arrivals issue is retired.
ARRIVALS_CURVE_OVER_MONTHS = 12.0
# A scope's issue that is still open and still below its floor is replaced by a
# new one (a new notification) after this many days, or (renewal) when the gap
# to the floor has grown by this many percentage points since it was opened.
RENOTIFY_AFTER_DAYS = 30
RENOTIFY_GAP_GROWTH = 5.0
TITLE_YEAR_RE = re.compile(r"\bhave (\d{4}-\d{2})\b")
ARRIVALS_TITLE_RE = re.compile(r"Almost nothing new arrived for (\d{4}-\d{2})")

Runner = Callable[[list[str]], "subprocess.CompletedProcess[str]"]
Scope = tuple[str, str]  # ("renewal" | "arrivals", CDS year)


class AlarmError(RuntimeError):
    pass


def run_gh(args: list[str]) -> subprocess.CompletedProcess[str]:
    return notify_discord.run_gh(args, os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN"))


def label_for(test_mode: bool) -> str:
    return TEST_LABEL if test_mode else ALARM_LABEL


def decide(below_floor: bool, open_issue: int | None) -> str:
    """create / update / close / none."""
    if below_floor:
        return "update" if open_issue is not None else "create"
    return "close" if open_issue is not None else "none"


def _pct0(value: Any) -> str:
    return "n/a" if value is None else f"{float(value):.0f}%"


def _pct1(value: Any) -> str:
    return "n/a" if value is None else f"{float(value):.1f}%"


def scope_marker(year: str, kind: str = "renewal") -> str:
    return f"<!-- alarm-scope: {kind}:{year} -->"


def discord_marker(posted: bool) -> str:
    return f"<!-- discord-posted: {'true' if posted else 'false'} -->"


def gap_marker(gap: float | None) -> str:
    return "" if gap is None else f"<!-- alarm-gap: {gap:.1f} -->\n"


def parse_gap(body: str | None) -> float | None:
    match = GAP_RE.search(body or "")
    return float(match.group(1)) if match else None


def gap_of(ysum: dict[str, Any]) -> float | None:
    """Points between the leading renewal check's floor and its number."""
    d = check_descriptor(ysum, lead_check(ysum) or "current")
    if d["floor"] is None or d["pct"] is None:
        return None
    return round(float(d["floor"]) - float(d["pct"]), 1)


def parse_created(issue: dict[str, Any]) -> datetime | None:
    raw = str(issue.get("created_at") or "")
    if not raw:
        return None
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def age_days(issue: dict[str, Any], now: datetime) -> int | None:
    created = parse_created(issue)
    return None if created is None else (now - created).days


def stale_reason(issue: dict[str, Any], ysum: dict[str, Any], now: datetime) -> str | None:
    """Why a still-open, still-short renewal issue should be replaced by a new
    one: old enough, or the gap grew. None when it should only be updated."""
    days = age_days(issue, now)
    gap_now, gap_then = gap_of(ysum), parse_gap(issue.get("body"))
    if days is not None and days >= RENOTIFY_AFTER_DAYS:
        if gap_now is not None and gap_then is not None:
            return f"still behind (gap {gap_then:.1f}→{gap_now:.1f} points)"
        return f"still behind after {days} days"
    if gap_now is not None and gap_then is not None and gap_now - gap_then >= RENOTIFY_GAP_GROWTH:
        return f"still behind (gap {gap_then:.1f}→{gap_now:.1f} points)"
    return None


def arrivals_stale_reason(issue: dict[str, Any], now: datetime) -> str | None:
    days = age_days(issue, now)
    if days is not None and days >= RENOTIFY_AFTER_DAYS:
        return f"still behind after {days} days"
    return None


def parse_scope(body: str | None) -> Scope | None:
    """(kind, year) from the marker; the older `year:`, `current:` and
    `two_year:` markers are renewal scopes."""
    match = SCOPE_RE.search(body or "")
    if not match:
        return None
    kind = "arrivals" if match.group(1) == "arrivals" else "renewal"
    return kind, match.group(2)


def discord_posted(body: str | None) -> bool:
    """False only when the issue says its alarm post did not go out."""
    match = DISCORD_RE.search(body or "")
    return match is None or match.group(1) == "true"


def issue_scope(issue: dict[str, Any], current_year: str) -> tuple[Scope, str | None]:
    """((kind, year), legacy marker kind) an open alarm issue is about. A missing
    or edited marker falls back to the title, else the current year's renewal
    scope, with a warning: it must never re-scope the alarm silently."""
    scope = parse_scope(issue.get("body"))
    if scope is not None:
        match = SCOPE_RE.search(issue.get("body") or "")
        return scope, match.group(1) if match else None
    title = str(issue.get("title") or "")
    arrivals = ARRIVALS_TITLE_RE.search(title)
    if arrivals:
        found: Scope = ("arrivals", arrivals.group(1))
        where = "its title"
    else:
        title_year = TITLE_YEAR_RE.search(title)
        found = ("renewal", title_year.group(1) if title_year else current_year)
        where = "its title" if title_year else "the current year"
    print(
        f"::warning::alarm issue #{issue['number']} has no readable alarm-scope marker; "
        f"treating it as {found[0]}:{found[1]} (from {where})",
        file=sys.stderr,
    )
    return found, None


def retired_comment(ysum: dict[str, Any] | None) -> str:
    if ysum is None:
        figures = "final numbers are no longer computed"
    else:
        one = check_descriptor(ysum, "current")
        two = check_descriptor(ysum, "two_year")
        figures = f"final one-year {_pct1(one['pct'])}, two-year {_pct1(two['pct'])}"
    return f"No longer tracked: {figures}; lapsed schools stay in the two-year check."


def issue_title(ysum: dict[str, Any], *, test_mode: bool) -> str:
    d = check_descriptor(ysum, lead_check(ysum) or "current")
    title = (
        f"Discovery is behind: {_pct0(d['pct'])} of schools with {d['prev']} "
        f"have {d['year']} (floor {_pct0(d['floor'])})"
    )
    return (TEST_TITLE_PREFIX if test_mode else "") + title


def recovery_comment(ysum: dict[str, Any], kind: str = "current") -> str:
    d = check_descriptor(ysum, kind)
    other = check_descriptor(ysum, "two_year" if kind == "current" else "current")
    other_text = (
        f" The {other['name']} check is {_pct1(other['pct'])}"
        + ("" if other["floor"] is None else f" (floor {_pct1(other['floor'])})")
        + "."
    )
    return (
        f"Recovered: the {d['name']} check for {d['year']} is {d['renewed']} of {d['total']} "
        f"({_pct1(d['pct'])}) of schools with {d['prev']} having {d['year']}, "
        f"floor {_pct1(d['floor'])}.{other_text} Closing."
    )


def discord_alert(ysum: dict[str, Any], issue_url: str | None, *, test_mode: bool) -> dict[str, Any]:
    d = check_descriptor(ysum, lead_check(ysum) or "current")
    return {
        "title": issue_title(ysum, test_mode=test_mode),
        "fields": [
            ("Check", d["name"]),
            ("Renewal", f"{d['renewed']} of {d['total']} ({_pct1(d['pct'])})"),
            ("Floor", _pct1(d["floor"])),
            ("Years", f"{d['prev']} to {d['year']}"),
            ("Issue", issue_url or "—"),
        ],
        "url": issue_url,
        "recovered": False,
    }


def discord_recovery(
    ysum: dict[str, Any], issue_url: str | None, kind: str, *, test_mode: bool
) -> dict[str, Any]:
    d = check_descriptor(ysum, kind)
    return {
        "title": (TEST_TITLE_PREFIX if test_mode else "")
        + f"Discovery renewal recovered: {d['name']} {_pct1(d['pct'])} "
        + f"of schools with {d['prev']} have {d['year']}",
        "fields": [
            ("Check", d["name"]),
            ("Renewal", f"{d['renewed']} of {d['total']}"),
            ("Floor", _pct1(d["floor"])),
            ("Issue", issue_url or "—"),
        ],
        "url": issue_url,
        "recovered": True,
    }


# ---------------------------------------------------------------- arrivals scope


def arrivals_recovered(a: dict[str, Any], *, sixty: bool = False) -> bool:
    """True when the year's own 30-day arrivals are back above
    max(3, ARRIVALS_RECOVER_SHARE x expected_30). The 30-day figures are always
    required, so a window switch or an unchecked window never closes an arrivals
    issue. When the issue has been judged on the 60-day window (`sixty`), the
    60-day count must also be back above max(3, ARRIVALS_RECOVER_SHARE x
    expected_60), so a count sitting on that window's boundary cannot open and
    close it daily."""
    back_30 = a["count_30"] >= max(ARRIVALS_RECOVER_MIN, ARRIVALS_RECOVER_SHARE * float(a["expected_30"]))
    if not sixty:
        return back_30
    back_60 = a["count_60"] >= max(ARRIVALS_RECOVER_MIN, ARRIVALS_RECOVER_SHARE * float(a["expected_60"]))
    return back_30 and back_60


def arrivals_passed_its_curve(a: dict[str, Any]) -> bool:
    """The current year is past its posting curve and can no longer be judged."""
    return (
        a.get("checked") is not True
        and float(a.get("months_since_fall", 0.0)) >= ARRIVALS_CURVE_OVER_MONTHS
    )


def arrivals_figures(a: dict[str, Any], *, holding: bool) -> tuple[int, int, int]:
    """(arrived, expected rounded, window days) for words. Held with the flag
    off: the 30-day figures."""
    window = 30 if holding else int(a["window_days"])
    return int(a[f"count_{window}"]), round(float(a[f"expected_{window}"])), window


def arrivals_title(year: str, a: dict[str, Any], *, holding: bool, test_mode: bool) -> str:
    arrived, expected, window = arrivals_figures(a, holding=holding)
    return (TEST_TITLE_PREFIX if test_mode else "") + (
        f"Almost nothing new arrived for {year}: {arrived} schools in {window} days "
        f"(expected {expected})"
    )


def arrivals_alert(
    year: str, a: dict[str, Any], issue_url: str | None, *, holding: bool, test_mode: bool
) -> dict[str, Any]:
    arrived, expected, window = arrivals_figures(a, holding=holding)
    return {
        "title": arrivals_title(year, a, holding=holding, test_mode=test_mode),
        "fields": [
            ("Check", "arrivals"),
            ("Arrived", f"{arrived} in {window} days, about {expected} expected"),
            ("Year", year),
            ("Issue", issue_url or "—"),
        ],
        "url": issue_url,
        "recovered": False,
    }


def arrivals_recovery_comment(year: str, a: dict[str, Any]) -> str:
    need = max(ARRIVALS_RECOVER_MIN, ARRIVALS_RECOVER_SHARE * float(a["expected_30"]))
    return (
        f"Recovered: {a['count_30']} schools gained a {year} document in the last 30 days "
        f"(at least {need:.0f} needed, with about {float(a['expected_30']):.0f} expected). Closing."
    )


def arrivals_recovery(year: str, a: dict[str, Any], issue_url: str | None, *, test_mode: bool) -> dict[str, Any]:
    return {
        "title": (TEST_TITLE_PREFIX if test_mode else "")
        + f"Discovery arrivals recovered for {year}: {a['count_30']} schools in 30 days",
        "fields": [("Check", "arrivals"), ("Year", year), ("Issue", issue_url or "—")],
        "url": issue_url,
        "recovered": True,
    }


def arrivals_hold_note(year: str, a: dict[str, Any], *, sixty: bool = False) -> str:
    need = max(ARRIVALS_RECOVER_MIN, ARRIVALS_RECOVER_SHARE * float(a["expected_30"]))
    extra = (
        f" and {max(ARRIVALS_RECOVER_MIN, ARRIVALS_RECOVER_SHARE * float(a['expected_60'])):.0f} in "
        "the last 60 days (it was judged on the 60-day window)" if sixty else ""
    )
    return (
        f"Arrivals for {year} are not back yet: {a['count_30']} schools in the last 30 days; "
        f"this issue stays open until at least {need:.0f} (the larger of {ARRIVALS_RECOVER_MIN} and "
        f"{ARRIVALS_RECOVER_SHARE:.0%} of the expected 30-day arrivals){extra}, whatever window the "
        "check is using.\n\n"
    )


def _gh(runner: Runner, args: list[str]) -> str:
    done = runner(args)
    if done.returncode != 0:
        raise AlarmError(f"gh {' '.join(args[:2])} failed: {(done.stderr or '').strip()[:300]}")
    return done.stdout or ""


def find_open_issues(repo: str, label: str, runner: Runner) -> list[dict[str, Any]]:
    """Open issues carrying `label`, oldest first, found by label (never by
    title). The REST issues list is used instead of `gh issue list --label`,
    which goes through search and lags behind a just-created issue. It also
    returns pull requests, which are dropped."""
    out = _gh(
        runner,
        ["api", "-X", "GET", f"repos/{repo}/issues", "-f", f"labels={label}",
         "-f", "state=open", "-f", "per_page=50"],
    )
    try:
        rows = json.loads(out or "[]")
    except json.JSONDecodeError as exc:
        raise AlarmError("could not parse the gh issues list") from exc
    if not isinstance(rows, list):
        raise AlarmError("gh issues list did not return a list")
    issues = [
        {"number": int(r["number"]), "title": r.get("title", ""),
         "url": r.get("html_url") or r.get("url"), "body": r.get("body") or "",
         "created_at": r.get("created_at") or ""}
        for r in rows
        if "pull_request" not in r
    ]
    return sorted(issues, key=lambda r: r["number"])


def ensure_label(repo: str, label: str, runner: Runner) -> None:
    # Already existing is fine; any other failure surfaces when the issue is created.
    runner(["label", "create", label, "--repo", repo, "--color", LABEL_COLOR,
            "--description", LABEL_DESCRIPTION])


def parse_issue_number(gh_output: str) -> int:
    last = gh_output.strip().splitlines()[-1] if gh_output.strip() else ""
    tail = last.rstrip("/").rsplit("/", 1)[-1]
    if "/issues/" not in last or not tail.isdigit():
        raise AlarmError(f"could not read the new issue number from {last!r}")
    return int(tail)


def _with_body_file(body: str, fn: Callable[[str], str]) -> str:
    with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False, encoding="utf-8") as fh:
        fh.write(body)
        path = fh.name
    try:
        return fn(path)
    finally:
        Path(path).unlink(missing_ok=True)


def build_body(
    report: str, scope: Scope, posted: bool, gap: float | None = None, sixty: bool = False,
    legacy_arrivals: bool = False,
) -> str:
    kind, year = scope
    return (
        report.rstrip("\n")
        + f"\n\n{scope_marker(year, kind)}\n{discord_marker(posted)}\n{gap_marker(gap)}"
        + (f"{WINDOW60_MARKER}\n" if sixty else "")
        + (f"{LEGACY_ARRIVALS_MARKER}\n" if legacy_arrivals else "")
    )


def format_next(year: str) -> str:
    start = int(year[:4]) + 1
    return f"{start}-{(start + 1) % 100:02d}"


def _retire(scope: Scope, current_start: int) -> bool:
    """A renewal year two or more cycles old, or an arrivals year that is no
    longer the current or next one, is no longer tracked. Some years never
    reached the flat mature floor (2023-24 sat at 82.9%), and an issue that can
    never close would hold the board lamp down for good."""
    kind, year = scope
    start = int(year[:4])
    return start < current_start - 1 if kind == "renewal" else start < current_start


def act(
    *,
    years: dict[str, dict[str, Any]],
    reports: dict[str, str],
    current_year: str,
    repo: str,
    test_mode: bool,
    dry_run: bool,
    assignee: str,
    runner: Runner,
    arrivals: dict[str, dict[str, Any]] | None = None,
    fallback_report: str = "",
    discord: Callable[..., bool] = notify_discord.post_custom_embed,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Do (or, in a dry run, print) what each scope calls for.

    Returns {"actions": [{scope, year, action, issue}], "issue": <the alarm
    issue number afterwards: the current year's renewal issue, else the newest>,
    "discord_failed"}.
    """
    arrivals = arrivals or {}
    label = label_for(test_mode)
    now = now or datetime.now(timezone.utc)
    issues = find_open_issues(repo, label, runner)
    if test_mode:
        for existing in issues:
            if not str(existing.get("title", "")).startswith(TEST_TITLE_PREFIX):
                raise AlarmError(
                    f"issue #{existing['number']} carries {label} but is not a test issue; "
                    "refusing to touch it"
                )
    by_scope: dict[Scope, list[dict[str, Any]]] = {}
    legacy_kind: dict[int, str | None] = {}
    for issue in issues:
        scope, kind = issue_scope(issue, current_year)
        by_scope.setdefault(scope, []).append(issue)
        legacy_kind[issue["number"]] = kind
    # Only the current year and the next one can open an alarm. An earlier
    # renewal year is evaluated only to decide whether an issue that is already
    # open for it recovers.
    current_start = int(current_year[:4])
    breaching: set[Scope] = {
        ("renewal", y) for y, ys in years.items()
        if int(y[:4]) >= current_start and lead_check(ys) is not None
    } | {
        ("arrivals", y) for y, a in arrivals.items()
        if int(y[:4]) >= current_start and a.get("below_floor") is True
    }
    prefix = "[dry run] " if dry_run else ""
    discord_failed = False

    def send(payload: dict[str, Any]) -> str:
        """posted / skipped (no webhook) / failed."""
        nonlocal discord_failed
        try:
            if dry_run:
                discord(**payload, dry_run=True)
                return "posted"
            return "posted" if discord(**payload, raise_on_failure=True) else "skipped"
        except notify_discord.DiscordPostError as exc:
            discord_failed = True
            print(f"::error::Discord post failed after the issue action: {exc}", file=sys.stderr)
            return "failed"

    def close(issue_number: int, comment: str) -> None:
        _gh(runner, ["issue", "close", str(issue_number), "--repo", repo, "--comment", comment])

    actions: list[dict[str, Any]] = []
    open_after: dict[Scope, int] = {}

    def record(scope: Scope, action: str, issue_number: int | None) -> None:
        actions.append({"scope": scope[0], "year": scope[1], "action": action, "issue": issue_number})
        if issue_number is not None and action in ("create", "renotify", "update", "skip"):
            open_after[scope] = issue_number

    for scope in sorted(set(by_scope) | breaching):
        kind, year = scope
        open_list = by_scope.get(scope, [])
        active = open_list[-1] if open_list else None
        older = open_list[:-1]
        number = active["number"] if active else None
        ysum = years.get(year) if kind == "renewal" else None
        a = arrivals.get(year) if kind == "arrivals" else None
        name = f"{kind}:{year}"

        passed_curve = (
            kind == "arrivals" and a is not None and year == current_year
            and arrivals_passed_its_curve(a)
        )
        if open_list and (passed_curve or _retire(scope, current_start)):
            if passed_curve:
                next_year = format_next(year)
                comment = (
                    f"No longer checked: {year} has passed its posting curve; "
                    f"arrivals:{next_year} and renewal:{year} keep watching."
                )
            elif kind == "renewal":
                comment = retired_comment(ysum)
            else:
                comment = (f"No longer tracked: arrivals are checked for {current_year} and the "
                           "next year only.")
            print(f"{prefix}alarm {name}: retire (no longer tracked)")
            if dry_run:
                print(f"{prefix}would close #{number} with the comment: {comment}")
            else:
                for old in open_list:
                    close(old["number"], comment)
                    print(f"closed issue #{old['number']} (no longer tracked)")
            send({
                "title": (TEST_TITLE_PREFIX if test_mode else "")
                + f"Discovery {kind}: {year} is no longer tracked",
                "fields": [("Year", year), ("Issue", (active or {}).get("url") or "—")],
                "url": (active or {}).get("url"),
                "recovered": True,
            })
            record(scope, "retire", None)
            continue
        if (kind == "renewal" and ysum is None) or (kind == "arrivals" and a is None):
            print(f"::warning::open alarm issue(s) for {name}, which is outside the evaluated "
                  "scopes; left untouched", file=sys.stderr)
            record(scope, "skip", number)
            continue

        # What differs between the two scopes, in one place.
        holding = False
        sixty = False
        legacy_hold = False
        if kind == "arrivals":
            below_now = a.get("below_floor") is True
            # Held open by this year's own recovery rule, not by the flag.
            # Both windows are judged; the 60-day one must also be back once it has been
            # judged for this issue (it can be checked now, or have been before).
            sixty = bool(a.get("checked_60")) or (active is not None and WINDOW60_MARKER in active["body"])
            holding = active is not None and not below_now and not arrivals_recovered(a, sixty=sixty)
            below = below_now or holding
            if passed_curve:
                below = False  # nothing is open for it (retired above) and nothing can open
            title = arrivals_title(year, a, holding=holding, test_mode=test_mode)
            alert = lambda url: arrivals_alert(  # noqa: E731
                year, a, url, holding=holding, test_mode=test_mode)
            recovery_text = arrivals_recovery_comment(year, a)
            recovery = lambda url: arrivals_recovery(year, a, url, test_mode=test_mode)  # noqa: E731
            report = reports.get(f"arrivals:{year}") or fallback_report
            if holding:
                report = arrivals_hold_note(year, a, sixty=sixty) + report
            gap = None
        else:
            below = lead_check(ysum) is not None
            # An older renewal issue that carries the arrivals-held marker stays
            # open until that year's arrivals recover, unless the arrivals scope
            # has opened its own issue for the year (then this one can close).
            arr_now = arrivals.get(year)
            legacy_hold = (
                active is not None
                and LEGACY_ARRIVALS_MARKER in active["body"]
                and arr_now is not None
                and arr_now.get("below_floor") is not True
                and not arrivals_recovered(
                    arr_now, sixty=bool(arr_now.get("checked_60")) or WINDOW60_MARKER in active["body"])
            )
            below = below or legacy_hold
            title = issue_title(ysum, test_mode=test_mode)
            alert = lambda url: discord_alert(ysum, url, test_mode=test_mode)  # noqa: E731
            old_kind = legacy_kind.get(number)
            old_kind = old_kind if old_kind in ("current", "two_year") else "current"
            recovery_text = recovery_comment(ysum, old_kind)
            recovery = lambda url: discord_recovery(  # noqa: E731
                ysum, url, old_kind, test_mode=test_mode)
            report = reports.get(year) or fallback_report
            if legacy_hold:
                report = arrivals_hold_note(year, arr_now) + report
            gap = gap_of(ysum)

        action = decide(below, number)
        renotify_reason = None
        if action == "update":
            renotify_reason = (
                arrivals_stale_reason(active, now) if kind == "arrivals"
                else stale_reason(active, ysum, now)
            )
            if renotify_reason:
                action = "renotify"
        print(f"{prefix}alarm {name}: {action} (below_floor={below}, open issue={number}, "
              f"label={label})")

        if action == "none":
            record(scope, action, None)
            continue

        if action in ("create", "renotify"):
            if dry_run:
                who = "none (test)" if test_mode else assignee
                extra = (f"\n  would close #{number} as superseded: {renotify_reason}"
                         if action == "renotify" else "")
                print(f"{prefix}would create issue: {title}\n  label={label} assignee={who}{extra}\n{report}")
                send(alert(None))
                record(scope, action, None)
                continue
            ensure_label(repo, label, runner)
            assign = [] if test_mode else ["--assignee", assignee]
            out = _with_body_file(build_body(report, scope, False, gap, sixty, legacy_hold), lambda path: _gh(
                runner, ["issue", "create", "--repo", repo, "--title", title,
                         "--body-file", path, "--label", label, *assign]))
            new_number = parse_issue_number(out)
            url = out.strip().splitlines()[-1]
            print(f"opened issue #{new_number} for {name}")
            if action == "renotify":
                for old in open_list:
                    close(old["number"], f"Superseded by #{new_number}: {renotify_reason}.")
                    print(f"closed issue #{old['number']} as superseded ({renotify_reason})")
            if send(alert(url)) == "posted":
                _with_body_file(build_body(report, scope, True, gap, sixty, legacy_hold), lambda path: _gh(
                    runner, ["issue", "edit", str(new_number), "--repo", repo,
                             "--body-file", path]))
            record(scope, action, new_number)
            continue

        if action == "update":
            posted = discord_posted(active["body"])
            retry = not posted
            if dry_run:
                print(f"{prefix}would replace the title and body of #{number} (no comment"
                      + (", retry the Discord post" if retry else ", no Discord post")
                      + f"): {title}\n{report}")
                if retry:
                    send(alert(active.get("url")))
                record(scope, action, number)
                continue
            if retry:
                posted = send(alert(active.get("url"))) == "posted"
            # The gap recorded when the issue was opened stays: it is what the
            # growth since then is measured against.
            gap_at_open = parse_gap(active["body"])
            if gap_at_open is None:
                gap_at_open = gap
            _with_body_file(
                build_body(report, scope, posted, gap_at_open, sixty, legacy_hold),
                lambda path: _gh(
                    runner, ["issue", "edit", str(number), "--repo", repo, "--title", title,
                             "--body-file", path]))
            print(f"updated issue #{number}")
            for old in older:
                close(old["number"], f"Superseded by #{number}.")
                print(f"closed duplicate issue #{old['number']}")
            record(scope, action, number)
            continue

        # close: this scope is back above its floors
        if dry_run:
            print(f"{prefix}would close #{number} with the comment: {recovery_text}")
            send(recovery(active.get("url")))
            record(scope, action, None)
            continue
        for old in open_list:
            close(old["number"], recovery_text if old is active else f"Superseded by #{number}; recovered.")
            print(f"closed issue #{old['number']}")
        send(recovery(active.get("url")))
        record(scope, action, None)

    if ("renewal", current_year) in open_after:
        alarm_issue: int | None = open_after[("renewal", current_year)]
    else:
        renewals = {s: n for s, n in open_after.items() if s[0] == "renewal"}
        pool = renewals or open_after
        alarm_issue = pool[max(pool)] if pool else None
    return {"actions": actions, "issue": alarm_issue, "discord_failed": discord_failed}


def outstanding(outcome: dict[str, Any]) -> tuple[bool, str]:
    """(any alarm outstanding, comma-separated CDS years still short): every
    year with an alarm issue, of either scope, open after this run, including
    an earlier year that is no longer the current or next one. Retired scopes
    never count."""
    years = sorted({
        a["year"] for a in outcome["actions"]
        if a["action"] in ("create", "renotify", "update", "skip")
    })
    return bool(years), ",".join(years)


def arrivals_years(outcome: dict[str, Any]) -> str:
    """The years with an open or new arrivals issue."""
    return ",".join(sorted({
        a["year"] for a in outcome["actions"]
        if a.get("scope") == "arrivals" and a["action"] in ("create", "renotify", "update", "skip")
    }))


def real_outstanding(
    years: dict[str, dict[str, Any]],
    arrivals: dict[str, dict[str, Any]],
    current_year: str,
    repo: str,
    runner: Runner,
) -> tuple[bool, str, str]:
    """Outstanding years for the heartbeat in a test-mode run: the REAL alarm
    label's open issues (a read-only list), plus the current and next scopes
    that are below their floors now. A test run opens test issues only, so
    without this it would report "nothing outstanding" and turn a lamp that is
    really down green. Retired scopes never count."""
    current_start = int(current_year[:4])
    found: set[str] = set()
    found_arrivals: set[str] = set()
    for issue_ in find_open_issues(repo, ALARM_LABEL, runner):
        scope, _ = issue_scope(issue_, current_year)
        if _retire(scope, current_start):
            continue
        found.add(scope[1])
        if scope[0] == "arrivals":
            found_arrivals.add(scope[1])
    for year, ysum in years.items():
        if int(year[:4]) >= current_start and lead_check(ysum) is not None:
            found.add(year)
    for year, a in arrivals.items():
        if int(year[:4]) >= current_start and a.get("below_floor") is True:
            found.add(year)
            found_arrivals.add(year)
    ordered = sorted(found)
    return bool(ordered), ",".join(ordered), ",".join(sorted(found_arrivals))


def main(argv: list[str] | None = None, *, runner: Runner = run_gh) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state", type=Path, required=True, help="out-state JSON from discovery_renewal.py")
    parser.add_argument("--report", type=Path, required=True,
                        help="fallback issue body markdown (used when a scope has no report of its own)")
    parser.add_argument("--year-reports", type=Path,
                        help="directory of <year>.md renewal bodies and arrivals-<year>.md arrivals bodies")
    parser.add_argument("--summary", type=Path, required=True,
                        help="heartbeat summary JSON; rewritten with alarm_issue")
    parser.add_argument("--repo", default=os.environ.get("GITHUB_REPOSITORY") or "bolewood/quadfile")
    parser.add_argument("--assignee", default=DEFAULT_ASSIGNEE)
    parser.add_argument("--test-mode", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    try:
        state = json.loads(args.state.read_text(encoding="utf-8"))
        summary = json.loads(args.summary.read_text(encoding="utf-8"))
        fallback = args.report.read_text(encoding="utf-8")
        years = state.get("years")
        if not isinstance(years, dict) or not years:
            raise AlarmError("state has no per-year checks")
        arrivals = state.get("arrivals")
        if arrivals is None:
            arrivals = {}
        if not isinstance(arrivals, dict):
            raise AlarmError("state arrivals is not an object")
        reports: dict[str, str] = {}
        if args.year_reports and args.year_reports.is_dir():
            for path in args.year_reports.glob("*.md"):
                stem = path.stem
                key = "arrivals:" + stem[len("arrivals-"):] if stem.startswith("arrivals-") else stem
                reports[key] = path.read_text(encoding="utf-8")
        current_year = str(state.get("current_year") or summary["current_year"])
        outcome = act(
            years=years,
            arrivals=arrivals,
            reports=reports,
            current_year=current_year,
            repo=args.repo,
            test_mode=args.test_mode,
            dry_run=args.dry_run,
            assignee=args.assignee,
            runner=runner,
            fallback_report=fallback,
        )
    except (AlarmError, OSError, json.JSONDecodeError, KeyError) as exc:
        print(f"::error::renewal alarm: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    if not args.dry_run:
        # A test issue is not the alarm: keep it out of the heartbeat summary.
        summary["alarm_issue"] = None if args.test_mode else outcome["issue"]
        # The heartbeat must show an earlier year that is still short even
        # when the current and next year are healthy.
        if args.test_mode:
            # Never derived from the test label's issues: a test dispatch must
            # not flip the real lamp.
            (summary["outstanding_below_floor"], summary["outstanding_years"],
             summary["arrivals_years"]) = real_outstanding(
                years, arrivals, current_year, args.repo, runner)
        else:
            summary["outstanding_below_floor"], summary["outstanding_years"] = outstanding(outcome)
            summary["arrivals_years"] = arrivals_years(outcome)
        args.summary.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    # The issue action is done; a Discord delivery failure still fails the job
    # (which posts through workflow_run).
    return 1 if outcome["discord_failed"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
