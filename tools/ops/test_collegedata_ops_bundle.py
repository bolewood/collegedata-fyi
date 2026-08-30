"""Contracts for the private collegedata-ops bundle.

The bundle is copied to a private GitHub repo. This test locks the
secretless-fetch split so a later edit cannot put the service role on
spoke-ops or attach those labels to the public workflows.
"""

from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BUNDLE = ROOT / "ops" / "collegedata-ops"
WORKFLOW = BUNDLE / ".github" / "workflows" / "residential-headless-archive.yml"
PUBLIC_HEADLESS = ROOT / ".github" / "workflows" / "ops-headless-archive.yml"


class CollegedataOpsBundleTests(unittest.TestCase):
    def test_bundle_files_exist(self) -> None:
        self.assertTrue(WORKFLOW.is_file())
        self.assertTrue((BUNDLE / "README.md").is_file())
        self.assertTrue((BUNDLE / "spoke-ops" / "run-loop.sh").is_file())
        self.assertTrue((BUNDLE / ".github" / "CODEOWNERS").is_file())

    def test_fetch_job_has_no_supabase_and_uses_spoke_ops_labels(self) -> None:
        text = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("fetch-residential:", text)
        fetch = text.split("fetch-residential:", 1)[1].split("commit-hosted:", 1)[0]
        self.assertNotIn("SUPABASE_URL", fetch)
        self.assertNotIn("secrets.SUPABASE", fetch)
        self.assertIn("self-hosted", fetch)
        self.assertIn("spoke-ops", fetch)
        self.assertIn("cds-headless", fetch)
        self.assertIn("--phase fetch", fetch)
        self.assertIn("persist-credentials: false", fetch)

    def test_hosted_jobs_keep_secrets_off_self_hosted(self) -> None:
        text = WORKFLOW.read_text(encoding="utf-8")
        plan = text.split("plan-hosted:", 1)[1].split("fetch-residential:", 1)[0]
        commit = text.split("commit-hosted:", 1)[1].split("heartbeat-on-failure:", 1)[0]
        self.assertIn("ubuntu-latest", plan)
        self.assertIn("ubuntu-latest", commit)
        self.assertNotIn("self-hosted", plan)
        self.assertNotIn("self-hosted", commit)
        self.assertIn("secrets.SUPABASE_SERVICE_ROLE_KEY", plan)
        self.assertIn("secrets.SUPABASE_SERVICE_ROLE_KEY", commit)
        self.assertIn("--phase plan", plan)
        self.assertIn("--phase commit", commit)

    def test_triggers_are_not_pull_request(self) -> None:
        text = WORKFLOW.read_text(encoding="utf-8")
        header = text.split("jobs:", 1)[0]
        self.assertNotIn("pull_request", header)
        self.assertNotIn("pull_request_target", header)
        self.assertNotIn("workflow_run", header)
        self.assertIn("workflow_dispatch:", header)
        self.assertIn("schedule:", header)

    def test_public_repo_workflow_does_not_use_spoke_ops_labels(self) -> None:
        text = PUBLIC_HEADLESS.read_text(encoding="utf-8")
        self.assertNotIn("cds-headless", text)
        self.assertNotRegex(text, r"(?m)^    runs-on:.*self-hosted")
        self.assertNotRegex(text, r"(?m)^    runs-on:.*spoke-ops")
        self.assertIn("runs-on: ubuntu-latest", text)

    def test_defaults_to_public_main_and_runs_after_hosted(self) -> None:
        text = WORKFLOW.read_text(encoding="utf-8")
        header = text.split("jobs:", 1)[0]
        self.assertIn('cron: "0 10 * * *"', header)
        self.assertNotIn("30 7", header)
        self.assertIn('default: "main"', text)
        self.assertNotIn("cursor/nyu-cds-coverage-audit", text)
        plan = text.split("plan-hosted:", 1)[1].split("fetch-residential:", 1)[0]
        self.assertIn("--require-only", plan)
        self.assertIn("--max-only 5", plan)
        self.assertIn("top100_coverage.py", plan)
        fetch = text.split("fetch-residential:", 1)[1].split("commit-hosted:", 1)[0]
        self.assertIn("--require-only", fetch)
        self.assertIn("--max-only 5", fetch)


if __name__ == "__main__":
    unittest.main()
