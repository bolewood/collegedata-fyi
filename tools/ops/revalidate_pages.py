#!/usr/bin/env python3
"""Refresh cached school pages after their data changed.

School pages are cached for 7 days and are refreshed when data changes, by a
POST to the web app's /api/revalidate. The extraction worker and the
scholarship loader do that for the schools they touch. This script covers
everything else.

Modes:

  --changed-since-hours N   The daily sweep (workflow ops-page-refresh.yml).
                            Finds schools whose data changed in the last N
                            hours and refreshes their pages.
  --school-id ID [...]      Refresh named schools, for example after a
                            hand-run SQL edit.
  --all                     Expire every school page. Pages regenerate on
                            their next visit, so use it sparingly: after an
                            IPEDS, FSA or Scorecard load, or a change to how
                            pages are built.

What the sweep looks at (all read with the service role):

  cds_documents.updated_at          a trigger keeps it, so it also catches
                                    hiding a document, removal flags and SQL
                                    edits made by hand. Documents the archiver
                                    re-verified inside the window are left out
                                    (see find_changed_schools); after a hand
                                    edit to one of those, use --school-id
  cds_artifacts.created_at          artifacts written without touching the
                                    document row (LLM fallback, overlay)
  school_browser_rows.updated_at    projection refreshes
  cds_field_change_events.updated_at  new events only: nothing maintains the
                                    column on re-projection or delete
  scholarship_programs.loaded_at    a newly added program only; the loader
                                    workflow refreshes edited programs itself
  scholarship_version_checks        only checks that change what the page
                                    says (needs_review, or result changed or
                                    conflicting)

Not covered, by design: institution_cds_coverage (the hourly refresh rewrites
every row, so its timestamp cannot tell what changed), federal loads and
school identity or alias changes (run --all by hand after either: the Scorecard
and slug-crosswalk reads are shared by every school, so only --all expires
them). Those wait for the 7-day window at worst.

Environment: SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY (sweep only),
COLLEGEDATA_REVALIDATE_URL, REVALIDATE_SECRET.

Exit code: 0 on success or --dry-run; 1 when a required setting is missing, a
read fails, or a refresh request fails. School ids are never printed: this
repository's workflow logs are public.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping, Optional

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "extraction_worker"))

from revalidate_notify import (  # noqa: E402
    SECRET_ENV,
    URL_ENV,
    notify_all_revalidation,
    notify_school_revalidation,
)

PAGE_SIZE = 1000  # PostgREST max_rows
MAX_PAGES = 50
ID_CHUNK = 100  # ids per in.(...) filter; keeps the URL short
BATCH_PAUSE_SECONDS = 1.0
SCHOLARSHIP_RESULTS_THAT_CHANGE_PAGES = ("changed", "conflicting")

Fetch = Callable[[str, Mapping[str, str]], list]


class SweepError(RuntimeError):
    """A read failed or a required setting is missing."""


def rest_fetcher(env: Mapping[str, str], opener=urllib.request.urlopen) -> Fetch:
    """Return fetch(table, params) -> every matching row, paged."""
    base = (env.get("SUPABASE_URL") or "").rstrip("/")
    key = env.get("SUPABASE_SERVICE_ROLE_KEY") or ""
    if not base or not key:
        raise SweepError("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY are required for the sweep")

    def fetch(table: str, params: Mapping[str, str]) -> list:
        rows: list = []
        for page in range(MAX_PAGES):
            query = dict(params, limit=str(PAGE_SIZE), offset=str(page * PAGE_SIZE))
            url = f"{base}/rest/v1/{table}?{urllib.parse.urlencode(query)}"
            request = urllib.request.Request(
                url,
                headers={"apikey": key, "Authorization": f"Bearer {key}", "Accept": "application/json"},
            )
            try:
                with opener(request, timeout=30) as response:
                    chunk = json.loads(response.read().decode("utf-8"))
            except urllib.error.HTTPError as e:
                raise SweepError(f"read of {table} failed: HTTP {e.code}") from None
            except Exception as e:  # noqa: BLE001
                raise SweepError(f"read of {table} failed: {type(e).__name__}") from None
            if not isinstance(chunk, list):
                raise SweepError(f"read of {table} returned an unexpected body")
            rows.extend(chunk)
            if len(chunk) < PAGE_SIZE:
                return rows
        raise SweepError(f"read of {table} did not finish in {MAX_PAGES} pages")

    return fetch


def _chunks(items: list, size: int) -> Iterable[list]:
    for i in range(0, len(items), size):
        yield items[i : i + size]


def _school_ids(rows: Iterable[Mapping[str, Any]]) -> set:
    return {r["school_id"] for r in rows if isinstance(r.get("school_id"), str) and r["school_id"]}


def find_changed_schools(fetch: Fetch, since: datetime) -> dict:
    """Schools whose page data changed after `since`.

    Returns {"schools": set, "scholarships": bool, "sources": {name: count}}.
    """
    stamp = since.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    after = f"gt.{stamp}"
    sources: dict = {}

    def add(name: str, ids: set) -> set:
        sources[name] = len(ids)
        return ids

    schools: set = set()
    # The weekly archive re-check of an unchanged file stamps last_verified_at,
    # which also moves updated_at. Pages do not show that date, so a document
    # verified inside the window is not counted: otherwise a seventh of all
    # schools would look changed every day.
    schools |= add(
        "documents",
        _school_ids(
            fetch(
                "cds_documents",
                {
                    "select": "school_id",
                    "updated_at": after,
                    "or": f"(last_verified_at.is.null,last_verified_at.lt.{stamp})",
                    "order": "id",
                },
            )
        ),
    )
    schools |= add(
        "browser_rows", _school_ids(fetch("school_browser_rows", {"select": "school_id", "updated_at": after, "order": "document_id"}))
    )
    schools |= add(
        "change_events", _school_ids(fetch("cds_field_change_events", {"select": "school_id", "updated_at": after, "order": "id"}))
    )

    # Artifacts carry a document id, not a school id.
    document_ids = sorted(
        {
            r["document_id"]
            for r in fetch("cds_artifacts", {"select": "document_id", "created_at": after, "order": "id"})
            if r.get("document_id")
        }
    )
    artifact_schools: set = set()
    for chunk in _chunks(document_ids, ID_CHUNK):
        artifact_schools |= _school_ids(
            fetch("cds_documents", {"select": "school_id", "id": f"in.({','.join(chunk)})", "order": "id"})
        )
    schools |= add("artifacts", artifact_schools)

    # Scholarships: a load, or a monitor check that changes what the page says.
    program_ids = {
        r["program_id"]
        for r in fetch("scholarship_programs", {"select": "program_id", "loaded_at": after, "order": "program_id"})
        if r.get("program_id")
    }
    results = ",".join(SCHOLARSHIP_RESULTS_THAT_CHANGE_PAGES)
    program_ids |= {
        r["program_id"]
        for r in fetch(
            "scholarship_version_checks",
            {
                "select": "program_id",
                "checked_at": after,
                "or": f"(needs_review.is.true,result.in.({results}))",
                "order": "id",
            },
        )
        if r.get("program_id")
    }
    scholarship_schools: set = set()
    for chunk in _chunks(sorted(program_ids), ID_CHUNK):
        for row in fetch(
            "scholarship_programs",
            {
                "select": "school_id,participating_schools",
                "program_id": f"in.({','.join(chunk)})",
                "order": "program_id",
            },
        ):
            if isinstance(row.get("school_id"), str) and row["school_id"]:
                scholarship_schools.add(row["school_id"])
            # participating_schools holds [{school_id, ipeds_id}] objects.
            for other in row.get("participating_schools") or []:
                other_id = other.get("school_id") if isinstance(other, dict) else other
                if isinstance(other_id, str) and other_id:
                    scholarship_schools.add(other_id)
    schools |= add("scholarships", scholarship_schools)

    return {"schools": schools, "scholarships": bool(program_ids), "sources": sources}


def _require_revalidate_env(env: Mapping[str, str]) -> None:
    if not (env.get(URL_ENV) or "").strip() or not env.get(SECRET_ENV):
        raise SweepError(f"{URL_ENV} and {SECRET_ENV} are required to refresh pages")


def run(
    args: argparse.Namespace,
    env: Mapping[str, str],
    *,
    fetch: Optional[Fetch] = None,
    opener=urllib.request.urlopen,
    now: Optional[datetime] = None,
    out=print,
) -> int:
    try:
        if args.all:
            if args.dry_run:
                out("revalidate_pages: dry run, would expire every school page")
                return 0
            _require_revalidate_env(env)
            result = notify_all_revalidation(env, opener=opener)
            out(f"revalidate_pages: expire-all sent, errors={result['errors']}")
            return 1 if result["errors"] else 0

        scholarships = bool(args.scholarships)
        if args.changed_since_hours is not None:
            since = (now or datetime.now(timezone.utc)) - timedelta(hours=args.changed_since_hours)
            found = find_changed_schools(fetch or rest_fetcher(env), since)
            ids = sorted(found["schools"])
            scholarships = scholarships or found["scholarships"]
            by_source = ", ".join(f"{k}={v}" for k, v in found["sources"].items())
            out(f"revalidate_pages: {len(ids)} school(s) changed in {args.changed_since_hours:g} h ({by_source})")
        else:
            ids = sorted({s.strip() for s in args.school_id if s.strip()})

        if not ids:
            out("revalidate_pages: nothing to refresh")
            return 0
        if args.dry_run:
            out(f"revalidate_pages: dry run, would refresh {len(ids)} school(s), scholarships={scholarships}")
            return 0
        _require_revalidate_env(env)
        result = notify_school_revalidation(
            ids,
            env,
            opener=opener,
            max_batches=None,
            scholarships=scholarships,
            pause_seconds=BATCH_PAUSE_SECONDS,
        )
        out(
            f"revalidate_pages: refreshed {result['sent']}/{len(ids)} school(s) "
            f"in {result['batches']} batch(es), errors={result['errors']}"
        )
        return 1 if result["errors"] or result["sent"] != len(ids) else 0
    except SweepError as e:
        print(f"revalidate_pages_error: {e}", file=sys.stderr, flush=True)
        return 1


def parse_args(argv: Optional[list] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--changed-since-hours", type=float, help="sweep: refresh schools changed in this window")
    mode.add_argument("--school-id", action="append", default=[], help="refresh this school (repeatable)")
    mode.add_argument("--all", action="store_true", help="expire every school page")
    parser.add_argument("--scholarships", action="store_true", help="also expire the scholarship directory read")
    parser.add_argument("--dry-run", action="store_true", help="report what would be refreshed; send nothing")
    args = parser.parse_args(argv)
    if args.changed_since_hours is not None and not 0 < args.changed_since_hours <= 24 * 14:
        parser.error("--changed-since-hours must be between 0 and 336")
    return args


def main(argv: Optional[list] = None) -> int:
    return run(parse_args(argv), os.environ)


if __name__ == "__main__":
    sys.exit(main())
