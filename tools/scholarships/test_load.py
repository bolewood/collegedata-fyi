"""Tests for the scholarship loader and row model (PRD 036 M2). No network, no database.

The SQL itself is exercised by hand against a throwaway local Postgres (see the
PR notes); these tests pin the Python that feeds it and keep the migration, the
view contract and the attribution string in step.
"""

from __future__ import annotations

import copy
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import load  # noqa: E402
import model  # noqa: E402
import validate as v  # noqa: E402

REPO = v.REPO_ROOT
FIXTURES = Path(__file__).resolve().parent / "fixtures" / "valid"
_MATCHES = sorted((REPO / "supabase" / "migrations").glob("*_scholarship_directory.sql"))
assert len(_MATCHES) == 1, _MATCHES  # resolved by name so a timestamp change at merge does not break the tests
MIGRATION = _MATCHES[0]
CONTRACT = REPO / "docs" / "prd" / "036-view-contract.md"
FOUNDATION = "fixture-foundation-program"
PARENT = "fixture-parent-program"


def fixture_docs() -> Dict[str, Dict[str, Any]]:
    return {
        str(p): v.load_yaml_text(p.read_text(encoding="utf-8"))
        for p in sorted(FIXTURES.glob("*/*.yaml"))
    }


@pytest.fixture()
def docs() -> Dict[str, Dict[str, Any]]:
    return fixture_docs()


@pytest.fixture()
def ds() -> model.Dataset:
    return model.build_dataset(fixture_docs(), root=REPO)


def foundation(docs: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    return next(d for d in docs.values() if d["program_id"] == FOUNDATION)


# --------------------------------------------------------- coverage derivation


def b(category: str, instrument: str = "scholarship", coverage: str = "full") -> Dict[str, Any]:
    return {"benefit_id": f"b-{category}", "category": category, "instrument": instrument, "coverage": coverage}


@pytest.mark.parametrize(
    "benefits, expected",
    [
        (None, None),  # not documented: unknown is not no
        ([], "other"),  # documented as no benefits
        ([b("tuition")], "full_tuition"),
        ([b("tuition"), b("mandatory_fees")], "full_tuition_fees"),
        ([b("tuition"), b("housing"), b("meals")], "tuition_housing_meals"),
        ([b("tuition"), b("mandatory_fees"), b("housing"), b("meals")], "tuition_housing_meals"),
        (
            [b("tuition"), b("mandatory_fees"), b("housing"), b("meals"), b("books"), b("stipend", "cash_stipend", "fixed_amount")],
            "full_school_coa",
        ),
        (
            [b("tuition"), b("mandatory_fees"), b("housing"), b("meals"), b("books")],
            "tuition_housing_meals",  # no stipend: not cost of attendance
        ),
        ([b("tuition", coverage="fixed_amount")], "partial_or_fixed"),
        ([b("tuition", coverage="partial")], "partial_or_fixed"),
        ([b("tuition", coverage="variable")], "partial_or_fixed"),
        ([b("stipend", "cash_stipend", "fixed_amount")], "partial_or_fixed"),
        ([b("tuition", coverage="unknown")], "other"),
        ([b("housing")], "other"),  # full housing alone is not tuition coverage
        ([b("tuition", instrument="unknown")], "other"),  # cannot prove it is a scholarship
        ([b("tuition", instrument="earned_compensation")], "other"),
        # Waivers never count as tuition coverage, in any bracket.
        ([b("tuition", instrument="tuition_waiver")], "other"),
        ([b("nonresident_differential", instrument="tuition_waiver")], "other"),
        ([b("nonresident_differential", instrument="scholarship")], "other"),
        ([b("nonresident_differential", instrument="tuition_waiver", coverage="partial")], "other"),
        (
            [b("tuition", instrument="tuition_waiver"), b("mandatory_fees"), b("housing"), b("meals")],
            "other",  # waiver "tuition" does not unlock the housing and meals bracket
        ),
        # The differential waiver beside a real tuition scholarship: the scholarship decides.
        ([b("nonresident_differential", instrument="tuition_waiver"), b("tuition")], "full_tuition"),
        (
            [b("nonresident_differential", instrument="tuition_waiver"), b("tuition", coverage="fixed_amount")],
            "partial_or_fixed",
        ),
    ],
)
def test_derive_normalized_coverage(benefits, expected):
    assert model.derive_normalized_coverage(benefits) == expected


def test_coverage_values_are_the_documented_set():
    for expected in (
        "full_tuition", "full_tuition_fees", "tuition_housing_meals", "full_school_coa", "partial_or_fixed", "other",
    ):
        assert expected in model.NORMALIZED_COVERAGE
    assert "full_ride" not in model.NORMALIZED_COVERAGE


def test_fixture_offers_derive_per_offer_with_no_parent_inheritance(ds):
    version = next(r for r in ds.versions if r["version_id"] == "fixture-foundation-program-2027")
    by_offer = {o["offer_id"]: o["normalized_coverage"] for o in version["offers"]}
    # o-main: full tuition scholarship + stipend + restricted fund. o-tier is a child of o-main
    # whose only benefit is the nonresident differential waiver: it is not full tuition.
    assert by_offer == {"o-main": "full_tuition", "o-tier": "other"}
    assert version["coverages"] == ["full_tuition", "other"]


def test_derived_coverage_is_not_in_the_stored_record_or_the_yaml(ds, docs):
    raw = foundation(docs)["versions"][1]
    assert all("normalized_coverage" not in o for o in raw["offers"])
    version = next(r for r in ds.versions if r["version_id"] == "fixture-foundation-program-2027")
    assert all("normalized_coverage" not in o for o in version["record"]["offers"])
    assert all("normalized_coverage" in o for o in version["offers"])


def test_derivation_does_not_mutate_the_source_offers():
    offers = [{"offer_id": "o", "benefits": [b("tuition")]}]
    out = model.derive_offers(offers)
    assert "normalized_coverage" not in offers[0]
    assert out[0]["normalized_coverage"] == "full_tuition"


# ------------------------------------------------------------------ row building


def test_version_row_filter_columns(ds):
    row = next(r for r in ds.versions if r["version_id"] == "fixture-foundation-program-2027")
    assert row["program_id"] == FOUNDATION
    assert row["is_chain_head"] is True
    assert row["entry_year"] == 2027
    assert row["verification_status"] == "verified"
    assert row["selection_modes"] == ["automatic_guaranteed", "competitive"]
    assert row["residencies"] == ["any", "out_of_state"]
    assert row["national_merit_statuses"] == ["finalist"]
    assert row["need_roles"] == ["considered", "not_considered"]
    assert row["separate_application"] == "required"
    # The November 1 admission deadline is only "recommended"; December 1 is required.
    assert row["deadline_months"] == [12]
    assert row["key_deadline"] == "2026-12-01"
    assert row["latest_milestone_date"] == "2026-12-01"
    assert row["source_retrieved_at"] == "2026-11-08"


def test_rows_serialize_to_json_and_keep_the_record_verbatim(ds, docs):
    json.dumps(ds.programs)
    json.dumps(ds.versions)
    json.dumps(ds.sources)
    row = next(r for r in ds.versions if r["version_id"] == "fixture-foundation-program-2027")
    assert row["record"] == foundation(docs)["versions"][1]


def test_unverified_draft_row_has_empty_filters(ds):
    row = next(r for r in ds.versions if r["version_id"] == "fixture-parent-program-draft")
    assert row["entry_year"] is None
    assert row["verification_status"] == "unverified"
    assert row["coverages"] == [] and row["deadline_months"] == []
    assert row["key_deadline"] is None and row["separate_application"] is None


def test_rows_match_the_migration_columns(ds):
    sql = MIGRATION.read_text(encoding="utf-8")
    for table, rows in (
        ("scholarship_programs", ds.programs),
        ("scholarship_program_versions", ds.versions),
        ("scholarship_sources", ds.sources),
    ):
        cols, required = table_columns(sql, table)
        for row in rows:
            assert set(row) <= cols, (table, set(row) - cols)
            assert required <= set(row), (table, required - set(row))


def test_same_version_id_in_two_programs_gets_distinct_keys(docs):
    other = copy.deepcopy(foundation(docs))
    other["program_id"] = "another-program"
    docs["elsewhere/another-program.yaml"] = other
    out = model.build_dataset(docs)
    keys = [(r["program_id"], r["version_id"]) for r in out.versions]
    assert len(keys) == len(set(keys)) == 5
    versions_only = [r["version_id"] for r in out.versions]
    assert len(versions_only) != len(set(versions_only))  # the collision is real, the key is composite


def test_joint_program_expands_participants(docs):
    doc = foundation(docs)
    doc["participating_schools"] = [
        {"school_id": "uva", "ipeds_id": "234076"},
        {"school_id": "unc", "ipeds_id": "199120"},
    ]
    out = model.build_dataset(docs)
    program = out.program(FOUNDATION)
    assert [p["school_id"] for p in program["participating_schools"]] == ["uva", "unc"]


def test_single_school_program_lists_itself(ds):
    assert ds.program(FOUNDATION)["participating_schools"] == [{"school_id": "uva", "ipeds_id": "234076"}]


# ------------------------------------------------------ chain heads and selection


def test_chain_head_is_the_unsuperseded_version(docs):
    doc = foundation(docs)
    assert model.chain_heads(doc) == {"fixture-foundation-program-2026", "fixture-foundation-program-2027"}
    fix = copy.deepcopy(doc["versions"][1])
    fix["version_id"] = "fixture-foundation-program-2027b"
    fix["supersedes"] = "fixture-foundation-program-2027"
    doc["versions"].append(fix)
    assert model.chain_heads(doc) == {"fixture-foundation-program-2026", "fixture-foundation-program-2027b"}


def test_chain_of_three_has_one_head(docs):
    doc = foundation(docs)
    a = doc["versions"][1]
    b2 = dict(copy.deepcopy(a), version_id="v-b", supersedes=a["version_id"])
    c = dict(copy.deepcopy(a), version_id="v-c", supersedes="v-b")
    doc["versions"] += [b2, c]
    assert model.chain_heads(doc) == {"fixture-foundation-program-2026", "v-c"}


def selected(out: model.Dataset) -> List[Tuple[str, str]]:
    return [(r["program_id"], r["version_id"]) for r in model.select_published(out)]


def test_select_serves_latest_year_and_never_unverified(ds):
    # The parent has only an unverified draft: no row. The foundation serves 2027, not the
    # historical 2026 version.
    assert selected(ds) == [(FOUNDATION, "fixture-foundation-program-2027")]


def test_select_serves_correction_head_not_the_superseded_version(docs):
    doc = foundation(docs)
    fix = copy.deepcopy(doc["versions"][1])
    fix["version_id"] = "fixture-foundation-program-2027b"
    fix["supersedes"] = "fixture-foundation-program-2027"
    fix["verification_status"] = "conflicting"
    doc["versions"].append(fix)
    assert selected(model.build_dataset(docs)) == [(FOUNDATION, "fixture-foundation-program-2027b")]


def test_unverified_correction_hides_its_entry_year(docs):
    # Decision as recorded: serve the chain head, never unverified. A draft correction therefore
    # takes its year off the view until it is verified; the next-latest year is served.
    doc = foundation(docs)
    fix = copy.deepcopy(doc["versions"][1])
    fix["version_id"] = "fixture-foundation-program-2027b"
    fix["supersedes"] = "fixture-foundation-program-2027"
    fix["verification_status"] = "unverified"
    doc["versions"].append(fix)
    assert selected(model.build_dataset(docs)) == [(FOUNDATION, "fixture-foundation-program-2026")]


def test_select_ranks_null_entry_year_last(docs):
    doc = foundation(docs)
    undated = copy.deepcopy(doc["versions"][1])
    undated.update(version_id="v-undated", entry_year=None, entry_year_label="Year unclear")
    undated["application"]["milestones"] = []
    doc["versions"].append(undated)
    assert selected(model.build_dataset(docs)) == [(FOUNDATION, "fixture-foundation-program-2027")]
    doc["versions"][1]["verification_status"] = "unverified"
    assert selected(model.build_dataset(docs)) == [(FOUNDATION, "fixture-foundation-program-2026")]
    doc["versions"][0]["verification_status"] = "unverified"
    assert selected(model.build_dataset(docs)) == [(FOUNDATION, "v-undated")]


def test_select_with_nothing_publishable_is_empty(docs):
    for d in docs.values():
        for ver in d["versions"]:
            ver["verification_status"] = "unverified"
    assert selected(model.build_dataset(docs)) == []


# ----------------------------------------------------------- validate then load


def test_load_dataset_builds_rows_for_the_valid_fixtures():
    out, issues = load.load_dataset(FIXTURES)
    assert issues == [] and out is not None
    assert [p["program_id"] for p in out.programs] == [FOUNDATION, PARENT]
    assert len(out.versions) == 3 and len(out.sources) == 4
    assert out.programs[0]["file_path"].endswith("fixtures/valid/uva/fixture-foundation-program.yaml")


def test_load_dataset_refuses_an_invalid_tree(tmp_path):
    school = tmp_path / "uva"
    school.mkdir()
    text = (FIXTURES / "uva" / "fixture-foundation-program.yaml").read_text(encoding="utf-8")
    (school / "fixture-foundation-program.yaml").write_text(text.replace("'234076'", "'199120'"), encoding="utf-8")
    out, issues = load.load_dataset(tmp_path)
    assert out is None
    assert any(i.code == "E_IDENTITY" for i in issues)


def test_main_dry_run_validates_and_never_touches_the_database(monkeypatch, tmp_path, capsys):
    def boom(*_a, **_k):
        raise AssertionError("dry run must not build a database client")

    monkeypatch.setattr(load.SupabaseStore, "from_env", classmethod(boom))
    report = tmp_path / "report.json"
    assert load.main([str(FIXTURES), "--report", str(report)]) == 0
    out = capsys.readouterr().out
    assert "DRY RUN" in out and "1 would be served" in out
    data = json.loads(report.read_text(encoding="utf-8"))
    assert data["counts"] == {"programs": 2, "versions": 3, "sources": 4, "published_programs": 1}
    published = {p["program_id"]: p["published_version"] for p in data["programs"]}
    assert published == {FOUNDATION: "fixture-foundation-program-2027", PARENT: None}
    assert "applied" not in data


def test_main_aborts_on_validation_issues(monkeypatch, tmp_path, capsys):
    school = tmp_path / "wrong-dir"
    school.mkdir()
    text = (FIXTURES / "uva" / "fixture-foundation-program.yaml").read_text(encoding="utf-8")
    (school / "fixture-foundation-program.yaml").write_text(text, encoding="utf-8")
    monkeypatch.setattr(load.SupabaseStore, "from_env", classmethod(lambda *_: pytest.fail("no client")))
    assert load.main([str(tmp_path), "--apply", "--report", str(tmp_path / "r.json")]) == 1
    assert "nothing loaded" in capsys.readouterr().err


# ------------------------------------------------------------------ prune + apply


class FakeStore(load.Store):
    """In-memory store that records the order of writes."""

    def __init__(self, existing: load.Existing | None = None) -> None:  # type: ignore[name-defined]
        self._existing = existing or load.Existing()
        self.calls: List[Tuple[str, str, int]] = []
        self.rows: Dict[str, Dict[Tuple[str, ...], Dict[str, Any]]] = {t: {} for t in load.TABLE_KEYS}

    def existing(self) -> load.Existing:
        return self._existing

    def upsert(self, table, rows):
        self.calls.append(("upsert", table, len(rows)))
        for r in rows:
            self.rows[table][tuple(r[c] for c in load.TABLE_KEYS[table])] = r

    def delete(self, table, keys):
        self.calls.append(("delete", table, len(keys)))

    def refresh(self):
        self.calls.append(("refresh", "", 0))
        return 1


def test_compute_prune_lists_only_what_the_yaml_no_longer_has(ds):
    existing = load.Existing(
        programs={(FOUNDATION,), (PARENT,), ("gone",)},
        versions={
            (FOUNDATION, "fixture-foundation-program-2027"),
            (FOUNDATION, "fixture-foundation-program-2026"),
            (FOUNDATION, "stale"),
            ("gone", "gone-1"),
        },
        sources={
            (FOUNDATION, "fixture-foundation-program-2027", "s-school"),
            (FOUNDATION, "fixture-foundation-program-2027", "s-old"),
            (FOUNDATION, "stale", "s1"),
            ("gone", "gone-1", "s1"),
        },
    )
    prune = load.compute_prune(ds, existing)
    assert prune.programs == [("gone",)]
    # Versions and sources under a pruned program, or under a pruned version, cascade: not listed.
    assert prune.versions == [(FOUNDATION, "stale")]
    assert prune.sources == [(FOUNDATION, "fixture-foundation-program-2027", "s-old")]


def test_compute_prune_is_empty_when_database_matches(ds):
    existing = load.Existing(
        programs={(p["program_id"],) for p in ds.programs},
        versions={(r["program_id"], r["version_id"]) for r in ds.versions},
        sources={(r["program_id"], r["version_id"], r["source_id"]) for r in ds.sources},
    )
    assert load.compute_prune(ds, existing).empty()


def test_apply_writes_parents_first_prunes_last_then_refreshes(ds):
    store = FakeStore(load.Existing(programs={("gone",)}, versions={(FOUNDATION, "stale")}, sources=set()))
    result = load.apply(store, ds)
    assert [(c[0], c[1]) for c in store.calls] == [
        ("upsert", "scholarship_programs"),
        ("upsert", "scholarship_program_versions"),
        ("upsert", "scholarship_sources"),
        ("delete", "scholarship_program_versions"),
        ("delete", "scholarship_programs"),
        ("refresh", ""),
    ]
    assert result["upserted"]["published_programs"] == 1 and result["cache_rows"] == 1


def test_apply_is_idempotent(ds):
    first = FakeStore()
    load.apply(first, ds)
    again = FakeStore(
        load.Existing(
            programs=set(first.rows["scholarship_programs"]),
            versions=set(first.rows["scholarship_program_versions"]),
            sources=set(first.rows["scholarship_sources"]),
        )
    )
    load.apply(again, ds)
    assert first.rows == again.rows
    assert not [c for c in again.calls if c[0] == "delete"]


def test_apply_refuses_to_wipe_the_database_from_an_empty_tree():
    store = FakeStore(load.Existing(programs={(FOUNDATION,)}))
    with pytest.raises(load.RefusedError):
        load.apply(store, model.Dataset())
    assert store.calls == []  # refused before any write
    load.apply(store, model.Dataset(), allow_empty=True)
    assert ("delete", "scholarship_programs", 1) in store.calls


def test_apply_on_an_empty_tree_and_empty_database_is_fine():
    store = FakeStore()
    assert load.apply(store, model.Dataset())["upserted"]["programs"] == 0


# --------------------------------------------------------------------- migration


def table_columns(sql: str, table: str) -> Tuple[set, set]:
    """(all columns, required columns without a default) of a create table block."""
    m = re.search(rf"create table public\.{table} \((.*?)\n\);", sql, re.S)
    assert m, table
    cols, required = set(), set()
    for line in m.group(1).splitlines():
        mm = re.match(r"^  ([a-z0-9_]+) (\S.*)$", line)
        if not mm or mm.group(1) in {"primary", "foreign", "references", "check"}:
            continue
        cols.add(mm.group(1))
        rest = mm.group(2).lower()
        if "not null" in rest and "default" not in rest and "generated" not in rest:
            required.add(mm.group(1))
    return cols, required


def view_columns(sql: str) -> List[str]:
    block = sql.split("create view public.scholarship_directory", 1)[1].split("from public.scholarship_directory_cache c;", 1)[0]
    names = []
    for line in block.splitlines():
        m = re.match(r"^  c\.([a-z_]+),?$", line) or re.search(r"\bas ([a-z_]+),?\s*$", line)
        if m:
            names.append(m.group(1))
    return names


def test_migration_timestamp_is_unique_and_after_the_scholarship_record_format_work():
    names = sorted(p.name for p in (REPO / "supabase" / "migrations").glob("*.sql"))
    stamps = [n.split("_", 1)[0] for n in names]
    assert len(stamps) == len(set(stamps))
    assert MIGRATION.name.split("_", 1)[0] > "20261114150000"  # newest migration when this was written


def test_migration_access_model():
    sql = MIGRATION.read_text(encoding="utf-8")
    bases = ["scholarship_programs", "scholarship_program_versions", "scholarship_sources", "scholarship_version_checks"]
    for t in bases:
        assert f"alter table public.{t} enable row level security;" in sql
        assert f"revoke all on public.{t} from public, anon, authenticated;" in sql
    # Anon and authenticated read the view and the cache it reads, and nothing else.
    grants = re.findall(r"grant select on public\.(\w+) to anon, authenticated;", sql)
    assert sorted(grants) == ["scholarship_directory", "scholarship_directory_cache"]
    assert not re.search(r"grant (all|insert|update|delete)[^;]* to [^;]*(anon|authenticated)", sql)
    assert "with (security_invoker = true)" in sql
    assert "grant execute on function public.refresh_scholarship_directory_cache() to service_role;" in sql
    assert "revoke all on function public.refresh_scholarship_directory_cache() from public, anon, authenticated;" in sql
    assert "create unique index scholarship_directory_cache_program_school_uidx" in sql


def test_migration_view_never_uses_now_inside_the_cache():
    sql = MIGRATION.read_text(encoding="utf-8")
    cache = sql.split("create materialized view public.scholarship_directory_cache", 1)[1].split("comment on materialized view", 1)[0]
    assert "now()" not in cache and "current_date" not in cache  # frozen at refresh; the view computes it
    assert "verification_status <> 'unverified'" in cache and "is_chain_head" in cache


def test_migration_check_constraints_cover_schema_enums():
    schema = v.load_schema()
    sql = MIGRATION.read_text(encoding="utf-8")
    props = schema["properties"]
    for field in ("program_family", "awarding_authority", "status"):
        for value in props[field]["enum"]:
            assert f"'{value}'" in sql, (field, value)
    for value in schema["$defs"]["version"]["properties"]["verification_status"]["enum"]:
        assert f"'{value}'" in sql


# ----------------------------------------------------------------- view contract


def contract_columns(text: str) -> List[str]:
    section = text.split("## Columns", 1)[1].split("### `normalized_coverage`", 1)[0]
    return re.findall(r"^\| `([a-z_]+)` \|", section, re.M)


def test_contract_lists_exactly_the_view_columns_in_order():
    sql = MIGRATION.read_text(encoding="utf-8")
    assert contract_columns(CONTRACT.read_text(encoding="utf-8")) == view_columns(sql)


def test_contract_example_row_matches_the_view_columns():
    text = CONTRACT.read_text(encoding="utf-8")
    example = json.loads(text.split("```json\n", 1)[1].split("\n```", 1)[0])
    assert sorted(example) == sorted(view_columns(MIGRATION.read_text(encoding="utf-8")))
    assert example["license"] == model.LICENSE_ID
    assert example["attribution"] == model.ATTRIBUTION
    assert example["freshness_status"] in {
        "current_cycle_verified", "current_cycle_unconfirmed", "past_cycle", "conflicting",
    }
    assert example["verification_status"] != "unverified"
    assert all(o["normalized_coverage"] in model.NORMALIZED_COVERAGE for o in example["offers"])


def test_contract_example_row_agrees_with_the_loader_output(ds):
    text = CONTRACT.read_text(encoding="utf-8")
    example = json.loads(text.split("```json\n", 1)[1].split("\n```", 1)[0])
    version = next(r for r in ds.versions if r["version_id"] == example["version_id"])
    rec = model.public_record(ds.program(FOUNDATION), version, {"school_id": "uva", "ipeds_id": "234076"})
    for key, value in rec.items():
        assert example[key] == value, key


def test_freshness_rule_is_stated_in_the_migration_and_the_contract():
    sql = MIGRATION.read_text(encoding="utf-8")
    contract = CONTRACT.read_text(encoding="utf-8")
    for state in ("current_cycle_verified", "current_cycle_unconfirmed", "past_cycle", "conflicting"):
        assert state in sql and state in contract
    assert "1 July" in sql and "1 July" in contract
