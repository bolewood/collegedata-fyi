"""Tell the web app which school pages changed after an extraction run.

School pages are ISR-cached for 24 h. After the worker finishes, POST the
affected ``school_id`` values to ``/api/revalidate`` so only those pages are
regenerated, instead of every page re-rendering hourly.

Best effort by design: no-op unless both ``COLLEGEDATA_REVALIDATE_URL`` and
``REVALIDATE_SECRET`` are set, short timeout, never raises, never changes the
worker exit code.
"""

from __future__ import annotations

import json
import os
import sys
import urllib.request
from typing import Iterable, Mapping, Optional

URL_ENV = "COLLEGEDATA_REVALIDATE_URL"
SECRET_ENV = "REVALIDATE_SECRET"
BATCH_SIZE = 100  # must stay <= MAX_SCHOOL_IDS in web/src/lib/revalidate-schools.ts
TIMEOUT_SECONDS = 5
MAX_BATCHES = 20  # bound total added runtime (~2,000 schools)


def notify_school_revalidation(
    school_ids: Iterable[Optional[str]],
    env: Optional[Mapping[str, str]] = None,
    *,
    opener=urllib.request.urlopen,
) -> dict:
    """POST school ids in batches. Returns counts; swallows every error."""
    env = os.environ if env is None else env
    url = (env.get(URL_ENV) or "").strip()
    secret = env.get(SECRET_ENV) or ""
    result = {"enabled": bool(url and secret), "sent": 0, "batches": 0, "errors": 0}
    if not result["enabled"]:
        return result
    ids = sorted({s.strip() for s in school_ids if isinstance(s, str) and s.strip()})
    if not ids:
        return result
    batches = [ids[i : i + BATCH_SIZE] for i in range(0, len(ids), BATCH_SIZE)]
    for batch in batches[:MAX_BATCHES]:
        request = urllib.request.Request(
            url,
            data=json.dumps({"school_ids": batch}).encode("utf-8"),
            method="POST",
            headers={
                "Authorization": f"Bearer {secret}",
                "Content-Type": "application/json",
                "User-Agent": "collegedata-extraction-worker",
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
            transport_failure = not isinstance(e, RuntimeError)
            print(
                f"revalidate_notify_error: {type(e).__name__}: "
                f"{str(e).splitlines()[0][:200] if str(e) else ''}",
                file=sys.stderr,
                flush=True,
            )
            if transport_failure:
                break  # endpoint unreachable/timing out: don't stall the run
    skipped = max(0, len(batches) - MAX_BATCHES)
    if skipped:
        print(
            f"revalidate_notify: skipped {skipped} batch(es) over the cap; "
            "daily ISR safety net will pick them up.",
            file=sys.stderr,
            flush=True,
        )
    return result
