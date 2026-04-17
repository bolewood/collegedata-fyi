"""
Diff two CDS structural schemas and emit a change report.

Structural schemas live at `schemas/cds_schema_YYYY_YY.structural.json` (see
`schemas/README.md`). Each is a per-year layout describing every subsection,
row label, and column header in the CDS template for that year.

This tool compares two years' structural schemas and classifies each field:

    unchanged        — same (subsection, normalized row_label, normalized header) in both
    removed          — exists in year A, absent in year B
    added            — exists in year B, absent in year A
    possibly_renamed — a removal and addition in the SAME subsection where the
                       row_label changed but the column_header matched, and the
                       label similarity is above a threshold

Normalization handles the known structural drifts:
    - "freshmen" / "freshman" → "first year"
    - "male(s)" / "female(s)" → "men" / "women"
    - "another gender" → "unknown"
    - "nonresident aliens" → "nonresidents"

These rewrites mean the B1 first-year enrollment fields register as unchanged
across the 2023-24 → 2025-26 boundary even though the visible labels changed.
The diff surfaces every OTHER change — the genuine schema discontinuities.

Output is two files:
    schemas/cds_schema_{yearA}-to-{yearB}.diff.json  (machine-readable)
    schemas/cds_schema_{yearA}-to-{yearB}.diff.md    (human-readable summary)

Usage:
    python tools/schema_builder/diff.py \\
        schemas/cds_schema_2023_24.structural.json \\
        schemas/cds_schema_2025_26.structural.json \\
        schemas/cds_schema_2023_24-to-2025_26.diff.json
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from difflib import SequenceMatcher
from pathlib import Path


# Rename-detection threshold — two labels with same (subsection, header) but
# different text need to be this similar (SequenceMatcher ratio) to flag as
# "possibly_renamed" rather than a distinct add+remove pair.
RENAME_SIMILARITY_THRESHOLD = 0.55


def normalize(s: str | None) -> str:
    """Normalize a row label or column header for structural comparison.

    Applies known CDS template drifts (freshmen→first-year, male→men,
    another gender→unknown, nonresident aliens→nonresidents) so that
    fields that are semantically the same but lexically different still
    compare equal.
    """
    if s is None:
        return ""
    t = s.lower().strip()
    t = re.sub(r"\bmales?\b", "men", t)
    t = re.sub(r"\bfemales?\b", "women", t)
    t = re.sub(r"\banother gender\b", "unknown", t)
    t = re.sub(r"\bunknown gender\b", "unknown", t)
    t = re.sub(r"\bnonresident aliens?\b", "nonresidents", t)
    t = re.sub(r"\bfreshmen\b", "first year", t)
    t = re.sub(r"\bfreshman\b", "first year", t)
    t = re.sub(r"[^\w\s]", " ", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t


@dataclass(frozen=True)
class FieldKey:
    subsection: str
    row_label: str          # normalized
    column_header: str      # normalized


@dataclass
class Field:
    key: FieldKey
    raw_row_label: str      # un-normalized, for display
    raw_column_header: str | None


def index_fields(schema: dict) -> dict[FieldKey, Field]:
    """Flatten a structural schema into a {FieldKey: Field} map."""
    out: dict[FieldKey, Field] = {}
    for sec in schema["sections"]:
        for sub in sec["subsections"]:
            for q in sub["questions"]:
                for col in q["columns"]:
                    raw_row = q["row_label"]
                    raw_col = col["header"]
                    k = FieldKey(
                        subsection=sub["id"],
                        row_label=normalize(raw_row),
                        column_header=normalize(raw_col),
                    )
                    # First write wins on collision (rare — would indicate
                    # duplicate row emission by the parser).
                    if k not in out:
                        out[k] = Field(
                            key=k,
                            raw_row_label=raw_row,
                            raw_column_header=raw_col,
                        )
    return out


def find_possible_renames(
    removed: list[Field],
    added: list[Field],
) -> tuple[list[tuple[Field, Field, float]], list[Field], list[Field]]:
    """Within each (subsection, column_header) group, try to pair up a removed
    field with an added field by label similarity.

    Returns (rename_pairs, remaining_removed, remaining_added).
    """
    # Group both lists by (subsection, normalized column_header).
    by_group = defaultdict(lambda: {"removed": [], "added": []})
    for f in removed:
        by_group[(f.key.subsection, f.key.column_header)]["removed"].append(f)
    for f in added:
        by_group[(f.key.subsection, f.key.column_header)]["added"].append(f)

    rename_pairs: list[tuple[Field, Field, float]] = []
    unmatched_removed: list[Field] = []
    unmatched_added: list[Field] = []

    for (sub, hdr), g in by_group.items():
        rem_list = g["removed"]
        add_list = g["added"]
        # Greedy best-pair match: for each removed, find most similar added
        # above threshold; consume both on match.
        add_used = [False] * len(add_list)
        for r in rem_list:
            best_j = -1
            best_sim = RENAME_SIMILARITY_THRESHOLD
            for j, a in enumerate(add_list):
                if add_used[j]:
                    continue
                sim = SequenceMatcher(None, r.key.row_label, a.key.row_label).ratio()
                if sim >= best_sim:
                    best_sim = sim
                    best_j = j
            if best_j >= 0:
                add_used[best_j] = True
                rename_pairs.append((r, add_list[best_j], best_sim))
            else:
                unmatched_removed.append(r)
        for j, a in enumerate(add_list):
            if not add_used[j]:
                unmatched_added.append(a)

    return rename_pairs, unmatched_removed, unmatched_added


def diff_schemas(schema_a: dict, schema_b: dict) -> dict:
    year_a = schema_a.get("schema_version", "A")
    year_b = schema_b.get("schema_version", "B")
    fields_a = index_fields(schema_a)
    fields_b = index_fields(schema_b)

    keys_a = set(fields_a.keys())
    keys_b = set(fields_b.keys())

    unchanged_keys = keys_a & keys_b
    only_in_a = [fields_a[k] for k in (keys_a - keys_b)]
    only_in_b = [fields_b[k] for k in (keys_b - keys_a)]

    rename_pairs, removed, added = find_possible_renames(only_in_a, only_in_b)

    # Per-subsection rollup.
    subs = set()
    for f in removed:
        subs.add(f.key.subsection)
    for f in added:
        subs.add(f.key.subsection)
    for r, a, _ in rename_pairs:
        subs.add(r.key.subsection)

    by_subsection = {}
    for sub in sorted(subs):
        r_count = sum(1 for f in removed if f.key.subsection == sub)
        a_count = sum(1 for f in added if f.key.subsection == sub)
        rn_count = sum(1 for r, a, _ in rename_pairs if r.key.subsection == sub)
        u_count = sum(1 for k in unchanged_keys if k.subsection == sub)
        by_subsection[sub] = {
            "unchanged": u_count,
            "added": a_count,
            "removed": r_count,
            "possibly_renamed": rn_count,
        }

    return {
        "year_a": year_a,
        "year_b": year_b,
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "summary": {
            "year_a_fields": len(fields_a),
            "year_b_fields": len(fields_b),
            "unchanged": len(unchanged_keys),
            "removed": len(removed),
            "added": len(added),
            "possibly_renamed": len(rename_pairs),
        },
        "by_subsection": by_subsection,
        "removed": [
            {
                "subsection": f.key.subsection,
                "row_label": f.raw_row_label,
                "column_header": f.raw_column_header,
            }
            for f in sorted(removed, key=lambda f: (f.key.subsection, f.key.row_label))
        ],
        "added": [
            {
                "subsection": f.key.subsection,
                "row_label": f.raw_row_label,
                "column_header": f.raw_column_header,
            }
            for f in sorted(added, key=lambda f: (f.key.subsection, f.key.row_label))
        ],
        "possibly_renamed": [
            {
                "subsection": r.key.subsection,
                "column_header": r.raw_column_header,
                "from": r.raw_row_label,
                "to": a.raw_row_label,
                "similarity": round(sim, 3),
            }
            for r, a, sim in sorted(
                rename_pairs,
                key=lambda t: (t[0].key.subsection, -t[2]),
            )
        ],
    }


def render_markdown(diff: dict) -> str:
    yA = diff["year_a"]
    yB = diff["year_b"]
    s = diff["summary"]
    lines = [
        f"# CDS schema diff: {yA} → {yB}",
        "",
        f"_Generated {diff['generated_at']}_",
        "",
        "## Summary",
        "",
        f"- **{yA}**: {s['year_a_fields']} fields",
        f"- **{yB}**: {s['year_b_fields']} fields",
        f"- **Unchanged**: {s['unchanged']}",
        f"- **Removed** (in {yA}, not {yB}): {s['removed']}",
        f"- **Added** (in {yB}, not {yA}): {s['added']}",
        f"- **Possibly renamed** (row label changed within same subsection + header): {s['possibly_renamed']}",
        "",
        "## Per-subsection churn",
        "",
        "| Subsection | Unchanged | Removed | Added | Renamed |",
        "|---|---:|---:|---:|---:|",
    ]
    for sub, counts in diff["by_subsection"].items():
        lines.append(
            f"| {sub} | {counts['unchanged']} | {counts['removed']} | "
            f"{counts['added']} | {counts['possibly_renamed']} |"
        )
    lines.append("")

    if diff["possibly_renamed"]:
        lines.append("## Possibly renamed fields")
        lines.append("")
        lines.append("| Subsection | Header | From | To | Similarity |")
        lines.append("|---|---|---|---|---:|")
        for r in diff["possibly_renamed"]:
            hdr = r["column_header"] or "—"
            lines.append(
                f"| {r['subsection']} | {hdr} | {r['from']!r} | {r['to']!r} | {r['similarity']:.2f} |"
            )
        lines.append("")

    if diff["removed"]:
        lines.append(f"## Removed ({len(diff['removed'])})")
        lines.append("")
        lines.append("| Subsection | Row label | Column header |")
        lines.append("|---|---|---|")
        for r in diff["removed"]:
            hdr = r["column_header"] or "—"
            lines.append(f"| {r['subsection']} | {r['row_label']} | {hdr} |")
        lines.append("")

    if diff["added"]:
        lines.append(f"## Added ({len(diff['added'])})")
        lines.append("")
        lines.append("| Subsection | Row label | Column header |")
        lines.append("|---|---|---|")
        for r in diff["added"]:
            hdr = r["column_header"] or "—"
            lines.append(f"| {r['subsection']} | {r['row_label']} | {hdr} |")
        lines.append("")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__.strip().split("\n\n")[0])
    parser.add_argument("schema_a", type=Path, help="Path to the older structural schema JSON")
    parser.add_argument("schema_b", type=Path, help="Path to the newer structural schema JSON")
    parser.add_argument("output", type=Path, help="Path to write the diff JSON")
    parser.add_argument(
        "--markdown",
        type=Path,
        help="Optional path to write a human-readable Markdown summary "
             "(defaults to <output>.md if not given)",
    )
    args = parser.parse_args()

    for p in [args.schema_a, args.schema_b]:
        if not p.exists():
            print(f"error: {p} does not exist", file=sys.stderr)
            sys.exit(1)

    schema_a = json.loads(args.schema_a.read_text())
    schema_b = json.loads(args.schema_b.read_text())

    diff = diff_schemas(schema_a, schema_b)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(diff, indent=2))

    md_path = args.markdown or args.output.with_suffix(".md")
    md_path.write_text(render_markdown(diff))

    s = diff["summary"]
    print(
        f"wrote {args.output}\n"
        f"wrote {md_path}\n"
        f"  {diff['year_a']} → {diff['year_b']}\n"
        f"  {s['year_a_fields']} → {s['year_b_fields']} fields\n"
        f"  unchanged: {s['unchanged']}  added: {s['added']}  removed: {s['removed']}  renamed: {s['possibly_renamed']}"
    )


if __name__ == "__main__":
    main()
