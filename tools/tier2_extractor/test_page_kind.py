"""PRD 038 A14: Lane 2 records the page kind (vector / raster) and the image-coverage fraction as metadata only."""

import sys
from pathlib import Path

import pypdfium2 as pdfium

sys.path.insert(0, str(Path(__file__).resolve().parent))
import lane2_ocr as L  # noqa: E402
import template_overlay as to  # noqa: E402
import test_lane2_ocr as X  # noqa: E402
import test_template_overlay as T  # noqa: E402
from test_lane2_a12 import YEAR, _b1_tags, _pages_of_calls  # noqa: E402
from test_lane2_ocr import flat_numbers  # noqa: E402,F401


def test_producer_version_was_bumped_for_the_new_metadata():
    assert to.PRODUCER_VERSION == "0.7.0"


def test_image_coverage_separates_vector_and_raster_pages():
    data = T.fill_and_flatten(YEAR, {}, {})
    vector = pdfium.PdfDocument(data)[12]
    assert to.page_image_coverage(vector) == 0.0 and to.page_kind_of(0.0) == "vector"
    raster = pdfium.PdfDocument(X.rasterise_page(data, 12))[0]
    cov = to.page_image_coverage(raster)
    assert cov >= 0.9 and to.page_kind_of(cov) == "raster"
    assert to.page_kind_of(0.49) == "vector" and to.page_kind_of(0.5) == "raster"


def test_lane_2_values_record_page_kind_and_do_not_change_what_is_emitted(monkeypatch):
    f2, w2 = X.widget("AP_RECD_1ST_WMN_N")
    q = w2["template_page"]
    data = T.add_text(T.fill_and_flatten(YEAR, {}, {}), q, w2["rect"][0] + 5, w2["rect"][1] + 5, "2345", render_mode=3)   # a vector page, invisible text
    out, _calls = _pages_of_calls(monkeypatch, data)
    rec = next(r for r in out["values"].values() if r.get("pdf_tag") == "AP_RECD_1ST_WMN_N")
    assert rec["lane"] == 2 and rec["value"] == "999" and rec["emission_class"] == "ocr_numeric"
    assert rec["page_kind"] == "vector" and rec["image_coverage"] == 0.0
    packet = X.packet_with_raster_page(data, q, data)
    out2, _ = _pages_of_calls(monkeypatch, packet)
    rec2 = [r for r in out2["values"].values() if r.get("pdf_tag") == "AP_RECD_1ST_WMN_N"]
    assert rec2 and rec2[0]["page_kind"] == "raster" and rec2[0]["image_coverage"] >= 0.9 and rec2[0]["value"] == "999"


def test_a_derived_total_records_the_page_kinds_of_its_lane_2_inputs():
    ft, pt, tot, tot_qn = _b1_tags()
    data = T.fill_and_flatten(YEAR, {}, {})

    def fake(env):
        env.record(ft, "100", 2, "Number", 12, to.CLASS_OCR_NUMERIC, {"page_kind": "vector", "image_coverage": 0.0})
        env.record(pt, "20", 2, "Number", 13, to.CLASS_OCR_NUMERIC, {"page_kind": "raster", "image_coverage": 0.98})
    out = to.extract_overlay(data, lane2=fake)
    rec = out["values"][tot_qn]
    assert rec["value"] == "120" and rec["emission_class"] == "ocr_numeric"
    assert rec["input_page_kinds"] == ["raster", "vector"]

    def fake_one(env):
        env.record(pt, "20", 2, "Number", 13, to.CLASS_OCR_NUMERIC, {"page_kind": "vector", "image_coverage": 0.0})
    out2 = to.extract_overlay(T.fill_and_flatten(YEAR, {ft: "100"}, {}), lane2=fake_one)
    assert out2["values"][tot_qn]["input_page_kinds"] == ["vector"]
