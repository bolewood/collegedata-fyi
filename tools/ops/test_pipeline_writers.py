from __future__ import annotations

import re
import unittest
from pathlib import Path

from tools.ops.record_heartbeat import REGISTRY_STATIONS

ROOT = Path(__file__).resolve().parents[2]
FINDER = ROOT / ".github/workflows/ops-finder-probe.yml"
EXTRACTION = ROOT / ".github/workflows/ops-extraction-worker.yml"
IPEDS = ROOT / ".github/workflows/ipeds-release-probe.yml"
STATION_RE = re.compile(r"--station\s+(\S+)")


class PipelineWriterLintTests(unittest.TestCase):
    def test_workflow_station_ids_are_in_the_registry(self) -> None:
        stations: set[str] = set()
        for path in (FINDER, EXTRACTION, IPEDS):
            stations.update(STATION_RE.findall(path.read_text(encoding="utf-8")))
        self.assertTrue(stations)
        self.assertTrue(stations <= set(REGISTRY_STATIONS), stations - set(REGISTRY_STATIONS))

    def test_scheduled_workflows_keep_on_schedule(self) -> None:
        for path in (FINDER, EXTRACTION, IPEDS):
            text = path.read_text(encoding="utf-8")
            self.assertRegex(text, r"(?m)^  schedule:\s*$", msg=f"{path.name} lost on.schedule")
            self.assertRegex(text, r"- cron:")

    def test_extraction_daily_cap_is_ten_with_catchup(self) -> None:
        text = EXTRACTION.read_text(encoding="utf-8")
        self.assertIn('- cron: "17 9 * * *"', text)
        self.assertIn('- cron: "47 */2 * * *"', text)
        self.assertIn("limit=10", text)
        self.assertIn("deadline=40", text)
        self.assertIn("limit=100", text)
        self.assertIn("Catch-up no-op: extraction queue is empty.", text)
        self.assertIn("needs.preflight.outputs.run_drain == 'true'", text)

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

    def test_ipeds_noop_heartbeat_maps_available_count_to_new_release(self) -> None:
        text = IPEDS.read_text(encoding="utf-8")
        self.assertIn("Heartbeat ipeds_release_probe finish", text)
        self.assertIn('"new_release": bool((summary.get("available_count") or 0) > 0)', text)
        self.assertIn("issue_opened", text)


if __name__ == "__main__":
    unittest.main()
