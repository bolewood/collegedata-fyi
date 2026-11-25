from __future__ import annotations

import contextlib
import io
import json
import subprocess
import unittest

from tools.ops import consecutive_failures as cf


def run(run_id: int, conclusion: str, status: str = "completed") -> dict:
    return {"databaseId": run_id, "conclusion": conclusion, "status": status}


def failing(n: int, *, start: int = 100) -> list[dict]:
    return [run(start - i, "failure") for i in range(n)]


class StreakTests(unittest.TestCase):
    def test_counts_failures_back_to_the_last_success(self) -> None:
        runs = [run(200, "", "in_progress")] + failing(3, start=199) + [run(150, "success")] + failing(5, start=140)
        self.assertEqual(cf.prior_failure_streak(runs, 200), 3)

    def test_the_current_run_is_not_counted_twice(self) -> None:
        runs = [run(200, "failure")] + failing(2, start=199)
        self.assertEqual(cf.prior_failure_streak(runs, 200), 2)

    def test_cancelled_and_skipped_runs_say_nothing(self) -> None:
        runs = [run(5, "failure"), run(4, "cancelled"), run(3, "skipped"), run(2, "failure"), run(1, "success")]
        self.assertEqual(cf.prior_failure_streak(runs, 99), 2)

    def test_a_success_right_before_means_no_streak(self) -> None:
        self.assertEqual(cf.prior_failure_streak([run(5, "success")] + failing(4, start=4), 99), 0)
        self.assertEqual(cf.prior_failure_streak([], 99), 0)

    def test_timeouts_are_failures(self) -> None:
        self.assertEqual(cf.prior_failure_streak([run(2, "timed_out"), run(1, "startup_failure")], 99), 2)

    def test_every_seventh_failure_posts(self) -> None:
        self.assertEqual([n for n in range(1, 30) if cf.should_post(n, 7)], [7, 14, 21, 28])
        self.assertFalse(cf.should_post(0, 7))

    def test_only_a_new_week_posts_when_the_previous_streak_is_known(self) -> None:
        # Day by day, with each day's streak compared with the day before.
        posted = [n for n in range(1, 30) if cf.should_post(n, 7, n - 1)]
        self.assertEqual(posted, [7, 14, 21, 28])
        # A streak that did not move (7 then 7) never posts twice.
        self.assertTrue(cf.should_post(7, 7, 6))
        self.assertFalse(cf.should_post(7, 7, 7))
        self.assertFalse(cf.should_post(8, 7, 7))

    def test_cancelled_runs_do_not_stop_or_freeze_the_count(self) -> None:
        # Failures separated by cancelled and skipped runs still add up to 14.
        runs = []
        number = 300
        for i in range(13):
            runs.append(run(number, "failure"))
            number -= 1
            runs.append(run(number, "cancelled" if i % 2 else "skipped"))
            number -= 1
        runs.append(run(number, "success"))
        self.assertEqual(cf.streak_info(runs, 999), (13, False))

    def test_a_list_that_ends_without_a_success_is_flagged_as_truncated(self) -> None:
        self.assertEqual(cf.streak_info(failing(5), 999), (5, True))
        self.assertEqual(cf.streak_info(failing(5) + [run(1, "success")], 999), (5, False))


class MainTests(unittest.TestCase):
    def call(self, runs: list[dict], *, returncode: int = 0):
        posts: list[dict] = []

        def runner(args):
            return subprocess.CompletedProcess(args, returncode, json.dumps(runs), "")

        err = io.StringIO()
        with contextlib.redirect_stderr(err), contextlib.redirect_stdout(io.StringIO()):
            code = cf.main(
                ["--repo", "o/r", "--workflow", "Ops discovery renewal", "--run-id", "200",
                 "--run-url", "https://run"],
                runner=runner, discord=lambda **p: posts.append(p) or True,
            )
        return code, err.getvalue(), posts

    def test_a_first_failure_is_quiet(self) -> None:
        code, err, posts = self.call([run(200, "", "in_progress"), run(199, "success")])
        self.assertEqual((code, posts), (0, []))
        self.assertNotIn("::error::", err)

    def test_a_second_day_prints_the_error_annotation_but_does_not_post(self) -> None:
        code, err, posts = self.call([run(200, "", "in_progress"), run(199, "failure"), run(198, "success")])
        self.assertEqual(code, 0)
        self.assertIn("::error::renewal check has failed 2 days running", err)
        self.assertEqual(posts, [])

    def test_the_seventh_day_posts_to_discord(self) -> None:
        code, err, posts = self.call([run(200, "", "in_progress")] + failing(6, start=199))
        self.assertEqual(code, 0)
        self.assertIn("has failed 7 days running", err)
        self.assertEqual(len(posts), 1)
        self.assertIn("7 days running", posts[0]["title"])

    def test_the_sixth_and_eighth_days_do_not_post(self) -> None:
        for prior in (5, 7):
            _, _, posts = self.call([run(200, "", "in_progress")] + failing(prior, start=199))
            self.assertEqual(posts, [], prior)

    def test_it_asks_for_far_more_runs_than_the_old_limit_of_40(self) -> None:
        asked = []

        def runner(args):
            asked.append(args)
            return subprocess.CompletedProcess(args, 0, "[]", "")

        with contextlib.redirect_stdout(io.StringIO()):
            cf.main(["--repo", "o/r", "--workflow", "w", "--run-id", "1"], runner=runner)
        self.assertGreaterEqual(int(asked[0][asked[0].index("--limit") + 1]), 400)

    def test_days_42_and_49_post_beyond_the_old_history_limit(self) -> None:
        for days in (42, 49):
            code, err, posts = self.call([run(1000, "", "in_progress")] + failing(days - 1, start=999)
                                         + [run(5, "success")])
            self.assertEqual(code, 0)
            self.assertIn(f"has failed {days} days running", err)
            self.assertEqual(len(posts), 1, days)
        # And the days in between stay quiet.
        for days in (41, 43, 48, 50):
            _, _, posts = self.call([run(1000, "", "in_progress")] + failing(days - 1, start=999)
                                    + [run(5, "success")])
            self.assertEqual(posts, [], days)

    def test_a_streak_longer_than_the_listing_is_reported_with_a_plus(self) -> None:
        runs = [run(9000, "", "in_progress")] + failing(cf.LIST_LIMIT, start=8999)
        _, err, _ = self.call(runs)
        self.assertIn(f"has failed {cf.LIST_LIMIT + 1}+ days running", err)

    def test_cancelled_runs_in_the_window_do_not_cause_daily_posts(self) -> None:
        # Day 8 after a day-7 post, with cancelled runs sprinkled in: quiet.
        runs = [run(1000, "", "in_progress")]
        for i in range(7):
            runs += [run(990 - 2 * i, "failure"), run(989 - 2 * i, "cancelled")]
        runs.append(run(5, "success"))
        _, err, posts = self.call(runs)
        self.assertIn("has failed 8 days running", err)
        self.assertEqual(posts, [])

    def test_a_lookup_failure_never_fails_the_job(self) -> None:
        code, err, posts = self.call([], returncode=1)
        self.assertEqual((code, posts), (0, []))
        self.assertIn("::warning::", err)


if __name__ == "__main__":
    unittest.main()
