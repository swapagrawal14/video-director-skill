"""Usage: python -m vidliboom examples/bablu_mausam.md -o output/episode.mp4 [--voice]"""
import argparse
import os
from . import script as S, planner, render, voice


def main():
    ap = argparse.ArgumentParser(prog="vidliboom")
    ap.add_argument("script")
    ap.add_argument("-o", "--out", default="output/episode.mp4")
    ap.add_argument("--voice", action="store_true", help="voice lines with Cartesia (needs CARTESIA_API_KEY)")
    ap.add_argument("--voices", default="voices.json", help="speaker to voice id map")
    ap.add_argument("--lang", default="hi")
    ap.add_argument("--format", default="landscape", choices=["landscape", "vertical", "square"])
    ap.add_argument("--no-camera", action="store_true", help="disable the zoom toward the speaker")
    ap.add_argument("--audio", help="use this audio track instead of the generated mix")
    a = ap.parse_args()
    os.makedirs(os.path.dirname(a.out) or ".", exist_ok=True)
    sc = S.parse(open(a.script, encoding="utf-8").read())
    voicer = None
    if a.voice:
        vmap = voice.load_voices(a.voices)
        def voicer(ln):
            vid = vmap.get(ln.speaker) or vmap.get("DEFAULT")
            return voice.read_wav(voice.tts(ln.text, vid, lang=a.lang)) if vid else None
    shots, total = planner.plan(sc, voicer=voicer)
    print(f"{sc.title}: {len(sc.scenes)} scenes, {len(shots)} shots, {total:.1f}s")
    print("wrote", render.render(sc, shots, total, a.out, a.audio, a.format, not a.no_camera))


if __name__ == "__main__":
    main()
