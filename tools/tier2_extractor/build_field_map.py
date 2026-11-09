#!/usr/bin/env python3
"""Build a committed PDF field map for one CDS year (PRD 038, milestone M0).

A field map records, for every AcroForm field of the official fillable CDS
template, where each widget sits on the page, plus a static-ink raster of the
blank template. Template overlay extraction (PRD 038 M1+) uses it to read a
flattened copy of the official PDF at known coordinates.

Sources:
  * 2025-26, 2023-24: the blank official template PDF in schemas/templates/.
  * 2024-25: no blank PDF exists. The map is a consensus of two or more
    filled (Tier 2) donor PDFs. Every widget must agree within --tolerance pt.

Why donors can supply the static layer: a fillable form keeps field values in
the widget annotations (/V and /AP), never in the page content stream. The
static ink raster and static text are therefore taken from the page content
alone (annotations and form widgets are not drawn), and the raster is a strict-majority
vote across donors (a pixelwise AND for two), so a mark that only a minority of
donors carry is dropped.

Output (schemas/field_maps/cds_pdf_field_map_YYYY_YY.json) is deterministic:
sorted keys, no timestamps, rects rounded to 3 decimals, and the ink masks are
encoded with a hand-written run-length codec rather than zlib so the bytes do
not depend on the zlib build.

Usage:
    python tools/tier2_extractor/build_field_map.py --year 2025-26
    python tools/tier2_extractor/build_field_map.py --year 2023-24
    python tools/tier2_extractor/build_field_map.py --year 2024-25 \\
        --donor scratch/donors/a.pdf --donor scratch/donors/b.pdf
    python tools/tier2_extractor/build_field_map.py --year 2025-26 --check
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import re
import sys
import warnings
from collections import Counter
from pathlib import Path
from typing import Any

import numpy as np
import pypdf
import pypdfium2 as pdfium

REPO_ROOT = Path(__file__).resolve().parents[2]
SCHEMA_DIR = REPO_ROOT / "schemas"
TEMPLATE_DIR = SCHEMA_DIR / "templates"
FIELD_MAP_DIR = SCHEMA_DIR / "field_maps"

MAP_FORMAT_VERSION = 1
MASK_DPI = 36
INK_THRESHOLD = 225  # gray level < this counts as ink
DEFAULT_TOLERANCE_PT = 0.5
MIN_DONORS = 2
YEARS = ("2023-24", "2024-25", "2025-26")

MASK_ENCODING = (
    "rle-varint-base64: row-major bits (1 = ink), run lengths alternate "
    "starting with a white run (may be 0), LEB128 varints, base64"
)


# --------------------------------------------------------------------------
# paths
# --------------------------------------------------------------------------

def year_slug(year: str) -> str:
    return year.replace("-", "_")


def schema_path_for(year: str) -> Path:
    return SCHEMA_DIR / f"cds_schema_{year_slug(year)}.json"


def template_path_for(year: str) -> Path:
    return TEMPLATE_DIR / f"cds_{year}_template.pdf"


def field_map_path_for(year: str) -> Path:
    return FIELD_MAP_DIR / f"cds_pdf_field_map_{year_slug(year)}.json"


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


# --------------------------------------------------------------------------
# mask codec (public: M1 decodes with decode_mask)
# --------------------------------------------------------------------------

def _varint(n: int, out: bytearray) -> None:
    while True:
        b = n & 0x7F
        n >>= 7
        if n:
            out.append(b | 0x80)
        else:
            out.append(b)
            return


def encode_mask(mask: np.ndarray) -> str:
    """Encode a 2-D bool array (True = ink) as the RLE/varint/base64 string."""
    flat = np.ascontiguousarray(mask, dtype=bool).ravel()
    out = bytearray()
    if flat.size:
        change = np.flatnonzero(flat[1:] != flat[:-1]) + 1
        bounds = np.concatenate(([0], change, [flat.size]))
        runs = np.diff(bounds).tolist()
        if flat[0]:
            runs.insert(0, 0)  # runs always start with a white run
        for r in runs:
            _varint(int(r), out)
    return base64.b64encode(bytes(out)).decode("ascii")


def decode_mask(encoded: str, width: int, height: int) -> np.ndarray:
    """Inverse of encode_mask. Returns a (height, width) bool array."""
    data = base64.b64decode(encoded)
    runs: list[int] = []
    cur = shift = 0
    for b in data:
        cur |= (b & 0x7F) << shift
        if b & 0x80:
            shift += 7
        else:
            runs.append(cur)
            cur = shift = 0
    flat = np.zeros(width * height, dtype=bool)
    pos = 0
    ink = False
    for r in runs:
        if ink:
            flat[pos:pos + r] = True
        pos += r
        ink = not ink
    if pos != width * height:
        raise ValueError(f"mask run lengths sum to {pos}, expected {width * height}")
    return flat.reshape(height, width)


# --------------------------------------------------------------------------
# AcroForm harvest
# --------------------------------------------------------------------------

def _to_str(v: Any) -> str:
    return str(v)


def harvest_acroform(pdf_path: Path) -> dict:
    """Harvest widgets from a PDF.

    Returns {"pages": n, "fields": {tag: {...}}, "inverted": n_inverted}. Each
    field has ft, opt ([[export, display], ...] or None) and widgets (annotation
    order) of {page, rect, on}. Rects are normalized (x0<x1, y0<y1); `inverted`
    counts widgets whose /Rect was stored inverted.
    """
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        reader = pypdf.PdfReader(str(pdf_path))
        fields: dict[str, dict] = {}
        inverted = 0
        for page_index, page in enumerate(reader.pages):
            for ref in page.get("/Annots") or []:
                annot = ref.get_object()
                if annot.get("/Subtype") != "/Widget":
                    continue
                ft = annot.get("/FT")
                opt = annot.get("/Opt")
                parts = [] if annot.get("/T") is None else [str(annot["/T"])]
                node = annot
                while node.get("/Parent") is not None:
                    node = node["/Parent"].get_object()
                    if node.get("/T") is not None:
                        parts.insert(0, str(node["/T"]))
                    if ft is None:
                        ft = node.get("/FT")
                    if opt is None:
                        opt = node.get("/Opt")
                if not parts:
                    continue
                tag = ".".join(parts)
                x0, y0, x1, y1 = (float(v) for v in annot["/Rect"])
                if x0 > x1 or y0 > y1:
                    inverted += 1
                rect = [min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1)]

                on = None
                ap = annot.get("/AP")
                if str(ft) == "/Btn" and ap is not None and "/N" in ap.get_object():
                    normal = ap.get_object()["/N"].get_object()
                    # Button /N is a dict of state -> stream. (Text widgets
                    # carry a stream there, whose keys are not states.)
                    if not isinstance(normal, pypdf.generic.StreamObject) and hasattr(normal, "keys"):
                        states = [str(k) for k in normal.keys() if k != "/Off"]
                        on = states[0] if states else None

                entry = fields.setdefault(
                    tag, {"ft": str(ft) if ft is not None else None, "opt": None, "widgets": []}
                )
                if opt is not None and entry["opt"] is None:
                    pairs = []
                    for item in opt:
                        item = item.get_object() if hasattr(item, "get_object") else item
                        if isinstance(item, (list, pypdf.generic.ArrayObject)):
                            pairs.append([_to_str(item[0]), _to_str(item[1])])
                        else:
                            pairs.append([_to_str(item), _to_str(item)])
                    entry["opt"] = pairs
                entry["widgets"].append({"page": page_index, "rect": rect, "on": on})
        return {"pages": len(reader.pages), "fields": fields, "inverted": inverted}


# --------------------------------------------------------------------------
# static layer (page content only: no annotations, no form widgets)
# --------------------------------------------------------------------------

_CTRL = re.compile(r"[\x00-\x1f\x7f]")
_WS = re.compile(r"\s+")


def _ink_mask(page: "pdfium.PdfPage") -> np.ndarray:
    bitmap = page.render(
        scale=MASK_DPI / 72.0, draw_annots=False, may_draw_forms=False, rev_byteorder=True
    )
    rgb = bitmap.to_numpy()[..., :3].astype(np.uint32)
    # ITU-R 601 luma with PIL's fixed-point weights, so no Pillow dependency
    gray = (rgb[..., 0] * 19595 + rgb[..., 1] * 38470 + rgb[..., 2] * 7471 + 0x8000) >> 16
    return gray < INK_THRESHOLD


def _page_chars(page: "pdfium.PdfPage") -> list[tuple[str, tuple[float, float]]]:
    """Return [(char, (center_x, center_y))] for the page content text layer."""
    textpage = page.get_textpage()
    out = []
    for i in range(textpage.count_chars()):
        ch = textpage.get_text_range(i, 1)
        if not ch:
            continue
        left, bottom, right, top = textpage.get_charbox(i)
        out.append((ch, ((left + right) / 2.0, (bottom + top) / 2.0)))
    return out


def _text_in_rect(chars: list, rect: list[float]) -> str:
    x0, y0, x1, y1 = rect
    picked = [
        ch for ch, (cx, cy) in chars if x0 <= cx <= x1 and y0 <= cy <= y1
    ]
    text = _CTRL.sub(" ", "".join(picked))
    return _WS.sub(" ", text).strip()


def static_layer(pdf_path: Path, rects_by_page: dict[int, list[list[float]]]) -> dict:
    """Render the static layer of one PDF.

    Returns {"sizes": [(w, h)], "masks": [bool array], "texts": {(page, i): str}}
    where i indexes rects_by_page[page].
    """
    doc = pdfium.PdfDocument(str(pdf_path))
    sizes, masks, texts = [], [], {}
    try:
        for p in range(len(doc)):
            page = doc[p]
            if page.get_rotation() != 0:
                raise ValueError(f"{pdf_path.name}: page {p} is rotated; unsupported")
            if tuple(page.get_mediabox())[:2] != (0.0, 0.0):
                raise ValueError(f"{pdf_path.name}: page {p} mediabox origin is not (0, 0)")
            sizes.append(tuple(round(v, 3) for v in page.get_size()))
            masks.append(_ink_mask(page))
            chars = _page_chars(page)
            for i, rect in enumerate(rects_by_page.get(p, [])):
                texts[(p, i)] = _text_in_rect(chars, rect)
    finally:
        doc.close()
    return {"sizes": sizes, "masks": masks, "texts": texts}


# --------------------------------------------------------------------------
# schema join
# --------------------------------------------------------------------------

def load_schema_index(year: str) -> dict[str, dict]:
    with schema_path_for(year).open() as f:
        schema = json.load(f)
    index: dict[str, dict] = {}
    for field in schema["fields"]:
        tag = field.get("pdf_tag")
        if tag and tag not in index:  # first wins; ROTC_ARMY_TEXT repeats in 2023-24/2024-25
            index[tag] = field
    return index


# --------------------------------------------------------------------------
# consensus across sources
# --------------------------------------------------------------------------

class DonorDisagreement(Exception):
    pass


def _consensus_fields(harvests: list[dict], tolerance: float) -> dict[str, dict]:
    """Merge field harvests from >= 2 donors; every widget must agree."""
    base = harvests[0]["fields"]
    for h in harvests[1:]:
        if set(h["fields"]) != set(base):
            only_a = sorted(set(base) - set(h["fields"]))[:5]
            only_b = sorted(set(h["fields"]) - set(base))[:5]
            raise DonorDisagreement(f"donors disagree on field set: {only_a} vs {only_b}")
    merged: dict[str, dict] = {}
    for tag, entry in base.items():
        group = [h["fields"][tag] for h in harvests]
        if len({g["ft"] for g in group}) != 1:
            raise DonorDisagreement(f"{tag}: donors disagree on field type")
        if len({json.dumps(g["opt"]) for g in group}) != 1:
            raise DonorDisagreement(f"{tag}: donors disagree on /Opt")
        if len({len(g["widgets"]) for g in group}) != 1:
            raise DonorDisagreement(f"{tag}: donors disagree on widget count")
        widgets = []
        for i in range(len(entry["widgets"])):
            ws = [g["widgets"][i] for g in group]
            if len({w["page"] for w in ws}) != 1:
                raise DonorDisagreement(f"{tag}[{i}]: donors disagree on page")
            if len({w["on"] for w in ws}) != 1:
                raise DonorDisagreement(f"{tag}[{i}]: donors disagree on /AP /N on-state")
            rect = []
            for k in range(4):
                vals = [w["rect"][k] for w in ws]
                if max(vals) - min(vals) > tolerance:
                    raise DonorDisagreement(
                        f"{tag}[{i}]: rect coordinate {k} spread {max(vals) - min(vals):.3f} pt "
                        f"exceeds {tolerance} pt"
                    )
                rect.append(sum(vals) / len(vals))
            widgets.append({"page": ws[0]["page"], "rect": rect, "on": ws[0]["on"]})
        merged[tag] = {"ft": entry["ft"], "opt": entry["opt"], "widgets": widgets}
    return merged


def _consensus_static(layers: list[dict]) -> tuple[list, list[np.ndarray], dict, dict]:
    """Merge static layers: sizes must match, masks by strict majority, text by majority."""
    sizes = layers[0]["sizes"]
    for lay in layers[1:]:
        if lay["sizes"] != sizes:
            raise DonorDisagreement("donors disagree on page count or page size")
    masks, mask_disagreement = [], []
    for p in range(len(sizes)):
        stack = [lay["masks"][p] for lay in layers]
        votes = np.sum(stack, axis=0)
        masks.append(votes >= len(stack) // 2 + 1)  # strict majority; AND for 2 donors
        mask_disagreement.append(int(((votes > 0) & (votes < len(stack))).sum()))
    texts, text_disagreements = {}, 0
    for key in layers[0]["texts"]:
        votes = Counter(lay["texts"][key] for lay in layers)
        if len(votes) > 1:
            text_disagreements += 1
        best = sorted(votes.items(), key=lambda kv: (-kv[1], kv[0]))[0][0]
        texts[key] = best
    return sizes, masks, texts, {
        "mask_split_px_max": max(mask_disagreement),
        "mask_split_px_total": sum(mask_disagreement),
        "text_disagreements": text_disagreements,
    }


# --------------------------------------------------------------------------
# build
# --------------------------------------------------------------------------

def _r3(v: float) -> float:
    return round(float(v) + 0.0, 3)


def build_field_map(
    year: str,
    sources: list[Path],
    *,
    kind: str,
    tolerance: float = DEFAULT_TOLERANCE_PT,
) -> dict:
    if year not in YEARS:
        raise ValueError(f"unsupported year {year!r}")
    if kind not in ("blank_template", "donor_consensus"):
        raise ValueError(kind)
    if kind == "donor_consensus" and len(sources) < MIN_DONORS:
        raise ValueError(f"donor consensus needs at least {MIN_DONORS} donor PDFs")
    if kind == "blank_template" and len(sources) != 1:
        raise ValueError("a blank-template map takes exactly one PDF")
    # sort donors by sha so output never depends on CLI order
    pairs = sorted(((sha256_of(p), p) for p in sources), key=lambda sp: sp[0])
    if len({sha for sha, _ in pairs}) != len(pairs):
        raise ValueError("duplicate donor PDFs (same sha256); consensus needs distinct documents")
    shas = {p: sha for sha, p in pairs}
    sources = [p for _, p in pairs]

    harvests = [harvest_acroform(p) for p in sources]
    page_counts = {h["pages"] for h in harvests}
    if len(page_counts) != 1:
        raise DonorDisagreement(f"donors disagree on page count: {sorted(page_counts)}")
    n_pages = page_counts.pop()
    fields = _consensus_fields(harvests, tolerance)

    # canonical widget order per field: page, top-to-bottom, left-to-right
    for entry in fields.values():
        entry["widgets"].sort(key=lambda w: (w["page"], -w["rect"][3], w["rect"][0], -w["rect"][2]))

    rects_by_page: dict[int, list[list[float]]] = {}
    index_of: dict[tuple[str, int], tuple[int, int]] = {}
    for tag in sorted(fields):
        for wi, w in enumerate(fields[tag]["widgets"]):
            lst = rects_by_page.setdefault(w["page"], [])
            index_of[(tag, wi)] = (w["page"], len(lst))
            lst.append(w["rect"])

    layers = [static_layer(p, rects_by_page) for p in sources]
    sizes, masks, texts, static_stats = _consensus_static(layers)
    if len(sizes) != n_pages:
        raise DonorDisagreement("page count of rendered PDF differs from AcroForm page count")

    schema_index = load_schema_index(year)
    out_fields: dict[str, dict] = {}
    unjoined = []
    multi_on = 0
    for tag in sorted(fields):
        entry = fields[tag]
        sf = schema_index.get(tag)
        if sf is None:
            unjoined.append(tag)
        widgets = []
        for wi, w in enumerate(entry["widgets"]):
            rec: dict[str, Any] = {
                "template_page": w["page"],
                "rect": [_r3(v) for v in w["rect"]],
                "static_text": texts[index_of[(tag, wi)]],
            }
            if entry["ft"] == "/Btn":
                rec["on_state"] = w["on"]
            widgets.append(rec)
        rec_field: dict[str, Any] = {
            "ft": entry["ft"],
            "question_number": sf["question_number"] if sf else None,
            "value_type": sf["value_type"] if sf else None,
            "widgets": widgets,
        }
        if entry["opt"]:
            rec_field["opt"] = entry["opt"]
        out_fields[tag] = rec_field

    widget_total = sum(len(f["widgets"]) for f in out_fields.values())
    by_ft_fields = Counter(f["ft"] for f in out_fields.values())
    by_ft_widgets = Counter(f["ft"] for f in out_fields.values() for _ in f["widgets"])
    inverted = sum(h["inverted"] for h in harvests[:1])

    pages = []
    for p in range(n_pages):
        h, w = masks[p].shape
        pages.append({
            "index": p,
            "width_pt": sizes[p][0],
            "height_pt": sizes[p][1],
            "mask": {
                "width": int(w),
                "height": int(h),
                "ink_pixels": int(masks[p].sum()),
                "rle": encode_mask(masks[p]),
            },
        })

    stats: dict[str, Any] = {
        "fields": len(out_fields),
        "widgets": widget_total,
        "fields_by_ft": dict(sorted(by_ft_fields.items())),
        "widgets_by_ft": dict(sorted(by_ft_widgets.items())),
        "pages": n_pages,
        "inverted_rects_normalized": inverted,
        "tags_not_in_schema": len(unjoined),
        "static_text_widgets": sum(1 for f in out_fields.values() for w in f["widgets"] if w["static_text"]),
    }
    if kind == "donor_consensus":
        stats["donors"] = len(sources)
        stats["rect_tolerance_pt"] = tolerance
        stats.update(static_stats)

    return {
        "map_format_version": MAP_FORMAT_VERSION,
        "template_year": year,
        "schema_file": schema_path_for(year).name,
        "source": {
            "kind": kind,
            "files": [
                {"sha256": shas[p], **({"path": f"schemas/templates/{p.name}"} if kind == "blank_template" else {})}
                for p in sources
            ],
        },
        "raster": {
            "dpi": MASK_DPI,
            "ink_gray_lt": INK_THRESHOLD,
            "layer": "page content only (annotations and form widgets not drawn)",
            "engine": f"pypdfium2 {pdfium.version.PYPDFIUM_INFO.version if hasattr(pdfium.version.PYPDFIUM_INFO, 'version') else pdfium.version.PYPDFIUM_INFO}",
            "encoding": MASK_ENCODING,
        },
        "stats": stats,
        "fields": out_fields,
        "pages": pages,
    }


# --------------------------------------------------------------------------
# deterministic serialization
# --------------------------------------------------------------------------

def _j(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def dumps_field_map(fmap: dict) -> str:
    """One line per field and per page so git diffs stay readable."""
    lines = ["{"]
    top = sorted(fmap)
    for ti, key in enumerate(top):
        comma = "," if ti < len(top) - 1 else ""
        value = fmap[key]
        if key in ("fields",):
            tags = sorted(value)
            lines.append(f'{_j(key)}:{{')
            for i, tag in enumerate(tags):
                c = "," if i < len(tags) - 1 else ""
                lines.append(f"{_j(tag)}:{_j(value[tag])}{c}")
            lines.append(f"}}{comma}")
        elif key == "pages":
            lines.append(f'{_j(key)}:[')
            for i, pg in enumerate(value):
                c = "," if i < len(value) - 1 else ""
                lines.append(f"{_j(pg)}{c}")
            lines.append(f"]{comma}")
        else:
            lines.append(f"{_j(key)}:{_j(value)}{comma}")
    lines.append("}")
    return "\n".join(lines) + "\n"


def load_field_map(year: str) -> dict:
    """Load a committed field map (seam for M1)."""
    with field_map_path_for(year).open() as f:
        return json.load(f)


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------

def _build_for_cli(year: str, donors: list[Path], tolerance: float) -> dict:
    if year == "2024-25":
        if len(donors) < MIN_DONORS:
            raise SystemExit(
                f"2024-25 has no blank PDF; pass at least {MIN_DONORS} --donor PDFs "
                "(distinct Tier 2 documents)"
            )
        return build_field_map(year, donors, kind="donor_consensus", tolerance=tolerance)
    if donors:
        raise SystemExit(f"--donor applies only to 2024-25; {year} builds from its blank template")
    template = template_path_for(year)
    if not template.exists():
        raise SystemExit(f"missing template {template}")
    return build_field_map(year, [template], kind="blank_template")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--year", required=True, choices=YEARS)
    ap.add_argument("--donor", action="append", default=[], type=Path,
                    help="2024-25 only: a filled Tier 2 donor PDF (repeat, at least 2)")
    ap.add_argument("--out", type=Path, help="output path (default: schemas/field_maps/...)")
    ap.add_argument("--tolerance", type=float, default=DEFAULT_TOLERANCE_PT,
                    help="max donor disagreement per rect coordinate, in pt (default 0.5)")
    ap.add_argument("--check", action="store_true",
                    help="rebuild and compare with the committed map instead of writing")
    args = ap.parse_args(argv)

    fmap = _build_for_cli(args.year, args.donor, args.tolerance)
    text = dumps_field_map(fmap)
    out = args.out or field_map_path_for(args.year)
    s = fmap["stats"]
    if args.check:
        committed = out.read_text() if out.exists() else None
        same = committed == text
        print(f"{args.year}: {'identical' if same else 'DIFFERS from'} {out}", file=sys.stderr)
        return 0 if same else 1
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text)
    print(
        f"{args.year}: wrote {out} ({len(text) / 1024:.0f} KiB) fields={s['fields']} "
        f"widgets={s['widgets']} by_ft={s['widgets_by_ft']} inverted_normalized={s['inverted_rects_normalized']} "
        f"tags_not_in_schema={s['tags_not_in_schema']}",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
