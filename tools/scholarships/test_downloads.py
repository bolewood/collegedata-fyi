"""Tests for tools/scholarships/build_downloads.py and attribution drift (PRD 036 M2). No network."""

from __future__ import annotations

import csv
import io
import json
import sys
import zipfile
from pathlib import Path
from typing import Any, Dict

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_downloads as bd  # noqa: E402
import model  # noqa: E402
import validate as v  # noqa: E402

REPO = v.REPO_ROOT
FIXTURES = Path(__file__).resolve().parent / "fixtures" / "valid"
ATTR = model.ATTRIBUTION
_MATCHES = sorted((REPO / "supabase" / "migrations").glob("*_scholarship_directory.sql"))
assert len(_MATCHES) == 1, _MATCHES
MIGRATION = _MATCHES[0]


def fixture_docs() -> Dict[str, Dict[str, Any]]:
    return {
        str(p): v.load_yaml_text(p.read_text(encoding="utf-8"))
        for p in sorted(FIXTURES.glob("*/*.yaml"))
    }


@pytest.fixture()
def ds() -> model.Dataset:
    return model.build_dataset(fixture_docs(), root=REPO)


def joint_dataset() -> model.Dataset:
    docs = fixture_docs()
    doc = next(d for d in docs.values() if d["program_id"] == "fixture-foundation-program")
    doc["participating_schools"] = [
        {"school_id": "uva", "ipeds_id": "234076"},
        {"school_id": "unc", "ipeds_id": "199120"},
    ]
    return model.build_dataset(docs)


def read_zip(path: Path) -> Dict[str, str]:
    with zipfile.ZipFile(path) as zf:
        return {i.filename: zf.read(i).decode("utf-8") for i in zf.infolist()}


def build(ds: model.Dataset, tmp_path: Path, **kw: Any):
    json_path, zip_path = bd.build(ds, tmp_path, **kw)
    return json_path, zip_path


# ---------------------------------------------------------------------------- JSON


def test_json_has_meta_block_before_records(ds, tmp_path):
    json_path, _ = build(ds, tmp_path)
    assert json_path.name == f"scholarships-v{model.DATASET_VERSION}.json"
    text = json_path.read_text(encoding="utf-8")
    doc = json.loads(text)
    assert list(doc) == ["meta", "programs"]
    meta = doc["meta"]
    assert meta["license"] == "CC-BY-SA-4.0"
    assert meta["license_url"] == "https://creativecommons.org/licenses/by-sa/4.0/"
    assert meta["attribution"] == ATTR
    assert meta["version"] == model.DATASET_VERSION
    assert meta["generated_at"] == "2026-11-08"  # newest last_reviewed_at, not the wall clock
    assert meta["source_repository"].startswith("https://github.com/")
    assert meta["record_count"] == 1
    assert meta["dataset_id"].startswith(f"collegedata-scholarships-v{model.DATASET_VERSION}-")


def test_json_records_are_the_published_selection_without_time_dependent_fields(ds, tmp_path):
    json_path, _ = build(ds, tmp_path)
    programs = json.loads(json_path.read_text(encoding="utf-8"))["programs"]
    assert [p["version_id"] for p in programs] == ["fixture-foundation-program-2027"]
    rec = programs[0]
    assert "freshness_status" not in rec and "current_entry_year" not in rec
    assert rec["verification_status"] == "verified"
    assert [o["normalized_coverage"] for o in rec["offers"]] == ["full_school_coa", "full_school_coa"]
    assert rec["participating_school_ids"] == ["uva"]
    assert rec["cycle_basis"] == "entry_year" and rec["cycle_through_date"] == "2026-12-01"
    assert rec["statuses_required"] == ["scholar"]
    assert "field_evidence" not in rec and "content_sha256" not in json.dumps(rec)


def test_output_is_deterministic(ds, tmp_path):
    a, b = tmp_path / "a", tmp_path / "b"
    pa = build(ds, a)
    pb = build(ds, b)
    for x, y in zip(pa, pb):
        assert x.read_bytes() == y.read_bytes()


def test_dataset_id_changes_when_a_record_changes(ds, tmp_path):
    first = json.loads(build(ds, tmp_path / "a")[0].read_text(encoding="utf-8"))["meta"]["dataset_id"]
    docs = fixture_docs()
    doc = next(d for d in docs.values() if d["program_id"] == "fixture-foundation-program")
    doc["official_name"] = "Fixture Foundation Scholars II"
    other = model.build_dataset(docs)
    second = json.loads(build(other, tmp_path / "b")[0].read_text(encoding="utf-8"))["meta"]["dataset_id"]
    assert first != second


def test_explicit_version_and_generated_at(ds, tmp_path):
    json_path, zip_path = build(ds, tmp_path, version=7, generated_at="2027-01-02")
    assert json_path.name == "scholarships-v7.json" and zip_path.name == "scholarships-v7.csv.zip"
    meta = json.loads(json_path.read_text(encoding="utf-8"))["meta"]
    assert (meta["version"], meta["generated_at"]) == (7, "2027-01-02")
    assert meta["dataset_id"].startswith("collegedata-scholarships-v7-")
    assert "scholarships-v7.csv" in read_zip(zip_path)


def test_empty_dataset_builds_meta_and_headers_only(tmp_path):
    json_path, zip_path = build(model.Dataset(), tmp_path, generated_at="2026-11-14")
    doc = json.loads(json_path.read_text(encoding="utf-8"))
    assert doc["programs"] == [] and doc["meta"]["record_count"] == 0
    files = read_zip(zip_path)
    csv_lines = files[f"scholarships-v{model.DATASET_VERSION}.csv"].splitlines()
    assert csv_lines[0] == f"# {ATTR}" and len(csv_lines) == 2  # comment + header


# ----------------------------------------------------------------------------- CSV


def test_zip_holds_csv_license_and_attribution(ds, tmp_path):
    _, zip_path = build(ds, tmp_path)
    files = read_zip(zip_path)
    assert sorted(files) == sorted(
        [f"scholarships-v{model.DATASET_VERSION}.csv", "ATTRIBUTION.txt", "LICENSE.txt"]
    )
    assert files["LICENSE.txt"] == (REPO / "data" / "scholarships" / "LICENSE").read_text(encoding="utf-8")
    assert ATTR in files["ATTRIBUTION.txt"] and "CC-BY-SA-4.0" in files["ATTRIBUTION.txt"]


def test_csv_first_line_is_the_attribution_comment_then_a_normal_csv(ds, tmp_path):
    _, zip_path = build(ds, tmp_path)
    text = read_zip(zip_path)[f"scholarships-v{model.DATASET_VERSION}.csv"]
    lines = text.splitlines()
    assert lines[0] == f"# {ATTR}"
    rows = list(csv.DictReader(io.StringIO("\n".join(lines[1:]) + "\n")))
    assert list(rows[0]) == bd.CSV_COLUMNS
    assert len(rows) == 1
    row = rows[0]
    assert row["program_id"] == "fixture-foundation-program" and row["school_id"] == "uva"
    assert row["coverages"] == "full_school_coa"
    assert row["cycle_basis"] == "entry_year" and row["cycle_through_date"] == "2026-12-01"
    assert row["statuses_required"] == "scholar"
    assert row["deadline_months"] == "12" and row["key_deadline"] == "2026-12-01"
    assert row["license"] == "CC-BY-SA-4.0" and row["attribution"] == ATTR
    assert row["source_urls"].split(";") == [
        "https://www.jeffersonscholars.org/scholarships/fixture-faq",  # ordered by source_id, like the view
        "https://admission.virginia.edu/affordability/fixture-page",
    ]
    offers = json.loads(row["offers_json"])
    assert [o["normalized_coverage"] for o in offers] == ["full_school_coa", "full_school_coa"]
    assert "freshness_status" not in row


def test_joint_program_is_one_json_record_and_one_csv_row_per_school(tmp_path):
    joint = joint_dataset()
    json_path, zip_path = build(joint, tmp_path)
    programs = json.loads(json_path.read_text(encoding="utf-8"))["programs"]
    assert len(programs) == 1 and programs[0]["participating_school_ids"] == ["uva", "unc"]
    text = read_zip(zip_path)[f"scholarships-v{model.DATASET_VERSION}.csv"]
    rows = list(csv.DictReader(io.StringIO("\n".join(text.splitlines()[1:]) + "\n")))
    assert sorted(r["school_id"] for r in rows) == ["unc", "uva"]
    assert {r["program_id"] for r in rows} == {"fixture-foundation-program"}
    assert {r["participating_school_ids"] for r in rows} == {"uva;unc"}


def test_zip_entries_have_fixed_timestamps(ds, tmp_path):
    _, zip_path = build(ds, tmp_path)
    with zipfile.ZipFile(zip_path) as zf:
        assert {i.date_time for i in zf.infolist()} == {bd.ZIP_EPOCH}


def test_main_builds_from_a_tree_and_refuses_an_invalid_one(tmp_path, capsys):
    out = tmp_path / "out"
    assert bd.main([str(FIXTURES), "--out-dir", str(out), "--generated-at", "2026-11-14"]) == 0
    assert (out / f"scholarships-v{model.DATASET_VERSION}.json").exists()
    bad = tmp_path / "bad" / "wrong-dir"
    bad.mkdir(parents=True)
    text = (FIXTURES / "uva" / "fixture-foundation-program.yaml").read_text(encoding="utf-8")
    (bad / "fixture-foundation-program.yaml").write_text(text, encoding="utf-8")
    assert bd.main([str(tmp_path / "bad"), "--out-dir", str(tmp_path / "out2")]) == 1
    assert not (tmp_path / "out2").exists()


# ------------------------------------------------------------------ attribution drift


def test_attribution_is_one_exact_string_everywhere(ds, tmp_path):
    """A test fails if the canonical attribution drifts on any surface."""
    json_path, zip_path = build(ds, tmp_path)
    files = read_zip(zip_path)
    csv_text = files[f"scholarships-v{model.DATASET_VERSION}.csv"]
    surfaces = {
        "data/scholarships/LICENSE": (REPO / "data" / "scholarships" / "LICENSE").read_text(encoding="utf-8"),
        "data/scholarships/README.md": (REPO / "data" / "scholarships" / "README.md").read_text(encoding="utf-8"),
        "migration": MIGRATION.read_text(encoding="utf-8"),
        "docs/prd/036-view-contract.md": (REPO / "docs" / "prd" / "036-view-contract.md").read_text(encoding="utf-8"),
        "docs/prd/036-named-scholarship-directory.md": (REPO / "docs" / "prd" / "036-named-scholarship-directory.md").read_text(encoding="utf-8"),
        "json meta": json.loads(json_path.read_text(encoding="utf-8"))["meta"]["attribution"],
        "csv first line": csv_text.splitlines()[0][2:],
        "zip LICENSE.txt": files["LICENSE.txt"],
        "zip ATTRIBUTION.txt": files["ATTRIBUTION.txt"],
    }
    for name, text in surfaces.items():
        assert ATTR in text, f"attribution string drifted in {name}"
    # The JSON meta and CSV comment are the string itself, not just a container for it.
    assert surfaces["json meta"] == ATTR and surfaces["csv first line"] == ATTR


def test_license_id_is_consistent_between_migration_and_downloads(ds, tmp_path):
    sql = MIGRATION.read_text(encoding="utf-8")
    assert f"'{model.LICENSE_ID}'::text as license" in sql
    meta = json.loads(build(ds, tmp_path)[0].read_text(encoding="utf-8"))["meta"]
    assert meta["license"] == model.LICENSE_ID


def test_drift_would_be_caught():
    drifted = ATTR.replace("CC BY-SA 4.0", "CC BY 4.0")
    assert drifted != ATTR
    assert ATTR not in (REPO / "data" / "scholarships" / "LICENSE").read_text(encoding="utf-8").replace(ATTR, drifted)


# ------------------------------------------------- evidence, determinism, snapshots


def test_json_exposes_evidence_locators_never_excerpts(ds, tmp_path):
    # Review 2 and the decision: locators yes, excerpts no.
    json_path, _ = build(ds, tmp_path)
    text = json_path.read_text(encoding="utf-8")
    rec = json.loads(text)["programs"][0]
    assert rec["evidence"], "locators must be present"
    assert all(set(e) == {"field_path", "source_ref", "locator", "value_status"} for e in rec["evidence"])
    assert "short_excerpt" not in text
    for ver in ds.versions:
        for ev in ver["record"]["field_evidence"]:
            if ev.get("short_excerpt"):
                assert ev["short_excerpt"] not in text


def test_generated_at_is_derived_from_the_records_never_the_clock(ds):
    assert bd.default_generated_at([]) == bd.EMPTY_GENERATED_AT == "1970-01-01"
    assert bd.default_generated_at([{"last_reviewed_at": None, "source_retrieved_at": "2026-10-01"}]) == "2026-10-01"
    assert bd.default_generated_at(
        [{"last_reviewed_at": "2026-11-08", "source_retrieved_at": "2026-12-01"}, {"last_reviewed_at": None, "source_retrieved_at": None}]
    ) == "2026-11-08"


def test_all_historical_dataset_builds_the_same_bytes_every_day(tmp_path, monkeypatch):
    # Review 3: records with no review date used to pick up today's date, so a byte compare failed daily.
    docs = fixture_docs()
    for d in docs.values():
        for ver in d["versions"]:
            ver["last_reviewed_at"] = None
            ver["verification_status"] = "historical_only" if ver["verification_status"] == "verified" else ver["verification_status"]
    dataset = model.build_dataset(docs)
    first = build(dataset, tmp_path / "a")[0].read_bytes()
    import datetime as real

    class Later(real.datetime):
        @classmethod
        def now(cls, tz=None):
            return real.datetime(2031, 1, 1, tzinfo=tz)

    monkeypatch.setattr(real, "datetime", Later)
    assert build(dataset, tmp_path / "b")[0].read_bytes() == first


COMMITTED = REPO / "web" / "public" / "data"


def test_committed_snapshots_are_current():
    """The committed downloads are built from data/scholarships/programs. Adding or
    changing a record without rerunning build_downloads.py fails here."""
    n = model.DATASET_VERSION
    json_path, zip_path = COMMITTED / f"scholarships-v{n}.json", COMMITTED / f"scholarships-v{n}.csv.zip"
    assert json_path.exists() and zip_path.exists(), "run: python tools/scholarships/build_downloads.py, then commit web/public/data"
    import load  # noqa: E402

    built, issues = load.load_dataset(v.DEFAULT_PROGRAMS_DIR)
    assert built is not None, issues
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        new_json, new_zip = bd.build(built, Path(tmp), version=n)
        assert json_path.read_bytes() == new_json.read_bytes(), "scholarships-v%d.json is stale: rerun build_downloads.py" % n
        # Compare the archive by content: deflate output can differ between zlib builds.
        assert read_zip(zip_path) == read_zip(new_zip), "scholarships-v%d.csv.zip is stale: rerun build_downloads.py" % n


def test_stale_snapshot_would_be_detected(ds, tmp_path):
    # The compare is not vacuous: a dataset with a record builds different bytes than the empty snapshot.
    committed = (COMMITTED / f"scholarships-v{model.DATASET_VERSION}.json").read_bytes()
    assert build(ds, tmp_path)[0].read_bytes() != committed
