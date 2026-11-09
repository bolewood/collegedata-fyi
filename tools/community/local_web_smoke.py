#!/usr/bin/env python3
"""Run browser -> Next -> real PostgREST -> isolated PostgreSQL; mock Resend only.

Requires postgrest, psql and an explicitly local community_feedback_test database
already initialized by test_database. No production configuration is read.
"""

import base64
import hashlib
import hmac
import json
import os
from pathlib import Path
import subprocess
import time
import urllib.request
import urllib.error
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from tools.community.test_database import DSN, ROOT, sql
from tools.community import notify_feedback


def wait_for(url):
    deadline = time.monotonic() + 90
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(
                urllib.request.Request(
                    url,
                    headers={
                        "User-Agent": "collegedata-pipeline/community-local-smoke"
                    },
                ),
                timeout=2,
            ):
                return
        except Exception:
            time.sleep(0.3)
    raise RuntimeError("Local server startup timed out")


def main():
    if (
        not DSN
        or not DSN.startswith("postgresql://127.0.0.1:")
        or not DSN.endswith("/community_feedback_test")
    ):
        raise RuntimeError("Explicit isolated database required")
    sql(
        "truncate public.community_submissions,public.community_rate_limits,public.community_notification_batches cascade"
    )
    secret = "isolated-local-smoke-secret-not-for-production-037"

    def part(value):
        return base64.urlsafe_b64encode(json.dumps(value).encode()).decode().rstrip("=")

    def jwt(role):
        token = (
            part({"alg": "HS256", "typ": "JWT"})
            + "."
            + part({"role": role, "exp": int(time.time()) + 3600})
        )
        return (
            token
            + "."
            + base64.urlsafe_b64encode(
                hmac.new(secret.encode(), token.encode(), hashlib.sha256).digest()
            )
            .decode()
            .rstrip("=")
        )

    service = jwt("service_role")
    env = {
        **os.environ,
        "PGRST_DB_URI": DSN,
        "PGRST_DB_ANON_ROLE": "anon",
        "PGRST_DB_SCHEMAS": "public",
        "PGRST_JWT_SECRET": secret,
        "PGRST_SERVER_PORT": "55439",
        "PGRST_SERVER_HOST": "127.0.0.1",
    }
    scratch = ROOT / "scratch/community-feedback"
    scratch.mkdir(parents=True, exist_ok=True)
    with (
        (scratch / "postgrest.log").open("w") as pglog,
        (scratch / "next.log").open("w") as weblog,
    ):
        pg = subprocess.Popen(
            ["postgrest"], env=env, stdout=pglog, stderr=subprocess.STDOUT
        )
        web = None

        # Standalone PostgREST serves /rpc; Supabase's gateway supplies /rest/v1.
        # This local prefix proxy forwards bytes to the real server, without mocks.
        class Gateway(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def forward(self):
                target = "http://127.0.0.1:55439" + self.path.removeprefix("/rest/v1")
                body = (
                    self.rfile.read(int(self.headers.get("Content-Length", 0)))
                    if self.command == "POST"
                    else None
                )
                request = urllib.request.Request(
                    target,
                    data=body,
                    headers={
                        k: v
                        for k, v in self.headers.items()
                        if k.lower() not in ("host", "content-length")
                    },
                    method=self.command,
                )
                try:
                    response = urllib.request.urlopen(request, timeout=20)
                except urllib.error.HTTPError as error:
                    response = error
                with response:
                    data = response.read()
                    self.send_response(response.status)
                    self.send_header(
                        "Content-Type",
                        response.headers.get("Content-Type", "application/json"),
                    )
                    self.send_header("Content-Length", str(len(data)))
                    self.end_headers()
                    self.wfile.write(data)

            do_POST = forward
            do_GET = forward

        gateway = ThreadingHTTPServer(("127.0.0.1", 55438), Gateway)
        threading.Thread(target=gateway.serve_forever, daemon=True).start()
        try:
            wait_for("http://127.0.0.1:55439/")
            webenv = {
                **os.environ,
                "CI": "true",
                "PORT": "3047",
                "NEXT_PUBLIC_SUPABASE_URL": "http://127.0.0.1:55438",
                "NEXT_PUBLIC_SUPABASE_ANON_KEY": jwt("anon"),
                "SUPABASE_SERVICE_ROLE_KEY": service,
                "COMMUNITY_FEEDBACK_ENABLED": "true",
                "COMMUNITY_ALLOW_LOCAL_WRITES": "true",
                "COMMUNITY_FEEDBACK_ORIGINS": "http://localhost:3047",
                "COMMUNITY_RATE_LIMIT_SECRET": secret,
            }
            web = subprocess.Popen(
                ["npm", "run", "dev", "--", "--webpack"],
                cwd=ROOT / "web",
                env=webenv,
                stdout=weblog,
                stderr=subprocess.STDOUT,
                start_new_session=True,
            )
            wait_for("http://localhost:3047/feedback")
            # Warm the route compiler before concurrent browsers; no valid write.
            try:
                urllib.request.urlopen(
                    urllib.request.Request(
                        "http://localhost:3047/api/feedback",
                        data=b"{}",
                        headers={
                            "Content-Type": "application/json",
                            "Origin": "http://localhost:3047",
                        },
                        method="POST",
                    ),
                    timeout=30,
                )
            except urllib.error.HTTPError as error:
                if error.code != 400:
                    raise RuntimeError("Local validation warmup failed") from None

            result = subprocess.run(
                [
                    "npx",
                    "playwright",
                    "test",
                    "community-feedback.spec.ts",
                    "--workers=2",
                    "--retries=0",
                ],
                cwd=ROOT / "web",
                env={
                    **webenv,
                    "PLAYWRIGHT_BASE_URL": "http://localhost:3047",
                    "COMMUNITY_E2E_ISOLATED": "true",
                },
            )
            if result.returncode:
                return result.returncode
            # Verify the committed browser canary lives only in the private queue.
            count = int(
                sql(
                    "select count(*) from public.community_submissions where payload->>'message' like 'PRIVATE BROWSER CANARY %'"
                )
            )
            if count != 2:
                raise RuntimeError("Expected one receipt per browser project")
            delivered = []

            def transport(url, payload, headers):
                if url == "https://api.resend.com/emails":
                    delivered.append(payload)
                    return {"id": "mock-only"}
                local = "http://127.0.0.1:55438" + url.split(".supabase.co", 1)[1]
                return notify_feedback.post(
                    local,
                    payload,
                    {"Authorization": "Bearer " + service, "apikey": service},
                )

            notify_feedback.run(
                {
                    "GITHUB_REF": "refs/heads/main",
                    "COMMUNITY_NOTIFICATIONS_ENABLED": "true",
                    "SUPABASE_URL": "https://abcdefghijklmnopqrst.supabase.co",
                    "SUPABASE_SERVICE_ROLE_KEY": service,
                    "RESEND_API_KEY": "mock-only",
                    "COMMUNITY_NOTIFICATION_FROM": notify_feedback.SENDER,
                    "COMMUNITY_INBOX_URL": "https://supabase.com/dashboard/project/abcdefghijklmnopqrst/editor/public.community_submissions",
                },
                transport,
            )
            if len(delivered) != 1 or "CANARY" in json.dumps(delivered):
                raise RuntimeError("Digest privacy check failed")
            logs = (scratch / "next.log").read_text() + (
                scratch / "postgrest.log"
            ).read_text()
            if (
                "PRIVATE BROWSER CANARY" in logs
                or "browser-canary@example.test" in logs
            ):
                raise RuntimeError("Private content leaked to server logs")
            print(
                "Real local browser/Next/PostgREST/PostgreSQL flow passed; one count-only mock-provider digest; server-log canaries absent."
            )
            return 0
        finally:
            if web:
                import signal

                os.killpg(web.pid, signal.SIGTERM)
                web.wait(timeout=15)
            gateway.shutdown()
            gateway.server_close()
            pg.terminate()
            pg.wait(timeout=10)


if __name__ == "__main__":
    raise SystemExit(main())
