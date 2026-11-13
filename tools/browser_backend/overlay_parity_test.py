"""PRD 038 A2/A13: overlay serving in the projection, against the fixture the web test also reads.

With the served set empty (the default) the overlay code is skipped and the projection output is identical
with or without overlay artifacts. With a set, the overlay merges only onto a Tier 4 base with an equal
recorded source sha, never held, never Lane 2, newest wins, overlay over Tier 4 over fallback.
"""

import copy
import inspect
import json
import unittest
from pathlib import Path

from tools.browser_backend import overlay_serving as ov
from tools.browser_backend import project_browser_data as pbd
from tools.browser_backend.project_browser_data_test import defs, doc

FIXTURE = json.loads((Path(__file__).parent / "fixtures" / "overlay_parity.json").read_text())
DOC_ID = "00000000-0000-0000-0000-000000000001"


def select(artifacts, serve):
    return pbd.select_extraction_result("d", artifacts, overlay_serve_classes=ov.parse_serve_classes(",".join(serve)))   # as the env does


def plain(selected):
    return {k: (r.get("value") if isinstance(r, dict) else r) for k, r in selected.values.items()}


class ParityFixtureTests(unittest.TestCase):
    def test_every_variant_resolves_as_recorded(self):
        for case in FIXTURE["cases"]:
            for variant in case.get("variants", []):
                with self.subTest(case=case["name"], serve=variant["serve"]):
                    selected = select(case["artifacts"], variant["serve"])
                    self.assertEqual(selected.base_artifact_id, case["base_artifact_id"])
                    self.assertEqual(plain(selected), variant["values"])
                    self.assertEqual(selected.overlay_artifact_id, variant["overlay_artifact_id"])
                    self.assertEqual(selected.overlay_producer_version, variant["producer_version_suffix"])
                    for qn, producer in (variant.get("sources") or {}).items():
                        self.assertEqual(selected.value_sources[qn][0], producer, qn)

    def test_the_recorded_divergence_python_leg(self):
        case = next(c for c in FIXTURE["cases"] if c["name"].startswith("known_divergence"))
        expected = case["per_selector"]["python"]
        selected = select(case["artifacts"], ["numeric", "choice", "checkbox_box"])
        self.assertEqual(selected.base_artifact_id, expected["base_artifact_id"])
        self.assertEqual(plain(selected), expected["values"])
        self.assertIsNone(selected.overlay_artifact_id)       # the Tier 2 base outranks Tier 4 here: no merge

    def test_empty_set_is_byte_identical_with_or_without_overlay_artifacts(self):
        case = FIXTURE["cases"][0]
        with_overlays = case["artifacts"]
        without = [a for a in with_overlays if a["producer"] != ov.OVERLAY_PRODUCER]
        self.assertLess(len(without), len(with_overlays))
        self.assertEqual(select(with_overlays, []), select(without, []))
        self.assertEqual(pbd.select_extraction_result("d", with_overlays), pbd.select_extraction_result("d", without))

    def test_env_default_is_empty_and_an_unknown_class_fails_closed(self):
        self.assertEqual(ov.served_classes({}), frozenset())
        self.assertEqual(ov.served_classes({"OVERLAY_SERVE_CLASSES": ""}), frozenset())
        self.assertEqual(ov.served_classes({"OVERLAY_SERVE_CLASSES": "numeric, choice"}), frozenset({"numeric", "choice"}))
        self.assertEqual(ov.served_classes({"OVERLAY_SERVE_CLASSES": "numeric,nope"}), frozenset())

    def test_the_projection_passes_the_configured_set_and_never_the_producers_default(self):
        calls = []
        real = ov.serve_overlay_values

        def spy(values, classes):
            calls.append(classes)
            return real(values, classes)

        sig = inspect.signature(real)
        self.assertIs(sig.parameters["classes"].default, inspect.Parameter.empty)     # no default to fall back on
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

    def test_lane_2_evidence_is_never_served_whatever_the_set_says(self):
        values = {
            "a": {"value": "1", "emission_class": "ocr_numeric", "lane": 2},
            "b": {"value": "2", "emission_class": "numeric", "lane": "text", "derived_lanes": [2, "text"]},
            "c": {"value": "3", "emission_class": "numeric", "lane": "text"},
        }
        every = frozenset(ov.KNOWN_CLASSES)
        self.assertEqual(set(ov.serve_overlay_values(values, every)), {"c"})
        self.assertEqual(ov.serve_overlay_values(values, frozenset()), {})

    def test_strict_sha_held_and_base_rules(self):
        base = {"producer": "tier4_docling", "schema_version": "2025-26", "notes": {"source_sha256": "S"}}
        good = {"kind": "cleaned", "producer": ov.OVERLAY_PRODUCER, "schema_version": "2025-26", "notes": {"source_sha256": "S", "held": False}}
        self.assertTrue(ov.overlay_matches_base(base, good))
        self.assertFalse(ov.overlay_matches_base(base, {**good, "notes": {"source_sha256": "S", "held": True}}))
        self.assertFalse(ov.overlay_matches_base(base, {**good, "notes": {"source_sha256": "S"}}))        # unmarked = held
        self.assertFalse(ov.overlay_matches_base(base, {**good, "notes": {"source_sha256": "T", "held": False}}))
        self.assertFalse(ov.overlay_matches_base({"producer": "tier4_docling", "schema_version": "2025-26", "notes": {}}, good))      # base records no sha
        self.assertFalse(ov.overlay_matches_base({**base, "schema_version": None}, good))                   # no schema version: ids are 2025-26 whatever the template
        self.assertFalse(ov.overlay_matches_base({**base, "schema_version": "2024-25"}, good))              # numbering differs
        self.assertFalse(ov.overlay_matches_base(base, {**good, "schema_version": None}))
        self.assertFalse(ov.overlay_matches_base({**base, "producer": "tier2_acroform"}, good))
        self.assertFalse(ov.overlay_matches_base(base, {**good, "kind": "canonical"}))
        legacy = {"producer": "tier4_docling", "schema_version": "2025-26", "notes": {"source_artifact": {"sha256": "S"}}}
        self.assertTrue(ov.overlay_matches_base(legacy, good))

    def test_disagreement_summary_compares_numbers_by_value(self):
        base = {"A": {"value": "1,000"}, "B": {"value": "$5.00"}, "C": {"value": "x"}, "D": {"value": "7"}}
        over = {"A": {"value": "1000"}, "B": {"value": "5"}, "C": {"value": "X "}, "D": {"value": "8"}, "E": {"value": "1"}}
        got = ov.disagreement_summary(base, over)
        self.assertEqual((got["both_populated"], got["disagreeing"]), (4, 1))
        self.assertEqual(got["disagreeing_fields"], ["D"])

    def test_yes_no_and_ticked_spellings_are_one_value_not_a_disagreement(self):
        # Tier 4 writes a ticked box as "X" and a yes/no pair as "Yes"/"No"; the overlay writes "/Y", "/N", "/X".
        self.assertTrue(ov.values_agree({"value": "/Y", "value_decoded": "Yes"}, {"value": "X"}))
        self.assertTrue(ov.values_agree({"value": "/X"}, {"value": "x"}))
        self.assertTrue(ov.values_agree({"value": "/N", "value_decoded": "No"}, {"value": "No"}))
        self.assertFalse(ov.values_agree({"value": "/N", "value_decoded": "No"}, {"value": "Yes"}))
        self.assertFalse(ov.values_agree({"value": "/Y", "value_decoded": "Yes"}, {"value": "No"}))

    def test_projection_rows_are_identical_with_the_set_empty_and_versioned_when_merged(self):
        artifacts = [
            {**a, "document_id": DOC_ID, "notes": {**a["notes"], "values": {k: v for k, v in a["notes"]["values"].items()}}}
            for a in copy.deepcopy(FIXTURE["cases"][0]["artifacts"])
        ]
        base_only = [a for a in artifacts if a["producer"] != ov.OVERLAY_PRODUCER]
        import os
        old = os.environ.pop("OVERLAY_SERVE_CLASSES", None)
        try:
            off_a = pbd.build_projection_rows(doc(), artifacts, defs())
            off_b = pbd.build_projection_rows(doc(), base_only, defs())
            self.assertEqual(json.dumps(off_a, sort_keys=True, default=str), json.dumps(off_b, sort_keys=True, default=str))
            self.assertEqual(off_a[1]["producer_version"], "0.6.0")
            os.environ["OVERLAY_SERVE_CLASSES"] = "numeric,choice,checkbox_box"
            on_fields, on_row = pbd.build_projection_rows(doc(), artifacts, defs())
            self.assertEqual(on_row["producer_version"], "0.6.0+overlay.0.6.0")
            producers = {r["field_id"]: r["producer"] for r in on_fields}
            self.assertEqual(producers["B.101"], "tier2_template_overlay")
            self.assertEqual(producers["C.101"], "tier4_docling")
        finally:
            os.environ.pop("OVERLAY_SERVE_CLASSES", None)
            if old is not None:
                os.environ["OVERLAY_SERVE_CLASSES"] = old


if __name__ == "__main__":
    unittest.main()


class ProducerNameConsumerTests(unittest.TestCase):
    def test_the_overlay_is_not_a_base_candidate_or_a_fallback(self):
        self.assertNotIn(ov.OVERLAY_PRODUCER, pbd.BASE_PRODUCER_RANK)
        base = {"id": "b", "producer": "tier4_docling", "schema_version": "2025-26", "producer_version": "1", "notes": {"markdown": "m"}}
        overlay = {"id": "o", "producer": ov.OVERLAY_PRODUCER, "kind": "cleaned", "schema_version": "2025-26",
                   "notes": {"base_artifact_id": "b", "values": {}}}
        self.assertFalse(pbd._fallback_matches_base(base, base["notes"], overlay))
        llm = {**overlay, "producer": pbd.FALLBACK_PRODUCER}
        self.assertTrue(pbd._fallback_matches_base(base, base["notes"], llm))
        # with only an overlay artifact the selection has no base at all
        self.assertIsNone(pbd.select_extraction_result("d", [{**overlay, "kind": "cleaned"}], overlay_serve_classes=frozenset({"numeric"})))
