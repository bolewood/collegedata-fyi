from __future__ import annotations

import argparse
import json
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from tools.ipeds.load_release import (
    build_loaded_table_payloads,
    build_release_notes,
    data_url_for_table,
    dedupe_rows,
    find_table_zip,
    read_release_manifest,
    read_table_zip,
    refresh_post_load_serving_views,
    prune_release_scope,
    supersede_lower_priority_facts,
    validate_release_priority,
    projection_gate_error,
    main as load_release_main,
    validate_release_manifest,
)
from tools.ipeds.mappings import FactMapping, fact_mappings_for_data_year, resolve_fact_mappings_for_columns, table_name_for_data_year
from tools.ipeds.metadata import IpedsColumn, IpedsTable, IpedsValueLabel, TablesDoc
from tools.ipeds.project import project_rows_to_facts, quality_from_label


class IpedsProjectionTests(unittest.TestCase):
    def test_imputed_fact_keeps_visible_status(self) -> None:
        rows = {"EF2024D": [{"UNITID": "123456", "RET_PCF": "88", "XRET_PCF": "2"}]}
        mapping = FactMapping(
            "retention_rate_full_time",
            "Full-time retention rate",
            "EF2024D",
            "RET_PCF",
            "number",
            "Outcomes",
            "near",
            unit="percent",
        )
        columns = [IpedsColumn("EF2024D", "RET_PCF", None, None, None, None, None, "XRET_PCF", "Retention rate", None, None, None, None, None, None, None, None, None, None, None)]
        labels = [IpedsValueLabel("EF2024D", "XRET_PCF", "2", "Imputed value", None, None, None, None)]
        facts = project_rows_to_facts(rows, [mapping], columns, labels, release_id=None, collection_year="2024-25", data_year=2024, release_type="provisional")
        self.assertEqual(facts[0]["value_numeric"], "88")
        self.assertEqual(facts[0]["quality_flag"], "imputed")
        self.assertEqual(facts[0]["imputation_label"], "Imputed value")

    def test_negative_code_becomes_status_fact(self) -> None:
        rows = {"ADM2024": [{"UNITID": "123456", "SATPCT": "-2"}]}
        mapping = FactMapping("sat_submit_rate", "SAT submit rate", "ADM2024", "SATPCT", "number", "Admissions testing", "near", unit="percent")
        columns = [IpedsColumn("ADM2024", "SATPCT", None, None, None, None, None, "XSATPCT", "SAT percent", None, None, None, None, None, None, None, None, None, None, None)]
        labels = [IpedsValueLabel("ADM2024", "SATPCT", "-2", "Not applicable", None, None, None, None)]
        facts = project_rows_to_facts(rows, [mapping], columns, labels, release_id=None, collection_year="2024-25", data_year=2024, release_type="provisional")
        self.assertEqual(facts[0]["value_numeric"], None)
        self.assertEqual(facts[0]["value_label"], "Not applicable")
        self.assertEqual(facts[0]["quality_flag"], "not_applicable")

    def test_negative_finance_value_without_value_label_stays_numeric(self) -> None:
        rows = {"F2223_F2": [{"UNITID": "123456", "F2H03C": "-725000", "XF2H03C": "R"}]}
        mapping = FactMapping(
            "endowment_spending_distribution",
            "Endowment spending distribution for current use",
            "F2223_F2",
            "F2H03C",
            "number",
            "Endowment",
            "not_cds_equivalent",
            unit="usd",
        )
        columns = [IpedsColumn("F2223_F2", "F2H03C", None, None, None, None, None, "XF2H03C", "Spending distribution", None, None, None, None, None, None, None, None, None, None, None)]
        labels = [IpedsValueLabel("F2223_F2", "XF2H03C", "R", "Reported", None, None, None, None)]

        facts = project_rows_to_facts(rows, [mapping], columns, labels, release_id=None, collection_year="2023-24", data_year=2023, release_type="final")

        self.assertEqual(facts[0]["value_numeric"], "-725000")
        self.assertEqual(facts[0]["quality_flag"], "reported")

    def test_blank_finance_value_projects_no_fact_even_with_a_flag(self) -> None:
        rows = {"F2223_F2": [{"UNITID": "123456", "F2H01": "", "XF2H01": "A"}]}
        mapping = FactMapping(
            "endowment_value_begin",
            "Endowment net assets, beginning of fiscal year",
            "F2223_F2",
            "F2H01",
            "number",
            "Endowment",
            "not_cds_equivalent",
            unit="usd",
        )
        columns = [IpedsColumn("F2223_F2", "F2H01", None, None, None, None, None, "XF2H01", "Beginning value", None, None, None, None, None, None, None, None, None, None, None)]

        facts = project_rows_to_facts(rows, [mapping], columns, [], release_id=None, collection_year="2023-24", data_year=2023, release_type="final")

        self.assertEqual(facts, [])

    def test_read_table_zip_handles_utf8_bom_csv(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "HD2024.zip"
            with zipfile.ZipFile(path, "w") as zf:
                zf.writestr("hd2024.csv", "\ufeffUNITID,INSTNM\n123456,Example College\n")
            rows = read_table_zip(path)
            self.assertEqual(rows, [{"UNITID": "123456", "INSTNM": "Example College"}])

    def test_access_export_uses_access_bundle_as_table_provenance(self) -> None:
        manifest = {
            "access_url": "https://example.test/IPEDS_2023-24_Final.zip",
            "access_exported_tables": ["F2223_F2"],
        }

        self.assertEqual(
            data_url_for_table(
                "F2223_F2",
                data_year=2023,
                access_url=None,
                release_manifest=manifest,
            ),
            "https://example.test/IPEDS_2023-24_Final.zip",
        )
        self.assertIn(
            "tableName=HD2023",
            data_url_for_table(
                "HD2023",
                data_year=2023,
                access_url=None,
                release_manifest=manifest,
            ),
        )

        with self.assertRaisesRegex(ValueError, "no Access source URL"):
            data_url_for_table(
                "F2223_F2",
                data_year=2023,
                access_url=None,
                release_manifest={"access_exported_tables": ["F2223_F2"]},
            )

    def test_release_manifest_inventory_wins_over_stale_sibling_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_dir = Path(tmp)
            stale_zip = data_dir / "F2223_F2.zip"
            access_csv = data_dir / "F2223_F2.csv"
            stale_zip.write_bytes(b"stale provisional")
            access_csv.write_text("UNITID,F2H01\n152080,17101110000\n", encoding="utf-8")

            self.assertEqual(
                find_table_zip(
                    data_dir,
                    "F2223_F2",
                    {
                        "downloaded_tables": [],
                        "access_exported_tables": ["F2223_F2"],
                    },
                ),
                access_csv,
            )
            self.assertIsNone(
                find_table_zip(
                    data_dir,
                    "F2223_F2",
                    {"downloaded_tables": [], "access_exported_tables": []},
                )
            )

    def test_quality_from_label(self) -> None:
        self.assertEqual(quality_from_label("Value was imputed"), "imputed")
        self.assertEqual(quality_from_label("Not in universe"), "not_applicable")
        self.assertEqual(quality_from_label("Privacy suppressed"), "suppressed")

    def test_dedupe_rows_uses_conflict_key(self) -> None:
        rows = [
            {"release_id": "r1", "table_name": "HD2024", "var_name": "CONTROL", "code_value": "1", "value_label": "Public"},
            {"release_id": "r1", "table_name": "HD2024", "var_name": "CONTROL", "code_value": "1", "value_label": "Public duplicate"},
            {"release_id": "r1", "table_name": "HD2024", "var_name": "CONTROL", "code_value": "2", "value_label": "Private"},
        ]
        out = dedupe_rows(rows, "release_id,table_name,var_name,code_value")
        self.assertEqual(len(out), 2)
        self.assertEqual(out[0]["value_label"], "Public duplicate")

    def test_fact_mappings_follow_data_year_table_names(self) -> None:
        self.assertEqual(table_name_for_data_year("HD2024", 2021), "HD2021")
        self.assertEqual(table_name_for_data_year("EF2024D", 2021), "EF2021D")
        self.assertEqual(table_name_for_data_year("COST1_2024", 2021), "COST1_2021")
        self.assertEqual(table_name_for_data_year("SFA2324", 2021), "SFA2021")
        self.assertEqual(table_name_for_data_year("F2223_F2", 2024), "F2324_F2")
        self.assertEqual(table_name_for_data_year("F2223_F2", 2021), "F2021_F2")
        self.assertEqual(table_name_for_data_year("F2223_F2", 2015), "F1415_F2")

        mapped_tables = {mapping.table_name for mapping in fact_mappings_for_data_year(2021)}
        self.assertIn("ADM2021", mapped_tables)
        self.assertIn("DRVGR2021", mapped_tables)
        self.assertIn("SFA2021", mapped_tables)
        self.assertIn("F2021_F2", mapped_tables)

    def test_endowment_mappings_have_required_provenance(self) -> None:
        mappings = [mapping for mapping in fact_mappings_for_data_year(2023) if mapping.display_group == "Endowment"]

        self.assertEqual(
            {mapping.field_key for mapping in mappings},
            {
                "endowment_value_begin",
                "endowment_value_end",
                "endowment_new_gifts",
                "endowment_investment_return",
                "endowment_spending_distribution",
                "endowment_other_change",
            },
        )
        self.assertTrue(all(mapping.table_name == "F2223_F2" for mapping in mappings))
        self.assertTrue(all(mapping.value_kind == "number" for mapping in mappings))
        self.assertTrue(all(mapping.unit == "usd" for mapping in mappings))
        self.assertTrue(all(mapping.definition_alignment == "not_cds_equivalent" for mapping in mappings))
        self.assertNotIn("F2H03", {mapping.var_name for mapping in mappings})

    def test_fact_mappings_resolve_finance_table_from_metadata(self) -> None:
        mappings = fact_mappings_for_data_year(2023)
        columns = [IpedsColumn("F2122_F2", "F2H01", None, None, None, None, None, "XF2H01", "Beginning value", None, None, None, None, None, None, None, None, None, None, None)]

        resolved = resolve_fact_mappings_for_columns(mappings, columns)
        beginning_value = next(mapping for mapping in resolved if mapping.field_key == "endowment_value_begin")

        self.assertEqual(beginning_value.table_name, "F2122_F2")

    def test_fact_mappings_resolve_split_sfa_tables_from_metadata(self) -> None:
        mappings = fact_mappings_for_data_year(2021)
        columns = [IpedsColumn("SFA2021_P1", "ANYAIDP", None, None, None, None, None, "XANYAIDP", "Any aid", None, None, None, None, None, None, None, None, None, None, None)]

        resolved = resolve_fact_mappings_for_columns(mappings, columns)
        any_aid = next(mapping for mapping in resolved if mapping.field_key == "any_aid_rate")

        self.assertEqual(any_aid.table_name, "SFA2021_P1")

    def test_fact_mappings_correct_2023_sfa_tablesdoc_split(self) -> None:
        mappings = fact_mappings_for_data_year(2023)
        columns = [IpedsColumn("SFA2223_P2", "ANYAIDP", None, None, None, None, None, "XANYAIDP", "Any aid", None, None, None, None, None, None, None, None, None, None, None)]

        resolved = resolve_fact_mappings_for_columns(mappings, columns)
        any_aid = next(mapping for mapping in resolved if mapping.field_key == "any_aid_rate")

        self.assertEqual(any_aid.table_name, "SFA2223_P1")

    def test_fact_mappings_resolve_historical_cost_tables(self) -> None:
        mappings = fact_mappings_for_data_year(2019)
        columns = [
            IpedsColumn("IC2019_AY", "TUITION2", None, None, None, None, None, "XTUITION2", "Tuition", None, None, None, None, None, None, None, None, None, None, None),
            IpedsColumn("IC2019", "RMBRDAMT", None, None, None, None, None, "XRMBRDAMT", "Room and board", None, None, None, None, None, None, None, None, None, None, None),
            IpedsColumn("DRVIC2019", "CINSON", None, None, None, None, None, "XCINSON", "Total price", None, None, None, None, None, None, None, None, None, None, None),
        ]

        resolved = resolve_fact_mappings_for_columns(mappings, columns)

        self.assertEqual(next(mapping for mapping in resolved if mapping.field_key == "tuition_in_state").table_name, "IC2019_AY")
        self.assertEqual(next(mapping for mapping in resolved if mapping.field_key == "room_and_board_on_campus").table_name, "IC2019")
        self.assertEqual(next(mapping for mapping in resolved if mapping.field_key == "total_price_in_state_on_campus").table_name, "DRVIC2019")

    def test_post_load_refreshes_current_cache_before_browser_modes(self) -> None:
        class FakeRpc:
            def __init__(self, calls: list[str], name: str) -> None:
                self.calls = calls
                self.name = name
                self.data = 1

            def execute(self) -> "FakeRpc":
                self.calls.append(self.name)
                return self

        class FakeClient:
            def __init__(self) -> None:
                self.calls: list[str] = []

            def rpc(self, name: str) -> FakeRpc:
                return FakeRpc(self.calls, name)

        client = FakeClient()

        refresh_post_load_serving_views(client)

        self.assertEqual(
            client.calls,
            ["refresh_ipeds_current_facts_cache", "refresh_ipeds_browser_source_modes"],
        )

    def test_required_current_cache_refresh_failure_propagates(self) -> None:
        class FailingRpc:
            def execute(self) -> None:
                raise RuntimeError("refresh failed")

        class FakeClient:
            def rpc(self, _name: str) -> FailingRpc:
                return FailingRpc()

        with self.assertRaisesRegex(RuntimeError, "refresh failed"):
            refresh_post_load_serving_views(FakeClient())

    def test_release_scope_prunes_stale_rows_after_upsert_at_mapping_scope(self) -> None:
        deletes: list[tuple[str, list[tuple[str, object]]]] = []
        selects: list[tuple[str, list[tuple[str, object]]]] = []

        class FakeQuery:
            def __init__(self, table: str) -> None:
                self.table = table
                self.filters: list[tuple[str, object]] = []
                self.operation = ""
                self.data: list[dict[str, object]] = []

            def delete(self) -> "FakeQuery":
                self.operation = "delete"
                return self

            def select(self, _columns: str) -> "FakeQuery":
                self.operation = "select"
                return self

            def eq(self, column: str, value: object) -> "FakeQuery":
                self.filters.append((column, value))
                return self

            def in_(self, column: str, value: object) -> "FakeQuery":
                self.filters.append((column, value))
                return self

            def order(self, _column: str, *, desc: bool) -> "FakeQuery":
                return self

            def range(self, _start: int, _end: int) -> "FakeQuery":
                return self

            def execute(self) -> "FakeQuery":
                if self.operation == "select":
                    selects.append((self.table, self.filters))
                    if self.table == "ipeds_raw_rows":
                        self.data = [{"unitid": 1}, {"unitid": 2}]
                    else:
                        self.data = [
                            {
                                "unitid": 1,
                                "field_key": "endowment_value_begin",
                                "source_table": "F2223_F2",
                                "source_variable": "F2H01",
                            },
                            {
                                "unitid": 2,
                                "field_key": "endowment_value_begin",
                                "source_table": "F2223_F2",
                                "source_variable": "F2H01",
                            },
                            {
                                "unitid": 3,
                                "field_key": "obsolete_endowment_field",
                                "source_table": "F2223_F2",
                                "source_variable": "OLDVAR",
                            },
                        ]
                else:
                    deletes.append((self.table, self.filters))
                return self

        class FakeClient:
            def table(self, name: str) -> FakeQuery:
                return FakeQuery(name)

        mapping = FactMapping(
            "endowment_value_begin",
            "Endowment net assets, beginning of fiscal year",
            "F2223_F2",
            "F2H01",
            "number",
            "Endowment",
            "not_cds_equivalent",
            unit="usd",
        )
        prune_release_scope(
            FakeClient(),
            release_id="release-1",
            rows_by_table={"F2223_F2": [{"UNITID": "1"}]},
            facts=[{
                "unitid": 1,
                "field_key": "endowment_value_begin",
                "source_table": "F2223_F2",
                "source_variable": "F2H01",
            }],
            fact_mappings=(mapping,),
            selected_display_groups={"Endowment"},
        )

        self.assertEqual(
            deletes,
            [
                (
                    "ipeds_raw_rows",
                    [
                        ("release_id", "release-1"),
                        ("table_name", "F2223_F2"),
                        ("unitid", [2]),
                    ],
                ),
                (
                    "ipeds_facts",
                    [
                        ("release_id", "release-1"),
                        ("field_key", "endowment_value_begin"),
                        ("source_table", "F2223_F2"),
                        ("source_variable", "F2H01"),
                        ("unitid", [2]),
                    ],
                ),
                (
                    "ipeds_facts",
                    [
                        ("release_id", "release-1"),
                        ("field_key", "obsolete_endowment_field"),
                        ("source_table", "F2223_F2"),
                        ("source_variable", "OLDVAR"),
                        ("unitid", [3]),
                    ],
                ),
            ],
        )
        self.assertEqual(len(selects), 2)

    def test_final_release_hides_lower_priority_facts_and_blocks_downgrade(self) -> None:
        updates: list[tuple[dict[str, object], list[tuple[str, object]]]] = []
        releases = [
            {"id": "preliminary-1", "release_type": "preliminary", "release_date": "2025-01-01"},
            {"id": "provisional-1", "release_type": "provisional", "release_date": "2025-06-01"},
            {"id": "final-0", "release_type": "final", "release_date": "2026-03-01"},
            {"id": "final-1", "release_type": "final", "release_date": "2026-04-01"},
        ]

        class FakeQuery:
            def __init__(self, table: str) -> None:
                self.table = table
                self.filters: list[tuple[str, object]] = []
                self.payload: dict[str, object] | None = None
                self.data: list[dict[str, object]] = []

            def select(self, _columns: str) -> "FakeQuery":
                return self

            def update(self, payload: dict[str, object]) -> "FakeQuery":
                self.payload = payload
                return self

            def eq(self, column: str, value: object) -> "FakeQuery":
                self.filters.append((column, value))
                return self

            def in_(self, column: str, value: object) -> "FakeQuery":
                self.filters.append((column, value))
                return self

            def execute(self) -> "FakeQuery":
                if self.table == "ipeds_releases":
                    self.data = releases
                elif self.payload is not None:
                    updates.append((self.payload, self.filters))
                return self

        class FakeClient:
            def table(self, name: str) -> FakeQuery:
                return FakeQuery(name)

        client = FakeClient()
        supersede_lower_priority_facts(
            client,
            release_id="final-1",
            data_year=2023,
            release_type="final",
            field_keys={"endowment_value_begin", "endowment_value_end"},
        )
        self.assertEqual(
            updates,
            [
                (
                    {"public_visible": False},
                    [
                        (
                            "release_id",
                            ["final-0", "preliminary-1", "provisional-1"],
                        ),
                        (
                            "field_key",
                            ["endowment_value_begin", "endowment_value_end"],
                        ),
                    ],
                )
            ],
        )

        with self.assertRaisesRegex(ValueError, "higher-priority release"):
            validate_release_priority(
                client,
                data_year=2023,
                release_type="provisional",
                release_date="2025-06-01",
                existing_release_id="provisional-1",
                existing_release_date="2025-06-01",
            )
        with self.assertRaisesRegex(ValueError, "same-priority revision"):
            validate_release_priority(
                client,
                data_year=2023,
                release_type="final",
                release_date="2026-03-01",
                existing_release_id="final-0",
                existing_release_date="2026-03-01",
            )
        validate_release_priority(
            client,
            data_year=2023,
            release_type="final",
            release_date="2026-05-01",
            existing_release_id=None,
            existing_release_date=None,
        )
        with self.assertRaisesRegex(ValueError, "Cannot roll back"):
            validate_release_priority(
                client,
                data_year=2023,
                release_type="final",
                release_date="2026-03-01",
                existing_release_id="final-1",
                existing_release_date="2026-04-01",
            )

    def test_targeted_table_payloads_do_not_touch_unloaded_tables(self) -> None:
        tablesdoc = TablesDoc(
            tables=[
                IpedsTable("HD2023", "HD", "2023", 1, "Directory", None, None, None),
                IpedsTable("F2223_F2", "Finance", "2022-23", 2, "Finance FASB", None, None, None),
            ],
            columns=[],
            value_labels=[],
        )
        sources = {
            "F2223_F2": {
                "data_url": "https://example.test/F2223_F2.zip",
                "row_count": 1800,
                "sha256": "abc123",
            }
        }

        payloads = build_loaded_table_payloads(
            tablesdoc,
            sources,
            release_id="release-1",
            loaded_at="2026-08-03T12:00:00+00:00",
        )

        self.assertEqual([payload["table_name"] for payload in payloads], ["F2223_F2"])
        self.assertEqual(payloads[0]["row_count"], 1800)
        self.assertEqual(payloads[0]["loaded_at"], "2026-08-03T12:00:00+00:00")

        with self.assertRaisesRegex(ValueError, "absent from Tablesdoc metadata"):
            build_loaded_table_payloads(
                tablesdoc,
                {"MISSING": {}},
                release_id="release-1",
                loaded_at="2026-08-03T12:00:00+00:00",
            )

    def test_targeted_release_notes_preserve_existing_provenance(self) -> None:
        args = argparse.Namespace(
            data_year=2023,
            display_groups=["Endowment"],
            release_date_text=None,
        )

        notes = build_release_notes(
            args,
            {
                "release_date_text": "March 2026",
                "release_date_precision": "month",
                "release_probe_due_on": "2027-01-01",
                "operator_note": "keep me",
            },
            release_date=None,
            release_date_precision=None,
        )

        self.assertEqual(notes["release_date_text"], "March 2026")
        self.assertEqual(notes["release_probe_due_on"], "2027-01-01")
        self.assertEqual(notes["operator_note"], "keep me")
        self.assertEqual(notes["last_display_groups"], ["Endowment"])

    def test_loader_rejects_provenance_that_disagrees_with_manifest(self) -> None:
        args = argparse.Namespace(
            collection_year="2023-24",
            data_year=2023,
            release_type="final",
            metadata_url="https://example.test/IPEDS202324Tablesdoc.xlsx",
            release_date_text="March 2026",
            release_date=None,
            access_url=None,
        )
        manifest = {
            "collection_year": "2023-24",
            "data_year": 2023,
            "release_type": "final",
            "metadata_url": "https://example.test/IPEDS202324Tablesdoc.xlsx",
            "release_date_text": "March 2026",
            "release_date": "2026-03-01",
            "access_url": "https://example.test/IPEDS_2023-24_Final.zip",
        }

        validate_release_manifest(args, manifest)
        args.release_date = "1999-01-01"
        with self.assertRaisesRegex(ValueError, "release date does not match"):
            validate_release_manifest(args, manifest)
        args.release_date = None
        args.release_type = "provisional"
        with self.assertRaisesRegex(ValueError, "does not match release.json"):
            validate_release_manifest(args, manifest)

        args.release_type = "final"
        args.access_url = "https://example.test/wrong.zip"
        with self.assertRaisesRegex(ValueError, "Access source URL"):
            validate_release_manifest(args, manifest)

        validate_release_manifest(args, {})

    def test_loader_requires_manifest_release_date_text_on_rerun(self) -> None:
        args = argparse.Namespace(
            collection_year="2023-24",
            data_year=2023,
            release_type="final",
            metadata_url="https://example.test/IPEDS202324Tablesdoc.xlsx",
            release_date_text=None,
            access_url=None,
        )
        manifest = {
            "collection_year": "2023-24",
            "data_year": 2023,
            "release_type": "final",
            "metadata_url": "https://example.test/IPEDS202324Tablesdoc.xlsx",
            "release_date_text": "March 2026",
        }

        with self.assertRaisesRegex(ValueError, "must be re-passed"):
            validate_release_manifest(args, manifest)

    def test_endowment_targeted_run_rejects_vacuous_success(self) -> None:
        args = argparse.Namespace(display_groups=["Endowment"])

        self.assertIn(
            "failed endowment run",
            projection_gate_error(args, {"facts_by_group": {}}) or "",
        )
        self.assertIsNone(
            projection_gate_error(args, {"facts_by_group": {"Endowment": 1}})
        )
        self.assertIsNone(
            projection_gate_error(
                argparse.Namespace(display_groups=["Costs"]),
                {"facts_by_group": {}},
            )
        )

    def test_loader_main_checks_endowment_gate_before_apply(self) -> None:
        mapping = FactMapping(
            "endowment_value_begin",
            "Endowment net assets, beginning of fiscal year",
            "F2223_F2",
            "F2H01",
            "number",
            "Endowment",
            "not_cds_equivalent",
            unit="usd",
        )
        tablesdoc = TablesDoc(tables=[], columns=[], value_labels=[])
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            data_dir = root / "release"
            data_dir.mkdir()
            metadata_path = data_dir / "tables.xlsx"
            metadata_path.write_bytes(b"metadata")
            metadata_url = "https://example.test/tables.xlsx"
            (data_dir / "release.json").write_text(
                json.dumps({
                    "collection_year": "2023-24",
                    "data_year": 2023,
                    "release_type": "final",
                    "release_date_text": "March 2026",
                    "metadata_url": metadata_url,
                    "downloaded_tables": [],
                    "access_exported_tables": ["F2223_F2"],
                }),
                encoding="utf-8",
            )
            argv = [
                "load_release.py",
                "--metadata-xlsx", str(metadata_path),
                "--metadata-url", metadata_url,
                "--data-dir", str(data_dir),
                "--collection-year", "2023-24",
                "--data-year", "2023",
                "--release-type", "final",
                "--release-date-text", "March 2026",
                "--display-groups", "Endowment",
                "--out-dir", str(root / "reports"),
                "--apply",
            ]
            with (
                patch.object(sys, "argv", argv),
                patch("tools.ipeds.load_release.parse_tablesdoc", return_value=tablesdoc),
                patch(
                    "tools.ipeds.load_release.resolve_fact_mappings_for_columns",
                    return_value=(mapping,),
                ),
                patch("tools.ipeds.load_release.project_rows_to_facts", return_value=[]),
                patch("tools.ipeds.load_release.apply_to_supabase") as apply_mock,
            ):
                self.assertEqual(load_release_main(), 2)
                apply_mock.assert_not_called()

            facts = [{"display_group": "Endowment", "quality_flag": "reported"}]
            with (
                patch.object(sys, "argv", argv),
                patch("tools.ipeds.load_release.parse_tablesdoc", return_value=tablesdoc),
                patch(
                    "tools.ipeds.load_release.resolve_fact_mappings_for_columns",
                    return_value=(mapping,),
                ),
                patch("tools.ipeds.load_release.project_rows_to_facts", return_value=facts),
                patch("tools.ipeds.load_release.apply_to_supabase") as apply_mock,
            ):
                self.assertEqual(load_release_main(), 0)
                apply_mock.assert_called_once()

    def test_release_manifest_reader_handles_absent_invalid_and_valid_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_dir = Path(tmp)
            self.assertEqual(read_release_manifest(data_dir), {})

            manifest_path = data_dir / "release.json"
            manifest_path.write_text("[]", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "must contain a JSON object"):
                read_release_manifest(data_dir)

            manifest_path.write_text("not json", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "Could not read release manifest"):
                read_release_manifest(data_dir)

            manifest_path.write_text(
                json.dumps({"release_type": "final"}),
                encoding="utf-8",
            )
            self.assertEqual(
                read_release_manifest(data_dir),
                {"release_type": "final"},
            )


if __name__ == "__main__":
    unittest.main()
