"""
Score a Tier 4 cleaner extract against hand-verified ground truth.

Pipeline:
  Docling markdown → tools/extraction_worker/tier4_cleaner.clean()
                    → {question_number: {"value": str, ...}}
                    → joined via id_map to ground-truth YAML
                    → per-field match report + overall accuracy.

Mirrors score_tier2.py (same summary shape, same numeric-tolerant
comparison) so both tiers can be compared apples-to-apples.

The cleaner lives at tools/extraction_worker/tier4_cleaner.py and is
imported at runtime. The markdown input is whatever
tier4_extractor.extract() produced as `markdown` — typically
tools/extraction-validator/runs/<school>/<config>/output.md in dev.

Usage:
    python tools/extraction-validator/score_tier4.py \\
        --ground-truth tools/extraction-validator/ground_truth/harvard-2024-25.yaml \\
        --markdown tools/extraction-validator/runs/harvard-2024-25/baseline/output.md \\
        --id-map tools/extraction-validator/id_maps/harvard-2024-25.yaml

Exits non-zero if any critical field fails (same contract as validate.py).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import yaml

# Import the cleaner from the extraction_worker package.
_REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO_ROOT / "tools" / "extraction_worker"))
from tier4_cleaner import clean  # noqa: E402


def numeric_match(expected: str, actual: str) -> bool:
    """Same semantics as score_tier2.numeric_match."""
    e = str(expected).strip()
    a = str(actual).strip()
    if e == a:
        return True
    try:
        ef = float(e)
        af = float(a)
    except ValueError:
        return False
    if "." not in e:
        return int(af) == int(ef)
    return abs(ef - af) < 0.005


def score(gt_path: Path, markdown_path: Path, idmap_path: Path) -> dict:
    gt = yaml.safe_load(gt_path.read_text())
    md = markdown_path.read_text()
    idmap = yaml.safe_load(idmap_path.read_text())["mappings"]

    values = clean(md)  # {q_number: {"value": ..., "source": ...}}
    fields = gt["fields"]

    results = []
    for f in fields:
        gid = f["id"]
        expected = f["expected"]
        critical = bool(f.get("critical", False))
        qn = idmap.get(gid)
        result = {
            "id": gid,
            "section": f.get("section", ""),
            "label": f.get("label", ""),
            "expected": expected,
            "critical": critical,
            "mapped_qn": qn,
            "actual": None,
            "match": False,
            "failure_reason": None,
        }
        if not qn:
            result["failure_reason"] = "no id_map entry"
            results.append(result)
            continue
        rec = values.get(qn)
        if not rec:
            result["failure_reason"] = f"qn {qn} not in cleaner output"
            results.append(result)
            continue
        actual = rec.get("value")
        result["actual"] = actual
        result["match"] = numeric_match(expected, actual)
        if not result["match"]:
            result["failure_reason"] = "value mismatch"
        results.append(result)

    total = len(results)
    matched = sum(1 for r in results if r["match"])
    critical_total = sum(1 for r in results if r["critical"])
    critical_matched = sum(1 for r in results if r["critical"] and r["match"])
    unmapped = sum(1 for r in results if r["mapped_qn"] is None)
    cleaner_populated = len(values)

    summary = {
        "school": gt.get("school"),
        "cds_year": gt.get("cds_year"),
        "markdown": str(markdown_path),
        "total_fields": total,
        "matched": matched,
        "failed": total - matched,
        "accuracy_pct": round(100 * matched / total, 1) if total else 0.0,
        "critical_total": critical_total,
        "critical_matched": critical_matched,
        "critical_accuracy_pct": round(100 * critical_matched / critical_total, 1) if critical_total else 0.0,
        "unmapped_fields": unmapped,
        "cleaner_fields_populated": cleaner_populated,
    }

    return {"summary": summary, "results": results}


def print_table(results: list) -> None:
    print(f"{'':2} {'ID':<28} {'Section':<6} {'Expected':>10} {'Actual':>10} {'QN':<8} {'Status'}")
    print("-" * 92)
    for r in results:
        star = "★" if r["critical"] else " "
        check = "✓" if r["match"] else "✗"
        actual_display = str(r["actual"] if r["actual"] is not None else "-")[:10]
        qn_display = r["mapped_qn"] or "-"
        status = "" if r["match"] else (r["failure_reason"] or "")
        print(f"{star}{check} {r['id']:<28} {r['section']:<6} {str(r['expected']):>10} {actual_display:>10} {qn_display:<8} {status}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.strip().split("\n\n")[0])
    parser.add_argument("--ground-truth", type=Path, required=True)
    parser.add_argument("--markdown", type=Path, required=True,
                        help="Docling output.md to score")
    parser.add_argument("--id-map", type=Path, required=True)
    parser.add_argument("--json", action="store_true",
                        help="Emit full results as JSON instead of the table")
    args = parser.parse_args()

    for p in [args.ground_truth, args.markdown, args.id_map]:
        if not p.exists():
            print(f"error: {p} does not exist", file=sys.stderr)
            return 2

    result = score(args.ground_truth, args.markdown, args.id_map)

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        s = result["summary"]
        print(f"\nScoring Tier 4 cleaner output against ground truth")
        print(f"School:                   {s['school']}")
        print(f"CDS year:                 {s['cds_year']}")
        print(f"Markdown:                 {s['markdown']}")
        print(f"Cleaner fields populated: {s['cleaner_fields_populated']}")
        print()
        print_table(result["results"])
        print()
        print("=" * 92)
        print(f"Overall:   {s['matched']}/{s['total_fields']} match ({s['accuracy_pct']}%)")
        print(f"Critical:  {s['critical_matched']}/{s['critical_total']} match ({s['critical_accuracy_pct']}%)")
        if s["unmapped_fields"]:
            print(f"Unmapped:  {s['unmapped_fields']} fields missing from id_map")
        print("=" * 92)

    crit_total = result["summary"]["critical_total"]
    crit_matched = result["summary"]["critical_matched"]
    return 0 if crit_matched == crit_total else 1


if __name__ == "__main__":
    sys.exit(main())
