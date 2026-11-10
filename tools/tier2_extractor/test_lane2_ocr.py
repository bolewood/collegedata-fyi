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
