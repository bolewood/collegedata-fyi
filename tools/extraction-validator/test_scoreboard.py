"""Tests for the extraction scoreboard's pure parts (no network)."""

from __future__ import annotations

import contextlib
import datetime as dt
import io
import json
import random
import socket
import sys
import tempfile
import unittest
import urllib.request
from collections import Counter
from decimal import Decimal
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
import scoreboard  # noqa: E402
from scoreboard import projection  # noqa: E402

SCHEMA_DIR = Path(__file__).resolve().parents[2] / "schemas"


def numbers(**values: int) -> dict[str, Decimal]:
    return {key.replace("_", "."): Decimal(value) for key, value in values.items()}


class SumCheckIdsMatchTheSchemas(unittest.TestCase):
    """Every id in SUM_CHECKS is the row its check says it is, in that year's schema."""

    def labels(self, year: str) -> dict[str, dict]:
        schema = json.loads((SCHEMA_DIR / f"cds_schema_{year.replace('-', '_')}.json").read_text())
        return {field["question_number"]: field for field in schema["fields"]}

    def test_totals_and_rows(self) -> None:
        for year, checks in scoreboard.SUM_CHECKS.items():
            labels = self.labels(year)
            for check in checks:
                with self.subTest(year=year, check=check.name):
                    total = labels[check.total]
                    self.assertIn("total", total["question"].lower())
                    for rows, required in check.groups:
                        self.assertTrue(set(required) <= set(rows))
                        for row in rows:
                            self.assertIn(row, labels)
                            self.assertNotEqual(row, check.total)
                    if check.table == "C1":
                        word = {"applied": "applied", "admitted": "admitted", "enrolled": "enrolled"}[check.name.split()[0]]
                        for field_id in (check.total, *check.groups[0][0]):
                            self.assertIn(word, labels[field_id]["question"].lower())
                            self.assertNotIn(labels[field_id]["residency"], ("In-State", "Out-of-State"))
                    if check.table == "H1":
                        column = "Non-need-based" if check.name.startswith("non-need") else "Need-based"
                        for field_id in (check.total, *check.groups[0][0]):
                            self.assertTrue(labels[field_id]["subsection"].startswith(column), field_id)
                        kind = "Scholarships/Grants" if "grants" in check.name else "Self-Help"
                        self.assertIn(kind, total["question"])
                    if check.table == "B1":
                        for field_id in (check.total, *check.groups[0][0]):
                            self.assertIn("total", labels[field_id]["question"].lower())

    def test_h1_grant_rows_are_the_four_sources(self) -> None:
        for year, checks in scoreboard.SUM_CHECKS.items():
            labels = self.labels(year)
            for check in checks:
                if check.table == "H1" and "grants" in check.name:
                    starts = [labels[r]["question"].split()[0].rstrip(":") for r in check.groups[0][0]]
                    self.assertEqual(starts, ["Federal", "State", "Institutional", "Scholarships/grants"], (year, check.name))


class RunCheck(unittest.TestCase):
    def test_pass_fail_and_not_checkable(self) -> None:
        check = scoreboard.SUM_CHECKS["2024-25"][0]  # C.117 = C.101..C.104, men and women required
        self.assertEqual(scoreboard.run_check(check, numbers(C_117=30, C_101=10, C_102=20)), "pass")
        self.assertEqual(scoreboard.run_check(check, numbers(C_117=31, C_101=10, C_102=20)), "fail")
        self.assertEqual(scoreboard.run_check(check, numbers(C_117=30, C_101=10)), "nc")
        self.assertEqual(scoreboard.run_check(check, numbers(C_101=10, C_102=20)), "nc")

    def test_a_zero_total_beside_filled_rows_is_not_checkable(self) -> None:
        check = scoreboard.SUM_CHECKS["2024-25"][0]
        self.assertEqual(scoreboard.run_check(check, numbers(C_117=0, C_101=10, C_102=20)), "nc")
        self.assertEqual(scoreboard.run_check(check, numbers(C_117=0, C_101=0, C_102=0)), "pass")

    def test_second_group_is_used_when_the_first_was_not_read(self) -> None:
        enrolled = next(c for c in scoreboard.SUM_CHECKS["2025-26"] if c.name == "enrolled by sex")
        self.assertEqual(scoreboard.run_check(enrolled, numbers(C_118=50, C_110=20, C_112=25, C_113=5)), "pass")

    def test_dollar_totals_allow_rounding(self) -> None:
        grants = next(c for c in scoreboard.SUM_CHECKS["2023-24"] if c.name == "need-based grants")
        self.assertEqual(scoreboard.run_check(grants, numbers(H_110=1004, H_106=500, H_108=500)), "pass")
        self.assertEqual(scoreboard.run_check(grants, numbers(H_110=1006, H_106=500, H_108=500)), "fail")
        self.assertEqual(scoreboard.run_check(grants, numbers(H_110=1000)), "nc")

    def test_one_failing_check_fails_the_table(self) -> None:
        outcome = scoreboard.table_outcomes("2024-25", numbers(
            C_117=30, C_101=10, C_102=20, C_118=9, C_105=5, C_106=5, B_193=100, B_195=100))
        self.assertEqual(outcome, {"B1": "pass", "C1": "fail", "H1": "nc"})
        self.assertEqual(scoreboard.table_outcomes("2019-20", {}), {"B1": "nc", "C1": "nc", "H1": "nc"})


class Admissions(unittest.TestCase):
    def test_rows_by_sex_then_printed_total(self) -> None:
        got = scoreboard.printed_admissions(
            "2023-24", numbers(C_117=3109, C_105=5, C_106=7, C_118=99, C_109=3, C_119=40))
        self.assertEqual(got, {"applied": 3109, "admitted": 12, "enrolled": 40})
        self.assertEqual(scoreboard.printed_admissions("2023-24", {})["applied"], None)

    def test_numbers_are_parsed_as_the_projection_parses_them(self) -> None:
        definitions = projection.load_schema_definitions()["2023-24"]
        values = {"C.117": {"value": "3,109"}, "C.101": {"value": "1182"}, "A.001": {"value": "A name"}}
        got = scoreboard.numbers_from_values(values, definitions, "2023-24")
        self.assertEqual(got, {"C.117": Decimal(3109), "C.101": Decimal(1182)})

    def test_a_field_the_sanity_rules_reject_is_dropped(self) -> None:
        definitions = projection.load_schema_definitions()["2024-25"]
        values = {field: {"value": value} for field, value in
                  {"C.117": "100", "C.118": "5000", "C.119": "20"}.items()}
        rejected = projection._sanity.implausible_fields(
            "2024-25", {k: Decimal(v["value"]) for k, v in values.items()})
        got = scoreboard.numbers_from_values(values, definitions, "2024-25")
        self.assertEqual(set(got), set(values) - set(rejected))

    def test_federal_classes(self) -> None:
        self.assertEqual(scoreboard.classify_federal(1020, Decimal(1000)), "match")
        self.assertEqual(scoreboard.classify_federal(1021, Decimal(1000)), "different")
        self.assertEqual(scoreboard.classify_federal(None, Decimal(1000)), "blank")
        self.assertIsNone(scoreboard.classify_federal(5, None))

    def test_percentile_is_nearest_rank(self) -> None:
        self.assertEqual(scoreboard.percentile(list(range(1, 11)), 10), 1)
        self.assertEqual(scoreboard.percentile(list(range(1, 11)), 50), 5)
        self.assertEqual(scoreboard.percentile([7], 10), 7)
        self.assertIsNone(scoreboard.percentile([], 50))


class PickServedArtifact(unittest.TestCase):
    """Lazy loading picks the row the projection's own sort puts first."""

    def test_agrees_with_the_projection_on_random_candidates(self) -> None:
        rng = random.Random(7)
        producers = list(projection.BASE_PRODUCER_RANK) + ["tier4_llm_fallback"]
        for case in range(400):
            full = []
            for index in range(rng.randint(1, 7)):
                producer = rng.choice(producers)
                column = rng.choice([None, "", "2023-24", "2024-25"])
                stats = {"acroform_fields_total": 80, "schema_fields_populated": rng.choice([0, 40]),
                         "unmapped_acroform_fields": 78}
                full.append({
                    "id": f"{case}-{index}", "kind": "canonical", "producer": producer,
                    "producer_version": "1", "schema_version": column,
                    "created_at": f"2026-0{rng.randint(1, 9)}-01",
                    "notes": {"schema_version": rng.choice([None, "2023-24", "2024-25"]),
                              "schema_fallback_used": rng.random() < 0.3, "stats": stats, "values": {}},
                })
            by_id = {row["id"]: row for row in full}
            bare = [{k: v for k, v in row.items() if k != "notes"} for row in full]
            loaded: list[str] = []

            def load(row: dict) -> dict:
                loaded.append(row["id"])
                return by_id[row["id"]]

            picked = scoreboard.pick_served_artifact(bare, "2023-24", load)
            base = [r for r in full if r["producer"] in projection.BASE_PRODUCER_RANK]
            expected = projection.sort_base_candidates(base, "2023-24")[0] if base else None
            self.assertEqual(picked and picked["id"], expected and expected["id"], f"case {case}")
            self.assertEqual(len(loaded), len(set(loaded)))

    def test_reads_one_artifact_when_the_newest_is_the_plain_choice(self) -> None:
        rows = [
            {"id": "old", "kind": "canonical", "producer": "tier4_docling", "schema_version": None, "created_at": "2026-05-01"},
            {"id": "new", "kind": "canonical", "producer": "tier4_docling", "schema_version": "2023-24", "created_at": "2026-11-01"},
        ]
        loaded: list[str] = []

        def load(row: dict) -> dict:
            loaded.append(row["id"])
            return {**row, "notes": {"schema_fallback_used": False, "values": {}}}

        self.assertEqual(scoreboard.pick_served_artifact(rows, "2023-24", load)["id"], "new")
        self.assertEqual(loaded, ["new"])


class RenderAndHolds(unittest.TestCase):
    def document(self, **overrides) -> dict:
        doc = {
            "document_id": "d1", "school_id": "example", "year": "2024-25", "format": "pdf_flat", "flag": None,
            "sub_institutional": False,
            "producer": "tier4_docling", "version": "0.3.36", "schema_version": "2024-25", "fields": 500,
            "newest_producer": "tier4_docling", "newest_version": "0.3.36", "newest_at": "2026-11-01",
            "admissions": {"applied": 10, "admitted": 5, "enrolled": 2},
            "federal": {"applied": "match", "admitted": "blank", "enrolled": "different"},
            "sums": {"B1": "pass", "C1": "fail", "H1": "nc"},
        }
        doc.update(overrides)
        return doc

    def data(self, documents: list[dict]) -> dict:
        return {"generated_at": "2026-11-23T00:00:00Z", "years": ["2024-25"], "current_tier4_version": "0.3.38",
                "projected_years": ["2024-25"], "federal_schools": {"2024-25": 1700}, "hold_summaries_read": 1,
                "not_served": {}, "documents": documents}

    def test_counts_and_deltas(self) -> None:
        before = self.data([self.document()])
        after = self.data([self.document(version="0.3.38", newest_version="0.3.38",
                                         federal={"applied": "match", "admitted": "match", "enrolled": "different"}),
                           self.document(document_id="d2", flag="low_coverage", fields=3)])
        metrics = scoreboard.aggregate(after)
        self.assertEqual(metrics["2024-25|all|docs"], 1)          # the flagged document is left out
        self.assertEqual(metrics["2024-25|all|flagged"], 1)
        self.assertEqual(metrics["2024-25|all|fields_median"], 500)
        self.assertEqual(metrics["2024-25|all|federal_match"], 2)
        self.assertEqual(metrics["2024-25|all|tier4_current"], 1)
        text = scoreboard.render(after, before)
        self.assertIn("| 2024-25 | all | 1 | 3 | 2 (+1) | 0 (-1) | 1 | 66.7% |", text)
        self.assertIn("Flagged: 2024-25 low coverage 1.", text)

    def test_holds_keep_only_a_latest_guard_outcome(self) -> None:
        import tempfile
        with tempfile.TemporaryDirectory() as folder:
            runs = [
                ("a", "2026-11-22T10:00:00+00:00", [("d1", "tier4_field_regression (400 < 420 fields; kept)"),
                                                    ("d2", "tier4_table_field_regression (B1; kept)")]),
                ("b", "2026-11-23T10:00:00+00:00", [("d2", "tier4_extracted")]),
            ]
            for name, finished, documents in runs:
                Path(folder, f"{name}.summary.json").write_text(json.dumps({
                    "finished_at": finished,
                    "documents": [{"document_id": d, "action": a} for d, a in documents]}))
            holds = scoreboard.load_holds(str(Path(folder) / "*.summary.json"))
        self.assertEqual(set(holds), {"d1"})
        self.assertEqual(holds["d1"]["guard"], "tier4_field_regression")

    def summaries(self, folder: str, runs: list[tuple]) -> str:
        for name, finished, dry_run, documents in runs:
            Path(folder, f"{name}.summary.json").write_text(json.dumps({
                "finished_at": finished, "dry_run": dry_run,
                "documents": [{"document_id": d, "action": a} for d, a in documents]}))
        return str(Path(folder) / "*.summary.json")

    def test_an_unchanged_reclean_is_known_by_its_cleaner_version(self) -> None:
        import tempfile
        unchanged = "tier4_reclean_unchanged (412 fields; cleaner 0.3.38 reads what is stored)"
        wrapped = "tier2_label_acroform_fallback_" + unchanged.replace("0.3.38", "0.3.37")
        with tempfile.TemporaryDirectory() as folder:
            pattern = self.summaries(folder, [
                ("a", "2026-11-22T10:00:00+00:00", False, [("d1", unchanged), ("d2", unchanged), ("d3", wrapped)]),
                # A later run that wrote nothing for another reason leaves the check standing.
                ("b", "2026-11-23T10:00:00+00:00", False, [("d1", "tier4_reclean_error: timeout"),
                                                           ("d5", "tier4_recleaned (413 fields, 9 chars, 2 pages)")]),
                # A dry run makes the same comparison, so its check counts, and the later one is kept.
                ("c", "2026-11-24T10:00:00+00:00", True, [("d2", unchanged.replace("0.3.38", "0.3.39")),
                                                          ("d4", unchanged)]),
            ])
            checked = scoreboard.load_unchanged(pattern)
        self.assertEqual(checked, {
            "d1": {"at": "2026-11-22T10:00:00+00:00", "version": "0.3.38"},
            "d2": {"at": "2026-11-24T10:00:00+00:00", "version": "0.3.39"},
            "d3": {"at": "2026-11-22T10:00:00+00:00", "version": "0.3.37"},
            "d4": {"at": "2026-11-24T10:00:00+00:00", "version": "0.3.38"},
        })

    def test_a_dry_run_does_not_clear_a_hold(self) -> None:
        import tempfile
        with tempfile.TemporaryDirectory() as folder:
            pattern = self.summaries(folder, [
                ("a", "2026-11-22T10:00:00+00:00", False, [("d1", "tier4_table_field_regression (B1; kept)")]),
                ("b", "2026-11-23T10:00:00+00:00", True, [("d1", "tier4_recleaned (413 fields, 9 chars, 2 pages)")]),
            ])
            self.assertEqual(set(scoreboard.load_holds(pattern)), {"d1"})

    def test_read_by_the_current_cleaner_counts_written_and_unchanged(self) -> None:
        documents = [
            self.document(document_id="written", version="0.3.38"),
            self.document(document_id="unchanged", version="0.3.20", checked_version="0.3.38"),
            self.document(document_id="checked-earlier", version="0.3.17", checked_version="0.3.37"),
            self.document(document_id="never", version="0.3.36"),
            self.document(document_id="other", producer="tier2_acroform", version="0.3.38"),
        ]
        metrics = scoreboard.aggregate(self.data(documents))
        self.assertEqual(metrics["2024-25|all|tier4"], 4)
        self.assertEqual(metrics["2024-25|all|tier4_checked"], 2)
        self.assertEqual(metrics["2024-25|all|tier4_current"], 1)
        text = scoreboard.render(self.data(documents))
        self.assertIn("| Read by 0.3.38 | Of those, written by it | Tier 4, not yet read by it |", text)
        self.assertIn("| 2024-25 | 5 | 4 | 2 | 1 | 0.3.36: 1, 0.3.17: 1 | tier2_acroform 0.3.38: 1 |", text)
        # A scoreboard saved before this measure existed is counted by version alone.
        old = self.data([self.document(document_id="written")])
        self.assertIn("| 2024-25 | 5 | 4 (+3) | 2 (+2) | 1 (+1) |", scoreboard.render(self.data(documents), old))


# ---------------------------------------------------------------------------
# PRD 040 M0: near misses, the classifier, run_format 2, --public, renewal
# ---------------------------------------------------------------------------

def values_for(outcomes: dict) -> dict:
    """`federal_values` that agree with `outcomes`: a match is 100 against 100, a blank has no number of ours, a
    different value is 150 against 100 (50% over, the large band), and no outcome means IPEDS has no figure."""
    cases = {"match": (100, "100"), "blank": (None, "100"), "different": (150, "100"), None: (100, None)}
    return {m: {"ours": cases[o][0], "federal": cases[o][1], "federal_data_year": 2023} for m, o in outcomes.items()}


TUITION_NAMES = {"g1_private_undergraduates": ("G.102", "tuition_in_state"), "g1_in_state_undergraduates": ("G.108", "tuition_in_state"),
                 "g1_out_of_state_undergraduates": ("G.109", "tuition_out_of_state"), "g1_private_first_year": ("G.101", "tuition_in_state"),
                 "g1_in_state_first_year": ("G.104", "tuition_in_state"), "g1_out_of_state_first_year": ("G.105", "tuition_out_of_state")}


def extra_for(year: str, enrollment: tuple = ("1000", "1000"), tuition: tuple = ("30000", "30000")) -> dict:
    """`federal_extra` as the run writes it: B1 and the six G1 candidates, each with (ours, IPEDS) strings or None.
    `tuition` is our G.102 figure and IPEDS' in-state tuition; the other candidates are empty. As in the 2026-11-25
    run, fall 2025 enrollment and the tuition of academic years 2025-26 and later (CDS 2024-25 and 2025-26) have no
    IPEDS figure loaded."""
    start = int(year[:4])
    loaded = start < 2025
    extra = {"b1_undergraduates": {"cds_field": "B.176" if start >= 2025 else "B.193", "ours": enrollment[0], "federal_key": "undergraduate_enrollment",
                                   "federal": enrollment[1] if loaded else None, "federal_data_year": start}}
    for name, (field, key) in TUITION_NAMES.items():
        mine = name == "g1_private_undergraduates"
        extra[name] = {"cds_field": field, "ours": tuition[0] if mine else None, "federal_key": key,
                       "federal": tuition[1] if (start < 2024 and key == "tuition_in_state") else None, "federal_data_year": start + 1}
    return extra


def doc(document_id: str, year: str, **overrides) -> dict:
    """A served document of a run, with the keys the public builder reads."""
    base = {
        "document_id": document_id, "school_id": f"school-{document_id}", "year": year, "format": "pdf_flat",
        "flag": None, "sub_institutional": False, "producer": "tier4_docling", "version": "0.3.43",
        "schema_version": year, "fields": 500, "newest_producer": "tier4_docling", "newest_version": "0.3.43",
        "newest_at": "2026-11-01", "admissions": {"applied": 10, "admitted": 5, "enrolled": 2},
        "federal": {"applied": "match", "admitted": "match", "enrolled": "match"},
        "sums": {"B1": "pass", "C1": "pass", "H1": "pass"}, "check_numbers": {},
    }
    base.update(overrides)
    base.setdefault("federal_values", values_for(base["federal"]))
    base.setdefault("federal_extra", extra_for(year))
    base.setdefault("sections", {"A": {"reported": 10, "not_applicable": 2}, "C": {"reported": 100, "parse_error": 3}})
    return base


def entry(document_id: str, year: str, status: str = "extracted", fmt: str | None = "pdf_flat",
          flag: str | None = None, removed: bool = False) -> dict:
    return {"document_id": document_id, "year": year, "source_format": fmt, "extraction_status": status,
            "data_quality_flag": flag, "removed": removed}


class NearMisses(unittest.TestCase):
    """A failing enrollment or admissions sum is a near miss when its gap is
    under 2% of its printed total."""

    def c1_applied(self, total: int, men: int, women: int) -> str:
        return scoreboard.table_outcomes("2024-25", numbers(C_117=total, C_101=men, C_102=women))["C1"]

    def test_gap_is_a_share_of_the_printed_total(self) -> None:
        check = scoreboard.SUM_CHECKS["2024-25"][0]
        self.assertEqual(scoreboard.run_check_detail(check, numbers(C_117=2462, C_101=1200, C_102=1256)),
                         ("fail", Decimal(6) / Decimal(2462)))  # the Vassar case: a small cell left out
        self.assertEqual(scoreboard.run_check_detail(check, numbers(C_117=30, C_101=10, C_102=20)), ("pass", None))
        self.assertEqual(scoreboard.run_check_detail(check, numbers(C_101=10, C_102=20)), ("nc", None))

    def test_the_split_is_strictly_under_two_percent(self) -> None:
        self.assertEqual(self.c1_applied(1000, 500, 481), "near")   # 1.9%
        self.assertEqual(self.c1_applied(1000, 500, 480), "fail")   # exactly 2%
        self.assertEqual(self.c1_applied(1000, 500, 400), "fail")
        self.assertEqual(self.c1_applied(1000, 500, 500), "pass")
        self.assertEqual(self.c1_applied(1000, 500, 519), "near")   # rows above the total count the same way

    def test_one_far_miss_outweighs_a_near_miss_and_a_pass(self) -> None:
        got = scoreboard.table_outcomes("2024-25", numbers(
            C_117=1000, C_101=500, C_102=490,      # applied: 1% off
            C_118=100, C_105=50, C_106=10,         # admitted: 40% off
            C_119=60, C_109=30, C_111=30))         # enrolled: passes
        self.assertEqual(got["C1"], "fail")
        near_and_pass = scoreboard.table_outcomes("2024-25", numbers(
            C_117=1000, C_101=500, C_102=490, C_119=60, C_109=30, C_111=30))
        self.assertEqual(near_and_pass["C1"], "near")

    def test_financial_aid_is_never_a_near_miss(self) -> None:
        grants = scoreboard.table_outcomes("2024-25", numbers(H_110=1000000, H_106=500000, H_108=499000))
        self.assertEqual(grants["H1"], "fail")

    def test_other_forms_split_on_their_own_field_ids(self) -> None:
        # (year, table, printed total, two rows that should add to it)
        cases = [
            ("2023-24", "C1", "C.117", ("C.101", "C.102")),
            ("2023-24", "B1", "B.193", ("B.149", "B.150")),
            ("2025-26", "C1", "C.116", ("C.101", "C.102")),
            ("2025-26", "C1", "C.117", ("C.104", "C.105")),
            ("2025-26", "B1", "B.176", ("B.113", "B.138")),
        ]
        for year, table, total, rows in cases:
            first, second = rows
            for second_value, expected in ((481, "near"), (480, "fail"), (500, "pass"), (400, "fail")):
                nums = {total: Decimal(1000), first: Decimal(500), second: Decimal(second_value)}
                with self.subTest(year=year, total=total, second=second_value):
                    self.assertEqual(scoreboard.table_outcomes(year, nums)[table], expected)
        # 2025-26 enrolled uses its second group of rows when the first was not read.
        nums = {"C.118": Decimal(1000), "C.110": Decimal(500), "C.112": Decimal(481)}
        self.assertEqual(scoreboard.table_outcomes("2025-26", nums)["C1"], "near")
        nums["C.112"] = Decimal(400)
        self.assertEqual(scoreboard.table_outcomes("2025-26", nums)["C1"], "fail")
        # 2025-26 undergraduate + graduate total.
        nums = {"B.178": Decimal(1000), "B.176": Decimal(990)}
        self.assertEqual(scoreboard.table_outcomes("2025-26", nums)["B1"], "near")
        # Financial aid on the 2025-26 and 2023-24 ids is never a near miss.
        self.assertEqual(scoreboard.table_outcomes("2025-26", {
            "H.109": Decimal(1000000), "H.105": Decimal(500000), "H.106": Decimal(499000)})["H1"], "fail")
        self.assertEqual(scoreboard.table_outcomes("2023-24", {
            "H.110": Decimal(1000000), "H.106": Decimal(500000), "H.108": Decimal(499000)})["H1"], "fail")

    def test_enrollment_splits_too(self) -> None:
        got = scoreboard.table_outcomes("2024-25", numbers(B_193=1000, B_149=500, B_150=490))
        self.assertEqual(got["B1"], "near")

    def test_a_zero_total_with_rows_is_not_checkable_not_a_gap(self) -> None:
        self.assertEqual(self.c1_applied(0, 10, 20), "nc")

    def test_the_near_miss_report_counts_sums_and_tables(self) -> None:
        run = {"generated_at": "2026-11-25T00:00:00Z", "documents": [
            doc("a", "2024-25", check_numbers={"C.117": "1000", "C.101": "500", "C.102": "490"}),
            doc("b", "2024-25", check_numbers={"C.117": "1000", "C.101": "500", "C.102": "100"}),
            doc("c", "2024-25", flag="low_coverage", check_numbers={"C.117": "1000", "C.101": "500", "C.102": "100"}),
        ]}
        got = scoreboard.near_miss_counts(run)["2024-25|C1"]
        self.assertEqual((got["sums_failing"], got["sums_near"], got["sums_over"]), (2, 1, 1))
        self.assertEqual((got["tables_near"], got["tables_fail"]), (1, 1))
        flagged_too = scoreboard.near_miss_counts(run, published_only=False)["2024-25|C1"]
        self.assertEqual(flagged_too["sums_failing"], 3)
        self.assertIn("1 of 2 failing sums are under 2%", scoreboard.render_near_miss(run))


class Classifier(unittest.TestCase):
    """Every manifest document gets exactly one class, in a fixed order."""

    served = {"producer": "tier4_docling"}

    def classify(self, served: dict | None = served, **kw) -> str:
        return scoreboard.classify_document(entry("d", "2024-25", **kw), served)

    def test_every_status(self) -> None:
        self.assertEqual(self.classify(removed=True), "removed")
        self.assertEqual(self.classify(None, status="not_applicable"), "no_file")
        self.assertEqual(self.classify(status="extracted"), "published")
        self.assertEqual(self.classify(None, status="failed"), "couldnt_read")
        self.assertEqual(self.classify(None, status="extraction_pending"), "not_read_yet")
        self.assertEqual(self.classify(None, status="discovered"), "not_read_yet")

    def test_flags_set_a_document_aside_whatever_its_status(self) -> None:
        for flag in scoreboard.HIDDEN_FLAGS:
            self.assertEqual(self.classify(flag=flag), "set_aside")
            self.assertEqual(self.classify(None, status="failed", flag=flag), "set_aside")  # failed AND flagged
            self.assertEqual(self.classify(None, status="extraction_pending", flag=flag), "set_aside")
            self.assertEqual(self.classify(None, status="extracted", flag=flag), "set_aside")  # flagged, no extraction
        self.assertEqual(self.classify(flag="some_future_flag"), "published")

    def test_removed_and_no_file_come_first(self) -> None:
        self.assertEqual(self.classify(removed=True, flag="blank_template", status="failed"), "removed")
        self.assertEqual(self.classify(None, status="not_applicable", flag="blank_template"), "no_file")

    def test_extracted_without_a_usable_extraction_is_not_read_yet(self) -> None:
        self.assertEqual(self.classify(None, status="extracted"), "not_read_yet")
        self.assertEqual(self.classify({"producer": None}, status="extracted"), "not_read_yet")

    def test_a_held_document_is_published(self) -> None:
        self.assertEqual(self.classify({"producer": "tier4_docling", "hold": "tier4_field_regression"}), "published")

    def test_an_unknown_status_is_an_error_not_a_default(self) -> None:
        with self.assertRaises(ValueError):
            self.classify(None, status="mystery")


YEARS = ["2023-24", "2024-25", "2025-26"]


def synthetic_run() -> dict:
    """A run_format 3 run with every status, several formats, flags, a held
    document, a single-campus report, and a year with no federal figures."""
    manifest: list[dict] = []
    documents: list[dict] = []
    counter = iter(range(1000))
    no_federal = {"applied": None, "admitted": None, "enrolled": None}

    def add(year, status="extracted", fmt="pdf_flat", flag=None, removed=False, served=True, **doc_kw):
        document_id = f"d{next(counter)}"
        manifest.append(entry(document_id, year, status, fmt, flag, removed))
        if status == "extracted" and not removed:
            fields = {"format": fmt or "unknown", "flag": flag, **doc_kw}
            if not served:
                fields.update(producer=None, version=None, schema_version=None, fields=0, federal=no_federal,
                              sums={"B1": "nc", "C1": "nc", "H1": "nc"})
            documents.append(doc(document_id, year, **fields))

    for year in YEARS:
        federal = no_federal if year == "2025-26" else {"applied": "match", "admitted": "blank", "enrolled": "different"}
        for i in range(8):
            add(year, fields=400 + 20 * i, federal=federal,
                sums={"B1": ["pass", "near", "fail", "nc"][i % 4], "C1": ["pass", "pass", "near", "nc"][i % 4],
                      "H1": ["pass", "fail", "nc", "pass"][i % 4]})
        for i in range(3):
            add(year, fmt="pdf_fillable", fields=900 + i, federal=federal)
        add(year, fmt="xlsx", fields=1000, federal=no_federal, sub_institutional=True)
        add(year, fmt="unknown", fields=300, federal=no_federal)
        add(year, flag="blank_template")
        add(year, flag="low_coverage", fmt="pdf_fillable")
        add(year, status="failed", fmt="pdf_scanned")
        add(year, status="failed", flag="wrong_file")
        add(year, status="extraction_pending", fmt="html")
        add(year, served=False, fmt="docx")
        add(year, removed=True)
        add(year, status="not_applicable", fmt=None)
    documents[0]["hold"] = "tier4_field_regression"
    other_year = "2023-24" if documents[1]["year"] != "2023-24" else "2025-26"
    documents[1]["schema_version"] = other_year     # numbered by another year's form
    documents[1]["federal_extra"]["b1_undergraduates"]["cds_field"] = "B.176" if other_year == "2025-26" else "B.193"
    return {
        "run_format": 3, "sum_check_version": 2, "limit": None, "generated_at": "2026-11-25T01:15:08Z",
        "years": YEARS, "current_tier4_version": "0.3.43", "projected_years": ["2024-25", "2025-26"],
        "federal_schools": {"2023-24": 1900, "2024-25": 1900, "2025-26": 0},
        "hold_summaries_read": 1, "not_served": {}, "manifest": manifest, "documents": documents,
        "federal_left_out": {y: scoreboard.federal_left_out(documents, y) for y in YEARS},
        "forms": scoreboard.forms_for(YEARS),
        "renewal": {"as_of": "2026-11-25", "current_year": "2025-26", "previous_year": "2024-25", "current": 380,
                    "previous": 479, "both": 364, "two_year_previous": 536, "two_year_both": 370},
    }


def blocked_network() -> contextlib.ExitStack:
    """Any attempt to open a socket or a URL fails the test."""
    def refuse(*args, **kwargs):
        raise AssertionError("--public made a network call")
    stack = contextlib.ExitStack()
    stack.enter_context(mock.patch.object(socket.socket, "connect", refuse))
    stack.enter_context(mock.patch.object(socket, "create_connection", refuse))
    stack.enter_context(mock.patch.object(urllib.request, "urlopen", refuse))
    return stack


class PublicSnapshot(unittest.TestCase):
    def setUp(self) -> None:
        self.run = synthetic_run()
        with blocked_network():
            self.public = scoreboard.build_public(self.run, "scoreboard-20261125T011508Z.json")

    def year(self, name: str) -> dict:
        return next(y for y in self.public["years"] if y["cds_year"] == name)

    def test_top_level_and_renewal(self) -> None:
        self.assertEqual(self.public["public_format"], 4)
        self.assertEqual(self.public["snapshot_of"], "2026-11-25T01:15:08Z")
        self.assertEqual(self.public["scoreboard_run"], "scoreboard-20261125T011508Z.json")
        self.assertEqual(self.public["renewal"], self.run["renewal"])
        self.assertEqual([y["cds_year"] for y in self.public["years"]], YEARS)

    def test_the_duplicate_block_stays_in_the_run_and_out_of_the_public_snapshot(self) -> None:
        run = {**self.run, "same_year_duplicates": scoreboard.same_year_duplicates_block(self.run["documents"])}
        with blocked_network():
            public = scoreboard.build_public(run, "x.json")
        self.assertNotIn("same_year_duplicates", json.dumps(public))
        self.assertNotIn("source_url", json.dumps(public))

    def test_statuses_sum_to_live_and_live_plus_removed_plus_no_file_to_the_manifest(self) -> None:
        for year in self.public["years"]:
            name = year["cds_year"]
            in_manifest = sum(1 for m in self.run["manifest"] if m["year"] == name)
            live = sum(year["total"]["status"].values())
            with self.subTest(year=name):
                self.assertEqual(sum(sum(r["status"].values()) for r in year["rows"]), live)
                self.assertEqual(live + year["removed"] + year["no_file"], in_manifest)
                self.assertEqual((year["removed"], year["no_file"]), (1, 1))
                self.assertEqual(year["total"]["status"],
                                 {"published": 13, "set_aside": 3, "couldnt_read": 1, "not_read_yet": 2})

    def test_set_aside_keeps_its_reason(self) -> None:
        for year in self.public["years"]:
            self.assertEqual(year["set_aside_reasons"], {"blank_form": 1, "too_little_read": 1, "wrong_file": 1})
            self.assertEqual(sum(year["set_aside_reasons"].values()), year["total"]["status"]["set_aside"])

    def test_row_bounds_and_totals_are_the_sum_of_the_rows(self) -> None:
        for year in self.public["years"]:
            for row in [*year["rows"], year["total"]]:
                with self.subTest(year=year["cds_year"], format=row.get("format", "total")):
                    f = row["federal"]
                    self.assertLessEqual(f["reports"], row["status"]["published"])
                    self.assertEqual(f["matches"] + f["no_value"] + f["differs"], f["values"])
                    self.assertEqual(f["differs_2_to_10pct"] + f["differs_over_10pct"], f["differs"])
                    self.assertLessEqual(f["values"], 3 * f["reports"])
                    t = row["totals"]
                    self.assertEqual(t["reports"], row["status"]["published"])
                    for table in ("B1", "C1", "H1"):
                        self.assertEqual(sum(t[table].values()), t["reports"])
            for block in ("status", "federal"):
                for key in year["total"][block]:
                    self.assertEqual(sum(r[block][key] for r in year["rows"]), year["total"][block][key])
            for table in ("B1", "C1", "H1"):
                for key in year["total"]["totals"][table]:
                    self.assertEqual(sum(r["totals"][table][key] for r in year["rows"]),
                                     year["total"]["totals"][table][key])
            self.assertEqual(sum(r["totals"]["reports"] for r in year["rows"]), year["total"]["totals"]["reports"])

    def test_other_and_unknown_formats_share_one_row_and_every_live_format_appears(self) -> None:
        rows = self.year("2024-25")["rows"]
        self.assertEqual([r["format"] for r in rows],
                         ["pdf_flat", "pdf_fillable", "pdf_scanned", "xlsx", "docx", "html", "other"])
        self.assertEqual({r["label"] for r in rows if r["format"] == "other"}, {"other or unknown format"})

    def test_a_year_without_federal_figures_has_zero_federal_counts(self) -> None:
        year = self.year("2025-26")
        self.assertFalse(year["federal_fall_loaded"])
        self.assertEqual(year["total"]["federal"], {"reports": 0, "values": 0, "matches": 0, "no_value": 0, "differs": 0,
                                                            "differs_2_to_10pct": 0, "differs_over_10pct": 0})
        self.assertEqual(year["federal_left_out"]["no_federal_figures"], 0)
        self.assertTrue(self.year("2024-25")["federal_fall_loaded"])
        self.assertEqual(self.year("2024-25")["federal_left_out"], {"single_campus": 1, "no_federal_figures": 1})

    def test_federal_reports_and_what_is_left_out_make_up_the_published_reports(self) -> None:
        for year in self.public["years"]:
            if year["federal_fall_loaded"]:
                left = year["federal_left_out"]
                self.assertEqual(year["total"]["federal"]["reports"] + left["single_campus"]
                                 + left["no_federal_figures"], year["total"]["status"]["published"],
                                 year["cds_year"])

    def test_a_single_campus_report_with_a_federal_outcome_is_not_counted_twice(self) -> None:
        run = synthetic_run()
        single = next(d for d in run["documents"] if d["sub_institutional"] and d["year"] == "2024-25")
        single["federal"] = {"applied": "match", "admitted": "match", "enrolled": "match"}
        year = next(y for y in scoreboard.build_public(run, "x.json")["years"] if y["cds_year"] == "2024-25")
        left = year["federal_left_out"]
        self.assertEqual(year["total"]["federal"]["reports"] + left["single_campus"] + left["no_federal_figures"],
                         year["total"]["status"]["published"])
        self.assertEqual(left["single_campus"], 1)

    def test_form_and_other_numbering(self) -> None:
        self.assertEqual(self.year("2023-24")["form"],
                         {"form_year": "2023-24", "full_field_schema": True, "questions": 1053})
        self.assertEqual(self.year("2025-26")["form"]["questions"], 1105)
        self.assertEqual(sum(y["other_form_numbering"] for y in self.public["years"]), 1)

    def test_shape_allow_list_rejects_a_key_outside_it(self) -> None:
        scoreboard.check_public_shape(self.public)
        for path in ("top", "year", "row", "total", "nested"):
            broken = json.loads(json.dumps(self.public))
            first = broken["years"][0]
            target = {"top": broken, "year": first, "row": first["rows"][0], "total": first["total"],
                      "nested": first["total"]["totals"]["B1"]}[path]
            target["document_id"] = "x"
            with self.subTest(path=path), self.assertRaises(ValueError):
                scoreboard.check_public_shape(broken)
        broken = json.loads(json.dumps(self.public))
        del broken["years"][0]["rows"][0]["federal"]
        with self.assertRaises(ValueError):
            scoreboard.check_public_shape(broken)
        broken = json.loads(json.dumps(self.public))
        broken["years"][0]["removed"] = -1
        with self.assertRaises(ValueError):
            scoreboard.check_public_shape(broken)

    def test_nothing_per_document_is_written(self) -> None:
        text = json.dumps(self.public)
        for document in self.run["documents"]:
            self.assertNotIn(document["document_id"], text)
            self.assertNotIn(document["school_id"], text)
        for private in ("0.3.43", "tier4", "hold", "producer"):
            self.assertNotIn(private, text)

    def test_agrees_with_the_runs_own_aggregate(self) -> None:
        metrics = scoreboard.aggregate(self.run)
        for year in self.public["years"]:
            groups = [(f"{year['cds_year']}|all", year["total"])]
            for row in year["rows"]:
                if row["format"] != "other":   # aggregate() keeps `unknown` apart from `other`
                    groups.append((f"{year['cds_year']}|{row['format']}", row))
            for key, row in groups:
                with self.subTest(key=key):
                    # A format whose documents were never served has no aggregate() group.
                    self.assertEqual(row["status"]["published"], metrics.get(f"{key}|docs", 0))
                    if row["status"]["published"]:
                        self.assertEqual(row["fields_stored"]["median"], metrics[f"{key}|fields_median"])
                        self.assertEqual(row["fields_stored"]["p10"], metrics[f"{key}|fields_p10"])
                    if year["federal_fall_loaded"] and row["status"]["published"]:
                        self.assertEqual(row["federal"]["reports"], metrics[f"{key}|federal_docs"])
                        self.assertEqual(row["federal"]["matches"], metrics[f"{key}|federal_match"])
                        self.assertEqual(row["federal"]["no_value"], metrics[f"{key}|federal_blank"])
                        self.assertEqual(row["federal"]["differs"], metrics[f"{key}|federal_different"])
                    if not row["status"]["published"]:
                        continue
                    t = row["totals"]
                    for table in ("B1", "C1"):
                        self.assertEqual(
                            [t[table][k] for k in ("adds_up", "under_2pct", "off_more", "cant_check")],
                            [metrics[f"{key}|{table}_{o}"] for o in ("pass", "near", "fail", "nc")])
                    self.assertEqual([t["H1"][k] for k in ("adds_up", "doesnt", "cant_check")],
                                     [metrics[f"{key}|H1_{o}"] for o in ("pass", "fail", "nc")])

    def test_a_document_with_no_extraction_is_not_published_in_any_table(self) -> None:
        docx = next(r for r in self.year("2024-25")["rows"] if r["format"] == "docx")
        self.assertEqual(docx["status"], {"published": 0, "set_aside": 0, "couldnt_read": 0, "not_read_yet": 1})
        self.assertEqual(docx["totals"]["reports"], 0)
        self.assertEqual(docx["federal"]["values"], 0)

    def test_the_manifest_and_the_documents_must_agree(self) -> None:
        run = synthetic_run()
        run["documents"][2]["flag"] = "low_coverage"      # flagged in the documents, not in the manifest
        with self.assertRaises(SystemExit):
            scoreboard.build_public(run, "x.json")
        run = synthetic_run()
        run["federal_left_out"]["2024-25"]["single_campus"] += 1
        with self.assertRaises(SystemExit):
            scoreboard.build_public(run, "x.json")



class FederalDifferenceSize(unittest.TestCase):
    """Table B's "differs", split by the gap as a share of the federal figure:
    over 2% up to and including 10%, and over 10%."""

    band = staticmethod(scoreboard.federal_difference_band)

    def test_the_boundaries(self) -> None:
        D = Decimal
        self.assertIsNone(self.band(102, D(100)))          # exactly 2%: a match, not a difference
        self.assertEqual(self.band(103, D(100)), "2_to_10")
        self.assertEqual(self.band(98, D(100)), None)      # exactly 2% below: a match
        self.assertEqual(self.band(97, D(100)), "2_to_10")
        self.assertEqual(self.band(110, D(100)), "2_to_10")   # exactly 10% is the lower band
        self.assertEqual(self.band(90, D(100)), "2_to_10")
        self.assertEqual(self.band(111, D(100)), "over_10")
        self.assertEqual(self.band(89, D(100)), "over_10")
        self.assertEqual(self.band(1101, D(1000)), "over_10")
        self.assertEqual(self.band(1100, D(1000)), "2_to_10")

    def test_no_federal_figure_or_no_number_of_ours_is_not_a_difference(self) -> None:
        self.assertIsNone(self.band(100, None))
        self.assertIsNone(self.band(100, Decimal(0)))
        self.assertIsNone(self.band(None, Decimal(100)))   # blank, not different

    def test_the_band_agrees_with_classify_federal_everywhere(self) -> None:
        for ours in range(0, 400):
            outcome = scoreboard.classify_federal(ours, Decimal(100))
            self.assertEqual(self.band(ours, Decimal(100)) is not None, outcome == "different", ours)

    def snapshot_with(self, applied: tuple) -> dict:
        run = synthetic_run()
        target = next(d for d in run["documents"] if d["year"] == "2024-25" and not d["sub_institutional"]
                      and d["federal"]["applied"] == "match")
        target["federal"] = {**target["federal"], "applied": "different"}
        target["federal_values"]["applied"] = {"ours": applied[0], "federal": applied[1], "federal_data_year": 2024}
        self.edited_format = target["format"]
        return scoreboard.build_public(run, "x.json")

    def test_a_value_lands_in_exactly_one_band_in_its_row_and_the_total(self) -> None:
        base = scoreboard.build_public(synthetic_run(), "x.json")
        year = lambda pub: next(y for y in pub["years"] if y["cds_year"] == "2024-25")  # noqa: E731
        for ours, key in ((110, "differs_2_to_10pct"), (111, "differs_over_10pct")):
            pub = self.snapshot_with((ours, "100"))
            before, after = year(base)["total"]["federal"], year(pub)["total"]["federal"]
            # The edited report's applied value was a match; it is now one more difference, in `key` only.
            self.assertEqual(after[key] - before[key], 1)
            self.assertEqual(after["matches"] - before["matches"], -1)
            other = "differs_over_10pct" if key == "differs_2_to_10pct" else "differs_2_to_10pct"
            self.assertEqual(after[other], before[other])
            self.assertEqual(after["differs"] - before["differs"], 1)
            # The same in the edited report's own format row, and no other row moves.
            fmt = lambda pub: {r["format"]: r["federal"] for r in year(pub)["rows"]}  # noqa: E731
            rows_before, rows_after = fmt(base), fmt(pub)
            for name, row in rows_after.items():
                for k in ("differs", "differs_2_to_10pct", "differs_over_10pct", "matches"):
                    expected = {"differs": 1, "matches": -1, key: 1}.get(k, 0) if name == self.edited_format else 0
                    self.assertEqual(row[k] - rows_before[name][k], expected, (name, k))

    def test_refuses_when_federal_values_disagree_with_the_run_outcome(self) -> None:
        run = synthetic_run()
        target = next(d for d in run["documents"] if d["federal"]["enrolled"] == "different")
        target["federal_values"]["enrolled"]["ours"] = 100   # now a match against 100
        with self.assertRaises(SystemExit):
            scoreboard.build_public(run, "x.json")

    def test_the_agreement_guard_fires_on_its_own(self) -> None:
        # Stored outcome "match" but our raw number is missing: federal_values would say "blank". The error must be the
        # agreement one, not the band-sum one that a wrong count would raise later.
        run = synthetic_run()
        target = next(d for d in run["documents"] if d["year"] == "2024-25" and not d["sub_institutional"]
                      and d["federal"]["applied"] == "match")
        target["federal_values"]["applied"] = {"ours": None, "federal": "100", "federal_data_year": 2024}
        with self.assertRaisesRegex(SystemExit, f"{target['document_id']} applied: federal_values say 'blank', the run's outcome is 'match'"):
            scoreboard.build_public(run, "x.json")
        # And a stored "blank" against raw numbers that match.
        run = synthetic_run()
        target = next(d for d in run["documents"] if d["year"] == "2024-25" and not d["sub_institutional"]
                      and d["federal"]["admitted"] == "blank")
        target["federal_values"]["admitted"] = {"ours": 100, "federal": "100", "federal_data_year": 2024}
        with self.assertRaisesRegex(SystemExit, f"{target['document_id']} admitted: federal_values say 'match', the run's outcome is 'blank'"):
            scoreboard.build_public(run, "x.json")

    def test_refuses_a_run_without_federal_values(self) -> None:
        run = synthetic_run()
        target = next(d for d in run["documents"] if d["federal"]["enrolled"] == "different")
        del target["federal_values"]
        with self.assertRaisesRegex(SystemExit, f"{target['document_id']}.*no federal_values"):
            scoreboard.build_public(run, "x.json")
        run = synthetic_run()
        target = next(d for d in run["documents"] if d["federal"]["enrolled"] == "different")
        del target["federal_values"]["enrolled"]
        with self.assertRaisesRegex(SystemExit, f"{target['document_id']}.*enrolled"):
            scoreboard.build_public(run, "x.json")

    def test_the_public_shape_requires_both_new_keys_and_allows_no_others(self) -> None:
        pub = scoreboard.build_public(synthetic_run(), "x.json")
        for key in ("differs_2_to_10pct", "differs_over_10pct"):
            broken = json.loads(json.dumps(pub))
            del broken["years"][0]["total"]["federal"][key]
            with self.assertRaises(ValueError):
                scoreboard.check_public_shape(broken)
        # Also where the counts are zero (a year with no federal figures): a zero must still be written.
        zero = next(y for y in pub["years"] if not y["federal_fall_loaded"])
        for key in ("differs_2_to_10pct", "differs_over_10pct"):
            for holder in (zero["total"], zero["rows"][0]):
                self.assertEqual(holder["federal"][key], 0)
                broken = json.loads(json.dumps(pub))
                target = next(y for y in broken["years"] if y["cds_year"] == zero["cds_year"])
                del (target["total"] if holder is zero["total"] else target["rows"][0])["federal"][key]
                with self.assertRaisesRegex(ValueError, key):
                    scoreboard.check_public_shape(broken)
        broken = json.loads(json.dumps(pub))
        broken["years"][0]["total"]["federal"]["differs_over_20pct"] = 1
        with self.assertRaises(ValueError):
            scoreboard.check_public_shape(broken)



class SectionsPublic(unittest.TestCase):
    """Fields stored and usable answers by CDS section (public format 3)."""

    Q = {"A": 10, "B": 20}

    def block(self, docs: list[dict], year: str = "2024-25", questions: dict | None = None) -> dict:
        return scoreboard.section_block(year, docs, self.Q if questions is None else questions)

    def d(self, number: int, sections: dict, year: str = "2024-25", **kw) -> dict:
        return doc(f"s{number}", year, sections=sections, **kw)

    def row(self, block: dict, letter: str) -> dict:
        return next(r for r in block["rows"] if r["section"] == letter)

    def test_questions_come_from_the_form_schema(self) -> None:
        q = scoreboard.section_questions("2024-25")
        self.assertEqual(list(q), list("ABCDEFGHIJ"))
        self.assertEqual((q["A"], q["C"], q["J"]), (51, 278, 120))
        self.assertEqual(sum(q.values()), scoreboard.forms_for(["2024-25"])["2024-25"]["field_count"])
        self.assertEqual(scoreboard.section_questions("2022-23"), {})

    def test_every_full_schema_year_has_the_questions_its_schema_file_lists(self) -> None:
        # Hand-counted from schemas/cds_schema_<year>.json by question-number prefix; a changed or dropped section fails.
        expected = {
            "2023-24": dict(zip("ABCDEFGHIJ", (51, 196, 274, 70, 32, 60, 47, 154, 49, 120))),
            "2024-25": dict(zip("ABCDEFGHIJ", (51, 219, 278, 73, 32, 60, 47, 154, 49, 120))),
            "2025-26": dict(zip("ABCDEFGHIJ", (63, 204, 278, 88, 34, 58, 46, 165, 49, 120))),
            "2026-27": dict(zip("ABCDEFGHIJ", (63, 204, 289, 88, 34, 58, 47, 165, 49, 120))),
        }
        for year, counts in expected.items():
            with self.subTest(year):
                self.assertEqual(scoreboard.section_questions(year), counts)
                self.assertEqual(sum(counts.values()), scoreboard.forms_for([year])[year]["field_count"])

    def test_medians_are_nearest_rank_p50_not_p10_or_an_average_for_odd_and_even_counts(self) -> None:
        def reports(rows):
            return [self.d(i, {"A": {"reported": r, "parse_error": e, "not_applicable": n}}) for i, (r, e, n) in enumerate(rows)]
        # Five reports, (reported, parse_error, not_applicable): stored 10, 2, 7, 5, 8 and usable 9, 1, 5, 3, 7.
        odd = self.row(self.block(reports([(9, 1, 0), (1, 0, 1), (5, 2, 0), (3, 0, 2), (7, 1, 0)])), "A")
        self.assertEqual((odd["stored_median"], odd["usable_median"]), (7, 5))   # sorted 2 5 7 8 10 and 1 3 5 7 9; p10 would be 2 and 1
        # Four reports: stored 3, 9, 4, 8 and usable 2, 8, 4, 6. Nearest rank takes the 2nd of 4 (not the 3rd, not the mean).
        even = self.row(self.block(reports([(2, 1, 0), (8, 0, 1), (4, 0, 0), (6, 1, 1)])), "A")
        self.assertEqual((even["stored_median"], even["usable_median"]), (4, 4))   # sorted 3 4 8 9 and 2 4 6 8; mean would be 6 and 5

    def test_usable_means_reported_only(self) -> None:
        block = self.block([self.d(1, {"A": {"reported": 4, "parse_error": 3, "not_applicable": 2, "missing": 1}})])
        self.assertEqual(self.row(block, "A"), {"section": "A", "questions": 10, "stored_median": 10, "usable_median": 4})

    def test_a_report_with_no_fields_in_a_section_counts_as_zero_and_medians_are_nearest_rank(self) -> None:
        docs = [self.d(i, s) for i, s in enumerate([{"A": {"reported": 8}}, {"B": {"reported": 1}}, {"A": {"reported": 2}}])]
        # A per report: 8, 0, 2 -> median 2. B: 0, 1, 0 -> 0.
        block = self.block(docs)
        self.assertEqual((self.row(block, "A")["stored_median"], self.row(block, "B")["stored_median"]), (2, 0))
        # Even count: nearest rank takes the lower middle value, as Table A's fields stored does.
        block = self.block([self.d(1, {"A": {"reported": 2}}), self.d(2, {"A": {"reported": 6}})])
        self.assertEqual(self.row(block, "A")["stored_median"], 2)

    def test_reports_numbered_by_another_years_form_are_left_out(self) -> None:
        docs = [self.d(1, {"A": {"reported": 4}}), self.d(2, {"A": {"reported": 9}}, schema_version="2025-26")]
        block = self.block(docs)
        self.assertEqual(block["reports"], 1)
        self.assertEqual(self.row(block, "A")["stored_median"], 4)

    def test_no_full_schema_gives_no_rows(self) -> None:
        self.assertEqual(self.block([self.d(1, {"C": {"reported": 1}})], year="2022-23", questions={}), {"reports": 0, "rows": []})

    def test_refuses_what_cannot_be_set_against_the_form(self) -> None:
        for sections, why in (({"A": {"reported": 11}}, "more fields than the form has questions"),
                              ({"A": {"reported": 1, "mystery": 1}}, "unknown value_status"),
                              ({"Z": {"reported": 1}}, "a section the form lacks")):
            with self.subTest(why), self.assertRaises(SystemExit):
                self.block([self.d(1, sections)])
        broken = self.d(1, {})
        del broken["sections"]
        with self.assertRaises(SystemExit):
            self.block([broken])

    def test_a_snapshots_sections_add_up(self) -> None:
        pub = scoreboard.build_public(synthetic_run(), "x.json")
        for year in pub["years"]:
            block = year["sections"]
            self.assertEqual(block["reports"], year["total"]["status"]["published"] - year["other_form_numbering"])
            self.assertEqual(sum(r["questions"] for r in block["rows"]), year["form"]["questions"])
            for r in block["rows"]:
                self.assertLessEqual(r["usable_median"], r["stored_median"])
                self.assertLessEqual(r["stored_median"], r["questions"])

    def test_zero_reports_give_zero_medians_and_rows_for_the_form(self) -> None:
        block = self.block([self.d(1, {"A": {"reported": 4}}, schema_version="2025-26")])
        self.assertEqual(block["reports"], 0)
        self.assertEqual([r["stored_median"] + r["usable_median"] for r in block["rows"]], [0, 0])
        self.assertEqual([r["questions"] for r in block["rows"]], [10, 20])
        self.assertEqual(self.block([]), {"reports": 0, "rows": [{"section": "A", "questions": 10, "stored_median": 0, "usable_median": 0},
                                                                  {"section": "B", "questions": 20, "stored_median": 0, "usable_median": 0}]})

    def test_the_section_arithmetic_is_enforced_when_the_snapshot_is_written(self) -> None:
        pub = scoreboard.build_public(synthetic_run(), "x.json")
        scoreboard.check_public_sections(pub)
        year = lambda p: p["years"][0]["sections"]  # noqa: E731
        cases = {
            # The questions are moved to the next section so the sum still matches and only this rule can fire.
            "no questions": lambda p: (year(p)["rows"][1].update(questions=year(p)["rows"][1]["questions"] + year(p)["rows"][0]["questions"]),
                                       year(p)["rows"][0].update(questions=0, stored_median=0, usable_median=0)),
            "questions sum": lambda p: year(p)["rows"][0].update(questions=year(p)["rows"][0]["questions"] + 1),
            "reports": lambda p: year(p).update(reports=year(p)["reports"] + 1),
            "usable above stored": lambda p: year(p)["rows"][2].update(usable_median=year(p)["rows"][2]["stored_median"] + 1),
            "stored above questions": lambda p: year(p)["rows"][2].update(stored_median=year(p)["rows"][2]["questions"] + 1,
                                                                        usable_median=0),
            "order": lambda p: year(p)["rows"].reverse(),
            "omitted last section": lambda p: year(p)["rows"].pop(),
            "omitted middle section": lambda p: year(p)["rows"].pop(3),
            "repeat": lambda p: year(p)["rows"].append(dict(year(p)["rows"][0])),
            "rows without a schema": lambda p: p["years"][0]["form"].update(full_field_schema=False),
            "no rows with a schema": lambda p: year(p).update(rows=[]),
            "median without reports": lambda p: (year(p).update(reports=0), p["years"][0].update(other_form_numbering=p["years"][0]["total"]["status"]["published"])),
        }
        for name, mutate in cases.items():
            broken = json.loads(json.dumps(pub))
            mutate(broken)
            with self.subTest(name), self.assertRaises(SystemExit):
                scoreboard.check_public_sections(broken)

    def test_build_public_runs_the_section_arithmetic(self) -> None:
        real = scoreboard.section_block

        def wrong(*args, **kwargs):
            block = real(*args, **kwargs)
            return {**block, "reports": block["reports"] + 1}
        with mock.patch.object(scoreboard, "section_block", wrong), self.assertRaisesRegex(SystemExit, "sections: reports is"):
            scoreboard.build_public(synthetic_run(), "x.json")

    def test_the_public_shape_requires_and_limits_the_keys(self) -> None:
        pub = scoreboard.build_public(synthetic_run(), "x.json")
        for mutate in (lambda y: y.pop("sections"), lambda y: y["sections"].pop("reports"),
                       lambda y: y["sections"]["rows"][0].pop("usable_median"),
                       lambda y: y["sections"]["rows"][0].update(extra=1),
                       lambda y: y["sections"]["rows"][0].update(usable_median=-1)):
            broken = json.loads(json.dumps(pub))
            mutate(broken["years"][0])
            with self.assertRaises(ValueError):
                scoreboard.check_public_shape(broken)



class FederalExtraChecks(unittest.TestCase):
    """B1 enrollment and G1 tuition against IPEDS (public format 4)."""

    def d(self, number: int, year: str = "2023-24", **kw) -> dict:
        return doc(f"x{number}", year, **kw)

    def counts(self, docs: list[dict], check: str, loaded: bool = True) -> dict:
        return scoreboard.federal_check_counts(docs, check, loaded)

    def test_the_pair_is_b1_total_and_the_one_all_undergraduates_tuition_figure(self) -> None:
        pair = scoreboard.federal_check_pair
        d = self.d(1)
        self.assertEqual(pair(d, "enrollment"), (Decimal("1000"), Decimal("1000")))
        self.assertEqual(pair(d, "tuition"), (Decimal("30000"), Decimal("30000")))
        # G.108 (in-state) first; else G.102 (private); first-year and out-of-state rows are never used.
        only108 = extra_for("2023-24")
        only108["g1_private_undergraduates"]["ours"] = None
        only108["g1_in_state_undergraduates"]["ours"] = "9500"
        only108["g1_out_of_state_undergraduates"]["ours"] = "20000"
        only108["g1_private_first_year"]["ours"] = "1"
        self.assertEqual(pair(self.d(2, federal_extra=only108), "tuition")[0], Decimal("9500"))
        # A public school that also fills G.102 (west-chester 2023-24: G.102 19,290 = IPEDS out-of-state, G.108 7,716 = in-state):
        # the in-state figure is the one held against IPEDS in-state tuition.
        both = extra_for("2023-24", tuition=("19290", "7716"))
        both["g1_in_state_undergraduates"]["ours"] = "7716"
        self.assertEqual(pair(self.d(3, federal_extra=both), "tuition"), (Decimal("7716"), Decimal("7716")))
        only102 = extra_for("2023-24")
        self.assertEqual(pair(self.d(5, federal_extra=only102), "tuition")[0], Decimal("30000"))
        neither = extra_for("2023-24")
        neither["g1_private_undergraduates"]["ours"] = None
        self.assertIsNone(pair(self.d(4, federal_extra=neither), "tuition")[0])

    def test_classes_and_the_two_percent_and_ten_percent_boundaries(self) -> None:
        def row(i, ours, fed="1000"):
            return self.d(i, federal_extra=extra_for("2023-24", enrollment=(ours, fed)))
        docs = [row(1, "1020"), row(2, "1021"), row(3, "1100"), row(4, "1101"), row(5, None), row(6, "980"), row(7, "899")]
        self.assertEqual(self.counts(docs, "enrollment"), {
            "reports": 7, "matches": 2, "no_value": 1, "differs": 4, "differs_2_to_10pct": 2, "differs_over_10pct": 2})

    def test_tuition_dollars_with_cents_are_compared_exactly(self) -> None:
        def row(i, ours):
            return self.d(i, federal_extra=extra_for("2023-24", tuition=(ours, "30000")))
        got = self.counts([row(1, "30600.00"), row(2, "30600.01"), row(3, "33000.00"), row(4, "33000.01")], "tuition")
        self.assertEqual((got["matches"], got["differs_2_to_10pct"], got["differs_over_10pct"]), (1, 2, 1))

    def test_a_report_without_a_positive_federal_figure_is_not_counted(self) -> None:
        docs = [self.d(1, federal_extra=extra_for("2023-24", enrollment=("1000", None))),
                self.d(2, federal_extra=extra_for("2023-24", enrollment=("1000", "0"))), self.d(3)]
        self.assertEqual(self.counts(docs, "enrollment")["reports"], 1)

    def test_single_campus_reports_are_left_out_and_counted(self) -> None:
        docs = [self.d(1), self.d(2, sub_institutional=True), self.d(3, federal_extra=extra_for("2023-24", enrollment=("1000", None)))]
        year = scoreboard.federal_check_year("2023-24", docs, "enrollment", True)
        self.assertEqual(year, {"loaded": True, "data_year": 2023, "single_campus": 1, "no_federal_figures": 1})
        self.assertEqual(self.counts(docs, "enrollment")["reports"], 1)

    def test_a_year_with_no_figures_or_no_schema_is_not_loaded_and_counts_zero(self) -> None:
        docs = [self.d(1, "2024-25"), self.d(2, "2024-25")]
        tuition = scoreboard.federal_check_year("2024-25", docs, "tuition", True)
        self.assertEqual(tuition, {"loaded": False, "data_year": 2025, "single_campus": 0, "no_federal_figures": 0})
        self.assertTrue(scoreboard.federal_check_year("2024-25", docs, "enrollment", True)["loaded"])
        self.assertFalse(scoreboard.federal_check_year("2023-24", [self.d(3)], "enrollment", False)["loaded"])
        self.assertEqual(self.counts(docs, "tuition", loaded=False)["reports"], 0)

    def real_record(self, g102, g108, g109, federal: str, year: str = "2023-24") -> dict:
        """The tuition fields of a real 2023-24 report as the run records them."""
        extra = extra_for(year, tuition=(None, federal))
        for name, ours in (("g1_private_undergraduates", g102), ("g1_in_state_undergraduates", g108), ("g1_out_of_state_undergraduates", g109)):
            extra[name]["ours"] = ours
        return self.d(9, federal_extra=extra)

    def test_real_2023_24_records_where_the_private_row_is_not_the_in_state_price(self) -> None:
        pair = scoreboard.federal_check_pair
        cases = [
            # Oregon Tech: G.102 34,899 is the out-of-state rate (= G.109); G.108 10,964 is IPEDS' in-state tuition.
            ("oregon-institute-of-technology", ("34899", "10964", "34899", "10964"), (Decimal("10964"), Decimal("10964")), "m"),
            # West Chester: G.102 19,290 = G.109; G.108 7,716 = IPEDS in-state.
            ("west-chester-university-of-pennsylvania", ("19290", "7716", "19290", "7716"), (Decimal("7716"), Decimal("7716")), "m"),
            # Mississippi and Chico leave G.102 at 0 beside the real in-state figure.
            ("university-of-mississippi", ("0.00", "9612.00", "28440.00", "9612"), (Decimal("9612.00"), Decimal("9612")), "m"),
            ("california-state-university-chico", ("0", "6084", "18552", "6084"), (Decimal("6084"), Decimal("6084")), "m"),
            # Rollins: the reverse, G.108 at 0.00 beside the real private figure G.102 60,580 (= IPEDS): the private row is used.
            ("rollins-college", ("60580.00", "0.00", None, "60580"), (Decimal("60580.00"), Decimal("60580")), "m"),
            # Southern Mississippi has no G.102 and a G.108 3.9% under IPEDS: a real difference, by the in-state row.
            ("university-of-southern-mississippi", (None, "9508", "11904", "9888"), (Decimal("9508"), Decimal("9888")), "s"),
        ]
        for school, (g102, g108, g109, fed), expected, code in cases:
            with self.subTest(school):
                record = self.real_record(g102, g108, g109, fed)
                self.assertEqual(pair(record, "tuition"), expected)
                ours, fed = pair(record, "tuition")
                got = {"match": "m", "different": scoreboard.federal_difference_band(ours, fed)}[scoreboard.classify_federal(ours, fed)]
                self.assertEqual(got, {"m": "m", "s": "2_to_10"}[code])

    def test_the_selected_candidate_must_be_the_field_and_key_the_check_is_defined_on(self) -> None:
        wrong_key = extra_for("2023-24")
        wrong_key["g1_in_state_undergraduates"]["federal_key"] = "tuition_out_of_state"
        with self.assertRaisesRegex(SystemExit, "g1_in_state_undergraduates is field 'G.108' against 'tuition_out_of_state'"):
            scoreboard.federal_check_pair(self.d(1, federal_extra=wrong_key), "tuition")
        wrong_field = extra_for("2023-24")
        wrong_field["g1_private_undergraduates"]["cds_field"] = "G.109"
        with self.assertRaisesRegex(SystemExit, "g1_private_undergraduates is field 'G.109'"):
            scoreboard.federal_check_pair(self.d(2, federal_extra=wrong_field), "tuition")
        # The year guard follows the candidate in use: G.102 empty, G.108 looked up in the wrong IPEDS year.
        wrong_year = extra_for("2023-24")
        wrong_year["g1_private_undergraduates"]["ours"] = None
        wrong_year["g1_in_state_undergraduates"]["ours"] = "9500"
        wrong_year["g1_in_state_undergraduates"]["federal_data_year"] = 2023
        with self.assertRaisesRegex(SystemExit, "tuition for IPEDS year"):
            scoreboard.federal_check_year("2023-24", [self.d(3, federal_extra=wrong_year)], "tuition", True)

    def test_a_b1_total_of_zero_is_no_value(self) -> None:
        # 2024-25 had one in practice: a school with a 0 in B1 has no undergraduate total, not a total of nobody.
        zero = self.d(1, federal_extra=extra_for("2023-24", enrollment=("0", "1000")))
        self.assertEqual(scoreboard.federal_check_pair(zero, "enrollment"), (None, Decimal("1000")))
        self.assertEqual(self.counts([zero], "enrollment"), {
            "reports": 1, "matches": 0, "no_value": 1, "differs": 0, "differs_2_to_10pct": 0, "differs_over_10pct": 0})
        self.assertEqual(scoreboard.federal_check_pair(self.d(2, federal_extra=extra_for("2023-24", enrollment=("0.00", "1000"))), "enrollment")[0], None)

    def test_b1_must_be_the_field_of_the_documents_own_numbering_and_a_compared_year_must_have_its_fields(self) -> None:
        pair = scoreboard.federal_check_pair
        # B.193 on the 2023-24 and 2024-25 forms, B.176 on 2025-26: never either one.
        wrong = extra_for("2023-24")
        wrong["b1_undergraduates"]["cds_field"] = "B.176"
        with self.assertRaisesRegex(SystemExit, "b1_undergraduates is field 'B.176' against 'undergraduate_enrollment', not 'B.193'"):
            pair(self.d(1, schema_version="2023-24", federal_extra=wrong), "enrollment")
        other_numbered = extra_for("2023-24")
        other_numbered["b1_undergraduates"]["cds_field"] = "B.176"   # a 2023-24 report numbered by the 2025-26 form
        self.assertEqual(pair(self.d(2, schema_version="2025-26", federal_extra=other_numbered), "enrollment")[1], Decimal("1000"))
        with self.assertRaisesRegex(SystemExit, "not 'B.176'"):
            pair(self.d(3, schema_version="2025-26", federal_extra=extra_for("2023-24")), "enrollment")
        # A missing field in a compared year fails loudly; in a year with no comparison it is expected.
        missing = extra_for("2023-24")
        missing["g1_in_state_undergraduates"]["cds_field"] = None
        with self.assertRaisesRegex(SystemExit, "g1_in_state_undergraduates is field None"):
            pair(self.d(4, federal_extra=missing), "tuition")
        for name in ("b1_undergraduates", "g1_in_state_undergraduates", "g1_private_undergraduates"):
            missing[name]["cds_field"] = None
        self.assertEqual(pair(self.d(5, federal_extra=missing, federal_compared=False), "tuition")[0], Decimal("30000"))
        # ...and a field present where nothing was compared is as wrong.
        with self.assertRaisesRegex(SystemExit, "is field 'G.108'"):
            pair(self.d(6, federal_extra=extra_for("2023-24"), federal_compared=False), "tuition")

    def test_federal_check_year_refuses_a_null_federal_extra(self) -> None:
        broken = self.d(1, federal_extra=None)
        with self.assertRaisesRegex(SystemExit, "x1 has no federal_extra"):
            scoreboard.federal_check_year("2023-24", [broken], "enrollment", True)

    def test_a_tuition_of_zero_is_no_value_and_the_next_candidate_is_used(self) -> None:
        # A school's in-state row left at 0 beside its real private figure (and the other way round): never compare $0
        # with the federal tuition.
        extra = extra_for("2023-24")
        extra["g1_private_undergraduates"]["ours"] = "12000"
        extra["g1_in_state_undergraduates"]["ours"] = "0"
        self.assertEqual(scoreboard.federal_check_pair(self.d(1, federal_extra=extra), "tuition")[0], Decimal("12000"))
        extra["g1_private_undergraduates"]["ours"] = "0"
        extra["g1_in_state_undergraduates"]["ours"] = "9500"
        self.assertEqual(scoreboard.federal_check_pair(self.d(6, federal_extra=extra), "tuition")[0], Decimal("9500"))
        zero_only = extra_for("2023-24")
        zero_only["g1_private_undergraduates"]["ours"] = "0.00"
        self.assertIsNone(scoreboard.federal_check_pair(self.d(2, federal_extra=zero_only), "tuition")[0])
        self.assertEqual(self.counts([self.d(3, federal_extra=zero_only)], "tuition")["no_value"], 1)

    def test_the_run_must_have_looked_up_the_year_the_check_is_defined_for(self) -> None:
        wrong = extra_for("2023-24")
        wrong["b1_undergraduates"]["federal_data_year"] = 2024
        with self.assertRaisesRegex(SystemExit, "enrollment for IPEDS year"):
            scoreboard.federal_check_year("2023-24", [self.d(1, federal_extra=wrong)], "enrollment", True)

    def test_federal_check_year_and_build_public_refuse_a_missing_federal_extra_or_a_wrong_candidate_year(self) -> None:
        missing = self.d(1)
        del missing["federal_extra"]
        with self.assertRaisesRegex(SystemExit, "x1 has no federal_extra"):
            scoreboard.federal_check_year("2023-24", [missing], "tuition", True)
        run = synthetic_run()
        del next(d for d in run["documents"] if d["year"] == "2023-24" and d["producer"] and not d["flag"])["federal_extra"]
        with self.assertRaisesRegex(SystemExit, "has no federal_extra"):
            scoreboard.build_public(run, "x.json")
        # Either tuition candidate looked up in the wrong IPEDS year is refused (the private one and the in-state one).
        for name in ("g1_private_undergraduates", "g1_in_state_undergraduates"):
            wrong = extra_for("2023-24")
            wrong[name]["federal_data_year"] = 2023
            with self.subTest(name), self.assertRaisesRegex(SystemExit, "tuition for IPEDS year"):
                scoreboard.federal_check_year("2023-24", [self.d(2, federal_extra=wrong)], "tuition", True)

    def test_refuses_a_document_without_federal_extra_or_with_split_tuition_figures(self) -> None:
        broken = self.d(1)
        del broken["federal_extra"]
        with self.assertRaisesRegex(SystemExit, "x1 has no federal_extra"):
            self.counts([broken], "enrollment")
        split = extra_for("2023-24")
        split["g1_in_state_undergraduates"]["federal"] = "1"
        with self.assertRaisesRegex(SystemExit, "different IPEDS figures"):
            self.counts([self.d(2, federal_extra=split)], "tuition")

    def test_the_snapshot_blocks_add_up_for_every_row_and_year(self) -> None:
        pub = scoreboard.build_public(synthetic_run(), "x.json")
        for year in pub["years"]:
            info = year["federal_checks"]
            for name in ("enrollment", "tuition"):
                for row in [*year["rows"], year["total"]]:
                    c = row["checks"][name]
                    self.assertEqual(c["matches"] + c["no_value"] + c["differs"], c["reports"])
                    self.assertEqual(c["differs_2_to_10pct"] + c["differs_over_10pct"], c["differs"])
                    self.assertLessEqual(c["reports"], row["status"]["published"])
                    if not info[name]["loaded"]:
                        self.assertEqual(c["reports"], 0)
                t = year["total"]["checks"][name]
                for key in t:
                    self.assertEqual(sum(r["checks"][name][key] for r in year["rows"]), t[key])
                if info[name]["loaded"]:
                    self.assertEqual(t["reports"] + info[name]["single_campus"] + info[name]["no_federal_figures"],
                                     year["total"]["status"]["published"])
        by_year = {y["cds_year"]: y["federal_checks"] for y in pub["years"]}
        self.assertEqual((by_year["2023-24"]["enrollment"]["loaded"], by_year["2023-24"]["tuition"]["loaded"]), (True, True))
        self.assertEqual((by_year["2024-25"]["enrollment"]["loaded"], by_year["2024-25"]["tuition"]["loaded"]), (True, False))
        self.assertEqual((by_year["2025-26"]["enrollment"]["loaded"], by_year["2025-26"]["tuition"]["loaded"]), (False, False))

    def test_the_public_shape_requires_and_limits_the_check_keys(self) -> None:
        pub = scoreboard.build_public(synthetic_run(), "x.json")
        for mutate in (lambda y: y["total"].pop("checks"), lambda y: y["total"]["checks"].pop("tuition"),
                       lambda y: y["rows"][0]["checks"]["enrollment"].pop("differs_over_10pct"),
                       lambda y: y["rows"][0]["checks"]["enrollment"].update(values=1),
                       lambda y: y.pop("federal_checks"), lambda y: y["federal_checks"]["tuition"].pop("data_year"),
                       lambda y: y["federal_checks"].update(other={})):
            broken = json.loads(json.dumps(pub))
            mutate(broken["years"][0])
            with self.assertRaises(ValueError):
                scoreboard.check_public_shape(broken)


class PublicInputs(unittest.TestCase):
    def refuses(self, run: dict) -> None:
        with blocked_network(), self.assertRaises(SystemExit):
            scoreboard.build_public(run, "x.json")

    def test_refuses_a_run_that_is_not_format_3(self) -> None:
        for change in ({"run_format": 1}, {"run_format": 2}, {"run_format": 4}, {"run_format": None}, {"sum_check_version": 1}, {"limit": 20},
                       {"manifest": []}, {"years": []}):
            with self.subTest(change=change):
                self.refuses({**synthetic_run(), **change})
        old = synthetic_run()
        for key in ("run_format", "manifest", "forms", "renewal", "federal_left_out"):
            del old[key]
        self.refuses(old)

    def test_refuses_a_run_without_a_usable_renewal_block(self) -> None:
        for change in ({"previous": 0, "both": 0}, {"both": 999}):
            run = synthetic_run()
            run["renewal"] = {**run["renewal"], **change}
            self.refuses(run)
        run = synthetic_run()
        del run["renewal"]["both"]
        self.refuses(run)

    def test_the_renewal_block_is_checked_offline_against_the_run_date(self) -> None:
        changes = {
            "as_of the wrong day": {"as_of": "2026-11-24"},
            "as_of not a date": {"as_of": "yesterday"},
            "current year is not the floor": {"current_year": "2024-25", "previous_year": "2023-24"},
            "previous year is not current - 1": {"previous_year": "2022-23"},
            "previous under the minimum": {"previous": 349, "both": 300, "two_year_previous": 536},
            "two-year previous under the minimum": {"two_year_previous": 349, "two_year_both": 349},
            "both over previous": {"both": 480},
            "both over current": {"current": 360},
            "two-year both over two-year previous": {"two_year_both": 537},
            "two-year both over current": {"two_year_both": 381, "two_year_previous": 600, "current": 380},
            "two-year previous under one-year previous": {"two_year_previous": 478},
            "two-year both under one-year both": {"two_year_both": 363},
            "a count that is text": {"both": "364"},
            "a negative count": {"current": -1},
        }
        for name, change in changes.items():
            run = synthetic_run()
            run["renewal"] = {**run["renewal"], **change}
            with self.subTest(name):
                self.refuses(run)

    def test_refuses_a_partial_run(self) -> None:
        run = synthetic_run()
        del run["limit"]
        self.refuses(run)
        for limit in (0, 20):
            self.refuses({**synthetic_run(), "limit": limit})
        self.refuses({**synthetic_run(), "years": YEARS + ["2024-25"]})                 # a year twice
        self.refuses({**synthetic_run(), "years": ["2024-25", "2025-26"]})              # a default year missing
        run = synthetic_run()
        run["years"] = ["2025-26"]
        self.refuses(run)

    def test_refuses_an_outcome_the_version_does_not_have(self) -> None:
        run = synthetic_run()
        run["documents"][0]["sums"]["H1"] = "near"       # H1 has no near-miss class
        self.refuses(run)

    def test_the_command_writes_one_dated_file_and_makes_no_network_call(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            run_path = Path(folder, "scoreboard-20261125T011508Z.json")
            run_path.write_text(json.dumps(synthetic_run()))
            out = Path(folder, "out")
            argv = ["scoreboard.py", "--public", str(run_path), "--public-out-dir", str(out)]
            with blocked_network(), mock.patch.object(sys, "argv", argv), contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(scoreboard.main(), 0)
            self.assertEqual([p.name for p in out.iterdir()], ["2026-11-25.json"])
            written = json.loads((out / "2026-11-25.json").read_text())
            self.assertEqual(written["scoreboard_run"], run_path.name)
            scoreboard.check_public_shape(written)

    def test_the_command_refuses_the_saved_runs_of_the_old_format(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            run_path = Path(folder, "old.json")
            run_path.write_text(json.dumps({"generated_at": "2026-11-25T00:00:00Z", "years": YEARS, "documents": []}))
            argv = ["scoreboard.py", "--public", str(run_path), "--public-out-dir", str(Path(folder, "out"))]
            with blocked_network(), mock.patch.object(sys, "argv", argv), self.assertRaises(SystemExit):
                scoreboard.main()
            self.assertFalse(Path(folder, "out").exists())


class Forms(unittest.TestCase):
    def test_read_from_the_local_schema_files(self) -> None:
        forms = scoreboard.forms_for(["2023-24", "2024-25", "2025-26", "2022-23"])
        self.assertEqual({y: (f["schema_exists"], f["field_count"]) for y, f in forms.items()}, {
            "2023-24": (True, 1053), "2024-25": (True, 1083), "2025-26": (True, 1105), "2022-23": (False, 0)})
        self.assertEqual(forms["2024-25"]["expected_form_year"], "2024-25")

    def test_only_a_year_with_a_full_schema_has_sum_tables(self) -> None:
        forms = scoreboard.forms_for(["2018-19", "2019-20", "2020-21", "2021-22", "2022-23", "2023-24", "2026-27"])
        self.assertEqual({y: f["sum_tables"] for y, f in forms.items()}, {
            "2018-19": [], "2019-20": [], "2020-21": [], "2021-22": [], "2022-23": [],
            "2023-24": ["B1", "C1", "H1"], "2026-27": ["B1", "C1", "H1"]})


class Renewal(unittest.TestCase):
    """The block comes from discovery_renewal; these check the wiring."""

    def rows(self, both: int, only_previous: int, only_current: int) -> list[dict]:
        out = []
        for name, years in ([(f"b{i}", ("2024-25", "2025-26")) for i in range(both)]
                            + [(f"p{i}", ("2024-25",)) for i in range(only_previous)]
                            + [(f"c{i}", ("2025-26",)) for i in range(only_current)]):
            out += [{"school_id": name, "canonical_year": y, "removed_at": None,
                     "participation_status": "published"} for y in years]
        return out

    def test_counts_and_year_names(self) -> None:
        rows = self.rows(300, 100, 20) + [
            {"school_id": "u", "canonical_year": "unknown", "removed_at": None, "participation_status": "published"},
            {"school_id": "p0", "canonical_year": "2025-26", "removed_at": "2026-01-01", "participation_status": "published"},
            {"school_id": "x", "canonical_year": "2024-25", "removed_at": None, "participation_status": "verified_absent"}]
        block = scoreboard.renewal_block(rows, dt.date(2026, 11, 25))
        self.assertEqual((block["current_year"], block["previous_year"]), ("2025-26", "2024-25"))
        self.assertEqual((block["previous"], block["both"], block["current"]), (400, 300, 320))
        self.assertEqual((block["two_year_previous"], block["two_year_both"]), (400, 300))
        self.assertEqual(block["as_of"], "2026-11-25")

    def test_a_flagged_current_year_document_is_not_a_renewal(self) -> None:
        # The block uses the alarm's numerator (PRD 040 amendment, #493).
        rows = self.rows(300, 100, 20)
        for row in rows:
            if row["school_id"] in {"b0", "b1", "b2"} and row["canonical_year"] == "2025-26":
                row["data_quality_flag"] = "blank_template"
        block = scoreboard.renewal_block(rows, dt.date(2026, 11, 25))
        self.assertEqual((block["previous"], block["both"]), (400, 297))
        self.assertEqual((block["two_year_previous"], block["two_year_both"]), (400, 297))

    def test_two_year_figures_count_schools_that_only_have_the_older_year(self) -> None:
        rows = self.rows(300, 100, 20)
        for i in range(60):       # schools with 2023-24 only: in the two-year denominator, not the one-year
            rows.append({"school_id": f"o{i}", "canonical_year": "2023-24", "removed_at": None,
                         "participation_status": "published"})
        for i in range(15):       # 2023-24 and 2025-26 but no 2024-25: renewed on the two-year check only
            rows += [{"school_id": f"g{i}", "canonical_year": y, "removed_at": None, "participation_status": "published"}
                     for y in ("2023-24", "2025-26")]
        block = scoreboard.renewal_block(rows, dt.date(2026, 11, 25))
        self.assertEqual((block["previous"], block["both"]), (400, 300))
        self.assertEqual((block["two_year_previous"], block["two_year_both"]), (475, 315))
        self.assertEqual(block["current"], 335)

    def test_the_year_follows_the_run_date(self) -> None:
        # Before September the current year is two years back, where these rows have no schools.
        with self.assertRaises(SystemExit):
            scoreboard.renewal_block(self.rows(300, 100, 20), dt.date(2026, 8, 31))

    def test_a_small_denominator_is_an_error_not_a_small_number(self) -> None:
        with self.assertRaises(SystemExit):
            scoreboard.renewal_block(self.rows(10, 5, 1), dt.date(2026, 11, 25))
        with self.assertRaises(SystemExit):
            scoreboard.renewal_block([], dt.date(2026, 11, 25))

    def test_a_floor_that_disagrees_with_the_database_is_an_error(self) -> None:
        rows = self.rows(300, 100, 20)
        scoreboard.renewal_block(rows, dt.date(2026, 11, 25), sql_floor="2025-26")
        with self.assertRaises(discovery_renewal_error()):
            scoreboard.renewal_block(rows, dt.date(2026, 11, 25), sql_floor="2024-25")


def discovery_renewal_error():
    return scoreboard.discovery_renewal.RenewalError


class CompareAcrossSumCheckVersions(unittest.TestCase):
    def runs(self) -> tuple[dict, dict]:
        helper = RenderAndHolds()
        before = helper.data([helper.document(sums={"B1": "pass", "C1": "fail", "H1": "pass"})])
        after = helper.data([helper.document(sums={"B1": "pass", "C1": "near", "H1": "fail"})])
        after["sum_check_version"] = 2
        return before, after

    def test_the_switch_is_noted_and_no_quality_change_is_reported(self) -> None:
        before, after = self.runs()
        text = scoreboard.render(after, before)
        self.assertIn("Sum checks changed from version 1 to 2", text)
        row = next(line for line in text.splitlines() if line.startswith("| 2024-25 | all | 1 | 1 / 0 / 0 / 0 |"))
        # C1 went from fail to near: no (+1) or (-1) is shown for B1 or C1 ...
        self.assertIn("| 1 / 0 / 0 / 0 | 0 / 1 / 0 / 0 |", row)
        self.assertIn("pass / off by under 2%", text)
        # ... but H1 is scored the same in both versions, so its change is still reported.
        self.assertTrue(row.endswith("| 0 (-1) / 1 (+1) / 0 |"), row)

    def test_the_same_version_reports_deltas_as_before(self) -> None:
        before, after = self.runs()
        after["sum_check_version"] = 1
        after["documents"][0]["sums"]["C1"] = "pass"
        text = scoreboard.render(after, before)
        self.assertNotIn("Sum checks changed", text)
        self.assertIn("(-1)", text)


class SameYearDuplicatesTests(unittest.TestCase):
    """The scoreboard reports two served documents in one filed year."""

    def doc(self, number: int, school: str = "a-college", year: str = "2024-25", **extra) -> dict:
        row = {
            "document_id": f"{number:08d}-0000-0000-0000-000000000000", "school_id": school, "year": year,
            "sub_institutional": False, "source_url": f"https://x.edu/f{number}.pdf",
            "cds_year": year, "detected_year": year,
        }
        return {**row, **extra}

    def test_a_pair_in_one_year_is_found_and_classified(self) -> None:
        block = scoreboard.same_year_duplicates_block([
            self.doc(1), self.doc(2, cds_year="2025-26"), self.doc(3, school="b-college"),
        ])
        self.assertEqual(block["same_year_duplicates"], 1)
        self.assertEqual(block["groups"][0]["class"], "year_conflict")
        self.assertEqual(block["same_year_duplicates_by_class"]["year_conflict"], 1)

    def test_one_document_per_year_is_not_a_group(self) -> None:
        block = scoreboard.same_year_duplicates_block([self.doc(1, year="2023-24"), self.doc(2)])
        self.assertEqual(block["same_year_duplicates"], 0)

    def test_a_saved_run_without_the_new_columns_still_counts_pairs(self) -> None:
        old = [{k: v for k, v in self.doc(i).items() if k not in ("source_url", "cds_year", "detected_year")}
               for i in (1, 2)]
        self.assertEqual(scoreboard.same_year_duplicates_block(old)["same_year_duplicates"], 1)

    def test_two_programs_of_one_school_are_not_a_duplicate(self) -> None:
        block = scoreboard.same_year_duplicates_block([
            self.doc(1, sub_institutional=True, sub_institutional_label="general-studies"),
            self.doc(2, sub_institutional=True, sub_institutional_label="nursing"),
        ])
        self.assertEqual(block["same_year_duplicates"], 0)
        same = scoreboard.same_year_duplicates_block([
            self.doc(1, sub_institutional=True, sub_institutional_label="nursing"),
            self.doc(2, sub_institutional=True, sub_institutional_label="nursing"),
        ])
        self.assertEqual(same["same_year_duplicates"], 1)
        self.assertEqual(same["groups"][0]["sub_institutional"], "nursing")

    def test_gather_keeps_the_raw_sub_institutional_label(self) -> None:
        source = Path(scoreboard.__file__).read_text()
        self.assertIn('"sub_institutional_label": doc.get("sub_institutional")', source)

    def test_pairs_without_hashes_are_not_called_different_files(self) -> None:
        block = scoreboard.same_year_duplicates_block([self.doc(1), self.doc(2)])
        self.assertIn("hashes not compared", block["groups"][0]["evidence"])
        text = scoreboard.render_same_year_duplicates({"same_year_duplicates": block})
        self.assertIn("same-file pairs show as duplicates", text)

    def test_render_prints_the_section(self) -> None:
        block = scoreboard.same_year_duplicates_block([self.doc(1), self.doc(2, cds_year="2025-26")])
        text = scoreboard.render_same_year_duplicates({"same_year_duplicates": block})
        self.assertIn("## Two documents in one year", text)
        self.assertIn("| a-college | 2024-25 | year_conflict |", text)
        self.assertIn("no duplicate check", scoreboard.render_same_year_duplicates({}))

    def test_fetch_asks_for_the_columns_the_check_reads(self) -> None:
        seen = {}

        class Api:
            def get(self, table, params, pause=0.0):
                seen.update(params)
                return []

        scoreboard.fetch_documents(Api(), ("2024-25",))
        for column in ("source_url", "cds_year", "detected_year"):
            self.assertIn(column, seen["select"])


# ---------------------------------------------------------------------------
# gather() end to end on a fake Api (run_format 3)
# ---------------------------------------------------------------------------

class FakeApi:
    """Answers the PostgREST reads gather() makes from small in-memory tables
    and records every request. Like PostgREST it returns only the selected
    columns (except the artifact reads, whose selects are JSON paths) and
    honours `removed_at=is.null` and the id filters."""

    url = "https://fake.invalid"
    key = "k"

    def __init__(self, tables: dict[str, list[dict]]):
        self.tables = tables
        self.calls: list[tuple[str, dict]] = []
        self.requests = 0

    def check_page_size(self) -> None:
        pass

    def wait_for_memory(self) -> None:
        pass

    def get(self, table: str, params: dict, pause: float = 0.0) -> list[dict]:
        self.calls.append((table, dict(params)))
        self.requests += 1
        rows = self.tables[table]
        if params.get("removed_at") == "is.null":
            rows = [r for r in rows if r.get("removed_at") is None]
        if table == "cds_manifest" and "canonical_year" in params:
            rows = [r for r in rows if r["canonical_year"] in params["canonical_year"][3:].strip("()").split(",")]
        if table != "cds_manifest":
            for column in ("document_id", "id", "data_year"):
                if column in params:
                    wanted = params[column]
                    if wanted.startswith("in."):
                        rows = [r for r in rows if str(r.get(column)) in wanted[3:].strip("()").split(",")]
                    else:
                        rows = [r for r in rows if str(r.get(column)) == wanted[3:]]
        if table == "cds_artifacts" and "id" in params:   # the notes read
            return [{"id": r["id"], "notes_schema_version": r["notes"]["schema_version"],
                     "schema_fallback_used": None, "stats": None, "values": r["notes"]["values"]} for r in rows]
        if table == "ipeds_facts":
            keys = params["field_key"][3:].strip("()").split(",")
            rows = [r for r in rows if r["field_key"] in keys]
        if table != "cds_artifacts":
            columns = params["select"].split(",")
            rows = [{c: r[c] for c in columns} for r in rows]
        return rows

    def tables_called(self) -> Counter:
        return Counter(table for table, _ in self.calls)


def fake_manifest_row(document_id: str, year: str, ipeds_id: str, **kw) -> dict:
    return {"document_id": document_id, "school_id": f"s-{document_id}", "school_name": document_id,
            "ipeds_id": ipeds_id, "sub_institutional": None, "canonical_year": year,
            "source_format": "pdf_flat", "extraction_status": "extracted", "data_quality_flag": None,
            "removed_at": None, "source_url": "https://x.invalid/f.pdf", "cds_year": year,
            "detected_year": year, **kw}


def field_row(document_id: str, year: str, field_id: str, value, status: str = "reported") -> dict:
    return {"document_id": document_id, "field_id": field_id, "value_num": value, "value_status": status,
            "schema_version": year, "producer": "tier4_docling", "producer_version": "0.3.43"}


def fact(ipeds_id: str, key: str, value, year: int, release: str = "final") -> dict:
    return {"ipeds_id": ipeds_id, "field_key": key, "value_numeric": value, "data_year": year,
            "release_type": release, "release_id": "r", "created_at": "2026-03-01T00:00:00Z"}


def candidate(field, ours, key, federal, year) -> dict:
    return {"cds_field": field, "ours": ours, "federal_key": key, "federal": federal, "federal_data_year": year}


class GatherOnAFakeApi(unittest.TestCase):
    """Documents (CDS year, school):
    P   2024-25, public; first-year and all-undergraduate in-state and out-of-state tuition.
    E   2024-25, private; a school whose only IPEDS facts are enrollment and tuition (no C1).
    S   2024-25, a single campus of the same file as P.
    O   2023-24, served from an artifact.
    N   2025-26, whose tuition year (2026) is not loaded.
    R removed, F failed. IPEDS tuition decoys sit in the CDS year (Y) to catch a pairing with Y."""

    YEARS = ("2023-24", "2024-25", "2025-26")

    def run_gather(self, years: tuple = YEARS, extend=lambda manifest, tables: None) -> tuple[dict, FakeApi]:
        """`extend(manifest, tables)` adds documents and facts before the run."""
        floor = scoreboard.discovery_renewal.cds_freshness_floor(dt.datetime.now(dt.timezone.utc).date())
        previous = scoreboard.discovery_renewal.format_year(scoreboard.discovery_renewal.parse_year(floor) - 1)
        renewal_rows = [{"school_id": f"r{i}", "canonical_year": y, "removed_at": None,
                         "participation_status": "published"} for i in range(400) for y in (previous, floor)]
        manifest = [
            fake_manifest_row("P", "2024-25", "111"),
            fake_manifest_row("E", "2024-25", "888"),
            fake_manifest_row("O", "2023-24", "222"),
            fake_manifest_row("S", "2024-25", "333", sub_institutional="Campus X"),
            fake_manifest_row("N", "2025-26", "777"),
            fake_manifest_row("R", "2024-25", "444", removed_at="2026-01-01T00:00:00Z"),
            fake_manifest_row("F", "2024-25", "555", extraction_status="failed"),
        ]
        old_values = {
            "A.001": {"value": "Old University"},
            "B.193": {"value": "4,000"}, "G.108": {"value": "$12,000"}, "G.109": {"value": "35000"},
            "G.104": {"value": "11,500"}, "G.105": {"value": "34000"},
            "C.101": {"value": "100"}, "C.102": {"value": "150"}, "C.105": {"value": "80"},
            "C.106": {"value": "90"}, "C.109": {"value": "30"}, "C.111": {"value": "40"},
            "C.201": {"value": "N/A"}, "G.102": {"value": ""},
            # H.401 (the graduating class) is a year, not a count: fails a sanity rule. H.511 is a loan average of 0
            # beside a borrower count of 0 (H.501): nobody borrowed.
            "H.401": {"value": "2023"}, "H.501": {"value": "0"}, "H.511": {"value": "0"},
        }
        p, e, s, n = "2024-25", "2024-25", "2024-25", "2025-26"
        tables = {
            "cds_manifest": manifest,
            # P and S are one university-wide file filed under two schools.
            "cds_documents": [
                {"id": "P", "source_sha256": "aa", "removed_at": None, "unselected": 1},
                {"id": "S", "source_sha256": "aa", "removed_at": None}, {"id": "O", "source_sha256": "bb", "removed_at": None},
                {"id": "E", "source_sha256": "dd", "removed_at": None}, {"id": "N", "source_sha256": None, "removed_at": None},
                {"id": "R", "source_sha256": "cc", "removed_at": "2026-01-01T00:00:00Z"}],
            "cds_artifacts": [
                {"id": "art-O", "document_id": "O", "kind": "canonical", "producer": "tier4_docling",
                 "producer_version": "0.3.43", "schema_version": "2023-24", "created_at": "2026-05-01T00:00:00Z",
                 "notes": {"schema_version": "2023-24", "values": old_values}},
            ],
            "school_browser_rows": [
                {"document_id": "P", "producer": "tier4_docling", "producer_version": "0.3.43",
                 "applied": 300, "admitted": 150, "enrolled_first_year": 70},
                {"document_id": "N", "producer": "tier4_docling", "producer_version": "0.3.43",
                 "applied": 50, "admitted": 20, "enrolled_first_year": 10}],
            "cds_fields": [
                field_row("P", p, "B.193", 5000), field_row("P", p, "G.108", 11000), field_row("P", p, "G.109", 30000),
                field_row("P", p, "G.104", 10500), field_row("P", p, "G.105", 29500),
                field_row("P", p, "G.102", None, "not_applicable"), field_row("P", p, "C.101", 100),
                field_row("P", p, "C.201", None, "parse_error"), field_row("P", p, "A.001", None, "reported"),
                field_row("E", e, "B.193", 2000), field_row("E", e, "G.101", 40000), field_row("E", e, "G.102", 41000),
                field_row("S", s, "B.193", 800), field_row("S", s, "C.201", None, "not_applicable"),
                field_row("N", n, "B.176", 900), field_row("N", n, "G.108", 9000),
            ],
            "ipeds_facts": [
                # P: fall 2024; tuition for the 2024-25 form is academic year 2025-26, data_year 2025.
                fact("111", "applicants_total", 305, 2024), fact("111", "admissions_total", 150, 2024),
                fact("111", "enrolled_total", 60, 2024), fact("111", "undergraduate_enrollment", 5100, 2024),
                fact("111", "tuition_in_state", 10000, 2024), fact("111", "tuition_out_of_state", 28000, 2024),  # decoys
                fact("111", "tuition_in_state", 11050.5, 2025), fact("111", "tuition_out_of_state", 29900, 2025),
                # O: fall 2023, tuition data_year 2024.
                fact("222", "applicants_total", 1000, 2023), fact("222", "undergraduate_enrollment", 4100, 2023),
                fact("222", "tuition_in_state", 9999, 2023), fact("222", "tuition_in_state", 12000, 2024),
                fact("333", "applicants_total", 9999, 2024), fact("333", "undergraduate_enrollment", 9000, 2024),
                fact("333", "tuition_in_state", 8000, 2025),
                # E: only enrollment and tuition, no C1 figure.
                fact("888", "undergraduate_enrollment", 2100, 2024), fact("888", "tuition_in_state", 41500.25, 2025),
                # N: fall 2025 only; nothing for 2026.
                fact("777", "applicants_total", 50, 2025), fact("777", "undergraduate_enrollment", 950, 2025),
                fact("777", "tuition_in_state", 7, 2025),   # the CDS year's own tuition year: a decoy
            ],
        }
        extend(manifest, tables)
        api = FakeApi(tables)
        with blocked_network(), tempfile.TemporaryDirectory() as folder, \
                mock.patch.object(scoreboard.time, "sleep"), \
                mock.patch.object(scoreboard.discovery_renewal, "fetch_live_manifest", return_value=renewal_rows), \
                mock.patch.object(scoreboard.discovery_renewal, "fetch_sql_floor", return_value=floor):
            run = scoreboard.gather(api, years, Path(folder), 0, 0, str(Path(folder, "none-*.json")), lambda _: None)
        return run, api

    def setUp(self) -> None:
        self.run, self.api = self.run_gather()
        self.by_id = {d["document_id"]: d for d in self.run["documents"]}

    def test_only_the_served_documents_are_in_the_run(self) -> None:
        self.assertEqual(set(self.by_id), {"P", "E", "O", "S", "N"})
        self.assertEqual(len(self.run["manifest"]), 7)
        self.assertEqual(self.run["run_format"], 3)

    def test_requests_are_the_same_tables_as_before_plus_the_hash_read_and_the_boundary_year(self) -> None:
        # One manifest page, one `cds_documents` read for the file hashes, one
        # artifact index chunk plus the one notes read of the 2023-24 document,
        # one browser read, one field read per served projected document (P, E,
        # S, N), and one ipeds_facts read per IPEDS data year.
        self.assertEqual(self.api.tables_called(), Counter(
            {"cds_manifest": 1, "cds_documents": 1, "cds_artifacts": 2, "school_browser_rows": 1,
             "cds_fields": 4, "ipeds_facts": 4}))
        facts = {p["data_year"]: p["field_key"] for t, p in self.api.calls if t == "ipeds_facts"}
        both = "admissions_total,applicants_total,enrolled_total,tuition_in_state,tuition_out_of_state,undergraduate_enrollment"
        self.assertEqual(facts, {
            "eq.2023": "in.(admissions_total,applicants_total,enrolled_total,undergraduate_enrollment)",
            "eq.2024": f"in.({both})", "eq.2025": f"in.({both})",
            "eq.2026": "in.(tuition_in_state,tuition_out_of_state)"})

    def test_the_document_and_manifest_reads_ask_for_what_the_run_keeps(self) -> None:
        by_table = {t: p for t, p in self.api.calls if t in ("cds_documents", "cds_manifest")}
        self.assertEqual({k: v for k, v in by_table["cds_documents"].items()},
                         {"select": "id,source_sha256", "removed_at": "is.null", "order": "id"})
        self.assertIn("ipeds_id", by_table["cds_manifest"]["select"].split(","))

    def test_each_document_keeps_its_ipeds_id_and_file_hash(self) -> None:
        self.assertEqual({k: (d["ipeds_id"], d["source_sha256"]) for k, d in self.by_id.items()},
                         {"P": ("111", "aa"), "S": ("333", "aa"), "O": ("222", "bb"), "E": ("888", "dd"),
                          "N": ("777", None)})

    def test_federal_values_hold_the_numbers_the_classification_used(self) -> None:
        self.assertEqual(self.by_id["P"]["federal_values"], {
            "applied": {"ours": 300, "federal": "305", "federal_data_year": 2024},
            "admitted": {"ours": 150, "federal": "150", "federal_data_year": 2024},
            "enrolled": {"ours": 70, "federal": "60", "federal_data_year": 2024}})
        self.assertEqual(self.by_id["P"]["federal"], {"applied": "match", "admitted": "match", "enrolled": "different"})
        self.assertEqual(self.by_id["O"]["federal_values"], {
            "applied": {"ours": 250, "federal": "1000", "federal_data_year": 2023},
            "admitted": {"ours": 170, "federal": None, "federal_data_year": 2023},
            "enrolled": {"ours": 70, "federal": None, "federal_data_year": 2023}})
        self.assertEqual(self.by_id["O"]["federal"]["applied"], "different")

    def test_a_single_campus_report_keeps_ours_and_has_no_federal_figure(self) -> None:
        self.assertEqual(self.by_id["S"]["federal_values"]["applied"],
                         {"ours": None, "federal": None, "federal_data_year": 2024})
        self.assertTrue(all(v["federal"] is None for v in self.by_id["S"]["federal_extra"].values()))
        self.assertEqual(self.by_id["S"]["federal_extra"]["b1_undergraduates"]["ours"], "800")

    def test_every_candidate_of_a_public_report(self) -> None:
        inn, out = "tuition_in_state", "tuition_out_of_state"
        self.assertEqual(self.by_id["P"]["federal_extra"], {
            "b1_undergraduates": candidate("B.193", "5000", "undergraduate_enrollment", "5100", 2024),
            "g1_private_undergraduates": candidate("G.102", None, inn, "11050.5", 2025),
            "g1_in_state_undergraduates": candidate("G.108", "11000", inn, "11050.5", 2025),
            "g1_out_of_state_undergraduates": candidate("G.109", "30000", out, "29900", 2025),
            "g1_private_first_year": candidate("G.101", None, inn, "11050.5", 2025),
            "g1_in_state_first_year": candidate("G.104", "10500", inn, "11050.5", 2025),
            "g1_out_of_state_first_year": candidate("G.105", "29500", out, "29900", 2025)})

    def test_every_candidate_of_a_private_report(self) -> None:
        inn, out = "tuition_in_state", "tuition_out_of_state"
        self.assertEqual(self.by_id["E"]["federal_extra"], {
            "b1_undergraduates": candidate("B.193", "2000", "undergraduate_enrollment", "2100", 2024),
            "g1_private_undergraduates": candidate("G.102", "41000", inn, "41500.25", 2025),
            "g1_in_state_undergraduates": candidate("G.108", None, inn, "41500.25", 2025),
            "g1_out_of_state_undergraduates": candidate("G.109", None, out, None, 2025),
            "g1_private_first_year": candidate("G.101", "40000", inn, "41500.25", 2025),
            "g1_in_state_first_year": candidate("G.104", None, inn, "41500.25", 2025),
            "g1_out_of_state_first_year": candidate("G.105", None, out, None, 2025)})

    def test_every_candidate_of_a_2023_24_report_read_from_its_artifact(self) -> None:
        inn, out = "tuition_in_state", "tuition_out_of_state"
        self.assertEqual(self.by_id["O"]["federal_extra"], {
            "b1_undergraduates": candidate("B.193", "4000", "undergraduate_enrollment", "4100", 2023),
            "g1_private_undergraduates": candidate("G.102", None, inn, "12000", 2024),
            "g1_in_state_undergraduates": candidate("G.108", "12000", inn, "12000", 2024),
            "g1_out_of_state_undergraduates": candidate("G.109", "35000", out, None, 2024),
            "g1_private_first_year": candidate("G.101", None, inn, "12000", 2024),
            "g1_in_state_first_year": candidate("G.104", "11500", inn, "12000", 2024),
            "g1_out_of_state_first_year": candidate("G.105", "34000", out, None, 2024)})

    def test_tuition_is_held_against_the_following_ipeds_year_not_the_cds_year(self) -> None:
        # The 2025 decoy for school 777 is its CDS year's; the figure for 2026 is not loaded.
        extra = self.by_id["N"]["federal_extra"]
        self.assertEqual(extra["b1_undergraduates"], candidate("B.176", "900", "undergraduate_enrollment", "950", 2025))
        self.assertEqual(extra["g1_in_state_undergraduates"],
                         candidate("G.108", "9000", "tuition_in_state", None, 2026))
        # P's CDS-year decoys (10000 / 28000) are never the figure.
        self.assertEqual(self.by_id["P"]["federal_extra"]["g1_in_state_undergraduates"]["federal"], "11050.5")
        for document in self.by_id.values():
            year = scoreboard.projection.parse_year_start(document["year"])
            for name, c in document["federal_extra"].items():
                self.assertEqual(c["federal_data_year"], year if name.startswith("b1") else year + 1, name)

    def test_the_2023_24_artifact_sections_pin_every_status(self) -> None:
        # "N/A" is not applicable; an empty value is "missing".
        self.assertEqual(self.by_id["O"]["sections"], {
            "A": {"reported": 1}, "B": {"reported": 1},
            "C": {"not_applicable": 1, "reported": 6},
            "G": {"missing": 1, "reported": 4},
            # H.401 fails a sanity rule (parse_error), H.511 has no borrowers (not_applicable), H.501 is a real 0.
            "H": {"not_applicable": 1, "parse_error": 1, "reported": 1}})

    def test_a_2023_24_artifact_gets_the_projections_downgrades_not_the_raw_parse(self) -> None:
        # Without them H.401 and H.511 would both be counted as usable.
        self.assertEqual(self.by_id["O"]["sections"]["H"].get("reported"), 1)
        defs = scoreboard.projection.load_schema_definitions()["2023-24"]
        down = lambda values, version="2023-24": scoreboard.effective_statuses(values, defs, version)  # noqa: E731
        # A year given as the graduating class fails a rule: parse_error, not a usable number.
        self.assertEqual(down({"H.401": {"value": "2023"}, "G.108": {"value": "9000"}}),
                         {"H.401": "parse_error", "G.108": "reported"})
        # A loan average of 0 with no borrowers is not applicable; one beside real borrowers is left alone.
        loans = {"H.501": {"value": "10"}, "H.502": {"value": "0"}, "H.512": {"value": "0"},
                 "H.503": {"value": "3"}, "H.513": {"value": "0"}}
        self.assertEqual(down(loans), {"H.501": "reported", "H.502": "reported", "H.512": "not_applicable",
                                       "H.503": "reported", "H.513": "reported"})
        # A form the sanity rules don't cover is left alone.
        self.assertEqual(set(down(loans, "2018-19").values()), {"reported"})
        # A borrower count that failed a rule is not evidence of "no borrowers". H.501 = 0 (any loan) is flagged because
        # H.503 = 3 exceeds it, and H.511 = 0 sits beside that 0: without the filter H.511 would be "not_applicable".
        failed = down({"H.501": {"value": "0"}, "H.511": {"value": "0"}, "H.503": {"value": "3"}, "H.513": {"value": "0"}})
        self.assertEqual(failed, {"H.501": "parse_error", "H.503": "parse_error", "H.511": "reported", "H.513": "reported"})

    def test_sections_of_a_projected_document_and_the_sum_rule(self) -> None:
        self.assertEqual(self.by_id["P"]["sections"], {
            "A": {"reported": 1}, "B": {"reported": 1}, "C": {"parse_error": 1, "reported": 1},
            "G": {"not_applicable": 1, "reported": 4}})
        for document in self.by_id.values():
            with self.subTest(document=document["document_id"]):
                self.assertEqual(sum(n for counts in document["sections"].values() for n in counts.values()),
                                 document["fields"])
                self.assertGreater(document["fields"], 0)

    def test_a_school_with_only_extra_facts_is_not_a_federal_school_and_the_run_is_usable(self) -> None:
        self.assertEqual(self.run["federal_schools"], {"2023-24": 1, "2024-25": 2, "2025-26": 1})
        # Published 2024-25: P, E, S. S is a single campus; E has no C1 figure.
        self.assertEqual(self.run["federal_left_out"]["2024-25"], {"single_campus": 1, "no_federal_figures": 1, "not_compared": 0})
        json.dumps(self.run)
        public = scoreboard.build_public(self.run, "scoreboard-x.json")
        scoreboard.check_public_shape(public)


def add_artifact_documents(spec: list[tuple[str, str, str, str]], facts: list[dict]):
    """(document id, CDS year, IPEDS id, the schema version its artifact carries) -> an `extend` for run_gather."""
    values = {"C.101": {"value": "100"}, "C.102": {"value": "150"}, "C.116": {"value": "250"},
              "B.113": {"value": "300"}, "B.138": {"value": "300"}, "B.163": {"value": "300"},
              "B.176": {"value": "1000"}, "G.108": {"value": "9000"}}

    def extend(manifest: list[dict], tables: dict[str, list[dict]]) -> None:
        for document_id, year, ipeds_id, version in spec:
            manifest.append(fake_manifest_row(document_id, year, ipeds_id))
            tables["cds_documents"].append({"id": document_id, "source_sha256": document_id * 2, "removed_at": None})
            tables["cds_artifacts"].append(
                {"id": f"art-{document_id}", "document_id": document_id, "kind": "canonical",
                 "producer": "tier4_docling", "producer_version": "0.3.43", "schema_version": version,
                 "created_at": "2026-05-01T00:00:00Z", "notes": {"schema_version": version, "values": values}})
        tables["ipeds_facts"] += facts
    return extend


# Y: 2022-23 read into the 2025-26 ids (what the worker does), with a B1 sum that misses and a C1 sum that adds up.
# V: 2022-23 labelled 2024-25. Z: 2022-23 numbered by its own year. W: 2018-19, which has no overlay.
# IPEDS has every one of their falls.
EARLIER = add_artifact_documents(
    [("Y", "2022-23", "901", "2025-26"), ("V", "2022-23", "904", "2024-25"), ("Z", "2022-23", "902", "2022-23"),
     ("W", "2018-19", "903", "2025-26")],
    [fact("901", "applicants_total", 250, 2022), fact("901", "undergraduate_enrollment", 1000, 2022),
     fact("904", "applicants_total", 250, 2022), fact("902", "applicants_total", 400, 2022),
     fact("903", "applicants_total", 250, 2018)])


class GatherAnEarlierYear(unittest.TestCase):
    YEARS = ("2025-26", "2022-23", "2023-24", "2024-25", "2018-19")   # given out of order

    def setUp(self) -> None:
        self.run, self.api = GatherOnAFakeApi.run_gather(self, self.YEARS, EARLIER)
        self.by_id = {d["document_id"]: d for d in self.run["documents"]}
        self.public = scoreboard.build_public(self.run, "scoreboard-x.json")
        self.years = {y["cds_year"]: y for y in self.public["years"]}

    def test_years_are_listed_oldest_first(self) -> None:
        self.assertEqual(self.run["years"], ["2018-19", "2022-23", "2023-24", "2024-25", "2025-26"])
        self.assertEqual(self.run["projected_years"], ["2024-25", "2025-26"])

    def test_a_year_without_a_full_schema_has_no_checks(self) -> None:
        self.assertEqual(self.run["forms"]["2022-23"], {
            "expected_form_year": "2022-23", "schema_exists": False, "field_count": 0, "sum_tables": []})
        self.assertEqual(self.run["forms"]["2023-24"]["sum_tables"], ["B1", "C1", "H1"])

    def test_a_document_of_an_earlier_year_is_served_from_its_artifact_and_keeps_its_counts(self) -> None:
        y = self.by_id["Y"]
        self.assertEqual((y["producer"], y["version"], y["schema_version"], y["fields"]),
                         ("tier4_docling", "0.3.43", "2025-26", 8))
        self.assertEqual(y["sections"], {"B": {"reported": 4}, "C": {"reported": 3}, "G": {"reported": 1}})
        self.assertEqual(y["admissions"], {"applied": 250, "admitted": None, "enrolled": None})
        self.assertEqual(y["federal_values"]["applied"], {"ours": 250, "federal": "250", "federal_data_year": 2022})
        self.assertEqual(self.run["federal_schools"]["2022-23"], 3)

    def test_no_sum_is_checked_and_no_admission_compared_whatever_the_numbering(self) -> None:
        # Y would pass C1 and fail B1 on the 2025-26 form; V and Z carry other numberings.
        for document_id in ("Y", "V", "Z", "W"):
            with self.subTest(document=document_id):
                d = self.by_id[document_id]
                self.assertEqual(d["sums"], {"B1": "nc", "C1": "nc", "H1": "nc"})
                self.assertEqual(d["check_numbers"], {})
                self.assertEqual(d["federal"], {"applied": None, "admitted": None, "enrolled": None})
                self.assertFalse(d["federal_compared"])
        self.assertTrue(all(c["cds_field"] is None and c["ours"] is None
                            for c in self.by_id["Y"]["federal_extra"].values()))
        self.assertEqual(self.by_id["Y"]["federal_extra"]["b1_undergraduates"]["federal"], "1000")

    def test_current_years_are_compared(self) -> None:
        self.assertTrue(self.by_id["O"]["federal_compared"] and self.by_id["P"]["federal_compared"])

    def test_not_compared_is_its_own_count_and_the_reports_add_up(self) -> None:
        self.assertEqual(self.run["federal_left_out"]["2022-23"],
                         {"single_campus": 0, "no_federal_figures": 0, "not_compared": 3})
        self.assertEqual(self.run["federal_left_out"]["2024-25"],
                         {"single_campus": 1, "no_federal_figures": 1, "not_compared": 0})
        for year, entry in self.years.items():
            if not entry["federal_fall_loaded"]:
                continue
            with self.subTest(year=year):
                left = entry["federal_left_out"]
                total = entry["total"]
                self.assertEqual(total["federal"]["reports"] + left["single_campus"] + left["no_federal_figures"]
                                 + left.get("not_compared", 0), total["status"]["published"])
                for row in entry["rows"]:   # and by format
                    self.assertLessEqual(row["federal"]["reports"], row["status"]["published"])

    def test_public_for_a_year_with_no_checks(self) -> None:
        for year, published in (("2022-23", 3), ("2018-19", 1)):
            with self.subTest(year=year):
                old = self.years[year]
                self.assertEqual(old["sum_checks_unavailable"], ["B1", "C1", "H1"])
                self.assertTrue(old["federal_fall_loaded"])   # IPEDS has the fall; we did not compare
                self.assertEqual(old["federal_left_out"],
                                 {"single_campus": 0, "no_federal_figures": 0, "not_compared": published})
                self.assertEqual(old["total"]["federal"],
                                 {"reports": 0, "values": 0, "matches": 0, "no_value": 0, "differs": 0,
                                                            "differs_2_to_10pct": 0, "differs_over_10pct": 0})
                self.assertEqual(old["total"]["status"]["published"], published)
                self.assertEqual(old["total"]["fields_stored"]["median"], 8)
                self.assertEqual(old["form"], {"form_year": year, "full_field_schema": False, "questions": 0})
                for table in ("B1", "C1", "H1"):
                    self.assertEqual(old["total"]["totals"][table]["cant_check"], published)

    def test_current_years_are_unchanged_by_the_earlier_ones(self) -> None:
        current, _ = GatherOnAFakeApi.run_gather(self, ("2023-24", "2024-25", "2025-26"))
        before = {y["cds_year"]: y for y in scoreboard.build_public(current, "scoreboard-x.json")["years"]}
        for year in ("2023-24", "2024-25", "2025-26"):
            self.assertEqual(self.years[year], before[year])
            self.assertNotIn("sum_checks_unavailable", self.years[year])
            self.assertNotIn("not_compared", self.years[year]["federal_left_out"])
        self.assertEqual([y["cds_year"] for y in self.public["years"]], self.run["years"])

    def test_the_markdown_says_our_mapping_is_missing(self) -> None:
        text = scoreboard.render(self.run)
        self.assertIn("2022-23: we have no checked field mapping for B1, C1, H1 on this form", text)
        self.assertIn("2022-23: we have no checked field mapping for admissions on this form", text)
        self.assertNotIn("2023-24: we have no checked field mapping", text)

    def test_renewal_does_not_depend_on_the_years(self) -> None:
        only_old, _ = GatherOnAFakeApi.run_gather(self, ("2022-23",), EARLIER)
        self.assertEqual(only_old["renewal"], self.run["renewal"])
        scoreboard.require_public_renewal(only_old["renewal"], only_old["generated_at"])

    def test_an_earlier_year_alone_cannot_be_published(self) -> None:
        only_old, _ = GatherOnAFakeApi.run_gather(self, ("2022-23",), EARLIER)
        with self.assertRaises(SystemExit) as caught:
            scoreboard.build_public(only_old, "x.json")
        self.assertIn("2023-24", str(caught.exception))

    def test_a_bad_or_repeated_year_is_refused_before_any_read(self) -> None:
        for years in (("2023-24", "unknown"), ("2023-24", "2023-24"), ("2023", "2024-25")):
            api = FakeApi({})
            with self.subTest(years=years), tempfile.TemporaryDirectory() as folder, \
                    mock.patch.object(scoreboard, "gather_renewal") as renewal, self.assertRaises(SystemExit):
                scoreboard.gather(api, years, Path(folder), 0, 0, "none", lambda _: None)
            self.assertEqual(api.calls, [])
            renewal.assert_not_called()

    def test_a_future_year_with_a_full_schema_is_checked_as_before(self) -> None:
        # 2026-27 has a full schema file and no SUM_CHECKS of its own: its documents are
        # still checked and compared by the numbering they carry, as on main.
        def extend(manifest: list[dict], tables: dict[str, list[dict]]) -> None:
            for document_id, ipeds_id, version in (("T", "905", "2025-26"), ("U", "906", "2031-32")):
                manifest.append(fake_manifest_row(document_id, "2026-27", ipeds_id))
                tables["cds_documents"].append({"id": document_id, "source_sha256": document_id * 2, "removed_at": None})
                tables["cds_fields"] += [
                    {**field_row(document_id, version, field_id, value), "schema_version": version}
                    for field_id, value in (("C.101", 100), ("C.102", 150), ("C.116", 250),
                                            ("B.113", 300), ("B.138", 300), ("B.163", 300), ("B.176", 1000))]
                tables["school_browser_rows"].append(
                    {"document_id": document_id, "producer": "tier4_docling", "producer_version": "0.3.43",
                     "applied": 250, "admitted": None, "enrolled_first_year": None})
            tables["ipeds_facts"] += [fact("905", "applicants_total", 250, 2026), fact("906", "applicants_total", 250, 2026)]

        run, _ = GatherOnAFakeApi.run_gather(self, ("2026-27",), extend)
        forms = run["forms"]["2026-27"]
        self.assertEqual((forms["schema_exists"], forms["sum_tables"]), (True, ["B1", "C1", "H1"]))
        by_id = {d["document_id"]: d for d in run["documents"]}
        self.assertEqual(by_id["T"]["sums"], {"B1": "fail", "C1": "pass", "H1": "nc"})
        self.assertEqual(by_id["T"]["federal"]["applied"], "match")
        # A numbering with no checks sums nothing, but the projected admissions are still
        # compared (main's behaviour), not "not compared".
        self.assertEqual(by_id["U"]["sums"], {"B1": "nc", "C1": "nc", "H1": "nc"})
        self.assertEqual(by_id["U"]["federal"]["applied"], "match")
        self.assertTrue(by_id["U"]["federal_compared"])
        self.assertEqual(run["federal_left_out"]["2026-27"], {"single_campus": 0, "no_federal_figures": 0, "not_compared": 0})


class SumChecksUnavailable(unittest.TestCase):
    def test_a_run_without_sum_tables_is_read_only_for_years_that_have_all_three(self) -> None:
        run = synthetic_run()
        for form in run["forms"].values():
            del form["sum_tables"]
        self.assertEqual(scoreboard.build_public(run, "x.json"), scoreboard.build_public(synthetic_run(), "x.json"))
        run["years"] = [*run["years"], "2022-23"]
        run["forms"]["2022-23"] = {"expected_form_year": "2022-23", "schema_exists": False, "field_count": 0}
        run["federal_left_out"]["2022-23"] = {"single_campus": 0, "no_federal_figures": 0, "not_compared": 0}
        with self.assertRaises(SystemExit) as caught:
            scoreboard.build_public(run, "x.json")
        self.assertIn("no sum_tables", str(caught.exception))

    def test_a_legacy_run_with_a_full_schema_year_without_its_own_checks_is_still_accepted(self) -> None:
        # main accepted a 2026-27 year (full schema, no SUM_CHECKS); so does a legacy run of it.
        def run_with(year: str, form_kw: dict) -> dict:
            run = synthetic_run()
            for form in run["forms"].values():
                del form["sum_tables"]
            run["years"] = [*run["years"], year]
            run["forms"][year] = {"expected_form_year": year, "field_count": 1117, **form_kw}
            run["federal_left_out"][year] = {"single_campus": 0, "no_federal_figures": 0}
            return run
        public = scoreboard.build_public(run_with("2026-27", {"schema_exists": True}), "x.json")
        self.assertNotIn("sum_checks_unavailable", public["years"][-1])
        with self.assertRaises(SystemExit):
            scoreboard.build_public(run_with("2026-27", {"schema_exists": False}), "x.json")

    def test_the_public_shape_allows_the_key_only_as_a_list_of_text(self) -> None:
        public = scoreboard.build_public(synthetic_run(), "x.json")
        scoreboard.check_public_shape(public)   # absent is fine
        public["years"][0]["sum_checks_unavailable"] = ["B1"]
        scoreboard.check_public_shape(public)
        for bad in ("B1", [1], {"B1": 1}, [], ["ZZ"], ["B1", "ZZ"]):
            public["years"][0]["sum_checks_unavailable"] = bad
            with self.assertRaises(ValueError):
                scoreboard.check_public_shape(public)
        del public["years"][0]["sum_checks_unavailable"]
        public["years"][0]["other"] = 1
        with self.assertRaises(ValueError):
            scoreboard.check_public_shape(public)

    def test_not_compared_is_optional_and_a_year_cannot_repeat(self) -> None:
        public = scoreboard.build_public(synthetic_run(), "x.json")
        public["years"][0]["federal_left_out"]["not_compared"] = 2
        scoreboard.check_public_shape(public)
        public["years"][0]["federal_left_out"]["not_compared"] = -1
        with self.assertRaises(ValueError):
            scoreboard.check_public_shape(public)
        public = scoreboard.build_public(synthetic_run(), "x.json")
        public["years"].append(public["years"][0])
        with self.assertRaises(ValueError):
            scoreboard.check_public_shape(public)

    def test_a_generator_of_tables_is_not_used_up(self) -> None:
        values = numbers(C_116=250, C_101=100, C_102=150, B_176=1000)
        self.assertEqual(scoreboard.table_outcomes("2025-26", values, (t for t in ("C1", "B1"))),
                         scoreboard.table_outcomes("2025-26", values, ("C1", "B1")))


class RunFormats(unittest.TestCase):
    def test_a_format_2_run_cannot_make_a_public_snapshot(self) -> None:
        # It has no federal_values, so the size split cannot be worked out. Refused, not written as public format 1.
        two = {**synthetic_run(), "run_format": 2}
        for document in two["documents"]:
            del document["federal_values"]
        with self.assertRaises(SystemExit):
            scoreboard.build_public(two, "x.json")

    def test_aggregate_and_render_read_a_format_3_run(self) -> None:
        run = {**synthetic_run(), "run_format": 3}
        self.assertEqual(scoreboard.aggregate(run), scoreboard.aggregate(synthetic_run()))
        self.assertEqual(scoreboard.render(run), scoreboard.render(synthetic_run()))

    def test_compare_across_formats(self) -> None:
        # The earlier run differs from the current one, so the report has real deltas.
        current = synthetic_run()
        earlier = synthetic_run()
        earlier["documents"] = earlier["documents"][:-5]
        earlier["manifest"] = earlier["manifest"][:-5]
        earlier["documents"][2]["federal"] = {"applied": "different", "admitted": "different", "enrolled": "blank"}
        as_3 = lambda run: {**run, "run_format": 3}  # noqa: E731
        same_format = scoreboard.render(current, earlier)
        self.assertNotEqual(same_format, scoreboard.render(current, current))
        self.assertEqual(scoreboard.render(as_3(current), earlier), same_format)
        self.assertEqual(scoreboard.render(current, as_3(earlier)), same_format)
        self.assertEqual(scoreboard.render(as_3(current), as_3(earlier)), same_format)

    def test_the_form_ids_the_extra_candidates_name_are_the_rows_they_say(self) -> None:
        for year in scoreboard.TUITION_FORM_YEARS:
            labels = {f["question_number"]: f for f in json.loads(
                (SCHEMA_DIR / f"cds_schema_{year.replace('-', '_')}.json").read_text())["fields"]}
            extra = scoreboard.federal_extra(year, {}, {}, 2000, {}, 2001)
            self.assertEqual(labels[extra["b1_undergraduates"]["cds_field"]]["question"], "Total all undergraduates")
            for name, (field_id, _) in scoreboard.TUITION_CANDIDATES.items():
                with self.subTest(year=year, name=name):
                    self.assertEqual(extra[name]["cds_field"], field_id)
                    row = labels[field_id]
                    self.assertTrue(row["question"].startswith("Tuition"))
                    self.assertEqual(row["cohort"], "First-year" if "first_year" in name else "Undergraduates")
                    self.assertEqual(row["subsection"].startswith("Private"), "private" in name)
                    if "in_state" in name:
                        self.assertIn("In-state", row["question"])
                    if "out_of_state" in name:
                        self.assertIn("Out-of-state", row["question"])
        for year in ("2019-20", "2022-23"):
            extra = scoreboard.federal_extra(year, {}, {}, 2000, {}, 2001)
            self.assertTrue(all(c["cds_field"] is None for n, c in extra.items() if n.startswith("g1")))


if __name__ == "__main__":
    unittest.main()
