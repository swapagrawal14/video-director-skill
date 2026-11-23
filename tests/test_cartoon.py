import json, os, subprocess, sys
import numpy as np
import cv2
import pytest
from PIL import Image, ImageDraw

ROOT = os.path.join(os.path.dirname(__file__), '..')
sys.path.insert(0, os.path.join(ROOT, 'motion2d'))
from cartoon import (ARTSTYLES, style_prompt, style_from_reference, palette_sheet, palette_match,  # noqa: E402
                     hold_time, seq, GRADES, grade, Light, light_pool, glow_eyes, spin, swing, shake, push,
                     camera_frame, Parallax, TinyPlanet, BeatSheet, Episode, paper_texture, make_style_finish,
                     night_grade_for)


# ------------------------------------------------------------------ synthetic inputs
def _rgb(h):
    return int(h[1:3], 16), int(h[3:5], 16), int(h[5:7], 16)


def _bgr(h):
    r, g, b = _rgb(h)
    return b, g, r


def _ref_image(outline=6):
    """Pastel BGR scene: sky, ground, three blobs; with or without dark navy outlines."""
    im = np.full((360, 640, 3), (255, 240, 200), np.uint8)
    cv2.rectangle(im, (0, 250), (640, 360), (180, 230, 170), -1)
    for x, c in [(150, (196, 92, 242)), (330, (255, 123, 140)), (500, (179, 231, 255))]:
        cv2.circle(im, (x, 150), 70, c, -1, cv2.LINE_AA)
        if outline: cv2.circle(im, (x, 150), 70, (58, 30, 30), outline, cv2.LINE_AA)
    if outline: cv2.line(im, (0, 250), (640, 250), (58, 30, 30), outline)
    return im


def _cutout(colors, ink=None, size=200):
    im = Image.new('RGBA', (size, size), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    d.ellipse((30, 30, 170, 170), fill=_rgb(colors[0]) + (255,),
              outline=(_rgb(ink) + (255,)) if ink else None, width=6 if ink else 0)
    d.rectangle((80, 10, 120, 60), fill=_rgb(colors[1]) + (255,))
    return im


def _bar(size=101):
    """RGBA: opaque bar from the centre pointing right (+x)."""
    im = Image.new('RGBA', (size, size), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    c = size // 2
    d.rectangle((c, c - 4, size - 5, c + 4), fill=(255, 255, 255, 255))
    return im


def _centroid(mask):
    ys, xs = np.nonzero(mask)
    return xs.mean(), ys.mean()


# ------------------------------------------------------------------ art styles
REQ = {'label', 'core', 'outline_px', 'ink', 'palette', 'boil', 'paper', 'grain', 'hold', 'squash', 'night'}


def _valid_hex(h):
    return isinstance(h, str) and len(h) == 7 and h[0] == '#' and all(c in '0123456789abcdefABCDEF' for c in h[1:])


def test_artstyles_complete_and_valid():
    assert len(ARTSTYLES) >= 8
    for name, s in ARTSTYLES.items():
        assert REQ <= set(s), (name, REQ - set(s))
        assert _valid_hex(s['ink']), name
        assert 4 <= len(s['palette']) <= 8, name
        for h in s['palette']:
            assert _valid_hex(h), (name, h)
            r, g, b = _rgb(h)
            # nothing chroma-key green: would be keyed out of the asset
            near_green = g > 180 and r < 110 and b < 110
            assert not near_green, (name, h)
            assert np.sqrt(r ** 2 + (g - 255) ** 2 + b ** 2) > 120, (name, h)
        assert s['outline_px'] >= 0 and isinstance(s['outline_px'], int)
        assert s['hold'] in ('ones', 'twos', 'threes')
        assert s['night'] in GRADES, name
        assert night_grade_for(name) == s['night']
    assert night_grade_for({'palette': []}) == 'night'


def test_style_prompt_words():
    for name, s in ARTSTYLES.items():
        for kind in ('character', 'pose', 'prop', 'part'):
            p = style_prompt(name, 'a sleepy boy', kind=kind)
            assert p.startswith('a sleepy boy.')
            assert 'NEGATIVE:' in p
            assert all(h in p for h in s['palette'])
            assert '#00FF00' in p and 'chroma' in p
            assert 'green tones on the subject' in p.split('NEGATIVE:')[1]
            if s['outline_px'] == 0:
                assert 'no outlines' in p
            else:
                assert f"outline {s['outline_px']} px" in p and s['ink'] in p
        ps = style_prompt(name, 'a bedroom', kind='set')
        assert 'chroma' not in ps and '#00FF00' not in ps
        assert 'green tones' not in ps
        assert 'empty of characters' in ps and 'NEGATIVE:' in ps
    # dict style works the same as a name, screen + extra honoured
    assert style_prompt(ARTSTYLES['anime_cel'], 'x') == style_prompt('anime_cel', 'x')
    p = style_prompt('anime_cel', 'x', screen='#0000FF', extra='looking left')
    assert '#0000FF' in p and 'looking left' in p


# ------------------------------------------------------------------ style from reference
def test_style_from_reference_detects_outline():
    s = style_from_reference(_ref_image(6))
    m = s['measured']
    assert m['has_outline'] is True and s['outline_px'] >= 2
    r, g, b = _rgb(s['ink'])
    assert max(r, g, b) < 90                                  # dark ink
    assert 'no outlines' not in s['core'] and s['ink'] in s['core']
    assert len(s['palette']) == 6 and all(_valid_hex(h) for h in s['palette'])
    assert m['flatness'] > 0.8 and m['texture'] < 60
    assert REQ <= set(s)
    # usable everywhere a pack is
    assert 'NEGATIVE:' in style_prompt(s, 'a cat')
    assert palette_sheet(s).shape == (220, 900, 3)


def test_style_from_reference_flat_no_outline():
    s = style_from_reference(_ref_image(0), k=5)
    assert s['measured']['has_outline'] is False
    assert s['outline_px'] == 0 and s['boil'] == 0.0
    assert 'no outlines' in s['core']
    assert len(s['palette']) == 5
    assert 'no outlines at all' in style_prompt(s, 'a cat')


def test_style_from_reference_deterministic_and_inputs(tmp_path):
    im = _ref_image(6)
    a = style_from_reference(im); b = style_from_reference(im)
    assert a == b
    pil = Image.fromarray(cv2.cvtColor(im, cv2.COLOR_BGR2RGB))
    assert style_from_reference(pil)['palette'] == a['palette']
    p = tmp_path / 'ref.png'; cv2.imwrite(str(p), im)
    assert style_from_reference(str(p))['palette'] == a['palette']
    with pytest.raises(ValueError):
        style_from_reference(str(tmp_path / 'missing.png'))


@pytest.mark.parametrize('path,outline', [('/workspace/work/pin.mp4', False), ('/workspace/work/pin2.mp4', True)])
def test_style_from_reference_real_videos(path, outline):
    if not os.path.exists(path): pytest.skip('reference video not present')
    assert style_from_reference(path)['measured']['has_outline'] is outline


# ------------------------------------------------------------------ palette tools
def test_palette_sheet_swatches():
    s = ARTSTYLES['pastel_outline']
    sh = palette_sheet('pastel_outline', w=600, h=100)
    assert sh.shape == (100, 600, 3) and sh.dtype == np.uint8
    bw = 600 // len(s['palette'])
    for i, h in enumerate(s['palette']):
        assert tuple(sh[10, i * bw + bw // 2]) == _bgr(h)


def test_palette_match_on_and_off_palette():
    s = ARTSTYLES['pastel_outline']
    on = _cutout(s['palette'][:2], ink=s['ink'])
    off = _cutout(['#00FF00', '#FF8000'], ink='#808000')
    assert palette_match(on, 'pastel_outline') > 0.95
    assert palette_match(off, 'pastel_outline') < 0.1
    # transparent pixels ignored, empty -> 0
    assert palette_match(Image.new('RGBA', (20, 20), (0, 255, 0, 0)), 'pastel_outline') == 0.0
    # plain RGB array input
    arr = np.zeros((10, 10, 3), np.uint8); arr[:] = _rgb(s['palette'][3])
    assert palette_match(arr, s) == 1.0


# ------------------------------------------------------------------ timing
def test_hold_time_quantises():
    for step in range(0, 500):
        t = step / 24
        assert hold_time(t, 'ones') == pytest.approx(step / 24)
        assert hold_time(t, 'twos') == pytest.approx((step // 2 * 2) / 24)
        assert hold_time(t, 'threes') == pytest.approx((step // 3 * 3) / 24)
        assert hold_time(t, 4) == pytest.approx((step // 4 * 4) / 24)
    assert hold_time(0.5, 'twos', fps=30) == pytest.approx(0.5 - (15 % 2) / 30)


def test_seq_picks_latest_key():
    table = [(2.0, 'b'), (0.0, 'a'), (5.0, 'c')]
    assert seq(-1, table) == 'b'                  # default = first row as given
    assert seq(-1, table, default='z') == 'z'
    assert seq(0.0, table) == 'a' and seq(1.99, table) == 'a'
    assert seq(2.0, table) == 'b' and seq(4.9, table) == 'b'
    assert seq(5.0, table) == 'c' and seq(99, table) == 'c'


# ------------------------------------------------------------------ grades + light
def _room():
    rs = np.random.RandomState(0)
    return rs.randint(40, 220, (60, 80, 3)).astype(np.uint8)


def test_grades_and_grade():
    for name, (mul, lift, sat) in GRADES.items():
        assert len(mul) == 3 and len(lift) == 3 and 0 < sat <= 1.2, name
    fr = _room()
    g = grade(fr, 'day')
    assert g.dtype == np.float32 and g.shape == fr.shape
    assert np.allclose(g, fr)
    assert np.allclose(grade(fr, 'powercut', amount=0.0), fr)
    assert grade(fr, 'powercut').mean() < fr.mean() * 0.7
    half = grade(fr, 'night', amount=0.5).mean()
    assert grade(fr, 'night').mean() < half < fr.mean()
    assert np.allclose(grade(fr, GRADES['sunset']), grade(fr, 'sunset'))
    assert grade(fr, 'horror').min() >= 0 and grade(fr, 'tv_glow').max() <= 255


def test_light_switch_is_instant():
    L = Light([(0, 'day'), (2.4, 'powercut'), (5.0, 'day')])
    assert L.level(0.0, 'day') == 1.0 and L.level(2.39, 'day') == 1.0 and L.level(2.39, 'powercut') == 0.0
    assert L.level(2.4, 'powercut') == 1.0 and L.level(2.4, 'day') == 0.0
    assert L.level(4.99, 'powercut') == 1.0 and L.level(5.0, 'day') == 1.0
    fr = _room()
    assert np.allclose(L.apply(fr, 1.0), grade(fr, 'day'))
    assert np.allclose(L.apply(fr, 3.0), grade(fr, 'powercut'))


def test_light_fade_levels():
    L = Light([(0, 'day'), (2.0, 'night')], fade=1.0)
    assert L.level(0.5, 'day') == 1.0 and L.level(0.5, 'night') == 0.0    # no transition yet
    assert L.level(2.0, 'night') == pytest.approx(0.0) and L.level(2.0, 'day') == pytest.approx(1.0)
    assert L.level(2.5, 'night') == pytest.approx(0.5) and L.level(2.5, 'day') == pytest.approx(0.5)
    assert L.level(3.5, 'night') == 1.0 and L.level(3.5, 'day') == 0.0
    vals = [L.level(2 + i / 10, 'night') for i in range(11)]
    assert all(b >= a for a, b in zip(vals, vals[1:]))                   # monotonic ease
    fr = _room()
    mid = L.apply(fr, 2.5)
    assert np.allclose(mid, 0.5 * grade(fr, 'day') + 0.5 * grade(fr, 'night'), atol=1e-3)
    for t in (0.0, 1.0, 2.5, 4.0):
        assert L.level(t, 'day') + L.level(t, 'night') == pytest.approx(1.0)


def test_light_flicker_bursts_then_settles():
    L = Light([(0, 'day'), (2.4, 'powercut')], flicker=[(2.4, 0.5)], seed=5)
    ts = [2.4 + i / 24 for i in range(12)]
    lv = [L.level(t, 'powercut') for t in ts]
    assert set(lv) <= {0.0, 1.0} and 0.0 in lv and 1.0 in lv            # really flickers on/off
    assert lv == [L.level(t, 'powercut') for t in ts]                     # deterministic
    assert [Light([(0, 'day'), (2.4, 'powercut')], flicker=[(2.4, 0.5)], seed=5).level(t, 'powercut') for t in ts] == lv
    assert L.level(2.95, 'powercut') == 1.0 and L.level(2.3, 'powercut') == 0.0   # settled / before
    fr = _room()
    for t, v in zip(ts, lv):
        assert np.allclose(L.apply(fr, t), grade(fr, 'powercut' if v == 1.0 else 'day'))


def test_light_pool_adds_light_locally():
    fr = np.full((100, 100, 3), 40, np.float32); orig = fr.copy()
    out = light_pool(fr, (50, 50), 30, color='#FFE7B3', strength=0.6)
    assert out is fr
    assert out[50, 50].mean() > 100 and np.allclose(out[0, 0], orig[0, 0]) and np.allclose(out[50, 85], 40)
    assert out[50, 50].mean() > out[50, 70].mean() > 40 - 1e-6
    assert out[50, 50][2] > out[50, 50][0]                                # warm: more red than blue (BGR)
    same = np.full((50, 50, 3), 40, np.float32)
    assert np.array_equal(light_pool(same, (500, 500), 10), np.full((50, 50, 3), 40, np.float32))
    assert np.array_equal(light_pool(same, (25, 25), 10, strength=0), np.full((50, 50, 3), 40, np.float32))


def test_glow_eyes_off_on_and_blink():
    base = np.full((200, 300, 3), 20, np.uint8)
    pts = [(40, 40), (80, 40)]
    off = glow_eyes(base.copy(), pts, 1.0, on=0.0)
    assert np.array_equal(off, base)
    full = glow_eyes(base.copy(), pts, 1.0, on=1.0)
    dim = glow_eyes(base.copy(), pts, 1.0, on=0.3)
    assert full.dtype == np.uint8 and full.shape == base.shape
    assert full[40, 40].astype(int).sum() > dim[40, 40].astype(int).sum() > base[40, 40].astype(int).sum()
    assert full[40, 52].astype(int).sum() > base[40, 52].astype(int).sum()         # bloom around the eye
    assert np.array_equal(full[190, 290], base[190, 290])                          # far away untouched
    assert np.array_equal(full, glow_eyes(base.copy(), pts, 1.0, on=1.0))          # deterministic
    blink = glow_eyes(base.copy(), pts, 1.0, on=1.0, blink=[(0.9, 0.2)])
    assert np.array_equal(blink, base)
    # pink by default: red channel dominates green (BGR)
    assert full[40, 48][2] > full[40, 48][1]


# ------------------------------------------------------------------ prop rigs
def test_spin_rotates_clockwise():
    bar = _bar()
    a0 = np.array(spin(bar, 0.0))
    assert np.array_equal(a0, np.array(bar.rotate(0)))
    q = np.array(spin(bar, 0.25, rpm=60))                 # quarter turn
    cx, cy = _centroid(q[..., 3] > 128)
    assert cy > 60 and abs(cx - 50) < 6                   # right-pointing bar now points down (clockwise)
    assert np.array_equal(np.array(spin(bar, 1.0, rpm=60))[..., 3] > 128, a0[..., 3] > 128)   # full turn


def test_spin_blur_is_average_of_rotations():
    bar = _bar()
    out = spin(bar, 0.1, rpm=60, blur_deg=40, steps=5)
    assert out.mode == 'RGBA' and out.size == bar.size
    a = -(0.1 * 60 / 60) * 360
    acc = sum(np.array(bar.rotate(a - 40 * i / 4, resample=Image.BICUBIC), np.float32) for i in range(5))
    assert np.array_equal(np.array(out), (acc / 5).astype(np.uint8))
    sharp = np.array(spin(bar, 0.1, rpm=60))[..., 3]; smear = np.array(out)[..., 3]
    partial = lambda al: int(((al > 10) & (al < 245)).sum())   # noqa: E731
    assert partial(smear) > 2 * partial(sharp)
    assert (smear > 10).sum() > (sharp > 10).sum()          # covers a wider arc


def test_swing_pendulum_and_damping():
    assert swing(0) == 0.0
    vals = [swing(t / 50) for t in range(500)]
    assert max(vals) == pytest.approx(8.0, abs=0.05) and min(vals) == pytest.approx(-8.0, abs=0.05)
    assert swing(1 / (4 * 0.6)) == pytest.approx(8.0)
    assert swing(3.0, t0=5.0) == 0.0
    early = max(abs(swing(t / 50, damp=1.0)) for t in range(0, 100))
    late = max(abs(swing(t / 50, damp=1.0)) for t in range(400, 500))
    assert late < early * 0.1


def test_shake_window_bounds_determinism():
    assert shake(0.9, 1.0) == (0.0, 0.0) and shake(1.5, 1.0, dur=0.35) == (0.0, 0.0)
    xs = [shake(1.0 + i / 100, 1.0) for i in range(35)]
    assert any(abs(dx) + abs(dy) > 1 for dx, dy in xs)
    assert all(abs(dx) <= 14 and abs(dy) <= 14 for dx, dy in xs)
    assert xs == [shake(1.0 + i / 100, 1.0) for i in range(35)]
    assert shake(1.01, 1.0, seed=1) != shake(1.01, 1.0, seed=2)
    early = np.mean([abs(dx) for dx, _ in xs[:8]]); late = np.mean([abs(dx) for dx, _ in xs[-8:]])
    assert late < early                                     # decays


def test_push_eases_and_clamps():
    assert push(0.0, 1.0, 3.0) == 1.0 and push(1.0, 1.0, 3.0) == 1.0
    assert push(2.0, 1.0, 3.0) == pytest.approx(1.06)
    assert push(3.0, 1.0, 3.0) == pytest.approx(1.12) and push(9.0, 1.0, 3.0) == pytest.approx(1.12)
    assert push(2.0, 2.0, 2.0, 1.0, 1.5) == 1.0


def test_camera_frame_identity_shift_zoom():
    fr = np.zeros((90, 120, 3), np.uint8); fr[40:50, 55:65] = 255
    same = camera_frame(fr)
    assert same.dtype == np.float32 and same.shape == fr.shape and np.allclose(same, fr)
    sh = camera_frame(fr, dx=10, dy=5)
    assert np.allclose(sh[45:55, 65:75], 255) and sh[42, 57].max() == 0
    z = camera_frame(fr, zoom=2.0)
    assert z[45, 60].min() == 255                             # centre stays put
    assert (z > 128).sum() > 3 * (fr > 128).sum()            # square grows ~4x


# ------------------------------------------------------------------ moving worlds
def _layer(w, h, seed=0):
    rs = np.random.RandomState(seed)
    a = np.zeros((h, w, 4), np.uint8); a[..., :3] = rs.randint(0, 255, (h, w, 3)); a[..., 3] = 255
    return a


def test_parallax_scrolls_by_depth_and_wraps():
    W, H = 160, 90
    ground = _layer(240, 30, 1)
    sky = np.zeros((H, 200, 3), np.uint8); sky[:] = (200, 150, 100)
    P = Parallax([(sky, 0.0), (ground, 1.0)], W, H, speed=40)
    f0 = P.render(0.0); f1 = P.render(0.5)
    assert f0.shape == (H, W, 3) and f0.dtype == np.float32
    assert np.allclose(f0[:60], f1[:60])                     # depth 0 sky is static
    assert np.allclose(f0[:60, 0], (200, 150, 100))          # BGR sky kept BGR
    # ground scrolled 20 px left: frame column x at t=.5 == column x+20 at t=0
    assert np.allclose(f1[60:, :W - 20], f0[60:, 20:])
    assert np.allclose(f0[60:], ground[:, :W, 2::-1])        # RGBA layer composited as BGR
    # wraps: one full tile later it repeats exactly; mid-wrap the seam is continuous with the tile start
    assert np.allclose(P.render(240 / 40), f0)
    f = P.render(200 / 40)                                    # off = 200, needs 40 px of tile then wrap
    assert np.allclose(f[60:, :40], ground[:, 200:, 2::-1]) and np.allclose(f[60:, 40:], ground[:, :120, 2::-1])
    base = np.full((H, W, 3), 7, np.uint8)
    assert np.allclose(Parallax([(np.zeros((10, 50, 4), np.uint8), 1)], W, H).render(0, base), 7)


def test_parallax_small_tile_and_tall_layer():
    W, H = 400, 100
    tile = _layer(100, 20, 2)                                 # tile narrower than W/2 must still tile
    f = Parallax([(tile, 1.0)], W, H, speed=30).render(1.0)   # off = 30
    assert f.shape == (H, W, 3)
    row = np.tile(tile, (1, 6, 1))[:, 30:30 + W, 2::-1]
    assert np.allclose(f[80:], row)
    tall = _layer(W * 2, 150, 3)                              # taller than the frame: bottom H rows show
    g = Parallax([(tall, 1.0)], W, H, speed=0).render(0.0)
    assert np.allclose(g, tall[50:, :W, 2::-1])
    pil = Image.fromarray(tall, 'RGBA')
    assert np.allclose(Parallax([(pil, 1.0)], W, H, speed=0).render(0.0), g)


def test_tiny_planet_draws_disc_and_props_move():
    disc = Image.new('RGBA', (100, 100), (0, 0, 0, 0)); ImageDraw.Draw(disc).ellipse((0, 0, 99, 99), fill=(255, 0, 0, 255))
    tree = Image.new('RGBA', (12, 30), (0, 0, 255, 255))      # pure blue prop
    P = TinyPlanet(disc, (200, 220), 80, props=[(tree, 0.0, 0)], deg_per_s=-18.0)
    assert P.top() == (200, 140) and P.angle(2.0) == -36.0

    def blue(fr):
        return (fr[..., 0] > 200) & (fr[..., 2] < 50)

    f0 = P.draw(np.zeros((300, 400, 3), np.float32), 0.0)
    assert f0[220, 200, 2] > 200 and f0[220, 200, 0] < 50     # red disc (BGR) at centre
    x0, y0 = _centroid(blue(f0))
    assert abs(x0 - 200) < 3 and 105 < y0 < 145               # tree stands on top of the hill
    f1 = P.draw(np.zeros((300, 400, 3), np.float32), 1.0)
    x1, y1 = _centroid(blue(f1))
    assert x1 > x0 + 10 and y1 > y0                            # planet turning: prop rides along the rim
    assert np.array_equal(f0, P.draw(np.zeros((300, 400, 3), np.float32), 0.0))
    f2 = P.draw(np.zeros((300, 400, 3), np.float32), 8.0)     # 144 deg round: below the horizon, hidden
    assert not blue(f2).any()


# ------------------------------------------------------------------ beat sheet + episode
BEATS = [(1.6, 'boy', 'reach', 'click'), (0.0, 'boy', 'stretch', 'yawn', 'opens'),
         (2.4, 'light', 'powercut', None), (3.0, 'cam', 'push', None), (3.2, 'ghost', 'peek', 'creak')]


def test_beatsheet_pose_since_sfx():
    B = BeatSheet(BEATS)
    assert [r['t'] for r in B.rows] == sorted(r['t'] for r in B.rows)
    assert B.rows[0]['note'] == 'opens' and B.rows[1]['note'] == ''
    assert B.pose('boy', -0.1) == 'idle' and B.pose('boy', 0.0) == 'stretch'
    assert B.pose('boy', 1.59) == 'stretch' and B.pose('boy', 1.6) == 'reach' and B.pose('boy', 9) == 'reach'
    assert B.pose('ghost', 1.0, default='hidden') == 'hidden'
    assert B.since('boy', 2.0) == pytest.approx(0.4) and B.since('ghost', 1.0) == 1e9
    assert B.sfx_events() == [(0.0, 'yawn'), (1.6, 'click'), (3.2, 'creak')]
    al = B.action_list()
    assert len(al.splitlines()) == 5 and 'stretch' in al and 'sfx=-' in al


def test_beatsheet_check_catches_long_holds_and_missing_sfx(tmp_path):
    ok = BeatSheet([(0.0, 'boy', 'a', 's1'), (3.0, 'boy', 'b', 's2'), (2.0, 'light', 'off', None), (1.0, 'cam', 'push', None)])
    assert ok.check(6.0) == []
    long_ = BeatSheet([(0.0, 'boy', 'a', 's1'), (5.0, 'boy', 'b', 's2')]).check(6.0)
    assert len(long_) == 1 and 'boy' in long_[0] and '5.0s' in long_[0]
    late_start = BeatSheet([(4.5, 'boy', 'a', 's1')]).check(6.0)        # gap from 0 counts too
    assert any('holds 4.5s' in p for p in late_start)
    tail = BeatSheet([(0.0, 'boy', 'a', 's1')]).check(4.5)              # and the gap to the end
    assert any('holds 4.5s' in p for p in tail)
    nos = BeatSheet([(0.0, 'boy', 'a', None), (1.0, 'boy', 'b', 's')]).check(3.0)
    assert nos == ["0.00s boy 'a' has no SFX"]
    missing = BeatSheet([(0.0, 'boy', 'a', 's')]).check(2.0, actors_on_screen=['boy', 'girl'])
    assert 'girl: no beats' in missing
    assert BeatSheet([(0.0, 'boy', 'a', 's'), (3.0, 'boy', 'b', 's')]).check(6.0, max_still=2.0) != []
    p = tmp_path / 'beats.json'; ok.to_json(str(p))
    rows = json.load(open(p))
    assert [r['act'] for r in rows] == ['a', 'push', 'off', 'b'] and set(rows[0]) == {'t', 'actor', 'act', 'sfx', 'note'}


def test_episode_at_boundaries():
    E = Episode([('wide', 2), ('close', 1.5), ('reveal', 3)])
    assert E.duration == pytest.approx(6.5)
    assert E.starts() == [(0.0, 'wide'), (2.0, 'close'), (3.5, 'reveal')]
    assert E.at(0.0) == (0, 'wide', 0.0, 0.0)
    i, n, lt, u = E.at(1.0); assert (i, n) == (0, 'wide') and lt == 1.0 and u == 0.5
    assert E.at(1.999)[0] == 0
    assert E.at(2.0)[:3] == (1, 'close', 0.0)                 # cut lands exactly on the boundary
    assert E.at(3.5)[:3] == (2, 'reveal', 0.0)
    i, n, lt, u = E.at(6.5); assert (i, n, u) == (2, 'reveal', 1.0) and lt == pytest.approx(3.0)
    assert E.at(10.0)[0] == 2 and E.at(10.0)[3] == 1.0      # past the end clamps to last shot
    assert E.at(-1.0)[0] == 0 and E.at(-1.0)[3] == 0.0


# ------------------------------------------------------------------ finish
def test_paper_texture():
    t = paper_texture(64, 48, 0.5)
    assert t.shape == (48, 64, 1) and t.dtype == np.float32
    assert np.array_equal(t, paper_texture(64, 48, 0.5)) and not np.array_equal(t, paper_texture(64, 48, 0.5, seed=1))
    assert 0.9 < t.min() <= t.max() <= 1.1 and t.std() > 0
    assert np.allclose(paper_texture(64, 48, 0.0), 1.0)
    assert paper_texture(64, 48, 1.0).std() > t.std()


def test_make_style_finish():
    fr = np.full((40, 60, 3), 128, np.float32)
    clean = make_style_finish(60, 40, 'flat_no_outline')
    out = clean(fr, 0)
    assert out.dtype == np.uint8 and np.array_equal(out, np.full((40, 60, 3), 128, np.uint8))
    f = make_style_finish(60, 40, 'rubber_hose', n=4)          # paper + grain
    a0, a1, a4 = f(fr, 0), f(fr, 1), f(fr, 4)
    assert a0.dtype == np.uint8 and a0.shape == fr.shape
    assert not np.array_equal(a0, a1) and np.array_equal(a0, a4)   # grain cycles every n steps
    assert np.array_equal(a0, make_style_finish(60, 40, 'rubber_hose', n=4)(fr, 0))
    assert a0.std() > 1
    assert make_style_finish(10, 10, 'rubber_hose')(np.full((10, 10, 3), 300, np.float32), 0).max() <= 255


# ------------------------------------------------------------------ CLI
def test_style_ref_script(tmp_path):
    ref = tmp_path / 'ref.png'; cv2.imwrite(str(ref), _ref_image(6))
    out = tmp_path / 'proj' / 'style.json'
    r = subprocess.run([sys.executable, os.path.join(ROOT, 'scripts', 'style_ref.py'), str(ref), str(out),
                        '--name', 'cosy_room', '--k', '5'], capture_output=True, text=True, timeout=120)
    assert r.returncode == 0, r.stderr
    st = json.load(open(out))
    assert st['label'].startswith('cosy_room') and len(st['palette']) == 5 and st['measured']['has_outline']
    sheet = cv2.imread(str(tmp_path / 'proj' / 'style_palette.png'))
    assert sheet is not None and sheet.shape == (220, 900, 3)
    assert 'NEGATIVE:' in r.stdout and 'wrote' in r.stdout
