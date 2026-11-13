"""PRD 038 A12 tests: the OCR emission class and serving, the second-model gate, token completeness, hidden native text,
engine robustness, registration plateaus, and the safety rules the verifier's mutations showed untested. Synthetic only."""

from __future__ import annotations

import stat
import sys
from pathlib import Path

import numpy as np
import pypdf
import pytest
from pypdf.generic import ArrayObject, DecodedStreamObject, DictionaryObject, NameObject, NumberObject

sys.path.insert(0, str(Path(__file__).resolve().parent))
import lane2_ocr as L  # noqa: E402
import template_overlay as to  # noqa: E402
import test_lane2_ocr as X  # noqa: E402
import test_template_overlay as T  # noqa: E402

YEAR = "2025-26"


# ---- 1. OCR class, derived provenance, serving by construction -----------------------------------

def _b1_tags():
    to._import_tier2()
    import b1_derive_totals as B
    idx = B._index_total_fields(to._schema(YEAR)["fields"])
    tag_of = {f["question_number"]: f["pdf_tag"] for f in to._schema(YEAR)["fields"] if f.get("pdf_tag")}
    for (sg, ul, g), qn in idx.items():
        if ul == "All" and (sg, "FT", g) in idx and (sg, "PT", g) in idx and all(q in tag_of for q in (idx[(sg, "FT", g)], idx[(sg, "PT", g)])):
            return tag_of[idx[(sg, "FT", g)]], tag_of[idx[(sg, "PT", g)]], tag_of.get(qn), qn
    pytest.skip("no FT/PT/All total in this map")


def test_a_total_derived_from_a_lane_2_input_is_ocr_class_and_not_served():
    ft, pt, tot, tot_qn = _b1_tags()
    data = T.fill_and_flatten(YEAR, {ft: "100"}, {})

    def fake(env):
        env.record(pt, "20", 2, "Number", 12, to.CLASS_OCR_NUMERIC, {"ocr_confidence": 99.0})
    out = to.extract_overlay(data, lane2=fake)
    rec = out["values"][tot_qn]
    assert rec["value"] == "120" and rec["emission_class"] == "ocr_numeric" and set(rec["derived_lanes"]) == {2, "text"}
    served = {r.get("pdf_tag") for r in to.serve_values(out["values"]).values()}
    assert ft in served and pt not in served and tot_qn not in {k for k in to.serve_values(out["values"])}
    both = to.extract_overlay(T.fill_and_flatten(YEAR, {ft: "100", pt: "20"}, {}))              # the all-Lane-1 control
    ctl = both["values"][tot_qn]
    assert ctl["value"] == "120" and ctl["emission_class"] == "numeric" and ctl["derived_lanes"] == ["text"]
    assert tot_qn in to.serve_values(both["values"])


def test_serve_values_excludes_ocr_by_construction():
    mis = {"1": {"value": "5", "emission_class": "numeric", "lane": 2}, "2": {"value": "6", "emission_class": "numeric", "derived_lanes": [2, "text"]},
           "3": {"value": "7", "emission_class": "numeric", "lane": "text"}, "4": {"value": "8", "emission_class": "ocr_numeric", "lane": 2}}
    assert set(to.serve_values(mis)) == {"3"}                                                    # even a mislabelled Lane 2 record is not served
    assert set(to.serve_values(mis, {"numeric", "ocr_numeric"})) == {"1", "2", "3", "4"}          # shadow inspection is explicit
    assert "ocr_numeric" not in to.SERVE_CLASSES_DEFAULT and to.CLASS_OCR_NUMERIC == "ocr_numeric"


# ---- 7. the safety rules the verifier's mutations showed untested --------------------------------

def _pages_of_calls(monkeypatch, packet, value="999"):
    calls = []
    monkeypatch.setattr(L.Lane2, "read_widget", lambda self, c, t, f, wi, rect, st: (calls.append((t, c.p)), L.Lane2Read(value=value, text=value, conf=99.0))[1])
    return to.extract_overlay(packet, lane2=L.make_hook(X.FixedEngine([]))), calls


def test_lane_2_never_overwrites_or_rereads_a_cell_lane_1_emitted(monkeypatch):
    f1, w1 = X.widget("AP_RECD_1ST_MEN_N")
    f2, w2 = X.widget("AP_RECD_1ST_WMN_N")
    q = w1["template_page"]
    assert w2["template_page"] == q
    data = T.fill_and_flatten(YEAR, {}, {})
    data = T.add_text(data, q, w1["rect"][0] + 5, w1["rect"][1] + 5, "1234")                      # visible: Lane 1
    data = T.add_text(data, q, w2["rect"][0] + 5, w2["rect"][1] + 5, "2345", render_mode=3)       # invisible: the page goes to Lane 2
    out, calls = _pages_of_calls(monkeypatch, data)
    recs = {r["pdf_tag"]: r for r in out["values"].values() if "pdf_tag" in r}
    assert recs["AP_RECD_1ST_MEN_N"]["value"] == "1234" and recs["AP_RECD_1ST_MEN_N"]["lane"] == "text"
    assert "AP_RECD_1ST_MEN_N" not in [t for t, _p in calls]
    assert recs["AP_RECD_1ST_WMN_N"]["lane"] == 2 and recs["AP_RECD_1ST_WMN_N"]["value"] == "999"


def test_lane_2_reads_only_pages_that_have_no_text_layer_and_are_not_rejected(monkeypatch):
    text, _btn = T.rich_fill(YEAR)
    data = T.fill_and_flatten(YEAR, text, {})
    packet = T.assemble([(X.rasterise_page(data, 12), 0) if i == 12 else (data, i) for i in range(50)])
    _out, calls = _pages_of_calls(monkeypatch, packet)
    lane1_pages = {w["template_page"] for t, f in to.load_maps()[YEAR].fmap["fields"].items() if t in text for w in f["widgets"]}
    assert 12 in {p for _t, p in calls} and not ({p for _t, p in calls} & (lane1_pages - {12}))   # no page whose text layer holds answers is read
    a = T.add_text(T.fill_and_flatten(YEAR, {}, {}), 12, 460, 380, "1234")
    b = T.add_text(T.fill_and_flatten(YEAR, {}, {}), 12, 460, 380, "1235")
    blank = T.fill_and_flatten(YEAR, {}, {})
    dup = T.assemble([(X.rasterise_page(a, 12), 0) if i == 12 else (blank, i) for i in range(50)] + [(X.rasterise_page(b, 12), 0)])
    out, calls = _pages_of_calls(monkeypatch, dup)
    assert out["notes"]["stage1"]["rejected_template_pages"] and not [1 for _t, p in calls if p == 12]      # a rejected page is never read


# ---- 2. the second-model gate ---------------------------------------------------------------------

def _scripted(ctx, texts):
    c, tag, f, w, st = ctx
    return X.reader(c, texts).read_widget(c, tag, f, 0, w["rect"], st)


@pytest.fixture
def ctx(flat_numbers):
    c, tag, f, w, st = flat_numbers
    c._rect = w["rect"]
    return c, tag, f, w, st


from test_lane2_ocr import flat_numbers  # noqa: E402,F401  (the module fixture)


def test_second_model_must_read_the_same_value(ctx):
    assert _scripted(ctx, ["1234"] * 5).value == "1234"
    r = _scripted(ctx, ["1234"] * 4 + ["1235"])
    assert r.value is None and r.reason == "second_model_disagrees" and r.reads["second_model"] == "1235"
    r = _scripted(ctx, ["1234"] * 4 + [""])
    assert r.value is None and r.reason == "second_model_empty"


def test_second_read_without_the_whitelist_catches_a_letter(ctx):
    for letters in ("l234", "O234", "1234a", "12 34"):
        r = _scripted(ctx, ["1234"] * 4 + [letters])
        assert r.value is None and r.reason == "second_model_disagrees", letters


# ---- 3. token completeness and form ----------------------------------------------------------------

def _digits(text_ink_cols, h=40, w=300):
    img = np.full((h, w), 255, dtype=np.uint8)
    for a, b in text_ink_cols:
        img[8:32, a:b] = 0
    return img


def test_token_geometry_edge_and_internal_gap():
    one = _digits([(40, 50), (56, 66), (72, 82), (88, 98)])
    assert L.token_geometry(one, "1234") == (False, False)
    assert L.token_geometry(_digits([(40, 50), (56, 66), (120, 130), (136, 146)]), "1234")[1] is True       # a word space inside the token
    assert L.token_geometry(_digits([(0, 10), (16, 26)]), "12")[0] is True                                  # ink at the crop's left edge
    assert L.token_geometry(_digits([(274, 284), (290, 300)]), "12")[0] is True
    assert L.GAP_RATIO == 0.5


def test_two_numbers_in_one_cell_abstain_on_the_raster_not_on_word_count():
    blank = T.fill_and_flatten(YEAR, {}, {})
    f, w = X.widget("AP_RECD_1ST_MEN_N")
    data = T.add_text(blank, w["template_page"], w["rect"][0] + 5, w["rect"][1] + 5, "1 2", size=10)
    out = X.lane2(X.packet_with_raster_page(blank, w["template_page"], data))
    assert "AP_RECD_1ST_MEN_N" not in X.l2_values(out)


def test_an_answer_that_overlaps_the_cell_edge_abstains_through_the_unmodified_raster():
    blank = T.fill_and_flatten(YEAR, {}, {})
    f, w = X.widget("AP_RECD_1ST_MEN_N")
    data = T.add_text(blank, w["template_page"], w["rect"][0] - 2.0, w["rect"][1] + 5, "1234", size=8)
    out = X.lane2(X.packet_with_raster_page(blank, w["template_page"], data))
    assert X.l2_values(out).get("AP_RECD_1ST_MEN_N") is None
    assert X.l2_held(out, "AP_RECD_1ST_MEN_N") == ["context_disagrees"]          # this Helvetica fixture is stopped by the context read; Codex's Times Roman probe by `raw_glyph_crosses_left_edge` (REPORT_v2)


# ---- 4. hidden native text --------------------------------------------------------------------------

def _paint_white_image(data: bytes, page: int, rect, *, behind: bool) -> bytes:
    w = T._writer_from(data)
    pg = w.pages[page]
    img = DecodedStreamObject()
    img.set_data(b"\xff")
    img.update({NameObject("/Type"): NameObject("/XObject"), NameObject("/Subtype"): NameObject("/Image"), NameObject("/Width"): NumberObject(1),
                NameObject("/Height"): NumberObject(1), NameObject("/ColorSpace"): NameObject("/DeviceGray"), NameObject("/BitsPerComponent"): NumberObject(8)})
    xo = pg["/Resources"].get("/XObject")
    xo = xo.get_object() if xo is not None else DictionaryObject()
    xo[NameObject("/FxImg")] = w._add_object(img)
    pg["/Resources"][NameObject("/XObject")] = xo
    x0, y0, x1, y1 = rect
    draw = T._raw(w, f"\nq {x1 - x0 + 4} 0 0 {y1 - y0 + 4} {x0 - 2} {y0 - 2} cm /FxImg Do Q\n".encode())
    parts = T._contents_parts(pg)
    pg[NameObject("/Contents")] = ArrayObject(([draw] + parts) if behind else (parts + [draw]))
    return T._write(w)


def test_native_text_painted_over_by_a_later_image_is_not_read_by_lane_1():
    f, w = X.widget("AP_RECD_1ST_MEN_N")
    q = w["template_page"]
    typed = T.add_text(T.fill_and_flatten(YEAR, {}, {}), q, w["rect"][0] + 5, w["rect"][1] + 5, "6789")
    over = to.extract_overlay(_paint_white_image(typed, q, w["rect"], behind=False))
    assert "AP_RECD_1ST_MEN_N" not in T._values_by_tag(over) \
        and any(o["pdf_tag"] == "AP_RECD_1ST_MEN_N" and o["reason"] == "invisible_text" for o in over["notes"]["ocr_widgets"])      # hidden text: not Lane 1, a Lane 2 work item
    under = to.extract_overlay(_paint_white_image(typed, q, w["rect"], behind=True))                         # the image is behind the text: the text shows
    assert T._values_by_tag(under).get("AP_RECD_1ST_MEN_N") == "6789"


# ---- 5. engine robustness --------------------------------------------------------------------------

def test_a_failed_tesseract_run_raises(tmp_path):
    exe = tmp_path / "fake-tesseract"
    exe.write_text("#!/bin/sh\necho 'Failed loading language eng' 1>&2\nexit 1\n")
    exe.chmod(exe.stat().st_mode | stat.S_IEXEC)
    with pytest.raises(RuntimeError, match="exited 1"):
        L.TesseractEngine(exe=str(exe)).read(np.full((20, 40), 255, dtype=np.uint8))


def test_a_failed_probe_or_missing_second_model_disables_lane_2_and_says_why(tmp_path):
    assert "second_model_missing_or_wrong_sha" in (L.TesseractEngine(best_dir=str(tmp_path)).check() or "") or not L.TesseractEngine.available()

    class Broken:
        def check(self):
            return "probe_misread: primary '', second ''"

        def read(self, img, **kw):
            raise AssertionError("a disabled Lane 2 must not read")
    data = T.fill_and_flatten(YEAR, {}, {})
    out = to.extract_overlay(X.packet_with_raster_page(data, 12, data), lane2=L.make_hook(Broken()))
    assert out["notes"]["lane2_disabled"].startswith("probe_misread") and not X.l2_values(out)


def test_model_shas_are_recorded_and_pinned():
    assert set(L.MODEL_SHA256) == {"fast", "best"} and all(len(v) == 64 for v in L.MODEL_SHA256.values())
    if L.TesseractEngine.available():
        out = to.extract_overlay(T.fill_and_flatten(YEAR, {}, {}), lane2=L.make_hook(L.TesseractEngine()))
        assert out["notes"]["ocr_engine"].startswith("tesseract") and set(out["notes"]["ocr_models"]) == {"fast_sha256", "best_sha256"}


# ---- 6. registration plateaus -----------------------------------------------------------------------

def test_subpoint_refinement_never_averages_disconnected_maxima():
    k = to.INK_DPI / 72.0
    t = np.full((int(792 * k), int(612 * k)), 255, dtype=np.uint8)
    for r, c, h, w in [(200, 150, 3, 200), (400, 150, 3, 200), (200, 150, 200, 3), (200, 347, 200, 3), (300, 250, 40, 3)]:
        t[r:r + h, c:c + w] = 0
    page = np.minimum(np.roll(t, 2, axis=1), np.roll(t, -2, axis=1))                  # two impressions 4 px apart: two disconnected maxima
    dx, dy = to.refine_subpoint_shift(page, t, 0.0, 0.0)
    assert (dx, dy) in {(0.0, 0.0), (2 / k, 0.0), (-2 / k, 0.0)}, (dx, dy)             # one of the maxima, or no refinement; never the mean between them
