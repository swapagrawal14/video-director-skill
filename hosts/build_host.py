"""Build a host pack from raw chroma-green AI edits (raster only, no SVG / no 3D).

Wraps screencast.make_pack.build_host (same output format: poses, mouth.*, blink, eyes.rest, pack.json) with
two pre-steps it does not do itself:
  1. chroma key (pure #00FF00-ish background -> alpha), conservative so GREEN CLOTHES (scrubs) survive;
  2. face lock: the face region (eyes + mouth, from the blink/mouth diffs) of the base is pasted, feathered,
     onto every pose edit, so all poses carry the SAME painted face and the mouth/blink patches sit seamlessly.
It also swaps make_pack's global despill for an edge-only one (the global one greys out green scrubs).

    python3 hosts/build_host.py --base raw/base.png --pose point=raw/point.png ... \
        --mouth A=raw/mA.png --mouth O=raw/mO.png --blink raw/blink.png -o hosts/<name>
"""
import argparse, json, os, sys, tempfile
import numpy as np, cv2
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from screencast import make_pack as mp  # noqa: E402


def key(rgb):
    """Chroma-green key -> RGBA. Only saturated, bright greens go transparent (scrubs are dark/muted)."""
    a = rgb.astype(np.float32); r, g, b = a[..., 0], a[..., 1], a[..., 2]
    spill = g - np.maximum(r, b)                      # how much greener than the other channels
    alpha = np.clip((140 - spill) / 60, 0, 1)        # spill>=140 -> 0, spill<=80 -> 1
    alpha = np.where(g < 150, 1, alpha)              # dark greens (scrubs, shadows) are always opaque
    alpha = cv2.GaussianBlur(alpha, (0, 0), .7)
    m = (alpha > .5).astype(np.uint8)                # drop specks
    n, lab, st, _ = cv2.connectedComponentsWithStats(m)
    keep = np.zeros(n, bool); keep[1:] = st[1:, 4] >= 400
    alpha *= keep[lab] | (cv2.dilate((keep[lab]).astype(np.uint8), np.ones((5, 5), np.uint8)) > 0)
    return np.dstack([rgb, (alpha * 255).astype(np.uint8)])


def edge_despill(rgba):
    """Clamp green spill only on soft / edge pixels, never on the opaque interior (keeps green clothes)."""
    a = rgba.astype(np.float32); r, g, b, al = a[..., 0], a[..., 1], a[..., 2], a[..., 3]
    edge = (al < 250) | (cv2.erode((al > 128).astype(np.uint8), np.ones((9, 9), np.uint8)) == 0)   # ~4 px band
    lim = np.maximum(r, b); spill = edge & (g > lim + 8)
    a[..., 1] = np.where(spill, lim, g)
    return np.clip(a, 0, 255).astype(np.uint8)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--base', required=True); ap.add_argument('--pose', action='append', default=[])
    ap.add_argument('--mouth', action='append', default=[]); ap.add_argument('--blink')
    ap.add_argument('--lock-pad', type=int, default=24); ap.add_argument('-o', required=True)
    a = ap.parse_args(); kv = lambda L: dict(x.split('=', 1) for x in L)
    rgb = lambda p: np.array(Image.open(p).convert('RGB'))
    B = rgb(a.base); poses, mouths = kv(a.pose), kv(a.mouth)
    # face-lock rect = union of where the mouth/blink edits differ from the base
    op = lambda im: np.dstack([im, np.full(im.shape[:2], 255, np.uint8)])
    rects = [mp.diff_rect(op(B), op(rgb(p))) for p in list(mouths.values()) + ([a.blink] if a.blink else [])]
    x0 = max(0, min(r[0] for r in rects) - a.lock_pad); y0 = max(0, min(r[1] for r in rects) - a.lock_pad)
    x1 = min(B.shape[1], max(r[2] for r in rects) + a.lock_pad); y1 = min(B.shape[0], max(r[3] for r in rects) + a.lock_pad)
    fm = mp.feather(x1 - x0, y1 - y0, 12)[..., None]
    tmp = tempfile.mkdtemp(); out = lambda n, im: (Image.fromarray(im).save(f'{tmp}/{n}.png'), f'{tmp}/{n}.png')[1]
    kb = out('base', key(B)); kp = {}
    for k, p in poses.items():
        P = rgb(p).astype(np.float32)
        P[y0:y1, x0:x1] = P[y0:y1, x0:x1] * (1 - fm) + B[y0:y1, x0:x1] * fm
        kp[k] = out(f'pose_{k}', key(P.astype(np.uint8)))
    km = {k: out(f'm_{k}', key(rgb(p))) for k, p in mouths.items()}
    kbl = out('blink', key(rgb(a.blink))) if a.blink else None
    mp.despill = edge_despill
    pack = mp.build_host(kb, kp, km, kbl, a.o)
    print(json.dumps({'face_lock': [int(v) for v in (x0, y0, x1, y1)], **pack}))


if __name__ == '__main__':
    main()
