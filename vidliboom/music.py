"""Mood music generated in code: a soft chord pad with a gentle pulse."""
import numpy as np

SR = 44100
CHORDS = {
    "day": [[60, 64, 67], [65, 69, 72], [67, 71, 74], [60, 64, 67]],
    "sunset": [[57, 60, 64], [65, 69, 72], [60, 64, 67], [67, 71, 74]],
    "night": [[57, 60, 64], [53, 57, 60], [55, 59, 62], [52, 55, 59]],
    "rain": [[50, 53, 57], [55, 58, 62], [48, 52, 55], [53, 57, 60]],
}


def hz(m):
    return 440 * 2 ** ((m - 69) / 12)


def score(moods_timeline, total, bpm=84):
    """moods_timeline: list of (start_sec, mood). Returns mono float32 audio."""
    n = int(total * SR)
    t = np.arange(n) / SR
    out = np.zeros(n, np.float32)
    bar = 4 * 60 / bpm
    for i in range(int(total / bar) + 1):
        s0 = i * bar
        mood = [m for st, m in moods_timeline if st <= s0 + 1e-6][-1] if moods_timeline else "day"
        chord = CHORDS.get(mood, CHORDS["day"])[i % 4]
        a, b = int(s0 * SR), min(n, int((s0 + bar) * SR))
        if a >= n:
            break
        tt = t[a:b] - s0
        env = np.minimum(1, tt / 0.4) * np.minimum(1, (bar - tt) / 0.4)
        pulse = 0.75 + 0.25 * np.cos(2 * np.pi * tt * bpm / 60) ** 8
        for note in chord:
            f = hz(note)
            out[a:b] += (np.sin(2 * np.pi * f * tt) + 0.3 * np.sin(4 * np.pi * f * tt)) * env * pulse * 0.05
        out[a:b] += np.sin(2 * np.pi * hz(chord[0] - 12) * tt) * env * 0.06
    return out
