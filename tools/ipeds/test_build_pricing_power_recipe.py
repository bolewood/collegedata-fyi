from __future__ import annotations

import os
import sys
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

from tools.ipeds.build_pricing_power_recipe import (
    ADM_COUNT_FIELDS,
    SYRACUSE_IPEDS_ID,
    SYRACUSE_SCHOOL_ID,
    _assert_build_invariants,
    acceptance_rate,
    build_recipe_artifact,
    debt_burden,
    fetch_recipe_inputs,
    index_adm_counts,
    instruction_net_price_ratio,
    main as recipe_builder_main,
    panel_a_quadrant,
    panel_b_quadrant,
    parse_count,
    parse_decimal,
    rate_json,
    render_typescript,
    round_rate,
    yield_rate,
)

SYRACUSE_APPLIED = 44480
SYRACUSE_ADMITTED = 20427
SYRACUSE_ENROLLED = 3835


def adm_rows(
    ipeds_id: str,
    *,
    school_id: str,
    name: str,
    applied: int | None,
    admitted: int | None,
    enrolled: int | None,
    in_scope: bool | None = True,
    source_table: str = "ADM2024",
) -> list[dict[str, object]]:
    counts = {
        "applicants_total": applied,
        "admissions_total": admitted,
        "enrolled_total": enrolled,
    }
    rows = []
    for field, value in counts.items():
        if value is None:
            continue
        rows.append(
            {
                "school_id": school_id,
                "school_name": name,
                "ipeds_id": ipeds_id,
                "in_scope": in_scope,
                "field_key": field,
                "value_numeric": value,
                "source_table": source_table,
                "data_year": 2024,
                "quality_flag": "reported",
            }
        )
    return rows


def scorecard_row(
    ipeds_id: str,
    *,
    earnings: float = 79164,
    monthly: float = 275.64,
    debt: float = 26000,
    net_price: float = 38793,
    instruction: float = 20551,
    year: str = "2022-23",
) -> dict[str, object]:
    return {
        "ipeds_id": ipeds_id,
        "scorecard_data_year": year,
        "earnings_10yr_median": earnings,
        "median_debt_monthly_payment": monthly,
        "median_debt_completers": debt,
        "avg_net_price": net_price,
        "instructional_expenditure_fte": instruction,
    }


def directory_row(
    ipeds_id: str,
    school_id: str,
    name: str,
    *,
    in_scope: bool = True,
) -> dict[str, object]:
    return {
        "ipeds_id": ipeds_id,
        "school_id": school_id,
        "school_name": name,
        "in_scope": in_scope,
    }


def syracuse_facts() -> list[dict[str, object]]:
    return adm_rows(
        SYRACUSE_IPEDS_ID,
        school_id=SYRACUSE_SCHOOL_ID,
        name="Syracuse University",
        applied=SYRACUSE_APPLIED,
        admitted=SYRACUSE_ADMITTED,
        enrolled=SYRACUSE_ENROLLED,
    )


class PricingPowerRecipeBuilderTests(unittest.TestCase):
    def test_rates_use_exact_decimal_division_from_raw_counts(self) -> None:
        applied = Decimal(SYRACUSE_APPLIED)
        admitted = Decimal(SYRACUSE_ADMITTED)
        enrolled = Decimal(SYRACUSE_ENROLLED)
        exact_acceptance = acceptance_rate(admitted, applied)
        exact_yield = yield_rate(enrolled, admitted)

        self.assertEqual(exact_acceptance, Decimal(SYRACUSE_ADMITTED) / Decimal(SYRACUSE_APPLIED))
        self.assertEqual(exact_yield, Decimal(SYRACUSE_ENROLLED) / Decimal(SYRACUSE_ADMITTED))
        self.assertNotEqual(exact_acceptance, Decimal("0.46"))
        self.assertNotEqual(exact_yield, Decimal("0.19"))
        self.assertEqual(round_rate(exact_acceptance), Decimal("0.4592"))
        self.assertEqual(round_rate(exact_yield), Decimal("0.1877"))
        self.assertEqual(rate_json(exact_acceptance), 0.4592)
        self.assertEqual(rate_json(exact_yield), 0.1877)

    def test_syracuse_fixture_reproduces_burden_and_instruction_ratio(self) -> None:
        burden = debt_burden(Decimal("275.64"), Decimal("79164"))
        ratio = instruction_net_price_ratio(Decimal("20551"), Decimal("38793"))
        self.assertEqual(round_rate(burden), Decimal("0.0418"))
        self.assertEqual(round_rate(ratio), Decimal("0.5298"))
        self.assertGreaterEqual(burden, Decimal("0.041"))
        self.assertLessEqual(burden, Decimal("0.043"))

    def test_rounding_happens_only_at_serialization(self) -> None:
        artifact = build_recipe_artifact(
            fact_rows=syracuse_facts()
            + adm_rows(
                "168148",
                school_id="tufts",
                name="Tufts University",
                applied=1000,
                admitted=200,
                enrolled=50,
            ),
            directory_rows=[],
            scorecard_rows=[
                scorecard_row(SYRACUSE_IPEDS_ID),
                scorecard_row("168148", earnings=80000, monthly=200),
            ],
            browser_rows=[],
            generated_at="2026-08-31",
            validate=False,
        )
        syracuse = next(
            row for row in artifact["schools"] if row["schoolId"] == SYRACUSE_SCHOOL_ID
        )
        exact = Decimal(SYRACUSE_ADMITTED) / Decimal(SYRACUSE_APPLIED)
        self.assertEqual(syracuse["acceptanceRate"], 0.4592)
        self.assertNotEqual(Decimal(str(syracuse["acceptanceRate"])), exact)
        self.assertEqual(syracuse["applied"], SYRACUSE_APPLIED)
        self.assertEqual(syracuse["admitted"], SYRACUSE_ADMITTED)
        self.assertEqual(syracuse["enrolled"], SYRACUSE_ENROLLED)
        self.assertEqual(syracuse["burden"], 0.0418)
        self.assertEqual(syracuse["medianDebt"], 26000)
        self.assertEqual(syracuse["monthlyPayment"], 275.64)
        self.assertEqual(syracuse["earnings10yr"], 79164)
        self.assertEqual(syracuse["avgNetPrice"], 38793)
        self.assertEqual(syracuse["instructionFte"], 20551)
        self.assertEqual(syracuse["instructionNetPriceRatio"], 0.5298)

    def test_excludes_missing_zero_inverted_counts_and_out_of_scope(self) -> None:
        facts = (
            syracuse_facts()
            + adm_rows("100001", school_id="zero-enroll", name="Zero College", applied=10, admitted=8, enrolled=0)
            + adm_rows("100002", school_id="incomplete", name="Incomplete College", applied=10, admitted=None, enrolled=None)
            + adm_rows("100003", school_id="over-admit", name="Over Admit", applied=10, admitted=12, enrolled=5)
            + adm_rows("100004", school_id="over-enroll", name="Over Enroll", applied=10, admitted=8, enrolled=9)
            + adm_rows(
                "100005",
                school_id="oos-college",
                name="Out of Scope College",
                applied=10,
                admitted=8,
                enrolled=4,
                in_scope=False,
            )
        )
        current = adm_rows(
            "100006",
            school_id="oos-current",
            name="Current OOS",
            applied=20,
            admitted=10,
            enrolled=5,
            in_scope=False,
        )
        artifact = build_recipe_artifact(
            fact_rows=facts,
            current_fact_rows=current,
            directory_rows=[
                directory_row(SYRACUSE_IPEDS_ID, SYRACUSE_SCHOOL_ID, "Syracuse University"),
                directory_row("100001", "zero-enroll", "Zero College"),
                directory_row("100002", "incomplete", "Incomplete College"),
                directory_row("100003", "over-admit", "Over Admit"),
                directory_row("100004", "over-enroll", "Over Enroll"),
                directory_row("100005", "oos-college", "Out of Scope College", in_scope=False),
                directory_row("100006", "oos-current", "Current OOS", in_scope=False),
            ],
            scorecard_rows=[scorecard_row(SYRACUSE_IPEDS_ID)],
            browser_rows=[],
            generated_at="2026-08-31",
            validate=False,
        )
        exclusions = artifact["meta"]["exclusions"]
        self.assertEqual(exclusions["missingZeroCounts"], 2)
        self.assertEqual(exclusions["admittedGtApplied"], 1)
        self.assertEqual(exclusions["enrolledGtAdmitted"], 1)
        self.assertEqual(exclusions["outOfScope"], 2)
        self.assertEqual(artifact["meta"]["panelACount"], 1)
        self.assertEqual(artifact["schools"][0]["schoolId"], SYRACUSE_SCHOOL_ID)

    def test_panel_b_drops_missing_and_nonpositive_scorecard_fields(self) -> None:
        facts = syracuse_facts() + adm_rows(
            "100010",
            school_id="no-earnings",
            name="No Earnings College",
            applied=100,
            admitted=50,
            enrolled=20,
        )
        artifact = build_recipe_artifact(
            fact_rows=facts,
            directory_rows=[],
            scorecard_rows=[
                scorecard_row(SYRACUSE_IPEDS_ID),
                scorecard_row("100010", earnings=0),
            ],
            browser_rows=[],
            generated_at="2026-08-31",
            validate=False,
        )
        self.assertEqual(artifact["meta"]["panelACount"], 2)
        self.assertEqual(artifact["meta"]["panelBCount"], 1)
        self.assertEqual(artifact["meta"]["exclusions"]["missingNonpositiveScorecard"], 1)
        self.assertEqual(artifact["meta"]["joinMisses"]["scorecard"], 0)
        self.assertIn("burden", artifact["schools"][1])
        self.assertNotIn("burden", next(row for row in artifact["schools"] if row["schoolId"] == "no-earnings"))

    def test_scorecard_join_miss_is_counted_separately(self) -> None:
        artifact = build_recipe_artifact(
            fact_rows=syracuse_facts()
            + adm_rows("100011", school_id="orphan", name="Orphan College", applied=10, admitted=5, enrolled=2),
            directory_rows=[],
            scorecard_rows=[scorecard_row(SYRACUSE_IPEDS_ID)],
            browser_rows=[],
            generated_at="2026-08-31",
            validate=False,
        )
        self.assertEqual(artifact["meta"]["joinMisses"]["scorecard"], 1)
        self.assertEqual(artifact["meta"]["panelBCount"], 1)

    def test_median_quadrants_use_inclusive_higher_side(self) -> None:
        self.assertEqual(
            panel_a_quadrant(Decimal("0.40"), Decimal("0.30"), Decimal("0.50"), Decimal("0.25")),
            "lowerAcceptanceHigherYield",
        )
        self.assertEqual(
            panel_a_quadrant(Decimal("0.50"), Decimal("0.25"), Decimal("0.50"), Decimal("0.25")),
            "higherAcceptanceHigherYield",
        )
        self.assertEqual(
            panel_a_quadrant(Decimal("0.40"), Decimal("0.20"), Decimal("0.50"), Decimal("0.25")),
            "lowerAcceptanceLowerYield",
        )
        self.assertEqual(
            panel_a_quadrant(Decimal("0.60"), Decimal("0.20"), Decimal("0.50"), Decimal("0.25")),
            "higherAcceptanceLowerYield",
        )
        self.assertEqual(
            panel_b_quadrant(Decimal("0.30"), Decimal("0.05"), Decimal("0.25"), Decimal("0.04")),
            "higherYieldHigherBurden",
        )
        self.assertEqual(
            panel_b_quadrant(Decimal("0.20"), Decimal("0.05"), Decimal("0.25"), Decimal("0.04")),
            "lowerYieldHigherBurden",
        )
        self.assertEqual(
            panel_b_quadrant(Decimal("0.30"), Decimal("0.03"), Decimal("0.25"), Decimal("0.04")),
            "higherYieldLowerBurden",
        )
        self.assertEqual(
            panel_b_quadrant(Decimal("0.20"), Decimal("0.03"), Decimal("0.25"), Decimal("0.04")),
            "lowerYieldLowerBurden",
        )

        facts = []
        scorecards = []
        # Four schools so medians sit on the 2nd/3rd average; counts still sum.
        specs = [
            ("a", "0.20", "0.40", "0.06"),
            ("b", "0.30", "0.30", "0.05"),
            ("c", "0.60", "0.20", "0.03"),
            ("d", "0.70", "0.10", "0.02"),
        ]
        for index, (slug, acc, yld, burden) in enumerate(specs, start=1):
            applied = 1000
            admitted = int(Decimal(acc) * applied)
            enrolled = int(Decimal(yld) * admitted)
            ipeds = f"20000{index}"
            facts.extend(
                adm_rows(
                    ipeds,
                    school_id=slug,
                    name=f"College {slug}",
                    applied=applied,
                    admitted=admitted,
                    enrolled=enrolled,
                )
            )
            # Choose earnings/monthly to hit the target burden exactly: monthly = burden * earnings / 12
            earnings = Decimal("60000")
            monthly = (Decimal(burden) * earnings) / Decimal(12)
            scorecards.append(
                scorecard_row(
                    ipeds,
                    earnings=float(earnings),
                    monthly=float(monthly),
                    debt=20000,
                    net_price=20000,
                    instruction=10000,
                )
            )
        artifact = build_recipe_artifact(
            fact_rows=facts,
            directory_rows=[],
            scorecard_rows=scorecards,
            browser_rows=[],
            generated_at="2026-08-31",
            validate=False,
        )
        self.assertEqual(sum(artifact["meta"]["quadrantsA"].values()), 4)
        self.assertEqual(sum(artifact["meta"]["quadrantsB"].values()), 4)
        self.assertEqual(artifact["meta"]["panelACount"], 4)
        self.assertEqual(artifact["meta"]["panelBCount"], 4)

    def test_cds_crosscheck_is_optional_and_dedupes_latest_row(self) -> None:
        artifact = build_recipe_artifact(
            fact_rows=syracuse_facts()
            + adm_rows("102614", school_id="alaska", name="Alaska", applied=100, admitted=50, enrolled=20),
            directory_rows=[],
            scorecard_rows=[
                scorecard_row(SYRACUSE_IPEDS_ID),
                scorecard_row("102614"),
            ],
            browser_rows=[
                {
                    "school_id": "alaska",
                    "ipeds_id": "102614",
                    "canonical_year": "2024-25",
                    "sub_institutional": None,
                    "acceptance_rate": 0.5,
                    "yield_rate": 0.4,
                    "updated_at": "2026-05-25T00:00:00+00:00",
                },
                {
                    "school_id": "alaska",
                    "ipeds_id": "102614",
                    "canonical_year": "2024-25",
                    "sub_institutional": None,
                    "acceptance_rate": 0.6,
                    "yield_rate": 0.3,
                    "updated_at": "2026-05-05T00:00:00+00:00",
                },
            ],
            generated_at="2026-08-31",
            validate=False,
        )
        alaska = next(row for row in artifact["schools"] if row["schoolId"] == "alaska")
        syracuse = next(row for row in artifact["schools"] if row["schoolId"] == SYRACUSE_SCHOOL_ID)
        self.assertEqual(alaska["cdsAcceptanceRate"], 0.5)
        self.assertEqual(alaska["cdsYieldRate"], 0.4)
        self.assertEqual(alaska["cdsYear"], "2024-25")
        self.assertNotIn("cdsAcceptanceRate", syracuse)
        self.assertEqual(artifact["meta"]["cdsCrosscheckCount"], 1)
        self.assertEqual(artifact["meta"]["cdsAttachedCount"], 1)

    def test_canonical_school_identity_overrides_a_stale_directory_slug(self) -> None:
        artifact = build_recipe_artifact(
            fact_rows=adm_rows(
                "168148",
                school_id="tufts-university",
                name="Tufts University",
                applied=100,
                admitted=20,
                enrolled=10,
            )
            + syracuse_facts(),
            directory_rows=[
                directory_row("168148", "tufts-university", "Tufts University"),
                directory_row(SYRACUSE_IPEDS_ID, SYRACUSE_SCHOOL_ID, "Syracuse University"),
            ],
            scorecard_rows=[scorecard_row("168148"), scorecard_row(SYRACUSE_IPEDS_ID)],
            browser_rows=[],
            generated_at="2026-08-31",
            canonical_school_ids={"168148": "tufts"},
            validate=False,
        )
        tufts = next(row for row in artifact["schools"] if row["ipedsId"] == "168148")
        self.assertEqual(tufts["schoolId"], "tufts")

    def test_refuses_integer_rounded_rate_fields_in_the_plotted_series(self) -> None:
        rows = syracuse_facts() + [
            {
                "school_id": SYRACUSE_SCHOOL_ID,
                "school_name": "Syracuse University",
                "ipeds_id": SYRACUSE_IPEDS_ID,
                "in_scope": True,
                "field_key": "admit_rate_total",
                "value_numeric": 46,
                "source_table": "DRVADM2024",
                "data_year": 2024,
                "quality_flag": "reported",
            }
        ]
        with self.assertRaisesRegex(ValueError, "integer-rounded DRVADM"):
            index_adm_counts(rows)

    def test_skips_non_adm2024_source_tables(self) -> None:
        rows = adm_rows(
            "100020",
            school_id="old-cycle",
            name="Old Cycle",
            applied=10,
            admitted=5,
            enrolled=2,
            source_table="ADM2023",
        )
        self.assertEqual(index_adm_counts(rows), {})

    def test_conflicting_counts_fail_loudly(self) -> None:
        rows = syracuse_facts() + adm_rows(
            SYRACUSE_IPEDS_ID,
            school_id=SYRACUSE_SCHOOL_ID,
            name="Syracuse University",
            applied=1,
            admitted=1,
            enrolled=1,
        )
        with self.assertRaisesRegex(ValueError, "conflicting ADM2024"):
            index_adm_counts(rows)

    def test_build_assertions_fail_without_syracuse_or_with_striped_rates(self) -> None:
        schools = [
            {
                "schoolId": "other",
                "ipedsId": "100000",
                "yieldRate": 0.1877,
            }
        ]
        with self.assertRaisesRegex(ValueError, "missing from Panel A"):
            _assert_build_invariants(
                schools,
                [],
                {"panelACount": 1800, "panelBCount": 1600},
                {0.1877},
            )
        syracuse_row = {
            "schoolId": SYRACUSE_SCHOOL_ID,
            "ipedsId": SYRACUSE_IPEDS_ID,
            "burdenExact": Decimal("0.0418"),
            "yieldRate": 0.1877,
        }
        with self.assertRaisesRegex(ValueError, "missing from Panel B"):
            _assert_build_invariants(
                [syracuse_row],
                [],
                {"panelACount": 1800, "panelBCount": 1600},
                {0.1877},
            )
        with self.assertRaisesRegex(ValueError, "integer-rounded"):
            _assert_build_invariants(
                [syracuse_row],
                [syracuse_row],
                {"panelACount": 1800, "panelBCount": 1600},
                {Decimal("0.01") * i for i in range(80)},
            )
        with self.assertRaisesRegex(ValueError, "Panel A count"):
            _assert_build_invariants(
                [syracuse_row],
                [syracuse_row],
                {"panelACount": 50, "panelBCount": 1600},
                {Decimal("0.1") + Decimal("0.0001") * i for i in range(120)},
            )

    def test_build_assertions_reject_bad_syracuse_burden_and_panel_b_count(
        self,
    ) -> None:
        yields = {Decimal("0.1") + Decimal("0.0001") * i for i in range(120)}
        drifted = {
            "schoolId": SYRACUSE_SCHOOL_ID,
            "ipedsId": SYRACUSE_IPEDS_ID,
            "burdenExact": Decimal("0.09"),
            "yieldRate": 0.1877,
        }
        with self.assertRaisesRegex(ValueError, "Syracuse burden"):
            _assert_build_invariants(
                [drifted],
                [drifted],
                {"panelACount": 1800, "panelBCount": 1600},
                yields,
            )
        healthy = dict(drifted, burdenExact=Decimal("0.0418"))
        with self.assertRaisesRegex(ValueError, "Panel B count"):
            _assert_build_invariants(
                [healthy],
                [healthy],
                {"panelACount": 1800, "panelBCount": 50},
                yields,
            )

    def test_parse_helpers_reject_nonfinite_and_fractional_values(self) -> None:
        for bad in (None, "NaN", "inf", "-Infinity", "abc", ""):
            self.assertIsNone(parse_decimal(bad), repr(bad))
        self.assertEqual(parse_decimal("0.5"), Decimal("0.5"))
        self.assertEqual(parse_decimal(10), Decimal(10))
        self.assertIsNone(parse_count("10.5"))
        self.assertIsNone(parse_count("NaN"))
        self.assertEqual(parse_count("10"), Decimal(10))

    def test_fetches_each_adm_field_from_unified_and_current_facts(self) -> None:
        with patch(
            "tools.ipeds.build_pricing_power_recipe.postgrest_get_all",
            return_value=[],
        ) as get_all:
            fetch_recipe_inputs("https://project.example", "test-key")

        calls = get_all.call_args_list
        unified_calls = [call for call in calls if call.args[2] == "school_facts_unified"]
        current_calls = [call for call in calls if call.args[2] == "ipeds_current_facts"]
        self.assertEqual(
            [call.args[3]["field_key"] for call in unified_calls],
            [f"eq.{field}" for field in ADM_COUNT_FIELDS],
        )
        self.assertEqual(
            [call.args[3]["field_key"] for call in current_calls],
            [f"eq.{field}" for field in ADM_COUNT_FIELDS],
        )
        for call in unified_calls + current_calls:
            self.assertEqual(call.args[3]["source_table"], "eq.ADM2024")
            self.assertNotIn("admit_rate_total", call.args[3]["select"])
            self.assertNotIn("yield_rate_total", call.args[3]["select"])
        tables = [call.args[2] for call in calls]
        self.assertIn("institution_directory", tables)
        self.assertIn("scorecard_summary", tables)
        self.assertIn("school_browser_rows", tables)
        browser = next(call for call in calls if call.args[2] == "school_browser_rows")
        self.assertEqual(browser.args[3]["canonical_year"], "eq.2024-25")
        self.assertEqual(browser.args[3]["sub_institutional"], "is.null")

    def test_cli_identity_guard_failure_does_not_write_an_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir) / "recipe-data.ts"
            argv = [
                "build_pricing_power_recipe.py",
                "--generated-at",
                "2026-08-31",
                "--out",
                str(output),
            ]
            inputs = {
                "fact_rows": [],
                "current_fact_rows": [],
                "directory_rows": [],
                "scorecard_rows": [],
                "browser_rows": [],
            }
            with (
                patch.object(sys, "argv", argv),
                patch.dict(
                    os.environ,
                    {
                        "SUPABASE_URL": "https://project.example",
                        "SUPABASE_SERVICE_ROLE_KEY": "test-key",
                    },
                    clear=False,
                ),
                patch("tools.ipeds.build_pricing_power_recipe.load_builder_env"),
                patch(
                    "tools.ipeds.build_pricing_power_recipe.fetch_recipe_inputs",
                    return_value=inputs,
                ),
                patch(
                    "tools.ipeds.build_pricing_power_recipe.validated_unique_school_claim_slug_map",
                    side_effect=ValueError("identity audit failed"),
                ),
                patch(
                    "tools.ipeds.build_pricing_power_recipe.build_recipe_artifact"
                ) as build_artifact,
            ):
                self.assertEqual(recipe_builder_main(), 2)

            build_artifact.assert_not_called()
            self.assertFalse(output.exists())

    def test_typescript_names_the_builder_and_syracuse_annotation(self) -> None:
        rendered = render_typescript(
            {
                "meta": {
                    "panelACount": 1,
                    "annotationSchoolId": SYRACUSE_SCHOOL_ID,
                },
                "schools": [
                    {
                        "schoolId": SYRACUSE_SCHOOL_ID,
                        "name": "Syracuse University",
                        "ipedsId": SYRACUSE_IPEDS_ID,
                        "applied": SYRACUSE_APPLIED,
                        "admitted": SYRACUSE_ADMITTED,
                        "enrolled": SYRACUSE_ENROLLED,
                        "acceptanceRate": 0.4592,
                        "yieldRate": 0.1877,
                    }
                ],
            }
        )
        self.assertIn("Generated by tools/ipeds/build_pricing_power_recipe.py", rendered)
        self.assertIn(f'PRICING_POWER_ANNOTATION_SCHOOL_ID = "{SYRACUSE_SCHOOL_ID}"', rendered)
        self.assertIn(f'PRICING_POWER_ANNOTATION_IPEDS_ID = "{SYRACUSE_IPEDS_ID}"', rendered)
        self.assertNotIn("test-key", rendered)
        self.assertNotIn("admit_rate_total", rendered)


if __name__ == "__main__":
    unittest.main()
