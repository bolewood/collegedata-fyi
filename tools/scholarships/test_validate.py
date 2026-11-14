"""Tests for tools/scholarships/validate.py (PRD 036 M1). No network.

Every rejecting case is the valid fixture plus exactly one mutation, and the
test asserts the exact set of error codes, so a case cannot pass by failing
for an unrelated reason.
"""

from __future__ import annotations

import copy
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import validate as v  # noqa: E402

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "valid"
MAIN = FIXTURES / "uva" / "fixture-foundation-program.yaml"
REPO = v.REPO_ROOT
ATTRIBUTION = (
    "Scholarship program data from collegedata.fyi (https://collegedata.fyi/scholarships), "
    "CC BY-SA 4.0. Terms as published by each school; see the source link on each record."
)


@pytest.fixture(scope="module")
def ctx() -> v.Context:
    c = v.load_context()
    c.program_ids = {"fixture-parent-program", "fixture-foundation-program"}
    return c


@pytest.fixture()
def doc() -> dict:
    return v.load_yaml_text(MAIN.read_text(encoding="utf-8"))


def codes(issues) -> set[str]:
    return {i.code for i in issues}


def version27(d: dict) -> dict:
    return d["versions"][1]


def drop_evidence(d: dict, path: str) -> None:
    ver = version27(d)
    ver["field_evidence"] = [e for e in ver["field_evidence"] if e["field_path"] != path]


# ----------------------------------------------------------------- valid cases


def test_valid_fixture_passes(doc, ctx):
    assert v.validate_doc(doc, ctx, "fixture") == []


def test_valid_fixture_exercises_required_shapes(doc):
    ver = version27(doc)
    assert any(o["parent_offer_id"] for o in ver["offers"])  # nested offer
    assert any(e["value_status"] == "conflicting" for e in ver["field_evidence"])
    assert any(m["recurring"] and m["date"] is None for m in ver["application"]["milestones"])
    assert any(s["authority"] == "foundation_official" for s in ver["sources"])


def test_fixture_tree_validates_with_cross_file_relation():
    assert v.validate_tree(FIXTURES) == []


def test_empty_or_missing_programs_dir_is_valid(tmp_path):
    assert v.validate_tree(tmp_path) == []
    assert v.validate_tree(tmp_path / "does-not-exist") == []
    assert v.main([str(tmp_path)]) == 0


def test_checked_in_programs_dir_is_valid():
    assert v.validate_tree(v.DEFAULT_PROGRAMS_DIR) == []


# --------------------------------------------------------------- banned patterns


def test_rejects_automatic_guaranteed_without_evidence(doc, ctx):
    drop_evidence(doc, "offers/1/selection_mode")
    assert codes(v.validate_doc(doc, ctx)) == {"E_GUARANTEED_NO_EVIDENCE"}


def test_rejects_automatic_guaranteed_with_evidence_but_no_quote(doc, ctx):
    for e in version27(doc)["field_evidence"]:
        if e["field_path"] == "offers/1/selection_mode":
            e["short_excerpt"] = None
    assert codes(v.validate_doc(doc, ctx)) == {"E_GUARANTEED_NO_EVIDENCE"}


def test_rejects_summed_total(doc, ctx):
    drop_evidence(doc, "offers/0/benefits/2/amount")
    assert codes(v.validate_doc(doc, ctx)) == {"E_SUMMED_TOTAL"}


def test_rejects_total_backed_only_by_not_published(doc, ctx):
    for e in version27(doc)["field_evidence"]:
        if e["field_path"] == "offers/0/benefits/2/amount":
            e["value_status"] = "not_published"
    assert codes(v.validate_doc(doc, ctx)) == {"E_SUMMED_TOTAL"}


def test_rejects_off_domain_source(doc, ctx):
    version27(doc)["sources"][0]["url"] = "https://scholarship-hub.example.com/fixture"
    assert codes(v.validate_doc(doc, ctx)) == {"E_OFF_DOMAIN"}


def test_rejects_look_alike_domain(doc, ctx):
    version27(doc)["sources"][0]["url"] = "https://notvirginia.edu/fixture"
    assert codes(v.validate_doc(doc, ctx)) == {"E_OFF_DOMAIN"}


def test_rejects_foundation_source_outside_allowlist(doc, ctx):
    version27(doc)["sources"][1]["url"] = "https://www.moreheadcain.org/fixture"  # UNC's foundation, not UVA's
    assert codes(v.validate_doc(doc, ctx)) == {"E_OFF_DOMAIN"}


def test_rejects_non_official_authority_by_schema(doc, ctx):
    version27(doc)["sources"][0]["authority"] = "third_party_directory"
    assert codes(v.validate_doc(doc, ctx)) == {"E_SCHEMA"}


def test_rejects_mismatched_school_and_ipeds(doc, ctx):
    doc["ipeds_id"] = "199120"  # UNC's UNITID on a UVA record
    assert codes(v.validate_doc(doc, ctx)) == {"E_IDENTITY"}


def test_rejects_unknown_school_and_retired_alias(doc, ctx):
    doc["school_id"] = "no-such-school"
    assert codes(v.validate_doc(doc, ctx)) == {"E_IDENTITY"}


def test_rejects_ipeds_not_in_snapshot(doc, ctx):
    bad = copy.copy(ctx)
    bad.snapshot = {}
    assert codes(v.validate_doc(doc, bad)) == {"E_IDENTITY"}


# --------------------------------------------------------- other required checks


def test_rejects_missing_evidence_on_publication_grade_field(doc, ctx):
    drop_evidence(doc, "offers/0/benefits/1/amount")
    assert codes(v.validate_doc(doc, ctx)) == {"E_NO_EVIDENCE"}


def test_evidence_on_a_parent_path_covers_children(doc, ctx):
    ver = version27(doc)
    drop_evidence(doc, "offers/0/benefits/1/amount")
    ver["field_evidence"].append(
        {
            "field_path": "offers/0/benefits/1",
            "source_ref": "s-foundation",
            "locator": "Benefits table",
            "value_status": "reported",
        }
    )
    assert v.validate_doc(doc, ctx) == []


def test_rejects_milestone_outside_cycle(doc, ctx):
    doc["versions"][1]["application"]["milestones"][0]["date"] = "2025-12-01"
    assert codes(v.validate_doc(doc, ctx)) == {"E_MILESTONE_WINDOW"}


def test_recurring_milestone_is_exempt_from_cycle(doc, ctx):
    doc["versions"][1]["application"]["milestones"][1]["recurring"] = {"month": 1, "day": 2}
    assert v.validate_doc(doc, ctx) == []


def test_rejects_dated_milestone_when_entry_year_unknown(doc, ctx):
    ver = version27(doc)
    ver["entry_year"] = None
    ver["entry_year_label"] = "Unconfirmed: page headed Fall 2027"
    assert codes(v.validate_doc(doc, ctx)) == {"E_ENTRY_YEAR_UNKNOWN"}


def test_milestone_needs_exactly_one_of_date_or_recurring(doc, ctx):
    doc["versions"][1]["application"]["milestones"][0]["recurring"] = {"month": 12, "day": 1}
    assert codes(v.validate_doc(doc, ctx)) == {"E_SCHEMA"}


def test_rejects_confident_value_next_to_conflict(doc, ctx):
    version27(doc)["renewal_rules"]["gpa_min"] = 3.0
    assert codes(v.validate_doc(doc, ctx)) == {"E_CONFLICT_VALUE"}


def test_conflict_needs_two_entries(doc, ctx):
    ver = version27(doc)
    ver["field_evidence"] = [
        e for e in ver["field_evidence"] if not (e["value_status"] == "conflicting" and e["reported_value"] == 3.2)
    ]
    assert codes(v.validate_doc(doc, ctx)) == {"E_CONFLICT_SHAPE"}


def test_rejects_verified_without_reviewer(doc, ctx):
    version27(doc)["reviewed_by"] = None
    assert codes(v.validate_doc(doc, ctx)) == {"E_VERIFIED_INCOMPLETE"}


def test_verified_with_unconfirmed_label_is_ok(doc, ctx):
    ver = version27(doc)
    ver["entry_year"] = None
    ver["entry_year_label"] = "Unconfirmed: heading says Fall 2026, deadlines say 2027"
    ver["application"]["milestones"][0]["date"] = None
    ver["application"]["milestones"][0]["recurring"] = {"month": 12, "day": 1}
    assert v.validate_doc(doc, ctx) == []


def test_rejects_evidence_pointing_nowhere(doc, ctx):
    extra = dict(version27(doc)["field_evidence"][0], field_path="offers/0/selction_mode")
    version27(doc)["field_evidence"].append(extra)
    assert codes(v.validate_doc(doc, ctx)) == {"E_EVIDENCE_PATH"}


def test_rejects_evidence_with_unknown_source(doc, ctx):
    version27(doc)["field_evidence"][0]["source_ref"] = "s-missing"
    assert codes(v.validate_doc(doc, ctx)) == {"E_EVIDENCE_SOURCE"}


def test_rejects_long_excerpt(doc, ctx):
    version27(doc)["field_evidence"][2]["short_excerpt"] = " ".join(["word"] * 26)
    assert codes(v.validate_doc(doc, ctx)) == {"E_EXCERPT_LENGTH"}


def test_rejects_bad_parent_offer_and_supersedes(doc, ctx):
    version27(doc)["offers"][1]["parent_offer_id"] = "o-ghost"
    assert codes(v.validate_doc(doc, ctx)) == {"E_OFFER_PARENT"}
    version27(doc)["offers"][1]["parent_offer_id"] = "o-main"
    version27(doc)["supersedes"] = "fixture-foundation-program-2099"
    assert codes(v.validate_doc(doc, ctx)) == {"E_SUPERSEDES"}


def test_rejects_duplicate_ids(doc, ctx):
    version27(doc)["offers"][1]["offer_id"] = "o-main"
    assert "E_DUPLICATE_ID" in codes(v.validate_doc(doc, ctx))


def test_rejects_missing_relation_target(doc, ctx):
    doc["related_programs"][0]["program_id"] = "fixture-ghost-program"
    assert codes(v.validate_doc(doc, ctx)) == {"E_RELATION_TARGET"}


def test_relation_target_checked_across_files(tmp_path):
    school = tmp_path / "uva"
    school.mkdir()
    shutil.copy(MAIN, school / MAIN.name)  # parent file deliberately absent
    assert codes(v.validate_tree(tmp_path)) == {"E_RELATION_TARGET"}


def test_rejects_file_in_wrong_directory(tmp_path):
    school = tmp_path / "duke"
    school.mkdir()
    shutil.copy(MAIN, school / MAIN.name)
    # The parent file is not in the tree either, so the relation check also fires.
    assert codes(v.validate_tree(tmp_path)) == {"E_DIR_MISMATCH", "E_RELATION_TARGET"}


def test_no_full_ride_value_anywhere(doc, ctx):
    assert "full ride" not in v.SCHEMA_PATH.read_text().lower()
    assert "full_ride" not in v.SCHEMA_PATH.read_text().lower()
    version27(doc)["offers"][0]["benefits"][0]["normalized_coverage"] = "full_ride"
    assert codes(v.validate_doc(doc, ctx)) == {"E_SCHEMA"}


def test_unknown_is_expressible_without_false(doc, ctx):
    offer = version27(doc)["offers"][0]
    offer["funds_limited"] = None
    offer["selection_mode"] = "unknown"
    drop_evidence(doc, "offers/0/selection_mode")
    assert v.validate_doc(doc, ctx) == []


def test_yaml_dates_stay_strings_and_duplicate_keys_fail():
    assert v.load_yaml_text("d: 2026-11-08\ni: '000123'\n") == {"d": "2026-11-08", "i": "000123"}
    with pytest.raises(Exception):
        v.load_yaml_text("a: 1\na: 2\n")


# ------------------------------------------------------- published versions


def test_compare_published_flags_edit_removal_and_allows_correction(doc):
    base = {"f.yaml": doc}
    assert v.compare_published(base, {"g.yaml": copy.deepcopy(doc)}) == []  # a moved file is fine

    edited = copy.deepcopy(doc)
    version27(edited)["offers"][0]["benefits"][1]["amount"]["value"] = 6000
    assert codes(v.compare_published(base, {"f.yaml": edited})) == {"E_PUBLISHED_EDITED"}

    removed = copy.deepcopy(doc)
    removed["versions"] = removed["versions"][:1]
    assert codes(v.compare_published(base, {"f.yaml": removed})) == {"E_PUBLISHED_EDITED"}
    assert codes(v.compare_published(base, {})) == {"E_PUBLISHED_EDITED"}

    corrected = copy.deepcopy(doc)
    new = copy.deepcopy(version27(corrected))
    new["version_id"] = "fixture-foundation-program-2027-b"
    new["supersedes"] = "fixture-foundation-program-2027"
    new["offers"][0]["benefits"][1]["amount"]["value"] = 6000
    corrected["versions"].append(new)
    assert v.compare_published(base, {"f.yaml": corrected}) == []


def test_compare_ignores_unverified_base_versions(doc):
    draft = copy.deepcopy(doc)
    version27(draft)["verification_status"] = "needs_review"
    changed = copy.deepcopy(draft)
    version27(changed)["source_cohort_text"] = "edited"
    assert v.compare_published({"f.yaml": draft}, {"f.yaml": changed}) == []


def _git(repo: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@example.invalid", "-C", str(repo), *args],
        check=True,
        capture_output=True,
    )


def test_git_base_ref_detects_edited_published_version(tmp_path):
    repo = tmp_path.resolve()
    programs = repo / "data" / "scholarships" / "programs"
    (programs / "uva").mkdir(parents=True)
    shutil.copy(FIXTURES / "uva" / "fixture-parent-program.yaml", programs / "uva")
    target = programs / "uva" / MAIN.name
    shutil.copy(MAIN, target)
    _git(repo, "init", "-q")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "base")

    assert v.main([str(programs), "--base", "HEAD"]) == 0

    target.write_text(target.read_text().replace("value: 5000", "value: 6000"))
    issues = v.validate_tree(programs, base="HEAD")
    assert codes(issues) == {"E_PUBLISHED_EDITED"}

    target.unlink()
    assert "E_PUBLISHED_EDITED" in codes(v.validate_tree(programs, base="HEAD"))


def test_unresolvable_base_ref_fails_instead_of_skipping(tmp_path):
    repo = tmp_path.resolve()
    programs = repo / "programs"
    programs.mkdir()
    _git(repo, "init", "-q")
    assert codes(v.validate_tree(programs, base="origin/main")) == {"E_BASE_REF"}
    assert v.main([str(programs), "--base", "origin/main"]) == 1


# -------------------------------------------------------------- contract guards


def test_fields_md_lists_every_schema_field():
    text = (REPO / "data" / "scholarships" / "schema" / "FIELDS.md").read_text()
    missing = [p for p, _, _ in v.schema_leaf_rows(v.load_schema()) if f"`{p}`" not in text]
    assert not missing, missing


def test_license_and_readme_carry_the_canonical_attribution():
    for name in ("LICENSE", "README.md"):
        assert ATTRIBUTION in (REPO / "data" / "scholarships" / name).read_text(), name


def test_foundation_domains_are_keyed_by_real_schools(ctx):
    for school_id in ctx.foundations:
        assert len(ctx.claims_by_school.get(school_id, [])) == 1, school_id
    assert "jeffersonscholars.org" in ctx.foundations["uva"]
    assert "moreheadcain.org" in ctx.foundations["unc"]
    assert "robertsonscholars.org" in ctx.foundations["unc"] and "robertsonscholars.org" in ctx.foundations["duke"]
