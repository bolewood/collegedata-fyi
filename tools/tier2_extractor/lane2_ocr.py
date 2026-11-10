#!/usr/bin/env python3
"""Lane 2 (PRD 038 M2): numeric OCR at the field map's widget rects.

Scope is the `numeric` emission class only (Number, Dollars, Percent, Identifier, Month, Day typed `/Tx`
widgets) on pages Lane 1 cannot read: image-only pages, invisible-text (OCR layer) pages and pages whose
text layer is unreadable. Free text, dropdowns and checkboxes are never read here.

Precision first: a value is emitted only when every one of these holds, and each failure is a named
abstention (`notes.withheld`, lane `ocr`):
  - the rect holds rendered ink the blank template does not have (`no_rendered_ink`);
  - the per-widget gates pass (`widget_gates`: band, local alignment, edge and numeric-token rules applied to
    the OCR word boxes, with the form's own label words dropped);
  - three reads agree: the tight rect at 300 DPI, the tight rect at 400 DPI, and the token found at the rect
    in a wider single-line context crop (`unstable_read`, `context_disagrees`);
  - every word of the three reads clears the Tesseract confidence floor (`low_confidence`);
  - the strict number grammar (`not_numeric` ...).
The OCR engine is injected (`Engine`): tests use a fake, the worker uses `TesseractEngine` (the `tesseract`
command line, no Python binding).
"""

from __future__ import annotations

import io
import os
import re
import shutil
import subprocess
from dataclasses import dataclass, field
from typing import Protocol

import numpy as np

import template_overlay as to

OCR_DPI = 300                  # the primary rendering
OCR_DPI_2 = 400                # the second rendering that must agree
CROP_INSET_PT = 1.2            # tight crop: the rect less the frame (PRD 038 Lane 2)
CROP_PAD_PX = 16               # white padding around every crop
CONTEXT_PAD_PT = 30.0          # the context crop reaches this far left and right of the rect, in its row
TEMPLATE_INK_GRAY = 200        # blank-template pixels darker than this are the form's own ink
TEMPLATE_INK_DILATE = 2        # ... thickened by this many pixels at OCR_DPI before they are erased from a context crop
MIN_NEW_INK_PX = 12            # rendered ink (216 DPI pixels) the blank lacks inside the rect
MIN_CONF = 85.0                # Tesseract word confidence floor (a further gate, never the only test)
LABEL_COVER = 0.5              # an OCR word box covered this much by the blank's own text boxes is label text
WHITELIST = "0123456789.,$%()+-"
# rule switches (all on in production; the report's per-rule costs run one off at a time)
RULE_NEW_INK = True            # the rect holds ink the blank lacks
RULE_GATES = True              # widget_gates on the OCR word boxes (band, local alignment, edge, token)
RULE_SECOND_RENDER = True      # the 400 DPI tight read must agree
RULE_CONTEXT = True            # the context-crop token at the rect must agree
RULE_CONF = True               # Tesseract confidence floor
RULE_LABEL_FILTER = True       # the blank's own label words are dropped from the boxes
RULE_ERASE_TEMPLATE = True     # the blank's own ink is erased from the context crop
NUMERIC_CLASS_TYPES = ("Number", "Dollars", "Percent", "Identifier", "Month", "Day")


@dataclass
class OcrWord:
    text: str
    conf: float
    left: int
    top: int
    right: int
    bottom: int                 # pixels of the image that was read


class Engine(Protocol):
    def read(self, img: np.ndarray, *, psm: int = 7) -> list[OcrWord]: ...


class TesseractEngine:
    """The `tesseract` command line, one single-line read per call (`--psm 7`, digit whitelist, TSV words)."""

    def __init__(self, exe: str = "tesseract", timeout: float = 30.0):
        self.exe, self.timeout = exe, timeout

    @staticmethod
    def available(exe: str = "tesseract") -> bool:
        return shutil.which(exe) is not None

    def version(self) -> str:
        r = subprocess.run([self.exe, "--version"], capture_output=True, text=True)
        return (r.stdout or r.stderr).splitlines()[0].strip()

    def read(self, img: np.ndarray, *, psm: int = 7) -> list[OcrWord]:
        from PIL import Image
        buf = io.BytesIO()
        Image.fromarray(img).save(buf, format="PNG")
        env = dict(os.environ, OMP_THREAD_LIMIT="1")
        r = subprocess.run([self.exe, "stdin", "stdout", "--psm", str(psm), "-c", f"tessedit_char_whitelist={WHITELIST}",
                            "-c", "load_system_dawg=0", "-c", "load_freq_dawg=0", "tsv"],
                           input=buf.getvalue(), capture_output=True, timeout=self.timeout, env=env)
        words = []
        for line in r.stdout.decode("utf-8", "replace").splitlines()[1:]:
            p = line.split("\t")
            if len(p) < 12 or p[0] != "5" or not p[11].strip():
                continue
            words.append(OcrWord(p[11].strip(), float(p[10]), int(p[6]), int(p[7]), int(p[6]) + int(p[8]), int(p[7]) + int(p[9])))
        return words


@dataclass
class Lane2Read:
    value: str | None = None
    reason: str | None = None            # the abstention, when value is None
    text: str = ""                       # the agreed raw read
    conf: float = 0.0                    # the lowest word confidence over the three reads
    reads: dict = field(default_factory=dict)


def _dilate(mask: np.ndarray, n: int) -> np.ndarray:
    return to._dilate(mask, n)


class Lane2:
    """OCR reader for one matched document (page renders are cached per page and DPI)."""

    def __init__(self, engine: Engine, year: str):
        self.engine, self.year = engine, year
        self._pages: dict[tuple, np.ndarray] = {}
        self._tpl: dict[tuple, np.ndarray] = {}

    # ---- renders -----------------------------------------------------------
    def page_gray(self, c: "to.PageCtx", dpi: int) -> np.ndarray:
        key = (id(c), dpi)
        if key not in self._pages:
            self._pages[key] = to._render_template_scale(c.page, c.geom, dpi)
        return self._pages[key]

    def template_gray(self, c: "to.PageCtx", dpi: int) -> np.ndarray:
        key = (c.year, c.p, dpi)
        if key not in self._tpl:
            self._tpl[key] = to._render_gray(to._template_doc(c.year)[c.p], dpi)
        return self._tpl[key]

    # ---- crops -------------------------------------------------------------
    def _crop(self, c, rect, dpi, *, x_pad_pt=0.0, inset_pt=0.0, erase_template=False) -> tuple[np.ndarray, tuple] | None:
        x0, y0, x1, y1 = rect
        win = [x0 + inset_pt - x_pad_pt, y0 + inset_pt, x1 - inset_pt + x_pad_pt, y1 - inset_pt]
        if win[2] <= win[0] or win[3] <= win[1]:
            return None
        g = self.page_gray(c, dpi)
        r0, r1, c0, c1 = to.template_rect_to_pixels(win, c.dx, c.dy, dpi)
        if x_pad_pt:                                     # the context crop may run off the page's side: it is cut at the page edge
            c0, c1 = max(c0, 0), min(c1, g.shape[1])
        if r0 < 0 or c0 < 0 or r1 > g.shape[0] or c1 > g.shape[1] or r1 <= r0 or c1 <= c0:
            return None
        img = g[r0:r1, c0:c1].copy()
        if erase_template:
            tg = self.template_gray(c, dpi)
            tr0, tr1, tc0, tc1 = to.template_rect_to_pixels(win, 0.0, 0.0, dpi)
            t = tg[tr0:tr1, tc0:tc1] < TEMPLATE_INK_GRAY
            h, w = min(img.shape[0], t.shape[0]), min(img.shape[1], t.shape[1])
            m = _dilate(t[:h, :w], TEMPLATE_INK_DILATE)
            img[:h, :w][m] = 255
        padded = np.full((img.shape[0] + 2 * CROP_PAD_PX, img.shape[1] + 2 * CROP_PAD_PX), 255, dtype=np.uint8)
        padded[CROP_PAD_PX:-CROP_PAD_PX, CROP_PAD_PX:-CROP_PAD_PX] = img
        return padded, (r0, c0)

    @staticmethod
    def _join(words: list[OcrWord]) -> str:
        return "".join(w.text for w in sorted(words, key=lambda w: w.left))

    def _to_boxes(self, c, words: list[OcrWord], origin: tuple[int, int], dpi: int) -> list["to.GlyphBox"]:
        """OCR word boxes as `GlyphBox` in template points (the same space and shape Lane 1's glyph boxes use)."""
        k = dpi / 72.0
        r0, c0 = origin
        out = []
        for w in words:
            col_l, col_r = c0 + w.left - CROP_PAD_PX, c0 + w.right - CROP_PAD_PX
            row_t, row_b = r0 + w.top - CROP_PAD_PX, r0 + w.bottom - CROP_PAD_PX
            left, right = col_l / k - c.dx, col_r / k - c.dx
            top, bottom = 792.0 - row_t / k - c.dy, 792.0 - row_b / k - c.dy
            out.append(to.GlyphBox(left, right, (top + bottom) / 2.0, top, bottom, w.text))
        return out

    @staticmethod
    def drop_label_words(boxes: list["to.GlyphBox"], static_chars) -> list["to.GlyphBox"]:
        """Seam S1: an OCR word box that the blank's own text boxes cover is label text, not an answer."""
        keep = []
        for b in boxes:
            area = max((b.right - b.left) * ((b.top or 0) - (b.bottom or 0)), 1e-6)
            cover = 0.0
            for s in static_chars:
                if s.ch.isspace() or s.top is None or s.bottom is None:
                    continue
                ox = min(b.right, s.right) - max(b.left, s.box_left)
                oy = min(b.top, s.top) - max(b.bottom, s.bottom)
                if ox > 0 and oy > 0:
                    cover += ox * oy
            if cover / area < LABEL_COVER:
                keep.append(b)
        return keep

    # ---- one widget --------------------------------------------------------
    def read_widget(self, c: "to.PageCtx", tag: str, f: dict, wi: int, rect: list[float], static_chars) -> Lane2Read:
        if RULE_NEW_INK and c.new_ink(rect) < MIN_NEW_INK_PX:
            return Lane2Read(reason="no_rendered_ink")
        reads: dict[str, str] = {}
        confs: list[float] = []
        for name, dpi in (("tight_300", OCR_DPI), ("tight_400", OCR_DPI_2)):
            cr = self._crop(c, rect, dpi, inset_pt=CROP_INSET_PT)
            if cr is None:
                return Lane2Read(reason="crop_off_page")
            words = self.engine.read(cr[0])
            reads[name] = self._join(words)
            confs += [w.conf for w in words]
            if name == "tight_300":
                if not reads[name]:
                    return Lane2Read(reason="ocr_empty", reads=reads)
                if RULE_CONF and min(confs) < MIN_CONF:       # no need to spend two more reads on a doubtful one
                    return Lane2Read(reason="low_confidence", reads=reads, conf=min(confs))
        ctx = self._crop(c, rect, OCR_DPI, x_pad_pt=CONTEXT_PAD_PT, erase_template=RULE_ERASE_TEMPLATE)
        if ctx is None:
            return Lane2Read(reason="crop_off_page", reads=reads)
        cwords = self.engine.read(ctx[0])
        boxes = self._to_boxes(c, cwords, ctx[1], OCR_DPI)
        if RULE_LABEL_FILTER:
            boxes = self.drop_label_words(boxes, static_chars)
        x0, y0, x1, y1 = rect
        at_rect = [(b, w) for b, w in zip(self._to_boxes(c, cwords, ctx[1], OCR_DPI), cwords)
                   if x0 <= b.cx <= x1 and y0 <= b.cy <= y1 and any(b is bb or b == bb for bb in boxes)]
        reads["context"] = "".join(w.text for _b, w in sorted(at_rect, key=lambda t: t[0].left))
        confs += [w.conf for _b, w in at_rect]
        why = to.widget_gates(c, tag, wi, rect, glyphs=boxes, multiline=False, emission_class=to.CLASS_NUMERIC) if RULE_GATES else None
        if why:
            return Lane2Read(reason=why, reads=reads)
        norm = {k: re.sub(r"\s+", "", v) for k, v in reads.items()}
        if RULE_SECOND_RENDER and norm["tight_300"] != norm["tight_400"]:
            return Lane2Read(reason="unstable_read", reads=reads)
        if RULE_CONTEXT and norm["context"] != norm["tight_300"]:
            return Lane2Read(reason="context_disagrees", reads=reads)
        conf = min(confs) if confs else 0.0
        if RULE_CONF and conf < MIN_CONF:
            return Lane2Read(reason="low_confidence", reads=reads, conf=conf)
        val, why = to.normalise_text_value(norm["tight_300"], f["value_type"], tag)
        if why:
            return Lane2Read(reason=why, text=norm["tight_300"], reads=reads, conf=conf)
        return Lane2Read(value=val, text=norm["tight_300"], conf=conf, reads=reads)


def make_hook(engine: Engine, stats: dict | None = None):
    """The `lane2=` callable for `template_overlay.extract_overlay`: reads the numeric widgets of the pages Lane 1 could not.

    Records `lane: 2`, `emission_class: numeric`, the agreeing reads and the confidence in the same shape as a
    Lane 1 value; every abstention goes to `notes.withheld` with lane `ocr`. `stats` (optional) collects counts
    and seconds for the report.
    """
    import time

    def hook(env) -> None:
        t0 = time.time()
        l2 = Lane2(engine, env.year)
        env.notes["ocr_engine"] = engine.version() if hasattr(engine, "version") else type(engine).__name__
        n_read = n_emit = 0
        for tag, f in env.fmap["fields"].items():
            if f["ft"] != "/Tx" or f["question_number"] is None or tag in env.done or tag not in env.tag_field:
                continue
            et = to.effective_type(tag, f["value_type"], f["ft"])
            if et not in NUMERIC_CLASS_TYPES:
                continue
            results: list[tuple[int, Lane2Read]] = []
            blocked = False
            for wi, w in enumerate(f["widgets"]):
                p = w["template_page"]
                q = env.by_tpage.get(p)
                if q is None or q not in env.ocr_pages:
                    blocked = True
                    continue
                c = env.ctx_for(q, p)
                n_read += 1
                r = l2.read_widget(c, tag, f, wi, w["rect"], to._template_chars(env.year, p))
                if r.reason == "no_rendered_ink":
                    results.append((q, r))              # an empty cell: nothing to read, nothing withheld
                    continue
                if r.value is None:
                    env.hold(tag, "ocr", r.reason or "ocr_failed", q, wi)
                    blocked = True
                    continue
                results.append((q, r))
            read = [(q, r) for q, r in results if r.value is not None]
            if blocked or not read:
                continue
            if len({r.value for _q, r in read}) > 1 or len(read) != len(results):
                env.hold(tag, "ocr", "multi_widget_disagreement", read[0][0])
                continue
            q, r = read[0]
            env.record(tag, r.value, 2, et, q, to.CLASS_NUMERIC,
                       {"ocr_confidence": round(r.conf, 1), "ocr_reads": r.reads, "lane_name": "ocr"})
            n_emit += 1
        if stats is not None:
            stats["seconds"] = stats.get("seconds", 0.0) + time.time() - t0
            stats["widgets_read"] = stats.get("widgets_read", 0) + n_read
            stats["emitted"] = stats.get("emitted", 0) + n_emit

    return hook
