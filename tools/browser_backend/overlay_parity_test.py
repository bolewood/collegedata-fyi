"""PRD 038 A2/A13/A14: overlay serving in the projection, against the fixture the web test and the SQL runner also read.

With the served set empty (the default) the overlay code is skipped, overlay artifacts are not even fetched, and the
projection output is identical with or without them. With a set, the overlay merges only onto a Tier 4 base with an
equal recorded sha and schema version, never held, never Lane 2, newest wins, overlay over Tier 4 over fallback.
The disagreement hold is a write-time fact (not evaluated here): selectors only skip `held` that is not exactly false.
"""

import copy
import inspect
import json
import os
import unittest
from pathlib import Path

from tools.browser_backend import overlay_serving as ov
from tools.browser_backend import project_browser_data as pbd
from tools.browser_backend.project_browser_data_test import defs, doc

FIXTURE = json.loads((Path(__file__).parent / "fixtures" / "overlay_parity.json").read_text())
DOC_ID = "00000000-0000-0000-0000-000000000001"


def select(artifacts, serve):
    raw = ",".join(serve) if serve else "none"                                    # an empty resolved set is the `none` off token
    return pbd.select_extraction_result("d", artifacts, overlay_serve_classes=ov.parse_serve_classes(raw))   # as the env does


def plain(selected):
    return {k: (r.get("value") if isinstance(r, dict) else r) for k, r in selected.values.items()}


class ParityFixtureTests(unittest.TestCase):
    def test_every_variant_resolves_as_recorded(self):
        n = 0
        for case in FIXTURE["cases"]:
            for variant in case.get("variants", []):
                with self.subTest(case=case["name"], serve=variant["serve"]):
                    selected = select(case["artifacts"], variant["serve"])
                    self.assertEqual(selected.base_artifact_id, case["base_artifact_id"])
                    self.assertEqual(plain(selected), variant["values"])
                    self.assertEqual(selected.overlay_artifact_id, variant["overlay_artifact_id"])
                    for qn, producer in (variant.get("sources") or {}).items():
                        self.assertEqual(selected.value_sources[qn][0], producer, qn)
                    n += 1
        self.assertGreater(n, 60)

    def test_the_recorded_divergence_python_leg(self):
        case = next(c for c in FIXTURE["cases"] if c["name"].startswith("known_divergence"))
        variant = case["variants"][0]
        selected = select(case["artifacts"], variant["serve"])
        self.assertEqual(selected.base_artifact_id, case["base_artifact_id"])          # Tier 2 outranks Tier 4 here: no merge
        self.assertEqual(plain(selected), variant["values"])
        self.assertIsNone(selected.overlay_artifact_id)

    def test_serve_config_parsing(self):
        for c in FIXTURE["serve_config_cases"]:
            self.assertEqual(ov.parse_serve_classes(c["raw"]), frozenset(c["classes"]), c["raw"])
        self.assertEqual(ov.served_classes({}), ov.DEFAULT_SERVE_CLASSES)
        self.assertEqual(sorted(ov.DEFAULT_SERVE_CLASSES), FIXTURE["default_serve_classes"])
        self.assertEqual(ov.served_classes({"OVERLAY_SERVE_CLASSES": ""}), ov.DEFAULT_SERVE_CLASSES)    # an unset repo variable expands to ""
        self.assertEqual(ov.served_classes({"OVERLAY_SERVE_CLASSES": "none"}), frozenset())

    def test_empty_set_is_byte_identical_with_or_without_overlay_artifacts(self):
        case = FIXTURE["cases"][0]
        with_overlays = case["artifacts"]
        without = [a for a in with_overlays if a["producer"] != ov.OVERLAY_PRODUCER]
        self.assertLess(len(without), len(with_overlays))
        self.assertEqual(select(with_overlays, []), select(without, []))
        none = ov.parse_serve_classes("none")
        self.assertEqual(pbd.select_extraction_result("d", with_overlays, overlay_serve_classes=none),
                         pbd.select_extraction_result("d", without, overlay_serve_classes=none))

    def test_with_the_set_empty_overlay_artifacts_are_not_fetched(self):
        class Q:
            def __init__(self):
                self.calls = []

            def table(self, name):
                self.calls.append(("table", name))
                return self

            def __getattr__(self, name):
                def call(*a):
                    self.calls.append((name,) + a)
                    return self
                return call

            def execute(self):
                return type("R", (), {"data": []})()

        old = os.environ.pop("OVERLAY_SERVE_CLASSES", None)
        try:
            q = Q()
            pbd.fetch_artifacts(q, "d")                                        # the default set serves: overlay artifacts are fetched
            self.assertFalse([c for c in q.calls if c[0] == "neq"])
            os.environ["OVERLAY_SERVE_CLASSES"] = "none"
            q = Q()
            pbd.fetch_artifacts(q, "d")                                        # the rollback lever: not fetched at all
            self.assertIn(("neq", "producer", ov.OVERLAY_PRODUCER), q.calls)
        finally:
            os.environ.pop("OVERLAY_SERVE_CLASSES", None)
            if old is not None:
                os.environ["OVERLAY_SERVE_CLASSES"] = old

    def test_the_projection_passes_the_configured_set_and_never_the_producers_default(self):
        calls = []
        real = ov.serve_overlay_values

        def spy(values, classes):
            calls.append(classes)
            return real(values, classes)

        self.assertIs(inspect.signature(real).parameters["classes"].default, inspect.Parameter.empty)
        ov.serve_overlay_values = spy
        try:
            artifacts = FIXTURE["cases"][0]["artifacts"]
            select(artifacts, [])
            self.assertEqual(calls, [])                                                   # empty set: no overlay code runs
            select(artifacts, ["checkbox_boxless"])
            self.assertEqual(calls, [frozenset({"checkbox_boxless"})])
        finally:
            ov.serve_overlay_values = real
        source = Path(pbd.__file__).read_text()
        self.assertNotIn("serve_values(", source.replace("serve_overlay_values(", ""))
        self.assertNotIn("SERVE_CLASSES_DEFAULT", source)
        self.assertNotIn("import template_overlay", source)
        for name in ("OVERLAY_HOLD_THRESHOLD", "hold_threshold"):
            self.assertNotIn(name, source)                                                # the hold is a write-time fact

    def test_strict_sha_held_and_base_rules(self):
        base = {"producer": "tier4_docling", "schema_version": "2025-26", "notes": {"source_sha256": "S"}}
        good = {"kind": "cleaned", "producer": ov.OVERLAY_PRODUCER, "schema_version": "2025-26", "notes": {"source_sha256": "S", "held": False}}
        self.assertTrue(ov.overlay_matches_base(base, good))
        self.assertFalse(ov.overlay_matches_base(base, {**good, "notes": {"source_sha256": "S", "held": True}}))
        self.assertFalse(ov.overlay_matches_base(base, {**good, "notes": {"source_sha256": "S"}}))        # unmarked = held
        self.assertFalse(ov.overlay_matches_base(base, {**good, "notes": {"source_sha256": "T", "held": False}}))
        self.assertFalse(ov.overlay_matches_base({**base, "notes": {}}, good))                             # base records no sha
        self.assertFalse(ov.overlay_matches_base({**base, "schema_version": None}, good))
        self.assertFalse(ov.overlay_matches_base({**base, "schema_version": "2024-25"}, good))
        self.assertFalse(ov.overlay_matches_base(base, {**good, "schema_version": None}))
        self.assertFalse(ov.overlay_matches_base({**base, "producer": "tier2_acroform"}, good))
        self.assertFalse(ov.overlay_matches_base(base, {**good, "kind": "canonical"}))
        legacy = {**base, "notes": {"source_artifact": {"sha256": "S"}}}
        self.assertTrue(ov.overlay_matches_base(legacy, good))

    def test_newest_matching_overlay_wins_whatever_its_version(self):
        base = {"id": "b", "producer": "tier4_docling", "schema_version": "2025-26", "notes": {"source_sha256": "S"}}
        mk = lambda i, t, v: {"id": i, "kind": "cleaned", "producer": ov.OVERLAY_PRODUCER, "schema_version": "2025-26",
                              "created_at": t, "producer_version": v, "notes": {"source_sha256": "S", "held": False}}
        old_high, new_low = mk("old", "2026-11-02T00:00:00+00:00", "9.9"), mk("new", "2026-11-03T00:00:00+00:00", "0.1")
        self.assertEqual(ov.pick_overlay(base, [old_high, new_low])["id"], "new")
        self.assertEqual(ov.pick_overlay(base, [new_low, old_high])["id"], "new")

    def test_lane_2_evidence_is_never_served_whatever_the_set_says(self):
        values = {
            "a": {"value": "1", "emission_class": "ocr_numeric", "lane": 2},
            "b": {"value": "2", "emission_class": "numeric", "lane": "text", "derived_lanes": [2, "text"]},
            "c": {"value": "3", "emission_class": "numeric", "lane": "text"},
            "d": {"value": "4", "emission_class": "numeric", "lane": "2"},
            "e": {"value": "5", "emission_class": "numeric", "lane": 2.0},
            "f": {"value": "6", "emission_class": "numeric", "lane": "text", "derived_lanes": ["2"]},
        }
        every = frozenset(ov.KNOWN_CLASSES)
        self.assertEqual(set(ov.serve_overlay_values(values, every)), {"c"})        # no page_kind on "a": the ocr rule is not met
        self.assertEqual(ov.serve_overlay_values(values, frozenset()), {})
        self.assertEqual(ov.serve_overlay_values(["not", "an", "object"], every), {})

    def test_the_overlay_identity_is_the_column_and_includes_the_served_class_set(self):
        a = ov.overlay_identity_string("0.7.0", ["numeric", "choice"])
        b = ov.overlay_identity_string("0.7.0", ["numeric"])
        self.assertEqual(a, "0.7.0/choice,numeric")
        self.assertNotEqual(a, b)
        self.assertIsNone(ov.overlay_identity_string(None, ["numeric"]))
        self.assertEqual(ov.overlay_identity_of_row({"overlay_producer_version": a, "producer_version": "0.3.17"}), a)
        self.assertIsNone(ov.overlay_identity_of_row({"producer_version": "0.3.17"}))
        # rows projected under the M3 suffix format are still readable
        self.assertEqual(ov.overlay_identity_of_row({"producer_version": "0.3.17+overlay.0.7.0/numeric"}), "0.7.0/numeric")

    def test_projection_rows_are_identical_with_the_set_empty_and_versioned_when_merged(self):
        artifacts = [{**a, "document_id": DOC_ID} for a in copy.deepcopy(FIXTURE["cases"][0]["artifacts"])]
        base_only = [a for a in artifacts if a["producer"] != ov.OVERLAY_PRODUCER]
        old = os.environ.pop("OVERLAY_SERVE_CLASSES", None)
        try:
            os.environ["OVERLAY_SERVE_CLASSES"] = "none"
            off_a = pbd.build_projection_rows(doc(), artifacts, defs())
            off_b = pbd.build_projection_rows(doc(), base_only, defs())
            self.assertEqual(json.dumps(off_a, sort_keys=True, default=str), json.dumps(off_b, sort_keys=True, default=str))
            self.assertEqual(off_a[1]["producer_version"], "0.6.0")
            self.assertIsNone(off_a[1]["overlay_producer_version"])
            os.environ["OVERLAY_SERVE_CLASSES"] = "numeric,choice,checkbox_box"
            on_fields, on_row = pbd.build_projection_rows(doc(), artifacts, defs())
            self.assertEqual(on_row["producer_version"], "0.6.0")                       # the plain Tier 4 version (A15)
            self.assertEqual(on_row["overlay_producer_version"], "0.6.0/checkbox_box,choice,numeric")
            producers = {r["field_id"]: r["producer"] for r in on_fields}
            self.assertEqual(producers["B.101"], "tier2_template_overlay")
            self.assertEqual(producers["C.101"], "tier4_docling")
        finally:
            os.environ.pop("OVERLAY_SERVE_CLASSES", None)
            if old is not None:
                os.environ["OVERLAY_SERVE_CLASSES"] = old

    def test_the_write_omits_a_null_overlay_column_so_a_database_without_it_still_works(self):
        sent = []
        client = type("C", (), {"rpc": lambda self, name, payload: (sent.append(payload), type("E", (), {"execute": lambda s: None})())[1]})()
        pbd.replace_projection_rows(client, "d", [], {"document_id": "d", "producer_version": "0.3.17", "overlay_producer_version": None})
        self.assertNotIn("overlay_producer_version", sent[0]["p_browser_row"])
        pbd.replace_projection_rows(client, "d", [], {"document_id": "d", "producer_version": "0.3.17", "overlay_producer_version": "0.7.0/numeric"})
        self.assertEqual(sent[1]["p_browser_row"]["overlay_producer_version"], "0.7.0/numeric")
        pbd.replace_projection_rows(client, "d", [], None)
        self.assertIsNone(sent[2]["p_browser_row"])


class ComparatorTests(unittest.TestCase):
    def test_numeric_classes_compare_by_value_only(self):
        self.assertTrue(ov.values_agree({"value": "1,000", "emission_class": "numeric"}, {"value": "1000"}))
        self.assertTrue(ov.values_agree({"value": "$5.00", "emission_class": "numeric"}, {"value": "5"}))
        self.assertFalse(ov.values_agree({"value": "5", "emission_class": "numeric"}, {"value": "6"}))
        # no yes/no/X normalisation for numbers; text that is not a number compares as trimmed text
        self.assertFalse(ov.values_agree({"value": "X", "emission_class": "numeric"}, {"value": "Yes"}))

    def test_checkbox_and_choice_classes_normalise_yes_no_x_only(self):
        for cls in ("checkbox_box", "choice", "checkbox_boxless"):
            self.assertTrue(ov.values_agree({"value": "/Y", "value_decoded": "Yes", "emission_class": cls}, {"value": "X"}), cls)
            self.assertTrue(ov.values_agree({"value": "/N", "value_decoded": "No", "emission_class": cls}, {"value": "No"}), cls)
            self.assertFalse(ov.values_agree({"value": "/N", "value_decoded": "No", "emission_class": cls}, {"value": "Yes"}), cls)
        # a number is not collapsed on these classes
        self.assertFalse(ov.values_agree({"value": "5", "emission_class": "choice"}, {"value": "5.0"}))

    def test_free_text_compares_as_trimmed_text(self):
        self.assertTrue(ov.values_agree({"value": " 1 year ", "emission_class": "free_text"}, {"value": "1 year"}))
        self.assertFalse(ov.values_agree({"value": "X", "emission_class": "free_text"}, {"value": "Yes"}))
        self.assertFalse(ov.values_agree({"value": "1 year", "emission_class": "free_text"}, {"value": "1year"}))
        self.assertFalse(ov.values_agree({"value": "00123", "emission_class": "free_text"}, {"value": "123"}))

    def test_known_spelling_difference_is_not_normalised(self):
        self.assertFalse(ov.values_agree({"value": "/TFER_REQ", "value_decoded": "Required", "emission_class": "checkbox_box"},
                                         {"value": "Required of All"}))

    def test_blank_decoded_falls_back_to_the_raw_value_and_blank_is_none(self):
        self.assertEqual(ov._record_text({"value": "/Y", "value_decoded": ""}), "/Y")
        self.assertIsNone(ov._record_text({"value": " ", "value_decoded": None}))
        self.assertIsNone(ov.normalise_for_compare({"value": "", "emission_class": "numeric"}))

    def test_comparison_facts_are_by_class_with_ids_and_the_blind_spot(self):
        base = {"A": {"value": "1"}, "B": {"value": "x"}, "C": {"value": "7"}, "D": {"value": "keep"}, "E": {"value": "q"}}
        over = {"A": {"value": "1", "emission_class": "numeric"}, "B": {"value": "/Y", "value_decoded": "Yes", "emission_class": "checkbox_box"},
                "C": {"value": "8", "emission_class": "numeric"}, "E": {"value": "", "emission_class": "numeric"}}
        facts = ov.comparison_facts(base, over, tier4_only_class_of=lambda q: {"D": "free_text", "E": "numeric"}.get(q))
        self.assertEqual(facts["by_class"], {"numeric": {"both": 2, "disagree": 1}, "checkbox_box": {"both": 1, "disagree": 0}})
        self.assertEqual(facts["disagreeing"], [{"question": "C", "class": "numeric"}])
        self.assertEqual(facts["tier4_populated_overlay_empty"], {"free_text": 1, "numeric": 1})

    def test_hold_decision_over_a_class_set_at_below_above_and_off(self):
        by_class = {"numeric": {"both": 100, "disagree": 5}, "checkbox_box": {"both": 100, "disagree": 40}, "free_text": {"both": 10, "disagree": 10}}
        at = ov.disagreement_hold(by_class, ["numeric"], 0.05)
        self.assertFalse(at["held"])                                    # exactly at the threshold is not above it
        self.assertTrue(ov.disagreement_hold(by_class, ["numeric"], 0.049)["held"])
        self.assertFalse(ov.disagreement_hold(by_class, ["numeric"], 0.06)["held"])
        wide = ov.disagreement_hold(by_class, ["numeric", "checkbox_box"], 0.05)
        self.assertEqual((wide["compared"], wide["disagree"], wide["held"]), (200, 45, True))
        self.assertFalse(ov.disagreement_hold(by_class, ["numeric", "checkbox_box"], None)["held"])     # `off`
        self.assertFalse(ov.disagreement_hold({}, ["numeric"], 0.05)["held"])                          # nothing compared
        self.assertEqual(ov.parse_hold_threshold("off"), None)
        self.assertEqual(ov.parse_hold_threshold("OFF"), None)
        self.assertIsNone(ov.parse_hold_threshold(None))                 # A15: the disagreement hold is off unless a threshold is given
        self.assertIsNone(ov.parse_hold_threshold(""))
        self.assertEqual(ov.parse_hold_threshold("0.2"), 0.2)
        self.assertIsNone(ov.parse_hold_threshold("junk"))
        self.assertIsNone(ov.parse_hold_threshold("7"))


class ProducerNameConsumerTests(unittest.TestCase):
    def test_the_overlay_is_not_a_base_candidate_or_a_fallback(self):
        self.assertNotIn(ov.OVERLAY_PRODUCER, pbd.BASE_PRODUCER_RANK)
        base = {"id": "b", "producer": "tier4_docling", "schema_version": "2025-26", "producer_version": "1", "notes": {"markdown": "m"}}
        overlay = {"id": "o", "producer": ov.OVERLAY_PRODUCER, "kind": "cleaned", "schema_version": "2025-26",
                   "notes": {"base_artifact_id": "b", "values": {}}}
        self.assertFalse(pbd._fallback_matches_base(base, base["notes"], overlay))
        llm = {**overlay, "producer": pbd.FALLBACK_PRODUCER}
        self.assertTrue(pbd._fallback_matches_base(base, base["notes"], llm))
        self.assertIsNone(pbd.select_extraction_result("d", [{**overlay, "kind": "cleaned"}], overlay_serve_classes=frozenset({"numeric"})))


if __name__ == "__main__":
    unittest.main()
