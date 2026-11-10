"""Tests for tools/tier2_extractor/template_overlay.py (PRD 038 M1).

Fixtures are synthesised from the committed blank templates: fill the AcroForm
with pypdf, then bake the widget appearances into page content (what Acrobat's
"flatten" does), so the text layer holds the values and no AcroForm remains.
Every failure the two independent reviews found has a fixture here (partial-page
shift, reflowed Yes/No line, nonzero box origin, /Rotate, scale, invisible text,
white text, duplicated pages, swapped pages, mixed-year and wrong-year-leads
packets, late unreadable glyph, clipped dropdown, malformed numbers).
Nothing school-specific is needed. Tests against real school PDFs are opt-in:
set CDS_M1_PDF_DIR to a directory holding the review PDFs.
"""

from __future__ import annotations

import inspect
import io
import json
import logging
import math
import os
import sys
from pathlib import Path

import numpy as np
import pypdf
import pypdfium2 as pdfium
import pytest
from pypdf.generic import (ArrayObject, DecodedStreamObject, DictionaryObject, NameObject, NumberObject,
                           RectangleObject, StreamObject)

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_field_map as bfm  # noqa: E402
import template_overlay as to  # noqa: E402

logging.getLogger("pypdf").setLevel(logging.ERROR)

FILL_TEXT = {"AP_RECD_1ST_MEN_N": "1234", "AP_RECD_1ST_WMN_N": "2345", "CDS_NAME": "Test College"}
FILL_BUTTONS = {"ROTC_ARMY": "/C", "HOUS_INTL": "/X", "LIFE_CAMPUS": "/Y", "AD_TFER": "/Y"}
# unchecked-looking boxes that carry a little stray ink: (tag -> share of the 35% core that is dark)
SPECKS = {"HOUS_DISABLED": 0.02, "HOUS_COOP": 0.08, "HOUS_SINGLE": 0.30}


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


def _writer_from(path_or_bytes) -> pypdf.PdfWriter:
    src = io.BytesIO(path_or_bytes) if isinstance(path_or_bytes, (bytes, bytearray)) else str(path_or_bytes)
    old = sys.getrecursionlimit()
    sys.setrecursionlimit(20000)           # the 2024-25 template nests deeply enough to trip pypdf's cloner
    try:
        return pypdf.PdfWriter(clone_from=pypdf.PdfReader(src))
    finally:
        sys.setrecursionlimit(old)


def _raw(w: pypdf.PdfWriter, data: bytes):
    st = DecodedStreamObject()
    st.set_data(data)
    return w._add_object(st)


def _contents_parts(page) -> list:
    cur = page.raw_get("/Contents")
    obj = cur.get_object()
    return list(obj) if isinstance(obj, ArrayObject) else [cur]


def _write(w: pypdf.PdfWriter) -> bytes:
    buf = io.BytesIO()
    w.write(buf)
    return buf.getvalue()


def fill_and_flatten(year: str, text: dict[str, str], buttons: dict[str, str], specks: dict[str, float] | None = None) -> bytes:
    """Fill a blank template, then bake the widget appearances into page content.

    Unchecked boxes are drawn with their /Off appearance (the bevelled box a
    PDFium-flattened print shows) and `specks` adds stray ink to chosen boxes, so
    unchecked widgets do not all score exactly 0.
    """
    w = _writer_from(bfm.template_path_for(year))
    for page in w.pages:
        w.update_page_form_field_values(page, text, auto_regenerate=False)
    fmap = bfm.load_field_map(year)["fields"]
    for page in w.pages:
        xobjs, n, content = DictionaryObject(), 0, b""
        for ref in list(page.get("/Annots") or []):
            a = ref.get_object()
            if a.get("/Subtype") != "/Widget" or a.get("/AP") is None or "/N" not in a["/AP"]:
                continue
            tag = _tag(a)
            normal = a["/AP"]["/N"].get_object()
            if not isinstance(normal, StreamObject):          # button: on-state stream, else /Off
                want = buttons.get(tag)
                normal = normal[want].get_object() if want and want in normal else (normal["/Off"].get_object() if "/Off" in normal else None)
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
            if not isinstance(a["/AP"]["/N"].get_object(), StreamObject) and buttons.get(tag) in a["/AP"]["/N"].get_object():
                # a clearly drawn check mark, as a school's own print shows (the template's own mark is tiny)
                content += (f"q 0 G 1.1 w {x0 + 0.2 * (x1 - x0):.3f} {y0 + 0.5 * (y1 - y0):.3f} m "
                            f"{x0 + 0.42 * (x1 - x0):.3f} {y0 + 0.2 * (y1 - y0):.3f} l "
                            f"{x0 + 0.85 * (x1 - x0):.3f} {y0 + 0.85 * (y1 - y0):.3f} l S Q\n").encode()
            if specks and tag in specks:
                cw, ch = (x1 - x0) * 0.3, (y1 - y0) * 0.3
                side = math.sqrt(specks[tag] * cw * ch)
                cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
                content += f"q 0 g {cx - side / 2:.3f} {cy - side / 2:.3f} {side:.3f} {side:.3f} re f Q\n".encode()
        if n:
            res = page["/Resources"]
            xo = res.get("/XObject")
            xo = xo.get_object() if xo is not None else DictionaryObject()
            xo.update(xobjs)
            res[NameObject("/XObject")] = xo
            page[NameObject("/Contents")] = ArrayObject(
                [_raw(w, b"q\n")] + _contents_parts(page) + [_raw(w, b"\nQ\n"), _raw(w, content)])
        if "/Annots" in page:
            del page["/Annots"]
    del w._root_object["/AcroForm"]
    return _write(w)


def region_shift(data: bytes, page_index: int, region: tuple[float, float, float, float], dx: float, dy: float) -> bytes:
    """Redraw one page with everything inside `region` (x, y, w, h) moved by (dx, dy)."""
    w = _writer_from(data)
    page = w.pages[page_index]
    x, y, rw, rh = region
    orig = _contents_parts(page)
    parts = ([_raw(w, f"q 0 0 612 792 re {x} {y} {rw} {rh} re W* n\n".encode())] + orig + [_raw(w, b"\nQ\n")]
             + [_raw(w, f"q {x} {y} {rw} {rh} re W n 1 0 0 1 {dx} {dy} cm\n".encode())] + orig + [_raw(w, b"\nQ\n")])
    page[NameObject("/Contents")] = ArrayObject(parts)
    return _write(w)


def set_geometry(data: bytes, box: list[float], rotate: int, cm: str) -> bytes:
    """Visually identical page with another box origin / size / rotation (content re-mapped by `cm`)."""
    w = _writer_from(data)
    for page in w.pages:
        page.mediabox = RectangleObject(box)
        page.cropbox = RectangleObject(box)
        if rotate:
            page[NameObject("/Rotate")] = NumberObject(rotate)
        page[NameObject("/Contents")] = ArrayObject(
            [_raw(w, f"q {cm} cm\n".encode())] + _contents_parts(page) + [_raw(w, b"\nQ\n")])
    return _write(w)


def add_text(data: bytes, page_index: int, x: float, y: float, text: str, *, render_mode: int = 0, white: bool = False) -> bytes:
    w = _writer_from(data)
    page = w.pages[page_index]
    res = page["/Resources"]
    fonts = res.get("/Font")
    fonts = fonts.get_object() if fonts is not None else DictionaryObject()
    fonts[NameObject("/FxAdd")] = DictionaryObject({NameObject("/Type"): NameObject("/Font"), NameObject("/Subtype"): NameObject("/Type1"),
                                                    NameObject("/BaseFont"): NameObject("/Helvetica")})
    res[NameObject("/Font")] = fonts
    color = "1 g" if white else "0 g"
    page[NameObject("/Contents")] = ArrayObject(
        _contents_parts(page) + [_raw(w, f"\nq {color} BT {render_mode} Tr /FxAdd 10 Tf {x} {y} Td ({text}) Tj ET Q\n".encode())])
    return _write(w)


def assemble(sources: list[tuple[bytes, int]]) -> bytes:
    """A packet built from (document, page index) pairs, in order."""
    readers: dict[int, pypdf.PdfReader] = {}
    w = pypdf.PdfWriter()
    old = sys.getrecursionlimit()
    sys.setrecursionlimit(20000)
    try:
        for data, idx in sources:
            r = readers.setdefault(id(data), pypdf.PdfReader(io.BytesIO(data)))
            w.add_page(r.pages[idx])
    finally:
        sys.setrecursionlimit(old)
    return _write(w)


def _page_count(data: bytes) -> int:
    return len(pypdf.PdfReader(io.BytesIO(data)).pages)


@pytest.fixture(scope="module")
def flat_2526() -> bytes:
    return fill_and_flatten("2025-26", FILL_TEXT, FILL_BUTTONS, SPECKS)


@pytest.fixture(scope="module")
def flat_2425() -> bytes:
    return fill_and_flatten("2024-25", FILL_TEXT, FILL_BUTTONS, SPECKS)


@pytest.fixture(scope="module")
def base(flat_2526):
    return to.extract_overlay(flat_2526)


def _values_by_tag(out: dict) -> dict[str, str]:
    return {r["pdf_tag"]: r["value"] for r in out["values"].values() if "pdf_tag" in r}


def _held(out: dict, tag: str) -> list[str]:
    return [w["reason"] for w in out["notes"]["withheld"] if w["pdf_tag"] == tag]


# --------------------------------------------------------------------------
# fixture sanity and the happy path
# --------------------------------------------------------------------------

def test_fixture_is_flat_with_values_in_text_layer(flat_2526):
    assert not pypdf.PdfReader(io.BytesIO(flat_2526)).get_fields()
    doc = pdfium.PdfDocument(flat_2526)
    text = "".join(doc[i].get_textpage().get_text_range() for i in range(len(doc)))
    assert "1234" in text and "2345" in text and "Test College" in text


def test_extract_overlay_reads_text_and_checkboxes(base):
    vals = _values_by_tag(base)
    assert base["producer"] == to.PRODUCER and base["schema_version"] == "2025-26"
    assert vals["AP_RECD_1ST_MEN_N"] == "1234" and vals["AP_RECD_1ST_WMN_N"] == "2345" and vals["CDS_NAME"] == "Test College"
    assert vals["ROTC_ARMY"] == "/C" and vals["HOUS_INTL"] == "/X" and vals["LIFE_CAMPUS"] == "/Y" and vals["AD_TFER"] == "/Y"
    assert vals["HOUS_SINGLE"] == "/X"                       # clearly inked box (0.30) is checked
    assert base["values"]["F.301"]["value_decoded"]          # decoded like Tier 2
    notes = base["notes"]
    assert notes["template_year"] == "2025-26" and notes["field_map_version"] == 1
    assert notes["matched_template_pages"] == 50 and not notes["rejected_fields"]
    assert notes["producer_version"] == to.PRODUCER_VERSION and notes["skipped_null_question_number"] == 2
    assert not notes["unreadable_pages"] and not notes["invisible_text_pages"]
    for key in ("producer", "producer_version", "schema_version", "source_pdf", "extracted_at", "stats", "values", "unmapped_fields"):
        assert key in base
    rec = base["values"]["C.101"]
    for key in ("value", "pdf_tag", "word_tag", "question", "section", "subsection", "value_type", "effective_type"):
        assert key in rec
    assert rec["effective_type"] == "Number" and base["values"]["F.301"]["effective_type"] == "Button"


def test_unchecked_boxes_with_realistic_ink_are_not_emitted(base):
    vals = _values_by_tag(base)
    assert "HOUS_DISABLED" not in vals                       # 2% stray ink: below the threshold
    assert "HOUS_COOP" not in vals                           # 8% stray ink: abstain, do not guess
    assert "lone_checkbox_gray_band" in _held(base, "HOUS_COOP")
    assert "HOUS_DISABLED" not in {w["pdf_tag"] for w in base["notes"]["withheld"]}
    assert sum(1 for r in base["values"].values() if r.get("lane") == "checkbox") == 5   # 4 filled + HOUS_SINGLE


def test_lane3_threshold_is_exercised(flat_2526):
    """A lower threshold must change the outcome, so a threshold mutation cannot go unnoticed."""
    low = to.extract_overlay(flat_2526, lane3_threshold=0.001)
    assert "lone_checkbox_gray_band" in _held(low, "HOUS_DISABLED")          # 2% ink now counts as a (doubtful) check
    assert _values_by_tag(low).get("HOUS_DISABLED") is None                  # ... and still is never emitted
    assert not _held(to.extract_overlay(flat_2526), "HOUS_DISABLED")


# --------------------------------------------------------------------------
# Stage 1: year, pages, geometry
# --------------------------------------------------------------------------

def test_decide_year_rules():
    d = to.decide_year
    c = {"2023-24": 39, "2024-25": 47, "2025-26": 50}
    assert d(c, {"2025-26": 49}, None)[:3] == (to.STATUS_MATCHED, "2025-26", None)
    assert d(c, {"2025-26": 49}, "2025-26")[1] == "2025-26"
    assert d(c, {"2025-26": 49}, "2024-25")[:3][0] == to.STATUS_AMBIGUOUS              # detected_year can only veto
    assert d(c, {"2025-26": 49}, "2024-25")[2] == "detected_year_contradicts_header_year"
    assert d(c, {"2024-25": 46, "2025-26": 3}, None)[2] == "header_year_contradicts_raster_year"   # wrong year leads
    assert d(c, {"2024-25": 25, "2025-26": 24}, None)[2] == "mixed_year_packet"
    assert d(c, {"2024-25": 2}, None)[2] == "header_year_unverified"
    assert d({"2024-25": 50, "2025-26": 50}, {"2025-26": 40}, "2025-26")[2] == "tie_between_years"
    assert d({"2023-24": 50, "2024-25": 30}, {"2023-24": 40}, None)[0] == to.STATUS_UNSUPPORTED_YEAR
    assert d({"2024-25": 29, "2025-26": 20}, {"2024-25": 20}, "2024-25")[0] == to.STATUS_NOT_TEMPLATE
    # a lead of 1 is enough when the header agrees: the header, not the lead, decides
    assert d({"2024-25": 48, "2025-26": 47}, {"2024-25": 40}, None)[1] == "2024-25"


def test_monotonic_assignment_handles_dropped_and_inserted_pages_and_argmax_guard():
    s = np.zeros((6, 6))
    for q, p in [(0, 0), (1, 1), (2, 3), (3, 4), (4, 5)]:    # template page 2 dropped
        s[q, p] = 0.95
    s[5, 0] = 0.99                                            # an inserted page that looks like page 0
    assert to._monotonic_assign(s) == {0: 0, 1: 1, 2: 3, 3: 4, 4: 5}
    # near-duplicate template pages: q's best page is 1 (0.99); 3 cross-matches at 0.87 and is not used
    s = np.zeros((3, 4))
    s[0, 0], s[1, 1], s[1, 3], s[2, 2] = 0.95, 0.99, 0.87, 0.95
    assert to._monotonic_assign(s) == {0: 0, 1: 1, 2: 2}


def test_stage1_matches_flattened_template(flat_2526):
    res = to.match_template(flat_2526)
    assert res.status == to.STATUS_MATCHED and res.year == "2025-26" and res.header_votes == {"2025-26": 49}
    assert len(res.page_map) == 50 and res.offsets == {0: 50}
    assert all(a["dx"] == 0 and a["dy"] == 0 for a in res.alignment.values())
    assert not res.rejected_pages and not res.band_rejections


def test_detected_year_never_chooses_the_map(flat_2526, flat_2425):
    assert to.match_template(flat_2526, detected_year=None, align=False).year == "2025-26"
    res = to.match_template(flat_2526, detected_year="2024-25", align=False)
    assert res.status == to.STATUS_AMBIGUOUS and res.reason == "detected_year_contradicts_header_year"
    out = to.extract_overlay(flat_2526, detected_year="2024-25")
    assert out["values"] == {} and out["notes"]["held"]["reason"] == "detected_year_contradicts_header_year"
    res = to.match_template(flat_2425, detected_year=None, align=False)
    assert res.status == to.STATUS_MATCHED and res.year == "2024-25"


def test_2023_24_is_recognised_and_rejected():
    flat = fill_and_flatten("2023-24", {"AP_RECD_1ST_MEN_N": "1234"}, {})
    res = to.match_template(flat, align=False)
    assert res.status == to.STATUS_UNSUPPORTED_YEAR and res.reason == "year_2023-24_not_supported"
    assert to.extract_overlay(flat)["values"] == {}


def test_forced_year_is_not_reachable_from_the_entry_points():
    assert "force_year" not in inspect.signature(to.extract_overlay).parameters
    assert "force_year" not in inspect.signature(to.match_template).parameters
    assert not any("force" in a for a in to.main.__code__.co_names)
    assert hasattr(to, "_diagnostic_extract_forced_year") and "_diagnostic" in to._diagnostic_extract_forced_year.__name__


def test_wrong_year_leads_document_is_held(flat_2425, flat_2526):
    """Raster best year 2025-26 (four pages swapped in) but the header says 2024-25: nothing is emitted."""
    pages = [(flat_2526 if i in (2, 11, 12, 13) else flat_2425, i) for i in range(50)]
    hybrid = assemble(pages)
    res = to.match_template(hybrid, detected_year="2024-25", align=False)
    assert res.pages_matched["2025-26"] > res.pages_matched["2024-25"]
    assert res.status == to.STATUS_AMBIGUOUS and res.reason == "header_year_contradicts_raster_year"
    assert to.extract_overlay(hybrid, detected_year="2024-25")["values"] == {}


def test_mixed_year_packet_is_held(flat_2425, flat_2526):
    mixed = assemble([(flat_2425 if i < 25 else flat_2526, i) for i in range(50)])
    res = to.match_template(mixed, align=False)
    assert res.status == to.STATUS_AMBIGUOUS and res.reason in ("mixed_year_packet", "header_year_contradicts_raster_year", "tie_between_years")
    assert to.extract_overlay(mixed)["values"] == {}


def test_stage1_dropped_and_inserted_pages(flat_2526):
    w = pypdf.PdfWriter()
    reader = pypdf.PdfReader(io.BytesIO(flat_2526))
    for i, page in enumerate(reader.pages):
        if i in (5, 6):                       # dropped
            continue
        w.add_page(page)
        if i == 10:                           # inserted non-template page
            w.add_blank_page(612, 792)
    packet = _write(w)
    res = to.match_template(packet, align=False)
    assert res.status == to.STATUS_MATCHED and len(res.page_map) == 48
    assert [p for _, p in sorted(res.page_map.items())] == sorted(res.page_map.values())      # monotonic
    assert set(res.page_map.values()) == set(range(50)) - {5, 6}
    assert res.offsets.get(0) and res.offsets.get(-2)
    assert _values_by_tag(to.extract_overlay(packet))["AP_RECD_1ST_MEN_N"] == "1234"


def test_stage1_rejects_non_template_pdfs():
    w = pypdf.PdfWriter()
    for _ in range(50):
        w.add_blank_page(612, 792)
    res = to.match_template(_write(w), align=False)
    assert res.status == to.STATUS_NOT_TEMPLATE and not res.page_map
    other = bfm.TEMPLATE_DIR / "cds_2021-22_template.pdf"            # another official template, not a mapped year
    assert to.match_template(other.read_bytes(), align=False).status == to.STATUS_NOT_TEMPLATE
    w = pypdf.PdfWriter()
    for _ in range(5):
        w.add_blank_page(612, 792)
    assert to.match_template(_write(w), align=False).reason == "page_count_out_of_range"


def test_duplicated_page_with_conflicting_values_is_rejected(flat_2526):
    other = fill_and_flatten("2025-26", {"AP_RECD_1ST_MEN_N": "9999", "AP_RECD_1ST_WMN_N": "8888"}, {})
    packet = assemble([(flat_2526, i) for i in range(50)] + [(other, 12)])
    res = to.match_template(packet, align=False)
    assert res.rejected_template_pages == {12: "duplicate_page_conflict"}
    out = to.extract_overlay(packet)
    vals = _values_by_tag(out)
    assert out["notes"]["stage1"]["status"] == "matched"
    assert "AP_RECD_1ST_MEN_N" not in vals and "AP_RECD_1ST_WMN_N" not in vals          # neither 1234 nor 9999
    assert vals["CDS_NAME"] == "Test College"                                            # other pages are fine


def test_identical_duplicate_page_is_not_a_conflict(flat_2526):
    packet = assemble([(flat_2526, i) for i in range(50)] + [(flat_2526, 12)])
    res = to.match_template(packet, align=False)
    assert not res.rejected_template_pages
    assert _values_by_tag(to.extract_overlay(packet))["AP_RECD_1ST_MEN_N"] == "1234"


def test_swapped_pages_38_and_41_are_not_read_through_each_others_map():
    a, b = "BACH_FT_N", "ASSOC_ADMIN"                # one numeric field on template page 38 and one on page 41
    flat = fill_and_flatten("2025-26", {a: "111", b: "22.5"}, {})
    order = list(range(50))
    order[38], order[41] = order[41], order[38]
    swapped = assemble([(flat, i) for i in order])
    res = to.match_template(swapped, align=False)
    for q, p in res.page_map.items():
        assert order[q] == p or abs(order[q] - p) == 0, (q, p)       # a pair is only ever the page's own template page
    vals = _values_by_tag(to.extract_overlay(swapped))
    assert vals.get(a) in (None, "111") and vals.get(b) in (None, "22.5")
    assert not (vals.get(a) == "22.5" or vals.get(b) == "111")


@pytest.mark.parametrize("name,box,rotate,cm", [
    ("origin_offset", [18, 18, 630, 810], 0, "1 0 0 1 18 18"),
    ("rotate_90", [0, 0, 792, 612], 90, "0 1 -1 0 792 0"),
    ("rotate_180", [0, 0, 612, 792], 180, "-1 0 0 -1 612 792"),
    ("rotate_270", [0, 0, 792, 612], 270, "0 -1 1 0 0 612"),
    ("scaled_4_3", [0, 0, 816, 1056], 0, "1.33333 0 0 1.33333 0 0"),
])
def test_page_geometry_variants_read_the_same_values(flat_2526, base, name, box, rotate, cm):
    data = set_geometry(flat_2526, box, rotate, cm)
    out = to.extract_overlay(data)
    assert out["notes"]["stage1"]["status"] == "matched", name
    got, want = _values_by_tag(out), _values_by_tag(base)
    assert got["AP_RECD_1ST_MEN_N"] == "1234" and got["AP_RECD_1ST_WMN_N"] == "2345", name
    assert got == want, (name, {k: (want.get(k), got.get(k)) for k in set(want) | set(got) if want.get(k) != got.get(k)})


def test_geometry_transforms():
    g = to.PageGeom(36, 36, 648, 828, 0, 612, 792, 1.0, 1.0)
    assert to.user_to_display(g, 100, 200) == (64, 164)
    g90 = to.PageGeom(0, 0, 792, 612, 90, 612, 792, 1.0, 1.0)
    assert to.user_to_display(g90, 792, 0) == (0, 0)          # bottom-right of the user box is the display's bottom-left
    assert to.user_to_display(g90, 0, 612) == (612, 792)
    g270 = to.PageGeom(0, 0, 792, 612, 270, 612, 792, 1.0, 1.0)
    assert to.user_to_display(g270, 0, 0) == (612, 0)
    g180 = to.PageGeom(0, 0, 612, 792, 180, 612, 792, 1.0, 1.0)
    assert to.user_to_display(g180, 612, 792) == (0, 0)
    gs = to.PageGeom(0, 0, 816, 1056, 0, 816, 1056, 4 / 3, 4 / 3)
    x, y = to.display_to_template(gs, 400, 800, dx=3, dy=-6)    # the shift is in template points: scaled with the page
    assert (round(x, 6), round(y, 6)) == (round(400 / (4 / 3) - 3, 6), round(800 / (4 / 3) + 6, 6))


# --------------------------------------------------------------------------
# local alignment, bands
# --------------------------------------------------------------------------

def test_partial_page_shift_withholds_the_shifted_half_only(flat_2526):
    """Lower half of the housing/ROTC page printed 15 pt low (CSU Northridge): nothing there is read."""
    data = fill_and_flatten("2025-26", FILL_TEXT, {"HOUS_COOP": "/X", "LIFE_CAMPUS": "/Y", "ROTC_ARMY": "/C"}, None)
    data = region_shift(data, 27, (0, 0, 612, 396), 0, -15)
    out = to.extract_overlay(data)
    vals = _values_by_tag(out)
    assert vals.get("LIFE_CAMPUS") == "/Y"                              # the unshifted top half is still read
    assert vals.get("HOUS_COOP") is None and vals.get("ROTC_ARMY") is None
    flagged = set(out["notes"]["stage1"]["band_rejections"].get("27", []))
    assert {3, 4, 5} <= flagged and not ({0, 1} & flagged), flagged             # the shifted lower half, not the top
    assert not any(r.get("lane") == "checkbox" and r["pdf_tag"].startswith("HOUS_") for r in out["values"].values())
    assert out["notes"]["withheld_by_reason"].get("band_misaligned", 0) >= 1    # ghost marks in the shifted half abstain


def test_reflowed_yes_no_line_never_emits_the_wrong_radio(flat_2526):
    """The school typed into the static line and it reflowed by 8.5 pt (Eastern Michigan): 'Yes' is not read as 'No'."""
    data = fill_and_flatten("2025-26", FILL_TEXT, {"AD_TFER": "/Y", "AD_TFER_CRDT": "/Y"}, None)
    data = region_shift(data, 23, (150, 600, 400, 80), 8.5, 0)
    out = to.extract_overlay(data)
    vals = _values_by_tag(out)
    for tag in ("AD_TFER", "AD_TFER_CRDT"):
        assert vals.get(tag) in (None, "/Y"), (tag, vals.get(tag))


def test_row_period_alternatives_do_not_flag_an_aligned_table(base):
    """Rows of a table repeat at one pitch; an aligned page must not abstain because of that."""
    assert base["notes"]["withheld_by_reason"].get("local_misalignment", 0) == 0
    assert base["notes"]["withheld_by_reason"].get("band_misaligned", 0) == 0


def test_local_alignment_check_unit():
    ymaps = to.load_maps()["2025-26"]
    tdoc = to._template_doc("2025-26")
    page = tdoc[12]
    g = to.page_geometry(page)
    m = to._page_masks(page, g, page)
    rect = ymaps.fmap["fields"]["AP_RECD_1ST_MEN_N"]["widgets"][0]["rect"]
    eq = to._equivalent_shifts("2025-26", 12, ("t", 0), rect, m.t)
    assert to.local_alignment_check(m, rect, (0, 0), eq)[0] == "ok"
    shifted = to.PageMasks(np.roll(m.g, 9, axis=0), m.t)             # the target page is 9 px (pt) low
    assert to.local_alignment_check(shifted, rect, (0, 0), eq)[0] == "misaligned"
    assert to.local_alignment_check(shifted, rect, (0, 9), eq)[0] == "ok"      # an applied page shift that explains it


def test_page_alignment_estimator_bands():
    page = to._template_doc("2025-26")[27]
    g = to.page_geometry(page)
    m = to._page_masks(page, g, page)
    est = to.estimate_page_alignment(m)
    assert (est["dx"], est["dy"]) == (0, 0) and est["consistent"] and not est["flagged_bands"]
    half = m.g.copy()
    half[396:] = np.roll(m.g, 12, axis=0)[396:]                       # lower half low by 12
    est = to.estimate_page_alignment(to.PageMasks(half, m.t))
    assert est["flagged_bands"] and 5 in est["flagged_bands"] and 0 not in est["flagged_bands"]
    rigid = to.PageMasks(np.roll(m.g, 5, axis=0), m.t)                # a rigid 5 pt shift is applied, not rejected
    est = to.estimate_page_alignment(rigid)
    assert est["dy"] == -5 and est["consistent"]


# --------------------------------------------------------------------------
# Lane 1: invisible text, ink, unreadable pages, choices, numbers
# --------------------------------------------------------------------------

def test_invisible_text_layer_is_never_lane_1(flat_2526):
    data = add_text(flat_2526, 12, 452, 377.5, "9876", render_mode=3)         # invisible OCR text over a printed 1234
    out = to.extract_overlay(data)
    vals = _values_by_tag(out)
    assert "AP_RECD_1ST_MEN_N" not in vals                                   # never 98761234, never 1234 from this read
    assert "invisible_text" in _held(out, "AP_RECD_1ST_MEN_N")
    assert 12 in out["notes"]["invisible_text_pages"] and 12 in out["notes"]["pages_needing_ocr"]
    assert any(w["pdf_tag"] == "AP_RECD_1ST_MEN_N" and w["reason"] == "invisible_text" for w in out["notes"]["ocr_widgets"])
    assert vals["AP_RECD_1ST_WMN_N"] == "2345"                               # visible text on the page is unaffected


def test_text_without_rendered_ink_is_not_read(flat_2526):
    data = add_text(flat_2526, 12, 452, 303.5, "7777", white=True)           # white text in an empty field
    out = to.extract_overlay(data)
    assert "AP_ADMT_1ST_MEN_N" not in _values_by_tag(out)
    assert "no_rendered_ink" in _held(out, "AP_ADMT_1ST_MEN_N")


def test_garbled_text_layer_marks_page_unreadable_and_schedules_ocr(flat_2526, monkeypatch):
    real = to._page_chars_display

    def garble(page, g):
        return [to.PageChar(chr(0x10 + int(c.ch)) if c.ch.isdigit() else c.ch, c.cx, c.cy, c.right, c.generated, c.invisible)
                for c in real(page, g)]

    monkeypatch.setattr(to, "_page_chars_display", garble)
    to._template_chars.cache_clear()
    out = to.extract_overlay(flat_2526)
    to._template_chars.cache_clear()
    notes = out["notes"]
    assert 12 in notes["unreadable_pages"] and 12 in notes["pages_needing_ocr"]
    assert "AP_RECD_1ST_MEN_N" not in _values_by_tag(out)
    assert notes["lane_counts"].get("checkbox", 0) >= 4                     # Lane 3 does not read the text layer
    assert any(w["pdf_tag"] == "AP_RECD_1ST_MEN_N" and w["reason"] == "unreadable_page" for w in notes["ocr_widgets"])


def test_late_unreadable_glyph_voids_the_page_and_schedules_ocr(flat_2526, monkeypatch):
    """A good first field and a bad glyph in the next one: the whole page goes to OCR, nothing is kept from it."""
    real = to._page_chars_display
    wmn = to.load_maps()["2025-26"].fmap["fields"]["AP_RECD_1ST_WMN_N"]["widgets"][0]["rect"]

    def late_bad(page, g):
        out = real(page, g)
        for c in out:
            if wmn[0] <= c.cx <= wmn[2] and wmn[1] <= c.cy <= wmn[3] and c.ch.isdigit():
                c.ch = "\x12"
        return out

    monkeypatch.setattr(to, "_page_chars_display", late_bad)
    out = to.extract_overlay(flat_2526)
    assert 12 in out["notes"]["unreadable_pages"] and 12 in out["notes"]["pages_needing_ocr"]
    vals = _values_by_tag(out)
    assert "AP_RECD_1ST_MEN_N" not in vals and "AP_RECD_1ST_WMN_N" not in vals


def _chars(s, x0=10.0, y=10.0, step=5.0, **kw):
    return [to.PageChar(c, x0 + i * step, y, x0 + i * step + 2, **kw) for i, c in enumerate(s)]


def test_read_widget_text_centre_in_rect_and_no_padding():
    chars = _chars("(123)")                       # centres at 10, 15, 20, 25, 30
    assert to.read_widget_text(chars, [12, 5, 28, 15]) == ("123", False)
    assert to.read_widget_text(chars, [12, 5, 28, 15], pad=3.0)[0] == "(123)"


def test_read_widget_text_subtracts_static_label_by_position():
    chars = _chars("$ 77")
    static = (to.PageChar("$", 10.0, 10.0),)
    assert to.read_widget_text(chars, [5, 5, 40, 15], static, [5, 5, 40, 15])[0] == "77"
    assert to.read_widget_text(_chars("$", x0=30), [5, 5, 40, 15], static, [5, 5, 40, 15])[0] == "$"


def test_read_widget_text_bad_glyphs_and_markers():
    rect = [5, 5, 40, 15]
    assert to.read_widget_text(_chars("1\x122"), rect)[1] is True
    assert to.read_widget_text(_chars("12"), rect)[1] is True
    assert to.read_widget_text(_chars("1�2"), rect)[1] is True
    # a noncharacter or format character is ignored ONLY when pdfium marks it generated
    assert to.read_widget_text(_chars("1￾2"), rect)[1] is True
    assert to.read_widget_text(_chars("1­2"), rect)[1] is True
    chars = _chars("1") + [to.PageChar("￾", 15.0, 10.0, generated=True)] + _chars("2", x0=20.0)
    assert to.read_widget_text(chars, rect) == ("12", False)
    chars = _chars("1") + [to.PageChar("­", 15.0, 10.0, generated=True)] + _chars("2", x0=20.0)
    assert to.read_widget_text(chars, rect) == ("12", False)


def test_read_widget_text_flags_invisible_and_clipping():
    rect = [5, 5, 30, 15]
    rd = to.read_widget_text(_chars("12", invisible=True), rect, detail=True)
    assert rd.invisible and rd.text == "12"
    clipped = _chars("per semester h", x0=5.0, step=1.8)
    rd = to.read_widget_text(clipped, [5, 5, 30, 15], detail=True)
    assert rd.max_right is not None and rd.max_right > 30 - 2
    chars = _chars("ab", x0=6.0) + [to.PageChar("c", 31.0, 10.0)]            # glyphs continue just past the edge
    assert to.read_widget_text(chars, rect, detail=True).continues


@pytest.mark.parametrize("raw,vt,expect", [
    ("1234", "Number", "1234"), ("1,234", "Number", "1234"), ("1,234,567", "Number", "1234567"), ("$1,234", "Nearest $1", "1234"),
    ("45%", "Nearest 1%", "45"), (".5", "Whole Number or Round to Nearest Tenth", ".5"), ("12.5", "Number", "12.5"),
    ("1,23", "Number", None), ("5,00", "Number", None), ("1 2", "Number", None), ("12%34", "Number", None), ("3,5", "Number", None),
    ("-5", "Number", None), ("1.234,5", "Number", None), ("1,2345", "Number", None), ("12 34", "Number", None),
    ("1²", "Number", None), ("٣", "Number", None), ("12-34", "Number", None), ("1e5", "Number", None),
])
def test_number_grammar(raw, vt, expect):
    val, why = to.normalise_text_value(raw, vt, "SOME_TAG_N")
    assert val == expect and (why is None) == (expect is not None)


def test_percent_fields_live_in_0_100_for_every_percent_typed_tag():
    n = to.normalise_text_value
    assert n("100", "Whole Number or Round to Nearest Tenth", "RETENTION_FRSH_P") == ("100", None)
    assert n("100.10", "Whole Number or Round to Nearest Tenth", "BACH_TOT_P") == (None, "percent_out_of_range")
    assert n("101", "Nearest 1%", "FRAT_P") == (None, "percent_out_of_range")
    assert n("1300", "Whole Number or Round to Nearest Tenth", "SAT1_COMP_75TH_P") == ("1300", None)     # a score, not a percent
    assert to.effective_type("SAT1_COMP_75TH_P", "Whole Number or Round to Nearest Tenth", "/Tx") == "Number"
    assert to.effective_type("BACH_TOT_P", "Whole Number or Round to Nearest Tenth", "/Tx") == "Percent"
    assert to.effective_type("AD_TFER_GRADE", "Number", "/Tx") == "Text"
    assert to.effective_type("HOUS_COOP", "x", "/Btn") == "Button" and to.effective_type("CDS_PHONE", "Numbers", "/Tx") == "Identifier"


def test_month_day_identifier_and_ascii_digits():
    n = to.normalise_text_value
    assert n("12", "MM", "X_MON") == ("12", None) and n("13", "MM", "X_MON") == (None, "bad_month")
    assert n("²", "MM", "X_MON") == (None, "bad_month")                                # no crash on "²"
    assert n("²", "DD", "X_DAY") == (None, "bad_day") and n("31", "DD", "X_DAY") == ("31", None)
    assert n("(219) 464-5000", "Numbers", "CDS_PHONE") == ("(219) 464-5000", None)
    assert n("46383-6493", "Numbers", "ZIPCODE") == ("46383-6493", None)
    assert n("abc", "Numbers", "ZIPCODE") == (None, "not_digits")
    assert n("https://x.edu", "URL", "CDS_URL") == ("https://x.edu", None)


def test_choice_to_export_and_clipped_dropdowns():
    opt = [[" ", " "], ["C", "per credit"], ["R", "per credit hour"], ["S", "per semester hour"], ["Z", "per semester"]]
    f = to.choice_to_export
    assert f("per credit hour", opt) == ("R", None) and f("percredit", opt) == ("C", None)    # lost word gap
    assert f("per semester h", opt) == ("S", None)                                           # clipped, unique prefix
    assert f("per semester", opt) == ("Z", None)                                             # complete on screen
    assert f("per semester", opt, clipped=True) == (None, "choice_possibly_clipped")        # may be a clipped "per semester hour"
    assert f("per credit", opt, clipped=True) == (None, "choice_possibly_clipped")
    assert f("per", opt)[0] is None and f("credits", opt)[0] is None
    assert f("08", [[" ", " "], ["8", "8"]]) == ("8", None)                                  # editable MM/DD combos
    assert f("²", [[" ", " "], ["8", "8"]])[0] is None                                 # no crash


def test_clipped_dropdown_through_the_widget_pipeline(flat_2526):
    """A real /Ch whose printed text runs to the edge of the box and is a prefix of another option abstains."""
    fld = to.load_maps()["2025-26"].fmap["fields"]["AD_TFER_CRDT_MIN_UNIT"]
    w = fld["widgets"][0]
    x0, y0, x1, y1 = w["rect"]
    full = to.choice_to_export("per semester", fld["opt"], clipped=False)
    assert full == ("Z", None)
    chars = [to.PageChar(c, x1 - 40 + i * 3.3, (y0 + y1) / 2, x1 - 40 + i * 3.3 + 3.0) for i, c in enumerate("per semester")]
    rd = to.read_widget_text(chars, w["rect"], detail=True)
    assert rd.max_right is not None and rd.max_right > x1 - to.CLIP_EDGE_PT
    assert to.choice_to_export(rd.text, fld["opt"], clipped=rd.max_right > x1 - to.CLIP_EDGE_PT) == (None, "choice_possibly_clipped")


def test_multi_widget_fields_must_agree():
    """No current /Tx field has two widgets, so exercise the rule through a patched map."""
    maps = to.load_maps()
    fmap = json.loads(json.dumps(maps["2025-26"].fmap))
    f = fmap["fields"]["AP_RECD_1ST_WMN_N"]
    other = fmap["fields"]["AP_RECD_1ST_MEN_N"]["widgets"][0]
    f["widgets"].append(dict(other))                                                 # a second widget reading 1234
    patched = {y: to.YearMaps(y, fmap if y == "2025-26" else m.fmap, m.pages) for y, m in maps.items()}
    out = to.extract_overlay(fill_and_flatten("2025-26", FILL_TEXT, {}), maps=patched)
    assert "AP_RECD_1ST_WMN_N" not in _values_by_tag(out)
    assert "multi_widget_disagreement" in _held(out, "AP_RECD_1ST_WMN_N")


# --------------------------------------------------------------------------
# Lane 3 decisions and groups
# --------------------------------------------------------------------------

def test_btn_decision():
    f = to._is_btn_checked
    assert f([0.4], 0.05, 0.03) == (0, None) and f([0.01], 0.05, 0.03) == (None, None)
    assert f([0.08], 0.05, 0.03) == (None, "lone_checkbox_gray_band") and f([0.12], 0.05, 0.03) == (0, None)
    assert f([0.0, 0.4, 0.01], 0.05, 0.03) == (1, None)
    assert f([0.4, 0.39], 0.05, 0.03) == (None, "ambiguous_radio")
    assert f([None, None], 0.05, 0.03) == (None, None)
    assert to.RADIO_BAND_RULE is True
    assert f([0.0, 0.09], 0.05, 0.03) == (None, "radio_gray_band")      # winner in the band, runner-up blank: abstain
    assert f([0.3, 0.09], 0.05, 0.03) == (0, None)                        # clear winner over a real runner-up
    assert f([0.0, 0.3], 0.05, 0.03) == (1, None)                         # a strong check is kept
    old = to.RADIO_BAND_RULE
    try:
        to.RADIO_BAND_RULE = False
        assert f([0.0, 0.09], 0.05, 0.03) == (1, None)
    finally:
        to.RADIO_BAND_RULE = old


def test_fill_in_one_group_with_two_checked_abstains_on_both():
    data = fill_and_flatten("2025-26", FILL_TEXT, {"AP_REPLY_DL_MUST": "/X", "AP_REPLY_OTH": "/X", "AP_NOTF_DL_FRSH": "/X"})
    out = to.extract_overlay(data)
    vals = _values_by_tag(out)
    assert "AP_REPLY_DL_MUST" not in vals and "AP_REPLY_OTH" not in vals
    assert vals["AP_NOTF_DL_FRSH"] == "/X"                                        # a different group, one box: kept
    assert "fill_in_one_conflict" in _held(out, "AP_REPLY_OTH")


# --------------------------------------------------------------------------
# validation
# --------------------------------------------------------------------------

def test_identities():
    check = to.check_identities
    tags = set(bfm.load_field_map("2025-26")["fields"])
    ok = {"EN_FRSH_FT_MEN_N": "10", "EN_OTH_1ST_FT_MEN_N": "5", "EN_DEG_FT_MEN_N": "7", "EN_TOT_DEG_FT_MEN_N": "22"}
    assert check(ok, tags) == []
    assert check(dict(ok, EN_TOT_DEG_FT_MEN_N="23"), tags)[0]["identity"] == "B1_total_degree_seeking"
    assert check({"AP_RECD_1ST_N": "100", "AP_ADMT_1ST_N": "50", "EN_TOT_1ST_N": "20"}, tags) == []
    assert check({"AP_RECD_1ST_N": "10", "AP_ADMT_1ST_N": "50", "EN_TOT_1ST_N": "20"}, tags)[0]["identity"].startswith("C1")
    assert check({"SAT1_COMP_25TH_P": "1100", "SAT1_COMP_50TH_P": "1200", "SAT1_COMP_75TH_P": "1300"}, tags) == []
    assert check({"SAT1_COMP_25TH_P": "1300", "SAT1_COMP_50TH_P": "1200"}, tags)[0]["identity"] == "C9_percentile_order"
    assert check({"ACT_COMP_25TH_P": "20", "ACT_COMP_75TH_P": "40"}, tags)[0]["identity"] == "C9_score_range"


def test_identity_failures_are_rejected_in_every_lane():
    flat = fill_and_flatten("2025-26", {"AP_RECD_1ST_N": "10", "AP_ADMT_1ST_N": "50", "EN_TOT_1ST_N": "20"}, {})
    out = to.extract_overlay(flat)
    notes = out["notes"]
    assert [f["identity"] for f in notes["identity_failures"]] == ["C1_applied_admitted_enrolled"]
    assert notes["identity_failures"][0]["action"] == "rejected"
    vals = _values_by_tag(out)
    assert not ({"AP_RECD_1ST_N", "AP_ADMT_1ST_N", "EN_TOT_1ST_N"} & set(vals))
    rejected = {r["pdf_tag"]: r["reason"] for r in notes["rejected_fields"]}
    assert rejected["AP_RECD_1ST_N"] == "identity_failed:C1_applied_admitted_enrolled" and len(rejected) == 3


def test_blank_template_page_emits_no_checkbox():
    out = to.extract_overlay(fill_and_flatten("2025-26", {}, {}))
    assert out["notes"]["lane_counts"].get("checkbox", 0) == 0


def test_cli_writes_json(flat_2526, tmp_path):
    pdf = tmp_path / "flat.pdf"
    pdf.write_bytes(flat_2526)
    out = tmp_path / "out.json"
    assert to.main([str(pdf), "--detected-year", "2025-26", "--output", str(out)]) == 0
    assert json.loads(out.read_text())["values"]["C.101"]["value"] == "1234"


# --------------------------------------------------------------------------
# opt-in: real school PDFs
# --------------------------------------------------------------------------

REAL = os.environ.get("CDS_M1_PDF_DIR")


@pytest.mark.skipif(not REAL, reason="set CDS_M1_PDF_DIR to the review PDF directory")
def test_real_pdfs_valparaiso_miami_arkansas():
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
        assert results[name]["extras"] == []                      # nothing emitted where Tier 2 is blank
    ark = to.extract_overlay((d / "e69a95f19092cef6d67f5ceea35056bea403815b02ce0ae1f4ce3685c9b46a13.pdf").read_bytes())
    assert ark["notes"]["lane_counts"].get("text", 0) == 0 and len(ark["notes"]["unreadable_pages"]) >= 30
    # v0.2.0 numbers (every loss is named by an abstention rule): Valparaiso 611/624, Miami /Btn 147/152
    assert results["valpo"]["ok"] >= 611 and results["miami"]["by_type"]["Btn"][0] >= 147
