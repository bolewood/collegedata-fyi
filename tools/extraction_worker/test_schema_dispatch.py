import unittest
import sys
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
    resolve_schema_for_year,
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
    def test_resolve_schema_uses_matching_year(self):
        registry = load_schema_registry()
        resolution = resolve_schema_for_year("2024-25", registry)

        self.assertEqual(resolution.schema_version, "2024-25")
        self.assertFalse(resolution.fallback_used)
        self.assertEqual(resolution.schema["schema_version"], "2024-25")

    def test_resolve_schema_falls_back_to_latest(self):
        registry = load_schema_registry()
        resolution = resolve_schema_for_year("2026-27", registry)

        self.assertEqual(resolution.schema_version, "2025-26")
        self.assertTrue(resolution.fallback_used)
        self.assertEqual(resolution.fallback_reason, "no_schema_for_2026-27")

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
