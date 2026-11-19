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


def printed_beside(pdf: Path, pdf_tag: str) -> dict[str, str]:
    """{on-state: text printed to the right of that widget, whitespace removed, lower case} for one button field."""
    reader = pypdf.PdfReader(str(pdf))
    document = pdfium.PdfDocument(str(pdf))
    out: dict[str, str] = {}
    for page_index, page in enumerate(reader.pages):
        for annot in page.get("/Annots") or []:
            annot = annot.get_object()
            parent = annot.get("/Parent")
            name = annot.get("/T") or (parent.get_object().get("/T") if parent else None)
            ap = annot.get("/AP")
            if name != pdf_tag or not ap or "/N" not in ap:
                continue
            left, bottom, right, top = (float(v) for v in annot["/Rect"])
            text = document[page_index].get_textpage().get_text_bounded(right, bottom - 2, right + 150, top + 2)
            for state in (str(k) for k in ap["/N"].get_object().keys()):
                if state != "/Off":
                    out[state] = "".join(text.split()).lower()
    return out


class Template2026OptionLabelTests(unittest.TestCase):
    """The three option fields 2026-27 adds: each decoder label is the text the blank template prints beside that box."""

    PDF = TEMPLATES / "cds_2026-27_template.pdf"
    FIELDS = {
        "ESSAY_AI": {"/Prohibited", "/Permitted", "/Fully allowed", "/Unmonitored", "/No Policy"},
        "ADMS_TEST_POLICY": {"/TO", "/TR", "/TB"},
        "EXP_I": {"/E", "/O"},
    }

    def test_each_label_is_printed_beside_its_box(self):
        for pdf_tag, states in self.FIELDS.items():
            beside = printed_beside(self.PDF, pdf_tag)
            self.assertEqual(set(beside), states, pdf_tag)
            for state, text in beside.items():
                label, known = dc.label_for(pdf_tag, state)
                self.assertTrue(known, (pdf_tag, state))
                self.assertIn("".join(label.split()).lower(), text, (pdf_tag, state))

    def test_states_are_read_for_buttons_pypdf_reports_none_for(self):
        states = dc.load_button_states(self.PDF)
        self.assertEqual(states["EXP_I"], ["/E", "/O"])
        self.assertEqual(states["ACAD_COA"], ["/On", "/Off"])        # the list pypdf gave this checkbox in 2025-26
        self.assertEqual(states["ACAD_COA"], dc.load_button_states(TEMPLATES / "cds_2025-26_template.pdf")["ACAD_COA"])

    def test_o_still_means_open_admission_on_its_own_field(self):
        self.assertEqual(dc.label_for("AD_OPEN_MOST", "/O"), ("Open admission", True))
        self.assertEqual(dc.label_for("EXP_I", "/O"), ("Firm and Final", True))


if __name__ == "__main__":
    unittest.main()
