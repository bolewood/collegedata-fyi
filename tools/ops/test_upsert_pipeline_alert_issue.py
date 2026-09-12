"""Tests for pipeline alert issue upserts."""

from __future__ import annotations

import os
import subprocess
import unittest
from unittest.mock import patch

from tools.ops import upsert_pipeline_alert_issue


def gh_result(
    returncode: int = 0,
    *,
    stdout: str = "",
    stderr: str = "",
) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(
        args=["gh"],
        returncode=returncode,
        stdout=stdout,
        stderr=stderr,
    )


class UpsertPipelineAlertIssueTests(unittest.TestCase):
    def run_main(
        self,
        results: list[subprocess.CompletedProcess[str]],
        *,
        token: bool = True,
    ) -> tuple[int, int]:
        argv = [
            "upsert_pipeline_alert_issue.py",
            "--repo",
            "owner/repo",
            "--component",
            "finder",
            "--title",
            "Pipeline alert",
            "--body",
            "Something failed.",
        ]
        env = {"GH_TOKEN": "test-token"} if token else {}
        with (
            patch.dict(os.environ, env, clear=True),
            patch("sys.argv", argv),
            patch.object(
                upsert_pipeline_alert_issue,
                "run_gh",
                side_effect=results,
            ) as run_gh,
        ):
            return upsert_pipeline_alert_issue.main(), run_gh.call_count

    def test_missing_token_returns_nonzero(self) -> None:
        returncode, calls = self.run_main([], token=False)
        self.assertNotEqual(returncode, 0)
        self.assertEqual(calls, 0)

    def test_issue_list_failure_returns_nonzero(self) -> None:
        returncode, calls = self.run_main([gh_result(1, stderr="list denied")])
        self.assertNotEqual(returncode, 0)
        self.assertEqual(calls, 1)

    def test_comment_failure_returns_nonzero(self) -> None:
        returncode, calls = self.run_main(
            [
                gh_result(stdout='[{"number": 42, "title": "Pipeline alert"}]'),
                gh_result(1, stderr="comment denied"),
            ]
        )
        self.assertNotEqual(returncode, 0)
        self.assertEqual(calls, 2)

    def test_existing_alert_comment_returns_zero(self) -> None:
        returncode, calls = self.run_main(
            [
                gh_result(stdout='[{"number": 42, "title": "Pipeline alert"}]'),
                gh_result(),
            ]
        )
        self.assertEqual(returncode, 0)
        self.assertEqual(calls, 2)

    def test_successful_labeled_create_returns_zero(self) -> None:
        returncode, calls = self.run_main(
            [
                gh_result(stdout="[]"),
                gh_result(stdout="https://github.com/owner/repo/issues/42\n"),
            ]
        )
        self.assertEqual(returncode, 0)
        self.assertEqual(calls, 2)

    def test_successful_bare_create_retry_returns_zero(self) -> None:
        returncode, calls = self.run_main(
            [
                gh_result(stdout="[]"),
                gh_result(1, stderr="label missing"),
                gh_result(stdout="https://github.com/owner/repo/issues/42\n"),
            ]
        )
        self.assertEqual(returncode, 0)
        self.assertEqual(calls, 3)

    def test_terminal_create_failure_returns_nonzero(self) -> None:
        returncode, calls = self.run_main(
            [
                gh_result(stdout="[]"),
                gh_result(1, stderr="label missing"),
                gh_result(1, stderr="create denied"),
            ]
        )
        self.assertNotEqual(returncode, 0)
        self.assertEqual(calls, 3)


if __name__ == "__main__":
    unittest.main()
