"""Tests for the scholarship change monitor (PRD 036 M4). No network, no database.

The fetcher gets an injected transport; the store is a fake with the same three
methods as SupabaseCheckStore.
"""

from __future__ import annotations

import copy
import datetime as dt
import hashlib
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import model  # noqa: E402
import monitor  # noqa: E402
import validate as v  # noqa: E402
from tools.common.polite_fetch import PoliteFetcher, Response  # noqa: E402

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "valid"
PROGRAM = "fixture-foundation-program"
VERSION = "fixture-foundation-program-2027"
S_SCHOOL = "https://admission.virginia.edu/affordability/fixture-page"
S_FOUND = "https://www.jeffersonscholars.org/scholarships/fixture-faq"
ROBOTS_SCHOOL = "https://admission.virginia.edu/robots.txt"
ROBOTS_FOUND = "https://www.jeffersonscholars.org/robots.txt"
TODAY = dt.date(2026, 11, 14)  # current entry year 2027
NOW = dt.datetime(2026, 11, 14, 12, 0, tzinfo=dt.timezone.utc)

PAGE = (
    "<html><head><title>x</title></head><body><nav>Menu Home</nav><main>"
    "<h1>Fixture Scholars 2027</h1>"
    "<p>The scholarship covers $12,000 per year. The application deadline is December 1, 2026. "
    "Awards are competitive.</p>"
    "<p>Applicants complete the online form, submit transcripts and one recommendation, and attend "
    "an interview with the selection committee before the finalist weekend on campus.</p>"
    "</main><footer>Contact us</footer></body></html>"
)


def html(body: str = PAGE) -> Response:
    return Response(200, {"content-type": "text/html; charset=utf-8"}, body.encode())


class Net:
    """Scripted transport: url -> list of responses (last one repeats)."""

    def __init__(self, routes: Dict[str, Any]):
        self.routes = {k: (list(v) if isinstance(v, list) else [v]) for k, v in routes.items()}
        self.calls: List[tuple] = []

    def transport(self, method, url, headers, timeout):
        self.calls.append((url, dict(headers)))
        q = self.routes[url]
        r = q.pop(0) if len(q) > 1 else q[0]
        if isinstance(r, Exception):
            raise r
        return r

    def fetcher(self, cache: Optional[dict] = None) -> PoliteFetcher:
        return PoliteFetcher(
            "scholarship-monitor",
            transport=self.transport,
            clock=lambda: 1_800_000_000.0,
            sleep=lambda s: None,
            min_spacing=0,
            cache=cache if cache is not None else {},
        )


def routes(school: Any = None, found: Any = None, robots_school: Any = None, robots_found: Any = None) -> Dict[str, Any]:
    return {
        ROBOTS_SCHOOL: robots_school or Response(404),
        ROBOTS_FOUND: robots_found or Response(404),
        S_SCHOOL: school or html(),
        S_FOUND: found or html(),
    }


class FakeStore(monitor.CheckStore):
    def __init__(self):
        self.rows: List[Dict[str, Any]] = []
        self.refreshes = 0
        self.inserts = 0

    unloaded: set = set()

    def known_versions(self):
        every = {(r["program_id"], r["version_id"]) for r in self.rows}
        return (every | {(PROGRAM, VERSION), ("other-program", "other-program-2027")}) - self.unloaded

    def latest(self, program_id, version_id):
        mine = [r for r in self.rows if r["program_id"] == program_id and r["version_id"] == version_id]
        return mine[-1] if mine else None

    def insert(self, rows):
        self.inserts += 1
        self.rows.extend(copy.deepcopy(rows))

    def refresh(self):
        self.refreshes += 1


@pytest.fixture()
def ds() -> model.Dataset:
    docs = {
        str(p): v.load_yaml_text(p.read_text(encoding="utf-8"))
        for p in sorted(FIXTURES.glob("*/*.yaml"))
    }
    return model.build_dataset(docs, root=v.REPO_ROOT)


@pytest.fixture()
def version(ds) -> Dict[str, Any]:
    return next(r for r in model.select_published(ds) if r["version_id"] == VERSION)


def check(version, net: Net, store: Optional[FakeStore] = None, today=TODAY) -> Dict[str, Any]:
    """One monitor pass over a single version; returns the written row."""
    store = store if store is not None else FakeStore()
    res = monitor.run([version], store, net.fetcher(), today, NOW)
    store.rows.extend(res.rows)  # run() does not write; main() does
    check.findings = res.findings  # type: ignore[attr-defined]
    return res.rows[0]


def src(row: Dict[str, Any], source_id: str = "s-school") -> Dict[str, Any]:
    return next(s for s in row["detail"]["sources"] if s["source_id"] == source_id)


# ------------------------------------------------------------------ first run


def test_first_run_records_baseline_only(version):
    row = check(version, Net(routes()))
    assert row["result"] == "unchanged" and row["needs_review"] is False
    assert row["detail"]["baseline_only"] is True and row["detail"]["first_run"] is True
    s = src(row)
    assert s["change"] == "baseline" and s["normalizer_version"] == monitor.NORMALIZER_VERSION
    assert s["parsers"] == monitor.parser_fingerprint()
    assert s["raw_sha256"] and s["text_sha256"]
    assert s["tokens"]["amounts"] == ["$12000"] and "dec 1 2026" in s["tokens"]["dates"]
    assert check.findings == []  # type: ignore[attr-defined]


def test_yaml_hash_is_the_raw_baseline_when_present(version):
    body = PAGE.encode()
    good = copy.deepcopy(version)
    good["record"]["sources"][0]["content_sha256"] = hashlib.sha256(body).hexdigest()
    row = check(good, Net(routes()))
    assert src(row)["yaml_content_sha256"] == "match" and "raw_differs_from_yaml" not in src(row)
    assert row["result"] == "unchanged" and row["needs_review"] is False

    bad = copy.deepcopy(version)
    bad["record"]["sources"][0]["content_sha256"] = "0" * 64
    row = check(bad, Net(routes()))
    # no text baseline: markup cannot be told from terms, so record and do not flag
    assert src(row)["raw_differs_from_yaml"] is True
    assert row["result"] == "unchanged" and row["needs_review"] is False


# ------------------------------------------------------------- change detection


def test_markup_only_change_is_unchanged(version):
    store = FakeStore()
    check(version, Net(routes()), store)
    noisy = PAGE.replace("<p>", "<p class='x' data-ts='123'>").replace(
        "<main>", "<!-- build 9 --><script>var a=1;</script><main>"
    ).replace("The scholarship", "The   scholarship\n")
    row = check(version, Net(routes(school=html(noisy), found=html(noisy))), store)
    assert row["result"] == "unchanged" and row["needs_review"] is False
    assert src(row)["change"] == "markup_only"
    assert check.findings == []  # type: ignore[attr-defined]


def test_amount_change_needs_review_with_diff(version):
    store = FakeStore()
    check(version, Net(routes()), store)
    row = check(version, Net(routes(school=html(PAGE.replace("$12,000", "$9,500")))), store)
    assert row["result"] == "changed" and row["needs_review"] is True
    s = src(row)
    assert s["change"] == "text_changed"
    assert s["diff"]["amounts"] == {"added": ["$9500"], "removed": ["$12000"]}
    f = check.findings[0]  # type: ignore[attr-defined]
    assert f["kind"] == "changed"
    assert f["changed_sources"][0]["archive_save_url"] == "https://web.archive.org/save/" + S_SCHOOL
    md = monitor.findings_markdown(check.findings, TODAY)  # type: ignore[attr-defined]
    assert "$9500" in md and "web.archive.org/save/" + S_SCHOOL in md


def test_date_and_selection_word_change(version):
    store = FakeStore()
    check(version, Net(routes()), store)
    changed = PAGE.replace("December 1, 2026", "November 15, 2026").replace("competitive", "guaranteed")
    row = check(version, Net(routes(school=html(changed))), store)
    d = src(row)["diff"]
    assert d["dates"] == {"added": ["nov 15 2026"], "removed": ["dec 1 2026"]}
    assert d["selection_words"] == {"added": ["guaranteed"], "removed": ["competitive"]}
    assert row["needs_review"] is True


def _flag_test(version, old: str, new: str, expect: str, key: str = "thresholds"):
    page = PAGE.replace("</main>", f"<p>{old}</p></main>")
    store = FakeStore()
    check(version, Net(routes(school=html(page))), store)
    row = check(version, Net(routes(school=html(page.replace(old, new)))), store)
    assert row["needs_review"] is True and row["result"] == "changed"
    assert expect in src(row)["diff"][key]["added"]


def test_renewal_gpa_change_flags(version):
    _flag_test(version, "Scholars must keep a cumulative GPA of 3.0 to renew.",
               "Scholars must keep a cumulative GPA of 3.2 to renew.", "gpa 3.2")


def test_sat_minimum_change_flags(version):
    _flag_test(version, "A minimum SAT score of 1400 is expected.", "A minimum SAT score of 1450 is expected.", "sat 1450")


def test_award_count_change_flags(version):
    _flag_test(version, "We select 25 awards each year.", "We select 20 awards each year.", "awards 20")


def test_unrelated_numbers_do_not_flag(version):
    old = "Questions? Call the office at 555-0100 or visit us. This page has had 12,345 visitors."
    page = PAGE.replace("</main>", f"<p>{old}</p></main>")
    store = FakeStore()
    check(version, Net(routes(school=html(page))), store)
    new = old.replace("555-0100", "555-0199").replace("12,345", "13,001")
    row = check(version, Net(routes(school=html(page.replace(old, new)))), store)
    assert row["needs_review"] is False and src(row)["change"] == "text_changed_no_terms"


def test_wording_change_that_touches_no_token_does_not_flag(version):
    store = FakeStore()
    check(version, Net(routes()), store)
    row = check(version, Net(routes(school=html(PAGE.replace("Awards are", "Awards are very")))), store)
    assert row["result"] == "unchanged" and row["needs_review"] is False
    assert src(row)["change"] == "text_changed_no_terms"
    assert check.findings == []  # type: ignore[attr-defined]
    # the baseline moved, so the next identical fetch is quiet too
    row = check(version, Net(routes(school=html(PAGE.replace("Awards are", "Awards are very")))), store)
    assert src(row)["change"] == "none"


def test_banner_and_updated_date_churn_does_not_flag(version):
    base = (
        "<html><body><header>Site header</header><div class='alert-banner'>Campus closed Monday</div>"
        "<div class='page'><h1>Fixture Scholars 2027</h1>"
        "<p>The scholarship covers $12,000 per year. The application deadline is December 1, 2026. "
        "Awards are competitive and applicants complete the online form with transcripts, one recommendation "
        "and an interview with the selection committee.</p>"
        "<div class='latest-news'>Story one about robotics</div>"
        "<p>Page last updated November 3, 2026</p></div></body></html>"
    )
    noisy = (
        base.replace("Campus closed Monday", "Snow day: campus closed Tuesday January 5")
        .replace("Story one about robotics", "A different story about $5,000 gifts on March 3")
        .replace("November 3, 2026", "November 10, 2026")
    )
    store = FakeStore()
    check(version, Net(routes(school=html(base))), store)
    row = check(version, Net(routes(school=html(noisy))), store)
    assert row["needs_review"] is False and src(row)["change"] in ("none", "markup_only")


def test_aside_deadline_box_is_kept_and_article_with_most_text_is_the_root(version):
    page = (
        "<html><body><article>Related story teaser</article>"
        "<article><h1>Fixture Scholars</h1><p>The scholarship covers $12,000 per year and awards are competitive. "
        "Applicants submit the form, transcripts, a recommendation and attend an interview with the committee "
        "before the finalist weekend on campus in the spring semester.</p>"
        "<aside>Deadline: December 1, 2026</aside></article></body></html>"
    )
    store = FakeStore()
    check(version, Net(routes(school=html(page))), store)
    row = check(version, Net(routes(school=html(page.replace("December 1", "November 1")))), store)
    assert row["needs_review"] is True
    assert src(row)["diff"]["dates"] == {"added": ["nov 1 2026"], "removed": ["dec 1 2026"]}


def test_needs_review_is_carried_until_cleared(version):
    store = FakeStore()
    check(version, Net(routes()), store)
    check(version, Net(routes(school=html(PAGE.replace("$12,000", "$9,500")))), store)
    # the next run sees the new text as its baseline: unchanged text, flag must stay
    row = check(version, Net(routes(school=html(PAGE.replace("$12,000", "$9,500")))), store)
    assert row["needs_review"] is True and row["result"] == "changed"
    assert row["detail"]["needs_review_carried"] is True
    # level-triggered: a still-flagged version is listed on every run, marked as not new
    f = check.findings[0]  # type: ignore[attr-defined]
    assert f["kind"] == "changed" and f["new"] is False and f["changed_sources"] == []
    # a person clears it (runbook): a row with needs_review false and the same baseline
    cleared = copy.deepcopy(store.rows[-1])
    cleared.update(result="unchanged", needs_review=False)
    cleared["detail"].pop("review", None)
    store.rows.append(cleared)
    row = check(version, Net(routes(school=html(PAGE.replace("$12,000", "$9,500")))), store)
    assert row["needs_review"] is False and row["result"] == "unchanged"


def test_normalizer_version_bump_rebaselines_instead_of_flagging(version, monkeypatch):
    store = FakeStore()
    check(version, Net(routes()), store)
    monkeypatch.setattr(monitor, "NORMALIZER_VERSION", 99)
    row = check(version, Net(routes(school=html(PAGE.replace("$12,000", "$9,500")))), store)
    assert row["result"] == "unchanged" and row["needs_review"] is False
    assert src(row)["change"] == "normalizer_rebaseline" and row["detail"]["normalizer_rebaseline"] is True
    assert src(row)["normalizer_version"] == 99


def test_parser_version_change_rebaselines_instead_of_flagging(version, monkeypatch):
    store = FakeStore()
    check(version, Net(routes()), store)
    monkeypatch.setattr(monitor, "parser_fingerprint", lambda: "bs4=9.9;pypdf=9.9")
    row = check(version, Net(routes(school=html(PAGE.replace("$12,000", "$9,500")))), store)
    assert row["needs_review"] is False and src(row)["change"] == "normalizer_rebaseline"


def test_parsers_are_pinned_exactly():
    reqs = (v.REPO_ROOT / "tools" / "ci-requirements.txt").read_text().splitlines()
    for name in ("pypdf", "beautifulsoup4"):
        assert any(line.startswith(name + "==") for line in reqs), name


def test_not_modified_uses_the_baselines_own_validators_and_carries_it(version):
    store = FakeStore()
    etagged = Response(200, {"content-type": "text/html", "etag": '"a"'}, PAGE.encode())
    check(version, Net(routes(school=etagged)), store)
    assert src(store.rows[0])["validators"]["etag"] == '"a"'
    net = Net(routes(school=Response(304)))
    row = check(version, net, store)
    assert dict(net.calls)[S_SCHOOL].get("If-None-Match") == '"a"'
    s = src(row)
    assert s["status"] == "not_modified" and s["fetched"] is False
    assert s["raw_sha256"] == src(store.rows[0])["raw_sha256"] and s["tokens"]["amounts"] == ["$12000"]
    assert s["validators"]["etag"] == '"a"'
    assert row["result"] == "unchanged"


def test_no_validators_are_sent_without_a_baseline(version):
    net = Net(routes())
    check(version, net, FakeStore())
    assert "If-None-Match" not in dict(net.calls)[S_SCHOOL]


def two_versions(version):
    """Two served versions of two programs that cite the same URL."""
    other = copy.deepcopy(version)
    other["program_id"] = "other-program"
    other["version_id"] = "other-program-2027"
    return [version, other]


def test_shared_url_change_reaches_every_version_that_cites_it(version):
    store = FakeStore()
    both = two_versions(version)
    etagged = Response(200, {"content-type": "text/html", "etag": '"a"'}, PAGE.encode())
    res = monitor.run(both, store, Net(routes(school=etagged)).fetcher(), TODAY, NOW)
    store.rows.extend(res.rows)
    new = Response(200, {"content-type": "text/html", "etag": '"b"'}, PAGE.replace("$12,000", "$9,500").encode())
    net = Net(routes(school=new))
    res = monitor.run(both, store, net.fetcher(), TODAY, NOW)
    assert [r["result"] for r in res.rows] == ["changed", "changed"]
    assert [r["needs_review"] for r in res.rows] == [True, True]
    assert [u for u, _ in net.calls].count(S_SCHOOL) == 1  # fetched once per run
    assert "If-None-Match" not in dict(net.calls)[S_SCHOOL]  # a shared fetch is unconditional


def test_milestone_run_does_not_hide_a_change_from_a_later_full_run(version):
    """A run that only refreshes one version's validators must not 304 another's baseline."""
    store = FakeStore()
    both = two_versions(version)
    a_page = Response(200, {"content-type": "text/html", "etag": '"a"'}, PAGE.encode())
    res = monitor.run(both, store, Net(routes(school=a_page)).fetcher(), TODAY, NOW)
    store.rows.extend(res.rows)
    new = Response(200, {"content-type": "text/html", "etag": '"b"'}, PAGE.replace("$12,000", "$9,500").encode())
    # only the first version is rechecked (milestone mode)
    res = monitor.run([both[0]], store, Net(routes(school=new)).fetcher(), TODAY, NOW, "milestones")
    store.rows.extend(res.rows)
    # the full run now sends the *second* version's own validators ("a"), not "b"
    net = Net(routes(school=Response(200, {"content-type": "text/html", "etag": '"b"'}, PAGE.replace("$12,000", "$9,500").encode())))
    res = monitor.run([both[1]], store, net.fetcher(), TODAY, NOW)
    assert dict(net.calls)[S_SCHOOL].get("If-None-Match") == '"a"'
    assert res.rows[0]["result"] == "changed"


# ----------------------------------------------------------------- unreachable


def test_robots_disallow_is_unreachable_not_a_change(version):
    net = Net(routes(robots_school=Response(200, {}, b"User-agent: *\nDisallow: /\n")))
    row = check(version, net)
    assert row["result"] == "unreachable" and row["needs_review"] is False
    s = src(row)
    assert s["status"] == "unreachable" and "robots" in s["reason"]
    assert S_SCHOOL not in [u for u, _ in net.calls]  # never fetched
    assert src(row, "s-foundation")["status"] == "ok"


def test_unreachable_robots_blocks_fetching(version):
    net = Net(routes(robots_school=Response(503), robots_found=Response(503)))
    row = check(version, net)
    assert row["result"] == "unreachable" and row["needs_review"] is False
    assert all("unreachable" in s["reason"] for s in row["detail"]["sources"])
    assert S_SCHOOL not in [u for u, _ in net.calls]


def test_404_is_unreachable_and_never_says_the_program_ended(version):
    row = check(version, Net(routes(school=Response(404), found=Response(404))))
    assert row["result"] == "unreachable" and row["needs_review"] is False
    assert "does not mean the program ended" in src(row)["reason"]


def test_login_wall_is_unreachable(version):
    login = Response(302, {"location": "https://login.example.org/sso"}, b"")
    row = check(version, Net(routes(school=login)))
    assert src(row)["status"] == "unreachable" and "login" in src(row)["reason"].lower()


def test_baseline_survives_an_unreachable_gap(version):
    store = FakeStore()
    check(version, Net(routes()), store)
    gap = check(version, Net(routes(school=Response(404))), store)
    assert src(gap)["raw_sha256"] == src(store.rows[0])["raw_sha256"]
    row = check(version, Net(routes(school=html(PAGE.replace("$12,000", "$9,500")))), store)
    assert row["result"] == "changed" and src(row)["diff"]["amounts"]["added"] == ["$9500"]


# ------------------------------------------------------------------- staleness


def test_heading_older_than_cycle(version):
    page = PAGE.replace("Fixture Scholars 2027", "Class of 2029 Fixture Scholars")  # entry year 2025
    row = check(version, Net(routes(school=html(page))))
    codes = [s["code"] for s in row["detail"]["stale_signals"]]
    assert "heading_year_older_than_cycle" in codes
    assert row["result"] == "stale_signal" and row["needs_review"] is False  # reported, never public
    f = check.findings[0]  # type: ignore[attr-defined]
    assert f["kind"] == "info" and f["stale_signals"]


def test_heading_year_conflicts_with_deadline_years(version):
    page = PAGE.replace("Fixture Scholars 2027", "Fixture Scholars fall 2027").replace(
        "December 1, 2026", "December 1, 2029"
    )
    row = check(version, Net(routes(school=html(page))))
    codes = [s["code"] for s in row["detail"]["stale_signals"]]
    assert "heading_year_conflicts_with_deadline_years" in codes
    assert "heading_year_older_than_cycle" not in codes


def test_all_milestones_past_without_a_next_cycle_year(version):
    late = dt.date(2027, 1, 20)  # entry year 2027 is still current until 1 July 2027
    row = check(version, Net(routes()), today=late)
    assert [s["code"] for s in row["detail"]["stale_signals"]] == ["all_milestones_past_no_next_cycle"]
    assert row["result"] == "stale_signal" and row["needs_review"] is False
    nxt = html(PAGE.replace("</main>", "<p>Applications for the class entering in 2028 open in August.</p></main>"))
    row = check(version, Net(routes(school=nxt)), today=late)
    assert row["detail"]["stale_signals"] == []


def test_no_stale_signal_for_a_version_already_past_cycle(version):
    row = check(version, Net(routes()), today=dt.date(2027, 8, 1))
    assert row["detail"]["stale_signals"] == []


def test_healthy_page_has_no_signal(version):
    row = check(version, Net(routes()))
    assert row["detail"]["stale_signals"] == []


# --------------------------------------------------------- milestone selector


def _with_milestone(version, date: str, requirement: str = "required", kind: str = "application_deadline"):
    v2 = copy.deepcopy(version)
    v2["record"]["application"]["milestones"] = [
        {"kind": kind, "requirement": requirement, "date": date, "precision": "day"}
    ]
    return v2


def _last(days_ago: Optional[int]) -> Optional[dt.date]:
    return None if days_ago is None else TODAY - dt.timedelta(days=days_ago)


@pytest.mark.parametrize(
    "offset, days_since_last_check, expected",
    [
        (30, None, True),
        (30, 5, True),  # last checked before the 30-day mark (today)
        (30, 0, False),  # checked today: the mark is covered
        (7, 8, True),
        (7, 0, False),
        (31, None, False),  # not yet in the window
        (-1, None, False),  # already past
        (29, 3, True),  # the day-30 run never happened: caught up
        (29, 0, False),
        (8, 23, True),  # still waiting for a 7-day mark; the 30-day mark was missed
        (8, 5, False),  # checked since the 30-day mark
        (6, 6, True),  # the day-7 run never happened
        (6, 0, False),
        (0, 8, True),
        (0, 0, False),
    ],
)
def test_milestone_selector_marks_and_catch_up(version, offset, days_since_last_check, expected):
    date = (TODAY + dt.timedelta(days=offset)).isoformat()
    assert monitor.milestone_due(_with_milestone(version, date), TODAY, _last(days_since_last_check)) is expected


def test_milestone_selector_ignores_recommended_and_undated(version):
    date = (TODAY + dt.timedelta(days=30)).isoformat()
    assert monitor.milestone_due(_with_milestone(version, date, "recommended"), TODAY) is False
    assert monitor.milestone_due(_with_milestone(version, date, "priority", "interview"), TODAY) is True
    undated = copy.deepcopy(version)
    undated["record"]["application"]["milestones"] = [
        {"kind": "application_deadline", "requirement": "required", "date": None,
         "recurring": {"month": 12, "day": 1}, "precision": "day"}
    ]
    assert monitor.milestone_due(undated, TODAY) is False


def test_select_versions_modes(ds):
    # fixture required deadline is 2026-12-01
    assert [r["version_id"] for r in monitor.select_versions(ds, "milestones", dt.date(2026, 11, 1))] == [VERSION]
    assert monitor.select_versions(ds, "milestones", dt.date(2026, 10, 31)) == []  # 31 days away
    assert len(monitor.select_versions(ds, "full", TODAY)) == len(model.select_published(ds))
    assert monitor.select_versions(ds, "full", TODAY, only=["nope"]) == []
    assert len(monitor.select_versions(ds, "full", TODAY, limit=1)) == 1


def test_select_versions_uses_the_latest_check_for_catch_up(ds):
    store = FakeStore()
    day = dt.date(2026, 11, 20)  # 11 days before the deadline; the day-30 mark was 2026-11-01
    assert [r["version_id"] for r in monitor.select_versions(ds, "milestones", day, store=store)] == [VERSION]
    store.rows.append({"program_id": PROGRAM, "version_id": VERSION, "checked_at": "2026-11-05T09:00:00Z"})
    assert monitor.select_versions(ds, "milestones", day, store=store) == []
    store.rows[-1]["checked_at"] = "2026-10-20T09:00:00Z"
    assert len(monitor.select_versions(ds, "milestones", day, store=store)) == 1


# --------------------------------------------------------------------- CLI run


def _main(tmp_path, net, store, *flags):
    args = [str(FIXTURES), "--only", PROGRAM, "--today", TODAY.isoformat(), *flags]
    return monitor.main(args, store=store, fetcher=net.fetcher(), now=NOW)


def test_dry_run_writes_no_rows_and_no_refresh(tmp_path, capsys):
    store = FakeStore()
    findings = tmp_path / "f.json"
    net = Net(routes(school=html(PAGE.replace("$12,000", "$9,500"))))
    # a baseline exists, so this run has a finding; a dry run still reports it
    store.rows.append(_baseline_row(tmp_path))
    assert _main(tmp_path, net, store, "--findings-json", str(findings)) == 0
    assert len(store.rows) == 1 and store.inserts == 0 and store.refreshes == 0
    assert json.loads(findings.read_text())[0]["kind"] == "changed"  # findings files are fine in a dry run
    assert "dry run: nothing written" in capsys.readouterr().out


def _baseline_row(tmp_path) -> Dict[str, Any]:
    scratch = FakeStore()
    res = monitor.run([_version_from_fixtures()], scratch, Net(routes()).fetcher(), TODAY, NOW)
    return res.rows[0]


def _version_from_fixtures() -> Dict[str, Any]:
    docs = {str(p): v.load_yaml_text(p.read_text(encoding="utf-8")) for p in sorted(FIXTURES.glob("*/*.yaml"))}
    d = model.build_dataset(docs, root=v.REPO_ROOT)
    return next(r for r in model.select_published(d) if r["version_id"] == VERSION)


def test_apply_inserts_each_row_and_refreshes(tmp_path):
    store = FakeStore()
    assert _main(tmp_path, Net(routes()), store, "--apply") == 0
    assert store.inserts == 1 and store.refreshes == 1 and len(store.rows) == 1
    assert set(store.rows[0]) == {"program_id", "version_id", "checked_at", "result", "needs_review", "detail"}
    assert store.rows[0]["result"] in ("unchanged", "changed", "stale_signal", "unreachable", "conflicting")


def test_failure_midway_keeps_written_rows_refreshes_and_writes_findings(tmp_path, monkeypatch, version):
    class Flaky(FakeStore):
        def insert(self, rows):
            if self.inserts >= 1:
                raise RuntimeError("db down")
            super().insert(rows)

    store = Flaky()
    monkeypatch.setattr(monitor, "select_versions", lambda *a, **k: two_versions(version))
    out = tmp_path / "f.json"
    args = [str(FIXTURES), "--today", TODAY.isoformat(), "--apply", "--findings-json", str(out)]
    with pytest.raises(RuntimeError):
        monitor.main(args, store=store, fetcher=Net(routes()).fetcher(), now=NOW)
    assert len(store.rows) == 1 and store.refreshes == 1  # refresh in finally: the view never lags the flags
    assert out.exists()


def test_failed_refresh_exits_nonzero_after_the_rows_are_written(tmp_path):
    class NoRefresh(FakeStore):
        def refresh(self):
            raise RuntimeError("timeout")

    store = NoRefresh()
    assert _main(tmp_path, Net(routes()), store, "--apply") == 1
    assert len(store.rows) == 1


def test_version_not_loaded_in_the_database_is_skipped(tmp_path, capsys):
    store = FakeStore()
    store.unloaded = {(PROGRAM, VERSION)}
    net = Net(routes())
    assert _main(tmp_path, net, store, "--apply") == 0
    assert store.rows == [] and net.calls == []  # no fetch, no insert that would hit the foreign key
    assert f"skipped (not loaded): {PROGRAM}/{VERSION}" in capsys.readouterr().out


def test_findings_files_are_written_when_asked(tmp_path):
    store = FakeStore()
    _main(tmp_path, Net(routes()), store, "--apply")
    out_json, out_md = tmp_path / "f.json", tmp_path / "f.md"
    _main(tmp_path, Net(routes(school=html(PAGE.replace("$12,000", "$9,500")))), store, "--apply",
          "--findings-json", str(out_json), "--findings-md", str(out_md))
    data = json.loads(out_json.read_text())
    assert data[0]["program_id"] == PROGRAM and "$9500" in out_md.read_text()


def test_findings_markdown_is_capped():
    big = [{"program_id": f"p{i}", "version_id": "v", "kind": "changed", "new": True,
            "changed_sources": [{"source_id": "s", "url": "https://x/" + "a" * 500, "archive_save_url": "u",
                                 "diff": {"amounts": {"added": ["$1"], "removed": []}}}],
            "stale_signals": [], "unreachable_sources": [], "unreadable_sources": [],
            "raw_changed_sources": []} for i in range(400)]
    assert len(monitor.findings_markdown(big, TODAY)) <= monitor.MAX_FINDINGS_CHARS + 200


# ------------------------------------------- stale, unreachable, unreadable: never flag


def test_clearing_a_stale_only_row_stays_cleared(version):
    store = FakeStore()
    page = html(PAGE.replace("Fixture Scholars 2027", "Class of 2029 Fixture Scholars"))
    check(version, Net(routes(school=page)), store)
    row = check(version, Net(routes(school=page)), store)
    assert row["needs_review"] is False and row["detail"]["stale_signals"]
    cleared = copy.deepcopy(store.rows[-1])
    cleared["detail"].pop("stale_signals")  # what the runbook SQL does
    store.rows.append(cleared)
    row = check(version, Net(routes(school=page)), store)
    assert row["needs_review"] is False


def test_stale_signal_on_the_first_run_does_not_flag(version):
    row = check(version, Net(routes(school=html(PAGE.replace("Fixture Scholars 2027", "Class of 2029 Fixture Scholars")))))
    assert row["detail"]["first_run"] is True and row["needs_review"] is False


def test_unreachable_is_reported_once_and_never_flags(version):
    store = FakeStore()
    check(version, Net(routes()), store)
    row = check(version, Net(routes(school=Response(404))), store)
    assert row["needs_review"] is False
    f = check.findings[0]  # type: ignore[attr-defined]
    assert f["kind"] == "info" and f["unreachable_sources"][0]["source_id"] == "s-school"
    check(version, Net(routes(school=Response(404))), store)
    assert check.findings == []  # type: ignore[attr-defined]  # already reported


def test_script_rendered_page_is_unreadable_and_never_flags(version):
    shell = "<html><body><div id='root'></div><script>load()</script></body></html>"
    store = FakeStore()
    row = check(version, Net(routes(school=html(shell))), store)
    assert src(row)["text_unreadable"] is True and src(row)["text_sha256"] is None
    assert check.findings[0]["unreadable_sources"]  # type: ignore[attr-defined]
    row = check(version, Net(routes(school=html(shell.replace("load()", "load(2)")))), store)
    assert row["needs_review"] is False and src(row)["change"] == "raw_changed"
    assert check.findings[0]["raw_changed_sources"] and not check.findings[0]["unreadable_sources"]  # type: ignore[attr-defined]


def test_200_maintenance_or_soft_404_page_is_unreachable_not_a_change(version):
    store = FakeStore()
    check(version, Net(routes()), store)
    for body in ("<html><body><main><h1>Page not found</h1><p>The page cannot be found.</p></main></body></html>",
                 "<html><body><main><p>This site is under maintenance. Please check back.</p></main></body></html>"):
        row = check(version, Net(routes(school=html(body))), store)
        s = src(row)
        assert s["status"] == "unreachable" and "suspect page" in s["reason"]
        assert row["needs_review"] is False
        assert s["raw_sha256"] == src(store.rows[0])["raw_sha256"]  # baseline carried, not replaced


def test_page_that_lost_most_of_its_content_is_suspect(version):
    store = FakeStore()
    check(version, Net(routes()), store)
    stub = "<html><body><main><h1>Fixture Scholars</h1>" + "<p>" + ("Welcome to our page. " * 20) + "</p></main></body></html>"
    row = check(version, Net(routes(school=html(stub))), store)
    assert src(row)["status"] == "unreachable" and row["needs_review"] is False


def test_a_challenge_page_is_never_baselined(version):
    chal = "<html><body><main><p>Verify you are human to continue. " + "x " * 100 + "</p></main></body></html>"
    row = check(version, Net(routes(school=html(chal))))
    assert src(row)["status"] == "unreachable" and "raw_sha256" not in src(row)


def test_pdf_without_text_reports_raw_change_but_never_flags(version):
    pdf = Response(200, {"content-type": "application/pdf"}, b"%PDF-1.4 /CreationDate 1")
    store = FakeStore()
    check(version, Net(routes(school=pdf)), store)
    row = check(version, Net(routes(school=Response(200, {"content-type": "application/pdf"}, b"%PDF-1.4 /CreationDate 2"))), store)
    assert src(row)["change"] == "raw_changed" and row["needs_review"] is False and row["result"] == "unchanged"
    assert check.findings[0]["raw_changed_sources"]  # type: ignore[attr-defined]


def test_throttling_host_is_skipped_for_the_rest_of_the_run(version):
    store = FakeStore()
    both = copy.deepcopy(version)
    both["record"]["sources"][1]["url"] = "https://admission.virginia.edu/affordability/second"
    net_routes = routes(school=Response(429, {"retry-after": "99999"}))
    net_routes["https://admission.virginia.edu/affordability/second"] = html()
    net = Net(net_routes)
    res = monitor.run([both], store, net.fetcher(), TODAY, NOW)
    row = res.rows[0]
    assert all(s["status"] == "unreachable" for s in row["detail"]["sources"])
    assert "skipped for the rest of this run" in src(row, "s-foundation")["reason"]
    assert "https://admission.virginia.edu/affordability/second" not in [u for u, _ in net.calls]


# ------------------------------------------------------------------ extraction


def test_tokens_and_heading_years():
    t = monitor.extract_tokens(
        monitor._clean("Apply by Dec. 1st, 2026 or 11/15/2026. Worth $5 million; $1,250.50; 2026-12-01. Automatically considered. No longer open.")
    )
    assert t["amounts"] == ["$1250.50", "$5000000"]
    assert "dec 1 2026" in t["dates"] and "nov 15 2026" in t["dates"]
    assert t["years"] == [2026]
    assert t["selection_words"] == ["automatic", "considered", "no longer"]
    assert monitor.heading_entry_years(["class of 2030 scholars", "2025-26 awards", "fall 2027 entrants"]) == [2025, 2026, 2027]


# -------------------------------------------------------------------- workflow

WORKFLOW = v.REPO_ROOT / ".github" / "workflows" / "scholarships-monitor.yml"


def test_workflow_schedules_never_set_both_day_fields_and_mode_matches():
    import re

    text = WORKFLOW.read_text(encoding="utf-8")
    crons = re.findall(r'- cron: "([^"]+)"', text)
    assert len(crons) == 3
    for c in crons:
        _, _, dom, _, dow = c.split()
        assert dom == "*" or dow == "*", c  # GitHub ORs the two day fields
    daily = next(c for c in crons if c.split()[2:] == ["*", "*", "*"])
    assert text.count(f'"{daily}"') >= 2  # the cron and the milestone-mode case string
    months = {c.split()[3] for c in crons}
    assert {"1,7-12", "2-6"} <= months


def test_workflow_keeps_the_service_key_in_the_monitor_step_only():
    text = WORKFLOW.read_text(encoding="utf-8")
    assert text.count("SUPABASE_SERVICE_ROLE_KEY") == 2  # name and value, one env block
    assert "SUPABASE_SERVICE_ROLE_KEY" not in text.split("    steps:")[0]
    install = text.split("name: Install Python dependencies")[1].split("- id: monitor")[0]
    assert "SUPABASE" not in install
    assert "--apply" in text and "dry_run" in text


def test_workflow_reports_findings_even_when_the_monitor_step_fails():
    text = WORKFLOW.read_text(encoding="utf-8")
    issue = text.split("name: Open or update the findings issue")[1].split("- name:")[0]
    assert "if: always()" in issue and "steps.monitor.outputs.findings" in issue
    step = text.split("name: Run the monitor")[1].split("- uses:")[0]
    assert "set -uo pipefail" in step and "set -e" not in step  # outputs are written before the exit
    assert step.index("findings=") < step.index('exit "${rc}"')
    assert "--cache-file" not in text


# ------------------------------------------------------------- browser fallback


def _bfetcher(plain: Net, browser: Net) -> PoliteFetcher:
    return PoliteFetcher(
        "scholarship-monitor", transport=plain.transport, browser_fallback=browser.transport,
        clock=lambda: 1_800_000_000.0, sleep=lambda s: None, min_spacing=0, cache={},
    )


def _refused(url_robots=Response(404)) -> Dict[str, Any]:
    """Plain client is refused (404) on both source pages."""
    return routes(school=Response(404), found=Response(404))


def _check_b(version, plain: Net, browser: Net, store: FakeStore) -> Dict[str, Any]:
    res = monitor.run([version], store, _bfetcher(plain, browser), TODAY, NOW)
    store.rows.extend(res.rows)
    return res.rows[0]


def _browser_net(school: str = PAGE, found: str = PAGE) -> Net:
    return Net({S_SCHOOL: html(school), S_FOUND: html(found), ROBOTS_SCHOOL: Response(404), ROBOTS_FOUND: Response(404)})


def test_fallback_records_transport_and_baselines(version):
    store = FakeStore()
    row = _check_b(version, Net(_refused()), _browser_net(), store)
    s = src(row)
    assert s["transport"] == "browser" and s["status"] == "ok" and s["change"] == "baseline"
    assert row["result"] == "unchanged" and row["needs_review"] is False


def test_browser_fetch_ignores_raw_sha256(version):
    store = FakeStore()
    _check_b(version, Net(_refused()), _browser_net(), store)
    # same text, different bytes (the rendered DOM is not byte-stable): not markup_only, not raw_changed
    noisy = PAGE.replace("<body>", "<body data-x='123'>") + "<!-- t=99 -->"
    row = _check_b(version, Net(_refused()), _browser_net(noisy, noisy), store)
    assert src(row)["change"] == "none" and src(row)["raw_sha256"] != store.rows[0]["detail"]["sources"][0]["raw_sha256"]
    assert row["result"] == "unchanged" and row["needs_review"] is False


def test_browser_fetch_still_flags_a_terms_change_by_text_and_tokens(version):
    store = FakeStore()
    _check_b(version, Net(_refused()), _browser_net(), store)
    row = _check_b(version, Net(_refused()), _browser_net(PAGE.replace("$12,000", "$10,000"), PAGE), store)
    assert src(row)["change"] == "text_changed" and row["needs_review"] is True


def test_transport_change_rebaselines_without_needs_review(version):
    store = FakeStore()
    check(version, Net(routes()), store)  # http baseline
    changed = PAGE.replace("$12,000", "$9,000")  # even a real difference must not flag across transports
    row = _check_b(version, Net(_refused()), _browser_net(changed, changed), store)
    s = src(row)
    assert s["change"] == "transport_rebaseline" and s["transport"] == "browser"
    assert row["needs_review"] is False and row["result"] == "unchanged"
    assert row["detail"]["transport_rebaseline"] is True
    # and back again: browser baseline, plain fetch works now
    row2 = check(version, Net(routes()), store)
    assert src(row2)["change"] == "transport_rebaseline" and src(row2)["transport"] == "http"
    assert row2["needs_review"] is False
    # the next plain run compares normally against the new baseline
    row3 = check(version, Net(routes()), store)
    assert src(row3)["change"] == "none"


def test_previous_row_without_transport_is_http(version):
    store = FakeStore()
    row = check(version, Net(routes()), store)
    for s in row["detail"]["sources"]:
        s.pop("transport", None)  # a row written before the fallback existed
        s.pop("attempt_transport", None)
    row2 = check(version, Net(routes()), store)
    assert src(row2)["change"] == "none" and src(row2)["transport"] == "http"


def test_unreachable_run_keeps_baseline_transport(version):
    store = FakeStore()
    _check_b(version, Net(_refused()), _browser_net(), store)
    dead = Net(routes(school=Response(404), found=Response(404)))
    row = _check_b(version, dead, Net({S_SCHOOL: Response(404), S_FOUND: Response(404), ROBOTS_SCHOOL: Response(404), ROBOTS_FOUND: Response(404)}), store)
    s = src(row)
    assert s["status"] == "unreachable" and s["transport"] == "browser"  # the baseline's transport survives
    assert s["attempt_transport"] == "http"  # the failed result was the plain one; the browser retry did not help


def test_error_page_served_with_200_through_the_browser_is_unreachable(version):
    store = FakeStore()
    _check_b(version, Net(_refused()), _browser_net(), store)
    err = "<html><body><main><h1>Page not found</h1><p>The page you requested could not be found.</p></main></body></html>"
    row = _check_b(version, Net(_refused()), _browser_net(err, err), store)
    s = src(row)
    assert s["status"] == "unreachable" and "suspect page" in s["reason"]
    assert row["needs_review"] is False and row["result"] == "unreachable"


def test_fallback_disabled_leaves_a_404_unreachable(version):
    row = check(version, Net(_refused()))
    s = src(row)
    assert s["status"] == "unreachable" and "transport" not in s
    assert "attempt_transport" in s and s["attempt_transport"] == "http"
    assert row["needs_review"] is False


def test_browser_fallback_flag_builds_fetcher_with_browser(monkeypatch, tmp_path):
    import tools.common.browser_transport as bt

    made = []

    class Fake:
        def __init__(self):
            made.append(self)
            self.closed = False

        def __call__(self, *a):
            raise ConnectionError("fake")

        def close(self):
            self.closed = True

    monkeypatch.setattr(bt, "BrowserTransport", Fake)
    store = FakeStore()
    rc = monitor.main(["--only", "nope", "--browser-fallback"], store=store, now=NOW)
    assert rc == 0 and len(made) == 1 and made[0].closed is True
