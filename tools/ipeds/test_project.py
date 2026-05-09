from __future__ import annotations

import tempfile
import unittest
import zipfile
from pathlib import Path

from tools.ipeds.load_release import read_table_zip
from tools.ipeds.mappings import FactMapping
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


if __name__ == "__main__":
    unittest.main()

