"""PRD 038 A14 (M2 re-check R1): a Lane 2 failure must not lose Lane 1+3. Any engine failure (nonzero exit, timeout, missing
binary) drops everything Lane 2 did, records the reason, and returns exactly the --no-lane2 result."""

import stat
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import lane2_ocr as L  # noqa: E402
import template_overlay as to  # noqa: E402
import test_lane2_ocr as X  # noqa: E402
import test_template_overlay as T  # noqa: E402
from test_lane2_a12 import YEAR  # noqa: E402
from test_lane2_ocr import flat_numbers  # noqa: E402,F401


def _packet():
    """Page 19 keeps its text layer (a Lane 1 value); page 12 is image-only with a printed 1234 (Lane 2 reads it)."""
    _f1, w1 = X.widget("AP_RECD_1ST_MEN_N")
    _f2, w2 = X.widget("ACT_1_P")
    q1, q2 = w1["template_page"], w2["template_page"]
    data = T.fill_and_flatten(YEAR, {}, {})
    data = T.add_text(data, q1, w1["rect"][0] + 5, w1["rect"][1] + 5, "1234")
    data = T.add_text(data, q2, w2["rect"][0] + 5, w2["rect"][1] + 5, "55")
    return X.packet_with_raster_page(data, q1, data)                                              # q1 becomes image-only


class Broken(L.TesseractEngine):
    """An engine whose probe passes (so Lane 2 starts) and whose reads then fail the way Tesseract can."""

    def __init__(self, exc):
        super().__init__()
        self.exc = exc

    def check(self):
        return None

    def version(self):
        return "tesseract 5.5.3"

    def model_info(self):
        return {"fast_sha256": "x", "best_sha256": "y"}

    def read(self, img, **kw):
        raise self.exc


def _same_lane13(a, b):
    return a["values"] == b["values"] and a["notes"]["withheld_by_reason"] == b["notes"]["withheld_by_reason"] \
        and a["notes"]["emission_class_counts"] == b["notes"]["emission_class_counts"]


@pytest.mark.parametrize("exc", [RuntimeError("tesseract exited 1: boom"), subprocess.TimeoutExpired("tesseract", 30), OSError("exec format error")])
def test_a_failure_mid_run_returns_the_lane_1_and_3_result_and_records_why(exc):
    data = _packet()
    base = to.extract_overlay(data)                                                               # the --no-lane2 run
    out = to.extract_overlay(data, lane2=L.make_hook(Broken(exc)))
    assert "lane2_failed" in out["notes"] and type(exc).__name__ in out["notes"]["lane2_failed"]
    assert _same_lane13(out, base)
    assert all(r.get("lane") != 2 for r in out["values"].values())
    assert "ACT_1_P" in {r.get("pdf_tag") for r in out["values"].values()}                         # Lane 1 survived
    assert "ocr_engine" not in out["notes"]                                                       # no partial Lane 2 metadata


def test_partial_lane_2_output_is_dropped_entirely(monkeypatch):
    data = _packet()
    base = to.extract_overlay(data)
    calls = []

    def flaky(self, c, tag, f, wi, rect, st):
        calls.append(tag)
        if len(calls) == 1:
            return L.Lane2Read(value="999", text="999", conf=99.0)                                 # one emitted, then a failure
        raise RuntimeError("tesseract exited 1")

    monkeypatch.setattr(L.Lane2, "read_widget", flaky)
    out = to.extract_overlay(data, lane2=L.make_hook(X.FixedEngine([])))
    assert len(calls) >= 2                                                                         # one emitted, the next failed
    assert "lane2_failed" in out["notes"] and _same_lane13(out, base)


def test_a_missing_binary_disables_lane_2_before_version_is_called(monkeypatch):
    data = _packet()
    base = to.extract_overlay(data)
    out = to.extract_overlay(data, lane2=L.make_hook(L.TesseractEngine(exe="no-such-tesseract-binary")))
    assert out["notes"]["lane2_disabled"] == "tesseract_not_installed"
    assert "ocr_engine" not in out["notes"] and _same_lane13(out, base)                            # version()/model_info() never reached


def test_check_runs_first_and_its_own_failure_is_contained():
    class CheckRaises(Broken):
        def check(self):
            raise FileNotFoundError("tessdata")
    out = to.extract_overlay(_packet(), lane2=L.make_hook(CheckRaises(RuntimeError("x"))))
    assert out["notes"]["lane2_disabled"].startswith("check_failed: FileNotFoundError")


def test_every_engine_call_has_a_timeout(monkeypatch):
    import numpy as np
    seen = []

    def fake_run(args, **kw):
        seen.append((args[1] if len(args) > 1 else "", kw.get("timeout")))
        raise subprocess.TimeoutExpired(args, kw.get("timeout"))
    monkeypatch.setattr(subprocess, "run", fake_run)
    engine = L.TesseractEngine(exe="tesseract", timeout=7.0)
    for call in (lambda: engine.read(np.zeros((10, 10), dtype="uint8")), engine.version, engine.model_info):
        with pytest.raises(subprocess.TimeoutExpired):
            call()
    assert [t for _a, t in seen] == [7.0, 7.0, 7.0] and L.TesseractEngine().timeout == 30.0     # read, --version, --list-langs


def test_a_hung_binary_is_contained_by_the_hook(monkeypatch):
    class Hung(L.TesseractEngine):
        def check(self):
            return None

        def version(self):
            raise subprocess.TimeoutExpired("tesseract", 30)
    out = to.extract_overlay(_packet(), lane2=L.make_hook(Hung()))
    assert "lane2_failed" in out["notes"] and "TimeoutExpired" in out["notes"]["lane2_failed"]
