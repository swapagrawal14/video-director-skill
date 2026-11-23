"""Turn AI-generated raster art into a screencast host pack + decor set. Raster only, no SVG.

Host pack (talking character), from pixel-aligned image edits of one painted base:
    python3 -m screencast.make_pack host --base talk.png --pose point=point.png --pose wave=wave.png \
        --mouth A=mA.png --mouth O=mO.png --mouth E=mE.png --blink blink.png -o screencast/assets/host
  -> <out>/talk.png point.png ... (cropped to one shared box), mouth.{rest,A,O,E}.png, blink.png, pack.json
  The mouth/blink patches are cut from the edits where they differ from the base, so the face is the SAME
  painted head in every pose and the expression never changes by itself (docs/CHARACTERS.md rule 1).

Decor (keyed PNG cut-outs: cursor, marker circle/arrow, click burst, highlighter, tape, torn strip, badge):
    python3 -m screencast.make_pack decor --src raw/ -o screencast/assets
"""
import argparse, json, os
import numpy as np, cv2
from PIL import Image


def despill(rgba):
    """Remove chroma-green fringe left by keying: clamp G to max(R, B) on semi-transparent / edge pixels."""
    a = rgba.astype(np.float32); r, g, b = a[..., 0], a[..., 1], a[..., 2]
    lim = np.maximum(r, b); spill = g > lim + 8
    a[..., 1] = np.where(spill, lim, g)
    a[..., 3] = np.where(spill & (a[..., 3] < 250), a[..., 3] * .6, a[..., 3])
    return np.clip(a, 0, 255).astype(np.uint8)


def alpha_bbox(rgba, thr=16, pad=4):
    ys, xs = np.nonzero(rgba[..., 3] > thr)
    h, w = rgba.shape[:2]
    return max(0, xs.min() - pad), max(0, ys.min() - pad), min(w, xs.max() + 1 + pad), min(h, ys.max() + 1 + pad)


def diff_rect(base, var, thr=40, pad=10, below=None):
    """Bounding box of the region where an image edit differs from its base (largest components)."""
    d = np.abs(var[..., :3].astype(np.float32) - base[..., :3]).max(-1)
    d *= np.minimum(var[..., 3], base[..., 3]) / 255.
    m = (cv2.GaussianBlur(d, (0, 0), 2) > thr).astype(np.uint8)
    n, _, st, _ = cv2.connectedComponentsWithStats(m)
    comps = [st[i] for i in range(1, n) if st[i][4] >= 300 and (below is None or st[i][1] >= below)]
    if not comps: raise SystemExit('edit does not differ from base')
    x0 = min(c[0] for c in comps); y0 = min(c[1] for c in comps)
    x1 = max(c[0] + c[2] for c in comps); y1 = max(c[1] + c[3] for c in comps)
    return x0 - pad, y0 - pad, x1 + pad, y1 + pad


def feather(w, h, f=8):
    m = np.zeros((h, w), np.float32); m[f:h - f, f:w - f] = 1
    return cv2.GaussianBlur(m, (0, 0), f / 2)


def build_host(base, poses, mouths, blink, out):
    os.makedirs(out, exist_ok=True)
    B = despill(np.array(Image.open(base).convert('RGBA')))
    P = {'talk': B, **{k: despill(np.array(Image.open(v).convert('RGBA'))) for k, v in poses.items()}}
    M = {k: despill(np.array(Image.open(v).convert('RGBA'))) for k, v in mouths.items()}
    boxes = [alpha_bbox(a) for a in P.values()]
    cx0, cy0 = min(b[0] for b in boxes), min(b[1] for b in boxes)
    cx1, cy1 = max(b[2] for b in boxes), max(b[3] for b in boxes)
    Bl = despill(np.array(Image.open(blink).convert('RGBA'))) if blink else None
    er = diff_rect(B, Bl) if blink else None
    rects = [diff_rect(B, m, below=er[3] - 4 if er else None) for m in M.values()]
    mr = [min(r[0] for r in rects), min(r[1] for r in rects), max(r[2] for r in rects), max(r[3] for r in rects)]
    pack = {'poses': {}, 'mouth': {}, 'crop': [int(cx0), int(cy0), int(cx1), int(cy1)]}

    def patch(src, r, name):
        x0, y0, x1, y1 = r; p = src[y0:y1, x0:x1].copy()
        p[..., 3] = (p[..., 3].astype(np.float32) * feather(x1 - x0, y1 - y0)).astype(np.uint8)
        Image.fromarray(p).save(f'{out}/{name}.png', optimize=True)
        return {'file': f'{name}.png', 'x': int(x0 - cx0), 'y': int(y0 - cy0), 'w': int(x1 - x0), 'h': int(y1 - y0)}

    for k, a in P.items():
        Image.fromarray(a[cy0:cy1, cx0:cx1]).save(f'{out}/{k}.png', optimize=True); pack['poses'][k] = f'{k}.png'
    pack['mouth']['rest'] = patch(B, mr, 'mouth.rest')
    for k, a in M.items(): pack['mouth'][k] = patch(a, mr, f'mouth.{k}')
    if blink:
        pack['blink'] = patch(Bl, er, 'blink'); pack['eyes_rest'] = patch(B, er, 'eyes.rest')
    json.dump(pack, open(f'{out}/pack.json', 'w'), indent=1)
    return pack


DECOR = {  # raw file -> (out name, max side)
    'sc_cursor_hand.png': ('cursor_hand', 220), 'sc_marker_circle.png': ('marker_circle', 700),
    'sc_marker_arrow.png': ('marker_arrow', 600), 'sc_click_burst.png': ('click_burst', 320),
    'sc_highlighter.png': ('highlighter', 700), 'sc_tape.png': ('tape', 360),
    'sc_torn_strip.png': ('torn_strip', 1000), 'sc_follow_badge.png': ('follow_badge', 640)}


def build_decor(src, out):
    os.makedirs(out, exist_ok=True)
    for f, (name, side) in DECOR.items():
        p = os.path.join(src, f)
        if not os.path.exists(p): continue
        a = despill(np.array(Image.open(p).convert('RGBA')))
        x0, y0, x1, y1 = alpha_bbox(a); im = Image.fromarray(a[y0:y1, x0:x1])
        s = min(1, side / max(im.size)); im = im.resize((round(im.width * s), round(im.height * s)), Image.LANCZOS)
        im.save(f'{out}/{name}.png', optimize=True)
    gp = os.path.join(src, 'sc_graphpaper.png')
    if os.path.exists(gp): Image.open(gp).convert('RGB').save(f'{out}/graphpaper.jpg', quality=88)


if __name__ == '__main__':
    ap = argparse.ArgumentParser(); ap.add_argument('kind', choices=['host', 'decor'])
    ap.add_argument('--base'); ap.add_argument('--pose', action='append', default=[]); ap.add_argument('--mouth', action='append', default=[])
    ap.add_argument('--blink'); ap.add_argument('--src'); ap.add_argument('-o', required=True)
    a = ap.parse_args(); kv = lambda L: dict(x.split('=', 1) for x in L)
    if a.kind == 'host': print(json.dumps(build_host(a.base, kv(a.pose), kv(a.mouth), a.blink, a.o)))
    else: build_decor(a.src, a.o)
