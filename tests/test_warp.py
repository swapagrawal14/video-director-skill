import math, os, sys
import numpy as np
from PIL import Image

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'motion2d'))
from warp import mls_map, warp_rgba, rotate_about, Puppet  # noqa: E402


def _sample(mx, my, pt):
    x, y = int(round(pt[0])), int(round(pt[1]))
    return float(mx[y, x]), float(my[y, x])


def test_pins_land_exactly_translation():
    src = [(50, 50), (150, 50), (100, 150)]
    dst = [(x + 10, y - 5) for x, y in src]
    mx, my = mls_map(src, dst, (200, 200), grid=8)
    for s, d in zip(src, dst):
        assert math.dist(_sample(mx, my, d), s) < 0.5


def test_global_rotation_is_rigid():
    src = [(50, 50), (150, 50), (100, 150), (60, 140)]
    dst = [rotate_about(p, (100, 100), 20) for p in src]
    mx, my = mls_map(src, dst, (200, 200), grid=8)
    c = rotate_about((120, 90), (100, 100), 20)
    assert math.dist(_sample(mx, my, c), (120, 90)) < 1.0


def test_identity_when_pins_unmoved():
    mx, my = mls_map([(10, 10), (90, 90)], [(10, 10), (90, 90)], (100, 100))
    assert abs(mx[40, 30] - 30) < 1e-3 and abs(my[40, 30] - 40) < 1e-3


def test_puppet_bend_moves_tip_keeps_anchor():
    im = Image.new('RGBA', (300, 300), (0, 0, 0, 0))
    a = np.array(im); a[140:160, 40:260] = (20, 20, 20, 255)   # a horizontal 'arm'
    P = Puppet(Image.fromarray(a), {'shoulder': (50, 150), 'elbow': (150, 150), 'hand': (250, 150)}, pad=40)
    out = np.array(P.bend('elbow', ['hand'], -40))
    assert out.shape == (380, 380, 4)
    # shoulder still opaque at its pin (+pad), hand pixels moved up
    assert out[150 + 40, 50 + 40, 3] > 200
    assert out[150 + 40, 245 + 40, 3] < 50
    hx, hy = rotate_about((250, 150), (150, 150), -40)
    assert out[int(hy) + 40, int(hx) + 40, 3] > 200


def test_no_dark_fringe_on_edges():
    a = np.zeros((120, 120, 4), np.uint8); a[30:90, 30:90] = (250, 250, 250, 255)
    out = np.array(warp_rgba(Image.fromarray(a), [(30, 30), (90, 90)], [(34, 30), (94, 92)]))
    edge = out[(out[..., 3] > 10) & (out[..., 3] < 245)]
    assert len(edge) == 0 or edge[:, :3].min() > 200
