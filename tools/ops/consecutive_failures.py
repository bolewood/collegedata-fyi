#!/usr/bin/env python3
"""Count how many scheduled runs of a workflow in a row have failed.

The Discord notifier posts only the first failure of a run of failures. For a
daily check that is not enough: a check that has been broken for a week still
looks like one old alert. Called from the failing run itself, this prints
`::error::<name> has failed N days running` (a visible annotation on the run)
and, on every 7th consecutive failure, posts to Discord #alerts directly.

Never fails the calling job: a lookup problem is a warning.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Callable

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.ops import notify_discord  # noqa: E402

FAILED = frozenset({"failure", "timed_out", "startup_failure"})
IGNORED = frozenset({"cancelled", "skipped", "neutral", "stale", ""})
# `gh run list` pages through the API up to this many runs. A streak that runs
# past it is reported as "400+" and not counted further.
LIST_LIMIT = 400


def prior_failure_streak(runs: list[dict[str, Any]], current_run_id: int) -> int:
    return streak_info(runs, current_run_id)[0]


def streak_info(runs: list[dict[str, Any]], current_run_id: int) -> tuple[int, bool]:
    """(failed scheduled runs in a row before `current_run_id`, whether the
    list ended before a success was found, so the streak may be longer)."""
    """Failed scheduled runs in a row before `current_run_id`.

    `runs` is newest first, as `gh run list` returns it. The current run (in
    progress) and any run that has not completed are skipped, as are
    cancelled and skipped runs, which say nothing either way. The streak ends
    at the first success.
    """
    streak = 0
    for run in runs:
        if int(run.get("databaseId") or 0) == int(current_run_id):
            continue
        if run.get("status") not in (None, "completed"):
            continue
        conclusion = str(run.get("conclusion") or "")
        if conclusion in IGNORED:
            continue
        if conclusion in FAILED:
            streak += 1
            continue
        return streak, False
    return streak, True


def should_post(streak: int, every: int, previous: int | None = None) -> bool:
    """Post when the streak has just reached a new multiple of `every`: its
    count of whole weeks went up compared with the previous run's streak.
    Comparing with the previous run (not just `streak % every`) keeps a
    streak that did not move from posting again."""
    if streak < every:
        return False
    if previous is None:
        return streak % every == 0
    return streak // every > previous // every


def run_gh(args: list[str]) -> subprocess.CompletedProcess[str]:
    return notify_discord.run_gh(args, os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN"))


def main(
    argv: list[str] | None = None,
    *,
    runner: Callable[[list[str]], subprocess.CompletedProcess[str]] = run_gh,
    discord: Callable[..., bool] = notify_discord.post_custom_embed,
) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", required=True)
    parser.add_argument("--workflow", required=True, help="workflow name or file")
    parser.add_argument("--run-id", type=int, required=True, help="the failing run (this one)")
    parser.add_argument("--label", default="renewal check", help="what to call the check in messages")
    parser.add_argument("--notify-every", type=int, default=7)
    parser.add_argument("--run-url", default="")
    args = parser.parse_args(argv)

    listed = runner(["run", "list", "--repo", args.repo, "--workflow", args.workflow,
                     "--event", "schedule", "--limit", str(LIST_LIMIT),
                     "--json", "databaseId,conclusion,status"])
    if listed.returncode != 0:
        print("::warning::could not list earlier runs to count failures", file=sys.stderr)
        return 0
    try:
        runs = json.loads(listed.stdout or "[]")
    except json.JSONDecodeError:
        print("::warning::could not read the earlier runs", file=sys.stderr)
        return 0
    prior, truncated = streak_info(runs, args.run_id)
    streak = prior + 1  # this run failed too
    if streak < 2:
        print(f"{args.label} failed today; no earlier consecutive failures")
        return 0
    days = f"{streak}+" if truncated and len(runs) >= LIST_LIMIT else str(streak)
    message = f"{args.label} has failed {days} days running"
    print(f"::error::{message}", file=sys.stderr)
    if should_post(streak, args.notify_every, prior):
        discord(
            title=f"{args.label[:1].upper()}{args.label[1:]} has failed {days} days running",
            fields=[("Workflow", args.workflow), ("Days running", days),
                    ("Run", args.run_url or "—")],
            url=args.run_url or None,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
