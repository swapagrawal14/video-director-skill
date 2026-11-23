"""Camera, transitions, captions and finishing for screencast reels. Every function here is a pure function of t.

Camera  : a slow push-in each beat (1.00 -> 1.05), a sine drift and a tiny roll, plus a punch-in kick on each beat start.
Cuts    : at each beat boundary, one of whip (horizontal motion-blur slide), rip (torn-paper wipe),
          zoomblur (radial zoom-blur punch) or flash (white pop). Choose per beat with "transition", or a rotation.
Captions: "box" style. A dark rounded pill top-centre, a chunk of words revealed with a per-letter scramble,
          and the current word in the accent colour.
Finish  : vignette + static-per-frame paper grain (seeded by frame index, so it is deterministic).
"""
import math, random, os
import numpy as np, cv2

ROTATION = ['whip', 'rip', 'zoomblur', 'whip', 'flash']
SCRAMBLE = '#%&@ABCDEFGHJKLMNPQRSTUVWXYZ'
DEVA_FONTS = [os.path.expanduser('~/.fonts/NotoSansDevanagari.ttf'), '/usr/share/fonts/truetype/noto/NotoSansDevanagari-Bold.ttf']


def is_deva(w): return any('\u0900' <= c <= '\u097f' for c in w)


def deva_font(size, _c={}):
    """Devanagari fallback (the caption fonts have no Devanagari glyphs). Needs Pillow with raqm for correct shaping."""
    if size not in _c:
        from PIL import ImageFont
        path = next((p for p in DEVA_FONTS if os.path.exists(p)), None)
        if not path: _c[size] = None
        else:
            f = ImageFont.truetype(path, size, layout_engine=ImageFont.Layout.RAQM if ImageFont.core.HAVE_RAQM else ImageFont.Layout.BASIC)
            try: f.set_variation_by_name('Bold')
            except Exception: pass
            _c[size] = f
    return _c[size]


def ease(x): x = min(1, max(0, x)); return x * x * (3 - 2 * x)


def camera(img, t, beat_start, beat_end, seed=0):
    """Push-in across the beat + drift + punch kick on the cut. img: HxWx3 uint8."""
    H, W = img.shape[:2]
    u = (t - beat_start) / max(.1, beat_end - beat_start)
    push = 1 + .05 * ease(u)
    kick = .045 * math.exp(-max(0, t - beat_start) * 7) * (t >= beat_start)
    z = push + kick
    dx = 6 * math.sin(t * .7 + seed); dy = 5 * math.sin(t * .53 + 1.3 + seed); rot = .35 * math.sin(t * .41 + seed)
    M = cv2.getRotationMatrix2D((W / 2, H * .45), rot, z); M[0, 2] += dx; M[1, 2] += dy
    return cv2.warpAffine(img, M, (W, H), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)


def _hblur(img, k):
    k = int(k) | 1
    if k < 3: return img
    ker = np.zeros((1, k), np.float32); ker[0] = 1 / k
    return cv2.filter2D(img, -1, ker)


def whip(img, d, W):
    """d in [-1, 1]: -1 = fully exited left, 0 = rest, +1 = entering from the right."""
    sh = int(d * W * .55); out = np.roll(img, -sh, axis=1)
    return _hblur(out, abs(d) * 140)


def zoomblur(img, s):
    """Radial zoom blur with strength s in [0, 1] (averages a few scaled copies)."""
    if s < .02: return img
    H, W = img.shape[:2]; acc = img.astype(np.float32); n = 6
    for i in range(1, n):
        z = 1 + s * .18 * i / n; M = cv2.getRotationMatrix2D((W / 2, H * .4), 0, z)
        acc += cv2.warpAffine(img, M, (W, H), borderMode=cv2.BORDER_REFLECT)
    return (acc / n).astype(np.uint8)


def torn_mask(H, W, p, seed=7):
    """Mask (HxW float32 0..1): 1 where the NEW frame shows. A ragged diagonal edge sweeps left->right as p goes 0->1."""
    rng = np.random.default_rng(seed); ys = np.arange(H)
    jag = np.cumsum(rng.normal(0, 3.2, H)); jag -= jag.mean(); jag = np.clip(jag, -40, 40)
    edge = (-.25 + p * 1.5) * W + jag - ys * .18
    m = (np.arange(W)[None, :] < edge[:, None]).astype(np.float32)
    return cv2.GaussianBlur(m, (3, 3), 0)


def transition(kind, frame_at, t, cut, dur=.32):
    """frame_at(t) -> finished RGB frame (camera applied). Returns the frame with the cut effect at time t near `cut`."""
    a, b = cut - dur / 2, cut + dur / 2
    cur = frame_at(t)
    if not (a <= t < b): return cur
    u = (t - a) / dur; W = cur.shape[1]; H = cur.shape[0]
    if kind == 'whip':
        d = -ease(u * 2) if t < cut else 1 - ease((u - .5) * 2)
        return whip(cur, d, W)
    if kind == 'zoomblur':
        return zoomblur(cur, 1 - abs(u - .5) * 2)
    if kind == 'flash':
        k = 1 - abs(u - .5) * 2; return (cur.astype(np.float32) * (1 - .85 * k) + 255 * .85 * k).astype(np.uint8)
    if kind == 'rip':
        old = frame_at(a - 1e-3); new = frame_at(max(t, cut)); m = torn_mask(H, W, ease(u))[..., None]
        shade = np.ones((H, W, 1), np.float32)
        edge = np.clip(cv2.GaussianBlur(m, (31, 31), 0)[..., None] - m, 0, 1) if m.ndim == 2 else None
        out = new * m + old * (1 - m)
        # paper-white torn lip just ahead of the edge
        lip = np.clip(torn_mask(H, W, min(1, ease(u) + .015), seed=7) - m[..., 0], 0, 1)[..., None]
        out = out * (1 - lip) + 248 * lip
        return out.astype(np.uint8)
    return cur


def finish(img, fi, vignette=.32, grain=5, _cache={}):
    H, W = img.shape[:2]
    key = (H, W, vignette)
    if key not in _cache:
        yy, xx = np.mgrid[0:H, 0:W]; r = np.sqrt(((xx - W / 2) / (W / 2)) ** 2 + ((yy - H / 2) / (H / 2)) ** 2) / 1.414
        _cache[key] = (1 - vignette * np.clip(r, 0, 1) ** 2.2)[..., None].astype(np.float32)
    out = img.astype(np.float32) * _cache[key]
    if grain:
        rng = np.random.default_rng(fi % 24); n = rng.normal(0, grain, (H // 2, W // 2)).astype(np.float32)
        out += cv2.resize(n, (W, H), interpolation=cv2.INTER_LINEAR)[..., None]
    return np.clip(out, 0, 255).astype(np.uint8)


def box_captions(dst, words, t, font_fn, accent, y=150, max_words=3, text_img=None, over=None, light=False):
    """Dark rounded pill top-centre; chunk of up to max_words; letters scramble for 0.12 s before they settle."""
    act = [i for i, w in enumerate(words) if w['start'] <= t < w['end'] + .25]
    if not act: return dst
    i = act[-1]; g0 = (i // max_words) * max_words; grp = words[g0:g0 + max_words]
    imgs = []
    for j, w in enumerate(grp):
        txt = w['word']; age = t - w['start']
        deva = is_deva(txt)
        if age < .12 and not deva:          # scramble Latin only: shaped scripts would render as broken clusters
            rnd = random.Random(int(t * 30) * 31 + g0 + j)
            k = int(len(txt) * ease(age / .12))
            txt = txt[:k] + ''.join(rnd.choice(SCRAMBLE) for _ in txt[k:])
        on = g0 + j == i
        if age < 0: continue
        base = (24, 24, 28, 255) if light else (255, 255, 255, 255)
        fnt = (deva_font(42) or font_fn(46)) if deva else font_fn(46)
        imgs.append(text_img(txt, fnt, accent if on else base, stroke=3 if light and on else 0, stroke_color=(24, 24, 28, 255)))
    if not imgs: return dst
    gap = 12; tw = sum(im.shape[1] for im in imgs) + gap * (len(imgs) - 1); th = max(im.shape[0] for im in imgs)
    W = dst.shape[1]; px, py = 26, 14
    bw, bh = int(tw + 2 * px), int(th + 2 * py); x0, y0 = int((W - bw) / 2), int(y - bh / 2)
    pc = (250, 248, 240, 240) if light else (20, 20, 24, 225)          # pill flips to light on dark backgrounds
    box = np.zeros((bh, bw, 4), np.float32); cv2.rectangle(box, (bh // 2, 0), (bw - bh // 2, bh), pc, -1)
    cv2.circle(box, (bh // 2, bh // 2), bh // 2, pc, -1, cv2.LINE_AA); cv2.circle(box, (bw - bh // 2, bh // 2), bh // 2, pc, -1, cv2.LINE_AA)
    over(dst, box, x0, y0)
    x = (W - tw) / 2
    for im in imgs: over(dst, im, x, y - im.shape[0] / 2); x += im.shape[1] + gap
    return dst


def sketch_play_sticker(size=150, seed=4):
    """Raster red sketched play-button sticker with a white die-cut border (drawn, not vector)."""
    rng = np.random.default_rng(seed); s = size; im = np.zeros((s, s, 4), np.uint8)
    w, h = int(s * .86), int(s * .62); x0, y0 = (s - w) // 2, (s - h) // 2
    cv2.rectangle(im, (x0 - 8, y0 - 8), (x0 + w + 8, y0 + h + 8), (255, 255, 255, 255), -1)
    cv2.rectangle(im, (x0, y0), (x0 + w, y0 + h), (225, 40, 40, 255), -1)
    for k in range(3):   # loose hand-drawn outline passes
        j = rng.integers(-3, 4, 4)
        cv2.rectangle(im, (x0 + j[0], y0 + j[1]), (x0 + w + j[2], y0 + h + j[3]), (40, 20, 20, 255), 3, cv2.LINE_AA)
    tri = np.array([[s * .43, s * .36], [s * .43, s * .64], [s * .64, s * .5]], np.int32)
    cv2.fillPoly(im, [tri], (255, 255, 255, 255), cv2.LINE_AA); cv2.polylines(im, [tri], True, (40, 20, 20, 255), 3, cv2.LINE_AA)
    return im.astype(np.float32)


# ---------------------------------------------------------------- per-beat backgrounds (contrast rotation)
BG_ROTATION = ['graph', 'chalk', 'sun', 'graph', 'teal', 'chalk', 'pink']
DARK_BGS = {'chalk', 'teal'}


def make_bg(kind, W, H, graph=None, seed=0):
    """Raster backgrounds that swap on every cut so the eye gets a fresh, contrasting field.
    graph: the graph-paper image (HxWx3 uint8). Dark kinds flip caption pills to light (see DARK_BGS)."""
    rng = np.random.default_rng(seed + hash(kind) % 997)
    if kind == 'graph' and graph is not None: return graph.copy()
    base = {'chalk': (34, 38, 48), 'sun': (255, 212, 74), 'teal': (22, 160, 150), 'pink': (255, 148, 170)}.get(kind, (240, 236, 226))
    img = np.full((H, W, 3), base, np.float32)
    if kind == 'chalk':          # chalkboard: faint grid + smudges
        for x in range(0, W, 40): img[:, x:x + 1] += 10
        for y in range(0, H, 40): img[y:y + 1, :] += 10
        sm = cv2.GaussianBlur(rng.normal(0, 1, (H // 8, W // 8)).astype(np.float32), (0, 0), 3)
        img += cv2.resize(sm, (W, H))[..., None] * 9
    elif kind == 'sun':          # halftone dots
        for y in range(0, H, 26):
            for x in range((y // 26) % 2 * 13, W, 26): cv2.circle(img, (x, y), 3, (255, 230, 140), -1, cv2.LINE_AA)
    elif kind == 'teal':         # diagonal stripes
        for k in range(-H, W, 46): cv2.line(img, (k, 0), (k + H, H), (34, 176, 166), 14, cv2.LINE_AA)
    elif kind == 'pink':         # confetti doodles
        for _ in range(70):
            x, y = int(rng.integers(0, W)), int(rng.integers(0, H)); c = [(255, 255, 255), (255, 214, 92), (90, 200, 250)][int(rng.integers(0, 3))]
            cv2.ellipse(img, (x, y), (9, 4), float(rng.integers(0, 180)), 0, 360, c, -1, cv2.LINE_AA)
    img += rng.normal(0, 3, (H, W, 1))
    return np.clip(img, 0, 255).astype(np.uint8)
