"""Unit tests for the pure audit-logic helpers in data_spike.py.

These are exactly the functions where an analysis script silently produces
wrong gate numbers: distance math, edge-set classification, evidence
matchers, contrast semantics, and diversity relaxation.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import data_spike as ds  # noqa: E402


def mk_school(**over):
    base = {
        "ipeds_id": over.get("ipeds_id", "1"),
        "school_id": over.get("school_id", "s1"),
        "name": "S",
        "state": over.get("state", "CA"),
        "control": over.get("control", 1),
        "lat": over.get("lat", 40.0),
        "lon": over.get("lon", -74.0),
        "enrollment": over.get("enrollment"),
        "direct": over.get("direct", {}),
        "adjacent": over.get("adjacent", {}),
        "scorecard": over.get("scorecard"),
    }
    return base


def test_haversine_known_pair():
    # NYC to LA is ~2,445 miles great-circle.
    d = ds.haversine_miles(40.7128, -74.0060, 34.0522, -118.2437)
    assert abs(d - 2445) < 25
    assert ds.haversine_miles(40.0, -74.0, 40.0, -74.0) == 0


def test_edge_sets_direct_wins_overlap_and_concept_scoping():
    ont = {"edges": [
        {"from_concept_id": "a", "to_cip": "03.0103", "relationship": "direct"},
        {"from_concept_id": "b", "to_cip": "03.0103", "relationship": "adjacent"},
        {"from_concept_id": "b", "to_cip": "44.0501", "relationship": "adjacent"},
        {"from_concept_id": "a", "to_cip": "13.1338", "relationship": "exploratory"},
    ]}
    direct, adjacent = ds.edge_sets(ont)
    assert "03.0103" in direct and "03.0103" not in adjacent
    assert "44.0501" in adjacent
    assert "13.1338" not in direct | adjacent  # exploratory never gates
    d_b, a_b = ds.edge_sets(ont, {"b"})
    assert "03.0103" in a_b and "03.0103" not in d_b


def test_edge_sets_empty_concepts_matches_nothing():
    ont = {"edges": [
        {"from_concept_id": "a", "to_cip": "01.0000", "relationship": "direct"},
    ]}
    assert ds.edge_sets(ont, set()) == (set(), set())


def test_matcher_bands_and_none_passthrough():
    assert ds.matcher("scale.small", mk_school(enrollment=4000)) == 1
    assert ds.matcher("scale.small", mk_school(enrollment=20000)) == -1
    assert ds.matcher("scale.small", mk_school(enrollment=9000)) == 0
    assert ds.matcher("scale.small", mk_school(enrollment=None)) == 0
    assert ds.matcher("unsupported.key", mk_school(enrollment=100)) == 0


def test_locale_matcher_tolerates_string_typed_locale():
    for loc, expected in ((11, 1), ("11", 1), (32, -1), (21, 0), (None, 0)):
        school = mk_school(scorecard={"locale": loc})
        assert ds.matcher("place.big_city", school) == expected, loc


def test_offering_any_never_returns_minus_one(monkeypatch):
    # cds.e1.* sources are pending, so pin the semantics via an injected
    # resolver: truthy offering -> +1; reported-absent or missing -> 0
    # ("absence never means mismatch", policy notes).
    school = mk_school()
    assert ds.matcher("opp.study_abroad", school) == 0  # no resolver yet
    monkeypatch.setitem(ds.FIELD_RESOLVERS, "cds.e1.study_abroad", lambda s: True)
    assert ds.matcher("opp.study_abroad", school) == 1
    monkeypatch.setitem(ds.FIELD_RESOLVERS, "cds.e1.study_abroad", lambda s: False)
    assert ds.matcher("opp.study_abroad", school) == 0


def test_checklist_membership_min_members(monkeypatch):
    # life.arts_scene requires >= 2 of its checklist members.
    school = mk_school()
    cases = [
        (["theater", "dance"], 1),
        (["theater"], 0),
        ([], 0),
        ("theater", 0),  # non-list evidence never counts
    ]
    for activities, expected in cases:
        monkeypatch.setitem(
            ds.FIELD_RESOLVERS, "cds.f1.activities", lambda s, a=activities: a)
        assert ds.matcher("life.arts_scene", school) == expected, activities
    # life.club_sports needs only one member.
    monkeypatch.setitem(
        ds.FIELD_RESOLVERS, "cds.f1.activities", lambda s: ["club_sports"])
    assert ds.matcher("life.club_sports", school) == 1


def test_numeric_max_aggregation_across_evidence_keys(monkeypatch):
    # life.greek_scene takes max(fraternity, sorority) share.
    school = mk_school()
    monkeypatch.setitem(ds.FIELD_RESOLVERS, "cds.f1.pct_fraternity", lambda s: 3)
    monkeypatch.setitem(ds.FIELD_RESOLVERS, "cds.f1.pct_sorority", lambda s: 25)
    assert ds.matcher("life.greek_scene", school) == 1  # max 25 >= 20
    monkeypatch.setitem(ds.FIELD_RESOLVERS, "cds.f1.pct_sorority", lambda s: 4)
    assert ds.matcher("life.greek_scene", school) == -1  # max 4 <= 5
    monkeypatch.setitem(ds.FIELD_RESOLVERS, "cds.f1.pct_sorority", lambda s: None)
    monkeypatch.setitem(ds.FIELD_RESOLVERS, "cds.f1.pct_fraternity", lambda s: 10)
    assert ds.matcher("life.greek_scene", school) == 0  # neutral band


def test_evidence_priority_first_non_null_wins(monkeypatch):
    # out.retention lists cds.b22.retention before the scorecard fallback:
    # school-authored CDS must win when both exist.
    scorecard_only = mk_school(scorecard={"retention_rate_ft": 0.9})
    assert ds.matcher("out.retention", scorecard_only) == 1
    monkeypatch.setitem(ds.FIELD_RESOLVERS, "cds.b22.retention", lambda s: 0.5)
    assert ds.matcher("out.retention", scorecard_only) == -1  # CDS 0.5 < 0.7


def test_strict_lt_opposite_boundary():
    # out.retention's opposite band uses lt 0.7 — exactly 0.7 is neutral.
    for rate, expected in ((0.85, 1), (0.7, 0), (0.699, -1)):
        school = mk_school(scorecard={"retention_rate_ft": rate})
        assert ds.matcher("out.retention", school) == expected, rate


def test_count_band_zero_related_cips_is_unknown():
    # academic.breadth: 0 related CIPs resolves to None (unknown, never -1);
    # 1 is the defined opposite; a mid count sits in the neutral band.
    cases = [
        ({"direct": {f"{i:02}.0101": 1 for i in range(1, 6)}}, 1),
        ({"direct": {"03.0103": 1}}, -1),
        ({"direct": {"03.0103": 1}, "adjacent": {"44.0501": 1, "01.0000": 1}}, 0),
        ({}, 0),
    ]
    for over, expected in cases:
        assert ds.matcher("academic.breadth", mk_school(**over)) == expected, over


def test_contrast_truth_table():
    school = mk_school(enrollment=4000)  # scale.small -> +1, scale.large -> -1
    # exactly one interesting mismatch (seek large, school is small)
    assert ds.mismatches_exactly_one_interesting(
        school, [{"key": "scale.large", "aggregate": 1}])
    # aggregate 2 counts as interesting, not silently ignored
    assert ds.mismatches_exactly_one_interesting(
        school, [{"key": "scale.large", "aggregate": 2}])
    # essential mismatch blocks
    assert not ds.mismatches_exactly_one_interesting(
        school, [{"key": "scale.large", "aggregate": 3}])
    # zero mismatches is not "exactly one"
    assert not ds.mismatches_exactly_one_interesting(
        school, [{"key": "scale.small", "aggregate": 1}])
    # unsupported keys are ignored entirely
    assert not ds.mismatches_exactly_one_interesting(
        school, [{"key": "life.residential_campus", "aggregate": 1}])


def test_reason_resolution_rejects_unbacked_reasons():
    school = mk_school(direct={"03.0103": 12}, enrollment=4000)
    assert ds.reason_resolves(
        ("academic_direct", "program.recent_awards_direct"),
        school, {"03.0103"}, set())
    # direct claim without qualifying awards fails
    assert not ds.reason_resolves(
        ("academic_direct", "program.recent_awards_direct"),
        mk_school(direct={}), {"03.0103"}, set())
    # match reason must have a live matcher signal
    assert ds.reason_resolves(("scale.small", "match:scale.small"),
                              school, set(), set())
    assert not ds.reason_resolves(("scale.small", "match:scale.small"),
                                  mk_school(enrollment=None), set(), set())
    assert not ds.reason_resolves(("bogus", "match:other"), school, set(), set())


def test_relaxation_fills_to_four_and_records_level():
    # 5 same-state public candidates; caps allow only 2 -> relaxation needed.
    pool = [mk_school(ipeds_id=str(i), school_id=f"s{i}",
                      direct={"03.0103": 10}, enrollment=4000)
            for i in range(5)]
    profile = {
        "geography": {"preferred_miles": None, "maximum_miles": None,
                      "allow_wildcards": False},
        "preferences": [],
    }
    chosen, slots, diags, n_cand, _ = ds.compose_round(
        pool, profile, None, ({"03.0103"}, set()))
    assert n_cand == 5
    assert len(chosen) >= 4
    assert diags.get("relaxation_level") in (1, 2)
    relaxed = [c for c in chosen if c["role"] == "additional_exploration_relaxed"]
    assert relaxed, "relaxation must be attributed to relaxed roles"


def test_no_relaxation_recorded_when_pool_is_just_small():
    pool = [mk_school(ipeds_id=str(i), school_id=f"s{i}", state=st,
                      control=ctrl, direct={"03.0103": 10}, enrollment=4000)
            for i, (st, ctrl) in enumerate([("CA", 1), ("NY", 2), ("TX", 1)])]
    profile = {
        "geography": {"preferred_miles": None, "maximum_miles": None,
                      "allow_wildcards": False},
        "preferences": [],
    }
    chosen, slots, diags, n_cand, _ = ds.compose_round(
        pool, profile, None, ({"03.0103"}, set()))
    assert len(chosen) == 3
    assert "relaxation_level" not in diags, \
        "scarcity must not be misattributed to diversity relaxation"
