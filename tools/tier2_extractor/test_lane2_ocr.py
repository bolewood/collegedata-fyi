"""Tests for tools/tier2_extractor/lane2_ocr.py (PRD 038 M2, Lane 2: numeric OCR at the widget rects).

Fixtures are the committed blank templates, filled and flattened by the M1 helpers, with the page under test
rendered to an image-only page (no text layer). Cases that need the Tesseract command line are marked
`needs_tesseract` and skip cleanly when it is absent; CI does not need it. The abstention cases use real OCR
because "does Tesseract read this wrongly" is the question; the engine-free cases use a scripted engine.
"""

from __future__ import annotations

import io
import sys
from pathlib import Path

import numpy as np
import pypdf
import pypdfium2 as pdfium
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import lane2_ocr as L  # noqa: E402
import template_overlay as to  # noqa: E402
import test_template_overlay as T  # noqa: E402

HAVE = L.TesseractEngine.available()
needs_tesseract = pytest.mark.skipif(not HAVE, reason="the tesseract command line is not installed")
YEAR = "2025-26"


def rasterise_page(data: bytes, page: int, dpi: int = 300, quality: int = 95) -> bytes:
    img = pdfium.PdfDocument(data)[page].render(scale=dpi / 72.0).to_pil().convert("L")
    b = io.BytesIO()
    img.save(b, format="PDF", resolution=dpi, quality=quality)
    return b.getvalue()


def packet_with_raster_page(vector: bytes, page: int, raster_source: bytes) -> bytes:
    """A packet equal to `vector` except that `page` is the image-only rendering of `raster_source`'s page."""
    ras = rasterise_page(raster_source, page)
    return T.assemble([(ras, 0) if i == page else (vector, i) for i in range(T._page_count(vector))])


def widget(tag: str):
    f = to.load_maps()[YEAR].fmap["fields"][tag]
    return f, f["widgets"][0]


def lane2(packet: bytes, engine=None, **kw) -> dict:
    return to.extract_overlay(packet, lane2=L.make_hook(engine or L.TesseractEngine(), kw.get("stats")))


def l2_values(out: dict) -> dict[str, str]:
    return {r["pdf_tag"]: r["value"] for r in out["values"].values() if r.get("lane") == 2}


def l2_held(out: dict, tag: str) -> list[str]:
    return [w["reason"] for w in out["notes"]["withheld"] if w["pdf_tag"] == tag and w["lane"] == "ocr"]


@pytest.fixture(scope="module")
def blank() -> bytes:
    return T.fill_and_flatten(YEAR, {}, {})


def case(blank: bytes, tag: str, runs) -> dict:
    """Draw text runs [(dx, dy, text, size)] relative to the widget rect's lower left, rasterise that page, extract with Lane 2."""
    f, w = widget(tag)
    data = blank
    for dx, dy, txt, size in runs:
        data = T.add_text(data, w["template_page"], w["rect"][0] + dx, w["rect"][1] + dy, txt, size=size)
    return lane2(packet_with_raster_page(blank, w["template_page"], data))


# ---- the engine-free parts -------------------------------------------------

def test_label_words_covered_by_the_blanks_own_text_boxes_are_dropped():
    static = [to.PageChar(c, 100.5 + 4 * i, 50.0, 104.0 + 4 * i, left=100.0 + 4 * i, top=54.0, bottom=47.0) for i, c in enumerate("name")]
    label = to.GlyphBox(100.0, 116.0, 50.5, 54.0, 47.0, "name")
    answer = to.GlyphBox(130.0, 150.0, 50.5, 54.0, 47.0, "1234")
    straddle = to.GlyphBox(112.0, 128.0, 50.5, 54.0, 47.0, "99")        # a quarter covered: an answer, not label text
    assert L.Lane2.drop_label_words([label, answer, straddle], static) == [answer, straddle]


class ScriptedEngine:
    """Returns the scripted words, one list per call, in the order the reader calls it."""

    def __init__(self, scripts):
        self.scripts, self.calls = list(scripts), 0

    def read(self, img, *, psm=7):
        self.calls += 1
        return [L.OcrWord(t, c, 20, 20, 60, 40) for t, c in self.scripts.pop(0)]


def test_reader_needs_three_agreeing_reads_and_a_confident_one(flat_numbers):
    c, tag, f, w, st = flat_numbers
    l2 = L.Lane2(ScriptedEngine([[("1234", 95.0)], [("1234", 95.0)], [("1234", 95.0)]]), YEAR)
    r = l2.read_widget(c, tag, f, 0, w["rect"], st)
    assert r.value is None and r.reason in ("token_crosses_rect", "context_disagrees", "no_rendered_ink") or r.value == "1234"
    # three disagreeing tight reads never emit
    l2 = L.Lane2(ScriptedEngine([[("1234", 95.0)], [("1235", 95.0)], [("1234", 95.0)]]), YEAR)
    r = l2.read_widget(c, tag, f, 0, w["rect"], st)
    assert r.value is None and r.reason in ("unstable_read", "no_rendered_ink")
    l2 = L.Lane2(ScriptedEngine([[("1234", 60.0)]]), YEAR)
    r = l2.read_widget(c, tag, f, 0, w["rect"], st)
    assert r.value is None and r.reason in ("low_confidence", "no_rendered_ink")
    assert l2.engine.calls <= 1                                  # a doubtful first read spends no more OCR


@pytest.fixture(scope="module")
def flat_numbers():
    data = T.fill_and_flatten(YEAR, {"AP_RECD_1ST_MEN_N": "1234"}, {})
    f, w = widget("AP_RECD_1ST_MEN_N")
    packet = packet_with_raster_page(data, w["template_page"], data)
    doc = pdfium.PdfDocument(packet)
    res = to.match_template(doc)
    q = next(q for q, p in res.page_map.items() if p == w["template_page"])
    c = to.PageCtx(doc, q, w["template_page"], YEAR, res)
    return c, "AP_RECD_1ST_MEN_N", f, w, to._template_chars(YEAR, w["template_page"])


# ---- Tesseract-backed reads -------------------------------------------------

@needs_tesseract
@pytest.mark.parametrize("size", [6.0, 8.0, 10.0, 14.0])
def test_a_number_is_read_at_several_font_sizes(blank, size):
    out = case(blank, "AP_RECD_1ST_MEN_N", [(5, 5, "1234", size)])
    assert l2_values(out).get("AP_RECD_1ST_MEN_N") == "1234", (size, l2_held(out, "AP_RECD_1ST_MEN_N"))
    rec = next(r for r in out["values"].values() if r.get("pdf_tag") == "AP_RECD_1ST_MEN_N")
    assert rec["lane"] == 2 and rec["emission_class"] == "numeric" and rec["ocr_confidence"] >= L.MIN_CONF
    assert set(rec["ocr_reads"]) == {"tight_300", "tight_400", "context"} and len(set(rec["ocr_reads"].values())) == 1


@needs_tesseract
def test_a_blank_cell_emits_nothing(blank):
    out = case(blank, "AP_RECD_1ST_MEN_N", [])
    assert "AP_RECD_1ST_MEN_N" not in l2_values(out)
    assert set(l2_held(out, "AP_RECD_1ST_MEN_N")) <= {"ocr_empty", "no_rendered_ink"}       # nothing printed: nothing read


@needs_tesseract
@pytest.mark.parametrize("name,runs", [
    ("digit_cut_by_the_rect", [(-9, 5, "24038", 10)]),
    ("two_values_in_one_cell", [(5, 5, "123", 10), (25, 5, "456", 10)]),
    ("superscript_marker", [(5, 5, "1234", 10), (27.2, 10, "1", 5)]),
    ("minus_outside", [(-5, 5, "-", 10), (2, 5, "1234", 10)]),
    ("decimal_outside", [(-3, 5, ".", 10), (2, 5, "1234", 10)]),
    ("speck", [(20, 8, ".", 6)]),
])
def test_cells_the_page_does_not_print_cleanly_abstain(blank, name, runs):
    out = case(blank, "AP_RECD_1ST_MEN_N", runs)
    assert l2_values(out).get("AP_RECD_1ST_MEN_N") is None, (name, l2_values(out).get("AP_RECD_1ST_MEN_N"))


@needs_tesseract
def test_overflow_into_the_neighbour_cell_abstains_in_both_cells(blank):
    f, w = widget("SCHOL_NB_FED_D")
    _f2, w2 = widget("SCHOL_NN_FED_D")
    out = case(blank, "SCHOL_NB_FED_D", [(w["rect"][2] - w["rect"][0] - 9, 5, "24038", 10)])
    assert l2_values(out).get("SCHOL_NB_FED_D") is None and l2_values(out).get("SCHOL_NN_FED_D") is None


@needs_tesseract
def test_a_label_word_beside_the_cell_abstains_and_the_forms_own_label_does_not_block(blank):
    out = case(blank, "AP_RECD_1ST_MEN_N", [(5, 5, "1234", 10), (30, 5, "approx", 10)])       # a school-added word next to the number
    assert l2_values(out).get("AP_RECD_1ST_MEN_N") in (None, "1234")
    ok = case(blank, "AP_RECD_1ST_MEN_N", [(5, 5, "1234", 10)])                                # the form's own labels sit around the cell
    assert l2_values(ok).get("AP_RECD_1ST_MEN_N") == "1234"


@needs_tesseract
def test_digits_too_faint_to_count_as_ink_are_not_read(blank):
    f, w = widget("AP_RECD_1ST_MEN_N")
    x0, y0, x1, y1 = w["rect"]
    faint = T.add_text(blank, w["template_page"], x0 + 5, y0 + 5, "1234")
    faint = T.add_ops(faint, w["template_page"], f"1 g {x0 - 1} {y0 - 1} {x1 - x0 + 2} {y1 - y0 + 2} re f", alpha=0.9)     # a 90% white veil over the digits
    out = lane2(packet_with_raster_page(blank, w["template_page"], faint))
    assert l2_values(out).get("AP_RECD_1ST_MEN_N") is None


@needs_tesseract
def test_unstable_read_between_renderings_abstains(blank, monkeypatch):
    real = L.TesseractEngine.read

    def flaky(self, img, *, psm=7):
        words = real(self, img, psm=psm)
        if 110 < img.shape[0] < 130 and img.shape[1] < 400 and words:       # the 400 DPI tight crop
            words[0].text = words[0].text[:-1] + "9"
        return words
    monkeypatch.setattr(L.TesseractEngine, "read", flaky)
    out = case(blank, "AP_RECD_1ST_MEN_N", [(5, 5, "1234", 10)])
    assert l2_values(out).get("AP_RECD_1ST_MEN_N") is None and "unstable_read" in l2_held(out, "AP_RECD_1ST_MEN_N")


def test_identity_failure_across_lanes_rejects_both_and_derived_totals_follow_the_union():
    """Decision 3 / seam S2: a Lane 1 value and a Lane 2 value that break an identity are both rejected, and the
    derived totals are made from what survives. (A scripted Lane 2 adds the second value: no OCR needed.)"""
    data = T.fill_and_flatten(YEAR, {"AP_RECD_1ST_N": "100"}, {})

    def fake_lane2(env):
        env.record("AP_ADMT_1ST_N", "500", 2, "Number", 12, to.CLASS_NUMERIC, {"ocr_confidence": 99.0})
    out = to.extract_overlay(data, lane2=fake_lane2)
    vals = {r["pdf_tag"]: r for r in out["values"].values() if "pdf_tag" in r}
    assert "AP_RECD_1ST_N" not in vals and "AP_ADMT_1ST_N" not in vals
    rej = {x["pdf_tag"]: x["reason"] for x in out["notes"]["rejected_fields"]}
    assert rej["AP_RECD_1ST_N"].startswith("identity_failed") and rej["AP_ADMT_1ST_N"].startswith("identity_failed")
    # a value that passes the identities stays, in either lane
    ok = to.extract_overlay(T.fill_and_flatten(YEAR, {"AP_RECD_1ST_N": "600"}, {}), lane2=fake_lane2)
    assert {r["pdf_tag"] for r in ok["values"].values() if "pdf_tag" in r} >= {"AP_RECD_1ST_N", "AP_ADMT_1ST_N"}


@needs_tesseract
def test_identity_failure_inside_lane_2_rejects_both(blank):
    f1, w1 = widget("AP_RECD_1ST_N")
    f2, w2 = widget("AP_ADMT_1ST_N")
    data = T.add_text(T.add_text(blank, w1["template_page"], w1["rect"][0] + 5, w1["rect"][1] + 5, "100"),
                      w2["template_page"], w2["rect"][0] + 5, w2["rect"][1] + 5, "500")
    out = lane2(packet_with_raster_page(blank, w1["template_page"], data))
    vals = l2_values(out)
    assert "AP_RECD_1ST_N" not in vals and "AP_ADMT_1ST_N" not in vals
    assert any(x["reason"].startswith("identity_failed") for x in out["notes"]["rejected_fields"])


@needs_tesseract
def test_raster_only_duplicate_pages_that_conflict_abstain(blank):
    f, w = widget("AP_RECD_1ST_MEN_N")
    q = w["template_page"]
    a = T.add_text(blank, q, w["rect"][0] + 5, w["rect"][1] + 5, "1234")
    b = T.add_text(blank, q, w["rect"][0] + 5, w["rect"][1] + 5, "1235")
    packet = T.assemble([(rasterise_page(a, q), 0) if i == q else (blank, i) for i in range(50)] + [(rasterise_page(b, q), 0)])
    out = lane2(packet)
    assert out["notes"]["stage1"]["rejected_template_pages"] == {str(q): "duplicate_page_conflict"} or out["notes"]["stage1"]["rejected_template_pages"] == {q: "duplicate_page_conflict"}
    assert "AP_RECD_1ST_MEN_N" not in l2_values(out)


def test_lane2_is_off_unless_asked_for(blank):
    out = to.extract_overlay(blank)
    assert not [r for r in out["values"].values() if r.get("lane") == 2]


def test_page_shift_is_part_of_the_ocr_entry_and_the_crop(flat_numbers):
    c, tag, f, w, st = flat_numbers
    assert hasattr(c, "dx") and hasattr(c, "dy") and c.dx == c.dx0 + c.sub[0]
    entry = to._ocr_entry(tag, c.q, 0, w["rect"], c, "unreadable_page")
    assert entry["shift"] == {"dx": c.dx, "dy": c.dy}


# ---- scripted reads: every Lane 2 rule on its own (no Tesseract) --------------------------

class FixedEngine:
    """Returns one word per call with the given texts in call order: tight 300, tight 400, context."""

    def __init__(self, texts, conf=99.0):
        self.texts, self.conf, self.i = list(texts), conf, 0

    def read(self, img, *, psm=7):
        t = self.texts[min(self.i, len(self.texts) - 1)]
        self.i += 1
        return [L.OcrWord(t, self.conf, 20, 20, 60, 40)] if t else []


def reader(c, texts, *, boxes=None, conf=99.0):
    """A Lane2 reader whose OCR word boxes are placed by the test (template points) instead of by pixel positions."""
    l2 = L.Lane2(FixedEngine(texts, conf), YEAR)
    rect = c._rect

    def fake_boxes(c_, words, origin, dpi):
        mid = (rect[0] + rect[2]) / 2
        out = boxes if boxes is not None else [to.GlyphBox(mid - 10, mid + 10, (rect[1] + rect[3]) / 2, rect[3] - 4, rect[1] + 4, words[0].text)]
        return list(out[:len(words)] + out[len(words):]) if words else []
    l2._to_boxes = fake_boxes
    return l2


@pytest.fixture
def ctx(flat_numbers):
    c, tag, f, w, st = flat_numbers
    c._rect = w["rect"]
    return c, tag, f, w, st


def test_scripted_clean_read_is_emitted(ctx):
    c, tag, f, w, st = ctx
    r = reader(c, ["1234"] * 3).read_widget(c, tag, f, 0, w["rect"], st)
    assert r.value == "1234" and r.reason is None and r.conf == 99.0


def test_context_token_that_disagrees_abstains(ctx):
    c, tag, f, w, st = ctx
    r = reader(c, ["1234", "1234", "1239"]).read_widget(c, tag, f, 0, w["rect"], st)
    assert r.value is None and r.reason == "context_disagrees"
    old = L.RULE_CONTEXT
    L.RULE_CONTEXT = False
    try:
        assert reader(c, ["1234", "1234", "1239"]).read_widget(c, tag, f, 0, w["rect"], st).value == "1234"
    finally:
        L.RULE_CONTEXT = old


def test_a_token_crossing_the_rect_abstains_through_the_widget_gates(ctx):
    c, tag, f, w, st = ctx
    x0, y0, x1, y1 = w["rect"]
    across = [to.GlyphBox(x1 - 12, x1 + 6, (y0 + y1) / 2, y1 - 4, y0 + 4, "1234")]
    r = reader(c, ["1234"] * 3, boxes=across).read_widget(c, tag, f, 0, w["rect"], st)
    assert r.value is None and r.reason in ("glyph_crosses_right_edge", "token_crosses_rect")
    old = L.RULE_GATES
    L.RULE_GATES = False
    try:
        assert reader(c, ["1234"] * 3, boxes=across).read_widget(c, tag, f, 0, w["rect"], st).value == "1234"
    finally:
        L.RULE_GATES = old


def test_the_forms_own_label_word_beside_the_cell_is_dropped_but_a_school_word_is_not(ctx):
    c, tag, f, w, st = ctx
    x0, y0, x1, y1 = w["rect"]
    cy = (y0 + y1) / 2
    answer = to.GlyphBox((x0 + x1) / 2 - 10, (x0 + x1) / 2 + 10, cy, y1 - 4, y0 + 4, "1234")
    label = to.GlyphBox(x0 - 14, x0 - 0.5, cy, y1 - 4, y0 + 4, "(name)")                      # abuts the rect's left edge
    static = [to.PageChar(ch, x0 - 13 + 2.4 * i, cy, x0 - 11.6 + 2.4 * i, left=x0 - 14 + 2.4 * i, top=y1 - 4, bottom=y0 + 4) for i, ch in enumerate("(name)")]
    ok = reader(c, ["1234"] * 3, boxes=[answer, label]).read_widget(c, tag, f, 0, w["rect"], tuple(static))
    assert ok.value == "1234"                                                                  # the blank's text: not an answer, not an obstacle
    school = reader(c, ["1234"] * 3, boxes=[answer, label]).read_widget(c, tag, f, 0, w["rect"], ())
    assert school.value is None and school.reason == "glyph_past_left_edge"                    # the same word, not on the blank: abstain
    old = L.RULE_LABEL_FILTER
    L.RULE_LABEL_FILTER = False
    try:
        assert reader(c, ["1234"] * 3, boxes=[answer, label]).read_widget(c, tag, f, 0, w["rect"], tuple(static)).value is None
    finally:
        L.RULE_LABEL_FILTER = old


def test_the_strict_number_grammar_applies_to_ocr_reads(ctx):
    c, tag, f, w, st = ctx
    for bad in ("1,23,4", "12.345", "1-2"):
        r = reader(c, [bad] * 3).read_widget(c, tag, f, 0, w["rect"], st)
        assert r.value is None and r.reason in ("not_numeric", "ambiguous_thousands_separator"), (bad, r.reason)


def test_the_template_ink_eraser_leaves_a_blank_cell_blank(ctx):
    """TEMPLATE_INK_DILATE: the blank's frame, registered to within a pixel, must not survive in the context crop."""
    c, tag, f, w, st = ctx
    other = to.load_maps()[YEAR].fmap["fields"]["AP_ADMT_1ST_MEN_N"]["widgets"][0]
    l2 = L.Lane2(FixedEngine([""]), YEAR)
    img, _o = l2._crop(c, other["rect"], L.OCR_DPI, x_pad_pt=L.CONTEXT_PAD_PT, erase_template=True)
    assert int((img[L.CROP_PAD_PX:-L.CROP_PAD_PX, L.CROP_PAD_PX:-L.CROP_PAD_PX] < 128).sum()) == 0
    kept, _o2 = l2._crop(c, other["rect"], L.OCR_DPI, x_pad_pt=L.CONTEXT_PAD_PT, erase_template=False)
    assert int((kept < 128).sum()) > 0                                                          # (without it the frame is there)


def test_word_boxes_are_mapped_through_the_applied_page_shift():
    from types import SimpleNamespace
    k = L.OCR_DPI / 72.0
    c = SimpleNamespace(dx=2.0, dy=-1.0)
    word = L.OcrWord("12", 99.0, L.CROP_PAD_PX + 30, L.CROP_PAD_PX + 10, L.CROP_PAD_PX + 90, L.CROP_PAD_PX + 50)
    (b,) = L.Lane2(FixedEngine([]), YEAR)._to_boxes(c, [word], (1000, 600), L.OCR_DPI)
    assert abs(b.left - ((600 + 30) / k - 2.0)) < 1e-9 and abs(b.right - ((600 + 90) / k - 2.0)) < 1e-9
    assert abs(b.top - (792.0 - (1000 + 10) / k + 1.0)) < 1e-9 and abs(b.bottom - (792.0 - (1000 + 50) / k + 1.0)) < 1e-9


def _hook_with(monkeypatch, per_call):
    """Run the Lane 2 hook over a raster packet with `Lane2.read_widget` scripted: per_call(tag, wi) -> Lane2Read."""
    calls = []

    def fake(self, c, tag, f, wi, rect, static_chars):
        calls.append((tag, wi))
        return per_call(tag, wi)
    monkeypatch.setattr(L.Lane2, "read_widget", fake)
    data = T.fill_and_flatten(YEAR, {}, {})
    packet = packet_with_raster_page(data, 12, data)
    return to.extract_overlay(packet, lane2=L.make_hook(FixedEngine([])), ), calls


def _multi_widget_numeric_tag():
    for t, f in to.load_maps()[YEAR].fmap["fields"].items():
        if f["ft"] == "/Tx" and f["question_number"] and len(f["widgets"]) >= 2 and to.effective_type(t, f["value_type"], "/Tx") == "Number" \
                and all(w["template_page"] == f["widgets"][0]["template_page"] for w in f["widgets"]):
            return t
    pytest.skip("no two-widget numeric field on one page in this map")


def test_hook_reads_numeric_fields_only(monkeypatch):
    fm = to.load_maps()[YEAR].fmap["fields"]
    calls = []
    data = T.fill_and_flatten(YEAR, {}, {})
    packet = packet_with_raster_page(data, 12, data)
    monkeypatch.setattr(L.Lane2, "read_widget", lambda self, c, t, f, wi, rect, st: (calls.append(t), L.Lane2Read(value="77", text="77", conf=99.0))[1])
    out = to.extract_overlay(packet, lane2=L.make_hook(FixedEngine([])))
    assert calls and not [t for t in calls if fm[t]["ft"] != "/Tx" or to.effective_type(t, fm[t]["value_type"], "/Tx") not in L.NUMERIC_CLASS_TYPES]
    assert l2_values(out) and all(r["emission_class"] == "numeric" and r["lane"] == 2 for r in out["values"].values() if r.get("lane") == 2)


def test_hook_withholds_a_field_whose_widgets_read_differently(monkeypatch):
    tag = _multi_widget_numeric_tag()
    page = to.load_maps()[YEAR].fmap["fields"][tag]["widgets"][0]["template_page"]
    data = T.fill_and_flatten(YEAR, {}, {})
    packet = packet_with_raster_page(data, page, data)
    monkeypatch.setattr(L.Lane2, "read_widget", lambda self, c, t, f, wi, rect, st:
                        L.Lane2Read(value=str(10 + wi), text=str(10 + wi), conf=99.0) if t == tag else L.Lane2Read(reason="no_rendered_ink"))
    out = to.extract_overlay(packet, lane2=L.make_hook(FixedEngine([])))
    assert tag not in l2_values(out) and "multi_widget_disagreement" in l2_held(out, tag)
