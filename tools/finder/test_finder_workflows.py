"""Workflow contracts so the next finder run cannot lose seeds the Friday way."""

from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FINDER = (ROOT / ".github/workflows/ops-finder-probe.yml").read_text()
CATCHUP = (ROOT / ".github/workflows/ops-archive-seed-catchup.yml").read_text()


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

    def test_probe_always_snapshots_yaml_into_the_artifact(self) -> None:
        self.assertIn("cp tools/finder/schools.yaml finder-probe/schools.yaml", FINDER)
        self.assertIn("cp tools/finder/schools.yaml finder-probe/schools-base.yaml", FINDER)


class ArchiveSeedCatchupWorkflowTests(unittest.TestCase):
    def test_runs_on_schools_yaml_push_to_main(self) -> None:
        self.assertIn("push:", CATCHUP)
        self.assertIn("tools/finder/schools.yaml", CATCHUP)
        self.assertIn("HEAD^", CATCHUP)
        self.assertIn("--apply", CATCHUP)


if __name__ == "__main__":
    unittest.main()
