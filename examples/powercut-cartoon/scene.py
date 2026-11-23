# examples/powercut-cartoon/scene.py  (run from repo root; PROJECT=projects/<name> to render a copy)  "2 AM Power Cut" - pastel cartoon, 9:16, 12 s, no VO
import os, sys, json, math, numpy as np, cv2
sys.path.insert(0, 'motion2d')
from PIL import Image, ImageDraw, ImageFont
from motion import paste, ffmpeg_writer, ease
from posepack import Cast
import cartoon
cartoon.GRADES['cut2am'] = ((0.36, 0.20, 0.26), (36, 4, 16), 0.62)
from cartoon import (Light, glow_eyes, light_pool, shake, push, camera_frame, BeatSheet, hold_time,
                     make_style_finish, swing)
import sfx, mix

P = os.environ.get('PROJECT', 'examples/powercut-cartoon')
FPS, DUR, W, H = 24, 12.0, 1080, 1920
STYLE = json.load(open(f'{P}/style.json'))
SET = cv2.imread(f'{P}/set.png').astype(np.float32)
BLADES = Image.open(f'{P}/props/fan_blades.png').convert('RGBA')
BLADES = BLADES.crop(BLADES.getbbox())
FAN_HUB = (540, 392)
LAMP = (1040, 1405)

GIRL = Cast(f'{P}/cast/girl/girl', ['read', 'yawn', 'doze', 'startled', 'torch', 'scared', 'deadpan'],
            x=610, floor=1565, scale=0.68, pop=STYLE['squash'])
CAT = Cast(f'{P}/props/cat', ['sit'], x=125, floor=1450, scale=0.30, pop=0.12, shadow=False, sway=0.3)

T_CUT, T_ON = 3.4, 8.0
BEATS = [
    (0.0, 'girl', 'read', 'dab', 'reading Dental Anatomy, fan spinning, lamp on'),
    (1.4, 'girl', 'yawn', 'squish', 'big yawn'),
    (2.4, 'girl', 'doze', 'whoosh', 'head drops, dozing'),
    (3.4, 'light', 'powercut', None, 'POWER CUT: thunder, flicker, fan winds down'),
    (3.7, 'girl', 'startled', 'plip', 'snaps awake'),
    (4.7, 'girl', 'torch', 'tick', 'phone torch on, scanning'),
    (5.6, 'cat', 'eyes', 'heartbeat', 'two glowing eyes open on the pillow'),
    (5.7, 'cam', 'push', None, 'slow push toward the eyes'),
    (6.6, 'girl', 'scared', 'squish', 'hides behind the book'),
    (6.9, 'cat', 'blink', 'riser_4s', 'eyes blink, lean closer'),
    (8.0, 'light', 'day', None, 'light comes back with flicker, fan restarts'),
    (8.0, 'cat', 'reveal', 'boing', 'just the hostel cat, sitting on her pillow'),
    (8.5, 'girl', 'deadpan', 'squish', 'flat stare at the cat'),
    (9.9, 'cat', 'smug', 'plip', 'cat settles, tail flick'),
    (10.4, 'girl', 'doze', 'whoosh', 'gives up, back to sleep'),
]
beats = BeatSheet(BEATS)
L = Light([(0, 'day'), (T_CUT, 'cut2am'), (T_ON, 'day')], flicker=[(T_CUT, 0.4), (T_ON, 0.3)])
finish = make_style_finish(W, H, STYLE)
FONT = ImageFont.truetype('fonts/baloo2.ttf', 64)
FONT_S = ImageFont.truetype('fonts/baloo2.ttf', 34)


def fan_angle(t):
    """rpm 110, winds down over 2.2 s after the cut, back up over 1.2 s after power returns."""
    w0 = 110 / 60 * 360  # deg/s
    def rate(u):
        if u < T_CUT: return w0
        if u < T_ON: return w0 * max(0.0, 1 - (u - T_CUT) / 2.2) ** 2
        return w0 * min(1.0, (u - T_ON) / 1.2)
    n = max(1, int(t * 48)); dt = t / n
    return -sum(rate(i * dt) for i in range(n)) * dt, rate(t)


def draw_fan(fr, t):
    a, r = fan_angle(t)
    steps = 4 if r > 300 else 1
    acc = None
    for i in range(steps):
        im = BLADES.rotate(a - 14 * i, resample=Image.BICUBIC)
        arr = np.array(im, np.float32); acc = arr if acc is None else acc + arr
    im = Image.fromarray((acc / steps).astype(np.uint8))
    w = 560; im = im.resize((w, int(w * 0.26)), Image.LANCZOS)   # fake perspective from below
    paste(fr, im, FAN_HUB[0], FAN_HUB[1])


def text(fr, s, xy, font, alpha, fill=(78, 46, 50)):
    if alpha <= 0: return fr
    im = Image.fromarray(fr.astype(np.uint8)[..., ::-1])
    lay = Image.new('RGBA', im.size, (0, 0, 0, 0)); d = ImageDraw.Draw(lay)
    bb = d.textbbox((0, 0), s, font=font); x = xy[0] - (bb[2] - bb[0]) / 2
    pad = 18
    d.rounded_rectangle((x - pad, xy[1] - 6, x + bb[2] - bb[0] + pad, xy[1] + bb[3] - bb[1] + pad + 4), 28,
                        fill=(249, 244, 242, int(230 * alpha)), outline=(78, 46, 50, int(255 * alpha)), width=5)
    d.text((x, xy[1] - bb[1] + 6), s, font=font, fill=fill + (int(255 * alpha),))
    im = Image.alpha_composite(im.convert('RGBA'), lay).convert('RGB')
    return np.array(im)[..., ::-1].astype(np.float32)


def frame(t, step):
    t = hold_time(t, STYLE['hold'], FPS)
    fr = SET.copy()
    # thunder flash in the window at the cut
    if T_CUT <= t < T_CUT + 0.12 or T_CUT + 0.22 <= t < T_CUT + 0.28:
        fr[700:1200, 620:1000] = np.clip(fr[700:1200, 620:1000] * 1.0 + 140, 0, 255)
    draw_fan(fr, t)
    cat_act = beats.pose('cat', t, 'none')
    if cat_act != 'none':
        CAT.draw(fr, t, 'sit', flip=True, rot=(swing(t, 2.0, 0.8, damp=1.5, t0=9.9) if t > 9.9 else 0))
    GIRL.draw(fr, t, beats.pose('girl', t))
    fr = L.apply(fr, t)
    day = L.level(t, 'day'); dark = L.level(t, 'cut2am')
    light_pool(fr, LAMP, 330, '#FFE7B3', 0.5 * day)
    if beats.pose('girl', t) == 'torch' or (beats.pose('girl', t) == 'scared' and t < T_ON):
        if beats.pose('girl', t) == 'torch':
            px, py = GIRL.world((243, 324), 'torch')
            sweep = math.sin((t - 4.7) * 2.2) * 120
            light_pool(fr, (px, py), 110, '#FFFFFF', 0.9 * dark)                          # phone LED
            light_pool(fr, (px - 260 + sweep, py + 120), 300, '#FFF6D8', 0.55 * dark, aspect=0.7)  # beam on the bed
    if cat_act in ('eyes', 'blink') and t < T_ON:
        ex, ey = CAT.world((373, 300), 'sit')
        lean = 0 if cat_act == 'eyes' else min(1.0, (t - 6.9) / 1.0) * 28
        pts = [(ex + lean, ey + lean * 0.3), (ex + 42 + lean, ey + 2 + lean * 0.3)]
        glow_eyes(fr, pts, t, on=dark * min(1.0, (t - 5.6) / 0.25), color='#FFD23F', r=9,
                  blink=[(6.9, 0.14), (7.5, 0.1)])
    # camera
    dx, dy = shake(t, T_ON, dur=0.3, amp=10)
    sx, sy = shake(t, T_CUT, dur=0.25, amp=7)
    z = 1.0 + 0.04 * ease(t / T_CUT) if t < T_CUT else 1.04
    if t >= 5.7: z = push(t, 5.7, 7.9, 1.04, 1.2) if t < T_ON else 1.04
    cx = 610 if t < 5.7 or t >= T_ON else 610 + (260 - 610) * ease((t - 5.7) / 2.2)
    cy = 1150 if t < 5.7 or t >= T_ON else 1150 + (1380 - 1150) * ease((t - 5.7) / 2.2)
    fr = camera_frame(fr, zoom=z, cx=cx, cy=cy, dx=dx + sx, dy=dy + sy)
    # titles
    a1 = min(1, t / 0.3) * (1 - min(1, max(0, t - 2.0) / 0.4))
    fr = text(fr, '2:00 AM  |  Exam kal hai', (W // 2, 150), FONT, a1)
    a3 = max(0, min(1, (t - 10.9) / 0.4))
    fr = text(fr, 'Swapnil Agrawal (BDS intern)', (W // 2, 1780), FONT_S, a3)
    return finish(fr, step)


def audio(path):
    N = int(DUR * mix.SR); buf = np.zeros(N, np.float32)
    MAXLEN = {'drone_sub': 4.6, 'heartbeat': 2.4, 'riser_4s': 1.1}
    for t, name in beats.sfx_events():
        clip = sfx.FX[name]() if name in sfx.FX else mix.read(f'{P}/sfx/{name}.wav')
        clip = clip[:int(MAXLEN.get(name, 99) * mix.SR)].astype(np.float32)
        mix.place(buf, clip, t, {'heartbeat': 1.2, 'riser_4s': 0.7}.get(name, 0.9))
    th = sfx.thunder().astype(np.float32); mix.place(buf, th, T_CUT, 1.0)
    dr = mix.read(f'{P}/sfx/drone_sub.wav')[:int(4.6 * mix.SR)].astype(np.float32)
    dr = dr * np.linspace(0, 1, len(dr)) ** 0.5; mix.place(buf, dr, T_CUT, 0.9)
    # fan hum: low noise band, gone during the cut
    tt = np.arange(N) / mix.SR
    hum = (np.sin(2 * np.pi * 95 * tt) * 0.02 + np.random.RandomState(1).randn(N) * 0.006).astype(np.float32)
    env = np.where(tt < T_CUT, 1.0, np.where(tt < T_ON, np.clip(1 - (tt - T_CUT) / 1.5, 0, 1), np.clip((tt - T_ON) / 1.2, 0, 1)))
    buf += hum * env
    bed = sfx.pluck_bed(DUR, vol=0.03).astype(np.float32)[:N]
    benv = np.where(tt < T_CUT, 1.0, np.where(tt < T_ON + 0.6, 0.0, np.clip((tt - T_ON - 0.6) / 0.8, 0, 1)))
    buf[:len(bed)] += bed * benv[:len(bed)]
    mix.place(buf, sfx.pop().astype(np.float32), T_ON, 1.0)
    mix.write(path, buf / max(1.0, np.abs(buf).max() / 0.9))


if __name__ == '__main__':
    os.makedirs(f'{P}/shots', exist_ok=True)
    prev = os.environ.get('PREVIEW')
    if prev:
        for s in prev.split(','):
            cv2.imwrite(f'{P}/shots/t{float(s):05.2f}.jpg', frame(float(s), int(float(s) * FPS)))
        sys.exit()
    print(beats.check(DUR, actors_on_screen=['girl']))
    wr = ffmpeg_writer(f'{P}/video.mp4', W, H, fps=FPS, out_fps=FPS)
    for step in range(int(DUR * FPS)):
        wr.stdin.write(frame(step / FPS, step).tobytes())
    wr.stdin.close(); wr.wait(); audio(f'{P}/mix.wav')
