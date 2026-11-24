"""Frame-by-frame hand-drawn finish for motion2d (raster only, never SVG).

Key poses + warp + tween give the motion; this module gives the *drawn* feel on top of it, the things
that make a viewer believe every frame was drawn by hand:

  * hold timing      on_ones / on_twos / on_threes / Holds: quantise t to drawings (12 drawings/s on twos)
  * line boil        boil(im, drawing): a new wobble ONLY when the drawing index changes (no shimmer)
  * paper            paper() plate, paper_texture() / grain(): tooth + fibre multiply, static or per drawing
  * texture fills    texture_fill(mask, colour, kind) / texturize(sprite, kind): pencil, marker, crayon, chalk
  * ink draw-on      InkDrawOn(line_art).frame(p): skeleton-traced pen order, round growing tip, pen lifts,
                     then the colour washes in; .tip(p) gives the pen position for a hand/pen sprite
  * re-ink           wobble_outline(sprite, drawing): hand-drawn outline of variable thickness from alpha
                     (+ thinner inner lines on colour boundaries) for flat sprites with no / dead outlines
  * smears           smear(im, dx, dy, kind='stretch'|'multiples'|'trail'), spin_smear(wheel, deg),
                     smear_amount(speed): when a move is too fast for clean in-betweens
  * debug            onion_skin(frames, i): previous drawings in red, next in green over the current one

Everything is deterministic: same inputs + seed + drawing index -> same pixels. Layers are PIL RGBA (numpy
RGBA also accepted), frames are BGR numpy arrays (motion.py convention). Noise fields are cached, so
full-frame calls at 1080x1920 stay in the tens of milliseconds after the first one.

    from handdrawn import on_twos, boil, paper, grain, texturize, wobble_outline, InkDrawOn, smear
    t_h, d = on_twos(t, 24)                         # animate with t_h, boil/texture with d
    truck = wobble_outline(texturize(TRUCK, 'marker', drawing=d % 3), d, width=7)
    fr = PAPER.copy(); paste(fr, boil(truck, d), x, y); out = grain(fr, d)

Playbook: docs/HANDDRAWN_FINISH.md. Credit: Swapnil Agrawal (BDS intern).
"""
import math
from collections import OrderedDict
import numpy as np, cv2
from PIL import Image
from scipy import ndimage as ndi

__all__ = ['hold', 'on_ones', 'on_twos', 'on_threes', 'hold_step', 'Holds', 'boil', 'paper', 'paper_texture',
           'grain', 'texture_fill', 'texturize', 'InkDrawOn', 'wobble_outline', 'smear', 'spin_smear',
           'smear_amount', 'onion_skin', 'TEXTURES']

TEXTURES = ('pencil', 'marker', 'crayon', 'chalk')


# ================================================================ small helpers
class _LRU(OrderedDict):
    def __init__(self, n=24): super().__init__(); self.n = n

    def get_or(self, key, fn):
        if key in self:
            self.move_to_end(key); return self[key]
        v = fn(); self[key] = v
        if len(self) > self.n: self.popitem(last=False)
        return v


_CACHE = _LRU(48)


def _key(*a):
    return hash(a) & 0x7fffffff


def _noise(h, w, cell, seed):
    """smooth value noise in -1..1, cell = feature size in px (cubic upsampled random grid)"""
    def make():
        gh, gw = max(2, int(math.ceil(h / cell)) + 3), max(2, int(math.ceil(w / cell)) + 3)
        g = np.random.RandomState(seed % (2 ** 31)).uniform(-1, 1, (gh, gw)).astype(np.float32)
        f = cv2.resize(g, (int(gw * cell), int(gh * cell)), interpolation=cv2.INTER_CUBIC)
        return np.ascontiguousarray(f[:h, :w])
    return _CACHE.get_or(('n', h, w, float(cell), seed), make)


def _grid(h, w):
    return _CACHE.get_or(('g', h, w), lambda: np.meshgrid(np.arange(w, dtype=np.float32),
                                                          np.arange(h, dtype=np.float32)))


def _rgba(im):
    """-> (uint8 RGBA array, was_pil)"""
    if isinstance(im, Image.Image): return np.array(im.convert('RGBA')), True
    a = np.asarray(im)
    if a.ndim == 3 and a.shape[2] == 4: return a.astype(np.uint8), False
    if a.ndim == 3 and a.shape[2] == 3:
        return np.dstack([a.astype(np.uint8), np.full(a.shape[:2], 255, np.uint8)]), False
    if a.ndim == 2:
        g = a.astype(np.uint8); return np.dstack([g, g, g, np.full_like(g, 255)]), False
    raise ValueError('need a PIL image or an (H, W[, 3|4]) array')


def _out(a, was_pil):
    return Image.fromarray(a, 'RGBA') if was_pil else a


def _col(c):
    """'#RRGGBB' or (r, g, b) -> np.float32 RGB"""
    if isinstance(c, str):
        c = c.lstrip('#'); return np.array([int(c[i:i + 2], 16) for i in (0, 2, 4)], np.float32)
    return np.array(c[:3], np.float32)


# ================================================================ 1. hold timing
def hold(t, fps=24, n=2, offset=0):
    """Hold each drawing for n frames ('on twos' = n 2). Returns (t_held, drawing):
    t_held = the time of the first frame of this drawing (animate EVERYTHING with it, so the whole
    picture changes only when a new drawing starts), drawing = integer drawing index (seed boil,
    textures and outlines with it). offset shifts where the holds start, in frames."""
    if n < 1: raise ValueError('n must be >= 1')
    f = int(math.floor(t * fps + 1e-6))
    d = (f - offset) // n
    return (d * n + offset) / fps, d


def on_ones(t, fps=24): return hold(t, fps, 1)
def on_twos(t, fps=24): return hold(t, fps, 2)
def on_threes(t, fps=24): return hold(t, fps, 3)


def hold_step(step, n=2, offset=0):
    """integer version for frame loops: (held_step, drawing)"""
    d = (step - offset) // n
    return d * n + offset, d


class Holds:
    """Mixed timing, like a real exposure sheet: ones for fast action, twos for normal, threes for slow
    settles. segments = [(t_start, n), ...] sorted by time (first should start at 0).
        H = Holds([(0, 2), (1.25, 1), (1.75, 2), (4.0, 3)], fps=24)
        t_h, d = H(t)
    Drawing indices keep counting up across segments, so boil/texture never repeat by accident."""

    def __init__(self, segments, fps=24):
        if not segments: raise ValueError('need at least one segment')
        self.fps = fps
        segs = sorted((int(round(t0 * fps)), int(n)) for t0, n in segments)
        if segs[0][0] > 0: segs.insert(0, (0, segs[0][1]))
        self.segs, base = [], 0
        for i, (f0, n) in enumerate(segs):
            f1 = segs[i + 1][0] if i + 1 < len(segs) else None
            self.segs.append((f0, f1, n, base))
            if f1 is not None: base += -(-(f1 - f0) // n)        # ceil

    def __call__(self, t):
        f = int(math.floor(t * self.fps + 1e-6))
        for f0, f1, n, base in self.segs:
            if f1 is None or f < f1:
                k = max(0, f - f0) // n
                return (f0 + k * n) / self.fps, base + k
        raise AssertionError('unreachable')


# ================================================================ 2. line boil
def _boil_field(h, w, drawing, amp, scale, seed):
    k = _key('boil', seed, drawing)
    dx = _noise(h, w, scale, k) * amp
    dy = _noise(h, w, scale, k + 7919) * amp
    return dx, dy


def boil(im, drawing, amp=1.2, scale=28, seed=0):
    """Hand-drawn line boil keyed ONLY on the drawing index: a smooth displacement field (feature `scale`
    px, max `amp` px) that is identical for every frame of one drawing and new for the next, so it never
    shimmers between held frames. Give each layer its own seed so layers do not boil in lockstep.
    amp 0.8-1.6 px at 1080 reads as redrawn; > 2 px reads as jelly. Works on PIL RGBA, RGBA/BGR arrays
    (whole frames too: ~25 ms at 1080x1920). Returns the same type it was given."""
    if isinstance(im, Image.Image):
        a, pil = np.array(im.convert('RGBA')), True
    else:
        a, pil = np.asarray(im), False
    if amp <= 0: return im.copy() if pil else a.copy()
    h, w = a.shape[:2]
    dx, dy = _boil_field(h, w, int(drawing), float(amp), float(scale), int(seed))
    gx, gy = _grid(h, w)
    border = cv2.BORDER_CONSTANT if (a.ndim == 3 and a.shape[2] == 4) else cv2.BORDER_REPLICATE
    out = cv2.remap(a, gx + dx, gy + dy, cv2.INTER_LINEAR, borderMode=border, borderValue=0)
    return Image.fromarray(out, 'RGBA') if pil else out


# ================================================================ 3. paper + grain
def paper_texture(h, w, seed=0, tooth=1.0, fibre=1.0, mottle=1.0):
    """Multiplicative paper texture around 1.0 (float32 HxW): tooth (fine bumps), fibres (short streaks),
    mottle (cloudy unevenness). Cached per (size, seed, amounts)."""
    def make():
        rs = np.random.RandomState(seed % (2 ** 31))
        fine = cv2.GaussianBlur(rs.randn(h, w).astype(np.float32), (0, 0), 0.8)
        fine /= fine.std() + 1e-6
        fib = rs.randn(max(2, h // 2), max(2, w // 16)).astype(np.float32)
        fib = cv2.resize(fib, (w, h), interpolation=cv2.INTER_LINEAR)          # streaks along x
        fib = cv2.GaussianBlur(fib, (0, 0), 0.6)
        fib = np.where(np.abs(fib) > 1.6, fib, 0)
        mot = _noise(h, w, max(h, w) / 5, seed + 11) * 0.7 + _noise(h, w, 60, seed + 12) * 0.3
        t = 1 + 0.035 * tooth * fine + 0.03 * fibre * fib + 0.045 * mottle * mot
        return t.astype(np.float32)
    return _CACHE.get_or(('paper', h, w, seed, tooth, fibre, mottle), make)


def paper(W, H, color='#F4EEE1', seed=0, tooth=1.0, fibre=1.0, mottle=1.0, vignette=0.0):
    """Paper / card plate as float32 BGR (H, W, 3). Colour multiplied by paper_texture(); vignette 0..0.3
    darkens the corners a touch. Use it as the frame plate instead of a flat colour."""
    rgb = _col(color); tex = paper_texture(H, W, seed, tooth, fibre, mottle)
    fr = np.empty((H, W, 3), np.float32); fr[:] = rgb[::-1]
    fr *= tex[..., None]
    if vignette > 0:
        gx, gy = _grid(H, W)
        v = 1 - vignette * (((gx - W / 2) / W) ** 2 + ((gy - H / 2) / H) ** 2) * 2
        fr *= v[..., None]
    return np.clip(fr, 0, 255)


def grain(fr, drawing=0, strength=1.0, variants=1, seed=3, tooth=1.0, fibre=0.6, mottle=0.4):
    """Multiply a finished BGR frame by a paper texture so the art looks printed on paper (ink and fills
    pick up the tooth, not just the plate). variants=1: one static sheet (the camera holds one paper);
    variants>1: a different sheet per drawing (index drawing % variants), the 'every frame is a new sheet'
    pencil-test feel; it changes only on drawing changes. Returns uint8 BGR."""
    fr = np.asarray(fr, np.float32); h, w = fr.shape[:2]
    tex = paper_texture(h, w, seed + (int(drawing) % max(1, variants)) * 101, tooth, fibre, mottle)
    if strength != 1.0: tex = 1 + (tex - 1) * strength
    return np.clip(fr * tex[..., None] + 0.5, 0, 255).astype(np.uint8)


# ================================================================ 4. texture fills
def _aniso(h, w, cell_along, cell_across, angle, seed):
    """-1..1 noise stretched along `angle` (deg, 0 = along x), cached"""
    def make():
        D = int(math.ceil(math.hypot(h, w))) + 4
        g = np.random.RandomState(seed % (2 ** 31)).uniform(-1, 1, (max(2, int(D / cell_across) + 2),
                                                                    max(2, int(D / cell_along) + 2))).astype(np.float32)
        f = cv2.resize(g, (D, D), interpolation=cv2.INTER_CUBIC)
        M = cv2.getRotationMatrix2D((D / 2, D / 2), -angle, 1.0)
        M[0, 2] -= (D - w) / 2; M[1, 2] -= (D - h) / 2
        return cv2.warpAffine(f, M, (w, h), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)
    return _CACHE.get_or(('an', h, w, cell_along, cell_across, angle, seed), make)


def _tex(h, w, kind, seed, angle, scale):
    """(shade, cover) float32 maps for one media. shade multiplies the colour, cover multiplies alpha."""
    s = scale
    if kind == 'pencil':
        a = angle if angle is not None else 35
        hatch = _aniso(h, w, 90 * s, 2.2 * s, a, seed)                     # long thin graphite strokes
        tooth = _aniso(h, w, 3 * s, 1.5 * s, a + 90, seed + 1)
        lvl = _noise(h, w, 70 * s, seed + 2)                               # uneven pressure
        cov = np.clip(0.55 + 0.55 * hatch + 0.25 * tooth + 0.15 * lvl, 0.12, 1.0)
        shade = 0.9 + 0.08 * tooth
        return shade, cov
    if kind == 'marker':
        a = angle if angle is not None else 8
        band = _aniso(h, w, 400 * s, 34 * s, a, seed)                       # one stroke ~34 px wide
        ov = np.clip(1 - np.abs(band) * 3.2, 0, 1)                         # overlap seams between strokes
        streak = _aniso(h, w, 160 * s, 3 * s, a, seed + 1)
        shade = 1 - 0.13 * ov - 0.025 * streak
        cov = np.clip(0.96 + 0.05 * streak, 0.85, 1.0)
        return shade, cov
    if kind == 'crayon':
        a = angle if angle is not None else -20
        wax = _aniso(h, w, 14 * s, 2.0 * s, a, seed)
        tooth = _noise(h, w, 2.2 * s, seed + 1)
        lvl = _noise(h, w, 50 * s, seed + 2)
        v = 0.6 * wax + 0.4 * tooth + 0.25 * lvl
        cov = np.clip((v + 0.62) * 2.4, 0.0, 1.0)
        shade = 0.96 + 0.06 * wax
        return shade, cov
    if kind == 'chalk':
        a = angle if angle is not None else 15
        dust = _noise(h, w, 1.6 * s, seed)
        streak = _aniso(h, w, 24 * s, 2.0 * s, a, seed + 1)
        lvl = _noise(h, w, 40 * s, seed + 2)
        v = 0.5 * dust + 0.5 * streak + 0.3 * lvl
        cov = np.clip((v + 0.35) * 1.8, 0.0, 1.0) * 0.92
        shade = 1.04 + 0.06 * dust
        return shade, cov
    raise ValueError(f'kind must be one of {TEXTURES}')


def texture_fill(mask, color, kind='crayon', seed=0, angle=None, scale=1.0, drawing=0):
    """Fill a mask with a hand media texture. mask: bool/uint8/float HxW (or a PIL 'L' image).
    kind: 'pencil' (hatched graphite strokes, paper shows through), 'marker' (solid with darker stroke
    overlaps), 'crayon' (waxy, broken by paper tooth), 'chalk' (dusty, broken, slightly lighter).
    drawing: new grain per drawing (seed + drawing), keep it fixed for a static texture.
    Returns PIL RGBA the size of the mask."""
    m = np.asarray(mask.convert('L') if isinstance(mask, Image.Image) else mask, np.float32)
    if m.max() > 1.0: m = m / 255.0
    h, w = m.shape
    shade, cov = _tex(h, w, kind, seed + int(drawing) * 31, angle, scale)
    rgb = np.clip(_col(color)[None, None] * shade[..., None], 0, 255)
    out = np.dstack([rgb, np.clip(m * cov, 0, 1) * 255]).astype(np.uint8)
    return Image.fromarray(out, 'RGBA')


def texturize(im, kind='marker', strength=1.0, seed=0, angle=None, scale=1.0, drawing=0, ink_lum=70):
    """Give a flat-fill sprite a hand media finish: every non-ink pixel gets the media's shade and
    coverage, dark ink lines (luminance < ink_lum) stay solid. strength 0..1 blends toward the flat sprite.
    Returns the same type it was given (PIL RGBA or RGBA array)."""
    a, pil = _rgba(im)
    h, w = a.shape[:2]
    shade, cov = _tex(h, w, kind, seed + int(drawing) * 31, angle, scale)
    rgb = a[..., :3].astype(np.float32)
    lum = rgb @ np.array([.299, .587, .114], np.float32)
    fill = (lum >= ink_lum).astype(np.float32)
    k = strength * fill
    sh = 1 + (shade - 1) * k
    cv_ = 1 + (cov - 1) * k
    out = np.dstack([np.clip(rgb * sh[..., None], 0, 255), a[..., 3] * cv_]).astype(np.uint8)
    return _out(out, pil)


# ================================================================ 5. ink draw-on
def _thin(mask):
    """Zhang-Suen thinning, vectorised (bool HxW -> bool skeleton)"""
    img = np.pad(mask.astype(np.uint8), 1)
    while True:
        changed = False
        for it in (0, 1):
            P = img
            p2, p3, p4 = P[:-2, 1:-1], P[:-2, 2:], P[1:-1, 2:]
            p5, p6, p7 = P[2:, 2:], P[2:, 1:-1], P[2:, :-2]
            p8, p9 = P[1:-1, :-2], P[:-2, :-2]
            c = P[1:-1, 1:-1]
            nb = [p2, p3, p4, p5, p6, p7, p8, p9, p2]
            B = p2 + p3 + p4 + p5 + p6 + p7 + p8 + p9
            A = sum(((nb[i] == 0) & (nb[i + 1] == 1)).astype(np.uint8) for i in range(8))
            if it == 0: c1, c2 = p2 * p4 * p6, p4 * p6 * p8
            else: c1, c2 = p2 * p4 * p8, p2 * p6 * p8
            rm = (c == 1) & (B >= 2) & (B <= 6) & (A == 1) & (c1 == 0) & (c2 == 0)
            if rm.any():
                img[1:-1, 1:-1][rm] = 0; changed = True
        if not changed: break
    return img[1:-1, 1:-1].astype(bool)


_NB = [(-1, 0), (1, 0), (0, -1), (0, 1), (-1, -1), (-1, 1), (1, -1), (1, 1)]


class InkDrawOn:
    """Pen draw-on of a raster line drawing (bold dark outlines + optional colour fills).

    The ink is thinned to a skeleton, every stroke group is traced like a pen (start at its top-left end,
    follow the line, finish a branch, lift, draw the next branch), and each ink pixel takes the time of its
    nearest skeleton pixel, so the line grows along itself with a round tip at its real width, not as a
    wipe. Fills wash in after the ink (fill_lag of the timeline) with a ragged marker edge.

        D = InkDrawOn(Image.open('mascot_lines.png'))      # RGBA, or RGB line art on white paper
        layer = D.frame(p)                                 # p 0..1 -> PIL RGBA, exact drawing at p = 1
        x, y = D.tip(p)                                    # pen position, to hang a hand/pen sprite on

    order: 'reading' (rows top->bottom, left->right), 'size' (biggest group first), 'ltr'.
    Precompute once (~0.2-1 s for a 1080 px drawing); frame() is a few vector ops (~10-20 ms)."""

    def __init__(self, im, ink_lum=95, order='reading', fill_lag=0.25, feather=3.0, seed=0):
        a, _ = _rgba(im)
        a = a.copy()
        rgb = a[..., :3].astype(np.float32)
        lum = rgb @ np.array([.299, .587, .114], np.float32)
        if a[..., 3].min() > 250:                               # line art on paper: key the paper out
            a[..., 3] = np.clip((248 - lum) * 255 / 40, 0, 255).astype(np.uint8)
        self.rgba = a
        self.h, self.w = a.shape[:2]
        alpha = a[..., 3]
        ink = (alpha > 100) & (lum < ink_lum)
        ink = cv2.morphologyEx(ink.astype(np.uint8), cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8)) > 0
        rim = cv2.dilate(ink.astype(np.uint8), np.ones((3, 3), np.uint8)) > 0
        self.ink = ink | (rim & (alpha > 0) & ((alpha < 250) | (lum < ink_lum + 35)))   # antialiased rim of the line
        self.fill_lag = float(fill_lag) if (alpha > 0)[~self.ink].any() else 0.0
        self.feather = float(feather)
        self._trace(order)
        # fill wash: diagonal ragged wipe, normalised 0..1
        gx, gy = np.meshgrid(np.arange(self.w, dtype=np.float32), np.arange(self.h, dtype=np.float32))
        ft = gx + 0.35 * gy + _noise(self.h, self.w, 26, seed + 5) * 0.06 * (self.w + 0.35 * self.h)
        ft -= ft.min(); self.fill_t = ft / max(1e-6, ft.max())

    def _trace(self, order):
        sk = _thin(self.ink)
        n, lab = cv2.connectedComponents(self.ink.astype(np.uint8), connectivity=8)
        has = np.zeros(n, bool); has[np.unique(lab[sk])] = True
        for i in range(1, n):                                     # dots that thinned away: keep their centre
            if not has[i]:
                ys, xs = np.nonzero(lab == i)
                if len(ys): sk[int(ys.mean()), int(xs.mean())] = True
        ys, xs = np.nonzero(sk)
        idx = -np.ones(sk.shape, np.int64); idx[ys, xs] = np.arange(len(ys))
        nbrs = []
        for y, x in zip(ys, xs):
            l = []
            for dy, dx in _NB:
                yy, xx = y + dy, x + dx
                if 0 <= yy < self.h and 0 <= xx < self.w and idx[yy, xx] >= 0: l.append(int(idx[yy, xx]))
            nbrs.append(l)
        N = len(ys)
        ncomp, slab = cv2.connectedComponents(sk.astype(np.uint8), connectivity=8)
        comps = [[] for _ in range(ncomp)]
        for i in range(N): comps[slab[ys[i], xs[i]]].append(i)
        starts = []
        for c in comps[1:]:
            if not c: continue
            ends = [i for i in c if len(nbrs[i]) == 1] or c
            s = min(ends, key=lambda i: xs[i] + ys[i])
            starts.append((s, len(c)))
        band = max(8, self.h * 0.06)
        if order == 'size': starts.sort(key=lambda sc: -sc[1])
        elif order == 'ltr': starts.sort(key=lambda sc: (xs[sc[0]], ys[sc[0]]))
        else: starts.sort(key=lambda sc: (int(ys[sc[0]] // band), xs[sc[0]]))
        tm = np.zeros(N, np.float32); seen = np.zeros(N, bool); clock = 1.0
        for s, _ in starts:
            stack = [(s, -1)]
            last = -1
            while stack:
                i, frm = stack.pop()
                if seen[i]: continue
                seen[i] = True
                if last >= 0 and abs(int(ys[i]) - int(ys[last])) <= 1 and abs(int(xs[i]) - int(xs[last])) <= 1:
                    clock += math.hypot(int(ys[i]) - int(ys[last]), int(xs[i]) - int(xs[last]))
                else:
                    clock += 1.0                                   # pen lift: no time jump, just continue
                tm[i] = clock; last = i
                nx = [j for j in nbrs[i] if not seen[j]]
                if not nx: continue
                if frm >= 0:                                        # prefer going straight on
                    dy0, dx0 = ys[i] - ys[frm], xs[i] - xs[frm]
                    nx.sort(key=lambda j: (ys[j] - ys[i]) * dy0 + (xs[j] - xs[i]) * dx0)
                for j in nx: stack.append((j, i))                   # best one popped first
        self.length = clock + self.feather
        self.sk_y, self.sk_x, self.sk_t = ys, xs, tm
        tmap = np.zeros(sk.shape, np.float32); tmap[ys, xs] = tm
        if N:
            _, (iy, ix) = ndi.distance_transform_edt(~sk, return_indices=True)
            self.ink_t = np.where(self.ink, tmap[iy, ix], 0).astype(np.float32)
        else:
            self.ink_t = np.zeros(sk.shape, np.float32)
        self._order_idx = np.argsort(tm)

    def _split(self, p):
        p = min(1.0, max(0.0, float(p)))
        if self.fill_lag <= 0: return p, 0.0
        lp = min(1.0, p / (1 - self.fill_lag))
        fp = min(1.0, max(0.0, (p - (1 - self.fill_lag)) / self.fill_lag))
        return lp, fp

    def frame(self, p):
        """p 0..1 -> PIL RGBA. p <= 0: fully transparent. p >= 1: exactly the input drawing."""
        lp, fp = self._split(p)
        a = self.rgba.copy()
        al = a[..., 3].astype(np.float32)
        ink_k = np.clip((lp * self.length - self.ink_t) / self.feather, 0, 1)
        s = 0.06
        fill_k = np.clip((fp * (1 + s) - self.fill_t) / s, 0, 1)
        k = np.where(self.ink, ink_k, fill_k)
        a[..., 3] = np.clip(al * k + 0.5, 0, 255).astype(np.uint8) if p < 1 else a[..., 3]
        return Image.fromarray(a, 'RGBA')

    def tip(self, p):
        """(x, y) of the pen tip at progress p, or None before the first / after the last stroke."""
        lp, _ = self._split(p)
        if len(self.sk_t) == 0 or lp <= 0 or lp >= 1: return None
        target = lp * self.length
        order = self._order_idx; tt = self.sk_t[order]
        k = int(np.searchsorted(tt, target)) - 1
        if k < 0: return None
        i = order[k]
        return float(self.sk_x[i]), float(self.sk_y[i])


# ================================================================ 6. wobble outline (re-ink)
def wobble_outline(im, drawing=0, width=6.0, var=0.45, wobble=1.2, scale=46, color='#1A1423', inner=True,
                   inner_width=None, outside=0.6, seed=0, pad=None, ink_lum=60):
    """Re-ink a flat sprite with a hand-drawn outline built from its alpha: variable thickness
    (width * (1 +- var), thick-thin like a brush pen), path wobble (wobble px), both keyed on `drawing`
    so they change only on drawing changes. inner=True also inks colour boundaries inside the sprite
    with a thinner line (inner_width, default 0.55 * width); existing dark ink is left alone. Run it on the
    FLAT sprite and texturize() afterwards: texture grain is smoothed out, but heavy texture can still
    read as colour boundaries.
    outside: share of the line that sits outside the silhouette (0.6 = mostly outside, the fill keeps
    its size). The canvas grows by `pad` px on every side (default fits the line) and stays centred, so
    motion.paste(fr, out, cx, cy) needs no change. Returns the same type it was given."""
    a, pil = _rgba(im)
    if pad is None: pad = int(math.ceil(width * (1 + var) * outside + wobble + 2))
    a = np.pad(a, ((pad, pad), (pad, pad), (0, 0)))
    h, w = a.shape[:2]
    m = (a[..., 3] > 127).astype(np.uint8)
    d_out = cv2.distanceTransform(1 - m, cv2.DIST_L2, 5)
    d_in = cv2.distanceTransform(m, cv2.DIST_L2, 5)
    sd = d_out - d_in                                         # signed distance, + outside
    k = _key('ink', seed, int(drawing))
    gx, gy = _grid(h, w)
    if wobble > 0:
        jx = _noise(h, w, scale, k) * wobble; jy = _noise(h, w, scale, k + 1) * wobble
        sd = cv2.remap(sd, gx + jx, gy + jy, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)
    th = width * (1 + var * _noise(h, w, scale * 1.7, k + 2))
    th = np.maximum(th, width * 0.25)
    lo, hi = -th * (1 - outside), th * outside
    line = np.clip(np.minimum(sd - lo, hi - sd) + 0.5, 0, 1)
    if inner:
        rgb = cv2.medianBlur(np.ascontiguousarray(a[..., :3]), 5).astype(np.int32)   # ignore texture grain
        lum = rgb @ np.array([299, 587, 114]) // 1000
        q = (rgb // 28)
        code = (q[..., 0] * 4096 + q[..., 1] * 64 + q[..., 2]).astype(np.int64)
        code[(lum < ink_lum) | (m == 0)] = -1
        e = np.zeros((h, w), bool)
        for dy, dx in ((0, 1), (1, 0)):
            c0 = code[:h - dy, :w - dx]; c1 = code[dy:, dx:]
            diff = (c0 != c1) & (c0 >= 0) & (c1 >= 0)
            e[:h - dy, :w - dx] |= diff
        e = ndi.binary_opening(e, structure=np.ones((1, 2))) | ndi.binary_opening(e, structure=np.ones((2, 1)))
        if e.any():
            de = cv2.distanceTransform((~e).astype(np.uint8), cv2.DIST_L2, 5)
            if wobble > 0:
                de = cv2.remap(de, gx + jx, gy + jy, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)
            iw = (inner_width or width * 0.55) * (1 + var * 0.6 * _noise(h, w, scale * 1.3, k + 3))
            il = np.clip(iw / 2 - de + 0.5, 0, 1) * (d_in > 0.5)
            line = np.maximum(line, il)
    ink = _col(color)
    src_a = a[..., 3:4].astype(np.float32) / 255
    la = line[..., None]
    out_a = la + src_a * (1 - la)
    rgb = (ink[None, None] * la + a[..., :3].astype(np.float32) * src_a * (1 - la)) / np.maximum(out_a, 1e-4)
    out = np.dstack([np.clip(rgb, 0, 255), out_a[..., 0] * 255]).astype(np.uint8)
    return _out(out, pil)


# ================================================================ 7. smears
def _premul(a):
    p = a.astype(np.float32) / 255; p[..., :3] *= p[..., 3:4]; return p


def _unpremul(p):
    al = np.clip(p[..., 3:4], 0, 1)
    rgb = np.where(al > 1e-4, p[..., :3] / np.maximum(al, 1e-4), 0)
    return (np.concatenate([np.clip(rgb, 0, 1), al], -1) * 255 + 0.5).astype(np.uint8)


def smear_amount(dx, dy, threshold=36.0, full=110.0):
    """0..1 smear strength from the per-frame (per-drawing) move in px: 0 below `threshold` (in-betweens
    read fine), 1 at `full` and above. Smear only on the 1-2 drawings of the fastest part of a move."""
    v = math.hypot(dx, dy)
    return float(min(1.0, max(0.0, (v - threshold) / max(1e-6, full - threshold))))


def smear(im, dx, dy, kind='stretch', strength=1.0, taper=0.65, n=None):
    """Smear drawing for a fast move of (dx, dy) px this drawing.
    kind 'stretch': the figure stays solid at its new spot and its back half is stretched into a tapering
           streak toward where it came from (the classic one-drawing smear);
    'multiples': 3 overlapping copies along the path, fading toward the back (dry-brush multiples);
    'trail': fading ghost trail (delegates to inbetween.smear).
    The canvas grows by the move length on every side and stays centred (paste by centre unchanged).
    Use for 1-2 drawings only, never hold a smear. Returns the same type it was given."""
    a, pil = _rgba(im)
    L = math.hypot(dx, dy) * float(strength)
    P = int(math.ceil(L)) + 2
    a = np.pad(a, ((P, P), (P, P), (0, 0)))
    if L < 1: return _out(a, pil)
    if kind == 'trail':
        from inbetween import smear as _trail
        return _out(np.array(_trail(Image.fromarray(a, 'RGBA'), dx, dy, strength)), pil)
    ux, uy = dx / math.hypot(dx, dy), dy / math.hypot(dx, dy)
    pm = _premul(a); h, w = pm.shape[:2]
    ys, xs = np.nonzero(a[..., 3] > 20)
    cx, cy = (xs.mean(), ys.mean()) if len(xs) else (w / 2, h / 2)
    acc = np.zeros_like(pm)
    if kind == 'multiples':
        copies = [(1.0, 0.35), (0.66, 0.6), (0.33, 0.85)]
        for s, op in copies:
            M = np.float32([[1, 0, -ux * L * s], [0, 1, -uy * L * s]])
            lay = cv2.warpAffine(pm, M, (w, h), flags=cv2.INTER_LINEAR, borderValue=0) * np.float32(op)
            acc = lay + acc * (1 - lay[..., 3:4])
        return _out(_unpremul(pm + acc * (1 - pm[..., 3:4])), pil)
    if kind != 'stretch': raise ValueError("kind must be 'stretch', 'multiples' or 'trail'")
    steps = int(n or min(28, max(4, math.ceil(L / 4))))
    for i in range(steps, 0, -1):
        s = i / steps
        k = 1 - taper * s                                      # narrower across the motion further back
        # scale across the motion axis about the centre, then shift back along it
        R = np.float32([[ux, uy], [-uy, ux]])                  # world -> (along, across)
        S = np.float32([[1, 0], [0, k]])
        A = R.T @ S @ R
        c = np.float32([cx, cy])
        t = c - A @ c - np.float32([ux, uy]) * L * s
        M = np.hstack([A, t[:, None]]).astype(np.float32)
        lay = cv2.warpAffine(pm, M, (w, h), flags=cv2.INTER_LINEAR, borderValue=0)
        acc = lay + acc * (1 - lay[..., 3:4])
    return _out(_unpremul(pm + acc * (1 - pm[..., 3:4])), pil)


def spin_smear(im, deg, n=None):
    """Rotational motion blur for a spinning part (wheel, fan, propeller): averages copies rotated across
    the `deg` the part turns during one exposure (one drawing), centred on the current angle. Square,
    centred input; canvas kept. deg ~ 360 * rpm / 60 / fps * hold. Returns the same type it was given."""
    a, pil = _rgba(im)
    if abs(deg) < 0.5: return _out(a.copy(), pil)
    n = int(n or min(24, max(3, math.ceil(abs(deg) / 3))))
    pm = _premul(a); h, w = pm.shape[:2]; acc = np.zeros_like(pm)
    for i in range(n):
        ang = deg * ((i + 0.5) / n - 0.5)
        M = cv2.getRotationMatrix2D((w / 2 - 0.5, h / 2 - 0.5), ang, 1.0)
        acc += cv2.warpAffine(pm, M, (w, h), flags=cv2.INTER_LINEAR, borderValue=0)
    return _out(_unpremul(acc / n), pil)


# ================================================================ 8. onion skin
def onion_skin(frames, i, before=2, after=1, opacity=0.45, prev_color=(40, 40, 230), next_color=(60, 170, 40),
               thresh=60, mode='darker', label=True):
    """Debug overlay like an animator's light table: frame i at full strength, the `before` previous
    DRAWINGS tinted red and the `after` next ones green, fading with distance. mode 'darker' (default,
    for ink drawings) tints where a ghost is darker than frame i, i.e. its lines; mode 'diff' tints every
    pixel that differs. You see the arcs and the spacing at a glance. frames: list of BGR uint8 arrays or a
    callable i -> frame. Held duplicates are skipped (drawings, not frames). Returns uint8 BGR."""
    get = frames if callable(frames) else (lambda k: frames[k])
    count = None if callable(frames) else len(frames)
    cur = np.asarray(get(i))[..., :3].astype(np.float32)
    out = cur.copy()

    def walk(step, m):
        res, k, last = [], i, cur
        while len(res) < m:
            k += step
            if k < 0 or (count is not None and k >= count): break
            f = np.asarray(get(k))[..., :3].astype(np.float32)
            if np.abs(f - last).max() < 1: continue              # same drawing, held frame
            res.append(f); last = f
        return res

    for col, seq in ((prev_color, walk(-1, before)), (next_color, walk(1, after))):
        for d, f in enumerate(seq, 1):
            if mode == 'diff': diff = np.abs(f - cur).sum(2) > thresh
            else: diff = (cur - f).sum(2) > thresh
            lum = (f @ np.array([.114, .587, .299], np.float32))[..., None] / 255
            tint = np.array(col, np.float32)[None, None] * (0.35 + 0.65 * (1 - lum)) + 255 * lum * 0.3
            op = opacity / d
            out[diff] = out[diff] * (1 - op) + tint[diff] * op
    out = np.clip(out, 0, 255).astype(np.uint8)
    if label:
        cv2.putText(out, f'frame {i}  -{before} red  +{after} green', (16, 40), cv2.FONT_HERSHEY_SIMPLEX, 1.0,
                    (0, 0, 0), 4, cv2.LINE_AA)
        cv2.putText(out, f'frame {i}  -{before} red  +{after} green', (16, 40), cv2.FONT_HERSHEY_SIMPLEX, 1.0,
                    (255, 255, 255), 2, cv2.LINE_AA)
    return out
