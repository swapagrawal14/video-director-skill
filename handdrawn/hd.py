"""handdrawn: raster hand-drawn / whiteboard animation kit. Absolutely no SVG or vector shapes.
Every element is a PNG (AI-painted line art, the user's own art, or text rendered from real fonts) and is
animated by masks: pen draw-on along the ink, line boil, write-on text, rough marker swipes, paper grain.
Look comes from swap-studio style packs (styles/<name>/style.json): colours + fonts + decorations.
All functions are pure functions of time -> deterministic, frame-exact renders."""
import os, json, math, subprocess
import numpy as np, cv2
from PIL import Image, ImageDraw, ImageFont, ImageFilter

HERE = os.path.dirname(os.path.abspath(__file__))


def hexc(h, a=255):
    h = h.lstrip('#'); a = int(h[6:8], 16) if len(h) == 8 else a
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16), a)


def load_style(name):
    S = json.load(open(f'{HERE}/styles/{name}/style.json'))
    if 'extends' in S:
        base = load_style(S['extends']); base['colors'].update(S.get('colors', {})); S = {**base, **{k: v for k, v in S.items() if k != 'colors'}}
    for role, f in S.get('fonts', {}).items():
        f['ttf'] = f"{HERE}/fonts/{os.path.basename(f['src']).replace('.woff2', '.ttf')}"
    return S


def font(S, role, size):
    f = S['fonts'].get(role) or S['fonts']['title']
    return ImageFont.truetype(f['ttf'], size)


# ---------- paper ----------
def paper(W, H, S, seed=1):
    """Paper/board background: base colour + fibre grain + soft vignette (raster noise, no shapes)."""
    c = np.array(hexc(S['colors'].get('paper', S['colors']['bg']))[:3], np.float32)
    rng = np.random.default_rng(seed)
    g = rng.normal(0, 1, (H // 4, W // 4)).astype(np.float32)
    g = cv2.resize(cv2.GaussianBlur(g, (0, 0), 1.2), (W, H), interpolation=cv2.INTER_CUBIC)
    fine = rng.normal(0, 1, (H, W)).astype(np.float32)
    yy, xx = np.mgrid[0:H, 0:W]; v = 1 - .18 * (((xx - W / 2) / W) ** 2 + ((yy - H / 2) / H) ** 2) * 2
    img = c[None, None] * v[..., None] + (g * 5 + fine * 3)[..., None]
    return np.clip(img, 0, 255).astype(np.uint8)


# ---------- draw-on ----------
class DrawOn:
    """Pen draw-on for a PNG: ink lines appear in a traced order, then the colour fill washes in.
    Order = per connected stroke group (top-left first), geodesic distance inside the group from its first point,
    so the line grows along itself like a pen, not as a wipe."""
    def __init__(self, path_or_img, scale=1.0, ink_thr=90):
        im = path_or_img if isinstance(path_or_img, Image.Image) else Image.open(path_or_img)
        im = im.convert('RGBA')
        if scale != 1: im = im.resize((int(im.width * scale), int(im.height * scale)), Image.LANCZOS)
        self.rgba = np.array(im).astype(np.float32)
        a = self.rgba[..., 3]; lum = self.rgba[..., :3].mean(-1)
        ink = ((lum < ink_thr) & (a > 120)).astype(np.uint8)
        ink = cv2.morphologyEx(ink, cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8))
        self.ink = ink.astype(bool)
        self.rank = self._order(ink)

    @staticmethod
    def _order(ink):
        h, w = ink.shape; small = cv2.resize(ink, (max(1, w // 3), max(1, h // 3)), interpolation=cv2.INTER_AREA) > 0
        n, lab, st, _ = cv2.connectedComponentsWithStats(small.astype(np.uint8), 8)
        comps = sorted(range(1, n), key=lambda i: (st[i, 1] // 40, st[i, 0]))
        sizes = np.array([st[i, 4] for i in comps], np.float64); total = sizes.sum() or 1
        R = np.full(small.shape, 2.0, np.float32); done = 0.
        for i, s in zip(comps, sizes):
            m = (lab == i).astype(np.uint8); ys, xs = np.nonzero(m); k = np.argmin(xs + ys * .5)
            seed = np.zeros_like(m); seed[ys[k], xs[k]] = 1
            # geodesic distance via repeated dilation inside the mask (BFS rings)
            dist = np.full(m.shape, -1, np.int32); cur = seed.copy(); d = 0; dist[cur > 0] = 0
            ker = np.ones((3, 3), np.uint8)
            while True:
                nxt = cv2.dilate(cur, ker) & m & (dist < 0)
                if not nxt.any(): break
                d += 1; dist[nxt > 0] = d; cur = nxt
            dd = dist[m > 0].astype(np.float32) / max(1, d)
            R[m > 0] = (done + dd * s) / total; done += s
        return cv2.resize(R, (w, h), interpolation=cv2.INTER_NEAREST)

    def frame(self, p, fill_lag=.25):
        """p: 0..1 lines draw; fill washes in over the last `fill_lag` and after. Returns RGBA float image."""
        lp = min(1, p / (1 - fill_lag)); fp = np.clip((p - (1 - fill_lag)) / fill_lag, 0, 1)
        out = self.rgba.copy(); a = out[..., 3]
        line = self.ink & (self.rank <= lp)
        fill_a = a * (fp ** 1.5) * (~self.ink)
        out[..., 3] = np.where(line, a, fill_a)
        return out


# ---------- boil ----------
def boil(rgba, t, amp=1.6, fps_boil=8, seed=0):
    """Hand-drawn line boil: a new smooth displacement every 1/fps_boil s (held, like redrawn frames)."""
    k = int(t * fps_boil) + seed * 97; rng = np.random.default_rng(k)
    h, w = rgba.shape[:2]
    dx = cv2.resize(rng.normal(0, amp, (6, 6)).astype(np.float32), (w, h), interpolation=cv2.INTER_CUBIC)
    dy = cv2.resize(rng.normal(0, amp, (6, 6)).astype(np.float32), (w, h), interpolation=cv2.INTER_CUBIC)
    xx, yy = np.meshgrid(np.arange(w, dtype=np.float32), np.arange(h, dtype=np.float32))
    return cv2.remap(rgba, xx + dx, yy + dy, cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT)


# ---------- text ----------
def text_img(txt, fnt, color, stroke=0, stroke_color=None):
    box = fnt.getbbox(txt, stroke_width=stroke); w, h = box[2] - box[0] + 8, box[3] - box[1] + 8
    im = Image.new('RGBA', (w, h), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    d.text((4 - box[0], 4 - box[1]), txt, font=fnt, fill=color, stroke_width=stroke, stroke_fill=stroke_color)
    return np.array(im).astype(np.float32)


def write_on(rgba, p, soft=18, seed=3):
    """Text writes itself left to right with a ragged, ink-like leading edge."""
    h, w = rgba.shape[:2]; rng = np.random.default_rng(seed)
    jag = cv2.resize(rng.normal(0, 1, (1, 8)).astype(np.float32), (1, h), interpolation=cv2.INTER_CUBIC)[:, 0] * 6
    edge = p * (w + soft) - soft / 2
    xx = np.arange(w, dtype=np.float32)[None, :]
    m = np.clip((edge + jag[:, None] - xx) / soft + .5, 0, 1)
    out = rgba.copy(); out[..., 3] *= m; return out


def marker_swipe(w, h, color, p, seed=5):
    """Highlighter swipe: rough-edged raster stroke growing left to right (noise mask, not a shape)."""
    rng = np.random.default_rng(seed)
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    top = cv2.resize(rng.normal(0, 1, (1, 10)).astype(np.float32), (w, 1), interpolation=cv2.INTER_CUBIC)[0] * h * .06 + h * .12
    bot = cv2.resize(rng.normal(0, 1, (1, 10)).astype(np.float32), (w, 1), interpolation=cv2.INTER_CUBIC)[0] * h * .06 + h * .9
    body = np.clip(np.minimum(yy - top[None], bot[None] - yy) / 3, 0, 1)
    streak = .82 + .18 * cv2.GaussianBlur(rng.random((h, w)).astype(np.float32), (0, 0), sigmaX=12, sigmaY=.8)
    grow = np.clip((p * w * 1.05 - xx) / 14, 0, 1)
    out = np.zeros((h, w, 4), np.float32); out[..., :3] = color[:3]; out[..., 3] = 255 * body * streak * grow * (color[3] / 255)
    return out


# ---------- compositing ----------
def over(dst, src, x, y, alpha=1.0):
    """Alpha-composite float RGBA src onto uint8 RGB dst at (x, y) (top-left). Clips to frame."""
    H, W = dst.shape[:2]; h, w = src.shape[:2]; x, y = int(round(x)), int(round(y))
    x0, y0, x1, y1 = max(0, x), max(0, y), min(W, x + w), min(H, y + h)
    if x0 >= x1 or y0 >= y1: return dst
    s = src[y0 - y:y1 - y, x0 - x:x1 - x]; a = s[..., 3:4] / 255 * alpha
    d = dst[y0:y1, x0:x1].astype(np.float32); dst[y0:y1, x0:x1] = (d * (1 - a) + s[..., :3] * a).astype(np.uint8)
    return dst


def ease(x): x = min(1, max(0, x)); return x * x * (3 - 2 * x)


def karaoke(dst, words, t, S, y, size=64, max_words=3):
    """Pack-styled karaoke captions: the spoken word pops in the pack's accent; raster text with ink outline."""
    act = [i for i, w in enumerate(words) if w['start'] <= t < w['end'] + .25]
    if not act: return dst
    i = act[-1]; g0 = (i // max_words) * max_words; grp = words[g0:g0 + max_words]
    f = font(S, 'caption', size); ink = hexc(S['colors']['ink']); hi = hexc(S['colors']['accent']); base = hexc(S['colors'].get('accent2', '#FFFFFF'))
    imgs = []
    for j, w in enumerate(grp):
        on = g0 + j == i; pop = 1 + .12 * math.exp(-max(0, t - w['start']) * 12) if on else 1
        im = text_img(w['word'], font(S, 'caption', int(size * pop)), hi if on else base, stroke=6, stroke_color=ink); imgs.append(im)
    tw = sum(im.shape[1] for im in imgs) + 14 * (len(imgs) - 1); x = (dst.shape[1] - tw) / 2
    for im in imgs: over(dst, im, x, y - im.shape[0] / 2); x += im.shape[1] + 14
    return dst


def end_card(dst, S, p, name, handle=''):
    """Raster end card: avatar photo (if the pack has one) cropped round by a soft mask, name writes on, handle fades."""
    H, W = dst.shape[:2]; c = S['colors']
    ec = S.get('endCard', {}); av = ec.get('avatar')
    cy = H * .42
    if av and os.path.exists(f'{HERE}/{av}'):
        r = int(W * .16); im = Image.open(f'{HERE}/{av}').convert('RGB').resize((2 * r, 2 * r), Image.LANCZOS)
        m = np.zeros((2 * r, 2 * r), np.float32); cv2.circle(m, (r, r), r - 2, 1, -1, cv2.LINE_AA)  # mask only, never drawn
        a = np.dstack([np.array(im, np.float32), m * 255 * ease(p * 2)])
        over(dst, a, W / 2 - r, cy - r * 1.5)
    t = text_img(name, font(S, 'title', int(W * .085)), hexc(c['ink'])); t = write_on(t, ease(p * 1.6 - .2))
    over(dst, t, (W - t.shape[1]) / 2, cy + W * .1)
    if handle:
        h = text_img(handle, font(S, 'body', int(W * .05)), hexc(c.get('mark', c['ink']))); over(dst, h, (W - h.shape[1]) / 2, cy + W * .22, ease(p * 2 - 1))
    return dst


def encode(frames_iter, out, W, H, fps=30, audio=None):
    cmd = ['ffmpeg', '-y', '-v', 'error', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', f'{W}x{H}', '-r', str(fps), '-i', '-']
    if audio: cmd += ['-i', audio, '-c:a', 'aac', '-b:a', '192k', '-shortest']
    cmd += ['-c:v', 'libx264', '-crf', '18', '-pix_fmt', 'yuv420p', '-movflags', '+faststart', out]
    pr = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    for fr in frames_iter: pr.stdin.write(fr.tobytes())
    pr.stdin.close(); pr.wait(); return out
