from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from openpyxl import Workbook

from tools.ipeds.metadata import parse_access_page, parse_tablesdoc


class IpedsMetadataTests(unittest.TestCase):
    def test_parse_access_page_finds_latest_excel_and_zip(self) -> None:
        html = """
        <a href="/ipeds/tablefiles/zipfiles/IPEDS_2024-25_Provisional.zip">2024-25 Access</a>
        <a href="/ipeds/tablefiles/tableDocs/IPEDS202425Tablesdoc.xlsx">2024-25 Excel</a>
        Provisional Data: March 2026
        """
        releases = parse_access_page(html)
        self.assertEqual(releases[0].collection_year, "2024-25")
        self.assertEqual(releases[0].data_year, 2024)
        self.assertEqual(releases[0].release_type, "provisional")
        self.assertTrue(releases[0].metadata_url.endswith("IPEDS202425Tablesdoc.xlsx"))
        self.assertTrue(releases[0].access_url.endswith("IPEDS_2024-25_Provisional.zip"))

    def test_parse_tablesdoc_reads_core_sheets(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "tablesdoc.xlsx"
            workbook = Workbook()
            ws = workbook.active
            ws.title = "tables24"
            ws.append(["Survey", "YearCoverage", "TableName", "Tablenumber", "TableTitle", "Description", "Release", "Release_date"])
            ws.append(["HD", "2024", "HD2024", 1, "Directory", "Header", "Provisional", "March 2026"])
            ws = workbook.create_sheet("varTable24")
            ws.append(["Survey", "TableNumber", "TableName", "TableTitle", "VarNumber", "VarOrder", "VarName", "ImputationVar", "VarTitle", "DataType", "FieldWidth", "Format", "MultiRecord", "HasRV", "FileNumber", "SectionNumber", "LongDescription", "VarSource", "FileTitle", "SectionTitle"])
            ws.append(["HD", 1, "HD2024", "Directory", 1, 1, "INSTNM", "", "Institution name", "Alpha", 100, "", "No", "No", 1, 1, "Name", "Source", "File", "Section"])
            ws = workbook.create_sheet("valueSets24")
            ws.append(["TableName", "VarName", "Codevalue", "Frequency", "Percent", "ValueOrder", "ValueLabel", "VarTitle"])
            ws.append(["HD2024", "CONTROL", "1", 10, 50.0, 1, "Public", "Control"])
            workbook.save(path)

            parsed = parse_tablesdoc(path)
            self.assertEqual(parsed.tables[0].table_name, "HD2024")
            self.assertEqual(parsed.columns[0].var_name, "INSTNM")
            self.assertEqual(parsed.value_labels[0].value_label, "Public")


if __name__ == "__main__":
    unittest.main()

