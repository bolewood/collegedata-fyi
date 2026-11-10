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
from pypdf.generic import (ArrayObject, DecodedStreamObject, DictionaryObject, FloatObject, NameObject, NumberObject,
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


def _shift_region_of_page(w: pypdf.PdfWriter, page, region: tuple[float, float, float, float], dx: float, dy: float) -> None:
    """Redraw the page's STATIC content with everything inside `region` (x, y, w, h) moved by (dx, dy).

    Only meant for the blank template page, before any widget appearance is baked in: the
    form's own label text inside the region is drawn twice (pdfium reads text through clips),
    which is harmless for labels (never an answer) and keeps every answer drawn exactly once.
    """
    x, y, rw, rh = region
    orig = _contents_parts(page)
    parts = ([_raw(w, f"q 0 0 612 792 re {x} {y} {rw} {rh} re W* n\n".encode())] + orig + [_raw(w, b"\nQ\n")]
             + [_raw(w, f"q {x} {y} {rw} {rh} re W n 1 0 0 1 {dx} {dy} cm\n".encode())] + orig + [_raw(w, b"\nQ\n")])
    page[NameObject("/Contents")] = ArrayObject(parts)


def fill_and_flatten(year: str, text: dict[str, str], buttons: dict[str, str], specks: dict[str, float] | None = None,
                     offsets: dict[str, tuple[float, float]] | None = None,
                     static_shift: tuple[int, tuple[float, float, float, float], float, float] | None = None) -> bytes:
    """Fill a blank template, then bake the widget appearances into page content.

    Unchecked boxes are drawn with their /Off appearance (the bevelled box a
    PDFium-flattened print shows) and `specks` adds stray ink to chosen boxes, so
    unchecked widgets do not all score exactly 0. `offsets` draws the named widgets' own
    appearance (text included, exactly once) displaced by (dx, dy) points; `static_shift`
    = (page, region, dx, dy) displaces the form's static ink inside a region of one page
    the same way. Together they make a partial-page shift without duplicating any answer.
    """
    w = _writer_from(bfm.template_path_for(year))
    if static_shift:
        _shift_region_of_page(w, w.pages[static_shift[0]], *static_shift[1:])
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
            odx, ody = (offsets or {}).get(tag, (0.0, 0.0))
            normal = a["/AP"]["/N"].get_object()
            if not isinstance(normal, StreamObject):          # button: on-state stream, else /Off
                want = buttons.get(tag)
                normal = normal[want].get_object() if want and want in normal else (normal["/Off"].get_object() if "/Off" in normal else None)
            if normal is None:
                continue
            bbox = [float(v) for v in normal.get("/BBox", [0, 0, 1, 1])]
            x0, y0, x1, y1 = (float(v) for v in a["/Rect"])
            x0, x1, y0, y1 = min(x0, x1) + odx, max(x0, x1) + odx, min(y0, y1) + ody, max(y0, y1) + ody
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


def translate_pages(data: bytes, dx: float, dy: float, pages: list[int] | None = None) -> bytes:
    """Whole pages (all, or the listed indices) printed displaced by (dx, dy) points, boxes unchanged."""
    w = _writer_from(data)
    for i, page in enumerate(w.pages):
        if pages is None or i in pages:
            page[NameObject("/Contents")] = ArrayObject(
                [_raw(w, f"q 1 0 0 1 {dx} {dy} cm\n".encode())] + _contents_parts(page) + [_raw(w, b"\nQ\n")])
    return _write(w)


def white_out(data: bytes, page_index: int, box: tuple[float, float, float, float], pad: float = 1.5) -> bytes:
    """Cover a region (x0, y0, x1, y1) with a white rectangle (e.g. to blank a printed header year)."""
    w = _writer_from(data)
    page = w.pages[page_index]
    x0, y0, x1, y1 = box
    page[NameObject("/Contents")] = ArrayObject(
        _contents_parts(page) + [_raw(w, f"\nq 1 g {x0 - pad} {y0 - pad} {x1 - x0 + 2 * pad} {y1 - y0 + 2 * pad} re f Q\n".encode())])
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


def add_text(data: bytes, page_index: int, x: float, y: float, text: str, *, render_mode: int = 0, white: bool = False,
             size: float = 10) -> bytes:
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
        _contents_parts(page) + [_raw(w, f"\nq {color} BT {render_mode} Tr /FxAdd {size} Tf {x} {y} Td ({text}) Tj ET Q\n".encode())])
    return _write(w)


def add_check(data: bytes, page_index: int, rect: list[float]) -> bytes:
    """Draw a clear check mark across a widget rect (a second tick in a group, or a mark on a box-less option)."""
    w = _writer_from(data)
    page = w.pages[page_index]
    x0, y0, x1, y1 = rect
    path = (f"\nq 0 G 1.1 w {x0 + 0.2 * (x1 - x0):.3f} {y0 + 0.5 * (y1 - y0):.3f} m {x0 + 0.42 * (x1 - x0):.3f} {y0 + 0.2 * (y1 - y0):.3f} l "
            f"{x0 + 0.85 * (x1 - x0):.3f} {y0 + 0.85 * (y1 - y0):.3f} l S Q\n").encode()
    page[NameObject("/Contents")] = ArrayObject(_contents_parts(page) + [_raw(w, path)])
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
    assert "HOUS_DISABLED" not in vals                       # 2% stray ink: far below the threshold
    assert "HOUS_COOP" not in vals                           # 8% stray ink (of the old 30% core): below the threshold
    assert not _held(base, "HOUS_COOP") and not _held(base, "HOUS_DISABLED")
    assert sum(1 for r in base["values"].values() if r.get("lane") == "checkbox") == 5   # 4 filled + HOUS_SINGLE


def test_lane3_threshold_is_exercised(flat_2526):
    """A lower threshold must change the outcome, so a threshold mutation cannot go unnoticed."""
    low = to.extract_overlay(flat_2526, lane3_threshold=0.001)
    assert _values_by_tag(low).get("HOUS_COOP") == "/X"                      # the 8% speck counts at a near-zero threshold ...
    assert "HOUS_COOP" not in _values_by_tag(to.extract_overlay(flat_2526))  # ... and not at the default
    assert "HOUS_COOP" not in _values_by_tag(to.extract_overlay(flat_2526, lane3_threshold=0.9))


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
    assert d(c, {"2024-25": 46}, None)[2] == "header_year_contradicts_raster_year"   # wrong year leads
    assert d(c, {"2024-25": 46, "2025-26": 3}, None)[2] == "mixed_year_packet"
    assert d(c, {"2024-25": 25, "2025-26": 24}, None)[2] == "mixed_year_packet"
    # strict: ONE confident other-year page holds the whole packet (no majority rule)
    assert d(c, {"2025-26": 48, "2024-25": 1}, None)[:3] == (to.STATUS_AMBIGUOUS, None, "mixed_year_packet")
    assert d(c, {"2025-26": 48, "2023-24": 1}, None)[2] == "mixed_year_packet"
    # a weak vote for another year (poor margin or fit: sub-point prints, odd fonts) cannot hold a packet; a confident one can
    assert d(c, {"2025-26": 48, "2023-24": 1}, None, {"2025-26": 40})[:3] == (to.STATUS_MATCHED, "2025-26", None)
    assert d(c, {"2025-26": 48, "2023-24": 1}, None, {"2025-26": 40, "2023-24": 1})[2] == "mixed_year_packet"
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
    assert res.status == to.STATUS_AMBIGUOUS and res.reason == "mixed_year_packet"      # strict: the 2025-26 pages' own headers
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

def widgets_in(year: str, page: int, region: tuple[float, float, float, float]) -> list[str]:
    """Tags of the widgets whose rect centre lies in region (x, y, w, h) of a template page."""
    x, y, rw, rh = region
    out = []
    for tag, f in to.load_maps()[year].fmap["fields"].items():
        for wd in f["widgets"]:
            cx, cy = (wd["rect"][0] + wd["rect"][2]) / 2, (wd["rect"][1] + wd["rect"][3]) / 2
            if wd["template_page"] == page and x <= cx <= x + rw and y <= cy <= y + rh:
                out.append(tag)
    return out


def shifted_fixture(year, text, buttons, page, region, dx, dy):
    """Answers AND form ink inside `region` of one page printed (dx, dy) away; every answer drawn once."""
    tags = widgets_in(year, page, region)
    return fill_and_flatten(year, text, buttons, None, offsets={t: (dx, dy) for t in tags}, static_shift=(page, region, dx, dy))


def _assert_alignment_not_grammar(out, tags):
    """A shifted read must be stopped by an alignment rule, never by the number grammar by accident."""
    rej = {r["pdf_tag"] for r in out["notes"]["rejected_fields"] if r["reason"] == "not_numeric"}
    assert not (rej & set(tags)), rej & set(tags)


def test_partial_page_shift_withholds_the_shifted_half_only(flat_2526):
    """Lower half of the housing/ROTC page printed 15 pt low (CSU Northridge): nothing there is read."""
    data = shifted_fixture("2025-26", FILL_TEXT, {"HOUS_COOP": "/X", "LIFE_CAMPUS": "/Y", "ROTC_ARMY": "/C"}, 27, (0, 0, 612, 396), 0, -15)
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
    data = shifted_fixture("2025-26", FILL_TEXT, {"AD_TFER": "/Y", "AD_TFER_CRDT": "/Y"}, 23, (150, 600, 400, 80), 8.5, 0)
    out = to.extract_overlay(data)
    vals = _values_by_tag(out)
    for tag in ("AD_TFER", "AD_TFER_CRDT"):
        assert vals.get(tag) in (None, "/Y"), (tag, vals.get(tag))


def test_one_shifted_table_row_is_caught_by_the_per_widget_check_alone():
    """12 pt shift of two table cells: too small for the band test, and 1234 would be read into the next row."""
    data = shifted_fixture("2025-26", {"AP_RECD_1ST_MEN_N": "1234"}, {}, 12, (440, 355, 80, 40), 0, -12)
    out = to.extract_overlay(data)
    vals = _values_by_tag(out)
    assert not out["notes"]["stage1"]["band_rejections"].get("12") and "12" not in out["notes"]["stage1"]["rejected_pages"]
    assert vals.get("AP_RECD_1ST_WMN_N") is None                                   # 1234 is not read into the next row
    assert vals.get("AP_RECD_1ST_MEN_N") in (None, "1234")
    assert "local_misalignment" in {w["reason"] for w in out["notes"]["withheld"]}
    # the cell that would receive the displaced 1234 is stopped by the alignment check, not by the grammar
    # (the displaced label "TOTAL" falling into the MEN cell is rejected as not_numeric: a fixture side effect)
    assert [w["reason"] for w in out["notes"]["withheld"] if w["pdf_tag"] == "AP_RECD_1ST_WMN_N"] == ["local_misalignment"]
    _assert_alignment_not_grammar(out, ["AP_RECD_1ST_WMN_N"])


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
    assert f([0.4], 0.04, 0.03) == (0, None) and f([0.01], 0.04, 0.03) == (None, None)
    assert f([0.06], 0.04, 0.03) == (0, None)                                # no gray band: interior scores are bimodal
    assert f([0.0, 0.4, 0.01], 0.04, 0.03) == (1, None)
    assert f([0.06, 0.035], 0.04, 0.03) == (None, "ambiguous_radio")       # one mark, a runner-up too close to call
    assert f([0.4, 0.39], 0.04, 0.03) == (None, "multiple_options_marked")
    assert f([None, None], 0.04, 0.03) == (None, None)
    assert f([None, 0.3, 0.0], 0.04, 0.03) == (1, None)
    for gone in ("RADIO_BAND_RULE", "LANE3_BAND_HI", "FRAME_GATE", "BORDER_RULE"):
        assert not hasattr(to, gone), gone                                   # the legacy rules are removed, not disabled
    assert not hasattr(to, "locate_frame") and not hasattr(to, "core_is_border_line")


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


# --------------------------------------------------------------------------
# fix round 2: residual page shift (B1), raster-year veto (B2), edge guard (B3),
# strict header year at the applied shift (N3), thousands dots (N6), Lane 2 seam
# --------------------------------------------------------------------------

def rich_fill(year: str, skip_tags: tuple[str, ...] = ()) -> tuple[dict[str, str], dict[str, str]]:
    """Every joined Number field gets a distinct value, every third button its first on-state."""
    tags = {x["pdf_tag"] for x in to._schema(year)["fields"] if x.get("pdf_tag")}
    text, btn, i = {}, {}, 0
    for t, f in to.load_maps()[year].fmap["fields"].items():
        if not f["question_number"] or t not in tags or t in skip_tags or to._C9_RE.match(t):
            continue
        if f["ft"] == "/Tx" and to.effective_type(t, f["value_type"], "/Tx") == "Number":
            i += 1
            text[t] = str(100 + 7 * i)
        elif f["ft"] == "/Btn":
            i += 1
            if i % 3 == 0:
                btn[t] = f["widgets"][0]["on_state"]
    return text, btn


def wrong_values(out: dict, text: dict[str, str], btn: dict[str, str]) -> list[tuple]:
    """Read values (lanes 1 and 3) that differ from what the fixture printed."""
    fields = to.load_maps()[out["notes"]["template_year"]].fmap["fields"] if out["notes"]["template_year"] else {}
    bad = []
    for r in out["values"].values():
        t = r.get("pdf_tag")
        if r.get("lane") not in ("text", "checkbox") or t not in fields:
            continue
        want = btn.get(t) if fields[t]["ft"] == "/Btn" else text.get(t)
        if want is None and r["value"] in ("0", "0.0", "0.00"):
            continue                                         # the blank template prints 0.00 in its calculated total fields
        if want is None or str(r["value"]).replace(",", "") != want:
            bad.append((t, r["value"], want))
    return bad


@pytest.fixture(scope="module")
def rich_2526():
    text, btn = rich_fill("2025-26")
    return fill_and_flatten("2025-26", text, btn, None), text, btn


@pytest.fixture(scope="module")
def rich_2425():
    text, btn = rich_fill("2024-25")
    return fill_and_flatten("2024-25", text, btn, None), text, btn


def _page_of(year: str, tag: str) -> int:
    return to.load_maps()[year].fmap["fields"][tag]["widgets"][0]["template_page"]


def test_rich_fixture_reads_back_exactly(rich_2526):
    data, text, btn = rich_2526
    out = to.extract_overlay(data)
    assert wrong_values(out, text, btn) == [] and len(out["values"]) > 400


@pytest.mark.parametrize("dx", [8.5, 10, 11, 12])
def test_page_shift_beyond_the_search_range_is_a_residual_shift_not_an_applied_one(rich_2526, dx):
    """B1: a page printed 8.5-12 pt aside has its optimum on (or inside, with every band disagreeing) the
    +-8 pt search range. It must be rejected, not read at a 2-4 pt residual (empty boxes read as checked)."""
    data, text, btn = rich_2526
    page = _page_of("2025-26", "ROTC_MARINE_OPT")
    doc = pdfium.PdfDocument(translate_pages(data, dx, 0))
    est = to.estimate_page_alignment(to._page_masks(doc[page], to.page_geometry(doc[page]), to._template_doc("2025-26")[page]))
    assert not est["consistent"] and est["inconsistent_reason"] == "residual_page_shift", est
    # end to end: nothing wrong is emitted (the document is held or the pages are rejected)
    assert wrong_values(to.extract_overlay(translate_pages(data, dx, 0)), text, btn) == []


def test_one_page_printed_11pt_aside_is_rejected_inside_a_document_that_still_matches(rich_2526):
    """B1 end to end: the page shift is beyond the search range, the rest of the packet is fine."""
    data, text, btn = rich_2526
    page = _page_of("2025-26", "ROTC_MARINE_OPT")
    shifted = translate_pages(data, 11, 0, [page])
    res = to.match_template(shifted)
    assert res.status == to.STATUS_MATCHED and res.year == "2025-26"
    assert res.rejected_pages.get(page) == "residual_page_shift" and page not in res.page_map
    out = to.extract_overlay(shifted)
    assert wrong_values(out, text, btn) == [] and len(out["values"]) > 400
    assert not any(r.get("pdf_tag") == "ROTC_MARINE_OPT" for r in out["values"].values())


def test_in_range_whole_page_shift_is_still_applied(rich_2526):
    data, text, btn = rich_2526
    for dx, dy in [(6, 0), (3, 0), (0, -5), (2, 3)]:
        out = to.extract_overlay(translate_pages(data, dx, dy))
        assert out["notes"]["stage1"]["status"] == "matched" and out["notes"]["stage1"]["header_votes"] == {"2025-26": 49 if dy == 0 else out["notes"]["stage1"]["header_votes"]["2025-26"]}
        assert wrong_values(out, text, btn) == [] and len(out["values"]) > 500, (dx, dy)


def test_local_check_uses_the_applied_page_shift_with_its_sign(rich_2526):
    """A whole page printed 3 pt low is shifted back by the page alignment; the per-widget check must
    then agree with that shift (a flipped dy sign makes every widget look 6 pt misaligned)."""
    data, text, btn = rich_2526
    base_out = to.extract_overlay(data)
    for dy in (-3, 3):
        out = to.extract_overlay(translate_pages(data, 0, dy))
        dys = [a["dy"] for a in out["notes"]["stage1"]["alignment"].values()]
        assert sum(1 for d in dys if d == dy) >= 0.8 * len(dys), (dy, sorted(set(dys)))
        assert len(out["values"]) >= 0.97 * len(base_out["values"]), (dy, len(out["values"]), len(base_out["values"]))
        assert out["notes"]["withheld_by_reason"].get("local_misalignment", 0) <= 5
        assert wrong_values(out, text, btn) == []


def test_page_that_prefers_the_other_year_is_not_read_through_this_years_map(rich_2425, rich_2526):
    """B2: one 2025-26 page (header digits blanked, so it casts no vote) inside a 2024-25 packet."""
    d25, d26 = rich_2425[0], rich_2526[0]
    hb = to._header_boxes()[4]
    blank4 = white_out(d26, 4, tuple(hb))
    packet = assemble([(blank4 if i == 4 else d25, i) for i in range(50)])
    res = to.match_template(packet)
    assert res.status == to.STATUS_MATCHED and res.year == "2024-25"
    assert res.rejected_pages.get(4) == "page_raster_prefers_other_year" and 4 not in res.page_map
    out = to.extract_overlay(packet)
    assert out["notes"]["page_map"].get("4") is None
    assert wrong_values(out, *rich_2425[1:]) == []
    # the same page with its header left on casts the other year's vote and holds the packet (strict)
    packet2 = assemble([(d26 if i == 4 else d25, i) for i in range(50)])
    assert to.match_template(packet2).reason == "mixed_year_packet"


def test_one_confident_other_year_page_holds_the_packet(rich_2425, rich_2526):
    """Strict year rule: no majority. A single page whose printed header says another year holds everything."""
    packet = assemble([(rich_2526[0] if i == 1 else rich_2425[0], i) for i in range(50)])
    res = to.match_template(packet)
    assert res.status == to.STATUS_AMBIGUOUS and res.reason == "mixed_year_packet", (res.status, res.reason, res.header_votes)
    assert to.extract_overlay(packet)["values"] == {}


def test_header_vote_is_cast_at_the_pages_applied_shift(rich_2526):
    """N3: shifted pages must not vote for the wrong year, and a shifted page must not hold a correct packet."""
    data, text, btn = rich_2526
    for name, d in [("doc x+3", translate_pages(data, 3, 0)), ("doc y-5", translate_pages(data, 0, -5)),
                    ("page 4 y-5", translate_pages(data, 0, -5, [4])), ("page 4 x+7", translate_pages(data, 7, 0, [4]))]:
        res = to.match_template(d)
        assert res.status == to.STATUS_MATCHED and set(res.header_votes) == {"2025-26"}, (name, res.status, res.reason, res.header_votes)
        assert wrong_values(to.extract_overlay(d), text, btn) == [], name


def test_header_vote_needs_an_absolute_match():
    """The best year must also match the header absolutely; a smudged or wrong-position header casts no vote."""
    year = "2025-26"
    tdoc = to._template_doc(year)
    page = tdoc[4]
    g = to.page_geometry(page)
    vote, d0, margin, ratio = to.header_year_vote(page, g, 4, detail=True)
    assert vote == year and d0 < 0.01 and margin >= to.HEADER_DISSENT_MARGIN and ratio <= to.HEADER_DISSENT_MAX_RATIO
    def confident(dx, dy):
        v, _d, m, r = to.header_year_vote(page, g, 4, dx, dy, detail=True)
        return v is not None and m >= to.HEADER_DISSENT_MARGIN and r <= to.HEADER_DISSENT_MAX_RATIO
    assert not confident(40.0, 0.0)          # crop taken 40 pt away from the header
    assert not confident(0.0, -10.0)         # a blank crop "votes" for the lightest year at best weakly
    assert not confident(0.0, 6.0)           # 6 pt off: matches no year well
    assert to.header_year_vote(page, g, 4, 0.0, -30.0) is None      # fully blank crop: no ink, no vote
    assert to.header_year_vote(page, g, 4, 0.0, 0.0) == year


# ---- B3: the printed answer continues past the rect ------------------------

def _gb(s: str, x0: float, y: float = 10.0, step: float = 5.0, w: float = 4.0):
    return [to.GlyphBox(x0 + i * step, x0 + i * step + w, y) for i, _c in enumerate(s)]


def test_edge_continuation_unit():
    rect = [100.0, 5.0, 130.0, 17.0]
    assert to.edge_continuation(_gb("12345", 102), rect) is None                          # fits, nothing near
    assert to.edge_continuation(_gb("1234567", 102), rect) == "glyph_crosses_right_edge"  # 24038 style: box spans the edge
    assert to.edge_continuation(_gb("1234567", 80, w=6.0), rect) == "glyph_crosses_left_edge"    # the rect cuts the left end
    assert to.edge_continuation(_gb("12", 102) + [to.GlyphBox(130.6, 134.0, 10.0)], rect) == "glyph_past_right_edge"   # gap <= 1 pt
    assert to.edge_continuation(_gb("12", 102) + [to.GlyphBox(133.0, 137.0, 10.0)], rect) is None                     # 3 pt away
    assert to.edge_continuation(_gb("12", 102) + [to.GlyphBox(90.0, 99.4, 10.0)], rect) == "glyph_past_left_edge"
    assert to.edge_continuation(_gb("12", 102) + [to.GlyphBox(132.0, 138.0, 30.0)], rect) is None                     # another line
    assert to.edge_continuation(_gb("", 0), rect) is None


def test_multiline_overflow_unit():
    rect = [100.0, 5.0, 160.0, 29.0]
    lines = _gb("abc", 102, 22.0) + _gb("def", 102, 10.0)
    assert to.edge_continuation(lines, rect) is None
    assert to.edge_continuation(lines + _gb("ghi", 102, -2.0), rect) == "multiline_overflow"     # a third line below
    assert to.edge_continuation(lines + _gb("ghi", 102, 34.0), rect) == "multiline_overflow"     # ... or above
    assert to.edge_continuation(lines + _gb("ghi", 102, -2.0), rect, multiline=False) is None    # numbers: a table neighbour
    assert to.edge_continuation(_gb("abc", 102, 10.0) + _gb("ghi", 102, -2.0), rect) is None     # single line: not multi-line


def test_number_overflowing_its_cell_is_not_split_across_two_cells(rich_2526):
    """B3: "24038" printed across SCHOL_NB_FED_D and the empty cell to its right emitted 24 and 038."""
    year = "2025-26"
    text, btn = rich_fill(year, skip_tags=("SCHOL_NB_FED_D", "SCHOL_NN_FED_D"))
    flat = fill_and_flatten(year, text, btn, None)
    fm = to.load_maps()[year].fmap["fields"]
    w = fm["SCHOL_NB_FED_D"]["widgets"][0]
    x0, y0, x1, y1 = w["rect"]
    assert fm["SCHOL_NN_FED_D"]["widgets"][0]["rect"][0] >= x1 - 1
    for inside in (0.3, 0.5, 0.7):
        data = add_text(flat, w["template_page"], x1 - inside * 27.8, y0 + 3, "24038")
        out = to.extract_overlay(data)
        vals = _values_by_tag(out)
        assert "SCHOL_NB_FED_D" not in vals and "SCHOL_NN_FED_D" not in vals, (inside, vals.get("SCHOL_NB_FED_D"), vals.get("SCHOL_NN_FED_D"))
        assert wrong_values(out, text, btn) == []
    # the guard is what stops it: without it the rect keeps the digits whose centres fall inside
    old = to.EDGE_GUARD, to.TOKEN_GUARD
    to.EDGE_GUARD = to.TOKEN_GUARD = False
    try:
        data = add_text(flat, w["template_page"], x1 - 0.5 * 27.8, y0 + 3, "24038")
        assert "SCHOL_NB_FED_D" in _values_by_tag(to.extract_overlay(data))
    finally:
        to.EDGE_GUARD, to.TOKEN_GUARD = old
    # a number that fits its cell is untouched
    data = add_text(flat, w["template_page"], x0 + 3, y0 + 3, "24")
    assert _values_by_tag(to.extract_overlay(data)).get("SCHOL_NB_FED_D") == "24"


def test_glyph_boxes_exclude_the_forms_own_label_text():
    static = tuple(_chars("Name:", 10.0, 10.0))
    chars = _chars("Name:", 10.0, 10.0) + _chars("Bob", 40.0, 10.0)
    boxes = to.glyph_boxes(chars, static, [38.0, 5.0, 60.0, 17.0])
    assert len(boxes) == 3 and all(b.left >= 37.0 for b in boxes)


def test_widget_gates_are_public_and_take_glyphs(rich_2526):
    data, _text, _btn = rich_2526
    doc = pdfium.PdfDocument(data)
    res = to.match_template(doc)
    q = next(q for q, p in res.page_map.items() if p == 12)
    c = to.PageCtx(doc, q, 12, "2025-26", res)
    w = to.load_maps()["2025-26"].fmap["fields"]["AP_RECD_1ST_MEN_N"]["widgets"][0]
    assert to.widget_gates(c, "AP_RECD_1ST_MEN_N", 0, w["rect"]) is None
    x0, y0, x1, y1 = w["rect"]
    cut = [to.GlyphBox(x1 - 3, x1 + 3, (y0 + y1) / 2), to.GlyphBox(x1 - 9, x1 - 4, (y0 + y1) / 2)]
    assert to.widget_gates(c, "AP_RECD_1ST_MEN_N", 0, w["rect"], glyphs=cut) == "glyph_crosses_right_edge"


def test_ocr_widgets_carry_index_rect_and_shift(flat_2526):
    data = add_text(flat_2526, 12, 452, 377.5, "9876", render_mode=3)
    out = to.extract_overlay(data)
    item = next(w for w in out["notes"]["ocr_widgets"] if w["pdf_tag"] == "AP_RECD_1ST_MEN_N")
    w = to.load_maps()["2025-26"].fmap["fields"]["AP_RECD_1ST_MEN_N"]["widgets"][0]
    assert item["widget"] == 0 and item["rect"] == [round(v, 3) for v in w["rect"]] and item["template_page"] == 12
    assert item["shift"] == {"dx": 0.0, "dy": 0.0} and item["page"] == 12


def test_identities_run_over_the_union_of_lanes():
    vals = {"1": {"pdf_tag": "AP_RECD_1ST_N", "value": "100", "lane": "text"},
            "2": {"pdf_tag": "AP_ADMT_1ST_N", "value": "500", "lane": "ocr"},        # a Lane 2 value added later
            "3": {"pdf_tag": "EN_TOT_1ST_N", "value": "50", "lane": "text"}}
    tags = {"AP_RECD_1ST_N", "AP_ADMT_1ST_N", "EN_TOT_1ST_N"}
    ident, rejected = to.reject_identity_failures(vals, tags)
    assert ident and vals == {} and {r["pdf_tag"] for r in rejected} == tags


@pytest.mark.parametrize("raw,vt,ok", [
    ("1.234", "Number", False), ("12.345", "Nearest $1", False), ("$9.999", "Nearest $1", False), ("1.234%", "Nearest 1%", False),
    ("1.234", "Whole Number or Round to Nearest Tenth", False),     # three decimals exceed every decimal type (tenths, hundredths)
    ("12.345", "Round to Nearest Hundredths", False), ("1.23", "Whole Number or Round to Nearest Tenth", True),
    ("1.23", "Number", True), ("0.123", "Number", True), ("1,234.5", "Number", True), ("1.2345", "Number", True),
])
def test_thousands_dot_on_integer_typed_fields(raw, vt, ok):
    val, why = to.normalise_text_value(raw, vt, "X_N")
    assert (why is None) == ok, (val, why)
    if not ok:
        assert why == "ambiguous_thousands_separator"


# ---- Lane 3: the box is measured where the print draws it -----------------------

K3 = 216 / 72


def _page_canvas() -> np.ndarray:
    return np.full((int(792 * K3), int(612 * K3)), 255, dtype=np.uint8)


def _draw_box(g: np.ndarray, x0: float, y0: float, x1: float, y1: float, stroke: float = 1.0, level: int = 0,
              gap: tuple[str, int] | None = None) -> None:
    """A frame with the outer edge on (x0, y0, x1, y1) (template pt, y up); `gap` ('top'|'left', px) opens it."""
    t = max(int(round(stroke * K3)), 1)
    r0, c0 = int((792 - y1) * K3), int(x0 * K3)
    r1, c1 = int((792 - y0) * K3), int(x1 * K3)
    g[r0:r0 + t, c0:c1] = level
    g[r1 - t:r1, c0:c1] = level
    g[r0:r1, c0:c0 + t] = level
    g[r0:r1, c1 - t:c1] = level
    if gap:
        side, n = gap
        mid = (r0 + r1) // 2 if side == "left" else (c0 + c1) // 2
        if side == "left":
            g[mid - n:mid + n, c0:c0 + t] = 255
        else:
            g[r0:r0 + t, mid - n:mid + n] = 255


def _draw_check(g: np.ndarray, cx: float, cy: float, size: float) -> None:
    r, c = int((792 - cy) * K3), int(cx * K3)
    for i in range(int(size * K3)):
        g[r + i // 2 - 2:r + i // 2 + 1, c - int(size * K3 / 2) + i:c - int(size * K3 / 2) + i + 3] = 0
        g[r - i // 2 - 3:r - i // 2, c + i:c + i + 3] = 0


RECT = [100.0, 500.0, 110.0, 510.0]       # a 10 x 10 pt widget rect


def test_interior_of_an_empty_box_scores_zero_wherever_the_print_draws_it():
    for ox, oy in [(0, 0), (0.5, 0), (-1.0, 0.7), (1.2, -1.1)]:                # box sits off the rect by up to ~1 pt
        g = _page_canvas()
        _draw_box(g, 100.8 + ox, 500.8 + oy, 109.2 + ox, 509.2 + oy, 1.2)
        it, why = to.locate_interior(g, RECT, 0.0, 0.0)
        assert it is not None and why is None, (ox, oy, why)
        assert to.interior_density(g, it) == 0.0                                  # the frame is never inside the measured core


def test_interior_density_measures_a_mark_not_the_frame_even_for_a_heavy_bevelled_box():
    g = _page_canvas()
    _draw_box(g, 99.4, 499.4, 110.6, 510.6, 1.0, level=128)                     # bigger than the rect, gray, heavy
    _draw_box(g, 100.4, 500.4, 109.6, 509.6, 0.6, level=190)
    it, _ = to.locate_interior(g, RECT, 0.0, 0.0)
    assert it is not None and to.interior_density(g, it) == 0.0
    _draw_check(g, 105.0, 505.0, 5.0)
    it, _ = to.locate_interior(g, RECT, 0.0, 0.0)
    assert to.interior_density(g, it) > 0.1


def test_check_that_splits_or_crosses_the_box_still_finds_the_whole_interior():
    g = _page_canvas()
    _draw_box(g, 100.8, 500.8, 109.2, 509.2, 1.0)
    clean, _ = to.locate_interior(g, RECT, 0.0, 0.0)
    _draw_check(g, 105.0, 505.0, 7.0)                                         # the tail leaves the box
    it, why = to.locate_interior(g, RECT, 0.0, 0.0)
    assert it is not None, why
    assert abs(it.w_pt - clean.w_pt) < 1.5 and abs(it.h_pt - clean.h_pt) < 1.5


def test_filled_dot_radio_is_found_through_its_ring():
    g = _page_canvas()
    _draw_box(g, 100.5, 500.5, 109.5, 509.5, 0.8, level=150)
    r0, c0 = int((792 - 505) * K3), int(105 * K3)
    yy, xx = np.mgrid[0:g.shape[0], 0:g.shape[1]]
    g[(yy - r0) ** 2 + (xx - c0) ** 2 <= (1.9 * K3) ** 2] = 0                 # a dot that covers the centre seed area
    it, why = to.locate_interior(g, RECT, 0.0, 0.0)
    assert it is not None, why
    assert to.interior_density(g, it) > 0.3


@pytest.mark.parametrize("name", ["open", "none"])
def test_open_or_missing_frame_is_not_a_box(name):
    g = _page_canvas()
    if name == "open":
        _draw_box(g, 100.8, 500.8, 109.2, 509.2, 1.0, gap=("left", 4))
    it, why = to.locate_interior(g, RECT, 0.0, 0.0)
    assert it is None and why == "box_not_closed"


def test_white_space_that_is_not_the_box_is_not_measured():
    g = _page_canvas()
    _draw_box(g, 98.0, 498.0, 114.0, 514.0, 1.0)                              # a frame far bigger than the rect: 16 pt, centred 4 pt away
    it, why = to.locate_interior(g, RECT, 0.0, 0.0)
    assert it is None and why in ("box_geometry", "box_not_closed")
    g = _page_canvas()
    _draw_box(g, 100.5, 503.0, 109.5, 506.0, 0.6)                              # a squashed 9 x 3 slot: not a box
    it, why = to.locate_interior(g, RECT, 0.0, 0.0)
    assert it is None


def test_interior_follows_the_applied_page_shift():
    g = _page_canvas()
    _draw_box(g, 103.8, 497.8, 112.2, 506.2, 1.0)                              # printed (3, -3) pt away from the template position
    assert to.locate_interior(g, RECT, 0.0, 0.0)[0] is None or abs(to.locate_interior(g, RECT, 0.0, 0.0)[0].dcx_pt) > 1
    it, why = to.locate_interior(g, RECT, 3.0, -3.0)
    assert it is not None, why
    assert abs(it.dcx_pt) < 1.0 and abs(it.dcy_pt) < 1.0


def test_pinhole_in_an_inner_frame_does_not_merge_it_with_the_ring_around_it():
    """FORM_DOM_*: the print draws an outer bevel and the template's inner square. A one-pixel gap in the inner
    frame (sub-pixel phase) lets the fill into the ring, whose core holds the inner frame (read as a mark)."""
    g = _page_canvas()
    _draw_box(g, 99.6, 499.6, 110.4, 510.4, 1.0, level=128)          # outer bevel
    _draw_box(g, 101.5, 501.5, 108.5, 508.5, 0.8)                    # the template's inner square
    tpl, _ = to.locate_interior(g, RECT, 0.0, 0.0)
    assert tpl is not None and tpl.w_pt < 6.0                        # the template's own interior is the inner pocket
    r0, c0 = int((792 - 508.5) * K3), int(101.5 * K3)
    g[r0 + 1, c0:c0 + 1] = 255                                       # a pinhole in the inner frame's top-left corner
    g[r0:r0 + 3, c0:c0 + 3] = 255
    merged, _ = to.locate_interior(g, RECT, 0.0, 0.0)                # without the template: the fill escapes into the ring
    guarded, why = to.locate_interior(g, RECT, 0.0, 0.0, tpl)
    assert merged is not None and merged.w_pt > tpl.w_pt * 1.2
    assert guarded is None or guarded.w_pt < tpl.w_pt * 1.2          # with it: pinholes are closed (or the box is not read)


def test_member_whose_box_is_not_found_blocks_the_group(flat_2526):
    """Winner emitted only when every box of its group can be compared: erase one frame edge of a checked box."""
    w = to.load_maps()["2025-26"].fmap["fields"]["HOUS_INTL"]["widgets"][0]
    x0, y0, x1, y1 = w["rect"]
    data = fill_and_flatten("2025-26", {}, {"HOUS_INTL": "/X"}, None)
    assert _values_by_tag(to.extract_overlay(data)).get("HOUS_INTL") == "/X"
    opened = white_out(data, w["template_page"], (x0 + 2, y1 - 2.5, x1 - 2, y1 + 3), pad=0.0)
    out = to.extract_overlay(opened)
    assert "HOUS_INTL" not in _values_by_tag(out)


def test_widget_without_a_template_box_is_read_from_its_core(flat_2526):
    """An N/A option has no box in the template: a check mark alone is measured in the rect's core."""
    fm = to.load_maps()["2025-26"].fmap["fields"]
    tag = next(t for t, f in fm.items() if f["ft"] == "/Btn" and f["question_number"] and len(f["widgets"]) == 3
               and f["widgets"][2]["on_state"].strip() == "/N/A")
    wi = 2
    w = fm[tag]["widgets"][wi]
    doc = pdfium.PdfDocument(flat_2526)
    res = to.match_template(doc)
    q = next(q for q, p in res.page_map.items() if p == w["template_page"])
    c = to.PageCtx(doc, q, w["template_page"], "2025-26", res)
    assert not c.template_has_box(w["rect"])
    assert c.template_has_box(fm[tag]["widgets"][0]["rect"])


def test_interior_core_is_the_central_60_percent_exactly():
    """Pin the measured area: ink in the first core column counts, ink one pixel outside it does not."""
    g = _page_canvas()
    _draw_box(g, 100.8, 500.8, 109.2, 509.2, 1.0)
    it, _ = to.locate_interior(g, RECT, 0.0, 0.0)
    ih, iw = int(round((it.r1 - it.r0) * to.INTERIOR_INSET)), int(round((it.c1 - it.c0) * to.INTERIOR_INSET))
    core_h, core_w = (it.r1 - it.r0) - 2 * ih, (it.c1 - it.c0) - 2 * iw
    g2 = g.copy()
    g2[it.r0 + ih:it.r1 - ih, it.c0 + iw] = 0                                  # the core's first column
    assert abs(to.interior_density(g2, it) - 1.0 / core_w) < 1e-6
    g3 = g.copy()
    g3[it.r0 + ih:it.r1 - ih, it.c0 + iw - 1] = 0                              # one pixel outside the core
    assert to.interior_density(g3, it) == 0.0
    g4 = g.copy()
    g4[it.r0 + ih:it.r1 - ih, it.c0 + iw + core_w - 1] = 0                     # the core's last column
    assert abs(to.interior_density(g4, it) - 1.0 / core_w) < 1e-6


def test_interior_geometry_gates():
    g = _page_canvas()
    _draw_box(g, 100.5, 502.4, 109.5, 507.6, 0.6)                              # 7.7 x 3.9 pt interior: aspect 1.97, not a box
    it, why = to.locate_interior(g, RECT, 0.0, 0.0)
    assert it is None and why == "box_geometry"
    g = _page_canvas()
    _draw_box(g, 103.0, 500.2, 112.6, 509.8, 0.6)                              # a real box whose interior is centred 2.8 pt right of the rect's centre
    it, why = to.locate_interior(g, RECT, 0.0, 0.0)
    assert it is None and why == "box_geometry"


def test_blank_prints_of_both_years_emit_no_checkbox(flat_2425):
    """Template glyphs and bevels inside a box (FORM_DOM_*, ACAD_YR, TUIT_VARY_*) must not read as marks."""
    for data in (flat_2425, fill_and_flatten("2025-26", {}, {})):
        out = to.extract_overlay(data)
        assert not [r for r in out["values"].values() if r.get("lane") == "checkbox" and r["pdf_tag"] not in FILL_BUTTONS and r["pdf_tag"] != "HOUS_SINGLE"]


def test_group_member_with_an_open_frame_blocks_the_winner():
    year = "2025-26"
    f = to.load_maps()[year].fmap["fields"]["AD_TFER"]
    data = fill_and_flatten(year, {}, {"AD_TFER": "/Y"})
    assert _values_by_tag(to.extract_overlay(data)).get("AD_TFER") == "/Y"
    other = next(w for w in f["widgets"] if w["on_state"] != "/Y" and to.PageCtx is not None)
    x0, y0, x1, y1 = other["rect"]
    opened = white_out(data, other["template_page"], (x0 + 1.5, y1 - 2.2, x1 - 1.5, y1 + 3.0), pad=0.0)
    out = to.extract_overlay(opened)
    assert "AD_TFER" not in _values_by_tag(out)
    assert {"box_not_closed", "box_geometry"} & set(_held(out, "AD_TFER"))


def test_lane3_decision_constants_are_what_the_extractor_uses(flat_2526, monkeypatch):
    calls = []
    real = to._is_btn_checked

    def spy(scores, th, mg):
        calls.append((th, mg))
        return real(scores, th, mg)
    monkeypatch.setattr(to, "_is_btn_checked", spy)
    to.extract_overlay(flat_2526)
    assert calls and set(calls) == {(0.04, 0.03)}                              # threshold and radio margin: the measured gap


def test_ink_the_blank_template_already_has_in_a_box_is_not_a_mark(flat_2526, monkeypatch):
    """Pre-printed ink inside the interior (the same in the blank) is subtracted: score = print - blank."""
    assert _values_by_tag(to.extract_overlay(flat_2526)).get("HOUS_SINGLE") == "/X"           # 30% speck: a mark
    real = to._PageCtx.template_interior

    def with_ink(self, key, rect):
        it, _d = real(self, key, rect)
        return it, 0.5
    monkeypatch.setattr(to._PageCtx, "template_interior", with_ink)
    assert "HOUS_SINGLE" not in _values_by_tag(to.extract_overlay(flat_2526))


def test_one_tick_in_a_group_is_a_winner():
    year = "2025-26"
    f = to.load_maps()[year].fmap["fields"]["AD_TFER"]
    one = add_check(fill_and_flatten(year, {}, {}), f["widgets"][1]["template_page"], f["widgets"][1]["rect"])
    assert _values_by_tag(to.extract_overlay(one)).get("AD_TFER") == "/N"


def test_number_cell_with_a_neighbour_row_below_is_read_but_multiline_text_is_not(flat_2526):
    """The multi-line rule belongs to Text: a table neighbour below a number cell is not a second line of it."""
    year = "2025-26"
    fm = to.load_maps()[year].fmap["fields"]
    t = fm["AD_TFER_POLICIES_T"]["widgets"][0]
    x0, y0, x1, y1 = t["rect"]
    data = fill_and_flatten(year, {}, {})
    for k, yy in enumerate((y1 - 10, y1 - 22, y0 - 8)):                        # two lines inside the rect, a third just below it
        data = add_text(data, t["template_page"], x0 + 4, yy, f"line number {k}")
    out = to.extract_overlay(data)
    assert "AD_TFER_POLICIES_T" not in _values_by_tag(out) and "multiline_overflow" in _held(out, "AD_TFER_POLICIES_T")


def test_header_vote_rejects_poorly_fitting_crops_with_literal_floors():
    page = to._template_doc("2025-26")[4]
    g = to.page_geometry(page)
    for dx, dy in [(0.0, 3.0), (0.0, 6.0), (40.0, 0.0), (3.0, 0.0)]:
        assert to.header_year_vote(page, g, 4, dx, dy) is None, (dx, dy)         # fit ratio 1.1-2.6: no vote at all
    assert to.header_year_vote(page, g, 4, 1.5, 0.0) == "2025-26"                  # within the residual search


def _fake_votes(monkeypatch, page_vote):
    real = to.header_year_vote

    def fake(page, g, p, dx=0.0, dy=0.0, *, detail=False):
        if p == 4 and page_vote:
            v = page_vote
            return v if detail else v[0]
        return real(page, g, p, dx, dy, detail=detail)
    monkeypatch.setattr(to, "header_year_vote", fake)


def test_only_a_confident_vote_can_hold_a_packet(rich_2526, monkeypatch):
    data = rich_2526[0]
    _fake_votes(monkeypatch, ("2024-25", 0.1, 0.03, 0.7))            # margin ok, fit ratio 0.7: a weak vote
    assert to.match_template(data).status == to.STATUS_MATCHED
    _fake_votes(monkeypatch, ("2024-25", 0.1, 0.015, 0.4))           # good fit, margin 0.015: weak
    assert to.match_template(data).status == to.STATUS_MATCHED
    _fake_votes(monkeypatch, ("2024-25", 0.05, 0.03, 0.4))           # margin >= 0.02 and ratio <= 0.6: confident
    assert to.match_template(data).reason == "mixed_year_packet"


def test_a_page_that_fails_alignment_does_not_vote(rich_2526, monkeypatch):
    data = rich_2526[0]
    _fake_votes(monkeypatch, ("2024-25", 0.05, 0.03, 0.4))
    real = to.estimate_page_alignment
    calls = []

    def bad_for_page_4(m):
        est = real(m)
        calls.append(1)
        if len(calls) == 5:                                          # the fifth matched page, template page 4
            est = dict(est, consistent=False, inconsistent_reason="partial_page_shift")
        return est
    monkeypatch.setattr(to, "estimate_page_alignment", bad_for_page_4)
    res = to.match_template(data)
    assert res.status == to.STATUS_MATCHED and res.header_votes == {"2025-26": 48}


def test_read_widget_text_keeps_pdfium_generated_spaces_below_the_line():
    chars = [to.PageChar("a", 10, 10, 12), to.PageChar("b", 15, 10, 17), to.PageChar(" ", 20, 6.5, 20, generated=True),
             to.PageChar("c", 25, 10, 27), to.PageChar("d", 30, 10, 32)]
    assert to.read_widget_text(chars, [8.0, 8.0, 34.0, 12.0])[0] == "ab cd"          # the space sits 3.5 pt under the glyph centres


def test_sub_point_prints_keep_every_check_and_emit_no_wrong_box(rich_2526):
    """Real prints sit at arbitrary sub-point phases: every box read must be right at every phase, and the
    checks must still be found (v0.2.0 lost 1-4% of them and emitted two wrong ones at these offsets)."""
    data, text, btn = rich_2526
    ref = to.extract_overlay(data)
    found0 = sum(1 for t, v in btn.items() if _values_by_tag(ref).get(t) == v)
    assert found0 >= 0.6 * len(btn)       # the fixture's synthetic marks are heavy; some fill the box and abstain
    for dx, dy in [(0.33, 0), (-0.5, 0), (0, 0.5), (0.5, -0.33), (-0.33, -0.5)]:
        out = to.extract_overlay(translate_pages(data, dx, dy))
        assert out["notes"]["stage1"]["status"] == "matched"
        assert wrong_values(out, text, btn) == [], (dx, dy)
        found = sum(1 for t, v in btn.items() if _values_by_tag(out).get(t) == v)
        assert found >= 0.85 * found0, (dx, dy, found, found0)       # the phase does not decide what is found (the fixture's heavy marks make a few boxes phase-sensitive; the real cohort harness measures 0.1-0.5% loss)


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
    # v0.3.0 numbers: every /Btn of both controls read right (Miami ACAD_YR included), no checkbox emitted wrongly
    assert results["valpo"]["by_type"]["Btn"][0] == 139 and results["miami"]["by_type"]["Btn"][0] == 152
    assert results["valpo"]["ok"] >= 614 and not [m for m in results["miami"]["misses"] if m.get("got") is not None]


# ==========================================================================
# Round 3 (v0.4.0): emission classes, tint, two marks, strokes, numeric tokens, free-text straddle,
# duplicate pages, weak other-year pages, and the four behaviours the verifier's mutations showed untested.
# Every fixture here is a reviewer counterexample or a surviving mutation; each has its positive control.
# ==========================================================================

def add_ops(data: bytes, page_index: int, ops: str, *, behind: bool = False, alpha: float | None = None) -> bytes:
    """Append (or, with `behind`, prepend) raw content-stream operators to one page; `alpha` draws them translucent."""
    w = _writer_from(data)
    page = w.pages[page_index]
    pre = ""
    if alpha is not None:
        res = page["/Resources"]
        egs = res.get("/ExtGState")
        egs = egs.get_object() if egs is not None else DictionaryObject()
        egs[NameObject("/FxAlpha")] = DictionaryObject({NameObject("/ca"): FloatObject(alpha)})
        res[NameObject("/ExtGState")] = egs
        pre = "/FxAlpha gs\n"
    part = _raw(w, f"\nq\n{pre}{ops}\nQ\n".encode())
    parts = _contents_parts(page)
    page[NameObject("/Contents")] = ArrayObject(([part] + parts) if behind else (parts + [part]))
    return _write(w)


def _op_line(x0, y0, x1, y1, width=0.6) -> str:
    return f"0 G {width} w {x0} {y0} m {x1} {y1} l S\n"


def _op_tick(r, width=0.6) -> str:
    x0, y0, x1, y1 = r
    w, h = x1 - x0, y1 - y0
    return (f"0 G {width} w {x0 + .2 * w} {y0 + .5 * h} m {x0 + .42 * w} {y0 + .2 * h} l {x0 + .85 * w} {y0 + .85 * h} l S\n")


def _op_erase(r, pad=0.0) -> str:
    x0, y0, x1, y1 = r
    return f"1 g {x0 - pad} {y0 - pad} {x1 - x0 + 2 * pad} {y1 - y0 + 2 * pad} re f\n"


def _op_frame(r, inset=0.0, width=0.5, fill=None) -> str:
    x0, y0, x1, y1 = r[0] + inset, r[1] + inset, r[2] - inset, r[3] - inset
    if fill is not None:
        return f"{fill} g {x0} {y0} {x1 - x0} {y1 - y0} re f\n"
    return f"0 G {width} w {x0} {y0} {x1 - x0} {y1 - y0} re S\n"


@pytest.fixture(scope="module")
def blank_2526() -> bytes:
    return fill_and_flatten("2025-26", {}, {})


def _fm(tag: str, year: str = "2025-26"):
    return to.load_maps()[year].fmap["fields"][tag]


# ---- A. emission classes --------------------------------------------------

def test_every_value_carries_an_emission_class_and_serving_filters_by_it(flat_2526):
    out = to.extract_overlay(flat_2526)
    vals = out["values"]
    assert vals and all(r.get("emission_class") for r in vals.values())
    by_tag = {r["pdf_tag"]: r["emission_class"] for r in vals.values() if "pdf_tag" in r}
    assert by_tag["AP_RECD_1ST_MEN_N"] == "numeric" and by_tag["CDS_NAME"] == "free_text" and by_tag["HOUS_INTL"] == "checkbox_box"
    assert out["notes"]["emission_class_counts"]["numeric"] >= 1
    served = to.serve_values(vals)
    assert to.SERVE_CLASSES_DEFAULT == {"numeric", "choice", "checkbox_box"}
    assert "CDS_NAME" not in {r.get("pdf_tag") for r in served.values()} and "AP_RECD_1ST_MEN_N" in {r.get("pdf_tag") for r in served.values()}
    assert to.serve_values(vals, {"free_text"}).keys() == {k for k, r in vals.items() if r["emission_class"] == "free_text"}
    assert to.serve_values({"1": {"value": "x"}}) == {}                           # a record with no class is never served


def test_boxless_option_and_dropdown_and_derived_total_classes(flat_2526):
    fm = to.load_maps()["2025-26"].fmap["fields"]
    tag = next(t for t, f in fm.items() if f["ft"] == "/Btn" and f["question_number"] and len(f["widgets"]) == 3
               and f["widgets"][2]["on_state"].strip() == "/N/A")
    w = fm[tag]["widgets"][2]
    out = to.extract_overlay(add_check(fill_and_flatten("2025-26", {}, {}), w["template_page"], w["rect"]))
    rec = next(r for r in out["values"].values() if r.get("pdf_tag") == tag)
    assert rec["value"].strip() == "/N/A" and rec["emission_class"] == "checkbox_boxless"
    assert to.serve_values({"1": rec}) == {}                                      # shadow-only by default
    assert to.emission_class_text("Text", "/Ch") == "choice" and to.emission_class_text("Text", "/Tx") == "free_text"
    for et in ("Number", "Dollars", "Percent", "Identifier", "Month", "Day"):
        assert to.emission_class_text(et, "/Tx") == "numeric"
    text, _btn = rich_fill("2025-26")
    out = to.extract_overlay(fill_and_flatten("2025-26", text, {}))
    assert out["notes"]["b1_all_totals_derived"] >= 0 and all(r.get("emission_class") for r in out["values"].values())


# ---- B. L1: a uniform tint is not ink ---------------------------------------

def test_ink_only_density_ignores_a_uniform_tint():
    for level in (255, 242, 235, 228):                                            # paper, 5% veil, 8%, 10%: all at or above INTERIOR_WHITE
        g = _page_canvas() * 0 + level
        g = g.astype(np.uint8)
        _draw_box(g, 100.8, 500.8, 109.2, 509.2, 1.0, level=0)
        it, why = to.locate_interior(g, RECT, 0.0, 0.0)
        assert it is not None, (level, why)
        assert to.interior_density(g, it) == 0.0, level
    g = _page_canvas()
    _draw_box(g, 100.8, 500.8, 109.2, 509.2, 1.0)
    _draw_check(g, 105.0, 505.0, 5.0)
    it, _ = to.locate_interior(g, RECT, 0.0, 0.0)
    assert to.interior_density(g, it) >= 0.08                                     # a real mark is unchanged
    patch = np.full((12, 12), 235, dtype=np.uint8)
    assert to._ink_density(patch) == 0.0 and to._crop_density is not None          # the boxless path measures the same way
    old = to.INK_ONLY_DENSITY
    to.INK_ONLY_DENSITY = False
    try:
        assert to._ink_density(patch) > 0.07                                       # the old mean read a tint as ink
    finally:
        to.INK_ONLY_DENSITY = old


@pytest.mark.parametrize("name,kw", [("paper_tint_0.93", dict(behind=True)), ("veil_8pct", dict(alpha=0.08))])
def test_tinted_prints_emit_no_wrong_checkbox(rich_2526, name, kw):
    data, text, btn = rich_2526
    n = _page_count(data)
    ops = "0.93 g 0 0 612 792 re f" if kw.get("behind") else "0 g 0 0 612 792 re f"
    tinted = data
    for i in range(n):
        tinted = add_ops(tinted, i, ops, **kw)
    out = to.extract_overlay(tinted)
    assert out["notes"]["stage1"]["status"] == "matched", out["notes"]["stage1"]
    assert wrong_values(out, text, btn) == [], name
    found = sum(1 for t, v in btn.items() if _values_by_tag(out).get(t) == v)
    assert found >= 0.5 * len(btn), (name, found, len(btn))                       # the marks themselves are still read


def test_without_ink_only_density_a_tint_does_emit_wrong_boxes(rich_2526):
    """(the fixture is not vacuous: the v0.3.0 measure emits on it)"""
    data, text, btn = rich_2526
    tinted = data
    for i in range(_page_count(data)):
        tinted = add_ops(tinted, i, "0.93 g 0 0 612 792 re f", behind=True)
    old = to.INK_ONLY_DENSITY
    to.INK_ONLY_DENSITY = False
    try:
        out = to.extract_overlay(tinted)
        assert len(wrong_values(out, text, btn)) >= 5
    finally:
        to.INK_ONLY_DENSITY = old


# ---- C. B4: two marked options ----------------------------------------------

@pytest.mark.parametrize("widths", [(1.1, 0.4), (1.1, 0.6), (0.7, 0.7)])
def test_two_ticks_in_one_group_abstain_whatever_their_strength(blank_2526, widths):
    f = _fm("AD_TFER")
    q = f["widgets"][0]["template_page"]
    data = add_ops(blank_2526, q, _op_tick(f["widgets"][0]["rect"], widths[0]) + _op_tick(f["widgets"][1]["rect"], widths[1]))
    out = to.extract_overlay(data)
    assert "AD_TFER" not in _values_by_tag(out) and _held(out, "AD_TFER") == ["multiple_options_marked"]
    assert [a["reason"] for a in out["notes"]["ambiguous_radios"] if a["pdf_tag"] == "AD_TFER"] == ["multiple_options_marked"]


def test_one_tick_in_a_group_still_wins_with_the_other_option_empty(blank_2526):
    f = _fm("AD_TFER")
    data = add_ops(blank_2526, f["widgets"][0]["template_page"], _op_tick(f["widgets"][0]["rect"], 1.1))
    assert _values_by_tag(to.extract_overlay(data))["AD_TFER"] == f["widgets"][0]["on_state"]


# ---- D. B3: a stroke that leaves the box --------------------------------------

def _hous_intl(blank, ops):
    w = _fm("HOUS_INTL")["widgets"][0]
    return to.extract_overlay(add_ops(blank, w["template_page"], ops)), w["rect"]


@pytest.mark.parametrize("name", ["row_strike", "underline", "overflow_text", "strike_left_only"])
def test_ink_that_continues_beyond_the_box_is_not_a_mark(blank_2526, name):
    w = _fm("HOUS_INTL")["widgets"][0]
    x0, y0, x1, y1 = w["rect"]
    cy = (y0 + y1) / 2
    if name == "row_strike":
        out, _ = _hous_intl(blank_2526, _op_line(x0 - 25, cy, x1 + 110, cy))
    elif name == "underline":
        out, _ = _hous_intl(blank_2526, _op_line(x0 - 20, cy - 1, x1 + 90, cy - 1))
    elif name == "strike_left_only":
        out, _ = _hous_intl(blank_2526, _op_line(x0 - 30, cy, x1 - 1, cy))
    else:
        data = add_text(blank_2526, w["template_page"], x0 - 9, cy - 2, "continued")
        out = to.extract_overlay(data)
    assert "HOUS_INTL" not in _values_by_tag(out), name
    assert _held(out, "HOUS_INTL") == ["stroke_continues_beyond_box"], (name, _held(out, "HOUS_INTL"))


def test_real_marks_that_stay_in_or_near_the_box_are_still_read(blank_2526):
    w = _fm("HOUS_INTL")["widgets"][0]
    x0, y0, x1, y1 = w["rect"]
    for name, ops in [("tick", _op_tick(w["rect"])),
                      ("tick_overshoots_frame", f"0 G 0.8 w {x0 + 2} {(y0 + y1) / 2} m {x0 + 4.5} {y0 + 1.5} l {x1 + 2.2} {y1 + 2.0} l S\n"),
                      ("cross", _op_line(x0 + 2, y0 + 2, x1 - 2, y1 - 2) + _op_line(x0 + 2, y1 - 2, x1 - 2, y0 + 2))]:
        out, _ = _hous_intl(blank_2526, ops)
        assert _values_by_tag(out).get("HOUS_INTL") == "/X", (name, _held(out, "HOUS_INTL"))
    data = add_text(blank_2526, w["template_page"], x0 + 2.3, y0 + 2.3, "X", size=8)    # a typed X inside the box
    assert _values_by_tag(to.extract_overlay(data)).get("HOUS_INTL") == "/X"


def test_a_shaded_empty_box_is_not_a_selection(blank_2526):
    w = _fm("HOUS_INTL")["widgets"][0]
    out, _ = _hous_intl(blank_2526, _op_erase(w["rect"], 1) + _op_frame(w["rect"], 0.9, 0.5) + _op_frame(w["rect"], 1.3, fill=0.9))
    assert "HOUS_INTL" not in _values_by_tag(out)


def test_stroke_guard_unit_on_a_canvas():
    g = _page_canvas()
    _draw_box(g, 100.8, 500.8, 109.2, 509.2, 1.0)
    t = _page_canvas()
    _draw_box(t, 100.8, 500.8, 109.2, 509.2, 1.0)
    it, _ = to.locate_interior(g, RECT, 0.0, 0.0)
    assert to.stroke_continues(g, t, it, 0.0, 0.0) is None
    r = int((792 - 505) * K3)
    g2 = g.copy()
    g2[r:r + 2, int(112 * K3):int(135 * K3)] = 0                                   # a line leaving the box to the right
    assert to.stroke_continues(g2, t, it, 0.0, 0.0) == "stroke_continues_beyond_box"
    g3 = g.copy()
    g3[r:r + 2, int(98 * K3):int(101 * K3)] = 0                                    # a tick's tail just outside the frame: not a stroke
    assert to.stroke_continues(g3, t, it, 0.0, 0.0) is None
    t2 = t.copy()
    t2[r:r + 2, int(112 * K3):int(135 * K3)] = 0                                   # the same ink printed on the blank is the form's own
    assert to.stroke_continues(g2, t2, it, 0.0, 0.0) is None


# ---- E. B1/B2 (Codex): numeric tokens, defined on boxes -----------------------

def _tb(s: str, x0: float, base: float = 10.0, size: float = 10.0, gap: float = 0.0):
    """Tight boxes for a string set in `size`: digits 0.72 high, 0.55 wide with side bearing; points small and low."""
    out, x = [], x0
    for c in s:
        if c.isdigit():
            out.append(to.GlyphBox(x + 0.06 * size, x + 0.5 * size, base + 0.36 * size, base + 0.72 * size, base, c))
            x += 0.556 * size + gap
        elif c in ".,":
            out.append(to.GlyphBox(x + 0.08 * size, x + 0.2 * size, base + 0.05 * size, base + 0.1 * size, base - 0.0, c))
            x += 0.278 * size + gap
        elif c == "-":
            out.append(to.GlyphBox(x + 0.04 * size, x + 0.29 * size, base + 0.25 * size, base + 0.28 * size, base + 0.22 * size, c))
            x += 0.333 * size + gap
        else:
            x += 0.278 * size
    return out


RECT_N = [100.0, 5.0, 160.0, 20.0]


@pytest.mark.parametrize("size", [3.0, 6.0, 10.0, 12.0, 16.0])
def test_numeric_token_gate_reads_a_uniform_number_at_any_size(size):
    assert to.numeric_token_gate(_tb("1234", 110, size=size), RECT_N) is None
    assert to.numeric_token_gate(_tb("1,234.5", 110, size=size), RECT_N) is None
    second = 160 - 3 * 0.556 * size - 3.0
    assert to.numeric_token_gate(_tb("12", 102, size=size) + _tb("345", second, size=size), RECT_N) is None   # two tokens a word space apart, both inside


@pytest.mark.parametrize("size", [8.0, 12.0, 16.0])
@pytest.mark.parametrize("phase", [0.0, 0.25, 0.5, 0.75, 1.0, 1.5])
def test_numeric_token_gate_withholds_a_string_cut_by_the_rect(size, phase):
    glyphs = _tb("24038", 100 + 60 - 2.3 * size * 0.556 + phase, size=size)        # the string runs across the rect's right edge
    assert any(g.cx > 160 for g in glyphs) and any(g.cx < 160 for g in glyphs)
    assert to.numeric_token_gate(glyphs, RECT_N) == "token_crosses_rect"
    left = _tb("24038", 100 - 2.3 * size * 0.556 + phase, size=size)               # ... or its left edge
    assert to.numeric_token_gate(left, RECT_N) == "token_crosses_rect"


@pytest.mark.parametrize("size", [8.0, 10.0, 14.0])
def test_numeric_token_gate_attaches_punctuation_by_vertical_extent_not_centre(size):
    inside = _tb("1234", 101, size=size)
    point = to.GlyphBox(100 - 0.12 * size, 100 + 0.04 * size, 10.0 + 0.05 * size, 10.0 + 0.1 * size, 10.0, ".")    # a decimal point crossing the left edge
    assert to.numeric_token_gate(inside + [point], RECT_N) == "token_crosses_rect"                                # its centre is far below the digits'
    sign = to.GlyphBox(100 - 0.3 * size, 100 - 0.05 * size, 10.0 + 0.265 * size, 10.0 + 0.28 * size, 10.0 + 0.22 * size, "-")
    assert to.numeric_token_gate(_tb("1234", 101, size=size) + [sign], RECT_N) == "token_crosses_rect"             # a minus just outside the rect
    far = to.GlyphBox(60.0, 64.0, 10.0 + 0.265 * size, 10.0 + 0.28 * size, 10.0 + 0.22 * size, "-")
    assert to.numeric_token_gate(inside + [far], RECT_N) is None                                                   # a dash a field away is not a sign


@pytest.mark.parametrize("raised", [5.0, 3.0, 1.5])
def test_numeric_token_gate_withholds_a_footnote_marker_but_not_a_small_uniform_font(raised):
    digits = _tb("1234", 110, size=10.0)
    marker = _tb("1", 110 + 4 * 5.56, base=10.0 + raised, size=5.0)
    assert to.numeric_token_gate(digits + marker, RECT_N) == "mixed_glyph_size"
    assert to.numeric_token_gate(_tb("1234", 110, size=3.0), RECT_N) is None


def test_numeric_gate_boxes_need_nothing_from_the_text_layer():
    """Lane 2 reuse: an OCR word box (whole word, a box, no per-character data) goes through the same function."""
    word = to.GlyphBox(110.0, 132.2, 13.6, 17.2, 10.0, "1234")
    assert to.numeric_token_gate([word], RECT_N) is None
    cut = to.GlyphBox(150.0, 172.2, 13.6, 17.2, 10.0, "1234")
    assert to.numeric_token_gate([cut], RECT_N) == "token_crosses_rect" or to.numeric_token_gate([cut], RECT_N) is None
    neighbour = to.GlyphBox(160.5, 175.0, 13.6, 17.2, 10.0, "99")
    assert to.numeric_token_gate([word, neighbour], RECT_N) is None


def _numeric_pdf(blank, tag, runs):
    """Draw text runs [(dx_from_rect_left, dy_from_rect_bottom, text, size)] next to a numeric widget."""
    w = _fm(tag)["widgets"][0]
    x0, y0 = w["rect"][0], w["rect"][1]
    data = blank
    for dx, dy, txt, size in runs:
        data = add_text(data, w["template_page"], x0 + dx, y0 + dy, txt, size=size)
    return to.extract_overlay(data)


def _codex_runs(name: str, size: float, ofs: float):
    """Codex's numeric counterexamples scaled to a font size: positions in glyph advances, shifted by `ofs` pt."""
    a = 0.556 * size
    if name in ("superscript", "footnote_low"):
        lift = 0.5 * size if name == "superscript" else 0.3 * size
        return [(5 + ofs, 5, "1234", size), (5 + ofs + 4 * a, 5 + lift, "1", 0.5 * size)]
    off = {"decimal_crosses_edge": -0.18 * size, "decimal_outside": -0.3 * size, "minus_outside": -0.5 * size}[name]
    return [(off + ofs, 5, "." if name.startswith("decimal") else "-", size), (0.2 * size + ofs, 5, "1234", size)]


@pytest.mark.parametrize("size", [6.0, 10.0, 14.0])
@pytest.mark.parametrize("ofs", [-0.25, 0.0, 0.3])
@pytest.mark.parametrize("name", ["superscript", "footnote_low", "decimal_crosses_edge", "decimal_outside", "minus_outside"])
def test_codex_numeric_counterexamples_are_withheld(blank_2526, name, size, ofs):
    out = _numeric_pdf(blank_2526, "AP_RECD_1ST_MEN_N", _codex_runs(name, size, ofs))
    assert "AP_RECD_1ST_MEN_N" not in _values_by_tag(out), (name, size, ofs, _values_by_tag(out).get("AP_RECD_1ST_MEN_N"))
    held = _held(out, "AP_RECD_1ST_MEN_N")
    assert held and held[0] in ("token_crosses_rect", "mixed_glyph_size", "glyph_crosses_left_edge", "glyph_past_left_edge",
                                "glyph_crosses_right_edge", "glyph_past_right_edge"), held     # the older edge test may stop it first at a small size


@pytest.mark.parametrize("name,runs,want", [
    ("plain", [(5, 5, "1234", 10)], "1234"),
    ("tiny_uniform_3pt", [(5, 5, "1234", 3)], "1234"),
    ("percent", [(5, 5, "12%", 10)], "12"),
])
def test_codex_numeric_positive_controls_are_read(blank_2526, name, runs, want):
    assert _values_by_tag(_numeric_pdf(blank_2526, "AP_RECD_1ST_MEN_N", runs)).get("AP_RECD_1ST_MEN_N") == want


@pytest.mark.parametrize("size", [8.0, 12.0, 16.0])
def test_a_string_across_two_financial_aid_cells_emits_in_neither_at_any_phase(blank_2526, size):
    """Codex B1: 24038 across SCHOL_NB_FED_D | SCHOL_NN_FED_D, swept through every glyph phase of the gutter."""
    a, z = _fm("SCHOL_NB_FED_D")["widgets"][0], _fm("SCHOL_NN_FED_D")["widgets"][0]
    data = blank_2526
    for k in range(-8, 9):
        x = a["rect"][2] - 2.3 * size * 0.556 + k * 0.25
        out = to.extract_overlay(add_text(data, a["template_page"], x, a["rect"][1] + 5, "24038", size=size))
        vals = _values_by_tag(out)
        assert vals.get("SCHOL_NN_FED_D") is None and vals.get("SCHOL_NB_FED_D") is None, (size, k, vals.get("SCHOL_NB_FED_D"), vals.get("SCHOL_NN_FED_D"))


# ---- F. free text: a line cut by the rect's top or bottom ----------------------

def test_line_straddles_rect_unit():
    rect = [100.0, 5.0, 200.0, 17.0]
    inside = [to.GlyphBox(102 + 5 * i, 106 + 5 * i, 11.0, 14.0, 8.0, "a") for i in range(8)]
    assert to.line_straddles_rect(inside, rect) is None
    cut = [to.GlyphBox(102 + 5 * i, 106 + 5 * i, 16.5 if i % 2 else 17.6, 20.0, 13.0, "a") for i in range(8)]   # centres on both sides of the top edge
    assert to.line_straddles_rect(cut, rect) == "line_straddles_rect"
    above = [to.GlyphBox(102 + 5 * i, 106 + 5 * i, 24.0, 27.0, 21.0, "a") for i in range(8)]                 # a whole line above: not a straddle
    assert to.line_straddles_rect(inside + above, rect) is None


def test_free_text_line_cut_by_the_rect_edge_is_withheld(blank_2526):
    w = _fm("ROTC_NAVY_TEXT")["widgets"][0]
    x0, y0, x1, y1 = w["rect"]
    ok = to.extract_overlay(add_text(blank_2526, w["template_page"], x0 + 4, (y0 + y1) / 2 - 3, "Alumni affiliation"))
    assert _values_by_tag(ok).get("ROTC_NAVY_TEXT") == "Alumni affiliation"
    cut = to.extract_overlay(add_text(blank_2526, w["template_page"], x0 + 4, y1 - 3.0, "Alumni affiliation"))
    assert "ROTC_NAVY_TEXT" not in _values_by_tag(cut) and _held(cut, "ROTC_NAVY_TEXT") == ["line_straddles_rect"]
    cut2 = to.extract_overlay(add_text(blank_2526, w["template_page"], x0 + 4, y0 - 1.8, "gypsy angry guppy"))      # descenders fall below the bottom edge
    assert "ROTC_NAVY_TEXT" not in _values_by_tag(cut2) and _held(cut2, "ROTC_NAVY_TEXT") == ["line_straddles_rect"]


# ---- G. B5: duplicate pages ------------------------------------------------------

@pytest.mark.parametrize("size", [3, 5, 10])
def test_duplicate_pages_that_differ_by_one_digit_conflict_at_any_font_size(blank_2526, size):
    tag = "AP_RECD_1ST_MEN_N"
    w = _fm(tag)["widgets"][0]
    q = w["template_page"]
    first = add_text(blank_2526, q, w["rect"][0] + 5, w["rect"][1] + 5, "1234", size=size)
    second = add_text(blank_2526, q, w["rect"][0] + 5, w["rect"][1] + 5, "1235", size=size)
    packet = assemble([(first, i) for i in range(50)] + [(second, q)])
    res = to.match_template(packet, align=False)
    assert res.rejected_template_pages == {q: "duplicate_page_conflict"}
    assert tag not in _values_by_tag(to.extract_overlay(packet))
    same = assemble([(first, i) for i in range(50)] + [(first, q)])
    assert not to.match_template(same, align=False).rejected_template_pages
    assert _values_by_tag(to.extract_overlay(same)).get(tag) == "1234"            # the positive control


def test_duplicate_pages_that_differ_in_a_checkbox_conflict(blank_2526):
    f = _fm("HOUS_INTL")
    q = f["widgets"][0]["template_page"]
    ticked = add_ops(blank_2526, q, _op_tick(f["widgets"][0]["rect"], 0.3))
    packet = assemble([(blank_2526, i) for i in range(50)] + [(ticked, q)])
    assert to.match_template(packet, align=False).rejected_template_pages == {q: "duplicate_page_conflict"}


def _rasterise(data: bytes, page: int) -> bytes:
    img = pdfium.PdfDocument(data)[page].render(scale=3).to_pil().convert("RGB")
    buf = io.BytesIO()
    img.save(buf, format="PDF", resolution=216)
    return buf.getvalue()


def test_raster_only_duplicates_compare_ink_and_abstain_when_equality_is_not_established(blank_2526):
    tag = "AP_RECD_1ST_MEN_N"
    w = _fm(tag)["widgets"][0]
    q = w["template_page"]
    a = add_text(blank_2526, q, w["rect"][0] + 5, w["rect"][1] + 5, "1234", size=10)
    b = add_text(blank_2526, q, w["rect"][0] + 5, w["rect"][1] + 5, "1235", size=10)
    ra, rb = _rasterise(a, q), _rasterise(b, q)
    conflict = assemble([(a, i) if i != q else (ra, 0) for i in range(50)] + [(rb, 0)])
    assert to.match_template(conflict, align=False).rejected_template_pages == {q: "duplicate_page_conflict"}
    same = assemble([(a, i) if i != q else (ra, 0) for i in range(50)] + [(ra, 0)])
    assert not to.match_template(same, align=False).rejected_template_pages
    mixed = assemble([(a, i) for i in range(50)] + [(ra, 0)])      # a native page and a raster copy of it: not the same evidence
    res = to.match_template(mixed, align=False)
    assert res.status == to.STATUS_MATCHED


# ---- H. N1: a weak other-year page is excluded without holding the packet -------

def test_weak_other_year_page_is_excluded_and_does_not_hold_the_packet(rich_2425, rich_2526):
    d25, d26 = rich_2425[0], rich_2526[0]
    hb = to._header_boxes()[7]
    # the 2025-26 page 7 printed with its header 2.3 pt high: its header still reads 2025-26 but weakly
    w = _writer_from(fill_and_flatten("2025-26", {}, {}))
    _shift_region_of_page(w, w.pages[7], (hb[0] - 8, hb[1] - 8, hb[2] - hb[0] + 16, hb[3] - hb[1] + 16), 0, 2.3)
    page7 = _write(w)
    packet = assemble([(page7 if i == 7 else d25, i) for i in range(50)])
    res = to.match_template(packet)
    assert res.status == to.STATUS_MATCHED and res.year == "2024-25"
    assert res.rejected_pages.get(7) == "weak_other_year_vote" and 7 not in res.page_map
    assert res.header_votes.get("2025-26") == 1 and res.header_confident.get("2025-26", 0) == 0
    out = to.extract_overlay(packet)
    assert out["notes"]["page_map"].get("7") is None
    assert wrong_values(out, *rich_2425[1:]) == []
    old = to.WEAK_VOTE_EXCLUDE
    to.WEAK_VOTE_EXCLUDE = False
    try:
        assert 7 in to.match_template(packet).page_map                              # without the rule the page is read through the other year's map
    finally:
        to.WEAK_VOTE_EXCLUDE = old


# ---- I. behaviours the verifier's mutations showed untested ----------------------

def test_band_majority_tolerance_is_one_point(monkeypatch):
    """SHIFT_AGREE_PT: most inked bands agreeing on a shift two points from the applied one reject the page; one point is tolerated."""
    page = to._template_doc("2025-26")[27]
    m = to._page_masks(page, to.page_geometry(page), page)
    def fake(dx):
        def descend(g, ty, tx, rng, base=(0, 0)):
            return (0.9, 0, 0) if rng == to.ALIGN_SEARCH_PT else (0.9, dx, 0)
        return descend
    monkeypatch.setattr(to, "_descend", fake(2))
    est = to.estimate_page_alignment(m)
    assert not est["consistent"] and est["inconsistent_reason"] == "residual_page_shift"
    monkeypatch.setattr(to, "_descend", fake(1))
    assert to.estimate_page_alignment(m)["consistent"]
    assert to.SHIFT_AGREE_PT == 1


def test_ocr_widgets_carry_the_pages_applied_shift(flat_2526):
    q = 12
    data = add_text(translate_pages(flat_2526, 3.0, -2.0, [q]), q, 455, 375.5, "9876", render_mode=3)
    out = to.extract_overlay(data)
    item = next(w for w in out["notes"]["ocr_widgets"] if w["pdf_tag"] == "AP_RECD_1ST_MEN_N")
    assert item["page"] == q and item["template_page"] == 12
    assert item["shift"] == {"dx": 3.0, "dy": -2.0}, item["shift"]


def test_interior_smaller_than_a_box_is_not_a_box():
    g = _page_canvas()
    _draw_box(g, 102.8, 502.8, 107.2, 507.2, 1.0)                                    # a 2.4 pt interior: a dot, not a box
    it, why = to.locate_interior(g, RECT, 0.0, 0.0)
    assert it is None and why == "box_geometry"
    assert to.INTERIOR_MIN_PT == 2.5


def test_group_member_whose_box_is_not_box_shaped_blocks_the_winner(blank_2526):
    f = _fm("AD_TFER")
    yes, no = f["widgets"]
    q = yes["template_page"]
    x0, y0, x1, y1 = no["rect"]
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    flat_box = [cx - 4.5, cy - 1.6, cx + 4.5, cy + 1.6]                              # a closed frame, three times wider than high
    ops = _op_tick(yes["rect"], 1.1) + _op_erase(no["rect"], 2.0) + _op_frame(flat_box, 0.0, 0.5)
    out = to.extract_overlay(add_ops(blank_2526, q, ops))
    assert "AD_TFER" not in _values_by_tag(out) and "box_geometry" in _held(out, "AD_TFER"), _held(out, "AD_TFER")


def test_speck_in_hous_single_still_reads_as_a_mark(flat_2526):
    """(unchanged by round 3: the 30% speck is far above the threshold; the ink-only measure, the two-mark and stroke rules do not touch it)"""
    out = to.extract_overlay(flat_2526)
    assert _values_by_tag(out).get("HOUS_SINGLE") == "/X"


def test_digits_of_one_size_on_two_baselines_are_withheld():
    """BASELINE_MAX_SHIFT: a footnote number set in the same size but raised is still not part of the count."""
    digits = _tb("1234", 110, size=10.0)
    raised = _tb("1", 110 + 4 * 5.56, base=10.0 + 3.0, size=10.0)
    assert to.numeric_token_gate(digits + raised, RECT_N) == "mixed_glyph_size"
    assert to.numeric_token_gate(digits + _tb("1", 110 + 4 * 5.56, base=10.0 + 1.0, size=10.0), RECT_N) is None     # 1 pt of drift is one line


def test_raster_only_duplicates_differing_in_a_3pt_digit_conflict(blank_2526):
    """DUPLICATE_RASTER_DPI: a one-digit change at 3 pt is invisible to a 72 DPI raster."""
    w = _fm("AP_RECD_1ST_MEN_N")["widgets"][0]
    q = w["template_page"]
    a = add_text(blank_2526, q, w["rect"][0] + 5, w["rect"][1] + 5, "1234", size=3)
    b = add_text(blank_2526, q, w["rect"][0] + 5, w["rect"][1] + 5, "1235", size=3)
    ra, rb = _rasterise(a, q), _rasterise(b, q)
    packet = assemble([(a, i) if i != q else (ra, 0) for i in range(50)] + [(rb, 0)])
    assert to.match_template(packet, align=False).rejected_template_pages == {q: "duplicate_page_conflict"}


@pytest.mark.parametrize("dpi", [180, 200, 288])
def test_stroke_guard_does_not_raise_at_other_render_resolutions(flat_2526, monkeypatch, dpi):
    """A crash here kills the whole document: the print's and the blank's crops can differ by a pixel (dpi 180 raised a shape error)."""
    monkeypatch.setattr(to, "INK_DPI", dpi)
    out = to.extract_overlay(flat_2526)
    assert out["notes"]["stage1"]["status"] == "matched" and _values_by_tag(out)       # no exception; what is read at 180 DPI is a recall matter, not tested here
