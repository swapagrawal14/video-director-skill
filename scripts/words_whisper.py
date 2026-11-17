#!/usr/bin/env python3
"""Word timestamps from any VO file with faster-whisper (CPU int8, works on linux-arm64).
Usage: python3 scripts/words_whisper.py vo.wav words.json [model=small] [lang=hi|en|auto] ["initial prompt with names"]
Tip: when you HAVE the script text, prefer alignment (stable-ts model.align) or TTS-native timings
(edge-tts WordBoundary, Cartesia timestamps) - they never mis-hear words."""
import json, sys
from faster_whisper import WhisperModel
import subprocess, numpy as np

def load16k(path):  # decode with ffmpeg CLI -> float32 mono 16 kHz (avoids PyAV version breakage)
    raw = subprocess.run(['ffmpeg', '-v', 'error', '-i', path, '-f', 's16le', '-ac', '1', '-ar', '16000', '-'],
                         capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.int16).astype(np.float32) / 32768.0
src, out = sys.argv[1], sys.argv[2]
size = sys.argv[3] if len(sys.argv) > 3 else 'small'
lang = sys.argv[4] if len(sys.argv) > 4 and sys.argv[4] != 'auto' else None
prompt = sys.argv[5] if len(sys.argv) > 5 else None
m = WhisperModel(size, device='cpu', compute_type='int8', cpu_threads=4)
segs, info = m.transcribe(load16k(src), word_timestamps=True, language=lang, vad_filter=True,
                          initial_prompt=prompt, beam_size=5)
words = [{'word': w.word.strip(), 'start': round(w.start, 3), 'end': round(w.end, 3), 'p': round(w.probability, 2)}
         for s in segs for w in s.words]
json.dump(words, open(out, 'w'), ensure_ascii=False, indent=0)
low = [w['word'] for w in words if w['p'] < 0.5]
print(out, len(words), 'words; lang', info.language, '; low-confidence:', low[:15])
