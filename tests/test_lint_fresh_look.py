"""Anti-clone checks in scripts/lint.py (docs/FRESH_LOOK.md): every video needs its own look."""
import json
import os
import shutil
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LINT = os.path.join(ROOT, "scripts", "lint.py")

FRESH_LOOK = {
    "set": "glowing X-ray lightbox wall in a dark ortho lab",
    "palette": ["#0e1621", "#7fd1ff", "#f4f1ea", "#ff8a3d"],
    "character": "none; a gloved hand performs every step",
    "type": "condensed sans caps titles, mono labels",
    "captions": "white text on a thin cyan underline, bottom left",
    "camera": "macro slides along the wire, rack focus between steps",
    "signature": "each bend lights up on the radiograph as it is made",
}
FRESH_THEME = {"accent": "#ff8a3d", "accent2": "#7fd1ff", "highlight": "#f4f1ea",
               "background": ["#0e1621", "#15253a", "#223a55"], "bench": "#2a3442", "mat": "#0e1621"}
OWN_INDEX = """<!doctype html><html><body><canvas id=c></canvas><script>
// fresh scene built for this video
const c = document.getElementById('c'), g = c.getContext('2d');
window.renderAt = function (t) { g.fillStyle = '#0e1621'; g.fillRect(0, 0, 1280, 720);
  g.fillStyle = '#7fd1ff'; g.fillRect(100 + t * 40, 300, 200, 6); };
window.READY = true;
</script></body></html>
"""


def lint(d, *extra):
    r = subprocess.run([sys.executable, LINT, str(d), "--json", *extra], capture_output=True, text=True)
    out = json.loads(r.stdout)
    return r.returncode, out["errors"], out["warnings"]


def make_project(d, look=FRESH_LOOK, theme=FRESH_THEME, index=OWN_INDEX, scenes=None):
    d.mkdir(parents=True, exist_ok=True)
    P = {"title": "Hawley retainer", "credit": "Swapnil Agrawal (BDS intern)", "scenes": scenes or [
        {"type": "title", "secs": 5, "sub": "Hawley retainer, step by step"},
        {"secs": 6, "sub": "The labial bow sits on the canines"},
        {"type": "end", "secs": 5, "sub": "Credit: Swapnil Agrawal (BDS intern)"}]}
    if look is not None: P["look"] = look
    if theme is not None: P["theme"] = theme
    (d / "project.json").write_text(json.dumps(P, ensure_ascii=False), encoding="utf-8")
    if index is not None: (d / "index.html").write_text(index, encoding="utf-8")
    return d


def test_template_project_fails(tmp_path):
    d = tmp_path / "tpl"; d.mkdir()
    for f in ("project.json", "index.html"):
        shutil.copy(os.path.join(ROOT, "template", f), d / f)
    rc, E, _ = lint(d)
    assert rc == 1
    txt = " ".join(E)
    assert "CHANGE ME" in txt and "mascot" in txt and "bench" in txt and "copied from template/index.html" in txt


def test_fresh_project_passes_anti_clone(tmp_path):
    rc, E, _ = lint(make_project(tmp_path / "fresh"))
    assert rc == 0, E


def test_missing_look_fails(tmp_path):
    rc, E, _ = lint(make_project(tmp_path / "nolook", look=None))
    assert rc == 1 and any('no "look" block' in e for e in E)


def test_pixar_clinic_theme_fails_unless_reuse_reason(tmp_path):
    pixar = {"accent": "#e2475b", "accent2": "#3b82c4", "highlight": "#ffd23f",
             "background": ["#24557a", "#5fa6b8", "#f2cfa8"], "bench": "#c98e5a", "mat": "#3e8e93"}
    rc, E, _ = lint(make_project(tmp_path / "pixar", theme=pixar))
    assert rc == 1 and any("Pixar Clinic" in e for e in E)
    rc, E, W = lint(make_project(tmp_path / "reuse", theme=pixar, look={**FRESH_LOOK, "reuse_reason": "part 2 of a series"}))
    assert rc == 0, E
    assert any("reuse_reason" in w for w in W)


def test_copied_braces_index_fails(tmp_path):
    braces = open(os.path.join(ROOT, "examples", "braces-tutorial", "index.html"), encoding="utf-8").read()
    rc, E, _ = lint(make_project(tmp_path / "clone", index=braces))
    assert rc == 1
    assert any("copied from examples/braces-tutorial/index.html" in e for e in E)
    assert any("Dentu" in e for e in E)


def test_copied_braces_vo_fails(tmp_path):
    line = json.load(open(os.path.join(ROOT, "examples", "braces-tutorial", "script.json"), encoding="utf-8"))[3]
    scenes = [{"type": "title", "secs": 5, "sub": "Hook"}, {"vo": line, "sub": "Step one"},
              {"type": "end", "secs": 5, "sub": "Credit: Swapnil Agrawal (BDS intern)"}]
    rc, E, _ = lint(make_project(tmp_path / "vo", scenes=scenes))
    assert rc == 1 and any("script.json" in e for e in E)


def test_pre_build_skips_index_checks(tmp_path):
    d = make_project(tmp_path / "pre", index=open(os.path.join(ROOT, "template", "index.html"), encoding="utf-8").read())
    rc, E, _ = lint(d, "--pre-build")
    assert rc == 0, E
    rc, E, _ = lint(d)
    assert rc == 1
