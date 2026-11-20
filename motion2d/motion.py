"""Reusable motion primitives for layered cut-out animation (any style).
Frames are float32 BGR numpy arrays (H, W, 3). Layers are PIL RGBA images."""
import math, random
import numpy as np, cv2
from PIL import Image, ImageFilter

# ---------- easing ----------
def clamp(x, a=0.0, b=1.0): return max(a, min(b, x))
def ease(x):            x = clamp(x); return x * x * (3 - 2 * x)          # smoothstep
def ease_out(x):        x = clamp(x); return 1 - (1 - x) ** 3
def ease_in(x):         x = clamp(x); return x ** 3
def back(x, c=1.9):     x = clamp(x); return 1 + (c + 1) * (x - 1) ** 3 + c * (x - 1) ** 2   # overshoot
def elastic(x):         x = clamp(x); return 1 - math.cos(x * 4.5 * math.pi) * math.exp(-x * 6)
POP = [0.3, 0.75, 1.12, 1.04, 0.97, 1.0]   # pop-in scale per step (on 12 fps "on twos")
def pop_scale(step): return POP[step] if step < len(POP) else 1.0
def squash(t_since_land, amt=0.06, freq=16, damp=5):
    """returns (sx, sy) for a damped squash-and-stretch after an impact"""
    s = math.exp(-t_since_land * damp) * math.sin(t_since_land * freq)
    return 1 + amt * s, 1 - amt * s

# ---------- layer ops ----------
def xform(im, sx=1, sy=1, rot=0):
    w, h = im.size
    im2 = im.resize((max(1, int(w * sx)), max(1, int(h * sy))), Image.BICUBIC)
    return im2.rotate(rot, resample=Image.BICUBIC, expand=True) if abs(rot) > 0.01 else im2

def shadow_of(im, op=0.35, blur=9, color=(40, 22, 12)):
    a = np.array(im)[..., 3]
    s = Image.new('RGBA', im.size, color + (0,))
    s.putalpha(Image.fromarray((a * op).astype(np.uint8)).filter(ImageFilter.GaussianBlur(blur)))
    return s

def paste(fr, im, cx, cy):
    """alpha-composite RGBA PIL image centred at (cx, cy) onto BGR float frame"""
    H, W = fr.shape[:2]
    a = np.array(im).astype(np.float32); h, w = a.shape[:2]
    x, y = int(round(cx - w / 2)), int(round(cy - h / 2))
    X0, Y0 = max(x, 0), max(y, 0); X1, Y1 = min(x + w, W), min(y + h, H)
    if X1 <= X0 or Y1 <= Y0: return
    sub = a[Y0 - y:Y1 - y, X0 - x:X1 - x]; al = sub[..., 3:4] / 255
    fr[Y0:Y1, X0:X1] = fr[Y0:Y1, X0:X1] * (1 - al) + sub[..., 2::-1] * al

def place_pivot(fr, im, px, py, pivot, rot, shadow=None):
    """place im so its pivot pixel lands on (px,py), rotated rot deg about pivot.
    shadow=(opacity, blur, dx, dy) drops a soft cast shadow."""
    w, h = im.size; vx, vy = w / 2 - pivot[0], h / 2 - pivot[1]
    a = math.radians(-rot)
    rx, ry = vx * math.cos(a) - vy * math.sin(a), vx * math.sin(a) + vy * math.cos(a)
    im2 = xform(im, rot=rot)
    if shadow: paste(fr, shadow_of(im2, *shadow[:2]), px + rx + shadow[2], py + ry + shadow[3])
    paste(fr, im2, px + rx, py + ry)

# ---------- paths ----------
class Path:
    """polyline path; at(u) for u in 0..1 at constant speed"""
    def __init__(self, pts):
        self.p = pts; self.seg = [math.dist(pts[i], pts[i + 1]) for i in range(len(pts) - 1)]; self.tot = sum(self.seg)
    def at(self, u):
        d = clamp(u) * self.tot
        for i, L in enumerate(self.seg):
            if d <= L:
                f = d / L if L else 0
                return (self.p[i][0] + (self.p[i + 1][0] - self.p[i][0]) * f, self.p[i][1] + (self.p[i + 1][1] - self.p[i][1]) * f)
            d -= L
        return self.p[-1]

# ---------- camera / finish ----------
def camera(BG, W, H, t, dur, step, zoom=0.06, drift=6, jitter=1.5):
    """slow push-in + drift + per-step stop-motion jitter over a background"""
    z = 1.0 + zoom * ease(t / dur); bh, bw = BG.shape[:2]; sc = max(W / bw, H / bh) * z
    vw, vh = W / sc, H / sc; x0 = (bw - vw) * 0.5 + drift * math.sin(t * 0.4); y0 = (bh - vh) * 0.5
    j = random.Random(step)
    M = np.array([[sc, 0, -x0 * sc + j.uniform(-jitter, jitter)], [0, sc, -y0 * sc + j.uniform(-jitter, jitter)]], np.float32)
    return cv2.warpAffine(BG, M, (W, H), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT).astype(np.float32)

def make_finish(W, H, vignette=0.28, grain=3.5, n=6, seed=7):
    rs = np.random.RandomState(seed)
    yy, xx = np.mgrid[0:H, 0:W]
    vign = np.clip(1 - vignette * (((xx - W / 2) / (W / 2)) ** 2 + ((yy - H / 2) / (H / 2)) ** 2) ** 1.2, 0.6, 1)[..., None]
    grains = [cv2.GaussianBlur(rs.randn(H, W).astype(np.float32), (0, 0), 0.8)[..., None] * grain for _ in range(n)]
    def finish(fr, step, flicker=0.015):
        fr = fr * (1 + random.Random(step).uniform(-flicker, flicker))
        return np.clip(fr * vign + grains[step % n], 0, 255).astype(np.uint8)
    return finish

def word_time(text, word, vo_dur, pre=0.0):
    """approximate when a word is spoken: char-proportional (good to ~0.3 s). Use word timestamps from TTS when available."""
    return pre + vo_dur * text.find(word) / len(text)

def ffmpeg_writer(path, W, H, fps=12, out_fps=24, crf=20):
    import subprocess
    return subprocess.Popen(['ffmpeg', '-y', '-loglevel', 'error', '-f', 'rawvideo', '-pix_fmt', 'bgr24', '-s', f'{W}x{H}', '-r', str(fps), '-i', '-',
                             '-vf', f'fps={out_fps}', '-c:v', 'libx264', '-preset', 'medium', '-crf', str(crf), '-pix_fmt', 'yuv420p', path], stdin=subprocess.PIPE)
