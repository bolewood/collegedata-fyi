"""SQL parity tests (PRD 036 M2): run the migration on a throwaway local Postgres.

The freshness rule, the 1 July rollover, the cache selection and the view's
columns live in SQL. model.py holds a Python reference of each; these tests
apply the real migration to a scratch cluster and check the two agree, so
changing `>= 7` to `> 7`, reordering the CASE, or dropping the rank in the
cache fails here. They need Postgres binaries (initdb, pg_ctl, psql); without
them the module is skipped. Nothing touches a Supabase project.
"""

from __future__ import annotations

import copy
import datetime as dt
import glob
import itertools
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import model  # noqa: E402
import validate as v  # noqa: E402

REPO = v.REPO_ROOT
FIXTURES = Path(__file__).resolve().parent / "fixtures" / "valid"
MIGRATION = sorted((REPO / "supabase" / "migrations").glob("*_scholarship_directory.sql"))[0]
CONTRACT = REPO / "docs" / "prd" / "036-view-contract.md"


def _bin(name: str) -> Optional[str]:
    found = shutil.which(name)
    if found:
        return found
    for pattern in (f"/usr/lib/postgresql/*/bin/{name}", f"/opt/homebrew/opt/postgresql@*/bin/{name}", f"/usr/local/opt/postgresql@*/bin/{name}"):
        hits = sorted(glob.glob(pattern))
        if hits:
            return hits[-1]
    return None


INITDB, PG_CTL, PSQL = _bin("initdb"), _bin("pg_ctl"), _bin("psql")
pytestmark = pytest.mark.skipif(not (INITDB and PG_CTL and PSQL), reason="Postgres binaries not available")


class Pg:
    def __init__(self, port: int, sockdir: str) -> None:
        self.port, self.sockdir = port, sockdir

    def run(self, sql: str, db: str = "t", role: Optional[str] = None) -> str:
        if role:
            sql = f"set role {role};\n{sql}"
        with tempfile.NamedTemporaryFile("w", suffix=".sql", delete=False, dir=self.sockdir) as f:
            f.write(sql)
        try:
            out = subprocess.run(
                [PSQL, "-h", "127.0.0.1", "-p", str(self.port), "-U", "postgres", "-d", db, "-X", "-q", "-A", "-t", "-v", "ON_ERROR_STOP=1", "-f", f.name],
                capture_output=True, text=True,
            )
        finally:
            os.unlink(f.name)
        if out.returncode != 0:
            raise RuntimeError(out.stderr)
        return out.stdout

    def rows(self, sql: str, role: Optional[str] = None) -> List[Any]:
        """Run a query that returns one JSON value per row."""
        return [json.loads(line) for line in self.run(sql, role=role).splitlines() if line.strip()]


@pytest.fixture(scope="module")
def pg():
    sockdir = tempfile.mkdtemp(prefix="sch", dir="/tmp")  # short: unix socket paths are length limited
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    data = os.path.join(sockdir, "data")
    subprocess.run([INITDB, "-D", data, "-U", "postgres", "--auth=trust", "-E", "UTF8"], check=True, capture_output=True)
    subprocess.run(
        [PG_CTL, "-D", data, "-o", f"-p {port} -h 127.0.0.1 -k {sockdir}", "-l", os.path.join(sockdir, "log"), "-w", "start"],
        check=True, capture_output=True,
    )
    try:
        db = Pg(port, sockdir)
        db.run("create role anon nologin; create role authenticated nologin; create role service_role nologin bypassrls;", db="postgres")
        db.run("create database t;", db="postgres")
        db.run(
            "alter default privileges in schema public grant all on tables to anon, authenticated, service_role;\n"
            "alter default privileges in schema public grant all on functions to anon, authenticated, service_role;\n"
            + MIGRATION.read_text(encoding="utf-8")
        )
        yield db
    finally:
        subprocess.run([PG_CTL, "-D", data, "-m", "immediate", "stop"], capture_output=True)
        shutil.rmtree(sockdir, ignore_errors=True)


# ---------------------------------------------------------------------- freshness


def lit(value: Any, sql_type: str) -> str:
    return f"NULL::{sql_type}" if value is None else f"'{value}'::{sql_type}"


def test_freshness_status_matches_the_python_reference(pg):
    years = [None, 2025, 2026, 2027, 2028]
    statuses = ["verified", "conflicting", "historical_only", "unverified"]
    dates = [None, "2026-06-30", "2026-11-13", "2026-11-14", "2027-01-01"]
    checks = [(None, None), ("changed", True), ("conflicting", False), ("unchanged", False)]
    reviewed = [None, "2026-03-01", "2026-07-01", "2026-11-01"]
    ats = ["2026-06-30 23:59:59+00:00", "2026-07-01 00:00:00+00:00", "2026-11-14 12:00:00+00:00", "2027-06-30 23:59:59+00:00", "2027-07-01 00:00:00+00:00"]
    cases = list(itertools.product(years, statuses, dates, reviewed, checks, ats))
    values = ",\n".join(
        f"({i}, {lit(y, 'int')}, {lit(st, 'text')}, {lit(d, 'date')}, {lit(rv, 'date')}, {lit(c[0], 'text')}, {lit(c[1], 'boolean')}, {lit(at, 'timestamptz')})"
        for i, (y, st, d, rv, c, at) in enumerate(cases)
    )
    got = pg.rows(
        "select json_build_object('i', t.i, 'f', public.scholarship_freshness_status(t.y, t.st, t.d, t.rv, t.cr, t.nr, t.at),"
        " 'b', public.scholarship_cycle_basis(t.y, t.d), 'c', public.scholarship_current_entry_year(t.at)) "
        f"from (values {values}) as t(i, y, st, d, rv, cr, nr, at) order by t.i;"
    )
    assert len(got) == len(cases)
    for row, (y, st, d, rv, c, at) in zip(got, cases):
        today = dt.datetime.fromisoformat(at).astimezone(dt.timezone.utc).date()
        expected = model.freshness_status(y, st, d, rv, c[0], c[1], today)
        assert row["f"] == expected, (y, st, d, rv, c, at)
        assert row["b"] == model.cycle_basis(y, d)
        assert row["c"] == model.current_entry_year(today)


def test_the_rollover_and_the_decision_a_rules_in_sql(pg):
    def f(*args: Any) -> str:
        reviewed = args[4] if len(args) > 4 else "NULL::date"
        return pg.run(f"select public.scholarship_freshness_status({args[0]}, {args[1]}, {args[2]}, {reviewed}, NULL, NULL, '{args[3]}');").strip()

    assert pg.run("select public.scholarship_current_entry_year('2026-06-30 23:59:59+00');").strip() == "2026"
    assert pg.run("select public.scholarship_current_entry_year('2026-07-01 00:00:00+00');").strip() == "2027"
    # Decision A: no entry_year. Through-date today or later and verified: current, basis milestone_dates.
    assert f("NULL::int", "'verified'", "'2026-11-14'::date", "2026-11-14 09:00+00:00") == "current_cycle_verified"
    assert f("NULL::int", "'verified'", "'2026-11-13'::date", "2026-11-14 09:00+00:00") == "past_cycle"
    # No entry_year and no dated milestone: year_not_stated, until the 1 July after last_reviewed_at.
    assert f("NULL::int", "'verified'", "NULL::date", "2026-11-14 09:00+00:00", "'2026-11-01'::date") == "year_not_stated"
    assert f("NULL::int", "'verified'", "NULL::date", "2027-06-30 23:59:59+00:00", "'2026-11-01'::date") == "year_not_stated"
    assert f("NULL::int", "'verified'", "NULL::date", "2027-07-01 00:00:00+00:00", "'2026-11-01'::date") == "past_cycle"
    assert f("NULL::int", "'verified'", "NULL::date", "2026-07-01 00:00:00+00:00", "'2026-03-01'::date") == "past_cycle"
    assert f("NULL::int", "'unverified'", "NULL::date", "2026-11-14 09:00+00:00", "'2026-11-01'::date") == "current_cycle_unconfirmed"
    assert pg.run("select public.scholarship_cycle_basis(NULL, NULL), public.scholarship_cycle_basis(NULL, '2026-12-01'), public.scholarship_cycle_basis(2027, NULL);").strip() == "none|milestone_dates|entry_year"
    # An explicit entry_year keeps its rule: verified for 2027 stays current even with every milestone passed.
    assert f("2027", "'verified'", "'2026-01-01'::date", "2026-11-14 09:00+00:00") == "current_cycle_verified"


# ------------------------------------------------------------- cache and the view


def seed_docs() -> Dict[str, Dict[str, Any]]:
    docs = {str(p): v.load_yaml_text(p.read_text(encoding="utf-8")) for p in sorted(FIXTURES.glob("*/*.yaml"))}
    base = next(d for d in docs.values() if d["program_id"] == "fixture-foundation-program")

    def variant(pid: str) -> Dict[str, Any]:
        d = copy.deepcopy(base)
        d["program_id"] = pid
        return d

    joint = variant("zz-joint")
    joint["participating_schools"] = [{"school_id": "uva", "ipeds_id": "234076"}, {"school_id": "unc", "ipeds_id": "199120"}]
    docs["zz-joint.yaml"] = joint

    corr = variant("zz-correction")  # an unverified correction over the verified 2027 version
    fix = copy.deepcopy(corr["versions"][1])
    fix.update(version_id="zz-correction-2027b", supersedes=corr["versions"][1]["version_id"], verification_status="unverified")
    corr["versions"].append(fix)
    docs["zz-correction.yaml"] = corr

    undated = variant("zz-undated")  # newer information with no entry_year, only a Dec 2026 deadline
    ver = copy.deepcopy(undated["versions"][1])
    ver.update(version_id="zz-undated-nodate", entry_year=None, entry_year_label="Year not stated", supersedes=None)
    ver["application"]["milestones"] = [
        {"kind": "application_deadline", "requirement": "required", "date": "2026-12-15", "recurring": None, "precision": "day", "source_date_text": "x"}
    ]
    undated["versions"] = [undated["versions"][0], ver]  # dated 2026 (historical) and the undated one
    docs["zz-undated.yaml"] = undated

    nodates = variant("zz-nodates")  # no entry_year and no dated milestone
    nv = copy.deepcopy(nodates["versions"][1])
    nv.update(version_id="zz-nodates-v", entry_year=None, entry_year_label="Year not stated", supersedes=None)
    nv["application"]["milestones"] = []
    nv["application"]["separate_application"] = "no_form_other_steps_required"
    nv["offers"][0]["consideration_route"] = "invitation"
    nodates["versions"] = [nv]
    docs["zz-nodates.yaml"] = nodates
    return docs


def insert_sql(ds: model.Dataset) -> str:
    out = ["truncate public.scholarship_programs cascade;"]
    for table, rows in (
        ("scholarship_programs", ds.programs),
        ("scholarship_program_versions", ds.versions),
        ("scholarship_sources", ds.sources),
    ):
        cols = ", ".join(rows[0].keys())
        payload = json.dumps(rows).replace("$j$", "")
        out.append(f"insert into public.{table} ({cols}) select {cols} from jsonb_populate_recordset(null::public.{table}, $j${payload}$j$::jsonb);")
    out.append("select public.refresh_scholarship_directory_cache();")
    return "\n".join(out)


@pytest.fixture(scope="module")
def seeded(pg):
    ds = model.build_dataset(seed_docs())
    pg.run(insert_sql(ds))
    return ds


def expected_rows(ds: model.Dataset) -> Dict[tuple, Dict[str, Any]]:
    out = {}
    for version in model.select_published(ds):
        program = ds.program(version["program_id"])
        for school in model.participants_of(program):
            out[(program["program_id"], school["school_id"])] = model.public_record(program, version, school)
    return out


def test_cache_selection_matches_select_published(pg, seeded):
    got = {(r["program_id"], r["school_id"]): r["version_id"] for r in pg.rows("select row_to_json(d) from public.scholarship_directory d;")}
    want = {k: rec["version_id"] for k, rec in expected_rows(seeded).items()}
    assert got == want
    # The scenarios the seed exists for.
    assert got[("zz-correction", "uva")] == "fixture-foundation-program-2027"  # unverified correction does not hide it
    assert got[("zz-undated", "uva")] == "zz-undated-nodate"  # undated ranks by cycle_through_date, above a historical year
    assert ("zz-joint", "unc") in got and ("zz-joint", "uva") in got  # one row per participating school
    assert not any(pid == "fixture-parent-program" for pid, _ in got)  # only an unverified draft: no row


def test_view_rows_equal_the_python_public_records(pg, seeded):
    rows = {(r["program_id"], r["school_id"]): r for r in pg.rows("select row_to_json(d) from public.scholarship_directory d;")}
    for key, rec in expected_rows(seeded).items():
        row = rows[key]
        for column, value in rec.items():
            assert row[column] == value, (key, column)
        assert row["license"] == model.LICENSE_ID and row["attribution"] == model.ATTRIBUTION


def test_view_never_exposes_excerpts_and_exposes_locators(pg, seeded):
    rows = pg.rows("select row_to_json(d) from public.scholarship_directory d;")
    text = json.dumps(rows)
    assert "short_excerpt" not in text
    for ver in (v_ for v_ in seeded.versions if v_["is_published"]):
        for ev in ver["record"]["field_evidence"]:
            if ev.get("short_excerpt"):
                assert ev["short_excerpt"] not in text
    row = next(r for r in rows if r["program_id"] == "fixture-foundation-program")
    assert row["evidence"] and all(set(e) == {"field_path", "source_ref", "locator", "value_status"} for e in row["evidence"])


def test_view_columns_are_the_contract_columns(pg, seeded):
    cols = pg.run("select column_name from information_schema.columns where table_schema = 'public' and table_name = 'scholarship_directory' order by ordinal_position;").split()
    text = CONTRACT.read_text(encoding="utf-8")
    section = text.split("## Columns", 1)[1].split("### `normalized_coverage`", 1)[0]
    import re

    assert cols == re.findall(r"^\| `([a-z_]+)` \|", section, re.M)


def test_new_enum_values_load_and_filter(pg, seeded):
    got = pg.rows(
        "select json_build_object('p', program_id, 'a', awarding_authority, 's', statuses_required, 'm', application ->> 'interview_mode') "
        "from public.scholarship_directory where statuses_required @> '{scholar}' and awarding_authority = 'state_program' "
        "and application ->> 'interview_mode' = 'mixed' and school_id = 'uva' order by program_id;"
    )
    assert got and all(r["a"] == "state_program" and r["m"] == "mixed" and r["s"] == ["scholar"] for r in got)
    other = pg.rows("select json_build_object('p', program_id, 'b', cycle_basis, 'f', freshness_status) from public.scholarship_directory where separate_application = 'no_form_other_steps_required';")
    # No entry_year, no dated milestone, verified: year_not_stated, and past_cycle once its review ages out (the clock is real here).
    assert [(r["p"], r["b"]) for r in other] == [("zz-nodates", "none")]
    assert other[0]["f"] in ("year_not_stated", "past_cycle")


def test_access_model_in_a_database_that_mimics_supabase_defaults(pg, seeded):
    assert pg.run("select count(*) from public.scholarship_directory;", role="anon").strip() != ""
    for sql in (
        "select 1 from public.scholarship_programs limit 1;",
        "select 1 from public.scholarship_version_checks limit 1;",
        "select public.refresh_scholarship_directory_cache();",
        "insert into public.scholarship_programs (program_id) values ('x');",
    ):
        for role in ("anon", "authenticated"):
            with pytest.raises(RuntimeError, match="permission denied"):
                pg.run(sql, role=role)
    assert pg.run("select public.refresh_scholarship_directory_cache();", role="service_role").strip().isdigit()
