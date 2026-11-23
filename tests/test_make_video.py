import importlib.util
import json
import os

import pytest

ROOT = os.path.join(os.path.dirname(__file__), "..")
_spec = importlib.util.spec_from_file_location("make_video", os.path.join(ROOT, "scripts", "make_video.py"))
MV = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(MV)
INTAKE = open(os.path.join(ROOT, "docs", "INTAKE.md"), encoding="utf-8").read()


def test_slugify():
    assert MV.slugify("Adams Clasp: wire bending (Hinglish)!") == "adams-clasp-wire-bending-hinglish"
    assert MV.slugify("???") == "video"
    assert len(MV.slugify("x" * 200)) <= 48


def test_parse_intake():
    T = MV.parse_intake(INTAKE)
    assert len(T) >= 9 and T[0]["n"] == 1 and T[0]["name"] == "Bench demo"
    assert all({"n", "name", "what", "engine", "best"} <= set(x) for x in T)


def test_rank_treatments():
    T = MV.parse_intake(INTAKE)
    assert MV.rank_treatments("Adams clasp wire bending", T)[0] == 1
    assert MV.rank_treatments("haunted hostel lift horror short", T)[0] == 8
    assert MV.rank_treatments("how to use ChatGPT website", T)[0] == 6
    r = MV.rank_treatments("something vague", T)
    assert len(r) == 3 and len(set(r)) == 3


def test_engine_for():
    T = {x["n"]: x for x in MV.parse_intake(INTAKE)}
    assert MV.engine_for(T[1]) == "motion2d"
    assert MV.engine_for(T[1], style="3d") == "template"
    assert MV.engine_for(T[5]) == "handdrawn"
    assert MV.engine_for(T[6]) == "screencast"
    assert MV.engine_for(T[7]) == "vidliboom"
    assert MV.engine_for(T[9]).startswith("external:")
    assert MV.engine_for(T[1], override="template") == "template"


def test_format_menu_marks_pick():
    T = MV.parse_intake(INTAKE)
    m = MV.format_menu("wire", T, [1, 2, 5])
    assert "1. **Bench demo (pick):**" in m and "5. **Whiteboard overview:**" in m and "Other treatments" in m


def test_state_flow():
    st = MV.new_state("x")
    assert MV.next_stage(st) == "brief"
    for s in MV.STAGES[:7]: st["stages"][s] = {"status": "done"}
    st["stages"]["vo"] = {"status": "skipped"}; st["storyboard_approved"] = True; st["treatment"] = 2
    assert MV.next_stage(st) == "render"
    MV.invalidate(st, "timing")
    assert MV.next_stage(st) == "timing" and "storyboard_approved" not in st and st["treatment"] == 2
    MV.invalidate(st, "treatment")
    assert "treatment" not in st and MV.next_stage(st) == "treatment"
    with pytest.raises(ValueError):
        MV.invalidate(st, "nope")


def test_scenes_ready():
    tpl = json.load(open(os.path.join(ROOT, "template", "project.json"), encoding="utf-8"))
    assert not MV.scenes_ready({"scenes": []})[0]
    assert not MV.scenes_ready(tpl, tpl)[0]
    ok, probs = MV.scenes_ready({"scenes": [{"vo": "namaste"}, {"secs": 3}]})
    assert ok and not probs
    ok, probs = MV.scenes_ready({"_todo": "x", "scenes": [{"sub": "no vo"}, {"vo": "TODO"}]})
    assert not ok and len(probs) == 3


def test_missing_vo(tmp_path):
    (tmp_path / "vo").mkdir(); (tmp_path / "vo" / "s00.wav").write_bytes(b"")
    P = {"scenes": [{"vo": "a"}, {"vo": "b"}, {"secs": 2}]}
    assert MV.missing_vo(P, str(tmp_path)) == [1]


def test_preview_times():
    T = {"duration": 30, "scenes": [{"t": 0, "d": 4}, {"t": 4, "d": 10}, {"t": 14, "d": 16}]}
    assert MV.preview_times(T) == [1.0, 2.0, 9.0, 22.0]
    many = {"duration": 100, "scenes": [{"t": i * 5, "d": 5} for i in range(20)]}
    assert len(MV.preview_times(many, n=8)) <= 8
    assert len(MV.preview_times({"duration": 16}, n=4)) == 4


def test_project_skeleton():
    P = MV.project_skeleton({"topic": "T", "format": "reel", "lang": "hi", "credit": "C"})
    assert (P["width"], P["height"], P["aspect"]) == (1080, 1920, [9, 16]) and P["scenes"] == [] and P["_todo"]


def test_dry_run_writes_nothing(tmp_path, capsys):
    rc = MV.main(["wire bending demo", "--projects-dir", str(tmp_path), "--dry-run"])
    out = capsys.readouterr().out
    assert rc == 0 and "would stop here (needs_approval)" in out and "first blocking stage: treatment" in out
    assert list(tmp_path.iterdir()) == []


def test_first_stops_at_treatment_and_resumes(tmp_path, capsys):
    assert MV.main(["wire bending demo", "--projects-dir", str(tmp_path), "--tts", "none"]) == 0
    d = tmp_path / "wire-bending-demo"
    st = json.load(open(d / "state.json"))
    assert st["stages"]["brief"]["status"] == "done" and st["stages"]["treatment"]["status"] == "needs_approval"
    assert (d / "TREATMENT_MENU.md").exists() and json.load(open(d / "brief.json"))["tts"] == "none"
    assert MV.main(["--slug", "wire-bending-demo", "--projects-dir", str(tmp_path), "--treatment", "5"]) == 0
    st = json.load(open(d / "state.json"))
    assert st["engine"] == "handdrawn" and st["stages"]["script"]["status"] == "needs_agent"
    assert (d / "TODO_script.md").exists() and json.load(open(d / "project.json"))["_todo"]
