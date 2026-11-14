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
    "Awards are competitive.</p></main><footer>Contact us</footer></body></html>"
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


def check(version, net: Net, store: Optional[FakeStore] = None, today=TODAY, cache=None) -> Dict[str, Any]:
    """One monitor pass over a single version; returns the written row."""
    store = store if store is not None else FakeStore()
    res = monitor.run([version], store, net.fetcher(cache), today, NOW)
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


def test_text_change_with_empty_token_diff_still_needs_review(version):
    store = FakeStore()
    check(version, Net(routes()), store)
    row = check(version, Net(routes(school=html(PAGE.replace("Awards are", "Awards are very")))), store)
    assert row["result"] == "changed" and row["needs_review"] is True
    assert src(row)["diff"] == {}
    assert "no amount, date, year or selection word changed" in monitor.findings_markdown(check.findings, TODAY)  # type: ignore[attr-defined]


def test_needs_review_is_carried_until_cleared(version):
    store = FakeStore()
    check(version, Net(routes()), store)
    check(version, Net(routes(school=html(PAGE.replace("$12,000", "$9,500")))), store)
    # the next run sees the new text as its baseline: unchanged text, flag must stay
    row = check(version, Net(routes(school=html(PAGE.replace("$12,000", "$9,500")))), store)
    assert row["needs_review"] is True and row["result"] == "changed"
    assert row["detail"]["needs_review_carried"] is True
    assert check.findings == []  # type: ignore[attr-defined]  # not reported twice
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
    monkeypatch.setattr(monitor, "NORMALIZER_VERSION", 2)
    row = check(version, Net(routes(school=html(PAGE.replace("$12,000", "$9,500")))), store)
    assert row["result"] == "unchanged" and row["needs_review"] is False
    assert src(row)["change"] == "normalizer_rebaseline" and row["detail"]["normalizer_rebaseline"] is True
    assert src(row)["normalizer_version"] == 2


def test_not_modified_carries_the_baseline(version):
    store = FakeStore()
    cache: dict = {}
    check(version, Net(routes(school=Response(200, {"content-type": "text/html", "etag": '"a"'}, PAGE.encode()))), store, cache=cache)
    assert cache[S_SCHOOL]["etag"] == '"a"'
    net = Net(routes(school=Response(304)))
    row = check(version, net, store, cache=cache)
    assert dict(net.calls)[S_SCHOOL].get("If-None-Match") == '"a"'
    s = src(row)
    assert s["status"] == "not_modified" and s["fetched"] is False
    assert s["raw_sha256"] == src(store.rows[0])["raw_sha256"] and s["tokens"]["amounts"] == ["$12000"]
    assert row["result"] == "unchanged"


def test_cache_entry_without_baseline_is_dropped_before_fetch(version):
    cache = {S_SCHOOL: {"etag": '"stale"', "last_modified": None, "final_url": S_SCHOOL}}
    net = Net(routes())
    row = check(version, net, FakeStore(), cache=cache)
    assert "If-None-Match" not in dict(net.calls)[S_SCHOOL]
    assert src(row)["change"] == "baseline"


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
    assert row["result"] == "stale_signal" and row["needs_review"] is True
    assert check.findings[0]["kind"] == "stale_signal"  # type: ignore[attr-defined]


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
    assert row["result"] == "stale_signal"
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


@pytest.mark.parametrize(
    "offset, expected",
    [(30, True), (7, True), (29, False), (31, False), (6, False), (8, False), (0, False)],
)
def test_milestone_selector_30_and_7_days(version, offset, expected):
    date = (TODAY + dt.timedelta(days=offset)).isoformat()
    assert monitor.milestone_due(_with_milestone(version, date), TODAY) is expected


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
    # fixture deadline is 2026-12-01 = 30 days after 2026-11-01
    assert [r["version_id"] for r in monitor.select_versions(ds, "milestones", dt.date(2026, 11, 1))] == [VERSION]
    assert monitor.select_versions(ds, "milestones", dt.date(2026, 11, 2)) == []
    assert len(monitor.select_versions(ds, "full", TODAY)) == len(model.select_published(ds))
    assert monitor.select_versions(ds, "full", TODAY, only=["nope"]) == []
    assert len(monitor.select_versions(ds, "full", TODAY, limit=1)) == 1


# --------------------------------------------------------------------- CLI run


def _main(tmp_path, net, store, *flags, cache: Optional[Path] = None):
    args = [str(FIXTURES), "--only", PROGRAM, "--today", TODAY.isoformat(), *flags]
    if cache:
        args += ["--cache-file", str(cache)]
    return monitor.main(args, store=store, fetcher=net.fetcher(monitor.load_cache(cache)), now=NOW)


def test_dry_run_writes_nothing(tmp_path, capsys):
    store, cache = FakeStore(), tmp_path / "cache.json"
    findings = tmp_path / "f.json"
    net = Net(routes(school=Response(200, {"content-type": "text/html", "etag": '"a"'}, PAGE.encode())))
    assert _main(tmp_path, net, store, cache=cache) == 0
    assert store.rows == [] and store.inserts == 0 and store.refreshes == 0
    assert not cache.exists() and not findings.exists()
    assert "dry run: nothing written" in capsys.readouterr().out


def test_apply_inserts_saves_cache_and_refreshes(tmp_path):
    store, cache = FakeStore(), tmp_path / "cache.json"
    net = Net(routes(school=Response(200, {"content-type": "text/html", "etag": '"a"'}, PAGE.encode())))
    assert _main(tmp_path, net, store, "--apply", cache=cache) == 0
    assert store.inserts == 1 and store.refreshes == 1 and len(store.rows) == 1
    assert json.loads(cache.read_text())[S_SCHOOL]["etag"] == '"a"'
    # the insert is a valid scholarship_version_checks row
    assert set(store.rows[0]) == {"program_id", "version_id", "checked_at", "result", "needs_review", "detail"}
    assert store.rows[0]["result"] in ("unchanged", "changed", "stale_signal", "unreachable", "conflicting")


def test_failed_insert_does_not_save_the_cache(tmp_path):
    class Boom(FakeStore):
        def insert(self, rows):
            raise RuntimeError("db down")

    cache = tmp_path / "cache.json"
    net = Net(routes(school=Response(200, {"content-type": "text/html", "etag": '"a"'}, PAGE.encode())))
    with pytest.raises(RuntimeError):
        _main(tmp_path, net, Boom(), "--apply", cache=cache)
    assert not cache.exists()


def test_findings_files_are_written_when_asked(tmp_path):
    store = FakeStore()
    _main(tmp_path, Net(routes()), store, "--apply")
    out_json, out_md = tmp_path / "f.json", tmp_path / "f.md"
    _main(tmp_path, Net(routes(school=html(PAGE.replace("$12,000", "$9,500")))), store, "--apply",
          "--findings-json", str(out_json), "--findings-md", str(out_md))
    data = json.loads(out_json.read_text())
    assert data[0]["program_id"] == PROGRAM and "$9500" in out_md.read_text()


def test_findings_markdown_is_capped():
    big = [{"program_id": f"p{i}", "version_id": "v", "kind": "changed",
            "changed_sources": [{"source_id": "s", "url": "https://x/" + "a" * 500, "archive_save_url": "u",
                                 "diff": {"amounts": {"added": ["$1"], "removed": []}}}],
            "stale_signals": []} for i in range(400)]
    assert len(monitor.findings_markdown(big, TODAY)) <= monitor.MAX_FINDINGS_CHARS + 200


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


def test_unreadable_pdf_falls_back_to_raw_bytes(version):
    pdf = Response(200, {"content-type": "application/pdf"}, b"%PDF-1.4 not really a pdf")
    store = FakeStore()
    row = check(version, Net(routes(school=pdf)), store)
    assert src(row)["text_sha256"] is None
    pdf2 = Response(200, {"content-type": "application/pdf"}, b"%PDF-1.4 different bytes")
    row = check(version, Net(routes(school=pdf2)), store)
    assert row["result"] == "changed" and src(row)["change"] == "raw_changed"


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
    install = text.split("name: Install Python dependencies")[1].split("- name:")[0]
    assert "SUPABASE" not in install
    assert "--apply" in text and "dry_run" in text
