"""Slice an AI-generated sprite sheet (one row of N frames, e.g. a walk/run cycle) into
registered frames: same canvas, feet on one baseline, torso centred, so the cycle doesn't jitter.

    from sheets import slice_sheet
    walk = slice_sheet('bablu_walk_sheet.png', n=6)      # list of RGBA PIL images

Prompt tip that works: pass a blank WIDE canvas (e.g. 2400x700 green) as the FIRST reference
image so the model draws a wide sheet, the character's key pose as the SECOND reference, and ask
for 'exactly N frames in one horizontal row, evenly spaced, same size, feet on one baseline,
strict side view facing RIGHT, solid #00FF00 background, no ground line'.
"""
import numpy as np
from PIL import Image


def _clean_ground_lines(a, frac=0.3):
    """remove floor lines the model sometimes draws: rows holding one unbroken run of
    alpha longer than frac of the width (characters in a sheet are separated by gaps)"""
    m = a > 40; W = m.shape[1]
    for y in range(m.shape[0]):
        r = m[y]
        if r.sum() < frac * W: continue
        d = np.diff(np.concatenate([[0], r.astype(np.int8), [0]]))
        st, en = np.where(d == 1)[0], np.where(d == -1)[0]
        if (en - st).max() > frac * W: a[y] = 0
    return a


def slice_sheet(path, n, thr=40, pad=20):
    """n = number of frames in the row. Every connected blob of ink is assigned to the
    frame cell its centre falls in, so arms/feet crossing a cell edge stay with their body."""
    import cv2
    im = Image.open(path).convert('RGBA'); arr = np.array(im)
    arr[..., 3] = _clean_ground_lines(arr[..., 3].copy())
    m = (arr[..., 3] > thr).astype(np.uint8)
    cnt, lab, stats, cents = cv2.connectedComponentsWithStats(m, 8)
    xs_all = np.where(m.any(axis=0))[0]; X0, X1 = xs_all.min(), xs_all.max() + 1
    cell = (X1 - X0) / n
    owner = np.zeros(cnt, int) - 1
    for k in range(1, cnt):
        if stats[k, cv2.CC_STAT_AREA] < 30: continue
        owner[k] = min(n - 1, int((cents[k][0] - X0) // cell))
    raw = []
    for c in range(n):
        keep = np.isin(lab, np.where(owner == c)[0])
        sub = arr.copy(); sub[..., 3] = np.where(keep, sub[..., 3], 0)
        ys, xs = np.where(sub[..., 3] > thr)
        raw.append(sub[ys.min():ys.max() + 1, xs.min():xs.max() + 1])
    frames = []
    for sub in raw:
        a = sub[..., 3] > thr; h = a.shape[0]
        top = a[: int(h * 0.55)]; xs = np.where(top)[1]
        cx = xs.mean() if len(xs) else a.shape[1] / 2      # torso/head centre = registration x
        frames.append((sub, cx))
    Hm = max(f[0].shape[0] for f in frames)
    half = int(max(max(cx, f.shape[1] - cx) for f, cx in frames)) + pad
    out = []
    for sub, cx in frames:
        c = np.zeros((Hm + pad, half * 2, 4), np.uint8)
        h, w = sub.shape[:2]; ox = int(round(half - cx)); oy = Hm + pad - h
        c[oy:oy + h, ox:ox + w] = sub
        out.append(Image.fromarray(c))
    return out


def mirror_legs_below_hem(im, hem_y, cx=None, feather=14, thr=40):
    """For front/back stepping sheets where the model drew the SAME leg forward in every frame: mirror only the
    region below the hem (hem_y, source px; a float < 1 is a fraction of the alpha-box height from its top)
    about the body's centre line and blend it back with a feathered seam, giving the alternate-leg frame.
    cx: centre x (default: centre of the alpha in the band just above the hem). Returns a new RGBA image."""
    import cv2
    a = np.array(im.convert('RGBA')).astype(np.float32); Hh, Ww = a.shape[:2]
    m = a[..., 3] > thr; ys, xs = np.where(m); y0, y1 = ys.min(), ys.max()
    hy = int(y0 + hem_y * (y1 - y0)) if hem_y < 1 else int(hem_y)
    if cx is None:
        band = m[max(0, hy - 30):hy]; bx = np.where(band)[1]
        cx = bx.mean() if len(bx) else Ww / 2
    M = np.float32([[-1, 0, 2 * cx], [0, 1, 0]])               # x' = 2cx - x
    mir = cv2.warpAffine(a, M, (Ww, Hh), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT, borderValue=(0, 0, 0, 0))
    w = np.clip((np.arange(Hh, dtype=np.float32) - (hy - feather / 2)) / max(feather, 1), 0, 1)[:, None, None]
    out = a * (1 - w) + mir * w
    return Image.fromarray(np.clip(out, 0, 255).astype(np.uint8), 'RGBA')


def cycle_fps(ground_speed, stride, frames_per_step):
    """frame rate that makes feet plant instead of skate: steps/s = ground speed / stride (same screen units,
    both scaled with the character), times frames per step (6-frame walk sheet = 2 steps -> 3)."""
    return ground_speed / stride * frames_per_step


def contact_sheet(frames, cols=None, cell_h=360, bg=(0, 255, 0), baseline=True, labels=True):
    """Lay frames side by side on one image for the walk check: legs must alternate, feet on the red baseline.
    frames: list of RGBA PIL images (registered) or paths. Returns an RGB PIL image."""
    from PIL import ImageDraw
    ims = [Image.open(f).convert('RGBA') if isinstance(f, str) else f.convert('RGBA') for f in frames]
    cols = cols or len(ims); rows = (len(ims) + cols - 1) // cols
    k = cell_h / max(i.height for i in ims); cw = int(max(i.width for i in ims) * k) + 10
    sheet = Image.new('RGB', (cols * cw, rows * (cell_h + 10)), bg); d = ImageDraw.Draw(sheet)
    for n, im in enumerate(ims):
        r, c = divmod(n, cols); t = im.resize((max(1, int(im.width * k)), max(1, int(im.height * k))), Image.LANCZOS)
        ox, oy = c * cw + (cw - t.width) // 2, r * (cell_h + 10) + cell_h - t.height
        sheet.paste(t, (ox, oy), t)
        if labels: d.text((c * cw + 6, r * (cell_h + 10) + 4), str(n), fill=(0, 0, 0))
    if baseline:
        for r in range(rows):
            y = r * (cell_h + 10) + cell_h - 1; d.line([(0, y), (sheet.width, y)], fill=(255, 0, 0), width=1)
    return sheet


if __name__ == '__main__':      # python3 engine/sheets.py out.png frame0.png frame1.png ...  -> walk-check contact sheet
    import sys
    contact_sheet(sys.argv[2:]).save(sys.argv[1]); print('wrote', sys.argv[1])
