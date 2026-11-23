"""Tests for the extraction scoreboard's pure parts (no network)."""

from __future__ import annotations

import json
import random
import sys
import unittest
from decimal import Decimal
from pathlib import Path

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


if __name__ == "__main__":
    unittest.main()
