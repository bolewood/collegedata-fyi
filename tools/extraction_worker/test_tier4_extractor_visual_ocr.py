from __future__ import annotations

import subprocess
import unittest
from pathlib import Path
from unittest.mock import patch

import tier4_extractor


class Tier4ExtractorVisualOcrTest(unittest.TestCase):
    def test_scanned_fallback_pages_when_text_layer_has_no_candidates(self):
        calls: list[list[str]] = []

        def fake_run(args, **kwargs):
            calls.append(list(args))
            if args[0] == "pdftoppm":
                Path(f"{args[-1]}-1.png").write_text("")
                return subprocess.CompletedProcess(args, 0)
            return subprocess.CompletedProcess(args, 0, stdout="Submitting SAT Scores 11 1031")

        with (
            patch("tier4_extractor.shutil.which", return_value="/usr/bin/tool"),
            patch("tier4_extractor._visual_ocr_candidate_pages", return_value=[]),
            patch("tier4_extractor.subprocess.run", side_effect=fake_run),
        ):
            text, pages = tier4_extractor._extract_visual_ocr_text(
                Path("fake.pdf"),
                fallback_page_count=3,
            )

        self.assertEqual(pages, [1, 2, 3])
        self.assertEqual(text.count("Submitting SAT Scores"), 3)
        self.assertEqual(sum(1 for call in calls if call[0] == "pdftoppm"), 3)
        self.assertEqual(sum(1 for call in calls if call[0] == "tesseract"), 3)


if __name__ == "__main__":
    unittest.main()
