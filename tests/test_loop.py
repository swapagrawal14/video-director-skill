import json, math, os, subprocess, sys
import numpy as np
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'motion2d'))
from loop import (Beat, loop_len, loop_t, cyc, csin, ccos, keyed, seamless_check, assert_seamless,  # noqa: E402
                  crossfade_loop, export_loop, music_for_loop)

FPS = 24


def _probe(path, stream=None):
    args = ['ffprobe', '-v', 'error']
    if stream: args += ['-select_streams', stream, '-show_entries', 'stream=duration,codec_name', '-of', 'json', path]
    else: args += ['-show_entries', 'format=duration', '-of', 'json', path]
    return json.loads(subprocess.run(args, capture_output=True, text=True, check=True).stdout)


def _dur(path):
    return float(_probe(path)['format']['duration'])


def _render(t, L, W=64, H=64):
    """periodic synthetic frame: a dot orbiting once per loop, background breathing twice."""
    fr = np.full((H, W, 3), int(60 + 40 * (0.5 - 0.5 * ccos(t, L, 2))), np.uint8)
    x = int(round(W / 2 + 20 * csin(t, L))); y = int(round(H / 2 + 20 * ccos(t, L)))
    fr[max(0, y - 5):y + 5, max(0, x - 5):x + 5] = (40, 200, 255)
    return fr


# ------------------------------------------------------------- beat maths
def test_beat_math_basic():
    B = Beat(bpm=120, offset=0.25)
    assert B.period == pytest.approx(0.5)
    assert B.beat_at(0.25) == pytest.approx(0)
    assert B.beat_at(1.25) == pytest.approx(2)
    assert B.phase(0.5) == pytest.approx(0.5)
    assert B.phase(0.75) == pytest.approx(0.0)
    assert B.snap(0.74) == pytest.approx(0.75)
    assert B.snap(0.9) == pytest.approx(0.75)
    assert B.snap(1.1) == pytest.approx(1.25)
    assert B.beats_between(0.0, 1.3) == pytest.approx([0.25, 0.75, 1.25])
    assert B.beats_between(0.25, 0.75) == pytest.approx([0.25])        # half-open


def test_pulse_peaks_on_beats():
    B = Beat(bpm=100)
    for n in range(6):
        tb = B.beat_time(n)
        assert B.pulse(tb) == pytest.approx(1.0)
        assert B.pulse(tb + 0.3 * B.period) < 0.2
        assert B.pulse(tb + 0.99 * B.period) < 0.01
    # bar pulse: 1 on downbeats only
    assert B.bar_pulse(0.0) == pytest.approx(1.0)
    assert B.bar_pulse(B.beat_time(4)) == pytest.approx(1.0)
    assert B.bar_pulse(B.beat_time(1)) < 0.01


def test_hit_windows():
    B = Beat(bpm=120, onsets=[0.1, 0.9], hits=[0.9])
    frames = [i / FPS for i in range(int(4 * FPS))]
    beat_frames = [t for t in frames if B.hit(t, 'beat', fps=FPS)]
    bar_frames = [t for t in frames if B.hit(t, 'bar', fps=FPS)]
    assert len(beat_frames) == 8                       # 4 s @ 120 bpm = 8 beats, each once
    assert len(bar_frames) == 2
    assert sum(B.hit(t, 'onset', fps=FPS) for t in frames) == 2
    assert sum(B.hit(t, 'hit', fps=FPS) for t in frames) == 1
    with pytest.raises(ValueError):
        B.hit(0, 'nope')


def test_from_json(tmp_path):
    p = tmp_path / 'beats.json'
    p.write_text(json.dumps({'bpm': 120.0, 'beats': [0.5, 1.0, 1.5, 2.0, 2.5], 'bars': [1.0],
                             'onsets': [0.5, 1.02], 'hits': [1.02]}))
    B = Beat.from_json(str(p))
    assert B.bpm == 120 and B.offset == pytest.approx(1.0)
    assert B.bar_pulse(1.0) == pytest.approx(1.0) and B.bar_pulse(3.0) == pytest.approx(1.0)
    assert B.hit(1.0, 'hit', fps=FPS)


# ------------------------------------------------------------- loop timing
def test_loop_len_and_cyc_close():
    L = loop_len(120, bars=2)
    assert L == pytest.approx(4.0)
    assert loop_t(5.5, L) == pytest.approx(1.5)
    for k in (1, 2, 3, 5):
        assert cyc(L, L, k) == pytest.approx(2 * math.pi * k)
        assert csin(L, L, k, 0.3) == pytest.approx(csin(0, L, k, 0.3), abs=1e-9)
        assert ccos(L, L, k) == pytest.approx(ccos(0, L, k), abs=1e-9)
    with pytest.raises(ValueError):
        cyc(1.0, L, 1.5)
    B = Beat(bpm=120)
    assert B.pulse(L) == pytest.approx(B.pulse(0))       # whole beats => pulses close too


def test_keyed_requires_closed_keys():
    L = 4.0
    assert keyed(0, L, [0, 10, 0]) == pytest.approx(0)
    assert keyed(2.0, L, [0, 10, 0]) == pytest.approx(10)
    assert keyed(L, L, [0, 10, 0]) == pytest.approx(keyed(0, L, [0, 10, 0]))
    with pytest.raises(ValueError):
        keyed(1.0, L, [0, 10, 5])


# ------------------------------------------------------------- seam
def test_seamless_check_periodic_vs_not():
    L = 2.0
    good = seamless_check(_render(0, L), _render(L, L))
    assert good < 0.002
    assert_seamless(_render(0, L), _render(L, L))
    bad_last = _render(0.5 * L, L)
    bad = seamless_check(_render(0, L), bad_last)
    assert bad > 0.02
    with pytest.raises(AssertionError, match='seam is visible'):
        assert_seamless(_render(0, L), bad_last)


def test_crossfade_loop_lengths_and_seam():
    N, n = 48, 8
    frames = [np.full((8, 8, 3), int(i * 255 / (N - 1)), np.uint8) for i in range(N)]   # ramp: not periodic
    out = crossfade_loop(frames, n)
    assert len(out) == N - n
    assert all(f.shape == (8, 8, 3) and f.dtype == np.uint8 for f in out)
    assert np.array_equal(out[0], frames[N - n])             # continues from frames[N-n-1]
    assert np.array_equal(out[-1], frames[N - n - 1])
    assert np.array_equal(out[n], frames[n])
    # seam out[-1] -> out[0] is now one ramp step, not the full jump
    assert seamless_check(out[0], out[-1]) < 2 * seamless_check(frames[1], frames[0]) + 1e-6
    assert len(crossfade_loop(frames, 0)) == N
    with pytest.raises(ValueError):
        crossfade_loop(frames, 30)


# ------------------------------------------------------------- export
@pytest.fixture(scope='module')
def loop_frames():
    L = 1.0
    return [_render(i / FPS, L) for i in range(int(L * FPS))]


def test_export_mp4_repeat(tmp_path, loop_frames):
    out = export_loop(loop_frames, str(tmp_path / 'loop.mp4'), fps=FPS, repeat=2)
    assert os.path.getsize(out) > 0
    assert _dur(out) == pytest.approx(2.0, abs=0.1)
    v = _probe(out, 'v:0')['streams'][0]
    assert v['codec_name'] == 'h264'


def test_export_gif(tmp_path, loop_frames):
    out = export_loop(loop_frames, str(tmp_path / 'loop.gif'), fps=FPS, kind='gif', size=(48, 48))
    assert _dur(out) == pytest.approx(1.0, abs=0.1)


def test_export_from_dir_with_audio_and_music_cut(tmp_path, loop_frames):
    import cv2
    d = tmp_path / 'frames'; d.mkdir()
    for i, f in enumerate(loop_frames):
        cv2.imwrite(str(d / f'{i:04d}.png'), f)
    wav = str(tmp_path / 'music.wav')
    subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-f', 'lavfi', '-i', 'sine=frequency=220:duration=6',
                    wav], check=True)
    bj = tmp_path / 'beats.json'
    bj.write_text(json.dumps({'bpm': 120, 'beats': [0.5 * i for i in range(12)], 'bars': [0.0, 2.0, 4.0],
                              'onsets': [], 'hits': []}))
    cut = str(tmp_path / 'loop.wav')
    s = music_for_loop(wav, 1.0, cut, beats_json=str(bj), after=1.0)
    assert s == pytest.approx(2.0)
    assert _dur(cut) == pytest.approx(1.0, abs=0.02)
    out = export_loop(str(d), str(tmp_path / 'loop_a.mp4'), fps=FPS, repeat=3, audio=cut)
    assert _dur(out) == pytest.approx(3.0, abs=0.1)
    a = _probe(out, 'a:0')['streams'][0]
    assert a['codec_name'] == 'aac'
    assert float(a['duration']) == pytest.approx(3.0, abs=0.1)
