# 2 AM Power Cut (pastel cartoon, 9:16, 12 s, no VO)

A dental student studies at 2 AM, the power goes out, two glowing eyes open on her pillow... and it's the hostel cat.
Made end to end by an agent with this repo, from one style reference, with no hand animation.

**Shows:** pastel_outline cartoon look from a reference (`scripts/style_ref.py` -> `style.json`), a 7-pose pose pack
keyed off #00FF00 (`posepack.chroma_key` + `drop_specks` + `check_registration`), story told in light (`Light` with
flicker, custom `cut2am` grade, `light_pool` lamp and phone torch), `glow_eyes` with blinks, a spinning ceiling fan
that winds down and back up (fake perspective by squashing the top-down blades), slow push + shake camera,
`BeatSheet` driving poses and SFX, procedural SFX + horror kit, `loudnorm.py --tame`.

```bash
python3 examples/powercut-cartoon/scene.py                      # video.mp4 + mix.wav in the folder
PREVIEW=0.5,3.8,6.2,8.6 python3 examples/powercut-cartoon/scene.py   # storyboard stills -> shots/
bash scripts/sfx_horror.sh examples/powercut-cartoon/sfx        # needed once (heartbeat, riser, drone)
python3 scripts/loudnorm.py examples/powercut-cartoon/mix.wav /tmp/ln.wav -14 -1.0 --tame
ffmpeg -i examples/powercut-cartoon/video.mp4 -i /tmp/ln.wav -c:v copy -c:a aac -b:a 192k -shortest out.mp4
python3 scripts/qa.py out.mp4 --lufs -14                         # QA PASSED
```

| t | beat |
|---|---|
| 0.0 | reading Dental Anatomy, fan spinning, "2:00 AM, Exam kal hai" |
| 1.4 / 2.4 | yawn, dozes off |
| 3.4 | power cut: thunder flash, flicker, fan winds down |
| 3.7 / 4.7 | snaps awake, phone torch |
| 5.6 | two yellow eyes open on the pillow, camera pushes in |
| 6.6 / 6.9 | hides behind the book, eyes blink and lean closer |
| 8.0 | lights back: it's the cat |
| 8.5 / 10.4 | deadpan stare, back to sleep, credit |

Credit: Swapnil Agrawal (BDS intern)
