# Example: Swap Creations — logo intro (9:16, 15 s)

A pastel doodle logo intro for **Swap Creations** (art + fashion): the white tee is drawn in, the colour patches
pop onto it, the scissors snip in, *SWAP CREATIONS* bounces in letter by letter, sparkles twinkle, and
*ART · FASHION · YOU / LAUNCHING SOON* slams in. Made and QA-passed by an agent with this repo.

<img src="../../docs/img/swap-creations-intro.gif" width="270" alt="Swap Creations logo intro">

- `swap-creations-intro.mp4` — the final intro (1080x1920, 24 fps, with SFX).
- `logo.png` — the logo used as input.

Re-make it (or any brand's intro) with the logo-intro tool ([`docs/LOGO_INTRO.md`](../../docs/LOGO_INTRO.md)):
```bash
python3 motion2d/logo_intro.py examples/swap-creations-intro/logo.png out.mp4 --secs 8 \
  --tagline "ART · FASHION · YOU" --sub "LAUNCHING SOON"
```
Quality reference only: for another brand, use that brand's logo, colours and words.

Credit: Swapnil Agrawal (BDS intern).
