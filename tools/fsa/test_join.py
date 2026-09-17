"""Join, collapse, rate, suppression, and numeric-Excel fixture tests."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from openpyxl import Workbook

from tools.fsa.match import (
    DirectoryRow,
    collapse_to_school_id,
    directory_from_scorecard,
    match_fsa_row,
    match_fsa_rows,
    index_directory,
)
from tools.fsa.parse import FsaRow, parse_workbook
from tools.fsa.opeid import restore_fsa_opeid


def _dir(
    ipeds_id: str,
    school_id: str,
    *,
    in_scope: bool = True,
    main_campus: bool = True,
    opeid: str | None = "00153500",
) -> DirectoryRow:
    return DirectoryRow(
        ipeds_id=ipeds_id,
        school_id=school_id,
        school_name=school_id,
        in_scope=in_scope,
        main_campus=main_campus,
        opeid=opeid,
        opeid6=None if opeid is None else opeid[:6],
    )


def _fsa(opeid: str, rate: float | None = 0.05, visible: bool = True) -> FsaRow:
    return FsaRow(
        opeid=opeid,
        school_name="x",
        school_type="PUBLIC",
        state="FL",
        borrowers_in_denom=10000,
        borrowers_raw="11500",
        nonpayment_rate=rate,
        rate_raw=None if rate is None else str(rate),
        suppressed=not visible,
        public_visible=visible,
    )


class JoinTests(unittest.TestCase):
    def test_six_digit_unique_main_rollup(self):
        by8, by6 = index_directory([
            _dir("134130", "uf", opeid="00153500"),
            _dir("134130b", "uf-branch", main_campus=False, opeid="00153501"),
        ])
        result = match_fsa_row("001535", by8, by6)
        self.assertEqual(result.school_id, "uf")
        self.assertEqual(result.match_kind, "rollup_6")

    def test_numeric_excel_does_not_take_eight_digit_path(self):
        restored = restore_fsa_opeid(100201)
        self.assertEqual(restored, "100201")
        by8, by6 = index_directory([
            _dir("1", "wrong-campus", opeid="00100201"),
            _dir("2", "main", opeid="10020100"),
        ])
        result = match_fsa_row(restored, by8, by6)
        self.assertEqual(result.school_id, "main")
        self.assertEqual(result.match_kind, "rollup_6")
        exact = match_fsa_row("00100201", by8, by6)
        self.assertEqual(exact.school_id, "wrong-campus")
        self.assertEqual(exact.match_kind, "exact_8")

    def test_exact_eight_when_present(self):
        by8, by6 = index_directory([_dir("1", "campus", opeid="00100201")])
        result = match_fsa_row("00100201", by8, by6)
        self.assertEqual(result.match_kind, "exact_8")
        self.assertEqual(result.school_id, "campus")

    def test_ambiguous_mains_unmatched(self):
        by8, by6 = index_directory([
            _dir("1", "a", opeid="03113300"),
            _dir("2", "b", opeid="03113300"),
        ])
        result = match_fsa_row("031133", by8, by6)
        self.assertIsNone(result.school_id)
        self.assertEqual(result.reason, "ambiguous_main")

    def test_out_of_scope_ignored(self):
        by8, by6 = index_directory([
            _dir("1", "closed", in_scope=False, opeid="00153500"),
        ])
        result = match_fsa_row("001535", by8, by6)
        self.assertIsNone(result.school_id)
        self.assertEqual(result.reason, "no_in_scope_main")

    def test_collapse_omits_two_rollups(self):
        matches = match_fsa_rows(
            [_fsa("031133"), _fsa("039696")],
            [
                _dir("1", "uei", opeid="03113300"),
                _dir("2", "uei", opeid="03969600"),
            ],
        )
        # Both mains are different UNITIDs that somehow share school_id.
        collapsed = collapse_to_school_id(matches)
        self.assertIn("uei", collapsed.collisions_before_collapse)
        self.assertIn("uei", collapsed.omitted_school_ids)

    def test_collapse_keeps_single_rollup(self):
        matches = match_fsa_rows(
            [_fsa("001535")],
            [_dir("134130", "uf", opeid="00153500")],
        )
        collapsed = collapse_to_school_id(matches)
        kept = [m for m in collapsed.kept if m.school_id]
        self.assertEqual(len(kept), 1)
        self.assertEqual(kept[0].school_id, "uf")


class ScorecardDirectoryAttachTests(unittest.TestCase):
    def test_scorecard_opeid_pads_to_eight(self):
        row = directory_from_scorecard(
            ipeds_id="134130",
            school_id="uf",
            school_name="University of Florida",
            in_scope=True,
            main_campus=True,
            scorecard_opeid=153500,
        )
        self.assertEqual(row.opeid, "00153500")
        self.assertEqual(row.opeid6, "001535")


class ParseWorkbookTests(unittest.TestCase):
    def _write(self, opeid: object, rate: object, denom: object = 1200) -> Path:
        wb = Workbook()
        defs = wb.active
        defs.title = "Definitions"
        defs["A1"] = "This tab provides definitions for nonpayment rates."
        defs["A4"] = "Data Run Date: Data was run late May 2026."
        ws = wb.create_sheet("School-Level Nonpayment Rates")
        ws["A1"] = "Nonpayment Rates by Institution (as of May 2026)"
        for col, header in enumerate(
            ["OPE ID", "School Name", "School Type", "State", "Total Borrowers Evaluated", "Nonpayment Rate"],
            1,
        ):
            ws.cell(3, col, header)
        ws.cell(4, 1, opeid)
        ws.cell(4, 2, "Example College")
        ws.cell(4, 3, "PUBLIC")
        ws.cell(4, 4, "FL")
        ws.cell(4, 5, denom)
        ws.cell(4, 6, rate)
        handle = tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False)
        path = Path(handle.name)
        handle.close()
        wb.save(path)
        return path

    def test_numeric_excel_opeid_fixture(self):
        path = self._write(100201, 0.25)
        parsed = parse_workbook(path)
        self.assertEqual(parsed.rows[0].opeid, "100201")
        self.assertEqual(parsed.opeid_digit_length, 6)
        self.assertEqual(parsed.rows[0].nonpayment_rate, 0.25)
        self.assertTrue(parsed.rows[0].public_visible)
        self.assertEqual(parsed.as_of_label, "late May 2026")
        self.assertEqual(parsed.rate_scale, "0-1")

    def test_percent_scale_converts_to_fraction(self):
        parsed = parse_workbook(self._write("001535", 25))
        self.assertEqual(parsed.rows[0].nonpayment_rate, 0.25)

    def test_suppression_not_public(self):
        parsed = parse_workbook(self._write("001535", "<10%", "<100"))
        row = parsed.rows[0]
        self.assertTrue(row.suppressed)
        self.assertFalse(row.public_visible)
        self.assertIsNone(row.nonpayment_rate)
        self.assertIn("<10%", parsed.suppression_tokens)

    def test_duplicate_opeid_aborts(self):
        wb_path = self._write("001535", 0.1)
        from openpyxl import load_workbook
        wb = load_workbook(wb_path)
        ws = wb["School-Level Nonpayment Rates"]
        for col, value in enumerate(["001535", "Dup", "PUBLIC", "FL", 200, 0.2], 1):
            ws.cell(5, col, value)
        wb.save(wb_path)
        with self.assertRaises(ValueError):
            parse_workbook(wb_path)


if __name__ == "__main__":
    unittest.main()
