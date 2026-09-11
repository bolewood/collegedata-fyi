#!/usr/bin/env python3
"""Upsert a GitHub issue for a red pipeline station.

Designed for Actions: opens an issue when a scheduled/dispatch station fails
so a silent red lamp is not the only signal. Reuses an open issue with the
same title (comment) instead of spamming.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys


def run_gh(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["gh", *args],
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", required=True)
    parser.add_argument("--component", required=True, help="Alert component label (not a heartbeat station id)")
    parser.add_argument("--title", required=True)
    parser.add_argument("--body", required=True)
    parser.add_argument("--run-url", default="")
    args = parser.parse_args()

    if not os.environ.get("GH_TOKEN") and not os.environ.get("GITHUB_TOKEN"):
        print("::warning::no GH_TOKEN; skipping pipeline alert issue", file=sys.stderr)
        return 0

    labels = ["pipeline-alert", f"component:{args.component}"]
    body = args.body.strip() + "\n"
    if args.run_url:
        body += f"\nRun: {args.run_url}\n"

    listed = run_gh(
        [
            "issue",
            "list",
            "--repo",
            args.repo,
            "--state",
            "open",
            "--search",
            f'in:title "{args.title}"',
            "--json",
            "number,title",
        ]
    )
    if listed.returncode != 0:
        print(f"::warning::gh issue list failed: {listed.stderr.strip()}", file=sys.stderr)
        return 0

    rows = json.loads(listed.stdout or "[]")
    match = next((row for row in rows if row.get("title") == args.title), None)
    if match:
        commented = run_gh(
            [
                "issue",
                "comment",
                str(match["number"]),
                "--repo",
                args.repo,
                "--body",
                body,
            ]
        )
        if commented.returncode != 0:
            print(
                f"::warning::gh issue comment failed: {commented.stderr.strip()}",
                file=sys.stderr,
            )
            return 0
        print(f"Commented on alert issue #{match['number']}")
        return 0

    create_args = [
        "issue",
        "create",
        "--repo",
        args.repo,
        "--title",
        args.title,
        "--body",
        body,
    ]
    for label in labels:
        create_args.extend(["--label", label])
    created = run_gh(create_args)
    if created.returncode != 0:
        # Labels may not exist yet — retry without them.
        print(
            f"::warning::gh issue create with labels failed ({created.stderr.strip()}); retrying bare",
            file=sys.stderr,
        )
        created = run_gh(
            [
                "issue",
                "create",
                "--repo",
                args.repo,
                "--title",
                args.title,
                "--body",
                body,
            ]
        )
        if created.returncode != 0:
            print(
                f"::warning::gh issue create failed: {created.stderr.strip()}",
                file=sys.stderr,
            )
            return 0
    print(f"Opened alert issue: {created.stdout.strip()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
