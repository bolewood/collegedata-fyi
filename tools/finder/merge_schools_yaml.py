"""Three-way merge of finder schools.yaml at school-id grain.

A 2h45m probe checks out main at start. If main's workflow or seeds move
before the seed PR push, GitHub treats the stale workflow tree as a
workflow update and rejects the GitHub App. Publish from current main and
overlay only schools the probe actually changed relative to the start SHA.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import yaml

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

SEED_FIELDS = ("discovery_seed_url", "cds_url_hint", "scrape_policy", "probe_state")


def load_schools(path: Path) -> tuple[dict, list[dict]]:
    data = yaml.safe_load(path.read_text())
    schools = data.get("schools") or []
    return data, schools


def by_id(schools: list[dict]) -> dict[str, dict]:
    return {str(school.get("id")): school for school in schools if school.get("id")}


def seed_url(school: dict | None) -> str | None:
    if not school:
        return None
    return school.get("discovery_seed_url") or school.get("cds_url_hint")


def seed_policy(school: dict | None):
    if not school:
        return None
    return school.get("scrape_policy")


def probe_state_signature(school: dict | None) -> tuple:
    if not school:
        return ()
    ps = school.get("probe_state") or {}
    return (ps.get("last_result"), ps.get("last_probed_at"), ps.get("last_method"))


def seed_signature(school: dict | None) -> tuple:
    if not school:
        return ()
    return (seed_url(school), seed_policy(school), *probe_state_signature(school))


def overlay_seed_fields(target: dict, source: dict) -> dict:
    merged = dict(target)
    for field in SEED_FIELDS:
        if field in source:
            merged[field] = source[field]
        elif field in merged and field not in source:
            if field == "cds_url_hint":
                continue
    return merged


def overlay_probe_state(target: dict, source: dict) -> dict:
    merged = dict(target)
    if "probe_state" in source:
        merged["probe_state"] = source["probe_state"]
    return merged


def merge_school_lists(
    base: list[dict],
    main: list[dict],
    probed: list[dict],
) -> tuple[list[dict], list[str]]:
    base_map = by_id(base)
    probed_map = by_id(probed)
    changed_ids: list[str] = []
    out: list[dict] = []
    seen: set[str] = set()
    for school in main:
        sid = str(school.get("id") or "")
        seen.add(sid)
        probed_school = probed_map.get(sid)
        if probed_school is None:
            out.append(school)
            continue
        started = base_map.get(sid)
        url_or_policy_changed = seed_url(probed_school) != seed_url(
            started
        ) or seed_policy(probed_school) != seed_policy(started)
        state_changed = probe_state_signature(probed_school) != probe_state_signature(
            started
        )
        if url_or_policy_changed:
            # Probe actually rewrote the seed. That find wins even if main
            # also moved the same school during the run.
            out.append(overlay_seed_fields(school, probed_school))
            changed_ids.append(sid)
        elif state_changed:
            # Cooldown / not_found stamps must land, but must not revert a
            # listing that merged to main while the probe still held the
            # start-of-run PDF.
            out.append(overlay_probe_state(school, probed_school))
            changed_ids.append(sid)
        else:
            out.append(school)
    for sid, probed_school in probed_map.items():
        if sid not in seen:
            out.append(probed_school)
            changed_ids.append(sid)
    return out, changed_ids


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.strip().split("\n\n")[0])
    ap.add_argument("--base", type=Path, required=True)
    ap.add_argument("--main", type=Path, required=True)
    ap.add_argument("--probed", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()
    _base_doc, base = load_schools(args.base)
    main_doc, main_schools = load_schools(args.main)
    _probed_doc, probed = load_schools(args.probed)
    merged, changed_ids = merge_school_lists(base, main_schools, probed)
    if args.out.resolve() != args.main.resolve():
        args.out.write_text(args.main.read_text())
    from tools.finder.apply_probe_log import write_school_updates

    write_school_updates(args.out, merged, set(changed_ids))
    print(json.dumps({"changed": len(changed_ids), "ids": changed_ids[:50]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
