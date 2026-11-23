"""Cartoon kit: full cartoon scenes and episodes in ANY art style (motion2d engine).

What YouTube animators do by hand, as code: a locked art style, a character pose pack that ACTS on
beats, a layered set, lighting that tells the story (lamp off -> scary room -> lamp on), little prop
rigs that keep the frame alive (fan, swing, flicker, glow eyes), a moving world (parallax, tiny planet)
and a beat sheet that drives pose, SFX and camera from one table.

Raster only (no SVG). Characters, props and sets are generated per video as raster images in the chosen
style (`style_prompt()`), keyed and checked; code adds only FX, light, camera and timing.

    from cartoon import ARTSTYLES, style_prompt, style_from_reference, Light, glow_eyes, light_pool, \
        spin, swing, Parallax, TinyPlanet, BeatSheet, Episode, hold_time, shake
    style = ARTSTYLES['pastel_outline']           # or style_from_reference('ref.mp4')
    prompt = style_prompt(style, 'a sleepy boy in a blue t-shirt', kind='character')
    L = Light([(0, 'day'), (2.4, 'powercut'), (5.0, 'day')], flicker=[(2.4, 0.35)])
    beats = BeatSheet([(0.0, 'boy', 'stretch', 'yawn'), (1.6, 'boy', 'reach', 'click'), ...])
    for step in range(N):
        t = hold_time(step / FPS, style['hold'])     # 'ones' or 'twos'
        fr = SET.copy(); ...draw props/cast with beats.pose('boy', t)...
        fr = L.apply(fr, t)                          # grade the whole room
        glow_eyes(fr, [(410, 300), (440, 300)], t, on=L.level(t, 'powercut'))   # emissive AFTER grade

Playbook: docs/CARTOON.md. Credit: Swapnil Agrawal (BDS intern).
"""
import json, math, os, random
import numpy as np, cv2
from PIL import Image
from motion import clamp, ease, squash, xform, paste, place_pivot

# ------------------------------------------------------------------ art styles
# Each pack fixes what keeps a cartoon consistent across every asset and shot. Prompts describe a look
# in words only: never name or copy a studio, show, brand or living artist's characters.
_COMMON_NEG = ('photo, photorealistic, 3D render, gradient mesh, text, watermark, logo, signature, extra limbs, '
               'deformed hands, blurry, jpeg artifacts, vector svg icon, clip-art')
ARTSTYLES = {
    'pastel_outline': dict(
        label='Pastel cel, thin outline (cosy slice-of-life / gentle spooky)',
        core='flat 2D cartoon, soft pastel colours, flat fills, thin even dark-navy outline, rounded simple shapes, '
             'big readable silhouettes, no shading or one flat shadow tone, clean cel animation look',
        outline_px=4, ink='#1E1E3A', palette=['#BDF4FF', '#A8F0D0', '#F25CC4', '#8C7BFF', '#FFE7B3', '#F7A08F'],
        boil=0.8, paper=0.0, grain=0.0, hold='twos', squash=0.07, night='violet'),
    'flat_no_outline': dict(
        label='Flat motion-design, no outlines (promo loops, brand mascots)',
        core='flat 2D motion-design illustration, no outlines, shapes separated by colour only, bold saturated '
             'palette, simple geometric anatomy, long smooth curves, one flat shadow shape per object',
        outline_px=0, ink='#2B3A55', palette=['#3FA9F5', '#FFE14D', '#F26A3D', '#E8E0D0', '#3C4A5E', '#2FA36B'],
        boil=0.0, paper=0.0, grain=0.0, hold='ones', squash=0.10, night='blue'),
    'rubber_hose': dict(
        label='1930s rubber-hose (bouncy vintage gags)',
        core='1930s rubber hose cartoon style, black ink outlines, pie-cut eyes, white gloves, noodle limbs, '
             'limited sepia and cream palette, slight print texture',
        outline_px=7, ink='#141010', palette=['#F3E6C8', '#141010', '#C8452F', '#E9B949', '#8A7F6A'],
        boil=1.4, paper=0.25, grain=6.0, hold='twos', squash=0.14, night='sepia'),
    'anime_cel': dict(
        label='Anime cel (emotional, cinematic)',
        core='anime cel shading, clean thin lineart, two-tone cel shadows, expressive eyes, soft painted '
             'background, cinematic lighting, crisp highlights',
        outline_px=3, ink='#2A2230', palette=['#FCE4D6', '#6C8EBF', '#F2A6A0', '#2A2230', '#FFF6E0', '#9BC4A8'],
        boil=0.0, paper=0.0, grain=2.0, hold='twos', squash=0.03, night='blue'),
    'chibi_sticker': dict(
        label='Chibi sticker (cute mascots, reactions)',
        core='cute chibi cartoon, oversized head, tiny body, thick white sticker border around a dark outline, '
             'flat candy colours, blush cheeks, simple dot eyes with a shine',
        outline_px=6, ink='#3A2E3F', palette=['#FFD6E0', '#FFF1B8', '#B8F2E6', '#A0C4FF', '#3A2E3F', '#FFFFFF'],
        boil=0.6, paper=0.0, grain=0.0, hold='twos', squash=0.12, night='violet'),
    'crayon_kids': dict(
        label='Crayon / kid drawing (storybook, nostalgia)',
        core="child's crayon drawing style, waxy crayon texture strokes, wobbly outlines, paper white background, "
             'bright primary colours with uneven fill',
        outline_px=5, ink='#22252B', palette=['#FFFFFF', '#E63946', '#1D70B8', '#FFC43D', '#3BB273', '#22252B'],
        boil=2.0, paper=0.5, grain=4.0, hold='twos', squash=0.08, night='blue'),
    'paper_cutout': dict(
        label='Paper cut-out (craft, explainers with charm)',
        core='layered coloured paper cut-out illustration, torn and scissor-cut edges, subtle drop shadow between '
             'layers, visible paper fibre texture, flat colours',
        outline_px=0, ink='#3B2F2F', palette=['#F4E9D8', '#E07A5F', '#3D405B', '#81B29A', '#F2CC8F'],
        boil=0.3, paper=0.6, grain=3.0, hold='twos', squash=0.05, night='blue'),
    'watercolor_storybook': dict(
        label='Watercolour storybook (soft, warm narration)',
        core='watercolour picture-book illustration, loose ink line, soft washes with paper bleed, warm light, '
             'gentle colours, hand-painted texture',
        outline_px=2, ink='#3A3430', palette=['#F6EEDF', '#E9A178', '#7FA7C9', '#A7C48D', '#3A3430'],
        boil=0.4, paper=0.7, grain=3.0, hold='twos', squash=0.03, night='blue'),
    'desi_gouache': dict(
        label='Desi gouache (Indian homes, streets, festivals)',
        core='Indian gouache illustration, matte opaque paint, warm earthy palette with marigold and indigo, '
             'simple faces, patterned textiles, flat perspective, hand-painted edges',
        outline_px=3, ink='#2E2333', palette=['#F3D9A4', '#E8833A', '#2F4B8A', '#B83B5E', '#7A9E7E', '#2E2333'],
        boil=0.4, paper=0.4, grain=3.0, hold='twos', squash=0.05, night='indigo'),
    'dark_cartoon': dict(
        label='Dark cartoon horror (adult, creepy but stylised)',
        core='dark stylised 2D cartoon horror, desaturated cold palette, heavy uneven black ink, long thin limbs, '
             'hollow eyes, deep shadows shaped as flat black areas, one sickly accent colour',
        outline_px=6, ink='#0B0B0F', palette=['#2B2D3A', '#4C5266', '#B9B7A7', '#0B0B0F', '#9BBF3B'],
        boil=1.2, paper=0.2, grain=8.0, hold='twos', squash=0.04, night='horror'),
}


def style_prompt(style, subject, kind='character', screen='#00FF00', extra=''):
    """Image-model prompt for one asset in a locked style. kind: character | pose | prop | set | part."""
    s = ARTSTYLES[style] if isinstance(style, str) else style
    pal = ', '.join(s['palette'])
    line = (f"uniform outline {s['outline_px']} px at 1080 in {s['ink']}" if s.get('outline_px')
            else 'no outlines at all')
    if kind == 'set':
        frame = 'full background plate, empty of characters, camera at eye level, room for the action in the middle third'
        bg = ''
    else:
        frame = {'character': 'full body, front three-quarter view, neutral pose, whole figure in frame with margin',
                 'pose': 'same character as the reference image, same proportions, outline and colours, new pose only',
                 'prop': 'single object, centred, whole object visible',
                 'part': 'single separate part for rigging, centred, flat-on, nothing else'}.get(kind, kind)
        bg = f'on a flat solid {screen} chroma background, no shadow on the background'
    return (f"{subject}. {s['core']}. Palette only: {pal}. {line}. {frame}. {bg} {extra}".strip()
            + f"\nNEGATIVE: {_COMMON_NEG}" + (', green tones on the subject' if bg else ''))


# ------------------------------------------------------------------ style from a reference (any art style)
def _read_frames(src, n=6):
    if isinstance(src, np.ndarray): return [src]
    if isinstance(src, Image.Image): return [cv2.cvtColor(np.array(src.convert('RGB')), cv2.COLOR_RGB2BGR)]
    ext = os.path.splitext(str(src))[1].lower()
    if ext in ('.png', '.jpg', '.jpeg', '.webp', '.bmp'):
        return [cv2.imread(str(src))]
    cap = cv2.VideoCapture(str(src)); N = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) or 1; out = []
    for i in range(n):
        cap.set(cv2.CAP_PROP_POS_FRAMES, int((i + 0.5) * N / n)); ok, f = cap.read()
        if ok: out.append(f)
    cap.release()
    return out


def _hex(bgr): return '#%02X%02X%02X' % (int(bgr[2]), int(bgr[1]), int(bgr[0]))


def style_from_reference(src, k=6, name='from_reference', seed=3):
    """Read the LOOK (not the content) of a reference image or video: palette (k-means), outline weight and
    colour, saturation and value, flatness. Returns a style dict usable everywhere ARTSTYLES is."""
    frames = [f for f in _read_frames(src) if f is not None]
    if not frames: raise ValueError(f'no frames in {src}')
    small = [cv2.resize(f, (320, int(320 * f.shape[0] / f.shape[1])), interpolation=cv2.INTER_AREA) for f in frames]
    px = np.concatenate([s.reshape(-1, 3) for s in small]).astype(np.float32)
    crit = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, 0.5)
    cv2.setRNGSeed(seed)
    _, lab, cen = cv2.kmeans(px, k, None, crit, 3, cv2.KMEANS_PP_CENTERS)
    counts = np.bincount(lab.ravel(), minlength=k); order = np.argsort(-counts)
    palette = [_hex(cen[i]) for i in order]
    # outline: thin dark ridges along colour edges
    g = cv2.cvtColor(small[0], cv2.COLOR_BGR2GRAY)
    dark = (g < 70).astype(np.uint8)
    edges = cv2.Canny(cv2.GaussianBlur(small[0], (3, 3), 0), 40, 120)
    edge_px = max(1, int(edges.sum() / 255))
    dark_near_edge = int((cv2.dilate(dark, np.ones((3, 3), np.uint8)) & (edges > 0)).sum())
    has_outline = dark_near_edge / edge_px > 0.35
    outline_px = 0
    if has_outline:
        dist = cv2.distanceTransform(dark, cv2.DIST_L2, 3)
        ridge = dist[(dist > 0) & (cv2.dilate(edges, np.ones((3, 3), np.uint8)) > 0)]
        outline_px = int(round(max(2, min(12, 2 * float(np.median(ridge)) * 1080 / 320)))) if len(ridge) else 4
    ink = _hex(np.median(small[0][dark > 0], axis=0)) if dark.sum() > 50 else '#111111'
    hsv = cv2.cvtColor(small[0], cv2.COLOR_BGR2HSV).reshape(-1, 3).astype(np.float32)
    sat, val = float(hsv[:, 1].mean() / 255), float(hsv[:, 2].mean() / 255)
    inner = cv2.dilate(edges, np.ones((7, 7), np.uint8)) == 0
    lap = cv2.Laplacian(g, cv2.CV_32F)
    lapv = float(lap[inner].var()) if inner.sum() > 100 else float(lap.var())
    flat = float((np.sqrt(((px - cen[lab.ravel()]) ** 2).sum(1)) < 24).mean())   # share of pixels on a flat palette colour
    tone = ('pastel' if sat < 0.38 and val > 0.7 else 'bold saturated' if sat > 0.55 else 'muted') + ' ' + \
        ('bright' if val > 0.72 else 'dark moody' if val < 0.4 else 'mid-tone')
    fill = 'textured hand-painted fills' if lapv > 60 else 'clean flat fills'
    core = (f"2D cartoon, {tone} colours, {fill}, "
            + (f'even {ink} outlines' if has_outline else 'no outlines, shapes separated by colour')
            + ', simple readable shapes, consistent cel look')
    return dict(label=f'{name} (read from reference)', core=core, outline_px=outline_px, ink=ink, palette=palette,
                boil=0.8 if has_outline else 0.0, paper=0.3 if lapv > 60 else 0.0, grain=0.0,
                hold='twos', squash=0.08, night='violet' if sat < 0.45 else 'blue',
                measured=dict(saturation=round(sat, 3), value=round(val, 3), texture=round(lapv, 1),
                              has_outline=bool(has_outline), flatness=round(flat, 3)))


def palette_sheet(style, w=900, h=220):
    """BGR uint8 swatch strip for the look sheet / storyboard."""
    s = ARTSTYLES[style] if isinstance(style, str) else style
    cols = s['palette']; fr = np.zeros((h, w, 3), np.uint8); bw = w // len(cols)
    for i, c in enumerate(cols):
        r, g, b = int(c[1:3], 16), int(c[3:5], 16), int(c[5:7], 16)
        fr[:, i * bw:(i + 1) * bw] = (b, g, r)
        cv2.putText(fr, c, (i * bw + 8, h - 14), cv2.FONT_HERSHEY_SIMPLEX, 0.55,
                    (0, 0, 0) if (r + g + b) > 380 else (255, 255, 255), 1, cv2.LINE_AA)
    return fr


def palette_match(im, style, tol=48.0, alpha_thr=40):
    """Share of an asset's opaque pixels within `tol` (RGB distance) of the style palette or ink.
    Use as the style-lock gate on every generated asset (>= 0.6 for flat styles)."""
    s = ARTSTYLES[style] if isinstance(style, str) else style
    a = np.array(im.convert('RGBA') if isinstance(im, Image.Image) else im)
    rgb = a[..., :3].reshape(-1, 3).astype(np.float32)
    if a.shape[-1] == 4: rgb = rgb[a[..., 3].reshape(-1) > alpha_thr]
    if len(rgb) == 0: return 0.0
    pal = np.array([[int(c[1:3], 16), int(c[3:5], 16), int(c[5:7], 16)] for c in s['palette'] + [s['ink'], '#FFFFFF']], np.float32)
    d = np.sqrt(((rgb[:, None, :] - pal[None]) ** 2).sum(-1)).min(1)
    return float((d < tol).mean())


# ------------------------------------------------------------------ timing
def hold_time(t, hold='twos', fps=24):
    """Quantise time like hand animation: 'ones' (every frame), 'twos' (12 drawings/s), 'threes'."""
    n = {'ones': 1, 'twos': 2, 'threes': 3}.get(hold, hold if isinstance(hold, int) else 1)
    return math.floor(t * fps / n) * n / fps


def seq(t, table, default=None):
    cur = default if default is not None else table[0][1]
    for t0, v in sorted(table, key=lambda e: e[0]):
        if t >= t0: cur = v
    return cur


# ------------------------------------------------------------------ lighting (the story is told in light)
# Each grade: per-channel multiply (B, G, R), lift (B, G, R), saturation multiplier.
GRADES = {
    'day':      ((1.00, 1.00, 1.00), (0, 0, 0), 1.00),
    'sunset':   ((0.80, 0.90, 1.08), (6, 4, 0), 1.05),
    'night':    ((0.62, 0.42, 0.40), (30, 8, 6), 0.75),
    'violet':   ((0.55, 0.30, 0.38), (60, 6, 26), 0.80),   # lamp off, pastel room goes indigo/violet
    'powercut': ((0.40, 0.22, 0.28), (54, 6, 22), 0.70),
    'blue':     ((0.70, 0.45, 0.35), (40, 12, 4), 0.70),
    'indigo':   ((0.62, 0.34, 0.32), (52, 10, 14), 0.72),
    'sepia':    ((0.50, 0.62, 0.72), (6, 10, 18), 0.35),
    'horror':   ((0.42, 0.40, 0.38), (16, 14, 8), 0.40),
    'tv_glow':  ((0.95, 0.70, 0.55), (40, 20, 6), 0.75),
}


def grade(fr, name_or_tuple, amount=1.0):
    mul, lift, sat = GRADES[name_or_tuple] if isinstance(name_or_tuple, str) else name_or_tuple
    f = fr.astype(np.float32)
    if abs(sat - 1) > 1e-3:
        g = f.mean(-1, keepdims=True); f = g + (f - g) * (1 + (sat - 1) * amount)
    m = 1 + (np.array(mul, np.float32) - 1) * amount
    return np.clip(f * m + np.array(lift, np.float32) * amount, 0, 255)


class Light:
    """Keyed lighting states over time. keys: [(t, grade_name), ...]; switches are instant (a light switch) or
    eased over `fade` seconds; flicker: [(t_start, dur)] bursts of on/off before settling (bulb, power cut)."""

    def __init__(self, keys, fade=0.0, flicker=(), seed=5):
        self.keys = sorted(keys, key=lambda k: k[0]); self.fade = fade; self.flicker = list(flicker); self.seed = seed

    def _state(self, t):
        prev, cur, t0 = self.keys[0][1], self.keys[0][1], self.keys[0][0]
        for tk, g in self.keys:
            if t >= tk: prev, cur, t0 = cur, g, tk
        u = 1.0 if self.fade <= 0 else ease((t - t0) / self.fade)
        for fs, fd in self.flicker:
            if fs <= t < fs + fd:
                r = random.Random(self.seed * 1000 + int((t - fs) * 24))
                u = 1.0 if r.random() < 0.5 else 0.0
        return prev, cur, u

    def level(self, t, name):
        """0..1: how much of grade `name` is on screen at t (drive emissive FX with it)."""
        prev, cur, u = self._state(t)
        return (u if cur == name else 0.0) + ((1 - u) if prev == name and cur != name else 0.0)

    def apply(self, fr, t):
        prev, cur, u = self._state(t)
        if u >= 1.0 or prev == cur: return grade(fr, cur)
        if u <= 0.0: return grade(fr, prev)
        return grade(fr, prev) * (1 - u) + grade(fr, cur) * u


def _bgr(c):
    if isinstance(c, str): return (int(c[5:7], 16), int(c[3:5], 16), int(c[1:3], 16))
    return tuple(c)


def light_pool(fr, centre, radius, color='#FFE7B3', strength=0.55, falloff=1.6, aspect=1.0):
    """Additive soft pool of light (lamp, torch, phone screen). Call AFTER the grade so it reads as light."""
    H, W = fr.shape[:2]; cx, cy = centre
    x0, x1 = int(max(0, cx - radius)), int(min(W, cx + radius)); y0, y1 = int(max(0, cy - radius * aspect)), int(min(H, cy + radius * aspect))
    if x1 <= x0 or y1 <= y0 or strength <= 0: return fr
    yy, xx = np.mgrid[y0:y1, x0:x1].astype(np.float32)
    d = np.sqrt(((xx - cx) / radius) ** 2 + ((yy - cy) / (radius * aspect)) ** 2)
    k = (np.clip(1 - d, 0, 1) ** falloff * strength)[..., None]
    col = np.array(_bgr(color), np.float32)
    sub = fr[y0:y1, x0:x1].astype(np.float32)
    fr[y0:y1, x0:x1] = np.clip(sub + (col - sub * 0.35) * k, 0, 255)
    return fr


def glow_eyes(fr, pts, t, on=1.0, color='#FF3D9A', r=7, bloom=3.2, blink=(), core='#FFFFFF', pulse=0.12):
    """Emissive eyes in the dark. on: 0..1 (drive with Light.level). blink: [(t0, dur)] closed windows."""
    if on <= 0.01: return fr
    for b0, bd in blink:
        if b0 <= t < b0 + bd: return fr
    k = on * (1 + pulse * math.sin(t * 9.0))
    glow = np.zeros_like(fr, dtype=np.float32)
    for (x, y) in pts:
        cv2.circle(glow, (int(x), int(y)), int(r * bloom), _bgr(color), -1, cv2.LINE_AA)
    glow = cv2.GaussianBlur(glow, (0, 0), r * bloom * 0.6)
    out = np.clip(fr.astype(np.float32) + glow * 0.9 * k, 0, 255)
    kk = min(1.0, k)
    for (x, y) in pts:
        cv2.circle(out, (int(x), int(y)), r, tuple(float(c) * kk for c in _bgr(color)), -1, cv2.LINE_AA)
        cv2.circle(out, (int(x), int(y)), max(1, r // 2), tuple(float(c) * kk for c in _bgr(core)), -1, cv2.LINE_AA)
    fr[...] = out
    return fr


# ------------------------------------------------------------------ prop rigs (keep the frame alive)
def spin(im, t, rpm=60.0, blur_deg=0.0, steps=5):
    """Rotate a centred part (fan blades, wheel, clock hand). blur_deg>0 smears it like a fast fan."""
    a = -(t * rpm / 60.0) * 360.0
    if blur_deg <= 0: return im.rotate(a, resample=Image.BICUBIC)
    acc = np.zeros((im.height, im.width, 4), np.float32)
    for i in range(steps):
        acc += np.array(im.rotate(a - blur_deg * i / max(1, steps - 1), resample=Image.BICUBIC), np.float32)
    return Image.fromarray((acc / steps).astype(np.uint8))


def swing(t, amp=8.0, freq=0.6, damp=0.0, t0=0.0):
    """Pendulum angle (deg) for hanging things: clothes on a hook, lamp cord, sign. damp>0 settles after a bump at t0."""
    u = max(0.0, t - t0)
    return amp * math.sin(2 * math.pi * freq * u) * (math.exp(-damp * u) if damp > 0 else 1.0)


def shake(t, t0, dur=0.35, amp=14.0, freq=28.0, seed=1):
    """Camera shake (dx, dy) after an impact or a scare at t0."""
    u = t - t0
    if u < 0 or u > dur: return 0.0, 0.0
    k = amp * (1 - u / dur) ** 2; r = random.Random(seed + int(u * freq))
    return k * (r.random() * 2 - 1), k * (r.random() * 2 - 1)


def push(t, t0, t1, z0=1.0, z1=1.12):
    """Camera zoom factor easing from z0 to z1 between t0 and t1 (slow push-in for tension)."""
    return z0 + (z1 - z0) * ease((t - t0) / max(1e-6, t1 - t0))


def camera_frame(fr, zoom=1.0, cx=None, cy=None, dx=0.0, dy=0.0):
    """Apply zoom about (cx, cy) plus offset to a finished frame."""
    H, W = fr.shape[:2]; cx = W / 2 if cx is None else cx; cy = H / 2 if cy is None else cy
    M = np.array([[zoom, 0, (1 - zoom) * cx + dx], [0, zoom, (1 - zoom) * cy + dy]], np.float32)
    return cv2.warpAffine(fr.astype(np.float32), M, (W, H), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)


# ------------------------------------------------------------------ moving worlds
class Parallax:
    """Side-scrolling world: layers = [(BGR or RGBA image, depth)], depth 0 = sky (static) .. 1 = ground.
    Layers tile horizontally. speed = ground px/s."""

    def __init__(self, layers, W, H, speed=240.0):
        self.L = []; self.W, self.H, self.speed = W, H, speed
        for im, depth in layers:
            a = np.array(im.convert('RGBA')) if isinstance(im, Image.Image) else im
            if a.shape[-1] == 3: a = np.dstack([a[..., ::-1], np.full(a.shape[:2], 255, np.uint8)])
            self.L.append((a, depth))

    def render(self, t, base=None):
        fr = np.zeros((self.H, self.W, 3), np.float32) if base is None else base.astype(np.float32).copy()
        for a, depth in self.L:
            h, w = a.shape[:2]; off = int(t * self.speed * depth) % w
            strip = np.concatenate([a, a], 1)[:, off:off + self.W] if w < self.W * 2 else a[:, off:off + self.W]
            if strip.shape[1] < self.W: strip = np.concatenate([strip, a[:, :self.W - strip.shape[1]]], 1)
            y = self.H - h
            sub = strip[:min(h, self.H), :self.W].astype(np.float32); al = sub[..., 3:4] / 255
            y0 = max(0, y); sub = sub[y0 - y:]; al = al[y0 - y:]
            fr[y0:y0 + sub.shape[0]] = fr[y0:y0 + sub.shape[0]] * (1 - al) + sub[..., 2::-1] * al
        return fr


class TinyPlanet:
    """A round hill the hero rides on: the ground disc turns, props stand on it at fixed angles and pass by.
    disc: RGBA image of the hill/planet (square). props: [(RGBA, angle_deg, lift_px)]."""

    def __init__(self, disc, centre, radius, props=(), deg_per_s=-18.0):
        self.disc = disc; self.c = centre; self.r = radius; self.props = list(props); self.w = deg_per_s

    def angle(self, t): return self.w * t

    def draw(self, fr, t):
        a = self.angle(t)
        d = self.disc.resize((int(self.r * 2), int(self.r * 2)), Image.LANCZOS).rotate(a, resample=Image.BICUBIC)
        for im, ang, lift in self.props:          # behind the rim line, standing on the surface
            th = math.radians(ang - a - 90)
            x = self.c[0] + (self.r + lift) * math.cos(th); y = self.c[1] + (self.r + lift) * math.sin(th)
            if y > self.c[1] + self.r * 0.2: continue
            place_pivot(fr, im, x, y, (im.width / 2, im.height), -(ang - a))
        paste(fr, d, self.c[0], self.c[1])
        return fr

    def top(self): return self.c[0], self.c[1] - self.r


# ------------------------------------------------------------------ beat sheet (acting + SFX + camera in one table)
class BeatSheet:
    """beats: [(t, actor, pose_or_action, sfx_or_None, note?)]. One row per thing that happens on screen.
    The same table drives pose changes, the SFX track, the action list for the storyboard and the lint gates."""

    def __init__(self, beats):
        rows = []
        for b in beats:
            b = list(b) + [None] * (5 - len(b)); rows.append(dict(t=float(b[0]), actor=b[1], act=b[2], sfx=b[3], note=b[4] or ''))
        self.rows = sorted(rows, key=lambda r: r['t'])

    def pose(self, actor, t, default='idle'):
        cur = default
        for r in self.rows:
            if r['actor'] == actor and r['t'] <= t: cur = r['act']
        return cur

    def since(self, actor, t):
        """seconds since this actor's last beat (for squash pops, settle wobbles)."""
        last = None
        for r in self.rows:
            if r['actor'] == actor and r['t'] <= t: last = r['t']
        return t - last if last is not None else 1e9

    def sfx_events(self):
        return [(r['t'], r['sfx']) for r in self.rows if r['sfx']]

    def action_list(self):
        return '\n'.join(f"{r['t']:5.2f}s  {r['actor']:<8} {r['act']:<14} sfx={r['sfx'] or '-':<10} {r['note']}" for r in self.rows)

    def check(self, duration, max_still=4.0, actors_on_screen=None):
        """Lint the acting: no actor holds a pose longer than max_still s while on screen; every beat that
        changes a character (not camera/light) has a sound. Returns a list of problems (empty = OK)."""
        probs = []
        acts = actors_on_screen or sorted({r['actor'] for r in self.rows if r['actor'] not in ('cam', 'light', 'fx')})
        for a in acts:
            ts = [r['t'] for r in self.rows if r['actor'] == a]
            if not ts: probs.append(f'{a}: no beats'); continue
            gaps = [b - a_ for a_, b in zip([0.0] + ts, ts + [duration])]
            if max(gaps) > max_still + 1e-6: probs.append(f'{a}: holds {max(gaps):.1f}s without a new beat (max {max_still}s)')
        for r in self.rows:
            if r['actor'] not in ('cam',) and not r['sfx'] and r['actor'] != 'light':
                probs.append(f"{r['t']:.2f}s {r['actor']} '{r['act']}' has no SFX")
        return probs

    def to_json(self, path):
        with open(path, 'w') as f: json.dump(self.rows, f, indent=1)


# ------------------------------------------------------------------ episodes (several shots, hard cuts)
class Episode:
    """shots: [(name, seconds)]. at(t) -> (index, name, local_t, u 0..1). Cuts are hard; use a 2-frame
    match-on-action when a move continues across the cut."""

    def __init__(self, shots):
        self.shots = [(n, float(d)) for n, d in shots]; self.duration = sum(d for _, d in self.shots)

    def at(self, t):
        acc = 0.0
        for i, (n, d) in enumerate(self.shots):
            if t < acc + d or i == len(self.shots) - 1:
                lt = t - acc; return i, n, lt, clamp(lt / d)
            acc += d

    def starts(self):
        acc, out = 0.0, []
        for n, d in self.shots: out.append((acc, n)); acc += d
        return out


# ------------------------------------------------------------------ finish
def paper_texture(W, H, amount=0.3, seed=9):
    """Multiply-style paper/canvas texture (crayon, watercolour, cut-out looks). Returns float32 (H,W,1)."""
    rs = np.random.RandomState(seed)
    n = cv2.GaussianBlur(rs.randn(H // 2, W // 2).astype(np.float32), (0, 0), 1.2)
    n = cv2.resize(n, (W, H)); fib = cv2.GaussianBlur(rs.randn(H, W).astype(np.float32), (0, 0), 0.6)
    tex = 1 - amount * 0.06 * (n / (np.abs(n).max() + 1e-6)) - amount * 0.03 * (fib / (np.abs(fib).max() + 1e-6))
    return tex[..., None]


def make_style_finish(W, H, style, n=4, seed=7):
    """Final pass for a style: paper texture + grain, quantised. finish(fr, step) -> uint8."""
    s = ARTSTYLES[style] if isinstance(style, str) else style
    tex = paper_texture(W, H, s.get('paper', 0.0), seed) if s.get('paper', 0) > 0 else None
    rs = np.random.RandomState(seed)
    grains = [rs.randn(H, W, 1).astype(np.float32) * s.get('grain', 0.0) for _ in range(n)] if s.get('grain', 0) > 0 else None

    def finish(fr, step):
        f = fr.astype(np.float32)
        if tex is not None: f = f * tex
        if grains is not None: f = f + grains[step % n]
        return np.clip(f, 0, 255).astype(np.uint8)
    return finish


def night_grade_for(style):
    s = ARTSTYLES[style] if isinstance(style, str) else style
    return s.get('night', 'night')
