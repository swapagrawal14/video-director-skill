"""Turn scenes into timed shots, using real voice lengths when available."""
from dataclasses import dataclass

WORDS_PER_SEC = 2.6
MIN_SHOT = 1.8
GAP = 0.35


@dataclass
class Shot:
    scene: object
    line: object
    start: float
    duration: float
    audio: object = None  # numpy array of the spoken line, if voiced

    @property
    def speaker(self):
        return self.line.speaker

    @property
    def text(self):
        return self.line.text


def plan(script, title_card=2.5, voicer=None):
    shots, t = [], title_card
    for sc in script.scenes:
        for ln in sc.lines:
            audio = voicer(ln) if voicer else None
            d = len(audio) / 44100 + GAP if audio is not None else max(MIN_SHOT, len(ln.text.split()) / WORDS_PER_SEC + 0.6)
            shots.append(Shot(sc, ln, t, d, audio))
            t += d
    return shots, t + 1.0
