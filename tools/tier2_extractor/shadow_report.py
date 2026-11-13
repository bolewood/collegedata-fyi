#!/usr/bin/env python3
"""PRD 038 A6 shadow report: read-only tooling over overlay artifacts. Writes only under --out-dir.

Inputs
  --overlay-dir DIR     `<sha256>.json` records from `overlay_entry.py --pdf-dir ... --out-dir DIR` (a dry run), or
  --overlay-json FILE   the `--json-out` of `overlay_entry.py --document-ids ...` (database mode).
  --tier4-json FILE     {sha256: {document_id, school_id, canonical_year, artifact_id, producer_version,
                        recorded_sha, values: {question: record}, twin: {producer, document_id, values} | null}}.
                        `fetch_tier4.sh` builds it from production with SELECT only.
  --pdf-dir DIR         the PDFs, `<sha256>.pdf`, for the rendered crops.

Outputs (under --out-dir): summary.json, summary.md, per_doc.csv, audit_sample.csv, crops/*.png.

Per document: field counts by class; fields both Tier 4 and the overlay populate and the share that disagree (all
classes, and per class); merged field count (Tier 4 plus the values of the candidate served set) against Tier 4 alone;
whether the document can merge at all under A3's strict sha rule. Cohort: median merged field count for text-layer and
vector-path documents, regression count (must be 0), disagreement against the fillable twin where one exists, and the
audit sample (about --per-class values per class, at least --min-disagree of them Tier 4 disagreements, seeded).
The A10 strata that the artifact does not record (weak-tail Lane 3 scores, specks) are listed as not available.
"""

from __future__ import annotations

import argparse
import csv
import json
import random
import statistics
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Optional

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from browser_backend import overlay_serving as serving  # noqa: E402  (pure Python)

DEFAULT_SERVE = ("numeric", "choice", "checkbox_box")           # A10's SERVE_CLASSES_DEFAULT: the candidate served set
AUDIT_CLASSES = ("numeric", "choice", "checkbox_box", "checkbox_boxless", "free_text")
VECTOR_PATH_TEXT_SHARE = 0.25     # a document with fewer Lane 1 values than this share of its values is "vector-path"


def load_overlay_records(overlay_dir: Optional[Path], overlay_json: Optional[Path]) -> dict[str, dict[str, Any]]:
    """{sha256: notes} for every document with a written overlay."""
    out: dict[str, dict[str, Any]] = {}
    if overlay_dir:
        for path in sorted(overlay_dir.glob("*.json")):
            rec = json.loads(path.read_text())
            if rec.get("status") == "dry_run" and rec.get("notes"):
                out[rec["source_sha256"]] = rec["notes"]
    if overlay_json:
        for rec in json.loads(overlay_json.read_text()):
            if rec.get("notes"):
                out[rec["notes"]["source_sha256"]] = rec["notes"]
    return out


VECTOR_SHAS: Optional[set] = None       # when given (--vector-shas), the authoritative list overrides the heuristic


def is_vector_path(notes: dict[str, Any]) -> bool:
    if VECTOR_SHAS is not None:
        return notes.get("source_sha256") in VECTOR_SHAS
    counts = notes.get("lane_counts") or {}
    total = sum(counts.values()) or 1
    return (counts.get("text", 0) / total) < VECTOR_PATH_TEXT_SHARE


def _populated(values: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in values.items() if serving.normalise_for_compare(v) is not None}


def per_document(sha: str, notes: dict[str, Any], tier4: Optional[dict[str, Any]], serve: frozenset[str]) -> dict[str, Any]:
    values = _populated(notes.get("values") or {})
    by_class = Counter(v.get("emission_class") for v in values.values())
    t4_values = _populated((tier4 or {}).get("values") or {})
    disagree_by_class: Counter = Counter()
    both_by_class: Counter = Counter()
    disagreeing: list[str] = []
    for key, record in values.items():
        if key not in t4_values:
            continue
        cls = record.get("emission_class")
        both_by_class[cls] += 1
        if not serving.values_agree(record, t4_values[key]):
            disagree_by_class[cls] += 1
            disagreeing.append(key)
    both = sum(both_by_class.values())
    served = serving.serve_overlay_values(values, serve)
    merged_keys = set(t4_values) | set(served)
    recorded = (tier4 or {}).get("recorded_sha")
    schema_ok = bool((tier4 or {}).get("schema_version")) and (tier4 or {}).get("schema_version") == notes.get("template_year")
    selectors = selector_bases(tier4)
    return {
        "sha256": sha, "school_id": (tier4 or {}).get("school_id"), "canonical_year": (tier4 or {}).get("canonical_year"),
        "document_id": (tier4 or {}).get("document_id"), "template_year": notes.get("template_year"),
        "vector_path": is_vector_path(notes), "overlay_values": len(values), "by_class": dict(by_class),
        "tier4_values": len(t4_values), "both_populated": both, "disagreeing": len(disagreeing),
        "disagreement_share": round(len(disagreeing) / both, 6) if both else None,
        "both_by_class": dict(both_by_class), "disagree_by_class": dict(disagree_by_class),
        "served_values": len(served), "merged_values": len(merged_keys),
        "regression": len(merged_keys) < len(t4_values),
        "tier4_recorded_sha": bool(recorded), "tier4_schema_version": (tier4 or {}).get("schema_version"), "schema_match": schema_ok,
        "mergeable_under_a3": bool(recorded) and recorded == sha and schema_ok,        # strict sha (A3) and equal schema (A13)
        "selector_bases": selectors,
        "mergeable_by_selector": {k: bool(recorded) and recorded == sha and schema_ok and v == "tier4_docling" for k, v in selectors.items()},
        "held_at_threshold": (len(disagreeing) / both > serving.hold_threshold()) if both else False,
        "disagreeing_fields": disagreeing,
    }


_RANK = {"tier1_xlsx": 1, "tier2_acroform": 2, "tier6_html": 3, "tier4_docling": 4}


def selector_bases(tier4: Optional[dict[str, Any]]) -> dict[str, Optional[str]]:
    """The base producer each selector would pick for the document: the view and the projection rank
    tier1 > tier2 > tier6 > tier4 then recency; the web takes the newest canonical (A2)."""
    arts = [a for a in ((tier4 or {}).get("canonical_artifacts") or []) if a.get("producer") in _RANK]
    if not arts:
        return {"sql": None, "python": None, "web": None}
    newest = sorted(arts, key=lambda a: (str(a.get("created_at")), str(a.get("id"))), reverse=True)
    ranked = sorted(newest, key=lambda a: _RANK[a["producer"]])
    return {"sql": ranked[0]["producer"], "python": ranked[0]["producer"], "web": newest[0]["producer"]}


def twin_stratum(notes: dict[str, Any], tier4: Optional[dict[str, Any]]) -> dict[str, Any]:
    twin = (tier4 or {}).get("twin")
    if not twin:
        return {"has_twin": False}
    values = _populated(notes.get("values") or {})
    twin_values = _populated(twin.get("values") or {})
    both = [k for k in values if k in twin_values]
    bad = [k for k in both if not serving.values_agree(values[k], twin_values[k])]
    return {"has_twin": True, "twin_producer": twin.get("producer"), "both": len(both), "disagree": len(bad), "fields": bad}


def _median(xs: list[int]) -> Optional[float]:
    return statistics.median(xs) if xs else None


def cohort_summary(rows: list[dict[str, Any]], twins: dict[str, dict[str, Any]]) -> dict[str, Any]:
    def medians(subset: list[dict[str, Any]]) -> dict[str, Any]:
        text = [r["merged_values"] for r in subset if not r["vector_path"]]
        vec = [r["merged_values"] for r in subset if r["vector_path"]]
        return {"text_layer": {"documents": len(text), "median_merged": _median(text)},
                "vector_path": {"documents": len(vec), "median_merged": _median(vec)}}

    mergeable = [r for r in rows if r["mergeable_under_a3"]]
    t4_only = [r["tier4_values"] for r in rows]
    both = sum(r["both_populated"] for r in rows)
    bad = sum(r["disagreeing"] for r in rows)
    shares = sorted(r["disagreement_share"] for r in rows if r["disagreement_share"] is not None)
    tw = [t for t in twins.values() if t.get("has_twin")]
    per_class: dict[str, dict[str, Any]] = {}
    for cls in AUDIT_CLASSES + ("ocr_numeric",):
        b = sum(r["both_by_class"].get(cls, 0) for r in rows)
        d = sum(r["disagree_by_class"].get(cls, 0) for r in rows)
        per_class[cls] = {"values": sum(r["by_class"].get(cls, 0) for r in rows), "both_populated": b, "disagreeing": d,
                          "share": round(d / b, 4) if b else None}
    return {
        "documents": len(rows),
        "overlay_values_total": sum(r["overlay_values"] for r in rows),
        "by_class": dict(sum((Counter(r["by_class"]) for r in rows), Counter())),
        "per_class_agreement": per_class,
        "both_populated": both, "disagreeing": bad, "disagreement_share": round(bad / both, 4) if both else None,
        "document_share_distribution": {"p50": shares[len(shares) // 2] if shares else None,
                                         "p90": shares[int(len(shares) * 0.9)] if shares else None,
                                         "max": shares[-1] if shares else None,
                                         "documents_over_threshold": sum(1 for r in rows if r["held_at_threshold"]),
                                         "threshold": serving.hold_threshold()},
        "tier4_alone_median": _median(t4_only),
        "median_merged_if_every_document_could_merge": medians(rows),
        "median_merged_strict_a3_only": medians(mergeable),
        "documents_that_can_merge_under_a3": len(mergeable),
        "documents_that_can_merge_by_selector": {k: sum(1 for r in rows if r["mergeable_by_selector"].get(k)) for k in ("sql", "python", "web")},
        "documents_where_selectors_pick_different_bases": sum(1 for r in rows if len(set(r["selector_bases"].values())) > 1),
        "schema_version_pairs": dict(Counter(f"tier4={r['tier4_schema_version']} overlay={r['template_year']}" for r in rows)),
        "disagreement_by_template_year": {y: {"both_populated": sum(r["both_populated"] for r in rows if r["template_year"] == y),
                                              "disagreeing": sum(r["disagreeing"] for r in rows if r["template_year"] == y)}
                                          for y in sorted({r["template_year"] for r in rows if r["template_year"]})},
        "documents_whose_tier4_base_records_no_sha": sum(1 for r in rows if not r["tier4_recorded_sha"]),
        "regressions_merged_below_tier4_alone": sum(1 for r in rows if r["regression"]),
        "regressions_note": "0 by construction: the supplement merge only adds overlay fields to Tier 4's, so a merged count below Tier 4 alone cannot occur. It is a guard against a merge bug, not evidence about accuracy.",
        "fillable_twin": {"documents_with_twin": len(tw), "values_both": sum(t["both"] for t in tw),
                          "disagreements": sum(t["disagree"] for t in tw)},
        "goal2_targets": {"text_layer": 550, "vector_path": 450},
    }


# ---- audit sample -----------------------------------------------------------------------------------------

def _stratum_tags(sha: str, key: str, record: dict[str, Any], notes: dict[str, Any], row: dict[str, Any],
                  twin: dict[str, Any]) -> list[str]:
    tags = []
    cls = record.get("emission_class")
    if key in row["disagreeing_fields"]:
        tags.append("tier4_disagreement")
    if key in (twin.get("fields") or []):
        tags.append("twin_disagreement")
    if cls == "checkbox_boxless":
        tags.append("boxless")
    if record.get("lane") == 2 or record.get("lane_name") == "ocr":
        tags.append("scan_lane2")
    if row["vector_path"]:
        tags.append("vector_path_doc")
    q = page_of(record, notes)
    shift = ((notes.get("stage1") or {}).get("alignment") or {}).get(str(q)) if q is not None else None
    if shift and (abs(shift.get("dx", 0) or 0) > 0.01 or abs(shift.get("dy", 0) or 0) > 0.01):
        tags.append("shifted_page")
    return tags


def build_audit_sample(
    overlays: dict[str, dict[str, Any]], rows: dict[str, dict[str, Any]], twins: dict[str, dict[str, Any]],
    per_class: int, min_disagree: int, seed: int, classes: tuple[str, ...],
) -> list[dict[str, Any]]:
    rng = random.Random(seed)
    sample: list[dict[str, Any]] = []
    for cls in classes:
        pool = []
        for sha in sorted(overlays):
            notes, row = overlays[sha], rows[sha]
            for key in sorted(notes.get("values") or {}):
                record = notes["values"][key]
                if record.get("emission_class") != cls or serving.normalise_for_compare(record) is None:
                    continue
                pool.append({"sha": sha, "key": key, "record": record, "tags": _stratum_tags(sha, key, record, notes, row, twins[sha])})
        rng.shuffle(pool)
        chosen: list[dict[str, Any]] = []
        taken = set()

        def take(pred, limit):
            for item in pool:
                if len(chosen) >= per_class or limit <= 0:
                    return
                ident = (item["sha"], item["key"])
                if ident not in taken and pred(item):
                    chosen.append(item)
                    taken.add(ident)
                    limit -= 1

        take(lambda i: "tier4_disagreement" in i["tags"], min_disagree)              # aimed at disagreements first
        take(lambda i: "twin_disagreement" in i["tags"], max(10, min_disagree // 5))
        for risk in ("boxless", "scan_lane2", "shifted_page", "vector_path_doc"):                     # then the A10 risk strata
            take(lambda i, risk=risk: risk in i["tags"], max(15, per_class // 6))
        take(lambda i: True, per_class)                                               # the rest: seeded random
        for item in chosen:
            sample.append({**item, "class": cls})
    return sample


def ensure_coverage(sample: list[dict[str, Any]], overlays: dict[str, dict[str, Any]], rows: dict[str, dict[str, Any]],
                    min_docs: int, min_vector: int, seed: int) -> None:
    """Make the sample span at least `min_docs` documents, `min_vector` of them vector-path (adds seeded extras)."""
    rng = random.Random(seed + 1)
    seen = {s["sha"] for s in sample}
    for want_vector, need in ((True, min_vector), (False, min_docs)):
        have = {s["sha"] for s in sample if rows[s["sha"]]["vector_path"]} if want_vector else {s["sha"] for s in sample}
        candidates = [sha for sha in sorted(overlays) if sha not in seen and (rows[sha]["vector_path"] or not want_vector)]
        rng.shuffle(candidates)
        while len(have) < need and candidates:
            sha = candidates.pop()
            keys = [k for k, v in (overlays[sha].get("values") or {}).items() if v.get("emission_class") in AUDIT_CLASSES]
            if not keys:
                continue
            key = rng.choice(sorted(keys))
            record = overlays[sha]["values"][key]
            sample.append({"sha": sha, "key": key, "record": record, "class": record.get("emission_class"), "tags": ["coverage_fill"]})
            seen.add(sha)
            have.add(sha)


def render_crop(sha: str, key: str, record: dict[str, Any], notes: dict[str, Any], pdf_dir: Path, out: Path, above: float = 14) -> Optional[str]:
    """A crop of the page around the widget with its rect in red, using the run's page map and alignment shift."""
    try:
        sys.path.insert(0, str(HERE))
        import pypdfium2 as pdfium
        import template_overlay as to
        from PIL import Image, ImageDraw

        year = notes["template_year"]
        fmap = to.load_maps()[year].fmap["fields"]
        widgets = fmap[record["pdf_tag"]]["widgets"]
        w = widgets[0]
        p = w["template_page"]
        pages = [w2 for w2 in widgets if w2["template_page"] == p]
        q = next((int(k) for k, v in (notes.get("page_map") or {}).items() if v == p), p)
        doc = pdfium.PdfDocument((pdf_dir / f"{sha}.pdf").read_bytes())
        page = doc[q]
        a = ((notes.get("stage1") or {}).get("alignment") or {}).get(str(q), {"dx": 0, "dy": 0})
        dpi = 150
        g = to.page_geometry(page)
        gray = to._render_template_scale(page, g, dpi)
        xs0 = min(x["rect"][0] for x in pages); ys0 = min(x["rect"][1] for x in pages)
        xs1 = max(x["rect"][2] for x in pages); ys1 = max(x["rect"][3] for x in pages)
        r0, r1, c0, c1 = to.template_rect_to_pixels([xs0 - 90, ys0 - above, xs1 + 90, ys1 + 14], a["dx"], a["dy"], dpi)
        im = Image.fromarray(gray[max(r0, 0):r1, max(c0, 0):c1]).convert("RGB")
        draw = ImageDraw.Draw(im)
        for x in pages:
            rr = to.template_rect_to_pixels(x["rect"], a["dx"], a["dy"], dpi)
            draw.rectangle([rr[2] - max(c0, 0) - 2, rr[0] - max(r0, 0) - 2, rr[3] - max(c0, 0) + 1, rr[1] - max(r0, 0) + 1], outline=(255, 0, 0), width=1)
        out.parent.mkdir(parents=True, exist_ok=True)
        im.save(out)
        return str(out)
    except Exception as exc:  # a missing PDF or crop failure is listed, never fatal
        return f"ERROR:{type(exc).__name__}"


_PAGE_CACHE: dict = {}


def page_of(record: dict[str, Any], notes: dict[str, Any]) -> Optional[int]:
    cache_key = (notes.get("template_year"), record.get("pdf_tag"), notes.get("source_sha256"))
    if cache_key not in _PAGE_CACHE:
        _PAGE_CACHE[cache_key] = _page_of(record, notes)
    return _PAGE_CACHE[cache_key]


def _page_of(record: dict[str, Any], notes: dict[str, Any]) -> Optional[int]:
    try:
        sys.path.insert(0, str(HERE))
        import template_overlay as to

        fmap = to.load_maps()[notes["template_year"]].fmap["fields"]
        p = fmap[record["pdf_tag"]]["widgets"][0]["template_page"]
        return next((int(k) for k, v in (notes.get("page_map") or {}).items() if v == p), p)
    except Exception:
        return None


# ---- main -------------------------------------------------------------------------------------------------

def main(argv: Optional[list[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--overlay-dir", type=Path)
    ap.add_argument("--overlay-json", type=Path)
    ap.add_argument("--tier4-json", type=Path, required=True)
    ap.add_argument("--vector-shas", type=Path, default=None, help="JSON list of source shas that are vector-path (overrides the heuristic).")
    ap.add_argument("--pdf-dir", type=Path, default=None, help="Render crops (omit to skip rendering).")
    ap.add_argument("--out-dir", type=Path, required=True)
    ap.add_argument("--seed", type=int, default=38)
    ap.add_argument("--serve-classes", default=",".join(DEFAULT_SERVE), help="Candidate served set for the merged counts.")
    ap.add_argument("--per-class", type=int, default=300)
    ap.add_argument("--min-disagree", type=int, default=100)
    ap.add_argument("--min-docs", type=int, default=20)
    ap.add_argument("--min-vector-docs", type=int, default=10)
    args = ap.parse_args(argv)

    global VECTOR_SHAS
    if args.vector_shas:
        VECTOR_SHAS = set(json.loads(args.vector_shas.read_text()))
    serve = serving.parse_serve_classes(args.serve_classes)
    if not serve:
        ap.error("--serve-classes names an unknown class (or is empty)")
    overlays = load_overlay_records(args.overlay_dir, args.overlay_json)
    tier4 = json.loads(args.tier4_json.read_text())
    args.out_dir.mkdir(parents=True, exist_ok=True)
    rows = {sha: per_document(sha, notes, tier4.get(sha), serve) for sha, notes in overlays.items()}
    twins = {sha: twin_stratum(notes, tier4.get(sha)) for sha, notes in overlays.items()}
    summary = cohort_summary(list(rows.values()), twins)
    summary["candidate_served_set"] = sorted(serve)
    summary["seed"] = args.seed
    summary["strata_not_available"] = ["weak-tail Lane 3 scores (0.04-0.10): the artifact does not store the score",
                                       "specks: no minimum mark size is recorded"]

    sample = build_audit_sample(overlays, rows, twins, args.per_class, args.min_disagree, args.seed, AUDIT_CLASSES)
    ensure_coverage(sample, overlays, rows, args.min_docs, args.min_vector_docs, args.seed)
    sample.sort(key=lambda s: (s["class"], s["sha"], s["key"]))
    out_rows = []
    for i, item in enumerate(sample):
        notes = overlays[item["sha"]]
        crop = None
        if args.pdf_dir and item["record"].get("pdf_tag"):
            crop = render_crop(item["sha"], item["key"], item["record"], notes, args.pdf_dir,
                               args.out_dir / "crops" / f"{i:04d}_{item['sha'][:8]}_{item['record']['pdf_tag']}.png")
        t4 = ((tier4.get(item["sha"]) or {}).get("values") or {}).get(item["key"])
        out_rows.append({
            "n": i, "school_id": (tier4.get(item["sha"]) or {}).get("school_id"), "document_id": (tier4.get(item["sha"]) or {}).get("document_id"),
            "sha256": item["sha"], "page": page_of(item["record"], notes), "tag": item["record"].get("pdf_tag"), "question": item["key"],
            "value": item["record"].get("value_decoded", item["record"].get("value")), "class": item["class"],
            "lane": item["record"].get("lane"), "tier4_value": None if t4 is None else serving._record_text(t4),
            "strata": "|".join(item["tags"]), "crop": crop, "verdict": "", "note": "",
        })
    with open(args.out_dir / "audit_sample.csv", "w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(out_rows[0].keys()) if out_rows else ["n"])
        writer.writeheader()
        writer.writerows(out_rows)
    docs_in_sample = {r["sha256"] for r in out_rows}
    vec_in_sample = {r["sha256"] for r in out_rows if rows[r["sha256"]]["vector_path"]}
    by_class_count = Counter(r["class"] for r in out_rows)
    disagree_in_sample = Counter(r["class"] for r in out_rows if "tier4_disagreement" in r["strata"])
    summary["audit_sample"] = {"rows": len(out_rows), "by_class": dict(by_class_count),
                               "tier4_disagreements_by_class": dict(disagree_in_sample),
                               "documents": len(docs_in_sample), "vector_path_documents": len(vec_in_sample),
                               "shifted_page_values": sum(1 for r in out_rows if "shifted_page" in r["strata"]),
                               "boxless_values": sum(1 for r in out_rows if "boxless" in r["strata"]),
                               "lane2_values": sum(1 for r in out_rows if "scan_lane2" in r["strata"]),
                               "twin_disagreements": sum(1 for r in out_rows if "twin_disagreement" in r["strata"]),
                               "crop_errors": sum(1 for r in out_rows if str(r["crop"]).startswith("ERROR"))}
    (args.out_dir / "summary.json").write_text(json.dumps(summary, indent=1, default=str))
    cols = ["sha256", "school_id", "canonical_year", "template_year", "vector_path", "overlay_values", "tier4_values", "both_populated",
            "disagreeing", "disagreement_share", "served_values", "merged_values", "regression", "tier4_recorded_sha",
            "mergeable_under_a3", "held_at_threshold"]
    with open(args.out_dir / "per_doc.csv", "w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=cols, extrasaction="ignore")
        writer.writeheader()
        for r in sorted(rows.values(), key=lambda r: (str(r["school_id"]), str(r["canonical_year"]))):
            writer.writerow(r)
    print(json.dumps({k: summary[k] for k in ("documents", "overlay_values_total", "regressions_merged_below_tier4_alone",
                                              "documents_that_can_merge_under_a3", "audit_sample")}, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
