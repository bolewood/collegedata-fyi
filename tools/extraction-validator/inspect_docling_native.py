#!/usr/bin/env python3
"""Inspect Docling native document/table output for PRD 0111A.

Run this with the Docling evaluation venv, for example:

    /Users/santhonys/docling-eval/bin/python \\
      tools/extraction-validator/inspect_docling_native.py \\
      --manifest .context/docling-spike/fixtures/manifest.json

For each PDF, the script writes markdown, Docling JSON, table exports, and a
summary with a deliberately narrow C9 SAT/ACT heuristic. This is a spike tool,
not production extraction code.
"""

from __future__ import annotations

import argparse
import csv
import importlib.metadata
import json
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUT_DIR = REPO_ROOT / ".context" / "docling-spike" / "native-runs"
CONFIG_CHOICES = (
    "production",
    "production-fast",
    "docling-default",
    "table-accurate",
    "ocr-off",
    "force-backend-text",
    "no-cell-matching",
    "force-full-page-ocr",
    "layout-keep-empty-clusters",
    "layout-no-orphan-clusters",
    "layout-skip-cell-assignment",
    "layout-no-orphan-table-accurate",
)


def package_version(name: str) -> str | None:
    try:
        return importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError:
        return None


def normalize(text: str) -> str:
    text = text.lower()
    text = re.sub(r"[^a-z0-9.%]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def parse_number(text: str) -> float | None:
    m = re.search(r"-?\d+(?:\.\d+)?", str(text).replace(",", ""))
    if not m:
        return None
    try:
        return float(m.group(0))
    except ValueError:
        return None


def parse_ints(cells: Iterable[str], lo: int, hi: int) -> list[int]:
    out: list[int] = []
    for cell in cells:
        for raw in re.findall(r"\d{1,4}", str(cell).replace(",", "")):
            val = int(raw)
            if lo <= val <= hi:
                out.append(val)
    return out


def first_monotonic_triplet(nums: list[int]) -> tuple[int, int, int] | None:
    for i in range(0, max(0, len(nums) - 2)):
        a, b, c = nums[i : i + 3]
        if a <= b <= c:
            return a, b, c
    return None


@dataclass
class FieldCandidate:
    field: str
    value: int | float
    table_index: int
    row_index: int
    evidence: str
    method: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "field": self.field,
            "value": self.value,
            "table_index": self.table_index,
            "row_index": self.row_index,
            "evidence": self.evidence,
            "method": self.method,
        }


def c9_candidates_from_rows(table_index: int, rows: list[list[str]]) -> list[FieldCandidate]:
    candidates: list[FieldCandidate] = []
    for row_index, row in enumerate(rows):
        row_text = " | ".join(str(cell) for cell in row if str(cell).strip())
        norm = normalize(row_text)
        if not row_text:
            continue

        def add_triplet(prefix: str, triplet: tuple[int, int, int], method: str) -> None:
            for suffix, value in zip(("p25", "p50", "p75"), triplet):
                candidates.append(
                    FieldCandidate(
                        field=f"{prefix}_{suffix}",
                        value=value,
                        table_index=table_index,
                        row_index=row_index,
                        evidence=row_text,
                        method=method,
                    )
                )

        if "sat" in norm and "composite" in norm:
            triplet = first_monotonic_triplet(parse_ints(row, 400, 1600))
            if triplet:
                add_triplet("sat_composite", triplet, "native_table_row")
        elif "evidence" in norm and ("reading" in norm or "writing" in norm):
            triplet = first_monotonic_triplet(parse_ints(row, 200, 800))
            if triplet:
                add_triplet("sat_ebrw", triplet, "native_table_row")
        elif "sat" in norm and "math" in norm:
            triplet = first_monotonic_triplet(parse_ints(row, 200, 800))
            if triplet:
                add_triplet("sat_math", triplet, "native_table_row")
        elif "act" in norm and "composite" in norm:
            triplet = first_monotonic_triplet(parse_ints(row, 1, 36))
            if triplet:
                add_triplet("act_composite", triplet, "native_table_row")

        if "submit" in norm and "sat" in norm and "%" in row_text:
            nums = [parse_number(cell) for cell in row]
            vals = [n for n in nums if n is not None and 0 <= n <= 100]
            if vals:
                candidates.append(
                    FieldCandidate(
                        field="sat_submit_rate",
                        value=round(vals[0] / 100, 4),
                        table_index=table_index,
                        row_index=row_index,
                        evidence=row_text,
                        method="native_table_row_percent",
                    )
                )
        if "submit" in norm and "act" in norm and "%" in row_text:
            nums = [parse_number(cell) for cell in row]
            vals = [n for n in nums if n is not None and 0 <= n <= 100]
            if vals:
                candidates.append(
                    FieldCandidate(
                        field="act_submit_rate",
                        value=round(vals[0] / 100, 4),
                        table_index=table_index,
                        row_index=row_index,
                        evidence=row_text,
                        method="native_table_row_percent",
                    )
                )
    return candidates


def rows_from_dataframe(df: Any) -> list[list[str]]:
    rows: list[list[str]] = [[str(c) for c in list(df.columns)]]
    for record in df.astype(str).fillna("").values.tolist():
        rows.append([str(cell) for cell in record])
    return rows


def provenance(item: Any) -> dict[str, Any]:
    prov = getattr(item, "prov", None) or []
    out: dict[str, Any] = {}
    if prov:
        first = prov[0]
        out["page_no"] = getattr(first, "page_no", None)
        bbox = getattr(first, "bbox", None)
        if bbox is not None:
            out["bbox"] = {
                key: getattr(bbox, key, None)
                for key in ("l", "t", "r", "b", "coord_origin")
                if hasattr(bbox, key)
            }
    try:
        out["item_ref"] = str(item.get_ref())
    except Exception:
        pass
    return {k: v for k, v in out.items() if v is not None}


def apply_production_like_options(pipeline: Any, table_mode: Any) -> None:
    pipeline.do_ocr = True
    pipeline.do_table_structure = True
    pipeline.table_structure_options.mode = table_mode
    pipeline.table_structure_options.do_cell_matching = True
    pipeline.images_scale = 1.0


def build_converter(config: str, force_ocr: bool, generate_page_images: bool) -> Any:
    from docling.datamodel.base_models import InputFormat
    from docling.datamodel.pipeline_options import EasyOcrOptions, PdfPipelineOptions, TableFormerMode
    from docling.document_converter import DocumentConverter, PdfFormatOption

    pipeline = PdfPipelineOptions()
    if config in ("production", "production-fast"):
        apply_production_like_options(pipeline, TableFormerMode.FAST)
    elif config == "docling-default":
        # Keep current Docling defaults. This is useful because Docling 2.85
        # defaults to Heron layout and ACCURATE table structure.
        pass
    elif config == "table-accurate":
        # One-variable change from production-fast: TableFormer FAST -> ACCURATE.
        apply_production_like_options(pipeline, TableFormerMode.ACCURATE)
    elif config == "ocr-off":
        # One-variable change from production-fast: disable OCR for text PDFs.
        apply_production_like_options(pipeline, TableFormerMode.FAST)
        pipeline.do_ocr = False
    elif config == "force-backend-text":
        # One-variable change from production-fast: require backend PDF text.
        apply_production_like_options(pipeline, TableFormerMode.FAST)
        pipeline.force_backend_text = True
    elif config == "no-cell-matching":
        # One-variable change from production-fast: disable table cell matching.
        apply_production_like_options(pipeline, TableFormerMode.FAST)
        pipeline.table_structure_options.do_cell_matching = False
    elif config == "force-full-page-ocr":
        # One-variable change from production-fast: OCR every page.
        apply_production_like_options(pipeline, TableFormerMode.FAST)
        pipeline.ocr_options = EasyOcrOptions(force_full_page_ocr=True)
    elif config == "layout-keep-empty-clusters":
        # One-variable change from production-fast: retain empty layout clusters.
        apply_production_like_options(pipeline, TableFormerMode.FAST)
        pipeline.layout_options.keep_empty_clusters = True
    elif config == "layout-no-orphan-clusters":
        # One-variable change from production-fast: disable orphan layout clusters.
        apply_production_like_options(pipeline, TableFormerMode.FAST)
        pipeline.layout_options.create_orphan_clusters = False
    elif config == "layout-skip-cell-assignment":
        # One-variable change from production-fast: skip layout cell assignment.
        apply_production_like_options(pipeline, TableFormerMode.FAST)
        pipeline.layout_options.skip_cell_assignment = True
    elif config == "layout-no-orphan-table-accurate":
        # Combination arm after isolated testing: no orphan clusters + ACCURATE tables.
        apply_production_like_options(pipeline, TableFormerMode.ACCURATE)
        pipeline.layout_options.create_orphan_clusters = False
    else:
        raise ValueError(f"unknown config: {config}")

    if force_ocr:
        pipeline.do_ocr = True
        pipeline.ocr_options = EasyOcrOptions(force_full_page_ocr=True)
    if generate_page_images:
        pipeline.generate_page_images = True

    return DocumentConverter(
        format_options={InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline)}
    )


def pdfs_from_args(args: argparse.Namespace) -> list[Path]:
    pdfs: list[Path] = []
    if args.manifest:
        manifest = json.loads(args.manifest.read_text())
        for fixture in manifest.get("fixtures", []):
            pdf_path = REPO_ROOT / fixture["pdf_path"]
            if pdf_path.exists():
                pdfs.append(pdf_path)
    for pdf in args.pdf:
        pdfs.append(pdf)
    if args.pdf_dir:
        pdfs.extend(sorted(args.pdf_dir.glob("*.pdf")))
    seen: set[Path] = set()
    deduped: list[Path] = []
    for pdf in pdfs:
        resolved = pdf.resolve()
        if resolved not in seen:
            seen.add(resolved)
            deduped.append(pdf)
    return deduped


def inspect_pdf(pdf: Path, out_dir: Path, config: str, force_ocr: bool, generate_page_images: bool) -> dict[str, Any]:
    converter = build_converter(config, force_ocr=force_ocr, generate_page_images=generate_page_images)
    target = out_dir / pdf.stem
    tables_dir = target / "tables"
    tables_dir.mkdir(parents=True, exist_ok=True)

    started = time.time()
    result = converter.convert(str(pdf))
    elapsed = time.time() - started
    doc = result.document

    markdown = doc.export_to_markdown()
    (target / "output.md").write_text(markdown)
    (target / "docling.json").write_text(json.dumps(doc.export_to_dict(), indent=2, default=str))

    table_summaries: list[dict[str, Any]] = []
    field_candidates: list[FieldCandidate] = []
    for table_index, table in enumerate(getattr(doc, "tables", []) or []):
        table_base = tables_dir / f"table_{table_index:03d}"
        table_prov = provenance(table)
        try:
            df = table.export_to_dataframe(doc=doc)
            df.to_csv(table_base.with_suffix(".csv"), index=False, quoting=csv.QUOTE_MINIMAL)
            rows = rows_from_dataframe(df)
        except Exception as exc:
            rows = []
            table_prov["dataframe_error"] = f"{type(exc).__name__}: {exc}"
        try:
            table_base.with_suffix(".md").write_text(table.export_to_markdown(doc=doc))
        except Exception as exc:
            table_prov["markdown_error"] = f"{type(exc).__name__}: {exc}"
        try:
            table_base.with_suffix(".html").write_text(table.export_to_html(doc=doc))
        except Exception as exc:
            table_prov["html_error"] = f"{type(exc).__name__}: {exc}"

        field_candidates.extend(c9_candidates_from_rows(table_index, rows))
        table_summaries.append(
            {
                "table_index": table_index,
                "row_count": max(0, len(rows) - 1),
                "column_count": len(rows[0]) if rows else 0,
                "provenance": table_prov,
                "contains_c9_terms": any(
                    term in normalize(" ".join(row))
                    for row in rows
                    for term in ("sat", "act", "gpa")
                ),
            }
        )

    by_field: dict[str, list[dict[str, Any]]] = {}
    for candidate in field_candidates:
        by_field.setdefault(candidate.field, []).append(candidate.to_dict())

    summary = {
        "pdf": str(pdf),
        "config": config,
        "force_ocr": force_ocr,
        "generate_page_images": generate_page_images,
        "elapsed_s": round(elapsed, 3),
        "page_count": len(getattr(doc, "pages", {}) or {}),
        "markdown_length": len(markdown),
        "table_count": len(getattr(doc, "tables", []) or []),
        "tables": table_summaries,
        "c9_candidate_fields": by_field,
    }
    (target / "summary.json").write_text(json.dumps(summary, indent=2))
    return summary


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--manifest", type=Path)
    ap.add_argument("--pdf", type=Path, action="append", default=[])
    ap.add_argument("--pdf-dir", type=Path)
    ap.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    ap.add_argument("--config", choices=CONFIG_CHOICES, default="production")
    ap.add_argument("--force-ocr", action="store_true")
    ap.add_argument("--generate-page-images", action="store_true")
    ap.add_argument("--print-json", action="store_true",
                    help="Print the full rollup JSON to stdout instead of a concise summary")
    args = ap.parse_args()
    args.out_dir = args.out_dir if args.out_dir.is_absolute() else REPO_ROOT / args.out_dir

    pdfs = pdfs_from_args(args)
    if not pdfs:
        raise SystemExit("No PDFs found. Use --manifest, --pdf, or --pdf-dir.")

    args.out_dir.mkdir(parents=True, exist_ok=True)
    versions = {
        name: package_version(name)
        for name in (
            "docling",
            "docling-core",
            "docling-ibm-models",
            "docling-parse",
            "easyocr",
            "rapidocr",
            "torch",
            "pandas",
        )
    }
    (args.out_dir / "versions.json").write_text(json.dumps(versions, indent=2))

    summaries = []
    for pdf in pdfs:
        print(f"[inspect] {pdf}")
        summaries.append(
            inspect_pdf(
                pdf,
                args.out_dir,
                config=args.config,
                force_ocr=args.force_ocr,
                generate_page_images=args.generate_page_images,
            )
        )

    rollup = {
        "versions": versions,
        "config": args.config,
        "pdf_count": len(summaries),
        "summaries": summaries,
    }
    (args.out_dir / "summary.json").write_text(json.dumps(rollup, indent=2))
    if args.print_json:
        print(json.dumps(rollup, indent=2))
    else:
        print(f"Wrote {args.out_dir / 'summary.json'}")
        for summary in summaries:
            fields = sorted((summary.get("c9_candidate_fields") or {}).keys())
            print(
                f"{Path(summary['pdf']).stem}: "
                f"pages={summary['page_count']} tables={summary['table_count']} "
                f"elapsed={summary['elapsed_s']}s c9_fields={len(fields)}"
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
