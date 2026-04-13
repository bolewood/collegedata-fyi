#!/usr/bin/env python3
"""Run every Docling config against every PDF and score each run.

Layout:
  pdfs/<school-year>.pdf          # source documents (gitignored)
  configs/<config>.yaml           # PdfPipelineOptions
  ground_truth/<school-year>.yaml # expected values
  runs/<school-year>/<config>/
      output.md                   # Docling markdown export
      output.json                 # Docling JSON export
      result.json                 # validator output

Pairs a PDF with a ground-truth file when the stem matches.

Usage:
    python run_matrix.py                 # run all configs on all PDFs
    python run_matrix.py --only ocr-tesseract
    python run_matrix.py --pdf harvey-mudd-2025-26
    python run_matrix.py --skip-extract  # re-score existing runs only
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import asdict
from pathlib import Path

import yaml

from validate import score, FieldResult

ROOT = Path(__file__).parent
PDF_DIR = ROOT / "pdfs"
CONFIG_DIR = ROOT / "configs"
GT_DIR = ROOT / "ground_truth"
RUNS_DIR = ROOT / "runs"


def load_configs(only: list[str] | None) -> list[dict]:
    configs = []
    for p in sorted(CONFIG_DIR.glob("*.yaml")):
        cfg = yaml.safe_load(p.read_text())
        if only and cfg["name"] not in only:
            continue
        configs.append(cfg)
    return configs


def find_pdfs(wanted: list[str] | None) -> list[Path]:
    pdfs = sorted(PDF_DIR.glob("*.pdf"))
    if wanted:
        pdfs = [p for p in pdfs if p.stem in wanted]
    return pdfs


def ground_truth_for(pdf: Path) -> Path | None:
    gt = GT_DIR / f"{pdf.stem}.yaml"
    return gt if gt.exists() else None


def build_converter(cfg: dict):
    """Translate a config YAML into a Docling DocumentConverter."""
    from docling.datamodel.base_models import InputFormat
    from docling.datamodel.pipeline_options import (
        PdfPipelineOptions,
        TableFormerMode,
    )
    from docling.document_converter import DocumentConverter, PdfFormatOption

    opts = cfg.get("pipeline_options", {}) or {}
    pipeline = PdfPipelineOptions()
    pipeline.do_ocr = opts.get("do_ocr", True)
    pipeline.do_table_structure = opts.get("do_table_structure", True)
    pipeline.images_scale = float(opts.get("images_scale", 1.0))

    ts = opts.get("table_structure_options") or {}
    if ts:
        mode = ts.get("mode", "fast").lower()
        pipeline.table_structure_options.mode = (
            TableFormerMode.ACCURATE if mode == "accurate" else TableFormerMode.FAST
        )
        if "do_cell_matching" in ts:
            pipeline.table_structure_options.do_cell_matching = bool(ts["do_cell_matching"])

    ocr = opts.get("ocr_options") or {}
    if ocr:
        kind = ocr.get("kind", "easyocr").lower()
        if kind == "tesseract":
            from docling.datamodel.pipeline_options import TesseractCliOcrOptions
            pipeline.ocr_options = TesseractCliOcrOptions(
                force_full_page_ocr=bool(ocr.get("force_full_page_ocr", False)),
                lang=list(ocr.get("lang", ["eng"])),
            )
        elif kind == "easyocr":
            from docling.datamodel.pipeline_options import EasyOcrOptions
            pipeline.ocr_options = EasyOcrOptions(
                force_full_page_ocr=bool(ocr.get("force_full_page_ocr", False)),
                lang=list(ocr.get("lang", ["en"])),
            )

    return DocumentConverter(
        format_options={InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline)}
    )


def extract(pdf: Path, cfg: dict, out_dir: Path) -> tuple[Path, float]:
    out_dir.mkdir(parents=True, exist_ok=True)
    md_path = out_dir / "output.md"
    json_path = out_dir / "output.json"
    t0 = time.time()
    conv = build_converter(cfg)
    result = conv.convert(str(pdf))
    doc = result.document
    md_path.write_text(doc.export_to_markdown())
    json_path.write_text(json.dumps(doc.export_to_dict(), indent=2, default=str))
    return md_path, time.time() - t0


def run_one(pdf: Path, cfg: dict, gt: dict, skip_extract: bool) -> dict:
    out_dir = RUNS_DIR / pdf.stem / cfg["name"]
    md_path = out_dir / "output.md"
    elapsed = None
    if not md_path.exists() or not skip_extract:
        try:
            md_path, elapsed = extract(pdf, cfg, out_dir)
        except Exception as exc:  # noqa: BLE001
            return {
                "pdf": pdf.stem,
                "config": cfg["name"],
                "error": f"{type(exc).__name__}: {exc}",
                "passed": 0,
                "total": len(gt["fields"]),
                "crit_passed": 0,
                "crit_total": sum(1 for f in gt["fields"] if f.get("critical")),
                "elapsed_s": None,
            }
    md_text = md_path.read_text()
    results: list[FieldResult] = score(md_text, gt)
    passed = sum(1 for r in results if r.passed)
    crit_total = sum(1 for r in results if r.critical)
    crit_passed = sum(1 for r in results if r.critical and r.passed)
    summary = {
        "pdf": pdf.stem,
        "config": cfg["name"],
        "passed": passed,
        "total": len(results),
        "crit_passed": crit_passed,
        "crit_total": crit_total,
        "elapsed_s": elapsed,
        "failures": [asdict(r) for r in results if not r.passed],
    }
    (out_dir / "result.json").write_text(json.dumps(summary, indent=2))
    return summary


def print_matrix(rows: list[dict]) -> None:
    pdfs = sorted({r["pdf"] for r in rows})
    configs = sorted({r["config"] for r in rows})
    by_pair = {(r["pdf"], r["config"]): r for r in rows}
    col_w = max(len(c) for c in configs) + 2
    pdf_w = max(len(p) for p in pdfs) + 2
    header = " " * pdf_w + "".join(c.ljust(col_w) for c in configs)
    print("\n" + header)
    for p in pdfs:
        line = p.ljust(pdf_w)
        for c in configs:
            r = by_pair.get((p, c))
            if not r:
                cell = "-"
            elif "error" in r:
                cell = "ERR"
            else:
                mark = "*" if r["crit_total"] and r["crit_passed"] < r["crit_total"] else " "
                cell = f"{r['passed']:>2}/{r['total']:<2}{mark}"
            line += cell.ljust(col_w)
        print(line)
    print("\n(* = at least one critical field still wrong)")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", nargs="*", help="Config names to run (default: all)")
    ap.add_argument("--pdf", nargs="*", help="PDF stems to run (default: all)")
    ap.add_argument(
        "--skip-extract",
        action="store_true",
        help="Reuse existing output.md files, only re-score.",
    )
    args = ap.parse_args()

    configs = load_configs(args.only)
    pdfs = find_pdfs(args.pdf)
    if not configs:
        print("No configs found.", file=sys.stderr)
        return 2
    if not pdfs:
        print(f"No PDFs found under {PDF_DIR}. Drop source PDFs there first.", file=sys.stderr)
        return 2

    rows: list[dict] = []
    for pdf in pdfs:
        gt_path = ground_truth_for(pdf)
        if not gt_path:
            print(f"[skip] no ground-truth for {pdf.stem}", file=sys.stderr)
            continue
        gt = yaml.safe_load(gt_path.read_text())
        for cfg in configs:
            print(f"[run ] {pdf.stem} :: {cfg['name']}", file=sys.stderr)
            row = run_one(pdf, cfg, gt, args.skip_extract)
            rows.append(row)
            if "error" in row:
                print(f"       ERROR: {row['error']}", file=sys.stderr)
            else:
                print(
                    f"       {row['passed']}/{row['total']} "
                    f"({row['crit_passed']}/{row['crit_total']} critical)"
                    + (f" in {row['elapsed_s']:.1f}s" if row['elapsed_s'] else ""),
                    file=sys.stderr,
                )

    print_matrix(rows)

    # Write summary CSV
    import csv
    csv_path = RUNS_DIR / "summary.csv"
    RUNS_DIR.mkdir(exist_ok=True)
    with csv_path.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["pdf", "config", "passed", "total", "crit_passed", "crit_total", "elapsed_s", "error"])
        for r in rows:
            w.writerow([
                r.get("pdf"), r.get("config"), r.get("passed"), r.get("total"),
                r.get("crit_passed"), r.get("crit_total"),
                f"{r['elapsed_s']:.1f}" if r.get("elapsed_s") else "",
                r.get("error", ""),
            ])
    print(f"\nSummary written to {csv_path.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
