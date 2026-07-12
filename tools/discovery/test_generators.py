"""Smoke tests for the rounds-engine generators' committed outputs.

build_evidence_bundle.py needs uncommitted scratch inputs (IPEDS completions,
directory, scorecard pulls), so it cannot run in CI — instead these tests pin
the contract of its committed output. build_conformance_fixture.py consumes
only committed artifacts, so it IS regenerated here and compared against the
committed fixture: an edit to policy, ontology, scenarios, or the bundle that
forgets to regenerate the fixture fails here instead of shipping a stale
conformance baseline.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import build_conformance_fixture as bcf  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
BUNDLE = json.loads(
    (ROOT / "web" / "public" / "discovery" / "evidence-v1.json").read_text()
)

SCORECARD_FIELDS = {
    "locale", "avg_net_price", "net_price_0_30k", "median_debt_completers",
    "retention_rate_ft", "graduation_rate_4yr", "graduation_rate_6yr",
    "earnings_10yr_median", "pell_grant_rate", "scorecard_data_year",
}

SCHOOL_FIELDS = {
    "school_id", "ipeds_id", "name", "city", "state", "control",
    "lat", "lon", "enrollment", "direct", "adjacent", "scorecard",
}


def test_committed_bundle_school_invariants():
    schools = BUNDLE["schools"]
    assert BUNDLE["school_count"] == len(schools) > 0
    ids = [s["school_id"] for s in schools]
    assert ids == sorted(ids), "bundle must be sorted by school_id (stable ties)"
    assert len(ids) == len(set(ids)), "school_ids must be unique"
    for s in schools:
        assert set(s) == SCHOOL_FIELDS, s["school_id"]
        assert set(s["scorecard"]) == SCORECARD_FIELDS, s["school_id"]
        # Policy stage 1 eligibility: every pooled school reports in-family
        # bachelor's completions.
        assert s["direct"] or s["adjacent"], s["school_id"]


def test_committed_bundle_versions_agree_with_content_artifacts():
    policy = json.load(open(ROOT / "data/discovery/policy/v1.json"))
    ontology = json.load(open(ROOT / "data/discovery/ontology/v1.json"))
    assert BUNDLE["bundle_version"] == "evidence-v1"
    assert BUNDLE["policy_version"] == policy["policy_version"]
    assert BUNDLE["ontology_version"] == ontology["ontology_version"]


def test_conformance_fixture_is_fresh():
    """Regenerating the fixture from committed inputs must be a no-op."""
    committed = json.loads(bcf.OUT.read_text())
    out = bcf.ROOT / "scratch" / "test-conformance-fixture" / "fixture.json"
    original_out = bcf.OUT
    try:
        bcf.OUT = out
        assert bcf.main() == 0
        fresh = json.loads(out.read_text())
    finally:
        bcf.OUT = original_out
        if out.exists():
            out.unlink()
        if out.parent.exists():
            out.parent.rmdir()
    assert fresh == committed, (
        "committed rounds-conformance fixture is stale — rerun "
        "python3 tools/discovery/build_conformance_fixture.py"
    )


def test_conformance_fixture_covers_every_scenario():
    committed = json.loads(bcf.OUT.read_text())
    scenarios = json.load(open(ROOT / "data/discovery/scenarios/v1.json"))
    # every origin x profile pair, plus the synthetic whole-family case
    expected = len(scenarios["origins"]) * len(scenarios["profiles"]) + 1
    assert len(committed["cases"]) == expected
    ids = {c["scenario_id"] for c in committed["cases"]}
    assert "synthetic--whole-family" in ids
    assert committed["scenario_corpus_version"] == scenarios["scenario_corpus_version"]
