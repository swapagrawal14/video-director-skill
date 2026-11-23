"""Optical-flow in-betweening for pose-pack characters (AI-free, raster only).

Pose packs (posepack.py) hard-cut between registered key poses. That is the house style, but for
small changes (idle -> wave, look left -> look right, hand up -> hand down) a 3-5 frame in-between
reads smoother and more 'animated'. This module builds those in-betweens from the two key poses
themselves: dense DIS optical flow (OpenCV) on premultiplied luminance + alpha, flow projected to the
in-between time, both poses warped on PREMULTIPLIED RGBA (no dark fringes), blended with
occlusion-aware weights, then un-premultiplied. Never SVG/vector: input and output are PIL RGBA.

Typical use:
    from inbetween import tween, tween_frames, Tweener, smear
    mid = tween(P['idle'], P['wave'], 0.5)                    # one in-between, PIL RGBA
    ins = tween_frames(P['idle'], P['wave'], 3)               # 3 in-betweens (endpoints excluded)
    TW = Tweener()                                            # caches flows per pose pair
    im = TW.frame(P, [(0, 'idle'), (1.2, 'wave'), (3.0, 'idle', 'hard')], t, dur=0.18)
    fast = smear(im, dx=60, dy=0, strength=1.0)               # classic smear frame on a fast move

Rules:
  * tween ONLY between registered poses of one character (same canvas, scale, feet baseline);
    run posepack.check_registration first. Unregistered poses tween into mush.
  * keep tweens short: 3-5 frames at 24 fps (dur ~0.12-0.2 s). Longer and the warp shows.
  * big pose changes (turn-around, sit -> jump, different silhouette) still HARD CUT + squash pop
    (Cast.draw does the pop); mark those entries 'hard' in the timeline.
  * smear frames are for 1-2 frames of a fast move only, never held.
  * optional: env VDS_RIFE_ONNX=/path/rife.onnx uses onnxruntime RIFE for the RGB; alpha always
    comes from the flow path. A missing/broken model silently falls back to flow.

Author: Swapnil Agrawal (BDS intern).
"""
import math, os
import numpy as np, cv2
from PIL import Image
from motion import ease_out

__all__ = ['tween', 'tween_frames', 'Tweener', 'smear', 'PairFlow']


# ---------------------------------------------------------------- premultiplied helpers
def _premul(im):
    a = np.asarray(im.convert('RGBA'), np.float32) / 255.0
    a[..., :3] *= a[..., 3:4]
    return a                                                    # (H, W, 4) float32 premultiplied 0..1


def _unpremul(p):
    al = np.clip(p[..., 3:4], 0, 1)
    rgb = np.where(al > 1e-4, p[..., :3] / np.maximum(al, 1e-4), 0)
    out = np.concatenate([np.clip(rgb, 0, 1), al], -1)
    return Image.fromarray((out * 255 + 0.5).astype(np.uint8), 'RGBA')


def _flow_plane(pm):
    """0.5 * premultiplied gray + 0.5 * alpha, uint8 - alpha (the silhouette) dominates the flow."""
    g = 0.299 * pm[..., 0] + 0.587 * pm[..., 1] + 0.114 * pm[..., 2]
    return np.clip((0.5 * g + 0.5 * pm[..., 3]) * 255, 0, 255).astype(np.uint8)


def _dis(preset):
    p = cv2.DISOPTICAL_FLOW_PRESET_ULTRAFAST if str(preset).lower() == 'ultrafast' else cv2.DISOPTICAL_FLOW_PRESET_MEDIUM
    return cv2.DISOpticalFlow_create(p)


def _grid(h, w):
    return np.meshgrid(np.arange(w, dtype=np.float32), np.arange(h, dtype=np.float32))


def _remap(img, gx, gy, F):
    return cv2.remap(img, gx + F[..., 0], gy + F[..., 1], cv2.INTER_LINEAR,
                     borderMode=cv2.BORDER_CONSTANT, borderValue=0)


# ---------------------------------------------------------------- flow projection (forward splat)
def _splat_flow(F, w, t, gx, gy, fill_scale=8):
    """Project source flow F (src -> other pose) to time t. Each source pixel lands at x + t*F and carries
    the backward vector -t*F (t-frame -> src). Bilinear splat weighted by w (alpha), holes filled by
    normalized convolution at two scales. Returns dense (H, W, 2) backward flow for cv2.remap."""
    h, wd = F.shape[:2]
    tx, ty = (gx + t * F[..., 0]).ravel(), (gy + t * F[..., 1]).ravel()
    vx, vy, ww = (-t * F[..., 0]).ravel(), (-t * F[..., 1]).ravel(), w.ravel()
    x0, y0 = np.floor(tx), np.floor(ty); fx, fy = tx - x0, ty - y0
    x0, y0 = x0.astype(np.int64), y0.astype(np.int64)
    num_x = np.zeros(h * wd, np.float64); num_y = np.zeros_like(num_x); den = np.zeros_like(num_x)
    for ox, oy, bw in ((0, 0, (1 - fx) * (1 - fy)), (1, 0, fx * (1 - fy)), (0, 1, (1 - fx) * fy), (1, 1, fx * fy)):
        xi, yi = x0 + ox, y0 + oy
        ok = (xi >= 0) & (xi < wd) & (yi >= 0) & (yi < h)
        idx = (yi * wd + xi)[ok]; k = (bw * ww)[ok]
        num_x += np.bincount(idx, k * vx[ok], h * wd)
        num_y += np.bincount(idx, k * vy[ok], h * wd)
        den += np.bincount(idx, k, h * wd)
    num = np.stack([num_x, num_y], -1).reshape(h, wd, 2).astype(np.float32)
    den = den.reshape(h, wd).astype(np.float32)
    out = num / np.maximum(den, 1e-6)[..., None]
    # fill splat holes: local 5x5 normalized blur, then a coarse pyramid level for big holes
    nb = cv2.blur(num, (5, 5)); db = cv2.blur(den, (5, 5))
    mid = nb / np.maximum(db, 1e-6)[..., None]
    sh, sw = max(1, h // fill_scale), max(1, wd // fill_scale)
    nc = cv2.GaussianBlur(cv2.resize(num, (sw, sh), interpolation=cv2.INTER_AREA), (0, 0), 3)
    dc = cv2.GaussianBlur(cv2.resize(den, (sw, sh), interpolation=cv2.INTER_AREA), (0, 0), 3)
    coarse = nc / np.maximum(dc, 1e-9)[..., None]
    coarse = np.where((dc > 1e-9)[..., None], coarse, 0)
    coarse = cv2.resize(coarse, (wd, h), interpolation=cv2.INTER_LINEAR)
    out = np.where((den > 0.05)[..., None], out, np.where((db > 0.02)[..., None], mid, coarse))
    return out.astype(np.float32)


class PairFlow:
    """Everything about a pose pair that does not depend on t: premultiplied images, bidirectional flow,
    forward-backward consistency. Build once, then .at(t) is cheap (two splats + four remaps)."""

    def __init__(self, a, b, preset='medium', flow_max=480, occlusion=True, occ_sigma=3.0, coarse=0.05):
        if a.size != b.size:
            raise ValueError(f'tween needs registered poses of one size, got {a.size} vs {b.size}')
        self.A, self.B = _premul(a), _premul(b)
        h, w = self.size = self.A.shape[:2]
        self.gx, self.gy = _grid(h, w)
        k = min(1.0, flow_max / max(h, w)) if flow_max else 1.0
        lw, lh = (max(8, int(round(w * k))), max(8, int(round(h * k)))) if k < 1.0 else (w, h)
        self.low = (lh, lw)
        self.scale = np.float32([w / lw, h / lh])
        sa, sb = self.A, self.B
        if (lw, lh) != (w, h):
            sa = cv2.resize(self.A, (lw, lh), interpolation=cv2.INTER_AREA)
            sb = cv2.resize(self.B, (lw, lh), interpolation=cv2.INTER_AREA)
        # everything t-independent lives at flow resolution (low); only the final warps run at full size
        self.lgx, self.lgy = _grid(lh, lw)
        dis = _dis(preset)
        pa, pb = _flow_plane(sa), _flow_plane(sb)
        sig = coarse * max(lw, lh)
        self.Fab, self.Fba = self._calc(dis, pa, pb, sig), self._calc(dis, pb, pa, sig)
        if occlusion:                                           # forward-backward consistency -> visibility
            ea = np.linalg.norm(self.Fab + _remap(self.Fba, self.lgx, self.lgy, self.Fab), axis=-1)
            eb = np.linalg.norm(self.Fba + _remap(self.Fab, self.lgx, self.lgy, self.Fba), axis=-1)
            s2 = 2 * (occ_sigma / float(self.scale.mean())) ** 2
            self.Va, self.Vb = np.exp(-ea ** 2 / s2).astype(np.float32), np.exp(-eb ** 2 / s2).astype(np.float32)
        else:
            self.Va = self.Vb = None
        self.wa = sa[..., 3] + 1e-3                              # splat weight: opaque pixels win
        self.wb = sb[..., 3] + 1e-3

    def _calc(self, dis, pa, pb, sig):
        """Two-stage flow: DIS on a heavily blurred plane first (thin limbs survive the coarse pyramid, so big
        arm swings are tracked), then DIS on the sharp plane against B pre-warped by that guess; flows composed."""
        if sig < 1:
            return dis.calc(pa, pb, None).astype(np.float32)
        f = dis.calc(cv2.GaussianBlur(pa, (0, 0), sig), cv2.GaussianBlur(pb, (0, 0), sig), None).astype(np.float32)
        r = dis.calc(pa, _remap(pb, self.lgx, self.lgy, f), None).astype(np.float32)
        return r + _remap(f, self.lgx, self.lgy, r)

    def _up(self, F):
        h, w = self.size
        if self.low == (h, w):
            return F
        return cv2.resize(F, (w, h), interpolation=cv2.INTER_LINEAR) * self.scale

    def _upv(self, V):
        h, w = self.size
        return V if self.low == (h, w) else cv2.resize(V, (w, h), interpolation=cv2.INTER_LINEAR)

    def at(self, t):
        Lt0 = _splat_flow(self.Fab, self.wa, t, self.lgx, self.lgy)       # t-frame -> A (low res)
        Lt1 = _splat_flow(self.Fba, self.wb, 1 - t, self.lgx, self.lgy)   # t-frame -> B
        wa = _remap(self.A, self.gx, self.gy, self._up(Lt0))
        wb = _remap(self.B, self.gx, self.gy, self._up(Lt1))
        ka, kb = np.float32(1 - t), np.float32(t)
        if self.Va is not None:
            va = self._upv(_remap(self.Va, self.lgx, self.lgy, Lt0)) + 0.05
            vb = self._upv(_remap(self.Vb, self.lgx, self.lgy, Lt1)) + 0.05
            ka, kb = ka * va, kb * vb
            s = ka + kb
            ka, kb = (ka / s)[..., None], (kb / s)[..., None]
        return ka * wa + kb * wb                                 # premultiplied blend


# ---------------------------------------------------------------- optional RIFE (onnxruntime) for RGB
_RIFE = {'sess': None, 'path': None, 'bad': False}


def _rife_session():
    path = os.environ.get('VDS_RIFE_ONNX')
    if not path or _RIFE['bad'] and _RIFE['path'] == path:
        return None
    if _RIFE['sess'] is not None and _RIFE['path'] == path:
        return _RIFE['sess']
    try:
        if not os.path.isfile(path):
            raise FileNotFoundError(path)
        import onnxruntime as ort
        _RIFE['sess'] = ort.InferenceSession(path, providers=['CPUExecutionProvider'])
        _RIFE['path'], _RIFE['bad'] = path, False
        return _RIFE['sess']
    except Exception:
        _RIFE.update(sess=None, path=path, bad=True)
        return None


def _rife_rgb(pa, pb, t):
    """RGB in-between from a RIFE onnx (inputs: img0, img1 [, timestep]; NCHW float 0..1). Colours are
    flattened over mid-grey first. Returns (H, W, 3) float 0..1 or None on any problem."""
    sess = _rife_session()
    if sess is None:
        return None
    try:
        h, w = pa.shape[:2]
        ins = sess.get_inputs()
        imgs = [p[..., :3] + 0.5 * (1 - p[..., 3:4]) for p in (pa, pb)]
        H, W = (h + 63) // 64 * 64, (w + 63) // 64 * 64
        x = [np.pad(i, ((0, H - h), (0, W - w), (0, 0)), mode='edge').transpose(2, 0, 1)[None].astype(np.float32) for i in imgs]
        feed = {ins[0].name: x[0], ins[1].name: x[1]}
        if len(ins) >= 3:
            shp = [d if isinstance(d, int) else 1 for d in (ins[2].shape or [1])]
            if len(shp) == 4:
                shp = [1, 1, H, W] if shp[2] != 1 else [1, 1, 1, 1]
            feed[ins[2].name] = np.full(shp, t, np.float32)
        elif abs(t - 0.5) > 1e-3:
            return None                                          # 2-input exports only do the midpoint
        out = sess.run(None, feed)[0]
        out = np.asarray(out, np.float32)[0, :3, :h, :w].transpose(1, 2, 0)
        return np.clip(out, 0, 1) if out.shape == (h, w, 3) else None
    except Exception:
        return None


def _finish(pm, pf, t, use_rife=True):
    if use_rife and os.environ.get('VDS_RIFE_ONNX'):
        rgb = _rife_rgb(pf.A, pf.B, t)
        if rgb is not None:                                      # RIFE colour inside, flow colour on edges
            al = np.clip(pm[..., 3:4], 0, 1)
            solid = (al > 0.98).astype(np.float32)
            pm = pm.copy(); pm[..., :3] = solid * rgb * al + (1 - solid) * pm[..., :3]
    return _unpremul(pm)


# ---------------------------------------------------------------- public API
def tween(a, b, t, preset='medium', flow_max=480, occlusion=True, flows=None, use_rife=True):
    """In-between of two registered RGBA poses at t in [0,1]. t<=0 returns a, t>=1 returns b (exact copies).
    preset: 'medium' (default) or 'ultrafast'. flow_max: flow is computed on a copy whose long side is at most
    this (then upscaled) - keeps 1080x1080 well under 0.5 s. flows: a PairFlow to reuse (see Tweener)."""
    if t <= 0:
        return a.convert('RGBA').copy()
    if t >= 1:
        return b.convert('RGBA').copy()
    pf = flows or PairFlow(a, b, preset, flow_max, occlusion)
    return _finish(pf.at(float(t)), pf, float(t), use_rife)


def tween_frames(a, b, n, ease=None, **kw):
    """n in-between frames (endpoints excluded) at u = i/(n+1), optionally eased (callable 0..1 -> 0..1).
    Flow is computed once for the whole run."""
    if n <= 0:
        return []
    pf = kw.pop('flows', None) or PairFlow(a, b, kw.pop('preset', 'medium'), kw.pop('flow_max', 480), kw.pop('occlusion', True))
    out = []
    for i in range(1, n + 1):
        u = i / (n + 1)
        out.append(tween(a, b, ease(u) if ease else u, flows=pf, **kw))
    return out


class Tweener:
    """Timeline helper for a Cast-like character. Caches one PairFlow per (pose_a, pose_b), so any t is cheap.

        TW = Tweener()
        im = TW.frame(P, [(0, 'idle'), (1.2, 'wave'), (3.0, 'jump', 'hard')], t)

    images_dict: pose name -> PIL RGBA (registered). timeline entries: (t0, pose) or (t0, pose, 'hard') /
    (t0, pose, {'hard': True}). During the first `dur` s after each soft cut the frame is
    tween(prev, cur, ease_out(u)); hard=True on the call makes every cut hard."""

    def __init__(self, preset='medium', flow_max=480, occlusion=True, ease=ease_out, max_pairs=32):
        self.preset, self.flow_max, self.occlusion, self.ease = preset, flow_max, occlusion, ease
        self.max_pairs, self.cache = max_pairs, {}

    def flows(self, images_dict, pa, pb):
        key = (pa, pb, id(images_dict[pa]), id(images_dict[pb]))
        pf = self.cache.get(key)
        if pf is None:
            if len(self.cache) >= self.max_pairs:
                self.cache.pop(next(iter(self.cache)))
            pf = self.cache[key] = PairFlow(images_dict[pa], images_dict[pb], self.preset, self.flow_max, self.occlusion)
        return pf

    @staticmethod
    def _hard(entry):
        if len(entry) < 3:
            return False
        o = entry[2]
        return o == 'hard' or o is True or (isinstance(o, dict) and bool(o.get('hard')))

    def state(self, timeline, t, dur=0.18, hard=False):
        """(prev_pose, cur_pose, u) - u is None when the plain pose should be shown."""
        tl = sorted(timeline, key=lambda e: e[0])
        i = max([k for k, e in enumerate(tl) if t >= e[0]], default=0)
        cur = tl[i][1]
        if i == 0 or hard or self._hard(tl[i]) or dur <= 0:
            return None, cur, None
        prev = tl[i - 1][1]
        u = (t - tl[i][0]) / dur
        if prev == cur or u >= 1:
            return None, cur, None
        return prev, cur, u

    def frame(self, images_dict, timeline, t, dur=0.18, hard=False):
        prev, cur, u = self.state(timeline, t, dur, hard)
        if u is None:
            return images_dict[cur]
        e = self.ease(u) if self.ease else u
        if e <= 0:
            return images_dict[prev]
        if e >= 1:
            return images_dict[cur]
        return tween(images_dict[prev], images_dict[cur], e, flows=self.flows(images_dict, prev, cur))


def smear(im, dx, dy, strength=1.0, steps=None, falloff=1.6):
    """Directional motion smear (classic animation smear frame) for a fast move of (dx, dy) px this frame.
    The figure stays solid at its current position and leaves a fading stretched trail behind it
    (opposite to the motion). Raster only, same canvas size - leave room on the canvas for the trail."""
    L = math.hypot(dx, dy) * float(strength)
    if L < 0.5:
        return im.convert('RGBA').copy()
    ux, uy = dx / math.hypot(dx, dy), dy / math.hypot(dx, dy)
    pm = _premul(im)
    h, w = pm.shape[:2]
    n = int(steps or min(32, max(3, math.ceil(L / 3))))
    acc = np.zeros_like(pm)
    for k in range(n, -1, -1):                                   # back (trail) to front (figure): 'over'
        s = k / n
        M = np.float32([[1, 0, -ux * L * s], [0, 1, -uy * L * s]])
        layer = cv2.warpAffine(pm, M, (w, h), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT, borderValue=0)
        layer *= np.float32((1 - s) ** falloff) if k else np.float32(1)
        acc = layer + acc * (1 - layer[..., 3:4])
    return _unpremul(acc)


if __name__ == '__main__':                                       # python3 motion2d/inbetween.py a.png b.png out_prefix [n]
    import sys, time
    A, B = Image.open(sys.argv[1]).convert('RGBA'), Image.open(sys.argv[2]).convert('RGBA')
    n = int(sys.argv[4]) if len(sys.argv) > 4 else 3
    t0 = time.time(); fr = tween_frames(A, B, n, ease=ease_out)
    for i, f in enumerate(fr): f.save(f'{sys.argv[3]}_{i + 1:02d}.png')
    print(f'{n} in-betweens in {time.time() - t0:.2f}s')
