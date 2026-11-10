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
CLI: python tools/tier2_extractor/template_overlay.py file.pdf [--detected-year Y]

The year of a document is decided by the printed page header ("Common Data Set
YYYY-YYYY") and must agree with the best raster year; `detected_year` and
`cds_year` never choose a map. Forced-year runs exist only as the private
`_diagnostic_extract_forced_year` used by the evaluation script.
"""

from __future__ import annotations

import argparse
import functools
import hashlib
import json
import re
import sys
import unicodedata
from collections import Counter
from dataclasses import dataclass, field
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
PRODUCER_VERSION = "0.2.0"
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
DUPLICATE_DIFF = 0.10                    # share of a widget rect's ink that differs between duplicate pages
DUPLICATE_MIN_PX = 6
HEADER_DPI = 144
HEADER_VOTE_MARGIN = 0.01                # diff margin that counts as a header-year vote
HEADER_MIN_VOTES = 5
HEADER_MAJORITY = 0.9                    # share of voting pages that must agree; the rest are rejected
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
LOCAL_WINDOW_PT = 14
LOCAL_RANGE_PT = 10
LOCAL_GAIN = 0.15
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


def _page_chars_display(page: "pdfium.PdfPage", g: PageGeom) -> list[PageChar]:
    """Text-layer characters in DISPLAY points, with generated and invisible flags.

    Characters pdfium generated (hyphen markers, line breaks) keep their flag so
    callers can ignore them; generated whitespace is kept because Distiller
    prints word gaps as gaps and pdfium's generated space is the only separator.
    """
    tp = page.get_textpage()
    out = []
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
        (xa, ya), (xb, yb) = user_to_display(g, left, bottom), user_to_display(g, right, top)
        out.append(PageChar(ch, (xa + xb) / 2.0, (ya + yb) / 2.0, max(xa, xb), generated, invisible))
    return out


def _chars_to_template(chars: list[PageChar], g: PageGeom, dx: float = 0.0, dy: float = 0.0) -> list[PageChar]:
    out = []
    for c in chars:
        tx, ty = display_to_template(g, c.cx, c.cy, dx, dy)
        out.append(PageChar(c.ch, tx, ty, c.right / g.sx - dx, c.generated, c.invisible))
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


def _answer_regions_differ(doc, geoms, qs, ymaps: YearMaps, p: int, shape=None) -> bool:
    """Do the candidate target pages for template page p differ inside any of p's widget rects?

    Compared per widget at 72 DPI (one answer is a few glyphs; a page-wide ratio would
    drown it in table ink): a rect differs when at least DUPLICATE_MIN_PX pixels differ
    and they are a DUPLICATE_DIFF share of the rect's ink.
    """
    rects = [w["rect"] for f in ymaps.fmap["fields"].values() for w in f["widgets"] if w["template_page"] == p]
    if not rects:
        return False
    grays = []
    for q in qs:
        if not geoms[q].supported:
            return True
        grays.append(_render_template_scale(doc[q], geoms[q], ALIGN_DPI) < bfm.INK_THRESHOLD)
    for x0, y0, x1, y1 in rects:
        r0, r1, c0, c1 = template_rect_to_pixels([x0, y0, x1, y1], 0.0, 0.0, ALIGN_DPI)
        crops = [g[max(r0, 0):r1, max(c0, 0):c1] for g in grays]
        base = crops[0]
        for other in crops[1:]:
            if other.shape != base.shape:
                return True
            xor, union = int((base ^ other).sum()), int((base | other).sum())
            if xor >= DUPLICATE_MIN_PX and union and xor / union > DUPLICATE_DIFF:
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


def header_year_vote(page: "pdfium.PdfPage", g: PageGeom, p: int) -> str | None:
    """Which year's printed header does this page carry? None when it cannot tell.

    Pixel comparison of the year digits against each year's blank page at 144 DPI,
    so it works on vector-drawn prints without OCR. 2023-24 is one of the choices
    so a 2023-24 document is recognised.
    """
    if p not in _header_boxes() or not g.supported:
        return None
    crop = _header_crop(_render_gray(page, HEADER_DPI / g.sx), _header_boxes()[p], HEADER_DPI)
    tcrops = _header_template_crops(p)
    if crop.shape != tcrops[bfm.YEARS[0]].shape:
        return None
    diffs = sorted((_best_shift_diff(crop, t), y) for y, t in tcrops.items())
    (d0, y0), (d1, _y1) = diffs[0], diffs[1]
    return y0 if d1 - d0 > HEADER_VOTE_MARGIN else None


def decide_year(counts: dict[str, int], header_votes: dict[str, int], detected_year: str | None) -> tuple[str, str | None, str | None, int, str | None]:
    """Year decision. Returns (status, year, reason, raster_lead, runner_up_year).

    The page header (printed year) is the discriminator: the document year is the
    header majority and must agree with the best raster year. `detected_year` can
    only veto. Mixed packets, contradictions, ties and unverifiable headers hold
    the document (nothing is emitted); 2023-24 is recognised and rejected.
    """
    ranked = sorted(counts, key=lambda y: (-counts[y], y))
    best = ranked[0]
    second = ranked[1] if len(ranked) > 1 else None
    lead = counts[best] - (counts[second] if second else 0)
    if counts[best] < GATE_PAGES:
        return STATUS_NOT_TEMPLATE, None, "fewer_than_30_template_pages", lead, second
    if lead == 0:
        return STATUS_AMBIGUOUS, None, "tie_between_years", lead, second
    total = sum(header_votes.values())
    if total < HEADER_MIN_VOTES:
        return STATUS_AMBIGUOUS, None, "header_year_unverified", lead, second
    hdr = max(header_votes, key=lambda y: (header_votes[y], y))
    if header_votes[hdr] / total < HEADER_MAJORITY:
        return STATUS_AMBIGUOUS, None, "mixed_year_packet", lead, second
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
    out = {"dx": float(bx), "dy": float(-by), "recall": round(best, 4), "bands": [], "flagged_bands": [], "consistent": True}
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
        out["consistent"] = False
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
    page_vote: dict[int, str | None] = {}
    if counts[best_raster] >= GATE_PAGES:
        for q, p in assign[best_raster].items():
            v = header_year_vote(doc[q], geoms[q], p)
            page_vote[q] = v
            if v:
                votes[v] += 1
    res.header_votes = {y: c for y, c in votes.items() if c}

    status, year, reason, lead, second = decide_year(counts, votes, detected_year)
    res.lead, res.runner_up_year = lead, second
    if status != STATUS_MATCHED:
        res.status, res.reason = status, reason
        return res

    res.status, res.year = STATUS_MATCHED, year
    page_map = dict(assign[year])
    sc = score[year]
    for q in list(page_map):               # pages whose own header votes the other year are not read
        v = page_vote.get(q)
        if v and v != year:
            res.rejected_pages[q] = "header_year_mismatch"
            del page_map[q]
    for p, qs in _duplicate_candidates(sc).items():   # one template page, several target pages
        if p in page_map.values() and _answer_regions_differ(doc, geoms, qs, maps[year], p):
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
                est = estimate_page_alignment(_page_masks(doc[q], geoms[q], tdoc[p]))
                res.alignment[q] = {"dx": est["dx"], "dy": est["dy"], "recall": est["recall"]}
                if est["recall"] < ALIGN_MIN_RECALL:
                    res.rejected_pages[q] = "alignment_recall_too_low"
                elif not est["consistent"]:
                    res.rejected_pages[q] = "partial_page_shift"
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
STATIC_MATCH_PT = 1.0
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


def normalise_text_value(raw: str, value_type: str | None, tag: str = "") -> tuple[str | None, str | None]:
    """Normalise a text read by effective type. Returns (value, reject_reason)."""
    et = effective_type(tag, value_type, "/Tx")
    if et == "Identifier":
        return (raw, None) if _IDENT_RE.match(raw) else (None, "not_digits")
    if et in ("Number", "Dollars", "Percent"):
        m = _NUM_RE.match(raw)
        if not m:
            return None, "not_numeric"
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

LANE3_INSET = 0.35          # fraction of each side trimmed before measuring
LANE3_THRESHOLD = 0.05      # baseline-subtracted ink density that counts as checked
LANE3_MARGIN = 0.03         # radio group: winner must beat the runner-up by this
LANE3_BAND_HI = 0.12        # a lone checkbox scoring in [THRESHOLD, BAND_HI) abstains
FRAME_MIN_RECALL = 0.85     # share of the blank box outline that must be present at the box that would be emitted
FRAME_MEMBER_MIN = 0.5      # ... and at least this share at every other box of its group
BORDER_MIN_PX = 8           # a measured interior with fewer dark pixels cannot show a line
BORDER_LINE_SHARE = 0.6     # two adjacent pixel rows/columns holding this share of the dark ink are a straight stroke
FRAME_SEARCH_PX = 6         # each box is registered on its own within this many 216-DPI pixels (about 2 pt)
FRAME_INNER = 0.20          # the outline ring is the rect minus its inner 60%
RADIO_BAND_RUNNER_UP = 0.01  # a radio winner in the gray band whose runner-up is this close to blank abstains
RADIO_BAND_RULE = True       # measured: the band rule is what removes the Lone Star and Eastern Michigan AP_FEE errors
# "fill in one only" groups: two checked members mean a misread, so abstain on all
FILL_ONE_GROUPS = (
    ("AP_NOTF_DL_FRSH_I", "AP_NOTF_DL_FRSH", "AP_NOTF_DL_OTH"),                   # C16
    ("AP_REPLY_DL", "AP_REPLY_DL_NO", "AP_REPLY_DL_MUST", "AP_REPLY_OTH"),         # C17
)


def _crop_density(gray: np.ndarray, rect: list[float], dx: float, dy: float, dpi: float, inset: float) -> float | None:
    """Mean ink density (0 white, 1 black) of a rect's interior in a template-scale render."""
    x0, y0, x1, y1 = rect
    ix, iy = (x1 - x0) * inset, (y1 - y0) * inset
    r0, r1, c0, c1 = template_rect_to_pixels([x0 + ix, y0 + iy, x1 - ix, y1 - iy], dx, dy, dpi)
    if r1 <= r0 or c1 <= c0 or r0 < 0 or c0 < 0 or r1 > gray.shape[0] or c1 > gray.shape[1]:
        return None
    return float((255.0 - gray[r0:r1, c0:c1].astype(np.float32)).mean() / 255.0)


def core_is_border_line(gray: np.ndarray, rect: list[float], dx: float, dy: float) -> bool:
    """Does the interior measured for a box hold one straight stroke (a box border), not a mark?

    A check or cross is diagonal ink spread over many rows and columns; the border of a
    box that is bigger or heavier than the template's glyph, or sits a little off, enters
    the measured interior as a single line along one edge. Such a box scores like a
    check mark while empty, so it is not read.
    """
    x0, y0, x1, y1 = rect
    ix, iy = (x1 - x0) * LANE3_INSET, (y1 - y0) * LANE3_INSET
    r0, r1, c0, c1 = template_rect_to_pixels([x0 + ix, y0 + iy, x1 - ix, y1 - iy], dx, dy, INK_DPI)
    if r0 < 0 or c0 < 0 or r1 > gray.shape[0] or c1 > gray.shape[1] or r1 <= r0 or c1 <= c0:
        return False
    dark = gray[r0:r1, c0:c1] < 128
    total = int(dark.sum())
    if total < BORDER_MIN_PX:
        return False
    def widest(v: np.ndarray) -> int:       # a stroke is a pixel or two wide
        return int(max(v[i:i + 2].sum() for i in range(max(len(v) - 1, 1))))

    return max(widest(dark.sum(axis=0)), widest(dark.sum(axis=1))) >= BORDER_LINE_SHARE * total


def locate_frame(c: "_PageCtx", rect: list[float]) -> tuple[float | None, float, float]:
    """Find a box's outline near the mapped rect: (recall, dx_pt, dy_pt).

    The blank template's outline (the rect's border ring) is matched against the
    target within +-FRAME_SEARCH_PX pixels (216 DPI, about +-2 pt) of the applied page
    transform. `recall` is the share of the outline found at the best offset (None: the
    template has no outline ink there) and the offsets are in template points (not
    applied to the interior measurement: PDFium-flattened prints draw their own bevelled
    box about 1 pt from the template's glyph, a systematic offset). A box whose outline is not there
    (typed text reflowed the line, a row shifted) has a low recall and is not read.
    """
    r0, r1, c0, c1 = template_rect_to_pixels(rect, c.dx, c.dy, INK_DPI)
    tr0, tr1, tc0, tc1 = template_rect_to_pixels(rect, 0.0, 0.0, INK_DPI)
    m = FRAME_SEARCH_PX + 1
    if min(r0 - m, c0 - m, tr0, tc0) < 0 or r1 + m > c.gray.shape[0] or c1 + m > c.gray.shape[1] \
            or tr1 > c.tgray.shape[0] or tc1 > c.tgray.shape[1]:
        return 0.0, 0.0, 0.0
    tpl = c.tgray[tr0:tr1, tc0:tc1] < 200
    h, w = tpl.shape
    ring = np.ones((h, w), dtype=bool)
    ih, iw = int(h * FRAME_INNER), int(w * FRAME_INNER)
    ring[ih:h - ih, iw:w - iw] = False
    ring &= tpl
    n = int(ring.sum())
    if n < 20:
        return None, 0.0, 0.0
    big = _dilate(c.gray[r0 - m:r1 + m, c0 - m:c1 + m] < 200, 1)
    best, hits = -1.0, []
    for sy in range(-FRAME_SEARCH_PX, FRAME_SEARCH_PX + 1):
        for sx in range(-FRAME_SEARCH_PX, FRAME_SEARCH_PX + 1):
            win = big[m + sy:m + sy + h, m + sx:m + sx + w]
            if win.shape != tpl.shape:
                continue
            rec = float((ring & win).sum()) / n
            if rec > best + 1e-9:
                best, hits = rec, [(sx, sy)]
            elif abs(rec - best) <= 1e-9:
                hits.append((sx, sy))
    sx = int(round(float(np.mean([a for a, _ in hits]))))
    sy = int(round(float(np.mean([b for _, b in hits]))))
    k = INK_DPI / 72.0
    return best, sx / k, -sy / k          # dy is up-positive


def _is_btn_checked(scores: list[float | None], threshold: float, margin: float):
    """Pick the checked widget of a field from its baseline-subtracted scores.

    Returns (index | None, reason | None). A lone widget is checked when its
    score reaches the threshold. In a group the top widget wins when it reaches
    the threshold and beats the runner-up by `margin`; otherwise nothing is
    emitted and the reason is "ambiguous_radio". A lone widget inside the gray
    band [threshold, LANE3_BAND_HI) abstains ("lone_checkbox_gray_band"), and so
    does (when enabled) a radio winner in the band whose runner-up is ~0.
    """
    live = [(s, i) for i, s in enumerate(scores) if s is not None]
    if not live:
        return None, None
    live.sort(key=lambda t: (-t[0], t[1]))
    top_s, top_i = live[0]
    if top_s < threshold:
        return None, None
    if len(live) == 1:
        if top_s < LANE3_BAND_HI:
            return None, "lone_checkbox_gray_band"
        return top_i, None
    if top_s - live[1][0] < margin:
        return None, "ambiguous_radio"
    if RADIO_BAND_RULE and top_s < LANE3_BAND_HI and live[1][0] <= RADIO_BAND_RUNNER_UP:
        return None, "radio_gray_band"
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

class _PageCtx:
    """Everything the lanes need about one matched page, built lazily."""

    def __init__(self, doc, q, p, year, res: MatchResult):
        self.page = doc[q]
        self.q, self.p, self.year = q, p, year
        self.geom = page_geometry(self.page)
        a = res.alignment.get(q) or {"dx": 0.0, "dy": 0.0}
        self.dx, self.dy = a["dx"], a["dy"]
        self.applied_px = (int(round(self.dx)), int(round(-self.dy)))   # (cols, rows) at 72 DPI
        self.bands = set(res.band_rejections.get(q, ()))
        self._chars = None
        self._masks = None
        self._gray = None
        self._tgray = None

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
) -> dict:
    """Stage 1 + Lane 1 + Lane 3 + validation for one PDF.

    Returns the Tier 2 `extract()` shape (producer, producer_version,
    schema_version, source_pdf, extracted_at, stats, values, unmapped_fields)
    plus `notes`. When Stage 1 does not match (or holds the document), `values` is
    empty and notes.stage1.status/reason say why. `detected_year` can only veto the
    printed header year; it never chooses the map.
    """
    return _extract(pdf, detected_year=detected_year, source_name=source_name, maps=maps, force_year=None,
                    lane3_threshold=lane3_threshold, lane3_margin=lane3_margin, lane1_pad=lane1_pad,
                    strict_types=strict_types)


def _diagnostic_extract_forced_year(pdf, force_year: str, **kw) -> dict:
    """DIAGNOSTIC ONLY (wrong-year control in the evaluation script). Not part of the API."""
    out = _extract(pdf, detected_year=None, force_year=force_year, **kw)
    out["notes"]["diagnostic_forced_year"] = force_year
    return out


def _extract(
    pdf, *, detected_year, source_name="", maps=None, force_year=None,
    lane3_threshold=None, lane3_margin=None, lane1_pad=0.0, strict_types=True,
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
    equiv: dict[tuple, frozenset] = {}

    def ctx_for(q: int, p: int) -> _PageCtx:
        if q not in ctxs:
            ctxs[q] = _PageCtx(doc, q, p, year, res)
        return ctxs[q]

    def hold(tag: str, lane: str, reason: str, q: int | None, widget: int = 0) -> None:
        withheld.append({"pdf_tag": tag, "lane": lane, "reason": reason, "page": q, "widget": widget})

    def gate(c: _PageCtx, tag: str, wi: int, rect: list[float]) -> str | None:
        """Band and per-widget local alignment checks; a reason means abstain."""
        if c.band_of(rect) in c.bands:
            return "band_misaligned"
        key = (tag, wi)
        if key not in equiv:
            equiv[key] = _equivalent_shifts(year, c.p, key, rect, c.masks.t)
        verdict, _gain = local_alignment_check(c.masks, rect, c.applied_px, equiv[key])
        return "local_misalignment" if verdict == "misaligned" else None

    def record(tag: str, value: str, lane: str, et: str, q: int) -> None:
        sf = tag_field[tag]
        rec = {"value": value, "pdf_tag": tag, "word_tag": sf.get("word_tag"), "question": sf.get("question"),
               "section": sf.get("section"), "subsection": sf.get("subsection"),
               "value_type": sf.get("value_type"), "effective_type": et, "lane": lane}
        dec = decode_button_value(value, sf.get("value_options"))
        if dec is not None:
            rec["value_decoded"] = dec
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
                ocr_widgets.append({"pdf_tag": tag, "page": q, "reason": "invisible_text"})
                hold(tag, "text", "invisible_text", q, wi)
                blocked = True
                continue
            if rd.text:
                why = gate(c, tag, wi, w["rect"])
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
        record(tag, val, "text", et, q)
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
        frames: list[tuple[float | None, float]] = []
        first_q = None
        missing_page = False
        gate_reason = None
        for wi, w in enumerate(f["widgets"]):
            p = w["template_page"]
            q = by_tpage.get(p)
            if q is None:
                row.append(None)
                frames.append((None, 0.0))
                missing_page = True
                continue
            first_q = first_q if first_q is not None else q
            c = ctx_for(q, p)
            fr, fdx, fdy = locate_frame(c, w["rect"])
            frames.append((fr, max(abs(fdx), abs(fdy))))
            tgt = _crop_density(c.gray, w["rect"], c.dx, c.dy, INK_DPI, LANE3_INSET)
            base = _crop_density(c.tgray, w["rect"], 0.0, 0.0, INK_DPI, LANE3_INSET)
            row.append(None if tgt is None or base is None else tgt - base)
        idx, why = _is_btn_checked(row, lane3_threshold, lane3_margin)
        if idx is None and not why:
            continue
        # something would be emitted (or is doubtful): only a group that is verifiably in place is read
        gate_reason = "page_not_matched" if missing_page else None
        if gate_reason is None and idx is not None:
            win = frames[idx]
            if (win[0] is not None and win[0] < FRAME_MIN_RECALL) or any(x[0] is not None and x[0] < FRAME_MEMBER_MIN for x in frames):
                gate_reason = "box_outline_missing"
        if gate_reason is None and idx is not None:
            wq = by_tpage[f["widgets"][idx]["template_page"]]
            if core_is_border_line(ctx_for(wq, f["widgets"][idx]["template_page"]).gray, f["widgets"][idx]["rect"],
                                   ctxs[wq].dx, ctxs[wq].dy):
                gate_reason = "box_border_in_interior"
        if gate_reason is None:
            for wi, w in enumerate(f["widgets"]):
                q = by_tpage.get(w["template_page"])
                gate_reason = gate(ctx_for(q, w["template_page"]), tag, wi, w["rect"])
                if gate_reason:
                    break
        if gate_reason:
            hold(tag, "checkbox", gate_reason, first_q)
            continue
        if why:
            ambiguous.append({"pdf_tag": tag, "reason": why, "scores": [None if s is None else round(s, 3) for s in row]})
            hold(tag, "checkbox", why, first_q)
            continue
        exp = f["widgets"][idx]["on_state"]
        if exp not in {w["on_state"] for w in f["widgets"]}:
            rejected.append({"pdf_tag": tag, "reason": "illegal_button_state", "read": exp})
            continue
        record(tag, exp, "checkbox", "Button", by_tpage[f["widgets"][idx]["template_page"]])
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

    # ---- identities reject in every lane (Decision 3)
    tag_values = {r["pdf_tag"]: r["value"] for r in values.values() if "pdf_tag" in r}
    ident = check_identities(tag_values, set(fmap["fields"]))
    for fail in ident:
        fail["action"] = "rejected"
        for t in fail["tags"]:
            for qn, r in list(values.items()):
                if r.get("pdf_tag") == t:
                    rejected.append({"pdf_tag": t, "reason": f"identity_failed:{fail['identity']}", "read": r["value"]})
                    del values[qn]
    derived = apply_b1(values, schema_fields=schema.get("fields") or [])

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
        for w in f["widgets"]:
            q = by_tpage.get(w["template_page"])
            if q is not None and (q in unreadable or q in invisible_pages) and (tag, q) not in seen:
                ocr_widgets.append({"pdf_tag": tag, "page": q, "reason": "unreadable_page" if q in unreadable else "invisible_text"})
    lane_counts = Counter(r["lane"] for r in values.values() if "lane" in r)
    notes.update({
        "lane_counts": dict(lane_counts), "rejected_fields": rejected, "identity_failures": ident,
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
