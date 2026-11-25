import unittest
from unittest import mock

from tools.ops import hand_check_sample as h


def rows(*pairs):
    return [{"school_id": s, "school_name": s.title(), "canonical_year": y} for s, y in pairs]


class NewestYearTests(unittest.TestCase):
    def test_unknown_never_wins_over_a_real_year(self):
        # "unknown" sorts above "2025-26" as text; it must be ignored.
        got = h.newest_years(rows(("a", "2024-25"), ("a", "unknown"), ("a", "2023-24")))
        self.assertEqual(got["a"], "2024-25")

    def test_picks_the_later_of_two_valid_years_across_a_century(self):
        got = h.newest_years(rows(("a", "1999-00"), ("a", "2000-01")))
        self.assertEqual(got["a"], "2000-01")

    def test_year_with_wrong_suffix_or_trailing_newline_is_invalid(self):
        self.assertIsNone(h.start_year("2025-27"))
        self.assertIsNone(h.start_year("2025-26\n"))
        self.assertEqual(h.start_year("1999-00"), 1999)

    def test_malformed_long_year_is_ignored_not_compared(self):
        # As text "2025-2026" sorts above "2024-25"; it is not a valid year.
        got = h.newest_years(rows(("a", "2024-25"), ("a", "2025-2026"), ("a", "unknown")))
        self.assertEqual(got["a"], "2024-25")

    def test_only_unknown_is_undated(self):
        got = h.newest_years(rows(("a", "unknown"), ("b", None)))
        self.assertIsNone(got["a"])
        self.assertIsNone(got["b"])

    def test_malformed_year_is_ignored(self):
        got = h.newest_years(rows(("a", "2025"), ("a", "2022-23")))
        self.assertEqual(got["a"], "2022-23")


class PickTests(unittest.TestCase):
    def setUp(self):
        self.newest = {f"s{i:03d}": "2024-25" for i in range(100)}

    def test_same_month_same_picks_and_twenty_distinct(self):
        a = h.pick_schools(self.newest, "2026-11")
        self.assertEqual(a, h.pick_schools(self.newest, "2026-11"))
        self.assertEqual(len(set(a)), 20)

    def test_other_month_differs(self):
        self.assertNotEqual(h.pick_schools(self.newest, "2026-11"), h.pick_schools(self.newest, "2026-12"))

    def test_too_few_schools_is_an_error(self):
        with self.assertRaises(ValueError):
            h.pick_schools({"a": "2024-25"}, "2026-11")

    def test_bad_month_is_an_error(self):
        with self.assertRaises(ValueError):
            h.pick_schools(self.newest, "2026-13")


class RenderTests(unittest.TestCase):
    PICKS = [
        {"school_id": "alpha", "name": "Alpha College", "newest_year": "2024-25",
         "domain": "alpha.edu", "seed_url": "https://alpha.edu/cds"},
        {"school_id": "beta", "name": "Beta U", "newest_year": None, "domain": None, "seed_url": None},
    ]

    def test_block_has_links_and_three_boxes(self):
        body = h.render_issue(self.PICKS, "2026-11")
        self.assertIn("https://www.collegedata.fyi/schools/alpha", body)
        self.assertIn("https://alpha.edu\n", body)
        self.assertIn("https://alpha.edu/cds", body)
        self.assertIn("site%3Aalpha.edu+%22common+data+set%22", body)
        self.assertIn("Our newest year: undated only", body)
        self.assertEqual(body.count("- [ ] "), 8)
        self.assertIn("none on file", body)
        # newest-year document link only for a school with a dated year
        self.assertIn("https://www.collegedata.fyi/schools/alpha/2024-25", body)
        self.assertNotIn("/schools/beta/", body)
        self.assertIn("not a full CDS", body)

    def test_first_hand_check_has_no_miss_line_with_numbers(self):
        self.assertIn("no earlier hand check", h.render_issue(self.PICKS, "2026-11"))


class MissRateTests(unittest.TestCase):
    def sample(self):
        # alpha: miss, beta: nothing newer, gamma: couldn't tell, delta: blank
        def block(sid, a, b, c):
            return (f"### {sid}\n<!-- hand-check-school:{sid} -->\n\n- Our page: x\n\n"
                    f"- [{a}] {h.LABEL_MISS}\n- [{b}] {h.LABEL_NONE}\n- [{c}] {h.LABEL_UNSURE}\n\n")
        return (block("alpha", "x", " ", " ") + block("beta", " ", "X", " ")
                + block("gamma", " ", " ", "x") + block("delta", " ", " ", " "))

    def test_counts(self):
        self.assertEqual(h.count_answers(self.sample()), (1, 2, 2, 0))

    def test_line_at_top_of_new_issue(self):
        body = h.render_issue(RenderTests.PICKS, "2026-12", self.sample())
        self.assertTrue(body.startswith("Last month: 1 misses of 2 answered (2 unanswered), 0 false greens\n"))

    def test_unreadable_body_raises_instead_of_zero_misses(self):
        with self.assertRaises(ValueError):
            h.count_answers("some other issue with - [x] boxes but no school markers")

    def test_roundtrip_of_our_own_rendering(self):
        body = h.render_issue(RenderTests.PICKS, "2026-11")
        self.assertEqual(h.count_answers(body), (0, 0, 2, 0))
        ticked = body.replace(f"- [ ] {h.LABEL_MISS}", f"- [x] {h.LABEL_MISS}", 1)
        self.assertEqual(h.count_answers(ticked), (1, 1, 1, 0))


class AnswerParsingTests(unittest.TestCase):
    def body(self, *boxes):
        lines = ["<!-- hand-check-school:alpha -->"]
        lines += [f"- [{m}] {t}" for m, t in boxes]
        return "\n".join(lines) + "\n"

    def test_note_after_label_and_curly_apostrophe_still_count(self):
        b = self.body(("x", h.LABEL_MISS + " \u2014 moved to /ir/cds"), (" ", h.LABEL_NONE))
        self.assertEqual(h.count_answers(b), (1, 1, 0, 0))
        b = self.body((" ", h.LABEL_MISS), ("x", "nothing newer posted, checked twice"), (" ", "couldn\u2019t tell"))
        self.assertEqual(h.count_answers(b), (0, 1, 0, 0))
        b = self.body(("x", "couldn\u2019t tell"))
        self.assertEqual(h.count_answers(b), (0, 0, 1, 0))

    def test_false_green_counts_with_any_answer_and_alone(self):
        fg = h.LABEL_FALSE_GREEN
        body = (self.body(("x", h.LABEL_NONE), ("x", fg)) + self.body(("x", fg))
                + self.body(("x", h.LABEL_NONE)))
        # same school id three times collapses to one block, so use distinct ids
        body = (body.replace("school:alpha", "school:a", 1).replace("school:alpha", "school:b", 1)
                .replace("school:alpha", "school:c", 1))
        self.assertEqual(h.count_answers(body), (0, 2, 1, 2))
        top = h.render_issue(RenderTests.PICKS, "2026-12", body).splitlines()[0]
        self.assertEqual(top, "Last month: 0 misses of 2 answered (1 unanswered), 2 false greens")

    def test_ticked_box_matching_no_label_raises(self):
        with self.assertRaises(ValueError):
            h.count_answers(self.body(("x", "something else entirely")))

    def test_miss_and_nothing_newer_both_ticked_raises(self):
        with self.assertRaises(ValueError):
            h.count_answers(self.body(("x", h.LABEL_MISS), ("x", h.LABEL_NONE)))


class PreviousIssueTests(unittest.TestCase):
    def test_marker_filters_and_picks_newest_earlier(self):
        issues = [
            {"body": "<!-- hand-check-month:2026-11 -->\nx"},
            {"body": "unrelated issue with the label"},
            {"body": "<!-- hand-check-month:2026-10 -->\nnewest earlier"},
            {"body": "<!-- hand-check-month:2026-09 -->\nolder"},
        ]
        exists, prev = h.split_issues(issues, "2026-11")
        self.assertTrue(exists)
        self.assertIn("newest earlier", prev)
        exists, prev = h.split_issues(issues[1:2], "2026-11")
        self.assertEqual((exists, prev), (False, None))

    def test_rendered_body_carries_its_month_marker(self):
        self.assertEqual(h.month_of(h.render_issue(RenderTests.PICKS, "2026-11")), "2026-11")


class FetchTests(unittest.TestCase):
    def fake_urlopen(self, pages, total_header):
        calls = iter(pages)

        def opener(req, timeout=0):
            import io, json
            page = next(calls)
            resp = io.BytesIO(json.dumps(page).encode())
            resp.headers = {"Content-Range": total_header(page)}
            resp.__enter__ = lambda s=resp: s
            resp.__exit__ = lambda *a: None
            return resp

        return opener

    def test_short_read_raises(self):
        # Header claims 5 rows, server returns 2 and then nothing.
        op = self.fake_urlopen([[{"school_id": "a"}, {"school_id": "b"}], []], lambda p: "0-1/5")
        with mock.patch.object(h.urllib.request, "urlopen", op):
            with self.assertRaises(RuntimeError):
                h.fetch_live_rows("https://x", "k")

    def test_zero_rows_raises(self):
        op = self.fake_urlopen([[]], lambda p: "*/0")
        with mock.patch.object(h.urllib.request, "urlopen", op):
            with self.assertRaises(RuntimeError):
                h.fetch_live_rows("https://x", "k")

    def test_multi_page_read_advances_range_and_keeps_rows_unique(self):
        import io, json
        data = [{"school_id": f"s{i}"} for i in range(5)]
        ranges = []

        def opener(req, timeout=0):
            lo, hi = (int(x) for x in req.get_header("Range").split("-"))
            ranges.append((lo, hi))
            page = data[lo:hi + 1]
            resp = io.BytesIO(json.dumps(page).encode())
            resp.headers = {"Content-Range": f"{lo}-{lo + len(page) - 1}/{len(data)}"}
            resp.__enter__ = lambda s=resp: s
            resp.__exit__ = lambda *a: None
            return resp

        with mock.patch.object(h, "PAGE_SIZE", 2), mock.patch.object(h.urllib.request, "urlopen", opener):
            got = h.fetch_live_rows("https://x", "k")
        self.assertEqual(ranges, [(0, 1), (2, 3), (4, 5)])
        self.assertEqual([r["school_id"] for r in got], [r["school_id"] for r in data])

    def test_misaligned_page_raises(self):
        # Server restarts at 0 on the second request: offset must be checked.
        op = self.fake_urlopen([[{"school_id": "a"}], [{"school_id": "a"}]], lambda p: "0-0/2")
        with mock.patch.object(h, "PAGE_SIZE", 1), mock.patch.object(h.urllib.request, "urlopen", op):
            with self.assertRaises(RuntimeError):
                h.fetch_live_rows("https://x", "k")

    def test_full_read_ok(self):
        op = self.fake_urlopen([[{"school_id": "a"}, {"school_id": "b"}]], lambda p: "0-1/2")
        with mock.patch.object(h.urllib.request, "urlopen", op):
            self.assertEqual(len(h.fetch_live_rows("https://x", "k")), 2)


class BuildPicksTests(unittest.TestCase):
    def test_school_missing_from_yaml_raises(self):
        data = rows(*[(f"s{i}", "2024-25") for i in range(25)])
        with self.assertRaises(RuntimeError):
            h.build_picks(data, {}, "2026-11")


if __name__ == "__main__":
    unittest.main()
