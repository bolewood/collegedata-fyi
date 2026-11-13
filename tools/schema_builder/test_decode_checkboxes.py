"""Pins the D5 transfer-credit checkbox labels to what the official blank templates print.

The widget export names are misleading: the widget whose on-state is /TFER_RFS sits under the printed column header
"Recommended of Some" and /TFER_ROS under "Required of Some" (checked below against every blank template PDF that is in
schemas/templates, 2021-22 through 2025-26 once the 2024-25 and 2025-26 PDFs are committed). The decoder's labels follow the printed
headers, and the committed schema artifacts carry exactly the decoder's labels.
"""

import collections
import json
import unittest
from pathlib import Path

import pypdf
import pypdfium2 as pdfium

from tools.schema_builder import decode_checkboxes as dc

ROOT = Path(__file__).resolve().parents[2]
TEMPLATES = ROOT / "schemas" / "templates"
# on-state -> the column header the official templates print above that widget column (read from the PDFs; see the test below)
PRINTED_HEADER = {
    "/TFER_REQ": "Required of All",
    "/TFER_REC": "Recommended of All",
    "/TFER_RFS": "Recommended of Some",
    "/TFER_ROS": "Required of Some",
    "/TFER_NREQ": "Not Required",
}


def label_from_header(header: str) -> str:
    """The decoder's wording for a printed header: "of All" is implicit, "of Some" reads "for Some"."""
    return header.replace(" of All", "").replace(" of Some", " for Some")


def printed_headers(pdf: Path) -> dict[str, str]:
    """{on-state: header text printed above that column of widgets} for the D5 grid (the page that holds /TFER_* states)."""
    reader = pypdf.PdfReader(str(pdf))
    for page_index, page in enumerate(reader.pages):
        columns: dict[str, list[float]] = collections.defaultdict(list)
        top = None
        for annot in page.get("/Annots") or []:
            annot = annot.get_object()
            ap = annot.get("/AP")
            if not ap or "/N" not in ap:
                continue
            for state in (str(k) for k in ap["/N"].get_object().keys()):
                if state.startswith("/TFER_"):
                    rect = [float(v) for v in annot["/Rect"]]
                    columns[state].append((rect[0] + rect[2]) / 2)
                    top = max(top or 0, rect[3])
        if not columns:
            continue
        text_page = pdfium.PdfDocument(str(pdf))[page_index].get_textpage()
        ordered = sorted(((sum(v) / len(v), s) for s, v in columns.items()))
        xs = [x for x, _ in ordered]
        out = {}
        for i, (x, state) in enumerate(ordered):
            lo = (xs[i - 1] + x) / 2 if i else x - 45
            hi = (x + xs[i + 1]) / 2 if i + 1 < len(xs) else x + 45
            raw = text_page.get_text_bounded(lo, top + 4, hi, top + 75)
            words = " ".join(raw.split())
            for header in PRINTED_HEADER.values():           # the header text is the tail of what sits above the column
                if words.endswith(header):
                    out[state] = header
        return out
    raise AssertionError(f"no /TFER_ widgets in {pdf}")


class TransferCreditLabelTests(unittest.TestCase):
    def test_every_on_state_is_pinned_to_its_printed_column_label(self):
        for state, header in PRINTED_HEADER.items():
            self.assertEqual(dc.LABELS[state], label_from_header(header), state)

    def test_the_two_swapped_names_are_not_swapped_back(self):
        self.assertEqual(dc.LABELS["/TFER_RFS"], "Recommended for Some")
        self.assertEqual(dc.LABELS["/TFER_ROS"], "Required for Some")
        self.assertEqual(dc.label_for("REQ_CODE_ESSAY", "/TFER_RFS"), ("Recommended for Some", True))

    def test_the_blank_templates_print_those_headers_under_those_on_states(self):
        pdfs = sorted(TEMPLATES.glob("cds_*_template.pdf"))
        self.assertGreaterEqual(len(pdfs), 3)
        for pdf in pdfs:
            with self.subTest(template=pdf.name):
                self.assertEqual(printed_headers(pdf), PRINTED_HEADER)

    def test_the_committed_schemas_carry_the_decoders_labels(self):
        checked = 0
        for path in sorted((ROOT / "schemas").glob("cds_schema_????_??.json")):
            for field in json.loads(path.read_text()).get("fields", []):
                for option in field.get("value_options") or []:
                    if option["export"] in PRINTED_HEADER:
                        checked += 1
                        self.assertEqual(option["label"], label_from_header(PRINTED_HEADER[option["export"]]), (path.name, field["pdf_tag"], option))
        self.assertGreaterEqual(checked, 3 * 6 * 5)               # three schema years, six D5 rows, five states


if __name__ == "__main__":
    unittest.main()
