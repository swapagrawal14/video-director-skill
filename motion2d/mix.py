"""VO-led, loudness-aware audio mix for any vid-shark video (generalised from examples/zebra/audio_mix.py).

The voiceover is the lead; everything else sits under it:
  * VO stem normalised ALONE to -16 LUFS (gentle comp + brickwall so true peaks stay under the master limit).
  * Beds (music, ambience) at their own LUFS target (~-30), faded in, ducked under the VO.
  * Every SFX normalised to its OWN loudness target. The gain is measured on the WHOLE clip (short clips are
    padded to one 400 ms BS.1770 block), THEN it is trimmed to max_len with a short fade. Measuring after the
    trim is unreliable: a 0.3 s horn can't be gated properly.
  * Sidechain ducking from a VO energy envelope (80 ms attack / 300 ms release): each bus has its own duck dB
    (music/ambience/horns/whooshes ~10 dB, Foley ~6 dB).
  * Master: sit the mix at -16 LUFS with a brickwall around -2.5 dBFS so the mux-time two-pass loudnorm needs
    ~0 dB gain and stays LINEAR (dynamic loudnorm pumps the VO).
  * verify(): VO vs bed loudness inside the VO windows (gap must be >= 10 dB) + final numbers; check() turns
    them into pass/fail lines for the QA gates in AGENTS.md.

Loudness is measured with ffmpeg's ebur128 (BS.1770) on temp wavs: no extra Python deps.

    from mix import Mix, verify, check, loudnorm_filter
    m = Mix(dur=18.0)
    m.vo('audio/vo.wav', at=1.0)                                   # or segments=[((a, b), at), ...]
    m.bed('audio/music.wav', lufs=-30, duck_db=10)
    m.bed('audio/ambience.wav', lufs=-31, duck_db=10)
    m.sfx(3.2, 'audio/horn_car.wav', lufs=-31, max_len=0.35, duck_db=10)
    m.sfx(4.0, 'audio/pour.wav', lufs=-27, duck_db=6)
    vo, bed, env = m.render('mix.wav', stems_dir='stems')
    ln, meas = loudnorm_filter('mix.wav')                          # use as -af when muxing
    print(check(verify(vo, bed, env, 'mix_loudnormed.wav')))

CLI (QA gate on existing stems / a final file):
    python3 engine/mix.py verify stems/vo.wav stems/bed.wav [final.wav|final.mp4]
    python3 engine/mix.py loudnorm mix.wav           # prints the linear two-pass filter + checks it stays linear
"""
import os, re, sys, json, wave, subprocess, tempfile
import numpy as np

SR = 44100
T_VO = -16.0
MIN_GAP_DB = 10.0           # VO must sit at least this far above the bed inside VO windows
TARGET_I, TARGET_TP = -16.0, -1.5


# ---------------------------------------------------------------- io + measurement
def read(path):
    """mono float32 @ SR from any audio/video file (wav fast path, else ffmpeg decode)"""
    if path.lower().endswith('.wav'):
        try:
            w = wave.open(path)
            if w.getsampwidth() == 2 and w.getframerate() == SR:
                a = np.frombuffer(w.readframes(w.getnframes()), np.int16).astype(np.float32) / 32768
                return a if w.getnchannels() == 1 else a.reshape(-1, w.getnchannels()).mean(1)
        except wave.Error:
            pass
    raw = subprocess.check_output(['ffmpeg', '-v', 'error', '-i', path, '-vn', '-f', 'f32le', '-ac', '1', '-ar', str(SR), '-'])
    return np.frombuffer(raw, np.float32).copy()


def write(path, a):
    with wave.open(path, 'wb') as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR)
        w.writeframes((np.clip(a, -1, 1) * 32767).astype(np.int16).tobytes())


def lufs(a):
    """(integrated LUFS, true peak dBFS) of a mono float array via ffmpeg ebur128"""
    if len(a) == 0 or np.abs(a).max() < 1e-6: return -120.0, -120.0
    if len(a) < int(0.5 * SR): a = np.pad(a, (0, int(0.5 * SR) - len(a)))   # BS.1770 needs >= one 400 ms block
    with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as f: p = f.name
    write(p, a)
    out = subprocess.run(['ffmpeg', '-hide_banner', '-nostats', '-i', p, '-af', 'ebur128=peak=true', '-f', 'null', '-'],
                         capture_output=True, text=True).stderr
    os.unlink(p)
    summ = out[out.rindex('Summary:'):]
    I = float(re.search(r'I:\s+(-?[\d.]+|-inf) LUFS', summ).group(1).replace('-inf', '-120'))
    pk = float(re.search(r'Peak:\s+(-?[\d.]+|-inf) dBFS', summ).group(1).replace('-inf', '-120'))
    return I, pk


def ffilter(a, af):
    """run a mono float array through an ffmpeg audio filter chain (length preserved)"""
    with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as f: p = f.name
    q = p[:-4] + '_o.wav'; write(p, a)
    subprocess.run(['ffmpeg', '-y', '-v', 'error', '-i', p, '-af', af, '-ar', str(SR), '-ac', '1', q], check=True)
    b = read(q); os.unlink(p); os.unlink(q)
    return np.pad(b, (0, max(0, len(a) - len(b))))[:len(a)]


def to_lufs(a, target):
    I, _ = lufs(a)
    return a if I <= -119 else a * 10 ** ((target - I) / 20)


def fade(a, fin=0.01, fout=0.01):
    a = a.copy(); fi, fo = int(fin * SR), int(fout * SR)
    if fi and len(a) > fi: a[:fi] *= np.linspace(0, 1, fi)
    if fo and len(a) > fo: a[-fo:] *= np.linspace(1, 0, fo) ** 2
    return a


def prepare_clip(a, target_lufs, max_len=None, tail_fade=0.06):
    """per-SFX loudness: gain from the WHOLE clip (lufs() pads short clips), then trim to max_len + fade"""
    a = to_lufs(a, target_lufs)
    if max_len and len(a) > max_len * SR:
        a = fade(a[:int(max_len * SR)], 0, tail_fade)
    return a


def place(buf, a, t, g=1.0):
    i = int(max(0, t) * SR); L = min(len(a), len(buf) - i)
    if L > 0: buf[i:i + L] += a[:L] * g


def vo_envelope(vo, thresh_db=-38, att=0.080, rel=0.300):
    """0..1 'VO is speaking' control: 5 ms RMS frames above (peak + thresh_db), one-pole attack/release.
    Returns (env per sample, gate per hop, hop)."""
    hop = int(0.005 * SR); n = len(vo) // hop + 1
    pad = np.pad(vo, (0, n * hop - len(vo)))
    rms = np.sqrt((pad.reshape(n, hop) ** 2).mean(1) + 1e-12); db = 20 * np.log10(rms)
    gate = (db > db.max() + thresh_db).astype(np.float32)
    ka, kr = 1 - np.exp(-hop / SR / att), 1 - np.exp(-hop / SR / rel)
    env = np.zeros(n, np.float32); e = 0.0
    for i in range(n):
        g = gate[i]; e += (ka if g > e else kr) * (g - e); env[i] = e
    return np.interp(np.arange(len(vo)), np.arange(n) * hop, env).astype(np.float32), gate, hop


def normalise_vo(vo, target=T_VO, passes=2):
    """VO stem alone to target LUFS; gentle comp + brickwall so true peaks stay low enough to master"""
    vo = to_lufs(vo, target)
    for _ in range(passes):
        vo = ffilter(vo, 'acompressor=threshold=-18dB:ratio=3:attack=5:release=120:makeup=1,'
                         'alimiter=limit=0.70:attack=1:release=60:level=false')
        vo = to_lufs(vo, target)
    return vo


def ln_measure(a, I=TARGET_I, TP=TARGET_TP, LRA=20):
    """(integrated LUFS, true peak dBTP) exactly as ffmpeg loudnorm pass 1 sees them (it can read ~0.2-0.9 LU
    lower than ebur128 on VO-led mixes, which is what pushes the final pass into dynamic mode)"""
    with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as f: p = f.name
    write(p, a)
    out = subprocess.run(['ffmpeg', '-hide_banner', '-i', p, '-af', f'loudnorm=I={I}:TP={TP}:LRA={LRA}:print_format=json',
                          '-f', 'null', '-'], capture_output=True, text=True).stderr
    os.unlink(p); d = json.loads(out[out.rindex('{'):out.rindex('}') + 1])
    return float(d['input_i']), float(d['input_tp'])


def master(mix, target=T_VO, limit=0.72, passes=6, tp=TARGET_TP, margin=0.4):
    """bring the full mix to target LUFS behind a brickwall; returns (mix, total linear gain applied).
    Measured the way the mux-time loudnorm measures (ln_measure). Stops when that pass would need < 0.3 dB of
    gain AND the true peak after it stays under tp - margin, so the final two-pass loudnorm stays LINEAR.
    If peaks are too hot the brickwall is lowered a little each pass."""
    g = 1.0
    for _ in range(passes):
        I, pk = ln_measure(mix)
        need = target - I
        if abs(need) <= 0.3 and pk + need <= tp - margin: break
        k = 10 ** (need / 20); mix = mix * k; g *= k
        if pk + need > tp - margin: limit *= 0.94
        mix = ffilter(mix, f'alimiter=limit={limit:.3f}:attack=1:release=50:level=false')
    return mix, g


# ---------------------------------------------------------------- builder
class Mix:
    """Collect a VO, beds and SFX on a timeline, then render() a VO-led ducked mix + stems."""

    def __init__(self, dur, vo_target=T_VO):
        self.dur, self.N, self.vo_target = dur, int(dur * SR), vo_target
        self._vo, self._beds, self._sfx, self._cache = None, [], [], {}

    def _load(self, src):
        if isinstance(src, np.ndarray): return src.astype(np.float32)
        if src not in self._cache: self._cache[src] = read(src)
        return self._cache[src]

    def vo(self, src, at=0.0, segments=None, pre=0.05, post=0.15):
        """src: path/array. segments: [((a, b), at), ...] to re-time phrases (seconds in src -> seconds in cut)."""
        v = self._load(src); buf = np.zeros(self.N, np.float32)
        if segments:
            for (a, b), t in segments:
                seg = fade(v[int(max(0, a - pre) * SR):int(min(len(v) / SR, b + post) * SR)])
                place(buf, seg, t - pre)
        else:
            place(buf, v, at)
        self._vo = buf
        return self

    def bed(self, src, lufs=-30.0, duck_db=10.0, at=0.0, fade_in=0.4, gain_curve=None, loop=True):
        """music/ambience bed. gain_curve: optional fn(t array) -> linear gain (level changes at a cut)."""
        self._beds.append((src, lufs, duck_db, at, fade_in, gain_curve, loop))
        return self

    def sfx(self, t, src, lufs=-30.0, max_len=None, gain=1.0, duck_db=6.0):
        """one SFX hit. lufs = target loudness of the clip itself; gain <= 1 for relative accents."""
        self._sfx.append((t, src, lufs, max_len, min(1.0, gain), duck_db))
        return self

    def render(self, out_path=None, stems_dir=None):
        """returns (vo_stem, bed_stem, env) after mastering; writes out_path + stems/vo.wav, stems/bed.wav"""
        assert self._vo is not None, 'call vo() first: the VO leads the mix'
        N = self.N; tt = np.arange(N) / SR
        vo = normalise_vo(self._vo, self.vo_target)
        env, _, _ = vo_envelope(vo)
        buses = {}                                          # duck_db -> buffer
        for src, tgt, dd, at, fi, curve, loop in self._beds:
            a = self._load(src)
            if loop and len(a) and len(a) < N: a = np.tile(a, N // len(a) + 1)
            b = np.zeros(N, np.float32); place(b, a, at)
            b = to_lufs(b, tgt) * np.clip((tt - at) / max(fi, 1e-3), 0, 1)
            if curve is not None: b = b * curve(tt)
            buses.setdefault(dd, np.zeros(N, np.float32))[:] += b
        clips = {}
        for t, src, tgt, mx, g, dd in self._sfx:
            key = (src if isinstance(src, str) else id(src), tgt, mx)
            if key not in clips: clips[key] = prepare_clip(self._load(src), tgt, mx)
            place(buses.setdefault(dd, np.zeros(N, np.float32)), clips[key], t, g)
        bed = np.zeros(N, np.float32)
        for dd, b in buses.items(): bed += b * 10 ** (-dd * env / 20)
        mix, g = master(vo + bed, self.vo_target)
        vo, bed = vo * g, bed * g
        if out_path: write(out_path, mix)
        if stems_dir:
            os.makedirs(stems_dir, exist_ok=True); write(stems_dir + '/vo.wav', vo); write(stems_dir + '/bed.wav', bed)
        return vo, bed, env


# ---------------------------------------------------------------- final loudnorm + QA
def loudnorm_filter(path, I=TARGET_I, TP=TARGET_TP, LRA=20):
    """two-pass loudnorm, LINEAR. Returns (filter string, pass-1 json).
    LRA must be >= the mix's own range: a VO-led mix with quiet gaps is ~13 LU, and with LRA=11 ffmpeg silently
    falls back to dynamic mode (pumping). Confirm with loudnorm_apply()['normalization_type'] == 'linear'."""
    meas = subprocess.run(['ffmpeg', '-hide_banner', '-i', path, '-vn', '-af', f'loudnorm=I={I}:TP={TP}:LRA={LRA}:print_format=json',
                           '-f', 'null', '-'], capture_output=True, text=True).stderr
    d = json.loads(meas[meas.rindex('{'):meas.rindex('}') + 1])
    lra = max(LRA, float(d['input_lra']) + 1)
    ln = (f"loudnorm=I={I}:TP={TP}:LRA={lra:g}:measured_I={d['input_i']}:measured_TP={d['input_tp']}:measured_LRA={d['input_lra']}"
          f":measured_thresh={d['input_thresh']}:offset={d['target_offset']}:linear=true:print_format=json")
    return ln, d


def loudnorm_apply(src, dst, **kw):
    """apply the two-pass filter to an audio file -> dst wav; returns pass-2 json (check normalization_type)"""
    ln, _ = loudnorm_filter(src, **kw)
    out = subprocess.run(['ffmpeg', '-y', '-hide_banner', '-i', src, '-vn', '-af', ln, '-ar', str(SR), '-ac', '1', dst],
                         capture_output=True, text=True).stderr
    return json.loads(out[out.rindex('{'):out.rindex('}') + 1])


def verify(vo, bed, env=None, final=None):
    """VO-vs-bed gap over the VO windows, bed level in the gaps, final-mix loudness/peak"""
    if env is None: env, _, _ = vo_envelope(vo)
    n = min(len(vo), len(bed), len(env)); vo, bed, env = vo[:n], bed[:n], env[:n]
    on = env > 0.5; r = {}
    r['vo_only_I'] = lufs(vo)[0]
    r['bed_only_I'] = lufs(bed)[0]
    r['vo_in_vo_windows'] = lufs(vo[on])[0]
    r['bed_in_vo_windows'] = lufs(bed[on])[0]
    r['bed_in_gaps'] = lufs(bed[~on])[0]
    r['gap_db'] = round(r['vo_in_vo_windows'] - r['bed_in_vo_windows'], 1)
    if final:
        I, pk = lufs(read(final)); r['final_I'], r['final_peak'] = I, pk
    return r


def check(r, min_gap=MIN_GAP_DB, I=TARGET_I, tol=1.0, max_peak=TARGET_TP):
    """QA gate lines: [(ok, text)]. Peak is the ebur128 true peak of the final file."""
    out = [(r['gap_db'] >= min_gap, f"VO over bed in VO windows: {r['gap_db']:.1f} dB (need >= {min_gap:g})")]
    if 'final_I' in r:
        out.append((abs(r['final_I'] - I) <= tol, f"final loudness {r['final_I']:.1f} LUFS (target {I:g} +-{tol:g})"))
        out.append((r['final_peak'] <= max_peak + 0.05, f"final true peak {r['final_peak']:.1f} dBFS (need <= {max_peak:g})"))
    if 'loudnorm_type' in r:
        out.append((r['loudnorm_type'] == 'linear', f"loudnorm mode {r['loudnorm_type']} (need linear)"))
    return out


def _cli():
    a = sys.argv[1:]
    if len(a) >= 3 and a[0] == 'verify':
        vo, bed = read(a[1]), read(a[2]); final = a[3] if len(a) > 3 else None
        if final:                                    # loudnorm the final the same way the mux does, then measure
            tmp = tempfile.mktemp(suffix='.wav'); d2 = loudnorm_apply(final, tmp)
            r = verify(vo, bed, None, tmp); r['loudnorm_type'] = d2['normalization_type']; os.unlink(tmp)
        else:
            r = verify(vo, bed)
        for k, v in r.items(): print(f'{k:20s} {v}')
        res = check(r)
        for ok, txt in res: print(('PASS ' if ok else 'FAIL ') + txt)
        sys.exit(0 if all(ok for ok, _ in res) else 1)
    if len(a) == 2 and a[0] == 'loudnorm':
        ln, d = loudnorm_filter(a[1]); tmp = tempfile.mktemp(suffix='.wav'); d2 = loudnorm_apply(a[1], tmp); os.unlink(tmp)
        print(ln); print('pass1 I', d['input_i'], 'TP', d['input_tp'], 'LRA', d['input_lra'], '| pass2 mode', d2['normalization_type'])
        sys.exit(0 if d2['normalization_type'] == 'linear' else 1)
    print(__doc__); sys.exit(2)


if __name__ == '__main__':
    _cli()
