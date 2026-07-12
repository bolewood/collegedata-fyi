"""Invariant tests for the versioned discovery content artifacts.

These pin the guarantees the artifacts document about themselves (PRD 026):
id uniqueness, cross-artifact reference resolution, deck interleaving, and
exhaustive include/exclude partitioning. A v2 edit that silently breaks a
published guarantee fails here instead of in production.
"""

import json
from pathlib import Path

DISCOVERY = Path(__file__).resolve().parents[2] / "data" / "discovery"


def load(rel):
    return json.load(open(DISCOVERY / rel))


def test_card_ids_unique_and_fields_complete():
    lib = load("cards/v1.json")
    ids = [c["card_id"] for c in lib["cards"]]
    assert len(ids) == len(set(ids))
    required = {"card_id", "version", "group", "domain", "evidence_status",
                "statement", "explanation", "preference_keys", "evidence_keys",
                "limitation_id"}
    for c in lib["cards"]:
        assert required <= set(c), c["card_id"]
        assert c["evidence_status"] in ("data", "proxy", "reflection_only")


def test_card_limitations_resolve():
    lib = load("cards/v1.json")
    lims = set(lib["limitations"])
    for c in lib["cards"]:
        assert c["limitation_id"] in lims, c["card_id"]


def test_reflection_cards_carry_no_evidence_keys():
    lib = load("cards/v1.json")
    for c in lib["cards"]:
        if c["evidence_status"] == "reflection_only":
            assert not c["evidence_keys"], c["card_id"]
        else:
            assert c["evidence_keys"], c["card_id"]


def test_deck_resolves_partitions_and_interleaves():
    cards = {c["card_id"]: c for c in load("cards/v1.json")["cards"]}
    deck = load("decks/opening-v1.json")
    order = deck["display_order"]
    assert len(order) == deck["size"] == len(set(order))
    assert all(cid in cards for cid in order)
    assert set(deck["included"]) == set(order)
    assert set(deck["excluded_to_library"]) == set(cards) - set(order)
    groups = [cards[cid]["group"] for cid in order]
    assert all(a != b for a, b in zip(groups, groups[1:])), \
        "no two consecutive deck cards may share a group"


def test_ontology_edges_resolve():
    ont = load("ontology/v1.json")
    concepts = {c["concept_id"] for c in ont["concepts"]}
    edge_ids = [e["edge_id"] for e in ont["edges"]]
    assert len(edge_ids) == len(set(edge_ids))
    for e in ont["edges"]:
        assert e["from_concept_id"] in concepts, e["edge_id"]
        assert e["relationship"] in ("direct", "adjacent", "exploratory")
        assert e["review_status"] in ("draft", "approved")
        if e["review_status"] == "approved":
            assert e["reviewer"] and e["reviewed_at"], e["edge_id"]


def test_scenario_profiles_reference_known_preference_keys():
    lib_keys = {k for c in load("cards/v1.json")["cards"]
                for k in c["preference_keys"]}
    scen = load("scenarios/v1.json")
    concepts = {c["concept_id"]
                for c in load("ontology/v1.json")["concepts"]}
    for p in scen["profiles"]:
        for pref in p["preferences"]:
            assert pref["key"] in lib_keys, (p["profile_id"], pref["key"])
        for concept in p["concepts"]:
            assert concept in concepts, (p["profile_id"], concept)
