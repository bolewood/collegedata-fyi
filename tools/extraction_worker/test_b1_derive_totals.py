"""Unit tests for B1 All-total derivation (FT+PT)."""

from __future__ import annotations

import json
import unittest
from pathlib import Path

from b1_derive_totals import apply_b1_derived_all_totals


ROOT = Path(__file__).resolve().parents[2]


class B1DeriveTotalsTest(unittest.TestCase):
    def test_interleaved_fallback_pairs(self):
        values = {
            "B.121": {"value": "100"},
            "B.145": {"value": "5"},
            "B.122": {"value": "200"},
            "B.146": {"value": "10"},
            "B.165": {"value": "50"},
            "B.181": {"value": "2"},
            "B.166": {"value": "60"},
            "B.182": {"value": "3"},
        }
        added = apply_b1_derived_all_totals(values)
        self.assertGreaterEqual(added, 4)
        self.assertEqual(values["B.149"]["value"], "105")
        self.assertEqual(values["B.150"]["value"], "210")
        self.assertEqual(values["B.185"]["value"], "52")
        self.assertEqual(values["B.186"]["value"], "63")
        self.assertEqual(values["B.189"]["value"], "157")
        self.assertEqual(values["B.190"]["value"], "273")

    def test_does_not_overwrite_existing(self):
        values = {
            "B.121": {"value": "100"},
            "B.145": {"value": "5"},
            "B.149": {"value": "999"},
        }
        apply_b1_derived_all_totals(values)
        self.assertEqual(values["B.149"]["value"], "999")

    def test_schema_fields_2024_25(self):
        schema = json.loads((ROOT / "schemas" / "cds_schema_2024_25.json").read_text())
        values = {
            "B.121": {"value": "878"},
            "B.145": {"value": "0"},
            "B.122": {"value": "991"},
            "B.146": {"value": "0"},
        }
        added = apply_b1_derived_all_totals(values, schema_fields=schema["fields"])
        self.assertGreaterEqual(added, 2)
        self.assertEqual(values["B.149"]["value"], "878")
        self.assertEqual(values["B.150"]["value"], "991")


if __name__ == "__main__":
    unittest.main()
