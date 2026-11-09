"""Unit tests for the flattened-reprint source selection guard in worker.py."""

from __future__ import annotations

from io import BytesIO
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

import pypdf
from pypdf.generic import (
    ArrayObject,
    BooleanObject,
    DictionaryObject,
    NameObject,
    NumberObject,
    TextStringObject,
)

TOOLS_DIR = Path(__file__).resolve().parent.parent
WORKER_DIR = Path(__file__).resolve().parent
for p in (TOOLS_DIR, WORKER_DIR):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from extraction_worker import worker  # noqa: E402


def _escape_pdf_text(text: str) -> str:
    return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def build_flat_pdf(page_texts: list[str]) -> bytes:
    """Create a valid multi-page PDF with a plain text layer and no form fields."""
    objects: list[bytes] = []

    def add_obj(body: bytes) -> int:
        objects.append(body)
        return len(objects)

    font_id = add_obj(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")
    pages_id = add_obj(b"")  # placeholder filled once kids are known
    kid_ids: list[int] = []

    for text in page_texts:
        lines = text.splitlines() or [""]
        ops = ["BT", "/F1 10 Tf", "36 750 Td", "12 TL"]
        for idx, line in enumerate(lines):
            escaped = _escape_pdf_text(line)
            if idx == 0:
                ops.append(f"({escaped}) Tj")
            else:
                ops.append(f"T* ({escaped}) Tj")
        ops.append("ET")
        stream_bytes = "\n".join(ops).encode("latin-1", errors="replace")
        content_id = add_obj(
            f"<< /Length {len(stream_bytes)} >>\nstream\n".encode("ascii")
            + stream_bytes
            + b"\nendstream"
        )
        page_id = add_obj(
            f"<< /Type /Page /Parent {pages_id} 0 R "
            f"/MediaBox [0 0 612 792] "
            f"/Resources << /Font << /F1 {font_id} 0 R >> >> "
            f"/Contents {content_id} 0 R >>".encode("ascii")
        )
        kid_ids.append(page_id)

    kids_ref = " ".join(f"{kid} 0 R" for kid in kid_ids)
    objects[pages_id - 1] = (
        f"<< /Type /Pages /Kids [{kids_ref}] /Count {len(kid_ids)} >>".encode("ascii")
    )
    catalog_id = add_obj(f"<< /Type /Catalog /Pages {pages_id} 0 R >>".encode("ascii"))

    out = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for idx, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out.extend(f"{idx} 0 obj\n".encode("ascii"))
        out.extend(body)
        out.extend(b"\nendobj\n")

    xref_pos = len(out)
    out.extend(f"xref\n0 {len(objects) + 1}\n".encode("ascii"))
    out.extend(b"0000000000 65535 f \n")
    for off in offsets[1:]:
        out.extend(f"{off:010d} 00000 n \n".encode("ascii"))
    out.extend(
        f"trailer\n<< /Size {len(objects) + 1} /Root {catalog_id} 0 R >>\n"
        f"startxref\n{xref_pos}\n%%EOF\n".encode("ascii")
    )
    return bytes(out)


def build_fillable_pdf(
    fields: dict[str, str],
    *,
    page_count: int = 10,
) -> bytes:
    """Create a valid PDF with `page_count` pages and AcroForm text fields."""
    writer = pypdf.PdfWriter()
    for _ in range(page_count):
        writer.add_blank_page(width=612, height=792)

    field_refs = ArrayObject()
    for name, value in fields.items():
        field_dict = DictionaryObject(
            {
                NameObject("/FT"): NameObject("/Tx"),
                NameObject("/T"): TextStringObject(name),
                NameObject("/V"): TextStringObject(value),
            }
        )
        field_refs.append(writer._add_object(field_dict))

    acroform = DictionaryObject(
        {
            NameObject("/Fields"): field_refs,
            NameObject("/NeedAppearances"): BooleanObject(True),
            NameObject("/SigFlags"): NumberObject(0),
        }
    )
    writer._root_object[NameObject("/AcroForm")] = writer._add_object(acroform)

    buf = BytesIO()
    writer.write(buf)
    return buf.getvalue()


def make_standard_fillable_fields(
    numeric_values: list[str],
    *,
    total_filled: int = 55,
) -> dict[str, str]:
    """Build >=50 filled fields combining the given numeric values with text fillers."""
    fields: dict[str, str] = {}
    for idx, val in enumerate(numeric_values):
        fields[f"NUM_FIELD_{idx:03d}"] = val
    filler_idx = 0
    while len(fields) < total_filled:
        fields[f"TEXT_FIELD_{filler_idx:03d}"] = f"Yes_{filler_idx}"
        filler_idx += 1
    return fields


class _FakeQuery:
    def __init__(self, client: "_FakeClient", table_name: str):
        self.client = client
        self.table_name = table_name
        self.action = "select"
        self.payload = None
        self.filters: list[tuple[str, str, object]] = []
        self.limit_n: int | None = None

    def select(self, *_args, **_kwargs):
        self.action = "select"
        return self

    def insert(self, payload):
        self.action = "insert"
        self.payload = payload
        return self

    def update(self, payload):
        self.action = "update"
        self.payload = payload
        return self

    def eq(self, col: str, val: object):
        self.filters.append(("eq", col, val))
        return self

    def in_(self, col: str, vals: list[object]):
        self.filters.append(("in", col, tuple(vals)))
        return self

    def is_(self, col: str, val: object):
        self.filters.append(("is", col, val))
        return self

    def order(self, *_args, **_kwargs):
        return self

    def limit(self, n: int):
        self.limit_n = n
        return self

    def _matches(self, row: dict) -> bool:
        for kind, col, val in self.filters:
            if kind == "eq" and row.get(col) != val:
                return False
            if kind == "in" and row.get(col) not in val:
                return False
            if kind == "is" and val == "null" and row.get(col) is not None:
                return False
        return True

    def execute(self):
        if self.table_name == "cds_artifacts":
            if self.action == "insert":
                row = dict(self.payload)
                row.setdefault("id", f"art-{len(self.client.artifacts) + 1}")
                row.setdefault("created_at", f"2026-11-09T12:00:{len(self.client.artifacts):02d}+00:00")
                # Newest first to mirror `.order("created_at", desc=True)`
                self.client.artifacts.insert(0, row)
                self.client.inserted_canonical.append(row)
                return type("R", (), {"data": [row], "count": 1})()

            rows = [r for r in self.client.artifacts if self._matches(r)]
            if self.limit_n is not None:
                rows = rows[: self.limit_n]
            return type("R", (), {"data": rows, "count": len(rows)})()

        if self.table_name == "cds_documents":
            if self.action == "update":
                self.client.document_updates.append(dict(self.payload))
            return type("R", (), {"data": [], "count": 0})()

        return type("R", (), {"data": [], "count": 0})()


class _FakeStorageBucket:
    def __init__(self, blobs: dict[str, bytes]):
        self.blobs = blobs

    def download(self, storage_path: str) -> bytes:
        if storage_path not in self.blobs:
            raise RuntimeError(f"missing storage blob: {storage_path}")
        return self.blobs[storage_path]


class _FakeStorage:
    def __init__(self, blobs: dict[str, bytes]):
        self.bucket = _FakeStorageBucket(blobs)

    def from_(self, _name: str) -> _FakeStorageBucket:
        return self.bucket


class _FakeClient:
    def __init__(self, artifacts: list[dict], blobs: dict[str, bytes]):
        self.artifacts = list(artifacts)
        self.storage = _FakeStorage(blobs)
        self.inserted_canonical: list[dict] = []
        self.document_updates: list[dict] = []

    def table(self, name: str) -> _FakeQuery:
        return _FakeQuery(self, name)


class FlattenedReprintGuardTests(unittest.TestCase):
    def setUp(self) -> None:
        self.numeric_values = [
            "$58,104",
            "12,345",
            "23,456",
            "34,567",
            "4,567",
            "5,678",
            "6,789",
            "7,890",
            "8,901",
            "9,012",
            "1,111",
            "2,222",
            "3,333",
            "4,444",
            "5,555",
            "6,666",
            "7,777",
            "8,888",
            "9,999",
            "94.25%",
        ]
        self.normalized_values = [
            worker.normalize_reprint_numeric_value(v) for v in self.numeric_values
        ]
        self.fillable_bytes = build_fillable_pdf(
            make_standard_fillable_fields(self.numeric_values, total_filled=55),
            page_count=10,
        )
        self.fillable_artifact = {
            "sha256": "sha_fillable_1111",
            "storage_path": "school/2025-26/sha_fillable_1111.pdf",
        }
        self.flat_artifact = {
            "sha256": "sha_flat_2222",
            "storage_path": "school/2025-26/sha_flat_2222.pdf",
        }

    def test_same_data_flattened_reprint_selects_fillable_source(self) -> None:
        # 19 of 20 values present (95% >= 90% threshold), including $- and comma-formatted numbers.
        present = self.numeric_values[:19]
        page_text = (
            "Common Data Set 2025-2026\nGeneral Information and Enrollment\n"
            + " ".join(present)
        )
        flat_bytes = build_flat_pdf([page_text] + ["Section page"] * 9)

        result = worker.compare_fillable_reprint_candidate(
            latest_bytes=flat_bytes,
            latest_artifact=self.flat_artifact,
            candidate_bytes=self.fillable_bytes,
            candidate_artifact=self.fillable_artifact,
        )

        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual(result.source_artifact["sha256"], "sha_fillable_1111")
        self.assertEqual(result.source_bytes, self.fillable_bytes)
        self.assertFalse(result.needs_review)
        self.assertEqual(
            result.selection_note,
            {
                "chosen_sha256": "sha_fillable_1111",
                "candidate_sha256": "sha_fillable_1111",
                "latest_sha256": "sha_flat_2222",
                "match_ratio": 0.95,
                "matched_values": 19,
                "total_values": 20,
                "reason": "flattened_reprint_same_data",
                "needs_review": False,
            },
        )

    def test_values_not_in_text_selects_fillable_and_marks_for_review(self) -> None:
        # Substantial text layer (>= 100 chars), but only 1 of 20 values present (5% <= 10%).
        template_only_text = (
            "Common Data Set 2025-2026\n"
            "Section A. General Information\n"
            "Section B. Enrollment and Persistence\n"
            "Section C. First-Time, First-Year Admission\n"
            "Value present: 58104\n"
        )
        flat_bytes = build_flat_pdf([template_only_text] + ["Template prompt text"] * 9)

        result = worker.compare_fillable_reprint_candidate(
            latest_bytes=flat_bytes,
            latest_artifact=self.flat_artifact,
            candidate_bytes=self.fillable_bytes,
            candidate_artifact=self.fillable_artifact,
        )

        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual(result.source_artifact["sha256"], "sha_fillable_1111")
        self.assertEqual(result.source_bytes, self.fillable_bytes)
        self.assertTrue(result.needs_review)
        self.assertEqual(
            result.selection_note,
            {
                "chosen_sha256": "sha_fillable_1111",
                "candidate_sha256": "sha_fillable_1111",
                "latest_sha256": "sha_flat_2222",
                "match_ratio": 0.05,
                "matched_values": 1,
                "total_values": 20,
                "reason": "print_to_pdf_values_missing_from_text",
                "needs_review": True,
            },
        )

    def test_edition_with_changed_values_keeps_newest_flat_file(self) -> None:
        # 16 of 20 values present (80%, between 10% and 90% -> Barnard case).
        present = self.numeric_values[:16]
        page_text = (
            "Common Data Set 2025-2026 Revised Edition\n"
            + " ".join(present)
            + " 81818 82828 83838 84848"
        )
        flat_bytes = build_flat_pdf([page_text] + ["Section page"] * 9)

        result = worker.compare_fillable_reprint_candidate(
            latest_bytes=flat_bytes,
            latest_artifact=self.flat_artifact,
            candidate_bytes=self.fillable_bytes,
            candidate_artifact=self.fillable_artifact,
        )

        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual(result.source_artifact["sha256"], "sha_flat_2222")
        self.assertEqual(result.source_bytes, flat_bytes)
        self.assertFalse(result.needs_review)
        self.assertEqual(
            result.selection_note,
            {
                "chosen_sha256": "sha_flat_2222",
                "candidate_sha256": "sha_fillable_1111",
                "latest_sha256": "sha_flat_2222",
                "match_ratio": 0.8,
                "matched_values": 16,
                "total_values": 20,
                "reason": "edition_values_changed",
                "needs_review": False,
            },
        )

    def test_no_history_keeps_newest_file_without_selection_note(self) -> None:
        flat_bytes = build_flat_pdf(
            ["Common Data Set 2025-2026\n" + " ".join(self.numeric_values)]
            + ["Page"] * 9
        )
        client = _FakeClient(
            artifacts=[
                {
                    "document_id": "doc-no-history",
                    "kind": "source",
                    **self.flat_artifact,
                    "created_at": "2026-10-01T00:00:00+00:00",
                }
            ],
            blobs={self.flat_artifact["storage_path"]: flat_bytes},
        )

        selection = worker.select_source_for_extraction(
            client, "doc-no-history", self.flat_artifact, flat_bytes,
        )

        self.assertEqual(selection.source_artifact, self.flat_artifact)
        self.assertEqual(selection.source_bytes, flat_bytes)
        self.assertIsNone(selection.selection_note)
        self.assertFalse(selection.needs_review)

    def test_page_count_mismatch_and_low_field_count_skip_candidate(self) -> None:
        # 10-page fillable vs 8-page flat (20% diff > 10% limit) -> None.
        flat_8_pages = build_flat_pdf(
            ["Common Data Set 2025-2026\n" + " ".join(self.numeric_values)]
            + ["Page"] * 7
        )
        mismatch = worker.compare_fillable_reprint_candidate(
            latest_bytes=flat_8_pages,
            latest_artifact=self.flat_artifact,
            candidate_bytes=self.fillable_bytes,
            candidate_artifact=self.fillable_artifact,
        )
        self.assertIsNone(mismatch)

        # 10-page fillable vs 9-page flat (10% diff <= 10% limit) -> accepted.
        flat_9_pages = build_flat_pdf(
            ["Common Data Set 2025-2026\n" + " ".join(self.numeric_values)]
            + ["Page"] * 8
        )
        within_tolerance = worker.compare_fillable_reprint_candidate(
            latest_bytes=flat_9_pages,
            latest_artifact=self.flat_artifact,
            candidate_bytes=self.fillable_bytes,
            candidate_artifact=self.fillable_artifact,
        )
        self.assertIsNotNone(within_tolerance)

        # Fillable candidate with <50 filled fields (49) -> None.
        sparse_fillable = build_fillable_pdf(
            make_standard_fillable_fields(self.numeric_values, total_filled=49),
            page_count=10,
        )
        sparse_result = worker.compare_fillable_reprint_candidate(
            latest_bytes=flat_9_pages,
            latest_artifact=self.flat_artifact,
            candidate_bytes=sparse_fillable,
            candidate_artifact=self.fillable_artifact,
        )
        self.assertIsNone(sparse_result)

    def test_extract_one_routes_print_to_pdf_to_tier2_with_review_and_rearchive_idempotency(self) -> None:
        template_only_text = (
            "Common Data Set 2025-2026\n"
            "Section A. General Information\n"
            "Section B. Enrollment and Persistence\n"
            "Section C. First-Time, First-Year Admission\n"
        )
        flat_bytes = build_flat_pdf([template_only_text] + ["Template prompt text"] * 9)

        # Simulate archiver having re-added the flattened file twice after an
        # earlier fillable source AND a pre-reprint Tier 2 canonical artifact.
        artifacts = [
            {
                "document_id": "doc-miami",
                "kind": "source",
                **self.flat_artifact,
                "created_at": "2026-08-05T00:00:00+00:00",
            },
            {
                "document_id": "doc-miami",
                "kind": "source",
                **self.flat_artifact,
                "created_at": "2026-07-30T00:00:00+00:00",
            },
            {
                "document_id": "doc-miami",
                "kind": "canonical",
                "producer": "tier2_acroform",
                "producer_version": "0.2.0",
                "schema_version": "2025-26",
                "notes": {
                    "source_sha256": "sha_fillable_1111",
                    "stats": {"schema_fields_populated": 758},
                },
                "created_at": "2026-06-17T00:00:00+00:00",
            },
            {
                "document_id": "doc-miami",
                "kind": "source",
                **self.fillable_artifact,
                "created_at": "2026-06-15T00:00:00+00:00",
            },
        ]
        blobs = {
            self.flat_artifact["storage_path"]: flat_bytes,
            self.fillable_artifact["storage_path"]: self.fillable_bytes,
        }
        client = _FakeClient(artifacts=artifacts, blobs=blobs)
        doc = {
            "id": "doc-miami",
            "school_id": "miami",
            "cds_year": "2025-26",
            "detected_year": "2025-26",
            "source_format": "pdf_flat",
        }
        schema_registry = {
            "2025-26": (
                Path("schemas/cds_schema_2025_26.json"),
                {"schema_version": "2025-26", "fields": []},
            )
        }
        fake_tier2_canonical = {
            "producer": "tier2_acroform",
            "producer_version": "0.2.0",
            "stats": {
                "acroform_fields_total": 1089,
                "schema_fields_total": 812,
                "schema_fields_populated": 758,
                "unmapped_acroform_fields": 0,
            },
            "values": {"A.1": {"value": "University of Miami"}},
        }

        with patch.object(worker, "run_tier2", return_value=dict(fake_tier2_canonical)):
            outcome = worker.extract_one(client, doc, schema_registry, dry_run=False)

        self.assertTrue(outcome.refresh_projection)
        self.assertTrue(outcome.needs_review)
        self.assertEqual(outcome.action, "extracted_needs_review (758/812 fields, 0 unmapped)")
        self.assertEqual(doc["source_format"], "pdf_fillable")
        self.assertEqual(len(client.inserted_canonical), 1)
        inserted_notes = client.inserted_canonical[0]["notes"]
        self.assertEqual(inserted_notes["source_sha256"], "sha_fillable_1111")
        self.assertEqual(
            inserted_notes["source_selection"]["reason"],
            "print_to_pdf_values_missing_from_text",
        )
        self.assertTrue(inserted_notes["source_selection"]["needs_review"])
        self.assertTrue(
            any(
                w.get("code") == "flattened_reprint_values_missing_from_text"
                for w in inserted_notes.get("quality_warnings", [])
            )
        )

        # If the archiver re-adds the same flattened PDF again on a later refresh,
        # the worker still selects the fillable source and recognizes that an
        # audited canonical artifact for (sha_fillable_1111, latest=sha_flat_2222)
        # already exists.
        client.artifacts.insert(
            0,
            {
                "document_id": "doc-miami",
                "kind": "source",
                **self.flat_artifact,
                "created_at": "2026-11-10T00:00:00+00:00",
            },
        )
        with patch.object(worker, "run_tier2", return_value=dict(fake_tier2_canonical)):
            second = worker.extract_one(client, doc, schema_registry, dry_run=False)

        self.assertEqual(second.action, "already_extracted")
        self.assertFalse(second.refresh_projection)
        self.assertTrue(second.needs_review)
        self.assertEqual(len(client.inserted_canonical), 1)

    def test_extract_one_changed_edition_keeps_flat_and_avoids_fillable_regression_guard(self) -> None:
        present = self.numeric_values[:16]
        page_text = (
            "Common Data Set 2025-2026\n"
            + " ".join(present)
            + " 81818 82828 83838 84848"
        )
        flat_bytes = build_flat_pdf([page_text] + ["Section page"] * 9)

        # Earlier fillable extraction had 652 fields; new edition has 319 fields in Tier 4.
        artifacts = [
            {
                "document_id": "doc-barnard",
                "kind": "source",
                **self.flat_artifact,
                "created_at": "2026-10-10T00:00:00+00:00",
            },
            {
                "document_id": "doc-barnard",
                "kind": "canonical",
                "producer": "tier2_acroform",
                "producer_version": "0.2.0",
                "schema_version": "2025-26",
                "notes": {
                    "source_sha256": "sha_fillable_1111",
                    "stats": {"schema_fields_populated": 652},
                },
                "created_at": "2026-06-29T00:00:00+00:00",
            },
            {
                "document_id": "doc-barnard",
                "kind": "source",
                **self.fillable_artifact,
                "created_at": "2026-06-29T00:00:00+00:00",
            },
        ]
        blobs = {
            self.flat_artifact["storage_path"]: flat_bytes,
            self.fillable_artifact["storage_path"]: self.fillable_bytes,
        }
        client = _FakeClient(artifacts=artifacts, blobs=blobs)
        doc = {
            "id": "doc-barnard",
            "school_id": "barnard",
            "cds_year": "2025-26",
            "detected_year": "2025-26",
            "source_format": "pdf_flat",
        }
        schema_registry = {
            "2025-26": (
                TOOLS_DIR.parent / "schemas" / "cds_schema_2025_26.json",
                {"schema_version": "2025-26", "fields": []},
            )
        }
        fake_tier4_canonical = {
            "producer": "tier4_docling",
            "producer_version": "0.3.17",
            "stats": {
                "schema_fields_populated": 319,
                "markdown_length": 42000,
                "page_count": 10,
            },
            "markdown": "# CDS",
            "values": {f"F.{i}": {"value": str(i)} for i in range(319)},
        }

        with patch("tier4_extractor.extract_from_bytes", return_value=dict(fake_tier4_canonical)):
            outcome = worker.extract_one(client, doc, schema_registry, dry_run=False)

        self.assertTrue(outcome.refresh_projection)
        self.assertFalse(outcome.needs_review)
        self.assertIn("tier4_extracted (319 fields", outcome.action)
        self.assertEqual(doc["source_format"], "pdf_flat")
        self.assertEqual(len(client.inserted_canonical), 1)
        inserted_notes = client.inserted_canonical[0]["notes"]
        self.assertEqual(inserted_notes["source_sha256"], "sha_flat_2222")
        self.assertEqual(
            inserted_notes["source_selection"],
            {
                "chosen_sha256": "sha_flat_2222",
                "candidate_sha256": "sha_fillable_1111",
                "latest_sha256": "sha_flat_2222",
                "match_ratio": 0.8,
                "matched_values": 16,
                "total_values": 20,
                "reason": "edition_values_changed",
                "needs_review": False,
            },
        )


if __name__ == "__main__":
    unittest.main()
