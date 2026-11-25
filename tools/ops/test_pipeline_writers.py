from __future__ import annotations

import re
import unittest
from pathlib import Path

from tools.ops.record_heartbeat import REGISTRY_STATIONS

ROOT = Path(__file__).resolve().parents[2]
FINDER = ROOT / ".github/workflows/ops-finder-probe.yml"
EXTRACTION = ROOT / ".github/workflows/ops-extraction-worker.yml"
HEADLESS = ROOT / ".github/workflows/ops-headless-archive.yml"
IPEDS = ROOT / ".github/workflows/ipeds-release-probe.yml"
API_USAGE = ROOT / ".github/workflows/ops-api-usage-ingest.yml"
CORPUS_AUDIT = ROOT / ".github/workflows/ops-corpus-audit.yml"
DISCOVERY_RENEWAL = ROOT / ".github/workflows/ops-discovery-renewal.yml"
STATION_RE = re.compile(r"--station\s+(\S+)")


class PipelineWriterLintTests(unittest.TestCase):
    def test_workflow_station_ids_are_in_the_registry(self) -> None:
        stations: set[str] = set()
        for path in (FINDER, EXTRACTION, HEADLESS, IPEDS, API_USAGE, CORPUS_AUDIT):
            stations.update(STATION_RE.findall(path.read_text(encoding="utf-8")))
        self.assertTrue(stations)
        self.assertTrue(stations <= set(REGISTRY_STATIONS), stations - set(REGISTRY_STATIONS))
        self.assertIn("headless_archive", stations)
        self.assertIn("api_usage_ingest", stations)
        self.assertIn("corpus_audit", stations)

    def test_discovery_renewal_workflow_is_safe_by_default_and_registered(self) -> None:
        text = DISCOVERY_RENEWAL.read_text(encoding="utf-8")
        self.assertIn("--station discovery_renewal", text)
        self.assertIn("discovery_renewal", REGISTRY_STATIONS)
        # Manual runs default to a dry run and the test label.
        self.assertRegex(text, r"dry_run:\n(?:.*\n){1,3}?\s+default: true")
        self.assertRegex(text, r"test_mode:\n(?:.*\n){1,3}?\s+default: true")
        # Scheduled runs are always real, and the job needs only these scopes.
        self.assertIn("github.event_name == 'schedule' && 'false'", text)
        self.assertIn("issues: write", text)
        self.assertIn("cron:", text)
        # A floor override only works with --test-mode, which the compute step passes.
        self.assertIn("args+=(--test-mode)", text.split("id: compute")[1].split("id: alarm")[0])
        # No `running` heartbeat: it would blank the board's last_summary.
        self.assertNotIn("--status running", text)
        self.assertIn('--status "${status}"', text)
        # The service key is only in the heartbeat steps.
        compute = text.split("id: compute")[1].split("id: fetch_failures")[0]
        self.assertNotIn("SERVICE_ROLE", compute)
        # The fetch-failures step reads archive_queue: the key is in its env only.
        fetch = text.split("id: fetch_failures")[1].split("id: alarm")[0]
        self.assertIn("SUPABASE_SERVICE_ROLE_KEY: ${{ secrets.SUPABASE_SERVICE_ROLE_KEY }}", fetch)
        self.assertIn("continue-on-error: true", fetch)
        self.assertIn('FETCH_OUTCOME}" == "failure"', text.split("Heartbeat discovery_renewal finish")[1])
        job_env = text.split("    env:\n", 1)[1].split("    steps:")[0]
        self.assertNotIn("SERVICE_ROLE", job_env)
        self.assertNotIn("SUPABASE_URL", job_env)
        install = text.split("Install Python dependencies")[1].split("- id: compute")[0]
        self.assertNotIn("SERVICE_ROLE", install)
        alarm = text.split("id: alarm")[1].split("upload-artifact")[0]
        self.assertNotIn("SERVICE_ROLE", alarm)
        # A dry run sends no heartbeat, and says so before calling the writer.
        finish = text.split("Heartbeat discovery_renewal finish")[1]
        guard = finish.index('"${DRY_RUN}" == "true"')
        self.assertIn("dry run: heartbeat not sent", finish[guard:guard + 200])
        self.assertLess(guard, finish.index("record_heartbeat.py"))

    def test_discovery_renewal_outside_check_in_is_schedule_only_and_never_echoes_the_url(self) -> None:
        text = DISCOVERY_RENEWAL.read_text(encoding="utf-8")
        step = text.split("- name: Outside check-in")[1]
        header = step.split("run: |")[0]
        self.assertIn("github.event_name == 'schedule'", header)
        self.assertIn("always()", header)
        body = step.split("run: |")[1]
        self.assertIn("RENEWAL_DEADMAN_URL not set; no outside check-in (see docs/ops-discord.md)", body)
        self.assertIn('curl -fsS -m 10 --retry 3', body)
        self.assertIn('"${RENEWAL_DEADMAN_URL}${suffix}"', body)
        self.assertIn('suffix="/fail"', body)
        # The URL is only ever tested for emptiness or passed to curl.
        for line in body.splitlines():
            if "${RENEWAL_DEADMAN_URL" in line:
                self.assertTrue('-z "${RENEWAL_DEADMAN_URL}"' in line or "curl" in line, line)
        self.assertNotIn("set -x", text)
        self.assertNotIn("echo \"${RENEWAL_DEADMAN_URL", text)
        self.assertNotIn("echo ${RENEWAL_DEADMAN_URL", text)

    def test_a_crashed_fetch_failures_step_still_fails_the_job(self) -> None:
        text = DISCOVERY_RENEWAL.read_text(encoding="utf-8")
        # The step is continue-on-error so it cannot hide the alarm; a final step
        # turns its failure into a red job so workflow_run and the failure
        # counter see it.
        self.assertIn("continue-on-error: true", text.split("id: fetch_failures")[1].split("run: |")[0])
        final = text.split("- name: Fail the job when fetch failures crashed")[1]
        header = final.split("run: |")[0]
        self.assertIn("steps.fetch_failures.outcome == 'failure'", header)
        self.assertIn("always()", header)
        self.assertIn("exit 1", final.split("run: |")[1].split("- name:")[0])
        # After the heartbeat and the outside check-in, before the counter.
        order = [text.index(n) for n in ("Heartbeat discovery_renewal finish", "- name: Outside check-in",
                                         "- name: Fail the job when fetch failures crashed",
                                         "- name: Count consecutive failures")]
        self.assertEqual(order, sorted(order))
        # The outside check-in reports the same failure.
        checkin = text.split("- name: Outside check-in")[1].split("- name:")[0]
        self.assertIn("steps.fetch_failures.outcome", checkin)

    def test_discovery_renewal_counts_consecutive_failures_on_scheduled_runs(self) -> None:
        text = DISCOVERY_RENEWAL.read_text(encoding="utf-8")
        step = text.split("- name: Count consecutive failures")[1].split("- name:")[0]
        self.assertIn("failure() && github.event_name == 'schedule'", step)
        self.assertIn("tools/ops/consecutive_failures.py", step)
        self.assertIn("actions: read", text)

    def test_discovery_renewal_passes_per_year_reports_to_the_alarm(self) -> None:
        text = DISCOVERY_RENEWAL.read_text(encoding="utf-8")
        self.assertIn("--out-year-reports renewal/years", text)
        self.assertIn("--year-reports renewal/years", text)

    def test_corpus_audit_keeps_the_service_key_out_of_dependency_install(self) -> None:
        text = CORPUS_AUDIT.read_text(encoding="utf-8")
        job_env = text.split("    steps:")[0]
        self.assertNotIn("SUPABASE_SERVICE_ROLE_KEY", job_env)
        self.assertIn("--out-heartbeat", text)

    def test_scheduled_workflows_keep_on_schedule(self) -> None:
        for path in (FINDER, EXTRACTION, HEADLESS, IPEDS, API_USAGE, CORPUS_AUDIT):
            text = path.read_text(encoding="utf-8")
            self.assertRegex(text, r"(?m)^  schedule:\s*$", msg=f"{path.name} lost on.schedule")
            self.assertRegex(text, r"- cron:")

    def test_finder_heartbeats_are_mode_guarded_and_id_keyed(self) -> None:
        text = FINDER.read_text(encoding="utf-8")
        self.assertIn("id: re_probe_stuck", text)
        self.assertIn("id: probe_unknown", text)
        self.assertIn("id: promote_landing_hints", text)
        self.assertIn(
            "if: always() && (env.INPUT_MODE == 'both' || env.INPUT_MODE == 'stuck-pdf')",
            text,
        )
        self.assertIn(
            "if: always() && (env.INPUT_MODE == 'both' || env.INPUT_MODE == 'unknown')",
            text,
        )
        self.assertIn("if: always() && env.INPUT_APPLY_LANDING_HINTS == 'true'", text)
        brave_finish = text.split("Heartbeat finder_brave finish", 1)[1]
        self.assertNotIn("INPUT_MODE == 'stuck-pdf'", brave_finish.split("- name:", 1)[0])

    def test_api_usage_ingest_is_hourly_and_never_echoes_rows(self) -> None:
        text = API_USAGE.read_text(encoding="utf-8")
        self.assertIn('- cron: "20,50 * * * *"', text)
        self.assertIn("group: api-usage-ingest", text)
        self.assertIn("--summary-json api-usage/heartbeat.json", text)
        self.assertNotIn("upload-artifact", text)
        self.assertNotIn("set -x", text)

    def test_ipeds_noop_heartbeat_maps_available_count_to_new_release(self) -> None:
        text = IPEDS.read_text(encoding="utf-8")
        self.assertIn("Heartbeat ipeds_release_probe finish", text)
        self.assertIn('"new_release": bool((summary.get("available_count") or 0) > 0)', text)
        self.assertIn("issue_opened", text)

    def test_extraction_worker_passes_closed_ledger_run_metadata(self) -> None:
        text = EXTRACTION.read_text(encoding="utf-8")
        drain = text.split("id: drain_pending", 1)[1].split("- name:", 1)[0]
        self.assertIn('--trigger "${PIPELINE_TRIGGER}"', drain)
        self.assertIn('--run-url "${PIPELINE_RUN_URL}"', drain)
        self.assertIn("--reconcile-pending", drain)
        self.assertIn("--summary-json ops-summary/summary.json", drain)

    def test_headless_archive_uses_playwright_not_force_urls(self) -> None:
        text = HEADLESS.read_text(encoding="utf-8")
        self.assertIn("playwright install --with-deps chromium", text)
        self.assertIn("tools/finder/headless_archive.py", text)
        self.assertIn("--station headless_archive", text)
        ingest = text.split("id: ingest", 1)[1]
        ingest_run = ingest.split("- name:", 1)[0]
        self.assertNotIn("force_urls", ingest_run)
        self.assertIn("runs-on: ubuntu-latest", text)
        self.assertNotRegex(text, r"(?m)^    runs-on:.*self-hosted")
        self.assertIn("--phase all", text)
        self.assertIn("collegedata-ops", text)


if __name__ == "__main__":
    unittest.main()
