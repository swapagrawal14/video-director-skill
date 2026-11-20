import os, sys, json, math, random, subprocess
import numpy as np, cv2
from PIL import Image, ImageDraw, ImageFont, ImageFilter
ROOT = os.environ.get('MOTION_ROOT', os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')))
sys.path.insert(0, ROOT)
from motion import *
import sfx as SFXLIB
W, H = 1920, 1080
def load(here, name, scale=1.0):
    im = Image.open(f'{here}/assets/{name}.png').convert('RGBA')
    return im.resize((int(im.width * scale), int(im.height * scale)), Image.LANCZOS) if scale != 1 else im
def load_bg(here):
    bg = cv2.imread(f'{here}/assets/bg.png'); return cv2.resize(bg, (int(W * 1.04), int(H * 1.04)), interpolation=cv2.INTER_LANCZOS4)
def vo_info(here):
    return float(subprocess.check_output(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', f'{here}/assets/vo.wav']))
def label(text, size=56, color=(120, 30, 30), font='Fredoka.ttf', wght=650, stroke=0, stroke_fill=(255, 255, 255)):
    f = ImageFont.truetype(f'{ROOT}/fonts/{font}', size)
    try:
        ax = f.get_variation_axes(); f.set_variation_by_axes([wght] + [100] * (len(ax) - 1))
    except Exception: pass
    bb = f.getbbox(text, stroke_width=stroke); im = Image.new('RGBA', (bb[2] + 20, bb[3] + 20), (0, 0, 0, 0))
    ImageDraw.Draw(im).text((10, 10), text, font=f, fill=color + (255,), stroke_width=stroke, stroke_fill=stroke_fill)
    return im
def rot_vec(vx, vy, rot):
    a = math.radians(-rot); return vx * math.cos(a) - vy * math.sin(a), vx * math.sin(a) + vy * math.cos(a)
def finish_audio(here, dur, events, pre):
    vo = np.frombuffer(subprocess.check_output(['ffmpeg', '-v', 'error', '-i', f'{here}/assets/vo.wav', '-f', 'f32le', '-ac', '1', '-ar', str(SFXLIB.SR), '-']), np.float32)
    m = SFXLIB.mix(dur, vo=vo, vo_at=pre, events=events)
    import wave
    with wave.open(f'{here}/out_audio.wav', 'wb') as w: w.setnchannels(1); w.setsampwidth(2); w.setframerate(SFXLIB.SR); w.writeframes((m * 32767).astype(np.int16).tobytes())
    subprocess.run(['ffmpeg', '-y', '-v', 'error', '-i', f'{here}/out_video.mp4', '-i', f'{here}/out_audio.wav', '-af', 'loudnorm=I=-16:TP=-1.5', '-c:v', 'copy', '-c:a', 'aac', '-b:a', '192k', '-ar', '48000', '-shortest', '-movflags', '+faststart', f'{here}/final.mp4'], check=True)
    print('final', f'{here}/final.mp4')
def run(here, DUR, FPS, draw, events, pre, jitter=False):
    PREV = [int(x) for x in os.environ.get('PREVIEW', '').split(',') if x]
    finish = make_finish(W, H, vignette=0.18, grain=2.5)
    BG = load_bg(here)
    N = int(DUR * FPS)
    proc = None if PREV else ffmpeg_writer(f'{here}/out_video.mp4', W, H, fps=FPS, out_fps=24)
    for step in range(N):
        t = step / FPS
        fr = camera(BG, W, H, t, DUR, step, zoom=0.03, drift=4, jitter=1.2 if jitter else 0)
        draw(fr, t, step)
        if t < 0.3: fr *= t / 0.3
        out = finish(fr, step, flicker=0.01 if jitter else 0)
        if PREV:
            if step in PREV: cv2.imwrite(f'{here}/pv_{step}.jpg', out)
            if step >= max(PREV): break
            continue
        proc.stdin.write(out.tobytes())
    if proc:
        proc.stdin.close(); proc.wait(); finish_audio(here, DUR, events, pre)
