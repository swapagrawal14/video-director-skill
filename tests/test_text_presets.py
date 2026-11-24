"""Text / caption presets (docs/TEXT_STYLES.md): captions.py presets, no silent default, legacy --style unchanged,
motion2d/textfx.py title motions, template TEXTFX kit, lint text-look checks."""
import json
import os
import re
import shutil
import subprocess
import sys

import numpy as np
import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CAP = os.path.join(ROOT, "scripts", "captions.py")
LINT = os.path.join(ROOT, "scripts", "lint.py")
sys.path.insert(0, os.path.join(ROOT, "scripts"))
sys.path.insert(0, os.path.join(ROOT, "motion2d"))
from text_presets import CAPTION_PRESETS, TITLE_MOTIONS, STEP_STYLES  # noqa: E402

PAL = "#2f3e46,#f1faee,#e76f51,#84a98c"


@pytest.fixture()
def words(tmp_path):
    ws, t = [], 0.0
    for i, w in enumerate("Namaste doston, aaj hum seekhenge Adams clasp kaise banta hai. Pehle wire ko bend karo!".split()):
        ws.append({"word": w, "start": round(t, 2), "end": round(t + 0.3, 2)}); t += 0.9 if i % 5 == 4 else 0.38
    p = tmp_path / "words.json"; p.write_text(json.dumps(ws)); return p


def run_cap(*args):
    return subprocess.run([sys.executable, CAP, *map(str, args)], capture_output=True, text=True)


def parse_ass(txt):
    assert txt.startswith("[Script Info]")
    for sec in ("[V4+ Styles]", "[Events]"): assert sec in txt
    styles = [l for l in txt.splitlines() if l.startswith("Style: ")]
    events = [l for l in txt.splitlines() if l.startswith("Dialogue: ")]
    fmt = [l for l in txt.splitlines() if l.startswith("Format: Name")][0]
    nf = len(fmt.split(":", 1)[1].split(","))
    for s in styles: assert len(s.split(":", 1)[1].split(",")) == nf, s
    names = {s.split(":", 1)[1].split(",")[0].strip() for s in styles}
    tre = re.compile(r"^\d:\d\d:\d\d\.\d\d$")
    for e in events:
        f = e.split(":", 1)[1].split(",", 9)
        assert len(f) == 10 and tre.match(f[1]) and tre.match(f[2]) and f[3] in names, e
        assert f[1] < f[2] or len(f[1]) != len(f[2]), e
        assert f[9].count("{") == f[9].count("}"), e
    return styles, events


def test_every_caption_preset_valid_and_distinct(tmp_path, words):
    assert len(CAPTION_PRESETS) >= 8
    seen = {}
    for p in CAPTION_PRESETS:
        out = tmp_path / f"{p}.ass"
        r = run_cap(words, out, "--w", 1080, "--h", 1920, "--preset", p, "--palette", PAL)
        assert r.returncode == 0, r.stderr
        styles, events = parse_ass(out.read_text(encoding="utf-8"))
        assert len(styles) == 1 and events, p
        body = styles[0].split(",", 1)[1]           # style line without its name
        assert body not in seen.values(), f"{p} has the same style line as {[k for k, v in seen.items() if v == body]}"
        seen[p] = body
    assert "Caveat" in seen["chalk-hand"]
    # palette drives colours: accent #e76f51 -> ASS &H00516FE7 somewhere in pop-word
    assert "&H00516FE7" in (tmp_path / "pop-word.ass").read_text()


def test_no_default_style_errors(tmp_path, words):
    r = run_cap(words, tmp_path / "x.ass")
    assert r.returncode != 0 and "TEXT_STYLES.md" in r.stderr
    assert not (tmp_path / "x.ass").exists()
    r = run_cap(words, tmp_path / "x.ass", "--preset", "comic-sans-wobble")
    assert r.returncode != 0 and "unknown caption preset" in r.stderr


def test_project_look_drives_preset(tmp_path, words):
    proj = tmp_path / "proj"; proj.mkdir()
    (proj / "project.json").write_text(json.dumps({"look": {"captions_preset": "lower-third-ticker",
                                                            "palette": ["#0e1621", "#7fd1ff", "#f4f1ea", "#ff8a3d"],
                                                            "captions_position": "top"}}))
    out = tmp_path / "p.ass"
    r = run_cap(words, out, "--project", proj, "--w", 1280, "--h", 720)
    assert r.returncode == 0, r.stderr
    st, _ = parse_ass(out.read_text())
    assert st[0].startswith("Style: lower-third-ticker,") and ",7," in st[0]     # top-left alignment


def test_legacy_style_pop_karaoke_unchanged(tmp_path, words):
    """--style pop|karaoke keep the original output (yellow FFE500 active, Baloo 2, style name Cap)."""
    for s in ("pop", "karaoke"):
        out = tmp_path / f"{s}.ass"
        assert run_cap(words, out, "--style", s).returncode == 0
        txt = out.read_text()
        st, ev = parse_ass(txt)
        assert st == ["Style: Cap,Baloo 2,70,&H0000E5FF,&H00FFFFFF,&H00000000,&H80000000,1,0,0,0,100,100,0,0,1,5,2,2,60,60,86,1"]
        assert "WrapStyle: 2" in txt
        if s == "karaoke": assert all("\\kf" in e for e in ev)
        else: assert any("\\fscx118" in e for e in ev)


# ---------------------------------------------------------------- 2D title motion
def test_textfx_presets_match_title_motions():
    from textfx import PRESETS
    assert set(PRESETS) == set(TITLE_MOTIONS) - {"none"}


@pytest.mark.parametrize("preset", [p for p in TITLE_MOTIONS if p != "none"])
def test_textfx_renders_and_settles(preset):
    from textfx import text_fx, settle_time
    txt = "Adams clasp\nstep 2"
    kw = dict(size=64, palette=["#0f1b2d", "#ffd166", "#d8dee6", "#ef6f6c"])
    size0 = None
    for t in (0.3, 0.6, 1.0, 2.0):
        im = text_fx(preset, txt, t, **kw)
        assert im.mode == "RGBA"
        size0 = size0 or im.size
        assert im.size == size0, "layer size must not change over time"
        assert np.asarray(im)[..., 3].max() > 0, f"{preset} empty at t={t}"
    assert np.asarray(text_fx(preset, txt, -0.5, **kw))[..., 3].max() == 0
    st = settle_time(preset, txt)
    a1 = np.asarray(text_fx(preset, txt, st + 0.05, **kw))
    a2 = np.asarray(text_fx(preset, txt, st + 3.0, **kw))
    assert np.array_equal(a1, a2), f"{preset} still moving after settle_time"
    cover = (a1[..., 3] > 0).mean()
    assert cover > 0.02, f"{preset} final frame nearly empty ({cover:.3f})"


def test_textfx_unknown_preset():
    from textfx import text_fx
    with pytest.raises(ValueError):
        text_fx("wobble", "x", 1.0)


# ---------------------------------------------------------------- three.js template kit
def test_template_textfx_kit_runs_every_mode():
    node = shutil.which("node")
    if not node: pytest.skip("node not installed")
    src = open(os.path.join(ROOT, "template", "index.html"), encoding="utf-8").read()
    for name in list(TITLE_MOTIONS) + list(STEP_STYLES) + list(CAPTION_PRESETS):
        assert f"'{name}'" in src or name in ("card-rise", "chip", "pill", "none"), name
    assert "<svg" not in src.lower()
    r = subprocess.run([node, os.path.join(ROOT, "tests", "js", "textfx_smoke.mjs"), os.path.join(ROOT, "template", "index.html")],
                       capture_output=True, text=True, timeout=60)
    assert r.returncode == 0 and r.stdout.startswith("OK"), r.stderr + r.stdout


# ---------------------------------------------------------------- lint
GOOD_LOOK = {"set": "slate tile with chalk marks", "palette": ["#2f3e46", "#f1faee", "#e76f51", "#84a98c"],
             "character": "none", "type": "chalk titles", "captions": "chalk captions", "camera": "fixed occlusal",
             "signature": "the coil winds like a watch spring", "title_motion": "draw-on", "captions_preset": "chalk-hand"}


def lint_look(tmp_path, look):
    d = tmp_path / "p"; d.mkdir(exist_ok=True)
    (d / "project.json").write_text(json.dumps({"title": "Z-spring", "look": look, "scenes": [
        {"type": "title", "secs": 5, "sub": "Z-spring"}, {"type": "end", "secs": 5, "sub": "Credit: Swapnil Agrawal (BDS intern)"}]}))
    r = subprocess.run([sys.executable, LINT, str(d), "--json"], capture_output=True, text=True)
    o = json.loads(r.stdout); return r.returncode, o["errors"], o["warnings"]


def test_lint_text_look(tmp_path):
    rc, E, _ = lint_look(tmp_path, GOOD_LOOK); assert rc == 0, E
    for k in ("title_motion", "captions_preset"):
        rc, E, _ = lint_look(tmp_path, {x: v for x, v in GOOD_LOOK.items() if x != k})
        assert rc == 1 and any(f"look.{k} is missing" in e for e in E)
        rc, E, _ = lint_look(tmp_path, {**GOOD_LOOK, k: "sparkle-zoom"})
        assert rc == 1 and any(f"look.{k}" in e and "not a known preset" in e for e in E)
    rc, E, _ = lint_look(tmp_path, {**GOOD_LOOK, "step_style": "ribbon"})
    assert rc == 1 and any("look.step_style" in e for e in E)


def test_lint_braces_text_clone(tmp_path):
    clone = {**GOOD_LOOK, "title_motion": "card-rise", "captions_preset": "pop-word"}
    rc, E, _ = lint_look(tmp_path, clone)
    assert rc == 1 and any("clones examples/braces-tutorial" in e for e in E)
    rc, E, W = lint_look(tmp_path, {**clone, "captions_preset": "pill"})
    assert rc == 1 and any("braces-tutorial" in e for e in E)
    rc, E, W = lint_look(tmp_path, {**clone, "reuse_reason": "part 2 of her braces series, she asked for the same look"})
    assert rc == 0, E
    assert any("braces-tutorial" in w for w in W)
    rc, E, _ = lint_look(tmp_path, {**clone, "captions_preset": "minimal-serif"})   # card-rise alone is fine
    assert rc == 0, E


def test_examples_lint_clean():
    for ex in ("dhai-baje", "painted-duet"):
        r = subprocess.run([sys.executable, LINT, os.path.join(ROOT, "examples", ex), "--json"], capture_output=True, text=True)
        assert r.returncode == 0, r.stdout
