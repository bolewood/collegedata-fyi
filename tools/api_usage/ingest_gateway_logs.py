#!/usr/bin/env python3
"""Ingest Supabase gateway logs into api_gateway_* aggregates (PRD 032).

Modes:
  hourly    Reprocess whole UTC hours from the last good window end (at least
            the last 3 hours) up to the current hour. Default.
  backfill  Reprocess --days whole days ending at the current hour.

--dry-run queries and aggregates without touching the database (a throwaway
in-memory salt stands in for the daily salt).

The repository is public, so GitHub Actions logs and --out-json are public:
they carry counts only, never IPs, user agents, hashes, or school ids.
"""

from __future__ import annotations

import argparse
import json
import os
import secrets
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Callable

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tools.api_usage import aggregate  # noqa: E402
from tools.api_usage import classify  # noqa: E402
from tools.api_usage import queries  # noqa: E402
from tools.api_usage.logs_api import LogsApiError, LogsClient, redact  # noqa: E402

DEFAULT_PROJECT_REF = "isduwmygvmdozhpvzaix"
HOURLY_MIN_HOURS = 3
MAX_LOOKBACK = timedelta(days=89)
RETENTION_PROBE_HOUR_UTC = 3


class IngestError(RuntimeError):
    pass


def floor_hour(dt: datetime) -> datetime:
    return dt.astimezone(timezone.utc).replace(minute=0, second=0, microsecond=0)


def slices(start: datetime, end: datetime, hours: int) -> list[tuple[datetime, datetime]]:
    out = []
    cursor = start
    step = timedelta(hours=hours)
    while cursor < end:
        out.append((cursor, min(cursor + step, end)))
        cursor += step
    return out


class Db:
    """Minimal PostgREST client using the service role key."""

    def __init__(self, url: str, key: str, opener: Callable = urllib.request.urlopen) -> None:
        if not url or not key:
            raise IngestError("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY are required")
        self._base = url.rstrip("/") + "/rest/v1"
        self._key = key
        self._opener = opener

    def _call(self, method: str, path: str, body: object = None, prefer: str = "") -> object:
        headers = {
            "apikey": self._key,
            "Authorization": f"Bearer {self._key}",
            "Content-Type": "application/json",
            "User-Agent": "collegedata-pipeline/api-usage-ingest",
        }
        if prefer:
            headers["Prefer"] = prefer
        data = json.dumps(body).encode("utf-8") if body is not None else None
        request = urllib.request.Request(self._base + path, data=data, method=method, headers=headers)
        try:
            with self._opener(request, timeout=120) as response:
                raw = response.read()
        except urllib.error.HTTPError as exc:
            detail = exc.read()[:300].decode("utf-8", "replace")
            raise IngestError(f"database {method} {path.split('?')[0]} HTTP {exc.code}: {redact(detail)}") from None
        return json.loads(raw) if raw else None

    def rpc(self, name: str, payload: dict) -> object:
        return self._call("POST", f"/rpc/{name}", payload)

    def select(self, table: str, query: str) -> list[dict]:
        result = self._call("GET", f"/{table}?{query}")
        return result if isinstance(result, list) else []

    def insert(self, table: str, row: dict, prefer: str) -> object:
        return self._call("POST", f"/{table}", row, prefer)

    def update(self, table: str, query: str, row: dict) -> None:
        self._call("PATCH", f"/{table}?{query}", row, "return=minimal")


class SaltStore:
    """Per-UTC-day HMAC salts. Created on first use; pruned by api_usage_prune()."""

    def __init__(self, db: Db | None) -> None:
        self._db = db
        self._cache: dict[str, str] = {}

    def __call__(self, day: str) -> str:
        if day in self._cache:
            return self._cache[day]
        if self._db is None:
            salt = secrets.token_hex(32)
        else:
            salt = self._fetch(day)
            if salt is None:
                self._db.insert(
                    "api_usage_hash_salts",
                    {"day": day, "salt": secrets.token_hex(32)},
                    "resolution=ignore-duplicates,return=minimal",
                )
                salt = self._fetch(day)
            if salt is None:
                raise IngestError("could not create the daily hash salt")
        self._cache[day] = salt
        return salt

    def _fetch(self, day: str) -> str | None:
        rows = self._db.select("api_usage_hash_salts", f"select=salt&day=eq.{day}")
        return rows[0]["salt"] if rows else None


def in_window(rows: list[dict], start: datetime, end: datetime) -> tuple[list[dict], int]:
    """Drop rows whose hour falls outside [start, end); return (kept, dropped requests)."""
    lo, hi = start.timestamp(), end.timestamp()
    kept, dropped = [], 0
    for row in rows:
        if lo <= int(row["h"]) < hi:
            kept.append(row)
        else:
            dropped += int(row.get("n") or 0)
    return kept, dropped


def _reconciled(raw: int, counted: int) -> bool:
    return abs(raw - counted) <= max(5, raw // 1000)


def process_window(
    logs: LogsClient,
    db: Db | None,
    salts: Callable[[str], str],
    start: datetime,
    end: datetime,
    t0: datetime | None,
) -> dict:
    edge_raw, edge_dropped = in_window(logs.query_all(queries.edge_rollup_sql(), start, end), start, end)
    school_raw, _ = in_window(logs.query_all(queries.edge_schools_sql(t0), start, end), start, end)
    client_raw, _ = in_window(logs.query_all(queries.edge_clients_sql(t0), start, end), start, end)
    fn_raw, fn_dropped = in_window(logs.query_all(queries.function_rollup_sql(), start, end), start, end)
    edge_count = int(logs.query(queries.raw_count_sql("edge_logs"), start, end)[0]["n"])
    fn_count = int(logs.query(queries.raw_count_sql("function_edge_logs"), start, end)[0]["n"])

    rollups = aggregate.edge_rollups(edge_raw, t0)
    schools = aggregate.edge_schools(school_raw, t0)
    clients = aggregate.edge_clients(client_raw, t0, salts)
    fn_rollups = aggregate.function_rollups(fn_raw)

    edge_total = sum(row["requests"] for row in rollups)
    fn_total = sum(row["requests"] for row in fn_rollups)
    written = 0
    if db is not None:
        common = {"p_start": start.isoformat(), "p_end": end.isoformat()}
        db.rpc("api_usage_replace_window", {
            **common,
            "p_log_source": "edge_logs",
            "p_rollups": rollups,
            "p_clients": clients,
            "p_schools": schools,
        })
        db.rpc("api_usage_replace_window", {
            **common,
            "p_log_source": "function_edge_logs",
            "p_rollups": fn_rollups,
        })
        written = len(rollups) + len(clients) + len(schools) + len(fn_rollups)

    return {
        "window_start": start.isoformat(),
        "window_end": end.isoformat(),
        "rows_read": len(edge_raw) + len(school_raw) + len(client_raw) + len(fn_raw),
        "rows_written": written,
        "raw_requests": edge_count + fn_count,
        "rollup_requests": edge_total + fn_total,
        "reconciled": _reconciled(edge_count, edge_total + edge_dropped)
        and _reconciled(fn_count, fn_total + fn_dropped),
        "rollup_rows": len(rollups) + len(fn_rollups),
        "client_rows": len(clients),
        "school_rows": len(schools),
        "summary": aggregate.summarize(rollups + fn_rollups),
    }


def last_good_end(db: Db) -> datetime | None:
    rows = db.select(
        "api_usage_ingest_runs",
        "select=window_end&status=eq.ok&order=window_end.desc&limit=1",
    )
    if not rows:
        return None
    return datetime.fromisoformat(rows[0]["window_end"].replace("Z", "+00:00"))


def plan_windows(mode: str, now: datetime, days: int, last_end: datetime | None) -> tuple[datetime, datetime]:
    end = floor_hour(now)
    oldest = end - MAX_LOOKBACK
    if mode == "backfill":
        if not 1 <= days <= 89:
            raise IngestError("--days must be between 1 and 89")
        return end - timedelta(days=days), end
    start = end - timedelta(hours=HOURLY_MIN_HOURS)
    if last_end is not None and last_end < start:
        start = max(floor_hour(last_end), oldest)
    return start, end


def retention_ok(logs: LogsClient, now: datetime) -> bool:
    probe_end = floor_hour(now) - timedelta(days=7)
    rows = logs.query(queries.raw_count_sql("edge_logs"), probe_end - timedelta(hours=1), probe_end)
    return int(rows[0]["n"]) > 0


def merge_summaries(parts: list[dict]) -> dict:
    out: dict[str, dict[str, int]] = {}
    for part in parts:
        for section, counts in part.items():
            bucket = out.setdefault(section, {})
            for key, value in counts.items():
                bucket[key] = bucket.get(key, 0) + value
    return {section: dict(sorted(counts.items())) for section, counts in out.items()}


def run(args: argparse.Namespace, *, now: datetime | None = None,
        logs: LogsClient | None = None, db: Db | None = None) -> dict:
    now = now or datetime.now(timezone.utc)
    t0 = classify.SITE_TAGGING_T0
    if logs is None:
        logs = LogsClient(
            os.environ.get("SUPABASE_LOGS_TOKEN", ""),
            os.environ.get("SUPABASE_PROJECT_REF", DEFAULT_PROJECT_REF),
        )
    if db is None and not args.dry_run:
        db = Db(os.environ.get("SUPABASE_URL", ""), os.environ.get("SUPABASE_SERVICE_ROLE_KEY", ""))

    last_end = last_good_end(db) if (db is not None and args.mode == "hourly") else None
    start, end = plan_windows(args.mode, now, args.days, last_end)
    lag_hours = int((floor_hour(now) - last_end).total_seconds() // 3600) if last_end else None
    salts = SaltStore(db)
    run_url = os.environ.get("PIPELINE_RUN_URL") or None

    report: dict = {
        "mode": args.mode,
        "dry_run": bool(args.dry_run),
        "window_start": start.isoformat(),
        "window_end": end.isoformat(),
        "lag_hours": lag_hours,
        "windows": 0,
        "requests": 0,
        "third_party_requests": 0,
        "rows_written": 0,
        "reconciled": True,
        "retention_ok": None,
        "windows_detail": [],
    }

    if args.mode == "hourly" and end.hour == RETENTION_PROBE_HOUR_UTC:
        report["retention_ok"] = retention_ok(logs, now)

    summaries = []
    for window_start, window_end in slices(start, end, args.slice_hours):
        run_id = None
        if db is not None:
            created = db.insert(
                "api_usage_ingest_runs",
                {
                    "mode": args.mode,
                    "window_start": window_start.isoformat(),
                    "window_end": window_end.isoformat(),
                    "run_url": run_url,
                },
                "return=representation",
            )
            run_id = created[0]["id"] if isinstance(created, list) and created else None
        try:
            stats = process_window(logs, db, salts, window_start, window_end, t0)
        except Exception as exc:
            if db is not None and run_id is not None:
                db.update("api_usage_ingest_runs", f"id=eq.{run_id}", {
                    "status": "error",
                    "finished_at": datetime.now(timezone.utc).isoformat(),
                    "error_code": type(exc).__name__,
                })
            raise
        if db is not None and run_id is not None:
            db.update("api_usage_ingest_runs", f"id=eq.{run_id}", {
                "status": "ok",
                "finished_at": datetime.now(timezone.utc).isoformat(),
                "rows_read": stats["rows_read"],
                "rows_written": stats["rows_written"],
                "raw_requests": stats["raw_requests"],
                "rollup_requests": stats["rollup_requests"],
            })
        summaries.append(stats.pop("summary"))
        report["windows"] += 1
        report["requests"] += stats["rollup_requests"]
        report["rows_written"] += stats["rows_written"]
        report["reconciled"] = report["reconciled"] and stats["reconciled"]
        report["windows_detail"].append(stats)
        print(
            f"window {stats['window_start']} .. {stats['window_end']}: "
            f"requests={stats['rollup_requests']} raw={stats['raw_requests']} "
            f"rollup_rows={stats['rollup_rows']} client_rows={stats['client_rows']} "
            f"school_rows={stats['school_rows']} reconciled={stats['reconciled']}",
            flush=True,
        )

    report["summary"] = merge_summaries(summaries)
    report["third_party_requests"] = report["summary"].get("by_classification", {}).get(classify.THIRD_PARTY, 0)
    report["queries_made"] = logs.queries_made
    if db is not None:
        db.rpc("api_usage_prune", {})
    return report


def heartbeat_summary(report: dict) -> dict:
    keys = ("windows", "requests", "third_party_requests", "mode", "rows_written",
            "lag_hours", "reconciled", "dry_run")
    return {key: report[key] for key in keys if report.get(key) is not None}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--mode", choices=("hourly", "backfill"), default="hourly")
    parser.add_argument("--days", type=int, default=7, help="backfill length in days (1-89)")
    parser.add_argument("--slice-hours", type=int, default=24)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--out-json", type=Path, help="counts-only report")
    parser.add_argument("--heartbeat-json", type=Path, help="heartbeat summary for record_heartbeat.py")
    args = parser.parse_args(argv)
    if not 1 <= args.slice_hours <= 24:
        parser.error("--slice-hours must be between 1 and 24")

    try:
        report = run(args)
    except (IngestError, LogsApiError) as exc:
        print(f"::error::api usage ingest failed: {redact(str(exc))}", file=sys.stderr)
        return 1
    except Exception as exc:  # noqa: BLE001 — never let a traceback print row data
        print(f"::error::api usage ingest failed: {type(exc).__name__}", file=sys.stderr)
        return 1

    if args.out_json:
        args.out_json.parent.mkdir(parents=True, exist_ok=True)
        args.out_json.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if args.heartbeat_json:
        args.heartbeat_json.parent.mkdir(parents=True, exist_ok=True)
        args.heartbeat_json.write_text(json.dumps(heartbeat_summary(report)) + "\n", encoding="utf-8")
    print(json.dumps({key: report[key] for key in (
        "mode", "dry_run", "windows", "requests", "third_party_requests",
        "rows_written", "reconciled", "retention_ok", "queries_made",
    )}), flush=True)

    if report["retention_ok"] is False:
        print("::error::gateway log retention is under 7 days; the hourly job cannot catch up after an outage", file=sys.stderr)
        return 3
    if not report["reconciled"]:
        print("::warning::rollup totals differ from raw log counts by more than 0.1%", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
