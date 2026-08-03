from __future__ import annotations

import csv
import io
import json
import tempfile
import unittest
import urllib.parse
import zipfile
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

from tools.ipeds.reconcile_endowment_scorecard import (
    FactPair,
    ScorecardRow,
    alignment_sort_key,
    fetch_in_scope_private_nonprofit_directory,
    fetch_ipeds_endowment_facts,
    fixture_results,
    parse_decimal,
    postgrest_get_all,
    read_scorecard_rows,
    reconcile_entity,
    reconcile_scorecard,
    reconcile_year,
)


def scorecard(
    unitid: int,
    begin: int | None,
    end: int | None,
    *,
    opeid6: str = "001234",
    name: str | None = None,
    control: int = 2,
    main: bool = True,
) -> ScorecardRow:
    return ScorecardRow(
        unitid=unitid,
        opeid6=opeid6,
        institution_name=name or f"School {unitid}",
        control=control,
        main_campus=main,
        endowment_begin=None if begin is None else Decimal(begin),
        endowment_end=None if end is None else Decimal(end),
    )


def fact(unitid: int, year: int, begin: int, end: int) -> FactPair:
    return FactPair(unitid, year, Decimal(begin), Decimal(end))


class FakeResponse(io.StringIO):
    def __enter__(self) -> "FakeResponse":
        return self

    def __exit__(self, *_args: object) -> None:
        return None


class ReconcileEndowmentScorecardTests(unittest.TestCase):
    def test_non_finite_numbers_are_rejected_at_the_input_boundary(self) -> None:
        for value in ("NaN", "sNaN", "Infinity", "-Infinity"):
            with self.subTest(value=value):
                self.assertIsNone(parse_decimal(value))

    def test_postgrest_paginates_and_sends_both_auth_headers(self) -> None:
        requests = []

        def opener(request: object, *, timeout: int) -> FakeResponse:
            requests.append((request, timeout))
            offset = urllib.parse.parse_qs(
                urllib.parse.urlsplit(request.full_url).query
            )["offset"][0]
            page = {
                "0": [{"id": 1}, {"id": 2}],
                "2": [{"id": 3}],
            }.get(offset, [])
            return FakeResponse(json.dumps(page))

        rows = postgrest_get_all(
            "https://project.example",
            "test-api-key",
            "ipeds_facts",
            {"select": "unitid"},
            page_size=2,
            opener=opener,
        )

        self.assertEqual(rows, [{"id": 1}, {"id": 2}, {"id": 3}])
        self.assertEqual(len(requests), 3)
        for request, timeout in requests:
            self.assertEqual(request.get_header("Apikey"), "test-api-key")
            self.assertEqual(request.get_header("Authorization"), "Bearer test-api-key")
            self.assertEqual(timeout, 60)

    def test_fact_and_directory_queries_bound_the_audit_population(self) -> None:
        with patch(
            "tools.ipeds.reconcile_endowment_scorecard.postgrest_get_all",
            return_value=[],
        ) as get_all:
            fetch_ipeds_endowment_facts(
                "https://project.example",
                "test-api-key",
                min_year=2020,
                max_year=2024,
            )
            fetch_in_scope_private_nonprofit_directory(
                "https://project.example",
                "test-api-key",
            )

        fact_call, directory_call = get_all.call_args_list
        self.assertEqual(fact_call.args[2], "ipeds_facts")
        self.assertEqual(
            fact_call.args[3],
            {
                "select": (
                    "release_id,ipeds_id,unitid,data_year,field_key,value_numeric,"
                    "source_table,source_variable"
                ),
                "field_key": "in.(endowment_value_begin,endowment_value_end)",
                "data_year": "gte.2020",
                "and": "(data_year.lte.2024,source_table.like.F*_F2)",
                "public_visible": "eq.true",
                "order": (
                    "data_year.asc,unitid.asc,field_key.asc,source_table.asc,"
                    "source_variable.asc,release_id.asc"
                ),
            },
        )
        self.assertEqual(directory_call.args[2], "institution_directory")
        self.assertEqual(directory_call.args[3]["control"], "eq.2")
        self.assertEqual(directory_call.args[3]["in_scope"], "eq.true")

    def test_opeid6_rollup_reports_every_member_including_missing_values(self) -> None:
        reporter = scorecard(100001, 60, 70)
        branch = scorecard(100002, 40, 50, main=False)
        missing_branch = scorecard(100003, None, None, main=False)

        result = reconcile_entity(
            reporter,
            fact(100001, 2024, 100, 120),
            opeid_groups={reporter.opeid6: [reporter, branch, missing_branch]},
            residual_candidates={},
        )

        self.assertTrue(result["matched"])
        self.assertEqual(result["method"], "opeid6_rollup")
        self.assertEqual(
            [member["unitid"] for member in result["members"]],
            [100001, 100002, 100003],
        )
        self.assertFalse(result["members"][2]["included_in_sum"])

    def test_unique_residual_handles_cross_opeid_allocation(self) -> None:
        reporter = scorecard(100001, 60, 70, opeid6="001111")
        acquired = scorecard(200001, 40, 50, opeid6="009999")

        result = reconcile_entity(
            reporter,
            fact(100001, 2024, 100, 120),
            opeid_groups={reporter.opeid6: [reporter]},
            residual_candidates={acquired.pair: [acquired]},  # type: ignore[dict-item]
        )

        self.assertTrue(result["matched"])
        self.assertEqual(result["method"], "unique_residual_match")
        self.assertEqual(
            [member["unitid"] for member in result["members"]],
            [100001, 200001],
        )

    def test_ambiguous_residual_is_visible_and_does_not_match(self) -> None:
        reporter = scorecard(100001, 60, 70)
        candidate_a = scorecard(200001, 40, 50, opeid6="002000")
        candidate_b = scorecard(200002, 40, 50, opeid6="003000")

        result = reconcile_entity(
            reporter,
            fact(100001, 2024, 100, 120),
            opeid_groups={reporter.opeid6: [reporter]},
            residual_candidates={candidate_a.pair: [candidate_a, candidate_b]},  # type: ignore[dict-item]
        )

        self.assertFalse(result["matched"])
        self.assertEqual(result["method"], "ambiguous_residual")
        self.assertEqual(
            [member["unitid"] for member in result["residual_candidates"]],
            [200001, 200002],
        )

    def test_branch_without_f2_fact_is_not_an_independent_reporter(self) -> None:
        reporter = scorecard(100001, 60, 70)
        branch = scorecard(100002, 40, 50, main=False)

        result = reconcile_year(
            2024,
            [reporter, branch],
            {100001: fact(100001, 2024, 100, 120)},
            [reporter, branch],
        )

        self.assertEqual(result["reporting_entities"], 1)
        self.assertEqual(result["consolidation_required"], 1)
        self.assertEqual(result["consolidation_matched"], 1)
        self.assertEqual(
            [row["unitid"] for row in result["no_f2_rows"]],
            [100002],
        )

    def test_independent_f2_reporter_cannot_be_used_as_a_residual_branch(self) -> None:
        reporter = scorecard(100001, 60, 70, opeid6="001111")
        independent = scorecard(200001, 40, 50, opeid6="001111")

        result = reconcile_year(
            2024,
            [reporter, independent],
            {
                100001: fact(100001, 2024, 100, 120),
                200001: fact(200001, 2024, 40, 50),
            },
            [reporter, independent],
        )

        by_unitid = {entity["reporter_unitid"]: entity for entity in result["entities"]}
        self.assertFalse(by_unitid[100001]["matched"])
        self.assertEqual(by_unitid[100001]["method"], "unreconciled")
        self.assertEqual(by_unitid[200001]["method"], "direct_unitid")

    def test_one_residual_branch_cannot_be_allocated_to_two_reporters(self) -> None:
        reporter_a = scorecard(100001, 60, 70, opeid6="001111")
        reporter_b = scorecard(100002, 60, 70, opeid6="002222")
        branch = scorecard(200001, 40, 50, opeid6="003333", main=False)

        result = reconcile_year(
            2024,
            [reporter_a, reporter_b, branch],
            {
                100001: fact(100001, 2024, 100, 120),
                100002: fact(100002, 2024, 100, 120),
            },
            [reporter_a, reporter_b, branch],
        )

        reporters = [
            entity for entity in result["entities"]
            if entity["reporter_unitid"] in {100001, 100002}
        ]
        self.assertEqual(
            [entity["method"] for entity in reporters],
            ["ambiguous_branch_allocation", "ambiguous_branch_allocation"],
        )
        self.assertTrue(all(not entity["matched"] for entity in reporters))
        self.assertTrue(
            all(
                next(
                    member["included_in_sum"]
                    for member in entity["members"]
                    if member["unitid"] == branch.unitid
                )
                is False
                for entity in reporters
            )
        )

    def test_one_branch_cannot_be_shared_by_rollup_and_residual_matches(self) -> None:
        rollup_reporter = scorecard(100001, 60, 70, opeid6="001111")
        residual_reporter = scorecard(100002, 60, 70, opeid6="002222")
        branch = scorecard(200001, 40, 50, opeid6="001111", main=False)

        result = reconcile_year(
            2024,
            [rollup_reporter, residual_reporter, branch],
            {
                100001: fact(100001, 2024, 100, 120),
                100002: fact(100002, 2024, 100, 120),
            },
            [rollup_reporter, residual_reporter, branch],
        )

        reporters = [
            entity for entity in result["entities"]
            if entity["reporter_unitid"] in {100001, 100002}
        ]
        self.assertEqual(
            [entity["method"] for entity in reporters],
            ["ambiguous_branch_allocation", "ambiguous_branch_allocation"],
        )
        self.assertTrue(all(not entity["matched"] for entity in reporters))
        self.assertTrue(
            all(
                entity["conflicting_allocation_unitids"] == [branch.unitid]
                for entity in reporters
            )
        )

    def test_alignment_prefers_highest_rate_then_larger_and_newer_population(self) -> None:
        candidates = [
            {"reporting_entity_rate": 0.9, "matched_reporting_entities": 9, "reporting_entities": 10, "data_year": 2023},
            {"reporting_entity_rate": 0.9, "matched_reporting_entities": 18, "reporting_entities": 20, "data_year": 2024},
            {"reporting_entity_rate": 0.8, "matched_reporting_entities": 80, "reporting_entities": 100, "data_year": 2022},
        ]

        self.assertEqual(max(candidates, key=alignment_sort_key)["data_year"], 2024)

    def test_fixture_results_require_exact_beginning_and_end_values(self) -> None:
        rows = {
            201195: scorecard(201195, 100, 120, name="Baldwin Wallace"),
            148131: scorecard(148131, 50, 60, name="Quincy"),
        }
        facts = {
            201195: fact(201195, 2024, 100, 120),
            148131: fact(148131, 2024, 50, 61),
        }

        results = fixture_results([201195, 148131, 231420], rows, facts)

        self.assertEqual([item["matched"] for item in results], [True, False, False])

    def test_gate_passes_and_fails_at_configured_threshold(self) -> None:
        rows = [scorecard(201195, 100, 120)]
        directory = [{"ipeds_id": "201195", "control": 2, "in_scope": True}]
        facts = [
            {"unitid": 201195, "data_year": 2024, "field_key": "endowment_value_begin", "value_numeric": 100},
            {"unitid": 201195, "data_year": 2024, "field_key": "endowment_value_end", "value_numeric": 120},
        ]

        passing = reconcile_scorecard(
            rows,
            facts,
            directory,
            min_year=2024,
            max_year=2024,
            threshold=Decimal("1"),
        )
        failing_facts = [
            {"unitid": 201195, "data_year": 2024, "field_key": "endowment_value_begin", "value_numeric": 100},
            {"unitid": 201195, "data_year": 2024, "field_key": "endowment_value_end", "value_numeric": 121},
        ]
        failing = reconcile_scorecard(
            rows,
            failing_facts,
            directory,
            min_year=2024,
            max_year=2024,
            threshold=Decimal("0.99"),
        )

        self.assertTrue(passing["gate"]["passed"])
        self.assertFalse(failing["gate"]["passed"])

    def test_sparse_exact_alignment_fails_reporting_coverage_gate(self) -> None:
        rows = [
            scorecard(
                200000 + index,
                100,
                120,
                opeid6=f"{index:06d}",
            )
            for index in range(100)
        ]
        directory = [
            {"ipeds_id": str(row.unitid), "control": 2, "in_scope": True}
            for row in rows
        ]
        facts = [
            {
                "unitid": rows[0].unitid,
                "data_year": 2024,
                "field_key": "endowment_value_begin",
                "value_numeric": 100,
            },
            {
                "unitid": rows[0].unitid,
                "data_year": 2024,
                "field_key": "endowment_value_end",
                "value_numeric": 120,
            },
        ]

        result = reconcile_scorecard(
            rows,
            facts,
            directory,
            min_year=2024,
            max_year=2024,
            threshold=Decimal("0.99"),
            min_reporting_coverage=Decimal("0.95"),
        )

        self.assertTrue(result["gate"]["rate_passed"])
        self.assertEqual(result["gate"]["reporting_coverage"], 0.01)
        self.assertFalse(result["gate"]["reporting_coverage_passed"])
        self.assertFalse(result["gate"]["passed"])

    def test_alignment_selection_rejects_higher_rate_sparse_year(self) -> None:
        rows = [
            scorecard(
                300000 + index,
                100,
                120,
                opeid6=f"{index:06d}",
            )
            for index in range(100)
        ]
        directory = [
            {"ipeds_id": str(row.unitid), "control": 2, "in_scope": True}
            for row in rows
        ]
        facts = [
            {
                "unitid": rows[0].unitid,
                "data_year": 2023,
                "field_key": field_key,
                "value_numeric": value,
            }
            for field_key, value in zip(
                ("endowment_value_begin", "endowment_value_end"),
                (100, 120),
            )
        ]
        for index, row in enumerate(rows[:95]):
            facts.extend([
                {
                    "unitid": row.unitid,
                    "data_year": 2024,
                    "field_key": "endowment_value_begin",
                    "value_numeric": 100,
                },
                {
                    "unitid": row.unitid,
                    "data_year": 2024,
                    "field_key": "endowment_value_end",
                    "value_numeric": 121 if index == 94 else 120,
                },
            ])

        result = reconcile_scorecard(
            rows,
            facts,
            directory,
            min_year=2023,
            max_year=2024,
            threshold=Decimal("0.99"),
            min_reporting_coverage=Decimal("0.95"),
        )

        by_year = {
            alignment["data_year"]: alignment for alignment in result["alignments"]
        }
        self.assertEqual(by_year[2023]["reporting_entity_rate"], 1)
        self.assertEqual(by_year[2023]["scorecard_population_coverage"], 0.01)
        self.assertEqual(result["best_alignment"]["data_year"], 2024)
        self.assertEqual(result["gate"]["reporting_coverage"], 0.95)

    def test_exact_decimal_reporting_coverage_boundary_passes(self) -> None:
        rows = [
            scorecard(400000 + index, 100, 120, opeid6=f"{index:06d}")
            for index in range(3)
        ]
        directory = [
            {"ipeds_id": str(row.unitid), "control": 2, "in_scope": True}
            for row in rows
        ]
        facts = [
            {
                "unitid": rows[0].unitid,
                "data_year": 2024,
                "field_key": "endowment_value_begin",
                "value_numeric": 100,
            },
            {
                "unitid": rows[0].unitid,
                "data_year": 2024,
                "field_key": "endowment_value_end",
                "value_numeric": 120,
            },
        ]
        exact_one_third = Decimal(1) / Decimal(3)

        result = reconcile_scorecard(
            rows,
            facts,
            directory,
            min_year=2024,
            max_year=2024,
            threshold=Decimal("1"),
            min_reporting_coverage=exact_one_third,
        )

        self.assertTrue(result["gate"]["reporting_coverage_passed"])
        self.assertTrue(result["gate"]["passed"])

    def test_csv_and_zip_fixture_parsing_preserves_na_branch_values(self) -> None:
        header = ["UNITID", "OPEID6", "INSTNM", "MAIN", "CONTROL", "ENDOWBEGIN", "ENDOWEND"]
        rows = [
            ["143978", "021553", "The Chicago School at Chicago", "0", "2", "14163764", "8540268"],
            ["501549", "021553", "The Chicago School at Dallas", "0", "2", "NA", "NA"],
        ]
        text = io.StringIO()
        writer = csv.writer(text)
        writer.writerow(header)
        writer.writerows(rows)

        with tempfile.TemporaryDirectory() as tmp:
            csv_path = Path(tmp) / "scorecard.csv"
            zip_path = Path(tmp) / "scorecard.zip"
            csv_path.write_text(text.getvalue(), encoding="utf-8")
            with zipfile.ZipFile(zip_path, "w") as archive:
                archive.writestr("scorecard.csv", text.getvalue())

            csv_rows = read_scorecard_rows(csv_path)
            zip_rows = read_scorecard_rows(zip_path)

        self.assertEqual(csv_rows, zip_rows)
        self.assertEqual(csv_rows[1].institution_name, "The Chicago School at Dallas")
        self.assertIsNone(csv_rows[1].pair)


if __name__ == "__main__":
    unittest.main()
