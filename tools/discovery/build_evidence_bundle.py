#!/usr/bin/env python3
"""Build the versioned discovery evidence bundle (PRD 026 rounds engine).

Emits web/public/discovery/evidence-v1.json: the policy-eligible school pool
with exactly the evidence fields discovery_policy_v1's matchers, slots, and
reason templates consume, plus a provenance manifest (source checksums and
data years). The browser engine fetches this bundle and composes rounds
entirely client-side — nothing about the student ever leaves the device.

Run after fetching the same inputs data_spike.py uses (see its header).
The bundle is a committed, versioned artifact: regenerating it with new
source data is a content release (bump the filename version when the shape
changes; a same-shape data refresh updates generated/source manifests).
"""

import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import data_spike as ds  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "web" / "public" / "discovery" / "evidence-v1.json"

SCORECARD_FIELDS = [
    "locale",
    "avg_net_price",
    "net_price_0_30k",
    "median_debt_completers",
    "retention_rate_ft",
    "graduation_rate_4yr",
    "graduation_rate_6yr",
    "earnings_10yr_median",
    "pell_grant_rate",
    "scorecard_data_year",
]


def file_manifest(path: Path) -> dict:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    try:
        name = str(path.relative_to(ROOT))
    except ValueError:
        name = f"scratch/{path.name}"
    return {"file": name, "sha256": h.hexdigest(), "bytes": path.stat().st_size}


def main() -> int:
    directory, scorecard, ontology, _scenarios = ds.load_inputs()
    city_by_id = {d["ipeds_id"]: d.get("city") for d in directory}
    family_direct, family_adjacent = ds.edge_sets(ontology)
    awards = ds.load_completions(family_direct | family_adjacent)
    pool, exclusions = ds.build_pool(
        directory, scorecard, awards, family_direct, family_adjacent
    )

    schools = []
    for s in sorted(pool, key=lambda x: x["school_id"] or ""):
        sc = s["scorecard"] or {}
        schools.append({
            "school_id": s["school_id"],
            "ipeds_id": s["ipeds_id"],
            "name": s["name"],
            "city": city_by_id.get(s["ipeds_id"]),
            "state": s["state"],
            "control": s["control"],
            "lat": s["lat"],
            "lon": s["lon"],
            "enrollment": s["enrollment"],
            "direct": s["direct"],
            "adjacent": s["adjacent"],
            "scorecard": {k: sc.get(k) for k in SCORECARD_FIELDS},
        })

    bundle = {
        "bundle_version": "evidence-v1",
        "policy_version": ds.POLICY["policy_version"],
        "ontology_version": ontology["ontology_version"],
        "completions_release": "C2024_A provisional (2023-24 awards, MAJORNUM=1, AWLEVEL=05)",
        "completions_data_year": 2024,
        "eligibility": "discovery_policy_v1 stages 1+3 pre-applied at build time; geography and preference stages run client-side",
        "exclusions_at_build": dict(exclusions),
        "source_manifests": [
            file_manifest(ds.SPIKE / "C2024_a.csv"),
            file_manifest(ds.SPIKE / "directory.json"),
            file_manifest(ds.SPIKE / "scorecard.json"),
            file_manifest(ROOT / "data/discovery/ontology/v1.json"),
            file_manifest(ROOT / "data/discovery/policy/v1.json"),
        ],
        "school_count": len(schools),
        "schools": schools,
    }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(bundle, separators=(",", ":")))
    print(f"wrote {OUT.relative_to(ROOT)}: {len(schools)} schools, "
          f"{OUT.stat().st_size / 1024:.0f} KB")
    return 0


if __name__ == "__main__":
    sys.exit(main())
