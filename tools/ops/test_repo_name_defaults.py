"""Tool code names the repository as bolewood/quadfile.

The ops scripts fall back to a hardcoded repo name when GITHUB_REPOSITORY is
unset or empty, and the fetchers put a repo URL in their User-Agent. A leftover
old name there would only show up when a script runs outside Actions. Tests may
keep the old name as a fixture; the scan covers non-test code only.
"""

from __future__ import annotations

import importlib
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tools.ops import (
    automation_health,
    directory_enqueue_batches,
    extraction_backlog_audit,
    notify_discord,
    renewal_alarm,
)

TOOLS = Path(__file__).resolve().parents[1]
OLD_REPO = "bolewood/collegedata-fyi"
NEW_REPO = "bolewood/quadfile"


class _Reached(BaseException):
    def __init__(self, repo: str) -> None:
        self.repo = repo


def _renewal_alarm_default_repo() -> str:
    def fake_act(**kwargs):
        raise _Reached(kwargs["repo"])

    with tempfile.TemporaryDirectory() as d:
        base = Path(d)
        state = base / "state.json"
        summary = base / "summary.json"
        report = base / "report.md"
        state.write_text(json.dumps({"years": {"2025-26": {}}, "current_year": "2025-26"}))
        summary.write_text(json.dumps({"current_year": "2025-26"}))
        report.write_text("body")
        with patch.object(renewal_alarm, "act", fake_act):
            try:
                renewal_alarm.main(
                    ["--state", str(state), "--report", str(report), "--summary", str(summary), "--dry-run"]
                )
            except _Reached as reached:
                return reached.repo
    raise AssertionError("renewal_alarm.main never reached act()")


def _defaults() -> dict[str, str]:
    # automation_health and extraction_backlog_audit read the env at import.
    importlib.reload(automation_health)
    importlib.reload(extraction_backlog_audit)
    return {
        "automation_health": automation_health.DEFAULT_REPO,
        "extraction_backlog_audit": extraction_backlog_audit.DEFAULT_GITHUB_REPO,
        "directory_enqueue_batches": directory_enqueue_batches.build_parser()
        .parse_args([])
        .extraction_audit_github_repo,
        "notify_discord": notify_discord.parse_args(["--event-name", "x"]).repo,
        "renewal_alarm": _renewal_alarm_default_repo(),
    }


class RepoNameDefaultsTests(unittest.TestCase):
    def tearDown(self) -> None:
        importlib.reload(automation_health)
        importlib.reload(extraction_backlog_audit)

    def _assert_all_default_to_new_repo(self) -> None:
        self.assertEqual(
            _defaults(),
            {name: NEW_REPO for name in (
                "automation_health",
                "extraction_backlog_audit",
                "directory_enqueue_batches",
                "notify_discord",
                "renewal_alarm",
            )},
        )

    def test_defaults_with_github_repository_unset(self) -> None:
        env = {k: v for k, v in os.environ.items() if k != "GITHUB_REPOSITORY"}
        with patch.dict(os.environ, env, clear=True):
            self._assert_all_default_to_new_repo()

    def test_defaults_with_github_repository_empty(self) -> None:
        with patch.dict(os.environ, {"GITHUB_REPOSITORY": ""}):
            self._assert_all_default_to_new_repo()

    def test_github_repository_still_wins(self) -> None:
        with patch.dict(os.environ, {"GITHUB_REPOSITORY": "someone/else"}):
            self.assertEqual(set(_defaults().values()), {"someone/else"})

    def test_no_tool_code_names_the_old_repo(self) -> None:
        offenders = [
            str(p.relative_to(TOOLS))
            for p in sorted(TOOLS.rglob("*.py"))
            if not p.name.startswith("test_")
            and "node_modules" not in p.parts
            and OLD_REPO in p.read_text(encoding="utf-8")
        ]
        self.assertEqual(offenders, [])


if __name__ == "__main__":
    unittest.main()
