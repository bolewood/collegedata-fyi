#!/usr/bin/env python3
"""Compare markdown-cleaner output with native Docling table-cleaner output.

This is a PRD 0111A spike helper. It reuses the existing Tier 4 resolver logic,
but replaces `_parse_markdown_tables(markdown)` with tables loaded from Docling's
native `TableItem.export_to_dataframe()` CSV exports. Inline non-table patterns
still receive the document markdown as surrounding text, but table extraction is
driven by native table rows rather than pipe-delimited markdown tables.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "tools" / "extraction_worker"))

import tier4_cleaner as cleaner  # noqa: E402


def value_of(item: Any) -> str:
    if isinstance(item, dict):
        return str(item.get("value", ""))
    return str(item)


def comparable_value(item: Any) -> str:
    value = value_of(item).replace(",", "").strip()
    try:
        number = float(value)
    except ValueError:
        return value.lower()
    if number.is_integer():
        return str(int(number))
    return f"{number:.10g}"


def section_of(question_number: str) -> str:
    if "." in question_number:
        return question_number.split(".", 1)[0]
    return question_number[:1] or "unknown"


def table_sort_key(path: Path) -> int:
    match = re.search(r"table_(\d+)", path.stem)
    return int(match.group(1)) if match else 0


def csv_rows(path: Path) -> list[list[str]]:
    with path.open(newline="") as fh:
        return [[cell.strip() for cell in row] for row in csv.reader(fh)]


def native_tables_from_run(run_doc_dir: Path) -> list[dict[str, Any]]:
    tables: list[dict[str, Any]] = []
    for csv_path in sorted((run_doc_dir / "tables").glob("table_*.csv"), key=table_sort_key):
        raw_rows = [row for row in csv_rows(csv_path) if any(cell.strip() for cell in row)]
        if not raw_rows:
            continue

        nominal_header = raw_rows[0]
        header_looks_like_data = any(re.search(r"\d", cell) for cell in nominal_header[1:])
        if header_looks_like_data:
            headers = [""] * len(nominal_header)
            data_rows = raw_rows
        else:
            headers = nominal_header
            data_rows = raw_rows[1:]

        parsed_rows: list[dict[str, Any]] = []
        prev_label = ""
        for cells in data_rows:
            if not cells:
                continue
            label = cells[0]
            values = cells[1:] if len(cells) > 1 else []
            if (
                re.fullmatch(r"[A-Z]?\d{1,3}", label.strip())
                and values
                and values[0].strip()
                and cleaner._extract_number(values[0]) is None
            ):
                label = f"{label} {values[0]}".strip()
                values = values[1:]
            has_values = any(v.strip() for v in values)

            if not label.strip() and has_values:
                label = prev_label
                parsed_rows.append({"label": label, "values": values, "headers": headers})
                continue

            if (
                label.strip()
                and has_values
                and parsed_rows
                and parsed_rows[-1]["label"].strip()
                and not any(v.strip() for v in parsed_rows[-1]["values"])
            ):
                merged = parsed_rows[-1]["label"] + " " + label
                parsed_rows[-1] = {"label": merged, "values": values, "headers": headers}
                prev_label = merged
                continue

            if label.strip():
                prev_label = label
            parsed_rows.append({"label": label, "values": values, "headers": headers})

        tables.append(
            {
                "section": "",
                "headers": headers,
                "rows": parsed_rows,
                "native_table_csv": str(csv_path),
            }
        )
    return tables


def grid_from_json_table(table: dict[str, Any]) -> tuple[list[list[str]], set[int]]:
    cells = table.get("data", {}).get("table_cells", [])
    max_row = 0
    max_col = 0
    column_header_cols: set[int] = set()
    for cell in cells:
        max_row = max(max_row, int(cell.get("end_row_offset_idx", 0)))
        max_col = max(max_col, int(cell.get("end_col_offset_idx", 0)))
        if cell.get("column_header"):
            for col in range(
                int(cell.get("start_col_offset_idx", 0)),
                int(cell.get("end_col_offset_idx", 0)),
            ):
                column_header_cols.add(col)

    grid = [["" for _ in range(max_col)] for _ in range(max_row)]
    for cell in cells:
        row = int(cell.get("start_row_offset_idx", 0))
        col = int(cell.get("start_col_offset_idx", 0))
        if row >= len(grid) or col >= len(grid[row]):
            continue
        text = str(cell.get("text") or "").strip()
        if not text:
            continue
        grid[row][col] = f"{grid[row][col]} {text}".strip() if grid[row][col] else text
    return grid, column_header_cols


def native_tables_from_json(run_doc_dir: Path) -> list[dict[str, Any]]:
    docling_path = run_doc_dir / "docling.json"
    data = json.loads(docling_path.read_text())
    tables: list[dict[str, Any]] = []
    for table_index, table in enumerate(data.get("tables", [])):
        grid, column_header_cols = grid_from_json_table(table)
        if not grid:
            continue
        if column_header_cols:
            first_value_col = min(column_header_cols)
            value_cols = sorted(column_header_cols)
        else:
            first_value_col = 1
            value_cols = list(range(1, len(grid[0]) if grid else 0))
        label_cols = max(1, first_value_col)
        headers = [
            " ".join(cell for cell in grid[0][:label_cols] if cell).strip(),
            *[grid[0][col] if col < len(grid[0]) else "" for col in value_cols],
        ]

        parsed_rows: list[dict[str, Any]] = []
        prev_label = ""
        for cells in grid[1:]:
            label = " ".join(cell for cell in cells[:label_cols] if cell).strip()
            values = [cells[col] if col < len(cells) else "" for col in value_cols]
            if (
                re.fullmatch(r"[A-Z]?\d{1,3}", label.strip())
                and values
                and values[0].strip()
                and cleaner._extract_number(values[0]) is None
            ):
                label = f"{label} {values[0]}".strip()
                values = values[1:]
            has_values = any(v.strip() for v in values)

            if not label.strip() and has_values:
                label = prev_label
                parsed_rows.append({"label": label, "values": values, "headers": headers})
                continue

            if (
                label.strip()
                and has_values
                and parsed_rows
                and parsed_rows[-1]["label"].strip()
                and not any(v.strip() for v in parsed_rows[-1]["values"])
            ):
                merged = parsed_rows[-1]["label"] + " " + label
                parsed_rows[-1] = {"label": merged, "values": values, "headers": headers}
                prev_label = merged
                continue

            if label.strip():
                prev_label = label
            parsed_rows.append({"label": label, "values": values, "headers": headers})

        tables.append(
            {
                "section": "",
                "headers": headers,
                "rows": parsed_rows,
                "native_table_ref": table.get("self_ref") or f"table_{table_index}",
            }
        )
    return tables


def clean_from_native_tables(tables: list[dict[str, Any]], text: str) -> dict[str, dict]:
    values: dict[str, dict] = {}

    def _norm_hint(ch: Any) -> Any:
        return cleaner._normalize_label(ch) if isinstance(ch, str) else ch

    field_map_norm = [
        (cleaner._normalize_label(s), qn, _norm_hint(ch))
        for s, qn, ch in cleaner._FIELD_MAP
    ]
    percentile_map_norm = [
        (cleaner._normalize_label(s), ci, qn)
        for s, ci, qn in cleaner._PERCENTILE_MAP
    ]

    for table in tables:
        for row in table["rows"]:
            label_norm = cleaner._normalize_label(row["label"])
            headers_norm = [cleaner._normalize_label(h) for h in row.get("headers", [])]

            for substr, qnum, col_hint in field_map_norm:
                if substr not in label_norm:
                    continue

                val_str = None
                if isinstance(col_hint, int):
                    if col_hint < len(row["values"]):
                        val_str = row["values"][col_hint]
                elif isinstance(col_hint, str):
                    matches = []
                    for ci, hdr in enumerate(headers_norm):
                        if col_hint in hdr:
                            vi = ci - 1
                            if 0 <= vi < len(row["values"]):
                                matches.append((ci, vi, hdr))
                    if matches:
                        best = next((m for m in matches if "full" in m[2]), matches[0])
                        val_str = row["values"][best[1]]

                if val_str is None:
                    continue
                num = cleaner._extract_number(val_str)
                if num is None:
                    continue
                if qnum not in values:
                    values[qnum] = {"value": num, "source": "native_docling_table"}

            for substr, col_idx, qnum in percentile_map_norm:
                if substr not in label_norm:
                    continue
                if col_idx < len(row["values"]):
                    num = cleaner._extract_number(row["values"][col_idx])
                    if num and qnum not in values:
                        values[qnum] = {"value": num, "source": "native_docling_table"}

    text_lower = text.lower()
    for anchor, value_re, qnum in cleaner._INLINE_PATTERNS:
        if qnum in values:
            continue
        match = re.search(anchor, text_lower)
        if not match:
            continue
        window = text[match.end(): match.end() + 300]
        value_match = re.search(value_re, window, re.IGNORECASE)
        if value_match:
            values[qnum] = {
                "value": value_match.group(1),
                "source": "native_docling_table_inline",
            }

    idx = cleaner._get_schema()
    for resolver in cleaner._RESOLVERS:
        new_values = resolver(tables, text, idx)
        for qn, rec in new_values.items():
            if qn not in values:
                values[qn] = {
                    **rec,
                    "source": "native_docling_table",
                }

    return values


def compare_values(left: dict[str, Any], right: dict[str, Any]) -> dict[str, Any]:
    left_keys = set(left)
    right_keys = set(right)
    common = left_keys & right_keys
    conflicts = {
        qn: {"left": value_of(left[qn]), "right": value_of(right[qn])}
        for qn in sorted(common)
        if comparable_value(left[qn]) != comparable_value(right[qn])
    }
    return {
        "left_count": len(left),
        "right_count": len(right),
        "overlap_count": len(common),
        "left_only": sorted(left_keys - right_keys),
        "right_only": sorted(right_keys - left_keys),
        "conflicts": conflicts,
    }


def stem_order_from_manifest(manifest_path: Path | None) -> list[str]:
    if not manifest_path:
        return []
    manifest = json.loads(manifest_path.read_text())
    return [
        Path(fixture["pdf_path"]).stem
        for fixture in manifest.get("fixtures", [])
        if fixture.get("pdf_path")
    ]


def run_stems(run_dir: Path, manifest_path: Path | None) -> list[str]:
    ordered = stem_order_from_manifest(manifest_path)
    if ordered:
        return ordered
    return sorted(p.parent.name for p in run_dir.glob("*/output.md"))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--run-dir", type=Path, required=True)
    ap.add_argument("--manifest", type=Path)
    ap.add_argument("--table-source", choices=["json", "csv"], default="json")
    ap.add_argument("--out", type=Path)
    args = ap.parse_args()

    run_dir = args.run_dir if args.run_dir.is_absolute() else REPO_ROOT / args.run_dir
    out_path = args.out
    if out_path and not out_path.is_absolute():
        out_path = REPO_ROOT / out_path

    rows = []
    for stem in run_stems(run_dir, args.manifest):
        doc_dir = run_dir / stem
        markdown = (doc_dir / "output.md").read_text()
        markdown_values = cleaner.clean(markdown)
        native_tables = (
            native_tables_from_json(doc_dir)
            if args.table_source == "json"
            else native_tables_from_run(doc_dir)
        )
        native_values = clean_from_native_tables(native_tables, markdown)
        comparison = compare_values(markdown_values, native_values)
        comparison["fixture"] = stem
        comparison["native_sections"] = {
            section: sum(1 for qn in native_values if section_of(qn) == section)
            for section in sorted({section_of(qn) for qn in native_values})
        }
        rows.append(comparison)

    totals = {
        "fixture_count": len(rows),
        "markdown_total_fields": sum(row["left_count"] for row in rows),
        "native_total_fields": sum(row["right_count"] for row in rows),
        "overlap_total_fields": sum(row["overlap_count"] for row in rows),
        "markdown_only_total_fields": sum(len(row["left_only"]) for row in rows),
        "native_only_total_fields": sum(len(row["right_only"]) for row in rows),
        "conflict_total_fields": sum(len(row["conflicts"]) for row in rows),
    }
    result = {
        "run_dir": str(run_dir),
        "manifest": str(args.manifest) if args.manifest else None,
        "table_source": args.table_source,
        "totals": totals,
        "fixtures": rows,
    }
    if out_path:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(result, indent=2))

    print("| Fixture | Markdown fields | Native table fields | Overlap | Markdown only | Native only | Conflicts |")
    print("|---|---:|---:|---:|---:|---:|---:|")
    for row in rows:
        print(
            f"| {row['fixture']} | {row['left_count']} | {row['right_count']} | "
            f"{row['overlap_count']} | {len(row['left_only'])} | "
            f"{len(row['right_only'])} | {len(row['conflicts'])} |"
        )
    print(json.dumps(totals, indent=2))
    if out_path:
        print(f"Wrote {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
