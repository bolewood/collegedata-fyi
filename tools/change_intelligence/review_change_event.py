#!/usr/bin/env python3
"""Record human review for a PRD 019 change event.

The projector writes generated candidates to `cds_field_change_events`. This
operator tool records the source-PDF review verdict and, for confirmed events,
can flip `public_visible` so the school-page card may render it.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from project_change_events import load_env


REVIEW_VERDICTS = {"confirmed", "extractor_noise", "ambiguous", "not_reportable"}


def review_payload(
    event_id: str,
    reviewer: str,
    verdict: str,
    notes: str | None,
    source_pages_checked: list[str],
) -> dict[str, Any]:
    if verdict not in REVIEW_VERDICTS:
        raise ValueError(f"unsupported verdict: {verdict}")
    return {
        "event_id": event_id,
        "reviewer": reviewer,
        "verdict": verdict,
        "notes": notes,
        "source_pages_checked": source_pages_checked,
    }


def event_update_payload(verdict: str, publish: bool) -> dict[str, Any]:
    if verdict not in REVIEW_VERDICTS:
        raise ValueError(f"unsupported verdict: {verdict}")
    if publish and verdict != "confirmed":
        raise ValueError("--publish is only valid for confirmed events")
    return {
        "verification_status": verdict,
        "public_visible": bool(publish and verdict == "confirmed"),
    }


def parse_source_pages(raw_pages: list[str]) -> list[str]:
    pages: list[str] = []
    for raw in raw_pages:
        for part in raw.split(","):
            value = part.strip()
            if value:
                pages.append(value)
    return pages


def fetch_event(client: Any, event_id: str) -> dict[str, Any]:
    rows = (
        client.table("cds_field_change_events")
        .select("id,school_name,field_label,event_type,severity,summary,verification_status,public_visible")
        .eq("id", event_id)
        .limit(1)
        .execute()
        .data
        or []
    )
    if not rows:
        raise RuntimeError(f"event not found: {event_id}")
    return rows[0]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env", type=Path)
    parser.add_argument("--event-id", required=True)
    parser.add_argument("--reviewer", required=True)
    parser.add_argument("--verdict", required=True, choices=sorted(REVIEW_VERDICTS))
    parser.add_argument("--notes")
    parser.add_argument("--source-page", action="append", default=[])
    parser.add_argument("--publish", action="store_true")
    args = parser.parse_args()

    try:
        from supabase import create_client
    except ImportError as e:
        raise SystemExit("supabase-py is required for change event review") from e

    review = review_payload(
        args.event_id,
        args.reviewer,
        args.verdict,
        args.notes,
        parse_source_pages(args.source_page),
    )
    update = event_update_payload(args.verdict, args.publish)

    env = load_env(args.env)
    client = create_client(env["SUPABASE_URL"], env["SUPABASE_SERVICE_ROLE_KEY"])
    event = fetch_event(client, args.event_id)
    client.table("cds_field_change_event_reviews").upsert(review).execute()
    client.table("cds_field_change_events").update(update).eq("id", args.event_id).execute()

    print(json.dumps({
        "event_id": args.event_id,
        "school": event.get("school_name"),
        "field": event.get("field_label"),
        "verdict": args.verdict,
        "public_visible": update["public_visible"],
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
