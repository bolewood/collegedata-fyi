"""PRD 038 A6: the shadow report is read-only, seeded and reproducible, and meets its sampling rules."""

import csv
import json
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import shadow_report as sr  # noqa: E402


def make_cohort(tmp_path, docs=30, per_doc=40):
    rng = random.Random(1)
    overlay_dir = tmp_path / "ov"
    overlay_dir.mkdir()
    tier4 = {}
    for d in range(docs):
        sha = f"{d:064x}"
        vector = d % 2 == 0
        values, t4 = {}, {}
        for i in range(per_doc):
            cls = ["numeric", "numeric", "choice", "checkbox_box", "checkbox_boxless", "free_text"][i % 6]
            lane = 2 if (vector and cls == "numeric" and i % 4 == 0) else ("text" if not vector or cls != "numeric" else "text")
            key = f"Q.{i}"
            values[key] = {"value": str(i), "emission_class": "ocr_numeric" if lane == 2 else cls, "lane": lane, "pdf_tag": f"T{i}"}
            if i % 3 == 0:                                   # Tier 4 populates a third of the fields; some disagree
                t4[key] = {"value": str(i if rng.random() > 0.2 else i + 1)}
        lane_counts = {"text": 5, "ocr": 35} if vector else {"text": 40}
        notes = {"source_sha256": sha, "template_year": "2025-26", "values": values, "lane_counts": lane_counts,
                 "page_map": {}, "stage1": {}}
        (overlay_dir / f"{sha}.json").write_text(json.dumps({"source_sha256": sha, "status": "dry_run", "notes": notes}))
        tier4[sha] = {"document_id": f"doc{d}", "school_id": f"s{d}", "canonical_year": "2025-26", "recorded_sha": sha if d % 3 else None,
                      "schema_version": "2024-25" if d == 1 else "2025-26",
                      "canonical_artifacts": [{"id": f"a{d}", "producer": "tier4_docling", "created_at": "2026-11-01"}] + ([{"id": f"b{d}", "producer": "tier2_acroform", "created_at": "2026-10-01"}] if d == 2 else []),
                      "producer_version": "0.3.17", "values": t4, "twin": None}
    (tmp_path / "t4.json").write_text(json.dumps(tier4))
    return overlay_dir


def run(tmp_path, out, extra=()):
    overlay_dir = make_cohort(tmp_path) if not (tmp_path / "ov").exists() else tmp_path / "ov"
    assert sr.main(["--overlay-dir", str(overlay_dir), "--tier4-json", str(tmp_path / "t4.json"), "--out-dir", str(out), *extra]) == 0
    return json.loads((out / "summary.json").read_text()), list(csv.DictReader(open(out / "audit_sample.csv")))


def test_sample_is_reproducible_stratified_and_spans_documents(tmp_path):
    summary, rows = run(tmp_path, tmp_path / "a", ["--per-class", "40", "--min-disagree", "10", "--seed", "7"])
    again, rows2 = run(tmp_path, tmp_path / "b", ["--per-class", "40", "--min-disagree", "10", "--seed", "7"])
    assert rows == [dict(r) for r in rows2]                                          # seeded: identical
    other, rows3 = run(tmp_path, tmp_path / "c", ["--per-class", "40", "--min-disagree", "10", "--seed", "8"])
    assert rows != rows3
    assert summary["audit_sample"]["documents"] >= 20 and summary["audit_sample"]["vector_path_documents"] >= 10
    for cls, n in summary["audit_sample"]["by_class"].items():
        assert n <= 40 + 2
    assert summary["audit_sample"]["tier4_disagreements_by_class"]["numeric"] >= 10        # aimed at disagreements
    assert {r["class"] for r in rows} <= set(sr.AUDIT_CLASSES)
    assert all(r["verdict"] == "" for r in rows)                                       # the audit is done by a person


def test_cohort_numbers_regressions_and_strict_a3_merge(tmp_path):
    summary, _rows = run(tmp_path, tmp_path / "a")
    assert summary["documents"] == 30
    assert summary["regressions_merged_below_tier4_alone"] == 0
    assert summary["documents_whose_tier4_base_records_no_sha"] == 10                    # d % 3 == 0
    assert summary["documents_that_can_merge_under_a3"] == 19            # d%3==0 records no sha; d==1 has the wrong schema
    assert summary["schema_version_pairs"]["tier4=2024-25 overlay=2025-26"] == 1
    assert summary["documents_that_can_merge_by_selector"] == {"sql": 18, "python": 18, "web": 19}     # doc 2 has an older Tier 2: the view picks it
    assert summary["documents_where_selectors_pick_different_bases"] == 1
    assert summary["median_merged_if_every_document_could_merge"]["vector_path"]["documents"] == 15
    assert summary["median_merged_strict_a3_only"]["text_layer"]["documents"] + summary["median_merged_strict_a3_only"]["vector_path"]["documents"] == 19
    assert summary["fillable_twin"]["documents_with_twin"] == 0
    assert "weak-tail" in summary["strata_not_available"][0]


def test_lane_2_values_never_count_toward_the_merged_total(tmp_path):
    notes = {"values": {"A": {"value": "1", "emission_class": "ocr_numeric", "lane": 2}, "B": {"value": "2", "emission_class": "numeric", "lane": "text"}},
             "lane_counts": {"text": 1}}
    row = sr.per_document("s", notes, {"values": {}, "recorded_sha": "s"}, frozenset({"numeric", "ocr_numeric"}))
    assert row["served_values"] == 1 and row["merged_values"] == 1 and row["regression"] is False


def test_the_report_writes_only_under_out_dir(tmp_path):
    before = {p for p in tmp_path.rglob("*") if p.is_file()}
    run(tmp_path, tmp_path / "out")
    new = {p for p in tmp_path.rglob("*") if p.is_file()} - before
    assert new and all((tmp_path / "out") in p.parents or p == tmp_path / "t4.json" or (tmp_path / "ov") in p.parents for p in new)
