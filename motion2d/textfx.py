"""Title / label text motion presets for the 2D (PIL + numpy) pipelines: the same names as the three.js template's
look.title_motion (docs/TEXT_STYLES.md), so a 2D video and a 3D video can share one look sheet.

    from textfx import text_fx, settle_time, PRESETS
    layer = text_fx('mask-wipe', 'Adams clasp', t, size=120, palette=['#0f1b2d', '#ffd166', '#d8dee6', '#ef6f6c'])
    paste(frame, layer, 540, 600)            # motion.paste: centre-anchored RGBA onto a BGR float frame

text_fx() returns a PIL RGBA layer of a FIXED size for a given (text, size, font) at any t, so it can be pasted by
its centre without jumping. t is seconds since the text's entrance started (t < 0 -> empty layer). After
settle_time(preset, text) the layer is static and fully legible. '\\n' in text makes several lines.

Presets: card-rise (cream card rises with overshoot; the template / braces-tutorial look, do not default to it),
slam-squash, typewriter, mask-wipe, letter-bounce, slide-stack, marker-sweep, draw-on (raster clip reveal of the
outline, then the fill floods in; never SVG), slow-fade.
Colours: palette (3-5 hex, darkest = outline, lightest = fill, most saturated = accent) or colors={'fill','stroke',
'accent','card','ink'}. Font: font_path or Fredoka Bold / Baloo 2 (doodle._font).  Credit: Swapnil Agrawal (BDS intern).
"""
import colorsys, math
from PIL import Image, ImageDraw
from motion import back, ease, ease_out, clamp
from doodle import _font, hex_rgb

PRESETS = ('card-rise', 'slam-squash', 'typewriter', 'mask-wipe', 'letter-bounce', 'slide-stack', 'marker-sweep',
           'draw-on', 'slow-fade')
CPS = 18.0          # typewriter characters per second


# ---------------------------------------------------------------- colours
def roles(palette=None, colors=None):
    pal = palette or ['#111418', '#F5F3EE', '#FF7A45']
    rgb = lambda h: [c / 255 for c in hex_rgb(h)]
    lum = lambda h: sum(c * k for c, k in zip(rgb(h), (.2126, .7152, .0722)))
    sat = lambda h: colorsys.rgb_to_hsv(*rgb(h))[1] * (0.4 + colorsys.rgb_to_hsv(*rgb(h))[2])
    dark, light = min(pal, key=lum), max(pal, key=lum)
    rest = sorted([p for p in pal if p not in (dark, light)], key=sat, reverse=True)
    if lum(dark) > 0.35: dark = '#111418'
    if lum(light) < 0.55: light = '#F5F3EE'
    R = dict(fill=light, stroke=dark, accent=rest[0] if rest else light, card=light, ink=dark)
    R.update(colors or {})
    return {k: (hex_rgb(v) + (255,)) if isinstance(v, str) else tuple(v) for k, v in R.items()}


# ---------------------------------------------------------------- layout
class _Layout:
    def __init__(self, text, size, font_path, align, stroke_px):
        self.f = _font(font_path, size); self.size = size
        self.lines = text.split('\n') or ['']
        self.sp = max(2, size // 14) if stroke_px is None else stroke_px
        asc, desc = self.f.getmetrics(); self.asc = asc
        self.lh = int((asc + desc) * 1.08)
        self.lw = [int(math.ceil(self.f.getlength(l))) for l in self.lines]
        mw, th = max(self.lw + [1]), self.lh * len(self.lines)
        self.m = int(size * 0.7) + self.sp
        self.W = int(mw * 1.6) + 2 * self.m; self.H = int(th * 1.6) + 2 * self.m
        self.y0 = (self.H - th) // 2
        self.x = [(self.W - w) // 2 if align == 'center' else (self.W - mw) // 2 for w in self.lw]
        self.block = ((self.W - mw) // 2, self.y0, (self.W + mw) // 2, self.y0 + th)

    def baseline(self, i): return self.y0 + i * self.lh + self.asc

    def char_x(self, i, k, track=0.0): return self.x[i] + self.f.getlength(self.lines[i][:k]) + k * track


def _draw_line(d, L, i, xy_off, fill, stroke, upto=None, track=0.0, sp=None):
    line = L.lines[i] if upto is None else L.lines[i][:upto]
    sp = L.sp if sp is None else sp
    x, y = L.x[i] + xy_off[0], L.baseline(i) + xy_off[1]
    if not track:
        d.text((x, y), line, font=L.f, fill=fill, stroke_width=sp, stroke_fill=stroke, anchor='ls'); return
    for k, ch in enumerate(line):
        d.text((L.char_x(i, k, track) + xy_off[0], y), ch, font=L.f, fill=fill, stroke_width=sp, stroke_fill=stroke, anchor='ls')


def _block(L, R, fill=None, stroke=None, sp=None):
    im = Image.new('RGBA', (L.W, L.H), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    for i in range(len(L.lines)): _draw_line(d, L, i, (0, 0), fill or R['fill'], stroke or R['stroke'], sp=sp)
    return im


def _alpha(im, a):
    if a >= 1: return im
    r, g, b, al = im.split(); al = al.point(lambda v: int(v * max(0.0, a))); return Image.merge('RGBA', (r, g, b, al))


def _scaled(im, sx, sy, W, H):
    if abs(sx - 1) < 1e-4 and abs(sy - 1) < 1e-4: return im
    w, h = max(1, int(im.width * sx)), max(1, int(im.height * sy))
    s = im.resize((w, h), Image.LANCZOS); out = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    out.alpha_composite(s.crop((max(0, (w - W) // 2), max(0, (h - H) // 2), max(0, (w - W) // 2) + min(w, W),
                                max(0, (h - H) // 2) + min(h, H))), (max(0, (W - w) // 2), max(0, (H - h) // 2)))
    return out


def _clip_x(im, x_right, soft=10):
    """keep columns left of x_right (soft edge): raster clip reveal"""
    W = im.width; r, g, b, a = im.split()
    ramp = Image.new('L', (W, 1)); ramp.putdata([int(255 * clamp((x_right - x) / max(1, soft) + 0.5)) for x in range(W)])
    m = ramp.resize((W, im.height))
    a = Image.composite(a, Image.new('L', a.size, 0), m)
    return Image.merge('RGBA', (r, g, b, a))


def _nchars(text): return len(text.replace('\n', ''))


def settle_time(preset, text):
    """seconds after which text_fx(preset, text, t) no longer changes"""
    n, nl = _nchars(text), len(text.split('\n'))
    return {'card-rise': 0.95, 'slam-squash': 1.45, 'typewriter': (n + nl - 1) / CPS + 0.85, 'mask-wipe': 0.7,
            'letter-bounce': n * 0.035 + 0.5, 'slide-stack': nl * 0.16 + 0.55, 'marker-sweep': nl * 0.12 + 0.6,
            'draw-on': 0.95, 'slow-fade': 1.35}[preset]


# ---------------------------------------------------------------- the presets
def text_fx(preset, text, t, size=120, palette=None, font_path=None, colors=None, align='center', stroke_px=None):
    if preset not in PRESETS: raise ValueError(f'unknown text preset {preset!r}; use one of {PRESETS} (docs/TEXT_STYLES.md)')
    L = _Layout(text, size, font_path, align, stroke_px); R = roles(palette, colors)
    out = Image.new('RGBA', (L.W, L.H), (0, 0, 0, 0))
    if t < 0: return out
    t = min(t, settle_time(preset, text) + 0.001)          # static after settling (exactly)
    d = ImageDraw.Draw(out)
    bx0, by0, bx1, by1 = L.block

    if preset == 'card-rise':
        k = back(clamp(t / 0.9)); a = clamp(t / 0.5); dy = int((1 - k) * size * 0.5)
        lay = Image.new('RGBA', (L.W, L.H), (0, 0, 0, 0)); dl = ImageDraw.Draw(lay); pad = int(size * 0.35)
        dl.rounded_rectangle((bx0 - pad, by0 - pad // 2 + dy, bx1 + pad, by1 + pad // 2 + dy), radius=int(size * 0.3), fill=R['card'])
        for i in range(len(L.lines)): _draw_line(dl, L, i, (0, dy), R['ink'], R['ink'], sp=0)
        out = _alpha(lay, a)
    elif preset == 'slam-squash':
        if t < 0.22: sx = sy = 1.6 - 0.6 * (t / 0.22) ** 2; a = clamp(t / 0.06)
        else:
            e = t - 0.22; w = 0.14 * math.exp(-7 * e) * math.cos(22 * e) if e < 1.2 else 0.0
            sx, sy, a = 1 + w, 1 - w, 1.0
        out = _alpha(_scaled(_block(L, R), sx, sy, L.W, L.H), a)
    elif preset == 'typewriter':
        n = int(t * CPS); left = n; cur = None
        for i, line in enumerate(L.lines):
            k = max(0, min(len(line), left)); _draw_line(d, L, i, (0, 0), R['fill'], R['stroke'], upto=k)
            if 0 <= left <= len(line): cur = (i, k)
            left -= len(line) + 1
        tot = (_nchars(text) + len(L.lines) - 1) / CPS
        if cur and (t < tot or (t - tot < 0.75 and int(t * 3) % 2 == 0)):
            i, k = cur; x = L.char_x(i, k) + L.sp + 3; yb = L.baseline(i)
            d.rectangle((x, yb - L.asc * 0.85, x + max(3, size * 0.08), yb + size * 0.05), fill=R['accent'])
    elif preset == 'mask-wipe':
        a, b = ease(clamp(t / 0.32)), ease(clamp((t - 0.32) / 0.32))
        x0, wb = bx0 - 8, (bx1 - bx0) + 16; l, r = x0 + wb * b, x0 + wb * a
        if b > 0: out = _clip_x(_block(L, R), l, soft=2); d = ImageDraw.Draw(out)
        if r > l + 0.5: d.rectangle((l, by0 - size * 0.08, r, by1 + size * 0.08), fill=R['accent'])
    elif preset == 'letter-bounce':
        idx = 0
        for i, line in enumerate(L.lines):
            for k, ch in enumerate(line):
                p = (t - idx * 0.035) / 0.45; idx += 1
                if p <= 0: continue
                lay = Image.new('RGBA', (L.W, L.H), (0, 0, 0, 0)); dy = -(1 - back(p)) * size * 1.2
                ImageDraw.Draw(lay).text((L.char_x(i, k), L.baseline(i) + dy), ch, font=L.f, fill=R['fill'],
                                         stroke_width=L.sp, stroke_fill=R['stroke'], anchor='ls')
                out.alpha_composite(_alpha(lay, clamp(p * 4)))
    elif preset == 'slide-stack':
        for i in range(len(L.lines)):
            p = ease_out(clamp((t - i * 0.16) / 0.5))
            if p <= 0: continue
            lay = Image.new('RGBA', (L.W, L.H), (0, 0, 0, 0)); dx = int((1 if i % 2 else -1) * (1 - p) * size * 1.4)
            _draw_line(ImageDraw.Draw(lay), L, i, (dx, 0), R['fill'], R['stroke'])
            out.alpha_composite(_alpha(lay, clamp(p * 1.6)))
    elif preset == 'marker-sweep':
        for i in range(len(L.lines)):
            p = ease(clamp((t - i * 0.12) / 0.55)); yb = L.baseline(i); top, bot = yb - L.asc * 0.78, yb + size * 0.14
            x0 = L.x[i] - size * 0.12; ww = (L.lw[i] + size * 0.24) * p
            if ww > 1:
                d.polygon([(x0, bot), (x0 + 4, top + 3), (x0 + ww + 6, top), (x0 + ww, bot + 3)], fill=R['accent'][:3] + (230,))
        txt = Image.new('RGBA', (L.W, L.H), (0, 0, 0, 0)); dt = ImageDraw.Draw(txt)
        for i in range(len(L.lines)): _draw_line(dt, L, i, (0, 0), R['ink'], R['fill'], sp=max(1, L.sp // 3))
        out.alpha_composite(_alpha(txt, clamp(t / 0.15)))
    elif preset == 'draw-on':
        p, q = ease(clamp(t / 0.7)), clamp((t - 0.55) / 0.35)
        ol = Image.new('RGBA', (L.W, L.H), (0, 0, 0, 0)); do = ImageDraw.Draw(ol); sp = max(2, L.sp)
        for i in range(len(L.lines)): _draw_line(do, L, i, (0, 0), (0, 0, 0, 0), R['accent'], sp=sp)
        out = _clip_x(ol, bx0 - 10 + (bx1 - bx0 + 20) * p, soft=14) if p < 1 else ol
        if q > 0: out.alpha_composite(_alpha(_block(L, R, stroke=R['accent'], sp=sp), q))
    elif preset == 'slow-fade':
        p = clamp(t / 1.3); track = (1 - ease_out(p)) * size * 0.25 if p < 1 else 0.0
        lay = Image.new('RGBA', (L.W, L.H), (0, 0, 0, 0)); dl = ImageDraw.Draw(lay)
        for i in range(len(L.lines)):
            off = -track * (len(L.lines[i]) - 1) / 2 if align == 'center' else 0
            _draw_line(dl, L, i, (off, 0), R['fill'], R['stroke'], track=track)
        out = _alpha(lay, ease(p))
    return out


def render_onto(frame, preset, text, t, centre, **kw):
    """text_fx + motion.paste (centre-anchored) onto a BGR frame; returns frame"""
    from motion import paste
    paste(frame, text_fx(preset, text, t, **kw), centre[0], centre[1])
    return frame
