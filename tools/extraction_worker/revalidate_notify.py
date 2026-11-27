"""Tell the web app which school pages changed after an extraction run.

School pages are ISR-cached for 7 days. After the worker finishes, POST the
affected ``school_id`` values to ``/api/revalidate`` so only those pages are
regenerated. ``tools/ops/revalidate_pages.py`` reuses this for the daily sweep.

Best effort by design: no-op unless both ``QUADFILE_REVALIDATE_URL`` (or the
older ``COLLEGEDATA_REVALIDATE_URL``) and ``REVALIDATE_SECRET`` are set, short timeout, never raises, never changes the
worker exit code.
"""

from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.request
from typing import Iterable, Mapping, Optional

URL_ENV = "QUADFILE_REVALIDATE_URL"
LEGACY_URL_ENV = "COLLEGEDATA_REVALIDATE_URL"  # read when URL_ENV is unset
SECRET_ENV = "REVALIDATE_SECRET"
BATCH_SIZE = 100  # must stay <= MAX_SCHOOL_IDS in web/src/lib/revalidate-schools.ts
TIMEOUT_SECONDS = 5
MAX_BATCHES = 20  # bound total added runtime (~2,000 schools)


def revalidate_url(env: Mapping[str, str]) -> str:
    """The new variable wins; the old name still works."""
    return (env.get(URL_ENV) or "").strip() or (env.get(LEGACY_URL_ENV) or "").strip()


def notify_school_revalidation(
    school_ids: Iterable[Optional[str]],
    env: Optional[Mapping[str, str]] = None,
    *,
    opener=urllib.request.urlopen,
    max_batches: Optional[int] = MAX_BATCHES,
    scholarships: bool = False,
    pause_seconds: float = 0.0,
    sleep=time.sleep,
) -> dict:
    """POST school ids in batches. Returns counts; swallows every error.

    ``max_batches=None`` sends every batch (the daily sweep). ``scholarships``
    also expires the shared scholarship directory read. ``pause_seconds`` waits
    between batches.
    """
    env = os.environ if env is None else env
    url = revalidate_url(env)
    secret = env.get(SECRET_ENV) or ""
    result = {"enabled": bool(url and secret), "sent": 0, "batches": 0, "errors": 0}
    if not result["enabled"]:
        return result
    ids = sorted({s.strip() for s in school_ids if isinstance(s, str) and s.strip()})
    if not ids:
        return result
    batches = [ids[i : i + BATCH_SIZE] for i in range(0, len(ids), BATCH_SIZE)]
    capped = batches if max_batches is None else batches[:max_batches]
    for index, batch in enumerate(capped):
        if index and pause_seconds > 0:
            sleep(pause_seconds)
        body = {"school_ids": batch}
        if scholarships:
            body["scholarships"] = True
        request = urllib.request.Request(
            url,
            data=json.dumps(body).encode("utf-8"),
            method="POST",
            headers={
                "Authorization": f"Bearer {secret}",
                "Content-Type": "application/json",
                "User-Agent": "quadfile-extraction-worker",
            },
        )
        try:
            with opener(request, timeout=TIMEOUT_SECONDS) as response:
                status = getattr(response, "status", 200)
            if status >= 300:
                raise RuntimeError(f"HTTP {status}")
            result["sent"] += len(batch)
            result["batches"] += 1
        except Exception as e:  # noqa: BLE001 - must never fail the run
            result["errors"] += 1
            # An HTTP error answer (a rejected batch, a 5xx) means the endpoint
            # is reachable: keep sending the other batches.
            transport_failure = not isinstance(e, (RuntimeError, urllib.error.HTTPError))
            print(
                f"revalidate_notify_error: {type(e).__name__}: "
                f"{str(e).splitlines()[0][:200] if str(e) else ''}",
                file=sys.stderr,
                flush=True,
            )
            if transport_failure:
                break  # endpoint unreachable/timing out: don't stall the run
    skipped = len(batches) - len(capped)
    if skipped:
        print(
            f"revalidate_notify: skipped {skipped} batch(es) over the cap; "
            "the daily page sweep will pick them up.",
            file=sys.stderr,
            flush=True,
        )
    return result


def notify_all_revalidation(
    env: Optional[Mapping[str, str]] = None,
    *,
    opener=urllib.request.urlopen,
) -> dict:
    """POST ``{"all": true}``: expire every school page. Swallows every error."""
    env = os.environ if env is None else env
    url = revalidate_url(env)
    secret = env.get(SECRET_ENV) or ""
    result = {"enabled": bool(url and secret), "sent": 0, "batches": 0, "errors": 0}
    if not result["enabled"]:
        return result
    request = urllib.request.Request(
        url,
        data=json.dumps({"all": True}).encode("utf-8"),
        method="POST",
        headers={
            "Authorization": f"Bearer {secret}",
            "Content-Type": "application/json",
            "User-Agent": "quadfile-extraction-worker",
        },
    )
    try:
        with opener(request, timeout=TIMEOUT_SECONDS) as response:
            status = getattr(response, "status", 200)
        if status >= 300:
            raise RuntimeError(f"HTTP {status}")
        result["batches"] = 1
    except Exception as e:  # noqa: BLE001 - must never raise
        result["errors"] = 1
        print(f"revalidate_notify_error: {type(e).__name__}", file=sys.stderr, flush=True)
    return result
