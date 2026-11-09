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
ALIGN_MIN_RECALL = 0.85

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
    shift). The page is rejected when |dx| or |dy| exceeds ALIGN_MAX_PT or the
    best recall is below ALIGN_MIN_RECALL.
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
    for dyp in range(-ALIGN_SEARCH_PT, ALIGN_SEARCH_PT + 1):
        for dxp in range(-ALIGN_SEARCH_PT, ALIGN_SEARCH_PT + 1):
            yy, xx = ty + dyp, tx + dxp
            ok = (yy >= 0) & (yy < hh) & (xx >= 0) & (xx < ww)
            rec = float(gd[yy[ok], xx[ok]].sum()) / ty.size
            tie_better = rec == best[0] and abs(dxp) + abs(dyp) < abs(best[1]) + abs(best[2])
            if rec > best[0] + 1e-9 or tie_better:
                best = (rec, dxp, dyp)
    recall, dxp, dyp = best
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
# CLI (Stage 1 only for now; extended below as lanes land)
# --------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("pdf", type=Path)
    ap.add_argument("--detected-year")
    ap.add_argument("--no-align", action="store_true")
    args = ap.parse_args(argv)
    res = match_template(args.pdf.read_bytes(), detected_year=args.detected_year, align=not args.no_align)
    print(json.dumps(res.to_dict(), indent=1, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
