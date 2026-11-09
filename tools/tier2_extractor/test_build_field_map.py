"""Tests for tools/tier2_extractor/build_field_map.py (PRD 038 M0).

Run: python -m pytest tools/tier2_extractor -q

Every map rebuilds byte-for-byte from its blank template in schemas/templates/.
The optional 2024-25 donor cross-check needs donor PDFs (school documents,
never committed): set CDS_2024_25_DONORS to two or more PDF paths separated by
os.pathsep, otherwise that test is skipped.
"""

from __future__ import annotations

import copy
import json
import os
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_field_map as bfm  # noqa: E402

EXPECTED = {
    # year: (fields, widgets, Tx, Ch, Btn)
    "2025-26": (1089, 1263, 789, 76, 398),
    "2024-25": (1116, 1257, 817, 76, 364),
    "2023-24": (1086, 1228, 784, 76, 368),
}

# Raster rebuilds can differ by antialiasing across pdfium builds; tolerate a
# tiny pixel drift only when the committed map was rendered by another build.
MAX_MASK_DRIFT = 0.01  # measured ~0.3% between pypdfium2 5.5.0 and 5.15.1


@pytest.fixture(scope="module")
def maps():
    return {y: bfm.load_field_map(y) for y in EXPECTED}


@pytest.mark.parametrize("year", sorted(EXPECTED))
def test_field_and_widget_counts(maps, year):
    fields, widgets, tx, ch, btn = EXPECTED[year]
    m = maps[year]
    assert len(m["fields"]) == fields
    all_widgets = [(f["ft"], w) for f in m["fields"].values() for w in f["widgets"]]
    assert len(all_widgets) == widgets
    by_ft = {ft: sum(1 for t, _ in all_widgets if t == ft) for ft in ("/Tx", "/Ch", "/Btn")}
    assert by_ft == {"/Tx": tx, "/Ch": ch, "/Btn": btn}
    assert m["stats"]["fields"] == fields and m["stats"]["widgets"] == widgets
    assert len(m["pages"]) == 50


@pytest.mark.parametrize("year", sorted(EXPECTED))
def test_no_inverted_or_off_page_rects(maps, year):
    m = maps[year]
    for tag, f in m["fields"].items():
        for w in f["widgets"]:
            x0, y0, x1, y1 = w["rect"]
            assert x0 < x1 and y0 < y1, f"{tag}: inverted rect {w['rect']}"
            page = m["pages"][w["template_page"]]
            assert 0 <= x0 and x1 <= page["width_pt"] + 1, f"{tag}: off page {w['rect']}"
            assert 0 <= y0 and y1 <= page["height_pt"] + 1, f"{tag}: off page {w['rect']}"


def test_2025_26_inverted_rects_were_normalized(maps):
    # The blank 2025-26 template stores 114 widgets with inverted /Rect.
    assert maps["2025-26"]["stats"]["inverted_rects_normalized"] == 114
    assert maps["2024-25"]["stats"]["inverted_rects_normalized"] == 0
    assert maps["2023-24"]["stats"]["inverted_rects_normalized"] == 0


@pytest.mark.parametrize("year", sorted(EXPECTED))
def test_field_records(maps, year):
    for tag, f in maps[year]["fields"].items():
        assert f["ft"] in ("/Tx", "/Ch", "/Btn")
        if f["ft"] == "/Ch":
            assert f.get("opt"), f"{tag}: choice field without /Opt"
            assert all(len(p) == 2 for p in f["opt"])
        for w in f["widgets"]:
            if f["ft"] == "/Btn":
                assert "on_state" in w
            else:
                assert "on_state" not in w
            assert isinstance(w["static_text"], str)


def test_btn_on_states_present(maps):
    for year, m in maps.items():
        missing = [t for t, f in m["fields"].items() if f["ft"] == "/Btn"
                   for w in f["widgets"] if not w["on_state"]]
        assert not missing, f"{year}: button widgets without an /AP /N on-state: {missing[:5]}"


def test_schema_join(maps):
    # question_number comes from the year's own schema; tags it does not know stay null.
    assert maps["2025-26"]["stats"]["tags_not_in_schema"] == 2
    assert maps["2024-25"]["stats"]["tags_not_in_schema"] == 302
    assert maps["2023-24"]["stats"]["tags_not_in_schema"] == 276
    for year, m in maps.items():
        idx = bfm.load_schema_index(year)
        for tag, f in m["fields"].items():
            if tag in idx:
                assert f["question_number"] == idx[tag]["question_number"]
                assert f["value_type"] == idx[tag]["value_type"]
            else:
                assert f["question_number"] is None and f["value_type"] is None


def test_mask_codec_roundtrip():
    rng = np.random.default_rng(0)
    for shape in [(1, 1), (7, 13), (396, 306)]:
        for fill in (0.0, 0.03, 0.5, 1.0):
            m = rng.random(shape) < fill
            assert np.array_equal(bfm.decode_mask(bfm.encode_mask(m), shape[1], shape[0]), m)
    ink_first = np.array([[True, False, False, True]])
    assert np.array_equal(bfm.decode_mask(bfm.encode_mask(ink_first), 4, 1), ink_first)


@pytest.mark.parametrize("year", sorted(EXPECTED))
def test_masks_decode(maps, year):
    for pg in maps[year]["pages"]:
        mk = pg["mask"]
        arr = bfm.decode_mask(mk["rle"], mk["width"], mk["height"])
        assert arr.shape == (mk["height"], mk["width"]) == (round(pg["height_pt"] / 2), round(pg["width_pt"] / 2))
        assert int(arr.sum()) == mk["ink_pixels"] > 100


def test_serialization_is_diff_stable(maps):
    for year, m in maps.items():
        text = bfm.dumps_field_map(m)
        assert text == bfm.field_map_path_for(year).read_text()
        assert json.loads(text) == m
        assert text.count("\n") < 1300  # one line per field/page, not one per token


def _compare_to_rebuild(year, rebuilt):
    committed = bfm.load_field_map(year)
    a, b = copy.deepcopy(committed), copy.deepcopy(rebuilt)
    same_engine = a["raster"]["engine"] == b["raster"]["engine"]
    if same_engine:
        assert bfm.dumps_field_map(b) == bfm.field_map_path_for(year).read_text()
        return
    for m in (a, b):
        m["raster"]["engine"] = None
    pa, pb = a.pop("pages"), b.pop("pages")
    assert a == b
    for x, y in zip(pa, pb):
        assert {k: x[k] for k in x if k != "mask"} == {k: y[k] for k in y if k != "mask"}
        ma = bfm.decode_mask(x["mask"]["rle"], x["mask"]["width"], x["mask"]["height"])
        mb = bfm.decode_mask(y["mask"]["rle"], y["mask"]["width"], y["mask"]["height"])
        assert (ma ^ mb).sum() <= MAX_MASK_DRIFT * max(ma.sum(), 1)


@pytest.mark.parametrize("year", sorted(EXPECTED))
def test_committed_map_equals_fresh_rebuild(year):
    template = bfm.template_path_for(year)
    assert template.exists(), f"{template} must be committed"
    assert bfm.load_field_map(year)["source"]["files"][0]["sha256"] == bfm.sha256_of(template)
    rebuilt = bfm.build_field_map(year, [template], kind="blank_template")
    _compare_to_rebuild(year, rebuilt)


@pytest.mark.parametrize("year", sorted(EXPECTED))
def test_maps_are_built_from_blank_templates(maps, year):
    m = maps[year]
    assert m["source"]["kind"] == "blank_template"
    assert m["source"]["files"][0]["path"] == f"schemas/templates/cds_{year}_template.pdf"
    assert "donors" not in m["stats"]


def test_template_shas_match_sources_md():
    sources = (bfm.TEMPLATE_DIR / "SOURCES.md").read_text()
    for year in EXPECTED:
        sha = bfm.sha256_of(bfm.template_path_for(year))
        assert f"`cds_{year}_template.pdf`" in sources and sha in sources, year


@pytest.mark.parametrize("year", sorted(EXPECTED))
def test_coordinate_convention_recorded(maps, year):
    c = maps[year]["coordinates"]
    assert c["page_index_base"] == 0 and "bottom-left" in c["origin"] and "points" in c["units"]
    assert all(0 <= w["template_page"] < 50 for f in maps[year]["fields"].values() for w in f["widgets"])


def test_rotc_text_tags_join_distinct_questions(maps):
    expected = {"ROTC_ARMY_TEXT": "F.303", "ROTC_NAVY_TEXT": "F.307", "ROTC_AF_TEXT": "F.310"}
    for year in ("2023-24", "2024-25"):
        for tag, qn in expected.items():
            assert maps[year]["fields"][tag]["question_number"] == qn, (year, tag)
    assert maps["2025-26"]["fields"]["ROTC_NAVY_TEXT"]["question_number"] == "F.305"


def test_duplicate_pdf_tag_in_schema_raises(tmp_path, monkeypatch):
    schema = {"fields": [
        {"question_number": "A.1", "pdf_tag": "DUP", "value_type": "Text"},
        {"question_number": "A.2", "pdf_tag": "DUP", "value_type": "Text"},
    ]}
    path = tmp_path / "s.json"
    path.write_text(json.dumps(schema))
    monkeypatch.setattr(bfm, "schema_path_for", lambda year: path)
    with pytest.raises(ValueError, match="DUP.*A.1.*A.2"):
        bfm.load_schema_index("2025-26")


@pytest.mark.parametrize("year", sorted(EXPECTED))
def test_real_schemas_have_unique_pdf_tags(year):
    bfm.load_schema_index(year)  # raises on duplicates


def test_2024_25_donors_agree_and_match_blank_map():
    """Optional cross-check: donor consensus reproduces the blank-derived map."""
    raw = os.environ.get("CDS_2024_25_DONORS", "")
    donors = [Path(p) for p in raw.split(os.pathsep) if p]
    if len(donors) < 2:
        pytest.skip("set CDS_2024_25_DONORS to >= 2 donor PDFs for the donor cross-check")
    committed = bfm.load_field_map("2024-25")
    rebuilt = bfm.build_field_map("2024-25", donors, kind="donor_consensus")  # raises on disagreement
    assert rebuilt["stats"]["text_disagreements"] == 0
    assert set(rebuilt["fields"]) == set(committed["fields"])
    for tag, f in committed["fields"].items():
        g = rebuilt["fields"][tag]
        assert (f["ft"], f.get("opt"), f["question_number"]) == (g["ft"], g.get("opt"), g["question_number"])
        assert len(f["widgets"]) == len(g["widgets"])
        for w, v in zip(f["widgets"], g["widgets"]):
            assert w["template_page"] == v["template_page"] and w.get("on_state") == v.get("on_state")
            assert w["static_text"] == v["static_text"]
            assert max(abs(p - q) for p, q in zip(w["rect"], v["rect"])) < 0.005
    for a, b in zip(committed["pages"], rebuilt["pages"]):
        ma = bfm.decode_mask(a["mask"]["rle"], a["mask"]["width"], a["mask"]["height"])
        mb = bfm.decode_mask(b["mask"]["rle"], b["mask"]["width"], b["mask"]["height"])
        assert (ma ^ mb).sum() <= MAX_MASK_DRIFT * max(ma.sum(), 1)


# ---- consensus rules, exercised without donor PDFs --------------------------

def _harvest_of_template():
    return bfm.harvest_acroform(bfm.template_path_for("2025-26"))


def _shift(harvest, dx):
    h = copy.deepcopy(harvest)
    for f in h["fields"].values():
        for w in f["widgets"]:
            w["rect"] = [w["rect"][0] + dx, w["rect"][1], w["rect"][2] + dx, w["rect"][3]]
    return h


def test_consensus_accepts_within_tolerance_and_rejects_beyond():
    base = _harvest_of_template()
    merged = bfm._consensus_fields([base, _shift(base, 0.4)], 0.5)
    tag = next(iter(merged))
    assert abs(merged[tag]["widgets"][0]["rect"][0] - (base["fields"][tag]["widgets"][0]["rect"][0] + 0.2)) < 1e-9
    with pytest.raises(bfm.DonorDisagreement, match="exceeds"):
        bfm._consensus_fields([base, _shift(base, 0.6)], 0.5)


def test_consensus_rejects_field_set_and_widget_count_mismatch():
    base = _harvest_of_template()
    missing = copy.deepcopy(base)
    del missing["fields"][next(iter(missing["fields"]))]
    with pytest.raises(bfm.DonorDisagreement, match="field set"):
        bfm._consensus_fields([base, missing], 0.5)
    fewer = copy.deepcopy(base)
    tag = next(t for t, f in fewer["fields"].items() if len(f["widgets"]) > 1)
    fewer["fields"][tag]["widgets"].pop()
    with pytest.raises(bfm.DonorDisagreement, match="widget count"):
        bfm._consensus_fields([base, fewer], 0.5)


def test_donor_build_needs_two_distinct_documents():
    t = bfm.template_path_for("2025-26")
    with pytest.raises(ValueError, match="at least 2"):
        bfm.build_field_map("2024-25", [t], kind="donor_consensus")
    with pytest.raises(ValueError, match="duplicate"):
        bfm.build_field_map("2024-25", [t, t], kind="donor_consensus")
