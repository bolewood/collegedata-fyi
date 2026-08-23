"""Enqueue archive work for schools whose discovery seed just changed.

Weekly archive otherwise waits out the 7-day success cooldown, so a PDF
that we just rewrote to a listing would sit for a week. After 4 silent
months, new listings should be fetched the same day they land on main.
"""

from __future__ import annotations

import argparse
import json
import sys
import uuid
from pathlib import Path

import yaml

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from tools.ops.directory_enqueue_batches import (  # noqa: E402
    OpsError,
    SupabaseClient,
    require_supabase_credentials,
)

CANARY_SCHOOL_ID = "__finder_seed_catchup_canary__"


def seed_of(school: dict) -> str:
    return str(school.get("discovery_seed_url") or school.get("cds_url_hint") or "")


def changed_seed_ids(before: list[dict], after: list[dict]) -> list[str]:
    before_map = {str(row.get("id")): row for row in before if row.get("id")}
    changed: list[str] = []
    for row in after:
        sid = str(row.get("id") or "")
        if not sid:
            continue
        prev = before_map.get(sid)
        if prev is None:
            if seed_of(row) and row.get("scrape_policy") == "active":
                changed.append(sid)
            continue
        if seed_of(row) and seed_of(row) != seed_of(prev):
            changed.append(sid)
        elif (
            prev.get("scrape_policy") != "active"
            and row.get("scrape_policy") == "active"
            and seed_of(row)
        ):
            changed.append(sid)
    return changed


def load_schools(path: Path) -> list[dict]:
    data = yaml.safe_load(path.read_text())
    return data.get("schools") or []


def chunked(ids: list[str], size: int = 80) -> list[list[str]]:
    return [ids[i : i + size] for i in range(0, len(ids), size)]


def canary_filter_error(result: dict) -> str | None:
    """Catch a rolled-back archive-enqueue that ignores school_ids.

    A missing filter plus force_recheck would re-queue the whole corpus.
    The canary itself never sends force_recheck; it refuses to continue
    unless the function echoes that it applied a 1-id filter and matched
    nothing.
    """
    requested = result.get("school_ids_requested")
    matched = result.get("school_ids_matched")
    enqueued = int(result.get("enqueued") or 0)
    if requested != 1:
        return (
            f"school_ids_requested={requested!r}, expected 1 "
            "(archive-enqueue school_ids filter is not live)"
        )
    if int(matched or 0) != 0:
        return f"school_ids_matched={matched!r}, expected 0"
    if enqueued != 0:
        return f"enqueued={enqueued}, expected 0"
    return None


def chunk_filter_error(result: dict, group: list[str]) -> str | None:
    requested = result.get("school_ids_requested")
    matched = result.get("school_ids_matched")
    enqueued = int(result.get("enqueued") or 0)
    if requested != len(group):
        return (
            f"school_ids_requested={requested!r}, expected {len(group)} "
            "(filter did not echo this chunk)"
        )
    if matched is None or int(matched) > len(group):
        return f"school_ids_matched={matched!r} exceeds chunk of {len(group)}"
    if enqueued > len(group):
        return f"enqueued={enqueued} exceeds chunk of {len(group)}"
    return None


def assert_school_ids_filter(client: SupabaseClient) -> dict:
    result = client.post_function(
        "archive-enqueue",
        {
            "school_ids": CANARY_SCHOOL_ID,
            "run_id": str(uuid.uuid4()),
        },
    )
    error = canary_filter_error(result)
    if error:
        raise OpsError(error)
    return result


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.strip().split("\n\n")[0])
    ap.add_argument("--before", type=Path, required=True)
    ap.add_argument("--after", type=Path, required=True)
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--env", type=Path, default=Path(".env"))
    ap.add_argument(
        "--skip-canary",
        action="store_true",
        help="Do not ping archive-enqueue with a fake school_id first.",
    )
    args = ap.parse_args()
    ids = changed_seed_ids(load_schools(args.before), load_schools(args.after))
    print(json.dumps({"changed": len(ids), "ids": ids}, indent=2))
    if not ids:
        print("No seed changes; skipping enqueue.", file=sys.stderr)
        return 0
    if not args.apply:
        print("Dry-run. Pass --apply to enqueue.", file=sys.stderr)
        return 0
    url, key = require_supabase_credentials(args.env)
    client = SupabaseClient(url, key)
    if not args.skip_canary:
        canary = assert_school_ids_filter(client)
        print(json.dumps({"canary": canary}))
    enqueued = 0
    run_id = str(uuid.uuid4())
    for group in chunked(ids):
        result = client.post_function(
            "archive-enqueue",
            {
                "force_recheck": "true",
                "school_ids": ",".join(group),
                "run_id": run_id,
            },
        )
        error = chunk_filter_error(result, group)
        if error:
            raise OpsError(error)
        enqueued += int(result.get("enqueued") or 0)
        print(json.dumps({"chunk": group, "result": result}))
    print(json.dumps({"enqueued_total": enqueued}))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except OpsError as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
