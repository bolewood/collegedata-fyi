#!/usr/bin/env python3
"""Generate the Python↔TypeScript rounds-engine conformance fixture.

Runs the reference engine (data_spike.compose_round) over the versioned
scenario corpus against the committed evidence bundle, and writes the
expected round compositions to a fixture the web test suite replays against
the TypeScript engine. Both engines consume only committed artifacts, so CI
can verify parity without any network or scratch inputs.

Regenerate whenever the policy, ontology, scenarios, or evidence bundle
change:  python3 tools/discovery/build_conformance_fixture.py
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import data_spike as ds  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
BUNDLE = ROOT / "web" / "public" / "discovery" / "evidence-v1.json"
OUT = ROOT / "web" / "src" / "lib" / "discovery" / "__fixtures__" / "rounds-conformance.v1.json"


def main() -> int:
    bundle = json.loads(BUNDLE.read_text())
    pool = bundle["schools"]
    scenarios = json.load(open(ROOT / "data/discovery/scenarios/v1.json"))
    ontology = json.load(open(ROOT / "data/discovery/ontology/v1.json"))

    cases = []
    # Synthetic case: empty concepts = whole interest family (the interests
    # step's "use the whole family" path) — pins the TS/Python agreement on
    # empty-selection semantics that no scenario profile exercises.
    d_all, a_all = ds.edge_sets(ontology, set())
    chosen, slots, diags, n_cand, _ = ds.compose_round(
        pool,
        {"geography": {"preferred_miles": None, "maximum_miles": None,
                       "allow_wildcards": False},
         "preferences": [{"key": "scale.small", "aggregate": 3}]},
        None,
        (d_all, a_all),
    )
    cases.append({
        "scenario_id": "synthetic--whole-family",
        "concepts": [],
        "geography": {"zip": None, "preferred_miles": None,
                      "maximum_miles": None, "allow_wildcards": False},
        "origin": None,
        "aggregates": {"scale.small": 3},
        "expected": {
            "schools": [[c["school_id"], c["role"]] for c in chosen],
            "slots": slots,
            "eligible_candidates": n_cand,
            "relaxation_level": diags.get("relaxation_level"),
        },
    })
    for origin in scenarios["origins"]:
        for profile in scenarios["profiles"]:
            d_cips, a_cips = ds.edge_sets(ontology, set(profile["concepts"]))
            chosen, slots, diags, n_cand, _ = ds.compose_round(
                pool, profile, origin, (d_cips, a_cips)
            )
            cases.append({
                "scenario_id": f"{origin['origin_id']}--{profile['profile_id']}",
                "concepts": profile["concepts"],
                "geography": {
                    "zip": None,
                    "preferred_miles": profile["geography"]["preferred_miles"],
                    "maximum_miles": profile["geography"]["maximum_miles"],
                    "allow_wildcards": profile["geography"]["allow_wildcards"],
                },
                "origin": {"lat": origin["lat"], "lon": origin["lon"]},
                "aggregates": {
                    p["key"]: p["aggregate"] for p in profile["preferences"]
                },
                "expected": {
                    "schools": [[c["school_id"], c["role"]] for c in chosen],
                    "slots": slots,
                    "eligible_candidates": n_cand,
                    "relaxation_level": diags.get("relaxation_level"),
                },
            })

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({
        "fixture_version": "rounds-conformance.v1",
        "bundle_version": bundle["bundle_version"],
        "policy_version": bundle["policy_version"],
        "ontology_version": bundle["ontology_version"],
        "scenario_corpus_version": scenarios["scenario_corpus_version"],
        "cases": cases,
    }, indent=1))
    full = sum(1 for c in cases if len(c["expected"]["schools"]) >= 6)
    print(f"wrote {OUT.relative_to(ROOT)}: {len(cases)} cases, {full} full rounds")
    return 0


if __name__ == "__main__":
    sys.exit(main())
