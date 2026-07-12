"""Invariant + behavior tests for discovery_policy_v1.

The policy file is executable content (data_spike.py runs it); these tests
pin the guarantees it documents about itself and its agreement with the PRD
and the card library.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import data_spike as ds  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
DISCOVERY = ROOT / "data" / "discovery"

POLICY = json.load(open(DISCOVERY / "policy" / "v1.json"))
LIBRARY = json.load(open(DISCOVERY / "cards" / "v1.json"))

VALID_KINDS = {"numeric_band", "numeric_band_inverted", "count_band",
               "category_set", "offering_any", "checklist_membership"}


def card_keys(status):
    return {k for c in LIBRARY["cards"] if c["evidence_status"] == status
            for k in c["preference_keys"]}


def test_every_evidence_backed_card_key_has_a_matcher():
    evidence_keys = card_keys("data") | card_keys("proxy")
    missing = evidence_keys - set(POLICY["matchers"])
    assert not missing, f"data/proxy card keys without a matcher: {missing}"


def test_unsupported_keys_exactly_cover_reflection_cards():
    reflection = card_keys("reflection_only")
    unsupported = set(POLICY["unsupported_keys"]["keys"])
    assert unsupported == reflection, (
        f"policy unsupported_keys must mirror the library's reflection-only "
        f"keys; only-in-policy={unsupported - reflection}, "
        f"only-in-library={reflection - unsupported}")


def test_no_key_is_both_matched_and_unsupported():
    overlap = set(POLICY["matchers"]) & set(POLICY["unsupported_keys"]["keys"])
    assert not overlap


def test_matcher_specs_well_formed():
    lims = set(LIBRARY["limitations"])
    for key, spec in POLICY["matchers"].items():
        assert spec["kind"] in VALID_KINDS, key
        assert spec["evidence_keys"], key
        assert spec["limitation_id"] in lims, key
        if spec["kind"] in ("numeric_band", "numeric_band_inverted", "count_band"):
            assert "seek" in spec and "opposite" in spec, key
        if spec["kind"] == "category_set":
            assert "seek_set" in spec, key
            assert not (set(spec["seek_set"]) & set(spec.get("opposite_set", []))), key
        if spec["kind"] == "checklist_membership":
            assert spec.get("members"), key


def test_numeric_bands_are_disjoint():
    ops = {"gte": lambda v, t: v >= t, "gt": lambda v, t: v > t,
           "lte": lambda v, t: v <= t, "lt": lambda v, t: v < t}

    def satisfiable_together(a, b):
        # sample a coarse grid around the thresholds
        points = set()
        for band in (a, b):
            for t in band.values():
                points.update({t - 0.01, t, t + 0.01})
        return any(
            all(ops[op](p, t) for op, t in a.items())
            and all(ops[op](p, t) for op, t in b.items())
            for p in points)

    for key, spec in POLICY["matchers"].items():
        if spec["kind"] in ("numeric_band", "numeric_band_inverted", "count_band"):
            assert not satisfiable_together(spec["seek"], spec["opposite"]), \
                f"{key}: seek and opposite bands overlap"


def test_scoring_constants_match_prd():
    sc = POLICY["scoring"]
    assert sc["academic_match"] == {"direct": 6, "adjacent": 3, "stacking": False}
    assert sc["preference_aggregate_clamp"] == [-5, 5]
    assert sc["bucket_weights"] == {"essential": 3, "interesting": 1,
                                    "not_important": 0, "not_for_me": -3}
    assert sc["inside_preferred_radius"] == 2
    assert sc["conflicted_key_contribution"] == 0


def test_round_composition_matches_prd():
    rc = POLICY["round_composition"]
    assert rc["round_size"] == 6 and rc["minimum_size"] == 4
    assert [s["slot"] for s in rc["slots"]] == [
        "anchor", "flexible", "contrast", "affordability", "wildcard", "exploration"]
    assert rc["diversity"]["max_per_state"] == 2
    assert rc["diversity"]["max_per_control"] == 3
    assert rc["relaxation"]["order"] == ["control", "state"]
    assert rc["tie_break"][-1] == "school_id_ascending"


def test_reason_template_limitations_resolve():
    lims = set(LIBRARY["limitations"])
    for tid, tpl in POLICY["reason_templates"].items():
        if tid == "note":
            continue
        assert tpl["limitation_id"] in lims, tid
        assert tpl["text"], tid


def test_engine_reads_policy_not_hardcoded_constants():
    # The reference implementation must source its constants from the file.
    assert ds.POLICY["policy_version"] == "discovery_policy_v1"
    assert ds.MAX_PER_STATE == POLICY["round_composition"]["diversity"]["max_per_state"]
    assert ds.SUPPORTED_KEYS == frozenset(POLICY["matchers"])


def test_pending_source_matchers_return_unknown():
    # Matchers whose evidence source is not loaded must return 0, never -1.
    school = {"scorecard": {"locale": 11}, "enrollment": 20000,
              "direct": {}, "adjacent": {}}
    for key in ("spirit.faith_life", "spirit.big_sports",
                "life.residential_campus", "opp.study_abroad",
                "place.metro_access", "cost.merit_aid"):
        assert ds.matcher(key, school) == 0, key


def test_determinism_same_inputs_identical_rounds():
    pool = [
        {"ipeds_id": str(i), "school_id": f"s{i:02}", "name": "S",
         "state": st, "control": ctrl, "lat": 40.0 + i, "lon": -90.0,
         "enrollment": 3000 + 700 * i, "direct": {"03.0103": 5 + i},
         "adjacent": {}, "scorecard": {"locale": 11 if i % 2 else 32,
                                       "avg_net_price": 10000 + 500 * i}}
        for i, (st, ctrl) in enumerate(
            [("CA", 1), ("NY", 2), ("TX", 1), ("WA", 2), ("GA", 1),
             ("OH", 2), ("CO", 1), ("VT", 2)])
    ]
    profile = {
        "geography": {"preferred_miles": 200, "maximum_miles": None,
                      "allow_wildcards": True},
        "concepts": [],
        "preferences": [{"key": "scale.small", "aggregate": 3}],
    }
    origin = {"lat": 41.0, "lon": -90.0}
    run = lambda: ds.compose_round(pool, profile, origin, ({"03.0103"}, set()))
    c1, s1, d1, n1, w1 = run()
    c2, s2, d2, n2, w2 = run()
    assert [x["school_id"] for x in c1] == [x["school_id"] for x in c2]
    assert [x["role"] for x in c1] == [x["role"] for x in c2]
    assert (s1, dict(d1), n1, w1) == (s2, dict(d2), n2, w2)
