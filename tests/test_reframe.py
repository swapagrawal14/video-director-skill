import importlib.util
import os
import shutil
import subprocess

import numpy as np
import pytest

ROOT = os.path.join(os.path.dirname(__file__), "..")
_spec = importlib.util.spec_from_file_location("reframe", os.path.join(ROOT, "scripts", "reframe.py"))
R = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(R)


def test_parse_aspects():
    assert R.parse_aspects("16x9, 1:1,16x9") == ["16x9", "1x1"]
    with pytest.raises(ValueError):
        R.parse_aspects("21x9")


def test_fit_and_cover():
    assert R.fit_inside(1080, 1920, 1920, 1080) == (608, 1080)
    assert R.cover_scale(1080, 1920, 1080, 1080) == (1080, 1920, "y")
    assert R.cover_scale(1920, 1080, 1080, 1080) == (1920, 1080, "x")


def test_best_and_subject_window():
    p = np.zeros(100); p[10:20] = 1.0
    assert 0 <= R.best_window(p, 30) <= 10
    s = R.subject_window(p, 30)
    assert abs((s + 15) - 15) <= 1   # centred on the subject (15), clamped at 0
    p2 = np.zeros(100); p2[60:70] = 1.0
    assert R.subject_window(p2, 30) == 50   # 65 - 15
    assert R.best_window(np.zeros(50), 20) == 15   # no energy -> centre
    assert R.best_window(p, 200) == 0


def test_constrain_window_zone():
    assert R.constrain_window(-5, 100, 300) == 0
    assert R.constrain_window(250, 100, 300) == 200
    # zone 220..260 must be inside a 100 window starting at 50 -> slides to 160
    assert R.constrain_window(50, 100, 300, (220, 260)) == 160
    # zone bigger than window is ignored
    assert R.constrain_window(50, 100, 300, (0, 290)) == 50


def test_smooth_track_speed_limit():
    out = R.smooth_track([0, 0, 100, 100, 100], max_step=10)
    assert np.all(np.abs(np.diff(out)) <= 10 + 1e-9)
    assert len(R.smooth_track([5], 1)) == 1


def test_piecewise_expr_values():
    e = R.piecewise_expr([0, 1, 2], [0, 10, 30])
    env = {"if_": lambda c, a, b: a if c else b, "lt": lambda a, b: a < b}
    run = lambda t: eval(e.replace("if(", "if_("), {**env, "t": t})   # ffmpeg if/lt -> python
    assert run(-1) == 0
    assert abs(run(0.5) - 5) < 1e-6
    assert abs(run(1.5) - 20) < 1e-6
    assert run(5) == 30
    assert R.piecewise_expr([1], [7]) == "7.0"


def test_energy_maps_motion_and_faces():
    f = np.zeros((3, 20, 20), np.float32); f[1, 5:8, 5:8] = 1.0
    e = R.energy_maps(f, faces=[[], [], [(10, 10, 4, 4)]])
    assert e.shape == f.shape
    assert e[1, 4:9, 4:9].sum() > e[1, 12:18, 12:18].sum()
    assert e[2, 10:14, 10:14].sum() > 0


def test_retarget_ass():
    src = ("[Script Info]\nPlayResX: 1080\nPlayResY: 1920\n\n[V4+ Styles]\n"
           "Format: Name, Fontname, Fontsize, PrimaryColour, Outline, Shadow, MarginL, MarginR, MarginV\n"
           "Style: Default,Baloo 2,80,&H00FFFFFF,4,2,40,40,300\n\n[Events]\nDialogue: 0,0:00:00.00,0:00:01.00,Default,,0,0,0,,{\\fs90}hi\n")
    out = R.retarget_ass(src, 1920, 1080)
    assert "PlayResX: 1920" in out and "PlayResY: 1080" in out
    assert "Style: Default,Baloo 2,80,&H00FFFFFF,4,2,71,71,300" in out   # short side 1080 -> 1080: same size
    out2 = R.retarget_ass(src.replace("1080\nPlayResY: 1920", "720\nPlayResY: 1280"), 1080, 1080)
    assert ",120," in out2 and "\\fs135" in out2


def test_wrap_words():
    assert R.wrap_words("Adams clasp kaise banaye", 12) == ["Adams clasp", "kaise banaye"]


def test_project_sources(tmp_path):
    with pytest.raises(FileNotFoundError):
        R.project_sources(str(tmp_path))
    (tmp_path / "Final.mp4").write_bytes(b"x"); (tmp_path / "Final_1x1.mp4").write_bytes(b"x")
    assert R.project_sources(str(tmp_path)) == (str(tmp_path / "Final.mp4"), None, False)
    (tmp_path / "video_only.mp4").write_bytes(b"x"); (tmp_path / "final_audio.wav").write_bytes(b"x")
    v, a, clean = R.project_sources(str(tmp_path))
    assert clean and v.endswith("video_only.mp4") and a.endswith("final_audio.wav")


@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="ffmpeg not installed")
def test_end_to_end_small(tmp_path):
    src = tmp_path / "reel.mp4"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", "testsrc2=s=180x320:r=12:d=1",
                    "-f", "lavfi", "-i", "sine=d=1:sample_rate=48000", "-shortest", "-pix_fmt", "yuv420p", str(src)], check=True)
    made = R.main([str(src), "-o", str(tmp_path / "out"), "--samples", "4", "--title", "Test"])
    assert [os.path.basename(m) for m in made] == ["reel_16x9.mp4", "reel_1x1.mp4"]
    p = R.probe(made[1]); assert (p["w"], p["h"], p["audio"]) == (1080, 1080, True)
