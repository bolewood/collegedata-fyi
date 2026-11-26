"""Runtime calls default to the project origin, never the custom API host.

Each test runs a runtime entry point with no env (default is PROJECT_ORIGIN)
and with SUPABASE_URL set (env wins). Putting the old literal back as a
default makes the "no env" test fail.
"""

import argparse
import importlib
import importlib.util
import os
import sys
import unittest
from unittest import mock

from tools.common.site import PROJECT_ORIGIN, runtime_api_origin

ENV_URL = "http://localhost:54321"


class Stop(Exception):
    pass


def parser_api_url_default(module_name: str, env: dict[str, str]) -> str:
    """The --api-url default a module's main() builds, under a clean env."""
    module = importlib.import_module(module_name)
    seen: dict[str, str] = {}

    def fake_parse_args(self, *args, **kwargs):
        seen["default"] = self._option_string_actions["--api-url"].default
        raise Stop

    with mock.patch.dict(os.environ, env, clear=True), mock.patch.object(
        argparse.ArgumentParser, "parse_args", fake_parse_args
    ):
        try:
            module.main()
        except Stop:
            pass
    return seen["default"]


class RuntimeApiOriginTests(unittest.TestCase):
    def test_no_env_is_the_project_origin(self):
        self.assertEqual(runtime_api_origin({}), PROJECT_ORIGIN)

    def test_supabase_url_wins_then_public_url_then_default(self):
        self.assertEqual(runtime_api_origin({"SUPABASE_URL": "https://a/", "NEXT_PUBLIC_SUPABASE_URL": "https://b"}), "https://a")
        self.assertEqual(runtime_api_origin({"NEXT_PUBLIC_SUPABASE_URL": "https://b"}), "https://b")
        self.assertEqual(runtime_api_origin({"SUPABASE_URL": "  "}), PROJECT_ORIGIN)
        self.assertEqual(runtime_api_origin({"SUPABASE_URL": " ", "NEXT_PUBLIC_SUPABASE_URL": "https://b"}), "https://b")

    def test_reads_the_process_env_when_not_given_one(self):
        with mock.patch.dict(os.environ, {"SUPABASE_URL": ENV_URL}, clear=True):
            self.assertEqual(runtime_api_origin(), ENV_URL)


class ApiUrlFlagDefaultTests(unittest.TestCase):
    MODULES = (
        "tools.finder.stuck_pdf_seeds",
        "tools.finder.seed_age",
        "tools.ops.discovery_renewal",
        "tools.ops.fetch_failures",
        "tools.ops.same_year_duplicates",
    )

    def test_default_is_the_project_origin(self):
        for name in self.MODULES:
            with self.subTest(module=name):
                self.assertEqual(parser_api_url_default(name, {}), PROJECT_ORIGIN)

    def test_env_wins(self):
        for name in self.MODULES:
            with self.subTest(module=name):
                self.assertEqual(parser_api_url_default(name, {"SUPABASE_URL": ENV_URL}), ENV_URL)

    def test_cds_api_url_still_overrides_where_it_existed(self):
        for name in ("tools.ops.discovery_renewal", "tools.ops.fetch_failures", "tools.ops.same_year_duplicates"):
            with self.subTest(module=name):
                env = {"CDS_API_URL": "https://override", "SUPABASE_URL": ENV_URL}
                self.assertEqual(parser_api_url_default(name, env), "https://override")


class OtherRuntimeDefaultTests(unittest.TestCase):
    def test_report_m0_directory_url(self):
        if importlib.util.find_spec("openpyxl") is None:
            self.skipTest("openpyxl not installed")
        m0 = importlib.import_module("tools.fsa.report_m0")
        with mock.patch.dict(os.environ, {}, clear=True):
            self.assertEqual(m0.directory_url(), f"{PROJECT_ORIGIN}/rest/v1/institution_directory")
        with mock.patch.dict(os.environ, {"SUPABASE_URL": ENV_URL}, clear=True):
            self.assertEqual(m0.directory_url(), f"{ENV_URL}/rest/v1/institution_directory")

    def test_card_coverage_api_base(self):
        name = "tools.discovery.cds_card_coverage"
        for env, want in (({}, PROJECT_ORIGIN), ({"SUPABASE_URL": ENV_URL}, ENV_URL)):
            with self.subTest(env=env), mock.patch.dict(os.environ, env, clear=True):
                sys.modules.pop(name, None)
                try:
                    module = importlib.import_module(name)
                    self.assertEqual(module.API, f"{want}/rest/v1")
                finally:
                    sys.modules.pop(name, None)

    def test_prd019_spike_requests_the_project_origin(self):
        module = importlib.import_module("tools.change_intelligence.prd019_spike_admissions_reporting")
        for env, want in (({}, PROJECT_ORIGIN), ({"SUPABASE_URL": ENV_URL}, ENV_URL)):
            env = {**env, "SUPABASE_ANON_KEY": "k"}
            seen = []

            def fake_urlopen(req, timeout=None):
                seen.append(req.full_url)
                raise Stop

            with self.subTest(env=env), mock.patch.object(module, "load_env", return_value=env), mock.patch.object(
                module, "urlopen", fake_urlopen
            ):
                with self.assertRaises(Stop):
                    module.fetch_rows()
                self.assertTrue(seen[0].startswith(f"{want}/rest/v1/"), seen[0])

    def _builder_url(self, module_name: str, patched: str, env: dict[str, str]) -> str:
        """URL a recipe builder's main() hands to its fetch step."""
        module = importlib.import_module(module_name)
        seen = []

        def fake(*args, **kwargs):
            seen.append(args[0])
            raise ValueError("stop")

        env = {**env, "SUPABASE_ANON_KEY": "k"}
        with mock.patch.dict(os.environ, env, clear=True), mock.patch.object(
            sys, "argv", ["builder"]
        ), mock.patch.object(module, "load_env", lambda *a, **k: None), mock.patch.object(
            module, "validated_unique_school_claim_slug_map", lambda **k: {}
        ), mock.patch.object(
            module, "validated_canonical_alias_slug_map", lambda **k: {}
        ), mock.patch.object(module, patched, fake):
            module.main()
        return seen[0]

    def test_recipe_builders_fetch_from_the_project_origin(self):
        cases = (
            ("tools.scorecard.build_alignment_gap_recipe", "build_artifact"),
            ("tools.scorecard.build_waitlist_recipe", "fetch_inputs"),
        )
        for name, patched in cases:
            for env, want in (({}, PROJECT_ORIGIN), ({"SUPABASE_URL": ENV_URL}, ENV_URL)):
                with self.subTest(module=name, env=env):
                    self.assertEqual(self._builder_url(name, patched, env), want)


if __name__ == "__main__":
    unittest.main()
