"""Supabase Management API logs client for PRD 032.

The endpoint allows 10 queries per minute per token, truncates results at
1,000 rows, and keeps 90 days. This client paces calls, backs off on 429,
and pages with LIMIT/OFFSET. Errors never echo response rows.
"""

from __future__ import annotations

import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime
from typing import Callable

from tools.api_usage.queries import PAGE_SIZE, paged

LOGS_URL = "https://api.supabase.com/v1/projects/{ref}/analytics/endpoints/logs"

_IPV4_RE = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")
_IPV6_RE = re.compile(r"(?<![\w:])[0-9a-fA-F]{0,4}(?::[0-9a-fA-F]{0,4}){2,7}(?![\w:])")


def redact(text: str) -> str:
    """Mask anything shaped like an IP address before it reaches a log."""
    return _IPV6_RE.sub("[ip]", _IPV4_RE.sub("[ip]", text))


class LogsApiError(RuntimeError):
    pass


def iso(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


class LogsClient:
    def __init__(
        self,
        token: str,
        project_ref: str,
        *,
        min_interval: float = 7.0,
        rate_limit_backoff: float = 300.0,
        server_error_backoff: float = 30.0,
        max_retries: int = 4,
        max_pages: int = 60,
        timeout: float = 120.0,
        opener: Callable = urllib.request.urlopen,
        sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if not token:
            raise LogsApiError("SUPABASE_LOGS_TOKEN is required")
        self._token = token
        self._url = LOGS_URL.format(ref=project_ref)
        self._min_interval = min_interval
        self._rate_limit_backoff = rate_limit_backoff
        self._server_error_backoff = server_error_backoff
        self._max_retries = max_retries
        self._max_pages = max_pages
        self._timeout = timeout
        self._opener = opener
        self._sleep = sleep
        self._clock = clock
        self._last_call: float | None = None
        self.queries_made = 0

    def _pace(self) -> None:
        if self._last_call is None:
            return
        wait = self._min_interval - (self._clock() - self._last_call)
        if wait > 0:
            self._sleep(wait)

    def query(self, sql: str, start: datetime, end: datetime) -> list[dict]:
        params = urllib.parse.urlencode(
            {"sql": sql, "iso_timestamp_start": iso(start), "iso_timestamp_end": iso(end)}
        )
        request = urllib.request.Request(
            f"{self._url}?{params}",
            headers={
                "Authorization": f"Bearer {self._token}",
                "User-Agent": "collegedata-pipeline/api-usage-ingest",
            },
        )
        for attempt in range(self._max_retries + 1):
            self._pace()
            self._last_call = self._clock()
            self.queries_made += 1
            try:
                with self._opener(request, timeout=self._timeout) as response:
                    body = json.loads(response.read())
            except urllib.error.HTTPError as exc:
                retryable = exc.code == 429 or exc.code >= 500
                if retryable and attempt < self._max_retries:
                    self._sleep(self._rate_limit_backoff if exc.code == 429 else self._server_error_backoff)
                    continue
                raise LogsApiError(f"logs API HTTP {exc.code}") from None
            except (urllib.error.URLError, TimeoutError) as exc:
                if attempt < self._max_retries:
                    self._sleep(self._server_error_backoff)
                    continue
                raise LogsApiError(f"logs API unreachable: {type(exc).__name__}") from None
            error = body.get("error") if isinstance(body, dict) else "malformed response"
            if error:
                message = error if isinstance(error, str) else json.dumps(error)[:300]
                raise LogsApiError(f"logs API query error: {redact(message)[:300]}")
            result = body.get("result")
            if not isinstance(result, list):
                raise LogsApiError("logs API returned no result list")
            return result
        raise LogsApiError("logs API retries exhausted")

    def query_all(self, sql: str, start: datetime, end: datetime) -> list[dict]:
        rows: list[dict] = []
        for page in range(self._max_pages):
            batch = self.query(paged(sql, page), start, end)
            rows.extend(batch)
            if len(batch) < PAGE_SIZE:
                return rows
        raise LogsApiError(f"more than {self._max_pages} pages; shorten the window")
