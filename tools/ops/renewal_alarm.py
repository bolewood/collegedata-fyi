#!/usr/bin/env python3
"""Open, update, supersede and close the one discovery-renewal alarm issue.

Reads the state, summary and report written by `discovery_renewal.py`. Three
checks feed it: one-year renewal, two-year renewal and next-year renewal. The
alarm is on when ANY of them is below its floor.

- Below the floor and no open alarm issue: open a new issue assigned to the
  owner and post to Discord #alerts.
- Below the floor and an issue is open for the same check and year: replace
  its title and body. Never comment, never post to Discord again. A count
  added to a standing issue is a log, not an alarm (#136).
- Below the floor but the open issue is about a different check or year (the
  September switch moved the current year, or the breach moved from one check
  to another): open a new issue, post to Discord, and close the old one with
  one comment, "Superseded by #N".
- Back above the floor on ALL checks and an issue is open: close it with one
  comment that states the recovered number, and post a recovery to Discord.
- Above the floor and no issue: nothing.

The issue is found by LABEL, never by title search (search lags), through the
REST issues list. Test runs use a different label and a `[test] ` title
prefix, are not assigned to anyone, and can never touch a real alarm issue.
A failed `gh` call is an error and exits nonzero: an alarm that cannot
deliver must not look like a quiet day. So is a failed Discord post when the
webhook is set, after the issue action has been done. A missing webhook is a
warning only.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
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
LABEL_DESCRIPTION = "Discovery renewal is below its floor (one open issue at a time)"
SCOPE_RE = re.compile(r"<!-- alarm-scope: ([a-z_]+):(\S+) -->")

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


def scope_of(summary: dict[str, Any]) -> tuple[str, str]:
    """("year", Y): the CDS year the alarm is about today. The one-year and
    two-year checks both concern the current year, so a flip of the lead
    between them updates one issue; the next-year check concerns the year
    after, and is its own scope."""
    kind = lead_check(summary) or "current"
    return "year", check_descriptor(summary, kind)["year"]


def scope_marker(scope: tuple[str, str]) -> str:
    return f"<!-- alarm-scope: {scope[0]}:{scope[1]} -->"


def parse_scope(body: str | None) -> tuple[str, str] | None:
    match = SCOPE_RE.search(body or "")
    return (match.group(1), match.group(2)) if match else None


def issue_title(summary: dict[str, Any], *, test_mode: bool) -> str:
    d = check_descriptor(summary, lead_check(summary) or "current")
    title = (
        f"Discovery is behind: {_pct0(d['pct'])} of schools with {d['prev']} "
        f"have {d['year']} (floor {_pct0(d['floor'])})"
    )
    return (TEST_TITLE_PREFIX if test_mode else "") + title


def _all_checks(summary: dict[str, Any]) -> str:
    parts = []
    for kind in ("current", "two_year", "next"):
        d = check_descriptor(summary, kind)
        floor = "not tracked" if d["floor"] is None else f"floor {_pct1(d['floor'])}"
        parts.append(f"{d['name']} {_pct1(d['pct'])} ({floor})")
    return "; ".join(parts)


def recovery_comment(summary: dict[str, Any], kind: str = "current") -> str:
    d = check_descriptor(summary, kind)
    return (
        f"Recovered: the {d['name']} check is {d['renewed']} of {d['total']} "
        f"({_pct1(d['pct'])}) of schools with {d['prev']} having {d['year']}, "
        f"floor {_pct1(d['floor'])}. All checks are above their floors: {_all_checks(summary)}. Closing."
    )


def discord_alert(summary: dict[str, Any], issue_url: str | None, *, test_mode: bool) -> dict[str, Any]:
    d = check_descriptor(summary, lead_check(summary) or "current")
    return {
        "title": issue_title(summary, test_mode=test_mode),
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
    summary: dict[str, Any], issue_url: str | None, kind: str, *, test_mode: bool
) -> dict[str, Any]:
    d = check_descriptor(summary, kind)
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
         "-f", "state=open", "-f", "per_page=20"],
    )
    try:
        rows = json.loads(out or "[]")
    except json.JSONDecodeError as exc:
        raise AlarmError("could not parse the gh issues list") from exc
    if not isinstance(rows, list):
        raise AlarmError("gh issues list did not return a list")
    issues = [
        {"number": int(r["number"]), "title": r.get("title", ""),
         "url": r.get("html_url") or r.get("url"), "body": r.get("body") or ""}
        for r in rows
        if "pull_request" not in r
    ]
    return sorted(issues, key=lambda r: r["number"])


def find_open_issue(repo: str, label: str, runner: Runner) -> dict[str, Any] | None:
    """The alarm issue: the newest open one carrying the label."""
    issues = find_open_issues(repo, label, runner)
    return issues[-1] if issues else None


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


def act(
    *,
    summary: dict[str, Any],
    below_floor: bool,
    report: str,
    repo: str,
    test_mode: bool,
    dry_run: bool,
    assignee: str,
    runner: Runner,
    discord: Callable[..., bool] = notify_discord.post_custom_embed,
) -> dict[str, Any]:
    """Do (or, in a dry run, print) what the state calls for. Returns
    {"action", "issue", "discord_failed"} where issue is the open alarm issue
    afterwards."""
    label = label_for(test_mode)
    issues = find_open_issues(repo, label, runner)
    if test_mode:
        for existing in issues:
            if not str(existing.get("title", "")).startswith(TEST_TITLE_PREFIX):
                raise AlarmError(
                    f"issue #{existing['number']} carries {label} but is not a test issue; "
                    "refusing to touch it"
                )
    active = issues[-1] if issues else None
    older = issues[:-1]
    number = active["number"] if active else None
    url = active.get("url") if active else None
    scope = scope_of(summary)
    old_scope = parse_scope(active.get("body")) if active else None
    action = decide(below_floor, number)
    # Scope is the CDS year only; an older marker that names a check matches
    # on its year.
    if action == "update" and old_scope is not None and old_scope[1] != scope[1]:
        action = "supersede"
    prefix = "[dry run] " if dry_run else ""
    print(f"{prefix}alarm action: {action} (below_floor={below_floor}, open issue={number}, "
          f"scope={scope[0]}:{scope[1]}, label={label})")

    discord_failed = False

    def send(payload: dict[str, Any]) -> None:
        nonlocal discord_failed
        try:
            if dry_run:
                discord(**payload, dry_run=True)
            else:
                discord(**payload, raise_on_failure=True)
        except notify_discord.DiscordPostError as exc:
            discord_failed = True
            print(f"::error::Discord post failed after the issue action: {exc}", file=sys.stderr)

    body = report.rstrip("\n") + "\n\n" + scope_marker(scope) + "\n"

    def create() -> tuple[int, str]:
        title = issue_title(summary, test_mode=test_mode)
        ensure_label(repo, label, runner)
        assign = [] if test_mode else ["--assignee", assignee]
        out = _with_body_file(body, lambda path: _gh(
            runner, ["issue", "create", "--repo", repo, "--title", title,
                     "--body-file", path, "--label", label, *assign]))
        return parse_issue_number(out), out.strip().splitlines()[-1]

    def close(issue_number: int, comment: str) -> None:
        _gh(runner, ["issue", "close", str(issue_number), "--repo", repo, "--comment", comment])

    if action == "none":
        return {"action": action, "issue": None, "discord_failed": False}

    if action in ("create", "supersede"):
        title = issue_title(summary, test_mode=test_mode)
        if dry_run:
            who = "none (test)" if test_mode else assignee
            extra = ""
            if action == "supersede":
                extra = (f"\n  would close #{number}"
                         + "".join(f", #{o['number']}" for o in older)
                         + " as superseded")
            print(f"{prefix}would create issue: {title}\n  label={label} assignee={who}{extra}\n{report}")
            send(discord_alert(summary, None, test_mode=test_mode))
            return {"action": action, "issue": None, "discord_failed": discord_failed}
        new_number, new_url = create()
        print(f"opened issue #{new_number}")
        if action == "supersede":
            for old in issues:
                close(old["number"], f"Superseded by #{new_number}: the alarm is now about "
                      f"renewal for {scope[1]}.")
                print(f"closed issue #{old['number']} as superseded")
        send(discord_alert(summary, new_url, test_mode=test_mode))
        return {"action": action, "issue": new_number, "discord_failed": discord_failed}

    if action == "update":
        title = issue_title(summary, test_mode=test_mode)
        if dry_run:
            print(f"{prefix}would replace the title and body of #{number} "
                  f"(no comment, no Discord post): {title}\n{report}")
            return {"action": action, "issue": number, "discord_failed": False}
        _with_body_file(body, lambda path: _gh(
            runner, ["issue", "edit", str(number), "--repo", repo, "--title", title,
                     "--body-file", path]))
        print(f"updated issue #{number}")
        for old in older:
            close(old["number"], f"Superseded by #{number}.")
            print(f"closed issue #{old['number']} as superseded")
        return {"action": action, "issue": number, "discord_failed": False}

    # close: name the check the standing issue was about
    kind = old_scope[0] if old_scope and old_scope[0] in ("current", "two_year", "next") else "current"
    comment = recovery_comment(summary, kind)
    if dry_run:
        print(f"{prefix}would close #{number} with the comment: {comment}")
        send(discord_recovery(summary, url, kind, test_mode=test_mode))
        return {"action": action, "issue": None, "discord_failed": discord_failed}
    for old in issues:
        close(old["number"], comment if old is active else f"Superseded by #{number}; recovered.")
        print(f"closed issue #{old['number']}")
    send(discord_recovery(summary, url, kind, test_mode=test_mode))
    return {"action": action, "issue": None, "discord_failed": discord_failed}


def main(argv: list[str] | None = None, *, runner: Runner = run_gh) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state", type=Path, required=True, help="out-state JSON from discovery_renewal.py")
    parser.add_argument("--report", type=Path, required=True, help="issue body markdown")
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
        report = args.report.read_text(encoding="utf-8")
        if not isinstance(state.get("below_floor"), bool):
            raise AlarmError("state has no boolean below_floor")
        outcome = act(
            summary=summary,
            below_floor=state["below_floor"],
            report=report,
            repo=args.repo,
            test_mode=args.test_mode,
            dry_run=args.dry_run,
            assignee=args.assignee,
            runner=runner,
        )
    except (AlarmError, OSError, json.JSONDecodeError, KeyError) as exc:
        print(f"::error::renewal alarm: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    if not args.dry_run:
        # A test issue is not the alarm: keep it out of the heartbeat summary.
        summary["alarm_issue"] = None if args.test_mode else outcome["issue"]
        args.summary.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    # The issue action is done; a Discord delivery failure still fails the job
    # (which posts through workflow_run).
    return 1 if outcome["discord_failed"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
