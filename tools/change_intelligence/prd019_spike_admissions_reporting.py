#!/usr/bin/env python3
"""PRD 019 pre-PRD spike: admissions/reporting deltas.

This intentionally uses the existing public school_browser_rows projection
instead of raw cds_fields. The spike goal is editorial signal discovery, not a
new production projector.

Outputs:
  .context/reports/prd019_admissions_reporting_spike.csv
  .context/reports/prd019_admissions_reporting_spike.md
"""

from __future__ import annotations

import csv
import json
import math
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlencode
from urllib.request import Request, urlopen


REPO_ROOT = Path(__file__).resolve().parents[2]
OUT_DIR = REPO_ROOT / ".context" / "reports"
CSV_OUT = OUT_DIR / "prd019_admissions_reporting_spike.csv"
MD_OUT = OUT_DIR / "prd019_admissions_reporting_spike.md"

PUBLIC_SUPABASE_URL = "https://api.collegedata.fyi"
YEARS = (2024, 2025)

SELECT_COLUMNS = [
    "document_id",
    "school_id",
    "school_name",
    "sub_institutional",
    "canonical_year",
    "year_start",
    "source_format",
    "producer",
    "producer_version",
    "data_quality_flag",
    "archive_url",
    "applied",
    "admitted",
    "enrolled_first_year",
    "acceptance_rate",
    "yield_rate",
    "sat_submit_rate",
    "act_submit_rate",
    "sat_composite_p25",
    "sat_composite_p50",
    "sat_composite_p75",
    "act_composite_p25",
    "act_composite_p50",
    "act_composite_p75",
    "ed_offered",
    "ed_applicants",
    "ed_admitted",
    "admission_strategy_card_quality",
]


def read_env_file(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    env: dict[str, str] = {}
    for raw in path.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        env[key.strip()] = value.strip().strip('"').strip("'")
    return env


def load_env() -> dict[str, str]:
    env = dict(os.environ)
    for path in (
        REPO_ROOT / ".env",
        REPO_ROOT / "web" / ".env.local",
        Path("/Users/santhonys/Projects/Owen/colleges/collegedata-fyi/web/.env.local"),
    ):
        for key, value in read_env_file(path).items():
            env.setdefault(key, value)
    return env


def fetch_rows() -> list[dict[str, Any]]:
    env = load_env()
    base_url = (
        env.get("SUPABASE_URL")
        or env.get("NEXT_PUBLIC_SUPABASE_URL")
        or PUBLIC_SUPABASE_URL
    ).rstrip("/")
    anon_key = env.get("SUPABASE_ANON_KEY") or env.get("NEXT_PUBLIC_SUPABASE_ANON_KEY")
    if not anon_key:
        raise SystemExit(
            "Missing SUPABASE_ANON_KEY or NEXT_PUBLIC_SUPABASE_ANON_KEY. "
            "Set it in env or web/.env.local."
        )

    params = {
        "select": ",".join(SELECT_COLUMNS),
        "year_start": f"in.({','.join(str(y) for y in YEARS)})",
        "sub_institutional": "is.null",
        "order": "school_id.asc,year_start.asc",
    }
    url = f"{base_url}/rest/v1/school_browser_rows?{urlencode(params)}"
    rows: list[dict[str, Any]] = []
    offset = 0
    page_size = 1000
    while True:
        req = Request(
            url,
            headers={
                "apikey": anon_key,
                "Authorization": f"Bearer {anon_key}",
                "Range-Unit": "items",
                "Range": f"{offset}-{offset + page_size - 1}",
            },
        )
        with urlopen(req, timeout=60) as res:
            page = json.loads(res.read().decode("utf-8"))
        if not page:
            break
        rows.extend(page)
        if len(page) < page_size:
            break
        offset += page_size
    return rows


def as_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        n = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(n):
        return None
    return n


def as_int(value: Any) -> int | None:
    n = as_float(value)
    return int(n) if n is not None else None


def pp(value: float | None) -> str:
    if value is None:
        return ""
    return f"{value * 100:.1f}%"


def fmt_num(value: float | int | None) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and not value.is_integer():
        return f"{value:.4f}"
    return str(int(value))


def has_any(row: dict[str, Any], keys: list[str]) -> bool:
    return any(row.get(key) is not None for key in keys)


@dataclass
class Event:
    school_id: str
    school_name: str
    ipeds_id: str
    metric: str
    event_type: str
    prior_year: str
    latest_year: str
    prior_value: str
    latest_value: str
    delta: str
    abs_delta_for_sort: float
    prior_source_format: str
    latest_source_format: str
    prior_producer: str
    latest_producer: str
    prior_quality: str
    latest_quality: str
    prior_archive_url: str
    latest_archive_url: str
    comparability: str
    notes: str


def event_base(prior: dict[str, Any], latest: dict[str, Any], metric: str, event_type: str) -> dict[str, Any]:
    return {
        "school_id": latest["school_id"],
        "school_name": latest["school_name"],
        "ipeds_id": latest.get("ipeds_id") or "",
        "metric": metric,
        "event_type": event_type,
        "prior_year": prior["canonical_year"],
        "latest_year": latest["canonical_year"],
        "prior_source_format": prior.get("source_format") or "",
        "latest_source_format": latest.get("source_format") or "",
        "prior_producer": prior.get("producer") or "",
        "latest_producer": latest.get("producer") or "",
        "prior_quality": prior.get("data_quality_flag") or "",
        "latest_quality": latest.get("data_quality_flag") or "",
        "prior_archive_url": prior.get("archive_url") or "",
        "latest_archive_url": latest.get("archive_url") or "",
        "comparability": comparability(prior, latest),
    }


def comparability(prior: dict[str, Any], latest: dict[str, Any]) -> str:
    bad_flags = {"wrong_file", "blank_template", "low_coverage"}
    if prior.get("data_quality_flag") in bad_flags or latest.get("data_quality_flag") in bad_flags:
        return "quality_flagged"
    if (prior.get("producer") or "") != (latest.get("producer") or ""):
        return "producer_changed"
    if (prior.get("source_format") or "") != (latest.get("source_format") or ""):
        return "format_changed"
    return "clean"


def rate_event(prior: dict[str, Any], latest: dict[str, Any], metric: str, column: str) -> Event | None:
    old = as_float(prior.get(column))
    new = as_float(latest.get(column))
    if old is None or new is None:
        return None
    delta = new - old
    return Event(
        **event_base(prior, latest, metric, "rate_delta"),
        prior_value=pp(old),
        latest_value=pp(new),
        delta=f"{delta * 100:+.1f} pp",
        abs_delta_for_sort=abs(delta),
        notes="",
    )


def count_event(prior: dict[str, Any], latest: dict[str, Any], metric: str, column: str) -> Event | None:
    old = as_int(prior.get(column))
    new = as_int(latest.get(column))
    if old is None or new is None:
        return None
    delta = new - old
    return Event(
        **event_base(prior, latest, metric, "count_delta"),
        prior_value=fmt_num(old),
        latest_value=fmt_num(new),
        delta=f"{delta:+d}",
        abs_delta_for_sort=abs(delta),
        notes="",
    )


def ed_admit_rate_event(prior: dict[str, Any], latest: dict[str, Any]) -> Event | None:
    old_apps = as_int(prior.get("ed_applicants"))
    old_admits = as_int(prior.get("ed_admitted"))
    new_apps = as_int(latest.get("ed_applicants"))
    new_admits = as_int(latest.get("ed_admitted"))
    if not old_apps or old_admits is None or not new_apps or new_admits is None:
        return None
    old = old_admits / old_apps
    new = new_admits / new_apps
    delta = new - old
    return Event(
        **event_base(prior, latest, "ED admit rate", "rate_delta"),
        prior_value=pp(old),
        latest_value=pp(new),
        delta=f"{delta * 100:+.1f} pp",
        abs_delta_for_sort=abs(delta),
        notes=f"prior ED {old_admits}/{old_apps}; latest ED {new_admits}/{new_apps}",
    )


def reporting_event(
    prior: dict[str, Any],
    latest: dict[str, Any],
    metric: str,
    keys: list[str],
) -> Event | None:
    old = has_any(prior, keys)
    new = has_any(latest, keys)
    if old == new:
        return None
    event_type = "newly_missing" if old and not new else "newly_reported"
    return Event(
        **event_base(prior, latest, metric, event_type),
        prior_value="reported" if old else "missing",
        latest_value="reported" if new else "missing",
        delta=event_type,
        abs_delta_for_sort=1.0,
        notes="candidate only; requires source-PDF human review",
    )


def score_range_delta(
    prior: dict[str, Any],
    latest: dict[str, Any],
    metric: str,
    keys: list[str],
) -> Event | None:
    old_values = [as_int(prior.get(k)) for k in keys]
    new_values = [as_int(latest.get(k)) for k in keys]
    if any(v is None for v in old_values + new_values):
        return None
    deltas = [n - o for o, n in zip(old_values, new_values) if o is not None and n is not None]
    max_abs = max(abs(d) for d in deltas)
    if max_abs == 0:
        return None
    return Event(
        **event_base(prior, latest, metric, "score_range_delta"),
        prior_value="/".join(fmt_num(v) for v in old_values),
        latest_value="/".join(fmt_num(v) for v in new_values),
        delta="/".join(f"{d:+d}" for d in deltas),
        abs_delta_for_sort=float(max_abs),
        notes="",
    )


def entity_id(row: dict[str, Any]) -> str:
    return str(row.get("ipeds_id") or row["school_id"])


def dedupe_years(rows: list[dict[str, Any]]) -> dict[tuple[str, int], dict[str, Any]]:
    # school_browser_rows is one row per document. If a school has more than one
    # primary row for a year, prefer non-low-quality rows, then newer updated_at
    # is unavailable from the public select, so fall back to lexical document id.
    out: dict[tuple[str, int], dict[str, Any]] = {}
    for row in rows:
        key = (entity_id(row), int(row["year_start"]))
        current = out.get(key)
        if current is None:
            out[key] = row
            continue
        current_bad = current.get("data_quality_flag") in {"wrong_file", "blank_template", "low_coverage"}
        row_bad = row.get("data_quality_flag") in {"wrong_file", "blank_template", "low_coverage"}
        if current_bad and not row_bad:
            out[key] = row
    return out


def build_events(rows: list[dict[str, Any]]) -> tuple[list[Event], int]:
    by_year = dedupe_years(rows)
    schools = sorted({school for school, _year in by_year})
    comparable = 0
    events: list[Event] = []
    for school_id in schools:
        prior = by_year.get((school_id, 2024))
        latest = by_year.get((school_id, 2025))
        if not prior or not latest:
            continue
        comparable += 1
        candidates = [
            rate_event(prior, latest, "Admit rate", "acceptance_rate"),
            rate_event(prior, latest, "Yield rate", "yield_rate"),
            count_event(prior, latest, "ED applicants", "ed_applicants"),
            count_event(prior, latest, "ED admits", "ed_admitted"),
            ed_admit_rate_event(prior, latest),
            rate_event(prior, latest, "SAT submit rate", "sat_submit_rate"),
            rate_event(prior, latest, "ACT submit rate", "act_submit_rate"),
            reporting_event(
                prior,
                latest,
                "SAT composite range reporting",
                ["sat_composite_p25", "sat_composite_p50", "sat_composite_p75"],
            ),
            reporting_event(
                prior,
                latest,
                "ACT composite range reporting",
                ["act_composite_p25", "act_composite_p50", "act_composite_p75"],
            ),
            score_range_delta(
                prior,
                latest,
                "SAT composite range",
                ["sat_composite_p25", "sat_composite_p50", "sat_composite_p75"],
            ),
            score_range_delta(
                prior,
                latest,
                "ACT composite range",
                ["act_composite_p25", "act_composite_p50", "act_composite_p75"],
            ),
        ]
        events.extend(e for e in candidates if e is not None)
    return events, comparable


def write_csv(events: list[Event]) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    fieldnames = list(Event.__dataclass_fields__.keys())
    with CSV_OUT.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for event in events:
            writer.writerow(event.__dict__)


def top_by_metric(events: list[Event], metric: str, limit: int = 10) -> list[Event]:
    subset = [e for e in events if e.metric == metric]
    return sorted(subset, key=lambda e: e.abs_delta_for_sort, reverse=True)[:limit]


def is_clean(event: Event) -> bool:
    return event.comparability == "clean"


def write_summary(events: list[Event], comparable: int, total_rows: int) -> None:
    reporting = [e for e in events if e.event_type in {"newly_missing", "newly_reported"}]
    clean_events = [e for e in events if is_clean(e)]
    top = sorted(clean_events, key=lambda e: e.abs_delta_for_sort, reverse=True)[:50]
    noisy = [e for e in events if not is_clean(e)]
    lines = [
        "# PRD 019 admissions/reporting spike",
        "",
        "This is a cheap signal-discovery pass over public `school_browser_rows`, not the final change-intelligence projector.",
        "",
        f"- Source rows fetched: {total_rows}",
        f"- Schools with primary 2024-25 and 2025-26 rows: {comparable}",
        f"- Candidate events written: {len(events)}",
        f"- Clean comparable events: {len(clean_events)}",
        f"- Noisy/provenance/quality-gated events: {len(noisy)}",
        f"- Reporting-status candidate events requiring human review: {len(reporting)}",
        f"- CSV: `{CSV_OUT.relative_to(REPO_ROOT)}`",
        "",
        "## Top 50 candidate events",
        "",
        "This table only includes events where producer, source format, and document quality are comparable. Noisy events remain in the CSV.",
        "",
        "| School | Metric | Event | Prior | Latest | Delta | Notes |",
        "|---|---:|---|---:|---:|---:|---|",
    ]
    for e in top:
        lines.append(
            f"| {e.school_name} | {e.metric} | {e.event_type} | "
            f"{e.prior_value} | {e.latest_value} | {e.delta} | {e.notes} |"
        )
    for metric in ["Admit rate", "Yield rate", "SAT submit rate", "ACT submit rate"]:
        metric_top = top_by_metric(clean_events, metric, 8)
        if not metric_top:
            continue
        lines.extend(["", f"## Largest {metric} moves", ""])
        for e in metric_top:
            lines.append(f"- {e.school_name}: {e.prior_value} -> {e.latest_value} ({e.delta})")
    if reporting:
        lines.extend(["", "## Reporting-status candidates", ""])
        for e in sorted(reporting, key=lambda item: (item.comparability, item.metric, item.school_name))[:50]:
            lines.append(
                f"- {e.school_name}: {e.metric} {e.prior_value} -> {e.latest_value} "
                f"({e.comparability})"
            )
    if noisy:
        lines.extend(["", "## Noisy top events gated out of the clean table", ""])
        for e in sorted(noisy, key=lambda item: item.abs_delta_for_sort, reverse=True)[:20]:
            lines.append(
                f"- {e.school_name}: {e.metric} {e.prior_value} -> {e.latest_value} "
                f"({e.delta}; {e.comparability}; {e.prior_producer} -> {e.latest_producer})"
            )
    MD_OUT.write_text("\n".join(lines) + "\n")


def main() -> int:
    rows = fetch_rows()
    events, comparable = build_events(rows)
    events = sorted(events, key=lambda e: e.abs_delta_for_sort, reverse=True)
    write_csv(events)
    write_summary(events, comparable, len(rows))
    print(f"fetched_rows={len(rows)}")
    print(f"comparable_schools={comparable}")
    print(f"events={len(events)}")
    print(f"csv={CSV_OUT}")
    print(f"summary={MD_OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
