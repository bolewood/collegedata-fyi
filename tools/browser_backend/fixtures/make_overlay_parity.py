#!/usr/bin/env python3
"""Writes overlay_parity.json, the fixture shared by the Python (overlay_parity_test.py), TypeScript
(web/src/lib/overlay-serving.test.ts) and SQL (run_overlay_sql_fixture.py, by hand) legs of the PRD 038 selector parity
test. Every expectation below is written by hand; none is generated from an implementation.

A case is one document: artifacts, the base artifact id every selector must pick, and variants
{serve: [class names, as the config or the SQL array], values: {question: value}, overlay_artifact_id}.
Cases after "known_divergence" come from the two independent M3 reviews (m3verify, m3review-codex)."""
import json
from pathlib import Path

S = ["numeric", "choice", "checkbox_box"]
DEFAULT = ["checkbox_box", "choice", "numeric", "ocr_numeric"]          # sorted; the default served set


def art(id, doc, kind, producer, ver, created, notes, schema="2025-26"):
    return {"id": id, "document_id": doc, "kind": kind, "producer": producer, "producer_version": ver,
            "schema_version": schema, "created_at": created, "notes": notes}


def v(value, cls=None, lane=None, **kw):
    r = {"value": value}
    if cls:
        r["emission_class"] = cls
    if lane is not None:
        r["lane"] = lane
    r.update(kw)
    return r


def ovl(id, doc, created, values, sha="S", held=False, schema="2025-26", ver="0.7.0", **notes):
    n = {"source_sha256": sha, "values": values, **notes}
    if held != "ABSENT":
        n["held"] = held
    return art(id, doc, "cleaned", "tier2_template_overlay", ver, created, n, schema=schema)


def base(doc, notes=None, schema="2025-26", producer="tier4_docling", id=None):
    n = {"source_sha256": "S", "values": {"Q": v("base"), "K": v("keep")}}
    n.update(notes or {})
    return art(id or f"b-{doc}", doc, "canonical", producer, "0.3.17", "2026-11-01T00:00:00+00:00", n, schema=schema)


cases = []

# ---- the original six --------------------------------------------------------------------------------
d1 = [
    art("t4a", "d1", "canonical", "tier4_docling", "0.6.0", "2026-11-01T00:00:00+00:00",
        {"source_sha256": "sha-A", "values": {"B.101": v("100"), "C.101": v("5"), "C.201": v("x"), "F.1": v("999")}}),
    art("fb1", "d1", "cleaned", "tier4_llm_fallback", "1", "2026-11-02T00:00:00+00:00",
        {"base_artifact_id": "t4a", "values": {"F.1": v("fallback1"), "F.2": v("fallback2")}}),
    art("ova", "d1", "cleaned", "tier2_template_overlay", "0.6.0", "2026-11-05T00:00:00+00:00",
        {"source_sha256": "sha-A", "held": False, "values": {
            "B.101": v("101", "numeric", "text"),
            "C.300": v("7", "ocr_numeric", 2),
            "C.301": v("X", "checkbox_boxless", "text"),
            "C.302": v("X", "checkbox_box", "text"),
            "C.303": v("12", "ocr_numeric", "text", derived_lanes=[2, "text"]),
            "C.304": v("13", "numeric", "text", derived_lanes=[2, "text"]),
            "C.305": v("free words", "free_text", "text"),
            "C.306": v("Yes", "choice", "text")}}),
    art("ovs", "d1", "cleaned", "tier2_template_overlay", "0.5.0", "2026-11-06T00:00:00+00:00",
        {"source_sha256": "sha-OLD", "held": False, "values": {"B.101": v("666", "numeric", "text"), "C.401": v("1", "numeric", "text")}}),
    art("ovh", "d1", "cleaned", "tier2_template_overlay", "0.6.0", "2026-11-07T00:00:00+00:00",
        {"source_sha256": "sha-A", "held": True, "values": {"B.101": v("777", "numeric", "text"), "C.402": v("2", "numeric", "text")}}),
]
base_d1 = {"B.101": "100", "C.101": "5", "C.201": "x", "F.1": "999", "F.2": "fallback2"}
cases.append({"name": "parity_same_tier4_base", "artifacts": d1, "base_artifact_id": "t4a", "variants": [
    {"serve": [], "values": base_d1, "overlay_artifact_id": None},
    {"serve": S, "values": {**base_d1, "B.101": "101", "C.302": "X", "C.306": "Yes"}, "overlay_artifact_id": "ova",
     "sources": {"B.101": "tier2_template_overlay", "C.302": "tier2_template_overlay", "C.306": "tier2_template_overlay",
                 "C.101": "tier4_docling", "F.1": "tier4_docling", "F.2": "tier4_llm_fallback"}},
    {"serve": ["checkbox_boxless", "free_text"], "values": {**base_d1, "C.301": "X", "C.305": "free words"}, "overlay_artifact_id": "ova"},
    {"serve": ["ocr_numeric"], "values": base_d1, "overlay_artifact_id": None, "note": "Lane 2 is never served, even when listed"},
    {"serve": ["bogus", "numeric"], "values": base_d1, "overlay_artifact_id": None, "note": "an unknown class fails the whole set closed"}]})
cases.append({"name": "tier2_base_never_merges", "base_artifact_id": "t2", "artifacts": [
    art("t2", "d2", "canonical", "tier2_acroform", "1.0", "2026-11-01T00:00:00+00:00", {"source_sha256": "sha-B", "values": {"B.101": v("20")}}),
    art("ov2", "d2", "cleaned", "tier2_template_overlay", "0.6.0", "2026-11-05T00:00:00+00:00",
        {"source_sha256": "sha-B", "held": False, "values": {"B.101": v("21", "numeric", "text")}})],
    "variants": [{"serve": S, "values": {"B.101": "20"}, "overlay_artifact_id": None}]})
cases.append({"name": "tier4_base_without_recorded_sha_never_merges", "base_artifact_id": "t4n", "artifacts": [
    art("t4n", "d4", "canonical", "tier4_docling", "0.6.0", "2026-11-01T00:00:00+00:00", {"values": {"B.101": v("40")}}),
    art("ov4", "d4", "cleaned", "tier2_template_overlay", "0.6.0", "2026-11-05T00:00:00+00:00",
        {"source_sha256": "sha-C", "held": False, "values": {"B.101": v("41", "numeric", "text")}})],
    "variants": [{"serve": S, "values": {"B.101": "40"}, "overlay_artifact_id": None}]})
cases.append({"name": "tier4_base_without_schema_version_never_merges", "base_artifact_id": "t4s", "artifacts": [
    art("t4s", "d5", "canonical", "tier4_docling", "0.3.9", "2026-11-01T00:00:00+00:00", {"source_sha256": "sha-F", "values": {"B.101": v("50")}}, schema=None),
    ovl("ov5", "d5", "2026-11-05T00:00:00+00:00", {"B.101": v("51", "numeric", "text")}, sha="sha-F")],
    "variants": [{"serve": S, "values": {"B.101": "50"}, "overlay_artifact_id": None}]})
cases.append({"name": "schema_mismatch_never_merges", "base_artifact_id": "t4m", "artifacts": [
    art("t4m", "d6", "canonical", "tier4_docling", "0.3.17", "2026-11-01T00:00:00+00:00", {"source_sha256": "sha-F", "values": {"B.101": v("60")}}, schema="2024-25"),
    ovl("ov6", "d6", "2026-11-05T00:00:00+00:00", {"B.101": v("51", "numeric", "text")}, sha="sha-F")],
    "variants": [{"serve": S, "values": {"B.101": "60"}, "overlay_artifact_id": None}]})
cases.append({"name": "known_divergence_tier2_older_than_tier4", "base_artifact_id": "t2old", "artifacts": [
    art("t2old", "d3", "canonical", "tier2_acroform", "1.0", "2026-10-01T00:00:00+00:00", {"source_sha256": "sha-D", "values": {"B.101": v("30"), "T.2": v("tier2only")}}),
    art("t4new", "d3", "canonical", "tier4_docling", "0.6.0", "2026-11-01T00:00:00+00:00", {"source_sha256": "sha-E", "values": {"B.101": v("31"), "T.4": v("tier4only")}}),
    art("ov3", "d3", "cleaned", "tier2_template_overlay", "0.6.0", "2026-11-05T00:00:00+00:00",
        {"source_sha256": "sha-E", "held": False, "values": {"B.101": v("32", "numeric", "text")}})],
    "note": "The view and project_browser_data rank tier2_acroform above tier4_docling; fetchExtract takes the newest canonical. Recorded, not fixed (A2).",
    "variants": [{"serve": S, "values": {"B.101": "30", "T.2": "tier2only"}, "overlay_artifact_id": None}],
    "per_selector": {"web": {"base_artifact_id": "t4new", "serve": S, "values": {"B.101": "32", "T.4": "tier4only"}, "overlay_artifact_id": "ov3"}}})

# ---- cases from the two reviews (edge encodings) ------------------------------------------------------
n = [0]


def edge(name, overlays, expect, serve=S, base_art=None, overlay_id=None, note=None, extra=None):
    n[0] += 1
    doc = f"e{n[0]}"
    b = base_art(doc) if base_art else base(doc)
    arts = [b] + [o(doc) for o in overlays]
    values = {"Q": "base", "K": "keep"}
    values.update(expect)
    case = {"name": name, "artifacts": arts, "base_artifact_id": b["id"],
            "variants": [{"serve": serve, "values": values, "overlay_artifact_id": overlay_id}]}
    if note:
        case["note"] = note
    cases.append(case)


T = "2026-11-03T00:00:00+00:00"
rec = lambda value, cls="numeric", lane="text", **kw: v(value, cls, lane, **kw)
edge("two_matching_versions_newest_wins", [
    lambda d: ovl("older-high-version", d, "2026-11-02T00:00:00+00:00", {"Q": rec("older")}, ver="9.9"),
    lambda d: ovl("o", d, T, {"Q": rec("overlay")})], {"Q": "overlay"}, overlay_id="o")
edge("newest_held_older_unheld", [
    lambda d: ovl("older-ok", d, "2026-11-02T00:00:00+00:00", {"Q": rec("older-ok")}),
    lambda d: ovl("newer-held", d, T, {"Q": rec("held")}, held=True)], {"Q": "older-ok"}, overlay_id="older-ok")
for nm, h in (("held_missing", "ABSENT"), ("held_null", None), ("held_string_false", "false"), ("held_zero", 0), ("held_true", True)):
    edge(nm, [lambda d, h=h: ovl("o", d, T, {"Q": rec("overlay")}, held=h)], {})
edge("held_false", [lambda d: ovl("o", d, T, {"Q": rec("overlay")})], {"Q": "overlay"}, overlay_id="o")
edge("unknown_class_fails_the_whole_set_closed", [lambda d: ovl("o", d, T, {"Q": rec("overlay")})], {}, serve=["numeric", "typo"])
edge("blank_overlay_values_never_overwrite_a_populated_base_value", [
    lambda d: ovl("o", d, T, {"Q": rec(""), "K": rec(None), "Z": rec("new"), "W": rec("  ")})], {"Z": "new"}, overlay_id="o")
edge("only_blank_values_merge_nothing", [lambda d: ovl("o", d, T, {"Q": rec("")})], {})
edge("overlay_value_kept_as_written_number", [lambda d: ovl("o", d, T, {"Q": rec(100)})], {"Q": 100}, overlay_id="o")
edge("overlay_value_kept_as_written_string", [lambda d: ovl("o", d, T, {"Q": rec("100")})], {"Q": "100"}, overlay_id="o")
edge("decoded_blank_falls_back_to_value", [lambda d: ovl("o", d, T, {"Q": rec("/Y", "checkbox_box", value_decoded="")})],
     {"Q": "/Y"}, serve=["checkbox_box"], overlay_id="o")
for nm, lane in (("lane_int_2", 2), ("lane_float_2", 2.0), ("lane_string_2", "2"), ("lane_string_2_spaces", " 2 ")):
    edge(nm, [lambda d, lane=lane: ovl("o", d, T, {"Q": rec("overlay", lane=lane)})], {})
for nm, dl in (("derived_int_2", [2, "text"]), ("derived_string_2", ["2"]), ("derived_float_2", [2.0])):
    edge(nm, [lambda d, dl=dl: ovl("o", d, T, {"Q": rec("overlay", derived_lanes=dl)})], {})
edge("lane_text_and_derived_text_are_served", [lambda d: ovl("o", d, T, {"Q": rec("overlay", lane="text", derived_lanes=["text", "checkbox"])})],
     {"Q": "overlay"}, overlay_id="o")
edge("lane_other_numbers_are_served", [lambda d: ovl("o", d, T, {"Q": rec("overlay", lane=3)})], {"Q": "overlay"}, overlay_id="o")
edge("empty_primary_sha_falls_back_to_nested_sha", [lambda d: ovl("o", d, T, {"Q": rec("overlay")})], {"Q": "overlay"},
     base_art=lambda d: base(d, {"source_sha256": "", "source_artifact": {"sha256": "S"}}), overlay_id="o")
edge("both_sha_empty_never_merges", [lambda d: ovl("o", d, T, {"Q": rec("overlay")}, sha="")], {},
     base_art=lambda d: base(d, {"source_sha256": ""}))
edge("both_schema_empty_never_merges", [lambda d: ovl("o", d, T, {"Q": rec("overlay")}, schema="")], {},
     base_art=lambda d: base(d, schema=""))
edge("equal_timestamp_ties_break_by_id_desc", [
    lambda d: ovl("o", d, T, {"Q": rec("tie-o")}), lambda d: ovl("z", d, T, {"Q": rec("tie-z")})], {"Q": "tie-z"}, overlay_id="z")
edge("fractional_timestamps_order", [
    lambda d: ovl("a", d, "2026-11-03T00:00:00.25+00:00", {"Q": rec("a")}),
    lambda d: ovl("b", d, "2026-11-03T00:00:00.5+00:00", {"Q": rec("b")})], {"Q": "b"}, overlay_id="b")
edge("non_object_values_array_serves_nothing", [lambda d: ovl("o", d, T, ["a", "b"])], {})
edge("non_object_values_string_serves_nothing", [lambda d: ovl("o", d, T, "text")], {})
edge("record_class_case_and_missing_class_are_not_served", [
    lambda d: ovl("o", d, T, {"Q": rec("x", "Numeric"), "K": {"value": "y", "lane": "text"}, "Z": rec("z")})], {"Z": "z"}, overlay_id="o")
edge("only_lane2_values_merge_nothing", [lambda d: ovl("o", d, T, {"Q": rec("1", "ocr_numeric", 2), "K": rec("2", "numeric", 2)})], {},
     serve=["numeric", "ocr_numeric"])
edge("sha_comparison_is_case_sensitive", [lambda d: ovl("o", d, T, {"Q": rec("overlay")}, sha="s")], {})
edge("a_fallback_never_stands_in_for_the_overlay", [
    lambda d: art("fbk", d, "cleaned", "tier4_llm_fallback", "1", T, {"base_artifact_id": f"b-{d}", "values": {"F": v("fb")}})],
     {"F": "fb"})

# ---- ocr_numeric: served only when listed AND on a vector page (PRD 038 A15) ------------------------------
SO = S + ["ocr_numeric"]
ocr = lambda value, page_kind="vector", lane=2, **kw: v(value, "ocr_numeric", lane, **({"page_kind": page_kind} if page_kind is not None else {}), **kw)
derived = lambda value, kinds="ABSENT", lane="text", dl=(2, "text"), **kw: v(value, "ocr_numeric", lane, derived_lanes=list(dl), **({} if kinds == "ABSENT" else {"input_page_kinds": kinds}), **kw)
edge("ocr_direct_vector_listed_is_served", [lambda d: ovl("o", d, T, {"Q": ocr("7")})], {"Q": "7"}, serve=SO, overlay_id="o")
edge("ocr_direct_vector_unlisted_is_not_served", [lambda d: ovl("o", d, T, {"Q": ocr("7")})], {}, serve=S)
edge("ocr_alone_listed_serves_the_vector_value", [lambda d: ovl("o", d, T, {"Q": ocr("7")})], {"Q": "7"}, serve=["ocr_numeric"], overlay_id="o")
edge("ocr_direct_raster_is_never_served", [lambda d: ovl("o", d, T, {"Q": ocr("7", "raster")})], {}, serve=SO)
edge("ocr_direct_missing_page_kind_is_not_served", [lambda d: ovl("o", d, T, {"Q": ocr("7", None)})], {}, serve=SO)
edge("ocr_direct_page_kind_is_exact", [lambda d: ovl("o", d, T, {"Q": ocr("7", "Vector")})], {}, serve=SO)
edge("ocr_lane_string_2_vector_is_served", [lambda d: ovl("o", d, T, {"Q": ocr("7", lane="2"), "K": ocr("8", lane=2.0)})], {"Q": "7", "K": "8"}, serve=SO, overlay_id="o")
edge("ocr_mislabelled_numeric_class_with_lane_2_vector_is_not_served", [
    lambda d: ovl("o", d, T, {"Q": v("7", "numeric", 2, page_kind="vector")})], {}, serve=SO)
edge("ocr_class_without_lane_2_evidence_is_not_served", [
    lambda d: ovl("o", d, T, {"Q": v("7", "ocr_numeric", "text", page_kind="vector")})], {}, serve=SO)
edge("ocr_derived_total_all_inputs_vector_is_served", [
    lambda d: ovl("o", d, T, {"Q": derived("7", ["vector"]), "K": derived("8", ["vector", "vector"], dl=["2"])})], {"Q": "7", "K": "8"}, serve=SO, overlay_id="o")
for nm, kinds in (("mixed", ["raster", "vector"]), ("unknown", ["unknown"]), ("empty_list", []), ("not_a_list", "vector"), ("absent", "ABSENT"), ("null", None)):
    edge(f"ocr_derived_total_{nm}_input_kinds_is_not_served", [lambda d, kinds=kinds: ovl("o", d, T, {"Q": derived("7", kinds)})], {}, serve=SO)
edge("ocr_derived_total_unlisted_is_not_served", [lambda d: ovl("o", d, T, {"Q": derived("7", ["vector"])})], {}, serve=S)
edge("ocr_values_do_not_unblock_other_classes", [
    lambda d: ovl("o", d, T, {"Q": ocr("7", "raster"), "Z": rec("z")})], {"Z": "z"}, serve=SO, overlay_id="o")

out = {"description": __doc__.strip().split("\n")[0], "serve_config_cases": [
    {"raw": " numeric , choice ", "classes": ["choice", "numeric"]}, {"raw": "numeric,,choice", "classes": ["choice", "numeric"]},
    {"raw": "NUMERIC,choice", "classes": []}, {"raw": "numeric,typo", "classes": []}, {"raw": "numeric;choice", "classes": []},
    {"raw": "ocr_numeric", "classes": ["ocr_numeric"]},
    # unset, empty or whitespace = the default set; `none` is the only off token (PRD 038 A15)
    {"raw": "", "classes": DEFAULT}, {"raw": None, "classes": DEFAULT}, {"raw": "   ", "classes": DEFAULT},
    {"raw": "none", "classes": []}, {"raw": " NONE ", "classes": []}, {"raw": "none,numeric", "classes": []}, {"raw": "off", "classes": []},
    {"raw": "numeric,choice,checkbox_box,ocr_numeric", "classes": DEFAULT}],
    "default_serve_classes": DEFAULT,
    "cases": cases}
Path(__file__).with_name("overlay_parity.json").write_text(json.dumps(out, indent=1))
print(len(cases), "cases")
