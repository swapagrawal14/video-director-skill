import os, sys
import numpy as np, cv2
from PIL import Image

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'motion2d'))
from inbetween import tween, tween_frames, Tweener, smear  # noqa: E402

W, H, R = 200, 140, 28


def _disc(cx, cy=70, rgb=(255, 255, 255)):
    """white (or rgb) disc with an anti-aliased ALPHA edge; colour is clean everywhere (straight alpha)."""
    a = np.zeros((H, W, 4), np.uint8); a[..., :3] = rgb
    m = np.zeros((H, W), np.uint8); cv2.circle(m, (cx, cy), R, 255, -1, cv2.LINE_AA)
    a[..., 3] = m
    return Image.fromarray(a, 'RGBA')


def _alpha(im):
    return np.asarray(im)[..., 3].astype(np.float64)


def _centroid(al):
    ys, xs = np.mgrid[:al.shape[0], :al.shape[1]]
    return (al * xs).sum() / al.sum(), (al * ys).sum() / al.sum()


def _area(im, thr=128):
    return int((_alpha(im) > thr).sum())


A, B = _disc(70), _disc(110)


def test_endpoints_exact():
    assert np.array_equal(np.asarray(tween(A, B, 0.0)), np.asarray(A))
    assert np.array_equal(np.asarray(tween(A, B, 1.0)), np.asarray(B))


def test_moving_disc_midpoint_no_ghost():
    m = tween(A, B, 0.5)
    cx, cy = _centroid(_alpha(m))
    assert abs(cx - 90) < 4 and abs(cy - 70) < 4
    assert abs(_area(m) / _area(A) - 1) < 0.15
    # no double image: the half-transparent band stays a thin edge, not two ghost discs
    al = _alpha(m)
    semi = ((al > 20) & (al < 235)).sum()
    assert semi < 0.25 * _area(A)


def test_quarter_point_tracks_motion():
    cx, _ = _centroid(_alpha(tween(A, B, 0.25)))
    assert abs(cx - 80) < 4


def test_no_dark_fringe_on_edges():
    m = np.asarray(tween(A, B, 0.5))
    edge = m[(m[..., 3] > 10) & (m[..., 3] < 245)]
    assert len(edge) > 0 and edge[:, :3].min() > 200


def test_tween_frames_count_and_order():
    fr = tween_frames(A, B, 3)
    assert len(fr) == 3 and all(f.size == A.size and f.mode == 'RGBA' for f in fr)
    xs = [_centroid(_alpha(f))[0] for f in fr]
    assert xs[0] < xs[1] < xs[2]
    assert all(abs(x - e) < 4 for x, e in zip(xs, (80, 90, 100)))


def test_tweener_hard_outside_window_tween_inside():
    P = {'left': A, 'right': B, 'red': _disc(90, rgb=(220, 30, 30))}
    tl = [(0.0, 'left'), (1.0, 'right'), (2.0, 'red', 'hard')]
    TW = Tweener()
    assert TW.frame(P, tl, 0.5) is A                     # before any cut
    assert TW.frame(P, tl, 1.5) is B                     # well after the cut window
    mid = TW.frame(P, tl, 1.05, dur=0.18)                # inside the window: an in-between
    assert mid is not A and mid is not B
    cx, _ = _centroid(_alpha(mid))
    assert 72 < cx < 108
    assert TW.frame(P, tl, 2.01) is P['red']             # 'hard' entry never tweens
    assert TW.frame(P, tl, 1.05, hard=True) is B         # global hard override
    assert len(TW.cache) == 1                            # flows cached per pair
    TW.frame(P, tl, 1.1)
    assert len(TW.cache) == 1


def test_smear_keeps_size_sane():
    im = _disc(130)
    s = smear(im, 40, 0, 1.0)
    assert s.size == im.size and s.mode == 'RGBA'
    a0, a1 = _area(im), _area(s)
    assert a0 * 0.9 <= a1 <= a0 + 2 * R * 40             # trail at most the swept box
    assert _alpha(s)[70, 130] > 240                     # figure stays solid where it is
    x0 = np.where(_alpha(s)[70] > 20)[0].min()
    assert x0 < 130 - R - 5                             # trail extends behind (opposite to motion)
    assert np.where(_alpha(s)[70] > 20)[0].max() <= 130 + R + 1   # nothing ahead of the figure
    edge = np.asarray(s)[(np.asarray(s)[..., 3] > 10)]
    assert edge[:, :3].min() > 200                       # no dark fringe in the trail


def test_missing_rife_model_falls_back(monkeypatch):
    monkeypatch.setenv('VDS_RIFE_ONNX', '/nonexistent/rife.onnx')
    m = tween(A, B, 0.5)
    assert abs(_centroid(_alpha(m))[0] - 90) < 4
