"""ZIPZOOM truck sting: a fully procedural 6 s 9:16 hand-drawn logo/mascot reel (no image generation).

A cute delivery truck putters in on the beat, brakes with a lean and a dust cloud, hops in place with its
wheels spinning, a "COOL!" bubble pops, the ZIPZOOM title slams in, an ink underline draws itself on and a
tagline pops. Finished frame by frame with motion2d/handdrawn.py: on twos (ones for the slam), per-drawing
line boil, a re-inked wobbly outline, marker/crayon texture fills, paper grain, smears on the fast entry.
Music and SFX are synthesised here (numpy) and mastered to -14 LUFS, true peak <= -1.5 dBTP before AAC.

    python3 examples/truck-sting/render.py                 # -> examples/truck-sting/zipzoom_sting.mp4
    python3 examples/truck-sting/render.py --sheet --gif   # + contact_sheet.jpg, onion.png, docs/img/truck-sting.gif

Why the truck is drawn in code here: this example is a self-contained proof of the hand-drawn finish that runs
with no image model. For a real client job the mascot is generated raster art (docs/MOTION_DOODLE.md asset rules)
and goes through the same finish. Brand "ZIPZOOM" and the truck design are original. Raster only, never SVG.
Credit: Swapnil Agrawal (BDS intern).
"""
import argparse, json, math, os, subprocess, sys, time, wave
import numpy as np, cv2
from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
sys.path.insert(0, os.path.join(ROOT, 'motion2d'))
from motion import back, ease_out, ease, clamp, squash, xform, paste           # noqa: E402
from doodle import text_layer, speed_lines, impact_burst                         # noqa: E402
from loop import Beat                                                            # noqa: E402
import handdrawn as hd                                                           # noqa: E402

W, H, FPS, SECS = 1080, 1920, 24, 6.0
N = int(SECS * FPS)
BPM = 120
B = Beat(BPM)

# ---------------------------------------------------------------- look sheet (fresh palette, not lilac)
PAL = dict(plate='#FF8F45',      # tangerine paper
           ground='#EE7433',     # crayon ground below the horizon
           cream='#FFF3D6',      # cargo box, title, puffs
           cobalt='#2D5BD3',     # cab, stripe, title shadow
           sun='#FFC93C',        # bolt, hub, headlight
           coral='#FF5A5F',      # emblem badge, cheeks
           sky='#CDEBFF',        # window
           ink='#1A1423',        # outlines and type stroke
           steel='#6C6A7A', chassis='#3A3445', tire='#2A2433', tread='#4A4258')
GROUND_Y = 1480
TITLE = 'ZIPZOOM'
TAGLINE = 'DELIVERED IN A ZIP!'


def rgb(h): h = h.lstrip('#'); return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


# ---------------------------------------------------------------- procedural assets (flat fills, 2x supersampled)
SS = 2


def _canvas(w, h): return Image.new('RGBA', (w * SS, h * SS), (0, 0, 0, 0))


K = 1.18                                  # draw in design px, ship at K x (bigger truck in the 9:16 frame)


def _down(im, k=1.0): return im.resize((round(im.width / SS * k), round(im.height / SS * k)), Image.LANCZOS)


def S(*v): return [x * SS for x in v]


BODY_W, BODY_H = 800, 480                 # design px (before K)
ORIGIN = (388, 474)                       # ground point between the wheels, in body px
WHEELS = [(165, 392), (610, 392)]
WHEEL_R = 82
SW, SH, SO = BODY_W * K, BODY_H * K, (ORIGIN[0] * K, ORIGIN[1] * K)      # shipped sizes
SWHEELS = [(x * K, y * K) for x, y in WHEELS]
SWHEEL_R = WHEEL_R * K


def draw_body():
    """truck body WITHOUT wheels, flat fills only (the outline is added per drawing by wobble_outline)"""
    im = _canvas(BODY_W, BODY_H); d = ImageDraw.Draw(im)
    for cx, cy in WHEELS:                                                   # wheel wells
        d.pieslice(S(cx - 96, cy - 96, cx + 96, cy + 96), 180, 360, fill=rgb(PAL['chassis']))
    d.rounded_rectangle(S(40, 368, 760, 404), radius=16 * SS, fill=rgb(PAL['chassis']))
    d.rectangle(S(4, 352, 36, 372), fill=rgb(PAL['steel']))                # exhaust
    d.rounded_rectangle(S(24, 40, 482, 382), radius=34 * SS, fill=rgb(PAL['cream']))      # cargo box
    d.rectangle(S(24, 262, 482, 300), fill=rgb(PAL['cobalt']))
    d.ellipse(S(253 - 64, 150 - 64, 253 + 64, 150 + 64), fill=rgb(PAL['coral']))        # emblem badge
    bolt = [(266, 92), (222, 160), (252, 160), (236, 212), (288, 136), (257, 136), (276, 92)]
    d.polygon([(x * SS, y * SS) for x, y in bolt], fill=rgb(PAL['sun']))
    d.rounded_rectangle(S(600, 124, 644, 146), radius=8 * SS, fill=rgb(PAL['sun']))       # roof light
    d.rounded_rectangle(S(470, 140, 775, 382), radius=46 * SS, fill=rgb(PAL['cobalt']))   # cab
    d.rounded_rectangle(S(556, 168, 748, 262), radius=24 * SS, fill=rgb(PAL['sky']))      # window
    for ex in (618, 694):                                                   # eyes look ahead (right)
        d.ellipse(S(ex - 15, 192, ex + 15, 240), fill=rgb(PAL['ink']))
        d.ellipse(S(ex - 2, 198, ex + 9, 210), fill=(255, 255, 255))
    for cx in (600, 726):
        d.ellipse(S(cx - 18, 280, cx + 18, 298), fill=rgb(PAL['coral']))  # cheeks
    d.arc(S(628, 262, 692, 312), 20, 160, fill=rgb(PAL['ink']), width=7 * SS)            # smile
    d.rounded_rectangle(S(492, 268, 524, 280), radius=5 * SS, fill=rgb(PAL['chassis']))  # door handle
    d.ellipse(S(740, 318, 768, 346), fill=rgb(PAL['sun']))                  # headlight
    d.rounded_rectangle(S(700, 360, 792, 394), radius=14 * SS, fill=rgb(PAL['steel']))   # bumper
    return _down(im, K)


def draw_wheel():
    s = 200; im = _canvas(s, s); d = ImageDraw.Draw(im); c = s / 2
    def circ(r, col): d.ellipse(S(c - r, c - r, c + r, c + r), fill=rgb(col))
    circ(WHEEL_R, PAL['tire'])
    for k in range(10):                                                     # tread marks show the spin
        a = 2 * math.pi * k / 10
        x, y = c + math.cos(a) * 70, c + math.sin(a) * 70
        d.ellipse(S(x - 6, y - 6, x + 6, y + 6), fill=rgb(PAL['tread']))
    circ(52, PAL['cream'])
    for k in range(5):
        a = 2 * math.pi * k / 5
        x, y = c + math.cos(a) * 34, c + math.sin(a) * 34
        d.ellipse(S(x - 8, y - 8, x + 8, y + 8), fill=rgb(PAL['cobalt']))
    circ(19, PAL['sun'])
    return _down(im, K)


def draw_bubble():
    w, h = 470, 330; im = _canvas(w, h); d = ImageDraw.Draw(im)
    d.polygon([(300 * SS, 220 * SS), (420 * SS, 318 * SS), (360 * SS, 200 * SS)], fill=(255, 255, 255))   # tail
    d.ellipse(S(20, 20, 450, 250), fill=(255, 255, 255))
    im = _down(im)
    txt = text_layer('COOL!', None, size=118, fill=PAL['cobalt'], stroke=PAL['ink'], stroke_px=9)
    txt = xform(txt, 1, 1, 4)
    im.alpha_composite(txt, (235 - txt.width // 2, 136 - txt.height // 2))
    return im


def draw_underline():
    """ink line art for the draw-on: a hand-drawn swoosh + two little sparkle crosses"""
    w, h = 760, 150; im = _canvas(w, h); d = ImageDraw.Draw(im)
    pts = []
    for i in range(61):
        u = i / 60; x = 40 + u * 600
        y = 70 + 14 * math.sin(u * math.pi * 2.2) - 18 * u
        pts.append((x * SS, y * SS))
    d.line(pts, fill=rgb(PAL['ink']), width=13 * SS, joint='curve')
    for cx, cy, r in ((690, 52, 26), (720, 112, 16)):
        d.line(S(cx - r, cy, cx + r, cy), fill=rgb(PAL['ink']), width=9 * SS)
        d.line(S(cx, cy - r, cx, cy + r), fill=rgb(PAL['ink']), width=9 * SS)
    return _down(im)


def draw_puff(seed, r=60):
    rs = np.random.RandomState(seed); s = int(r * 3.2); im = _canvas(s, s); d = ImageDraw.Draw(im)
    for k in range(4):
        a = rs.uniform(0, 2 * math.pi); rr = r * rs.uniform(0.5, 0.85); o = r * 0.55
        cx, cy = s / 2 + math.cos(a) * o * (k > 0), s / 2 + math.sin(a) * o * 0.6 * (k > 0)
        d.ellipse(S(cx - rr, cy - rr, cx + rr, cy + rr), fill=rgb(PAL['cream']))
    return _down(im)


def ground_layer():
    """crayon ground below a hand-drawn horizon line (static art; it boils per drawing)"""
    h = H - GROUND_Y + 40
    m = np.zeros((h, W), np.float32); m[30:] = 1
    g = hd.texture_fill(m, PAL['ground'], 'crayon', seed=4, angle=-8)
    d = ImageDraw.Draw(g)
    pts = [(x, 30 + 3 * math.sin(x / 90) + 2 * math.sin(x / 23)) for x in range(-10, W + 20, 10)]
    d.line(pts, fill=rgb(PAL['ink']), width=8, joint='curve')
    for x0, L in ((120, 90), (420, 60), (760, 120), (930, 50)):          # little ground dashes
        d.line([(x0, 80 + x0 % 37), (x0 + L, 80 + x0 % 37)], fill=rgb(PAL['ink']), width=6)
    return g


def title_layer():
    t = text_layer(TITLE, None, size=200, fill=PAL['cream'], stroke=PAL['ink'], stroke_px=14)
    t = hd.texturize(t, 'marker', strength=0.9, seed=2, angle=-6)
    sh = Image.new('RGBA', t.size, rgb(PAL['cobalt']) + (0,)); sh.putalpha(t.getchannel('A'))
    out = Image.new('RGBA', (t.width + 18, t.height + 18), (0, 0, 0, 0))
    out.alpha_composite(sh, (16, 16)); out.alpha_composite(t, (0, 0))
    return out


def tagline_layer():
    t = text_layer(TAGLINE, None, size=88, fill=PAL['cream'], stroke=PAL['ink'], stroke_px=8)
    return hd.texturize(t, 'marker', strength=0.7, seed=5, angle=4)


# ---------------------------------------------------------------- choreography (times in s, beats at 120 bpm)
T_STOP = 1.5            # beat 3: brakes
T_BUBBLE = 2.0          # beat 4
T_WHOOSH = 2.78
T_TITLE = 3.0           # beat 6, slam
T_LINE = (3.45, 4.15)   # underline draw-on
T_TAG = 4.0             # beat 8
T_ACCENT = 5.0          # beat 10: big hop
X_START, X_END = -140.0, 540.0

HOLDS = hd.Holds([(0, 2), (2.92, 1), (3.25, 2)], FPS)   # on twos, ones for the slam


def truck_x(t):
    if t >= T_STOP: return X_END
    return X_START + (X_END - X_START) * ease_out(t / T_STOP)


def truck_pose(t):
    """(x, hop_dy, sx, sy, rot) of the truck origin"""
    x = truck_x(t)
    if t < T_STOP:
        p = (t % 0.5) / 0.5; dy = -38 * 4 * p * (1 - p)
        c = clamp(1 - min(p, 1 - p) / 0.14); c = c * c * (3 - 2 * c)
        sx, sy = 1 + 0.08 * c, 1 - 0.08 * c; rot = 1.8 * math.sin(t * 9)
    else:
        u = t - T_STOP
        rot = -6 * math.exp(-u * 5) * math.cos(u * 15)                         # nose dips, rocks back
        height = 52 if B.beat_at(t) >= 10 and B.beat_at(t) < 11 else 24          # bigger accent hop on beat 10
        start_hop = u > 0.5
        p = (t % 0.5) / 0.5
        dy = -height * 4 * p * (1 - p) if start_hop else 0.0
        c = clamp(1 - min(p, 1 - p) / 0.16) if start_hop else 0.0; c = c * c * (3 - 2 * c)
        fx, fy = squash(u, amt=0.10, freq=16, damp=6)
        sx, sy = (1 + 0.11 * c) * fy, (1 - 0.11 * c) * fx
    return x, dy, sx, sy, rot


def truck_speed(t):
    dt = 1 / FPS
    return (truck_x(t + dt) - truck_x(t)) / dt


def wheel_angle(t):
    """integrated rolling angle (deg): rolling without skid while driving, 70 rpm spin when hopping in place"""
    if t <= T_STOP:
        return -(truck_x(t) - X_START) / (2 * math.pi * SWHEEL_R) * 360
    a0 = -(X_END - X_START) / (2 * math.pi * SWHEEL_R) * 360
    return a0 - 360 * 70 / 60 * (t - T_STOP)


PUFFS = []                                                                  # (t0, x, y, vx, vy, r, seed)
for k, t0 in enumerate(np.arange(0.0, T_STOP - 0.1, 0.25)):                 # trail from the back wheel
    x = truck_x(t0) + (WHEELS[0][0] - ORIGIN[0]) * K - 50
    PUFFS.append((t0, x, GROUND_Y - 30, -90, -60, 34 + 6 * (k % 2), 100 + k))
for k, (dx, vx) in enumerate(((180, 160), (250, 260), (120, 60))):         # brake cloud at the front wheel
    PUFFS.append((T_STOP + 0.02 * k, X_END + dx, GROUND_Y - 34, vx, -50 - 30 * k, 58 - 8 * k, 200 + k))
for k, t0 in enumerate((2.5, 3.5, 4.5, 5.5)):                               # exhaust putts on beats
    PUFFS.append((t0, X_END - 380 * K, GROUND_Y - 112 * K, -140, -70, 28, 300 + k))
PUFF_LIFE = 0.62

# sound cues (t, name) - built from the same choreography so picture and sound line up
CUES = [(T_STOP - 0.06, 'squeak'), (T_STOP, 'boing'), (T_BUBBLE, 'pop'), (T_WHOOSH, 'whoosh'), (T_TITLE, 'slam'),
        (T_LINE[0], 'scribble'), (T_TAG, 'pop2'), (T_ACCENT, 'boing2')] + \
       [(t0, 'putt') for t0 in (2.5, 3.5, 4.5, 5.5)]


# ---------------------------------------------------------------- render
class Assets:
    def __init__(self):
        body = draw_body(); wheel = draw_wheel()
        self.body, self.wheel = body, wheel                     # flat; outlined, then textured per drawing
        self.cloud = [xform(draw_puff(400 + i, 80), 1.5, 0.85) for i in range(2)]
        self.bubble = hd.texturize(draw_bubble(), 'marker', strength=0.5, seed=9)
        self.puffs = {}
        self.ground = ground_layer()
        self.title = title_layer(); self.tag = tagline_layer()
        self.line = hd.InkDrawOn(draw_underline(), order='ltr')
        self.plate = hd.paper(W, H, PAL['plate'], seed=1, tooth=1.4, fibre=1.2, mottle=1.0)

    def puff(self, seed, r):
        if (seed, r) not in self.puffs: self.puffs[(seed, r)] = draw_puff(seed, r)
        return self.puffs[(seed, r)]


def _rot(vx, vy, deg):
    a = math.radians(-deg); return vx * math.cos(a) - vy * math.sin(a), vx * math.sin(a) + vy * math.cos(a)


def render_truck(A, t, d):
    """truck layer (PIL RGBA on a local canvas) + the screen point its origin goes to"""
    x, dy, sx, sy, rot = truck_pose(t)
    CW, CH = 1200, 860; ox, oy = CW / 2, CH - 170
    lay = Image.new('RGBA', (CW, CH), (0, 0, 0, 0))
    body = xform(A.body, sx, sy, rot)
    body = hd.wobble_outline(body, d, width=8, var=0.5, wobble=1.3, color=PAL['ink'], seed=1)
    body = hd.texturize(body, 'marker', strength=0.6, seed=1, angle=-4, drawing=d % 3)   # 3 coloured redraws
    bx, by = _rot((SW / 2 - SO[0]) * sx, (SH / 2 - SO[1]) * sy, rot)
    lay.alpha_composite(body, (int(ox + bx - body.width / 2), int(oy + by - body.height / 2)))
    ang = wheel_angle(t)
    spin = abs(wheel_angle(t + 2 / FPS) - ang) * 0.6                      # deg turned during the exposure
    for i, (wx, wy) in enumerate(SWHEELS):
        wim = A.wheel.rotate(ang + 31 * i, resample=Image.BICUBIC)
        wim = hd.spin_smear(wim, spin)
        wim = xform(wim, sx, sy, 0)
        wim = hd.wobble_outline(wim, d, width=7, var=0.4, wobble=1.0, color=PAL['ink'], inner=False, seed=2 + i)
        wim = hd.texturize(wim, 'crayon', strength=0.5, seed=3 + i, drawing=d % 3)
        vx, vy = (wx - SO[0]) * sx, (wy - SO[1]) * sy          # wheels stay on the road; only the body pitches
        lay.alpha_composite(wim, (int(ox + vx - wim.width / 2), int(oy + vy - wim.height / 2)))
    v = truck_speed(t) * 2 / FPS                                            # px moved per drawing (on twos)
    k = hd.smear_amount(v, 0, threshold=60, full=140)
    if k > 0:
        lay = hd.smear(lay, v * 0.9, 0, kind='stretch', strength=k)
        ox += (lay.width - CW) / 2; oy += (lay.height - CH) / 2
    lay = hd.boil(lay, d, amp=1.3, scale=30, seed=11)
    return lay, (x - ox + lay.width / 2, GROUND_Y + dy - oy + lay.height / 2), (x, dy)


def render_drawing(A, t, d):
    fr = A.plate.copy()
    paste(fr, hd.boil(A.ground, d, amp=1.0, seed=3), W / 2, GROUND_Y - 30 + A.ground.height / 2)
    for i, (cx0, cy0, sp) in enumerate(((250, 250, 14), (950, 720, -6))):   # slow clouds fill the sky
        c = hd.wobble_outline(A.cloud[i], d, width=6, var=0.5, color=PAL['ink'], inner=False, seed=61 + i)
        c = hd.texturize(c, 'chalk', strength=0.5, seed=60 + i, drawing=d % 2)
        paste(fr, hd.boil(c, d, amp=1.0, seed=62 + i), cx0 + sp * t, cy0 + 6 * math.sin(t * 2 + i))
    x, dy, sx, sy, rot = truck_pose(t)
    # contact shadow (shrinks while airborne)
    sw = 390 * (1 + dy / 260); sh = 24 * (1 + dy / 260)
    cv2.ellipse(fr, (int(x + 6), GROUND_Y + 4), (int(sw), int(max(6, sh))), 0, 0, 360,
                tuple(c * 0.82 for c in rgb(PAL['ground'])[::-1]), -1, cv2.LINE_AA)
    # puffs behind the truck
    for (t0, px, py, vx, vy, r, seed) in PUFFS:
        u = (t - t0) / PUFF_LIFE
        if not 0 <= u < 1: continue
        s = (0.35 + 0.75 * ease_out(min(1, u * 2.2))) * (1 - ease(max(0, (u - 0.6) / 0.4)) * 0.9)
        im = xform(A.puff(seed, r), s, s, 30 * u)
        im = hd.wobble_outline(im, d, width=5, var=0.5, wobble=1.0, color=PAL['ink'], inner=False, seed=seed)
        im = hd.texturize(im, 'crayon', strength=0.7, seed=seed, drawing=d)
        paste(fr, im, px + vx * u * PUFF_LIFE, py + vy * u * PUFF_LIFE)
    if t < T_STOP - 0.15:
        speed_lines(fr, (x - 500, GROUND_Y - 260), 0, t, n=4, length=170, spread=240, thick=7,
                    color=tuple(rgb(PAL['ink'])[::-1]), seed=3)
    lay, (cx, cy), _ = render_truck(A, t, d)
    paste(fr, lay, cx, cy)
    # speech bubble
    if t >= T_BUBBLE:
        u = t - T_BUBBLE
        if u < 0.25: s = max(0.05, 0.1 + 0.9 * back(u / 0.25, 2.4)); bsx = bsy = s
        else:
            bp = B.pulse(t, decay=10); bsx, bsy = 1 + 0.05 * bp, 1 - 0.05 * bp
        bub = xform(A.bubble, bsx, bsy, -3 + 2 * math.sin(t * 3))
        bub = hd.wobble_outline(bub, d, width=7, var=0.5, wobble=1.2, color=PAL['ink'], inner=False, seed=21)
        paste(fr, hd.boil(bub, d, amp=1.2, seed=22), 480, 800 + dy * 0.35)
        impact_burst(fr, (480, 800), u - 0.12, color=tuple(rgb(PAL['ink'])[::-1]), r0=250, r1=330, thick=7, aspect=0.75)
    # title slam
    shake = (0, 0)
    if t >= T_TITLE - 0.12:
        u = t - T_TITLE
        if u < 0:
            s = 1.9; al = clamp((u + 0.12) / 0.12)
            sx_, sy_ = s, s
        elif u < 0.0001:
            sx_, sy_, al = 1.25, 0.8, 1
        else:
            fx, fy = squash(u, amt=0.16, freq=20, damp=7); sx_, sy_, al = fx, fy, 1
        tl = xform(A.title, sx_, sy_, -4)
        if al < 1: tl.putalpha(Image.fromarray((np.array(tl)[..., 3] * al).astype(np.uint8)))
        if u < 0:
            tl = hd.smear(tl, 0, 90 * al, kind='multiples')
        paste(fr, hd.boil(tl, d, amp=1.0, seed=31), W / 2, 400)
        if u >= 0:
            impact_burst(fr, (W / 2, 400), u, color=tuple(rgb(PAL['ink'])[::-1]), n=12, r0=440, r1=560, thick=9,
                         aspect=0.45, dur=0.3)
            if u < 0.2: shake = (int(14 * math.sin(u * 90) * (1 - u / 0.2)), int(10 * math.cos(u * 70) * (1 - u / 0.2)))
    # underline draw-on
    if t >= T_LINE[0]:
        p = clamp((t - T_LINE[0]) / (T_LINE[1] - T_LINE[0]))
        ul = A.line.frame(ease(p))
        paste(fr, hd.boil(ul, d, amp=1.0, seed=41), W / 2 + 10, 560)
    # tagline
    if t >= T_TAG:
        u = t - T_TAG
        if u < 0.22: s = max(0.05, 0.2 + 0.8 * back(u / 0.22, 2.2)); tsx = tsy = s
        else: tsx, tsy = squash(u - 0.22, amt=0.08, freq=18, damp=7)
        tg = xform(A.tag, tsx, tsy, 2)
        paste(fr, hd.boil(tg, d, amp=1.0, seed=51), W / 2, 1700)
    if shake != (0, 0):
        M = np.float32([[1, 0, shake[0]], [0, 1, shake[1]]])
        fr = cv2.warpAffine(fr, M, (W, H), borderMode=cv2.BORDER_REFLECT)
    return hd.grain(fr, d, strength=1.0, variants=2, seed=5, tooth=1.2, fibre=0.5, mottle=0.3)


def render_video(path, sheet=None, onion=None):
    A = Assets(); t0 = time.time()
    tmp = path + '.v.mp4'
    pr = subprocess.Popen(['ffmpeg', '-y', '-loglevel', 'error', '-f', 'rawvideo', '-pix_fmt', 'bgr24', '-s', f'{W}x{H}',
                           '-r', str(FPS), '-i', '-', '-c:v', 'libx264', '-preset', 'medium', '-crf', '18',
                           '-pix_fmt', 'yuv420p', '-movflags', '+faststart', tmp], stdin=subprocess.PIPE)
    last_d, img, frames_keep, drawings = None, None, {}, 0
    keep = set(range(0, N, 12)) | set(range(int(0.25 * FPS), int(0.25 * FPS) + 6))
    for f in range(N):
        t_h, d = HOLDS(f / FPS)
        if d != last_d:
            img = render_drawing(A, t_h, d); last_d = d; drawings += 1
        pr.stdin.write(img.tobytes())
        if f in keep: frames_keep[f] = img
    pr.stdin.close(); pr.wait()
    dt = time.time() - t0
    print(f'[truck-sting] {N} frames, {drawings} drawings in {dt:.1f}s ({dt / drawings:.2f}s per drawing)')
    if sheet: contact_sheet([frames_keep[k] for k in sorted(k for k in frames_keep if k % 12 == 0)], sheet)
    if onion:
        seq = [frames_keep[k] for k in range(int(0.25 * FPS), int(0.25 * FPS) + 6)]
        cv2.imwrite(onion, cv2.resize(hd.onion_skin(seq, 2, before=1, after=1), (540, 960), interpolation=cv2.INTER_AREA))
    return tmp


def contact_sheet(frames, path, cols=4):
    th = [cv2.resize(f, (270, 480), interpolation=cv2.INTER_AREA) for f in frames]
    rows = math.ceil(len(th) / cols)
    sh = np.full((rows * 490 + 10, cols * 280 + 10, 3), 30, np.uint8)
    for i, im in enumerate(th):
        y, x = 10 + (i // cols) * 490, 10 + (i % cols) * 280
        sh[y:y + 480, x:x + 270] = im
        cv2.putText(sh, f'{i * 0.5:.1f}s', (x + 8, y + 28), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2, cv2.LINE_AA)
    cv2.imwrite(path, sh, [cv2.IMWRITE_JPEG_QUALITY, 88])


# ---------------------------------------------------------------- audio (all synthesised, 48 kHz)
SR = 48000


def _t(sec): return np.arange(int(sec * SR)) / SR


def _place(buf, x, t, g=1.0):
    i = int(round(t * SR))
    if i >= len(buf): return
    x = x[:len(buf) - i] if i >= 0 else x[-i:]
    i = max(0, i); buf[i:i + len(x)] += x * g


def _lp(x, cut):
    """one-pole low-pass"""
    a = math.exp(-2 * math.pi * cut / SR); y = np.empty_like(x); s = 0.0
    from scipy.signal import lfilter
    return lfilter([1 - a], [1, -a], x).astype(np.float32)


def _bp(x, lo, hi):
    from scipy.signal import butter, sosfilt
    return sosfilt(butter(2, [lo, hi], 'band', fs=SR, output='sos'), x).astype(np.float32)


RNG = np.random.default_rng(7)


def kick():
    t = _t(0.28); f = 48 + 110 * np.exp(-t * 32)
    return (np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 11) + 0.15 * np.sin(2 * np.pi * 3000 * t) * np.exp(-t * 300)).astype(np.float32)


def clap():
    t = _t(0.22); n = RNG.standard_normal(len(t)).astype(np.float32)
    env = np.exp(-t * 26) + 0.6 * np.exp(-((t - 0.012) % 0.011) * 400) * (t < 0.035)
    return _bp(n, 900, 5000) * env * 0.9


def hat(open_=False):
    t = _t(0.18 if open_ else 0.05); n = RNG.standard_normal(len(t)).astype(np.float32)
    return _bp(n, 6000, 15000) * np.exp(-t * (22 if open_ else 90)) * 0.5


def pluck(freq, dur=0.32, bright=1.0):
    t = _t(dur)
    x = np.sin(2 * np.pi * freq * t) + 0.45 * bright * np.sin(4 * np.pi * freq * t) * np.exp(-t * 18) \
        + 0.18 * bright * np.sin(6 * np.pi * freq * t) * np.exp(-t * 30)
    return (x * np.exp(-t * 9) * np.minimum(1, t * 400)).astype(np.float32)


def bass(freq, dur=0.45):
    t = _t(dur); x = np.sin(2 * np.pi * freq * t) + 0.3 * np.sin(4 * np.pi * freq * t)
    return (x * np.exp(-t * 4) * np.minimum(1, t * 300) * np.minimum(1, (dur - t) * 60)).astype(np.float32)


def nf(n): return 440.0 * 2 ** ((n - 69) / 12)


def music():
    buf = np.zeros(int(SECS * SR), np.float32)
    beat = 60 / BPM
    chords = [(48, [60, 64, 67, 72]), (53, [60, 65, 69, 72]), (55, [59, 62, 67, 71])]   # C | F | G (2 s bars)
    for b in range(12):
        tb = b * beat; bar = b // 4
        root, notes = chords[min(bar, 2)]
        _place(buf, kick(), tb, 0.9)
        if b % 2 == 1: _place(buf, clap(), tb, 0.45)
        _place(buf, hat(), tb + beat / 2, 0.35); _place(buf, hat(), tb, 0.18)
        _place(buf, bass(nf(root - 12 + (7 if b % 4 == 3 else 0))), tb, 0.55)
        for k in range(2):                                                    # bouncy 8th-note arpeggio
            n = notes[(b * 2 + k) % 4]
            _place(buf, pluck(nf(n + 12), 0.3), tb + k * beat / 2, 0.16)
    melody = [(2.0, 76), (2.25, 79), (2.5, 81), (3.0, 84), (3.25, 81), (3.5, 79), (4.0, 77), (4.5, 81), (5.0, 79)]
    for tm, n in melody: _place(buf, pluck(nf(n), 0.4, 1.4), tm, 0.2)
    for n in (72, 76, 79, 84):                                               # ending chord on beat 11
        _place(buf, pluck(nf(n), 0.7, 0.8), 5.5, 0.14)
    _place(buf, kick(), 5.5, 0.9)
    return buf


def sfx(name):
    if name == 'putt':                                                     # single exhaust putt
        t = _t(0.09); f = 70 * np.exp(-t * 8)
        return (np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 40) * 0.8
                + _lp(RNG.standard_normal(len(t)).astype(np.float32), 600) * np.exp(-t * 50) * 0.8)
    if name == 'squeak':
        t = _t(0.32); f = 1900 - 500 * t / 0.32 + 40 * np.sin(2 * np.pi * 28 * t)
        return np.sin(2 * np.pi * np.cumsum(f) / SR) * np.minimum(1, t * 60) * np.exp(-t * 6) * 0.22
    if name in ('boing', 'boing2'):
        t = _t(0.5); f = (180 if name == 'boing' else 240) + 140 * np.sin(t * 55) * np.exp(-t * 5)
        return np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 6) * 0.5
    if name in ('pop', 'pop2'):
        t = _t(0.14); f = (620 if name == 'pop' else 820) * np.exp(-t * 12) + 200
        return np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 32) * 0.6
    if name == 'whoosh':
        d = T_TITLE - T_WHOOSH + 0.06; t = _t(d); n = RNG.standard_normal(len(t)).astype(np.float32)
        env = (t / d) ** 2.2
        lo = _bp(n, 400, 2500); hi = _bp(n, 2500, 9000)
        return (lo * (1 - t / d) + hi * (t / d)) * env * 0.5
    if name == 'slam':
        t = _t(0.7); f = 42 + 90 * np.exp(-t * 18)
        body = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 6)
        crack = _bp(RNG.standard_normal(len(t)).astype(np.float32), 1500, 9000) * np.exp(-t * 14) * 0.6
        return (body + crack) * 0.8
    if name == 'scribble':                                                 # marker squeak-scratch for the draw-on
        d = T_LINE[1] - T_LINE[0]; t = _t(d); n = RNG.standard_normal(len(t)).astype(np.float32)
        am = 0.55 + 0.45 * np.sin(2 * np.pi * 9 * t) ** 2
        return _bp(n, 1800, 6000) * am * np.minimum(1, t * 30) * np.minimum(1, (d - t) * 20) * 0.22
    raise KeyError(name)


def engine_bed():
    """2-stroke putter while driving in: pulse rate follows the truck speed, then idles low"""
    buf = np.zeros(int(SECS * SR), np.float32); t = 0.0
    while t < T_STOP + 0.15:
        v = abs(truck_speed(min(t, T_STOP - 0.01)))
        rate = 11 + 16 * min(1, v / 1500)
        _place(buf, sfx('putt'), t, 0.55); t += 1 / rate
    while t < SECS - 0.4:
        _place(buf, sfx('putt'), t, 0.14); t += 1 / 8.0
    return buf


def ln_measure(path):
    out = subprocess.run(['ffmpeg', '-hide_banner', '-i', path, '-af', 'loudnorm=I=-14:TP=-1.5:LRA=11:print_format=json',
                          '-f', 'null', '-'], capture_output=True, text=True).stderr
    j = json.loads(out[out.rindex('{'):out.rindex('}') + 1])
    return float(j['input_i']), float(j['input_tp'])


def wav_write(path, x):
    with wave.open(path, 'wb') as w:
        w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR)
        st = np.stack([x, x], 1) if x.ndim == 1 else x
        w.writeframes((np.clip(st, -1, 1) * 32767).astype(np.int16).tobytes())


def build_audio(path):
    mus = music(); eng = engine_bed(); fx = np.zeros_like(mus)
    for t, name in CUES: _place(fx, sfx(name).astype(np.float32), t, 1.0)
    mix = mus * 0.8 + eng * 0.7 + fx * 1.0
    # gentle stereo: music plucks slightly wide via a 9 ms delay on the right side
    dl = int(0.009 * SR); right = mix.copy(); right[dl:] = mix[:-dl] * 0.35 + mix[dl:] * 0.65
    st = np.stack([mix, right], 1)
    fade = np.minimum(1, (SECS - _t(SECS)) / 0.25)[:, None]; st = st * fade
    raw = path + '.raw.wav'
    st = st / (np.abs(st).max() + 1e-9) * 0.5; wav_write(raw, st)
    # master: gain toward -14 LUFS behind a brickwall, measured like loudnorm, until I is on target and TP <= -1.5
    limit, gain, cur = 0.80, 1.0, raw
    for it in range(8):
        I, tp = ln_measure(cur)
        need = -14.0 - I
        if abs(need) <= 0.25 and tp <= -1.6: break
        gain *= 10 ** (need / 20)
        if tp + need > -1.6: limit *= 0.93
        nxt = path + f'.m{it}.wav'
        subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-i', raw, '-af',
                        f'volume={gain:.5f},alimiter=limit={limit:.4f}:attack=0.5:release=40:level=false,'
                        f'aresample=192000,alimiter=limit={limit:.4f}:attack=0.3:release=30:level=false,aresample={SR}',
                        '-ar', str(SR), '-c:a', 'pcm_s16le', nxt], check=True)
        if cur != raw: os.remove(cur)
        cur = nxt
    os.replace(cur, path); os.remove(raw)
    I, tp = ln_measure(path)
    print(f'[truck-sting] audio master: {I:.2f} LUFS, true peak {tp:.2f} dBTP (before AAC)')
    return I, tp


def mux(video, audio, out):
    subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-i', video, '-i', audio, '-map', '0:v', '-map', '1:a',
                    '-c:v', 'copy', '-c:a', 'aac', '-b:a', '192k', '-ar', str(SR), '-movflags', '+faststart',
                    '-t', f'{SECS:.3f}', out], check=True)


def make_gif(mp4, gif, width=360, fps=12):
    """README gif <= 2.5 MB: paper grain changes every drawing and kills GIF compression, so soften it
    (blur at full size + temporal denoise) and use a small undithered palette."""
    pal = gif + '.pal.png'
    vf = f'fps={fps},gblur=sigma=3,scale={width}:-1:flags=lanczos,hqdn3d=0:0:14:14'
    subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-i', mp4, '-vf', vf + ',palettegen=max_colors=36:stats_mode=full',
                    pal], check=True)
    subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-i', mp4, '-i', pal, '-lavfi',
                    vf + '[x];[x][1:v]paletteuse=dither=none:diff_mode=rectangle', '-loop', '0', gif], check=True)
    os.remove(pal)
    print(f'[truck-sting] gif {os.path.getsize(gif) / 1e6:.2f} MB -> {gif}')


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--out', default=os.path.join(HERE, 'zipzoom_sting.mp4'))
    ap.add_argument('--sheet', action='store_true', help='also write contact_sheet.jpg + onion.png next to the mp4')
    ap.add_argument('--gif', action='store_true', help='also write docs/img/truck-sting.gif (360 px)')
    ap.add_argument('--still', type=float, help='render one still at this time to still.png and exit')
    A = ap.parse_args()
    if A.still is not None:
        t_h, d = HOLDS(A.still)
        cv2.imwrite(os.path.join(HERE, 'still.png'), render_drawing(Assets(), t_h, d)); return
    out_dir = os.path.dirname(os.path.abspath(A.out))
    tmp = render_video(A.out, sheet=os.path.join(out_dir, 'contact_sheet.jpg') if A.sheet else None,
                       onion=os.path.join(out_dir, 'onion.png') if A.sheet else None)
    wav = A.out + '.mix.wav'
    build_audio(wav)
    mux(tmp, wav, A.out); os.remove(tmp); os.remove(wav)
    print(f'[truck-sting] -> {A.out}')
    if A.gif: make_gif(A.out, os.path.join(ROOT, 'docs', 'img', 'truck-sting.gif'))


if __name__ == '__main__':
    main()
