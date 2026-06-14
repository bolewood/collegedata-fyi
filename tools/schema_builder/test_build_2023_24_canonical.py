import json
import unittest
from pathlib import Path

from pypdf import PdfReader

from tools.schema_builder.build_2023_24_canonical import synthesize_schema


ROOT = Path(__file__).resolve().parents[2]


class Build202324CanonicalTest(unittest.TestCase):
    def test_synthesized_schema_uses_2023_nonbinary_tags(self):
        base = json.loads((ROOT / "schemas/cds_schema_2024_25.json").read_text())
        pdf_path = ROOT / "schemas/templates/cds_2023-24_template.pdf"
        pdf_tags = set(PdfReader(str(pdf_path)).get_fields())

        schema = synthesize_schema(
            base,
            pdf_tags,
            pdf_source_name=pdf_path.name,
        )
        by_qnum = {field["question_number"]: field for field in schema["fields"]}

        self.assertEqual(schema["schema_version"], "2023-24")
        self.assertEqual(schema["field_count"], len(schema["fields"]))
        self.assertEqual(schema["synthesis"]["unknown_gender_fields_dropped"], 30)
        self.assertEqual(
            sum(1 for field in schema["fields"] if field.get("gender") == "Unknown"),
            0,
        )

        self.assertEqual(by_qnum["B.103"]["pdf_tag"], "CDS_EN_FRSH_FT_NON_BINARY_N")
        self.assertNotIn("B.104", by_qnum)
        self.assertEqual(by_qnum["C.103"]["pdf_tag"], "AP_RECD_1ST_NON_BINARY_N")
        self.assertNotIn("C.104", by_qnum)
        self.assertEqual(by_qnum["C.113"]["pdf_tag"], "EN_TOT_1ST_FT_NON_BINARY_N")
        self.assertEqual(by_qnum["C.114"]["pdf_tag"], "EN_TOT_1ST_PT_NON_BINARY_N")
        self.assertNotIn("C.115", by_qnum)
        self.assertNotIn("C.116", by_qnum)
        self.assertEqual(by_qnum["D.203"]["pdf_tag"], "AP_TFER_NON_BINARY_N")
        self.assertNotIn("D.204", by_qnum)
        self.assertEqual(by_qnum["B.193"]["pdf_tag"], "EN_TOT _UG_N")

        missing_tags = [
            field["pdf_tag"]
            for field in schema["fields"]
            if field.get("pdf_tag") and field["pdf_tag"] not in pdf_tags
        ]
        self.assertEqual(missing_tags, [])


if __name__ == "__main__":
    unittest.main()
