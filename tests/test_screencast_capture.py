import os
import shutil
import subprocess
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from screencast import capture as C  # noqa: E402


def test_validate_ok():
    plan = C.validate_steps([{"goto": "https://x"}, {"wait": 1}, {"scroll": -200},
                             {"scroll_to": "#a"}, {"click": "a"}, {"hover": "b"},
                             {"type": ["input", "hi"]}])
    assert [k for k, _ in plan] == ["goto", "wait", "scroll", "scroll_to", "click", "hover", "type"]
    assert plan[-1][1] == ("input", "hi")


@pytest.mark.parametrize("bad", [
    "nope", [{"fly": 1}], [{"wait": -1}], [{"wait": True}], [{"goto": ""}],
    [{"type": ["sel"]}], [{"click": 3}], [{"goto": "a", "wait": 1}], [{"scroll": "10"}],
])
def test_validate_bad(bad):
    with pytest.raises(ValueError):
        C.validate_steps(bad)


def test_time_math():
    assert C.frames_for(0.6, 30) == 18
    assert C.frames_for(0, 30) == 0
    assert C.frame_time(45, 30) == 1.5


def test_scroll_increments_sum_and_ease():
    inc = C.scroll_increments(600, 18)
    assert len(inc) == 18 and sum(inc) == 600
    assert inc[0] < inc[9] and inc[-1] < inc[9]          # slow-fast-slow
    assert sum(C.scroll_increments(-333, 7)) == -333
    assert C.scroll_increments(100, 0) == [100]


def test_box_helpers():
    assert C.box_to_list({"x": 1.4, "y": 2.6, "width": 10, "height": 5}) == [1, 3, 10, 5]
    assert C.box_to_list(None) is None
    assert C.scroll_to_delta([0, 1000, 10, 10], 1000) == 700
    ev = C.make_event(1.23456, "click", "a", [1, 2, 3, 4])
    assert ev == {"t": 1.2346, "type": "click", "selector": "a", "box": [1, 2, 3, 4]}


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg missing")
def test_load_recording(tmp_path):
    mp4 = tmp_path / "in.mp4"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i",
                    "color=c=blue:s=64x64:d=1:r=30", "-pix_fmt", "yuv420p", str(mp4)], check=True)
    r = C.load_recording(str(mp4), str(tmp_path / "out"), fps=10)
    assert r["fps"] == 10 and r["boxes"] == {} and r["events"] == []
    assert 9 <= r["n_frames"] <= 11
    assert os.path.isfile(os.path.join(r["frames_dir"], "00000.png"))


def _chromium_ok():
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            p.chromium.launch(headless=True).close()
        return True
    except Exception:
        return False


@pytest.mark.skipif(not _chromium_ok(), reason="Playwright/Chromium unavailable")
def test_capture_local_html(tmp_path):
    html = tmp_path / "p.html"
    html.write_text("<html><body style='margin:0'><div style='height:1500px;background:#eee'></div>"
                    "<input id='q' style='font-size:30px'><button id='b' onclick=\"this.textContent='ok'\">"
                    "Go</button><div style='height:1500px'></div></body></html>")
    with pytest.warns(UserWarning):
        r = C.capture([{"goto": html.as_uri()}, {"wait": 0.2}, {"scroll_to": "#q"},
                       {"type": ["#q", "hey"]}, {"hover": "#b"}, {"click": "#b"},
                       {"click": "#missing"}],
                      str(tmp_path / "cap"), viewport=(320, 480), fps=10)
    assert r["n_frames"] == len(os.listdir(r["frames_dir"]))
    assert {"#q", "#b"} <= set(r["boxes"])
    assert "#missing" not in r["boxes"]
    x, y, w, h = r["boxes"]["#q"]
    assert 0 <= y < 480 and w > 0
    types = [e["type"] for e in r["events"]]
    assert types == ["goto", "wait", "scroll_to", "type", "hover", "click"]
    ts = [e["t"] for e in r["events"]]
    assert ts == sorted(ts)
