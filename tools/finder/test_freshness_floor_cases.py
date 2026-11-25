"""default_min_fresh_year against the shared freshness-floor cases.

The same rule lives in SQL (cds_freshness_floor), in web/src/lib/freshness.ts,
and in tools/ops/discovery_renewal.py once it lands. They all read
tests/fixtures/freshness_floor_cases.json, so they can't drift apart.
"""

import json
import unittest
from datetime import date
from pathlib import Path

from tools.finder.stuck_pdf_seeds import default_min_fresh_year

CASES = Path(__file__).resolve().parents[2] / "tests" / "fixtures" / "freshness_floor_cases.json"


class FreshnessFloorCases(unittest.TestCase):
    def test_every_shared_case(self):
        cases = json.loads(CASES.read_text())["cases"]
        self.assertGreaterEqual(len(cases), 10, "fixture lost its cases")
        for case in cases:
            with self.subTest(date=case["date"]):
                self.assertEqual(
                    default_min_fresh_year(date.fromisoformat(case["date"])),
                    case["floor"],
                )


if __name__ == "__main__":
    unittest.main()
