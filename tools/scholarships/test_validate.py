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
import model  # noqa: E402
import validate as v  # noqa: E402

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "valid"
MAIN = FIXTURES / "uva" / "fixture-foundation-program.yaml"
REPO = v.REPO_ROOT
ATTRIBUTION = model.ATTRIBUTION  # one canonical string, test_load.py checks every surface


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


def ms(d: dict, kind: str) -> dict:
    return next(m for m in version27(d)["application"]["milestones"] if m["kind"] == kind)


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
    ms(doc, "notification")["recurring"] = {"month": 1, "day": 2}
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
    version27(doc)["renewal_rules"][0]["gpa_min"] = 3.0
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


def test_dated_milestone_allowed_when_entry_year_unconfirmed_by_evidence(doc, ctx):
    ver = version27(doc)
    ver["entry_year"] = None
    ver["entry_year_label"] = "Unconfirmed: heading says Fall 2026, deadlines say 2027"
    assert codes(v.validate_doc(doc, ctx)) == {"E_ENTRY_YEAR_UNKNOWN"}  # no evidence yet
    for year, src in ((2026, "s-school"), (2027, "s-foundation")):
        ver["field_evidence"].append(
            {"field_path": "entry_year", "source_ref": src, "locator": "heading", "value_status": "conflicting", "reported_value": year}
        )
    assert v.validate_doc(doc, ctx) == []  # window check skipped, dates kept as published
    assert ms(doc, "application_deadline")["date"] == "2026-12-01"


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


# ------------------------------------------- rejecting fixtures as files

REJECTING = Path(__file__).resolve().parent / "fixtures" / "rejecting"
REJECT_CASES = {
    "automatic-guaranteed-without-evidence": {"E_GUARANTEED_NO_EVIDENCE"},
    "summed-total": {"E_SUMMED_TOTAL"},
    "off-domain-source": {"E_OFF_DOMAIN"},
    "mismatched-school-and-ipeds": {"E_IDENTITY"},
    "missing-evidence": {"E_NO_EVIDENCE"},
    "milestone-outside-cycle": {"E_MILESTONE_WINDOW"},
}


@pytest.mark.parametrize("case", sorted(REJECT_CASES))
def test_rejecting_fixture_files(case, ctx):
    path = REJECTING / case / "uva" / MAIN.name
    record = v.load_yaml_text(path.read_text(encoding="utf-8"))
    assert codes(v.validate_doc(record, ctx, str(path), "uva", path.stem)) == REJECT_CASES[case]


def test_rejecting_fixture_edited_published_version():
    base = v.load_yaml_text((REJECTING / "edited-published-version" / "base.yaml").read_text())
    head = v.load_yaml_text((REJECTING / "edited-published-version" / "head.yaml").read_text())
    assert codes(v.compare_published({"f.yaml": base}, {"f.yaml": head})) == {"E_PUBLISHED_EDITED"}


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


def test_compare_published_is_type_strict(doc):
    edited = copy.deepcopy(doc)
    for e in version27(edited)["field_evidence"]:
        if e["field_path"] == "offers/0/benefits/1/amount":
            e["reported_value"] = 5000.0  # 5000 == 5000.0 in Python, not in YAML
    assert codes(v.compare_published({"f.yaml": doc}, {"f.yaml": edited})) == {"E_PUBLISHED_EDITED"}
    base, head = copy.deepcopy(doc), copy.deepcopy(doc)
    version27(base)["field_evidence"][0]["reported_value"] = True
    version27(head)["field_evidence"][0]["reported_value"] = 1
    assert codes(v.compare_published({"f.yaml": base}, {"f.yaml": head})) == {"E_PUBLISHED_EDITED"}


def test_compare_ignores_unverified_base_versions(doc):
    draft = copy.deepcopy(doc)
    version27(draft)["verification_status"] = "unverified"
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


# ===================================================== review round (15 findings)


def other_evidence(d: dict, path: str, **kw) -> dict:
    e = {"field_path": path, "source_ref": "s-foundation", "locator": "x", "value_status": "reported"}
    e.update(kw)
    version27(d)["field_evidence"].append(e)
    return e


# 1. conflicting dated facts -------------------------------------------------


def test_f1_conflicting_deadline_can_be_stored_null(doc, ctx):
    m = ms(doc, "application_deadline")
    m["date"] = None
    drop_evidence(doc, "application/milestones/1")
    for dated in ("2026-12-01", "2027-01-15"):
        other_evidence(doc, "application/milestones/1/date", value_status="conflicting", reported_value=dated)
    assert v.validate_doc(doc, ctx) == []


def test_f1_undated_milestone_without_conflict_is_rejected(doc, ctx):
    ms(doc, "application_deadline")["date"] = None
    drop_evidence(doc, "application/milestones/1")
    assert codes(v.validate_doc(doc, ctx)) == {"E_MILESTONE_UNDATED"}


def test_f1_milestone_cannot_be_dated_and_recurring(doc, ctx):
    ms(doc, "application_deadline")["recurring"] = {"month": 12, "day": 1}
    assert codes(v.validate_doc(doc, ctx)) == {"E_SCHEMA"}


# 2. renewal is a list with scope -------------------------------------------


def test_f2_renewal_rules_per_benefit(doc, ctx):
    ver = version27(doc)
    ver["renewal_rules"] = [
        {"applies_to": [{"offer_id": "o-main", "benefit_id": "b-tuition"}], "gpa_min": 2.0},
        {"applies_to": [{"offer_id": "o-main", "benefit_id": "b-stipend"}], "gpa_min": 3.25},
        {"applies_to": [], "max_semesters": 8},
    ]
    ver["field_evidence"] = [e for e in ver["field_evidence"] if not e["field_path"].startswith("renewal_rules")]
    assert v.validate_doc(doc, ctx) == []


def test_f2_renewal_scope_must_exist(doc, ctx):
    version27(doc)["renewal_rules"][0]["applies_to"] = [{"offer_id": "o-main", "benefit_id": "b-ghost"}]
    assert codes(v.validate_doc(doc, ctx)) == {"E_APPLIES_TO"}
    version27(doc)["renewal_rules"][0]["applies_to"] = [{"offer_id": None, "benefit_id": None}]
    assert codes(v.validate_doc(doc, ctx)) == {"E_APPLIES_TO"}


def test_f2_single_object_renewal_rules_is_rejected(doc, ctx):
    version27(doc)["renewal_rules"] = {"gpa_min": 3.0}
    assert codes(v.validate_doc(doc, ctx)) == {"E_SCHEMA"}


# 3. joint programs ----------------------------------------------------------


def _joint(d: dict) -> None:
    d["participating_schools"] = [
        {"school_id": "uva", "ipeds_id": "234076"},
        {"school_id": "duke", "ipeds_id": "198419"},
    ]


def test_f3_joint_program_accepts_each_participants_domain(doc, ctx):
    version27(doc)["sources"][0]["url"] = "https://ousf.duke.edu/merit-scholarships/fixture"
    assert codes(v.validate_doc(doc, ctx)) == {"E_OFF_DOMAIN"}  # not joint yet
    _joint(doc)
    assert v.validate_doc(doc, ctx) == []


def test_f3_joint_program_unions_foundation_domains(doc, ctx):
    _joint(doc)
    version27(doc)["sources"][1]["url"] = "https://robertsonscholars.org/fixture"  # Duke's and UNC's foundation
    assert v.validate_doc(doc, ctx) == []


def test_f3_participants_are_validated_against_identity(doc, ctx):
    _joint(doc)
    doc["participating_schools"][1]["ipeds_id"] = "199120"
    assert codes(v.validate_doc(doc, ctx)) == {"E_IDENTITY"}
    _joint(doc)
    doc["participating_schools"][0] = {"school_id": "duke", "ipeds_id": "198419"}
    assert codes(v.validate_doc(doc, ctx)) == {"E_IDENTITY"}  # first must be the record's own school


# 4. program-level evidence and per-entry status ----------------------------


def test_f4_status_for_entry_needs_evidence_unless_active(doc, ctx):
    version27(doc)["program_status_for_entry"] = "closed_to_new_entrants"
    assert codes(v.validate_doc(doc, ctx)) == {"E_NO_EVIDENCE"}
    other_evidence(doc, "program_status_for_entry", short_excerpt="no longer accepting new applicants")
    assert v.validate_doc(doc, ctx) == []


def test_f4_evidence_can_address_program_fields(doc, ctx):
    other_evidence(doc, "/related_programs/0")
    assert v.validate_doc(doc, ctx) == []  # /awarding_authority is already in the fixture
    other_evidence(doc, "/awarding_authorty")
    assert codes(v.validate_doc(doc, ctx)) == {"E_EVIDENCE_PATH"}


def test_f4_status_for_entry_is_optional(doc, ctx):
    del version27(doc)["program_status_for_entry"]
    assert v.validate_doc(doc, ctx) == []


# 5. coverage label is derived, nonresident differential ---------------------


def test_f5_normalized_coverage_is_gone_from_yaml(doc, ctx):
    version27(doc)["offers"][0]["benefits"][0]["normalized_coverage"] = "full_tuition"
    assert codes(v.validate_doc(doc, ctx)) == {"E_SCHEMA"}
    assert "normalized_coverage" not in v.SCHEMA_PATH.read_text()


def test_f5_nonresident_differential_category_exists(doc, ctx):
    b = version27(doc)["offers"][1]["benefits"][0]
    assert b["category"] == "nonresident_differential" and b["instrument"] == "tuition_waiver"
    assert v.validate_doc(doc, ctx) == []


# 6. guaranteed needs a real promise on the exact path -----------------------


def test_f6_guaranteed_rejects_parent_path_evidence(doc, ctx):
    drop_evidence(doc, "offers/1/selection_mode")
    other_evidence(doc, "offers", short_excerpt="Benefits table", reported_value="automatic_guaranteed")
    assert codes(v.validate_doc(doc, ctx)) == {"E_GUARANTEED_NO_EVIDENCE"}


def test_f6_guaranteed_rejects_evidence_reporting_another_value(doc, ctx):
    for e in version27(doc)["field_evidence"]:
        if e["field_path"] == "offers/1/selection_mode":
            e["reported_value"] = "competitive"
    assert codes(v.validate_doc(doc, ctx)) == {"E_GUARANTEED_NO_EVIDENCE"}


# 7. evidence must support the value ----------------------------------------


def test_f7_total_rejects_evidence_on_a_distant_ancestor(doc, ctx):
    drop_evidence(doc, "offers/0/benefits/2/amount")
    other_evidence(doc, "offers/0", short_excerpt="quoted", source_ref="s-school")
    assert codes(v.validate_doc(doc, ctx)) == {"E_SUMMED_TOTAL"}


def test_f7_total_needs_an_excerpt(doc, ctx):
    for e in version27(doc)["field_evidence"]:
        if e["field_path"] == "offers/0/benefits/2/amount":
            e["short_excerpt"] = None
    assert codes(v.validate_doc(doc, ctx)) == {"E_SUMMED_TOTAL"}


def test_f7_not_published_evidence_cannot_back_a_stated_amount(doc, ctx):
    for e in version27(doc)["field_evidence"]:
        if e["field_path"] == "offers/0/benefits/1/amount":
            e["value_status"] = "not_published"
    assert codes(v.validate_doc(doc, ctx)) == {"E_NO_EVIDENCE"}


def test_f7_grandparent_evidence_does_not_count(doc, ctx):
    drop_evidence(doc, "offers/0/benefits/1/amount")
    other_evidence(doc, "offers/0/benefits")
    assert codes(v.validate_doc(doc, ctx)) == {"E_NO_EVIDENCE"}


# 8. no monitor fields; schema_version; additive evolution -------------------


@pytest.mark.parametrize("key,value", [("last_checked_at", "2026-11-08"), ("next_reverify_at", "2027-08-15")])
def test_f8_monitor_fields_are_gone(doc, ctx, key, value):
    version27(doc)[key] = value
    assert codes(v.validate_doc(doc, ctx)) == {"E_SCHEMA"}


def test_f8_needs_review_is_not_a_yaml_status(doc, ctx):
    version27(doc)["verification_status"] = "needs_review"
    assert codes(v.validate_doc(doc, ctx)) == {"E_SCHEMA"}


def test_f8_schema_version_is_required_and_pinned(doc, ctx):
    del doc["schema_version"]
    assert codes(v.validate_doc(doc, ctx)) == {"E_SCHEMA"}
    doc["schema_version"] = 2
    assert codes(v.validate_doc(doc, ctx)) == {"E_SCHEMA"}


def test_f8_absent_at_base_and_null_at_head_is_not_an_edit(doc):
    base = copy.deepcopy(doc)
    del version27(base)["owner_spot_checked"]
    del version27(base)["offers"][0]["funds_limited"]
    head = copy.deepcopy(base)
    version27(head)["owner_spot_checked"] = None
    version27(head)["offers"][0]["funds_limited"] = None
    assert v.compare_published({"f.yaml": base}, {"f.yaml": head}) == []


def test_f8_other_differences_are_still_edits(doc):
    base = copy.deepcopy(doc)
    del version27(base)["owner_spot_checked"]
    added = copy.deepcopy(base)
    version27(added)["owner_spot_checked"] = True  # absent -> non-null
    assert codes(v.compare_published({"f.yaml": base}, {"f.yaml": added})) == {"E_PUBLISHED_EDITED"}
    nulled = copy.deepcopy(doc)  # present at base, absent at head
    base2 = copy.deepcopy(doc)
    del version27(nulled)["offers"][0]["funds_limited"]
    assert codes(v.compare_published({"f.yaml": base2}, {"f.yaml": nulled})) == {"E_PUBLISHED_EDITED"}


# 9. supersedes -------------------------------------------------------------


def _correction(d: dict) -> dict:
    new = copy.deepcopy(version27(d))
    new["version_id"] = "fixture-foundation-program-2027-b"
    new["supersedes"] = "fixture-foundation-program-2027"
    d["versions"].append(new)
    return new


def test_f9_correction_in_same_year_is_valid(doc, ctx):
    _correction(doc)
    assert v.validate_doc(doc, ctx) == []


def test_f9_supersedes_cannot_cross_entry_years(doc, ctx):
    version27(doc)["supersedes"] = "fixture-foundation-program-2026"
    assert codes(v.validate_doc(doc, ctx)) == {"E_SUPERSEDES"}


def test_f9_two_unsuperseded_versions_in_one_year(doc, ctx):
    new = _correction(doc)
    new["supersedes"] = None
    assert codes(v.validate_doc(doc, ctx)) == {"E_SUPERSEDES"}


def test_f9_supersedes_cycle(doc, ctx):
    new = _correction(doc)
    version27(doc)["supersedes"] = new["version_id"]
    assert codes(v.validate_doc(doc, ctx)) == {"E_SUPERSEDES"}


# 11. null means not documented ----------------------------------------------


def test_f11_null_lists_are_valid_and_empty_stacking_needs_evidence(doc, ctx):
    ver = version27(doc)
    ver["stacking_rules"] = None
    ver["offers"][0]["benefits"][0]["exclusions"] = None
    ver["offers"][0]["eligibility"]["test_rules"] = None
    assert v.validate_doc(doc, ctx) == []
    ver["stacking_rules"] = []
    assert codes(v.validate_doc(doc, ctx)) == {"E_NO_EVIDENCE"}
    other_evidence(doc, "stacking_rules", short_excerpt="may be combined with any other aid")
    assert v.validate_doc(doc, ctx) == []


# 12. application additions -------------------------------------------------


def test_f12_admission_deadline_and_lead_time_are_representable(doc, ctx):
    app = version27(doc)["application"]
    assert ms(doc, "admission_deadline")["date"] == "2026-11-01"
    assert app["prerequisites"][0]["minimum_lead_days"] == 5
    assert app["admission_plan_requirement"] and "notes" in app
    app["prerequisites"][0]["kind"] = "carrier_pigeon"
    assert codes(v.validate_doc(doc, ctx)) == {"E_SCHEMA"}


# 13. amount shape ----------------------------------------------------------


@pytest.mark.parametrize(
    "amount",
    [
        {"qualifier": "exact", "value": None, "min": None, "max": None, "period": "academic_year"},
        {"qualifier": "range", "value": None, "min": None, "max": None, "period": "academic_year"},
        {"qualifier": "range", "value": None, "min": 1000, "max": None, "period": "academic_year"},
        {"qualifier": "up_to", "value": 100, "min": 1, "max": 2, "period": None},
        {"qualifier": "not_published", "value": 100, "min": None, "max": None, "period": None},
    ],
)
def test_f13_malformed_amounts_are_rejected(doc, ctx, amount):
    version27(doc)["offers"][0]["benefits"][1]["amount"] = amount
    assert codes(v.validate_doc(doc, ctx)) == {"E_SCHEMA"}


def test_f13_range_amount_rules(doc, ctx):
    b = version27(doc)["offers"][0]["benefits"][1]
    b["amount"] = {"qualifier": "range", "value": None, "min": 1000, "max": 5000, "period": "academic_year"}
    assert v.validate_doc(doc, ctx) == []
    b["amount"]["min"] = 5000
    assert codes(v.validate_doc(doc, ctx)) == {"E_AMOUNT_RANGE"}


# 14. contradictions, vocab, counts, statuses --------------------------------


def test_f14_merit_only_with_required_need_is_a_contradiction(doc, ctx):
    o = version27(doc)["offers"][0]
    o["aid_basis"], o["need_role"] = "merit_only", "required"
    assert codes(v.validate_doc(doc, ctx)) == {"E_CONTRADICTION"}


def test_f14_admission_route_with_required_separate_application(doc, ctx):
    version27(doc)["offers"][0]["consideration_route"] = "admission_application"
    assert codes(v.validate_doc(doc, ctx)) == {"E_CONTRADICTION"}
    version27(doc)["offers"][0]["consideration_route"] = "separate_application"
    version27(doc)["application"]["separate_application"] = "not_required"
    assert codes(v.validate_doc(doc, ctx)) == {"E_CONTRADICTION"}


def test_f14_one_residency_vocabulary(doc, ctx):
    version27(doc)["offers"][0]["residency"] = "nonresident"
    assert codes(v.validate_doc(doc, ctx)) == {"E_SCHEMA"}
    version27(doc)["offers"][0]["residency"] = "in_state"
    version27(doc)["offers"][0]["eligibility"]["residency_eligible"] = ["in_state"]
    assert codes(v.validate_doc(doc, ctx)) == {"E_SCHEMA"}


def test_f14_award_counts_claim_and_denominator(doc, ctx):
    counts = version27(doc)["award_counts"]
    assert {c["claim"] for c in counts} == {"target", "actual"}
    counts[1]["denominator"] = None
    assert codes(v.validate_doc(doc, ctx)) == {"E_SCHEMA"}
    counts[1]["denominator"] = "entering class"
    counts[0]["metric"] = "target"
    assert codes(v.validate_doc(doc, ctx)) == {"E_SCHEMA"}


def test_f14_recognition_statuses_and_required_status(doc, ctx):
    e = version27(doc)["offers"][1]["eligibility"]
    e["national_merit_statuses"] = ["semifinalist", "finalist", "commended", "nrp_hispanic"]
    e["status_required_for_award"] = "finalist"
    assert v.validate_doc(doc, ctx) == []
    e["status_required_for_award"] = "winner"
    assert codes(v.validate_doc(doc, ctx)) == {"E_SCHEMA"}


# 15. boundaries and CI git shapes -------------------------------------------


@pytest.mark.parametrize(
    "date,ok",
    [("2026-06-30", False), ("2026-07-01", True), ("2027-08-31", True), ("2027-09-01", False)],
)
def test_f15_cycle_window_boundaries(doc, ctx, date, ok):
    ms(doc, "application_deadline")["date"] = date
    expected = set() if ok else {"E_MILESTONE_WINDOW"}
    assert codes(v.validate_doc(doc, ctx)) == expected


def test_f15_non_vacuous_tree_run():
    assert v.main([str(FIXTURES)]) == 0
    assert v.main([str(REJECTING / "off-domain-source")]) == 1


def _repo_with_program(tmp_path: Path):
    repo = tmp_path.resolve()
    programs = repo / "data" / "scholarships" / "programs"
    (programs / "uva").mkdir(parents=True)
    shutil.copy(FIXTURES / "uva" / "fixture-parent-program.yaml", programs / "uva")
    shutil.copy(MAIN, programs / "uva")
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "base")
    return repo, programs


def _sha(repo: Path) -> str:
    return subprocess.run(["git", "-C", str(repo), "rev-parse", "HEAD"], capture_output=True, text=True, check=True).stdout.strip()


def test_f15_branch_behind_main_uses_the_merge_base(tmp_path):
    repo, programs = _repo_with_program(tmp_path)
    _git(repo, "checkout", "-q", "-b", "feature")
    _git(repo, "checkout", "-q", "main")
    other = programs / "uva" / "fixture-other-program.yaml"  # a verified program that landed on main later
    text = (programs / "uva" / MAIN.name).read_text().replace("fixture-foundation-program", "fixture-other-program")
    text = text.replace("related_programs:\n- program_id: fixture-parent-program\n  relation: component_of\n", "")
    other.write_text(text)
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "main moves on")
    _git(repo, "update-ref", "refs/remotes/origin/main", "main")
    _git(repo, "checkout", "-q", "feature")
    assert not other.exists()  # the feature branch has never seen that file
    assert "E_PUBLISHED_EDITED" in codes(v.validate_tree(programs, base="origin/main"))  # the false failure
    assert v.main([str(programs), "--merge-base", "origin/main"]) == 0
    assert v.main([str(programs), "--merge-base", "origin/nope"]) == 1


def test_f15_base_equal_to_head_is_clean_and_edits_are_caught_by_before_sha(tmp_path):
    repo, programs = _repo_with_program(tmp_path)
    before = _sha(repo)
    assert v.main([str(programs), "--base", before]) == 0
    target = programs / "uva" / MAIN.name
    target.write_text(target.read_text().replace("value: 5000", "value: 6000"))
    _git(repo, "commit", "-aq", "-m", "edit published version")
    assert v.main([str(programs), "--base", _sha(repo)]) == 0  # base == HEAD: nothing to compare
    assert v.main([str(programs), "--base", before]) == 1  # push-to-main shape: before sha catches it


@pytest.mark.parametrize("status", ["conflicting", "historical_only"])
def test_f10_every_non_draft_status_is_protected(doc, status):
    base = copy.deepcopy(doc)
    version27(base)["verification_status"] = status
    edited = copy.deepcopy(base)
    version27(edited)["source_cohort_text"] = "edited"
    assert codes(v.compare_published({"f.yaml": base}, {"f.yaml": edited})) == {"E_PUBLISHED_EDITED"}


# ===================================================== real-record amendments


def test_a1_cost_of_attendance_category(doc, ctx):
    b = version27(doc)["offers"][0]["benefits"][3]
    assert b["category"] == "cost_of_attendance"
    assert v.validate_doc(doc, ctx) == []
    b["category"] = "full_ride"
    assert codes(v.validate_doc(doc, ctx)) == {"E_SCHEMA"}


def test_a2_advertised_total_is_valid_with_null_period_and_evidence(doc, ctx):
    t = version27(doc)["offers"][0]["advertised_totals"][0]
    assert t["amount"]["period"] is None
    assert v.validate_doc(doc, ctx) == []


def test_a2_advertised_total_needs_exact_path_evidence_with_excerpt(doc, ctx):
    drop_evidence(doc, "offers/0/advertised_totals/0/amount")
    assert codes(v.validate_doc(doc, ctx)) == {"E_SUMMED_TOTAL"}
    other_evidence(doc, "offers/0/advertised_totals", short_excerpt="quoted")  # parent path is not enough
    assert codes(v.validate_doc(doc, ctx)) == {"E_SUMMED_TOTAL"}
    version27(doc)["field_evidence"].pop()
    other_evidence(doc, "offers/0/advertised_totals/0/amount", short_excerpt=None)
    assert codes(v.validate_doc(doc, ctx)) == {"E_SUMMED_TOTAL"}


def test_a2_advertised_total_shape(doc, ctx):
    t = version27(doc)["offers"][0]["advertised_totals"][0]
    t["scope_text"] = ""
    assert codes(v.validate_doc(doc, ctx)) == {"E_SCHEMA"}
    t["scope_text"] = "x"
    t["amount"] = {"qualifier": "range", "value": None, "min": 5, "max": 1, "period": None}
    assert codes(v.validate_doc(doc, ctx)) == {"E_AMOUNT_RANGE"}


def test_a3_credit_load_per_year(doc, ctx):
    assert version27(doc)["renewal_rules"][0]["credit_load_min_per_year"] == 24
    assert v.validate_doc(doc, ctx) == []


def test_a4_maximum_lead_days(doc, ctx):
    p = version27(doc)["application"]["prerequisites"][0]
    assert p["maximum_lead_days"] == 5
    p["maximum_lead_days"] = "five"
    assert codes(v.validate_doc(doc, ctx)) == {"E_SCHEMA"}


def test_a5_interview_mode_mixed(doc, ctx):
    assert version27(doc)["application"]["interview_mode"] == "mixed"
    assert v.validate_doc(doc, ctx) == []


def test_a6_scholar_is_a_status_required_for_award_only(doc, ctx):
    e = version27(doc)["offers"][1]["eligibility"]
    assert e["status_required_for_award"] == "scholar"
    e["national_merit_statuses"] = ["scholar"]  # not a status a student holds when applying
    assert codes(v.validate_doc(doc, ctx)) == {"E_SCHEMA"}


def test_a7_state_program_authority(doc, ctx):
    assert doc["awarding_authority"] == "state_program"
    assert v.validate_doc(doc, ctx) == []


def test_a8_citizenship_text_length(doc, ctx):
    e = version27(doc)["offers"][1]["eligibility"]
    e["citizenship_text"] = " ".join(["word"] * 40)
    assert v.validate_doc(doc, ctx) == []
    e["citizenship_text"] = " ".join(["word"] * 41)
    assert codes(v.validate_doc(doc, ctx)) == {"E_TEXT_LENGTH"}


def test_a9_no_form_other_steps_required(doc, ctx):
    app = version27(doc)["application"]
    app["separate_application"] = "no_form_other_steps_required"
    assert v.validate_doc(doc, ctx) == []  # evidence on separate_application still counts
    version27(doc)["offers"][0]["consideration_route"] = "separate_application"
    assert codes(v.validate_doc(doc, ctx)) == {"E_CONTRADICTION"}
    drop_evidence(doc, "application/separate_application")
    assert "E_NO_EVIDENCE" in codes(v.validate_doc(doc, ctx))


def test_a10_conditions_text_needs_evidence(doc, ctx):
    b = version27(doc)["offers"][1]["benefits"][0]
    assert b["conditions_text"]
    assert v.validate_doc(doc, ctx) == []
    drop_evidence(doc, "offers/1/benefits/0/conditions_text")
    assert codes(v.validate_doc(doc, ctx)) == {"E_NO_EVIDENCE"}
    b["conditions_text"] = None
    assert v.validate_doc(doc, ctx) == []


def test_amendments_are_additive_for_published_versions(doc):
    """A version published before these fields existed still compares equal."""
    base = copy.deepcopy(doc)
    head = copy.deepcopy(doc)
    for ver in (base,):
        o = version27(ver)["offers"][0]
        o.pop("advertised_totals")
        o["benefits"][0].pop("conditions_text", None)
    version27(head)["offers"][0]["advertised_totals"] = None
    version27(head)["offers"][0]["benefits"][0]["conditions_text"] = None
    version27(head)["offers"][0]["benefits"].pop(3)
    version27(base)["offers"][0]["benefits"].pop(3)
    assert v.compare_published({"f.yaml": base}, {"f.yaml": head}) == []
