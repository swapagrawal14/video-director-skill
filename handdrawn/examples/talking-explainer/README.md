# Talking-character whiteboard explainer

A demo short (about 41 s, 9:16): "Sote waqt jhatka kyun lagta hai?" (the hypnic jerk), narrated in Hinglish. A painted cartoon host talks and blinks at the bottom of the frame, while each scene's illustration draws itself on with the pen above, with a marker-swipe title and karaoke captions. It ends on the end card. Everything is raster: no SVG and no 3D.

## The face rig: diff patches
1. Generate the host once on a chroma background, with a closed mouth, eyes open and the full pose: `char_base.png`.
2. Make **image edits of that exact file** that change only one feature: `char_mA.png` (open "aah" mouth), `char_mO.png` (round "ooh" mouth), and `char_blink.png` (eyes closed).
3. `render.py` diffs each edit against the base, finds the bounding box of the changed region, and pastes only that patch onto the base. The body never drifts, and the expression changes only when you direct it.
4. Mouth shapes follow the VO loudness per frame (rest, O or A, with 2-frame smoothing). Blinks run on a fixed schedule and never happen while the mouth is open. Secondary motion: breathing, a talk bob, a small hop on each scene cut, and the host growing to centre stage for the outro.

## Make one
```
# 1. lines.json = one VO line per scene (the last one is the outro over the big host)
# 2. VO per scene -> vo/s00.wav ... (Cartesia: scripts/tts_cartesia.py, or tts_edge.py)
python3 build_audio.py                      # vo_full.wav + timeline.json (scene times, word timings, mouth levels)
# 3. music bed + duck + -14 LUFS
mkdir -p mus && echo '{"music_mood":"upbeat"}' > mus/project.json
python3 -c "import json;json.dump({'duration':json.load(open('timeline.json'))['duration']},open('mus/timing.json','w'))"
python3 ../../../scripts/music.py mus upbeat
ffmpeg -y -i vo_full.wav -i mus/music.wav -filter_complex "[0:a]aresample=48000,asplit=2[vo][sc];[1:a]aresample=48000,volume=0.35[m];[m][sc]sidechaincompress=threshold=0.03:ratio=8:attack=20:release=300[md];[vo][md]amix=inputs=2:normalize=0:duration=first,loudnorm=I=-14:TP=-1.5[out]" -map "[out]" -ac 2 mix.wav
# 4. preview stills, LOOK at them, then render in 2 chunks (at most 2 parallel jobs)
python3 render.py 0 0 shots 1.5 9 20 30 40
python3 render.py 0 630 /tmp/c0.mp4 & python3 render.py 630 99999 /tmp/c1.mp4 & wait
printf "file /tmp/c0.mp4\nfile /tmp/c1.mp4\n" > l.txt
ffmpeg -y -f concat -safe 0 -i l.txt -i mix.wav -vf scale=1080:1920:flags=lanczos -c:v libx264 -crf 18 -pix_fmt yuv420p -c:a aac -b:a 192k -shortest final.mp4
python3 ../../../scripts/motion_qa.py final.mp4
```
It renders at about 0.35 s per frame at 720×1280 on CPU, so the 41 s demo takes about 4 minutes with 2 jobs.

## Editing
- `LABELS` sets the title for each scene. `ART` lists one illustration PNG per scene (use the pack's `imageStylePrompt`, or the host's own style with **bold dark outlines**, since `DrawOn` traces dark ink).
- The scene-specific motion lives in `frame()` (the jolt in scene 0, the shake in scene 4). Add yours there.
- Word timings are proportional estimates. For exact karaoke, swap in `scripts/words_whisper.py` (decode to 16 kHz PCM first) or edge-tts word boundaries.
