import os, sys
import numpy as np
import pytest
from PIL import Image, ImageDraw

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'motion2d'))
import handdrawn as hd  # noqa: E402


def _flat(size=160, outline=True):
    im = Image.new('RGBA', (size, size), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    kw = dict(outline=(20, 20, 30, 255), width=6) if outline else {}
    d.ellipse((20, 20, size - 20, size - 20), fill=(255, 200, 60, 255), **kw)
    d.rectangle((60, 60, 100, 100), fill=(60, 120, 220, 255), **kw)
    return im


def _lineart(size=160):
    im = Image.new('RGBA', (size, size), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    d.line((20, 30, 140, 30), fill=(15, 15, 20, 255), width=7)
    d.ellipse((40, 60, 120, 140), fill=(250, 120, 90, 255), outline=(15, 15, 20, 255), width=7)
    return im


# ---------------------------------------------------------------- holds
def test_on_twos_holds_two_frames():
    fps = 24
    got = [hd.on_twos(f / fps, fps) for f in range(8)]
    assert [d for _, d in got] == [0, 0, 1, 1, 2, 2, 3, 3]
    assert got[0][0] == got[1][0] == 0.0 and got[2][0] == pytest.approx(2 / fps)
    assert [hd.on_threes(f / fps, fps)[1] for f in range(7)] == [0, 0, 0, 1, 1, 1, 2]
    assert [hd.on_ones(f / fps, fps)[1] for f in range(3)] == [0, 1, 2]
    assert hd.hold_step(5, 2) == (4, 2)


def test_holds_mixed_segments_monotonic():
    H = hd.Holds([(0, 2), (0.25, 1), (0.5, 3)], fps=24)
    ds = [H(f / 24)[1] for f in range(24)]
    assert ds == sorted(ds)
    assert ds[:6] == [0, 0, 1, 1, 2, 2]                       # twos
    assert ds[6:12] == [3, 4, 5, 6, 7, 8]                     # ones
    assert ds[12:15] == [9, 9, 9]                             # threes
    t_h, _ = H(13 / 24); assert t_h == pytest.approx(12 / 24)


# ---------------------------------------------------------------- boil
def test_boil_changes_only_on_drawing_change():
    im = _flat(); fps = 24
    outs = [np.array(hd.boil(im, hd.on_twos(f / fps, fps)[1], seed=3)) for f in range(4)]
    assert np.array_equal(outs[0], outs[1]) and np.array_equal(outs[2], outs[3])
    assert not np.array_equal(outs[1], outs[2])
    assert np.array_equal(np.array(hd.boil(im, 7, seed=3)), np.array(hd.boil(im, 7, seed=3)))
    assert not np.array_equal(np.array(hd.boil(im, 7, seed=3)), np.array(hd.boil(im, 7, seed=4)))


def test_boil_keeps_shape_and_type():
    im = _flat()
    out = hd.boil(im, 2)
    assert isinstance(out, Image.Image) and out.size == im.size
    fr = np.full((90, 120, 3), 200, np.uint8)
    o2 = hd.boil(fr, 1)
    assert o2.shape == fr.shape and o2.dtype == np.uint8
    c0 = (np.array(im)[..., 3] > 40).mean(); c1 = (np.array(out)[..., 3] > 40).mean()
    assert abs(c1 - c0) / c0 < 0.05


# ---------------------------------------------------------------- paper + textures
def test_paper_and_grain_deterministic():
    p = hd.paper(64, 96, '#F4EEE1', seed=2)
    assert p.shape == (96, 64, 3) and p.dtype == np.float32
    assert np.array_equal(p, hd.paper(64, 96, '#F4EEE1', seed=2))
    assert p.std() > 0.5                                      # has tooth
    fr = np.full((96, 64, 3), 180, np.float32)
    g0, g1 = hd.grain(fr, 0, variants=3), hd.grain(fr, 1, variants=3)
    assert g0.dtype == np.uint8 and not np.array_equal(g0, g1)
    assert np.array_equal(hd.grain(fr, 0, variants=3), hd.grain(fr, 3, variants=3))
    assert np.array_equal(hd.grain(fr, 0), hd.grain(fr, 5))  # variants=1: static sheet


@pytest.mark.parametrize('kind', hd.TEXTURES)
def test_texture_fill_and_texturize(kind):
    m = np.zeros((80, 100), bool); m[10:70, 20:90] = True
    t = hd.texture_fill(m, '#E8553A', kind, seed=1)
    a = np.array(t)
    assert t.size == (100, 80) and a[~m, 3].max() == 0 and a[m, 3].mean() > 40
    assert np.array_equal(a, np.array(hd.texture_fill(m, '#E8553A', kind, seed=1)))
    im = _flat()
    tx = np.array(hd.texturize(im, kind, seed=1)); src = np.array(im)
    assert tx.shape == src.shape
    ink = (src[..., :3].astype(int) @ [299, 587, 114] // 1000 < 70) & (src[..., 3] == 255)
    assert np.array_equal(tx[ink], src[ink])                  # ink lines untouched
    assert not np.array_equal(tx, src)


# ---------------------------------------------------------------- draw-on
def test_draw_on_empty_at_0_full_at_1():
    im = _lineart(); D = hd.InkDrawOn(im)
    assert np.array(D.frame(0.0))[..., 3].max() == 0
    assert np.array_equal(np.array(D.frame(1.0)), np.array(im))
    cov = [(np.array(D.frame(p))[..., 3] > 0).sum() for p in (0.1, 0.3, 0.5, 0.7, 0.9)]
    assert cov == sorted(cov) and cov[0] > 0
    half = np.array(D.frame(0.5))
    assert half[..., 3][np.array(im)[..., 0] > 200].max() == 0  # fill (red-ish) not yet washed in
    assert D.tip(0.3) is not None and D.tip(0.0) is None


def test_draw_on_line_art_on_white_paper():
    im = Image.new('RGB', (120, 80), 'white'); ImageDraw.Draw(im).line((10, 40, 110, 40), fill='black', width=5)
    D = hd.InkDrawOn(im)
    x0 = D.tip(0.2)[0]; x1 = D.tip(0.7)[0]
    assert x1 > x0                                            # pen moves along the line
    assert np.array(D.frame(0.0))[..., 3].max() == 0


# ---------------------------------------------------------------- outline / smear / onion
def test_wobble_outline_pads_and_inks():
    im = _flat(outline=False)
    o = hd.wobble_outline(im, 0, width=6, pad=8)
    a = np.array(o)
    assert o.size == (im.width + 16, im.height + 16)
    dark = (a[..., 3] > 200) & (a[..., :3].max(2) < 60)
    assert dark.sum() > 300                                   # an ink line exists
    assert np.array_equal(a, np.array(hd.wobble_outline(im, 0, width=6, pad=8)))
    assert np.array_equal(a, np.array(hd.wobble_outline(im, 1, width=6, pad=8))) is False


def test_smears():
    im = _flat()
    for kind in ('stretch', 'multiples', 'trail'):
        s = hd.smear(im, 30, 0, kind=kind)
        assert s.size == (im.width + 2 * 32, im.height + 2 * 32)
        cov = (np.array(s)[..., 3] > 30).sum()
        assert cov > (np.array(im)[..., 3] > 30).sum()       # trail adds coverage
    assert hd.smear_amount(10, 0) == 0 and hd.smear_amount(200, 0) == 1
    w = Image.new('RGBA', (64, 64), (0, 0, 0, 0)); ImageDraw.Draw(w).rectangle((28, 4, 36, 60), fill=(0, 0, 0, 255))
    b = np.array(hd.spin_smear(w, 60))
    assert b.shape == (64, 64, 4) and ((b[..., 3] > 0) & (b[..., 3] < 250)).sum() > 100


def test_onion_skin():
    base = np.full((60, 80, 3), 230, np.uint8)
    fr = []
    for x in (10, 10, 25, 25, 40, 40):
        f = base.copy(); f[20:40, x:x + 10] = 20; fr.append(f)
    o = hd.onion_skin(fr, 2, before=1, after=1, label=False)
    assert o.shape == base.shape and o.dtype == np.uint8
    assert o[30, 13, 2] > o[30, 13, 1]                         # previous drawing tinted red (BGR)
    assert o[30, 43, 1] > o[30, 43, 2]                         # next drawing tinted green
    assert np.array_equal(o[30, 28], fr[2][30, 28])            # current untouched
