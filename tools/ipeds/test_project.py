from __future__ import annotations

import tempfile
import unittest
import zipfile
from pathlib import Path

from tools.ipeds.load_release import read_table_zip
from tools.ipeds.load_release import dedupe_rows, refresh_post_load_serving_views
from tools.ipeds.mappings import FactMapping, fact_mappings_for_data_year, resolve_fact_mappings_for_columns, table_name_for_data_year
from tools.ipeds.metadata import IpedsColumn, IpedsValueLabel
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

    def test_read_table_zip_handles_utf8_bom_csv(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "HD2024.zip"
            with zipfile.ZipFile(path, "w") as zf:
                zf.writestr("hd2024.csv", "\ufeffUNITID,INSTNM\n123456,Example College\n")
            rows = read_table_zip(path)
            self.assertEqual(rows, [{"UNITID": "123456", "INSTNM": "Example College"}])

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

        mapped_tables = {mapping.table_name for mapping in fact_mappings_for_data_year(2021)}
        self.assertIn("ADM2021", mapped_tables)
        self.assertIn("DRVGR2021", mapped_tables)
        self.assertIn("SFA2021", mapped_tables)

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


if __name__ == "__main__":
    unittest.main()
