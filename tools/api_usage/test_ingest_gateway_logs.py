import argparse
import contextlib
import io
import json
import tempfile
import unittest
import urllib.error
from datetime import datetime, timedelta, timezone
from pathlib import Path

from tools.api_usage import aggregate, queries
from tools.api_usage import classify as c
from tools.api_usage import ingest_gateway_logs as ingest
from tools.api_usage.logs_api import LogsApiError, LogsClient, TooManyPages, redact

NOW = datetime(2026, 10, 2, 12, 20, tzinfo=timezone.utc)
H = int(datetime(2026, 10, 2, 10, tzinfo=timezone.utc).timestamp())
IPV4 = "203.0.113.77"
IPV6 = "2001:db8:85a3::8a2e:370:7334"
SCRIPT_UA = "python-requests/2.32.3 (internal build 7f3a)"
BROWSER_UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 Safari/605.1.15"
BOT_UA = "Mozilla/5.0 (compatible; ExampleBot/2.0; +https://bot.example.org/about)"


def edge_row(**overrides):
    row = {
        "h": H, "svc": "rest", "seg4": "cds_documents", "seg5": "", "is_archive": 0,
        "method": "GET", "role": "anon", "kp": "", "ci": "", "ref": "", "aws": 0,
        "host": "api.collegedata.fyi", "status": "200", "ua": SCRIPT_UA,
        "n": 10, "downloads": 0, "ranges": 0, "hits": 0, "bytes": 1000,
    }
    row.update(overrides)
    return row


EDGE_ROWS = [
    edge_row(),
    edge_row(ci="supabase-js-node/2.50", aws=1, n=500),
    edge_row(role="service_role", ci="supabase-py/2.9", n=40),
    edge_row(svc="storage", seg4="object", seg5="public", is_archive=1, role="", ua=BROWSER_UA,
             n=7, downloads=6, ranges=1),
    edge_row(svc="storage", seg4="object", seg5="public", is_archive=1, role="", ua=BOT_UA, n=3, downloads=3),
    edge_row(method="OPTIONS", n=2),
    edge_row(h=H + 7200, n=4),
]
SCHOOL_ROWS = [
    {**edge_row(svc="storage", seg4="object", seg5="public", is_archive=1, role=""),
     "school_raw": "harvard-university", "ua_browser": 1, "ua_internal": 0, "n": 7, "downloads": 6},
    {**edge_row(), "school_raw": "yale-university", "ua_browser": 0, "ua_internal": 0, "n": 3, "downloads": 0},
    {**edge_row(), "school_raw": "not+a+slug", "ua_browser": 0, "ua_internal": 0, "n": 1, "downloads": 0},
    {**edge_row(ci="supabase-js-web/2", ua=BROWSER_UA), "school_raw": "mit", "ua_browser": 1,
     "ua_internal": 0, "n": 9, "downloads": 0},
]
CLIENT_ROWS = [
    {**edge_row(), "ip": IPV4, "ja4": "t13d1516h2_8daaf6152771", "org": "Example Hosting LLC",
     "country": "US", "schools": 3, "s4": 1, "s5": 0},
    {**edge_row(seg4="schools"), "ip": IPV4, "ja4": "t13d1516h2_8daaf6152771", "org": "Example Hosting LLC",
     "country": "US", "schools": 1, "s4": 0, "s5": 0},
    {**edge_row(svc="storage", seg4="object", seg5="public", is_archive=1, role="", ua=BOT_UA), "ip": IPV6,
     "ja4": "t13d_x", "org": "Bot Cloud", "country": "DE", "schools": 2, "s4": 0, "s5": 0},
    {**edge_row(ua=BROWSER_UA), "ip": "198.51.100.9", "ja4": "", "org": "", "country": "", "schools": 0,
     "s4": 0, "s5": 0},
]
FN_ROWS = [
    {"h": H, "pathname": "/functions/v1/archive-process", "method": "POST", "role": "service_role",
     "aws": 1, "status": "200", "ua": "pg_net/0.10", "n": 100, "bytes": 0},
    {"h": H, "pathname": "/functions/v1/browser-search", "method": "POST", "role": "anon",
     "aws": 0, "status": "200", "ua": SCRIPT_UA, "n": 2, "bytes": 50},
]


class FakeLogs:
    def __init__(self):
        self.queries_made = 0
        self.calls = []

    def query_all(self, sql, start, end):
        self.queries_made += 1
        self.calls.append((sql, start, end))
        if "school_raw" in sql:
            return [dict(row) for row in SCHOOL_ROWS]
        if "cf_connecting_ip" in sql:
            return [dict(row) for row in CLIENT_ROWS]
        if "function_edge_logs" in sql:
            return [dict(row) for row in FN_ROWS]
        return [dict(row) for row in EDGE_ROWS]

    def query(self, sql, start, end):
        self.queries_made += 1
        if "function_edge_logs" in sql:
            return [{"n": sum(row["n"] for row in FN_ROWS)}]
        return [{"n": sum(row["n"] for row in EDGE_ROWS)}]


class FakeDb(ingest.Db):
    def __init__(self, last_end=None):
        self.rpcs = []
        self.inserts = []
        self.updates = []
        self.salts = {}
        self.last_end = last_end
        self.run_queries = []

    def rpc(self, name, payload):
        self.rpcs.append((name, payload))
        return {}

    def select(self, table, query):
        if table == "api_usage_hash_salts":
            day = query.split("day=eq.")[1]
            return [{"salt": self.salts[day]}] if day in self.salts else []
        if table == "api_usage_ingest_runs":
            self.run_queries.append(query)
            return [{"window_end": self.last_end.isoformat()}] if self.last_end else []
        return []

    def insert(self, table, row, prefer):
        self.inserts.append((table, row))
        if table == "api_usage_hash_salts":
            self.salts.setdefault(row["day"], row["salt"])
            return None
        return [{"id": len(self.inserts)}]

    def update(self, table, query, row):
        self.updates.append((table, query, row))


def args(**overrides):
    base = dict(mode="hourly", days=7, slice_hours=24, dry_run=False)
    base.update(overrides)
    return argparse.Namespace(**base)


class AggregateTest(unittest.TestCase):
    def test_rollups_reconcile_and_classify(self):
        rows = aggregate.edge_rollups(EDGE_ROWS, None)
        self.assertEqual(sum(r["requests"] for r in rows), sum(r["n"] for r in EDGE_ROWS))
        by_class = {}
        for row in rows:
            by_class[row["classification"]] = by_class.get(row["classification"], 0) + row["requests"]
        self.assertEqual(by_class["first_party_site"], 500)
        self.assertEqual(by_class["internal_pipeline"], 40)
        self.assertEqual(by_class["browser_unattributed"], 7)
        self.assertEqual(by_class["third_party"], 10 + 3 + 2 + 4)
        archive = [r for r in rows if r["route_kind"] == "archive_file" and r["classification"] == "browser_unattributed"]
        self.assertEqual((archive[0]["downloads"], archive[0]["range_requests"], archive[0]["inferred"]), (6, 1, True))
        self.assertIn("options_preflight", {r["route_kind"] for r in rows})

    def test_schools_keep_archive_and_third_party_lookups_only(self):
        rows = aggregate.edge_schools(SCHOOL_ROWS, None)
        self.assertEqual(
            {(r["school_id"], r["surface"], r["classification"]) for r in rows},
            {("harvard-university", "storage", "browser_unattributed"), ("yale-university", "postgrest", "third_party")},
        )

    def test_clients_hash_merge_and_skip_browsers(self):
        rows = aggregate.edge_clients(CLIENT_ROWS, None, lambda day: "cd" * 32)
        self.assertEqual(len(rows), 3)
        names = {r["client_name"] for r in rows}
        self.assertEqual(names, {None, "ExampleBot"})
        self.assertTrue(all(len(r["client_hash"]) == 16 for r in rows))
        self.assertEqual(len({r["client_hash"] for r in rows if r["user_agent_family"] == "python"}), 1)

    def test_function_rollups(self):
        rows = aggregate.function_rollups(FN_ROWS)
        self.assertEqual(
            {(r["route_kind"], r["classification"]) for r in rows},
            {("archive-process", "internal_pipeline"), ("browser-search", "third_party")},
        )


class RunTest(unittest.TestCase):
    def test_no_ip_or_raw_user_agent_leaves_the_job(self):
        logs, db = FakeLogs(), FakeDb()
        out = io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
            report = ingest.run(args(), now=NOW, logs=logs, db=db)
        blob = json.dumps([db.rpcs, db.inserts, db.updates, report]) + out.getvalue()
        for secret in (IPV4, IPV6, "198.51.100.9", SCRIPT_UA, BROWSER_UA, BOT_UA, "t13d1516h2_8daaf6152771"):
            self.assertNotIn(secret, blob)
        public = json.dumps(report) + out.getvalue()
        for private in ("harvard-university", "yale-university", "client_hash"):
            self.assertNotIn(private, public)
        for row in db.rpcs[0][1]["p_clients"]:
            self.assertNotIn(row["client_hash"], public)

    def test_hourly_run_replaces_whole_window_and_prunes(self):
        logs, db = FakeLogs(), FakeDb()
        with contextlib.redirect_stdout(io.StringIO()):
            report = ingest.run(args(), now=NOW, logs=logs, db=db)
        names = [name for name, _ in db.rpcs]
        self.assertEqual(names, ["api_usage_replace_window", "api_usage_replace_window", "api_usage_prune"])
        edge = db.rpcs[0][1]
        self.assertEqual((edge["p_start"], edge["p_end"]), ("2026-10-02T09:00:00+00:00", "2026-10-02T12:00:00+00:00"))
        self.assertNotIn("p_clients", db.rpcs[1][1])
        self.assertTrue(report["reconciled"])
        self.assertEqual(report["windows"], 1)
        self.assertEqual(db.updates[-1][2]["status"], "ok")
        self.assertEqual(len(db.salts), 1)

    def test_rows_outside_window_are_dropped_but_counted(self):
        logs = FakeLogs()
        start = datetime(2026, 10, 2, 10, tzinfo=timezone.utc)
        stats = ingest.process_window(logs, None, lambda day: "ab" * 32, start, start + timedelta(hours=1), None)
        self.assertTrue(stats["reconciled"])
        self.assertEqual(stats["rollup_requests"], sum(r["n"] for r in EDGE_ROWS) - 4 + 102)

    def test_dry_run_never_writes(self):
        logs = FakeLogs()
        with contextlib.redirect_stdout(io.StringIO()):
            report = ingest.run(args(dry_run=True), now=NOW, logs=logs, db=None)
        self.assertEqual(report["rows_written"], 0)
        self.assertTrue(report["dry_run"])

    def test_failed_window_marks_run_error(self):
        class Boom(FakeLogs):
            def query_all(self, sql, start, end):
                raise LogsApiError("logs API HTTP 500")

        db = FakeDb()
        with self.assertRaises(LogsApiError):
            ingest.run(args(), now=NOW, logs=Boom(), db=db)
        self.assertEqual(db.updates[-1][2]["status"], "error")
        self.assertEqual(db.updates[-1][2]["error_code"], "LogsApiError")

    def test_retention_probe_runs_once_a_day(self):
        logs, db = FakeLogs(), FakeDb()
        with contextlib.redirect_stdout(io.StringIO()):
            report = ingest.run(args(), now=datetime(2026, 10, 2, 3, 20, tzinfo=timezone.utc), logs=logs, db=db)
        self.assertTrue(report["retention_ok"])


    def test_watermark_ignores_backfill_runs(self):
        db = FakeDb(last_end=datetime(2026, 10, 1, 20, tzinfo=timezone.utc))
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            report = ingest.run(args(), now=NOW, logs=FakeLogs(), db=db)
        self.assertIn("mode=eq.hourly", db.run_queries[0])
        self.assertEqual(report["window_start"], "2026-10-01T20:00:00+00:00")
        self.assertEqual(report["windows"], 1)

    def test_unreconciled_window_writes_nothing_and_fails(self):
        class Drifted(FakeLogs):
            def query(self, sql, start, end):
                rows = super().query(sql, start, end)
                return [{"n": rows[0]["n"] + 500}]

        db = FakeDb()
        with self.assertRaises(ingest.IngestError), contextlib.redirect_stderr(io.StringIO()):
            ingest.run(args(), now=NOW, logs=Drifted(), db=db)
        self.assertEqual([name for name, _ in db.rpcs], ["api_usage_prune"])
        self.assertEqual(db.updates[-1][2]["error_code"], "unreconciled")

    def test_client_page_overflow_splits_to_hours_then_skips_clients(self):
        class Flood(FakeLogs):
            def query_all(self, sql, start, end):
                if "cf_connecting_ip" in sql:
                    raise TooManyPages("more than 60 pages")
                return super().query_all(sql, start, end)

        db = FakeDb()
        out = io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
            report = ingest.run(args(), now=NOW, logs=Flood(), db=db)
        edge_calls = [p for name, p in db.rpcs if name == "api_usage_replace_window" and p["p_log_source"] == "edge_logs"]
        self.assertEqual(len(edge_calls), 3)
        self.assertTrue(all(call["p_clients"] == [] for call in edge_calls))
        self.assertEqual(report["clients_overflow_hours"], 3)
        self.assertEqual(db.updates[-1][2]["status"], "ok")

    def test_database_errors_hide_row_details(self):
        body = json.dumps({"code": "23514", "details": f"Failing row contains (x, {IPV4})"}).encode()

        def opener(request, timeout):
            raise urllib.error.HTTPError(request.full_url, 400, "Bad", {}, io.BytesIO(body))

        db = ingest.Db("https://example.supabase.co", "key", opener=opener)
        with self.assertRaises(ingest.IngestError) as ctx:
            db.rpc("api_usage_replace_window", {})
        self.assertIn("(23514)", str(ctx.exception))
        self.assertNotIn("Failing", str(ctx.exception))
        self.assertNotIn(IPV4, str(ctx.exception))


class PlanTest(unittest.TestCase):
    def test_hourly_minimum_and_catch_up(self):
        self.assertEqual(
            ingest.plan_windows("hourly", NOW, 7, None),
            (datetime(2026, 10, 2, 9, tzinfo=timezone.utc), datetime(2026, 10, 2, 12, tzinfo=timezone.utc)),
        )
        last = datetime(2026, 10, 1, 20, tzinfo=timezone.utc)
        self.assertEqual(ingest.plan_windows("hourly", NOW, 7, last)[0], last)
        ancient = NOW - timedelta(days=200)
        self.assertEqual(ingest.plan_windows("hourly", NOW, 7, ancient)[0], ingest.floor_hour(NOW) - ingest.MAX_LOOKBACK)

    def test_backfill_bounds(self):
        start, end = ingest.plan_windows("backfill", NOW, 3, None)
        self.assertEqual(end - start, timedelta(days=3))
        with self.assertRaises(ingest.IngestError):
            ingest.plan_windows("backfill", NOW, 90, None)

    def test_slices(self):
        start = datetime(2026, 10, 1, tzinfo=timezone.utc)
        parts = ingest.slices(start, start + timedelta(hours=30), 24)
        self.assertEqual([(b - a).total_seconds() / 3600 for a, b in parts], [24, 6])


class FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def read(self):
        return json.dumps(self._payload).encode()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class LogsClientTest(unittest.TestCase):
    def make(self, responses):
        self.sleeps = []
        self.requests = []
        clock = iter(range(0, 10_000, 1))

        def opener(request, timeout):
            self.requests.append(request.full_url)
            item = responses.pop(0)
            if isinstance(item, Exception):
                raise item
            return FakeResponse(item)

        return LogsClient("token", "ref", opener=opener, sleep=self.sleeps.append, clock=lambda: next(clock))

    def test_pages_until_short_page(self):
        client = self.make([{"result": [{"n": 1}] * 1000}, {"result": [{"n": 1}] * 3}])
        start = datetime(2026, 10, 1, tzinfo=timezone.utc)
        rows = client.query_all("select 1", start, start + timedelta(hours=1))
        self.assertEqual(len(rows), 1003)
        self.assertIn("offset+1000", self.requests[1])
        self.assertTrue(all(wait > 0 for wait in self.sleeps))

    def test_backs_off_on_429_then_succeeds(self):
        err = urllib.error.HTTPError("u", 429, "Too Many", {}, io.BytesIO(b"{}"))
        client = self.make([err, {"result": []}])
        start = datetime(2026, 10, 1, tzinfo=timezone.utc)
        self.assertEqual(client.query("select 1", start, start), [])
        self.assertIn(300.0, self.sleeps)

    def test_errors_do_not_echo_bodies(self):
        err = urllib.error.HTTPError("u", 400, "Bad", {}, io.BytesIO(IPV4.encode()))
        client = self.make([err])
        start = datetime(2026, 10, 1, tzinfo=timezone.utc)
        with self.assertRaises(LogsApiError) as ctx:
            client.query("select 1", start, start)
        self.assertNotIn(IPV4, str(ctx.exception))

    def test_query_error_is_redacted(self):
        client = self.make([{"error": f"bad value {IPV4} near {IPV6}"}])
        start = datetime(2026, 10, 1, tzinfo=timezone.utc)
        with self.assertRaises(LogsApiError) as ctx:
            client.query("select 1", start, start)
        self.assertNotIn(IPV4, str(ctx.exception))
        self.assertNotIn(IPV6, str(ctx.exception))

    def test_redact(self):
        self.assertEqual(redact(f"from {IPV4} and {IPV6}"), "from [ip] and [ip]")


class QueryTest(unittest.TestCase):
    def test_every_query_orders_by_its_group_keys(self):
        t0 = datetime(2026, 10, 2, 14, 25, tzinfo=timezone.utc)
        for sql in (queries.edge_rollup_sql(), queries.edge_schools_sql(t0), queries.edge_clients_sql(t0),
                    queries.function_rollup_sql()):
            group = sql.split(" group by ")[1].split(" order by ")[0]
            self.assertEqual(group, sql.split(" order by ")[1])

    def test_only_the_client_query_reads_identifying_fields(self):
        for sql in (queries.edge_rollup_sql(), queries.edge_schools_sql(None), queries.function_rollup_sql()):
            self.assertNotIn("cf_connecting_ip", sql)
            self.assertNotIn("ja4", sql)
        self.assertIn("cf_connecting_ip", queries.edge_clients_sql(None))

    def test_head_requests_are_not_downloads_or_bytes(self):
        sql = queries.edge_rollup_sql()
        self.assertIn("= 'GET')", sql.split(" as downloads")[0])
        self.assertIn("!= 'HEAD'", sql.split(" as bytes")[0])

    def test_school_id_match_is_anchored(self):
        self.assertIn("(?:^|[?&])school_id=eq", queries.edge_schools_sql(None))

    def test_prefilter_clauses_never_hide_third_parties(self):
        sql = queries.not_third_party_condition(None)
        cases = [
            ("'service_role'", c.Signals(role="service_role", ua_browser=True)),
            ("'sb_secret_'", c.Signals(key_prefix="sb_secret_abc")),
            ("collegedata-pipeline", c.Signals(ua_internal=True)),
            ("'collegedata-web'", c.Signals(client_info="collegedata-web/abc", before_t0=False)),
            ("'collegedata-friendly-api'", c.Signals(client_info="collegedata-friendly-api/abc", before_t0=False)),
            ("'www.collegedata.fyi'", c.Signals(referer_host="www.collegedata.fyi", ua_browser=True, before_t0=False)),
            ("'supabase-js-node'", c.Signals(role="anon", client_info="supabase-js-node/2", aws=True, before_t0=True)),
            ("'supabase-js-web'", c.Signals(role="anon", client_info="supabase-js-web/2", ua_browser=True, before_t0=True)),
        ]
        for literal, signals in cases:
            with self.subTest(literal=literal):
                self.assertIn(literal, sql)
                self.assertNotIn(c.classify(signals)[0], (c.THIRD_PARTY, c.BROWSER))

    def test_t0_cutoff_rendered_in_utc(self):
        sql = queries.edge_clients_sql(datetime(2026, 10, 2, 14, 25, tzinfo=timezone.utc))
        self.assertIn("toDateTime('2026-10-02 14:00:00', 'UTC')", sql)
        self.assertIn("(1 and ", queries.edge_clients_sql(None))


class MainTest(unittest.TestCase):
    def test_main_writes_counts_only_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "report.json"
            hb = Path(tmp) / "hb.json"
            original = ingest.run
            ingest.run = lambda a: {
                "mode": "hourly", "dry_run": False, "windows": 1, "requests": 9, "third_party_requests": 2,
                "rows_written": 3, "reconciled": True, "retention_ok": None, "queries_made": 6, "lag_hours": None,
                "clients_overflow_hours": 0,
            }
            try:
                with contextlib.redirect_stdout(io.StringIO()):
                    code = ingest.main(["--out-json", str(out), "--heartbeat-json", str(hb)])
            finally:
                ingest.run = original
            self.assertEqual(code, 0)
            self.assertEqual(
                set(json.loads(hb.read_text())),
                {"windows", "mode", "rows_written", "reconciled", "dry_run"},
            )

    def test_main_hides_unexpected_exception_text(self):
        original = ingest.run

        def boom(a):
            raise KeyError(IPV4)

        ingest.run = boom
        err = io.StringIO()
        try:
            with contextlib.redirect_stderr(err):
                code = ingest.main([])
        finally:
            ingest.run = original
        self.assertEqual(code, 1)
        self.assertNotIn(IPV4, err.getvalue())


if __name__ == "__main__":
    unittest.main()
