#!/usr/bin/env python3
"""Compare full Tier 4 cleaner output across two Docling native-inspection runs.

This is a PRD 0111A spike helper. It does not score against ground truth; it
answers a narrower question: given the same PDFs converted with two Docling
configs, how many canonical CDS fields does the current full Tier 4 cleaner
recover from each markdown output, and where do the outputs differ?
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "tools" / "extraction_worker"))

from tier4_cleaner import clean  # noqa: E402


def value_of(item: Any) -> str:
    if isinstance(item, dict):
        return str(item.get("value", ""))
    return str(item)


def section_of(question_number: str) -> str:
    if "." in question_number:
        return question_number.split(".", 1)[0]
    return question_number[:1] or "unknown"


def stem_order_from_manifest(manifest_path: Path | None) -> list[str]:
    if not manifest_path:
        return []
    manifest = json.loads(manifest_path.read_text())
    stems: list[str] = []
    for fixture in manifest.get("fixtures", []):
        pdf_path = fixture.get("pdf_path")
        if pdf_path:
            stems.append(Path(pdf_path).stem)
    return stems


def run_stems(left_dir: Path, right_dir: Path, manifest_path: Path | None) -> list[str]:
    ordered = stem_order_from_manifest(manifest_path)
    if ordered:
        return ordered
    left = {p.parent.name for p in left_dir.glob("*/output.md")}
    right = {p.parent.name for p in right_dir.glob("*/output.md")}
    return sorted(left & right)


def clean_run(run_dir: Path, stem: str) -> dict[str, dict[str, Any]]:
    markdown_path = run_dir / stem / "output.md"
    if not markdown_path.exists():
        raise FileNotFoundError(markdown_path)
    return clean(markdown_path.read_text())


def section_counts(values: dict[str, Any]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for question_number in values:
        section = section_of(question_number)
        counts[section] = counts.get(section, 0) + 1
    return dict(sorted(counts.items()))


def compare_values(left: dict[str, Any], right: dict[str, Any]) -> dict[str, Any]:
    left_keys = set(left)
    right_keys = set(right)
    common = left_keys & right_keys
    conflicts = {
        qn: {"left": value_of(left[qn]), "right": value_of(right[qn])}
        for qn in sorted(common)
        if value_of(left[qn]) != value_of(right[qn])
    }
    return {
        "left_count": len(left),
        "right_count": len(right),
        "overlap_count": len(common),
        "left_only": sorted(left_keys - right_keys),
        "right_only": sorted(right_keys - left_keys),
        "conflicts": conflicts,
        "left_sections": section_counts(left),
        "right_sections": section_counts(right),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--left-dir", type=Path, required=True)
    ap.add_argument("--right-dir", type=Path, required=True)
    ap.add_argument("--left-label", default="left")
    ap.add_argument("--right-label", default="right")
    ap.add_argument("--manifest", type=Path)
    ap.add_argument("--out", type=Path)
    args = ap.parse_args()

    left_dir = args.left_dir if args.left_dir.is_absolute() else REPO_ROOT / args.left_dir
    right_dir = args.right_dir if args.right_dir.is_absolute() else REPO_ROOT / args.right_dir
    out_path = args.out
    if out_path and not out_path.is_absolute():
        out_path = REPO_ROOT / out_path

    rows = []
    for stem in run_stems(left_dir, right_dir, args.manifest):
        left_values = clean_run(left_dir, stem)
        right_values = clean_run(right_dir, stem)
        comparison = compare_values(left_values, right_values)
        comparison["fixture"] = stem
        rows.append(comparison)

    totals = {
        "fixture_count": len(rows),
        "left_total_fields": sum(row["left_count"] for row in rows),
        "right_total_fields": sum(row["right_count"] for row in rows),
        "overlap_total_fields": sum(row["overlap_count"] for row in rows),
        "left_only_total_fields": sum(len(row["left_only"]) for row in rows),
        "right_only_total_fields": sum(len(row["right_only"]) for row in rows),
        "conflict_total_fields": sum(len(row["conflicts"]) for row in rows),
    }
    result = {
        "left_label": args.left_label,
        "right_label": args.right_label,
        "left_dir": str(left_dir),
        "right_dir": str(right_dir),
        "manifest": str(args.manifest) if args.manifest else None,
        "totals": totals,
        "fixtures": rows,
    }

    if out_path:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(result, indent=2))

    print(
        f"| Fixture | {args.left_label} fields | {args.right_label} fields | "
        f"Overlap | {args.left_label} only | {args.right_label} only | Conflicts |"
    )
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
