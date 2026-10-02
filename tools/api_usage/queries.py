"""ClickHouse SQL for the Supabase logs endpoint (PRD 032).

Each query groups raw dimensions; tools/api_usage/classify.py does the
classification in Python. Every query orders by all of its group keys so
LIMIT/OFFSET paging is deterministic (the endpoint truncates at 1,000 rows).
"""

from __future__ import annotations

from datetime import datetime

from tools.api_usage.classify import (
    ARCHIVE_PREFIX,
    FIRST_PARTY_REFERER_HOSTS,
    FRIENDLY_CLIENT_INFO_PREFIX,
    INTERNAL_UA_MARKERS,
    NON_BROWSER_PATTERN,
    SITE_CLIENT_INFO_PREFIX,
    t0_hour,
)

PAGE_SIZE = 1000

_PATH = "log_attributes['request.path']"
_IP = "log_attributes['request.headers.cf_connecting_ip']"
_UA_RAW = "log_attributes['request.headers.user_agent']"
# Python classifies on this same 300-character prefix.
_UA = f"substring({_UA_RAW}, 1, 300)"
_STATUS = "toString(log_attributes['response.status_code'])"
_BYTES = "toUInt64OrZero(log_attributes['response.headers.content_length'])"
_GET = "upper(log_attributes['request.method']) = 'GET'"
_NOT_HEAD = "upper(log_attributes['request.method']) != 'HEAD'"

_HOUR = "toUnixTimestamp(toStartOfHour(timestamp))"
_IS_ARCHIVE = f"startsWith({_PATH}, '{ARCHIVE_PREFIX}')"
_ROLE = "log_attributes['request.sb.jwt.apikey.payload.role']"
_KEY_PREFIX = "substring(log_attributes['request.sb.apikey.apikey.prefix'], 1, 16)"
_CLIENT_INFO = "substring(log_attributes['request.headers.x_client_info'], 1, 80)"
_REFERER = "lower(domain(log_attributes['request.headers.referer']))"
_AWS = "position(lower(log_attributes['request.cf.asOrganization']), 'amazon') > 0"
_UA_BROWSER = (
    f"(startsWith({_UA}, 'Mozilla/') and position({_UA}, '(') > 0"
    f" and not match(lower({_UA}), '{NON_BROWSER_PATTERN}'))"
)
_UA_INTERNAL = "(" + " or ".join(
    f"position(lower({_UA}), '{marker}') > 0" for marker in INTERNAL_UA_MARKERS
) + ")"
_SCHOOL_RAW = (
    f"if({_IS_ARCHIVE}, splitByChar('/', {_PATH})[7], "
    "extract(log_attributes['request.search'], '(?:^|[?&])school_id=eq\\\\.([^&]+)'))"
)

_EDGE_DIMS = [
    ("h", _HOUR),
    ("svc", f"splitByChar('/', {_PATH})[2]"),
    ("seg4", f"splitByChar('/', {_PATH})[4]"),
    ("seg5", f"splitByChar('/', {_PATH})[5]"),
    ("is_archive", _IS_ARCHIVE),
    ("method", "upper(log_attributes['request.method'])"),
    ("role", _ROLE),
    ("kp", _KEY_PREFIX),
    ("ci", _CLIENT_INFO),
    ("ref", _REFERER),
    ("aws", _AWS),
]


def _sql_list(values: tuple[str, ...]) -> str:
    return ", ".join(f"'{value}'" for value in values)


def _before_t0(t0: datetime | None) -> str:
    cutoff = t0_hour(t0)
    if cutoff is None:
        return "1"
    return f"(toStartOfHour(timestamp) <= toDateTime('{cutoff.strftime('%Y-%m-%d %H:%M:%S')}', 'UTC'))"


def not_third_party_condition(t0: datetime | None) -> str:
    """Rows classify() never labels third_party or browser_unattributed.

    Used only to shrink the client and school queries; classify() still runs
    on every returned row, so this must stay a subset of those rules.
    """
    return (
        "("
        f"{_ROLE} = 'service_role'"
        f" or startsWith({_KEY_PREFIX}, 'sb_secret_')"
        f" or {_UA_INTERNAL}"
        f" or startsWith({_CLIENT_INFO}, '{SITE_CLIENT_INFO_PREFIX}')"
        f" or startsWith({_CLIENT_INFO}, '{FRIENDLY_CLIENT_INFO_PREFIX}')"
        f" or {_REFERER} in ({_sql_list(FIRST_PARTY_REFERER_HOSTS)})"
        f" or ({_before_t0(t0)} and {_ROLE} = 'anon' and ("
        f"(startsWith({_CLIENT_INFO}, 'supabase-js-node') and {_AWS})"
        f" or startsWith({_CLIENT_INFO}, 'supabase-js-web')))"
        ")"
    )


def _build(dims: list[tuple[str, str]], metrics: list[tuple[str, str]], where: str) -> str:
    select = ", ".join(f"{expr} as {alias}" for alias, expr in dims + metrics)
    keys = ", ".join(alias for alias, _ in dims)
    return f"select {select} from logs where {where} group by {keys} order by {keys}"


def paged(sql: str, page: int) -> str:
    return f"{sql} limit {PAGE_SIZE} offset {page * PAGE_SIZE}"


def edge_rollup_sql() -> str:
    dims = _EDGE_DIMS + [
        ("host", "lower(log_attributes['request.host'])"),
        ("status", _STATUS),
        ("ua", _UA),
    ]
    metrics = [
        ("n", "count()"),
        ("downloads", f"countIf({_STATUS} = '200' and {_IS_ARCHIVE} and {_GET})"),
        ("ranges", f"countIf({_STATUS} = '206')"),
        ("hits", "countIf(log_attributes['response.headers.cf_cache_status'] = 'HIT')"),
        ("bytes", f"sumIf({_BYTES}, {_NOT_HEAD})"),
    ]
    return _build(dims, metrics, "source = 'edge_logs'")


def edge_schools_sql(t0: datetime | None) -> str:
    dims = _EDGE_DIMS + [
        ("school_raw", _SCHOOL_RAW),
        ("ua_browser", _UA_BROWSER),
        ("ua_internal", _UA_INTERNAL),
    ]
    metrics = [
        ("n", "count()"),
        ("downloads", f"countIf({_STATUS} = '200' and {_IS_ARCHIVE} and {_GET})"),
    ]
    where = (
        "source = 'edge_logs' and ("
        f"{_IS_ARCHIVE}"
        f" or (position(log_attributes['request.search'], 'school_id=eq.') > 0"
        f" and not {not_third_party_condition(t0)})"
        ")"
    )
    return _build(dims, metrics, where)


def edge_clients_sql(t0: datetime | None) -> str:
    dims = _EDGE_DIMS + [
        ("ip", _IP),
        ("ua", _UA),
        ("ja4", "log_attributes['request.cf.botManagement.ja4']"),
        ("org", "substring(log_attributes['request.cf.asOrganization'], 1, 120)"),
        ("country", "substring(log_attributes['request.cf.country'], 1, 2)"),
    ]
    metrics = [
        ("n", "count()"),
        ("schools", f"uniqExactIf({_SCHOOL_RAW}, {_SCHOOL_RAW} != '')"),
        ("s4", f"countIf(startsWith({_STATUS}, '4'))"),
        ("s5", f"countIf(startsWith({_STATUS}, '5'))"),
        ("bytes", f"sumIf({_BYTES}, {_NOT_HEAD})"),
    ]
    where = (
        "source = 'edge_logs'"
        f" and not {not_third_party_condition(t0)}"
        f" and not {_UA_BROWSER}"
    )
    return _build(dims, metrics, where)


def function_rollup_sql() -> str:
    dims = [
        ("h", _HOUR),
        ("pathname", "substring(log_attributes['request.pathname'], 1, 120)"),
        ("method", "upper(log_attributes['request.method'])"),
        ("role", "log_attributes['request.sb.jwt.authorization.payload.role']"),
        ("aws", _AWS),
        ("status", _STATUS),
        ("ua", _UA),
    ]
    metrics = [
        ("n", "count()"),
        ("bytes", f"sumIf({_BYTES}, {_NOT_HEAD})"),
    ]
    return _build(dims, metrics, "source = 'function_edge_logs'")


def _between(start: datetime, end: datetime) -> str:
    fmt = "%Y-%m-%d %H:%M:%S"
    return (
        f"timestamp >= toDateTime('{start.strftime(fmt)}', 'UTC')"
        f" and timestamp < toDateTime('{end.strftime(fmt)}', 'UTC')"
    )


def _download_where(start: datetime, end: datetime) -> str:
    return (
        f"source = 'edge_logs' and {_IS_ARCHIVE} and {_GET}"
        f" and {_STATUS} in ('200', '206') and {_between(start, end)}"
    )


def daily_downloads_sql(
    start: datetime, end: datetime, heavy_files: int, part: tuple[int, int] | None = None
) -> str:
    """Unique downloads for [start, end), normally one UTC day (PRD 033).

    The client key (IP + user agent) never leaves ClickHouse: the inner query
    collapses fetches to one row per (client key, file), the window flags
    keys over heavy_files distinct files, and the outer query returns counts
    by school, user agent, and flags.

    part=(i, n) keeps only user agents whose hash falls in bucket i of n, for
    days too large to page in one pass. The heavy window partitions by
    (ip, ua), so splitting by user agent never changes a key's flag.
    """
    internal = (
        f"{_ROLE} = 'service_role' or startsWith({_KEY_PREFIX}, 'sb_secret_')"
        f" or startsWith({_CLIENT_INFO}, '{FRIENDLY_CLIENT_INFO_PREFIX}')"
    )
    first_party = f"{_REFERER} in ({_sql_list(FIRST_PARTY_REFERER_HOSTS)})"
    inner = (
        f"select splitByChar('/', {_PATH})[7] as school_raw, {_PATH} as obj, {_IP} as ip, {_UA} as ua,"
        f" max({first_party}) as fp, max({internal}) as internal, count() as fetches"
        f" from logs where {_download_where(start, end)} group by school_raw, obj, ip, ua"
    )
    flagged = (
        "select school_raw, ua, fp, internal, fetches,"
        f" if(count() over (partition by ip, ua) > {int(heavy_files)}, 1, 0) as heavy"
        f" from ({inner})"
    )
    keys = "school_raw, ua, fp, internal, heavy"
    bucket = ""
    if part is not None:
        index, count = int(part[0]), int(part[1])
        bucket = f" where cityHash64(ua) % {count} = {index}"
    return (
        f"select {keys}, count() as uniq, sum(fetches) as raw from ({flagged}){bucket}"
        f" group by {keys} order by {keys}"
    )


def download_count_sql(start: datetime, end: datetime) -> str:
    return f"select count() as n from logs where {_download_where(start, end)}"


def raw_count_sql(source: str) -> str:
    if source not in ("edge_logs", "function_edge_logs"):
        raise ValueError(f"unknown log source {source}")
    return f"select count() as n from logs where source = '{source}'"
