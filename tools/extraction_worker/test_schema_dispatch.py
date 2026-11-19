import unittest
import json
import sys
import tempfile
from pathlib import Path

TOOLS_ROOT = Path(__file__).resolve().parents[1]
WORKER_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS_ROOT))
sys.path.insert(0, str(WORKER_DIR))

from tier1_extractor.extract import build_cell_map
from tier4_cleaner import SchemaIndex, schema_path_for_year
from worker import (
    artifact_already_extracted,
    canonical_year_for_doc,
    load_schema_registry,
    resolve_schema_for_form,
    resolve_schema_for_year,
    run_tier2,
)
from llm_fallback_worker import _find_eligible_docs


class FakeResult:
    def __init__(self, data):
        self.data = data


class FakeQuery:
    def __init__(self, rows):
        self.rows = rows
        self.filters = []
        self.in_filters = []
        self.ordering = []

    def select(self, *_args, **_kwargs):
        return self

    def eq(self, column, value):
        self.filters.append((column, value))
        return self

    def in_(self, column, values):
        self.in_filters.append((column, set(values)))
        return self

    def order(self, column, desc=False):
        self.ordering.append((column, desc))
        return self

    def limit(self, *_args, **_kwargs):
        return self

    def execute(self):
        rows = self.rows
        for column, value in self.filters:
            rows = [row for row in rows if row.get(column) == value]
        for column, values in self.in_filters:
            rows = [row for row in rows if row.get(column) in values]
        for column, desc in reversed(self.ordering):
            rows = sorted(rows, key=lambda row: str(row.get(column) or ""), reverse=desc)
        return FakeResult(rows)


class FakeClient:
    def __init__(self, rows):
        self.rows = rows

    def table(self, _name):
        return FakeQuery(self.rows)


class MultiTableFakeClient:
    def __init__(self, tables):
        self.tables = tables

    def table(self, name):
        return FakeQuery(self.tables.get(name, []))


class SchemaDispatchTest(unittest.TestCase):
    def test_schema_registry_ignores_overlay_files_without_fields(self):
        with tempfile.TemporaryDirectory() as tmp:
            schema_dir = Path(tmp)
            (schema_dir / "cds_schema_2023_24.core_table_overlay.json").write_text(
                json.dumps({
                    "schema_version": "2023-24",
                    "overlay_version": "core_table_v1",
                    "mappings": [],
                })
            )
            (schema_dir / "cds_schema_2025_26.json").write_text(
                json.dumps({
                    "schema_version": "2025-26",
                    "fields": [
                        {
                            "question_number": "A.001",
                            "question": "First Name:",
                            "section": "General Information",
                            "subsection": "Respondent Information",
                        }
                    ],
                })
            )

            registry = load_schema_registry(schema_dir)
            resolution = resolve_schema_for_year("2023-24", registry)

        self.assertNotIn("2023-24", registry)
        self.assertEqual(resolution.schema_version, "2025-26")
        self.assertTrue(resolution.fallback_used)
        self.assertEqual(resolution.fallback_reason, "no_schema_for_2023-24")

    def test_resolve_schema_uses_matching_year(self):
        registry = load_schema_registry()
        resolution = resolve_schema_for_year("2024-25", registry)

        self.assertEqual(resolution.schema_version, "2024-25")
        self.assertFalse(resolution.fallback_used)
        self.assertEqual(resolution.schema["schema_version"], "2024-25")

    def test_resolve_schema_uses_2023_canonical_schema(self):
        registry = load_schema_registry()
        resolution = resolve_schema_for_year("2023-24", registry)

        self.assertEqual(resolution.schema_version, "2023-24")
        self.assertFalse(resolution.fallback_used)
        self.assertEqual(resolution.schema["schema_version"], "2023-24")

    def test_resolve_schema_uses_2026_27_schema(self):
        registry = load_schema_registry()
        resolution = resolve_schema_for_year("2026-27", registry)

        self.assertEqual(resolution.schema_version, "2026-27")
        self.assertFalse(resolution.fallback_used)
        self.assertEqual(resolution.schema["schema_version"], "2026-27")

    def test_a_year_newer_than_every_schema_falls_back_to_the_newest(self):
        registry = load_schema_registry()
        newest = max(registry)
        resolution = resolve_schema_for_year("2031-32", registry)

        self.assertEqual(resolution.schema_version, newest)
        self.assertGreaterEqual(newest, "2026-27")
        self.assertTrue(resolution.fallback_used)
        self.assertEqual(resolution.fallback_reason, "no_schema_for_2031-32")

    def test_undated_and_older_documents_keep_the_2025_26_schema(self):
        # These cannot be on a newer form, and their stored results are keyed
        # by the 2025-26 numbering; a new template year must not move them.
        registry = load_schema_registry()
        for year, reason in (
            (None, "missing_canonical_year"),
            ("unknown", "no_schema_for_unknown"),
            ("2019-20", "no_schema_for_2019-20"),
            ("2022-23", "no_schema_for_2022-23"),
        ):
            with self.subTest(year=year):
                resolution = resolve_schema_for_year(year, registry)
                self.assertEqual(resolution.schema_version, "2025-26")
                self.assertTrue(resolution.fallback_used)
                self.assertEqual(resolution.fallback_reason, reason)

    def test_fallback_without_the_baseline_schema_uses_the_newest(self):
        registry = {
            version: entry for version, entry in load_schema_registry().items()
            if version != "2025-26"
        }
        resolution = resolve_schema_for_year("2019-20", registry)

        self.assertEqual(resolution.schema_version, max(registry))
        self.assertTrue(resolution.fallback_used)

    def test_a_2026_27_file_built_on_the_2025_26_form_uses_the_2025_26_schema(self):
        # The blank templates stand in for filled copies: a filled copy keeps
        # the form's field names (PDF) and its hidden lookup columns (XLSX).
        templates = TOOLS_ROOT.parent / "schemas" / "templates"
        registry = load_schema_registry()
        dated_2026 = resolve_schema_for_year("2026-27", registry)
        for source_format, suffix in (("pdf_fillable", "pdf"), ("xlsx", "xlsx")):
            with self.subTest(source_format=source_format):
                old_form = (templates / f"cds_2025-26_template.{suffix}").read_bytes()
                new_form = (templates / f"cds_2026-27_template.{suffix}").read_bytes()

                on_old = resolve_schema_for_form(dated_2026, registry, source_format, old_form)
                self.assertEqual(on_old.schema_version, "2025-26")
                self.assertEqual(on_old.schema["schema_version"], "2025-26")
                self.assertEqual(on_old.canonical_year, "2026-27")
                self.assertTrue(on_old.fallback_used)
                self.assertEqual(on_old.fallback_reason, "form_is_2025-26")
                self.assertEqual(on_old.schema_path.name, "cds_schema_2025_26.json")

                self.assertIs(resolve_schema_for_form(dated_2026, registry, source_format, new_form), dated_2026)

    def test_the_2026_27_fillable_form_maps_every_form_name_under_its_own_schema(self):
        templates = TOOLS_ROOT.parent / "schemas" / "templates"
        registry = load_schema_registry()
        form = (templates / "cds_2026-27_template.pdf").read_bytes()

        own = run_tier2(form, registry["2026-27"][1])
        self.assertEqual(own["unmapped_fields"], [])
        self.assertEqual(own["schema_version"], "2026-27")
        # The blank form prints 0 in both total rows; each lands on its own field.
        self.assertEqual((own["values"]["C.116"]["value"], own["values"]["C.1T01"]["value"]), ("0", "0"))

        # Read with the 2025-26 schema, the residency totals have nowhere to go.
        older = run_tier2(form, registry["2025-26"][1])
        self.assertEqual(
            sorted(f["pdf_tag"] for f in older["unmapped_fields"]),
            ["AP_ADMT_1ST_RES_N", "AP_RECD_1ST_RES_N", "EN_TOT_1ST_RES_N"],
        )

    def test_the_form_check_leaves_everything_else_alone(self):
        templates = TOOLS_ROOT.parent / "schemas" / "templates"
        registry = load_schema_registry()
        old_pdf = (templates / "cds_2025-26_template.pdf").read_bytes()
        dated_2026 = resolve_schema_for_year("2026-27", registry)
        # A flattened PDF is read as text; the two years share their numbering.
        for source_format in ("pdf_flat", "pdf_scanned", "html", "docx", None):
            self.assertIs(resolve_schema_for_form(dated_2026, registry, source_format, old_pdf), dated_2026)
        # A file it cannot judge keeps the schema it was given.
        for junk in (b"", b"not a pdf", b"%PDF-1.4\n%%EOF"):
            self.assertIs(resolve_schema_for_form(dated_2026, registry, "pdf_fillable", junk), dated_2026)
            self.assertIs(resolve_schema_for_form(dated_2026, registry, "xlsx", junk), dated_2026)
        # Years with no earlier same-numbering form are never changed.
        for year in ("2025-26", "2024-25", "2023-24", None):
            resolution = resolve_schema_for_year(year, registry)
            self.assertIs(resolve_schema_for_form(resolution, registry, "pdf_fillable", old_pdf), resolution)

    def test_the_cleaner_picks_the_same_schema_file_as_the_worker(self):
        # The LLM fallback worker picks its schema through schema_path_for_year
        # and skips a document whose base extraction used a different one.
        registry = load_schema_registry()
        for year in ("2026-27", "2025-26", "2024-25", "2023-24", "2031-32", "2022-23", "2019-20", "unknown", None):
            with self.subTest(year=year):
                self.assertEqual(schema_path_for_year(year), resolve_schema_for_year(year, registry).schema_path)

    def test_canonical_year_prefers_detected_year(self):
        self.assertEqual(
            canonical_year_for_doc({"detected_year": "2024-25", "cds_year": "2025-26"}),
            "2024-25",
        )

    def test_schema_index_loads_requested_year(self):
        schema = SchemaIndex(schema_path_for_year("2024-25"))

        self.assertEqual(schema.schema_version, "2024-25")
        hit = schema.lookup(
            section="First-Time, First-Year Admission",
            subsection="First-time, first-year Profile",
            question_norm="sat math 50th percentile",
            category="Test Scores",
        )
        self.assertEqual(hit, "C.912")

    def test_tier1_cell_maps_are_year_specific(self):
        map_2024 = build_cell_map(Path("schemas/templates/cds_2024-25_template.xlsx"))
        map_2025 = build_cell_map(Path("schemas/templates/cds_2025-26_template.xlsx"))

        self.assertEqual(map_2024["C.912"], ("CDS-C", "C284"))
        self.assertEqual(map_2025["C.912"], ("CDS-C", "D181"))

    def test_idempotency_checks_schema_version(self):
        client = FakeClient([
            {
                "document_id": "doc1",
                "kind": "canonical",
                "producer": "tier2_acroform",
                "producer_version": "0.2.0",
                "schema_version": "2025-26",
            }
        ])

        self.assertTrue(
            artifact_already_extracted(
                client, "doc1", "tier2_acroform", "0.2.0", "2025-26",
            )
        )

    def test_llm_fallback_eligibility_prefers_matching_schema_artifact(self):
        client = MultiTableFakeClient({
            "cds_documents": [
                {
                    "id": "doc1",
                    "school_id": "example",
                    "cds_year": "2024-25",
                    "detected_year": None,
                    "source_sha256": "abc",
                    "data_quality_flag": None,
                }
            ],
            "cds_artifacts": [
                {
                    "id": "new-wrong-schema",
                    "document_id": "doc1",
                    "kind": "canonical",
                    "producer": "tier4_docling",
                    "producer_version": "0.3.0",
                    "schema_version": "2025-26",
                    "created_at": "2026-01-03T00:00:00Z",
                    "notes": {"stats": {"schema_fields_populated": 300}},
                },
                {
                    "id": "old-matching-schema",
                    "document_id": "doc1",
                    "kind": "canonical",
                    "producer": "tier4_docling",
                    "producer_version": "0.3.0",
                    "schema_version": "2024-25",
                    "created_at": "2026-01-01T00:00:00Z",
                    "notes": {"stats": {"schema_fields_populated": 300}},
                },
            ],
        })

        eligible = _find_eligible_docs(
            client,
            school_filter=None,
            year_filter=None,
            limit=None,
            low_coverage_threshold=200,
        )

        self.assertEqual(len(eligible), 1)
        self.assertEqual(eligible[0]["artifact"]["id"], "old-matching-schema")
        self.assertFalse(
            artifact_already_extracted(
                client, "doc1", "tier2_acroform", "0.2.0", "2024-25",
            )
        )


if __name__ == "__main__":
    unittest.main()
