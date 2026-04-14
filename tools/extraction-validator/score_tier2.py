"""
Score a Tier 2 extract against hand-verified ground truth.

Loads a ground-truth YAML (from tools/extraction-validator/ground_truth/)
and a Tier 2 extract JSON (from tools/tier2_extractor/), joins them via
a hand-maintained ID map (from tools/extraction-validator/id_maps/), and
reports per-field match results plus an overall accuracy percentage.

Why the ID map is hand-maintained: the ground-truth files use homegrown
field IDs (b1_ft_firstyear_men) chosen for human readability during the
initial audit. The canonical CDS schema uses question numbers (B.101,
C.101, ...) derived from the commondataset.org template. The two ID
spaces don't share structure, so the join needs an explicit mapping
built once per school by inspecting both files.

The scorer uses numeric-tolerant comparison: if both the expected and
actual values parse as floats, integer-only expected values match the
integer part of the actual (e.g. "95" matches "95.24" for a percentage
field that the source PDF stores with decimal precision but the ground
truth transcribed from a visually-rounded display).

Usage:
    python tools/extraction-validator/score_tier2.py \\
        --ground-truth tools/extraction-validator/ground_truth/harvey-mudd-2025-26.yaml \\
        --tier2-extract /tmp/hmc_tier2.json \\
        --id-map tools/extraction-validator/id_maps/harvey-mudd-2025-26.yaml

The tier2 extract is produced by:
    python tools/tier2_extractor/extract.py \\
        scratch/CDS-HMC-2025.2026_shared.pdf \\
        schemas/cds_schema_2025_26.json \\
        --output /tmp/hmc_tier2.json
"""

import argparse
import json
import sys
from pathlib import Path

import yaml


def numeric_match(expected: str, actual: str) -> bool:
    """True if expected and actual represent the same number.

    Exact string equality always wins. For numeric values, an
    integer-only expected value matches the integer part of the actual
    (handles GT "95" vs actual "95.24" for percentages stored with
    decimal precision). Otherwise, exact float equality to 2 decimal
    places.
    """
    e = str(expected).strip()
    a = str(actual).strip()
    if e == a:
        return True
    try:
        ef = float(e)
        af = float(a)
    except ValueError:
        return False
    # If the expected has no decimal, compare integer parts
    if "." not in e:
        return int(af) == int(ef)
    return abs(ef - af) < 0.005


def load_ground_truth(path: Path) -> dict:
    data = yaml.safe_load(path.read_text())
    if not data or "fields" not in data:
        raise ValueError(f"{path} has no 'fields' list")
    return data


def load_tier2_extract(path: Path) -> dict:
    return json.loads(path.read_text())


def load_id_map(path: Path) -> dict:
    data = yaml.safe_load(path.read_text())
    if not data or "mappings" not in data:
        raise ValueError(f"{path} has no 'mappings' dict")
    return data["mappings"]


def score(gt_path: Path, tier2_path: Path, idmap_path: Path, verbose: bool = False) -> dict:
    gt = load_ground_truth(gt_path)
    t2 = load_tier2_extract(tier2_path)
    idmap = load_id_map(idmap_path)

    values = t2.get("values", {})
    fields = gt["fields"]

    results = []
    for f in fields:
        gid = f["id"]
        expected = f["expected"]
        critical = f.get("critical", False)
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
            result["failure_reason"] = f"qn {qn} not in tier2 extract"
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

    summary = {
        "school": gt.get("school"),
        "cds_year": gt.get("cds_year"),
        "total_fields": total,
        "matched": matched,
        "failed": total - matched,
        "accuracy_pct": round(100 * matched / total, 1) if total else 0.0,
        "critical_total": critical_total,
        "critical_matched": critical_matched,
        "critical_accuracy_pct": round(100 * critical_matched / critical_total, 1) if critical_total else 0.0,
        "unmapped_fields": unmapped,
        "tier2_producer": t2.get("producer"),
        "tier2_producer_version": t2.get("producer_version"),
        "tier2_schema_version": t2.get("schema_version"),
    }

    return {"summary": summary, "results": results}


def print_table(results: list) -> None:
    print(f"{'':2} {'ID':<28} {'Section':<6} {'Expected':>10} {'Actual':>10} {'QN':<8} {'Status'}")
    print("-" * 92)
    for r in results:
        star = "★" if r["critical"] else " "
        check = "✓" if r["match"] else "✗"
        actual_display = str(r["actual"] or "-")[:10]
        qn_display = r["mapped_qn"] or "-"
        status = check if r["match"] else f"{check} {r['failure_reason']}"
        print(f"{star}{check} {r['id']:<28} {r['section']:<6} {str(r['expected']):>10} {actual_display:>10} {qn_display:<8} {status if not r['match'] else ''}")


def main():
    parser = argparse.ArgumentParser(description=__doc__.strip().split("\n\n")[0])
    parser.add_argument("--ground-truth", type=Path, required=True,
                        help="Path to ground_truth/*.yaml")
    parser.add_argument("--tier2-extract", type=Path, required=True,
                        help="Path to Tier 2 extract JSON")
    parser.add_argument("--id-map", type=Path, required=True,
                        help="Path to id_maps/*.yaml")
    parser.add_argument("--json", action="store_true",
                        help="Output full results as JSON instead of the table")
    args = parser.parse_args()

    for p in [args.ground_truth, args.tier2_extract, args.id_map]:
        if not p.exists():
            print(f"error: {p} does not exist", file=sys.stderr)
            sys.exit(1)

    result = score(args.ground_truth, args.tier2_extract, args.id_map)

    if args.json:
        print(json.dumps(result, indent=2))
        return

    s = result["summary"]
    print(f"\nScoring Tier 2 extract against ground truth")
    print(f"School:           {s['school']}")
    print(f"CDS year:         {s['cds_year']}")
    print(f"Tier 2 producer:  {s['tier2_producer']} v{s['tier2_producer_version']}")
    print(f"Schema version:   {s['tier2_schema_version']}")
    print()

    print_table(result["results"])

    print()
    print("=" * 92)
    print(f"Overall:       {s['matched']}/{s['total_fields']} match ({s['accuracy_pct']}%)")
    print(f"Critical:      {s['critical_matched']}/{s['critical_total']} match ({s['critical_accuracy_pct']}%)")
    if s["unmapped_fields"]:
        print(f"Unmapped:      {s['unmapped_fields']} fields missing from id_map")
    print("=" * 92)


if __name__ == "__main__":
    main()
