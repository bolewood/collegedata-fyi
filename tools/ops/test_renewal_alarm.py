from __future__ import annotations

import contextlib
import io
import json
import os
import subprocess
import tempfile
import unittest
import unittest.mock
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from tools.ops import notify_discord
from tools.ops import renewal_alarm as ra


def ysum(year: str, *, one: float, one_floor: float | None, two: float | None = None,
         two_floor: float | None = None, renewed: int = 0, total: int = 479) -> dict:
    """One CDS year's checks, shaped like discovery_renewal.year_summary."""
    two = one if two is None else two
    return {
        "current_year": year,
        "renewed": renewed or round(total * one / 100),
        "prev_schools": total,
        "renewal_pct": one,
        "floor_pct": one_floor,
        "below_floor": one_floor is not None and one < one_floor,
        "two_year_renewed": round(536 * two / 100),
        "two_year_prev_schools": 536,
        "two_year_renewal_pct": two,
        "two_year_floor_pct": two_floor,
        "two_year_below_floor": two_floor is not None and two < two_floor,
    }


def arrivals_fields(cur_30: int, cur_exp: float, *, next_30: int = 0, next_exp: float = 0.0,
                    cur_win: int = 30, next_win: int = 30, cur_checked: bool = True,
                    next_checked: bool = False, cur_below: bool = False,
                    next_below: bool = False, cur_60: int | None = None,
                    cur_exp_60: float = 25.0) -> dict:
    """The per-year arrivals keys of a heartbeat summary, with their totals."""
    cur_60 = cur_30 + 400 if cur_60 is None else cur_60
    return {
        "arrivals_30d": cur_30 + next_30, "arrivals_expected_30d": cur_exp + next_exp,
        "arrivals_60d": cur_60 + next_30, "arrivals_expected_60d": cur_exp_60,
        "arrivals_window_days": cur_win, "arrivals_checked": cur_checked or next_checked,
        "arrivals_below_floor": cur_below or next_below,
        "arrivals_current_30d": cur_30, "arrivals_expected_current_30d": cur_exp,
        "arrivals_current_60d": cur_60, "arrivals_expected_current_60d": cur_exp_60,
        "arrivals_current_window_days": cur_win, "arrivals_current_checked": cur_checked,
        "arrivals_current_below_floor": cur_below,
        "arrivals_next_30d": next_30, "arrivals_expected_next_30d": next_exp,
        "arrivals_next_60d": next_30, "arrivals_expected_next_60d": next_exp,
        "arrivals_next_window_days": next_win, "arrivals_next_checked": next_checked,
        "arrivals_next_below_floor": next_below,
    }


BELOW = ysum("2025-26", one=76.0, one_floor=82.5, two=70.3, two_floor=74.5, renewed=364)
HEALTHY = ysum("2025-26", one=85.6, one_floor=82.5, two=84.0, two_floor=74.5, renewed=410)
TWO_YEAR_ONLY = ysum("2025-26", one=90.0, one_floor=82.5, two=70.9, two_floor=74.5)
NEXT_BELOW = ysum("2026-27", one=10.0, one_floor=50.7, total=417)
NEXT_UNTRACKED = ysum("2026-27", one=1.0, one_floor=None, two=1.0, total=417)


def issue(number: int, year: str = "2025-26", *, posted: bool = True, title: str | None = None,
          body: str | None = None) -> dict:
    return {
        "number": number,
        "title": title or f"Discovery is behind: 76% of schools with 2024-25 have {year} (floor 82%)",
        "url": f"https://github.com/o/r/issues/{number}",
        "body": body if body is not None else f"report\n{ra.scope_marker(year)}\n{ra.discord_marker(posted)}\n",
    }


class FakeGh:
    """Records gh calls; `open_issues` is what the REST issues list returns."""

    def __init__(self, open_issues: list[dict] | None = None, fail_on: str | None = None) -> None:
        self.open_issues = open_issues or []
        self.fail_on = fail_on
        self.calls: list[list[str]] = []
        self.bodies: list[tuple[str, str]] = []  # (verb, body)
        self.next_number = 777

    def __call__(self, args: list[str]) -> subprocess.CompletedProcess[str]:
        self.calls.append(args)
        verb = "issue list" if args[0] == "api" else " ".join(args[:2])
        if "--body-file" in args:
            self.bodies.append((verb, Path(args[args.index("--body-file") + 1]).read_text()))
        if self.fail_on and verb == self.fail_on:
            return subprocess.CompletedProcess(args, 1, "", "boom")
        if args[0] == "api":
            rest = [{**i, "html_url": i.get("url")} for i in self.open_issues]
            rest.append({"number": 1, "title": "a PR", "pull_request": {}, "html_url": "p"})
            return subprocess.CompletedProcess(args, 0, json.dumps(rest), "")
        if args[:2] == ["issue", "create"]:
            number, self.next_number = self.next_number, self.next_number + 1
            return subprocess.CompletedProcess(args, 0, f"https://github.com/o/r/issues/{number}\n", "")
        return subprocess.CompletedProcess(args, 0, "", "")

    def verbs(self) -> list[str]:
        return ["issue list" if c[0] == "api" else " ".join(c[:2]) for c in self.calls]

    def calls_for(self, verb: str) -> list[list[str]]:
        return [c for c in self.calls if " ".join(c[:2]) == verb]


class Discord:
    def __init__(self, *, fail: bool = False, skip: bool = False) -> None:
        self.posts: list[dict] = []
        self.fail, self.skip = fail, skip

    def __call__(self, **payload) -> bool:
        self.posts.append(payload)
        if self.fail:
            raise notify_discord.DiscordPostError("HTTP 500")
        return not self.skip


def run(years, gh, discord=None, *, current="2025-26", test_mode=False, dry_run=False, reports=None):
    return ra.act(
        years=years, reports=reports or {}, current_year=current, repo="o/r",
        test_mode=test_mode, dry_run=dry_run, assignee="santhonys", runner=gh,
        fallback_report="REPORT BODY", discord=discord or Discord(),
    )


def actions(outcome) -> dict[str, str]:
    return {a["year"]: a["action"] for a in outcome["actions"]}


class DecisionTests(unittest.TestCase):
    def test_decide_table(self) -> None:
        self.assertEqual(ra.decide(True, None), "create")
        self.assertEqual(ra.decide(True, 5), "update")
        self.assertEqual(ra.decide(False, 5), "close")
        self.assertEqual(ra.decide(False, None), "none")


class ActTests(unittest.TestCase):
    def test_below_floor_without_an_issue_creates_one_and_posts(self) -> None:
        gh, discord = FakeGh(), Discord()
        outcome = run({"2025-26": BELOW}, gh, discord)
        self.assertEqual((outcome["actions"][0]["action"], outcome["issue"]), ("create", 777))
        create = gh.calls_for("issue create")[0]
        self.assertEqual(create[create.index("--label") + 1], "alarm:discovery-renewal")
        self.assertEqual(create[create.index("--assignee") + 1], "santhonys")
        self.assertEqual(
            create[create.index("--title") + 1],
            "Discovery is behind: 76% of schools with 2024-25 have 2025-26 (floor 82%)",
        )
        self.assertIn("label create", gh.verbs())
        self.assertEqual(len(discord.posts), 1)
        self.assertFalse(discord.posts[0]["recovered"])
        # Created marked as not posted, then flipped once the post went out.
        created, flipped = gh.bodies[0][1], gh.bodies[1][1]
        self.assertIn("alarm-scope: year:2025-26", created)
        self.assertIn("discord-posted: false", created)
        self.assertIn("discord-posted: true", flipped)

    def test_issue_is_found_by_label_through_rest_not_search(self) -> None:
        gh = FakeGh()
        run({"2025-26": BELOW}, gh)
        listing = next(c for c in gh.calls if c[0] == "api")
        self.assertIn("labels=alarm:discovery-renewal", listing)
        self.assertIn("repos/o/r/issues", listing)
        self.assertFalse(any(c[:2] == ["issue", "list"] for c in gh.calls))

    def test_pull_requests_are_never_the_alarm_issue(self) -> None:
        self.assertEqual(ra.find_open_issues("o/r", ra.ALARM_LABEL, FakeGh()), [])

    def test_standing_issue_gets_title_and_body_replaced_with_no_comment_or_post(self) -> None:
        gh, discord = FakeGh([issue(12)]), Discord()
        outcome = run({"2025-26": ysum("2025-26", one=78.0, one_floor=82.5, two=80.0, two_floor=74.5)}, gh, discord)
        self.assertEqual(actions(outcome), {"2025-26": "update"})
        self.assertEqual(outcome["issue"], 12)
        edit = gh.calls_for("issue edit")[0]
        self.assertIn("78% of schools with 2024-25", edit[edit.index("--title") + 1])
        self.assertEqual(discord.posts, [])
        self.assertFalse(any("--comment" in c for c in gh.calls))
        self.assertEqual(gh.verbs(), ["issue list", "issue edit"])

    def test_recovery_closes_with_one_comment_and_posts_green(self) -> None:
        gh, discord = FakeGh([issue(12)]), Discord()
        outcome = run({"2025-26": HEALTHY}, gh, discord)
        self.assertEqual((outcome["actions"][0]["action"], outcome["issue"]), ("close", None))
        close = gh.calls_for("issue close")[0]
        comment = close[close.index("--comment") + 1]
        self.assertIn("410 of 479 (85.6%)", comment)
        self.assertIn("two-year check is 84.0%", comment)
        self.assertEqual(len(discord.posts), 1)
        self.assertTrue(discord.posts[0]["recovered"])

    def test_above_floor_without_an_issue_does_nothing(self) -> None:
        gh, discord = FakeGh(), Discord()
        self.assertEqual(actions(run({"2025-26": HEALTHY}, gh, discord)), {})
        self.assertEqual(gh.verbs(), ["issue list"])
        self.assertEqual(discord.posts, [])

    def test_the_alarm_stays_open_while_only_the_two_year_check_is_below(self) -> None:
        # The one-year number recovers (schools that missed a year left its
        # denominator) while the two-year check still sees them.
        gh = FakeGh([issue(12)])
        outcome = run({"2025-26": TWO_YEAR_ONLY}, gh)
        self.assertNotIn("issue close", gh.verbs())
        self.assertEqual(outcome["issue"], 12)
        self.assertIn("71% of schools with 2024-25 or 2023-24", ra.issue_title(TWO_YEAR_ONLY, test_mode=False))

    def test_dry_run_changes_and_sends_nothing(self) -> None:
        for existing, ys in (([], BELOW), ([issue(3)], BELOW), ([issue(3)], HEALTHY),
                             ([issue(3, posted=False)], BELOW)):
            gh, posted = FakeGh(existing), []
            ra.act(
                years={"2025-26": ys}, reports={}, current_year="2025-26", repo="o/r",
                test_mode=False, dry_run=True, assignee="santhonys", runner=gh,
                fallback_report="R", discord=lambda **p: posted.append(p) or True,
            )
            self.assertEqual(gh.verbs(), ["issue list"], existing)
            self.assertTrue(all(p.get("dry_run") for p in posted))

    def test_test_mode_uses_the_test_label_prefix_and_assigns_nobody(self) -> None:
        gh = FakeGh()
        run({"2025-26": BELOW}, gh, test_mode=True)
        create = gh.calls_for("issue create")[0]
        self.assertEqual(create[create.index("--label") + 1], "alarm:discovery-renewal-test")
        self.assertTrue(create[create.index("--title") + 1].startswith("[test] "))
        self.assertNotIn("--assignee", create)

    def test_test_mode_never_touches_a_real_alarm_issue(self) -> None:
        gh = FakeGh([issue(9, title="Discovery is behind: real")])
        with self.assertRaises(ra.AlarmError):
            run({"2025-26": HEALTHY}, gh, test_mode=True)
        self.assertNotIn("issue close", gh.verbs())
        gh = FakeGh()
        run({"2025-26": HEALTHY}, gh)
        self.assertIn(f"labels={ra.ALARM_LABEL}", gh.calls[0])
        self.assertNotEqual(ra.ALARM_LABEL, ra.TEST_LABEL)

    def test_extra_open_issues_for_one_year_are_closed_as_duplicates(self) -> None:
        gh = FakeGh([issue(5), issue(9)])
        run({"2025-26": BELOW}, gh)
        closes = gh.calls_for("issue close")
        self.assertEqual([c[2] for c in closes], ["5"])
        self.assertIn("Superseded by #9", closes[0][closes[0].index("--comment") + 1])

    def test_gh_failure_is_an_error_not_a_quiet_day(self) -> None:
        with self.assertRaises(ra.AlarmError):
            run({"2025-26": BELOW}, FakeGh(fail_on="issue list"))
        with self.assertRaises(ra.AlarmError):
            run({"2025-26": BELOW}, FakeGh(fail_on="issue create"))
        with self.assertRaises(ra.AlarmError):
            run({"2025-26": HEALTHY}, FakeGh([issue(1)], fail_on="issue close"))

    def test_parse_issue_number(self) -> None:
        self.assertEqual(ra.parse_issue_number("https://github.com/o/r/issues/42\n"), 42)
        with self.assertRaises(ra.AlarmError):
            ra.parse_issue_number("created!")


class PerYearTests(unittest.TestCase):
    def test_june_2027_next_year_breach_opens_its_own_issue_and_posts(self) -> None:
        # 2027-06-30: 2025-26 is still the current year (78% vs 83) with its
        # issue open; 2026-27 is at 10% against a floor of 50.7%.
        years = {
            "2025-26": ysum("2025-26", one=78.0, one_floor=83.0, two=76.0, two_floor=75.0),
            "2026-27": NEXT_BELOW,
        }
        gh, discord = FakeGh([issue(12)]), Discord()
        outcome = run(years, gh, discord, current="2025-26")
        self.assertEqual(actions(outcome), {"2025-26": "update", "2026-27": "create"})
        create = gh.calls_for("issue create")[0]
        self.assertEqual(
            create[create.index("--title") + 1],
            "Discovery is behind: 10% of schools with 2025-26 have 2026-27 (floor 51%)",
        )
        self.assertEqual(len(discord.posts), 1)  # the new issue only; 12 is not re-announced
        self.assertIn("2026-27", discord.posts[0]["title"])
        self.assertEqual(outcome["issue"], 12)  # the current year's issue is the alarm issue
        created = [b for verb, b in gh.bodies if verb == "issue create"][0]
        self.assertIn("alarm-scope: year:2026-27", created)

    def test_each_year_gets_its_own_report(self) -> None:
        years = {"2025-26": BELOW, "2026-27": NEXT_BELOW}
        gh = FakeGh()
        run(years, gh, reports={"2025-26": "BODY A", "2026-27": "BODY B"})
        bodies = [b for verb, b in gh.bodies if verb == "issue create"]
        self.assertTrue(bodies[0].startswith("BODY A"))
        self.assertTrue(bodies[1].startswith("BODY B"))

    def test_the_september_switch_does_not_close_a_still_short_year(self) -> None:
        # 2027-09-01: 2026-27 becomes the current year; 2025-26 is judged on
        # its own numbers against the flat mature floor and stays short.
        years = {
            "2025-26": ysum("2025-26", one=78.0, one_floor=83.0, two=76.0, two_floor=75.0),
            "2026-27": ysum("2026-27", one=51.0, one_floor=76.0, two=48.0, two_floor=68.0, total=417),
        }
        gh, discord = FakeGh([issue(12, "2025-26")]), Discord()
        outcome = run(years, gh, discord, current="2026-27")
        self.assertEqual(actions(outcome), {"2025-26": "update", "2026-27": "create"})
        self.assertNotIn("issue close", gh.verbs())
        self.assertEqual(len(discord.posts), 1)

    def test_a_recovered_year_closes_without_touching_the_others(self) -> None:
        years = {"2025-26": HEALTHY, "2026-27": NEXT_BELOW}
        gh, discord = FakeGh([issue(12, "2025-26"), issue(13, "2026-27")]), Discord()
        outcome = run(years, gh, discord)
        self.assertEqual(actions(outcome), {"2025-26": "close", "2026-27": "update"})
        closed = [c[2] for c in gh.calls_for("issue close")]
        self.assertEqual(closed, ["12"])
        self.assertEqual(len(discord.posts), 1)
        self.assertTrue(discord.posts[0]["recovered"])
        self.assertEqual(outcome["issue"], 13)

    def test_an_earlier_year_below_the_flat_floor_never_opens_an_issue(self) -> None:
        # 2023-24 held at about 82% against the flat 83%: not an alarm.
        years = {
            "2023-24": ysum("2023-24", one=82.0, one_floor=83.0, two=80.0, two_floor=75.0),
            "2025-26": HEALTHY,
        }
        gh = FakeGh()
        self.assertEqual(actions(run(years, gh)), {})
        self.assertNotIn("issue create", gh.verbs())

    def test_an_untracked_next_year_alarms_nothing(self) -> None:
        gh = FakeGh()
        self.assertEqual(actions(run({"2025-26": HEALTHY, "2026-27": NEXT_UNTRACKED}, gh)), {})

    def test_an_open_issue_for_a_year_that_is_no_longer_evaluated_is_retired(self) -> None:
        # 2019-20 is far older than the evaluated years: close it, say why,
        # and never count it as outstanding.
        gh, discord = FakeGh([issue(8, "2019-20")]), Discord()
        outcome = run({"2025-26": HEALTHY}, gh, discord)
        self.assertEqual(actions(outcome), {"2019-20": "retire"})
        close = gh.calls_for("issue close")[0]
        self.assertIn("No longer tracked", close[close.index("--comment") + 1])
        self.assertEqual(len(discord.posts), 1)
        self.assertEqual(ra.outstanding(outcome), (False, ""))

    def test_a_year_two_cycles_old_is_retired_with_its_final_numbers(self) -> None:
        # 2023-24 sat at 82.9% against the flat 83% and would never close.
        years = {
            "2023-24": ysum("2023-24", one=82.9, one_floor=83.0, two=79.0, two_floor=75.0),
            "2024-25": ysum("2024-25", one=88.0, one_floor=83.0, two=85.0, two_floor=75.0),
            "2025-26": HEALTHY,
        }
        gh, discord = FakeGh([issue(7, "2023-24")]), Discord()
        outcome = run(years, gh, discord)
        self.assertEqual(actions(outcome), {"2023-24": "retire"})
        close = gh.calls_for("issue close")[0]
        comment = close[close.index("--comment") + 1]
        self.assertEqual(
            comment,
            "No longer tracked: final one-year 82.9%, two-year 79.0%; "
            "lapsed schools stay in the two-year check.",
        )
        self.assertEqual(len(discord.posts), 1)
        self.assertIn("2023-24 is no longer tracked", discord.posts[0]["title"])
        self.assertEqual(ra.outstanding(outcome), (False, ""))
        self.assertNotIn("issue create", gh.verbs())

    def test_last_years_issue_is_still_tracked_after_the_september_switch(self) -> None:
        # current-1 is not retired: 2025-26 stays open at 2027-09-01.
        years = {
            "2025-26": ysum("2025-26", one=78.0, one_floor=83.0, two=76.0, two_floor=75.0),
            "2026-27": ysum("2026-27", one=51.0, one_floor=76.0, two=60.0, two_floor=68.0, total=417),
        }
        gh = FakeGh([issue(12, "2025-26")])
        outcome = run(years, gh, current="2026-27")
        self.assertEqual(actions(outcome)["2025-26"], "update")


class MarkerTests(unittest.TestCase):
    def test_year_marker_is_read_and_legacy_markers_match_on_year(self) -> None:
        self.assertEqual(ra.issue_year({"number": 1, "body": ra.scope_marker("2025-26")}, "2026-27"),
                         ("2025-26", "year"))
        self.assertEqual(
            ra.issue_year({"number": 1, "body": "<!-- alarm-scope: two_year:2025-26 -->"}, "2026-27"),
            ("2025-26", "two_year"))

    def test_a_missing_marker_uses_the_year_in_the_title_and_warns(self) -> None:
        edited = issue(12, "2025-26", body="someone rewrote the whole body")
        with contextlib.redirect_stderr(io.StringIO()) as err:
            year, _ = ra.issue_year(edited, "2026-27")
        self.assertEqual(year, "2025-26")  # from the title, not the current year
        self.assertIn("::warning::", err.getvalue())

    def test_a_missing_marker_and_title_falls_back_to_the_current_year_and_warns(self) -> None:
        with contextlib.redirect_stderr(io.StringIO()) as err:
            year, _ = ra.issue_year({"number": 3, "title": "renamed", "body": ""}, "2026-27")
        self.assertEqual(year, "2026-27")
        self.assertIn("::warning::", err.getvalue())

    def test_an_edited_marker_does_not_open_a_duplicate_or_silently_rescope(self) -> None:
        # The body lost its marker. The issue is still the 2025-26 alarm: it
        # is updated (and the marker restored), not duplicated or re-scoped.
        edited = issue(12, "2025-26", body="edited by hand")
        gh = FakeGh([edited])
        with contextlib.redirect_stderr(io.StringIO()):
            outcome = run({"2025-26": BELOW, "2026-27": NEXT_UNTRACKED}, gh, current="2026-27")
        self.assertEqual(actions(outcome), {"2025-26": "update"})
        self.assertNotIn("issue create", gh.verbs())
        self.assertIn("alarm-scope: year:2025-26", gh.bodies[0][1])


class DiscordRetryTests(unittest.TestCase):
    def test_a_missing_webhook_leaves_the_post_marked_false(self) -> None:
        gh = FakeGh()
        outcome = run({"2025-26": BELOW}, gh, Discord(skip=True))
        self.assertFalse(outcome["discord_failed"])  # a warning, not a failure
        self.assertEqual(len(gh.bodies), 1)  # never flipped to true
        self.assertIn("discord-posted: false", gh.bodies[0][1])

    def test_a_failed_post_leaves_the_marker_false_and_fails_the_job(self) -> None:
        gh = FakeGh()
        with contextlib.redirect_stderr(io.StringIO()):
            outcome = run({"2025-26": BELOW}, gh, Discord(fail=True))
        self.assertTrue(outcome["discord_failed"])
        self.assertIn("issue create", gh.verbs())  # the issue action was done first
        self.assertIn("discord-posted: false", gh.bodies[0][1])

    def test_a_later_update_retries_the_post_and_flips_the_marker(self) -> None:
        gh, discord = FakeGh([issue(12, posted=False)]), Discord()
        outcome = run({"2025-26": BELOW}, gh, discord)
        self.assertEqual(actions(outcome), {"2025-26": "update"})
        self.assertEqual(len(discord.posts), 1)
        self.assertEqual(discord.posts[0]["url"], "https://github.com/o/r/issues/12")
        self.assertIn("discord-posted: true", gh.bodies[-1][1])
        # Once flipped, the next update stays quiet.
        gh2, discord2 = FakeGh([issue(12, posted=True)]), Discord()
        run({"2025-26": BELOW}, gh2, discord2)
        self.assertEqual(discord2.posts, [])

    def test_a_retry_that_fails_again_keeps_the_marker_false(self) -> None:
        gh = FakeGh([issue(12, posted=False)])
        with contextlib.redirect_stderr(io.StringIO()):
            outcome = run({"2025-26": BELOW}, gh, Discord(fail=True))
        self.assertTrue(outcome["discord_failed"])
        self.assertIn("discord-posted: false", gh.bodies[-1][1])

    def test_issues_without_the_marker_are_treated_as_posted(self) -> None:
        self.assertTrue(ra.discord_posted("no marker at all"))
        self.assertFalse(ra.discord_posted(ra.discord_marker(False)))


class MainTests(unittest.TestCase):
    def files(self, tmp: Path, years: dict, current: str = "2025-26") -> list[str]:
        (tmp / "state.json").write_text(json.dumps({"years": years, "current_year": current,
                                                    "below_floor": True}))
        (tmp / "summary.json").write_text(json.dumps({"current_year": current, "alarm_issue": None}))
        (tmp / "report.md").write_text("REPORT BODY")
        return ["--state", str(tmp / "state.json"), "--summary", str(tmp / "summary.json"),
                "--report", str(tmp / "report.md"), "--repo", "o/r"]

    def alarm_issue(self, tmp: Path):
        return json.loads((tmp / "summary.json").read_text())["alarm_issue"]

    def test_alarm_issue_is_written_into_the_summary(self) -> None:
        os.environ.pop("DISCORD_ALERTS_WEBHOOK_URL", None)
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(ra.main(self.files(Path(d), {"2025-26": BELOW}), runner=FakeGh()), 0)
            self.assertEqual(self.alarm_issue(Path(d)), 777)

    def test_year_reports_directory_supplies_each_issue_body(self) -> None:
        os.environ.pop("DISCORD_ALERTS_WEBHOOK_URL", None)
        with tempfile.TemporaryDirectory() as d:
            argv = self.files(Path(d), {"2025-26": BELOW})
            (Path(d) / "yr").mkdir()
            (Path(d) / "yr" / "2025-26.md").write_text("YEAR BODY")
            gh = FakeGh()
            ra.main(argv + ["--year-reports", str(Path(d) / "yr")], runner=gh)
            self.assertTrue(gh.bodies[0][1].startswith("YEAR BODY"))

    def test_test_issue_number_is_not_recorded_as_the_alarm(self) -> None:
        os.environ.pop("DISCORD_ALERTS_WEBHOOK_URL", None)
        with tempfile.TemporaryDirectory() as d:
            argv = self.files(Path(d), {"2025-26": BELOW}) + ["--test-mode"]
            self.assertEqual(ra.main(argv, runner=FakeGh()), 0)
            self.assertIsNone(self.alarm_issue(Path(d)))

    def test_failure_exits_nonzero(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            argv = self.files(Path(d), {"2025-26": BELOW})
            self.assertEqual(ra.main(argv, runner=FakeGh(fail_on="issue list")), 1)

    def test_state_without_years_is_an_error(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            argv = self.files(Path(d), {})
            self.assertEqual(ra.main(argv, runner=FakeGh()), 1)

    def test_discord_failure_exits_nonzero_but_keeps_the_issue_number(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            argv = self.files(Path(d), {"2025-26": BELOW})
            os.environ["DISCORD_ALERTS_WEBHOOK_URL"] = "https://hook/secret"
            try:
                with unittest.mock.patch.object(
                        notify_discord, "post_webhook",
                        side_effect=notify_discord.DiscordPostError("HTTP 500")), \
                        contextlib.redirect_stderr(io.StringIO()):
                    self.assertEqual(ra.main(argv, runner=FakeGh()), 1)
            finally:
                os.environ.pop("DISCORD_ALERTS_WEBHOOK_URL")
            self.assertEqual(self.alarm_issue(Path(d)), 777)


class SimGh:
    """A stateful gh: issues are opened, edited and closed across simulated days."""

    def __init__(self) -> None:
        self.issues: dict[int, dict] = {}
        self.next_number = 100
        self.now = datetime(2026, 4, 19, 12, tzinfo=timezone.utc)
        self.created = 0
        self.closed: list[tuple[int, str]] = []
        self.assignees: list[bool] = []

    def __call__(self, args: list[str]) -> subprocess.CompletedProcess[str]:
        if args[0] == "api":
            rows = [{"number": n, "title": i["title"], "body": i["body"], "created_at": i["created_at"],
                     "html_url": f"https://github.com/o/r/issues/{n}"}
                    for n, i in self.issues.items() if i["open"]]
            return subprocess.CompletedProcess(args, 0, json.dumps(rows), "")
        verb = " ".join(args[:2])
        body = Path(args[args.index("--body-file") + 1]).read_text() if "--body-file" in args else None
        if verb == "issue create":
            number, self.next_number = self.next_number, self.next_number + 1
            self.issues[number] = {"title": args[args.index("--title") + 1], "body": body or "",
                                   "created_at": self.now.isoformat(), "open": True}
            self.created += 1
            self.assignees.append("--assignee" in args)
            return subprocess.CompletedProcess(args, 0, f"https://github.com/o/r/issues/{number}\n", "")
        if verb == "issue edit":
            issue_ = self.issues[int(args[2])]
            if body is not None:
                issue_["body"] = body
            if "--title" in args:
                issue_["title"] = args[args.index("--title") + 1]
        if verb == "issue close":
            self.issues[int(args[2])]["open"] = False
            self.closed.append((int(args[2]), args[args.index("--comment") + 1]))
        return subprocess.CompletedProcess(args, 0, "", "")


class RenotifyTests(unittest.TestCase):
    """A standing issue that is still short is replaced by a new one (a new
    notification), monthly or when the gap grows by 5 points."""

    def replay(self, days: int, pct_for_day) -> tuple[SimGh, Discord]:
        gh, discord = SimGh(), Discord()
        for day in range(days + 1):
            gh.now = datetime(2026, 4, 19, 12, tzinfo=timezone.utc) + timedelta(days=day)
            ys = ysum("2025-26", one=pct_for_day(day), one_floor=80.0, two=90.0, two_floor=70.0)
            ra.act(years={"2025-26": ys}, reports={}, current_year="2025-26", repo="o/r",
                   test_mode=False, dry_run=False, assignee="santhonys", runner=gh,
                   fallback_report="R", discord=discord, now=gh.now)
        return gh, discord

    def test_a_slow_slide_notifies_about_monthly(self) -> None:
        # The gap grows from 8 to 28 points over 220 days (0.09 a day: +5 takes 55
        # days), so the 30-day rule is what fires.
        gh, discord = self.replay(220, lambda d: 72.0 - 20.0 * d / 220)
        self.assertEqual(gh.created, 8)  # days 0, 30, 60, ..., 210
        self.assertEqual(len(discord.posts), 8)
        self.assertEqual(sum(1 for i in gh.issues.values() if i["open"]), 1)
        self.assertEqual(len(gh.closed), 7)
        self.assertTrue(all(gh.assignees))

    def test_a_jump_of_five_points_notifies_at_once(self) -> None:
        gh, discord = self.replay(45, lambda d: 72.0 if d < 10 else 66.0)
        # day 0 opens; day 10 the gap grew 8 -> 14; day 40 is 30 days after that.
        self.assertEqual(gh.created, 3)
        reasons = [c for _, c in gh.closed]
        self.assertTrue(reasons[0].startswith("Superseded by #101: still behind (gap 8.0\u219214.0 points)"))
        self.assertEqual(len(discord.posts), 3)

    def test_a_steady_gap_does_not_renotify_inside_thirty_days(self) -> None:
        gh, _ = self.replay(29, lambda d: 72.0)
        self.assertEqual(gh.created, 1)
        self.assertEqual(gh.closed, [])

    def test_small_growth_inside_a_month_does_not_renotify(self) -> None:
        gh, _ = self.replay(29, lambda d: 72.0 - 4.0 * d / 29)  # +4 points
        self.assertEqual(gh.created, 1)

    def test_the_gap_at_open_stays_in_the_body_through_updates(self) -> None:
        gh, _ = self.replay(20, lambda d: 72.0 - 0.1 * d)
        (body,) = [i["body"] for i in gh.issues.values() if i["open"]]
        self.assertEqual(ra.parse_gap(body), 8.0)
        self.assertIn("<!-- alarm-gap: 8.0 -->", body)

    def test_a_fall_in_the_gap_never_renotifies(self) -> None:
        gh, _ = self.replay(29, lambda d: 72.0 + 5.0 * d / 29)
        self.assertEqual(gh.created, 1)

    def test_a_legacy_issue_with_no_gap_marker_is_renotified_by_age_only(self) -> None:
        old = issue(12)
        old["created_at"] = "2026-10-01T00:00:00+00:00"
        gh, discord = FakeGh([old]), Discord()
        ys = ysum("2025-26", one=60.0, one_floor=80.0, two=90.0, two_floor=70.0)
        out = ra.act(years={"2025-26": ys}, reports={}, current_year="2025-26", repo="o/r",
                     test_mode=False, dry_run=False, assignee="santhonys", runner=gh,
                     fallback_report="R", discord=discord,
                     now=datetime(2026, 10, 20, tzinfo=timezone.utc))
        self.assertEqual(actions(out), {"2025-26": "update"})  # 19 days, no marker: no growth known
        out = ra.act(years={"2025-26": ys}, reports={}, current_year="2025-26", repo="o/r",
                     test_mode=False, dry_run=False, assignee="santhonys", runner=FakeGh([old]),
                     fallback_report="R", discord=discord,
                     now=datetime(2026, 11, 5, tzinfo=timezone.utc))
        self.assertEqual(actions(out), {"2025-26": "renotify"})

    def test_a_dry_run_reports_the_renotify_and_changes_nothing(self) -> None:
        old = issue(12, body=ra.scope_marker("2025-26") + ra.discord_marker(True) + "\n<!-- alarm-gap: 8.0 -->")
        old["created_at"] = "2026-09-01T00:00:00+00:00"
        gh = FakeGh([old])
        ys = ysum("2025-26", one=60.0, one_floor=80.0, two=90.0, two_floor=70.0)
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            ra.act(years={"2025-26": ys}, reports={}, current_year="2025-26", repo="o/r",
                   test_mode=False, dry_run=True, assignee="santhonys", runner=gh,
                   fallback_report="R", discord=lambda **p: True,
                   now=datetime(2026, 11, 1, tzinfo=timezone.utc))
        self.assertEqual(gh.verbs(), ["issue list"])
        self.assertIn("renotify", buf.getvalue())

    def test_the_arrivals_title_names_the_window(self) -> None:
        ys = {**ysum("2025-26", one=90.0, one_floor=80.0, two=90.0, two_floor=70.0),
              **arrivals_fields(5, 3.0, cur_win=60, cur_below=True, cur_60=4, cur_exp_60=24.0)}
        self.assertEqual(ra.issue_title(ys, test_mode=False),
                         "Almost nothing new arrived for 2025-26: 4 schools in 60 days (expected 24)")

    def test_the_gap_boundary_is_exactly_five_points(self) -> None:
        # Gap at open 8.0. Exactly +5.0 notifies before day 30; +4.9 does not.
        gh, _ = self.replay(10, lambda d: 72.0 if d < 5 else 67.0)
        self.assertEqual(gh.created, 2)
        gh, _ = self.replay(10, lambda d: 72.0 if d < 5 else 67.1)
        self.assertEqual(gh.created, 1)

    def test_the_arrivals_check_alone_renotifies_by_age(self) -> None:
        ys = {**ysum("2025-26", one=90.0, one_floor=80.0, two=90.0, two_floor=70.0),
              **arrivals_fields(2, 30.0, cur_below=True)}
        self.assertIsNone(ra.gap_of(ys))
        self.assertEqual(ra.issue_title(ys, test_mode=False),
                         "Almost nothing new arrived for 2025-26: 2 schools in 30 days (expected 30)")
        gh, discord = SimGh(), Discord()
        for day in range(0, 65):
            gh.now = datetime(2026, 9, 1, tzinfo=timezone.utc) + timedelta(days=day)
            ra.act(years={"2025-26": ys}, reports={}, current_year="2025-26", repo="o/r",
                   test_mode=False, dry_run=False, assignee="santhonys", runner=gh,
                   fallback_report="R", discord=discord, now=gh.now)
        self.assertEqual(gh.created, 3)  # days 0, 30, 60


class JoinTests(unittest.TestCase):
    """A check that joins an open issue's set (arrivals going short on an issue
    opened for the renewal number) supersedes it, after 3 daily runs, once."""

    def two_checks(self, *, renewal_below: bool, arrivals_below: bool) -> dict:
        one = 70.0 if renewal_below else 95.0
        return {
            **ysum("2025-26", one=one, one_floor=82.5, two=95.0, two_floor=74.5),
            **arrivals_fields(0 if arrivals_below else 30, 20.0, cur_below=arrivals_below),
        }

    def run_days(self, gh, discord, series, start=datetime(2026, 11, 25, 13, tzinfo=timezone.utc)):
        out = []
        for day, ys in enumerate(series):
            gh.now = start + timedelta(days=day)
            out.append(ra.act(years={"2025-26": ys}, reports={}, current_year="2025-26", repo="o/r",
                              test_mode=False, dry_run=False, assignee="santhonys", runner=gh,
                              fallback_report="R", discord=discord, now=gh.now))
        return out

    def test_arrivals_joining_a_renewal_issue_supersedes_it_with_its_own_title(self) -> None:
        gh, discord = SimGh(), Discord()
        renewal_only = self.two_checks(renewal_below=True, arrivals_below=False)
        both = self.two_checks(renewal_below=True, arrivals_below=True)
        out = self.run_days(gh, discord, [renewal_only, renewal_only] + [both] * 3)
        kinds = [actions(o)["2025-26"] for o in out]
        # Below on three consecutive daily runs (days 3, 4, 5): joins on the third.
        self.assertEqual(kinds, ["create", "update", "update", "update", "renotify"])
        self.assertEqual(gh.created, 2)
        newest = max(gh.issues)
        self.assertTrue(gh.issues[newest]["title"].startswith("Almost nothing new arrived for 2025-26"))
        self.assertIn("Superseded by #", gh.closed[-1][1])
        self.assertIn("also below its floor: arrivals", gh.closed[-1][1])
        self.assertEqual(len(discord.posts), 2)
        self.assertIn("alarm-checks: arrivals,current", gh.issues[newest]["body"])

    def test_a_daily_boundary_flap_never_supersedes(self) -> None:
        gh, discord = SimGh(), Discord()
        renewal_only = self.two_checks(renewal_below=True, arrivals_below=False)
        both = self.two_checks(renewal_below=True, arrivals_below=True)
        series = [renewal_only] + [both if d % 2 else renewal_only for d in range(40)]
        out = self.run_days(gh, discord, series)
        self.assertEqual(sum(actions(o)["2025-26"] == "renotify" for o in out), 1)  # the 30-day rule only
        self.assertEqual(sum("also below its floor" in c for _, c in gh.closed), 0)

    def test_once_joined_it_is_not_a_second_supersede_when_the_check_flaps(self) -> None:
        gh, discord = SimGh(), Discord()
        renewal_only = self.two_checks(renewal_below=True, arrivals_below=False)
        both = self.two_checks(renewal_below=True, arrivals_below=True)
        series = [renewal_only] + [both] * 3 + [renewal_only, both, renewal_only, both, both, both]
        out = self.run_days(gh, discord, series)
        joins = [i for i, o in enumerate(out) if actions(o)["2025-26"] == "renotify"]
        self.assertEqual(len(joins), 1)

    def test_a_check_below_for_two_runs_then_back_resets_its_count(self) -> None:
        gh, discord = SimGh(), Discord()
        renewal_only = self.two_checks(renewal_below=True, arrivals_below=False)
        both = self.two_checks(renewal_below=True, arrivals_below=True)
        series = [renewal_only, both, both, renewal_only, both, both, renewal_only]
        out = self.run_days(gh, discord, series)
        self.assertNotIn("renotify", [actions(o)["2025-26"] for o in out])

    def test_an_issue_with_no_checks_marker_is_never_superseded_for_a_new_check(self) -> None:
        gh, discord = FakeGh([issue(12)]), Discord()
        both = self.two_checks(renewal_below=True, arrivals_below=True)
        for _ in range(4):
            out = run({"2025-26": both}, gh, discord)
            self.assertEqual(actions(out), {"2025-26": "update"})

    def test_pending_counts_once_per_calendar_day(self) -> None:
        confirmed, pending = {"current"}, {}
        for _ in range(5):  # five runs on the same day
            joined, pending = ra.join_progress(["current", "arrivals"], confirmed, pending, "2026-11-25")
        self.assertEqual((joined, pending), ([], {"arrivals": (1, "2026-11-25")}))
        joined, pending = ra.join_progress(["current", "arrivals"], confirmed, pending, "2026-11-26")
        joined, pending = ra.join_progress(["current", "arrivals"], confirmed, pending, "2026-11-27")
        self.assertEqual(joined, ["arrivals"])


class ArrivalsHoldTests(unittest.TestCase):
    """An arrivals breach that is why an issue is open is cleared only by a real
    30-day recovery, never by the check changing windows or being unchecked."""

    def arrivals_ysum(self, *, count_30: int, expected_30: float, below: bool,
                      window: int = 30, checked: bool = True) -> dict:
        return {
            **ysum("2025-26", one=95.0, one_floor=82.5, two=95.0, two_floor=74.5),
            **arrivals_fields(count_30, expected_30, cur_win=window, cur_checked=checked,
                              cur_below=below),
        }

    def open_with_arrivals(self):
        gh, discord = SimGh(), Discord()
        gh.now = datetime(2026, 11, 25, 12, tzinfo=timezone.utc)
        first = self.arrivals_ysum(count_30=0, expected_30=12.0, below=True)
        out = ra.act(years={"2025-26": first}, reports={}, current_year="2025-26", repo="o/r",
                     test_mode=False, dry_run=False, assignee="santhonys", runner=gh,
                     fallback_report="R", discord=discord, now=gh.now)
        self.assertEqual(actions(out), {"2025-26": "create"})
        (body,) = [i["body"] for i in gh.issues.values()]
        self.assertIn(ra.ARRIVALS_OPEN_MARKER, body)
        return gh, discord

    def step(self, gh, discord, ys, days: int = 1):
        gh.now += timedelta(days=days)
        return ra.act(years={"2025-26": ys}, reports={}, current_year="2025-26", repo="o/r",
                      test_mode=False, dry_run=False, assignee="santhonys", runner=gh,
                      fallback_report="R", discord=discord, now=gh.now)

    def test_a_window_switch_that_clears_the_flag_does_not_close_the_issue(self) -> None:
        gh, discord = self.open_with_arrivals()
        # December: the 30-day window cannot judge, the 60-day one still holds
        # October's arrivals, so the flag is off. 30-day arrivals are still 0.
        out = self.step(gh, discord, self.arrivals_ysum(
            count_30=0, expected_30=8.0, below=False, window=60))
        self.assertEqual(actions(out), {"2025-26": "update"})
        self.assertEqual(gh.closed, [])
        self.assertEqual(ra.outstanding(out), (True, "2025-26"))
        (issue_,) = [i for i in gh.issues.values() if i["open"]]
        self.assertIn(ra.ARRIVALS_OPEN_MARKER, issue_["body"])
        self.assertIn("Arrivals breach still open", issue_["body"])
        self.assertIn("Almost nothing new arrived for 2025-26: 0 schools", issue_["title"])

    def test_an_unchecked_window_holds_the_breach(self) -> None:
        gh, discord = self.open_with_arrivals()
        for _ in range(10):
            out = self.step(gh, discord, self.arrivals_ysum(
                count_30=1, expected_30=5.0, below=False, window=60, checked=False))
            self.assertEqual(actions(out), {"2025-26": "update"})
        self.assertEqual(gh.closed, [])

    def test_the_breach_closes_on_a_real_recovery_only(self) -> None:
        gh, discord = self.open_with_arrivals()
        # Expected 12: the threshold is max(3, 0.4 x 12) = 4.8. Four is not back.
        self.assertEqual(actions(self.step(gh, discord, self.arrivals_ysum(
            count_30=4, expected_30=12.0, below=False))), {"2025-26": "update"})
        out = self.step(gh, discord, self.arrivals_ysum(count_30=5, expected_30=12.0, below=False))
        self.assertEqual(actions(out), {"2025-26": "close"})
        self.assertEqual(ra.outstanding(out), (False, ""))
        self.assertTrue(discord.posts[-1]["recovered"])
        # A small expectation never asks for fewer than 3.
        gh2, discord2 = SimGh(), Discord()
        gh2.now = datetime(2026, 11, 25, 12, tzinfo=timezone.utc)
        ra.act(years={"2025-26": self.arrivals_ysum(count_30=0, expected_30=12.0, below=True)},
               reports={}, current_year="2025-26", repo="o/r", test_mode=False, dry_run=False,
               assignee="santhonys", runner=gh2, fallback_report="R", discord=discord2, now=gh2.now)
        self.assertEqual(actions(self.step(gh2, discord2, self.arrivals_ysum(
            count_30=2, expected_30=5.0, below=False, window=60, checked=False))), {"2025-26": "update"})
        self.assertEqual(actions(self.step(gh2, discord2, self.arrivals_ysum(
            count_30=3, expected_30=5.0, below=False, window=60, checked=False))), {"2025-26": "close"})
        # A larger expectation asks for more: 0.4 x 40 = 16.
        gh3, discord3 = self.open_with_arrivals()
        self.assertEqual(actions(self.step(gh3, discord3, self.arrivals_ysum(
            count_30=15, expected_30=40.0, below=False))), {"2025-26": "update"})
        self.assertEqual(actions(self.step(gh3, discord3, self.arrivals_ysum(
            count_30=16, expected_30=40.0, below=False))), {"2025-26": "close"})

    def test_no_flapping_when_expected_crosses_ten(self) -> None:
        gh, discord = self.open_with_arrivals()
        created = gh.created
        for day in range(40):
            expected = 10.4 if day % 2 == 0 else 9.6  # the boundary the window switches at
            checked = expected >= 10
            ys = self.arrivals_ysum(count_30=2, expected_30=expected,
                                    below=checked and 2 < 0.25 * expected,
                                    window=30 if checked else 60, checked=checked)
            out = self.step(gh, discord, ys)
            self.assertIn(actions(out)["2025-26"], ("update", "renotify"))
        self.assertEqual(sum(1 for a in gh.issues.values() if a["open"]), 1)
        # Only the 30-day cadence ever replaced it: one extra issue in 40 days.
        self.assertEqual(gh.created - created, 1)
        self.assertFalse(any(p["recovered"] for p in discord.posts))

    def test_an_issue_not_opened_for_arrivals_is_not_held_by_them(self) -> None:
        # A renewal issue (no arrivals marker) closes as soon as it recovers.
        gh, discord = FakeGh([issue(12)]), Discord()
        ys = self.arrivals_ysum(count_30=0, expected_30=30.0, below=False)
        self.assertEqual(actions(run({"2025-26": ys}, gh, discord)), {"2025-26": "close"})

    def test_the_october_stop_stays_open_through_december(self) -> None:
        """Replay a frozen archive: its last arrivals land on 2026-10-25."""
        from tools.ops import discovery_renewal as dr
        rows = []
        for i in range(500):
            rows.append(_row(f"s{i}", "2023-24"))
            rows.append({**_row(f"s{i}", "2024-25"), "discovered_at": "2026-01-10T00:00:00+00:00"})
            rows.append({**_row(f"s{i}", "2025-26"), "discovered_at": "2026-10-25T12:00:00+00:00"})
        gh, discord = SimGh(), Discord()
        opened = None
        day = date(2026, 10, 25)
        while day <= date(2026, 12, 31):
            res = dr.compute(rows, day)
            years = {dr.format_year(y): dr.year_summary(c, res.arrivals if y == res.current_year else None)
                     for y, c in res.year_checks.items()}
            gh.now = datetime(day.year, day.month, day.day, 13, 41, tzinfo=timezone.utc)
            out = ra.act(years=years, reports={}, current_year="2025-26", repo="o/r",
                         test_mode=False, dry_run=False, assignee="santhonys", runner=gh,
                         fallback_report="R", discord=discord, now=gh.now)
            if opened is None and gh.created:
                opened = day
            if opened:
                self.assertEqual(sum(1 for i in gh.issues.values() if i["open"]), 1, day)
                self.assertIn("2025-26", ra.outstanding(out)[1], day)
            day += timedelta(days=1)
        self.assertIsNotNone(opened)
        self.assertLessEqual(abs((opened - date(2026, 11, 25)).days), 3)
        # It never recovered, and 60-day windows opened and closed under it.
        self.assertFalse(any(p["recovered"] for p in discord.posts))
        (final,) = [i for i in gh.issues.values() if i["open"]]
        self.assertIn(ra.ARRIVALS_OPEN_MARKER, final["body"])



class OutstandingTests(unittest.TestCase):
    def september_2027_rows(self) -> list[dict]:
        """500 schools filed 2024-25; 400 of them 2025-26; all 400 of those
        2026-27. At 2027-09-01 the current year (2026-27) looks perfect while
        2025-26 stays at 80% of its denominator."""
        rows = []
        for i in range(500):
            rows.append(_row(f"s{i}", "2024-25"))
            if i < 400:
                # The 2026-27 files arrived this month, so the arrivals check is quiet.
                rows += [_row(f"s{i}", "2025-26"),
                         {**_row(f"s{i}", "2026-27"), "discovered_at": "2027-08-20T00:00:00+00:00"}]
        return rows

    def run_pipeline(self, tmp: Path, open_issues: list[dict]):
        from tools.ops import discovery_renewal as dr
        (tmp / "m.json").write_text(json.dumps(self.september_2027_rows()))
        self.assertEqual(dr.main(["--manifest-json", str(tmp / "m.json"), "--as-of", "2027-09-01",
                                  "--out-state", str(tmp / "state.json"),
                                  "--out-summary", str(tmp / "summary.json"),
                                  "--out-report", str(tmp / "report.md"),
                                  "--out-year-reports", str(tmp / "yr")]), 0)
        gh = FakeGh(open_issues)
        os.environ.pop("DISCORD_ALERTS_WEBHOOK_URL", None)
        code = ra.main(["--state", str(tmp / "state.json"), "--summary", str(tmp / "summary.json"),
                        "--report", str(tmp / "report.md"), "--year-reports", str(tmp / "yr"),
                        "--repo", "o/r"], runner=gh)
        return code, gh, json.loads((tmp / "summary.json").read_text())

    def test_an_earlier_year_that_is_still_short_stays_outstanding(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            code, gh, summary = self.run_pipeline(Path(d), [issue(12, "2025-26")])
        self.assertEqual(code, 0)
        # The current year looks healthy on every flag the old summary had...
        self.assertFalse(summary["below_floor"])
        self.assertFalse(summary["two_year_below_floor"])
        self.assertIsNot(summary["next_below_floor"], True)
        # ...but the alarm for 2025-26 is open and says so.
        self.assertTrue(summary["outstanding_below_floor"])
        self.assertEqual(summary["outstanding_years"], "2025-26")
        self.assertEqual(summary["alarm_issue"], 12)
        self.assertNotIn("issue close", gh.verbs())

    def test_a_test_mode_dispatch_reports_the_real_labels_issues(self) -> None:
        class TwoLabels(FakeGh):
            def __call__(self, args):
                if args[0] == "api":
                    self.calls.append(args)
                    label = next(a for a in args if a.startswith("labels=")).split("=", 1)[1]
                    rows = [{**i, "html_url": i["url"]} for i in self.by_label.get(label, [])]
                    return subprocess.CompletedProcess(args, 0, json.dumps(rows), "")
                return super().__call__(args)

        for real_issues, expect in (([issue(12, "2025-26")], (True, "2025-26")), ([], (False, ""))):
            with tempfile.TemporaryDirectory() as d:
                gh = TwoLabels()
                gh.by_label = {ra.ALARM_LABEL: real_issues, ra.TEST_LABEL: []}
                tmp = Path(d)
                years = {"2025-26": HEALTHY}
                (tmp / "state.json").write_text(json.dumps({"years": years, "current_year": "2025-26",
                                                            "below_floor": False}))
                (tmp / "summary.json").write_text(json.dumps({"current_year": "2025-26"}))
                (tmp / "report.md").write_text("R")
                os.environ.pop("DISCORD_ALERTS_WEBHOOK_URL", None)
                code = ra.main(["--state", str(tmp / "state.json"), "--summary", str(tmp / "summary.json"),
                                "--report", str(tmp / "report.md"), "--repo", "o/r", "--test-mode"],
                               runner=gh)
                summary = json.loads((tmp / "summary.json").read_text())
            self.assertEqual(code, 0)
            self.assertEqual((summary["outstanding_below_floor"], summary["outstanding_years"]), expect)
            self.assertIsNone(summary["alarm_issue"])
            listed = [a for c in gh.calls if c[0] == "api" for a in c if a.startswith("labels=")]
            self.assertIn(f"labels={ra.ALARM_LABEL}", listed)  # the real label is read, read only
            self.assertFalse(any(" ".join(c[:2]) in ("issue close", "issue edit") for c in gh.calls))

    def test_a_retired_real_issue_is_not_outstanding_in_a_test_run(self) -> None:
        out = ra.real_outstanding({"2025-26": HEALTHY}, "2025-26", "o/r",
                                  lambda args: subprocess.CompletedProcess(
                                      args, 0, json.dumps([{**issue(8, "2019-20"), "html_url": "u"}]), ""),
                                  {"actions": []})
        self.assertEqual(out, (False, ""))

    def test_nothing_outstanding_when_every_year_is_fine(self) -> None:
        outcome = {"actions": [{"year": "2025-26", "action": "close", "issue": None},
                               {"year": "2026-27", "action": "none", "issue": None}]}
        self.assertEqual(ra.outstanding(outcome), (False, ""))

    def test_outstanding_lists_every_open_year_in_order(self) -> None:
        outcome = {"actions": [{"year": "2026-27", "action": "create", "issue": 5},
                               {"year": "2025-26", "action": "update", "issue": 4},
                               {"year": "2024-25", "action": "skip", "issue": 3}]}
        self.assertEqual(ra.outstanding(outcome), (True, "2024-25,2025-26,2026-27"))

    def test_an_earlier_year_below_the_flat_floor_with_no_issue_is_not_outstanding(self) -> None:
        self.assertEqual(ra.outstanding({"actions": []}), (False, ""))


def _row(school: str, year: str) -> dict:
    return {"school_id": school, "canonical_year": year, "participation_status": "published",
            "removed_at": None, "discovered_at": None}


class DiscordHelperTests(unittest.TestCase):
    def test_missing_secret_warns_and_never_prints_a_url(self) -> None:
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
        def poster(url, payload):
            raise notify_discord.DiscordPostError("HTTP 500")

        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            self.assertFalse(notify_discord.post_custom_embed(
                title="a", fields=[], webhook_url="https://hook/secret", poster=poster))
        self.assertNotIn("secret", err.getvalue())


if __name__ == "__main__":
    unittest.main()
