#!/usr/bin/env python3
"""Probe NCES/IPEDS for the next Access Database releases.

The probe is intentionally read-only. It checks the official NCES Access
Database page against the latest loaded provisional release and reports when
the next provisional bundle or the matching final bundle appears.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.request
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

if __package__ is None or __package__ == "":
    sys.path.append(str(Path(__file__).resolve().parents[2]))

from tools.ipeds.metadata import NCES_IPEDS_ACCESS_PAGE, normalize_release_date_text, parse_access_page

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PROBE_DELAY_MONTHS = 10


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--as-of", help="Override today's date for dry runs, YYYY-MM-DD.")
    parser.add_argument("--probe-delay-months", type=int, default=DEFAULT_PROBE_DELAY_MONTHS)
    parser.add_argument("--force", action="store_true", help="Probe targets even before their computed due date.")
    parser.add_argument("--out-json", type=Path, help="Write the full probe summary to this path.")
    parser.add_argument("--env", type=Path, default=REPO_ROOT / ".env", help="Optional .env file for local runs.")
    args = parser.parse_args()

    load_env(args.env)
    as_of = date.fromisoformat(args.as_of) if args.as_of else datetime.now(timezone.utc).date()
    loaded_releases = fetch_loaded_releases()
    remote_releases = fetch_remote_releases()
    summary = summarize_probe(
        loaded_releases,
        remote_releases,
        as_of=as_of,
        probe_delay_months=args.probe_delay_months,
        force=args.force,
    )
    summary["generated_at"] = datetime.now(timezone.utc).isoformat()
    summary["source_page_url"] = NCES_IPEDS_ACCESS_PAGE

    body = json.dumps(summary, indent=2, sort_keys=True)
    print(body)
    if args.out_json:
        args.out_json.parent.mkdir(parents=True, exist_ok=True)
        args.out_json.write_text(body + "\n", encoding="utf-8")
    return 0


def fetch_loaded_releases() -> list[dict[str, Any]]:
    try:
        from supabase import create_client
    except ImportError as exc:
        raise SystemExit("supabase package is required to read loaded IPEDS releases") from exc

    supabase_url = os.environ.get("SUPABASE_URL") or os.environ.get("NEXT_PUBLIC_SUPABASE_URL")
    key = (
        os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
        or os.environ.get("SUPABASE_ANON_KEY")
        or os.environ.get("NEXT_PUBLIC_SUPABASE_ANON_KEY")
    )
    if not supabase_url or not key:
        raise SystemExit("SUPABASE_URL and a Supabase API key are required")

    client = create_client(supabase_url, key)
    response = (
        client.table("ipeds_releases")
        .select("collection_year,data_year,release_type,release_date,metadata_url,access_url,notes")
        .execute()
    )
    return response.data or []


def fetch_remote_releases() -> list[dict[str, Any]]:
    request = urllib.request.Request(
        NCES_IPEDS_ACCESS_PAGE,
        headers={"User-Agent": "collegedata-fyi-ipeds-release-probe/1.0"},
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        html = response.read().decode("utf-8", errors="replace")

    releases = []
    for release in parse_access_page(html):
        normalized_date, precision = normalize_release_date_text(release.release_date)
        releases.append({
            "collection_year": release.collection_year,
            "data_year": release.data_year,
            "release_type": release.release_type,
            "release_date": normalized_date,
            "release_date_text": release.release_date,
            "release_date_precision": precision,
            "metadata_url": release.metadata_url,
            "access_url": release.access_url,
        })
    return releases


def summarize_probe(
    loaded_releases: list[dict[str, Any]],
    remote_releases: list[dict[str, Any]],
    *,
    as_of: date,
    probe_delay_months: int,
    force: bool = False,
) -> dict[str, Any]:
    loaded_keys = {(row["collection_year"], row["release_type"]) for row in loaded_releases}
    remote_by_key = {(row["collection_year"], row["release_type"]): row for row in remote_releases}
    reference = latest_loaded_provisional(loaded_releases, remote_by_key)

    targets: list[dict[str, Any]] = []
    if reference is not None:
        due_on = add_months(date.fromisoformat(reference["release_date"]), probe_delay_months)
        for collection_year, release_type in [
            (reference["collection_year"], "final"),
            (next_collection_year(reference["collection_year"]), "provisional"),
        ]:
            key = (collection_year, release_type)
            remote = remote_by_key.get(key)
            if key in loaded_keys:
                status = "loaded"
            elif as_of < due_on and not force:
                status = "not_due"
            elif remote is not None:
                status = "available"
            else:
                status = "not_available"
            targets.append({
                "collection_year": collection_year,
                "release_type": release_type,
                "due_on": due_on.isoformat(),
                "status": status,
                "remote_release": remote,
            })

    return {
        "as_of": as_of.isoformat(),
        "probe_delay_months": probe_delay_months,
        "reference_release": reference,
        "available_count": sum(1 for target in targets if target["status"] == "available"),
        "targets": targets,
        "remote_releases": remote_releases[:5],
    }


def latest_loaded_provisional(
    loaded_releases: list[dict[str, Any]],
    remote_by_key: dict[tuple[str, str], dict[str, Any]],
) -> dict[str, Any] | None:
    candidates = []
    for row in loaded_releases:
        if row.get("release_type") != "provisional":
            continue
        release_date = release_date_from_loaded_row(row)
        if release_date is None:
            remote = remote_by_key.get((row["collection_year"], row["release_type"]))
            release_date = remote.get("release_date") if remote else None
        if release_date is None:
            continue
        candidates.append({
            "collection_year": row["collection_year"],
            "data_year": row["data_year"],
            "release_type": row["release_type"],
            "release_date": release_date,
            "metadata_url": row.get("metadata_url"),
            "access_url": row.get("access_url"),
        })
    if not candidates:
        return None
    return max(candidates, key=lambda row: (row["release_date"], row["data_year"], row["collection_year"]))


def release_date_from_loaded_row(row: dict[str, Any]) -> str | None:
    release_date = row.get("release_date")
    if release_date:
        return str(release_date)[:10]
    notes = row.get("notes") or {}
    if isinstance(notes, str):
        try:
            notes = json.loads(notes)
        except json.JSONDecodeError:
            notes = {}
    normalized, _precision = normalize_release_date_text(notes.get("release_date_text"))
    return normalized


def next_collection_year(collection_year: str) -> str:
    start_text, end_text = collection_year.split("-", 1)
    start = int(start_text) + 1
    end = (int(end_text) + 1) % 100
    return f"{start}-{end:02d}"


def add_months(value: date, months: int) -> date:
    month_index = value.month - 1 + months
    year = value.year + month_index // 12
    month = month_index % 12 + 1
    day = min(value.day, days_in_month(year, month))
    return date(year, month, day)


def days_in_month(year: int, month: int) -> int:
    if month == 2:
        if year % 400 == 0 or (year % 4 == 0 and year % 100 != 0):
            return 29
        return 28
    if month in {4, 6, 9, 11}:
        return 30
    return 31


def load_env(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


if __name__ == "__main__":
    raise SystemExit(main())
