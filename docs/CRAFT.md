# Craft: what separates a studio video from AI slop

## 1. The render contract (non-negotiable)
Every frame must be a pure function of time `t`. A frame rendered twice must be pixel-identical.
1. No wall clock: no `Date.now()`, `performance.now()`, `requestAnimationFrame` loops, `setTimeout`/`setInterval` driving motion.
2. No unseeded randomness: use the engine's seeded `rnd()` at build time; never `Math.random()` inside `renderAt`.
3. No network at render time: fonts, textures, models are local files (fonts/, assets/).
4. No layout that depends on load order: wait for `window.READY === true` before the first frame.
5. Physics/particles: precompute or make them closed-form in `t`.
**Custom scenes** (a GSAP timeline, a CodePen, a particle library) that break rules 1–2 can still render: set
`"timeshim": true` in project.json. `scripts/timeshim.js` is injected before page scripts and replaces the clock,
timers, rAF and `Math.random` with a virtual, seeded version; drive it with `window.__setTime(t)` inside `renderAt`.
CSS/WAAPI animations are paused and seeked automatically.

## 2. Hook and retention
- **First second:** something moving and a question or promise on screen. `intro_lead` defaults to 0.3 s. Never open on a logo.
- **First 3 s:** the hook says what the viewer gets ("3 mistakes that ruin bracket bonding"). Cold-open on the most visual moment, then title.
- **Every 2–3 s something changes** (camera move, label, cut, colour shift). `lint.py` warns on long static scenes.
- **Pattern interrupt every 20–40 s:** a zoom punch, a mascot beat, a "but here's the catch" card, a sound accent.
- **Open loops:** tease the payoff early ("the last step is the one everyone gets wrong"), pay it off late.
- **End fast:** recap in ≤10 s, one CTA, credit. No long goodbye.

## 3. Shot list (write it before code)
| # | Beat (VO gist) | Shot (wide/medium/close, move) | On-screen action | Text/label | SFX/music cue |
Keep it in `SPEC.md` next to project.json. Get the human's OK on SPEC.md before building scenes: changing a
spec costs a minute, changing a render costs an hour.

## 4. Review loop (the agent "watches" with stills)
1. `python3 scripts/shot.py <dir> t1 t2 …` → `shots/sheet.jpg` contact sheet. Open it.
2. Also check one frame at phone width (render a still at `--width 360` or just downscale the sheet mentally: is text still readable?).
3. Write `REVIEW.md`: one line per problem, fix, re-shoot. Ship only when REVIEW.md has no open lines.
4. After render: `scripts/qa.py` must PASS before you deliver.

## 5. Banned defaults (instant "AI video" tells)
- Centred title on flat gradient for the whole intro. Stock "whoosh" on every cut. Rainbow palettes.
- Text that appears all at once and sits. Subtitles over labels. Objects floating above surfaces.
- Camera locked for >4 s. Same ease on everything. Music louder than voice. Hard audio clicks at cuts.
- Horror: bright frames, cartoon monsters, constant loud music, jump scare without build or silence.
- Promo: no product in the first 2 s, no CTA, feature list read out without showing it.

## 6. Horror scare structure
1. **Build** (5–15 s): sub-bass drone + room tone, slow push-in, heartbeat rising (`sfx_horror.sh`: drone_sub, room_tone_dark, heartbeat, riser_4s).
2. **Vacuum** (0.5–1.0 s): kill music with a `mute` window; keep only faint room tone. Hold a dark, "empty" frame.
3. **Hit**: stinger on the SAME frame as the visual (face, slam, cut to black). `sfx: [{"file":"sfx/stinger.wav","at":<frame time>}]`.
4. **Aftermath** (2–4 s): ringing low drone, slow pull back. Don't scare again for 20+ s.
Grade: `grade.py --look horror --grain 14 --vignette 0.6 --ca 2`, optional `--bars 2.39`. Keep blacks crushed, never pure flat black for long (QA flags it).

## 7. Cutting on the beat
`scripts/beats.py music.wav beats.json`, then `"beat_snap": true` in project.json and re-run `build_timing.py`:
every scene cut moves ≤0.25 s onto the nearest beat. Put title slams and whooshes on `hits` from beats.json.
(Downbeat/"bars" detection is approximate; trust `beats`, not `bars`.)
