import json, os, shutil, subprocess, sys

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')


def _proj(tmp_path, beats):
    d = tmp_path / 'p'
    shutil.copytree(os.path.join(ROOT, 'examples', 'painted-duet'), d)
    (d / 'beats.json').write_text(json.dumps(beats))
    return d


def _lint(d):
    r = subprocess.run([sys.executable, os.path.join(ROOT, 'scripts', 'lint.py'), str(d), '--json'], capture_output=True, text=True)
    return r.returncode, json.loads(r.stdout)


def test_lint_beats_ok(tmp_path):
    beats = [{'t': 0, 'actor': 'boy', 'act': 'stretch', 'sfx': 'yawn'},
             {'t': 2.5, 'actor': 'boy', 'act': 'reach', 'sfx': 'click'},
             {'t': 2.6, 'actor': 'light', 'act': 'powercut'},
             {'t': 5.0, 'actor': 'boy', 'act': 'sleep', 'sfx': 'squish'}]
    code, out = _lint(_proj(tmp_path, beats))
    assert not [e for e in out['errors'] if 'beats.json' in e], out


def test_lint_beats_long_hold_and_missing_sfx(tmp_path):
    beats = [[0, 'boy', 'idle', 'pop'], [1.0, 'boy', 'wave', None], [9.0, 'boy', 'sleep', 'squish']]
    code, out = _lint(_proj(tmp_path, beats))
    errs = [e for e in out['errors'] if 'beats.json' in e]
    assert code == 1
    assert any('holds' in e for e in errs) and any('no SFX' in e for e in errs), errs
