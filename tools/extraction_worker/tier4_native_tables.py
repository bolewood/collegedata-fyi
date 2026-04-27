"""Compact Docling native table payloads for Tier 4 artifacts.

The public Tier 4 contract still exposes canonical values through
``notes.values``. This module preserves enough of Docling's native table model
to support deterministic native-table parsers and repair passes without
re-running conversion or relying only on lossy markdown.
"""

from __future__ import annotations

from typing import Any


def _get_attr(obj: Any, name: str, default: Any = None) -> Any:
    if isinstance(obj, dict):
        return obj.get(name, default)
    return getattr(obj, name, default)


def compact_bbox(bbox: Any) -> dict[str, Any] | None:
    if bbox is None:
        return None
    out: dict[str, Any] = {}
    for key in ("l", "t", "r", "b"):
        value = _get_attr(bbox, key)
        if value is not None:
            out[key] = round(float(value), 3)
    coord_origin = _get_attr(bbox, "coord_origin")
    if coord_origin is not None:
        out["coord_origin"] = str(getattr(coord_origin, "value", coord_origin))
    return out or None


def compact_provenance(item: Any) -> dict[str, Any]:
    prov = _get_attr(item, "prov", None) or []
    out: dict[str, Any] = {}
    if prov:
        first = prov[0]
        page_no = _get_attr(first, "page_no")
        if page_no is not None:
            out["page_no"] = page_no
        bbox = compact_bbox(_get_attr(first, "bbox"))
        if bbox:
            out["bbox"] = bbox
    try:
        out["item_ref"] = str(item.get_ref())
    except Exception:
        self_ref = _get_attr(item, "self_ref")
        if self_ref is not None:
            out["item_ref"] = str(self_ref)
    return out


def _cell_flag(cell: Any, name: str) -> bool:
    return bool(_get_attr(cell, name, False))


def compact_cell(cell: Any) -> dict[str, Any]:
    out = {
        "row_start": _get_attr(cell, "start_row_offset_idx", 0),
        "row_end": _get_attr(cell, "end_row_offset_idx", 0),
        "col_start": _get_attr(cell, "start_col_offset_idx", 0),
        "col_end": _get_attr(cell, "end_col_offset_idx", 0),
        "text": str(_get_attr(cell, "text", "") or ""),
    }
    row_span = _get_attr(cell, "row_span", 1)
    col_span = _get_attr(cell, "col_span", 1)
    if row_span != 1:
        out["row_span"] = row_span
    if col_span != 1:
        out["col_span"] = col_span
    for key in ("column_header", "row_header", "row_section", "fillable"):
        if _cell_flag(cell, key):
            out[key] = True
    bbox = compact_bbox(_get_attr(cell, "bbox"))
    if bbox:
        out["bbox"] = bbox
    return out


def compact_table(table: Any, table_index: int) -> dict[str, Any]:
    data = _get_attr(table, "data")
    cells = _get_attr(data, "table_cells", []) or []
    max_row = 0
    max_col = 0
    compact_cells = []
    for cell in cells:
        compact = compact_cell(cell)
        max_row = max(max_row, int(compact.get("row_end") or 0))
        max_col = max(max_col, int(compact.get("col_end") or 0))
        if compact["text"] or any(
            compact.get(flag)
            for flag in ("column_header", "row_header", "row_section", "fillable")
        ):
            compact_cells.append(compact)

    return {
        "table_index": table_index,
        "row_count": max_row,
        "column_count": max_col,
        "provenance": compact_provenance(table),
        "cells": compact_cells,
    }


def compact_tables(doc: Any) -> dict[str, Any]:
    tables = list(getattr(doc, "tables", []) or [])
    compact = [compact_table(table, i) for i, table in enumerate(tables)]
    cell_count = sum(len(table["cells"]) for table in compact)
    return {
        "format": "docling_table_cells_compact_v1",
        "table_count": len(compact),
        "cell_count": cell_count,
        "tables": compact,
    }
