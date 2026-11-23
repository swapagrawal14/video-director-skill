import os, sys
import numpy as np
from PIL import Image, ImageDraw

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'motion2d'))
from doodle import (PALETTES, asset_prompt, line_boil, flat_bg, DOODLE_FINISH, speed_lines,  # noqa: E402
                    impact_burst, pop_text, wheel_spin, bounce)


def _cutout(size=200):
    im = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.ellipse((40, 40, 160, 160), fill=(255, 244, 222, 255), outline=(17, 17, 17, 255), width=6)
    d.rectangle((80, 20, 120, 60), fill=(255, 92, 138, 255), outline=(17, 17, 17, 255), width=6)
    return im


def _cov(im):
    return float((np.array(im)[..., 3] > 40).mean())


def test_line_boil_deterministic_and_holds():
    im = _cutout()
    a0 = np.array(line_boil(im, 0)); a1 = np.array(line_boil(im, 1)); a0b = np.array(line_boil(im, 0))
    assert np.array_equal(a0, a0b)                         # deterministic per step
    assert np.array_equal(a0, a1)                          # same hold (hold=3)
    a3 = np.array(line_boil(im, 3))
    assert not np.array_equal(a0, a3)                      # next hold changes
    assert np.abs(a0.astype(int) - a3.astype(int)).max() > 20


def test_line_boil_preserves_alpha_coverage():
    im = _cutout(); c = _cov(im)
    for step in (0, 3, 6, 30):
        assert abs(_cov(line_boil(im, step)) - c) / c < 0.05


def test_asset_prompt_words():
    for kind in ('character', 'prop', 'logo_mark'):
        for pal in PALETTES:
            p = asset_prompt('ice-cream truck mascot', pal, kind)
            assert '#00FF00' in p and 'outline' in p.lower() and 'NEGATIVE' in p
            assert 'svg' not in p.lower()
    bg = asset_prompt('bedroom', 'pastel_cel', 'background')
    assert 'svg' not in bg.lower() and 'outline' in bg.lower()


def test_fx_draw_something():
    W = H = 256
    base = flat_bg(W, H, 'sunny_lineart')
    fr = speed_lines(base.copy(), (128, 128), 0, 0.3, color=PALETTES['sunny_lineart']['ink'])
    assert np.abs(fr - base).sum() > 0
    fr = impact_burst(base.copy(), (128, 128), 0.08)
    assert np.abs(fr - base).sum() > 0
    fr = pop_text(base.copy(), 'COOL!', None, (128, 128), 0.15, size=60, stroke_px=5)
    assert np.abs(fr - base).sum() > 0
    out = DOODLE_FINISH(W, H)(fr, 0)
    assert out.dtype == np.uint8 and out.shape == (H, W, 3)


def test_bounce_squash_at_landing():
    dy, sx, sy = bounce(0.0, period=0.5, height=60)
    assert abs(dy) < 1e-6 and sx > 1.05 and sy < 0.95
    dy, sx, sy = bounce(0.25, period=0.5, height=60)
    assert abs(dy + 60) < 1e-6 and abs(sx - 1) < 0.05 and abs(sy - 1) < 0.05


def test_wheel_spin_keeps_size():
    w = _cutout(); r = wheel_spin(w, 0.25, rpm=60)
    assert r.size == w.size and not np.array_equal(np.array(r), np.array(w))
