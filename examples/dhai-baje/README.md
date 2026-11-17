# ढाई बजे · 2:30 AM — vertical horror short

64 s, 9:16 (720×1280 rendered, export to 1080×1920), Hindi, recipe **Cinematic Horror**.

**Story:** an old hostel wing has one rule: after 2:30 AM, never look at the corridor light. Every time the bulbs flicker, the figure at the far end is closer. The door is locked from outside. The lights die one by one. Then the hit.

**What to study here**
- A fully custom scene (`index.html`), not the template: procedural plaster/tile textures, practical bulbs, a backlit EXIT sign so the figure reads as a silhouette, a phone torch parented to the camera.
- **Teleport-in-the-dark rule:** the figure only moves while the light is off (`EV` / `FZ` arrays). Never animate it moving on screen.
- Lights die far to near before the vacuum; the stinger frame is exported as `window.SCARE_T` so the mix lands the sound exactly on it.
- A 2-frame subliminal glimpse in the opening sputter (t ≈ 1.45 s) as the hook.
- Audio in `project.json`: flicker buzz on every event, door rattle, heartbeat, 0.85 s music mute (vacuum) before the stinger.
- Captions: `captions.py --style pop --active E8E8E8 --idle 8A8A8A --w 720 --h 1280`.
- Grade: `grade.py --look horror --grain 10 --vignette 0.45 --mix 0.8`.

QA note: the lights-off section and the end card are intentionally near-black, so `qa.py` flags them; that is expected for this recipe.

Voice: Edge `hi-IN-MadhurNeural` at `-12%` rate (free).
