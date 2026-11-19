# चाय में नमक: painted duet (16 s, 9:16, Hindi)

Sharmaji and Kaushalya are painted pose packs from rigpop-motion. They talk in an AI-painted aangan.
The demo shows hard-cut pose rotations while each speaks, listen, think and laugh poses, blinks, eye darts,
and lip-sync patches driven by edge-tts lines (`hi-IN-MadhurNeural`, `hi-IN-SwaraNeural`). It also has a
camera push, a cut to a medium on the punchline, and Baloo 2 captions.

Build: `ln -s ../../node_modules node_modules`, run `scripts/render.py examples/painted-duet 0 485 out.mp4 720`,
then mux `voice.wav` and burn captions from `words.json` (see docs/CHARACTERS.md).
Credit: Swapnil Agrawal (BDS intern).
