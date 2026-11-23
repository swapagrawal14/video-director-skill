"""Puppet warp for raster cut-outs (After Effects 'puppet pin' style), no SVG, no rigs.

Bend an AI-drawn character or prop like rubber: put pins on the image (shoulder, elbow,
hand...), move some of them, and the picture deforms smoothly around them while the
unmoved pins hold still. Uses Moving Least Squares (Schaefer et al. 2006), similarity or
rigid variant, evaluated on a coarse grid and upsampled, so a 1000 px layer warps in ~0.2 s on CPU.

Typical use:
    from warp import Puppet
    P = Puppet(img, {'hip': (210, 520), 'shoulder': (205, 300), 'elbow': (300, 330), 'hand': (380, 300)})
    frame_img = P.pose({'elbow': (310, 250), 'hand': (330, 160)})      # arm waves up
    frame_img = P.bend('shoulder', ['elbow', 'hand'], deg=-35)        # rotate a chain about a pin
    frame_img = P.wiggle(t, ['hand'], amp=8, freq=2.0)                 # secondary motion

Rules that keep it looking hand-animated (not 'clip-art'):
  * pin every part that must stay put (feet, hip, head) or it drifts;
  * move pins on arcs, with ease/overshoot from motion.py, never linearly;
  * keep deformations under ~35% of the limb length; past that, cut to a new pose from
    the pose pack and use inbetween.py to bridge.
"""
import math
import numpy as np, cv2
from PIL import Image


def _to_rgba_array(im):
    if isinstance(im, Image.Image):
        return np.array(im.convert('RGBA'))
    a = np.asarray(im)
    if a.ndim == 3 and a.shape[2] == 4:
        return a
    raise ValueError('need an RGBA image')


def mls_map(src_pins, dst_pins, shape, grid=12, alpha=1.0, rigid=True):
    """Backward map for an MLS deformation.

    src_pins: (N,2) pin positions in the source image; dst_pins: where they go.
    Returns (map_x, map_y) float32 of the output size, for cv2.remap: out(x) = src(map(x)).
    We solve the inverse problem directly (dst -> src), which is what remap needs.
    """
    H, W = shape[:2]
    p = np.asarray(dst_pins, np.float64)   # control points in OUTPUT space
    q = np.asarray(src_pins, np.float64)   # where they sample from in SOURCE
    if len(p) == 0 or np.allclose(p, q):
        xs, ys = np.meshgrid(np.arange(W, dtype=np.float32), np.arange(H, dtype=np.float32))
        return xs, ys
    gx = np.arange(0, W + grid, grid, dtype=np.float64)
    gy = np.arange(0, H + grid, grid, dtype=np.float64)
    vx, vy = np.meshgrid(gx, gy)
    v = np.stack([vx, vy], -1).reshape(-1, 1, 2)                    # (M,1,2)
    d2 = ((v - p[None]) ** 2).sum(-1)                                # (M,N)
    w = 1.0 / np.maximum(d2, 1e-8) ** alpha
    ws = w.sum(1, keepdims=True)
    pstar = (w[..., None] * p[None]).sum(1) / ws                     # (M,2)
    qstar = (w[..., None] * q[None]).sum(1) / ws
    ph = p[None] - pstar[:, None]                                    # (M,N,2)
    qh = q[None] - qstar[:, None]
    vp = v[:, 0] - pstar                                             # (M,2)
    # per-point weighted similarity fit: qh ~ [[ca, -sb], [sb, ca]] @ ph
    mu = (w * (ph ** 2).sum(-1)).sum(1)                              # (M,)
    ca = (w * (ph * qh).sum(-1)).sum(1) / np.maximum(mu, 1e-8)
    sb = (w * (ph[..., 0] * qh[..., 1] - ph[..., 1] * qh[..., 0])).sum(1) / np.maximum(mu, 1e-8)
    if rigid:                                                         # rotation only, no scale
        n = np.maximum(np.hypot(ca, sb), 1e-8); ca, sb = ca / n, sb / n
    f = np.stack([ca * vp[:, 0] - sb * vp[:, 1], sb * vp[:, 0] + ca * vp[:, 1]], -1)
    out = (f + qstar).reshape(len(gy), len(gx), 2).astype(np.float32)
    # exact upsample: output pixel (x, y) reads grid cell (x/grid, y/grid)
    ux, uy = np.meshgrid(np.arange(W, dtype=np.float32) / grid, np.arange(H, dtype=np.float32) / grid)
    mx = cv2.remap(np.ascontiguousarray(out[..., 0]), ux, uy, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)
    my = cv2.remap(np.ascontiguousarray(out[..., 1]), ux, uy, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)
    return mx, my


def warp_rgba(im, src_pins, dst_pins, grid=12, rigid=True, pad=0):
    """Deform an RGBA image so each src pin lands on its dst pin. Returns PIL RGBA.
    pad: extra transparent border (px) so limbs can swing outside the original canvas;
    pins are given in un-padded coordinates."""
    a = _to_rgba_array(im)
    if pad:
        a = cv2.copyMakeBorder(a, pad, pad, pad, pad, cv2.BORDER_CONSTANT, value=(0, 0, 0, 0))
        src_pins = [(x + pad, y + pad) for x, y in src_pins]
        dst_pins = [(x + pad, y + pad) for x, y in dst_pins]
    # premultiply so transparent edges don't bleed dark fringes
    f = a.astype(np.float32)
    f[..., :3] *= f[..., 3:4] / 255.0
    mx, my = mls_map(src_pins, dst_pins, a.shape, grid=grid, rigid=rigid)
    o = cv2.remap(f, mx, my, cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT, borderValue=(0, 0, 0, 0))
    al = o[..., 3:4]
    o[..., :3] = np.where(al > 0.5, o[..., :3] * 255.0 / np.maximum(al, 1e-3), 0)
    return Image.fromarray(np.clip(o, 0, 255).astype(np.uint8), 'RGBA')


def rotate_about(pt, centre, deg):
    a = math.radians(deg)
    x, y = pt[0] - centre[0], pt[1] - centre[1]
    return (centre[0] + x * math.cos(a) - y * math.sin(a), centre[1] + x * math.sin(a) + y * math.cos(a))


class Puppet:
    """Named pins on one raster layer. Every call returns a NEW deformed PIL RGBA image;
    pins not mentioned stay where they are (they act as anchors)."""

    def __init__(self, im, pins, grid=12, rigid=True, pad=0):
        self.im = im if isinstance(im, Image.Image) else Image.fromarray(np.asarray(im))
        self.pins = {k: (float(x), float(y)) for k, (x, y) in pins.items()}
        self.grid, self.rigid, self.pad = grid, rigid, pad

    def pose(self, moved):
        names = list(self.pins)
        src = [self.pins[n] for n in names]
        dst = [moved.get(n, self.pins[n]) for n in names]
        return warp_rgba(self.im, src, dst, self.grid, self.rigid, self.pad)

    def targets_bend(self, pivot, chain, deg):
        c = self.pins[pivot]
        return {n: rotate_about(self.pins[n], c, deg) for n in chain}

    def bend(self, pivot, chain, deg, extra=None):
        """rotate the pins in `chain` about pin `pivot` by deg (screen degrees, + = clockwise)."""
        t = self.targets_bend(pivot, chain, deg)
        if extra: t.update(extra)
        return self.pose(t)

    def wiggle(self, t, names, amp=6.0, freq=1.5, phase=0.0):
        """smooth secondary motion: each named pin drifts on a small Lissajous loop."""
        moved = {}
        for i, n in enumerate(names):
            x, y = self.pins[n]; ph = phase + i * 1.7
            moved[n] = (x + amp * math.sin(2 * math.pi * freq * t + ph), y + amp * 0.6 * math.sin(4 * math.pi * freq * t + ph))
        return self.pose(moved)
