#!/usr/bin/env python3
"""Template overlay extraction for flattened official CDS PDFs (PRD 038, M1).

A pure library: bytes in, JSON-able dict out. No database, network or worker
access. Milestone scope is Stage 1 (template match), Lane 1 (text layer) and
Lane 3 (checkboxes and radios) plus validation. Lane 2 (crop OCR) is M2 and the
worker/DB wiring is M3; pages that need OCR are reported in
`notes.pages_needing_ocr` so M2 has a seam.

Public API:
    load_maps()                      committed field maps with decoded masks
    match_template(pdf, ...)         Stage 1: which official template, which year
    extract_overlay(pdf, ...)        Stage 1 + Lanes 1 and 3 + validation
CLI: python tools/tier2_extractor/template_overlay.py file.pdf [--detected-year Y]
"""

from __future__ import annotations

import argparse
import functools
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
import pypdfium2 as pdfium

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_field_map as bfm  # noqa: E402

PRODUCER = "tier2_template_overlay"
PRODUCER_VERSION = "0.1.0"
FIELD_MAP_VERSION = bfm.MAP_FORMAT_VERSION

# ---- Stage 1 parameters (PRD §2) -------------------------------------------
MIN_PAGES, MAX_PAGES = 30, 70            # pre-filter page-count window
PAGE_MATCH_MIN = 0.85                    # share of template static ink found
GATE_PAGES = 30                          # template pages that must match
YEAR_LEAD_MIN = 3                        # below this lead, detected_year must agree
DILATE_ITERS = 2                         # 4-neighbour dilations (review's "within 3 px")
PRECISION_SLACK = 0.25                   # s = min(recall, precision + slack)
MIN_TEMPLATE_INK_PX = 50                 # template pages with less ink are skipped
ALIGN_DPI = 72                           # 1 px = 1 pt, so a 1 pt residual is testable
ALIGN_SEARCH_PT = 3
ALIGN_MAX_PT = 1.0                       # a shift beyond this rejects the page
ALIGN_MIN_RECALL = 0.5                   # sanity floor; PDFium-flattened widgets overdraw some ink
ALIGN_MIN_GAIN = 0.02                    # a nonzero shift must beat (0, 0) by this much recall

STATUS_MATCHED = "matched"
STATUS_NOT_TEMPLATE = "not_official_pdf_template"
STATUS_AMBIGUOUS = "template_year_ambiguous"


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
# Stage 1
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
    page_map: dict[int, int] = field(default_factory=dict)        # target page -> template page
    offsets: dict[int, int] = field(default_factory=dict)         # target - template -> count
    alignment: dict[int, dict] = field(default_factory=dict)      # target page -> sx, sy, dx, dy
    rejected_pages: dict[int, str] = field(default_factory=dict)
    page_scores: dict[int, float] = field(default_factory=dict)

    def to_dict(self) -> dict:
        d = {k: v for k, v in self.__dict__.items()}
        d["page_map"] = {str(k): v for k, v in self.page_map.items()}
        d["alignment"] = {str(k): v for k, v in self.alignment.items()}
        d["rejected_pages"] = {str(k): v for k, v in self.rejected_pages.items()}
        d["page_scores"] = {str(k): round(v, 4) for k, v in self.page_scores.items()}
        d["offsets"] = {str(k): v for k, v in self.offsets.items()}
        return d


def _page_mask36(page: "pdfium.PdfPage", shape: tuple[int, int]) -> np.ndarray | None:
    """Render a target page into the template mask grid (uniform scale).

    Returns None when the page aspect ratio is not the template's.
    """
    w, h = page.get_size()
    tw, th = 612.0, 792.0
    f = tw / w
    if abs(f - th / h) > 0.01 * f:
        return None
    mask = bfm._ink_mask(page, dpi=bfm.MASK_DPI * f)
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

    score[q][p] >= PAGE_MATCH_MIN marks a valid pair. Ties on count prefer the
    higher total score. Handles dropped and inserted pages mid-packet.
    """
    nq, npg = score.shape
    valid = score >= PAGE_MATCH_MIN
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


def _align_page(page: "pdfium.PdfPage", tpl_page: "pdfium.PdfPage") -> dict:
    """Estimate the (dx, dy) shift between a matched target page and its template.

    Definition: both pages are rendered at 72 DPI (1 px = 1 pt) and the integer
    shift (in pt, within +-ALIGN_SEARCH_PT) of the template ink that maximises
    the share of template ink landing on target ink dilated by 1 px is taken,
    ties going to the smaller shift. The transform is then
    x' = x*sx + dx, y' = y*sy + dy with sx, sy the mediabox ratios, in PDF
    points with a bottom-left origin (dy is therefore the negated image-row
    shift). A nonzero shift is only taken when it raises recall by ALIGN_MIN_GAIN
    over (0, 0). The page is rejected when |dx| or |dy| exceeds ALIGN_MAX_PT or
    the best recall is below ALIGN_MIN_RECALL.
    """
    w, h = page.get_size()
    sx, sy = w / 612.0, h / 792.0
    f = 612.0 / w
    g = bfm._ink_mask(page, dpi=ALIGN_DPI * f)
    t = bfm._ink_mask(tpl_page, dpi=ALIGN_DPI)
    hh, ww = min(g.shape[0], t.shape[0]), min(g.shape[1], t.shape[1])
    g, t = g[:hh, :ww], t[:hh, :ww]
    gd = _dilate(g, 1)
    ty, tx = np.nonzero(t)
    if ty.size > 20000:
        keep = np.arange(0, ty.size, ty.size // 20000 + 1)
        ty, tx = ty[keep], tx[keep]
    best = (-1.0, 0, 0)
    rec0 = None
    for dyp in range(-ALIGN_SEARCH_PT, ALIGN_SEARCH_PT + 1):
        for dxp in range(-ALIGN_SEARCH_PT, ALIGN_SEARCH_PT + 1):
            yy, xx = ty + dyp, tx + dxp
            ok = (yy >= 0) & (yy < hh) & (xx >= 0) & (xx < ww)
            rec = float(gd[yy[ok], xx[ok]].sum()) / ty.size
            if dxp == 0 and dyp == 0:
                rec0 = rec
            tie_better = rec == best[0] and abs(dxp) + abs(dyp) < abs(best[1]) + abs(best[2])
            if rec > best[0] + 1e-9 or tie_better:
                best = (rec, dxp, dyp)
    recall, dxp, dyp = best
    if rec0 is not None and recall - rec0 < ALIGN_MIN_GAIN:
        recall, dxp, dyp = rec0, 0, 0   # sub-noise gains are antialiasing, not a shift
    return {"sx": round(sx, 5), "sy": round(sy, 5), "dx": float(dxp), "dy": float(-dyp),
            "recall": round(recall, 4)}


def match_template(
    pdf: bytes | str | Path | "pdfium.PdfDocument",
    maps: dict[str, YearMaps] | None = None,
    detected_year: str | None = None,
    *,
    align: bool = True,
) -> MatchResult:
    """Stage 1: decide whether `pdf` is a print of an official CDS template.

    Matches each target page against every template page of every year's mask
    (36 DPI, ink gray < 225). A page matches a template page when at least 85%
    of the template's static ink is present within the dilation tolerance. The
    matcher keeps the review's precision clamp (min(recall, precision + 0.25))
    so pages with a lot of extra ink (other layouts) do not match. Pages are
    then assigned monotonically to template pages per year; the year with the
    most assigned pages wins (needs >= 30). Under a lead of 3 pages the year
    must equal `detected_year`, otherwise the result is template_year_ambiguous;
    a tie is always ambiguous.
    """
    maps = maps or load_maps()
    doc = pdf if isinstance(pdf, pdfium.PdfDocument) else pdfium.PdfDocument(pdf)
    n = len(doc)
    res = MatchResult(status=STATUS_NOT_TEMPLATE, page_count=n)
    if not (MIN_PAGES <= n <= MAX_PAGES):
        res.reason = "page_count_out_of_range"
        return res

    years = list(maps)
    shape = next(iter(maps.values())).pages[0].mask.shape
    score = {y: np.zeros((n, len(maps[y].pages))) for y in years}
    for q in range(n):
        g = _page_mask36(doc[q], shape)
        if g is None:
            continue
        for y in years:
            score[y][q] = _score_page(g, maps[y])
    assign = {y: _monotonic_assign(score[y]) for y in years}
    counts = {y: len(assign[y]) for y in years}
    res.pages_matched = counts

    ranked = sorted(years, key=lambda y: (-counts[y], y))
    best, second = ranked[0], ranked[1] if len(ranked) > 1 else None
    res.lead = counts[best] - (counts[second] if second else 0)
    res.runner_up_year = second
    if counts[best] < GATE_PAGES:
        res.reason = "fewer_than_30_template_pages"
        return res

    if res.lead == 0:
        res.status, res.reason = STATUS_AMBIGUOUS, "tie_between_years"
        res.year = None
        return res
    if res.lead < YEAR_LEAD_MIN and detected_year != best:
        res.status = STATUS_AMBIGUOUS
        res.reason = "lead_under_3_and_detected_year_missing" if not detected_year else "lead_under_3_and_detected_year_disagrees"
        return res

    res.status, res.year = STATUS_MATCHED, best
    res.page_map = assign[best]
    for q, p in res.page_map.items():
        res.page_scores[q] = float(score[best][q][p])
        off = q - p
        res.offsets[off] = res.offsets.get(off, 0) + 1
    if align:
        tdoc = _template_doc(best)
        for q, p in list(res.page_map.items()):
            a = _align_page(doc[q], tdoc[p])
            res.alignment[q] = a
            if abs(a["dx"]) > ALIGN_MAX_PT or abs(a["dy"]) > ALIGN_MAX_PT or a["recall"] < ALIGN_MIN_RECALL:
                res.rejected_pages[q] = "alignment_residual_over_1pt"
                del res.page_map[q]
                del res.page_scores[q]
    return res


# --------------------------------------------------------------------------
# geometry
# --------------------------------------------------------------------------

_IDENTITY = {"sx": 1.0, "sy": 1.0, "dx": 0.0, "dy": 0.0}


def _xform_rect(rect: list[float], a: dict) -> list[float]:
    x0, y0, x1, y1 = rect
    return [x0 * a["sx"] + a["dx"], y0 * a["sy"] + a["dy"], x1 * a["sx"] + a["dx"], y1 * a["sy"] + a["dy"]]


def _alignment_for(res: MatchResult, q: int, page: "pdfium.PdfPage") -> dict:
    a = res.alignment.get(q)
    if a:
        return a
    w, h = page.get_size()
    return {"sx": w / 612.0, "sy": h / 792.0, "dx": 0.0, "dy": 0.0}


# --------------------------------------------------------------------------
# Lane 3: checkboxes and radios (ink density, baseline-subtracted)
# --------------------------------------------------------------------------

LANE3_DPI = 216
LANE3_INSET = 0.35          # fraction of each side trimmed before measuring
LANE3_THRESHOLD = 0.05      # baseline-subtracted ink density that counts as checked
LANE3_MARGIN = 0.03         # radio group: winner must beat the runner-up by this


def _gray(page: "pdfium.PdfPage", dpi: float, annots: bool = False) -> np.ndarray:
    bitmap = page.render(scale=dpi / 72.0, draw_annots=annots, may_draw_forms=annots, rev_byteorder=True)
    rgb = bitmap.to_numpy()[..., :3].astype(np.uint32)
    return ((rgb[..., 0] * 19595 + rgb[..., 1] * 38470 + rgb[..., 2] * 7471 + 0x8000) >> 16).astype(np.float32)


def _crop_density(gray: np.ndarray, rect: list[float], page_h_pt: float, dpi: float, inset: float) -> float | None:
    """Mean ink density (0 = white, 1 = black) of a rect's interior; None if off-page."""
    x0, y0, x1, y1 = rect
    ix, iy = (x1 - x0) * inset, (y1 - y0) * inset
    k = dpi / 72.0
    r0, r1 = int((page_h_pt - y1 + iy) * k), int((page_h_pt - y0 - iy) * k)
    c0, c1 = int((x0 + ix) * k), int((x1 - ix) * k)
    if r1 <= r0 or c1 <= c0 or r0 < 0 or c0 < 0 or r1 > gray.shape[0] or c1 > gray.shape[1]:
        return None
    return float((255.0 - gray[r0:r1, c0:c1]).mean() / 255.0)


def button_scores(
    doc: "pdfium.PdfDocument",
    res: MatchResult,
    fmap: dict,
    *,
    year: str | None = None,
    dpi: int = LANE3_DPI,
    inset: float = LANE3_INSET,
    baseline_annots: bool = False,
    pages: set[int] | None = None,
) -> dict[str, list[float | None]]:
    """Baseline-subtracted ink score of every /Btn widget on matched pages.

    score = density(target crop) - density(blank template crop at the same rect).
    Returns {pdf_tag: [score per widget, in map order]}; None for widgets on
    unmatched or rejected pages.
    """
    year = year or res.year
    tdoc = _template_doc(year)
    by_template_page = {p: q for q, p in res.page_map.items()}
    out: dict[str, list[float | None]] = {}
    cache_t: dict[int, np.ndarray] = {}
    cache_g: dict[int, np.ndarray] = {}
    for tag, f in fmap["fields"].items():
        if f["ft"] != "/Btn":
            continue
        row: list[float | None] = []
        for w in f["widgets"]:
            p = w["template_page"]
            q = by_template_page.get(p)
            if q is None or (pages is not None and q not in pages):
                row.append(None)
                continue
            tpage = tdoc[p]
            page = doc[q]
            if p not in cache_t:
                cache_t[p] = _gray(tpage, dpi, baseline_annots)
            if q not in cache_g:
                cache_g[q] = _gray(page, dpi, False)
            a = _alignment_for(res, q, page)
            tgt = _crop_density(cache_g[q], _xform_rect(w["rect"], a), page.get_size()[1], dpi, inset)
            base = _crop_density(cache_t[p], w["rect"], tpage.get_size()[1], dpi, inset)
            row.append(None if tgt is None or base is None else tgt - base)
        out[tag] = row
    return out


def _is_btn_checked(scores: list[float | None], threshold: float, margin: float):
    """Pick the checked widget of a field from its baseline-subtracted scores.

    Returns (index | None, reason | None). A lone widget is checked when its
    score reaches the threshold. In a group the top widget wins when it reaches
    the threshold and beats the runner-up by `margin`; otherwise nothing is
    emitted and the reason is "ambiguous_radio".
    """
    live = [(s, i) for i, s in enumerate(scores) if s is not None]
    if not live:
        return None, None
    live.sort(key=lambda t: (-t[0], t[1]))
    top_s, top_i = live[0]
    if top_s < threshold:
        return None, None
    if len(live) > 1 and top_s - live[1][0] < margin:
        return None, "ambiguous_radio"
    return top_i, None


# --------------------------------------------------------------------------
# Lane 1: text layer (/Tx and /Ch)
# --------------------------------------------------------------------------

import re  # noqa: E402
import unicodedata  # noqa: E402

try:  # pdfium's raw API: is this character one pdfium generated (line breaks, hyphens)?
    import pypdfium2.raw as _pdfium_c
except Exception:  # pragma: no cover
    _pdfium_c = None

# "Numbers" is the schema's type for digit identifiers (ZIP, phone, area code,
# extension): kept as typed and checked for digits and phone punctuation only.
IDENTIFIER_NUMBER_TYPE = "Numbers"
_IDENT_RE = re.compile(r"^[0-9][0-9\-\s().+x]*$")
NUMERIC_TYPES = {
    "Number", "Nearest $1", "Nearest 1%", "Carnegie units",
    "Whole Number or Round to Nearest Tenth", "Whole Number or Round to Nearest Tenths",
    "Whole Number or Round to Nearest Hundredths", "Round to Nearest Hundredths",
}
_NUM_RE = re.compile(r"^-?(\d+(\.\d*)?|\.\d+)$")
STATIC_MATCH_PT = 1.0


@dataclass
class PageChar:
    ch: str
    cx: float
    cy: float


def _page_chars(page: "pdfium.PdfPage") -> list[PageChar]:
    """Text-layer characters with their box centres; pdfium-generated ones dropped."""
    tp = page.get_textpage()
    out = []
    for i in range(tp.count_chars()):
        if _pdfium_c is not None and _pdfium_c.FPDFText_IsGenerated(tp.raw, i):
            continue
        ch = tp.get_text_range(i, 1)
        if not ch:
            continue
        left, bottom, right, top = tp.get_charbox(i)
        out.append(PageChar(ch, (left + right) / 2.0, (bottom + top) / 2.0))
    return out


@functools.lru_cache(maxsize=None)
def _template_chars(year: str, page: int) -> tuple[PageChar, ...]:
    return tuple(_page_chars(_template_doc(year)[page]))


def _bad_char(ch: str) -> bool:
    """Control, private-use, surrogate, unassigned or replacement code points."""
    if ch in "\t\n\r":
        return False
    cat = unicodedata.category(ch[0])
    return cat in ("Cc", "Co", "Cs", "Cn") or ch == "�"


def read_widget_text(
    chars: list[PageChar],
    rect: list[float],
    static_chars: tuple[PageChar, ...] = (),
    static_rect: list[float] | None = None,
    *,
    pad: float = 0.0,
) -> tuple[str, bool]:
    """Read the characters whose box centre lies inside `rect` (no padding by default).

    Characters that coincide (within STATIC_MATCH_PT) with a blank-template
    character inside the widget's template rect are the form's own label text
    and are dropped. Returns (text, bad) where bad is True when a control,
    private-use or replacement character remains: such a read is never cleaned.
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
                          and (c.ch == s.ch or _bad_char(c.ch) or _bad_char(s.ch)) for s in stat)
                if not hit:
                    kept.append(c)
            inside = kept
    raw = "".join(c.ch for c in inside)
    bad = any(_bad_char(c.ch) for c in inside)
    return re.sub(r"\s+", " ", raw).strip(), bad


def normalise_text_value(raw: str, value_type: str | None) -> tuple[str | None, str | None]:
    """Normalise a text read by schema value_type. Returns (value, reject_reason)."""
    if value_type == IDENTIFIER_NUMBER_TYPE:
        return (raw, None) if _IDENT_RE.match(raw) else (None, "not_digits")
    if value_type in NUMERIC_TYPES:
        v = raw.replace("$", "").replace(",", "").replace("%", "").replace(" ", "")
        if not _NUM_RE.match(v):
            return None, "not_numeric"
        if value_type == "Nearest 1%" and not (0 <= float(v) <= 100):
            return None, "percent_out_of_range"
        return v, None
    if value_type == "MM":
        return (raw, None) if raw.isdigit() and 1 <= int(raw) <= 12 else (None, "bad_month")
    if value_type == "DD":
        return (raw, None) if raw.isdigit() and 1 <= int(raw) <= 31 else (None, "bad_day")
    return raw, None


def choice_to_export(raw: str, opt: list[list[str]] | None) -> str | None:
    """Map a /Ch display string to its export value through /Opt."""
    if not opt:
        return None
    key = re.sub(r"\s+", " ", raw).strip().lower()
    for export, display in opt:
        if re.sub(r"\s+", " ", display).strip().lower() == key:
            return export
    for export, _display in opt:
        if re.sub(r"\s+", " ", export).strip().lower() == key:
            return export
    return None


# --------------------------------------------------------------------------
# validation (PRD §4 steps 1 and 2)
# --------------------------------------------------------------------------

_C9_RE = re.compile(r"^(SAT1_COMP|SAT1_VERB|SAT1_MATH|ACT_[A-Z]+)_(25|50|75)TH_P$")
_C9_RANGE = {"SAT1_COMP": (400, 1600), "SAT1_VERB": (200, 800), "SAT1_MATH": (200, 800)}
_GENDERS = ("MEN", "WMN", "UNK", "NON_BINARY")


def _num(v: Any) -> float | None:
    try:
        return float(str(v).replace(",", "").replace("$", "").replace("%", "").strip())
    except (TypeError, ValueError):
        return None


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
    if all(c1 + [True]) and all(t in tag_values for t in c1):
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

def extract_overlay(
    pdf: bytes | str | Path,
    *,
    detected_year: str | None = None,
    source_name: str = "",
    maps: dict[str, YearMaps] | None = None,
    force_year: str | None = None,
    lane3_threshold: float = LANE3_THRESHOLD,
    lane3_margin: float = LANE3_MARGIN,
    lane1_pad: float = 0.0,
    strip_parens: bool = False,
    strict_types: bool = True,
) -> dict:
    """Stage 1 + Lane 1 + Lane 3 + validation for one PDF.

    Returns the Tier 2 `extract()` shape (producer, producer_version,
    schema_version, source_pdf, extracted_at, stats, values, unmapped_fields)
    plus `notes`. When Stage 1 does not match, `values` is empty and
    notes.stage1.status says why. `force_year` skips year selection (used by
    the wrong-year control); `lane1_pad` and `strip_parens` reproduce the
    review's ±1 pt padding read for comparison; `strict_types=False` keeps a
    read that fails its value_type (recorded as a warning) to quantify the check.
    """
    import hashlib
    from datetime import datetime, timezone

    data = pdf if isinstance(pdf, (bytes, bytearray)) else Path(pdf).read_bytes()
    maps = maps or load_maps()
    doc = pdfium.PdfDocument(bytes(data))
    if force_year:  # match against that year's map only (wrong-year control)
        res = match_template(doc, {force_year: maps[force_year]}, detected_year=force_year)
    else:
        res = match_template(doc, maps, detected_year=detected_year)

    out: dict[str, Any] = {
        "producer": PRODUCER, "producer_version": PRODUCER_VERSION,
        "schema_version": res.year, "source_pdf": source_name,
        "extracted_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "values": {}, "unmapped_fields": [],
    }
    notes: dict[str, Any] = {
        "producer_version": PRODUCER_VERSION, "field_map_version": FIELD_MAP_VERSION,
        "source_sha256": hashlib.sha256(data).hexdigest(), "stage1": res.to_dict(),
        "template_year": res.year,
    }
    out["notes"] = notes
    if res.status != STATUS_MATCHED:
        out["stats"] = {"schema_fields_populated": 0}
        return out

    year = res.year
    fmap = maps[year].fmap
    schema = _schema(year)
    tag_field = {f["pdf_tag"]: f for f in schema["fields"] if f.get("pdf_tag")}
    decode_button_value, apply_b1 = _import_tier2()
    tdoc = _template_doc(year)
    by_tpage = {p: q for q, p in res.page_map.items()}
    notes["matched_template_pages"] = len(res.page_map)
    notes["page_map"] = {str(q): p for q, p in res.page_map.items()}

    page_chars: dict[int, list[PageChar]] = {}
    unreadable: set[int] = set()
    reads: dict[str, tuple[str, int]] = {}          # tag -> (raw read, target page)
    rejected: list[dict] = []
    skipped_unjoined = 0
    fields_unmatched_page = 0
    pages_with_text: set[int] = set()
    lane_of: dict[str, str] = {}

    # ---- Lane 1
    for tag, f in fmap["fields"].items():
        if f["ft"] not in ("/Tx", "/Ch"):
            continue
        if f["question_number"] is None:
            skipped_unjoined += 1
            continue
        for w in f["widgets"]:
            p = w["template_page"]
            q = by_tpage.get(p)
            if q is None:
                fields_unmatched_page += 1
                continue
            if q in unreadable:
                continue
            page = doc[q]
            if q not in page_chars:
                page_chars[q] = _page_chars(page)
            a = _alignment_for(res, q, page)
            text, bad = read_widget_text(
                page_chars[q], _xform_rect(w["rect"], a), _template_chars(year, p), w["rect"], pad=lane1_pad)
            if strip_parens:
                text = text.strip("() ").strip()
            if bad:
                unreadable.add(q)
                continue
            if text:
                pages_with_text.add(q)
                reads.setdefault(tag, (text, q))
    # drop everything read from a page found unreadable after some of its widgets were read
    reads = {t: v for t, v in reads.items() if v[1] not in unreadable}

    values: dict[str, dict] = {}

    def record(tag: str, value: str, lane: str) -> None:
        sf = tag_field[tag]
        rec = {"value": value, "pdf_tag": tag, "word_tag": sf.get("word_tag"), "question": sf.get("question"),
               "section": sf.get("section"), "subsection": sf.get("subsection"),
               "value_type": sf.get("value_type"), "lane": lane}
        dec = decode_button_value(value, sf.get("value_options"))
        if dec is not None:
            rec["value_decoded"] = dec
        values[sf["question_number"]] = rec
        lane_of[tag] = lane

    for tag, (raw, q) in reads.items():
        f = fmap["fields"][tag]
        if tag not in tag_field:
            continue
        if f["ft"] == "/Ch":
            exp = choice_to_export(raw, f.get("opt"))
            if exp is None:
                rejected.append({"pdf_tag": tag, "reason": "choice_not_in_opt", "read": raw, "page": q})
                continue
            raw = exp
        val, why = normalise_text_value(raw, f["value_type"])
        if why:
            rejected.append({"pdf_tag": tag, "reason": why, "read": raw, "page": q,
                             **({} if strict_types else {"kept": True})})
            if strict_types:
                continue
            val = raw
        record(tag, val, "text")

    # ---- Lane 3
    scores = button_scores(doc, res, fmap)
    ambiguous = []
    for tag, row in scores.items():
        f = fmap["fields"][tag]
        if f["question_number"] is None:
            skipped_unjoined += 1
            continue
        if tag not in tag_field:
            continue
        idx, why = _is_btn_checked(row, lane3_threshold, lane3_margin)
        if why:
            ambiguous.append({"pdf_tag": tag, "scores": [None if s is None else round(s, 3) for s in row]})
        if idx is not None:
            record(tag, f["widgets"][idx]["on_state"], "checkbox")
    notes["ambiguous_radios"] = ambiguous

    # ---- validation (type happened above; identities here)
    tag_values = {r["pdf_tag"]: r["value"] for r in values.values()}
    ident = check_identities(tag_values, set(fmap["fields"]))
    to_reject: set[str] = set()
    for fail in ident:
        fail["action"] = "recorded"
        if any(lane_of.get(t) == "ocr" for t in fail["tags"]):   # M2: OCR'd values are rejected wholesale
            fail["action"] = "rejected"
            to_reject.update(t for t in fail["tags"] if t in lane_of)
    for t in sorted(to_reject):
        for qn, r in list(values.items()):
            if r["pdf_tag"] == t:
                rejected.append({"pdf_tag": t, "reason": "identity_failed", "read": r["value"]})
                del values[qn]

    derived = apply_b1(values, schema_fields=schema.get("fields") or [])

    # pages where Lane 1 found nothing although they hold number widgets: Lane 2 candidates
    ocr_pages = sorted(q for p, q in by_tpage.items()
                       if q not in pages_with_text and any(
                           f["ft"] == "/Tx" and f["question_number"] and any(w["template_page"] == p for w in f["widgets"])
                           for f in fmap["fields"].values()))
    lane_counts = Counter(r["lane"] for r in values.values() if "lane" in r)
    notes.update({
        "lane_counts": dict(lane_counts), "rejected_fields": rejected, "identity_failures": ident,
        "unreadable_pages": sorted(unreadable), "pages_needing_ocr": ocr_pages,
        "skipped_null_question_number": skipped_unjoined // 1,
        "widgets_on_unmatched_pages": fields_unmatched_page, "b1_all_totals_derived": derived,
    })
    out["values"] = values
    out["stats"] = {"schema_fields_populated": len(values), "b1_all_totals_derived": derived,
                    "lane_counts": dict(lane_counts)}
    return out


from collections import Counter  # noqa: E402


# --------------------------------------------------------------------------
# CLI (Stage 1 only for now; extended below as lanes land)
# --------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("pdf", type=Path)
    ap.add_argument("--detected-year")
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
