from __future__ import annotations

import unittest
from types import SimpleNamespace

from tier4_native_tables import compact_bbox, compact_tables


class FakeTable:
    def __init__(self, cells):
        self.data = SimpleNamespace(table_cells=cells)
        self.prov = [
            SimpleNamespace(
                page_no=7,
                bbox=SimpleNamespace(l=1.23456, t=2.34567, r=3.45678, b=4.56789, coord_origin="TOPLEFT"),
            )
        ]

    def get_ref(self):
        return "#/tables/0"


class Tier4NativeTablesTest(unittest.TestCase):
    def test_compact_bbox_rounds_coordinates(self):
        bbox = SimpleNamespace(l=1.23456, t=2.34567, r=3.45678, b=4.56789, coord_origin="TOPLEFT")

        self.assertEqual(
            compact_bbox(bbox),
            {
                "l": 1.235,
                "t": 2.346,
                "r": 3.457,
                "b": 4.568,
                "coord_origin": "TOPLEFT",
            },
        )

    def test_compact_tables_preserves_cell_flags_and_provenance(self):
        cells = [
            SimpleNamespace(
                start_row_offset_idx=0,
                end_row_offset_idx=1,
                start_col_offset_idx=0,
                end_col_offset_idx=1,
                text="Header",
                column_header=True,
                row_header=False,
                row_section=False,
                fillable=False,
                bbox=None,
            ),
            SimpleNamespace(
                start_row_offset_idx=1,
                end_row_offset_idx=2,
                start_col_offset_idx=0,
                end_col_offset_idx=1,
                text="Row",
                column_header=False,
                row_header=True,
                row_section=False,
                fillable=False,
                bbox=None,
            ),
        ]
        doc = SimpleNamespace(tables=[FakeTable(cells)])

        payload = compact_tables(doc)

        self.assertEqual(payload["format"], "docling_table_cells_compact_v1")
        self.assertEqual(payload["table_count"], 1)
        self.assertEqual(payload["cell_count"], 2)
        table = payload["tables"][0]
        self.assertEqual(table["row_count"], 2)
        self.assertEqual(table["column_count"], 1)
        self.assertEqual(table["provenance"]["page_no"], 7)
        self.assertEqual(table["provenance"]["item_ref"], "#/tables/0")
        self.assertTrue(table["cells"][0]["column_header"])
        self.assertTrue(table["cells"][1]["row_header"])


if __name__ == "__main__":
    unittest.main()
