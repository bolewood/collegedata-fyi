#!/usr/bin/env python3
"""PRD 026 Milestone 0 data spike.

Measures recent-award evidence coverage for the environment/climate interest
family across the in-scope institution directory, audits identity joins and
geography completeness, then simulates discovery rounds against the versioned
scenario corpus and evaluates the numeric feasibility gate.

Inputs (fetch first — see docs/plans/prd-026-data-spike-findings.md):
  scratch/discovery-spike/C2024_a.csv        IPEDS completions, 2023-24 awards
  scratch/discovery-spike/directory.json      institution_directory dump
  scratch/discovery-spike/scorecard.json      scorecard_summary dump
  data/discovery/ontology/v1-draft.json       interest-family edges
  data/discovery/scenarios/v1.json            20 scenario fixtures

Outputs:
  scratch/discovery-spike/audit.json          full machine-readable audit
  stdout                                       gate summary

Prototype-policy notes (documented deviations, all spike-only):
  - Evidence matchers cover directory/scorecard-backed keys only; CDS-backed
    keys (residential_campus, small_discussion, greek_scene) and geodata keys
    (outdoors_access) are unsupported and contribute zero, exercising the
    supported-preference rule.
  - Origins are coordinates, not ZIPs (centroid source still unselected).
  - Completions use MAJORNUM=1 (first majors) and AWLEVEL=05 (bachelor's).
"""

import csv
import json
import math
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SPIKE = ROOT / "scratch" / "discovery-spike"

BACHELOR_AWLEVEL = "5"
FIRST_MAJOR = "1"

# Scorecard locale codes: 11-13 city, 21-23 suburb, 31-33 town, 41-43 rural.
CITY = {11, 12, 13}
TOWNISH = {31, 32, 33, 41, 42, 43}
BIG_CITY = {11, 12}


def haversine_miles(lat1, lon1, lat2, lon2):
    r = 3958.8
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def load_inputs():
    directory = json.load(open(SPIKE / "directory.json"))
    scorecard = {r["ipeds_id"]: r for r in json.load(open(SPIKE / "scorecard.json"))}
    ontology = json.load(open(ROOT / "data/discovery/ontology/v1-draft.json"))
    scenarios = json.load(open(ROOT / "data/discovery/scenarios/v1.json"))
    return directory, scorecard, ontology, scenarios


def load_completions(cip_universe):
    """UNITID -> {cip: total bachelor's first-major awards}, plus all-CIP
    bachelor counts per school for breadth measures."""
    by_school = defaultdict(dict)
    breadth = Counter()
    with open(SPIKE / "C2024_a.csv", newline="", encoding="utf-8-sig", errors="replace") as fh:
        for row in csv.DictReader(fh):
            if row["MAJORNUM"].strip() != FIRST_MAJOR:
                continue
            if row["AWLEVEL"].strip() != BACHELOR_AWLEVEL:
                continue
            total = int(row["CTOTALT"] or 0)
            if total <= 0:
                continue
            cip = row["CIPCODE"].strip().strip('"')
            unitid = row["UNITID"].strip()
            if cip == "99":  # grand-total rollup rows
                continue
            breadth[unitid] += 1
            if cip in cip_universe:
                by_school[unitid][cip] = by_school[unitid].get(cip, 0) + total
    return by_school, breadth


def edge_sets(ontology, concepts=None):
    direct, adjacent = set(), set()
    for e in ontology["edges"]:
        if concepts and e["from_concept_id"] not in concepts:
            continue
        if e["relationship"] == "direct":
            direct.add(e["to_cip"])
        elif e["relationship"] == "adjacent":
            adjacent.add(e["to_cip"])
    return direct, adjacent - direct


def matcher(key, school):
    """Prototype evidence matchers -> -1 | 0 | +1 (0 = unknown/unsupported)."""
    sc = school["scorecard"] or {}
    enr = school["enrollment"]
    loc = sc.get("locale")
    if key == "scale.small":
        if enr is None:
            return 0
        return 1 if enr <= 5000 else (-1 if enr >= 15000 else 0)
    if key == "scale.large":
        if enr is None:
            return 0
        return 1 if enr >= 15000 else (-1 if enr <= 5000 else 0)
    if key == "place.big_city":
        if loc is None:
            return 0
        return 1 if loc in BIG_CITY else (-1 if loc in TOWNISH else 0)
    if key == "place.quiet_setting":
        if loc is None:
            return 0
        return 1 if loc in TOWNISH else (-1 if loc in BIG_CITY else 0)
    if key == "cost.need_aid_strength":
        np = sc.get("net_price_0_30k")
        if np is None:
            return 0
        return 1 if np < 15000 else (-1 if np > 25000 else 0)
    if key == "cost.low_debt":
        d = sc.get("median_debt_completers")
        if d is None:
            return 0
        return 1 if d < 20000 else (-1 if d > 27000 else 0)
    if key == "out.retention":
        r = sc.get("retention_rate_ft")
        if r is None:
            return 0
        return 1 if r >= 0.85 else (-1 if r < 0.70 else 0)
    if key == "out.four_year_grad":
        g = sc.get("graduation_rate_4yr")
        if g is None:
            return 0
        return 1 if g >= 0.60 else (-1 if g < 0.35 else 0)
    return 0  # unsupported in the spike


SUPPORTED_KEYS = {
    "scale.small", "scale.large", "place.big_city", "place.quiet_setting",
    "cost.need_aid_strength", "cost.low_debt", "out.retention", "out.four_year_grad",
}


def build_pool(directory, scorecard, awards, family_direct, family_adjacent):
    """Eligibility stages 1+3 for the family (no geography)."""
    pool, exclusions = [], Counter()
    seen_unitids = Counter(d["ipeds_id"] for d in directory if d["ipeds_id"])
    for d in directory:
        uid = d["ipeds_id"]
        if not uid:
            exclusions["no_ipeds_id"] += 1
            continue
        if seen_unitids[uid] > 1:
            exclusions["ambiguous_ipeds_join"] += 1
            continue
        if not d.get("in_scope"):
            exclusions["out_of_scope"] += 1
            continue
        if not d.get("currently_operating"):
            exclusions["not_operating"] += 1
            continue
        if d.get("control") not in (1, 2):
            exclusions["control"] += 1
            continue
        if (d.get("predominant_degree") or 0) < 3:
            exclusions["not_bachelors_predominant"] += 1
            continue
        cips = awards.get(uid, {})
        direct_hits = {c: n for c, n in cips.items() if c in family_direct}
        adjacent_hits = {c: n for c, n in cips.items() if c in family_adjacent}
        if not direct_hits and not adjacent_hits:
            exclusions["no_recent_award_evidence"] += 1
            continue
        pool.append({
            "ipeds_id": uid,
            "school_id": d["school_id"],
            "name": d["school_name"],
            "state": d["state"],
            "control": d["control"],
            "lat": d.get("latitude"),
            "lon": d.get("longitude"),
            "enrollment": d.get("undergraduate_enrollment"),
            "direct": direct_hits,
            "adjacent": adjacent_hits,
            "scorecard": scorecard.get(uid),
        })
    return pool, exclusions


def relevance(school, prefs, direct_cips, adjacent_cips, in_preferred):
    score = 0
    reasons = []
    if any(c in direct_cips for c in school["direct"]):
        score += 6
        reasons.append(("academic_direct", "program.recent_awards_direct"))
    elif any(c in adjacent_cips for c in school["adjacent"]) or any(
        c in adjacent_cips for c in school["direct"]
    ):
        score += 3
        reasons.append(("academic_adjacent", "program.recent_awards_adjacent"))
    for p in prefs:
        key, agg = p["key"], p["aggregate"]
        if key not in SUPPORTED_KEYS:
            continue
        m = matcher(key, school)
        if m != 0:
            score += agg * m
            if agg * m > 0:
                reasons.append((key, f"match:{key}"))
    if in_preferred:
        score += 2
    return score, reasons


def tie_key(school):
    return (
        -len(school["direct"]),
        -(len([k for k in SUPPORTED_KEYS if matcher(k, school) != 0])),
        school["school_id"] or "",
    )


def compose_round(pool, profile, origin, family_edges_by_concept):
    """PRD 026 §7-8 prototype: eligibility geo stage, relevance, slots."""
    direct_cips, adjacent_cips = family_edges_by_concept
    geo = profile["geography"]
    prefs = profile["preferences"]
    max_mi, pref_mi = geo["maximum_miles"], geo["preferred_miles"]
    use_geo = origin is not None and (max_mi or pref_mi)

    candidates, diagnostics = [], Counter()
    for s in pool:
        if not any(c in direct_cips for c in s["direct"]) and not any(
            c in adjacent_cips for c in list(s["direct"]) + list(s["adjacent"])
        ):
            diagnostics["outside_selected_concepts"] += 1
            continue
        dist = None
        if use_geo:
            if s["lat"] is None or s["lon"] is None:
                if max_mi:
                    diagnostics["missing_coordinates_under_hard_radius"] += 1
                    continue
            else:
                dist = haversine_miles(origin["lat"], origin["lon"], s["lat"], s["lon"])
                if max_mi and dist > max_mi:
                    diagnostics["beyond_maximum"] += 1
                    continue
        in_pref = bool(pref_mi and dist is not None and dist <= pref_mi)
        score, reasons = relevance(s, prefs, direct_cips, adjacent_cips, in_pref)
        candidates.append({**s, "distance": dist, "score": score,
                           "reasons": reasons, "in_preferred": in_pref})

    candidates.sort(key=lambda s: (-s["score"], *tie_key(s)))

    chosen, state_count, control_count = [], Counter(), Counter()

    def diversity_ok(s):
        return state_count[s["state"]] < 2 and control_count[s["control"]] < 3

    def take(pred, role):
        for s in candidates:
            if any(c["ipeds_id"] == s["ipeds_id"] for c in chosen):
                continue
            if not pred(s):
                continue
            if not diversity_ok(s):
                diagnostics[f"diversity_rejected:{role}"] += 1
                continue
            chosen.append({**s, "role": role})
            state_count[s["state"]] += 1
            control_count[s["control"]] += 1
            return True
        return False

    is_direct = lambda s: any(c in direct_cips for c in s["direct"])

    slots_filled = {}
    slots_filled["anchor"] = take(is_direct, "anchor")
    slots_filled["flexible"] = take_flexible(candidates, chosen, direct_cips,
                                             state_count, control_count, diagnostics)
    slots_filled["contrast"] = take(
        lambda s: mismatches_exactly_one_interesting(s, prefs), "contrast")
    slots_filled["affordability"] = take_affordability(
        candidates, chosen, state_count, control_count, diagnostics)
    slots_filled["wildcard"] = (
        take(lambda s: geo["allow_wildcards"] and pref_mi and s["distance"] is not None
             and s["distance"] > pref_mi, "wildcard")
        if geo["allow_wildcards"] and pref_mi else False)
    slots_filled["exploration"] = take(lambda s: True, "exploration")
    while len(chosen) < 6 and take(lambda s: True, "additional_exploration"):
        pass

    # PRD 026 §8: if diversity caps prevent a four-school minimum, relax
    # control type first, then state, recording the relaxation.
    if len(chosen) < 4:
        for level, (state_cap, control_cap) in enumerate(
            [(2, None), (None, None)], start=1
        ):
            diagnostics["relaxation_level"] = level
            for s in candidates:
                if len(chosen) >= 4:
                    break
                if any(c["ipeds_id"] == s["ipeds_id"] for c in chosen):
                    continue
                if state_cap is not None and state_count[s["state"]] >= state_cap:
                    continue
                chosen.append({**s, "role": "additional_exploration_relaxed"})
                state_count[s["state"]] += 1
                control_count[s["control"]] += 1
            if len(chosen) >= 4:
                break

    return chosen, slots_filled, diagnostics, len(candidates)


def take_flexible(candidates, chosen, direct_cips, state_count, control_count, diagnostics):
    best = None
    for s in candidates:
        if any(c["ipeds_id"] == s["ipeds_id"] for c in chosen):
            continue
        if not any(c in direct_cips for c in s["direct"]):
            continue
        if state_count[s["state"]] >= 2 or control_count[s["control"]] >= 3:
            diagnostics["diversity_rejected:flexible"] += 1
            continue
        related = len(s["direct"]) + len(s["adjacent"])
        if best is None or related > best[0]:
            best = (related, s)
    if best:
        s = best[1]
        chosen.append({**s, "role": "flexible"})
        state_count[s["state"]] += 1
        control_count[s["control"]] += 1
        return True
    return False


def take_affordability(candidates, chosen, state_count, control_count, diagnostics):
    best = None
    for s in candidates:
        if any(c["ipeds_id"] == s["ipeds_id"] for c in chosen):
            continue
        np = (s["scorecard"] or {}).get("avg_net_price")
        if np is None:
            continue
        if state_count[s["state"]] >= 2 or control_count[s["control"]] >= 3:
            diagnostics["diversity_rejected:affordability"] += 1
            continue
        if best is None or np < best[0]:
            best = (np, s)
    if best:
        s = best[1]
        chosen.append({**s, "role": "affordability"})
        state_count[s["state"]] += 1
        control_count[s["control"]] += 1
        return True
    return False


def mismatches_exactly_one_interesting(school, prefs):
    mismatched_interesting = 0
    for p in prefs:
        if p["key"] not in SUPPORTED_KEYS:
            continue
        m = matcher(p["key"], school)
        agg = p["aggregate"]
        if agg >= 3 or agg <= -3:  # essential seek/avoid must not mismatch
            if (agg > 0 and m == -1) or (agg < 0 and m == 1):
                return False
        elif abs(agg) == 1:
            if (agg > 0 and m == -1) or (agg < 0 and m == 1):
                mismatched_interesting += 1
    return mismatched_interesting == 1


def main():
    directory, scorecard, ontology, scenarios = load_inputs()
    family_direct, family_adjacent = edge_sets(ontology)
    cip_universe = family_direct | family_adjacent
    awards, breadth = load_completions(cip_universe)

    pool, exclusions = build_pool(directory, scorecard, awards,
                                  family_direct, family_adjacent)

    direct_pool = [s for s in pool if s["direct"]]
    adjacent_only = [s for s in pool if not s["direct"]]
    states = sorted({s["state"] for s in pool if s["state"]})
    controls = Counter(s["control"] for s in pool)
    geo_missing = [s["school_id"] for s in pool if s["lat"] is None or s["lon"] is None]
    outcomes_available = sum(
        1 for s in pool
        if s["scorecard"] and s["scorecard"].get("graduation_rate_6yr") is not None)

    # identity-join audit against the full completions file
    directory_ids = {d["ipeds_id"] for d in directory if d["ipeds_id"]}
    family_unitids = set(awards)
    unmatched = family_unitids - directory_ids

    # scenario simulation
    scenario_results = []
    for origin in scenarios["origins"]:
        for profile in scenarios["profiles"]:
            concepts = set(profile["concepts"])
            d_cips, a_cips = edge_sets(ontology, concepts)
            chosen, slots, diags, n_cand = compose_round(
                pool, profile, origin, (d_cips, a_cips))
            reasons_valid = all(s["reasons"] for s in chosen)
            scenario_results.append({
                "scenario_id": f"{origin['origin_id']}--{profile['profile_id']}",
                "eligible_candidates": n_cand,
                "round_size": len(chosen),
                "slots": slots,
                "roles": [s["role"] for s in chosen],
                "schools": [
                    {"school_id": s["school_id"], "role": s["role"],
                     "score": s["score"],
                     "distance": round(s["distance"], 1) if s["distance"] is not None else None}
                    for s in chosen],
                "all_reasons_resolve": reasons_valid,
                "diagnostics": dict(diags),
            })

    # gate evaluation
    n_pool, n_direct, n_adj = len(pool), len(direct_pool), len(adjacent_only)
    rounds4 = sum(1 for r in scenario_results if r["round_size"] >= 4)
    rounds6 = sum(1 for r in scenario_results if r["round_size"] >= 6)
    n_scen = len(scenario_results)
    wildcard_possible = [r for r in scenario_results if "--no-distance" not in r["scenario_id"]
                         and not r["scenario_id"].endswith("strict-max")]

    def fill_rate(role, universe):
        pool_ = [r for r in universe]
        return (sum(1 for r in pool_ if r["slots"].get(role)) / len(pool_)) if pool_ else None

    gate = {
        "eligible_institutions": {"value": n_pool, "threshold": 75, "pass": n_pool >= 75},
        "direct_path": {"value": n_direct, "threshold": 30, "pass": n_direct >= 30},
        "additional_adjacent_path": {"value": n_adj, "threshold": 40, "pass": n_adj >= 40},
        "states": {"value": len(states), "threshold": 15, "pass": len(states) >= 15},
        "both_controls": {"value": dict(controls), "pass": controls.get(1, 0) > 0 and controls.get(2, 0) > 0},
        "rounds_min4": {"value": f"{rounds4}/{n_scen}", "threshold": "100%", "pass": rounds4 == n_scen},
        "rounds_full6": {"value": f"{rounds6}/{n_scen}", "threshold": ">=80%", "pass": rounds6 >= 0.8 * n_scen},
        "slot_anchor": {"value": fill_rate("anchor", scenario_results), "threshold": 1.0},
        "slot_flexible": {"value": fill_rate("flexible", scenario_results), "threshold": 0.8},
        "slot_contrast": {"value": fill_rate("contrast", scenario_results), "threshold": 0.5},
        "slot_affordability": {"value": fill_rate("affordability", scenario_results), "threshold": 0.7},
        "slot_wildcard": {"value": fill_rate("wildcard", wildcard_possible), "threshold": 0.7},
        "reasons_resolve": {"value": all(r["all_reasons_resolve"] for r in scenario_results), "threshold": True},
    }
    for k in ("slot_anchor", "slot_flexible", "slot_contrast", "slot_affordability", "slot_wildcard"):
        v = gate[k]["value"]
        gate[k]["pass"] = v is not None and v >= gate[k]["threshold"]
    gate["reasons_resolve"]["pass"] = gate["reasons_resolve"]["value"] is True

    audit = {
        "spike_version": "v1",
        "completions_release": "C2024_A provisional (2023-24 awards, MAJORNUM=1, AWLEVEL=05)",
        "ontology_version": ontology["ontology_version"],
        "scenario_corpus_version": scenarios["scenario_corpus_version"],
        "pool_size": n_pool,
        "direct_path_institutions": n_direct,
        "adjacent_only_institutions": n_adj,
        "states": states,
        "controls": dict(controls),
        "exclusions": dict(exclusions),
        "geography_missing_coordinates": geo_missing,
        "outcomes_available_pct": round(outcomes_available / n_pool, 3) if n_pool else 0,
        "identity_join": {
            "family_unitids_in_completions": len(family_unitids),
            "matched_to_directory": len(family_unitids & directory_ids),
            "unmatched_unitids": sorted(unmatched)[:50],
            "unmatched_count": len(unmatched),
        },
        "gate": gate,
        "scenarios": scenario_results,
        "direct_pool_sample": sorted(
            ({"school_id": s["school_id"], "state": s["state"],
              "direct_cips": s["direct"]} for s in direct_pool),
            key=lambda x: x["school_id"] or "")[:40],
    }
    (SPIKE / "audit.json").write_text(json.dumps(audit, indent=2))

    print(f"pool={n_pool} direct={n_direct} adjacent_only={n_adj} "
          f"states={len(states)} controls={dict(controls)}")
    print(f"exclusions={dict(exclusions)}")
    print(f"identity join: {len(family_unitids)} family unitids, "
          f"{len(unmatched)} unmatched to directory")
    print(f"geography: {len(geo_missing)} pool schools missing coordinates")
    print("GATE:")
    ok = True
    for k, v in gate.items():
        status = "PASS" if v.get("pass") else "FAIL"
        ok = ok and v.get("pass", False)
        print(f"  {status:4} {k}: {v.get('value')} (threshold {v.get('threshold')})")
    print("OVERALL:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
