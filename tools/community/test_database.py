"""Real PostgreSQL tests. ONLY an explicitly isolated localhost test database.

COMMUNITY_TEST_DATABASE_URL=postgresql://...@127.0.0.1:55437/community_feedback_test
PSQL=/opt/homebrew/opt/postgresql@17/bin/psql python3 -m unittest tools.community.test_database
"""

from __future__ import annotations
import concurrent.futures
import json
import os
from pathlib import Path
import subprocess
import unittest
from urllib.parse import urlparse
from uuid import uuid4

DSN = os.getenv("COMMUNITY_TEST_DATABASE_URL")
PSQL = os.getenv("PSQL", "psql")
ROOT = Path(__file__).resolve().parents[2]
SENDER = "CollegeData.fyi <feedback@notify.collegedata.fyi>"
INBOX = "https://supabase.com/dashboard/project/abcdefghijklmnopqrst/editor/public.community_submissions"


def literal(value):
    return "'" + str(value).replace("'", "''") + "'"


def sql(query, role=None):
    result = subprocess.run(
        [
            PSQL,
            DSN,
            "-X",
            "-qAt",
            "-v",
            "ON_ERROR_STOP=1",
            "-c",
            ("set role " + role + "; " if role else "") + query,
        ],
        text=True,
        capture_output=True,
    )
    if result.returncode:
        raise RuntimeError(result.stderr)
    return result.stdout.strip()


def admit(request=None, digest="a" * 64, bucket="b" * 64, previous="c" * 64):
    payload = json.dumps(
        {
            "kind": "feedback",
            "message": "PRIVATE MESSAGE CANARY",
            "email": "canary@example.test",
        }
    )
    return json.loads(
        sql(
            f"select public.community_submit('{request or uuid4()}','{digest}',{literal(payload)}::jsonb,'{bucket}','{previous}')",
            "service_role",
        )
    )


def claim():
    raw = sql(
        f"select public.community_claim_notification({literal(SENDER)},{literal(INBOX)})",
        "service_role",
    )
    return json.loads(raw) if raw else None


@unittest.skipUnless(DSN, "explicit isolated PostgreSQL test storage required")
class DatabaseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        parsed = urlparse(DSN)
        if (
            parsed.hostname not in ("127.0.0.1", "localhost")
            or parsed.path != "/community_feedback_test"
        ):
            raise RuntimeError("Refusing non-local or non-test database")
        sql(
            "do $$ begin if not exists(select 1 from pg_roles where rolname='anon') then create role anon; end if; if not exists(select 1 from pg_roles where rolname='authenticated') then create role authenticated; end if; if not exists(select 1 from pg_roles where rolname='service_role') then create role service_role bypassrls; end if; end $$;"
        )
        sql(
            "drop table if exists public.community_submissions, public.community_rate_limits, public.community_notification_batches cascade; drop function if exists public.community_submit(uuid,text,jsonb,text,text), public.community_claim_notification(text,text), public.community_finish_notification(uuid,uuid,text), public.community_notification_health(), public.community_expire();"
        )
        sql(
            (
                ROOT / "supabase/migrations/20261108210000_community_feedback.sql"
            ).read_text()
        )

    def setUp(self):
        sql(
            "truncate public.community_submissions,public.community_rate_limits,public.community_notification_batches cascade"
        )

    def test_concurrent_idempotency_and_conflict(self):
        request = str(uuid4())
        with concurrent.futures.ThreadPoolExecutor(max_workers=12) as pool:
            results = list(pool.map(lambda _: admit(request), range(20)))
        self.assertEqual(sum(r["status"] == "created" for r in results), 1)
        self.assertEqual(len({r["receipt"] for r in results}), 1)
        self.assertEqual(sql("select count(*) from public.community_submissions"), "1")
        self.assertEqual(admit(request, digest="d" * 64)["status"], "conflict")
        self.assertEqual(
            sql("select cardinality(admitted_at) from public.community_rate_limits"),
            "1",
        )

    def test_shared_windows_midnight_and_expiry(self):
        with concurrent.futures.ThreadPoolExecutor(max_workers=12) as pool:
            results = list(pool.map(lambda _: admit(), range(30)))
        self.assertEqual(sum(r["status"] == "created" for r in results), 5)
        self.assertTrue(
            all(
                0 < r["retry_after"] <= 600 for r in results if r["status"] == "limited"
            )
        )
        self.assertEqual(admit(bucket="e" * 64, previous="b" * 64)["status"], "limited")
        for _ in range(3):
            sql(
                "update public.community_rate_limits set admitted_at=array(select t-interval '11 minutes' from unnest(admitted_at) t)"
            )
            for __ in range(5):
                self.assertEqual(admit()["status"], "created")
        sql(
            "update public.community_rate_limits set admitted_at=array(select t-interval '11 minutes' from unnest(admitted_at) t)"
        )
        self.assertEqual(
            admit()["status"], "limited"
        )  # daily cap independent of burst window
        self.assertEqual(admit(bucket="f" * 64)["status"], "created")
        sql(
            "update public.community_rate_limits set expires_at=now()-interval '1 second'; select public.community_expire()"
        )
        self.assertEqual(sql("select count(*) from public.community_rate_limits"), "0")

    def test_denied_tables_rls_and_all_rpcs_for_anon_and_authenticated(self):
        admit()
        tables = [
            "community_submissions",
            "community_rate_limits",
            "community_notification_batches",
        ]
        calls = [
            "community_submit(gen_random_uuid(),'a','{}','b','c')",
            f"community_claim_notification({literal(SENDER)},{literal(INBOX)})",
            "community_finish_notification(gen_random_uuid(),gen_random_uuid(),null)",
            "community_notification_health()",
            "community_expire()",
        ]
        self.assertEqual(
            sql(
                "select count(*) from pg_class where relname like 'community_%' and relrowsecurity"
            ),
            "3",
        )
        for role in ["anon", "authenticated"]:
            for table in tables:
                for action in [
                    f"select * from public.{table}",
                    f"insert into public.{table} default values",
                    f"update public.{table} set expires_at=now()"
                    if table == "community_rate_limits"
                    else f"update public.{table} set created_at=now()",
                    f"delete from public.{table}",
                ]:
                    with self.assertRaisesRegex(RuntimeError, "permission denied"):
                        sql(action, role)
            for call in calls:
                with self.assertRaisesRegex(RuntimeError, "permission denied"):
                    sql("select public." + call, role)
        # No view depends on any private table.
        self.assertEqual(
            sql(
                "select count(*) from pg_rewrite r join pg_depend d on d.objid=r.oid join pg_class c on c.oid=d.refobjid where c.relname in ('community_submissions','community_rate_limits','community_notification_batches')"
            ),
            "0",
        )

    def test_batch_claims_retry_lease_and_no_content(self):
        for _ in range(3):
            admit()
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
            batches = list(pool.map(lambda _: claim(), range(8)))
        self.assertEqual(sum(b is not None for b in batches), 1)
        first = next(b for b in batches if b)
        self.assertEqual(first["count"], 3)
        self.assertNotIn("CANARY", json.dumps(first))
        self.assertNotIn("canary@example.test", json.dumps(first))
        self.assertEqual(set(first["payload"]), {"from", "to", "subject", "text"})
        sql(
            "update public.community_notification_batches set lease_until=now()-interval '1 second'"
        )
        recovered = claim()
        self.assertEqual(first["id"], recovered["id"])
        self.assertEqual(first["payload"], recovered["payload"])
        self.assertNotEqual(first["token"], recovered["token"])
        self.assertEqual(
            sql(
                f"select public.community_finish_notification('{first['id']}','{first['token']}',null)",
                "service_role",
            ),
            "f",
        )
        self.assertEqual(
            sql(
                f"select public.community_finish_notification('{recovered['id']}','{recovered['token']}','timeout')",
                "service_role",
            ),
            "t",
        )
        self.assertIsNone(claim())
        self.assertEqual(sql("select count(*) from public.community_submissions"), "3")
        sql(
            "update public.community_notification_batches set next_retry_at=now()-interval '1 second',created_at=now()-interval '25 hours'"
        )
        self.assertEqual(
            json.loads(
                sql("select public.community_notification_health()", "service_role")
            )["overdue"],
            1,
        )
        retry = claim()
        self.assertEqual(retry["id"], first["id"])
        sql(
            f"select public.community_finish_notification('{retry['id']}','{retry['token']}',null)",
            "service_role",
        )
        self.assertIsNone(claim())
        self.assertEqual(
            sql(
                "select count(*) from public.community_submissions where notified_at is not null"
            ),
            "3",
        )
        sql(
            "update public.community_notification_batches set sent_at=now()-interval '31 days'; select public.community_expire()"
        )
        self.assertIsNone(claim())  # deleted completed metadata never re-notifies

    def test_approval_requires_final_record_and_withdrawal_time(self):
        receipt = admit()["receipt"]
        with self.assertRaisesRegex(RuntimeError, "check constraint"):
            sql(
                f"update public.community_submissions set publication_status='approved' where id='{receipt}'"
            )
        with self.assertRaisesRegex(RuntimeError, "check constraint"):
            sql(
                f"update public.community_submissions set publication_status='withdrawn' where id='{receipt}'"
            )
        with self.assertRaisesRegex(RuntimeError, "check constraint"):
            sql(
                f"update public.community_submissions set publication_permission='{{\"email\":\"private@example.test\"}}'::jsonb where id='{receipt}'"
            )

    def test_retention_independent_of_unresolved_batches_and_permission(self):
        for _ in range(4):
            admit(bucket=uuid4().hex * 2)
        claim()
        rows = sql(
            "select id from public.community_submissions order by id"
        ).splitlines()
        sql(
            f"update public.community_submissions set created_at=now()-interval '181 days' where id='{rows[0]}'"
        )
        sql(
            f"update public.community_submissions set created_at=now()-interval '31 days',review_status='spam' where id='{rows[1]}'"
        )
        permission = json.dumps(
            dict(
                text="Final approved text",
                credit="Approved name",
                version="v1",
                approved_at="2026-01-01",
                evidence_ref="private-mail-reference",
            )
        )
        sql(
            f"update public.community_submissions set created_at=now()-interval '181 days',publication_status='approved',publication_permission={literal(permission)} where id='{rows[2]}'"
        )
        sql(
            f"update public.community_submissions set created_at=now()-interval '181 days',publication_status='withdrawn',withdrawn_at=now()-interval '91 days',publication_permission={literal(permission)} where id='{rows[3]}'"
        )
        sql("select public.community_expire()", "service_role")
        self.assertEqual(sql("select count(*) from public.community_submissions"), "1")
        self.assertEqual(
            sql(
                "select payload is null and request_id is null and payload_digest is null from public.community_submissions"
            ),
            "t",
        )
        self.assertEqual(
            sql(
                "select publication_permission->>'text' from public.community_submissions"
            ),
            "Final approved text",
        )
        self.assertEqual(
            sql(
                "select count(*) from public.community_notification_batches where sent_at is null"
            ),
            "1",
        )
