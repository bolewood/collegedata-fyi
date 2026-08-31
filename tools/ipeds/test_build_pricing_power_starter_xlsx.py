"""Tests for the pricing-power starter XLSX generator."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tools.ipeds.build_pricing_power_starter_xlsx import (
    PANEL_A_HEADERS,
    PANEL_B_HEADERS,
    load_pricing_power_dataset,
    verify_workbook,
    write_workbook,
)


def _school(school_id: str, panel_b: bool) -> dict:
    row = {
        "schoolId": school_id,
        "name": school_id.replace("-", " ").title(),
        "ipedsId": "100001",
        "applied": 1000,
        "admitted": 500,
        "enrolled": 200,
        "acceptanceRate": 0.5,
        "yieldRate": 0.4,
    }
    if panel_b:
        row.update(
            {
                "burden": 0.05,
                "medianDebt": 27000,
                "monthlyPayment": 275.64,
                "earnings10yr": 66000,
                "avgNetPrice": 30000,
                "instructionFte": 15000,
                "instructionNetPriceRatio": 0.5,
            }
        )
    return row


def _meta(panel_a: int, panel_b: int) -> dict:
    return {
        "generatedAt": "2026-08-31T00:00:00Z",
        "sourceApiUrl": "https://api.example.test",
        "ipedsCycle": "fall 2024 (ADM2024)",
        "scorecardYears": ["2022-23"],
        "panelACount": panel_a,
        "panelBCount": panel_b,
        "medianAcceptance": 0.776,
        "medianYield": 0.215,
        "medianYieldB": 0.201,
        "medianBurden": 0.0521,
        "cdsCrosscheckCount": 1,
        "cdsAttachedCount": 1,
        "exclusions": {"outOfScope": 0, "missingZeroCounts": 0},
    }


def _dataset_ts(meta: dict, schools: list[dict]) -> str:
    return (
        "// generated test fixture\n"
        f"export const PRICING_POWER_META = {json.dumps(meta)} as const;\n"
        "export const PRICING_POWER_SCHOOLS: PricingPowerSchool[] "
        f"= {json.dumps(schools)};\n"
    )


def test_load_pricing_power_dataset_parses_meta_and_schools(tmp_path: Path) -> None:
    schools = [_school("alpha-college", True), _school("beta-college", False)]
    src = tmp_path / "data.ts"
    src.write_text(_dataset_ts(_meta(2, 1), schools), encoding="utf-8")
    meta, rows = load_pricing_power_dataset(src)
    assert meta["panelACount"] == 2
    assert [row["schoolId"] for row in rows] == ["alpha-college", "beta-college"]


def test_load_pricing_power_dataset_rejects_malformed_ts(tmp_path: Path) -> None:
    src = tmp_path / "broken.ts"
    src.write_text("export const SOMETHING_ELSE = 1;\n", encoding="utf-8")
    with pytest.raises(ValueError, match="could not parse"):
        load_pricing_power_dataset(src)


def test_write_workbook_rejects_meta_count_mismatch(tmp_path: Path) -> None:
    schools = [_school("alpha-college", True)]
    with pytest.raises(ValueError, match="Panel A row count"):
        write_workbook(_meta(5, 1), schools, tmp_path / "out.xlsx")
    with pytest.raises(ValueError, match="Panel B row count"):
        write_workbook(_meta(1, 3), schools, tmp_path / "out.xlsx")


def test_workbook_round_trip_verifies(tmp_path: Path) -> None:
    schools = [
        _school("alpha-college", True),
        _school("beta-college", False),
        _school("gamma-college", True),
    ]
    meta = _meta(3, 2)
    dest = tmp_path / "starter.xlsx"
    counts = write_workbook(meta, schools, dest)
    assert counts["panelAData"] == 3
    assert counts["panelBData"] == 2
    verified = verify_workbook(dest, meta)
    assert verified["panelARows"] == 1 + 3
    assert verified["panelBRows"] == 1 + 2


def test_verify_workbook_rejects_row_drift(tmp_path: Path) -> None:
    schools = [_school("alpha-college", True)]
    meta = _meta(1, 1)
    dest = tmp_path / "starter.xlsx"
    write_workbook(meta, schools, dest)
    drifted = dict(meta, panelACount=9)
    with pytest.raises(ValueError, match="Panel A row count"):
        verify_workbook(dest, drifted)


def test_headers_stay_in_sync_with_page_contract() -> None:
    assert PANEL_B_HEADERS[: len(PANEL_A_HEADERS)] == PANEL_A_HEADERS
    assert "burden" in PANEL_B_HEADERS
    assert "instruction_net_price_ratio" in PANEL_B_HEADERS
