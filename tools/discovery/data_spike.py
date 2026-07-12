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
  data/discovery/ontology/v1.json             interest-family edges
  data/discovery/scenarios/v1.json            20 scenario fixtures
  data/discovery/policy/v1.json               discovery_policy_v1 (executed)

Outputs:
  scratch/discovery-spike/audit.json          full machine-readable audit
  stdout                                       gate summary

Sibling: cds_card_coverage.py regenerates the per-card CDS coverage numbers
cited in the findings doc.

Spike-scope notes:
  - Matchers execute data/discovery/policy/v1.json. Keys whose evidence
    sources are not loaded here (cds.*, ipeds.ic.*, distance.*,
    merit_profile.*) resolve to None and return 0 — unknown, never mismatch.
    The policy's unsupported set is the reflection-only keys.
  - Origins are coordinates, not ZIPs (centroid source still unselected).
  - Completions use MAJORNUM=1 (first majors) and AWLEVEL=05 (bachelor's).
  - The "fewer_quality_flags" tie-break is not implementable here (quality
    flags are not loaded); ordering falls through to school_id.
"""

import csv
import hashlib
import json
import math
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SPIKE = ROOT / "scratch" / "discovery-spike"

BACHELOR_AWLEVEL = "5"
FIRST_MAJOR = "1"

# The versioned policy is the single source of truth for matchers, weights,
# slots, diversity caps, and relaxation (PRD 026 §7-8). This script is its
# reference implementation.
POLICY = json.load(open(ROOT / "data" / "discovery" / "policy" / "v1.json"))
SCORING = POLICY["scoring"]
DIVERSITY = POLICY["round_composition"]["diversity"]
MAX_PER_STATE = DIVERSITY["max_per_state"]
MAX_PER_CONTROL = DIVERSITY["max_per_control"]
ROUND_SIZE = POLICY["round_composition"]["round_size"]
MINIMUM_SIZE = POLICY["round_composition"]["minimum_size"]
ESSENTIAL = SCORING["essential_threshold"]
SUPPORTED_KEYS = frozenset(POLICY["matchers"])


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
    ontology = json.load(open(ROOT / "data/discovery/ontology/v1.json"))
    scenarios = json.load(open(ROOT / "data/discovery/scenarios/v1.json"))
    return directory, scorecard, ontology, scenarios


def load_completions(cip_universe):
    """UNITID -> {cip: total bachelor's first-major awards}."""
    by_school = defaultdict(dict)
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
            if cip in cip_universe:
                by_school[unitid][cip] = by_school[unitid].get(cip, 0) + total
    return by_school


def edge_sets(ontology, concepts=None):
    """Direct/adjacent CIP sets. Both None and an empty set mean the whole
    family — matching the product semantics (the interests step's "use the
    whole family" path) and the TypeScript engine."""
    direct, adjacent = set(), set()
    for e in ontology["edges"]:
        if concepts and e["from_concept_id"] not in concepts:
            continue
        if e["relationship"] == "direct":
            direct.add(e["to_cip"])
        elif e["relationship"] == "adjacent":
            adjacent.add(e["to_cip"])
    return direct, adjacent - direct


def _sc(school):
    return school["scorecard"] or {}


def _locale(school):
    v = _sc(school).get("locale")
    return int(v) if v is not None else None


# Evidence-key resolvers for the sources this spike loads. Keys without a
# resolver (cds.*, ipeds.ic.*, distance.*, merit_profile.*) resolve to None,
# so their matchers return 0 (unknown) — absence never means mismatch.
FIELD_RESOLVERS = {
    "directory.enrollment": lambda s: s["enrollment"],
    "program.related_cip_count": lambda s: (len(s["direct"]) + len(s["adjacent"])) or None,
    "scorecard.locale": _locale,
    "scorecard.net_price_0_30k": lambda s: _sc(s).get("net_price_0_30k"),
    "scorecard.median_debt_completers": lambda s: _sc(s).get("median_debt_completers"),
    "scorecard.retention_rate_ft": lambda s: _sc(s).get("retention_rate_ft"),
    "scorecard.graduation_rate_4yr": lambda s: _sc(s).get("graduation_rate_4yr"),
    "scorecard.earnings_10yr_median": lambda s: _sc(s).get("earnings_10yr_median"),
    "scorecard.pell_grant_rate": lambda s: _sc(s).get("pell_grant_rate"),
}


def _band_test(value, band):
    ops = {"gte": lambda v, t: v >= t, "gt": lambda v, t: v > t,
           "lte": lambda v, t: v <= t, "lt": lambda v, t: v < t}
    return all(ops[op](value, t) for op, t in band.items())


def matcher(key, school):
    """Execute the policy matcher for key -> -1 | 0 | +1."""
    spec = POLICY["matchers"].get(key)
    if spec is None:
        return 0  # unsupported key: ledger-only
    vals = []
    for ek in spec["evidence_keys"]:
        resolve = FIELD_RESOLVERS.get(ek)
        v = resolve(school) if resolve else None
        if v is not None:
            vals.append(v)
    kind = spec["kind"]
    if kind == "offering_any":
        return 1 if any(vals) else 0
    if kind == "checklist_membership":
        for v in vals:
            if isinstance(v, (list, set)):
                hits = sum(1 for m in spec["members"] if m in v)
                if hits >= spec.get("min_members", 1):
                    return 1
        return 0
    if kind == "category_set":
        if not vals:
            return 0
        v = vals[0]
        if v in spec.get("seek_set", []):
            return 1
        if v in spec.get("opposite_set", []):
            return -1
        return 0
    # numeric kinds: numeric_band, numeric_band_inverted, count_band
    if not vals:
        return 0
    v = max(vals) if spec.get("aggregation") == "max" else vals[0]
    if _band_test(v, spec["seek"]):
        return 1
    if _band_test(v, spec["opposite"]):
        return -1
    return 0


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
        score += SCORING["academic_match"]["direct"]
        reasons.append(("academic_direct", "program.recent_awards_direct"))
    elif any(c in adjacent_cips for c in school["adjacent"]) or any(
        c in adjacent_cips for c in school["direct"]
    ):
        score += SCORING["academic_match"]["adjacent"]
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
        # radius contribution; not a displayable reason (PRD shows distance itself)
        score += SCORING["inside_preferred_radius"]
    return score, reasons


def reason_resolves(reason, school, direct_cips, adjacent_cips):
    """Spike-level stand-in for PRD fail-closed rendering: a reason reference
    must resolve to loaded evidence for this school. Full RecommendationReason
    validation (templates, coverage records, limitation versions) is a
    discovery_policy_v1 deliverable."""
    kind, ref = reason
    if kind == "academic_direct":
        return ref == "program.recent_awards_direct" and any(
            c in direct_cips and n > 0 for c, n in school["direct"].items())
    if kind == "academic_adjacent":
        return ref == "program.recent_awards_adjacent" and any(
            c in adjacent_cips and n > 0
            for c, n in list(school["direct"].items()) + list(school["adjacent"].items()))
    if ref == f"match:{kind}":
        return kind in SUPPORTED_KEYS and matcher(kind, school) != 0
    return False


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
    wildcard_possible = bool(geo["allow_wildcards"] and pref_mi)
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
        return (state_count[s["state"]] < MAX_PER_STATE
                and control_count[s["control"]] < MAX_PER_CONTROL)

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
    slots_filled["flexible"] = take_flexible(candidates, chosen, direct_cips, adjacent_cips,
                                             state_count, control_count, diagnostics)
    slots_filled["contrast"] = take(
        lambda s: mismatches_exactly_one_interesting(s, prefs), "contrast")
    slots_filled["affordability"] = take_affordability(
        candidates, chosen, state_count, control_count, diagnostics)
    slots_filled["wildcard"] = (
        take(lambda s: s["distance"] is not None and s["distance"] > pref_mi, "wildcard")
        if geo["allow_wildcards"] and pref_mi else False)
    slots_filled["exploration"] = take(lambda s: True, "exploration")
    while len(chosen) < ROUND_SIZE and take(lambda s: True, "additional_exploration"):
        pass

    # PRD 026 §8: if diversity caps prevent a four-school minimum, relax
    # control type first, then state, recording the relaxation.
    if len(chosen) < MINIMUM_SIZE:
        # level 1 drops the control cap (state cap kept); level 2 drops both.
        for level, state_cap in enumerate([MAX_PER_STATE, None], start=1):
            added = 0
            for s in candidates:
                if len(chosen) >= MINIMUM_SIZE:
                    break
                if any(c["ipeds_id"] == s["ipeds_id"] for c in chosen):
                    continue
                if state_cap is not None and state_count[s["state"]] >= state_cap:
                    continue
                chosen.append({**s, "role": "additional_exploration_relaxed"})
                state_count[s["state"]] += 1
                control_count[s["control"]] += 1
                added += 1
            if added:
                diagnostics["relaxation_level"] = level
                diagnostics[f"relaxation_added_l{level}"] = added
            if len(chosen) >= MINIMUM_SIZE:
                break

    return chosen, slots_filled, diagnostics, len(candidates), wildcard_possible


def take_flexible(candidates, chosen, direct_cips, adjacent_cips,
                  state_count, control_count, diagnostics):
    """Highest related-CIP count among remaining direct matches, counted
    within the SELECTED concepts' edge sets (PRD 026 §8 slot 2), not the
    whole family."""
    best = None
    scoped = direct_cips | adjacent_cips
    for s in candidates:
        if any(c["ipeds_id"] == s["ipeds_id"] for c in chosen):
            continue
        if not any(c in direct_cips for c in s["direct"]):
            continue
        if state_count[s["state"]] >= MAX_PER_STATE or control_count[s["control"]] >= MAX_PER_CONTROL:
            diagnostics["diversity_rejected:flexible"] += 1
            continue
        related = sum(1 for c in list(s["direct"]) + list(s["adjacent"]) if c in scoped)
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
        if state_count[s["state"]] >= MAX_PER_STATE or control_count[s["control"]] >= MAX_PER_CONTROL:
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
        if abs(agg) >= ESSENTIAL:  # essential seek/avoid must not mismatch
            if (agg > 0 and m == -1) or (agg < 0 and m == 1):
                return False
        elif agg != 0:  # any sub-essential aggregate counts as interesting
            if (agg > 0 and m == -1) or (agg < 0 and m == 1):
                mismatched_interesting += 1
    return mismatched_interesting == 1


def main():
    directory, scorecard, ontology, scenarios = load_inputs()
    family_direct, family_adjacent = edge_sets(ontology)
    cip_universe = family_direct | family_adjacent
    awards = load_completions(cip_universe)

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

    # Identity-join audit: membership of family UNITIDs in the directory.
    # NOTE: ipeds_id is the directory's primary key, so the ambiguity check
    # in build_pool can never fire on this input; the PRD §6 audit of branch
    # campuses, systems, closures, and consolidations is future work.
    directory_ids = {d["ipeds_id"] for d in directory if d["ipeds_id"]}
    family_unitids = set(awards)
    unmatched = family_unitids - directory_ids

    # scenario simulation
    scenario_results = []
    for origin in scenarios["origins"]:
        for profile in scenarios["profiles"]:
            concepts = set(profile["concepts"])
            d_cips, a_cips = edge_sets(ontology, concepts)
            chosen, slots, diags, n_cand, wc_possible = compose_round(
                pool, profile, origin, (d_cips, a_cips))
            reasons_valid = all(
                s["reasons"] and all(
                    reason_resolves(r, s, d_cips, a_cips) for r in s["reasons"])
                for s in chosen)
            scenario_results.append({
                "scenario_id": f"{origin['origin_id']}--{profile['profile_id']}",
                "eligible_candidates": n_cand,
                "round_size": len(chosen),
                "slots": slots,
                "wildcard_possible": wc_possible,
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
    wildcard_universe = [r for r in scenario_results if r["wildcard_possible"]]

    def fill_rate(role, universe):
        return (sum(1 for r in universe if r["slots"].get(role)) / len(universe)) if universe else None

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
        "slot_wildcard": {"value": fill_rate("wildcard", wildcard_universe), "threshold": 0.7},
        "reasons_resolve": {"value": all(r["all_reasons_resolve"] for r in scenario_results), "threshold": True},
    }
    for k in ("slot_anchor", "slot_flexible", "slot_contrast", "slot_affordability", "slot_wildcard"):
        v = gate[k]["value"]
        gate[k]["pass"] = v is not None and v >= gate[k]["threshold"]
    gate["reasons_resolve"]["pass"] = gate["reasons_resolve"]["value"] is True

    def file_manifest(path):
        h = hashlib.sha256()
        with open(path, "rb") as fh:
            for chunk in iter(lambda: fh.read(1 << 20), b""):
                h.update(chunk)
        stat = path.stat()
        return {"file": path.name, "sha256": h.hexdigest(), "bytes": stat.st_size}

    audit = {
        "spike_version": "v1",
        "input_manifests": [
            file_manifest(SPIKE / "C2024_a.csv"),
            file_manifest(SPIKE / "directory.json"),
            file_manifest(SPIKE / "scorecard.json"),
            file_manifest(ROOT / "data/discovery/ontology/v1.json"),
            file_manifest(ROOT / "data/discovery/scenarios/v1.json"),
            file_manifest(ROOT / "data/discovery/policy/v1.json"),
        ],
        "policy_version": POLICY["policy_version"],
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
