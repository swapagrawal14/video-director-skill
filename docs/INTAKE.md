# Intake: treatments to offer

Offer 3 of these (engines for each: `docs/ENGINES.md`) (the ones that fit the topic), one line each, your pick marked, before generating any asset.
A style (hand-drawn, clay, paper, 3D toy, 3D) can be paired with almost any treatment; keep the user's style.

| # | Treatment | What happens on screen | Engine | Best for |
|---|---|---|---|---|
| 1 | **Bench demo** | The work piece stays on screen; tools travel in, act on it step by step; close-ups at each step; result builds up | `motion2d/` (2D) or `template/` (3D) | procedures, lab work, wire bending, recipes, DIY |
| 2 | **Host-led explainer** | The host (pose pack) talks, points, holds props; objects pop in and act beside them | `motion2d/` posepack or `screencast/` host | concepts with a personal face, reels |
| 3 | **Object story** | No host; objects perform the whole idea like stop-motion (vid-shark style) | `motion2d/` | short reels, 15–40 s, ads, fun facts |
| 4 | **3D procedure** | Lit 3D models, camera orbits, cross-sections, tool paths | `template/` | anatomy, mechanisms, clinical steps in 3D |
| 5 | **Whiteboard overview** | Pen draws diagrams, write-on labels, marker swipes | `handdrawn/` | theory overviews, revision notes; never the default for a procedure |
| 6 | **Screencast tutorial** | Real browser recording on a tilted card + gesturing host | `screencast/` | apps, websites, software |
| 7 | **Dialogue cartoon** | Characters talk scene to scene from a script | `vidliboom/` | stories, skits, patient-education dialogues |
| 8 | **Cinematic horror** | Dark grade, slow push, scare structure | `template/` horror recipe | horror shorts |
| 9 | **Talking-character reel** | 1–2 rigged characters talk, gesture, lip-sync | `rigpop-agents` / `rigpop-motion` | skits, Q&A, hooks |
| 10 | **Act it out** | The user performs on camera, a cartoon copies them | `rangmanch-ar`, `doodle-mirror` | personal reels |
| 11 | **Footage restyle** | Real clip redrawn as ink-on-paper | `rigpop-ink` | vlogs, clinical footage, horror |
| 12 | **Audiogram** | Waveform, captions, cover art over a voice clip | `clipcast` | podcasts, voice notes |
| 13 | **AI video model** | Clay or Zack-D-style shots from a paid video model | claymation / zack-d workflows | when the user has credits; ask first |

## The message (example, Hinglish user, "Adams clasp, hand-drawn, 9:16")

> Adams clasp ke liye 3 options, sab hand-drawn ink-marker look mein:
> 1. **Bench demo (meri pick):** cast screen pe rahega, wire us par rakh ke plier se step by step mudega, har bend pe close-up, tum point karte hue.
> 2. **Host-led:** tum gestures ke saath samjhaogi, plier aur wire saath mein action karenge.
> 3. **Whiteboard overview:** pen se diagram aur labels.
> Kaunsa?

## After the pick
1. Action sheet: one row per VO sentence: `t, verb, object, close-up?, SFX`. No verb = rewrite the sentence.
2. Character: master pose from the user's reference, then 5–10 poses (talk, point, explain, hold tool, react,
   thumbs-up) with the master as first reference. Never a single still.
3. Storyboard sheet (one still per scene) to the USER for a yes. Then render, `motion_qa.py`, deliver.
