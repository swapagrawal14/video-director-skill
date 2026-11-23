
## Gotchas learned on `examples/powercut-cartoon`
- Image models return **RGB with the green screen baked in**. Run `posepack.chroma_key(im)` (float maths, then despill) and `drop_specks(im)` on every pose/prop before `check_registration`; coverage ~0.99 means the key failed.
- SFX-only mixes (thunder, stingers) fail qa.py true peak with plain loudnorm: use `scripts/loudnorm.py in.wav out.wav -14 -1.0 --tame`.
- A ceiling fan from a top-down blade PNG reads right if you rotate it, then squash it to ~0.26 height for perspective; integrate the rpm for wind-down/up instead of `spin(t)`.
