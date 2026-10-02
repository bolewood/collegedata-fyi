"""Turn grouped log rows into api_gateway_* table rows (PRD 032).

Inputs are rows returned by tools/api_usage/queries.py. Outputs are the JSON
payloads for api_usage_replace_window() and api_usage_replace_downloads_day().
Raw IPs and user agents go in and
never come out: client rows carry a salted hash and a product token only.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime
from typing import Callable, Iterable, Mapping

from tools.api_usage import classify as c


def _flag(value: object) -> bool:
    return value in (True, 1, "1", "true", "True")


def _int(value: object) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _iso(hour: datetime) -> str:
    return hour.strftime("%Y-%m-%dT%H:%M:%SZ")


def _edge_signals(row: Mapping[str, object], surface: str, route: str, t0: datetime | None,
                  ua_browser: bool, ua_internal: bool) -> c.Signals:
    return c.Signals(
        role=str(row.get("role") or ""),
        key_prefix=str(row.get("kp") or ""),
        client_info=str(row.get("ci") or ""),
        referer_host=str(row.get("ref") or ""),
        ua_browser=ua_browser,
        ua_internal=ua_internal,
        aws=_flag(row.get("aws")),
        before_t0=c.is_before_t0(c.hour_from_epoch(row["h"]), t0),
        surface=surface,
        route_kind=route,
    )


def _route(row: Mapping[str, object]) -> tuple[str, str]:
    return c.edge_route(
        str(row.get("svc") or ""),
        str(row.get("seg4") or ""),
        str(row.get("seg5") or ""),
        _flag(row.get("is_archive")),
        str(row.get("method") or ""),
    )


def edge_rollups(rows: Iterable[Mapping[str, object]], t0: datetime | None) -> list[dict]:
    totals: dict[tuple, list[int]] = defaultdict(lambda: [0, 0, 0, 0, 0])
    for row in rows:
        ua = str(row.get("ua") or "")
        surface, route = _route(row)
        signals = _edge_signals(row, surface, route, t0, c.ua_is_browser(ua), c.ua_is_internal(ua))
        classification, inferred = c.classify(signals)
        key = (
            _iso(c.hour_from_epoch(row["h"])),
            c.normalize_host(str(row.get("host") or "")),
            surface,
            route,
            classification,
            c.rollup_family(classification, ua, signals.client_info),
            c.status_class(row.get("status")),
            inferred,
        )
        acc = totals[key]
        acc[0] += _int(row.get("n"))
        acc[1] += _int(row.get("downloads"))
        acc[2] += _int(row.get("ranges"))
        acc[3] += _int(row.get("hits"))
        acc[4] += _int(row.get("bytes"))
    return [_rollup_row(key, acc) for key, acc in sorted(totals.items())]


def function_rollups(rows: Iterable[Mapping[str, object]]) -> list[dict]:
    totals: dict[tuple, list[int]] = defaultdict(lambda: [0, 0, 0, 0, 0])
    for row in rows:
        ua = str(row.get("ua") or "")
        surface, route = c.function_route(str(row.get("pathname") or ""), str(row.get("method") or ""))
        signals = c.Signals(
            role=str(row.get("role") or ""),
            ua_browser=c.ua_is_browser(ua),
            ua_internal=c.ua_is_internal(ua) or ua.lower().startswith("pg_net"),
            aws=_flag(row.get("aws")),
            before_t0=False,
            surface=surface,
            route_kind=route,
        )
        classification, inferred = c.classify(signals)
        key = (
            _iso(c.hour_from_epoch(row["h"])),
            "functions",
            surface,
            route,
            classification,
            c.rollup_family(classification, ua, ""),
            c.status_class(row.get("status")),
            inferred,
        )
        acc = totals[key]
        acc[0] += _int(row.get("n"))
        acc[4] += _int(row.get("bytes"))
    return [_rollup_row(key, acc) for key, acc in sorted(totals.items())]


def _rollup_row(key: tuple, acc: list[int]) -> dict:
    hour, host, surface, route, classification, family, status, inferred = key
    return {
        "hour": hour,
        "host": host,
        "surface": surface,
        "route_kind": route,
        "classification": classification,
        "client_family": family,
        "status_class": status,
        "inferred": inferred,
        "requests": acc[0],
        "downloads": acc[1],
        "range_requests": acc[2],
        "cache_hits": acc[3],
        "response_bytes": acc[4],
    }


def edge_schools(rows: Iterable[Mapping[str, object]], t0: datetime | None) -> list[dict]:
    totals: dict[tuple, list[int]] = defaultdict(lambda: [0, 0])
    for row in rows:
        surface, route = _route(row)
        if route == "options_preflight":
            continue
        school = c.school_id_from(str(row.get("school_raw") or ""))
        if not school:
            continue
        signals = _edge_signals(
            row, surface, route, t0, _flag(row.get("ua_browser")), _flag(row.get("ua_internal"))
        )
        classification, _ = c.classify(signals)
        if surface == "storage":
            if route != "archive_file":
                continue
        elif surface == "postgrest":
            if classification not in (c.THIRD_PARTY, c.BROWSER):
                continue
        else:
            continue
        key = (_iso(c.hour_from_epoch(row["h"])), school, surface, classification)
        totals[key][0] += _int(row.get("n"))
        totals[key][1] += _int(row.get("downloads"))
    return [
        {
            "hour": hour,
            "school_id": school,
            "surface": surface,
            "classification": classification,
            "requests": acc[0],
            "downloads": acc[1],
        }
        for (hour, school, surface, classification), acc in sorted(totals.items())
    ]


def edge_clients(
    rows: Iterable[Mapping[str, object]],
    t0: datetime | None,
    salt_for_day: Callable[[str], str],
) -> list[dict]:
    """Non-browser third-party clients. salt_for_day takes 'YYYY-MM-DD'."""
    merged: dict[tuple, dict] = {}
    for row in rows:
        ua = str(row.get("ua") or "")
        surface, route = _route(row)
        signals = _edge_signals(row, surface, route, t0, c.ua_is_browser(ua), c.ua_is_internal(ua))
        classification, _ = c.classify(signals)
        if classification != c.THIRD_PARTY:
            continue
        hour = c.hour_from_epoch(row["h"])
        digest = c.client_hash(
            salt_for_day(hour.strftime("%Y-%m-%d")),
            str(row.get("ip") or ""),
            ua,
            str(row.get("ja4") or ""),
        )
        key = (_iso(hour), digest, surface, route)
        family = c.client_family(ua, signals.client_info)
        name, version = c.client_name_version(ua, family, signals.client_info)
        out = merged.get(key)
        if out is None:
            out = merged[key] = {
                "hour": key[0],
                "client_hash": digest,
                "surface": surface,
                "route_kind": route,
                "client_family": family,
                "client_name": name,
                "client_version": version,
                "user_agent_family": c.user_agent_family(ua),
                "network_owner": c.clean_org(str(row.get("org") or "")),
                "country": c.clean_country(str(row.get("country") or "")),
                "requests": 0,
                "distinct_schools": 0,
                "status_4xx": 0,
                "status_5xx": 0,
                "response_bytes": 0,
            }
        out["requests"] += _int(row.get("n"))
        out["distinct_schools"] = max(out["distinct_schools"], _int(row.get("schools")))
        out["status_4xx"] += _int(row.get("s4"))
        out["status_5xx"] += _int(row.get("s5"))
        out["response_bytes"] += _int(row.get("bytes"))
    return [merged[key] for key in sorted(merged)]


def downloads_daily(rows: Iterable[Mapping[str, object]], day: date) -> tuple[list[dict], int]:
    """api_usage_downloads_daily rows for one day, plus fetches without a valid school id.

    Input rows come from queries.daily_downloads_sql. The user agent is used
    to classify and then dropped.
    """
    totals: dict[tuple, list[int]] = defaultdict(lambda: [0, 0])
    dropped = 0
    for row in rows:
        school = c.school_id_from(str(row.get("school_raw") or ""))
        if not school:
            dropped += _int(row.get("raw"))
            continue
        ua = str(row.get("ua") or "")
        family = c.client_family(ua)
        method = c.access_method(ua, family, _flag(row.get("internal")), _flag(row.get("heavy")))
        if method == "excluded":
            family = "first_party"
        key = (school, method, family, _flag(row.get("fp")))
        totals[key][0] += _int(row.get("uniq"))
        totals[key][1] += _int(row.get("raw"))
    return [
        {
            "day": day.isoformat(),
            "school_id": school,
            "access_method": method,
            "client_family": family,
            "from_site": from_site,
            "unique_downloads": acc[0],
            "raw_downloads": acc[1],
            "method_version": c.DOWNLOADS_METHOD_VERSION,
        }
        for (school, method, family, from_site), acc in sorted(totals.items())
    ], dropped


def summarize_downloads(rows: Iterable[Mapping[str, object]]) -> dict[str, int]:
    """Unique downloads by access method; counts only, safe for public CI logs."""
    out: dict[str, int] = defaultdict(int)
    for row in rows:
        out[str(row["access_method"])] += int(row["unique_downloads"])
    return dict(sorted(out.items()))


def summarize(rollups: Iterable[Mapping[str, object]]) -> dict[str, dict[str, int]]:
    """Counts only; safe for public CI logs."""
    out: dict[str, dict[str, int]] = {
        "by_classification": defaultdict(int),
        "by_surface": defaultdict(int),
        "third_party_by_family": defaultdict(int),
    }
    for row in rollups:
        if row["route_kind"] == "options_preflight":
            continue
        requests = int(row["requests"])
        out["by_classification"][str(row["classification"])] += requests
        out["by_surface"][str(row["surface"])] += requests
        if row["classification"] == c.THIRD_PARTY:
            out["third_party_by_family"][str(row["client_family"])] += requests
    return {key: dict(sorted(value.items())) for key, value in out.items()}
