"""Workflow contracts so the next finder run cannot lose seeds the Friday way."""

from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FINDER = (ROOT / ".github/workflows/ops-finder-probe.yml").read_text()
CATCHUP = (ROOT / ".github/workflows/ops-archive-seed-catchup.yml").read_text()
IR_BACKFILL = (ROOT / ".github/workflows/ops-ir-hub-backfill.yml").read_text()


class FinderProbeWorkflowTests(unittest.TestCase):
    def test_publish_job_does_not_require_probe_success(self) -> None:
        _, publish = FINDER.split("publish-seeds:", 1)
        job_header = publish.split("steps:", 1)[0]
        self.assertIn("always()", job_header)
        self.assertNotIn("if: success()", job_header)

    def test_publish_checks_out_current_main(self) -> None:
        _, publish = FINDER.split("publish-seeds:", 1)
        self.assertIn("ref: main", publish)

    def test_publish_may_only_add_schools_yaml(self) -> None:
        self.assertIn("git add -- tools/finder/schools.yaml", FINDER)
        self.assertNotIn("git add -A", FINDER)
        self.assertNotIn("git add .", FINDER)
        self.assertIn(
            'publish-seeds may only commit tools/finder/schools.yaml',
            FINDER,
        )

    
    def test_stuck_reprobe_avoids_nested_heredocs_and_uses_pipefail(self) -> None:
        _, step = FINDER.split("id: re_probe_stuck", 1)
        run = step.split("- name:", 1)[0]
        self.assertIn("set -euo pipefail", run)
        self.assertNotIn("<<", run)
        self.assertIn("printf", run)

    def test_stuck_heartbeat_comes_from_the_outcome_judge(self) -> None:
        # `replaced` is not `fixed`: the heartbeat reports what the re-probe
        # achieved, from reprobe_outcome.py, not a count of rewritten seeds.
        judge_at = FINDER.index("id: reprobe_outcome")
        heartbeat_at = FINDER.index("- name: Heartbeat finder_stuck_pdf finish")
        self.assertLess(judge_at, heartbeat_at)
        judge = FINDER[judge_at:].split("\n      - name:", 1)[0]
        self.assertIn("tools/finder/reprobe_outcome.py", judge)
        self.assertIn("--out-heartbeat finder-probe/stuck-heartbeat.json", judge)
        self.assertIn("--flagged finder-probe/stuck.json", judge)
        heartbeat = FINDER[heartbeat_at:].split("\n      - name:", 1)[0]
        self.assertIn("--summary-json finder-probe/stuck-heartbeat.json", heartbeat)
        self.assertIn("steps.reprobe_outcome.outcome", heartbeat)
        self.assertNotIn('summary.get("replaced"', FINDER)

    def test_stuck_heartbeat_is_error_when_a_step_did_not_succeed(self) -> None:
        heartbeat = FINDER.split("- name: Heartbeat finder_stuck_pdf finish", 1)[1].split(
            "\n      - name:", 1
        )[0]
        for step in ("re_probe_stuck", "refresh_stuck", "reprobe_outcome"):
            self.assertIn(f"steps.{step}.outcome", heartbeat)
        self.assertIn('"$outcome" != "success"', heartbeat)
        # The empty list is a lone newline, so `-s` would call it non-empty.
        self.assertNotIn("-s finder-probe/stuck-ids.txt", FINDER)

    def test_stuck_report_is_not_posted_to_a_standing_issue(self) -> None:
        # Postmortem section 4: a monthly comment with a steady count reads as
        # "known and handled". The report goes in the run summary and artifact.
        self.assertNotIn("Upsert coverage issue", FINDER)
        self.assertNotIn("'issue', 'comment'", FINDER)
        self.assertNotIn("gh issue", FINDER)
        summary = FINDER.split("- name: Add run summary", 1)[1].split("\n      - name:", 1)[0]
        self.assertIn("GITHUB_STEP_SUMMARY", summary)
        self.assertIn("reprobe-outcome.md", summary)
        self.assertIn("head -c", summary)

    def test_unknown_probe_audits_failed_active_html_seeds(self) -> None:
        _, step = FINDER.split("id: probe_unknown", 1)
        run = step.split("- name:", 1)[0]
        self.assertIn("--audit-active-html", run)
        self.assertIn(
            "--audit-report-json finder-probe/active-html-audit.json",
            run,
        )
        self.assertIn("--new-two-year-cap 300", run)
        self.assertIn("--brave-budget", run)

    def test_failures_open_pipeline_alert_issues(self) -> None:
        self.assertIn("upsert_pipeline_alert_issue.py", FINDER)
        self.assertIn("--component", FINDER)
        self.assertIn("Pipeline alert: Stuck PDFs re-probe failed", FINDER)
        self.assertIn("Pipeline alert: Finder seed branch needs PR", FINDER)
        _, publish = FINDER.split("publish-seeds:", 1)
        self.assertIn("issues: write", publish.split("steps:", 1)[0])
        self.assertIn("id: open_seed_pr", publish)

    def test_probe_always_snapshots_yaml_into_the_artifact(self) -> None:
        self.assertIn("cp tools/finder/schools.yaml finder-probe/schools.yaml", FINDER)
        self.assertIn("cp tools/finder/schools.yaml finder-probe/schools-base.yaml", FINDER)


class ArchiveSeedCatchupWorkflowTests(unittest.TestCase):
    def test_runs_on_schools_yaml_push_to_main(self) -> None:
        self.assertIn("push:", CATCHUP)
        self.assertIn("tools/finder/schools.yaml", CATCHUP)
        self.assertIn("HEAD^", CATCHUP)
        self.assertIn("--apply", CATCHUP)


class IrHubBackfillWorkflowTests(unittest.TestCase):
    def test_review_only_dispatch_does_not_touch_production(self) -> None:
        self.assertIn("workflow_dispatch:", IR_BACKFILL)
        self.assertNotIn("schedule:", IR_BACKFILL)
        self.assertIn("backfill_ir_hubs.py", IR_BACKFILL)
        self.assertIn("contents: read", IR_BACKFILL)
        self.assertNotIn("archive-process", IR_BACKFILL)
        self.assertNotIn("force_urls", IR_BACKFILL)
        self.assertNotIn("tools/finder/schools.yaml", IR_BACKFILL.split("git add", 1)[0] if "git add" in IR_BACKFILL else IR_BACKFILL)
        self.assertNotIn("git add", IR_BACKFILL)
        self.assertNotIn("git commit", IR_BACKFILL)
        self.assertIn("must not modify the working tree", IR_BACKFILL)
        self.assertIn("published", IR_BACKFILL)


class HeadlessArchiveWorkflowTests(unittest.TestCase):
    def test_missing_summary_is_an_error_not_fabricated_zeros(self) -> None:
        text = (ROOT / ".github/workflows/ops-headless-archive.yml").read_text()
        # Required keys stay (so the registry does not relabel it
        # heartbeat_summary_malformed) but the status is an explicit error.
        self.assertIn('"failed":0,"summary_missing":true}', text)
        self.assertIn("summary_missing=true", text)
        self.assertIn('"$summary_missing" == "true"', text)


if __name__ == "__main__":
    unittest.main()
