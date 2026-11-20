"""Pose-pack character animation (rigpop-motion method) for vid-shark.

Characters are NOT puppets built from vector/SVG shapes. Each character is a pack of
AI-drawn key poses (full-body PNGs, transparent), all REGISTERED in one frame (same canvas
size, same scale, feet on the same baseline). The engine:
  * hard-cuts between key poses on a timeline (no cross-dissolves),
  * keeps every pose alive: breathing, slow sway, a squash 'pop' on each cut,
  * plays cycles (walk / run sheets sliced with sheets.py) while moving the body along x,
  * gives world coordinates of any anchor point (dome, hand, phone...) so props follow.

Typical use:
    from posepack import Cast, seq
    BA = Cast('poses/bablu', ['idle','wave','flinch'], x=975, floor=1050, scale=0.88)
    pose = seq(t, [(0,'idle'), (1.2,'wave'), (3.0,'idle')])
    BA.draw(fr, t, pose, rot=0, dy=0)
    dome = BA.world(DOME_IN_SOURCE_PX)
"""
import math, os
import numpy as np, cv2
from PIL import Image
from motion import squash, xform, paste, place_pivot


def seq(t, table, default=None):
    """table: [(t0, value), ...]. Returns the value of the last entry with t0 <= t."""
    cur = default if default is not None else table[0][1]
    for t0, v in sorted(table, key=lambda e: e[0]):
        if t >= t0: cur = v
    return cur


def alpha_bbox(im, thr=40):
    a = np.array(im)[..., 3] > thr; ys, xs = np.where(a)
    return xs.min(), ys.min(), xs.max(), ys.max()


class Cast:
    """One character = a folder/prefix of registered pose PNGs: <prefix>_<pose>.png"""

    def __init__(self, prefix, poses, x, floor, scale=1.0, phase=0.0, fix_scale=None,
                 breath=0.007, sway=0.7, bob=2.5, pop=0.06, shadow=True, cycles=None):
        self.x, self.floor, self.phase = x, floor, phase
        self.breath, self.sway, self.bob, self.pop, self.shadow = breath, sway, bob, pop, shadow
        self.P = {}
        fix_scale = fix_scale or {}
        for p in poses:
            im = Image.open(f'{prefix}_{p}.png').convert('RGBA')
            k = scale * fix_scale.get(p, 1.0)
            _, _, _, by = alpha_bbox(im)
            im = im.resize((int(im.width * k), int(im.height * k)), Image.LANCZOS)
            # pivot = feet (bottom of alpha) at canvas centre x; all keys share the canvas
            self.P[p] = (im, (im.width / 2, by * k), k)
        for name, frames in (cycles or {}).items():       # frames: list of RGBA PIL (from sheets.py)
            for i, im in enumerate(frames):
                im = im.resize((int(im.width * scale), int(im.height * scale)), Image.LANCZOS)
                _, _, _, by = alpha_bbox(im)
                self.P[f'{name}{i}'] = (im, (im.width / 2, by), scale)
        self.last, self.cut_t, self.xf = None, 0.0, (0, 1, 1, 0, 0)
        self.flip = False

    def cycle(self, name, t, fps=10, n=None):
        """pose name of a looping cycle (walk0..walkN) at time t"""
        n = n or sum(1 for k in self.P if k.startswith(name) and k[len(name):].isdigit())
        return f'{name}{int(t * fps) % n}'

    def world(self, ip, pose=None):
        """source-pixel point of the current pose -> world coords (call after draw)"""
        pose = pose or self.last
        im, piv, k = self.P[pose]; rot, sx, sy, dx, dy = self.xf
        ix = ip[0] * k
        if self.flip: ix = im.width - ix
        vx, vy = (ix - piv[0]) * sx, (ip[1] * k - piv[1]) * sy
        a = math.radians(-rot)
        return (self.x + dx + vx * math.cos(a) - vy * math.sin(a),
                self.floor + dy + vx * math.sin(a) + vy * math.cos(a))

    def draw(self, fr, t, pose, rot=0.0, dx=0.0, dy=0.0, sq=(1, 1), live=True, flip=False):
        is_cycle = pose.rstrip('0123456789') != pose and pose not in ('',)
        if pose != self.last and not (is_cycle and self.last and self.last.rstrip('0123456789') == pose.rstrip('0123456789')):
            self.cut_t = t
        self.last, self.flip = pose, flip
        im, piv, k = self.P[pose]
        if flip: im = im.transpose(Image.FLIP_LEFT_RIGHT)
        br = self.breath * math.sin(t * 2.2 + self.phase) if live else 0
        r = rot + (self.sway * math.sin(t * 1.9 + self.phase) if live else 0)
        kc = t - self.cut_t
        px, py = squash(kc, self.pop, 22, 7) if kc < 0.6 else (1, 1)
        sx, sy = px * sq[0] * (1 - br * 0.4), py * sq[1] * (1 + br)
        by = self.bob * math.sin(t * 2.6 + self.phase) if live else 0
        self.xf = (r, sx, sy, dx, dy + by)
        if self.shadow:
            sh = np.zeros((44, im.width + 40, 4), np.uint8)
            cv2.ellipse(sh, (sh.shape[1] // 2, 22), (int(im.width * 0.3), 12), 0, 0, 360, (70, 40, 60, 70), -1, cv2.LINE_AA)
            paste(fr, Image.fromarray(sh), self.x + dx, self.floor - 4)
        img = xform(im, sx, sy) if (abs(sx - 1) > 1e-3 or abs(sy - 1) > 1e-3) else im
        piv2 = (piv[0] * img.width / im.width, piv[1] * img.height / im.height)
        place_pivot(fr, img, self.x + dx, self.floor + dy + by, piv2, r)


# ---------------------------------------------------------------- cut-out QA helpers (see AGENTS.md QA gates)
def alpha_coverage(im, thr=40):
    """fraction of the canvas that is opaque. ~1.0 means keying failed (no transparency): regenerate.
    A healthy full-body cut-out is usually 0.05-0.6."""
    return float((np.array(im.convert('RGBA'))[..., 3] > thr).mean())


def despill_edge(im, ring_px=4):
    """Kill green-screen spill/halo on a cut-out's outline: clamp G to max(R, B) inside an edge ring of
    ring_px, and erode alpha by 1 px. Apply at load time to any cut-out keyed off #00FF00."""
    a = np.array(im.convert('RGBA')); al = a[..., 3]; m = (al > 8).astype(np.uint8)
    ring = (m - cv2.erode(m, np.ones((2 * ring_px + 1,) * 2, np.uint8))).astype(bool)
    rgb = a[..., :3].astype(np.int16); g = np.minimum(rgb[..., 1], np.maximum(rgb[..., 0], rgb[..., 2]))
    a[..., 1] = np.where(ring, g, rgb[..., 1]).astype(np.uint8)
    a[..., 3] = cv2.erode(al, np.ones((3, 3), np.uint8))
    return Image.fromarray(a, 'RGBA')


def green_fringe(im, ring_px=4, thr=40):
    """share of edge-ring pixels that are green-dominant (G > max(R,B) + 25). > ~0.05 = visible halo: despill."""
    a = np.array(im.convert('RGBA')); m = (a[..., 3] > thr).astype(np.uint8)
    ring = (m - cv2.erode(m, np.ones((2 * ring_px + 1,) * 2, np.uint8))).astype(bool)
    if not ring.any(): return 0.0
    r, g, b = [a[..., i].astype(np.int16)[ring] for i in range(3)]
    return float((g > np.maximum(r, b) + 25).mean())


def check_registration(paths, base_tol=6, height_tol=0.04, thr=40):
    """Pose-pack registration report. paths: list of pose PNGs meant to share one canvas.
    Checks: same canvas size, feet baseline (alpha bottom) within base_tol px of the median, figure height
    within height_tol of the median (fix with Cast(fix_scale=...) or regenerate), alpha coverage, green fringe.
    Returns (rows, problems) where rows = [dict(name, size, bottom, height, coverage, fringe)]."""
    rows = []
    for p in paths:
        im = Image.open(p).convert('RGBA'); x0, y0, x1, y1 = alpha_bbox(im, thr)
        rows.append(dict(name=os.path.basename(p), size=im.size, bottom=int(y1), height=int(y1 - y0),
                         coverage=round(alpha_coverage(im, thr), 3), fringe=round(green_fringe(im), 3)))
    sizes = {r['size'] for r in rows}; mb = float(np.median([r['bottom'] for r in rows]))
    mh = float(np.median([r['height'] for r in rows])); probs = []
    if len(sizes) > 1: probs.append(f'canvas sizes differ: {sorted(sizes)} (regenerate with a registered pose as FIRST ref)')
    for r in rows:
        if abs(r['bottom'] - mb) > base_tol: probs.append(f"{r['name']}: feet at y={r['bottom']} vs median {mb:.0f}")
        if abs(r['height'] / mh - 1) > height_tol: probs.append(f"{r['name']}: height {r['height']} vs median {mh:.0f} (fix_scale {mh / r['height']:.3f})")
        if r['coverage'] > 0.95: probs.append(f"{r['name']}: no transparency (coverage {r['coverage']}), keying failed")
        if r['fringe'] > 0.05: probs.append(f"{r['name']}: green fringe {r['fringe']:.0%} of edge, run despill_edge")
    return rows, probs


if __name__ == '__main__':                                  # python3 engine/posepack.py girl/girl_*.png
    import sys, glob
    files = sorted(f for a in sys.argv[1:] for f in glob.glob(a))
    rows, probs = check_registration(files)
    for r in rows: print(r)
    print('\n'.join(probs) if probs else 'registration OK')
