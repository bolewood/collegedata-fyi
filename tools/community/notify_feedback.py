#!/usr/bin/env python3
"""PRD 037 private digest worker. Output contains fixed status codes/counts only."""

from __future__ import annotations
import json
import os
import re
import sys
import urllib.error
import urllib.request
from typing import Callable

SENDER = "CollegeData.fyi <feedback@notify.collegedata.fyi>"
RECIPIENT = "contact@bolewood.com"
INBOX_RE = re.compile(
    r"https://supabase\.com/dashboard/project/[a-z0-9]{20}/editor(?:/[^?#\s]*)?"
)


class WorkerError(Exception):
    """Fixed redacted failure category; never wrap provider exception text."""


def post(url: str, payload: dict, headers: dict) -> object:
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json", **headers},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            return json.loads(response.read(65536))
    except (TimeoutError, ConnectionError):
        raise WorkerError("timeout") from None
    except Exception:
        raise WorkerError("provider") from None


def run(env: dict[str, str], transport: Callable = post) -> int:
    # Production writes are opt-in and workflow restricted. Tests inject transport;
    # no CLI mode can redirect messages to a supplied recipient.
    if (
        env.get("GITHUB_REF") != "refs/heads/main"
        or env.get("COMMUNITY_NOTIFICATIONS_ENABLED") != "true"
    ):
        raise WorkerError("configuration")
    base = env.get("SUPABASE_URL", "").rstrip("/")
    key = env.get("SUPABASE_SERVICE_ROLE_KEY", "")
    sender = env.get("COMMUNITY_NOTIFICATION_FROM", "")
    inbox = env.get("COMMUNITY_INBOX_URL", "")
    api_key = env.get("RESEND_API_KEY", "")
    if (
        not re.fullmatch(r"https://[a-z0-9]{20}\.supabase\.co", base)
        or not key
        or not api_key
        or sender != SENDER
        or not INBOX_RE.fullmatch(inbox)
    ):
        raise WorkerError("configuration")
    headers = {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "X-Client-Info": "collegedata-community-worker",
    }

    def rpc(name, args):
        return transport(f"{base}/rest/v1/rpc/{name}", args, headers)

    health = rpc("community_notification_health", {})
    overdue = int(health["overdue"])
    batch = rpc(
        "community_claim_notification", {"p_sender": sender, "p_inbox_url": inbox}
    )
    if batch:
        # Defense in depth: only the fixed SQL-created count/link payload may leave.
        count = int(batch["count"])
        expected = {
            "from": sender,
            "to": [RECIPIENT],
            "subject": f"CollegeData.fyi: {count} new feedback message(s)",
            "text": f"There are {count} new messages waiting for review.\n\nOpen the private feedback inbox: {inbox}",
        }
        if not 1 <= count <= 500 or batch["payload"] != expected:
            raise WorkerError("configuration")
        error = None
        try:
            result = transport(
                "https://api.resend.com/emails",
                batch["payload"],
                {
                    "Authorization": f"Bearer {api_key}",
                    "Idempotency-Key": f"community-feedback/{batch['id']}",
                },
            )
            if not isinstance(result, dict) or not result.get("id"):
                raise WorkerError("provider")
        except WorkerError as exc:
            error = "timeout" if str(exc) == "timeout" else "provider"
        acknowledged = rpc(
            "community_finish_notification",
            {"p_id": batch["id"], "p_token": batch["token"], "p_error": error},
        )
        if not acknowledged:
            raise WorkerError("lease")
        if error:
            raise WorkerError(error)
        print(f"community_feedback sent_count={count}")
    else:
        if int(health["pending"]):
            # A backoff/lease wait is not delivery recovery. Keep the workflow
            # failing until the durable outstanding batch is acknowledged.
            raise WorkerError("retry_pending")
        print("community_feedback no_batch")
    # Even recovery of an overdue batch must make this run visibly fail; the next
    # scheduled run establishes recovery after checking queue health again.
    if overdue:
        raise WorkerError("overdue")
    return 0


def main():
    try:
        return run(dict(os.environ))
    except Exception as exc:
        category = str(exc) if isinstance(exc, WorkerError) else "worker"
        print(f"community_feedback failed={category}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
