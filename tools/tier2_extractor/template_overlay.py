#!/usr/bin/env python3
"""Template overlay extraction for flattened official CDS PDFs (PRD 038, M1).

A pure library: bytes in, JSON-able dict out. No database, network or worker
access. Scope is Stage 1 (template match), Lane 1 (text layer) and Lane 3
(checkboxes and radios) plus validation. Lane 2 (crop OCR) is M2 and the
worker/DB wiring is M3; pages and widgets that need OCR are reported in
`notes.pages_needing_ocr` / `notes.ocr_widgets` so M2 has a seam.

Governing rule: a missing value is acceptable, a wrong emitted value is not.
Every check below therefore abstains (recording the reason in `notes.withheld`
or `notes.rejected_fields`) instead of guessing.

Public API:
    load_maps()                      committed field maps with decoded masks
    match_template(pdf, ...)         Stage 1: which official template, which year
    extract_overlay(pdf, ...)        Stage 1 + Lanes 1 and 3 + validation
    serve_values(values, classes)    the values whose `emission_class` is served (SERVE_CLASSES_DEFAULT)
Lane 2 seam (reused by M2): PageCtx, widget_gates, GlyphBox, glyph_boxes, edge_continuation,
    numeric_token_gate, line_straddles_rect, stroke_continues, reject_identity_failures.
Every emitted value carries `emission_class` (numeric, choice, checkbox_box, checkbox_boxless,
free_text); the shadow artifact keeps all, serving defaults to numeric, choice and checkbox_box.
CLI: python tools/tier2_extractor/template_overlay.py file.pdf [--detected-year Y]

The year of a document is decided by the printed page header ("Common Data Set
YYYY-YYYY") and must agree with the best raster year; `detected_year` and
`cds_year` never choose a map. Forced-year runs exist only as the private
`_diagnostic_extract_forced_year` used by the evaluation script.
"""

from __future__ import annotations

import argparse
import ctypes
import functools
import hashlib
import json
import re
import sys
import unicodedata
from collections import Counter
from dataclasses import dataclass, field
from types import SimpleNamespace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pypdfium2 as pdfium

try:  # pdfium's raw API: generated characters, text render mode
    import pypdfium2.raw as _pdfium_c
except Exception:  # pragma: no cover
    _pdfium_c = None

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_field_map as bfm  # noqa: E402

PRODUCER = "tier2_template_overlay"
PRODUCER_VERSION = "0.6.0"
FIELD_MAP_VERSION = bfm.MAP_FORMAT_VERSION

# Only these years may emit values (PRD Decision 5). 2023-24 is recognised so a
# 2023-24 print is rejected rather than read through a 2024-25 map.
EMIT_YEARS = ("2024-25", "2025-26")

# ---- Stage 1 parameters (PRD §2) -------------------------------------------
MIN_PAGES, MAX_PAGES = 30, 70            # pre-filter page-count window
PAGE_MATCH_MIN = 0.85                    # share of template static ink found
GATE_PAGES = 30                          # template pages that must match
ARGMAX_WINDOW = 0.02                     # a (target, template) pair must be this close to the target's best page
DILATE_ITERS = 2                         # 4-neighbour dilations (Manhattan radius 2 at 36 DPI)
PRECISION_SLACK = 0.25                   # s = min(recall, precision + slack)
MIN_TEMPLATE_INK_PX = 50                 # template pages with less ink are skipped
DUPLICATE_DIFF = 0.10                    # share of a widget rect's ink that differs between duplicate pages (no longer used: see DUPLICATE_RASTER_MIN_PX)
DUPLICATE_MIN_PX = 6
DUPLICATE_TEXT_COMPARE = True            # B5: duplicate candidates with a native text layer are compared by the text read at each answer rect
DUPLICATE_RASTER_DPI = 216               # ... and the rest (buttons, raster-only candidates) by ink at this resolution
DUPLICATE_RASTER_MIN_PX = 3              # any difference this large means equality is not established
HEADER_DPI = 144
HEADER_VOTE_MARGIN = 0.01                # a vote: the best year beats the next by this much of the crop
HEADER_VOTE_MAX_RATIO = 0.85            # ... and fits: diff below this share of the crop's own ink (a blank crop scores 1.0)
HEADER_DISSENT_MARGIN = 0.02             # a vote that can HOLD the packet (a confident other-year page) needs more: margin >= this
HEADER_DISSENT_MAX_RATIO = 0.6           # ... and ratio <= this. Cohort votes: median ratio 0.14, p99 0.59, max 0.70; the spurious dissent of sub-point
                                         # shifted prints scored 0.68-0.74 (4 documents held at 0.5 pt before this split)
HEADER_MIN_VOTES = 5
WEAK_VOTE_EXCLUDE = True                 # N1: a page whose own header weakly votes another year is not read (it does not hold the packet)
RASTER_YEAR_VETO = 0.02                  # B2: a matched page whose best score in another year beats the chosen year's by this is not read
# alignment (72 DPI: 1 px = 1 pt in template space)
ALIGN_DPI = 72
ALIGN_SEARCH_PT = 8
ALIGN_MIN_GAIN = 0.02                    # a nonzero page shift must beat (0, 0) by this much recall
ALIGN_MIN_RECALL = 0.5
BAND_COUNT = 6
BAND_RANGE_PT = 16
BAND_MIN_INK = 200
BAND_GAIN = 0.10                         # a band whose best shift beats the applied one by this much is flagged
SHIFT_AGREE_PT = 1                       # band estimates must agree with the applied shift within this
RESIDUAL_SHIFT_RULES = True              # B1: boundary optimum / band majority disagreement reject the page
LOCAL_WINDOW_PT = 14
LOCAL_RANGE_PT = 10
LOCAL_GAIN = 0.10                        # a 12 pt one-row shift of two cells scores 0.143: 0.15 missed it
LOCAL_MIN_INK = 30
LOCAL_SELF_EQUIV = 0.75                  # shifts the template itself cannot tell from 0 (table-row periods) are ignored

STATUS_MATCHED = "matched"
STATUS_NOT_TEMPLATE = "not_official_pdf_template"
STATUS_AMBIGUOUS = "template_year_ambiguous"            # held: year evidence missing, tied, mixed or contradictory
STATUS_UNSUPPORTED_YEAR = "template_year_unsupported"   # recognised (e.g. 2023-24) but not allowed to emit


# --------------------------------------------------------------------------
# maps
# --------------------------------------------------------------------------

def _dilate(m: np.ndarray, iterations: int) -> np.ndarray:
    out = m.copy()
    for _ in range(iterations):
        o = out.copy()
        o[1:] |= out[:-1]
        o[:-1] |= out[1:]
        o[:, 1:] |= out[:, :-1]
        o[:, :-1] |= out[:, 1:]
        out = o
    return out


@dataclass
class TemplatePage:
    mask: np.ndarray
    ys: np.ndarray
    xs: np.ndarray
    dilated: np.ndarray
    usable: bool


@dataclass
class YearMaps:
    year: str
    fmap: dict
    pages: list[TemplatePage]


@functools.lru_cache(maxsize=1)
def load_maps(years: tuple[str, ...] = bfm.YEARS) -> dict[str, YearMaps]:
    """Load the committed field maps and decode their 36-DPI ink masks."""
    out: dict[str, YearMaps] = {}
    for year in years:
        fmap = bfm.load_field_map(year)
        pages = []
        for pg in fmap["pages"]:
            mk = pg["mask"]
            arr = bfm.decode_mask(mk["rle"], mk["width"], mk["height"])
            ys, xs = np.nonzero(arr)
            pages.append(TemplatePage(arr, ys, xs, _dilate(arr, DILATE_ITERS), arr.sum() >= MIN_TEMPLATE_INK_PX))
        out[year] = YearMaps(year, fmap, pages)
    return out


@functools.lru_cache(maxsize=None)
def _template_doc(year: str) -> "pdfium.PdfDocument":
    return pdfium.PdfDocument(str(bfm.template_path_for(year)))


# --------------------------------------------------------------------------
# page geometry: one display coordinate space for text, widgets and pixels
# --------------------------------------------------------------------------

@dataclass
class PageGeom:
    """PDFium's view of a page: effective box, rotation and display size.

    Display space is PDF points of the *displayed* page (CropBox ∩ MediaBox,
    after /Rotate), origin bottom-left, y up. Template space divides by the
    uniform page scale (sx = sy = display width / 612) so the official layout is
    always 612 x 792.
    """
    bx0: float
    by0: float
    bx1: float
    by1: float
    rot: int
    W: float
    H: float
    sx: float
    sy: float
    supported: bool = True
    reason: str | None = None


def page_geometry(page: "pdfium.PdfPage") -> PageGeom:
    media = tuple(float(v) for v in page.get_mediabox())
    crop = tuple(float(v) for v in page.get_cropbox())
    bx0, by0 = max(media[0], crop[0]), max(media[1], crop[1])
    bx1, by1 = min(media[2], crop[2]), min(media[3], crop[3])
    rot = int(page.get_rotation()) % 360
    bw, bh = bx1 - bx0, by1 - by0
    W, H = (bh, bw) if rot in (90, 270) else (bw, bh)
    sx, sy = W / 612.0, H / 792.0
    g = PageGeom(bx0, by0, bx1, by1, rot, W, H, sx, sy)
    pw, ph = page.get_size()
    if bw <= 0 or bh <= 0 or abs(pw - W) > 0.75 or abs(ph - H) > 0.75:
        g.supported, g.reason = False, "page_box_unsupported"
    elif rot not in (0, 90, 180, 270):
        g.supported, g.reason = False, "rotation_unsupported"
    elif abs(sx - sy) > 0.01 * sx:
        g.supported, g.reason = False, "page_aspect_not_template"
    return g


def user_to_display(g: PageGeom, x: float, y: float) -> tuple[float, float]:
    """PDF user space -> display points (origin bottom-left of the displayed page)."""
    if g.rot == 0:
        return x - g.bx0, y - g.by0
    if g.rot == 90:
        return y - g.by0, g.bx1 - x
    if g.rot == 180:
        return g.bx1 - x, g.by1 - y
    return g.by1 - y, x - g.bx0


def display_to_template(g: PageGeom, X: float, Y: float, dx: float = 0.0, dy: float = 0.0) -> tuple[float, float]:
    """Display points -> template space, undoing the page scale and the applied (dx, dy) shift."""
    return X / g.sx - dx, Y / g.sy - dy


def template_rect_to_pixels(rect: list[float], dx: float, dy: float, dpi: float) -> tuple[int, int, int, int]:
    """Template rect -> (row0, row1, col0, col1) in a template-scale render at `dpi`."""
    x0, y0, x1, y1 = rect
    k = dpi / 72.0
    return (int((792.0 - (y1 + dy)) * k), int(np.ceil((792.0 - (y0 + dy)) * k)),
            int((x0 + dx) * k), int(np.ceil((x1 + dx) * k)))


# --------------------------------------------------------------------------
# text layer characters
# --------------------------------------------------------------------------

INVISIBLE_MODES = {3, 7}            # PDF text render modes: invisible, clip only


@dataclass
class PageChar:
    ch: str
    cx: float
    cy: float
    right: float = 0.0
    generated: bool = False
    invisible: bool = False
    left: float | None = None           # left edge of the glyph box; None: mirror `right` about the centre
    top: float | None = None            # vertical extent of the glyph box (template points, y up); None: unknown
    bottom: float | None = None

    @property
    def box_left(self) -> float:
        return self.left if self.left is not None else 2.0 * self.cx - self.right


def _paint_order(page: "pdfium.PdfPage"):
    """(text-object address -> paint index, [(paint index, bounds) of each image object]): the page's deterministic paint order."""
    if _pdfium_c is None:
        return {}, []
    try:
        objs = list(page.get_objects())
    except Exception:  # noqa: BLE001
        return {}, []
    covers = [(i, tuple(o.get_bounds())) for i, o in enumerate(objs) if o.type == _pdfium_c.FPDF_PAGEOBJ_IMAGE]
    if not covers:
        return {}, []
    return {ctypes.cast(o.raw, ctypes.c_void_p).value: i for i, o in enumerate(objs) if o.type == _pdfium_c.FPDF_PAGEOBJ_TEXT}, covers


def _page_chars_display(page: "pdfium.PdfPage", g: PageGeom) -> list[PageChar]:
    """Text-layer characters in DISPLAY points, with generated and invisible flags.

    Characters pdfium generated (hyphen markers, line breaks) keep their flag so
    callers can ignore them; generated whitespace is kept because Distiller
    prints word gaps as gaps and pdfium's generated space is the only separator.
    """
    tp = page.get_textpage()
    out = []
    order, covers = _paint_order(page)
    for i in range(tp.count_chars()):
        ch = tp.get_text_range(i, 1)
        if not ch:
            continue
        generated = bool(_pdfium_c is not None and _pdfium_c.FPDFText_IsGenerated(tp.raw, i))
        invisible = False
        if _pdfium_c is not None and not generated:
            obj = _pdfium_c.FPDFText_GetTextObject(tp.raw, i)
            if obj:
                invisible = int(_pdfium_c.FPDFTextObj_GetTextRenderMode(obj)) in INVISIBLE_MODES
        left, bottom, right, top = tp.get_charbox(i)
        if covers and not generated and _pdfium_c is not None and not invisible:
            obj = _pdfium_c.FPDFText_GetTextObject(tp.raw, i)
            idx = order.get(ctypes.cast(obj, ctypes.c_void_p).value) if obj else None
            if idx is not None and any(j > idx and l <= left and b <= bottom and r >= right and t >= top for j, (l, b, r, t) in covers):
                invisible = True                    # painted over by a later image: the text is not what the page shows
        (xa, ya), (xb, yb) = user_to_display(g, left, bottom), user_to_display(g, right, top)
        out.append(PageChar(ch, (xa + xb) / 2.0, (ya + yb) / 2.0, max(xa, xb), generated, invisible, min(xa, xb),
                            max(ya, yb), min(ya, yb)))
    return out


def _chars_to_template(chars: list[PageChar], g: PageGeom, dx: float = 0.0, dy: float = 0.0) -> list[PageChar]:
    out = []
    for c in chars:
        tx, ty = display_to_template(g, c.cx, c.cy, dx, dy)
        out.append(PageChar(c.ch, tx, ty, c.right / g.sx - dx, c.generated, c.invisible,
                            c.box_left / g.sx - dx,
                            None if c.top is None else c.top / g.sy - dy,
                            None if c.bottom is None else c.bottom / g.sy - dy))
    return out


@functools.lru_cache(maxsize=None)
def _template_chars(year: str, page: int) -> tuple[PageChar, ...]:
    p = _template_doc(year)[page]
    return tuple(_page_chars_display(p, page_geometry(p)))


# --------------------------------------------------------------------------
# rendering
# --------------------------------------------------------------------------

def _render_gray(page: "pdfium.PdfPage", dpi: float) -> np.ndarray:
    """Gray (uint8) render with PDFium's own page transform; annotations off."""
    bitmap = page.render(scale=dpi / 72.0, draw_annots=False, may_draw_forms=False, rev_byteorder=True)
    rgb = bitmap.to_numpy()[..., :3].astype(np.uint32)
    return (((rgb[..., 0] * 19595 + rgb[..., 1] * 38470 + rgb[..., 2] * 7471 + 0x8000) >> 16)).astype(np.uint8)


def _render_template_scale(page: "pdfium.PdfPage", g: PageGeom, dpi: float) -> np.ndarray:
    """Gray render in which one template point is dpi/72 pixels (the page scale divided out)."""
    return _render_gray(page, dpi / g.sx)


# --------------------------------------------------------------------------
# Stage 1: scoring and page assignment
# --------------------------------------------------------------------------

@dataclass
class MatchResult:
    status: str
    year: str | None = None
    reason: str | None = None
    page_count: int = 0
    pages_matched: dict[str, int] = field(default_factory=dict)   # year -> pages matched
    lead: int | None = None
    runner_up_year: str | None = None
    header_votes: dict[str, int] = field(default_factory=dict)
    header_confident: dict[str, int] = field(default_factory=dict)   # votes that may hold the packet (margin and fit)
    page_map: dict[int, int] = field(default_factory=dict)        # target page -> template page
    offsets: dict[int, int] = field(default_factory=dict)         # target - template -> count
    alignment: dict[int, dict] = field(default_factory=dict)      # target page -> dx, dy, recall (template pt)
    rejected_pages: dict[int, str] = field(default_factory=dict)  # target page -> reason
    rejected_template_pages: dict[int, str] = field(default_factory=dict)   # template page -> reason
    band_rejections: dict[int, list[int]] = field(default_factory=dict)     # target page -> bands to withhold
    page_scores: dict[int, float] = field(default_factory=dict)

    def to_dict(self) -> dict:
        d = {k: v for k, v in self.__dict__.items()}
        for k in ("page_map", "alignment", "rejected_pages", "rejected_template_pages", "band_rejections", "offsets"):
            d[k] = {str(a): b for a, b in getattr(self, k).items()}
        d["page_scores"] = {str(k): round(v, 4) for k, v in self.page_scores.items()}
        return d


def _page_mask36(page: "pdfium.PdfPage", g: PageGeom, shape: tuple[int, int]) -> np.ndarray | None:
    if not g.supported:
        return None
    mask = _render_template_scale(page, g, bfm.MASK_DPI) < bfm.INK_THRESHOLD
    out = np.zeros(shape, dtype=bool)
    hh, ww = min(shape[0], mask.shape[0]), min(shape[1], mask.shape[1])
    out[:hh, :ww] = mask[:hh, :ww]
    return out


def _score_page(g: np.ndarray, tpl: YearMaps) -> list[float]:
    """Match score of one target-page mask against every template page of a year."""
    gy, gx = np.nonzero(g)
    if gy.size == 0:
        return [0.0] * len(tpl.pages)
    gd = _dilate(g, DILATE_ITERS)
    scores = []
    for tp in tpl.pages:
        if not tp.usable:
            scores.append(0.0)
            continue
        recall = float(gd[tp.ys, tp.xs].mean())
        if recall < PAGE_MATCH_MIN:
            scores.append(recall)
            continue
        precision = float(tp.dilated[gy, gx].mean())
        scores.append(min(recall, precision + PRECISION_SLACK))
    return scores


def _monotonic_assign(score: np.ndarray) -> dict[int, int]:
    """Max-count increasing assignment of target pages to template pages.

    A pair (q, p) is valid only when its score reaches PAGE_MATCH_MIN *and* p is
    within ARGMAX_WINDOW of the best template page for q: near-duplicate template
    pages (8, 38 and 41 cross-match at 0.85-0.87) can then never be read through
    each other's map. Ties on count prefer the higher total score.
    """
    nq, npg = score.shape
    rowmax = score.max(axis=1, keepdims=True) if npg else np.zeros((nq, 1))
    valid = (score >= PAGE_MATCH_MIN) & (score >= rowmax - ARGMAX_WINDOW)
    w = np.where(valid, 1.0 + score * 1e-3, 0.0)
    f = np.zeros((nq + 1, npg + 1))
    for i in range(1, nq + 1):
        for j in range(1, npg + 1):
            best = max(f[i - 1, j], f[i, j - 1])
            if valid[i - 1, j - 1]:
                best = max(best, f[i - 1, j - 1] + w[i - 1, j - 1])
            f[i, j] = best
    pairs: dict[int, int] = {}
    i, j = nq, npg
    while i > 0 and j > 0:
        if valid[i - 1, j - 1] and f[i, j] == f[i - 1, j - 1] + w[i - 1, j - 1]:
            pairs[i - 1] = j - 1
            i -= 1
            j -= 1
        elif f[i, j] == f[i - 1, j]:
            i -= 1
        else:
            j -= 1
    return dict(sorted(pairs.items()))


def _duplicate_candidates(score: np.ndarray) -> dict[int, list[int]]:
    """Template pages that more than one target page claims (strongly, within the argmax window)."""
    rowmax = score.max(axis=1, keepdims=True)
    claims: dict[int, list[int]] = {}
    for q in range(score.shape[0]):
        for p in range(score.shape[1]):
            if score[q, p] >= PAGE_MATCH_MIN and score[q, p] >= rowmax[q, 0] - ARGMAX_WINDOW:
                claims.setdefault(p, []).append(q)
    return {p: qs for p, qs in claims.items() if len(qs) > 1}


def _native_text(chars: list[PageChar], tchars: tuple[PageChar, ...]) -> bool:
    """Does this page carry a usable text layer (at least half the blank page's own visible characters)?"""
    vis = sum(1 for c in chars if not c.ch.isspace() and not _marker(c))
    tvis = sum(1 for c in tchars if not c.ch.isspace() and not _marker(c))
    return vis >= max(1, int(0.5 * tvis))


def _answer_regions_differ(doc, geoms, qs, ymaps: YearMaps, p: int, shape=None, year: str | None = None) -> bool:
    """Do the candidate target pages for template page p differ inside any of p's widget rects?

    Duplicate candidates are the same page printed twice; they must agree on every answer. A
    candidate with a native text layer is compared by the text read at each /Tx and /Ch rect (a
    one-digit change at any font size differs; a binary raster at 72 DPI cannot see it). Buttons
    (ink, not text) and candidates with no native text layer are compared by ink at
    DUPLICATE_RASTER_DPI: any DUPLICATE_RASTER_MIN_PX pixels that differ, or a rect that cannot
    be compared, mean equality is not established and the pages conflict.
    """
    ws = [(f["ft"], w["rect"]) for f in ymaps.fmap["fields"].values() for w in f["widgets"] if w["template_page"] == p]
    if not ws:
        return False
    for q in qs:
        if not geoms[q].supported:
            return True
    tchars = _template_chars(year, p) if year else ()
    chars = [_chars_to_template(_page_chars_display(doc[q], geoms[q]), geoms[q]) for q in qs] if DUPLICATE_TEXT_COMPARE else []
    native = DUPLICATE_TEXT_COMPARE and all(_native_text(c, tchars) for c in chars)
    grays = None
    for ft, rect in ws:
        if native and ft in ("/Tx", "/Ch"):
            reads = [read_widget_text(c, rect, tchars, rect)[0] for c in chars]
            if any(r != reads[0] for r in reads[1:]):
                return True
            continue
        if grays is None:
            grays = [_render_template_scale(doc[q], geoms[q], DUPLICATE_RASTER_DPI) < bfm.INK_THRESHOLD for q in qs]
        r0, r1, c0, c1 = template_rect_to_pixels(rect, 0.0, 0.0, DUPLICATE_RASTER_DPI)
        crops = [g[max(r0, 0):r1, max(c0, 0):c1] for g in grays]
        for other in crops[1:]:
            if other.shape != crops[0].shape:
                return True
            if int((crops[0] ^ other).sum()) >= DUPLICATE_RASTER_MIN_PX:
                return True
    return False


# --------------------------------------------------------------------------
# Stage 1: printed header year
# --------------------------------------------------------------------------

_HEADER_RE = re.compile(r"Common Data Set (20\d\d-20\d\d)")


@functools.lru_cache(maxsize=1)
def _header_boxes() -> dict[int, list[float]]:
    """Union box of the printed 'Common Data Set YYYY-YYYY' year digits per template page."""
    boxes: dict[int, list[list[float]]] = {}
    for year in bfm.YEARS:
        doc = _template_doc(year)
        for p in range(len(doc)):
            tp = doc[p].get_textpage()
            m = _HEADER_RE.search(tp.get_text_range())
            if not m:
                continue
            bx = [tp.get_charbox(j) for j in range(m.start(1), m.end(1))]
            boxes.setdefault(p, []).append([min(b[0] for b in bx), min(b[1] for b in bx),
                                            max(b[2] for b in bx), max(b[3] for b in bx)])
    out = {}
    for p, lst in boxes.items():
        if len(lst) == len(bfm.YEARS):
            out[p] = [min(b[0] for b in lst), min(b[1] for b in lst), max(b[2] for b in lst), max(b[3] for b in lst)]
    return out


def _header_crop(gray: np.ndarray, box: list[float], dpi: float, pad: float = 3.0) -> np.ndarray:
    k = dpi / 72.0
    x0, y0, x1, y1 = box
    return gray[int((792 - y1 - pad) * k):int((792 - y0 + pad) * k), int((x0 - pad) * k):int((x1 + pad) * k)].astype(np.float32)


@functools.lru_cache(maxsize=None)
def _header_template_crops(p: int) -> dict[str, np.ndarray]:
    box = _header_boxes()[p]
    return {y: _header_crop(_render_gray(_template_doc(y)[p], HEADER_DPI), box, HEADER_DPI) for y in bfm.YEARS}


def _best_shift_diff(c: np.ndarray, t: np.ndarray) -> float:
    best = 9.0
    H, W = t.shape
    for dy in range(-4, 5):
        for dx in range(-4, 5):
            ys, xs = 4 + dy, 4 + dx
            cc = c[ys:ys + H - 8, xs:xs + W - 8]
            tt = t[4:H - 4, 4:W - 4]
            if cc.shape == tt.shape and cc.size:
                best = min(best, float(np.abs(cc - tt).mean() / 255.0))
    return best


def header_year_vote(page: "pdfium.PdfPage", g: PageGeom, p: int, dx: float = 0.0, dy: float = 0.0,
                     *, detail: bool = False):
    """Which year's printed header does this page carry? None when it cannot tell.

    Pixel comparison of the year digits against each year's blank page at 144 DPI,
    so it works on vector-drawn prints without OCR. 2023-24 is one of the choices
    so a 2023-24 document is recognised. The crop is taken at the page's applied
    shift (`dx`, `dy`: template points, y up, as in `Stage1.alignment`) and the
    +-4 px residual search is kept. A vote needs the best year to beat the next by
    HEADER_VOTE_MARGIN *and* to explain the crop: its diff must be under
    HEADER_VOTE_MAX_RATIO of the crop's own ink. A blank, smudged or misplaced header
    (which would otherwise "vote" for whichever year has the least ink) casts no vote.
    With detail=True returns (vote, best_diff, margin, diff / ink).
    """
    none = (None, None, None, None) if detail else None
    if p not in _header_boxes() or not g.supported:
        return none
    x0, y0, x1, y1 = _header_boxes()[p]
    crop = _header_crop(_render_gray(page, HEADER_DPI / g.sx), [x0 + dx, y0 + dy, x1 + dx, y1 + dy], HEADER_DPI)
    tcrops = _header_template_crops(p)
    if crop.shape != tcrops[bfm.YEARS[0]].shape:
        return none
    diffs = sorted((_best_shift_diff(crop, t), y) for y, t in tcrops.items())
    (d0, y0_), (d1, _y1) = diffs[0], diffs[1]
    ink = float((255.0 - crop[4:-4, 4:-4]).mean() / 255.0)
    vote = y0_ if (d1 - d0 > HEADER_VOTE_MARGIN and d0 <= HEADER_VOTE_MAX_RATIO * ink) else None
    if detail:
        return vote, d0, d1 - d0, (d0 / ink if ink > 0 else 9.0)
    return vote


def decide_year(counts: dict[str, int], header_votes: dict[str, int], detected_year: str | None,
                confident_votes: dict[str, int] | None = None) -> tuple[str, str | None, str | None, int, str | None]:
    """Year decision. Returns (status, year, reason, raster_lead, runner_up_year).

    The page header (printed year) is the discriminator: the document year is the
    header year and must agree with the best raster year. `detected_year` can
    only veto. The rule is strict: ANY confident other-year page (a page whose
    header matches another year absolutely and by margin) makes the packet mixed
    and holds the whole document. Contradictions, ties and unverifiable headers hold
    it too (nothing is emitted); 2023-24 is recognised and rejected.
    """
    ranked = sorted(counts, key=lambda y: (-counts[y], y))
    best = ranked[0]
    second = ranked[1] if len(ranked) > 1 else None
    lead = counts[best] - (counts[second] if second else 0)
    if counts[best] < GATE_PAGES:
        return STATUS_NOT_TEMPLATE, None, "fewer_than_30_template_pages", lead, second
    if lead == 0:
        return STATUS_AMBIGUOUS, None, "tie_between_years", lead, second
    conf = header_votes if confident_votes is None else confident_votes
    total = sum(header_votes.values())
    if total < HEADER_MIN_VOTES:
        if len([y for y, n in conf.items() if n]) > 1:
            return STATUS_AMBIGUOUS, None, "mixed_year_packet", lead, second
        return STATUS_AMBIGUOUS, None, "header_year_unverified", lead, second
    hdr = max(header_votes, key=lambda y: (header_votes[y], y))
    if any(n and y != hdr for y, n in conf.items()):
        return STATUS_AMBIGUOUS, None, "mixed_year_packet", lead, second      # one confident other-year page holds the packet
    if hdr != best:
        return STATUS_AMBIGUOUS, None, "header_year_contradicts_raster_year", lead, second
    if detected_year and detected_year != hdr:
        return STATUS_AMBIGUOUS, None, "detected_year_contradicts_header_year", lead, second
    if hdr not in EMIT_YEARS:
        return STATUS_UNSUPPORTED_YEAR, None, f"year_{hdr}_not_supported", lead, second
    return STATUS_MATCHED, hdr, None, lead, second


# --------------------------------------------------------------------------
# alignment: page shift, per-band consistency, per-widget local check
# --------------------------------------------------------------------------

def _recall(g: np.ndarray, ty: np.ndarray, tx: np.ndarray, dxp: int, dyp: int) -> float:
    yy, xx = ty + dyp, tx + dxp
    ok = (yy >= 0) & (yy < g.shape[0]) & (xx >= 0) & (xx < g.shape[1])
    return float(g[yy[ok], xx[ok]].sum()) / max(ty.size, 1)


def _subsample(ty: np.ndarray, tx: np.ndarray, n: int) -> tuple[np.ndarray, np.ndarray]:
    if ty.size > n:
        keep = np.arange(0, ty.size, ty.size // n + 1)
        return ty[keep], tx[keep]
    return ty, tx


def _descend(g: np.ndarray, ty: np.ndarray, tx: np.ndarray, rng: int, base: tuple[int, int] = (0, 0)):
    """Best (recall, dxp, dyp) pixel shift by alternating 1-D searches (x and y separately).

    The target is dilated, so several neighbouring shifts reach the same recall; the
    centre of the plateau nearest to `base` is taken, and the incumbent only moves
    when a shift is strictly better.
    """
    bx, by = base
    best = _recall(g, ty, tx, bx, by)
    for _ in range(3):
        moved = False
        for axis in ("y", "x"):
            rs = {s: _recall(g, ty, tx, bx if axis == "y" else s, s if axis == "y" else by) for s in range(-rng, rng + 1)}
            mx = max(rs.values())
            if mx <= best + 1e-9:
                continue
            hits = [s for s in sorted(rs) if rs[s] >= mx - 1e-9]
            runs, run = [], [hits[0]]
            for s in hits[1:]:
                if s == run[-1] + 1:
                    run.append(s)
                else:
                    runs.append(run)
                    run = [s]
            runs.append(run)
            cur = by if axis == "y" else bx
            chosen = min(runs, key=lambda r: min(abs(s - cur) for s in r))
            c = int(round((chosen[0] + chosen[-1]) / 2))
            if axis == "y":
                by = c
            else:
                bx = c
            best, moved = mx, True
        if not moved:
            break
    return best, bx, by


@dataclass
class PageMasks:
    """72-DPI template-scale masks for a matched page and its template."""
    g: np.ndarray        # target ink, dilated by 1 px
    t: np.ndarray        # template ink


def _page_masks(page: "pdfium.PdfPage", g: PageGeom, tpage: "pdfium.PdfPage") -> PageMasks:
    gm = _render_template_scale(page, g, ALIGN_DPI) < bfm.INK_THRESHOLD
    tm = _render_gray(tpage, ALIGN_DPI) < bfm.INK_THRESHOLD
    hh, ww = min(gm.shape[0], tm.shape[0]), min(gm.shape[1], tm.shape[1])
    return PageMasks(_dilate(gm[:hh, :ww], 1), tm[:hh, :ww])


def estimate_page_alignment(m: PageMasks) -> dict:
    """Page shift plus six horizontal band estimates (template pt; dy up-positive).

    Returns {"dx", "dy", "recall", "bands", "flagged_bands", "consistent"}. A
    nonzero page shift is only reported consistent when no inked band has a
    better shift of its own (a partial-page shift is not a page shift). With a
    zero page shift, bands whose best shift is elsewhere are flagged so their
    widgets abstain.
    """
    g, t = m.g, m.t
    ty, tx = np.nonzero(t)
    sty, stx = _subsample(ty, tx, 6000)
    rec0 = _recall(g, sty, stx, 0, 0)
    best, bx, by = _descend(g, sty, stx, ALIGN_SEARCH_PT)
    if best - rec0 < ALIGN_MIN_GAIN:
        best, bx, by = rec0, 0, 0
    out = {"dx": float(bx), "dy": float(-by), "recall": round(best, 4), "bands": [], "flagged_bands": [], "consistent": True,
           "inconsistent_reason": None}
    hh = g.shape[0]
    for b in range(BAND_COUNT):
        r0, r1 = b * hh // BAND_COUNT, (b + 1) * hh // BAND_COUNT
        sel = (ty >= r0) & (ty < r1)
        if sel.sum() < BAND_MIN_INK:
            out["bands"].append(None)
            continue
        bty, btx = _subsample(ty[sel], tx[sel], 1500)
        rec_applied = _recall(g, bty, btx, bx, by)
        bbest, bbx, bby = _descend(g, bty, btx, BAND_RANGE_PT, base=(bx, by))
        out["bands"].append({"rec_applied": round(rec_applied, 3), "best": round(bbest, 3), "dx": bbx, "dy": -bby})
        differs = abs(bbx - bx) > SHIFT_AGREE_PT or abs(bby - by) > SHIFT_AGREE_PT
        if differs and bbest - rec_applied >= BAND_GAIN:
            out["flagged_bands"].append(b)
    if (bx, by) != (0, 0) and out["flagged_bands"]:
        out["consistent"], out["inconsistent_reason"] = False, "partial_page_shift"
    if RESIDUAL_SHIFT_RULES and out["consistent"]:
        inked = [bd for bd in out["bands"] if bd]
        if max(abs(bx), abs(by)) >= ALIGN_SEARCH_PT:
            # the optimum sits on the edge of the search range: the true shift is probably beyond it
            out["consistent"], out["inconsistent_reason"] = False, "residual_page_shift"
        elif inked and 2 * sum(1 for bd in inked if abs(bd["dx"] - bx) > SHIFT_AGREE_PT
                               or abs(-bd["dy"] - by) > SHIFT_AGREE_PT) > len(inked):
            # most inked bands agree on another shift (any gain): the applied one is not the page's
            out["consistent"], out["inconsistent_reason"] = False, "residual_page_shift"
    return out


_LOCAL_EQUIV_CACHE: dict[tuple, frozenset] = {}


def _local_window(rect: list[float], hh: int, ww: int) -> tuple[int, int, int, int]:
    x0, y0, x1, y1 = rect
    r0, r1 = max(0, int(792 - y1 - LOCAL_WINDOW_PT)), min(hh, int(np.ceil(792 - y0 + LOCAL_WINDOW_PT)))
    c0, c1 = max(0, int(x0 - LOCAL_WINDOW_PT)), min(ww, int(np.ceil(x1 + LOCAL_WINDOW_PT)))
    return r0, r1, c0, c1


def _equivalent_shifts(year: str, p: int, key: tuple, rect: list[float], t: np.ndarray) -> frozenset:
    """Shifts the blank template cannot distinguish from 0 inside the widget's window.

    A table repeats its rules at one row pitch, so target ink fits the template
    just as well one row up or down; such alternatives say nothing about
    misalignment and are ignored by the local check.
    """
    k = (year, p, key)
    if k in _LOCAL_EQUIV_CACHE:
        return _LOCAL_EQUIV_CACHE[k]
    td = _dilate(t, 1)
    r0, r1, c0, c1 = _local_window(rect, *t.shape)
    ty, tx = np.nonzero(t[r0:r1, c0:c1])
    ty, tx = _subsample(ty + r0, tx + c0, 600)
    eq = set()
    if ty.size >= LOCAL_MIN_INK:
        for axis in ("y", "x"):
            for s in range(-LOCAL_RANGE_PT, LOCAL_RANGE_PT + 1):
                if abs(s) <= SHIFT_AGREE_PT:
                    continue
                if _recall(td, ty, tx, s if axis == "x" else 0, s if axis == "y" else 0) >= LOCAL_SELF_EQUIV:
                    eq.add((axis, s))
    _LOCAL_EQUIV_CACHE[k] = frozenset(eq)
    return _LOCAL_EQUIV_CACHE[k]


def local_alignment_stats(m: PageMasks, rect: list[float], applied: tuple[int, int], equiv: frozenset) -> tuple[float, float, int]:
    """(recall at the applied transform +-1 px, best recall over x or y shifts, template ink points)."""
    g, t = m.g, m.t
    r0, r1, c0, c1 = _local_window(rect, *t.shape)
    ty, tx = np.nonzero(t[r0:r1, c0:c1])
    n_ink = int(ty.size)
    if n_ink < LOCAL_MIN_INK:
        return 0.0, 0.0, n_ink
    ty, tx = _subsample(ty + r0, tx + c0, 600)
    ax, ay = applied
    near0 = max(_recall(g, ty, tx, ax + a, ay + b) for a in (-1, 0, 1) for b in (-1, 0, 1))
    best = near0
    for s in range(-LOCAL_RANGE_PT, LOCAL_RANGE_PT + 1):
        if abs(s) <= SHIFT_AGREE_PT:
            continue
        if ("y", s) not in equiv:
            best = max(best, max(_recall(g, ty, tx, ax + a, ay + s) for a in (-1, 0, 1)))
        if ("x", s) not in equiv:
            best = max(best, max(_recall(g, ty, tx, ax + s, ay + b) for b in (-1, 0, 1)))
    return near0, best, n_ink


def local_alignment_check(m: PageMasks, rect: list[float], applied: tuple[int, int], equiv: frozenset) -> tuple[str, float]:
    """Per-widget check that the applied page transform really lands this widget.

    Template static ink in the rect + LOCAL_WINDOW_PT is compared with the target:
    the widget is misaligned when shifting x or y alone (within +-LOCAL_RANGE_PT,
    ignoring row-period alternatives) explains the target ink at least LOCAL_GAIN
    better than the applied transform (+-1 px).
    Returns ("ok"|"misaligned"|"no_ink", gain).
    """
    near0, best, n_ink = local_alignment_stats(m, rect, applied, equiv)
    if n_ink < LOCAL_MIN_INK:
        return "no_ink", 0.0
    gain = best - near0
    bad = gain >= LOCAL_GAIN
    return ("misaligned" if bad else "ok"), gain


# --------------------------------------------------------------------------
# Stage 1 driver
# --------------------------------------------------------------------------

def _open(pdf) -> "pdfium.PdfDocument":
    if isinstance(pdf, pdfium.PdfDocument):
        return pdf
    if isinstance(pdf, (str, Path)):
        return pdfium.PdfDocument(str(pdf))
    return pdfium.PdfDocument(bytes(pdf))


def match_template(
    pdf: bytes | str | Path | "pdfium.PdfDocument",
    maps: dict[str, YearMaps] | None = None,
    detected_year: str | None = None,
    *,
    align: bool = True,
) -> MatchResult:
    """Stage 1: decide whether `pdf` is a print of an official CDS template, and which year.

    Pages are scored against every year's masks (36 DPI, ink gray < 225, two
    4-neighbour dilations, `min(recall, precision + 0.25)`), assigned
    monotonically with the argmax guard, checked for conflicting duplicate pages,
    voted by their printed header year, and aligned. See `decide_year` for the
    year rule; `detected_year` can only veto.
    """
    maps = maps or load_maps()
    doc = _open(pdf)
    n = len(doc)
    res = MatchResult(status=STATUS_NOT_TEMPLATE, page_count=n)
    if not (MIN_PAGES <= n <= MAX_PAGES):
        res.reason = "page_count_out_of_range"
        return res

    years = list(maps)
    shape = next(iter(maps.values())).pages[0].mask.shape
    geoms = [page_geometry(doc[q]) for q in range(n)]
    score = {y: np.zeros((n, len(maps[y].pages))) for y in years}
    for q in range(n):
        gm = _page_mask36(doc[q], geoms[q], shape)
        if gm is None:
            res.rejected_pages[q] = geoms[q].reason or "page_geometry_unsupported"
            continue
        for y in years:
            score[y][q] = _score_page(gm, maps[y])
    assign = {y: _monotonic_assign(score[y]) for y in years}
    counts = {y: len(assign[y]) for y in years}
    res.pages_matched = counts

    best_raster = sorted(years, key=lambda y: (-counts[y], y))[0]
    votes = {y: 0 for y in years}
    confident = {y: 0 for y in years}
    page_vote: dict[int, str] = {}           # q -> the year this page's own header votes for (weak or confident)
    est_cache: dict[int, dict] = {}
    if counts[best_raster] >= GATE_PAGES:
        # the decided year must equal the best raster year, so the page shifts are found
        # against it first and the header crops are taken at the applied shift
        tdoc0 = _template_doc(best_raster)
        for q, p in assign[best_raster].items():
            dxy = (0.0, 0.0)
            if align and geoms[q].supported:
                est_cache[q] = estimate_page_alignment(_page_masks(doc[q], geoms[q], tdoc0[p]))
                dxy = (est_cache[q]["dx"], est_cache[q]["dy"])
                if not est_cache[q]["consistent"] or est_cache[q]["recall"] < ALIGN_MIN_RECALL:
                    continue            # a page that will be rejected for alignment is not a reliable voter (nor read)
            v, _d0, margin, ratio = header_year_vote(doc[q], geoms[q], p, *dxy, detail=True)
            if v:
                votes[v] += 1
                page_vote[q] = v
                if margin >= HEADER_DISSENT_MARGIN and ratio <= HEADER_DISSENT_MAX_RATIO:
                    confident[v] += 1
    res.header_votes = {y: c for y, c in votes.items() if c}
    res.header_confident = {y: c for y, c in confident.items() if c}

    status, year, reason, lead, second = decide_year(counts, votes, detected_year, confident)
    res.lead, res.runner_up_year = lead, second
    if status != STATUS_MATCHED:
        res.status, res.reason = status, reason
        return res

    res.status, res.year = STATUS_MATCHED, year
    page_map = dict(assign[year])
    sc = score[year]
    # A confident other-year page holds the packet (decide_year). A WEAK other-year vote (sub-point shift,
    # veil) is not enough to hold it, but that page is not read through this year's map either.
    for q, p in list(page_map.items()):
        if WEAK_VOTE_EXCLUDE and page_vote.get(q, year) != year:
            res.rejected_pages[q] = "weak_other_year_vote"
            del page_map[q]
    for q, p in list(page_map.items()):      # B2: a page whose own raster prefers another year is not read through this map
        if any(score[y2][q].max() - sc[q][p] > RASTER_YEAR_VETO for y2 in years if y2 != year):
            res.rejected_pages[q] = "page_raster_prefers_other_year"
            del page_map[q]
    for p, qs in _duplicate_candidates(sc).items():   # one template page, several target pages
        if p in page_map.values() and _answer_regions_differ(doc, geoms, qs, maps[year], p, year=year):
            res.rejected_template_pages[p] = "duplicate_page_conflict"
            for q, pp in list(page_map.items()):
                if pp == p:
                    del page_map[q]
                    res.rejected_pages[q] = "duplicate_page_conflict"
    for q, p in page_map.items():
        res.page_scores[q] = float(sc[q][p])
        res.offsets[q - p] = res.offsets.get(q - p, 0) + 1
    res.page_map = page_map

    if align:
        tdoc = _template_doc(year)
        for q, p in list(res.page_map.items()):
            if not geoms[q].supported:
                res.rejected_pages[q] = geoms[q].reason or "page_geometry_unsupported"
            else:
                est = est_cache.get(q) or estimate_page_alignment(_page_masks(doc[q], geoms[q], tdoc[p]))
                res.alignment[q] = {"dx": est["dx"], "dy": est["dy"], "recall": est["recall"]}
                if est["recall"] < ALIGN_MIN_RECALL:
                    res.rejected_pages[q] = "alignment_recall_too_low"
                elif not est["consistent"]:
                    res.rejected_pages[q] = est.get("inconsistent_reason") or "partial_page_shift"
                elif est["flagged_bands"]:
                    res.band_rejections[q] = list(est["flagged_bands"])
            if q in res.rejected_pages:
                del res.page_map[q]
                res.page_scores.pop(q, None)
    return res


# --------------------------------------------------------------------------
# Lane 1: text layer (/Tx and /Ch)
# --------------------------------------------------------------------------

# "Numbers" is the schema's type for digit identifiers (ZIP, phone, area code,
# extension): kept as typed and checked for digits and phone punctuation only.
IDENTIFIER_NUMBER_TYPE = "Numbers"
_IDENT_RE = re.compile(r"^[0-9(+][0-9\-\s().+x]*$", re.ASCII)
# one numeric token: optional $, digits with comma grouping only as \d{1,3}(,\d{3})+,
# optional decimals, optional %; no internal spaces, no sign, no second run
_NUM_RE = re.compile(r"^\$?\s?(?P<n>(?:[0-9]{1,3}(?:,[0-9]{3})+|[0-9]+)(?:\.[0-9]+)?|\.[0-9]+)\s?%?$", re.ASCII)
NUMERIC_TYPES = {
    "Number", "Nearest $1", "Nearest 1%", "Carnegie units",
    "Whole Number or Round to Nearest Tenth", "Whole Number or Round to Nearest Tenths",
    "Whole Number or Round to Nearest Hundredths", "Round to Nearest Hundredths",
}
# Schema value_type corrections (the schema types these numeric; the questions take text).
VALUE_TYPE_OVERRIDES = {"AD_TFER_GRADE": "Text"}
_PERCENTILE_RE = re.compile(r"_(25|50|75)TH_P$")
# schema value types that are whole numbers: "1.234" there is a thousands separator, not a decimal
INTEGER_VALUE_TYPES = {"Number", "Nearest $1", "Nearest 1%"}
# N-f: no numeric type of the schema takes three decimals (tenths and hundredths are the finest), so
# "1.234" is a thousands separator, or a misread, on every numeric field -- Dollars and Percent included.
GRAMMAR_ALL_TYPES = True
_THOUSANDS_DOT_RE = re.compile(r"^\$?\s?[1-9][0-9]{0,2}\.[0-9]{3}\s?%?$", re.ASCII)
STATIC_MATCH_PT = 1.0
SPACE_LINE_PT = 4.0            # a generated space belongs to a read line when it sits within this of a glyph's centre height
MIN_NEW_INK_PX = 6
INK_DPI = 216
CLIP_EDGE_PT = 2.0

_IGNORABLE_GENERATED = {"￾", "￿"}
_REPLACEMENT = "�"


def effective_type(tag: str, value_type: str | None, ft: str) -> str:
    """The type a field is validated as; recorded in every emitted value."""
    if ft == "/Btn":
        return "Button"
    vt = VALUE_TYPE_OVERRIDES.get(tag, value_type)
    if vt == IDENTIFIER_NUMBER_TYPE:
        return "Identifier"
    if vt == "Nearest 1%" or (tag.endswith("_P") and not _PERCENTILE_RE.search(tag)):
        return "Percent"          # every percentage-typed field lives in 0-100
    if vt == "Nearest $1":
        return "Dollars"
    if vt in NUMERIC_TYPES:
        return "Number"
    if vt in ("MM", "DD"):
        return {"MM": "Month", "DD": "Day"}[vt]
    return "Text"


def _marker(c: PageChar) -> bool:
    """A noncharacter or format character that pdfium itself generated: not a glyph."""
    return c.generated and (c.ch in _IGNORABLE_GENERATED or unicodedata.category(c.ch[0]) == "Cf")


def _bad_char(c: PageChar) -> bool:
    """Control, private-use, surrogate, unassigned, replacement, or a noncharacter or
    format character that pdfium did NOT mark as generated (a real, unreadable glyph)."""
    ch = c.ch
    if ch in "\t\n\r" or _marker(c):
        return False
    return unicodedata.category(ch[0]) in ("Cc", "Co", "Cs", "Cn", "Cf") or ch == _REPLACEMENT


@dataclass
class WidgetRead:
    text: str = ""
    bad: bool = False
    invisible: bool = False
    max_right: float | None = None      # right edge of the last included glyph (template pt)
    continues: bool = False             # glyphs of the same line continue just past the rect


def read_widget_text(
    chars: list[PageChar],
    rect: list[float],
    static_chars: tuple[PageChar, ...] = (),
    static_rect: list[float] | None = None,
    *,
    pad: float = 0.0,
    detail: bool = False,
):
    """Read the characters whose box centre lies inside `rect` (template space, no padding).

    `chars` and `static_chars` must already be in template space. Characters that
    coincide (within STATIC_MATCH_PT) with a blank-template character inside the
    widget's template rect are the form's own label text and are dropped. A read
    holding a control, private-use or replacement character (or a noncharacter
    pdfium did not mark as generated) is never cleaned: `bad` is True. A read
    holding an invisible (render mode 3/7) glyph is flagged `invisible`.

    Returns (text, bad) or, with detail=True, a WidgetRead.
    """
    x0, y0, x1, y1 = rect
    inside = [c for c in chars if x0 - pad <= c.cx <= x1 + pad and y0 - pad <= c.cy <= y1 + pad]
    # a space (pdfium-generated between words) sits at the line's baseline, below the glyph centres:
    # a tight rect then misses it and the words run together. Keep spaces that sit between the
    # glyphs already read, on their line.
    glyphs_in = [c for c in inside if not c.ch.isspace()]
    if glyphs_in:
        lo, hi = min(c.cx for c in glyphs_in), max(c.cx for c in glyphs_in)
        keep = {id(c) for c in inside}
        for c in chars:
            if id(c) not in keep and c.ch.isspace() and lo <= c.cx <= hi and any(abs(c.cy - g.cy) <= SPACE_LINE_PT for g in glyphs_in):
                keep.add(id(c))
        inside = [c for c in chars if id(c) in keep]
    if static_chars and static_rect is not None:
        sx0, sy0, sx1, sy1 = static_rect
        stat = [c for c in static_chars if sx0 <= c.cx <= sx1 and sy0 <= c.cy <= sy1]
        if stat:
            kept = []
            for c in inside:
                hit = any(abs(c.cx - s.cx) <= STATIC_MATCH_PT and abs(c.cy - s.cy) <= STATIC_MATCH_PT
                          and (c.ch == s.ch or _bad_char(c) or _bad_char(s)) for s in stat)
                if not hit:
                    kept.append(c)
            inside = kept
    shown = [c for c in inside if not _marker(c)]
    text = re.sub(r"\s+", " ", "".join(c.ch for c in shown)).strip()
    bad = any(_bad_char(c) for c in inside)
    if not detail:
        return text, bad
    visible = [c for c in shown if not c.ch.isspace()]
    mr = max((c.right for c in visible), default=None)
    cont = False
    if visible:
        yc = float(np.mean([c.cy for c in visible]))
        cont = any(c.cx > x1 and abs(c.cy - yc) <= 2.0 and c.cx - x1 <= 6.0 and not c.ch.isspace() for c in chars)
    return WidgetRead(text, bad, any(c.invisible for c in inside), mr, cont)


# ---- emission classes (A): what kind of evidence produced a value ----------------
CLASS_NUMERIC = "numeric"                # typed numerics read from the text layer (Number, Dollars, Percent, Identifier, Month, Day)
CLASS_CHOICE = "choice"                  # /Ch dropdowns mapped through /Opt
CLASS_CHECKBOX_BOX = "checkbox_box"      # Lane 3 through a located box interior
CLASS_CHECKBOX_BOXLESS = "checkbox_boxless"   # Lane 3 where the blank draws no box (read from the rect core)
CLASS_FREE_TEXT = "free_text"
CLASS_OCR_NUMERIC = "ocr_numeric"            # Lane 2 (and any total derived from a Lane 2 value): never served by default (A12)
# Classes a consumer serves by default; the shadow artifact keeps every class. Free text and the boxless
# path are shadow-only until M3 decides from shadow data, a held-out perturbation set and the hand audit.
SERVE_CLASSES_DEFAULT = frozenset({CLASS_NUMERIC, CLASS_CHOICE, CLASS_CHECKBOX_BOX})
_NUMERIC_EFFECTIVE = {"Number", "Dollars", "Percent", "Identifier", "Month", "Day"}


def emission_class_text(et: str, ft: str) -> str:
    """The class of a Lane 1 value from its effective type and widget type."""
    if ft == "/Ch":
        return CLASS_CHOICE
    return CLASS_NUMERIC if et in _NUMERIC_EFFECTIVE else CLASS_FREE_TEXT


def serve_values(values: dict, classes=SERVE_CLASSES_DEFAULT) -> dict:
    """The values (extract() shape) whose `emission_class` is in `classes`. A record without a class is not served."""
    ocr_ok = CLASS_OCR_NUMERIC in classes
    return {k: r for k, r in values.items() if r.get("emission_class") in classes
            and (ocr_ok or (r.get("lane") != 2 and 2 not in (r.get("derived_lanes") or ())))}      # OCR evidence is excluded by construction


# ---- edge-continuation guard (B3): shared by Lane 1 and the Lane 2 crops ----------
EDGE_GUARD = True            # glyph boxes crossing / hugging the rect's left or right edge
MULTILINE_GUARD = True       # a multi-line read whose paragraph runs past the rect's top or bottom
EDGE_NEAR_PT = 1.0           # a glyph whose box starts within this of an edge, outside it, is a continuation
EDGE_LINE_TOL_PT = 2.0       # glyphs within this of a read line's height are on that line
MULTILINE_REACH = 1.5        # lines above/below the rect within this many line pitches belong to the same paragraph


@dataclass(frozen=True)
class GlyphBox:
    """One non-form glyph (or OCR word box) in template points: horizontal extent, line height and,
    when known, vertical extent (`top` > `bottom`, y up) and the text it shows (`ch`; a word box
    carries its whole word, so its character width is width / len(ch)). Nothing here is specific
    to the PDF text layer: Lane 2's OCR word boxes build the same object."""
    left: float
    right: float
    cy: float
    top: float | None = None
    bottom: float | None = None
    ch: str = ""

    @property
    def cx(self) -> float:
        return (self.left + self.right) / 2.0


def glyph_boxes(chars: list[PageChar], static_chars: tuple[PageChar, ...] | list[PageChar], rect: list[float],
                reach: float = 40.0) -> list[GlyphBox]:
    """Visible, non-label glyph boxes near `rect` (template space), for `edge_continuation`.

    `static_chars` are the blank template page's characters; a glyph that coincides with one
    (position within STATIC_MATCH_PT, same character) is form text, not the school's answer.
    """
    x0, y0, x1, y1 = rect
    near_static = [s for s in static_chars if x0 - reach <= s.cx <= x1 + reach and y0 - reach <= s.cy <= y1 + reach]
    out = []
    for c in chars:
        if c.ch.isspace() or _marker(c) or not (x0 - reach <= c.cx <= x1 + reach and y0 - reach <= c.cy <= y1 + reach):
            continue
        if any(abs(c.cx - s.cx) <= STATIC_MATCH_PT and abs(c.cy - s.cy) <= STATIC_MATCH_PT and c.ch == s.ch for s in near_static):
            continue
        out.append(GlyphBox(c.box_left, c.right, c.cy, c.top, c.bottom, c.ch))
    return out


def edge_continuation(glyphs: list[GlyphBox], rect: list[float], *, multiline: bool = True) -> str | None:
    """Does the printed answer continue past the widget rect? A reason means abstain, else None.

    `glyphs` are the non-form glyph boxes (or OCR word boxes) around the rect. The read is the
    glyphs whose centre lies inside the rect, grouped into lines. For each line, any glyph on
    the line whose box crosses the rect's left or right edge, or lies outside it with a gap of
    at most EDGE_NEAR_PT to it, means the rect cuts a longer string ("24" of "24038",
    "lth" of "Physical Ed & Health"); a multi-line read with more of its paragraph above or
    below the rect is cut the same way (`multiline`: pass False for numbers and dropdowns,
    where a second glyph line is a neighbouring table row, not more of the answer). The edge
    test is used for Number, Text and /Ch alike.
    """
    x0, y0, x1, y1 = rect
    inside = sorted((g for g in glyphs if x0 <= g.cx <= x1 and y0 <= g.cy <= y1), key=lambda g: -g.cy)
    if not inside:
        return None
    lines: list[list[GlyphBox]] = []
    for g in inside:
        if lines and abs(g.cy - float(np.mean([h.cy for h in lines[-1]]))) <= EDGE_LINE_TOL_PT:
            lines[-1].append(g)
        else:
            lines.append([g])
    if EDGE_GUARD:
        for ln in lines:
            yc = float(np.mean([h.cy for h in ln]))
            for g in glyphs:
                if abs(g.cy - yc) > EDGE_LINE_TOL_PT:
                    continue
                if g.left < x0 < g.right:
                    return "glyph_crosses_left_edge"
                if g.left < x1 < g.right:
                    return "glyph_crosses_right_edge"
                if g.cx > x1 and g.left - x1 <= EDGE_NEAR_PT:
                    return "glyph_past_right_edge"
                if g.cx < x0 and x0 - g.right <= EDGE_NEAR_PT:
                    return "glyph_past_left_edge"
    if MULTILINE_GUARD and multiline and len(lines) >= 2:
        ys = [float(np.mean([h.cy for h in ln])) for ln in lines]
        pitch = float(np.median([a - b for a, b in zip(ys, ys[1:])])) or 10.0
        for g in glyphs:
            if x0 <= g.cx <= x1 and ((y1 < g.cy <= y1 + MULTILINE_REACH * pitch) or (y0 - MULTILINE_REACH * pitch <= g.cy < y0)):
                return "multiline_overflow"
    return None


STRADDLE_GUARD = True        # free text: a line cut by the rect's top or bottom is overflow
TOKEN_GUARD = True           # numeric reads: the printed number must lie wholly in the rect
SIZE_GUARD = True            # ... and be set in one size on one baseline
TOKEN_GAP_RATIO = 0.35       # a gap above this share of the median character width starts a new token (a word space is ~0.5)
PUNCT_GAP_RATIO = 1.25       # ... except a sign, point, comma, percent or currency mark, which attaches within about one character cell
                             # (glyph boxes are tight: a point before a "1" sits a full side bearing away from it)
SIGN_PUNCT = "-+\u2212\u2013\u2014.,$%()"
SIZE_MIN_RATIO = 0.8         # a digit shorter than this share of the tallest digit of its token is a raised/smaller run
BASELINE_MAX_SHIFT = 0.25    # digit bottoms of one token differ by at most this share of the digit height


def _lines_by_centre(glyphs: list[GlyphBox]) -> list[list[GlyphBox]]:
    lines: list[list[GlyphBox]] = []
    for g in sorted(glyphs, key=lambda g: -g.cy):
        if lines and abs(g.cy - float(np.mean([h.cy for h in lines[-1]]))) <= EDGE_LINE_TOL_PT:
            lines[-1].append(g)
        else:
            lines.append([g])
    return lines


def line_straddles_rect(glyphs: list[GlyphBox], rect: list[float]) -> str | None:
    """Free text: is a printed line cut by the rect's top or bottom? Reason `line_straddles_rect` or None.

    The glyphs in the rect's horizontal span are grouped into lines. A line with glyph centres on
    both sides of the rect's top (or bottom) edge is a line the rect cuts in two: reading the
    centres inside gives the garbled half ("can be used i li f SAT/ACT"). The line is overflow,
    whatever the text says.
    """
    x0, y0, x1, y1 = rect
    for ln in _lines_by_centre([g for g in glyphs if x0 <= g.cx <= x1]):
        inside = [g for g in ln if y0 <= g.cy <= y1]
        if inside and len(inside) < len(ln):
            return "line_straddles_rect"
    return None


def numeric_token_gate(glyphs: list[GlyphBox], rect: list[float]) -> str | None:
    """Numeric reads: is the printed number wholly inside the rect, in one size on one baseline?

    `glyphs` are the non-form glyph or OCR word boxes around the rect. The read is the boxes whose
    centre lies in the rect. Starting from them, the token grows over every box that overlaps the
    token's vertical extent and sits within TOKEN_GAP_RATIO of the median character width of
    either end, so a sign, a decimal point or a comma (whose centre sits far below the digits'
    but whose extent lies within them) belongs to its digits, and so do the digits of a neighbouring
    cell that the same string continues into. Reasons:
      token_crosses_rect  a box of the token has its centre outside the rect (the rect holds only
                          part of a printed token, or a token crosses its edge)
      mixed_glyph_size    digits of the token differ in height by more than SIZE_MIN_RATIO, or
                          stand on different baselines (a superscript or footnote marker)
    """
    x0, y0, x1, y1 = rect
    read = [g for g in glyphs if x0 <= g.cx <= x1 and y0 <= g.cy <= y1]
    if not read:
        return None
    ext = [(g.bottom, g.top) for g in read if g.top is not None and g.bottom is not None]
    widths = [(g.right - g.left) / max(1, len(g.ch)) for g in read if g.ch.strip() and not g.ch.strip() in ",.-+$%()'"]
    widths = [w for w in widths if w > 0] or [(g.right - g.left) / max(1, len(g.ch)) for g in read]
    wmed = float(np.median(widths)) if widths else 0.0
    if wmed <= 0:
        return None
    gap_max = TOKEN_GAP_RATIO * wmed
    punct_max = PUNCT_GAP_RATIO * wmed
    token = list(read)
    lo = min(e[0] for e in ext) if ext else min(g.cy for g in read) - EDGE_LINE_TOL_PT
    hi = max(e[1] for e in ext) if ext else max(g.cy for g in read) + EDGE_LINE_TOL_PT

    def on_line(g: GlyphBox) -> bool:
        if g.top is not None and g.bottom is not None:
            return g.bottom < hi and g.top > lo
        return lo <= g.cy <= hi
    read_ids = {id(g) for g in read}
    rest = [g for g in glyphs if id(g) not in read_ids and on_line(g)]
    grew = True
    while grew and rest:
        grew = False
        tl, tr = min(g.left for g in token), max(g.right for g in token)
        for g in list(rest):
            gm = punct_max if g.ch.strip() and all(ch in SIGN_PUNCT for ch in g.ch.strip()) else gap_max
            if (tl - g.right <= gm and g.left <= tr) or (g.left - tr <= gm and g.right >= tl):
                token.append(g)
                rest.remove(g)
                grew = True
    if TOKEN_GUARD and any(not (x0 <= g.cx <= x1 and y0 <= g.cy <= y1) for g in token):
        return "token_crosses_rect"
    if SIZE_GUARD:
        digits = [g for g in token if g.ch.isdigit() and g.top is not None and g.bottom is not None]
        if len(digits) >= 2:
            hs = [g.top - g.bottom for g in digits]
            if min(hs) < SIZE_MIN_RATIO * max(hs):
                return "mixed_glyph_size"
            if max(g.bottom for g in digits) - min(g.bottom for g in digits) > BASELINE_MAX_SHIFT * max(hs):
                return "mixed_glyph_size"
    return None


def normalise_text_value(raw: str, value_type: str | None, tag: str = "") -> tuple[str | None, str | None]:
    """Normalise a text read by effective type. Returns (value, reject_reason)."""
    et = effective_type(tag, value_type, "/Tx")
    if et == "Identifier":
        return (raw, None) if _IDENT_RE.match(raw) else (None, "not_digits")
    if et in ("Number", "Dollars", "Percent"):
        m = _NUM_RE.match(raw)
        if not m:
            return None, "not_numeric"
        if _THOUSANDS_DOT_RE.match(raw) and (GRAMMAR_ALL_TYPES or value_type in INTEGER_VALUE_TYPES):
            return None, "ambiguous_thousands_separator"
        v = m.group("n").replace(",", "")
        if et == "Percent" and not (0 <= float(v) <= 100):
            return None, "percent_out_of_range"
        return v, None
    if et == "Month":
        return (raw, None) if re.fullmatch(r"[0-9]{1,2}", raw) and 1 <= int(raw) <= 12 else (None, "bad_month")
    if et == "Day":
        return (raw, None) if re.fullmatch(r"[0-9]{1,2}", raw) and 1 <= int(raw) <= 31 else (None, "bad_day")
    return raw, None


def choice_to_export(raw: str, opt: list[list[str]] | None, *, clipped: bool = False) -> tuple[str | None, str | None]:
    """Map a /Ch display string to its export value through /Opt: (export, reason).

    Matching ignores case and all whitespace (flattened dropdowns often lose word
    gaps). A read cut off at the widget edge ("per semester h") maps only when it
    is a prefix of exactly one display string. An exact match that is a proper
    prefix of another option ("per semester" vs "per semester hour") abstains
    when `clipped` (the glyphs run to, or past, the rect edge).
    """
    if not opt:
        return None, "choice_not_in_opt"

    def k(x: str) -> str:
        return re.sub(r"\s+", "", x).lower()

    key = k(raw)
    for export, display in opt:
        if k(display) == key:
            shadowed = any(k(d2).startswith(key) and k(d2) != key for _e, d2 in opt)
            if shadowed and clipped:
                return None, "choice_possibly_clipped"
            return export, None
    for export, _display in opt:
        if k(export) == key:
            return export, None
    if re.fullmatch(r"[0-9]+", key):  # editable MM/DD combos: "08" is the option "8"
        for export, display in opt:
            if re.fullmatch(r"[0-9]+", k(display)) and int(k(display)) == int(key):
                return export, None
    if len(key) >= 4:
        hits = [export for export, display in opt if k(display).startswith(key)]
        if len(hits) == 1:
            return hits[0], None
    return None, "choice_not_in_opt"


# --------------------------------------------------------------------------
# Lane 3: checkboxes and radios (ink density, baseline-subtracted)
# --------------------------------------------------------------------------

# A box is measured where the print draws it: the white interior enclosed by the box's own frame is
# found by flood fill from the rect's centre, and the mark is the ink density of the central part of
# that interior. Frame, bevel and template glyph are therefore never inside the measured area, so the
# score does not depend on where the print puts the box (sub-point offsets, boxes bigger or heavier
# than the template's) and an empty box scores ~0 with no baseline to subtract.
INTERIOR_WHITE = 225        # gray level from which a pixel counts as the box's white interior
INTERIOR_MARGIN_PT = 3.0    # the flood is confined to the rect plus this margin; leaving it means "no closed box"
INTERIOR_SEED_PT = 1.6      # seeds: white pixels within this of the rect centre (a check mark may split the interior)
INTERIOR_INSET = 0.20       # central share of the interior that is measured: the inner 60%
INTERIOR_MAX_OFFSET_PT = 2.5   # the interior's centre must lie this close to the rect's centre
INTERIOR_ASPECT = (0.6, 1.7)   # width / height of an interior
INTERIOR_NEST_RATIO = 1.4      # print interior / template interior (area) above which pinholes are closed
INTERIOR_MIN_PT = 2.5          # smaller interiors are not boxes
INK_ONLY_DENSITY = True     # L1: only ink darker than the interior-white level counts (a uniform tint or veil is not a mark)
MULTI_MARK_GUARD = True     # B4: two or more options of a group at or above the threshold abstain before any winner margin
STROKE_GUARD = True         # B3: ink in the box that continues as a stroke or a text run beyond it is not a mark
STROKE_FRAME_PT = 3.0       # the strips start this far from the interior (the frame and its bevel are not "beyond the box")
STROKE_INK = 160            # gray below this is ink in a strip
STROKE_COVER = 0.5          # a strip one box long with ink on at least this share of its length continues the stroke
LANE3_INSET = 0.35          # boxless widgets (no frame to avoid): the central 30% of the rect
LANE3_THRESHOLD = 0.04      # interior ink density that counts as checked (cohort controls: blank boxes <= 0.012, checks >= 0.085)
LANE3_MARGIN = 0.03         # radio group: winner must beat the runner-up by this
# "fill in one only" groups: two checked members mean a misread, so abstain on all
FILL_ONE_GROUPS = (
    ("AP_NOTF_DL_FRSH_I", "AP_NOTF_DL_FRSH", "AP_NOTF_DL_OTH"),                   # C16
    ("AP_REPLY_DL", "AP_REPLY_DL_NO", "AP_REPLY_DL_MUST", "AP_REPLY_OTH"),         # C17
)


@dataclass
class Interior:
    """The white interior of a box as the print draws it (216-DPI pixel rows/cols of the page render)."""
    r0: int
    r1: int
    c0: int
    c1: int
    w_pt: float
    h_pt: float
    dcx_pt: float
    dcy_pt: float


def _flood_interior(gray: np.ndarray, rect: list[float], dx: float, dy: float, close: bool):
    """The fill itself. Returns (Interior | None, reason | None, region_area_px)."""
    x0, y0, x1, y1 = rect
    r0, r1, c0, c1 = template_rect_to_pixels([x0 - INTERIOR_MARGIN_PT, y0 - INTERIOR_MARGIN_PT,
                                              x1 + INTERIOR_MARGIN_PT, y1 + INTERIOR_MARGIN_PT], dx, dy, INK_DPI)
    if r0 < 0 or c0 < 0 or r1 > gray.shape[0] or c1 > gray.shape[1]:
        return None, "box_off_page", 0
    white_raw = gray[r0:r1, c0:c1] >= INTERIOR_WHITE
    white = white_raw.copy()
    if close:
        # one-pixel pinholes in an anti-aliased frame must not open it: the fill runs on the white eroded
        # by one pixel and its result is grown back by one pixel
        white[1:] &= white_raw[:-1]
        white[:-1] &= white_raw[1:]
        white[:, 1:] &= white_raw[:, :-1]
        white[:, :-1] &= white_raw[:, 1:]
    H, Wd = white.shape
    k = INK_DPI / 72.0
    cy, cx = (H - 1) / 2.0, (Wd - 1) / 2.0
    yy0, xx0 = np.mgrid[0:H, 0:Wd]
    dist = np.hypot(yy0 - cy, xx0 - cx)
    seeds = white & (dist <= INTERIOR_SEED_PT * k)
    if not seeds.any():
        # a solid mark (a radio's dot) covers the centre: start from the white nearest to it, inside the box
        near = white & (dist <= 0.5 * min(x1 - x0, y1 - y0) * k)
        if not near.any():
            return None, "box_not_closed", 0
        seeds = near & (dist <= dist[near].min() + 1.5)
    sy, sx = np.nonzero(seeds)
    seen = np.zeros_like(white)
    stack = [(int(a), int(b)) for a, b in zip(sy, sx)]
    for y, x in stack:
        seen[y, x] = True
    while stack:
        y, x = stack.pop()
        for ny, nx in ((y - 1, x), (y + 1, x), (y, x - 1), (y, x + 1)):
            if not (0 <= ny < H and 0 <= nx < Wd):
                return None, "box_not_closed", 0
            if white[ny, nx] and not seen[ny, nx]:
                seen[ny, nx] = True
                stack.append((ny, nx))
    if close:
        grown = seen.copy()
        grown[1:] |= seen[:-1]
        grown[:-1] |= seen[1:]
        grown[:, 1:] |= seen[:, :-1]
        grown[:, :-1] |= seen[:, 1:]
        seen = grown & white_raw
    yy, xx = np.nonzero(seen)
    a, b, c, d = int(yy.min()), int(yy.max()) + 1, int(xx.min()), int(xx.max()) + 1
    w_pt, h_pt = (d - c) / k, (b - a) / k
    # centre offsets in template points (x right, y up) relative to the rect centre
    dcx = ((c0 + (c + d) / 2.0) / k - dx) - (x0 + x1) / 2.0
    dcy = (792.0 - (r0 + (a + b) / 2.0) / k - dy) - (y0 + y1) / 2.0
    lo, hi = INTERIOR_ASPECT
    if (abs(dcx) > INTERIOR_MAX_OFFSET_PT or abs(dcy) > INTERIOR_MAX_OFFSET_PT or min(w_pt, h_pt) < INTERIOR_MIN_PT
            or not lo <= w_pt / h_pt <= hi):
        return None, "box_geometry", 0
    return Interior(r0 + a, r0 + b, c0 + c, c0 + d, w_pt, h_pt, dcx, dcy), None, (b - a) * (d - c)


def locate_interior(gray: np.ndarray, rect: list[float], dx: float, dy: float,
                    template_interior: "Interior | None" = None) -> tuple[Interior | None, str | None]:
    """Find the interior of the box the print draws at `rect` (template space, page shift applied).

    Returns (interior, None) or (None, reason). The interior is the connected white region (4-neighbour,
    gray >= INTERIOR_WHITE) around the rect's centre, confined to the rect plus INTERIOR_MARGIN_PT:
    a frame that is not closed leaks out of that window ("box_not_closed"); a region that is not
    box-shaped or not centred on the rect ("box_geometry") is some other white space (a reflowed line,
    typed text). All white pixels near the centre seed the fill, so a check mark that splits the
    interior still yields the whole box.

    `template_interior` is the same measurement on the blank template. A template whose box has a second,
    inner frame (FORM_DOM_*) has a small interior there; if the print's fill comes out much bigger
    (INTERIOR_NEST_RATIO) it has run through a pinhole of that inner frame into the ring around it, so the
    fill is repeated with pinholes closed and, if that finds nothing, the box is not read.
    """
    it, why, area = _flood_interior(gray, rect, dx, dy, close=False)
    if it is None or template_interior is None:
        return it, why
    t_area = (template_interior.r1 - template_interior.r0) * (template_interior.c1 - template_interior.c0)
    if area > INTERIOR_NEST_RATIO * t_area:
        it2, why2, _a2 = _flood_interior(gray, rect, dx, dy, close=True)
        return (it2, None) if it2 is not None else (None, why2 or "box_geometry")
    return it, why


def interior_density(gray: np.ndarray, it: Interior, inset: float = INTERIOR_INSET) -> float | None:
    """Mean ink (0 white .. 1 black) of the central part of a located interior."""
    ih, iw = int(round((it.r1 - it.r0) * inset)), int(round((it.c1 - it.c0) * inset))
    core = gray[it.r0 + ih:it.r1 - ih, it.c0 + iw:it.c1 - iw]
    if core.size == 0:
        return None
    return _ink_density(core)


def _crop_density(gray: np.ndarray, rect: list[float], dx: float, dy: float, dpi: float, inset: float) -> float | None:
    """Mean ink density (0 white, 1 black) of a rect's interior in a template-scale render."""
    x0, y0, x1, y1 = rect
    ix, iy = (x1 - x0) * inset, (y1 - y0) * inset
    r0, r1, c0, c1 = template_rect_to_pixels([x0 + ix, y0 + iy, x1 - ix, y1 - iy], dx, dy, dpi)
    if r1 <= r0 or c1 <= c0 or r0 < 0 or c0 < 0 or r1 > gray.shape[0] or c1 > gray.shape[1]:
        return None
    return _ink_density(gray[r0:r1, c0:c1])


def _ink_density(px: np.ndarray) -> float:
    """Mean ink of a patch (0 white .. 1 black). With INK_ONLY_DENSITY a pixel counts only by how far it is
    darker than INTERIOR_WHITE: a uniformly gray paper, scan tone or box background (all at or above the
    white level the box was found with) adds nothing, where a mean of (255 - gray) would read it as a mark."""
    if INK_ONLY_DENSITY:
        w = float(INTERIOR_WHITE)
        return float(np.clip(w - px.astype(np.float32), 0.0, None).mean() / w)
    return float((255.0 - px.astype(np.float32)).mean() / 255.0)


def stroke_continues(gray: np.ndarray, tgray: np.ndarray, it: Interior, dx: float, dy: float) -> str | None:
    """Does the ink in a located box continue as a stroke or a text run beyond it? Reason or None.

    A strike-through, an underline or an overflowing word crosses the box and goes on into the row
    around it; a real mark stays in or near its box. Two strips one box long lie in the box's row,
    left and right of the interior (past STROKE_FRAME_PT, which holds the frame and its bevel). The ink in a strip is the page's dark pixels
    that the blank does not have there (the form's own label text is not an answer). A strip
    with ink along STROKE_COVER of its length means a stroke leaves the box: abstain.
    """
    k = INK_DPI / 72.0
    f = int(round(STROKE_FRAME_PT * k))
    w = it.c1 - it.c0
    # the blank's ink at the same place, thickened by the page shift's uncertainty
    pad = 2
    def new_ink(r0: int, r1: int, c0: int, c1: int) -> np.ndarray | None:
        if r0 < pad or c0 < pad or r1 > gray.shape[0] - pad or c1 > gray.shape[1] - pad:
            return None
        pr0, pr1 = int(round(r0 + dy * k)), int(round(r1 + dy * k))   # print pixel -> blank pixel (shift undone)
        pc0, pc1 = int(round(c0 - dx * k)), int(round(c1 - dx * k))
        if pr0 < pad or pc0 < pad or pr1 > tgray.shape[0] - pad or pc1 > tgray.shape[1] - pad:
            return None
        tpl = tgray[pr0 - pad:pr1 + pad, pc0 - pad:pc1 + pad] < STROKE_INK
        tpl = _dilate(tpl, pad)[pad:-pad, pad:-pad] if tpl.size else tpl
        ink = gray[r0:r1, c0:c1] < STROKE_INK
        h, w = min(ink.shape[0], tpl.shape[0]), min(ink.shape[1], tpl.shape[1])      # the blank's render can differ by a pixel at other DPIs
        return ink[:h, :w] & ~tpl[:h, :w]
    # (the row only: above and below a box in a column of boxes lie the neighbouring boxes)
    for r0, r1, c0, c1 in ((it.r0, it.r1, it.c1 + f, it.c1 + f + w), (it.r0, it.r1, it.c0 - f - w, it.c0 - f)):
        m = new_ink(r0, r1, c0, c1)
        if m is None or m.size == 0:
            continue
        if float(m.any(axis=0).mean()) >= STROKE_COVER:
            return "stroke_continues_beyond_box"
    return None


def _is_btn_checked(scores: list[float | None], threshold: float, margin: float):
    """Pick the checked widget of a field from its baseline-subtracted scores.

    Returns (index | None, reason | None). A lone widget is checked when its
    score reaches the threshold. In a group the top widget wins when it reaches
    the threshold and beats the runner-up by `margin`; otherwise nothing is
    emitted and the reason is "ambiguous_radio"; a group with two or more options at or above the
    threshold is "multiple_options_marked" (a second mark is not outvoted by a stronger first one). Interior scores are bimodal (blank
    boxes ~0, marks >= 0.06), so no gray band is needed.
    """
    live = [(s, i) for i, s in enumerate(scores) if s is not None]
    if not live:
        return None, None
    live.sort(key=lambda t: (-t[0], t[1]))
    top_s, top_i = live[0]
    if top_s < threshold:
        return None, None
    if MULTI_MARK_GUARD and len(live) > 1 and live[1][0] >= threshold:
        return None, "multiple_options_marked"      # two options carry a mark: no winner, whatever their margin
    if len(live) == 1:
        return top_i, None
    if top_s - live[1][0] < margin:
        return None, "ambiguous_radio"
    return top_i, None


# --------------------------------------------------------------------------
# validation (PRD §4 steps 1 and 2)
# --------------------------------------------------------------------------

_C9_RE = re.compile(r"^(SAT1_COMP|SAT1_VERB|SAT1_MATH|ACT_[A-Z]+)_(25|50|75)TH_P$")
_C9_RANGE = {"SAT1_COMP": (400, 1600), "SAT1_VERB": (200, 800), "SAT1_MATH": (200, 800)}
_GENDERS = ("MEN", "WMN", "UNK", "NON_BINARY")


def _num(v: Any) -> float | None:
    m = _NUM_RE.match(str(v).strip())
    return float(m.group("n").replace(",", "")) if m else None


def check_identities(tag_values: dict[str, str], tags_in_map: set[str]) -> list[dict]:
    """Cross-field identities over {pdf_tag: value}. Returns failure records.

    B1: total degree-seeking = first-year + other first-year + all other
    degree-seeking rows (blank rows count as 0 when the total is present).
    C1: applied >= admitted >= enrolled (first-time, first-year totals).
    C9: 25th <= 50th <= 75th and scores inside the test's range.
    """
    fails: list[dict] = []

    def tag(*names):
        for n in names:
            if n in tags_in_map:
                return n
        return None

    for load in ("FT", "PT"):
        for g in _GENDERS:
            total = tag(f"EN_TOT_DEG_{load}_{g}_N", f"CDS_EN_TOT_DEG_{load}_{g}_N")
            rows = [tag(f"EN_FRSH_{load}_{g}_N", f"CDS_EN_FRSH_{load}_{g}_N"),
                    tag(f"EN_OTH_1ST_{load}_{g}_N", f"CDS_EN_OTH_1ST_{load}_{g}_N"),
                    tag(f"EN_DEG_{load}_{g}_N", f"CDS_EN_DEG_{load}_{g}_N")]
            if not total or total not in tag_values or not all(rows):
                continue
            t = _num(tag_values[total])
            parts = [_num(tag_values.get(r, "0")) for r in rows]
            if t is None or any(p is None for p in parts):
                continue
            if abs(sum(parts) - t) > 1e-6:
                fails.append({"identity": "B1_total_degree_seeking", "tags": [total] + rows,
                              "detail": f"rows sum to {sum(parts):g}, total reads {t:g}"})

    c1 = [tag("AP_RECD_1ST_N"), tag("AP_ADMT_1ST_N"), tag("EN_TOT_1ST_N")]
    if all(c1) and all(t in tag_values for t in c1):
        a, d, e = (_num(tag_values[t]) for t in c1)
        if None not in (a, d, e) and not (a >= d >= e):
            fails.append({"identity": "C1_applied_admitted_enrolled", "tags": c1,
                          "detail": f"applied {a:g}, admitted {d:g}, enrolled {e:g}"})

    groups: dict[str, dict[str, float]] = {}
    for t, v in tag_values.items():
        m = _C9_RE.match(t)
        n = _num(v)
        if m and n is not None:
            groups.setdefault(m.group(1), {})[m.group(2)] = n
    for grp, pct in sorted(groups.items()):
        lo, hi = _C9_RANGE.get(grp, (1, 36) if grp.startswith("ACT_") else (None, None))
        vals = [pct[k] for k in ("25", "50", "75") if k in pct]
        tags = [f"{grp}_{k}TH_P" for k in ("25", "50", "75") if k in pct]
        if vals != sorted(vals):
            fails.append({"identity": "C9_percentile_order", "tags": tags, "detail": f"{vals}"})
        if lo is not None and any(not (lo <= v <= hi) for v in vals):
            fails.append({"identity": "C9_score_range", "tags": tags, "detail": f"{vals} outside {lo}-{hi}"})
    return fails


# --------------------------------------------------------------------------
# schema
# --------------------------------------------------------------------------

@functools.lru_cache(maxsize=None)
def _schema(year: str) -> dict:
    with bfm.schema_path_for(year).open() as f:
        return json.load(f)


def _import_tier2():
    """decode_button_value and the B1 derivation, imported the way the worker does."""
    tools = Path(__file__).resolve().parents[1]
    for p in (tools, tools / "extraction_worker"):
        if str(p) not in sys.path:
            sys.path.insert(0, str(p))
    from tier2_extractor.extract import decode_button_value  # noqa: WPS433
    from b1_derive_totals import apply_b1_derived_all_totals  # noqa: WPS433
    return decode_button_value, apply_b1_derived_all_totals


# --------------------------------------------------------------------------
# extraction
# --------------------------------------------------------------------------

SUBPOINT_ALIGN = True            # Part 0 (M2): refine the applied page shift to one INK_DPI pixel (1/3 pt)
SUBPOINT_RANGE_PX = 3            # search +-3 px around the whole-point shift
SUBPOINT_MIN_GAIN = 0.01         # a nonzero refinement must beat (0, 0) by this much recall
SUBPOINT_POINTS = 4000


def refine_subpoint_shift(gray: np.ndarray, tgray: np.ndarray, dx: float, dy: float) -> tuple[float, float]:
    """Residual page shift below one point, in template points (x right, y up), from the INK_DPI renders.

    The page's static ink (gray < INK_THRESHOLD) against the blank's, at the whole-point shift (dx, dy)
    plus a residual of up to SUBPOINT_RANGE_PX pixels each way. (0, 0) unless a residual beats it by
    SUBPOINT_MIN_GAIN of recall, so a page that is already registered is never moved.
    """
    k = INK_DPI / 72.0
    h, w = min(gray.shape[0], tgray.shape[0]), min(gray.shape[1], tgray.shape[1])
    pg = _dilate(gray[:h, :w] < bfm.INK_THRESHOLD, 1)
    ty, tx = np.nonzero(tgray[:h, :w] < bfm.INK_THRESHOLD)
    if ty.size < MIN_TEMPLATE_INK_PX:
        return 0.0, 0.0
    ty, tx = _subsample(ty, tx, SUBPOINT_POINTS)
    bx, by = int(round(dx * k)), int(round(-dy * k))        # page content: col + dx*k, row - dy*k
    r = SUBPOINT_RANGE_PX
    grid = np.zeros((2 * r + 1, 2 * r + 1))
    for iy in range(-r, r + 1):
        for ix in range(-r, r + 1):
            yy, xx = ty + by + iy, tx + bx + ix
            ok = (yy >= 0) & (yy < h) & (xx >= 0) & (xx < w)
            grid[iy + r, ix + r] = float(pg[yy[ok], xx[ok]].sum()) / ty.size
    best, base = float(grid.max()), float(grid[r, r])
    if best - base < SUBPOINT_MIN_GAIN:
        return 0.0, 0.0
    # the page's ink was dilated by one pixel, so the best recall is a plateau: its centre is the shift
    top = grid >= best - 1e-9
    start = tuple(int(v) for v in np.argwhere(top)[0])
    comp, stack = {start}, [start]
    while stack:                                       # 8-connected plateau containing a maximum; never average disconnected maxima
        y, x = stack.pop()
        for dy_ in (-1, 0, 1):
            for dx_ in (-1, 0, 1):
                n = (y + dy_, x + dx_)
                if 0 <= n[0] < top.shape[0] and 0 <= n[1] < top.shape[1] and top[n] and n not in comp:
                    comp.add(n)
                    stack.append(n)
    iys = np.array([c[0] for c in comp])
    ixs = np.array([c[1] for c in comp])
    cy, cx = int(round(iys.mean())), int(round(ixs.mean()))
    if (cy, cx) not in comp:                           # the centre of a non-convex plateau may fall off it: take its nearest member
        cy, cx = min(comp, key=lambda c: (c[0] - iys.mean()) ** 2 + (c[1] - ixs.mean()) ** 2)
    ix, iy = cx - r, cy - r
    return ix / k, -iy / k


class _PageCtx:
    """Everything the lanes need about one matched page, built lazily."""

    def __init__(self, doc, q, p, year, res: MatchResult):
        self.page = doc[q]
        self.q, self.p, self.year = q, p, year
        self.geom = page_geometry(self.page)
        a = res.alignment.get(q) or {"dx": 0.0, "dy": 0.0}
        self.dx0, self.dy0 = a["dx"], a["dy"]          # the whole-point page shift Stage 1 applied
        self._sub = None
        self.applied_px = (int(round(self.dx0)), int(round(-self.dy0)))   # (cols, rows) at 72 DPI
        self.bands = set(res.band_rejections.get(q, ()))
        self._chars = None
        self._masks = None
        self._gray = None
        self._tgray = None

    @property
    def sub(self) -> tuple[float, float]:
        """The sub-point refinement of the page shift (template points), estimated once on the INK_DPI render."""
        if self._sub is None:
            self._sub = refine_subpoint_shift(self.gray, self.tgray, self.dx0, self.dy0) if SUBPOINT_ALIGN else (0.0, 0.0)
        return self._sub

    @property
    def dx(self) -> float:
        return self.dx0 + self.sub[0]

    @property
    def dy(self) -> float:
        return self.dy0 + self.sub[1]

    @property
    def chars(self) -> list[PageChar]:
        if self._chars is None:
            self._chars = _chars_to_template(_page_chars_display(self.page, self.geom), self.geom, self.dx, self.dy)
        return self._chars

    @property
    def masks(self) -> PageMasks:
        if self._masks is None:
            self._masks = _page_masks(self.page, self.geom, _template_doc(self.year)[self.p])
        return self._masks

    @property
    def gray(self) -> np.ndarray:
        if self._gray is None:
            self._gray = _render_template_scale(self.page, self.geom, INK_DPI)
        return self._gray

    @property
    def tgray(self) -> np.ndarray:
        if self._tgray is None:
            self._tgray = _render_gray(_template_doc(self.year)[self.p], INK_DPI)
        return self._tgray

    def template_has_box(self, rect: list[float]) -> bool:
        """Does the blank template draw a box outline at this rect (outer ring of the rect)?"""
        tr0, tr1, tc0, tc1 = template_rect_to_pixels(rect, 0.0, 0.0, INK_DPI)
        tpl = self.tgray[tr0:tr1, tc0:tc1] < 200
        h, w = tpl.shape
        if h == 0 or w == 0:
            return False
        ring = np.ones((h, w), dtype=bool)
        ih, iw = int(h * 0.2), int(w * 0.2)
        ring[ih:h - ih, iw:w - iw] = False
        return int((ring & tpl).sum()) >= 20

    def template_interior(self, key, rect: list[float]) -> "tuple[Interior | None, float]":
        """The blank template's own box interior at this rect and the ink density inside it (0 if none)."""
        cache = self.__dict__.setdefault("_tint", {})
        if key not in cache:
            it, _why = locate_interior(self.tgray, rect, 0.0, 0.0)
            d = interior_density(self.tgray, it) if it is not None else None
            cache[key] = (it, d or 0.0)
        return cache[key]

    def template_interior_density(self, key, rect: list[float]) -> float:
        return self.template_interior(key, rect)[1]

    def band_of(self, rect: list[float]) -> int:
        cy = 792.0 - (rect[1] + rect[3]) / 2.0
        return min(BAND_COUNT - 1, max(0, int(cy * BAND_COUNT / 792.0)))

    def new_ink(self, rect: list[float]) -> int:
        """Dark pixels inside the rect that the blank template does not have there."""
        r0, r1, c0, c1 = template_rect_to_pixels(rect, self.dx, self.dy, INK_DPI)
        tr0, tr1, tc0, tc1 = template_rect_to_pixels(rect, 0.0, 0.0, INK_DPI)
        if r0 < 0 or c0 < 0 or r1 > self.gray.shape[0] or c1 > self.gray.shape[1] or r1 <= r0 or c1 <= c0:
            return 0
        tgt = self.gray[r0:r1, c0:c1] < 128
        tpl = _dilate(self.tgray[tr0:tr1, tc0:tc1] < 128, 2)
        h, w = min(tgt.shape[0], tpl.shape[0]), min(tgt.shape[1], tpl.shape[1])
        return int((tgt[:h, :w] & ~tpl[:h, :w]).sum())


PageCtx = _PageCtx          # public name for Lane 2


def _ocr_entry(tag: str, q: int, wi: int, rect: list[float], c: _PageCtx, reason: str) -> dict:
    """A Lane 2 work item: enough to crop the rect again (page, widget index, template rect, applied shift)."""
    return {"pdf_tag": tag, "page": q, "widget": wi, "rect": [round(v, 3) for v in rect],
            "shift": {"dx": c.dx, "dy": c.dy}, "template_page": c.p, "reason": reason}


def widget_gates(c: _PageCtx, tag: str, wi: int, rect: list[float], *, glyphs: list[GlyphBox] | None = None,
                 multiline: bool = True, emission_class: str | None = None) -> str | None:
    """Every per-widget geometry gate a read of `rect` on matched page `c` must pass.

    Shared by Lane 1 (text layer), Lane 3 and the Lane 2 crops, which call it before
    reading a rect. A reason means abstain, else None:
      band_misaligned     the rect's horizontal band disagrees with the page shift
      local_misalignment  the template ink around the rect fits the page better shifted
      glyph_*, multiline_overflow  (only when `glyphs` is given) the printed answer
                          continues past the rect: pass the page's glyph or OCR word boxes
      line_straddles_rect (free_text), token_crosses_rect / mixed_glyph_size (numeric): with
                          `emission_class`, the rules for that class run on the same boxes
    Page-level rejections (B1 residual shift, B2 raster-year veto, duplicate and
    partial-page shifts) are already applied when the page is mapped: a page with a
    context here is one that passed them.
    """
    if c.band_of(rect) in c.bands:
        return "band_misaligned"
    key = (c.year, c.p, tag, wi)
    eq = _equivalent_shifts(c.year, c.p, key, rect, c.masks.t)
    verdict, _gain = local_alignment_check(c.masks, rect, c.applied_px, eq)
    if verdict == "misaligned":
        return "local_misalignment"
    if glyphs is not None:
        why = edge_continuation(glyphs, rect, multiline=multiline)
        if why:
            return why
        if emission_class == CLASS_FREE_TEXT and STRADDLE_GUARD:
            return line_straddles_rect(glyphs, rect)
        if emission_class == CLASS_NUMERIC:
            return numeric_token_gate(glyphs, rect)
    return None


def reject_identity_failures(values: dict[str, dict], tags_in_map: set[str]) -> tuple[list[dict], list[dict]]:
    """Apply PRD 4 identity checks over the union of all lanes' values (mutates `values`).

    `values` is the extract() shape {question_number: record with pdf_tag, value}. Lane 2
    calls this again after it adds its values. Returns (failures, rejected_field_records).
    """
    tag_values = {r["pdf_tag"]: r["value"] for r in values.values() if "pdf_tag" in r}
    ident = check_identities(tag_values, tags_in_map)
    rejected = []
    for fail in ident:
        fail["action"] = "rejected"
        for t in fail["tags"]:
            for qn, r in list(values.items()):
                if r.get("pdf_tag") == t:
                    rejected.append({"pdf_tag": t, "reason": f"identity_failed:{fail['identity']}", "read": r["value"]})
                    del values[qn]
    return ident, rejected


def extract_overlay(
    pdf: bytes | str | Path,
    *,
    detected_year: str | None = None,
    source_name: str = "",
    maps: dict[str, YearMaps] | None = None,
    lane3_threshold: float | None = None,
    lane3_margin: float | None = None,
    lane1_pad: float = 0.0,
    strict_types: bool = True,
    lane2=None,
) -> dict:
    """Stage 1 + Lane 1 + Lane 3 + validation for one PDF (+ Lane 2 when `lane2` is given).

    `lane2` is a callable taking one namespace (see `_extract`): `lane2_ocr.make_hook(engine)`. It adds
    numeric OCR values on the pages Lane 1 cannot read, before the identities run over the union.

    Returns the Tier 2 `extract()` shape (producer, producer_version,
    schema_version, source_pdf, extracted_at, stats, values, unmapped_fields)
    plus `notes`. When Stage 1 does not match (or holds the document), `values` is
    empty and notes.stage1.status/reason say why. `detected_year` can only veto the
    printed header year; it never chooses the map.
    """
    return _extract(pdf, detected_year=detected_year, source_name=source_name, maps=maps, force_year=None,
                    lane3_threshold=lane3_threshold, lane3_margin=lane3_margin, lane1_pad=lane1_pad,
                    strict_types=strict_types, lane2=lane2)


def _diagnostic_extract_forced_year(pdf, force_year: str, **kw) -> dict:
    """DIAGNOSTIC ONLY (wrong-year control in the evaluation script). Not part of the API."""
    out = _extract(pdf, detected_year=None, force_year=force_year, **kw)
    out["notes"]["diagnostic_forced_year"] = force_year
    return out


def _extract(
    pdf, *, detected_year, source_name="", maps=None, force_year=None,
    lane3_threshold=None, lane3_margin=None, lane1_pad=0.0, strict_types=True, lane2=None,
) -> dict:
    lane3_threshold = LANE3_THRESHOLD if lane3_threshold is None else lane3_threshold   # read at call time
    lane3_margin = LANE3_MARGIN if lane3_margin is None else lane3_margin
    data = pdf if isinstance(pdf, (bytes, bytearray)) else Path(pdf).read_bytes()
    maps = maps or load_maps()
    doc = pdfium.PdfDocument(bytes(data))
    res = _forced_match(doc, maps, force_year) if force_year else match_template(doc, maps, detected_year=detected_year)

    out: dict[str, Any] = {
        "producer": PRODUCER, "producer_version": PRODUCER_VERSION,
        "schema_version": res.year, "source_pdf": source_name,
        "extracted_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "values": {}, "unmapped_fields": [],
    }
    notes: dict[str, Any] = {
        "producer_version": PRODUCER_VERSION, "field_map_version": FIELD_MAP_VERSION,
        "source_sha256": hashlib.sha256(data).hexdigest(), "stage1": res.to_dict(),
        "template_year": res.year, "detected_year": detected_year,
    }
    out["notes"] = notes
    if res.status != STATUS_MATCHED:
        out["stats"] = {"schema_fields_populated": 0}
        notes.update({"withheld": [], "withheld_by_reason": {}, "rejected_fields": [], "lane_counts": {},
                      "held": {"status": res.status, "reason": res.reason}})
        return out

    year = res.year
    fmap = maps[year].fmap
    schema = _schema(year)
    tag_field = {f["pdf_tag"]: f for f in schema["fields"] if f.get("pdf_tag")}
    decode_button_value, apply_b1 = _import_tier2()
    by_tpage = {p: q for q, p in res.page_map.items()}
    notes["matched_template_pages"] = len(res.page_map)
    notes["page_map"] = {str(q): p for q, p in res.page_map.items()}

    ctxs: dict[int, _PageCtx] = {}
    withheld: list[dict] = []
    rejected: list[dict] = []
    ocr_widgets: list[dict] = []
    unreadable: set[int] = set()
    invisible_pages: set[int] = set()
    skipped_unjoined = 0
    lane_of: dict[str, str] = {}
    page_of: dict[str, int] = {}
    values: dict[str, dict] = {}

    def ctx_for(q: int, p: int) -> _PageCtx:
        if q not in ctxs:
            ctxs[q] = _PageCtx(doc, q, p, year, res)
        return ctxs[q]

    def hold(tag: str, lane: str, reason: str, q: int | None, widget: int = 0) -> None:
        withheld.append({"pdf_tag": tag, "lane": lane, "reason": reason, "page": q, "widget": widget})

    def gate(c: _PageCtx, tag: str, wi: int, rect: list[float]) -> str | None:
        return widget_gates(c, tag, wi, rect)

    def record(tag: str, value: str, lane, et: str, q: int, eclass: str, extra: dict | None = None) -> None:
        sf = tag_field[tag]
        rec = {"value": value, "pdf_tag": tag, "word_tag": sf.get("word_tag"), "question": sf.get("question"),
               "section": sf.get("section"), "subsection": sf.get("subsection"),
               "value_type": sf.get("value_type"), "effective_type": et, "lane": lane, "emission_class": eclass}
        dec = decode_button_value(value, sf.get("value_options"))
        if dec is not None:
            rec["value_decoded"] = dec
        if extra:
            rec.update(extra)
        values[sf["question_number"]] = rec
        lane_of[tag] = lane
        page_of[tag] = q

    # ---- Lane 1
    for tag, f in fmap["fields"].items():
        if f["ft"] not in ("/Tx", "/Ch"):
            continue
        if f["question_number"] is None:
            skipped_unjoined += 1
            continue
        if tag not in tag_field:
            continue
        et = effective_type(tag, f["value_type"], f["ft"])
        reads: list[tuple[int, int, WidgetRead]] = []
        blocked = False
        for wi, w in enumerate(f["widgets"]):
            p = w["template_page"]
            q = by_tpage.get(p)
            if q is None or q in unreadable:
                blocked = True
                continue
            c = ctx_for(q, p)
            rd = read_widget_text(c.chars, w["rect"], _template_chars(year, p), w["rect"], pad=lane1_pad, detail=True)
            if rd.bad:
                unreadable.add(q)
                blocked = True
                continue
            if rd.invisible:
                invisible_pages.add(q)
                ocr_widgets.append(_ocr_entry(tag, q, wi, w["rect"], c, "invisible_text"))
                hold(tag, "text", "invisible_text", q, wi)
                blocked = True
                continue
            if rd.text:
                why = widget_gates(c, tag, wi, w["rect"], glyphs=glyph_boxes(c.chars, _template_chars(year, p), w["rect"]),
                                    multiline=(et == "Text" and f["ft"] == "/Tx"), emission_class=emission_class_text(et, f["ft"]))
                if why:
                    hold(tag, "text", why, q, wi)
                    blocked = True
                    continue
                if c.new_ink(w["rect"]) < MIN_NEW_INK_PX:
                    hold(tag, "text", "no_rendered_ink", q, wi)
                    blocked = True
                    continue
            reads.append((wi, q, rd))
        nonempty = [r for r in reads if r[2].text]
        if blocked or not nonempty:
            continue
        if len({r[2].text for r in nonempty}) > 1 or len(nonempty) != len(reads):
            hold(tag, "text", "multi_widget_disagreement", nonempty[0][1])
            continue
        wi, q, rd = nonempty[0]
        raw = rd.text
        if f["ft"] == "/Ch":
            clipped = rd.continues or (rd.max_right is not None and rd.max_right > f["widgets"][wi]["rect"][2] - CLIP_EDGE_PT)
            exp, why = choice_to_export(raw, f.get("opt"), clipped=clipped)
            if exp is None:
                rejected.append({"pdf_tag": tag, "reason": why, "read": raw, "page": q})
                continue
            raw = exp
        val, why = normalise_text_value(raw, f["value_type"], tag)
        if why:
            rejected.append({"pdf_tag": tag, "reason": why, "read": raw, "page": q, **({} if strict_types else {"kept": True})})
            if strict_types:
                continue
            val = raw
        record(tag, val, "text", et, q, emission_class_text(et, f["ft"]))
    # a page found unreadable late must not leave earlier reads from it behind
    for qn, r in list(values.items()):
        if r.get("lane") == "text" and page_of.get(r["pdf_tag"]) in unreadable:
            del values[qn]
            lane_of.pop(r["pdf_tag"], None)

    # ---- Lane 3
    ambiguous: list[dict] = []
    for tag, f in fmap["fields"].items():
        if f["ft"] != "/Btn":
            continue
        if f["question_number"] is None:
            skipped_unjoined += 1
            continue
        if tag not in tag_field:
            continue
        row: list[float | None] = []
        first_q = None
        missing_page = False
        unlocated = None
        gate_reason = None
        located: dict[int, Interior] = {}      # widget index -> its box interior (absent: read boxless)
        for wi, w in enumerate(f["widgets"]):
            p = w["template_page"]
            q = by_tpage.get(p)
            if q is None:
                row.append(None)
                missing_page = True
                continue
            first_q = first_q if first_q is not None else q
            c = ctx_for(q, p)
            tit, tdens = c.template_interior((tag, wi), w["rect"])
            it, why_box = locate_interior(c.gray, w["rect"], c.dx, c.dy, tit)
            tgt = interior_density(c.gray, it) if it is not None else None
            if tgt is not None:
                located[wi] = it
                row.append(tgt - tdens)
            elif c.template_has_box(w["rect"]):
                unlocated = unlocated or why_box or "box_not_closed"    # the template draws a box here and the print's is not found
                row.append(None)
            else:
                # the template draws no box here (an N/A option): a mark is the only ink, measured in the rect's core
                tgt = _crop_density(c.gray, w["rect"], c.dx, c.dy, INK_DPI, LANE3_INSET)
                base = _crop_density(c.tgray, w["rect"], 0.0, 0.0, INK_DPI, LANE3_INSET)
                row.append(None if tgt is None or base is None else tgt - base)
        idx, why = _is_btn_checked(row, lane3_threshold, lane3_margin)
        if idx is None and not why:
            continue
        # something would be emitted (or is doubtful): only a group that is verifiably in place is read
        gate_reason = "page_not_matched" if missing_page else None
        if gate_reason is None and unlocated:
            gate_reason = unlocated            # a member's box was not found: the winner cannot be compared with it
        if gate_reason is None:
            for wi, w in enumerate(f["widgets"]):
                q = by_tpage.get(w["template_page"])
                gate_reason = gate(ctx_for(q, w["template_page"]), tag, wi, w["rect"])
                if gate_reason:
                    break
        if gate_reason is None and STROKE_GUARD and idx is not None and idx in located:
            cw = ctx_for(by_tpage[f["widgets"][idx]["template_page"]], f["widgets"][idx]["template_page"])
            gate_reason = stroke_continues(cw.gray, cw.tgray, located[idx], cw.dx, cw.dy)   # boxless winners are not gated here
        if gate_reason:
            hold(tag, "checkbox", gate_reason, first_q)
            continue
        if why:
            ambiguous.append({"pdf_tag": tag, "reason": why, "scores": [None if s is None else round(s, 3) for s in row]})
            hold(tag, "checkbox", why, first_q)
            continue
        exp = f["widgets"][idx]["on_state"]
        wq = by_tpage[f["widgets"][idx]["template_page"]]
        boxless_winner = not ctx_for(wq, f["widgets"][idx]["template_page"]).template_has_box(f["widgets"][idx]["rect"])   # the blank draws no box here
        if exp not in {w["on_state"] for w in f["widgets"]}:
            rejected.append({"pdf_tag": tag, "reason": "illegal_button_state", "read": exp})
            continue
        record(tag, exp, "checkbox", "Button", by_tpage[f["widgets"][idx]["template_page"]],
               CLASS_CHECKBOX_BOXLESS if boxless_winner else CLASS_CHECKBOX_BOX)
    notes["ambiguous_radios"] = ambiguous

    # fill-in-one groups: two checked members means a misread
    for grp in FILL_ONE_GROUPS:
        checked = [t for t in grp if lane_of.get(t) == "checkbox"]
        if len(checked) > 1:
            for t in checked:
                for qn, r in list(values.items()):
                    if r.get("pdf_tag") == t:
                        del values[qn]
                lane_of.pop(t, None)
                hold(t, "checkbox", "fill_in_one_conflict", page_of.get(t))

    # ---- Lane 2 (optional): numeric OCR on the pages Lane 1 could not read, added BEFORE the identities so
    #      that Decision 3 runs over the union of lanes and the derived totals are made from that union
    if lane2 is not None:
        done0 = {r["pdf_tag"] for r in values.values() if "pdf_tag" in r}
        text_pages0 = {page_of[t] for t in done0 if lane_of.get(t) == "text" and t in page_of}
        tx_pages0 = {q for p, q in by_tpage.items() if any(
            f["ft"] == "/Tx" and f["question_number"] and any(w["template_page"] == p for w in f["widgets"])
            for f in fmap["fields"].values())}
        pages0 = unreadable | invisible_pages | {q for q in tx_pages0 if q not in text_pages0 and q not in set(res.rejected_pages)}
        lane2(SimpleNamespace(doc=doc, res=res, year=year, fmap=fmap, tag_field=tag_field, by_tpage=by_tpage, ctx_for=ctx_for,
                              ocr_pages=pages0, done=done0, record=record, hold=hold, notes=notes))

    # ---- identities reject in every lane (Decision 3)
    ident, id_rejected = reject_identity_failures(values, set(fmap["fields"]))
    rejected.extend(id_rejected)
    ocr_keys = {k for k, r in values.items() if r.get("lane") == 2}
    keys_before = set(values)
    derived = apply_b1(values, schema_fields=schema.get("fields") or [])
    if ocr_keys:                                      # which derived totals depend on a Lane 2 input: derive again without them
        plain = {k: r for k, r in values.items() if k not in ocr_keys and not (r.get("derived_from") and k not in keys_before)}
        apply_b1(plain, schema_fields=schema.get("fields") or [])
        ocr_dep = {k for k, r in values.items() if r.get("derived_from") and k not in keys_before and (k not in plain or plain[k].get("value") != r.get("value"))}
    else:
        ocr_dep = set()
    for k, r in values.items():
        if r.get("derived_from") and k not in keys_before:
            r["derived_lanes"] = [2, "text"] if k in ocr_dep else ["text"]
            r["emission_class"] = CLASS_OCR_NUMERIC if k in ocr_dep else CLASS_NUMERIC       # a total derived from counts; OCR-dependent ones are OCR

    # ---- Lane 2 seam: always the unreadable and invisible pages, pages with no usable text
    #      left after rejection, and the unresolved numeric widgets on unreadable/invisible pages
    done = {r["pdf_tag"] for r in values.values() if "pdf_tag" in r}
    text_pages = {page_of[t] for t in done if lane_of.get(t) == "text" and t in page_of}
    tx_pages = {q for p, q in by_tpage.items() if any(
        f["ft"] == "/Tx" and f["question_number"] and any(w["template_page"] == p for w in f["widgets"])
        for f in fmap["fields"].values())}
    geometry_blocked = set(res.rejected_pages)       # their rects are unsound for OCR as well
    ocr_pages = sorted(unreadable | invisible_pages | {q for q in tx_pages if q not in text_pages and q not in geometry_blocked})
    seen = {(w["pdf_tag"], w["page"]) for w in ocr_widgets}
    for tag, f in fmap["fields"].items():
        if f["ft"] != "/Tx" or f["question_number"] is None or tag in done:
            continue
        if effective_type(tag, f["value_type"], f["ft"]) not in ("Number", "Dollars", "Percent", "Identifier"):
            continue
        for wi, w in enumerate(f["widgets"]):
            q = by_tpage.get(w["template_page"])
            if q is not None and (q in unreadable or q in invisible_pages) and (tag, q) not in seen:
                ocr_widgets.append(_ocr_entry(tag, q, wi, w["rect"], ctx_for(q, w["template_page"]),
                                              "unreadable_page" if q in unreadable else "invisible_text"))
    lane_counts = Counter(str(r["lane"]) for r in values.values() if "lane" in r)
    notes.update({
        "lane_counts": dict(lane_counts), "emission_class_counts": dict(Counter(r.get("emission_class") for r in values.values())),
        "rejected_fields": rejected, "identity_failures": ident,
        "withheld": withheld, "withheld_by_reason": dict(Counter(w["reason"] for w in withheld)),
        "unreadable_pages": sorted(unreadable), "invisible_text_pages": sorted(invisible_pages),
        "pages_needing_ocr": ocr_pages, "ocr_widgets": ocr_widgets,
        "skipped_null_question_number": skipped_unjoined, "b1_all_totals_derived": derived,
    })
    out["values"] = values
    out["stats"] = {"schema_fields_populated": len(values), "b1_all_totals_derived": derived,
                    "lane_counts": dict(lane_counts)}
    return out


def _forced_match(doc, maps, force_year: str) -> MatchResult:
    """Diagnostic: match against a single year's map, skipping the header-year rule."""
    n = len(doc)
    res = MatchResult(status=STATUS_NOT_TEMPLATE, page_count=n)
    shape = maps[force_year].pages[0].mask.shape
    geoms = [page_geometry(doc[q]) for q in range(n)]
    score = np.zeros((n, len(maps[force_year].pages)))
    for q in range(n):
        gm = _page_mask36(doc[q], geoms[q], shape)
        if gm is not None:
            score[q] = _score_page(gm, maps[force_year])
    assign = _monotonic_assign(score)
    res.pages_matched = {force_year: len(assign)}
    if len(assign) < GATE_PAGES:
        res.reason = "fewer_than_30_template_pages"
        return res
    res.status, res.year, res.page_map = STATUS_MATCHED, force_year, dict(assign)
    tdoc = _template_doc(force_year)
    for q, p in list(res.page_map.items()):
        est = estimate_page_alignment(_page_masks(doc[q], geoms[q], tdoc[p]))
        res.alignment[q] = {"dx": est["dx"], "dy": est["dy"], "recall": est["recall"]}
        if est["recall"] < ALIGN_MIN_RECALL or not est["consistent"]:
            res.rejected_pages[q] = "alignment"
            del res.page_map[q]
        elif est["flagged_bands"]:
            res.band_rejections[q] = list(est["flagged_bands"])
    return res


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("pdf", type=Path)
    ap.add_argument("--detected-year", help="may only veto the printed header year")
    ap.add_argument("--match-only", action="store_true", help="print the Stage 1 result and stop")
    ap.add_argument("--output", type=Path, help="write JSON here instead of stdout")
    args = ap.parse_args(argv)
    if args.match_only:
        out = match_template(args.pdf.read_bytes(), detected_year=args.detected_year).to_dict()
    else:
        out = extract_overlay(args.pdf.read_bytes(), detected_year=args.detected_year, source_name=args.pdf.name)
    text = json.dumps(out, indent=1, sort_keys=True)
    if args.output:
        args.output.write_text(text + "\n")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
