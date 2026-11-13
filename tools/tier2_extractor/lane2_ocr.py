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
from pathlib import Path
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
RULE_SECOND_MODEL = True       # A12: tessdata_best on an Otsu crop, no whitelist, must parse to the same value
RULE_TOKEN_COMPLETE = True     # A12: no ink at the tight crop's left or right edge (the crop would cut the token), on the unmodified raster
RULE_RAW_CONTEXT = True        # A12: the edge and token gates also run on an OCR of the UNMODIFIED context crop (erasure must not hide a token's overlap with the cell edge)
RULE_CONTIGUOUS = True         # A12: one contiguous token: no internal gap wider than GAP_RATIO of the digit advance
RAW_BOX_MIN_INK = 10          # A12: a raw-context word whose box holds fewer dark pixels than this once the blank's ink is erased is the form's own rule or label, not a token
EDGE_BAND_PT = 1.5             # A12: ink (the blank's own ink erased from the strip) this far beyond the cell's left or right edge is a token the cell cuts
EDGE_BAND_MIN_PX = 6
CROP_EDGE_COLS = 2             # ink within this many pixel columns of the tight crop's left/right edge is ink the crop cuts
GAP_RATIO = 0.5                # fixed before the two.jsonl sweep (a word space is ~0.5 of a digit advance; set from typography, not the sweep)
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


# the second model (PRD A12): tessdata_best eng, fetched and verified by fetch_tessdata.py, never committed
MODEL_SHA256 = {
    "fast": "7d4322bd2a7749724879683fc3912cb542f19906c83bcc1a52132556427170b2",     # tessdata_fast eng (the Homebrew / apt model)
    "best": "8280aed0782fe27257a68ea10fe7ef324ca0f8d85bd2fd145d1c2b560bcb66ba",     # tessdata_best eng (LSTM float)
}


def best_model_dir() -> str:
    return os.environ.get("CDS_TESSDATA_BEST") or str(Path.home() / ".cache" / "cds-tessdata" / "best")


def _sha256(path: str) -> str | None:
    import hashlib
    try:
        return hashlib.sha256(Path(path).read_bytes()).hexdigest()
    except OSError:
        return None


def otsu(img: np.ndarray) -> np.ndarray:
    """Otsu-binarised copy (0 ink, 255 paper): the second model's preprocessing, as the verifier defined it."""
    h = np.bincount(img.ravel(), minlength=256).astype(float)
    p = h / h.sum()
    w, m = np.cumsum(p), np.cumsum(p * np.arange(256))
    s = (m[-1] * w - m) ** 2 / np.maximum(w * (1 - w), 1e-12)
    return np.where(img > int(np.argmax(s)), 255, 0).astype(np.uint8)


class TesseractEngine:
    """The `tesseract` command line, one single-line read per call (`--psm 7`, digit whitelist, TSV words).

    `read` raises on a failed run (a missing model must not look like thousands of empty cells). `check()` probes a
    known rendered string with the primary and the second model and returns a reason when Lane 2 must be off.
    """

    def __init__(self, exe: str = "tesseract", timeout: float = 30.0, best_dir: str | None = None):
        self.exe, self.timeout = exe, timeout
        self.best_dir = best_dir or best_model_dir()

    def model_info(self) -> dict:
        prim = None
        r = subprocess.run([self.exe, "--list-langs"], capture_output=True, text=True)
        for line in (r.stdout or "").splitlines():
            m = re.search(r'languages in "?([^"(]+?)"?\s*(?:\(|:|$)', line)
            if line.startswith("List of available languages") and m:
                prim = m.group(1).strip()
        return {"fast_sha256": _sha256(str(Path(prim) / "eng.traineddata")) if prim else None,
                "best_sha256": _sha256(str(Path(self.best_dir) / "eng.traineddata"))}

    def check(self) -> str | None:
        """None when both models read a probe string; else why Lane 2 is disabled (fail closed)."""
        from PIL import Image, ImageDraw, ImageFont
        if not self.available(self.exe):
            return "tesseract_not_installed"
        info = self.model_info()
        if info["best_sha256"] != MODEL_SHA256["best"]:
            return f"second_model_missing_or_wrong_sha ({self.best_dir})"
        if info["fast_sha256"] != MODEL_SHA256["fast"]:
            return "primary_model_sha_not_the_measured_tessdata_fast"
        img = Image.new("L", (520, 110), 255)
        ImageDraw.Draw(img).text((20, 15), "0123456789", fill=0, font=ImageFont.load_default(size=64))
        arr = np.array(img)
        try:
            a = "".join(w.text for w in self.read(arr))
            b = "".join(w.text for w in self.read(otsu(arr), whitelist=False, tessdata=self.best_dir))
        except Exception as e:  # noqa: BLE001
            return f"probe_failed: {e}"
        if a != "0123456789" or b != "0123456789":
            return f"probe_misread: primary {a!r}, second {b!r}"
        return None

    @staticmethod
    def available(exe: str = "tesseract") -> bool:
        return shutil.which(exe) is not None

    def version(self) -> str:
        r = subprocess.run([self.exe, "--version"], capture_output=True, text=True)
        return (r.stdout or r.stderr).splitlines()[0].strip()

    def read(self, img: np.ndarray, *, psm: int = 7, whitelist: bool = True, tessdata: str | None = None) -> list[OcrWord]:
        from PIL import Image
        buf = io.BytesIO()
        Image.fromarray(img).save(buf, format="PNG")
        env = dict(os.environ, OMP_THREAD_LIMIT="1")
        args = [self.exe, "stdin", "stdout", "--psm", str(psm)]
        if tessdata:
            args += ["--tessdata-dir", tessdata]
        if whitelist:
            args += ["-c", f"tessedit_char_whitelist={WHITELIST}"]
        args += ["-c", "load_system_dawg=0", "-c", "load_freq_dawg=0", "-c", "tessedit_create_tsv=1"]     # (the `tsv` config file is not in tessdata_best)
        r = subprocess.run(args, input=buf.getvalue(), capture_output=True, timeout=self.timeout, env=env)
        if r.returncode != 0:
            raise RuntimeError(f"tesseract exited {r.returncode}: {r.stderr.decode('utf-8', 'replace').strip()[:200]}")
        words = []
        for line in r.stdout.decode("utf-8", "replace").splitlines()[1:]:
            p = line.split("\t")
            if len(p) < 12 or p[0] != "5" or not p[11].strip():
                continue
            words.append(OcrWord(p[11].strip(), float(p[10]), int(p[6]), int(p[7]), int(p[6]) + int(p[8]), int(p[7]) + int(p[9])))
        return words


def token_geometry(tight: np.ndarray, text: str) -> tuple[bool, bool]:
    """(touches_edge, has_gap) of the ink in the UNMODIFIED tight crop (no template erasure, no padding).

    touches_edge: ink in the first or last CROP_EDGE_COLS columns, i.e. the crop cuts (or abuts) a glyph.
    has_gap: an internal run of empty columns wider than GAP_RATIO of the digit advance (extent / characters).
    """
    ink = otsu(tight) == 0
    cols = ink.any(axis=0)
    if not cols.any():
        return False, False
    edge = bool(cols[:CROP_EDGE_COLS].any() or cols[-CROP_EDGE_COLS:].any())
    xs = np.nonzero(cols)[0]
    lo, hi = int(xs[0]), int(xs[-1])
    n = max(1, len(re.sub(r"[^0-9]", "", text)))
    adv = (hi - lo + 1) / n
    gap = 0
    run = 0
    for c in cols[lo:hi + 1]:
        run = 0 if c else run + 1
        gap = max(gap, run)
    return edge, gap > GAP_RATIO * adv


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

    @staticmethod
    def _new_ink_in(erased: np.ndarray, raw: np.ndarray, w: OcrWord) -> int:
        """Dark pixels the blank does not explain inside an OCR word's box (the erased context crop has the same geometry as the raw one)."""
        if erased.shape != raw.shape:
            return RAW_BOX_MIN_INK
        return int((erased[max(w.top, 0):w.bottom, max(w.left, 0):w.right] < 128).sum())

    def _ink_beyond_edges(self, c, rect) -> bool:
        """Completeness against the raster: dark ink left over in a strip just outside the cell's left or right edge, after the
        blank's own ink (the rule the digit may touch) is removed from the strip, means the cell cuts a longer token."""
        x0, y0, x1, y1 = rect
        for win in ([x0 - EDGE_BAND_PT, y0 + 1.0, x0, y1 - 1.0], [x1, y0 + 1.0, x1 + EDGE_BAND_PT, y1 - 1.0]):
            cr = self._crop(c, win, OCR_DPI, erase_template=True)
            if cr is not None and int((cr[0][CROP_PAD_PX:-CROP_PAD_PX, CROP_PAD_PX:-CROP_PAD_PX] < 128).sum()) >= EDGE_BAND_MIN_PX:
                return True
        return False

    def _second_model(self, tight: np.ndarray) -> str:
        """tessdata_best, Otsu-binarised tight crop, psm 7, NO digit whitelist (a letter must survive to be seen)."""
        words = self.engine.read(otsu(tight), whitelist=False, tessdata=getattr(self.engine, "best_dir", None))
        return " ".join(w.text for w in sorted(words, key=lambda w: w.left))      # spaces kept: "12 34" must not parse

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
        cr300 = self._crop(c, rect, OCR_DPI, inset_pt=CROP_INSET_PT)[0][CROP_PAD_PX:-CROP_PAD_PX, CROP_PAD_PX:-CROP_PAD_PX]
        edge, gap = token_geometry(cr300, norm["tight_300"])
        if RULE_RAW_CONTEXT:
            raw = self._crop(c, rect, OCR_DPI, x_pad_pt=CONTEXT_PAD_PT, erase_template=False)
            if raw is not None:
                rwords = self.engine.read(raw[0])
                rwords = [w for w in rwords if self._new_ink_in(ctx[0], raw[0], w) >= RAW_BOX_MIN_INK]
                rboxes = self._to_boxes(c, rwords, raw[1], OCR_DPI)
                if RULE_LABEL_FILTER:
                    rboxes = self.drop_label_words(rboxes, static_chars)
                rwhy = to.widget_gates(c, tag, wi, rect, glyphs=rboxes, multiline=False, emission_class=to.CLASS_NUMERIC) if RULE_GATES else None
                if rwhy:
                    return Lane2Read(reason="raw_" + rwhy, reads=reads, conf=conf)
        if RULE_TOKEN_COMPLETE and self._ink_beyond_edges(c, rect):
            return Lane2Read(reason="ink_beyond_cell_edge", reads=reads, conf=conf)
        if RULE_TOKEN_COMPLETE and edge:
            return Lane2Read(reason="token_touches_crop_edge", reads=reads, conf=conf)
        if RULE_CONTIGUOUS and gap:
            return Lane2Read(reason="token_not_contiguous", reads=reads, conf=conf)
        if RULE_SECOND_MODEL:
            second = self._second_model(cr300)
            reads["second_model"] = second
            sv, swhy = to.normalise_text_value(second.strip(), f["value_type"], tag) if second.strip() else (None, "empty")
            if sv is None or sv != val:
                return Lane2Read(reason="second_model_empty" if not second else "second_model_disagrees", reads=reads, conf=conf)
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
        if hasattr(engine, "model_info"):
            env.notes["ocr_models"] = engine.model_info()
        why_off = engine.check() if hasattr(engine, "check") and RULE_SECOND_MODEL else None
        if why_off:
            env.notes["lane2_disabled"] = why_off              # fail closed, loudly: nothing is read, and the notes say why
            return
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
            env.record(tag, r.value, 2, et, q, to.CLASS_OCR_NUMERIC,
                       {"ocr_confidence": round(r.conf, 1), "ocr_reads": r.reads, "lane_name": "ocr"})
            n_emit += 1
        if stats is not None:
            stats["seconds"] = stats.get("seconds", 0.0) + time.time() - t0
            stats["widgets_read"] = stats.get("widgets_read", 0) + n_read
            stats["emitted"] = stats.get("emitted", 0) + n_emit

    return hook
