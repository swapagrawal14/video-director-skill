"""Music-loop mode for vid-shark: beat-driven motion, exported as seamless loops.

No voiceover. The music is the clock: every pop, squash, cut and camera nudge lands on
the beat, and the clip ends exactly where it began, so Instagram / Pinterest / Shorts
replay it forever without a visible jump (the motion-doodle reel look). The engine:
  * Beat: a steady beat grid (bpm + offset, or straight from scripts/beats.py JSON) with
    phase, sharp 1->0 pulses on every beat / bar, snapping and per-frame hit tests,
  * loop_len / loop_t / cyc / csin / ccos / keyed: timing helpers that make every periodic
    motion close exactly at the loop length L,
  * seamless_check / assert_seamless: measure the seam (frame 0 vs the frame at t = L),
  * crossfade_loop: fallback blend for content that can't be made periodic,
  * export_loop: mp4 (yuv420p, faststart) / gif (palettegen + paletteuse) / webm, optional
    repeats and an audio bed trimmed to the exact length with a tiny fade at the seam,
  * music_for_loop: cut L seconds of a music bed starting on a bar.

Typical use:
    from loop import Beat, loop_len, cyc, csin, export_loop, music_for_loop, assert_seamless
    B = Beat.from_json('beats.json')                 # or Beat(bpm=120)
    L = loop_len(B.bpm, bars=2)                      # 2 bars @120 = 4.0 s
    N = round(L * FPS)                               # render frames t = i / FPS, i in 0..N-1
    s = 1 + 0.12 * B.pulse(t)                        # pop on every beat
    y = 40 * csin(t, L, k=2)                         # bob, twice per loop, closes at L
    if B.hit(t, 'bar', fps=FPS): flash = 1           # cut / flash on the bar
    assert_seamless(render(0.0), render(L))          # frame at L must equal frame 0
    music_for_loop('music.wav', L, 'loop.wav', beats_json='beats.json', after=4.0)
    export_loop(frames, 'reel.mp4', fps=FPS, repeat=3, audio='loop.wav')

THE LOOP RULE: every animated parameter must be periodic in L (built from cyc / csin / ccos
/ loop_t with integer k, or from Beat pulses when L is a whole number of beats), or be
keyed with first value == last value (keyed()). Anything driven by raw t (drifts, zooms,
random seeds per frame) breaks the seam. Render frames at t = i / fps for i < N; the frame
at t = L is NOT exported, it only exists to verify the seam.

Rules of thumb:
  * open on motion: frame 0 is mid-action, never a static title card or a fade from black,
  * loop 4-8 s (2-4 bars at 100-128 bpm); L must be a whole number of bars,
  * hit cuts / pops / colour flashes on beats, the big change on the bar (downbeat),
  * verify the seam (assert_seamless) before export; if the content can't be periodic,
    crossfade_loop the last few frames into the first,
  * scripts/music.py beds fade in over the first ~1.5 s and kicks start at 4 s: cut the loop
    music from after the intro (music_for_loop(..., after=4.0)).
Frames are BGR uint8 numpy arrays (cv2 / motion.ffmpeg_writer convention). Raster only, never SVG.
Credit: Swapnil Agrawal (BDS intern).
"""
import glob, json, math, os, shutil, subprocess, tempfile
import numpy as np, cv2

TAU = 2 * math.pi


# ---------------------------------------------------------------- beat grid
class Beat:
    """Steady beat grid. t in seconds; beat index 0 sits at `offset`, bars start every
    `beats_per_bar` beats from `offset`. Lists from beats.py are kept for snap/hit on
    detected onsets and hits; beat/bar maths stay on the steady grid so loops close."""

    def __init__(self, bpm=120, offset=0.0, beats_per_bar=4, onsets=None, hits=None, beats=None, bars=None):
        if bpm <= 0: raise ValueError('bpm must be > 0')
        self.bpm, self.offset, self.bpb = float(bpm), float(offset), int(beats_per_bar)
        self.period = 60.0 / self.bpm
        self.onsets = sorted(onsets or []); self.hits = sorted(hits or [])
        self.beats = list(beats or []); self.bars = list(bars or [])

    @classmethod
    def from_json(cls, path, beats_per_bar=4):
        """Load scripts/beats.py output. offset = first detected bar (downbeat), else first beat."""
        J = json.load(open(path))
        off = (J.get('bars') or J.get('beats') or [0.0])[0]
        return cls(bpm=J['bpm'], offset=off, beats_per_bar=beats_per_bar, onsets=J.get('onsets'),
                   hits=J.get('hits'), beats=J.get('beats'), bars=J.get('bars'))

    @property
    def bar_len(self): return self.period * self.bpb

    def beat_at(self, t):
        """float beat index at time t (integer on each beat)"""
        return (t - self.offset) / self.period

    def phase(self, t):
        """0..1 position inside the current beat (0 exactly on the beat)"""
        b = self.beat_at(t); p = b - math.floor(b)
        return 0.0 if p > 1 - 1e-9 else p

    def bar_phase(self, t):
        b = self.beat_at(t) / self.bpb; p = b - math.floor(b)
        return 0.0 if p > 1 - 1e-9 else p

    def pulse(self, t, decay=8.0):
        """sharp envelope: 1 on each beat, exp(-decay * phase) down to ~0 before the next"""
        return math.exp(-decay * self.phase(t))

    def bar_pulse(self, t, decay=8.0):
        """1 on each downbeat; decays per beat-length (same speed as pulse), silent rest of bar"""
        return math.exp(-decay * self.bar_phase(t) * self.bpb)

    def beat_time(self, n): return self.offset + n * self.period

    def snap(self, t):
        """nearest beat time on the grid"""
        return self.beat_time(round(self.beat_at(t)))

    def beats_between(self, t0, t1):
        """beat times in [t0, t1)"""
        n0 = math.ceil(self.beat_at(t0) - 1e-9); out = []
        while self.beat_time(n0) < t1 - 1e-9:
            out.append(self.beat_time(n0)); n0 += 1
        return out

    def bars_between(self, t0, t1):
        return [b for b in self.beats_between(t0, t1) if round(self.beat_at(b)) % self.bpb == 0]

    def hit(self, t, kind='beat', fps=24):
        """True if an event of `kind` ('beat' | 'bar' | 'onset' | 'hit') falls in this frame's
        window [t, t + 1/fps). Use it to fire one-frame cuts / flashes / pops."""
        t1 = t + 1.0 / fps
        if kind == 'beat': return bool(self.beats_between(t, t1))
        if kind == 'bar': return bool(self.bars_between(t, t1))
        if kind in ('onset', 'hit'):
            ev = self.onsets if kind == 'onset' else self.hits
            return any(t - 1e-9 <= e < t1 - 1e-9 for e in ev)
        raise ValueError(f"kind must be 'beat', 'bar', 'onset' or 'hit', got {kind!r}")


# ---------------------------------------------------------------- loop timing
def loop_len(bpm, bars, beats_per_bar=4):
    """seconds for `bars` bars at `bpm`"""
    return bars * beats_per_bar * 60.0 / bpm

def loop_t(t, L): return t % L

def cyc(t, L, k=1):
    """angle 2*pi*k*t/L. Integer k => any sin/cos of it closes exactly at L."""
    if abs(k - round(k)) > 1e-9: raise ValueError('k must be an integer or the loop will not close')
    return TAU * k * t / L

def csin(t, L, k=1, phase=0.0): return math.sin(cyc(t, L, k) + phase)
def ccos(t, L, k=1, phase=0.0): return math.cos(cyc(t, L, k) + phase)
def cnorm(t, L, k=1, phase=0.0):
    """0..1 periodic wave (0.5 - 0.5 cos), starts at 0"""
    return 0.5 - 0.5 * ccos(t, L, k, phase)
def ctri(t, L, k=1):
    """0..1..0 triangle wave, k times per loop"""
    u = (k * t / L) % 1.0
    return 1 - abs(2 * u - 1)

def keyed(t, L, values, ease=True):
    """evenly spaced keys over the loop, values[0] must equal values[-1]. Smoothstep between keys."""
    if len(values) < 2: raise ValueError('need at least 2 keys')
    if not np.allclose(np.asarray(values[0], float), np.asarray(values[-1], float)):
        raise ValueError('keyed loop: first key must equal last key or the loop will jump')
    u = (t % L) / L * (len(values) - 1); i = min(int(u), len(values) - 2); f = u - i
    if ease: f = f * f * (3 - 2 * f)
    a, b = np.asarray(values[i], float), np.asarray(values[i + 1], float)
    v = a + (b - a) * f
    return float(v) if v.ndim == 0 else v


# ---------------------------------------------------------------- seam
def _arr(fr):
    a = np.asarray(fr)
    if a.ndim == 2: a = a[..., None]
    return a.astype(np.float32)

def seamless_check(first_frame, last_plus_one_frame):
    """mean abs difference (0..1) between frame 0 and the frame rendered at t = L.
    ~0 = perfect seam; > ~0.02 is a visible jump on most content."""
    a, b = _arr(first_frame), _arr(last_plus_one_frame)
    if a.shape != b.shape: raise ValueError(f'frame shapes differ: {a.shape} vs {b.shape}')
    return float(np.abs(a - b).mean() / 255.0)

def assert_seamless(first_frame, last_plus_one_frame, threshold=0.02):
    s = seamless_check(first_frame, last_plus_one_frame)
    if s > threshold:
        raise AssertionError(f'loop seam is visible: mean abs diff {s:.4f} > {threshold} between frame 0 and '
                             f'the frame at t=L. Make every animated parameter periodic in L (cyc/csin/keyed) '
                             f'or use crossfade_loop() as a fallback.')
    return s

def crossfade_loop(frames_list, n):
    """Fallback seam: the last n frames blend into the first n. Returns len-n frames whose
    end flows into its start. out[i] (i<n) = mix(frames[len-n+i], frames[i], i/n)."""
    N = len(frames_list)
    if n <= 0: return list(frames_list)
    if 2 * n > N: raise ValueError(f'crossfade n={n} too long for {N} frames (need n <= len/2)')
    out = []
    for i in range(N - n):
        if i < n:
            w = i / n; a = frames_list[N - n + i].astype(np.float32); b = frames_list[i].astype(np.float32)
            out.append(np.clip(a * (1 - w) + b * w + 0.5, 0, 255).astype(np.uint8))
        else:
            out.append(frames_list[i])
    return out


# ---------------------------------------------------------------- export
def _ffmpeg_has(encoder):
    r = subprocess.run(['ffmpeg', '-hide_banner', '-encoders'], capture_output=True, text=True)
    return f' {encoder} ' in r.stdout

def _load_frames(frames_or_dir):
    if isinstance(frames_or_dir, (str, os.PathLike)):
        paths = sorted(glob.glob(os.path.join(frames_or_dir, '*.png')) + glob.glob(os.path.join(frames_or_dir, '*.jpg')))
        if not paths: raise FileNotFoundError(f'no .png/.jpg frames in {frames_or_dir}')
        return [cv2.imread(p, cv2.IMREAD_COLOR) for p in paths]
    fr = list(frames_or_dir)
    if not fr: raise ValueError('no frames')
    out = []
    for f in fr:
        a = np.asarray(f)
        if a.ndim == 2: a = cv2.cvtColor(a, cv2.COLOR_GRAY2BGR)
        elif a.shape[2] == 4: a = a[..., :3]
        out.append(np.ascontiguousarray(a, dtype=np.uint8))
    return out

def export_loop(frames_or_dir, out_path, fps=24, kind=None, repeat=1, audio=None, size=None, crf=20):
    """Write the loop with ffmpeg. frames: list of BGR uint8 arrays or a dir of PNG/JPG frames.
    kind: 'mp4' (h264 yuv420p +faststart) | 'gif' (palettegen/paletteuse, loops forever) |
    'webm' (vp9). Default from the extension. repeat: play the loop N times (Reels: 2-3).
    audio: wav/mp3 trimmed (or looped) to exactly one loop, 10 ms fades at the seam, then
    repeated with the picture. Ignored for gif. size: (W, H) output scale. Returns out_path."""
    kind = (kind or os.path.splitext(out_path)[1].lstrip('.') or 'mp4').lower()
    if kind not in ('mp4', 'gif', 'webm'): raise ValueError(f'kind must be mp4, gif or webm, got {kind!r}')
    frames = _load_frames(frames_or_dir); H, W = frames[0].shape[:2]
    repeat = max(1, int(repeat)); n = len(frames); L = n / fps; total = L * repeat
    vf = []
    if size: vf.append(f'scale={int(size[0])}:{int(size[1])}:flags=lanczos')
    if kind != 'gif': vf.append('scale=trunc(iw/2)*2:trunc(ih/2)*2')     # yuv420p needs even sides
    cmd = ['ffmpeg', '-y', '-loglevel', 'error', '-f', 'rawvideo', '-pix_fmt', 'bgr24', '-s', f'{W}x{H}',
           '-r', str(fps), '-i', '-']
    use_audio = audio is not None and kind != 'gif'
    if use_audio:
        cmd += ['-stream_loop', '-1', '-i', str(audio)]
    if kind == 'gif':
        chain = ','.join(vf + ['split[a][b]']) if vf else 'split[a][b]'
        cmd += ['-filter_complex', f'[0:v]{chain};[a]palettegen=stats_mode=diff[p];'
                                   f'[b][p]paletteuse=dither=bayer:bayer_scale=3:diff_mode=rectangle',
                '-loop', '0', out_path]
    else:
        fc = f'[0:v]{",".join(vf)}[v]'
        if use_audio:
            SR = 48000; ns = int(round(L * SR)); fd = min(0.01, L / 4)
            fc += (f';[1:a]aresample={SR},atrim=end_sample={ns},asetpts=N/SR/TB,'
                   f'afade=t=in:st=0:d={fd},afade=t=out:st={L - fd:.6f}:d={fd},'
                   f'aloop=loop={repeat - 1}:size={ns},atrim=end_sample={ns * repeat}[a]')
        cmd += ['-filter_complex', fc, '-map', '[v]']
        if use_audio: cmd += ['-map', '[a]']
        if kind == 'mp4':
            cmd += ['-c:v', 'libx264', '-preset', 'medium', '-crf', str(crf), '-pix_fmt', 'yuv420p', '-movflags', '+faststart']
            if use_audio: cmd += ['-c:a', 'aac', '-b:a', '192k']
        else:
            enc = 'libvpx-vp9' if _ffmpeg_has('libvpx-vp9') else 'libvpx'
            cmd += ['-c:v', enc, '-b:v', '0', '-crf', str(max(crf, 30)), '-pix_fmt', 'yuv420p']
            if use_audio: cmd += ['-c:a', 'libopus' if _ffmpeg_has('libopus') else 'libvorbis']
        cmd += ['-t', f'{total:.6f}', out_path]
    p = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        for _ in range(repeat):
            for f in frames:
                if f.shape[:2] != (H, W): raise ValueError('all frames must share one size')
                p.stdin.write(f.tobytes())
        p.stdin.close()
    except BrokenPipeError:
        pass
    err = p.stderr.read().decode(errors='replace'); p.wait()
    if p.returncode != 0: raise RuntimeError(f'ffmpeg failed ({kind}): {err.strip()}')
    return out_path


def _duration(path):
    r = subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', path],
                       capture_output=True, text=True)
    return float(r.stdout.strip())

def music_for_loop(wav, L, out, beats_json=None, start=None, after=0.0, fade=0.01):
    """Cut exactly L seconds of `wav` into `out`, starting on a bar from beats.json (first bar
    at or after `after` that still leaves L seconds), with `fade` (10 ms) in/out so the seam
    doesn't click. Without beats_json starts at `start` (or `after`). Returns the start time."""
    dur = _duration(wav)
    if start is None:
        start = after
        if beats_json:
            bars = json.load(open(beats_json)).get('bars') or []
            ok = [b for b in bars if b >= after - 1e-6 and b + L <= dur + 1e-6]
            if ok: start = ok[0]
            else:
                fit = [b for b in bars if b + L <= dur + 1e-6]
                start = fit[-1] if fit else 0.0
    if start + L > dur + 1e-6: start = max(0.0, dur - L)
    fd = min(fade, L / 4)
    cmd = ['ffmpeg', '-y', '-loglevel', 'error', '-ss', f'{start:.6f}', '-i', wav, '-t', f'{L:.6f}',
           '-af', f'afade=t=in:st=0:d={fd},afade=t=out:st={L - fd:.6f}:d={fd}', out]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0: raise RuntimeError(f'ffmpeg failed cutting music: {r.stderr.strip()}')
    return float(start)
