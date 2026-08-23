"""Tests for landing-hint Supabase credential resolution."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tools.finder.promote_landing_hints import supabase_credentials


class SupabaseCredentialsTests(unittest.TestCase):
    def test_process_env_works_without_dotenv_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            missing = Path(tmp) / ".env"
            with mock.patch.dict(
                "os.environ",
                {
                    "SUPABASE_URL": "https://example.supabase.co",
                    "SUPABASE_SERVICE_ROLE_KEY": "service-role",
                },
                clear=False,
            ):
                creds = supabase_credentials(missing)
        self.assertEqual(creds["SUPABASE_URL"], "https://example.supabase.co")
        self.assertEqual(creds["SUPABASE_SERVICE_ROLE_KEY"], "service-role")

    def test_process_env_wins_over_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            env_path = Path(tmp) / ".env"
            env_path.write_text(
                "SUPABASE_URL=https://file.example\n"
                "SUPABASE_SERVICE_ROLE_KEY=file-key\n"
            )
            with mock.patch.dict(
                "os.environ",
                {
                    "SUPABASE_URL": "https://env.example",
                    "SUPABASE_SERVICE_ROLE_KEY": "env-key",
                },
                clear=False,
            ):
                creds = supabase_credentials(env_path)
        self.assertEqual(creds["SUPABASE_URL"], "https://env.example")


if __name__ == "__main__":
    unittest.main()
