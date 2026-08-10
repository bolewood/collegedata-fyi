from __future__ import annotations

import os
import sys
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

from tools.ipeds.build_endowment_draw_rate_recipe import (
    FINANCE_FIELDS,
    FactCell,
    build_recipe_artifact,
    fetch_recipe_inputs,
    index_finance_rows,
    index_identity_rows,
    main as recipe_builder_main,
    normalize_draw_rate,
    quantile,
    render_typescript,
)


def cell(
    value: int | None,
    *,
    field: str,
    quality: str = "reported",
    release_id: str = "release-2024",
) -> FactCell:
    variables = {
        "endowment_value_begin": "F2H01",
        "endowment_value_end": "F2H02",
        "endowment_new_gifts": "F2H03A",
        "endowment_investment_return": "F2H03B",
        "endowment_spending_distribution": "F2H03C",
        "endowment_other_change": "F2H03D",
    }
    return FactCell(
        value=Decimal(value) if value is not None else None,
        quality_flag=quality,
        release_id=release_id,
        release_type="provisional",
        source_table="F2324_F2",
        source_variable=variables[field],
    )


def cells_for(
    *,
    begin: int = 100,
    end: int = 110,
    gifts: int = 10,
    investment: int = 5,
    spending: int = -5,
    other: int = 0,
) -> dict[str, FactCell]:
    values = {
        "endowment_value_begin": begin,
        "endowment_value_end": end,
        "endowment_new_gifts": gifts,
        "endowment_investment_return": investment,
        "endowment_spending_distribution": spending,
        "endowment_other_change": other,
    }
    return {field: cell(value, field=field) for field, value in values.items()}


def raw_finance_rows(
    ipeds_id: str,
    values: dict[str, FactCell],
    *,
    year: int = 2024,
) -> list[dict[str, object]]:
    return [
        {
            "release_id": fact.release_id,
            "ipeds_id": ipeds_id,
            "data_year": year,
            "field_key": field,
            "value_numeric": fact.value,
            "quality_flag": fact.quality_flag,
            "release_type": fact.release_type,
            "source_table": fact.source_table,
            "source_variable": fact.source_variable,
        }
        for field, fact in values.items()
    ]


def identity_rows(
    ipeds_id: str,
    name: str,
    *,
    control: str = "2",
    year: int = 2024,
) -> list[dict[str, object]]:
    values = {"institution_name": name, "control": control, "state": "MI"}
    return [
        {
            "release_id": "identity-release",
            "ipeds_id": ipeds_id,
            "data_year": year,
            "field_key": field,
            "value_text": value,
            "value_label": None,
            "quality_flag": "reported",
        }
        for field, value in values.items()
    ]


class EndowmentDrawRateRecipeBuilderTests(unittest.TestCase):
    def test_canonical_school_identity_overrides_a_stale_directory_slug(self) -> None:
        artifact = build_recipe_artifact(
            finance_rows=raw_finance_rows("168148", cells_for()),
            identity_rows=identity_rows("168148", "Tufts University"),
            directory_rows=[
                {
                    "ipeds_id": "168148",
                    "school_id": "tufts-university",
                    "in_scope": True,
                }
            ],
            release_rows=[{
                "id": "release-2024",
                "collection_year": "2024-25",
                "data_year": 2024,
                "release_type": "provisional",
                "release_date": "2026-03-01",
                "metadata_sha256": "a" * 64,
                "access_sha256": "b" * 64,
                "source_page_url": "https://example.edu",
            }],
            min_year=2024,
            max_year=2024,
            generated_at="2026-08-10",
            canonical_school_ids={"168148": "tufts"},
        )

        self.assertEqual(artifact["rows"][0]["schoolId"], "tufts")
        self.assertTrue(artifact["rows"][0]["hasCurrentSchoolPage"])

    def test_cli_identity_guard_failure_does_not_write_an_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir) / "recipe-data.ts"
            argv = [
                "build_endowment_draw_rate_recipe.py",
                "--min-year",
                "2024",
                "--max-year",
                "2024",
                "--generated-at",
                "2026-08-10",
                "--out",
                str(output),
            ]
            inputs = {
                "finance_rows": [],
                "identity_rows": [],
                "directory_rows": [],
                "release_rows": [],
            }
            with (
                patch.object(sys, "argv", argv),
                patch.dict(
                    os.environ,
                    {
                        "SUPABASE_URL": "https://project.example",
                        "SUPABASE_ANON_KEY": "test-key",
                    },
                    clear=False,
                ),
                patch(
                    "tools.ipeds.build_endowment_draw_rate_recipe.load_env"
                ),
                patch(
                    "tools.ipeds.build_endowment_draw_rate_recipe.fetch_recipe_inputs",
                    return_value=inputs,
                ),
                patch(
                    "tools.ipeds.build_endowment_draw_rate_recipe.validated_unique_school_claim_slug_map",
                    side_effect=ValueError("identity audit failed"),
                ),
                patch(
                    "tools.ipeds.build_endowment_draw_rate_recipe.build_recipe_artifact"
                ) as build_artifact,
            ):
                self.assertEqual(recipe_builder_main(), 2)

            build_artifact.assert_not_called()
            self.assertFalse(output.exists())

    def test_normalizes_both_reported_spending_signs(self) -> None:
        negative_rate, negative_error = normalize_draw_rate(cells_for())
        positive_rate, positive_error = normalize_draw_rate(
            cells_for(end=120, gifts=5, investment=5, spending=5, other=5)
        )

        self.assertEqual(negative_rate, Decimal("0.05"))
        self.assertIsNone(negative_error)
        self.assertEqual(positive_rate, Decimal("0.05"))
        self.assertIsNone(positive_error)

        zero_rate, zero_error = normalize_draw_rate(
            cells_for(end=100, gifts=0, investment=0, spending=0, other=0)
        )
        self.assertEqual(zero_rate, Decimal("0"))
        self.assertIsNone(zero_error)

    def test_excludes_unreliable_inputs_from_draw_rate(self) -> None:
        cases = {
            "incomplete_components": {
                key: value for key, value in cells_for().items() if key != "endowment_other_change"
            },
            "non_reported_input": {
                **cells_for(),
                "endowment_value_begin": cell(
                    100,
                    field="endowment_value_begin",
                    quality="imputed",
                ),
            },
            "missing_numeric_value": {
                **cells_for(),
                "endowment_other_change": cell(None, field="endowment_other_change"),
            },
            "nonpositive_beginning_value": cells_for(
                begin=0,
                end=0,
                gifts=0,
                investment=0,
                spending=0,
                other=0,
            ),
            "negative_beginning_value": cells_for(
                begin=-100,
                end=-100,
                gifts=0,
                investment=0,
                spending=0,
                other=0,
            ),
            "accounting_identity_mismatch": cells_for(end=111),
        }

        for case_name, values in cases.items():
            with self.subTest(reason=case_name):
                rate, reason = normalize_draw_rate(values)
                self.assertIsNone(rate)
                self.assertEqual(
                    reason,
                    "incomplete_components"
                    if case_name == "missing_numeric_value"
                    else "nonpositive_beginning_value"
                    if case_name == "negative_beginning_value"
                    else case_name,
                )

    def test_threshold_counts_use_strict_greater_than_boundaries(self) -> None:
        threshold_amounts = [
            50_000_000,
            50_000_001,
            70_000_000,
            70_000_001,
            150_000_000,
            150_000_001,
        ]
        finance_rows = []
        identities = []
        for index, spending in enumerate(threshold_amounts, start=1):
            ipeds_id = f"200{index:03d}"
            finance_rows.extend(
                raw_finance_rows(
                    ipeds_id,
                    cells_for(
                        begin=1_000_000_000,
                        end=1_000_000_000 + spending,
                        gifts=0,
                        investment=0,
                        spending=spending,
                        other=0,
                    ),
                )
            )
            identities.extend(identity_rows(ipeds_id, f"Threshold College {index}"))

        artifact = build_recipe_artifact(
            finance_rows=finance_rows,
            identity_rows=identities,
            directory_rows=[],
            release_rows=[{
                "id": "release-2024",
                "collection_year": "2024-25",
                "data_year": 2024,
                "release_type": "provisional",
                "release_date": "2026-03-01",
                "metadata_sha256": "a" * 64,
                "access_sha256": "b" * 64,
                "source_page_url": "https://nces.ed.gov/ipeds/use-the-data",
            }],
            min_year=2024,
            max_year=2024,
            generated_at="2026-08-03",
        )

        summary = artifact["yearSummaries"][0]
        self.assertEqual(summary["above5Count"], 5)
        self.assertEqual(summary["above7Count"], 3)
        self.assertEqual(summary["above15Count"], 1)

    def test_artifact_filters_control_and_preserves_rows_without_school_pages(self) -> None:
        eligible = cells_for(end=116, gifts=10, investment=12, spending=-6, other=0)
        mismatch = cells_for(end=117, gifts=10, investment=12, spending=-6, other=0)
        public = cells_for()
        finance = (
            raw_finance_rows("100001", eligible)
            + raw_finance_rows("100002", mismatch)
            + raw_finance_rows("100003", public)
        )
        identities = (
            identity_rows("100001", "Open College")
            + identity_rows("100002", "Former College")
            + identity_rows("100003", "Public College", control="1")
        )
        artifact = build_recipe_artifact(
            finance_rows=finance,
            identity_rows=identities,
            directory_rows=[{
                "ipeds_id": "100001",
                "school_id": "open-college",
                "in_scope": True,
                "currently_operating": True,
            }],
            release_rows=[{
                "id": "release-2024",
                "collection_year": "2024-25",
                "data_year": 2024,
                "release_type": "provisional",
                "release_date": "2026-03-01",
                "metadata_sha256": "a" * 64,
                "access_sha256": "b" * 64,
                "source_page_url": "https://nces.ed.gov/ipeds/use-the-data",
            }],
            min_year=2024,
            max_year=2024,
            generated_at="2026-08-03",
        )

        self.assertEqual([row["ipedsId"] for row in artifact["rows"]], ["100001", "100002"])
        self.assertTrue(artifact["rows"][0]["hasCurrentSchoolPage"])
        self.assertFalse(artifact["rows"][1]["hasCurrentSchoolPage"])
        self.assertEqual(artifact["rows"][1]["exclusionReason"], "accounting_identity_mismatch")
        self.assertEqual(artifact["yearSummaries"][0]["reporters"], 2)
        self.assertEqual(artifact["yearSummaries"][0]["eligible"], 1)
        self.assertEqual(artifact["yearSummaries"][0]["above5Count"], 1)
        self.assertEqual(artifact["meta"]["schoolsWithoutCurrentPage"], 1)
        self.assertRegex(
            artifact["meta"]["datasetVersion"],
            r"^ipeds-endowment-[0-9a-f]{16}$",
        )

    def test_fetches_each_fact_field_separately_and_bounds_every_query(self) -> None:
        with patch(
            "tools.ipeds.build_endowment_draw_rate_recipe.postgrest_get_all",
            return_value=[],
        ) as get_all:
            fetch_recipe_inputs(
                "https://project.example",
                "test-key",
                min_year=2020,
                max_year=2024,
            )

        calls = get_all.call_args_list
        finance_calls = calls[: len(FINANCE_FIELDS)]
        self.assertEqual(
            [call.args[3]["field_key"] for call in finance_calls],
            [f"eq.{field}" for field in FINANCE_FIELDS],
        )
        for call in finance_calls:
            self.assertEqual(call.args[3]["data_year"], "gte.2020")
            self.assertIn("data_year.lte.2024", call.args[3]["and"])
            self.assertEqual(call.args[3]["public_visible"], "eq.true")
        self.assertEqual(calls[-2].args[2], "institution_directory")
        self.assertEqual(calls[-1].args[2], "ipeds_releases")

    def test_conflicting_public_facts_fail_loudly(self) -> None:
        rows = raw_finance_rows("100001", cells_for())
        duplicate = dict(rows[0])
        duplicate["value_numeric"] = 999
        with self.assertRaisesRegex(ValueError, "conflicting public facts"):
            index_finance_rows([*rows, duplicate])

        identities = identity_rows("100001", "Original College")
        conflicting_identity = dict(identities[0])
        conflicting_identity["value_text"] = "Renamed College"
        with self.assertRaisesRegex(ValueError, "conflicting public identity facts"):
            index_identity_rows([*identities, conflicting_identity])

    def test_empty_year_and_missing_release_metadata_fail_loudly(self) -> None:
        finance = raw_finance_rows("100001", cells_for())
        with self.assertRaisesRegex(ValueError, "no eligible private nonprofit"):
            build_recipe_artifact(
                finance_rows=finance,
                identity_rows=identity_rows("100001", "Public College", control="1"),
                directory_rows=[],
                release_rows=[],
                min_year=2024,
                max_year=2024,
                generated_at="2026-08-03",
            )

        with self.assertRaisesRegex(ValueError, "release metadata is missing"):
            build_recipe_artifact(
                finance_rows=finance,
                identity_rows=identity_rows("100001", "Private College"),
                directory_rows=[],
                release_rows=[],
                min_year=2024,
                max_year=2024,
                generated_at="2026-08-03",
            )

    def test_quantiles_interpolate_and_typescript_is_deterministic(self) -> None:
        self.assertIsNone(quantile([], Decimal("0.50")))
        self.assertEqual(quantile([Decimal("0.04")], Decimal("0.50")), Decimal("0.04"))
        self.assertEqual(
            quantile([Decimal("0.02"), Decimal("0.10")], Decimal("0.50")),
            Decimal("0.060"),
        )
        artifact = {
            "meta": {"datasetVersion": "test"},
            "yearSummaries": [],
            "rows": [],
        }
        rendered = render_typescript(artifact)
        self.assertIn("Generated by tools/ipeds/build_endowment_draw_rate_recipe.py", rendered)
        self.assertIn('"datasetVersion": "test"', rendered)
        self.assertNotIn("test-key", rendered)

    def test_typescript_uses_the_latest_school_identity(self) -> None:
        base_row = {
            "ipedsId": "100001",
            "schoolId": "new-university",
            "hasCurrentSchoolPage": True,
            "state": "MI",
            "beginningValue": 100,
            "endingValue": 105,
            "spendingDistribution": -5,
            "drawRate": 0.05,
            "exclusionReason": None,
            "releaseType": "final",
            "sourceTable": "F2324_F2",
            "sourceVariable": "F2H03C",
        }
        rendered = render_typescript({
            "meta": {"datasetVersion": "test"},
            "yearSummaries": [],
            "rows": [
                {**base_row, "year": 2020, "schoolName": "Old College"},
                {**base_row, "year": 2024, "schoolName": "New University"},
            ],
        })

        self.assertIn('"schoolName":"New University"', rendered)
        self.assertNotIn('"schoolName":"Old College"', rendered)


if __name__ == "__main__":
    unittest.main()
