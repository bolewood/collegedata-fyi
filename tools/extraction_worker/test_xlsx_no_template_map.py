"""XLSX routing when the schema year has no template cell map."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

TOOLS_ROOT = Path(__file__).resolve().parents[1]
WORKER_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS_ROOT))
sys.path.insert(0, str(WORKER_DIR))

from worker import (  # noqa: E402
    ExtractionOutcome,
    SchemaResolution,
    extract_one,
)


class XlsxNoTemplateMapRoutingTests(unittest.TestCase):
    def test_xlsx_without_template_map_still_calls_tier1(self) -> None:
        doc = {
            "id": "doc-2023-24-xlsx",
            "school_id": "example-university",
            "cds_year": "2023-24",
            "detected_year": None,
            "source_format": "xlsx",
        }
        resolution = SchemaResolution(
            schema={"schema_version": "2023-24", "fields": []},
            schema_version="2023-24",
            canonical_year="2023-24",
            fallback_used=False,
            fallback_reason=None,
            schema_path=Path("schemas/cds_schema_2023_24.json"),
        )
        tier1_outcome = ExtractionOutcome(
            action="tier1_extracted (120 fields)",
            refresh_projection=True,
        )

        with (
            patch(
                "worker.fetch_latest_source_artifact",
                return_value={"storage_path": "sources/example.xlsx", "id": "art-1"},
            ),
            patch("worker.download_source", return_value=b"PK\x03\x04fake-xlsx"),
            patch("worker.detect_year_from_bytes", return_value="2023-24"),
            patch("worker.write_detected_year"),
            patch("worker.canonical_year_for_doc", return_value="2023-24"),
            patch("worker.resolve_schema_for_year", return_value=resolution),
            patch("worker.choose_source_format", return_value=("xlsx", False)),
            patch("worker.write_source_metadata"),
            patch("worker._run_tier1", return_value=tier1_outcome) as run_tier1,
            patch("worker.mark_extraction_status") as mark_status,
        ):
            outcome = extract_one(
                client=MagicMock(),
                doc=doc,
                schema_registry={},
                dry_run=False,
                cell_maps={},  # 2023-24 has no template map
            )

        self.assertEqual(outcome.action, "tier1_extracted (120 fields)")
        run_tier1.assert_called_once()
        cell_map_arg = run_tier1.call_args.args[6]
        self.assertEqual(cell_map_arg, {})
        mark_status.assert_not_called()

    def test_xlsx_with_template_map_passes_it_through(self) -> None:
        doc = {
            "id": "doc-2025-26-xlsx",
            "school_id": "example-university",
            "cds_year": "2025-26",
            "detected_year": None,
            "source_format": "xlsx",
        }
        resolution = SchemaResolution(
            schema={"schema_version": "2025-26", "fields": []},
            schema_version="2025-26",
            canonical_year="2025-26",
            fallback_used=False,
            fallback_reason=None,
            schema_path=Path("schemas/cds_schema_2025_26.json"),
        )
        template_map = {"C.101": ("CDS-C", "C10")}
        tier1_outcome = ExtractionOutcome(
            action="tier1_extracted (500 fields)",
            refresh_projection=True,
        )

        with (
            patch(
                "worker.fetch_latest_source_artifact",
                return_value={"storage_path": "sources/example.xlsx", "id": "art-1"},
            ),
            patch("worker.download_source", return_value=b"PK\x03\x04fake-xlsx"),
            patch("worker.detect_year_from_bytes", return_value="2025-26"),
            patch("worker.write_detected_year"),
            patch("worker.canonical_year_for_doc", return_value="2025-26"),
            patch("worker.resolve_schema_for_year", return_value=resolution),
            patch("worker.choose_source_format", return_value=("xlsx", False)),
            patch("worker.write_source_metadata"),
            patch("worker._run_tier1", return_value=tier1_outcome) as run_tier1,
        ):
            outcome = extract_one(
                client=MagicMock(),
                doc=doc,
                schema_registry={},
                dry_run=False,
                cell_maps={"2025-26": template_map},
            )

        self.assertEqual(outcome.action, "tier1_extracted (500 fields)")
        self.assertEqual(run_tier1.call_args.args[6], template_map)


if __name__ == "__main__":
    unittest.main()
