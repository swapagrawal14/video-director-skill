"""Text-to-speech with Cartesia (https://cartesia.ai). Cached per line.

Set CARTESIA_API_KEY in the environment, and map speakers to voice ids in
voices.json ({"BABLU": "<voice id>", "DEFAULT": "<voice id>"})."""
import hashlib
import json
import os
import subprocess
import wave

import numpy as np

SR = 44100
API = "https://api.cartesia.ai/tts/bytes"


def load_voices(path="voices.json"):
    return json.load(open(path)) if os.path.exists(path) else {}


def tts(text, voice_id, cache="output/cache", lang="hi"):
    os.makedirs(cache, exist_ok=True)
    key = hashlib.sha1(f"{voice_id}|{lang}|{text}".encode()).hexdigest()[:16]
    out = os.path.join(cache, key + ".wav")
    if not os.path.exists(out):
        body = json.dumps({
            "model_id": "sonic-latest", "transcript": text, "language": lang,
            "voice": {"mode": "id", "id": voice_id},
            "output_format": {"container": "wav", "encoding": "pcm_s16le", "sample_rate": SR},
        })
        cmd = ["curl", "-sf", "-o", out, "-X", "POST", API,
               "-H", "Cartesia-Version: 2024-06-10", "-H", "Content-Type: application/json"]
        if os.environ.get("CARTESIA_API_KEY"):
            cmd += ["-H", "X-API-Key: " + os.environ["CARTESIA_API_KEY"]]
        subprocess.run(cmd + ["-d", body], check=True)
    return out


def read_wav(path):
    with wave.open(path) as w:
        a = np.frombuffer(w.readframes(w.getnframes()), np.int16).astype(np.float32) / 32768
        if w.getnchannels() == 2:
            a = a.reshape(-1, 2).mean(1)
        if w.getframerate() != SR:
            n = int(len(a) * SR / w.getframerate())
            a = np.interp(np.linspace(0, len(a) - 1, n), np.arange(len(a)), a)
    return a


def envelope(audio, fps):
    """Loudness per video frame, 0..1, used to drive talking motion."""
    hop = SR // fps
    n = len(audio) // hop
    e = np.sqrt((audio[: n * hop].reshape(n, hop) ** 2).mean(1)) if n else np.zeros(1)
    return np.clip(e / (e.max() + 1e-6), 0, 1)
