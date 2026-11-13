"""PRD 038 A6/A14: the shadow report is read-only, seeded and reproducible, fails hard on missing cohort documents, and its
labels cannot be read as "servable"."""

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
    shas = []
    for d in range(docs):
        sha = f"{d:064x}"
        shas.append(sha)
        vector = d % 2 == 0
        values, t4 = {}, {}
        for i in range(per_doc):
            cls = ["numeric", "numeric", "choice", "checkbox_box", "checkbox_boxless", "free_text"][i % 6]
            lane2 = vector and cls == "numeric" and i % 4 == 0
            key = f"Q.{i}"
            rec = {"value": str(i), "emission_class": "ocr_numeric" if lane2 else cls, "lane": 2 if lane2 else "text", "pdf_tag": f"T{i}"}
            if lane2:
                rec["page_kind"] = "vector" if d % 4 == 0 else "raster"
                rec["image_coverage"] = 0.0 if d % 4 == 0 else 0.98
            values[key] = rec
            if i % 3 == 0:                                   # Tier 4 populates a third of the fields; some disagree
                t4[key] = {"value": str(i if rng.random() > 0.2 else i + 1)}
        lane_counts = {"text": 5, "ocr": 35} if vector else {"text": 40}
        notes = {"source_sha256": sha, "template_year": "2025-26", "values": values, "lane_counts": lane_counts, "page_map": {}, "stage1": {}}
        (overlay_dir / f"{sha}.json").write_text(json.dumps({"source_sha256": sha, "status": "dry_run", "notes": notes}))
        tier4[sha] = {"document_id": f"doc{d}", "school_id": f"s{d}", "canonical_year": "2025-26", "recorded_sha": sha if d % 3 else None,
                      "schema_version": "2024-25" if d == 1 else "2025-26",
                      "canonical_artifacts": [{"id": f"a{d}", "producer": "tier4_docling", "created_at": "2026-11-01"}]
                                              + ([{"id": f"b{d}", "producer": "tier2_acroform", "created_at": "2026-10-01"}] if d == 2 else []),
                      "producer_version": "0.3.17", "values": t4, "twin": None}
    (tmp_path / "t4.json").write_text(json.dumps(tier4))
    (tmp_path / "cohort.txt").write_text(",".join(shas))
    return overlay_dir


def run(tmp_path, out, extra=()):
    overlay_dir = make_cohort(tmp_path) if not (tmp_path / "ov").exists() else tmp_path / "ov"
    rc = sr.main(["--overlay-dir", str(overlay_dir), "--tier4-json", str(tmp_path / "t4.json"), "--cohort-shas", str(tmp_path / "cohort.txt"),
                  "--out-dir", str(out), *extra])
    assert rc == 0
    return json.loads((out / "summary.json").read_text()), list(csv.DictReader(open(out / "audit_sample.csv")))


def test_sample_is_reproducible_stratified_and_spans_documents(tmp_path):
    summary, rows = run(tmp_path, tmp_path / "a", ["--per-class", "40", "--min-disagree", "10", "--seed", "7"])
    again, rows2 = run(tmp_path, tmp_path / "b", ["--per-class", "40", "--min-disagree", "10", "--seed", "7"])
    assert rows == [dict(r) for r in rows2]
    other, rows3 = run(tmp_path, tmp_path / "c", ["--per-class", "40", "--min-disagree", "10", "--seed", "8"])
    assert rows != rows3
    assert summary["audit_sample"]["documents"] >= 20 and summary["audit_sample"]["vector_path_documents"] >= 10
    for cls, n in summary["audit_sample"]["by_class"].items():
        assert n <= 40 + 2
    assert summary["audit_sample"]["tier4_disagreements_by_class"]["numeric"] >= 10
    assert {r["class"] for r in rows} <= set(sr.AUDIT_CLASSES) | {"ocr_numeric"}
    assert all(r["verdict"] == "" for r in rows)


def test_the_ocr_numeric_stratum_is_vector_pages_only(tmp_path):
    summary, rows = run(tmp_path, tmp_path / "a", ["--per-class", "40", "--min-disagree", "5", "--seed", "7"])
    ocr = [r for r in rows if r["class"] == "ocr_numeric"]
    assert ocr and {r["page_kind"] for r in ocr} == {"vector"}           # raster-page OCR values are never in the stratum
    assert summary["audit_sample"]["by_class"]["ocr_numeric"] == len(ocr)
    assert summary["lane2_values_by_page_kind"]["vector"] > 0 and summary["lane2_values_by_page_kind"]["raster"] > 0


def test_the_report_fails_hard_when_a_cohort_document_is_missing(tmp_path, capsys):
    overlay_dir = make_cohort(tmp_path)
    victim = sorted(overlay_dir.glob("*.json"))[3]
    victim.unlink()                                                      # e.g. an `already_overlaid` rerun that dropped out
    out = tmp_path / "out"
    rc = sr.main(["--overlay-dir", str(overlay_dir), "--tier4-json", str(tmp_path / "t4.json"), "--cohort-shas", str(tmp_path / "cohort.txt"),
                  "--out-dir", str(out)])
    assert rc == 2 and not (out / "summary.json").exists()
    assert "COHORT COVERAGE FAILED" in capsys.readouterr().err
    t4 = json.loads((tmp_path / "t4.json").read_text())
    t4.pop(next(iter(t4)))                                               # and a document missing from the Tier 4 input
    (tmp_path / "t4b.json").write_text(json.dumps(t4))
    victim.write_text(json.dumps({"source_sha256": victim.stem, "status": "dry_run", "notes": {"source_sha256": victim.stem, "template_year": "2025-26", "values": {}}}))
    assert sr.main(["--overlay-dir", str(overlay_dir), "--tier4-json", str(tmp_path / "t4b.json"), "--cohort-shas", str(tmp_path / "cohort.txt"),
                    "--out-dir", str(tmp_path / "out2")]) == 2


def test_labels_cannot_be_read_as_servable_and_holds_are_counted_over_the_candidate_set(tmp_path):
    summary, _rows = run(tmp_path, tmp_path / "a")
    assert summary["documents"] == 30 and summary["regressions_merged_below_tier4_alone"] == 0
    assert "mergeable_under_a3" not in json.dumps(summary) and "median_merged_strict_a3_only" not in json.dumps(summary)
    assert "documents_sha_and_schema_eligible_before_hold" in summary and "does not mean servable" in summary["labels_note"]
    assert summary["documents_sha_and_schema_eligible_before_hold"] == 19        # d%3==0 records no sha; d==1 has the wrong schema
    assert summary["documents_whose_tier4_base_records_no_sha"] == 10
    assert summary["documents_sha_schema_eligible_by_selector"] == {"sql": 18, "python": 18, "web": 19}
    assert summary["documents_where_selectors_pick_different_bases"] == 1
    held = summary["held_documents"]
    assert held["at_10pct"] <= held["at_5pct"] <= 30 and "numeric+choice+checkbox_box" in held["rule"]
    assert summary["hold_candidate_set"] == ["numeric", "choice", "checkbox_box"]
    assert summary["median_merged_with_vector_page_ocr"]["vector_path"]["median_merged"] >= summary["median_merged_if_every_document_could_merge"]["vector_path"]["median_merged"]
    assert summary["fillable_twin"]["documents_with_twin"] == 0 and "weak-tail" in summary["strata_not_available"][0]
    assert "regressions_note" in summary and "by construction" in summary["regressions_note"]


def test_held_counts_use_only_the_served_candidate_classes():
    # all the disagreement is in free_text and ocr_numeric: not held; a numeric disagreement above the threshold: held
    notes = {"template_year": "2025-26", "lane_counts": {"text": 10}, "values": {
        "A": {"value": "1", "emission_class": "free_text"}, "B": {"value": "x", "emission_class": "ocr_numeric", "lane": 2, "page_kind": "vector"},
        "C": {"value": "5", "emission_class": "numeric"}, "D": {"value": "6", "emission_class": "numeric"}}}
    quiet = sr.per_document("s", notes, {"values": {"A": {"value": "2"}, "B": {"value": "y"}, "C": {"value": "5"}, "D": {"value": "6"}}, "recorded_sha": "s",
                                         "schema_version": "2025-26"}, frozenset({"numeric"}))
    assert quiet["held_at_5pct_over_candidate_set"] is False and quiet["hold_candidate_compared"] == 2 and quiet["disagreeing"] == 2
    loud = sr.per_document("s", notes, {"values": {"C": {"value": "9"}, "D": {"value": "6"}}, "recorded_sha": "s", "schema_version": "2025-26"}, frozenset({"numeric"}))
    assert loud["held_at_5pct_over_candidate_set"] is True and loud["held_at_10pct_over_candidate_set"] is True    # 50%


def test_ocr_counts_toward_served_only_when_listed_and_on_a_vector_page():
    notes = {"values": {"A": {"value": "1", "emission_class": "ocr_numeric", "lane": 2, "page_kind": "vector"},
                        "B": {"value": "2", "emission_class": "numeric", "lane": "text"},
                        "C": {"value": "3", "emission_class": "ocr_numeric", "lane": 2, "page_kind": "raster"}}, "lane_counts": {"text": 1}}
    t4 = {"values": {}, "recorded_sha": "s", "schema_version": "x"}
    unlisted = sr.per_document("s", notes, t4, frozenset({"numeric"}))
    assert unlisted["served_values"] == 1 and unlisted["merged_values"] == 1 and unlisted["regression"] is False
    listed = sr.per_document("s", notes, t4, frozenset({"numeric", "ocr_numeric"}))
    assert listed["served_values"] == 2                                                  # the vector value; the raster-page value never
    assert unlisted["merged_values_with_vector_ocr"] == 2 and unlisted["vector_ocr_values"] == 1
    assert unlisted["lane2_by_page_kind"] == {"vector": 1, "raster": 1}


def test_the_report_writes_only_under_out_dir(tmp_path):
    before = {p for p in tmp_path.rglob("*") if p.is_file()}
    run(tmp_path, tmp_path / "out")
    new = {p for p in tmp_path.rglob("*") if p.is_file()} - before
    assert new and all((tmp_path / "out") in p.parents or p.name in ("t4.json", "cohort.txt") or (tmp_path / "ov") in p.parents for p in new)
