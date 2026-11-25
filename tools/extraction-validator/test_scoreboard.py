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
    """A run_format 2 run with every status, several formats, flags, a held
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
    return {
        "run_format": 2, "sum_check_version": 2, "limit": None, "generated_at": "2026-11-25T01:15:08Z",
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
        self.assertEqual(self.public["public_format"], 1)
        self.assertEqual(self.public["snapshot_of"], "2026-11-25T01:15:08Z")
        self.assertEqual(self.public["scoreboard_run"], "scoreboard-20261125T011508Z.json")
        self.assertEqual(self.public["renewal"], self.run["renewal"])
        self.assertEqual([y["cds_year"] for y in self.public["years"]], YEARS)

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
        self.assertEqual(year["total"]["federal"], {"reports": 0, "values": 0, "matches": 0, "no_value": 0, "differs": 0})
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


class PublicInputs(unittest.TestCase):
    def refuses(self, run: dict) -> None:
        with blocked_network(), self.assertRaises(SystemExit):
            scoreboard.build_public(run, "x.json")

    def test_refuses_a_run_that_is_not_format_2(self) -> None:
        for change in ({"run_format": 1}, {"run_format": None}, {"sum_check_version": 1}, {"limit": 20},
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


if __name__ == "__main__":
    unittest.main()
