"""Producer-vs-registry contract: every key a heartbeat producer emits must be
in the station's allowed_keys in supabase/migrations.

record_pipeline_heartbeat silently drops keys that are not allowed, so a
producer that adds a key without a migration looks green and publishes nothing.
This test reads the registry the way the migrations build it (insert, then
append-updates, in filename order) and fails with the missing key's name.

finder_brave and headless_archive build their summaries inside workflow shell
steps and scripts that cannot be imported or parsed reliably, so they are
checked only for the registry being parseable and non-empty.
"""
from __future__ import annotations

import importlib
import re
import unittest
from datetime import date
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
MIGRATIONS = sorted((REPO / "supabase" / "migrations").glob("*.sql"))

STATIONS = ("discovery_renewal", "finder_stuck_pdf", "finder_brave", "headless_archive")

_STR = re.compile(r"'([^']*)'")
_INSERT = re.compile(
    r"\(\s*'(?P<id>\w+)'\s*,[^;]*?\barray\[(?P<req>[^\]]*)\]\s*,\s*array\[(?P<allowed>[^\]]*)\]\s*\)",
    re.S,
)
_APPEND = re.compile(
    r"s\.allowed_keys\s*\|\|\s*array\[(?P<keys>[^\]]*)\].*?where\s+s\.station_id\s*=\s*'(?P<id>\w+)'",
    re.S,
)
_SET = re.compile(
    r"set\s+allowed_keys\s*=\s*array\[(?P<keys>[^\]]*)\]\s*where\s+station_id\s*=\s*'(?P<id>\w+)'",
    re.S,
)


def _strings(blob: str) -> list[str]:
    return _STR.findall(blob)


def registry() -> dict[str, set[str]]:
    """allowed_keys per station after replaying every migration in order."""
    keys: dict[str, set[str]] = {}
    for path in MIGRATIONS:
        text = path.read_text(encoding="utf-8")
        events: list[tuple[int, str, str, list[str]]] = []
        if "insert into public.pipeline_stations" in text:
            for m in _INSERT.finditer(text):
                events.append((m.start(), "set", m["id"], _strings(m["allowed"])))
        for m in _APPEND.finditer(text):
            events.append((m.start(), "append", m["id"], _strings(m["keys"])))
        for m in _SET.finditer(text):
            events.append((m.start(), "set", m["id"], _strings(m["keys"])))
        for _, kind, station, found in sorted(events):
            if kind == "set":
                keys[station] = set(found)
            else:
                keys.setdefault(station, set()).update(found)
    return keys


def _rows(prev_schools: int = 6) -> list[dict]:
    rows = []
    for i in range(prev_schools):
        for year in ("2023-24", "2024-25"):
            rows.append({"school_id": f"s{i}", "canonical_year": year,
                         "participation_status": "published", "removed_at": None,
                         "discovered_at": "2026-01-01T00:00:00+00:00"})
        if i % 2:
            rows.append({"school_id": f"s{i}", "canonical_year": "2025-26",
                         "participation_status": "published", "removed_at": None,
                         "discovered_at": "2026-01-01T00:00:00+00:00"})
    return rows


class HeartbeatKeyRegistry(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.reg = registry()

    def missing(self, station: str, emitted: set[str]) -> list[str]:
        return sorted(emitted - self.reg.get(station, set()))

    def test_registry_parses_for_every_station(self) -> None:
        for station in STATIONS:
            self.assertTrue(self.reg.get(station), f"no allowed_keys parsed for {station}")

    def test_discovery_renewal_keys_are_registered(self) -> None:
        dr = importlib.import_module("tools.ops.discovery_renewal")
        result = dr.compute(_rows(), date(2026, 11, 24), enforce_min_prev=False)
        emitted = set(dr.summary_dict(result, run_url="https://example.invalid/run"))
        # Written by the alarm step after summary_dict.
        emitted |= {"alarm_issue", "outstanding_below_floor", "outstanding_years"}
        try:
            ff = importlib.import_module("tools.ops.fetch_failures")
        except ImportError:
            ff = None  # not on main yet: nothing to check
        if ff is not None:
            emitted |= set(getattr(ff, "SUMMARY_KEYS", ()))
        self.assertEqual(self.missing("discovery_renewal", emitted), [],
                         "producer emits keys the migration registry does not allow")

    def test_stuck_pdf_keys_are_registered(self) -> None:
        ro = importlib.import_module("tools.finder.reprobe_outcome")
        emitted = set(ro.summarize([], {"flagged": 0}, reprobed=0))
        self.assertEqual(self.missing("finder_stuck_pdf", emitted), [],
                         "producer emits keys the migration registry does not allow")

    def test_a_missing_key_is_reported_by_name(self) -> None:
        self.assertEqual(self.missing("finder_stuck_pdf", {"stuck", "not_a_real_key"}),
                         ["not_a_real_key"])


if __name__ == "__main__":
    unittest.main()
