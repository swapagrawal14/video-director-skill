"""Composite frames and encode the episode with ffmpeg."""
import os
import subprocess
import wave
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from . import backgrounds, characters, music, voice

W, H, FPS = 1280, 720, 24
FORMATS = {"landscape": (1280, 720), "vertical": (720, 1280), "square": (1080, 1080)}
SR = 44100


def _font(sz):
    for f in ("/usr/share/fonts/truetype/noto/NotoSansDevanagari-Bold.ttf",
              "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"):
        try:
            return ImageFont.truetype(f, sz)
        except OSError:
            pass
    return ImageFont.load_default()


def _subtitle(img, text, font):
    d = ImageDraw.Draw(img)
    lines, cur = [], ""
    for w in text.split():
        if cur and d.textlength(cur + " " + w, font=font) > W * 0.8:
            lines.append(cur); cur = w
        else:
            cur = (cur + " " + w).strip()
    lines.append(cur)
    y = H - 30 - len(lines) * 40
    bar = Image.new("RGBA", (W, len(lines) * 40 + 24), (0, 0, 0, 110))
    img.paste(bar, (0, y - 12), bar)
    d = ImageDraw.Draw(img)
    for ln in lines:
        x = (W - d.textlength(ln, font=font)) / 2
        d.text((x, y), ln, font=font, fill="white", stroke_width=4, stroke_fill="black")
        y += 40


def _bench(img, cx, w):
    d = ImageDraw.Draw(img)
    top = int(H * 0.80)
    d.rounded_rectangle((cx - w // 2, top, cx + w // 2, top + 18), 8, fill=(150, 95, 60), outline=(60, 35, 25), width=3)
    for x in (cx - w // 2 + 20, cx + w // 2 - 32):
        d.rectangle((x, top + 18, x + 12, H * 0.92), fill=(110, 70, 45), outline=(60, 35, 25), width=2)


def mix(shots, total, out_wav):
    n = int(total * SR)
    vo = np.zeros(n, np.float32)
    for s in shots:
        if s.audio is not None:
            a = int(s.start * SR)
            seg = s.audio[: max(0, n - a)]
            vo[a:a + len(seg)] += seg
    timeline = [(0.0, shots[0].scene.mood)] + [(s.start, s.scene.mood) for s in shots]
    bg = music.score(timeline, total)
    duck = np.convolve((np.abs(vo) > 0.02).astype(np.float32), np.ones(SR // 5) / (SR // 5), "same")
    mixd = np.clip(vo + bg * (1 - 0.6 * np.clip(duck * 3, 0, 1)), -1, 1)
    with wave.open(out_wav, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR)
        w.writeframes((mixd * 32767).astype(np.int16).tobytes())
    return out_wav


def _camera(img, cx, cy, z):
    """Zoom toward (cx, cy) by factor z, keeping the frame size."""
    if z <= 1.001:
        return img
    cw, ch = W / z, H / z
    x0 = min(max(cx - cw / 2, 0), W - cw)
    y0 = min(max(cy - ch / 2, 0), H - ch)
    return img.resize((W, H), Image.BICUBIC, box=(x0, y0, x0 + cw, y0 + ch))


def write_srt(shots, path):
    def ts(x):
        ms = int(round(x * 1000))
        return f"{ms // 3600000:02d}:{ms // 60000 % 60:02d}:{ms // 1000 % 60:02d},{ms % 1000:03d}"
    with open(path, "w", encoding="utf-8") as f:
        for i, s in enumerate(shots, 1):
            f.write(f"{i}\n{ts(s.start)} --> {ts(s.start + s.duration - 0.1)}\n{s.speaker.title()}: {s.text}\n\n")
    return path


def render(script, shots, total, out="episode.mp4", audio=None, fmt="landscape", camera=True):
    global W, H
    W, H = FORMATS[fmt]
    write_srt(shots, os.path.splitext(out)[0] + ".srt")
    font, tfont = _font(32 if W >= H else 30), _font(64 if W >= H else 52)
    envs = {id(s): voice.envelope(s.audio, FPS) for s in shots if s.audio is not None}
    if audio is None:
        audio = mix(shots, total, os.path.splitext(out)[0] + "_mix.wav")
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
           "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-", "-i", audio, "-shortest",
           "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "20", "-c:a", "aac", "-b:a", "160k", out]
    p = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    last_pose = {}
    for f in range(int(total * FPS)):
        t = f / FPS
        shot = next((s for s in shots if s.start <= t < s.start + s.duration), None)
        if shot is None and t > 3:
            shot_sc = shots[-1].scene
        else:
            shot_sc = shot.scene if shot else script.scenes[0]
        img = Image.fromarray(backgrounds.render(W, H, t, shot_sc.mood, shot_sc.bg))
        if t < shots[0].start:
            d = ImageDraw.Draw(img)
            x = (W - d.textlength(script.title, font=tfont)) / 2
            d.text((x, H / 2 - 40), script.title, font=tfont, fill="white", stroke_width=5, stroke_fill="black")
        else:
            cast = list(dict.fromkeys(l.speaker for l in shot_sc.lines))
            slots = {n: (i + 1) * W // (len(cast) + 1) for i, n in enumerate(cast)}
            if shot:
                last_pose[shot.speaker] = shot.line.pose
            for i, name in enumerate(cast):
                loud = 0.0
                if shot and name == shot.speaker and id(shot) in envs:
                    e = envs[id(shot)]; k = int((t - shot.start) * FPS)
                    loud = float(e[k]) if k < len(e) else 0.0
                elif shot and name == shot.speaker:
                    loud = 0.5 + 0.5 * np.sin(t * 20)
                seated = characters.has_poses(name)
                hgt = int(min(H * 0.56, W / (len(cast) + 0.6) * (1.15 if W >= H else 1.6))) if seated else int(H * 0.47)
                ch, bob = characters.pose(name, t, loud, hgt, last_pose.get(name, "idle"), phase=i * 1.7)
                if seated:
                    _bench(img, slots[name], int(hgt * 0.65))
                base = int(H * 0.84) if seated else int(H * 0.86)
                img.paste(ch, (slots[name] - ch.width // 2, base - ch.height + bob), ch)
            if camera and shot:
                k = min(1.0, (t - shot.start) / 1.2)
                z = 1 + 0.07 * (k * k * (3 - 2 * k))
                img = _camera(img, slots[shot.speaker], H * 0.6, z)
            if shot:
                _subtitle(img, f"{shot.speaker.title()}: {shot.text}", font)
        arr = np.asarray(img.convert("RGB"))
        # fade through black at scene changes
        for s_ in shots[1:]:
            prev = shots[shots.index(s_) - 1]
            if s_.scene is not prev.scene and abs(t - s_.start) < 0.35:
                arr = (arr * (abs(t - s_.start) / 0.35)).astype(np.uint8)
        if t > total - 0.6:
            arr = (arr * max(0.0, (total - t) / 0.6)).astype(np.uint8)
        p.stdin.write(arr.tobytes())
    p.stdin.close(); p.wait()
    return out
