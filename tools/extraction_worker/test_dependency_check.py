from __future__ import annotations

import unittest

from dependency_check import LOCK_PATH, environment_problems, parse_lock


class DependencyCheckTest(unittest.TestCase):
    LOCK = (
        "docling==2.148.0\n"
        "    # via -r requirements.txt\n"
        "Docling_Core==2.106.0\n"
        "pywin32==311 ; sys_platform == 'win32'\n"
        "torch==2.15.0\n"
    )

    def test_parse_lock_normalizes_names_and_skips_comments(self):
        self.assertEqual(
            parse_lock(self.LOCK),
            {"docling": "2.148.0", "docling-core": "2.106.0", "pywin32": "311", "torch": "2.15.0"},
        )

    def test_matching_environment_has_no_problems(self):
        installed = {"docling": "2.148.0", "docling-core": "2.106.0", "torch": "2.15.0", "extra": "1"}
        self.assertEqual(environment_problems(parse_lock(self.LOCK), installed, (3, 12), "3.12"), [])

    def test_stale_venv_is_reported(self):
        # The April venv: Python 3.9, Docling 2.69.1.
        installed = {"docling": "2.69.1", "docling-core": "2.60.1", "torch": "2.15.0"}
        problems = environment_problems(parse_lock(self.LOCK), installed, (3, 9), "3.12")
        self.assertEqual(problems, [
            "python 3.9 (expected 3.12)",
            "docling 2.69.1 (lock 2.148.0)",
            "docling-core 2.60.1 (lock 2.106.0)",
        ])

    def test_checked_in_lock_pins_docling_like_requirements(self):
        pins = parse_lock(LOCK_PATH.read_text())
        requirements = parse_lock((LOCK_PATH.parent / "requirements.txt").read_text())
        for name in ("docling", "docling-core", "docling-parse", "docling-ibm-models"):
            self.assertEqual(pins[name], requirements[name], name)


if __name__ == "__main__":
    unittest.main()
