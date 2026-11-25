from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
import unittest.mock
from pathlib import Path

from tools.ops import notify_discord
from tools.ops import renewal_alarm as ra
from tools.ops.discovery_renewal import lead_check

SUMMARY = {
    "current_year": "2025-26",
    "renewed": 364,
    "prev_schools": 479,
    "renewal_pct": 76.0,
    "floor_pct": 82.5,
    "below_floor": True,
    "next_year": "2026-27",
    "next_renewed": 4,
    "next_prev_schools": 417,
    "next_renewal_pct": 1.0,
    "next_floor_pct": None,
    "next_below_floor": None,
    "two_year_renewed": 377,
    "two_year_prev_schools": 536,
    "two_year_renewal_pct": 70.3,
    "two_year_floor_pct": 74.5,
    "two_year_below_floor": True,
}
HEALTHY = {**SUMMARY, "renewed": 410, "renewal_pct": 85.6, "below_floor": False,
           "two_year_renewed": 450, "two_year_renewal_pct": 84.0, "two_year_below_floor": False}
NEXT_ONLY = {
    **HEALTHY, "renewal_pct": 90.0,
    "next_renewed": 40, "next_prev_schools": 417, "next_renewal_pct": 9.6,
    "next_floor_pct": 20.0, "next_below_floor": True,
}
TWO_YEAR_ONLY = {**HEALTHY, "two_year_renewed": 380, "two_year_renewal_pct": 70.9,
                 "two_year_below_floor": True}
# The September switch: the same kind of breach, a different year.
SWITCHED = {**SUMMARY, "current_year": "2026-27", "next_year": "2027-28"}


class FakeGh:
    """Records gh calls; `open_issues` is what `gh issue list` returns."""

    def __init__(self, open_issues: list[dict] | None = None, fail_on: str | None = None) -> None:
        self.open_issues = open_issues or []
        self.fail_on = fail_on
        self.calls: list[list[str]] = []
        self.bodies: list[str] = []

    def __call__(self, args: list[str]) -> subprocess.CompletedProcess[str]:
        self.calls.append(args)
        if "--body-file" in args:
            self.bodies.append(Path(args[args.index("--body-file") + 1]).read_text())
        if self.fail_on and (args[:2] == self.fail_on.split() or (
                self.fail_on == "issue list" and args[0] == "api")):
            return subprocess.CompletedProcess(args, 1, "", "boom")
        if args[0] == "api":
            # REST shape: html_url, and pull requests come back too.
            rest = [{**i, "html_url": i.get("url"), "body": i.get("body", "")} for i in self.open_issues]
            rest.append({"number": 1, "title": "a PR", "pull_request": {}, "html_url": "p"})
            return subprocess.CompletedProcess(args, 0, json.dumps(rest), "")
        if args[:2] == ["issue", "create"]:
            return subprocess.CompletedProcess(args, 0, "https://github.com/o/r/issues/777\n", "")
        return subprocess.CompletedProcess(args, 0, "", "")

    def verbs(self) -> list[str]:
        return ["issue list" if c[0] == "api" else " ".join(c[:2]) for c in self.calls]


class Discord:
    def __init__(self, fail: bool = False) -> None:
        self.posts = []
        self.fail = fail

    def __call__(self, **payload) -> bool:
        self.posts.append(payload)
        if self.fail:
            raise notify_discord.DiscordPostError("HTTP 500")
        return True


def below_of(summary) -> bool:
    return lead_check(summary) is not None


below_floor_of = below_of


def run(summary, below, gh, discord=None, *, test_mode=False, dry_run=False):
    return ra.act(
        summary=summary, below_floor=below, report="REPORT BODY", repo="o/r",
        test_mode=test_mode, dry_run=dry_run, assignee="santhonys", runner=gh,
        discord=discord or Discord(),
    )


class DecisionTests(unittest.TestCase):
    def test_decide_table(self) -> None:
        self.assertEqual(ra.decide(True, None), "create")
        self.assertEqual(ra.decide(True, 5), "update")
        self.assertEqual(ra.decide(False, 5), "close")
        self.assertEqual(ra.decide(False, None), "none")


class ActTests(unittest.TestCase):
    def test_below_floor_without_an_issue_creates_one_and_posts(self) -> None:
        gh, discord = FakeGh(), Discord()
        outcome = run(SUMMARY, True, gh, discord)
        self.assertEqual((outcome["action"], outcome["issue"]), ("create", 777))
        create = next(c for c in gh.calls if c[:2] == ["issue", "create"])
        self.assertEqual(create[create.index("--label") + 1], "alarm:discovery-renewal")
        self.assertEqual(create[create.index("--assignee") + 1], "santhonys")
        gh2 = FakeGh()
        run(SUMMARY, True, gh2, test_mode=True)
        test_create = next(c for c in gh2.calls if c[:2] == ["issue", "create"])
        self.assertNotIn("--assignee", test_create)  # no notification spam from tests
        self.assertEqual(
            create[create.index("--title") + 1],
            "Discovery is behind: 76% of schools with 2024-25 have 2025-26 (floor 82%)",
        )
        self.assertEqual(len(gh.bodies), 1)
        self.assertTrue(gh.bodies[0].startswith("REPORT BODY"))
        self.assertIn("label create", gh.verbs())
        self.assertEqual(len(discord.posts), 1)
        self.assertFalse(discord.posts[0]["recovered"])

    def test_issue_is_found_by_label_not_by_title(self) -> None:
        gh = FakeGh()
        run(SUMMARY, True, gh)
        listing = next(c for c in gh.calls if c[0] == "api")
        self.assertIn("labels=alarm:discovery-renewal", listing)
        self.assertIn("repos/o/r/issues", listing)
        # Not `gh issue list --label`, which uses the lagging search API.
        self.assertFalse(any(c[:2] == ["issue", "list"] for c in gh.calls))

    def test_standing_issue_gets_its_body_replaced_and_no_comment_or_post(self) -> None:
        gh, discord = FakeGh([{"number": 12, "title": "x", "url": "u"}]), Discord()
        outcome = run(SUMMARY, True, gh, discord)
        self.assertEqual((outcome["action"], outcome["issue"]), ("update", 12))
        self.assertEqual(gh.verbs(), ["issue list", "issue edit"])
        self.assertEqual(len(gh.bodies), 1)
        self.assertTrue(gh.bodies[0].startswith("REPORT BODY"))
        self.assertEqual(discord.posts, [])
        self.assertFalse(any("--comment" in c or c[:2] == ["issue", "comment"] for c in gh.calls))

    def test_recovery_closes_with_one_comment_and_posts_green(self) -> None:
        gh, discord = FakeGh([{"number": 12, "title": "x", "url": "https://u/12"}]), Discord()
        outcome = run(HEALTHY, False, gh, discord)
        self.assertEqual((outcome["action"], outcome["issue"]), ("close", None))
        close = next(c for c in gh.calls if c[:2] == ["issue", "close"])
        comment = close[close.index("--comment") + 1]
        self.assertIn("410 of 479 (85.6%)", comment)
        self.assertEqual(len(discord.posts), 1)
        self.assertTrue(discord.posts[0]["recovered"])

    def test_above_floor_without_an_issue_does_nothing(self) -> None:
        gh, discord = FakeGh(), Discord()
        outcome = run(HEALTHY, False, gh, discord)
        self.assertEqual((outcome["action"], outcome["issue"]), ("none", None))
        self.assertEqual(gh.verbs(), ["issue list"])
        self.assertEqual(discord.posts, [])

    def test_two_year_breach_leads_with_the_two_year_check(self) -> None:
        self.assertEqual(
            ra.issue_title(TWO_YEAR_ONLY, test_mode=False),
            "Discovery is behind: 71% of schools with 2024-25 or 2023-24 have 2025-26 (floor 74%)",
        )
        gh, discord = FakeGh(), Discord()
        run(TWO_YEAR_ONLY, True, gh, discord)
        self.assertIn("alarm-scope: year:2025-26", gh.bodies[0])
        self.assertEqual(dict(discord.posts[0]["fields"])["Check"], "two-year")

    def test_standing_issue_title_follows_the_current_numbers(self) -> None:
        body = ra.scope_marker(("year", "2025-26"))
        gh = FakeGh([{"number": 12, "title": "old", "url": "u", "body": body}])
        run({**SUMMARY, "renewal_pct": 78.0, "renewed": 374}, True, gh)
        edit = next(c for c in gh.calls if c[:2] == ["issue", "edit"])
        self.assertIn("78% of schools with 2024-25", edit[edit.index("--title") + 1])

    def test_scope_change_supersedes_the_old_issue(self) -> None:
        old_body = ra.scope_marker(("year", "2025-26"))
        gh, discord = FakeGh([{"number": 12, "title": "old", "url": "u", "body": old_body}]), Discord()
        outcome = run(SWITCHED, True, gh, discord)
        self.assertEqual(outcome["action"], "supersede")
        self.assertEqual(outcome["issue"], 777)
        verbs = gh.verbs()
        self.assertLess(verbs.index("issue create"), verbs.index("issue close"))  # new one first
        close = next(c for c in gh.calls if c[:2] == ["issue", "close"])
        self.assertEqual(close[2], "12")
        self.assertIn("Superseded by #777", close[close.index("--comment") + 1])
        self.assertEqual(len(discord.posts), 1)
        self.assertFalse(discord.posts[0]["recovered"])
        # A different check in the same year is not: it updates the one issue.
        gh = FakeGh([{"number": 12, "title": "old", "url": "u", "body": old_body}])
        self.assertEqual(run(TWO_YEAR_ONLY, True, gh)["action"], "update")
        # The next year's check is its own scope.
        gh = FakeGh([{"number": 12, "title": "old", "url": "u", "body": old_body}])
        self.assertEqual(run(NEXT_ONLY, True, gh)["action"], "supersede")
        # Old-format markers match on their year.
        gh = FakeGh([{"number": 12, "title": "old", "url": "u",
                      "body": "<!-- alarm-scope: two_year:2025-26 -->"}])
        self.assertEqual(run(SUMMARY, True, gh)["action"], "update")

    def test_same_scope_is_not_superseded_and_unmarked_issues_are_updated(self) -> None:
        gh = FakeGh([{"number": 12, "title": "old", "url": "u", "body": "no marker"}])
        self.assertEqual(run(SWITCHED, True, gh)["action"], "update")
        gh = FakeGh([{"number": 12, "title": "old", "url": "u", "body": ra.scope_marker(("year", "2026-27"))}])
        self.assertEqual(run(SWITCHED, True, gh)["action"], "update")

    def test_extra_open_issues_are_closed_as_superseded(self) -> None:
        marker = ra.scope_marker(("year", "2025-26"))
        gh = FakeGh([{"number": 5, "title": "a", "url": "u", "body": marker},
                     {"number": 9, "title": "b", "url": "u", "body": marker}])
        run(SUMMARY, True, gh)
        closes = [c for c in gh.calls if c[:2] == ["issue", "close"]]
        self.assertEqual([c[2] for c in closes], ["5"])
        self.assertIn("Superseded by #9", closes[0][closes[0].index("--comment") + 1])

    def test_recovery_needs_every_check_above_its_floor_and_names_the_check(self) -> None:
        marker = ra.scope_marker(("two_year", "2025-26"))
        issue = [{"number": 12, "title": "x", "url": "https://u/12", "body": marker}]
        discord = Discord()
        gh = FakeGh(issue)
        run(HEALTHY, False, gh, discord)
        close = next(c for c in gh.calls if c[:2] == ["issue", "close"])
        comment = close[close.index("--comment") + 1]
        self.assertIn("two-year check", comment)
        self.assertIn("450 of 536", comment)
        self.assertIn("two-year", discord.posts[0]["title"])

    def test_the_alarm_stays_open_when_only_the_two_year_check_is_below(self) -> None:
        # The one-year check recovers (150 schools that missed a year left its
        # denominator) while the two-year check still sees them.
        gh = FakeGh([{"number": 12, "title": "x", "url": "u",
                      "body": ra.scope_marker(("two_year", "2025-26"))}])
        outcome = run(TWO_YEAR_ONLY, below_floor_of(TWO_YEAR_ONLY), gh)
        self.assertNotIn("issue close", gh.verbs())
        self.assertEqual(outcome["issue"], 12)

    def test_next_year_below_floor_titles_the_next_year(self) -> None:
        self.assertEqual(
            ra.issue_title(NEXT_ONLY, test_mode=False),
            "Discovery is behind: 10% of schools with 2025-26 have 2026-27 (floor 20%)",
        )

    def test_dry_run_changes_and_sends_nothing(self) -> None:
        for existing, below in (([], True), ([{"number": 3, "title": "x", "url": "u"}], True),
                                ([{"number": 3, "title": "x", "url": "u"}], False)):
            gh, discord = FakeGh(existing), Discord()
            posted = []
            ra.act(
                summary=SUMMARY if below else HEALTHY, below_floor=below, report="R", repo="o/r",
                test_mode=False, dry_run=True, assignee="santhonys", runner=gh,
                discord=lambda **p: posted.append(p) or True,
            )
            self.assertEqual(gh.verbs(), ["issue list"], existing)
            self.assertTrue(all(p.get("dry_run") for p in posted))

    def test_test_mode_uses_the_test_label_and_prefix(self) -> None:
        gh = FakeGh()
        run(SUMMARY, True, gh, test_mode=True)
        create = next(c for c in gh.calls if c[:2] == ["issue", "create"])
        self.assertEqual(create[create.index("--label") + 1], "alarm:discovery-renewal-test")
        self.assertTrue(create[create.index("--title") + 1].startswith("[test] "))

    def test_test_mode_never_touches_a_real_alarm_issue(self) -> None:
        # Even if the test label were put on a real issue, refuse.
        gh = FakeGh([{"number": 9, "title": "Discovery is behind: real", "url": "u"}])
        with self.assertRaises(ra.AlarmError):
            run(HEALTHY, False, gh, test_mode=True)
        self.assertNotIn("issue close", gh.verbs())
        # And a real run looks only at the real label.
        gh = FakeGh()
        run(HEALTHY, False, gh, test_mode=False)
        self.assertIn(f"labels={ra.ALARM_LABEL}", gh.calls[0])
        self.assertNotEqual(ra.ALARM_LABEL, ra.TEST_LABEL)

    def test_pull_requests_are_never_the_alarm_issue(self) -> None:
        self.assertIsNone(ra.find_open_issue("o/r", ra.ALARM_LABEL, FakeGh()))

    def test_newest_open_issue_is_the_alarm(self) -> None:
        gh = FakeGh([{"number": 30, "title": "a", "url": "u"}, {"number": 12, "title": "b", "url": "u"}])
        self.assertEqual(ra.find_open_issue("o/r", ra.ALARM_LABEL, gh)["number"], 30)

    def test_discord_failure_fails_the_job_after_the_issue_exists(self) -> None:
        gh = FakeGh()
        outcome = run(SUMMARY, True, gh, Discord(fail=True))
        self.assertTrue(outcome["discord_failed"])
        self.assertIn("issue create", gh.verbs())  # the issue action was done first
        with tempfile.TemporaryDirectory() as d:
            argv = MainTests().files(Path(d), dict(SUMMARY), True)
            import os
            os.environ["DISCORD_ALERTS_WEBHOOK_URL"] = "https://hook/secret"
            try:
                with unittest.mock.patch.object(
                        notify_discord, "post_webhook",
                        side_effect=notify_discord.DiscordPostError("HTTP 500")):
                    self.assertEqual(ra.main(argv, runner=FakeGh()), 1)
            finally:
                os.environ.pop("DISCORD_ALERTS_WEBHOOK_URL")
            # The issue number is still recorded.
            self.assertEqual(json.loads((Path(d) / "summary.json").read_text())["alarm_issue"], 777)

    def test_missing_webhook_is_only_a_warning(self) -> None:
        import os
        os.environ.pop("DISCORD_ALERTS_WEBHOOK_URL", None)
        with tempfile.TemporaryDirectory() as d:
            argv = MainTests().files(Path(d), dict(SUMMARY), True)
            self.assertEqual(ra.main(argv, runner=FakeGh()), 0)

    def test_gh_failure_is_an_error_not_a_quiet_day(self) -> None:
        with self.assertRaises(ra.AlarmError):
            run(SUMMARY, True, FakeGh(fail_on="issue list"))
        with self.assertRaises(ra.AlarmError):
            run(SUMMARY, True, FakeGh(fail_on="issue create"))
        with self.assertRaises(ra.AlarmError):
            run(HEALTHY, False, FakeGh([{"number": 1, "title": "t", "url": "u"}], fail_on="issue close"))

    def test_parse_issue_number(self) -> None:
        self.assertEqual(ra.parse_issue_number("https://github.com/o/r/issues/42\n"), 42)
        with self.assertRaises(ra.AlarmError):
            ra.parse_issue_number("created!")


class MainTests(unittest.TestCase):
    def files(self, tmp: Path, summary, below):
        (tmp / "state.json").write_text(json.dumps({"below_floor": below}))
        (tmp / "summary.json").write_text(json.dumps(summary))
        (tmp / "report.md").write_text("REPORT BODY")
        return ["--state", str(tmp / "state.json"), "--summary", str(tmp / "summary.json"),
                "--report", str(tmp / "report.md"), "--repo", "o/r"]

    def test_alarm_issue_is_written_into_the_summary(self) -> None:
        import os
        os.environ.pop("DISCORD_ALERTS_WEBHOOK_URL", None)
        with tempfile.TemporaryDirectory() as d:
            argv = self.files(Path(d), dict(SUMMARY), True)
            self.assertEqual(ra.main(argv, runner=FakeGh()), 0)
            self.assertEqual(json.loads((Path(d) / "summary.json").read_text())["alarm_issue"], 777)

    def test_test_issue_number_is_not_recorded_as_the_alarm(self) -> None:
        import os
        os.environ.pop("DISCORD_ALERTS_WEBHOOK_URL", None)
        with tempfile.TemporaryDirectory() as d:
            argv = self.files(Path(d), dict(SUMMARY), True) + ["--test-mode"]
            self.assertEqual(ra.main(argv, runner=FakeGh()), 0)
            self.assertIsNone(json.loads((Path(d) / "summary.json").read_text())["alarm_issue"])

    def test_failure_exits_nonzero(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            argv = self.files(Path(d), dict(SUMMARY), True)
            self.assertEqual(ra.main(argv, runner=FakeGh(fail_on="issue list")), 1)


class DiscordHelperTests(unittest.TestCase):
    def test_missing_secret_skips_and_never_prints_a_url(self) -> None:
        import contextlib, io, os
        os.environ.pop("DISCORD_ALERTS_WEBHOOK_URL", None)
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            posted = notify_discord.post_custom_embed(title="t", fields=[("a", "b")])
        self.assertFalse(posted)
        self.assertIn("::warning::DISCORD_ALERTS_WEBHOOK_URL not set; skipped Discord post", out.getvalue())

    def test_posts_red_alert_and_green_recovery(self) -> None:
        sent = []
        poster = lambda url, payload: sent.append((url, payload))  # noqa: E731
        self.assertTrue(notify_discord.post_custom_embed(
            title="a", fields=[("k", "v")], webhook_url="https://hook/secret", poster=poster))
        self.assertTrue(notify_discord.post_custom_embed(
            title="b", fields=[("k", "v")], recovered=True, webhook_url="https://hook/secret", poster=poster))
        self.assertEqual(sent[0][1]["embeds"][0]["color"], notify_discord.COLOR_FAILURE)
        self.assertEqual(sent[1][1]["embeds"][0]["color"], notify_discord.COLOR_SUCCESS)

    def test_post_failure_does_not_raise_or_leak(self) -> None:
        import contextlib, io

        def poster(url, payload):
            raise notify_discord.DiscordPostError("HTTP 500")

        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            self.assertFalse(notify_discord.post_custom_embed(
                title="a", fields=[], webhook_url="https://hook/secret", poster=poster))
        self.assertNotIn("secret", err.getvalue())


if __name__ == "__main__":
    unittest.main()
