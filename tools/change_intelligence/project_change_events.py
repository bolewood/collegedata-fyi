#!/usr/bin/env python3
"""PRD 019 deterministic CDS change-event projector.

The first production slice compares selected primary `school_browser_rows`
between adjacent years, applies field-specific rules from `rules.yaml`, and
writes generated rows to `cds_field_change_events` when `--apply` is supplied.

The pure classification functions are intentionally importable for unit tests;
database access is kept at the CLI boundary.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:  # pragma: no cover - CI and operator venvs include PyYAML.
    yaml = None


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_RULES = REPO_ROOT / "tools" / "change_intelligence" / "rules.yaml"
DEFAULT_WATCHLIST = REPO_ROOT / "data" / "watchlists" / "change_intelligence_calibration.yaml"
DEFAULT_REPORT_DIR = REPO_ROOT / ".context" / "reports"

BAD_FLAGS = {"wrong_file", "blank_template", "low_coverage"}
PRODUCER_FAMILY = {
    "tier1_xlsx": "tier1",
    "tier2_acroform": "tier2",
    "tier4_docling": "tier4",
    "tier6_html": "tier6",
}


@dataclass(frozen=True)
class FieldRule:
    key: str
    label: str
    family: str
    column: str
    value_kind: str
    thresholds: dict[str, Any]


def read_env_file(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    out: dict[str, str] = {}
    for raw in path.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        out[key.strip()] = value.strip().strip('"').strip("'")
    return out


def load_env(path: Path | None = None) -> dict[str, str]:
    env = dict(os.environ)
    for candidate in (
        path,
        REPO_ROOT / ".env",
        Path("/Users/santhonys/Projects/Owen/colleges/collegedata-fyi/.env"),
    ):
        if candidate:
            env.update({k: v for k, v in read_env_file(candidate).items() if k not in env})
    return env


def load_yaml(path: Path) -> dict[str, Any]:
    if yaml is None:
        raise RuntimeError("PyYAML is required to read change-intelligence config")
    return yaml.safe_load(path.read_text()) or {}


def load_rules(path: Path = DEFAULT_RULES) -> tuple[dict[str, Any], dict[str, FieldRule]]:
    raw = load_yaml(path)
    fields = {
        key: FieldRule(
            key=key,
            label=str(spec["label"]),
            family=str(spec["family"]),
            column=str(spec["column"]),
            value_kind=str(spec["value_kind"]),
            thresholds=dict(spec.get("thresholds") or {}),
        )
        for key, spec in (raw.get("fields") or {}).items()
    }
    return raw, fields


def load_watchlist(path: Path | None) -> set[str] | None:
    if not path:
        return None
    raw = load_yaml(path)
    schools = raw.get("schools") or []
    ids = {
        str(item["school_id"] if isinstance(item, dict) else item)
        for item in schools
        if item
    }
    return ids or None


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


def reported(value: Any) -> bool:
    return as_float(value) is not None if isinstance(value, (int, float, str)) else value is not None


def producer_family(producer: str | None) -> str:
    if not producer:
        return ""
    return PRODUCER_FAMILY.get(producer, producer.split("_", 1)[0])


def compatible_producer_version(prior: dict[str, Any], latest: dict[str, Any]) -> bool:
    return (
        producer_family(prior.get("producer")) == producer_family(latest.get("producer"))
        and (prior.get("producer_version") or "") == (latest.get("producer_version") or "")
    )


def selectivity_band(prior_admit_rate: Any, rules: dict[str, Any]) -> str:
    rate = as_float(prior_admit_rate)
    if rate is None:
        return "unknown_selectivity"
    bands = rules.get("selectivity_bands") or {}
    for name in ("high_selectivity", "selective", "broad_access"):
        spec = bands.get(name) or {}
        min_rate = spec.get("min_admit_rate")
        max_rate = spec.get("max_admit_rate")
        if min_rate is not None and rate < float(min_rate):
            continue
        if max_rate is not None and rate >= float(max_rate):
            continue
        return name
    return "unknown_selectivity"


def threshold_for(rule: FieldRule, band: str) -> tuple[str, dict[str, Any]]:
    if rule.value_kind == "rate":
        spec = rule.thresholds.get(band) or rule.thresholds.get("default") or {}
        return band if band in rule.thresholds else "default", spec
    spec = rule.thresholds.get("default") or {}
    return "default", spec


def severity_for_delta(rule: FieldRule, old: float, new: float, band: str) -> tuple[str, str, float | None]:
    delta = new - old
    abs_delta = abs(delta)
    rule_name, spec = threshold_for(rule, band)
    relative = None
    severity = "watch"
    if rule.value_kind == "rate":
        if abs_delta >= float(spec.get("major_pp", math.inf)):
            severity = "major"
        elif abs_delta >= float(spec.get("notable_pp", math.inf)):
            severity = "notable"
    else:
        denom = abs(old)
        if denom:
            relative = abs_delta / denom
        min_denominator = float(spec.get("min_denominator", 0) or 0)
        major = abs_delta >= float(spec.get("major_abs", math.inf))
        notable = abs_delta >= float(spec.get("notable_abs", math.inf))
        if relative is not None and denom >= min_denominator:
            major = major or relative >= float(spec.get("major_relative", math.inf))
            notable = notable or relative >= float(spec.get("notable_relative", math.inf))
        if major:
            severity = "major"
        elif notable:
            severity = "notable"
    return severity, rule_name, relative


def cap_severity(severity: str, cap: str) -> str:
    order = {"watch": 0, "notable": 1, "major": 2}
    if order[severity] > order[cap]:
        return cap
    return severity


def format_value(value: Any, kind: str) -> str | None:
    n = as_float(value)
    if n is None:
        return None
    if kind == "rate":
        return f"{n * 100:.1f}%"
    if float(n).is_integer():
        return str(int(n))
    return f"{n:.2f}"


def event_id(parts: list[Any]) -> str:
    raw = "|".join("" if part is None else str(part) for part in parts)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]


def evidence(
    prior: dict[str, Any],
    latest: dict[str, Any],
    old: Any,
    new: Any,
    threshold_rule: str,
    absolute_delta: float | None,
    relative_delta: float | None,
    caveats: list[str],
) -> dict[str, Any]:
    same_family = producer_family(prior.get("producer")) == producer_family(latest.get("producer"))
    return {
        "from_value": {
            "num": as_float(old),
            "text": None if old is None else str(old),
            "status": "reported" if reported(old) else "missing",
        },
        "to_value": {
            "num": as_float(new),
            "text": None if new is None else str(new),
            "status": "reported" if reported(new) else "missing",
        },
        "from_producer": prior.get("producer") or "",
        "to_producer": latest.get("producer") or "",
        "from_source_provenance": prior.get("source_provenance"),
        "to_source_provenance": latest.get("source_provenance"),
        "threshold_rule_fired": threshold_rule,
        "computed_delta": {
            "absolute": absolute_delta,
            "percentage_points": absolute_delta * 100 if absolute_delta is not None else None,
            "relative_pct": relative_delta * 100 if relative_delta is not None else None,
        },
        "comparability": {
            "same_canonical_field": True,
            "same_producer_family": same_family,
            "compatible_producer_version": compatible_producer_version(prior, latest),
            "same_source_provenance": (prior.get("source_provenance") or None) == (latest.get("source_provenance") or None),
        },
        "caveats": caveats,
    }


def base_event(
    prior: dict[str, Any],
    latest: dict[str, Any],
    rule: FieldRule,
    event_type: str,
    severity: str,
    old: Any,
    new: Any,
    absolute_delta: float | None,
    relative_delta: float | None,
    threshold_rule: str,
    summary: str,
    caveats: list[str],
) -> dict[str, Any]:
    verification = "candidate" if severity == "major" or event_type == "newly_missing" else "not_required"
    return {
        "id": event_id([
            latest.get("school_id"), rule.key, prior.get("canonical_year"),
            latest.get("canonical_year"), event_type,
        ]),
        "school_id": latest.get("school_id"),
        "school_name": latest.get("school_name"),
        "ipeds_id": latest.get("ipeds_id"),
        "field_key": rule.key,
        "field_label": rule.label,
        "field_family": rule.family,
        "from_document_id": prior.get("document_id"),
        "to_document_id": latest.get("document_id"),
        "from_year": prior.get("canonical_year"),
        "to_year": latest.get("canonical_year"),
        "from_year_start": prior.get("year_start"),
        "to_year_start": latest.get("year_start"),
        "event_type": event_type,
        "severity": severity,
        "from_value": format_value(old, rule.value_kind),
        "to_value": format_value(new, rule.value_kind),
        "from_value_numeric": as_float(old),
        "to_value_numeric": as_float(new),
        "absolute_delta": absolute_delta,
        "relative_delta": relative_delta,
        "threshold_rule": threshold_rule,
        "summary": summary,
        "from_producer": prior.get("producer"),
        "to_producer": latest.get("producer"),
        "from_producer_version": prior.get("producer_version"),
        "to_producer_version": latest.get("producer_version"),
        "from_source_provenance": prior.get("source_provenance"),
        "to_source_provenance": latest.get("source_provenance"),
        "from_archive_url": prior.get("archive_url"),
        "to_archive_url": latest.get("archive_url"),
        "from_source_url": prior.get("source_url"),
        "to_source_url": latest.get("source_url"),
        "evidence_json": evidence(prior, latest, old, new, threshold_rule, absolute_delta, relative_delta, caveats),
        "verification_status": verification,
        "public_visible": False,
    }


def classify_field_change(
    prior: dict[str, Any],
    latest: dict[str, Any],
    rule: FieldRule,
    rules: dict[str, Any],
    had_earlier_reported: bool = False,
) -> dict[str, Any] | None:
    old = prior.get(rule.column)
    new = latest.get(rule.column)
    old_reported = reported(old)
    new_reported = reported(new)
    if not old_reported and not new_reported:
        return None

    caveats: list[str] = []
    prior_bad = prior.get("data_quality_flag") in BAD_FLAGS
    latest_bad = latest.get("data_quality_flag") in BAD_FLAGS
    if latest_bad and not prior_bad:
        return base_event(
            prior, latest, rule, "quality_regression", "watch", old, new, None, None,
            "quality_flag_changed",
            f"{latest.get('school_name')} has a newer quality flag blocking clean comparison for {rule.label}.",
            ["latest document has data_quality_flag"],
        )
    if prior_bad and not latest_bad and new_reported:
        return base_event(
            prior, latest, rule, "quality_recovered", "watch", old, new, None, None,
            "quality_flag_changed",
            f"{latest.get('school_name')} recovered usable extraction quality for {rule.label}.",
            ["prior document had data_quality_flag"],
        )
    if prior_bad or latest_bad:
        return None

    same_producer_family = producer_family(prior.get("producer")) == producer_family(latest.get("producer"))
    same_format = (prior.get("source_format") or "") == (latest.get("source_format") or "")
    same_provenance = (prior.get("source_provenance") or None) == (latest.get("source_provenance") or None)

    if old_reported and not new_reported:
        if not same_producer_family or not compatible_producer_version(prior, latest):
            event_type = "format_changed" if not same_format else "producer_changed"
            return base_event(
                prior, latest, rule, event_type, "watch", old, new, None, None,
                "producer_or_format_changed",
                f"{latest.get('school_name')} no longer has comparable extracted {rule.label}; producer or format changed.",
                ["not classified as school-side silence without human review"],
            )
        event_type = "newly_missing"
        severity = "notable" if rule.value_kind.startswith("score") or rule.value_kind == "rate" else "watch"
        return base_event(
            prior, latest, rule, event_type, severity, old, new, None, None,
            "reported_to_missing",
            f"{latest.get('school_name')} reported {rule.label} in {prior.get('canonical_year')} but it is missing in {latest.get('canonical_year')}.",
            ["candidate silence; source PDF review required"],
        )

    if not old_reported and new_reported:
        event_type = "reappeared" if had_earlier_reported else "newly_reported"
        return base_event(
            prior, latest, rule, event_type, "watch", old, new, None, None,
            "missing_to_reported",
            f"{latest.get('school_name')} now reports {rule.label} in {latest.get('canonical_year')}.",
            [],
        )

    old_n = as_float(old)
    new_n = as_float(new)
    if old_n is None or new_n is None or old_n == new_n:
        return None

    band = selectivity_band(prior.get("acceptance_rate"), rules)
    severity, rule_name, relative = severity_for_delta(rule, old_n, new_n, band)
    if not same_provenance:
        severity = cap_severity(severity, str((rules.get("global") or {}).get("source_provenance_severity_cap") or "watch"))
        caveats.append("source provenance changed across compared years")
    delta = new_n - old_n
    delta_text = f"{delta * 100:+.1f} percentage points" if rule.value_kind == "rate" else f"{delta:+.0f}"
    return base_event(
        prior, latest, rule, "material_delta", severity, old, new, abs(delta), relative,
        f"{rule.key}:{rule_name}:{band}",
        f"{latest.get('school_name')} changed {rule.label} by {delta_text} from {prior.get('canonical_year')} to {latest.get('canonical_year')}.",
        caveats,
    )


def enrich_rows_with_documents(client: Any, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    doc_ids = sorted({row["document_id"] for row in rows if row.get("document_id")})
    docs: dict[str, dict[str, Any]] = {}
    for i in range(0, len(doc_ids), 100):
        page = (
            client.table("cds_documents")
            .select("id,source_provenance,source_url,source_sha256")
            .in_("id", doc_ids[i:i + 100])
            .execute()
            .data
            or []
        )
        docs.update({row["id"]: row for row in page})
    for row in rows:
        doc = docs.get(row.get("document_id")) or {}
        row["source_provenance"] = doc.get("source_provenance")
        row["source_url"] = doc.get("source_url")
        row["source_sha256"] = doc.get("source_sha256")
    return rows


def row_rank(row: dict[str, Any]) -> tuple[int, int, str]:
    bad = 1 if row.get("data_quality_flag") in BAD_FLAGS else 0
    provenance = 0 if row.get("source_provenance") in ("school_direct", "operator_manual") else 1
    return bad, provenance, str(row.get("document_id") or "")


def select_primary_rows(rows: list[dict[str, Any]]) -> dict[tuple[str, int], dict[str, Any]]:
    grouped: dict[tuple[str, int], list[dict[str, Any]]] = {}
    for row in rows:
        if row.get("sub_institutional") is not None:
            continue
        if row.get("year_start") is None:
            continue
        grouped.setdefault((str(row["school_id"]), int(row["year_start"])), []).append(row)
    return {key: sorted(values, key=row_rank)[0] for key, values in grouped.items()}


def build_events(
    rows: list[dict[str, Any]],
    rules: dict[str, Any],
    field_rules: dict[str, FieldRule],
    from_year: int,
    to_year: int,
) -> list[dict[str, Any]]:
    selected = select_primary_rows(rows)
    schools = sorted({school_id for school_id, _year in selected})
    events: list[dict[str, Any]] = []
    for school_id in schools:
        prior = selected.get((school_id, from_year))
        latest = selected.get((school_id, to_year))
        if not prior or not latest:
            continue
        for rule in field_rules.values():
            earlier_reported = any(
                y < from_year and reported(row.get(rule.column))
                for (sid, y), row in selected.items()
                if sid == school_id
            )
            event = classify_field_change(prior, latest, rule, rules, earlier_reported)
            if event:
                events.append(event)
    events.sort(key=lambda e: (
        {"major": 0, "notable": 1, "watch": 2}.get(e["severity"], 9),
        e["school_id"],
        e["field_key"],
    ))
    return events


def fetch_browser_rows(
    client: Any,
    field_rules: dict[str, FieldRule],
    watchlist: set[str] | None,
    min_year: int,
    max_year: int,
) -> list[dict[str, Any]]:
    columns = [
        "document_id", "school_id", "school_name", "sub_institutional", "ipeds_id",
        "canonical_year", "year_start", "schema_version", "source_format",
        "producer", "producer_version", "data_quality_flag", "archive_url",
    ]
    columns += sorted({rule.column for rule in field_rules.values()})
    query = (
        client.table("school_browser_rows")
        .select(",".join(columns))
        .gte("year_start", min_year)
        .lte("year_start", max_year)
        .is_("sub_institutional", "null")
        .order("school_id")
    )
    if watchlist:
        query = query.in_("school_id", sorted(watchlist))
    rows = query.execute().data or []
    return enrich_rows_with_documents(client, rows)


def write_csv(events: list[dict[str, Any]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not events:
        path.write_text("")
        return
    fieldnames = [key for key in events[0].keys() if key != "evidence_json"] + ["evidence_json"]
    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for event in events:
            row = dict(event)
            row["evidence_json"] = json.dumps(row["evidence_json"], sort_keys=True)
            writer.writerow(row)


def write_report(events: list[dict[str, Any]], path: Path, from_year: int, to_year: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        f"# CDS change intelligence events: {from_year}-{str(from_year + 1)[-2:]} to {to_year}-{str(to_year + 1)[-2:]}",
        "",
        "Generated by `tools/change_intelligence/project_change_events.py`.",
        "",
        f"- Events: {len(events)}",
        f"- Major: {sum(1 for e in events if e['severity'] == 'major')}",
        f"- Notable: {sum(1 for e in events if e['severity'] == 'notable')}",
        f"- Watch: {sum(1 for e in events if e['severity'] == 'watch')}",
        f"- Human-review candidates: {sum(1 for e in events if e['verification_status'] == 'candidate')}",
        "",
        "| School | Field | Type | Severity | From | To | Summary |",
        "|---|---|---|---|---:|---:|---|",
    ]
    for event in events[:100]:
        lines.append(
            f"| {event['school_name'] or event['school_id']} | {event['field_label']} | "
            f"{event['event_type']} | {event['severity']} | {event.get('from_value') or ''} | "
            f"{event.get('to_value') or ''} | {event['summary']} |"
        )
    path.write_text("\n".join(lines) + "\n")


def persist_events(client: Any, events: list[dict[str, Any]], to_year: int, watchlist: set[str] | None) -> None:
    existing_status: dict[str, str] = {}
    event_ids = [event["id"] for event in events]
    for i in range(0, len(event_ids), 100):
        rows = (
            client.table("cds_field_change_events")
            .select("id,verification_status")
            .in_("id", event_ids[i:i + 100])
            .execute()
            .data
            or []
        )
        existing_status.update({row["id"]: row.get("verification_status") for row in rows})
    for event in events:
        status = existing_status.get(event["id"])
        if status in {"confirmed", "extractor_noise", "ambiguous", "not_reportable"}:
            event["verification_status"] = status

    if watchlist:
        schools = sorted(watchlist)
        for i in range(0, len(watchlist), 100):
            (
                client.table("cds_field_change_events")
                .delete()
                .eq("to_year_start", to_year)
                .in_("school_id", schools[i:i + 100])
                .execute()
            )
    else:
        client.table("cds_field_change_events").delete().eq("to_year_start", to_year).execute()
    for i in range(0, len(events), 100):
        client.table("cds_field_change_events").upsert(events[i:i + 100]).execute()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env", type=Path)
    parser.add_argument("--rules", type=Path, default=DEFAULT_RULES)
    parser.add_argument("--watchlist", type=Path, default=DEFAULT_WATCHLIST)
    parser.add_argument("--from-year", type=int, default=2024)
    parser.add_argument("--to-year", type=int, default=2025)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--csv", type=Path, default=DEFAULT_REPORT_DIR / "cds-change-events.csv")
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT_DIR / "cds-change-intelligence-2025-26.md")
    parser.add_argument("--summary-json", type=Path)
    args = parser.parse_args()

    rules, field_rules = load_rules(args.rules)
    watchlist = load_watchlist(args.watchlist)
    env = load_env(args.env)
    try:
        from supabase import create_client
    except ImportError as e:
        raise SystemExit("supabase-py is required for the change projector") from e
    client = create_client(env["SUPABASE_URL"], env["SUPABASE_SERVICE_ROLE_KEY"])

    rows = fetch_browser_rows(client, field_rules, watchlist, args.from_year - 3, args.to_year)
    events = build_events(rows, rules, field_rules, args.from_year, args.to_year)
    write_csv(events, args.csv)
    write_report(events, args.report, args.from_year, args.to_year)
    if args.apply:
        persist_events(client, events, args.to_year, watchlist)

    summary = {
        "rows": len(rows),
        "events": len(events),
        "major": sum(1 for e in events if e["severity"] == "major"),
        "notable": sum(1 for e in events if e["severity"] == "notable"),
        "watch": sum(1 for e in events if e["severity"] == "watch"),
        "human_review_candidates": sum(1 for e in events if e["verification_status"] == "candidate"),
        "applied": args.apply,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
    if args.summary_json:
        args.summary_json.parent.mkdir(parents=True, exist_ok=True)
        args.summary_json.write_text(json.dumps(summary, indent=2, sort_keys=True))
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
