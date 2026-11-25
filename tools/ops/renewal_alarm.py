#!/usr/bin/env python3
"""Open, update and close the discovery-renewal alarm issues, one per CDS year.

Reads the state (and the per-year issue bodies) written by
`discovery_renewal.py`. Each CDS year has its own checks: the one-year and
two-year renewal of the current year, the early-curve check of the next year,
and the flat mature floors of earlier years. For every year:

- Below its floor and no open issue for that year: open a new issue assigned
  to the owner and post to Discord #alerts. A next-year breach opens its own
  issue even while the current year's issue is open.
- Below its floor and an issue for that year is open: replace its title and
  body. Never comment, never post again (a count added to a standing issue is a
  log, not an alarm, #136), except to retry a Discord post that failed, and
  except when the issue has gone stale (below).
- Still below its floor after RENOTIFY_AFTER_DAYS days, or after the gap to the
  floor has grown by RENOTIFY_GAP_GROWTH points since the issue was opened:
  supersede it. Open a new assigned issue, post to Discord, and close the old
  one with "Superseded by #N: still behind". Without this, one issue opened in
  April would be the only notification for a gap that grew for seven months.
- Back above its floor and an issue for that year is open: close it with one
  comment that states the recovered number, and post a recovery to Discord.
  The September switch never closes an earlier year's issue: that year is
  judged on its own numbers against the flat mature floor.
- Above its floor and no issue: nothing.

An issue's year is kept in a hidden marker, `alarm-scope: year:<Y>`. If the
marker is gone or edited, the year in the issue's title is used, else the
current year, with a warning, so an edit never silently re-scopes an alarm.

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
from tools.ops.discovery_renewal import check_descriptor, lead_check  # noqa: E402

ALARM_LABEL = "alarm:discovery-renewal"
TEST_LABEL = "alarm:discovery-renewal-test"
TEST_TITLE_PREFIX = "[test] "
DEFAULT_ASSIGNEE = "santhonys"
LABEL_COLOR = "D73A4A"
LABEL_DESCRIPTION = "Discovery renewal is below its floor (one open issue per CDS year)"
# `year:2025-26`; the older `current:2025-26` / `two_year:2025-26` format is
# read as a match on its year.
SCOPE_RE = re.compile(r"<!-- alarm-scope: ([a-z_]+):(\d{4}-\d{2}) -->")
DISCORD_RE = re.compile(r"<!-- discord-posted: (true|false) -->")
GAP_RE = re.compile(r"<!-- alarm-gap: (-?\d+(?:\.\d+)?) -->")
# A year's issue that is still open and still below its floor is replaced by a
# new one (a new notification) after this many days, or when the gap to the
# floor has grown by this many percentage points since it was opened.
RENOTIFY_AFTER_DAYS = 30
RENOTIFY_GAP_GROWTH = 5.0
TITLE_YEAR_RE = re.compile(r"\bhave (\d{4}-\d{2})\b")

Runner = Callable[[list[str]], "subprocess.CompletedProcess[str]"]


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


def scope_marker(year: str) -> str:
    return f"<!-- alarm-scope: year:{year} -->"


def discord_marker(posted: bool) -> str:
    return f"<!-- discord-posted: {'true' if posted else 'false'} -->"


def gap_marker(gap: float | None) -> str:
    return "" if gap is None else f"<!-- alarm-gap: {gap:.1f} -->\n"


def parse_gap(body: str | None) -> float | None:
    match = GAP_RE.search(body or "")
    return float(match.group(1)) if match else None


def gap_of(ysum: dict[str, Any]) -> float | None:
    """Points between the leading check's floor and its number: how far behind.
    None for the arrivals check, which has no percentage."""
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


def stale_reason(
    issue: dict[str, Any], ysum: dict[str, Any], now: datetime
) -> str | None:
    """Why a still-open, still-short issue should be replaced by a new one:
    old enough, or the gap grew. None when it should only be updated."""
    created = parse_created(issue)
    if created is not None and (now - created).days >= RENOTIFY_AFTER_DAYS:
        gap_now, gap_then = gap_of(ysum), parse_gap(issue.get("body"))
        if gap_now is not None and gap_then is not None:
            return f"still behind (gap {gap_then:.1f}\u2192{gap_now:.1f} points)"
        return f"still behind after {(now - created).days} days"
    gap_now, gap_then = gap_of(ysum), parse_gap(issue.get("body"))
    if gap_now is not None and gap_then is not None and gap_now - gap_then >= RENOTIFY_GAP_GROWTH:
        return f"still behind (gap {gap_then:.1f}\u2192{gap_now:.1f} points)"
    return None


def parse_scope(body: str | None) -> tuple[str, str] | None:
    match = SCOPE_RE.search(body or "")
    return (match.group(1), match.group(2)) if match else None


def discord_posted(body: str | None) -> bool:
    """False only when the issue says its alarm post did not go out."""
    match = DISCORD_RE.search(body or "")
    return match is None or match.group(1) == "true"


def issue_year(issue: dict[str, Any], current_year: str) -> tuple[str, str | None]:
    """(CDS year, legacy kind) an open alarm issue is about. A missing or
    edited marker falls back to the year in the title, else the current year,
    with a warning: it must never re-scope the alarm silently."""
    scope = parse_scope(issue.get("body"))
    if scope is not None:
        return scope[1], scope[0]
    title_year = TITLE_YEAR_RE.search(str(issue.get("title") or ""))
    year = title_year.group(1) if title_year else current_year
    where = "its title" if title_year else "the current year"
    print(
        f"::warning::alarm issue #{issue['number']} has no readable alarm-scope marker; "
        f"treating it as {year} (from {where})",
        file=sys.stderr,
    )
    return year, None


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
    if d["kind"] == "arrivals":
        title = (
            f"Discovery is behind: only {d['renewed']} schools gained a {d['year']} or later "
            f"document in 30 days (expected about {d['total']})"
        )
    else:
        title = (
            f"Discovery is behind: {_pct0(d['pct'])} of schools with {d['prev']} "
            f"have {d['year']} (floor {_pct0(d['floor'])})"
        )
    return (TEST_TITLE_PREFIX if test_mode else "") + title


def recovery_comment(ysum: dict[str, Any], kind: str = "current") -> str:
    kind = "current" if kind == "arrivals" else kind
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
    renewal_text = (
        f"{d['renewed']} arrived, about {d['total']} expected"
        if d["kind"] == "arrivals"
        else f"{d['renewed']} of {d['total']} ({_pct1(d['pct'])})"
    )
    return {
        "title": issue_title(ysum, test_mode=test_mode),
        "fields": [
            ("Check", d["name"]),
            ("Renewal", renewal_text),
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


def build_body(report: str, year: str, posted: bool, gap: float | None = None) -> str:
    return (
        report.rstrip("\n")
        + f"\n\n{scope_marker(year)}\n{discord_marker(posted)}\n{gap_marker(gap)}"
    )


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
    fallback_report: str = "",
    discord: Callable[..., bool] = notify_discord.post_custom_embed,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Do (or, in a dry run, print) what each year calls for.

    Returns {"actions": [{year, action, issue}], "issue": <alarm issue number
    afterwards: the current year's, else the newest year's>, "discord_failed"}.
    """
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
    by_year: dict[str, list[dict[str, Any]]] = {}
    legacy_kind: dict[int, str | None] = {}
    for issue in issues:
        year, kind = issue_year(issue, current_year)
        by_year.setdefault(year, []).append(issue)
        legacy_kind[issue["number"]] = kind
    # Only the current year and the next one can open an alarm. An earlier year
    # is judged by the flat mature floor, which some years never reached (2023-24
    # held at about 82%); it is evaluated only to decide whether an issue that
    # is already open for it recovers.
    current_start = int(current_year[:4])
    breaching = {
        y for y, ys in years.items()
        if int(y[:4]) >= current_start and lead_check(ys) is not None
    }
    # A year two or more cycles old is no longer tracked. Some years never
    # reached the flat mature floor (2023-24 sat at 82.9%), and an issue that can
    # never close would hold the board lamp down for good.
    retired_before = current_start - 1  # years <= current - 2
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
    open_after: dict[str, int] = {}

    for year in sorted(set(by_year) | breaching):
        ysum = years.get(year)
        open_list = by_year.get(year, [])
        active = open_list[-1] if open_list else None
        older = open_list[:-1]
        number = active["number"] if active else None
        if open_list and int(year[:4]) < retired_before:
            comment = retired_comment(ysum)
            print(f"{prefix}alarm {year}: retire (no longer tracked)")
            if dry_run:
                print(f"{prefix}would close #{number} with the comment: {comment}")
            else:
                for old in open_list:
                    close(old["number"], comment)
                    print(f"closed issue #{old['number']} (no longer tracked)")
            send({
                "title": (TEST_TITLE_PREFIX if test_mode else "")
                + f"Discovery renewal: {year} is no longer tracked",
                "fields": [("Year", year), ("Issue", (active or {}).get("url") or "—")],
                "url": (active or {}).get("url"),
                "recovered": True,
            })
            actions.append({"year": year, "action": "retire", "issue": None})
            continue
        if ysum is None:
            print(f"::warning::open alarm issue(s) for {year}, which is outside the evaluated "
                  "years; left untouched", file=sys.stderr)
            if number is not None:
                open_after[year] = number
            actions.append({"year": year, "action": "skip", "issue": number})
            continue
        below = lead_check(ysum) is not None
        action = decide(below, number)
        renotify_reason = None
        if action == "update":
            renotify_reason = stale_reason(active, ysum, now)
            if renotify_reason:
                action = "renotify"
        print(f"{prefix}alarm {year}: {action} (below_floor={below}, open issue={number}, "
              f"label={label})")
        report = reports.get(year) or fallback_report

        if action == "none":
            actions.append({"year": year, "action": action, "issue": None})
            continue

        if action in ("create", "renotify"):
            title = issue_title(ysum, test_mode=test_mode)
            gap = gap_of(ysum)
            if dry_run:
                who = "none (test)" if test_mode else assignee
                extra = (f"\n  would close #{number} as superseded: {renotify_reason}"
                         if action == "renotify" else "")
                print(f"{prefix}would create issue: {title}\n  label={label} assignee={who}{extra}\n{report}")
                send(discord_alert(ysum, None, test_mode=test_mode))
                actions.append({"year": year, "action": action, "issue": None})
                continue
            ensure_label(repo, label, runner)
            assign = [] if test_mode else ["--assignee", assignee]
            out = _with_body_file(build_body(report, year, False, gap), lambda path: _gh(
                runner, ["issue", "create", "--repo", repo, "--title", title,
                         "--body-file", path, "--label", label, *assign]))
            new_number = parse_issue_number(out)
            url = out.strip().splitlines()[-1]
            print(f"opened issue #{new_number} for {year}")
            if action == "renotify":
                for old in open_list:
                    close(old["number"], f"Superseded by #{new_number}: {renotify_reason}.")
                    print(f"closed issue #{old['number']} as superseded ({renotify_reason})")
            outcome = send(discord_alert(ysum, url, test_mode=test_mode))
            if outcome == "posted":
                _with_body_file(build_body(report, year, True, gap), lambda path: _gh(
                    runner, ["issue", "edit", str(new_number), "--repo", repo,
                             "--body-file", path]))
            open_after[year] = new_number
            actions.append({"year": year, "action": action, "issue": new_number})
            continue

        if action == "update":
            title = issue_title(ysum, test_mode=test_mode)
            posted = discord_posted(active["body"])
            retry = not posted
            if dry_run:
                print(f"{prefix}would replace the title and body of #{number} (no comment"
                      + (", retry the Discord post" if retry else ", no Discord post")
                      + f"): {title}\n{report}")
                if retry:
                    send(discord_alert(ysum, active.get("url"), test_mode=test_mode))
                open_after[year] = number
                actions.append({"year": year, "action": action, "issue": number})
                continue
            if retry:
                posted = send(discord_alert(ysum, active.get("url"), test_mode=test_mode)) == "posted"
            # The gap recorded when the issue was opened stays: it is what the
            # growth since then is measured against.
            gap_at_open = parse_gap(active["body"])
            if gap_at_open is None:
                gap_at_open = gap_of(ysum)
            _with_body_file(build_body(report, year, posted, gap_at_open), lambda path: _gh(
                runner, ["issue", "edit", str(number), "--repo", repo, "--title", title,
                         "--body-file", path]))
            print(f"updated issue #{number}")
            for old in older:
                close(old["number"], f"Superseded by #{number}.")
                print(f"closed duplicate issue #{old['number']}")
            open_after[year] = number
            actions.append({"year": year, "action": action, "issue": number})
            continue

        # close: this year is back above its floors
        kind = legacy_kind.get(number)
        kind = kind if kind in ("current", "two_year") else "current"
        comment = recovery_comment(ysum, kind)
        if dry_run:
            print(f"{prefix}would close #{number} with the comment: {comment}")
            send(discord_recovery(ysum, active.get("url"), kind, test_mode=test_mode))
            actions.append({"year": year, "action": action, "issue": None})
            continue
        for old in open_list:
            close(old["number"], comment if old is active else f"Superseded by #{number}; recovered.")
            print(f"closed issue #{old['number']}")
        send(discord_recovery(ysum, active.get("url"), kind, test_mode=test_mode))
        actions.append({"year": year, "action": action, "issue": None})

    if current_year in open_after:
        alarm_issue: int | None = open_after[current_year]
    else:
        alarm_issue = open_after[max(open_after)] if open_after else None
    return {"actions": actions, "issue": alarm_issue, "discord_failed": discord_failed}


def outstanding(outcome: dict[str, Any]) -> tuple[bool, str]:
    """(any alarm outstanding, comma-separated CDS years still short): every
    year whose alarm issue is open after this run, including an earlier year
    that is no longer the current or next one."""
    years = sorted(
        a["year"] for a in outcome["actions"]
        if a["action"] in ("create", "renotify", "update", "skip")
    )
    return bool(years), ",".join(years)


def real_outstanding(
    years: dict[str, dict[str, Any]],
    current_year: str,
    repo: str,
    runner: Runner,
    outcome: dict[str, Any],
) -> tuple[bool, str]:
    """Outstanding years for the heartbeat in a test-mode run: the REAL alarm
    label's open issues (a read-only list), plus the current and next years
    that are below their floors now. A test run opens test issues only, so
    without this it would report "nothing outstanding" and turn a lamp that is
    really down green. Retired years never count."""
    current_start = int(current_year[:4])
    found: set[str] = set()
    for issue_ in find_open_issues(repo, ALARM_LABEL, runner):
        year, _ = issue_year(issue_, current_year)
        if int(year[:4]) >= current_start - 1:
            found.add(year)
    for year, ysum in years.items():
        if int(year[:4]) >= current_start and lead_check(ysum) is not None:
            found.add(year)
    ordered = sorted(found)
    return bool(ordered), ",".join(ordered)


def main(argv: list[str] | None = None, *, runner: Runner = run_gh) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state", type=Path, required=True, help="out-state JSON from discovery_renewal.py")
    parser.add_argument("--report", type=Path, required=True,
                        help="fallback issue body markdown (used when a year has no report of its own)")
    parser.add_argument("--year-reports", type=Path, help="directory of <year>.md issue bodies")
    parser.add_argument("--summary", type=Path, required=True,
                        help="heartbeat summary JSON; rewritten with alarm_issue")
    parser.add_argument("--repo", default=os.environ.get("GITHUB_REPOSITORY", "bolewood/collegedata-fyi"))
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
        reports: dict[str, str] = {}
        if args.year_reports and args.year_reports.is_dir():
            for path in args.year_reports.glob("*.md"):
                reports[path.stem] = path.read_text(encoding="utf-8")
        current_year = str(state.get("current_year") or summary["current_year"])
        outcome = act(
            years=years,
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
            summary["outstanding_below_floor"], summary["outstanding_years"] = real_outstanding(
                years, current_year, args.repo, runner, outcome)
        else:
            summary["outstanding_below_floor"], summary["outstanding_years"] = outstanding(outcome)
        args.summary.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    # The issue action is done; a Discord delivery failure still fails the job
    # (which posts through workflow_run).
    return 1 if outcome["discord_failed"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
