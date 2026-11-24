#!/usr/bin/env python3
"""Reframe a finished vertical (9:16) render into 16:9 and 1:1. Raster only (ffmpeg + numpy, OpenCV optional).

  16:9  the vertical video sits sharp in the centre over a background:
          --bg blur   (default) a scaled, blurred, slightly darkened copy of itself
          --bg paper  a procedural warm paper texture (numpy), or --bg-image my_texture.png
        optional side title panel: --title "Adams Clasp" [--subtitle "step by step"] [--handle "@swap"]
  1:1   a crop that follows the subject: per-sample saliency (edges) + motion energy + faces (OpenCV Haar, if
        installed) -> best window. --crop static (default, one steady window) | track (eased pan, keyframed).
        --caption-zone 0.72,0.9 keeps that band (fractions of source height) inside the crop when it fits, so
        captions burned into the source stay readable.
Captions: --captions words.json|captions.ass|captions.srt re-burns them at the NEW size. When the input is a
project dir, the clean picture (video_only.mp4 + final_audio.wav, i.e. before mux burned captions) is used and
words.json is re-captioned automatically (scripts/captions.py) unless --no-recaption.
Output: H.264 (yuv420p, BT.709) + AAC 48 kHz, faststart, written in /tmp then copied.
Usage:
  python3 scripts/reframe.py Final_9x16.mp4 [--to 16x9,1x1] [-o outdir] [--bg blur|paper] [--title ...]
  python3 scripts/reframe.py projects/<slug> --to 1x1 --crop track
Writes <outdir>/<stem>_16x9.mp4, <stem>_1x1.mp4 and a look frame <stem>_<aspect>.jpg for each."""
import argparse, glob, json, os, re, shutil, subprocess, sys, tempfile

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE); FONTS = os.path.join(ROOT, 'fonts')
SIZES = {'16x9': (1920, 1080), '1x1': (1080, 1080), '9x16': (1080, 1920), '4x5': (1080, 1350)}


# ---------------------------------------------------------------- pure helpers (unit tested)
def parse_aspects(s):
    out = []
    for a in re.split(r'[,\s]+', s.strip()):
        if not a: continue
        a = a.replace(':', 'x').lower()
        if a not in SIZES: raise ValueError(f'unknown aspect {a!r} (use {", ".join(SIZES)})')
        if a not in out: out.append(a)
    return out


def even(x): return int(round(x / 2.0)) * 2


def fit_inside(sw, sh, W, H):
    """Size of the source scaled to fit inside WxH (keeps aspect, even numbers)."""
    k = min(W / sw, H / sh)
    return min(W, even(sw * k)), min(H, even(sh * k))


def cover_scale(sw, sh, W, H):
    """Size of the source scaled to cover WxH; the crop axis is the one that overflows ('x' or 'y')."""
    k = max(W / sw, H / sh)
    w, h = max(W, even(sw * k)), max(H, even(sh * k))
    return w, h, ('y' if h > H else 'x')


def best_window(profile, win, prior=0.15):
    """Start index of the length-`win` window with the most energy in a 1-D profile. A mild centre prior
    breaks ties toward the middle (prior=0 disables it)."""
    p = np.asarray(profile, dtype=float); n = len(p)
    if win >= n: return 0
    c = np.concatenate([[0.0], np.cumsum(p)]); sums = c[win:] - c[:-win]
    if sums.max() <= 0: return (n - win) // 2
    starts = np.arange(len(sums)); mid = (n - win) / 2.0
    score = sums / sums.max() - prior * np.abs(starts - mid) / max(mid, 1.0)
    return int(np.argmax(score))


def subject_window(profile, win, prior=0.15):
    """best_window, then re-centred on the energy centroid inside it, so the subject sits mid-frame instead of
    hugging an edge of the crop."""
    p = np.asarray(profile, dtype=float); n = len(p)
    if win >= n: return 0
    s = best_window(p, win, prior); seg = p[s:s + win]
    if seg.sum() <= 0: return s
    c = s + float((seg * np.arange(win)).sum() / seg.sum())
    return int(min(max(round(c - win / 2), 0), n - win))


def constrain_window(start, win, n, zone=None):
    """Clamp a window to [0, n) and, if a zone (a, b in pixels) fits inside a window, slide it to include it."""
    start = int(min(max(start, 0), max(n - win, 0)))
    if zone:
        a, b = zone
        if b - a <= win:
            if a < start: start = int(a)
            if b > start + win: start = int(b - win)
            start = int(min(max(start, 0), max(n - win, 0)))
    return start


def smooth_track(values, max_step, alpha=0.5):
    """Exponential smoothing forward + backward (no lag), then a speed limit per sample."""
    v = np.asarray(values, dtype=float)
    if len(v) < 2: return v
    f = v.copy()
    for i in range(1, len(f)): f[i] = alpha * v[i] + (1 - alpha) * f[i - 1]
    b = f.copy()
    for i in range(len(b) - 2, -1, -1): b[i] = alpha * f[i] + (1 - alpha) * b[i + 1]
    out = b.copy()
    for i in range(1, len(out)): out[i] = out[i - 1] + np.clip(out[i] - out[i - 1], -max_step, max_step)
    return out


def piecewise_expr(times, vals, var='t'):
    """ffmpeg expression: linear interpolation through (times[i], vals[i]), held flat outside the range."""
    pts = [(float(t), float(v)) for t, v in zip(times, vals)]
    if not pts: return '0'
    if len(pts) == 1: return f'{pts[0][1]:.1f}'
    expr = f'{pts[-1][1]:.1f}'
    for (t0, v0), (t1, v1) in reversed(list(zip(pts, pts[1:]))):
        seg = f'{v0:.1f}+({v1 - v0:.1f})*({var}-{t0:.3f})/{max(t1 - t0, 1e-3):.3f}'
        expr = f'if(lt({var},{t1:.3f}),{seg},{expr})'
    return f'if(lt({var},{pts[0][0]:.3f}),{pts[0][1]:.1f},{expr})'


def energy_maps(frames, faces=None, motion_w=2.0, face_w=4.0):
    """frames: (N, h, w) float grey 0..1 -> (N, h, w) energy = edges + motion_w*|frame diff| + face_w*face boxes."""
    F = np.asarray(frames, dtype=np.float32); out = np.zeros_like(F)
    for i, f in enumerate(F):
        gy, gx = np.gradient(f); e = np.hypot(gx, gy)
        if i > 0: e = e + motion_w * np.abs(f - F[i - 1])
        elif len(F) > 1: e = e + motion_w * np.abs(F[1] - f)
        if faces and faces[i]:
            for (x, y, w, h) in faces[i]: e[y:y + h, x:x + w] += face_w * max(e.mean(), 1e-3) * 4
        out[i] = e
    return out


def retarget_ass(text, W, H):
    """Re-target an .ass made for another frame size: set PlayRes to WxH and scale font sizes/margins by the
    height ratio so the line keeps its look; alignment-anchored lines then land in the new frame.
    Lines positioned with \\pos/\\move keep source coordinates (warned by the caller)."""
    m = re.search(r'^PlayResY:\s*(\d+)', text, re.M); oh = int(m.group(1)) if m else 288
    mw = re.search(r'^PlayResX:\s*(\d+)', text, re.M); ow = int(mw.group(1)) if mw else 384
    k = min(W, H) / min(ow, oh)   # keep size relative to the short side (a 1080-wide reel line stays 1080-sized)
    text = re.sub(r'^PlayResY:.*$', f'PlayResY: {H}', text, flags=re.M)
    text = re.sub(r'^PlayResX:.*$', f'PlayResX: {W}', text, flags=re.M)
    if 'PlayResX' not in text: text = text.replace('[Script Info]', f'[Script Info]\nPlayResX: {W}\nPlayResY: {H}', 1)
    lines = text.split('\n'); fmt = None
    for i, ln in enumerate(lines):
        if ln.startswith('Format:') and fmt is None and any(x.startswith('Style:') for x in lines[i + 1:i + 3]):
            fmt = [c.strip() for c in ln[7:].split(',')]
        elif ln.startswith('Style:') and fmt:
            v = [c.strip() for c in ln[6:].split(',')]
            for key in ('Fontsize', 'Outline', 'Shadow', 'MarginV', 'Spacing'):
                if key in fmt and fmt.index(key) < len(v):
                    try: v[fmt.index(key)] = f'{float(v[fmt.index(key)]) * k:.0f}' if key != 'Spacing' else f'{float(v[fmt.index(key)]) * k:.1f}'
                    except ValueError: pass
            for key in ('MarginL', 'MarginR'):
                if key in fmt and fmt.index(key) < len(v):
                    try: v[fmt.index(key)] = f'{float(v[fmt.index(key)]) * W / ow:.0f}'
                    except ValueError: pass
            lines[i] = 'Style: ' + ','.join(v)
    text = '\n'.join(lines)
    text = re.sub(r'\\fs(\d+(?:\.\d+)?)', lambda m: f'\\fs{float(m.group(1)) * k:.0f}', text)
    return text


def wrap_words(words, max_chars):
    lines, cur = [], ''
    for w in words.split():
        if cur and len(cur) + 1 + len(w) > max_chars: lines.append(cur); cur = w
        else: cur = f'{cur} {w}'.strip()
    if cur: lines.append(cur)
    return lines


def project_sources(d):
    """For a project dir: (picture, audio, is_clean). Prefers video_only.mp4 + final_audio.wav (no burned captions),
    else the newest finished mp4 in the dir."""
    vo, au = os.path.join(d, 'video_only.mp4'), os.path.join(d, 'final_audio.wav')
    if os.path.exists(vo): return vo, (au if os.path.exists(au) else None), True
    c = [f for f in glob.glob(os.path.join(d, '*.mp4')) if not re.search(r'_(16x9|1x1|4x5|9x16)\.mp4$', f)]
    if not c: raise FileNotFoundError(f'no video_only.mp4 or finished *.mp4 in {d}')
    return max(c, key=os.path.getmtime), None, False


# ---------------------------------------------------------------- media helpers
def probe(path):
    p = json.loads(subprocess.run(['ffprobe', '-v', 'error', '-show_streams', '-show_format', '-of', 'json', path],
                                  capture_output=True, text=True, check=True).stdout)
    v = next(s for s in p['streams'] if s['codec_type'] == 'video')
    num, den = (v.get('r_frame_rate') or '24/1').split('/')
    return dict(w=int(v['width']), h=int(v['height']), fps=float(num) / float(den or 1),
                dur=float(p['format'].get('duration') or v.get('duration') or 0),
                audio=any(s['codec_type'] == 'audio' for s in p['streams']))


def sample_frames(path, n, dur, sw, sh, small=160):
    """n grey frames, evenly spaced, at `small` px on the long side -> (frames float32 (n,h,w), times, scale)."""
    k = small / max(sw, sh); w, h = max(2, even(sw * k)), max(2, even(sh * k))
    rate = n / max(dur, 0.1)
    raw = subprocess.run(['ffmpeg', '-v', 'error', '-i', path, '-vf', f'fps={rate:.6f},scale={w}:{h},format=gray',
                          '-f', 'rawvideo', '-'], capture_output=True, check=True).stdout
    m = len(raw) // (w * h)
    fr = np.frombuffer(raw[:m * w * h], np.uint8).reshape(m, h, w).astype(np.float32) / 255.0
    times = (np.arange(m) + 0.5) / rate
    return fr, times, (w / sw)


def detect_faces(frames):
    try: import cv2
    except Exception: return None
    xml = os.path.join(getattr(cv2, 'data', None).haarcascades if hasattr(cv2, 'data') else '', 'haarcascade_frontalface_default.xml')
    if not os.path.exists(xml): return None
    cc = cv2.CascadeClassifier(xml); out = []
    for f in frames:
        g = (f * 255).astype(np.uint8)
        out.append([tuple(map(int, r)) for r in cc.detectMultiScale(g, 1.1, 4, minSize=(max(8, g.shape[1] // 20),) * 2)])
    return out


def paper_texture(W, H, path, seed=7):
    from PIL import Image
    r = np.random.default_rng(seed)
    base = np.array([243, 236, 222], np.float32)
    n = r.normal(0, 1, (H // 4 + 1, W // 4 + 1)).astype(np.float32)
    n = np.kron(n, np.ones((4, 4), np.float32))[:H, :W]
    fib = r.normal(0, 1, (H, W)).astype(np.float32)
    for _ in range(3): fib = (fib + np.roll(fib, 1, 1) + np.roll(fib, 2, 1)) / 3   # horizontal fibre streaks
    yy, xx = np.mgrid[0:H, 0:W]; vig = 1 - 0.18 * (((xx - W / 2) / (W / 2)) ** 2 + ((yy - H / 2) / (H / 2)) ** 2)
    img = (base[None, None, :] + (n * 5 + fib * 7)[..., None]) * vig[..., None]
    Image.fromarray(np.clip(img, 0, 255).astype(np.uint8)).save(path)


def font(size, kind='baloo2'):
    from PIL import ImageFont
    for f in (os.path.join(FONTS, f'{kind}.ttf'), os.path.join(FONTS, 'baloo2.ttf')):
        if os.path.exists(f): return ImageFont.truetype(f, size)
    return ImageFont.load_default()


def decor_layer(W, H, fw, fh, path, title=None, subtitle=None, handle=None, dark_text=False, shadow=True):
    """RGBA overlay drawn UNDER the centred video: soft drop shadow + side title panel text."""
    from PIL import Image, ImageDraw, ImageFilter
    im = Image.new('RGBA', (W, H), (0, 0, 0, 0)); x0, y0 = (W - fw) // 2, (H - fh) // 2
    if shadow:
        sh = Image.new('L', (W, H), 0); ImageDraw.Draw(sh).rounded_rectangle([x0 - 6, y0 + 10, x0 + fw + 6, y0 + fh + 18], 18, fill=150)
        sh = sh.filter(ImageFilter.GaussianBlur(22)); im.paste(Image.new('RGBA', (W, H), (0, 0, 0, 255)), (0, 0), sh)
    D = ImageDraw.Draw(im); ink = (40, 32, 26, 255) if dark_text else (255, 255, 255, 255)
    halo = (255, 255, 255, 0) if dark_text else (0, 0, 0, 170); pw = x0 - 2 * 56
    if pw > 160 and (title or subtitle):
        y = H * 0.36; fs = 92 if pw > 500 else 64
        for ln in wrap_words(title or '', max(6, int(pw / (fs * 0.5)))):
            f = font(fs); D.text((56, y), ln, font=f, fill=ink, stroke_width=0 if dark_text else 4, stroke_fill=halo); y += fs * 1.05
        if subtitle:
            y += 14; fs2 = 44
            for ln in wrap_words(subtitle, max(8, int(pw / (fs2 * 0.5)))):
                D.text((58, y), ln, font=font(fs2, 'caveat'), fill=ink, stroke_width=0 if dark_text else 2, stroke_fill=halo); y += fs2 * 1.15
    if handle and pw > 160:
        f = font(44); tw = D.textlength(handle, font=f)
        D.text((W - 56 - tw, H - 120), handle, font=f, fill=ink, stroke_width=0 if dark_text else 3, stroke_fill=halo)
    im.save(path)


def captions_file(cap, W, H, tmpd, style=None, project=None):
    """words.json -> fresh .ass via scripts/captions.py ; .ass -> retargeted copy ; .srt -> as is.
    Caption look: explicit style/preset, else the project's look.captions_preset, else the legacy 'pop'."""
    ext = os.path.splitext(cap)[1].lower()
    if ext == '.json':
        out = os.path.join(tmpd, f'cap_{W}x{H}.ass')
        how = ['--style', style] if style else None
        if not how and project and os.path.exists(os.path.join(project, 'project.json')):
            try: lk = json.load(open(os.path.join(project, 'project.json'), encoding='utf-8')).get('look') or {}
            except Exception: lk = {}
            if isinstance(lk, dict) and lk.get('captions_preset'): how = ['--project', project]
        how = how or ['--style', 'pop']
        subprocess.run([sys.executable, os.path.join(HERE, 'captions.py'), cap, out, '--w', str(W), '--h', str(H), *how], check=True,
                       capture_output=True)
        return out
    if ext == '.ass':
        t = open(cap, encoding='utf-8-sig').read()
        if re.search(r'\\(pos|move)\(', t): print('note: captions use \\pos/\\move; those lines keep source coordinates', file=sys.stderr)
        out = os.path.join(tmpd, f'cap_{W}x{H}.ass'); open(out, 'w', encoding='utf-8').write(retarget_ass(t, W, H)); return out
    if ext == '.srt': return cap
    raise ValueError(f'captions must be words.json, .ass or .srt, got {cap}')


def esc_path(p): return p.replace('\\', '/').replace(':', '\\:').replace("'", "\\'")


def encode(inputs, fgraph, out_label, audio_src, dst, dur, crf=18):
    tmp = os.path.join(tempfile.gettempdir(), f'reframe_{os.getpid()}_{os.path.basename(dst)}')
    cmd = ['ffmpeg', '-y', '-loglevel', 'error']
    for i in inputs: cmd += i
    cmd += ['-filter_complex', fgraph, '-map', out_label]
    if audio_src is not None: cmd += ['-map', f'{audio_src}:a:0', '-c:a', 'aac', '-b:a', '320k', '-ar', '48000']
    cmd += ['-t', f'{dur:.3f}', '-c:v', 'libx264', '-preset', 'medium', '-crf', str(crf), '-profile:v', 'high', '-pix_fmt', 'yuv420p',
            '-color_primaries', 'bt709', '-color_trc', 'bt709', '-colorspace', 'bt709', '-movflags', '+faststart', tmp]
    subprocess.run(cmd, check=True); shutil.copyfile(tmp, dst); os.remove(tmp)


def look_frame(mp4, t, jpg):
    subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-ss', f'{t:.2f}', '-i', mp4, '-frames:v', '1', '-q:v', '3', jpg], check=True)


# ---------------------------------------------------------------- main
def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('src', help='finished 9:16 mp4, or a project dir'); ap.add_argument('--to', default='16x9,1x1')
    ap.add_argument('-o', '--outdir'); ap.add_argument('--stem')
    ap.add_argument('--bg', default='blur', choices=['blur', 'paper']); ap.add_argument('--bg-image')
    ap.add_argument('--title'); ap.add_argument('--subtitle'); ap.add_argument('--handle')
    ap.add_argument('--crop', default='static', choices=['static', 'track']); ap.add_argument('--samples', type=int, default=32)
    ap.add_argument('--caption-zone', help='a,b fractions of source height to keep inside a crop (burned captions)')
    ap.add_argument('--captions', help='words.json | .ass | .srt to (re-)burn at the new size')
    ap.add_argument('--caption-style', default=None, help="pop | karaoke | a preset (docs/TEXT_STYLES.md); default: project look.captions_preset, else pop"); ap.add_argument('--no-recaption', action='store_true')
    ap.add_argument('--audio', help='separate audio file (default: the source audio)'); ap.add_argument('--crf', type=int, default=18)
    A = ap.parse_args(argv)
    src, audio, cap = A.src, A.audio, A.captions
    proj_dir = src if os.path.isdir(src) else None
    if os.path.isdir(src):
        d = src; src, pa, clean = project_sources(d); audio = audio or pa
        wj = os.path.join(d, 'words.json')
        if clean and not cap and not A.no_recaption and os.path.exists(wj): cap = wj
        stem = A.stem or (json.load(open(os.path.join(d, 'project.json'))).get('slug') if os.path.exists(os.path.join(d, 'project.json')) else None) or os.path.basename(os.path.abspath(d))
        outdir = A.outdir or d
    else:
        stem = A.stem or re.sub(r'_(9x16|vertical|reel)$', '', os.path.splitext(os.path.basename(src))[0]); outdir = A.outdir or os.path.dirname(os.path.abspath(src))
    os.makedirs(outdir, exist_ok=True)
    info = probe(src); sw, sh, dur = info['w'], info['h'], info['dur']
    ainputs = [['-i', audio]] if audio else []
    tmpd = tempfile.mkdtemp(prefix='reframe_'); made = []
    zone = None
    if A.caption_zone:
        a, b = [float(x) for x in A.caption_zone.split(',')]; zone = (a, b)
    try:
        for asp in parse_aspects(A.to):
            W, H = SIZES[asp]; inputs = [['-i', src]] + ainputs
            asrc = 1 if audio else (0 if info['audio'] else None)
            fw, fh = fit_inside(sw, sh, W, H); pillar = (fw < W - 8 or fh < H - 8)
            if asp == '1x1' or not pillar:
                # ---- subject-aware crop
                cw, ch, axis = cover_scale(sw, sh, W, H)
                if axis == 'y' and ch > H or axis == 'x' and cw > W:
                    fr, times, k = sample_frames(src, A.samples, dur, sw, sh)
                    emap = energy_maps(fr, detect_faces(fr))
                    if zone and axis == 'y':   # don't let caption text pull the crop; the zone rule keeps it in instead
                        a0, b0 = int(zone[0] * emap.shape[1]), int(zone[1] * emap.shape[1]); emap[:, a0:b0] *= 0.25
                    n_small = emap.shape[1] if axis == 'y' else emap.shape[2]
                    n_big = ch if axis == 'y' else cw; win_big = H if axis == 'y' else W
                    win_small = max(1, int(round(win_big * n_small / n_big)))
                    prof = emap.sum(axis=2) if axis == 'y' else emap.sum(axis=1)
                    starts = np.array([subject_window(p, win_small) for p in prof], float) * (n_big / n_small)
                    zpx = (zone[0] * ch, zone[1] * ch) if (zone and axis == 'y') else None
                    if A.crop == 'static':
                        wts = prof.sum(axis=1) + 1e-6; order = np.argsort(starts); cum = np.cumsum(wts[order])
                        s0 = constrain_window(starts[order][np.searchsorted(cum, cum[-1] / 2)], win_big, n_big, zpx)
                        pos = f'{s0}'
                    else:
                        tr = smooth_track(starts, max_step=0.08 * win_big)
                        tr = [constrain_window(v, win_big, n_big, zpx) for v in tr]
                        pos = "'" + piecewise_expr(times, tr) + "'"
                    cx, cy = (pos, '0') if axis == 'x' else ('0', pos)
                else:
                    cx, cy = '0', '0'
                g = f'[0:v]scale={cw}:{ch}:flags=lanczos,crop={W}:{H}:{cx}:{cy},setsar=1[v]'
            else:
                # ---- centred over blurred self / paper, optional title panel
                dec = os.path.join(tmpd, f'decor_{asp}.png')
                darkt = A.bg == 'paper' or bool(A.bg_image)
                decor_layer(W, H, fw, fh, dec, A.title, A.subtitle, A.handle, dark_text=darkt)
                if A.bg == 'paper' or A.bg_image:
                    tex = A.bg_image or os.path.join(tmpd, 'paper.png')
                    if not A.bg_image: paper_texture(W, H, tex)
                    inputs.insert(1, ['-loop', '1', '-i', tex]); bi = 1
                    asrc = (asrc + 1) if (asrc is not None and asrc >= 1) else asrc
                    bg = f'[{bi}:v]scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},setsar=1[bg]'
                else:
                    bg = (f'[0:v]scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},gblur=sigma=40,'
                          f'eq=brightness=-0.10:saturation=0.85,setsar=1[bg]')
                inputs.append(['-loop', '1', '-i', dec]); di = len(inputs) - 1
                g = (f'{bg};[0:v]scale={fw}:{fh}:flags=lanczos,setsar=1[fg];[{di}:v]format=rgba[dec];'
                     f'[bg][dec]overlay=0:0:shortest=0[b2];[b2][fg]overlay=(W-w)/2:(H-h)/2:shortest=1[v]')
            if cap:
                cf = captions_file(cap, W, H, tmpd, A.caption_style, proj_dir)
                flt = f"ass='{esc_path(cf)}':fontsdir='{esc_path(FONTS)}'" if cf.endswith('.ass') else f"subtitles='{esc_path(cf)}':fontsdir='{esc_path(FONTS)}'"
                g = g[:-3] + f'[v0];[v0]{flt}[v]'
            dst = os.path.join(outdir, f'{stem}_{asp}.mp4')
            encode(inputs, g, '[v]', asrc, dst, dur, A.crf)
            jpg = dst[:-4] + '.jpg'; look_frame(dst, min(dur * 0.4, max(dur - 0.1, 0)), jpg)
            made.append(dst); print(f'{asp} {W}x{H} -> {dst}  (look: {jpg})')
    finally:
        shutil.rmtree(tmpd, ignore_errors=True)
    return made


if __name__ == '__main__':
    main()
