"""Motion-doodle style preset (Pinterest-style flat 2D motion reels) for vid-shark.

Characters and props are NOT drawn in code and are NOT vector/SVG shapes. Every character, prop and
logo mark is an AI-generated RASTER cut-out, generated on chroma green #00FF00 and keyed out, in a
flat cel look: flat fills, one clean uniform black outline, no gradients, a small bright palette.
This module adds the doodle feel on top of those cut-outs:
  * PALETTES + asset_prompt(): one place for the colour sets and the image-model prompt core,
  * line_boil(): the hand-drawn "boil" (outline wobble that changes every few frames),
  * flat_bg() / DOODLE_FINISH(): flat colour plates and a clean finish (no grain/vignette by default),
  * speed_lines(), impact_burst(), pop_text(): FX strokes and slam-in type (FX, like particles: allowed),
  * wheel_spin(), bounce(): the two moves every mascot sting needs.

Typical use:
    from doodle import PALETTES, flat_bg, line_boil, bounce, wheel_spin, pop_text, DOODLE_FINISH
    from motion import paste, xform
    W, H, FPS = 1080, 1920, 24
    BG = flat_bg(W, H, 'bubblegum'); finish = DOODLE_FINISH(W, H)
    for step in range(int(4 * FPS)):
        t = step / FPS; fr = BG.copy()
        dy, sx, sy = bounce(t, period=0.5, height=60)
        paste(fr, line_boil(xform(TRUCK, sx, sy), step), 540, 1100 + dy)
        pop_text(fr, 'COOL!', None, (540, 600), t - 1.0, color=PALETTES['bubblegum']['ink'])
        out = finish(fr, step)

Frames are float32 (or uint8) BGR numpy arrays (H, W, 3), layers are PIL RGBA images, like motion.py.
Playbook: docs/MOTION_DOODLE.md.  Credit: Swapnil Agrawal (BDS intern).
"""
import math, os, random
import numpy as np, cv2
from PIL import Image, ImageDraw, ImageFont
from motion import back, squash, xform, paste, clamp

HERE = os.path.dirname(os.path.abspath(__file__))
FONT_CANDIDATES = [os.path.join(HERE, 'fonts', 'Fredoka.ttf'),
                   os.path.join(HERE, '..', 'fonts', 'baloo2.ttf')]

# ---------------------------------------------------------------- palettes
# colours are hex strings (RGB). bg = flat plate, ink = outlines/FX/type, fills = cel colours for assets.
# No pure/near-pure green anywhere: it would key out with the #00FF00 screen.
PALETTES = {
    'bubblegum':     dict(bg='#F7A8C4', ink='#111111', fills=['#FFF4DE', '#111111', '#FF5C8A', '#FFD23F', '#FFFFFF'],
                          note='pink plate, black + cream mascot, hot-pink and yellow accents (logo stings)'),
    'sunny_lineart': dict(bg='#FFD43B', ink='#111111', fills=['#FFFFFF', '#111111'],
                          note='yellow plate, black line-art with white fills only (delivery/runner gags)'),
    'pastel_cel':    dict(bg='#CFE3F5', ink='#1E1E28', fills=['#F9D5C2', '#A9C7EC', '#F6E7A8', '#E8B4D0', '#FFFFFF', '#8C6B5A'],
                          note='soft pastel cel cartoon, rooms and slice-of-life'),
    'mono_ink':      dict(bg='#F4EFE6', ink='#111111', fills=['#F4EFE6', '#111111', '#E63946'],
                          note='off-white plate, black ink, one red spot colour'),
}


def hex_rgb(h):
    h = h.lstrip('#'); return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def hex_bgr(h):
    r, g, b = hex_rgb(h); return (b, g, r)


def _pal(palette):
    return PALETTES[palette] if isinstance(palette, str) else palette


# ---------------------------------------------------------------- asset prompt
NEGATIVE = ['gradients', 'shading', 'soft shadows', 'highlights', 'texture', 'grain', 'noise', 'halftone',
            'glow', '3D render', 'photorealism', 'sketchy or broken lines', 'varying line weight', 'drop shadow',
            'background scenery', 'ground line', 'cast shadow', 'green colours on the subject', 'green spill',
            'watermark', 'signature', 'brand logos', 'copied text', 'blurry edges', 'extra limbs']

_KIND = {
    'character': ('a single cartoon character, full body, centred, whole figure inside the frame with a margin, '
                  'simple rubber-hose limbs, big readable silhouette, neutral standing pose'),
    'prop': 'a single object, centred, whole object inside the frame with a margin, side or 3/4 view',
    'logo_mark': ('a bold mascot/emblem mark, centred, chunky simple shapes, sticker-like, readable at small size'),
    'background': ('a simple flat background plate, full frame, very few large shapes, low detail, '
                   'leave the centre clear for characters, no characters, no people'),
}


def asset_prompt(subject, palette='bubblegum', kind='character', size=1080, outline_px=6, text=None):
    """Prompt core for the image model (append the acting beat / pose yourself).
    kind: 'character' | 'prop' | 'logo_mark' | 'background'. Outline ~6 px at 1080, scaled with `size`.
    Text is never drawn by the model except on a logo_mark when `text` is given; normally pop_text() adds it.
    Returns one string ending in a NEGATIVE: list."""
    if kind not in _KIND: raise ValueError(f'kind must be one of {list(_KIND)}')
    p = _pal(palette); ow = max(2, round(outline_px * size / 1080))
    fills = ', '.join(p['fills'])
    parts = [f'{_KIND[kind]}: {subject}.',
             'Flat 2D cel cartoon in a modern motion-doodle style: flat solid colour fills only, '
             f'one clean uniform black outline of about {ow} px around every shape (same weight everywhere), '
             'no gradients, no shading, no texture, crisp hard edges, simple geometric shapes, minimal detail.',
             f'Limited palette: {fills}; outline colour {p["ink"]}.']
    if kind == 'background':
        parts.append(f'Base colour {p["bg"]}, flat fills, no chroma green.')
    else:
        parts.append('Place the subject on a perfectly flat pure chroma green #00FF00 background (it will be keyed out), '
                     'no green anywhere on the subject, no shadow on the ground, nothing touching the frame edge.')
    if kind == 'logo_mark' and text:
        parts.append(f'Lettering exactly "{text}" in a bold rounded display font with the same black outline.')
    else:
        parts.append('No text, no letters, no numbers (any type is added later in code).')
    parts.append('Separate parts that will move (wheels, speech bubble, fan blades) are generated as their own images.')
    return ' '.join(parts) + ' NEGATIVE: ' + ', '.join(NEGATIVE) + '.'


# ---------------------------------------------------------------- line boil
def _noise_field(h, w, scale, seed):
    gh, gw = max(2, int(math.ceil(h / scale)) + 2), max(2, int(math.ceil(w / scale)) + 2)
    g = np.random.RandomState(seed).uniform(-1, 1, (gh, gw)).astype(np.float32)
    f = cv2.resize(g, (int(gw * scale), int(gh * scale)), interpolation=cv2.INTER_CUBIC)
    return f[:h, :w]


def line_boil(im, step, amp=1.2, scale=24, hold=3, seed=11):
    """Hand-drawn boil: displace the whole RGBA layer by a smooth noise field (cell `scale` px, max
    `amp` px) that changes every `hold` frames. Same (step // hold, seed) -> same pixels, always.
    Keep amp 0.8-1.6 px at 1080; more reads as jelly, not as a redraw. Returns PIL RGBA."""
    im = im if isinstance(im, Image.Image) else Image.fromarray(np.asarray(im))
    a = np.array(im.convert('RGBA')); h, w = a.shape[:2]
    if amp <= 0: return Image.fromarray(a, 'RGBA')
    k = (seed * 7919 + (step // max(1, hold)) * 104729) % (2 ** 31)
    dx = _noise_field(h, w, scale, k) * amp
    dy = _noise_field(h, w, scale, k + 1) * amp
    xx, yy = np.meshgrid(np.arange(w, dtype=np.float32), np.arange(h, dtype=np.float32))
    out = cv2.remap(a, xx + dx, yy + dy, cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT, borderValue=(0, 0, 0, 0))
    return Image.fromarray(out, 'RGBA')


# ---------------------------------------------------------------- plates / finish
def flat_bg(W, H, palette='bubblegum', paper_tint=0.0, seed=3):
    """Flat colour plate as float32 BGR. paper_tint (0..1, keep <= 0.3) adds a VERY subtle low-frequency
    paper mottling (max ~3 levels at 1.0); 0 = perfectly flat, the default doodle look."""
    fr = np.empty((H, W, 3), np.float32); fr[:] = hex_bgr(_pal(palette)['bg'])
    if paper_tint > 0:
        n = _noise_field(H, W, max(W, H) / 6, seed) * 0.7 + _noise_field(H, W, 40, seed + 1) * 0.3
        fr += (n * 3.0 * paper_tint)[..., None]
    return np.clip(fr, 0, 255)


def DOODLE_FINISH(W, H, grain=0.0, n=4, seed=7):
    """Finish factory for flat doodle frames: no vignette, no flicker, no grain by default.
    grain > 0 (try 1.0-2.0) adds a tiny static-ish grain cycling over n tiles. finish(fr, step) -> uint8 BGR."""
    rs = np.random.RandomState(seed)
    grains = [rs.randn(H, W, 1).astype(np.float32) * grain for _ in range(n)] if grain > 0 else None
    def finish(fr, step=0):
        fr = np.asarray(fr, np.float32)
        if grains is not None: fr = fr + grains[step % n]
        return np.clip(np.rint(fr), 0, 255).astype(np.uint8)
    return finish


make_doodle_finish = DOODLE_FINISH


# ---------------------------------------------------------------- FX strokes
def _color(c):
    return hex_bgr(c) if isinstance(c, str) else tuple(c)


def speed_lines(frame_bgr, origin, direction_deg, t, n=4, length=140, spread=90, gap=26, thick=6,
                color='#111111', speed=2.5, seed=5):
    """Animated dash lines trailing BEHIND a moving object. origin = back edge of the object,
    direction_deg = direction of travel (0 = right, 90 = down, screen coords). Dashes slide backwards
    and restart, so they read as wind. spread = total width across the trail. Draws in place and returns the frame."""
    col = _color(color); a = math.radians(direction_deg)
    ux, uy = -math.cos(a), -math.sin(a)                 # backwards
    px, py = -uy, ux                                    # perpendicular
    rnd = random.Random(seed)
    for i in range(n):
        off = (i / (n - 1) - 0.5) * spread if n > 1 else 0.0
        ph = rnd.random(); L = length * rnd.uniform(0.6, 1.0)
        u = (t * speed + ph) % 1.0                      # 0..1 travel along the trail
        s0 = gap + u * length * 0.5; s1 = s0 + L * (1 - 0.7 * u)   # slide back + shorten, then restart
        x0, y0 = origin[0] + px * off + ux * s0, origin[1] + py * off + uy * s0
        x1, y1 = origin[0] + px * off + ux * s1, origin[1] + py * off + uy * s1
        cv2.line(frame_bgr, (int(x0), int(y0)), (int(x1), int(y1)), col, thick, cv2.LINE_AA)
    return frame_bgr


def impact_burst(frame, centre, t_since, color='#111111', n=8, r0=40, r1=110, dur=0.25, thick=6, rot=12, aspect=1.0):
    """Comic pop burst: n short rays shoot out from centre and shrink away over `dur` s.
    aspect < 1 squashes the ring vertically (for wide text). Nothing is drawn before the hit (t_since < 0)
    or after dur. Flat strokes, no fade. Returns frame."""
    if t_since < 0 or t_since > dur: return frame
    u = t_since / dur; col = _color(color)
    inner = r0 + (r1 - r0) * min(1.0, u * 1.6); outer = r0 + (r1 - r0) * min(1.0, 0.35 + u * 1.2)
    if outer - inner < 2: return frame
    for i in range(n):
        a = math.radians(rot + 360 * i / n)
        L = 1.0 if i % 2 == 0 else 0.75
        p0 = (int(centre[0] + math.cos(a) * inner), int(centre[1] + math.sin(a) * inner * aspect))
        p1 = (int(centre[0] + math.cos(a) * outer * L), int(centre[1] + math.sin(a) * outer * L * aspect))
        cv2.line(frame, p0, p1, col, thick, cv2.LINE_AA)
    return frame


def _font(font_path, size):
    for p in ([font_path] if font_path else []) + FONT_CANDIDATES:
        if p and os.path.exists(p):
            f = ImageFont.truetype(p, size)
            try:
                names = [v.decode() if isinstance(v, bytes) else v for v in f.get_variation_names()]
                for want in ('ExtraBold', 'Bold'):
                    if want in names: f.set_variation_by_name(want); break
            except Exception:
                pass
            return f
    return ImageFont.load_default()


def text_layer(text, font_path=None, size=160, fill='#FFFFFF', stroke='#111111', stroke_px=10):
    """Bold outlined type rendered by PIL to an RGBA raster (cropped to the ink)."""
    f = _font(font_path, size)
    d = ImageDraw.Draw(Image.new('RGBA', (8, 8)))
    x0, y0, x1, y1 = d.textbbox((0, 0), text, font=f, stroke_width=stroke_px)
    pad = stroke_px + 4
    im = Image.new('RGBA', (x1 - x0 + 2 * pad, y1 - y0 + 2 * pad), (0, 0, 0, 0))
    ImageDraw.Draw(im).text((pad - x0, pad - y0), text, font=f, fill=hex_rgb(fill) if isinstance(fill, str) else fill,
                            stroke_width=stroke_px, stroke_fill=hex_rgb(stroke) if isinstance(stroke, str) else stroke)
    return im


def pop_text(frame, text, font_path, centre, t_since, size=160, fill='#FFFFFF', color='#111111', stroke_px=10,
             dur=0.28, rot=-4, burst=True):
    """Slam-in type: scale from 0.2 with back() overshoot over `dur`, then a damped squash on landing,
    plus an impact_burst at the landing. font_path None -> motion2d/fonts/Fredoka.ttf (Bold) or fonts/baloo2.ttf.
    Nothing drawn while t_since < 0. Returns frame."""
    if t_since < 0: return frame
    im = text_layer(text, font_path, size, fill, color, stroke_px)
    if t_since < dur:
        s = 0.2 + 0.8 * back(t_since / dur); sx, sy = s, s
    else:
        sx, sy = squash(t_since - dur, amt=0.10, freq=22, damp=7)   # land: wide + short first
    im = xform(im, max(0.05, sx), max(0.05, sy), rot)
    if burst:
        hw = im.width / 2; asp = clamp(im.height / max(1, im.width) * 1.8, 0.3, 1.0)
        impact_burst(frame, centre, t_since - dur, color, r0=hw * 1.08, r1=hw * 1.4, thick=stroke_px // 2 + 3, aspect=asp)
    paste(frame, im, centre[0], centre[1])
    return frame


# ---------------------------------------------------------------- moves
def wheel_spin(im, t, rpm=90.0):
    """Rotate a (square, centred) wheel layer about its centre: rpm turns/min, + = clockwise on screen.
    Canvas size is kept. Rolling without skid: rpm = 60 * speed_px_s / (pi * wheel_diameter_px)."""
    deg = -360.0 * rpm / 60.0 * t
    im = im if isinstance(im, Image.Image) else Image.fromarray(np.asarray(im))
    return im.rotate(deg, resample=Image.BICUBIC, expand=False)


def bounce(t, period=0.5, height=60.0, amt=0.14, contact=0.12, stretch=0.06):
    """Mascot hop. Returns (dy, sx, sy): dy <= 0 (up is negative, add to the floor y), and scale factors
    for xform(). Lands at every multiple of `period`: squash wide+short around contact (window `contact`
    of the period), then motion.squash() follow-through, a little stretch while moving fast in the air.
    Pivot the scale at the feet (place by the bottom edge) so the squash sits on the floor."""
    p = (t % period) / period
    dy = -height * 4 * p * (1 - p)
    d = min(p, 1 - p)                                  # distance to the nearest contact (period units)
    c = clamp(1 - d / contact) if contact > 0 else 0.0
    c = c * c * (3 - 2 * c)
    sx, sy = 1 + amt * c, 1 - amt * c
    speed = abs(1 - 2 * p)                             # 1 at take-off/landing, 0 at apex
    if c == 0:
        sy *= 1 + stretch * speed; sx *= 1 - stretch * speed * 0.5
    fx, fy = squash(t % period, amt=amt * 0.25, freq=18, damp=9)
    return dy, sx * fy, sy * fx


__all__ = ['PALETTES', 'NEGATIVE', 'hex_rgb', 'hex_bgr', 'asset_prompt', 'line_boil', 'flat_bg', 'DOODLE_FINISH',
           'make_doodle_finish', 'speed_lines', 'impact_burst', 'text_layer', 'pop_text', 'wheel_spin', 'bounce']
