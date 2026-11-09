"""Tests for tools/tier2_extractor/template_overlay.py (PRD 038 M1).

Fixtures are synthesised from the committed blank templates: fill the AcroForm
with pypdf, then flatten widget appearances into page content (what Acrobat's
"flatten" does), so the text layer holds the values and no AcroForm remains.
Nothing school-specific is needed. Tests against real school PDFs are opt-in:
set CDS_M1_PDF_DIR to a directory holding the review PDFs (see
test_real_pdfs below) and they run; otherwise they skip.
"""

from __future__ import annotations

import io
import logging
import os
import sys
from pathlib import Path

import numpy as np
import pypdf
import pypdfium2 as pdfium
import pytest
from pypdf.generic import ArrayObject, DecodedStreamObject, DictionaryObject, NameObject, StreamObject

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_field_map as bfm  # noqa: E402
import template_overlay as to  # noqa: E402

logging.getLogger("pypdf").setLevel(logging.ERROR)

FILL_TEXT = {"AP_RECD_1ST_MEN_N": "1234", "AP_RECD_1ST_WMN_N": "2345", "CDS_NAME": "Test College"}
FILL_BUTTONS = {"ROTC_ARMY": "/C", "HOUS_INTL": "/X"}


# --------------------------------------------------------------------------
# fixture builders
# --------------------------------------------------------------------------

def _tag(annot) -> str:
    parts, node = [], annot
    while node is not None:
        if node.get("/T") is not None:
            parts.insert(0, str(node["/T"]))
        node = node["/Parent"].get_object() if node.get("/Parent") is not None else None
    return ".".join(parts)


def fill_and_flatten(year: str, text: dict[str, str], buttons: dict[str, str]) -> bytes:
    """Fill a blank template, then bake the widget appearances into page content."""
    old_limit = sys.getrecursionlimit()
    sys.setrecursionlimit(20000)           # the 2024-25 template nests deeply enough to trip pypdf's cloner
    try:
        w = pypdf.PdfWriter(clone_from=pypdf.PdfReader(str(bfm.template_path_for(year))))
    finally:
        sys.setrecursionlimit(old_limit)
    for page in w.pages:
        w.update_page_form_field_values(page, text, auto_regenerate=False)

    def raw_stream(data: bytes):
        st = DecodedStreamObject()
        st.set_data(data)
        return w._add_object(st)

    for page in w.pages:
        xobjs, n, content = DictionaryObject(), 0, b""
        for ref in list(page.get("/Annots") or []):
            a = ref.get_object()
            if a.get("/Subtype") != "/Widget" or a.get("/AP") is None or "/N" not in a["/AP"]:
                continue
            normal = a["/AP"]["/N"].get_object()
            if not isinstance(normal, StreamObject):          # button: pick the on-state stream
                want = buttons.get(_tag(a))
                normal = normal[want].get_object() if want and want in normal else None
            if normal is None:
                continue
            bbox = [float(v) for v in normal.get("/BBox", [0, 0, 1, 1])]
            x0, y0, x1, y1 = (float(v) for v in a["/Rect"])
            x0, x1, y0, y1 = min(x0, x1), max(x0, x1), min(y0, y1), max(y0, y1)
            sx, sy = (x1 - x0) / ((bbox[2] - bbox[0]) or 1), (y1 - y0) / ((bbox[3] - bbox[1]) or 1)
            name = f"/FmFx{n}"
            n += 1
            xobjs[NameObject(name)] = normal.indirect_reference or w._add_object(normal)
            content += f"q {sx:.5f} 0 0 {sy:.5f} {x0 - bbox[0] * sx:.4f} {y0 - bbox[1] * sy:.4f} cm {name} Do Q\n".encode()
        if n:
            res = page["/Resources"]
            xo = res.get("/XObject")
            xo = xo.get_object() if xo is not None else DictionaryObject()
            xo.update(xobjs)
            res[NameObject("/XObject")] = xo
            cur = page.raw_get("/Contents")
            cur_obj = cur.get_object()
            arr = ArrayObject([raw_stream(b"q\n")] + (list(cur_obj) if isinstance(cur_obj, ArrayObject) else [cur])
                              + [raw_stream(b"\nQ\n"), raw_stream(content)])
            page[NameObject("/Contents")] = arr
        if "/Annots" in page:
            del page["/Annots"]
    del w._root_object["/AcroForm"]
    buf = io.BytesIO()
    w.write(buf)
    return buf.getvalue()


@pytest.fixture(scope="module")
def flat_2526() -> bytes:
    return fill_and_flatten("2025-26", FILL_TEXT, FILL_BUTTONS)


@pytest.fixture(scope="module")
def flat_2425() -> bytes:
    return fill_and_flatten("2024-25", FILL_TEXT, FILL_BUTTONS)


def _values_by_tag(out: dict) -> dict[str, str]:
    return {r["pdf_tag"]: r["value"] for r in out["values"].values() if "pdf_tag" in r}


# --------------------------------------------------------------------------
# fixture sanity
# --------------------------------------------------------------------------

def test_fixture_is_flat_with_values_in_text_layer(flat_2526):
    assert not pypdf.PdfReader(io.BytesIO(flat_2526)).get_fields()
    doc = pdfium.PdfDocument(flat_2526)
    text = "".join(doc[i].get_textpage().get_text_range() for i in range(len(doc)))
    assert "1234" in text and "2345" in text and "Test College" in text


# --------------------------------------------------------------------------
# Stage 1
# --------------------------------------------------------------------------

def test_select_year_rules():
    sel = to.select_year
    assert sel({"2024-25": 47, "2025-26": 50}, None)[:3] == (to.STATUS_MATCHED, "2025-26", None)
    # lead of 2 needs detected_year agreement
    assert sel({"2024-25": 48, "2025-26": 50}, None)[0] == to.STATUS_AMBIGUOUS
    assert sel({"2024-25": 48, "2025-26": 50}, "2024-25")[0] == to.STATUS_AMBIGUOUS
    assert sel({"2024-25": 48, "2025-26": 50}, "2025-26")[:2] == (to.STATUS_MATCHED, "2025-26")
    # a tie is always ambiguous, even with a detected_year
    assert sel({"2024-25": 50, "2025-26": 50}, "2025-26")[0] == to.STATUS_AMBIGUOUS
    # gate
    assert sel({"2024-25": 29, "2025-26": 20}, "2024-25")[0] == to.STATUS_NOT_TEMPLATE
    assert sel({"2024-25": 30, "2025-26": 10}, None)[:2] == (to.STATUS_MATCHED, "2024-25")
    assert sel({"2023-24": 40, "2024-25": 40, "2025-26": 31}, "2024-25")[0] == to.STATUS_AMBIGUOUS


def test_monotonic_assignment_handles_dropped_and_inserted_pages():
    s = np.zeros((6, 6))
    for q, p in [(0, 0), (1, 1), (2, 3), (3, 4), (4, 5)]:   # template page 2 dropped
        s[q, p] = 0.95
    s[5, 0] = 0.99                                            # an inserted page that looks like page 0
    assert to._monotonic_assign(s) == {0: 0, 1: 1, 2: 3, 3: 4, 4: 5}


def test_stage1_matches_flattened_template(flat_2526):
    res = to.match_template(flat_2526, detected_year="2025-26")
    assert res.status == to.STATUS_MATCHED and res.year == "2025-26"
    assert len(res.page_map) == 50 and res.offsets == {0: 50}
    assert res.pages_matched["2025-26"] == 50 and res.lead >= 3
    assert all(a["dx"] == 0 and a["dy"] == 0 for a in res.alignment.values())
    assert not res.rejected_pages


def test_stage1_wrong_year_is_never_chosen(flat_2425):
    for detected in ("2024-25", "2025-26", None):
        res = to.match_template(flat_2425, detected_year=detected, align=False)
        assert res.year != "2025-26", (detected, res.pages_matched)
    res = to.match_template(flat_2425, detected_year="2024-25", align=False)
    assert res.status == to.STATUS_MATCHED and res.year == "2024-25"


def test_stage1_dropped_and_inserted_pages(flat_2526):
    reader = pypdf.PdfReader(io.BytesIO(flat_2526))
    w = pypdf.PdfWriter()
    for i, page in enumerate(reader.pages):
        if i in (5, 6):                       # dropped
            continue
        w.add_page(page)
        if i == 10:                           # inserted non-template page
            w.add_blank_page(612, 792)
    buf = io.BytesIO()
    w.write(buf)
    res = to.match_template(buf.getvalue(), detected_year="2025-26", align=False)
    assert res.status == to.STATUS_MATCHED
    assert len(res.page_map) == 48
    pairs = sorted(res.page_map.items())
    assert [p for _, p in pairs] == sorted(p for _, p in pairs)            # monotonic
    assert set(res.page_map.values()) == set(range(50)) - {5, 6}
    assert res.offsets.get(0) and res.offsets.get(-2)                         # before the drop / after it
    out = to.extract_overlay(buf.getvalue(), detected_year="2025-26")
    assert _values_by_tag(out)["AP_RECD_1ST_MEN_N"] == "1234"


def test_stage1_rejects_non_template_pdfs():
    # 50 blank pages: no ink to match
    w = pypdf.PdfWriter()
    for _ in range(50):
        w.add_blank_page(612, 792)
    buf = io.BytesIO()
    w.write(buf)
    res = to.match_template(buf.getvalue(), detected_year="2025-26", align=False)
    assert res.status == to.STATUS_NOT_TEMPLATE and not res.page_map
    # another official template (2021-22) is not one of the mapped years
    other = bfm.TEMPLATE_DIR / "cds_2021-22_template.pdf"
    res = to.match_template(other.read_bytes(), detected_year="2025-26", align=False)
    assert res.status == to.STATUS_NOT_TEMPLATE
    # outside the page-count window
    w = pypdf.PdfWriter()
    for _ in range(5):
        w.add_blank_page(612, 792)
    buf = io.BytesIO()
    w.write(buf)
    assert to.match_template(buf.getvalue(), align=False).reason == "page_count_out_of_range"


# --------------------------------------------------------------------------
# Lane 1 + Lane 3 end to end
# --------------------------------------------------------------------------

def test_extract_overlay_reads_text_and_checkboxes(flat_2526):
    out = to.extract_overlay(flat_2526, detected_year="2025-26", source_name="fixture.pdf")
    vals = _values_by_tag(out)
    assert out["producer"] == to.PRODUCER and out["schema_version"] == "2025-26"
    assert vals["AP_RECD_1ST_MEN_N"] == "1234" and vals["AP_RECD_1ST_WMN_N"] == "2345"
    assert vals["CDS_NAME"] == "Test College"
    assert vals["ROTC_ARMY"] == "/C" and vals["HOUS_INTL"] == "/X"
    assert out["values"]["F.301"]["value_decoded"]          # decoded like Tier 2
    notes = out["notes"]
    assert notes["lane_counts"]["checkbox"] == 2           # no other box is reported checked
    assert notes["template_year"] == "2025-26" and notes["field_map_version"] == 1
    assert notes["matched_template_pages"] == 50 and not notes["rejected_fields"]
    assert notes["producer_version"] == to.PRODUCER_VERSION and notes["skipped_null_question_number"] == 2
    assert not notes["unreadable_pages"] and not notes["ambiguous_radios"]
    # Tier 2 shape: same top-level keys and per-value keys
    for key in ("producer", "producer_version", "schema_version", "source_pdf", "extracted_at", "stats", "values", "unmapped_fields"):
        assert key in out
    rec = out["values"]["C.101"]
    for key in ("value", "pdf_tag", "word_tag", "question", "section", "subsection", "value_type"):
        assert key in rec


def test_blank_template_page_emits_no_checkbox():
    blank = fill_and_flatten("2025-26", {}, {})
    out = to.extract_overlay(blank, detected_year="2025-26")
    assert out["notes"]["lane_counts"].get("checkbox", 0) == 0


def test_garbled_text_layer_marks_page_unreadable(flat_2526, monkeypatch):
    real = to._page_chars

    def garble(page):
        return [to.PageChar(chr(0x10 + int(c.ch)) if c.ch.isdigit() else c.ch, c.cx, c.cy) for c in real(page)]

    monkeypatch.setattr(to, "_page_chars", garble)
    # static-text subtraction uses template chars; garble those too, as a garbled print would
    to._template_chars.cache_clear()
    out = to.extract_overlay(flat_2526, detected_year="2025-26")
    to._template_chars.cache_clear()
    notes = out["notes"]
    assert 12 in notes["unreadable_pages"]
    assert "AP_RECD_1ST_MEN_N" not in _values_by_tag(out)          # nothing cleaned out of the garbled page
    assert all(r.get("lane") != "text" for q, r in out["values"].items() if r.get("pdf_tag") and q.startswith("C.1"))
    assert notes["lane_counts"].get("checkbox") == 2                # Lane 3 does not read the text layer
    assert 12 in notes["pages_needing_ocr"]


# --------------------------------------------------------------------------
# units
# --------------------------------------------------------------------------

def _chars(s, x0=10.0, y=10.0, step=5.0):
    return [to.PageChar(c, x0 + i * step, y) for i, c in enumerate(s)]


def test_read_widget_text_centre_in_rect_and_no_padding():
    chars = _chars("(123)")                       # centres at 10, 15, 20, 25, 30
    text, bad = to.read_widget_text(chars, [12, 5, 28, 15])
    assert (text, bad) == ("123", False)           # parens centred outside the rect are not pulled in
    assert to.read_widget_text(chars, [12, 5, 28, 15], pad=3.0)[0] == "(123)"


def test_read_widget_text_subtracts_static_label_by_position():
    chars = _chars("$ 77")
    static = (to.PageChar("$", 10.0, 10.0),)
    assert to.read_widget_text(chars, [5, 5, 40, 15], static, [5, 5, 40, 15])[0] == "77"
    # same glyph at another position is a value, not a label
    assert to.read_widget_text(_chars("$", x0=30), [5, 5, 40, 15], static, [5, 5, 40, 15])[0] == "$"


def test_read_widget_text_flags_control_and_private_use_but_ignores_markers():
    assert to.read_widget_text(_chars("1\x122"), [5, 5, 40, 15])[1] is True
    assert to.read_widget_text(_chars("12"), [5, 5, 40, 15])[1] is True
    assert to.read_widget_text(_chars("1�2"), [5, 5, 40, 15])[1] is True
    text, bad = to.read_widget_text(_chars("1￾2­3"), [5, 5, 40, 15])   # pdfium marker, soft hyphen
    assert (text, bad) == ("123", False)


def test_normalise_text_value():
    n = to.normalise_text_value
    assert n("$1,234", "Nearest $1") == ("1234", None)
    assert n("45%", "Nearest 1%") == ("45", None)
    assert n("145%", "Nearest 1%") == (None, "percent_out_of_range")
    assert n("12.5", "Whole Number or Round to Nearest Tenth") == ("12.5", None)
    assert n("twelve", "Number") == (None, "not_numeric")
    assert n("(219) 464-5000", "Numbers") == ("(219) 464-5000", None)
    assert n("46383-6493", "Numbers") == ("46383-6493", None)
    assert n("abc", "Numbers") == (None, "not_digits")
    assert n("https://x.edu", "URL") == ("https://x.edu", None)
    assert n("13", "MM") == (None, "bad_month") and n("12", "MM") == ("12", None)


def test_choice_to_export():
    opt = [[" ", " "], ["C", "per credit"], ["S", "per semester hour"], ["Z", "per semester"]]
    f = to.choice_to_export
    assert f("per credit", opt) == "C" and f("percredit", opt) == "C"     # lost word gap
    assert f("per semester h", opt) == "S"                                # clipped, unique prefix
    assert f("per semester", opt) == "Z"                                  # exact beats prefix
    assert f("per", opt) is None and f("credits", opt) is None
    assert f("08", [[" ", " "], ["8", "8"]]) == "8"                       # editable MM/DD combos


def test_btn_decision():
    f = to._is_btn_checked
    assert f([0.4], 0.05, 0.03) == (0, None) and f([0.01], 0.05, 0.03) == (None, None)
    assert f([0.0, 0.4, 0.01], 0.05, 0.03) == (1, None)
    assert f([0.4, 0.39], 0.05, 0.03) == (None, "ambiguous_radio")
    assert f([None, None], 0.05, 0.03) == (None, None)


def test_identities():
    check = to.check_identities
    tags = set(bfm.load_field_map("2025-26")["fields"])
    ok = {"EN_FRSH_FT_MEN_N": "10", "EN_OTH_1ST_FT_MEN_N": "5", "EN_DEG_FT_MEN_N": "7", "EN_TOT_DEG_FT_MEN_N": "22"}
    assert check(ok, tags) == []
    bad = dict(ok, EN_TOT_DEG_FT_MEN_N="23")
    assert check(bad, tags)[0]["identity"] == "B1_total_degree_seeking"
    assert check({"AP_RECD_1ST_N": "100", "AP_ADMT_1ST_N": "50", "EN_TOT_1ST_N": "20"}, tags) == []
    assert check({"AP_RECD_1ST_N": "10", "AP_ADMT_1ST_N": "50", "EN_TOT_1ST_N": "20"}, tags)[0]["identity"].startswith("C1")
    assert check({"SAT1_COMP_25TH_P": "1100", "SAT1_COMP_50TH_P": "1200", "SAT1_COMP_75TH_P": "1300"}, tags) == []
    assert check({"SAT1_COMP_25TH_P": "1300", "SAT1_COMP_50TH_P": "1200"}, tags)[0]["identity"] == "C9_percentile_order"
    assert check({"ACT_COMP_25TH_P": "20", "ACT_COMP_75TH_P": "40"}, tags)[0]["identity"] == "C9_score_range"


def test_text_identity_failure_is_recorded_not_rejected(monkeypatch):
    flat = fill_and_flatten("2025-26", {"AP_RECD_1ST_N": "10", "AP_ADMT_1ST_N": "50", "EN_TOT_1ST_N": "20"}, {})
    out = to.extract_overlay(flat, detected_year="2025-26")
    notes = out["notes"]
    assert [f["identity"] for f in notes["identity_failures"]] == ["C1_applied_admitted_enrolled"]
    assert notes["identity_failures"][0]["action"] == "recorded"
    assert _values_by_tag(out)["AP_RECD_1ST_N"] == "10"           # published numbers are kept


def test_cli_writes_json(flat_2526, tmp_path):
    pdf = tmp_path / "flat.pdf"
    pdf.write_bytes(flat_2526)
    out = tmp_path / "out.json"
    assert to.main([str(pdf), "--detected-year", "2025-26", "--output", str(out)]) == 0
    import json
    assert json.loads(out.read_text())["values"]["C.101"]["value"] == "1234"


# --------------------------------------------------------------------------
# opt-in: real school PDFs
# --------------------------------------------------------------------------

REAL = os.environ.get("CDS_M1_PDF_DIR")


@pytest.mark.skipif(not REAL, reason="set CDS_M1_PDF_DIR to the review PDF directory")
def test_real_pdfs_valparaiso_and_miami():
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import eval_template_overlay as ev
    d = Path(REAL)
    fm = to.load_maps()["2025-26"].fmap
    cases = {
        "valpo": ("5969b8e69123cb66b2d8a8ca8d897fde8086d8743e0f282c7969080432492086.pdf",
                  "80475b8f8dcb177a4daa1316b505c12579b2b5a222922637d78b9d1e1e7a1784.pdf"),
        "miami": ("eaed9690fa58423535915724bf1ed474ce9b0ac8211a693e2ded86381b2c0f10.pdf",
                  "b61624de99fa2a6b7641fb9c0895ba6990f235ece605808160561ee20894e9ad.pdf"),
    }
    results = {}
    for name, (flat, fill) in cases.items():
        ov = to.extract_overlay((d / flat).read_bytes(), detected_year="2025-26")
        results[name] = ev.compare_with_tier2(ov, ev.tier2_truth(d / fill, "2025-26"), fm)
    assert results["valpo"]["ok"] >= 614 and results["valpo"]["by_type"]["Btn"] == [139, 139]
    assert results["valpo"]["extras"] == []
    assert results["miami"]["by_type"]["Btn"] == [152, 152] and results["miami"]["extras"] == []
