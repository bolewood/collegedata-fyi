"""Tests for the scholarship loader and row model (PRD 036 M2). No network, no database.

The SQL itself is exercised by hand against a throwaway local Postgres (see the
PR notes); these tests pin the Python that feeds it and keep the migration, the
view contract and the attribution string in step.
"""

from __future__ import annotations

import copy
import datetime as dt
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
# The migration that last (re)defined the cache and the view: a materialized view cannot gain a
# column in place, so the other_info migration recreates both. Column and cache pins read this one.
VIEW_MIGRATION = sorted((REPO / "supabase" / "migrations").glob("*_scholarship_directory*.sql"))[-1]
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


def b(
    category: str,
    instrument: str = "scholarship",
    coverage: str = "full",
    qualifier: Any = None,
    conditions: Any = None,
) -> Dict[str, Any]:
    out: Dict[str, Any] = {"benefit_id": f"b-{category}", "category": category, "instrument": instrument, "coverage": coverage}
    if qualifier:
        out["amount"] = {"qualifier": qualifier, "value": 15000 if qualifier != "not_published" else None}
    if conditions:
        out["conditions_text"] = conditions
    return out


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
        ([b("housing")], "partial_or_fixed"),  # full housing alone is not tuition coverage, but it is not nothing
        ([b("tuition", instrument="unknown")], "other"),  # cannot prove it is a scholarship
        ([b("tuition", instrument="earned_compensation")], "other"),
        # A waiver of tuition itself counts as tuition coverage (Hawaii at Manoa Regents).
        ([b("tuition", instrument="tuition_waiver")], "full_tuition"),
        ([b("tuition", instrument="tuition_waiver"), b("stipend", "cash_stipend", "fixed_amount")], "full_tuition"),
        ([b("tuition", instrument="tuition_waiver"), b("mandatory_fees")], "full_tuition_fees"),
        ([b("tuition", instrument="tuition_waiver", coverage="partial")], "partial_or_fixed"),
        ([b("tuition", instrument="tuition_waiver", qualifier="up_to")], "partial_or_fixed"),
        ([b("tuition", instrument="tuition_waiver", conditions="needs $4,000 in other scholarships")], "partial_or_fixed"),
        ([b("tuition", instrument="tuition_waiver", coverage="unknown")], "other"),
        # A waiver of anything else, or of the out-of-state differential, never counts.
        ([b("mandatory_fees", instrument="tuition_waiver")], "other"),
        ([b("nonresident_differential", instrument="tuition_waiver")], "other"),
        ([b("nonresident_differential", instrument="scholarship")], "other"),
        ([b("nonresident_differential", instrument="tuition_waiver", coverage="partial")], "other"),
        (
            [b("tuition", instrument="tuition_waiver"), b("mandatory_fees"), b("housing"), b("meals")],
            "tuition_housing_meals",  # a full tuition waiver fills the tuition slot of a bracket
        ),
        (
            [b("nonresident_differential", instrument="tuition_waiver"), b("mandatory_fees"), b("housing"), b("meals")],
            "partial_or_fixed",  # the differential waiver does not
        ),
        # Review 4: `full` with a capped or inexact amount is not full.
        ([b("tuition", qualifier="up_to")], "partial_or_fixed"),
        ([b("tuition", qualifier="at_least")], "partial_or_fixed"),
        ([b("tuition", qualifier="approximate")], "partial_or_fixed"),
        ([b("tuition", qualifier="exact")], "full_tuition"),
        ([b("tuition", qualifier="not_published")], "full_tuition"),
        # Review 5: full tuition paid from a restricted fund is still full tuition.
        ([b("tuition", instrument="restricted_fund")], "full_tuition"),
        ([b("tuition", instrument="cash_stipend")], "partial_or_fixed"),
        # Review 7: a stipend of unknown size does not unlock cost of attendance.
        (
            [b("tuition"), b("mandatory_fees"), b("housing"), b("meals"), b("books"), b("stipend", "cash_stipend", "unknown")],
            "tuition_housing_meals",
        ),
        # A benefit with conditions_text never counts toward a full_* label.
        ([b("tuition", conditions="needs $4,000 in other scholarships")], "partial_or_fixed"),
        ([b("tuition"), b("mandatory_fees", conditions="if enrolled in honors")], "full_tuition"),
        (
            [b("tuition"), b("mandatory_fees"), b("housing"), b("meals"), b("books"), b("stipend", "cash_stipend", "fixed_amount", conditions="summer only")],
            "tuition_housing_meals",
        ),
        # cost_of_attendance, full, scholarship instrument: full_school_coa.
        ([b("cost_of_attendance")], "full_school_coa"),
        ([b("cost_of_attendance", qualifier="not_published")], "full_school_coa"),
        ([b("cost_of_attendance", conditions="while on campus")], "partial_or_fixed"),
        ([b("cost_of_attendance", instrument="tuition_waiver")], "other"),
        ([b("cost_of_attendance", instrument="restricted_fund")], "partial_or_fixed"),
        ([b("cost_of_attendance", qualifier="up_to")], "partial_or_fixed"),
        ([b("cost_of_attendance", coverage="partial")], "partial_or_fixed"),
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


def test_fixture_offers_derive_with_ancestors(ds):
    version = next(r for r in ds.versions if r["version_id"] == "fixture-foundation-program-2027")
    by_offer = {o["offer_id"]: o["normalized_coverage"] for o in version["offers"]}
    # o-main has a full cost_of_attendance scholarship. o-tier is its child whose own benefit
    # is only a (conditional) differential waiver; it inherits the parent's package.
    assert by_offer == {"o-main": "full_school_coa", "o-tier": "full_school_coa"}
    assert version["coverages"] == ["full_school_coa"]


def offer(oid: str, benefits, parent=None) -> Dict[str, Any]:
    return {"offer_id": oid, "parent_offer_id": parent, "benefits": benefits}


def test_child_offer_adds_to_its_ancestors_and_the_parent_is_unchanged():
    # Review 6: a tier lists only what it adds.
    offers = [
        offer("o-main", [b("tuition")]),
        offer("o-finalist", [b("housing"), b("meals")], parent="o-main"),
        offer("o-grand", [b("books")], parent="o-finalist"),
    ]
    got = {o["offer_id"]: o["normalized_coverage"] for o in model.derive_offers(offers)}
    assert got == {"o-main": "full_tuition", "o-finalist": "tuition_housing_meals", "o-grand": "tuition_housing_meals"}


def test_child_with_undocumented_benefits_stays_unknown_and_ancestor_waivers_do_not_count():
    offers = [
        offer("o-main", [b("nonresident_differential", "tuition_waiver")]),
        offer("o-unknown", None, parent="o-main"),
        offer("o-kid", [b("housing")], parent="o-main"),
    ]
    got = {o["offer_id"]: o["normalized_coverage"] for o in model.derive_offers(offers)}
    assert got == {"o-main": "other", "o-unknown": None, "o-kid": "partial_or_fixed"}


def test_advertised_totals_pass_through_and_never_derive_coverage(ds):
    version = next(r for r in ds.versions if r["version_id"] == "fixture-foundation-program-2027")
    main = version["record"]["offers"][0]
    assert main["advertised_totals"][0]["amount"]["value"] == 89000
    assert version["offers"][0]["advertised_totals"] == main["advertised_totals"]
    only_total = offer("o", [])
    only_total["advertised_totals"] = [{"amount": {"qualifier": "at_least", "value": 89000}, "scope_text": "advertised"}]
    assert model.derive_offers([only_total])[0]["normalized_coverage"] == "other"


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
    assert row["statuses_required"] == ["scholar"]  # new enum value loads and is filterable
    assert row["need_roles"] == ["considered", "not_considered"]
    assert row["separate_application"] == "required"
    # The November 1 admission deadline is only "recommended"; December 1 is required.
    assert row["deadline_months"] == [12]
    assert row["key_deadline"] == "2026-12-01"
    assert row["cycle_through_date"] == "2026-12-01"
    assert row["is_published"] is True
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


def add_version(doc: Dict[str, Any], vid: str, **changes: Any) -> Dict[str, Any]:
    ver = copy.deepcopy(doc["versions"][1])
    ver["version_id"] = vid
    ver.update(changes)
    doc["versions"].append(ver)
    return ver


def test_select_serves_latest_year_and_never_unverified(ds):
    # The parent has only an unverified draft: no row. The foundation serves 2027, not the
    # historical 2026 version.
    assert selected(ds) == [(FOUNDATION, "fixture-foundation-program-2027")]


def test_select_serves_correction_head_not_the_superseded_version(docs):
    doc = foundation(docs)
    add_version(doc, "fixture-foundation-program-2027b", supersedes="fixture-foundation-program-2027", verification_status="conflicting")
    assert selected(model.build_dataset(docs)) == [(FOUNDATION, "fixture-foundation-program-2027b")]


def test_unverified_correction_leaves_the_verified_version_published(docs):
    # Review 1: the newest publishable member of the chain is served. An unverified
    # correction must not hide the verified version it supersedes.
    doc = foundation(docs)
    add_version(doc, "fixture-foundation-program-2027b", supersedes="fixture-foundation-program-2027", verification_status="unverified")
    out = model.build_dataset(docs)
    assert selected(out) == [(FOUNDATION, "fixture-foundation-program-2027")]
    flags = {r["version_id"]: r["is_published"] for r in out.versions if r["program_id"] == FOUNDATION}
    assert flags == {
        "fixture-foundation-program-2026": True,
        "fixture-foundation-program-2027": True,
        "fixture-foundation-program-2027b": False,
    }


def test_published_walks_back_through_a_chain_of_unverified_corrections(docs):
    doc = foundation(docs)
    add_version(doc, "v-b", supersedes="fixture-foundation-program-2027", verification_status="unverified")
    add_version(doc, "v-c", supersedes="v-b", verification_status="unverified")
    assert model.published_ids(doc) == {"fixture-foundation-program-2026", "fixture-foundation-program-2027"}
    doc["versions"][1]["verification_status"] = "unverified"
    assert model.published_ids(doc) == {"fixture-foundation-program-2026"}  # a wholly unverified chain publishes nothing


def test_rank_year_for_undated_versions():
    assert model.rank_year(2027, "2026-01-01", "2020-01-01") == 2027
    assert model.rank_year(None, "2026-12-01", None) == 2027  # Dec 2026 falls in the 2027 cycle
    assert model.rank_year(None, "2026-06-30", None) == 2026
    assert model.rank_year(None, None, "2026-11-08") == 2027  # no milestones: the retrieval day
    assert model.rank_year(None, None, None) is None


def undated(doc: Dict[str, Any], vid: str, milestone: Any) -> None:
    ver = add_version(doc, vid, entry_year=None, entry_year_label="Year not stated")
    ms = [] if milestone is None else [
        {"kind": "application_deadline", "requirement": "required", "date": milestone, "recurring": None, "precision": "day", "source_date_text": "x"}
    ]
    ver["application"]["milestones"] = ms
    ver["field_evidence"] = [e for e in ver["field_evidence"] if not e["field_path"].startswith("application/milestones")]
    ver["field_evidence"].append(
        {"field_path": "entry_year", "source_ref": "s-school", "locator": "page", "short_excerpt": None, "value_status": "not_published", "reported_value": None}
    )


def test_undated_version_ranks_by_cycle_through_date(docs):
    # Review 8A + decision A: the school's current page names no class, only a Dec 2026 deadline.
    # That is the 2027 cycle, so it ties the dated 2027 version (dated wins) and beats a dated 2026 one.
    doc = foundation(docs)
    undated(doc, "v-undated", "2026-12-15")
    assert selected(model.build_dataset(docs)) == [(FOUNDATION, "fixture-foundation-program-2027")]
    doc["versions"][1]["verification_status"] = "unverified"  # now only 2026 (dated) vs undated Dec 2026
    assert selected(model.build_dataset(docs)) == [(FOUNDATION, "v-undated")]


def test_undated_version_with_no_milestones_ranks_by_retrieval_day(docs):
    doc = foundation(docs)
    undated(doc, "v-no-dates", None)  # retrieved 2026-11-08 -> cycle 2027
    doc["versions"][1]["verification_status"] = "unverified"  # leaves historical 2026 vs the undated one
    assert selected(model.build_dataset(docs)) == [(FOUNDATION, "v-no-dates")]


def test_undated_old_version_does_not_beat_a_newer_dated_one(docs):
    doc = foundation(docs)
    undated(doc, "v-old", "2025-12-01")  # 2026 cycle
    assert selected(model.build_dataset(docs)) == [(FOUNDATION, "fixture-foundation-program-2027")]


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
    load.apply(store, model.Dataset(), allow_prune=True)
    assert ("delete", "scholarship_programs", 1) in store.calls


def existing_programs(n: int) -> load.Existing:
    return load.Existing(programs={(f"p{i}",) for i in range(n)} | {(FOUNDATION,), (PARENT,)})


def test_prune_guard_refuses_a_mass_removal_not_just_an_empty_tree(ds):
    # Review 11: a checkout with one school's YAML would otherwise delete everything else.
    store = FakeStore(existing_programs(40))  # 42 in the database, 2 in the tree: 40 would go
    with pytest.raises(load.RefusedError, match="remove 40 of 42"):
        load.apply(store, ds)
    assert store.calls == []
    assert load.apply(FakeStore(existing_programs(40)), ds, allow_prune=True)["pruned"]["programs"]


def test_prune_guard_limits(ds):
    # 6 programs of 100 is over the 5-program limit; 5 of 100 is fine; 2 of 12 is over 10%.
    big = lambda n, total: load.Existing(programs={(f"p{i}",) for i in range(n)} | {(f"keep{i}",) for i in range(total - n - 2)} | {(FOUNDATION,), (PARENT,)})  # noqa: E731
    keep_all = model.Dataset(programs=[{"program_id": f"keep{i}"} for i in range(200)] + list(ds.programs), versions=[], sources=[])
    with pytest.raises(load.RefusedError):
        load.check_prune_guard(load.compute_prune(keep_all, big(6, 108)), big(6, 108), False)
    load.check_prune_guard(load.compute_prune(keep_all, big(5, 108)), big(5, 108), False)
    with pytest.raises(load.RefusedError):
        load.check_prune_guard(load.compute_prune(keep_all, big(2, 14)), big(2, 14), False)
    # One program may always be removed.
    load.check_prune_guard(load.compute_prune(keep_all, big(1, 8)), big(1, 8), False)


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
    sql = VIEW_MIGRATION.read_text(encoding="utf-8")
    cache = sql.split("create materialized view public.scholarship_directory_cache", 1)[1].split("comment on materialized view", 1)[0]
    assert "now()" not in cache and "current_date" not in cache  # frozen at refresh; the view computes it
    assert "v.is_published" in cache and "is_chain_head" not in cache  # review 1: serve the newest publishable version
    assert "scholarship_cycle_year(v.cycle_through_date)" in cache  # decision A: rank an undated version by its dates
    assert "'field_path'" in cache and "short_excerpt" not in cache  # review 2: locators, never excerpts


def test_migration_check_constraints_cover_schema_enums():
    schema = v.load_schema()
    sql = MIGRATION.read_text(encoding="utf-8")
    props = schema["properties"]
    for field in ("program_family", "awarding_authority", "status"):
        for value in props[field]["enum"]:
            assert f"'{value}'" in sql, (field, value)
    for value in schema["$defs"]["version"]["properties"]["verification_status"]["enum"]:
        assert f"'{value}'" in sql
    for value in schema["$defs"]["source"]["properties"]["authority"]["enum"]:
        assert f"'{value}'" in sql, value  # scholarship_sources.authority CHECK


# ----------------------------------------------------------------- view contract


def contract_columns(text: str) -> List[str]:
    section = text.split("## Columns", 1)[1].split("### `normalized_coverage`", 1)[0]
    return re.findall(r"^\| `([a-z_]+)` \|", section, re.M)


def test_contract_lists_exactly_the_view_columns_in_order():
    sql = MIGRATION.read_text(encoding="utf-8")
    assert contract_columns(CONTRACT.read_text(encoding="utf-8")) == view_columns(VIEW_MIGRATION.read_text(encoding="utf-8"))


def test_contract_example_row_matches_the_view_columns():
    text = CONTRACT.read_text(encoding="utf-8")
    example = json.loads(text.split("```json\n", 1)[1].split("\n```", 1)[0])
    assert sorted(example) == sorted(view_columns(VIEW_MIGRATION.read_text(encoding="utf-8")))
    assert example["license"] == model.LICENSE_ID
    assert example["attribution"] == model.ATTRIBUTION
    assert example["freshness_status"] in {
        "current_cycle_verified", "year_not_stated", "current_cycle_unconfirmed", "past_cycle", "conflicting",
    }
    assert example["verification_status"] != "unverified"
    assert all(o["normalized_coverage"] in model.NORMALIZED_COVERAGE for o in example["offers"])


def full_row(ds: model.Dataset, today: dt.date) -> Dict[str, Any]:
    version = model.select_published(ds)[0]
    rec = model.public_record(ds.program(version["program_id"]), version, {"school_id": "uva", "ipeds_id": "234076"})
    rec["freshness_status"] = model.freshness_status(
        rec["entry_year"], rec["verification_status"], rec["cycle_through_date"], rec["last_reviewed_at"], None, None, today
    )
    rec["current_entry_year"] = model.current_entry_year(today)
    rec.update(last_check_at=None, last_check_result=None, needs_review=None, license=model.LICENSE_ID, attribution=model.ATTRIBUTION)
    return rec


def test_contract_example_row_agrees_with_the_loader_output(ds):
    text = CONTRACT.read_text(encoding="utf-8")
    example = json.loads(text.split("```json\n", 1)[1].split("\n```", 1)[0])
    assert example == full_row(ds, dt.date(2026, 11, 14))
    assert list(example) == view_columns(VIEW_MIGRATION.read_text(encoding="utf-8"))  # same order as the view


def test_freshness_rule_is_stated_in_the_migration_and_the_contract():
    sql = MIGRATION.read_text(encoding="utf-8")
    contract = CONTRACT.read_text(encoding="utf-8")
    for state in ("current_cycle_verified", "year_not_stated", "current_cycle_unconfirmed", "past_cycle", "conflicting"):
        assert state in sql and state in contract
    assert "1 July" in sql and "1 July" in contract


# ------------------------------------------------------------ freshness reference


def fr(entry_year, status="verified", through=None, result=None, review=None, today="2026-11-14", reviewed="2026-11-01"):
    return model.freshness_status(entry_year, status, through, reviewed, result, review, dt.date.fromisoformat(today))


def test_cycle_rollover_is_on_1_july():
    assert model.current_entry_year(dt.date(2026, 6, 30)) == 2026
    assert model.current_entry_year(dt.date(2026, 7, 1)) == 2027
    assert model.current_entry_year(dt.date(2026, 12, 31)) == 2027
    assert model.current_entry_year(dt.date(2027, 1, 1)) == 2027


def test_explicit_entry_year_rule_is_kept():
    assert fr(2027) == "current_cycle_verified"
    assert fr(2028) == "current_cycle_verified"
    assert fr(2026) == "past_cycle"
    assert fr(2026, today="2026-06-30") == "current_cycle_verified"
    assert fr(2027, today="2027-07-01") == "past_cycle"  # the 2028 cycle has opened
    assert fr(2027, through="2026-01-01") == "current_cycle_verified"  # milestones never override an explicit year
    assert fr(2027, review=True) == "current_cycle_unconfirmed"


def test_decision_a_undated_versions_use_their_milestone_dates():
    assert model.cycle_basis(None, "2026-12-01") == "milestone_dates"
    assert model.cycle_basis(None, None) == "none"
    assert model.cycle_basis(2027, "2026-12-01") == "entry_year"
    # Latest dated milestone today or later, verified, no needs_review: current.
    assert fr(None, through="2026-11-14") == "current_cycle_verified"
    assert fr(None, through="2027-03-01") == "current_cycle_verified"
    # Every dated milestone past: past_cycle.
    assert fr(None, through="2026-11-13") == "past_cycle"
    # No dated milestone at all (a recurring month/day never counts): year_not_stated, see below.
    assert fr(None, through=None) == "year_not_stated"
    # needs_review, or a status other than verified, still unconfirms.
    assert fr(None, through="2027-03-01", review=True) == "current_cycle_unconfirmed"
    assert fr(None, status="unverified", through="2027-03-01") == "current_cycle_unconfirmed"


def test_year_not_stated_ages_out_on_the_1_july_after_review():
    assert fr(None, reviewed="2026-11-01", today="2027-06-30") == "year_not_stated"
    assert fr(None, reviewed="2026-11-01", today="2027-07-01") == "past_cycle"
    assert fr(None, reviewed="2026-03-01", today="2026-06-30") == "year_not_stated"
    assert fr(None, reviewed="2026-03-01", today="2026-07-01") == "past_cycle"
    assert fr(None, reviewed="2026-07-01", today="2027-06-30") == "year_not_stated"  # review on a 1 July waits a year
    assert model.year_not_stated_expiry("2026-07-01") == dt.date(2027, 7, 1)
    assert model.year_not_stated_expiry("2026-06-30") == dt.date(2026, 7, 1)
    # Only verified, unflagged versions get year_not_stated or age out this way.
    assert fr(None, review=True) == "current_cycle_unconfirmed"
    assert fr(None, review=True, today="2028-01-01") == "current_cycle_unconfirmed"
    assert fr(None, status="unverified") == "current_cycle_unconfirmed"
    assert fr(None, status="conflicting", today="2028-01-01") == "conflicting"
    # Explicit-year and dated-milestone versions are not affected by the review date.
    assert fr(2027, today="2027-06-30", reviewed="2025-01-01") == "current_cycle_verified"
    assert fr(None, through="2027-03-01", reviewed="2025-01-01") == "current_cycle_verified"


def test_conflicting_and_historical_precedence():
    assert fr(2026, status="conflicting") == "conflicting"  # conflicting before past_cycle
    assert fr(2027, result="conflicting") == "conflicting"
    assert fr(2027, status="historical_only") == "past_cycle"
    assert fr(None, status="historical_only", through="2027-03-01") == "past_cycle"


# ------------------------------------------------------- migration text pins


def test_helper_functions_pin_their_search_path():
    sql = MIGRATION.read_text(encoding="utf-8")
    for name in ("scholarship_cycle_year", "scholarship_current_entry_year", "scholarship_cycle_basis", "scholarship_freshness_status"):
        block = sql.split(f"create function public.{name}(", 1)[1].split("$$;", 1)[0]
        assert "set search_path = pg_catalog, public" in block, name


def test_view_pins_the_attribution_and_license_literals():
    sql = MIGRATION.read_text(encoding="utf-8")
    assert f"'{model.ATTRIBUTION}'::text as attribution" in sql
    assert f"'{model.LICENSE_ID}'::text as license" in sql


def test_view_exposes_last_check_result_on_purpose():
    # Review 9: the cache is readable by anon, so every cache column the view omits would be a
    # second, undocumented endpoint. The cache and the view agree except for computed columns.
    sql = VIEW_MIGRATION.read_text(encoding="utf-8")
    cache = sql.split("create materialized view public.scholarship_directory_cache", 1)[1].split("comment on materialized view", 1)[0]
    cache_cols = set(re.findall(r"\bas ([a-z_]+),?$", cache, re.M)) | set(re.findall(r"^  [a-z]+\.([a-z_]+),?$", cache, re.M))
    hidden = cache_cols - set(view_columns(sql))
    assert hidden == set(), hidden


def test_reload_workflow_triggers_on_derivation_code():
    wf = (REPO / ".github" / "workflows" / "scholarships-load.yml").read_text(encoding="utf-8")
    for path in ("tools/scholarships/model.py", "tools/scholarships/load.py", "supabase/migrations/*_scholarship_directory.sql", "data/scholarships/**"):
        assert f'- "{path}"' in wf, path
    assert "allow_prune" in wf and "dispatch this workflow once" in wf


def test_report_lists_every_participating_school_for_revalidation(ds):
    """The load workflow tells the web app which school pages to refresh from this list."""
    report = load.build_report(ds, None)
    expected = sorted({s["school_id"] for p in ds.programs for s in model.participants_of(p)})
    assert report["school_ids"] == expected and expected


# ------------------------------------------------------------------ other_info


def docs_with_other_info() -> Dict[str, Dict[str, Any]]:
    docs = fixture_docs()
    ver = next(v_ for v_ in foundation(docs)["versions"] if v_["version_id"] == "fixture-foundation-program-2027")
    ver["other_info"] = [
        {"text": "A student may hold only one merit scholarship.", "source_ref": "s-school"},
        {"text": "Entry is in the fall term only.", "source_ref": "s-foundation"},
    ]
    for i in range(2):
        ver["field_evidence"].append(
            {"field_path": f"other_info/{i}", "source_ref": ver["other_info"][i]["source_ref"], "locator": "x",
             "value_status": "reported", "short_excerpt": "one merit scholarship"}
        )
    return docs


def test_other_info_round_trips_through_the_loader_and_the_public_record():
    docs = docs_with_other_info()
    ds = model.build_dataset(docs, root=REPO)
    row = next(r for r in ds.versions if r["version_id"] == "fixture-foundation-program-2027")
    assert [e["text"] for e in row["record"]["other_info"]] == [
        "A student may hold only one merit scholarship.",
        "Entry is in the fall term only.",
    ]  # the stored record keeps the key verbatim
    json.dumps(ds.versions)  # and the rows still serialize
    program = ds.program(row["program_id"])
    rec = model.public_record(program, row, model.participants_of(program)[0])
    urls = {s["source_id"]: s["url"] for s in row["record"]["sources"]}
    assert rec["other_info"] == [
        {"text": "A student may hold only one merit scholarship.", "source_ref": "s-school", "source_url": urls["s-school"]},
        {"text": "Entry is in the fall term only.", "source_ref": "s-foundation", "source_url": urls["s-foundation"]},
    ]
    assert "short_excerpt" not in json.dumps(rec["other_info"]) and "one merit scholarship\"" not in json.dumps(rec["other_info"])


def test_other_info_is_empty_when_absent_or_null(ds, docs):
    for row in ds.versions:
        program = ds.program(row["program_id"])
        assert model.public_record(program, row, model.participants_of(program)[0])["other_info"] == []
    foundation(docs)["versions"][1]["other_info"] = None
    ds2 = model.build_dataset(docs, root=REPO)
    row = next(r for r in ds2.versions if r["version_id"] == "fixture-foundation-program-2027")
    assert model.public_record(ds2.program(row["program_id"]), row, {"school_id": "uva", "ipeds_id": "234076"})["other_info"] == []


def test_other_info_changes_no_derived_value():
    base = model.build_dataset(fixture_docs(), root=REPO)
    withinfo = model.build_dataset(docs_with_other_info(), root=REPO)
    keep = lambda r: {k: r[k] for k in r if k != "record"}  # noqa: E731
    key = lambda r: (r["program_id"], r["version_id"])  # noqa: E731
    assert sorted(map(keep, base.versions), key=key) == sorted(map(keep, withinfo.versions), key=key)


def test_other_info_validates_through_the_tree():
    docs = docs_with_other_info()
    ctx = v.load_context()
    ctx.program_ids = {"fixture-parent-program", "fixture-foundation-program"}
    assert v.validate_doc(foundation(docs), ctx, "fixture") == []


def test_other_info_migration_recreates_cache_and_view_with_the_same_access():
    sql = VIEW_MIGRATION.read_text(encoding="utf-8")
    assert VIEW_MIGRATION != MIGRATION
    assert sql.index("drop view public.scholarship_directory;") < sql.index("drop materialized view public.scholarship_directory_cache;")
    assert "with (security_invoker = true)" in sql
    for obj in ("scholarship_directory", "scholarship_directory_cache"):
        assert f"revoke all on public.{obj} from public, anon, authenticated;" in sql
        assert f"grant select on public.{obj} to anon, authenticated;" in sql
    assert not re.search(r"grant (all|insert|update|delete)[^;]* to [^;]*(anon|authenticated)", sql)
    for idx in ("scholarship_directory_cache_program_school_uidx", "scholarship_directory_cache_school_idx",
                "scholarship_directory_cache_coverages_idx", "scholarship_directory_cache_nm_idx"):
        assert f"create unique index {idx}" in sql or f"create index {idx}" in sql
    assert f"'{model.ATTRIBUTION}'::text as attribution" in sql and f"'{model.LICENSE_ID}'::text as license" in sql
    assert "coalesce(oi.other_info, '[]'::jsonb) as other_info" in sql
    assert "short_excerpt" not in sql
