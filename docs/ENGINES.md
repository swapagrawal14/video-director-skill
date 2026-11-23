# Engine registry: every Swapnil Agrawal repo this skill can call

video-director is the hub. It owns intake, script, VO, timing, mix, QA and delivery; the engines below make the
picture. Pick by the treatment the user chose (`docs/INTAKE.md`), fetch the engine with
`scripts/fetch_engine.sh <name>` (shallow clone into `engines/<name>/`, git-ignored), read that repo's
AGENTS.md / README, render, then bring the MP4 back here for mix, captions, `qa.py` and packaging.
Several engines can be cut together in one video (`scripts/mux.py`).

Machine-readable copy: `engines.json`. Built-in engines live in this repo; the rest are fetched on demand.

## Built in
| Engine | What it does best | Start |
|---|---|---|
| `template/` | 3D explainers, procedures, horror, painted 3D-stage characters (`headrig3d.js`) | `scripts/new_project.sh` |
| `motion2d/` | objects perform actions, pose-pack characters, SFX; any raster style | `docs/MOTION2D.md` |
| `motion2d/` doodle preset | flat 2D motion-doodle reels: logo stings, rubber-hose line-art, pastel cel loops, beat-synced, seamless | `docs/MOTION_DOODLE.md` |
| `motion2d/cartoon.py` cartoon kit | cartoon scenes/episodes in ANY art style: style packs or style read from a reference, beat-sheet acting, light gags, glow eyes, prop rigs, tiny-planet/parallax | `docs/CARTOON.md` |
| `motion2d/logo_intro.py` | logo intros from ANY client logo: auto-splits the raster logo into parts and builds it with pops, letter bounces, sparkles, tagline, SFX | `docs/LOGO_INTRO.md` |
| `handdrawn/` | whiteboard pen draw-on reels, talking painted host | `docs/HANDDRAWN.md` |
| `screencast/` | browser recording on a tilted card + gesturing host | `python3 -m screencast all <proj>` |
| `vidliboom/` | dialogue cartoon episode from script.md | `python3 -m vidliboom script.md -o out.mp4` |

## Fetched on demand (agent-runnable)
| Name | Repo | Treatment it powers | How to run |
|---|---|---|---|
| vid-shark | swapagrawal14/vid-shark | object story, bench demo in clay / desi / paper / 3D toy / doodle; pose packs, walk cycles | read AGENTS.md; `examples/*/render.py` |
| vid-liboom | swapagrawal14/vid-liboom | full cartoon episodes, rigged AI-art characters | `pip install -e .`; README |
| rigpop-agents | swapagrawal14/rigpop-agents | talking-character reels from a few dialogue lines, lip-sync, gestures, captions, free voices; CLI + MCP | `npx rigpop-agents init reel.md && npx rigpop-agents render reel.md` |
| rigpop-motion | swapagrawal14/rigpop-motion | screenplay-style shorts: IK skeleton rigs, pose packs, always-alive motion, cue-locked SFX (use its AI-painted image rig, not the vector rig) | `npx rigpop-motion rig <char>`, `render script.md` |
| rigpop-forge | swapagrawal14/rigpop-forge | one drawing in, a character pack out (parts, rig.json, face/talk patches, voice preset, duets). Use it to turn the user's photo-based character into a rigged pack for any engine | `node bin/rigpop-forge.js init/cut/facepack/qa` |
| rigpop-ink | swapagrawal14/rigpop-ink | restyle real footage as ink-on-paper (manga-noir, pulp-horror…) | `node bin/rigpop-ink.js restyle in.mp4 -o out.mp4 --preset <p>` |
| swap-studio | swapagrawal14/swap-studio | branded explainer reels: SwapDraws whiteboard renderer + Remotion brand kit (titles, karaoke captions, end cards, style packs) | read AGENTS.md |
| clipcast | swapagrawal14/clipcast-by-swapnilagrawal | audiogram / podcast clip videos (waveform, captions, cover) | browser app; AI-AUDIOGRAM-DIRECTOR.md |
| rangmanch-ar | swapagrawal14/rangmanch-ar | performance capture: the user acts in front of a camera, a cartoon copies face, hands, body | browser app; README |
| doodle-mirror | swapagrawal14/doodle-mirror | live webcam doodle twin (blink, talk, costumes) for selfie-style reels | browser app |

## Browser studios (the user drives them; the agent writes the input)
| Name | Use | Agent's part |
|---|---|---|
| swap-draws | whiteboard videos, hand draws onto the board | write the storyboard with AI-STORYBOARD-PROMPT.md |
| chalkline | whiteboard studio with motion packs, captions, looks | CHALKLINE prompt in whiteboard-explainer-videomaker-opensource |
| rigpop / rigpop-talk | pin joints on a picture, talking-character reels in the browser | prepare the art + script |
| reelwright-studio | short reels from Reel JSON | write Reel JSON with REEL-JSON-AGENT-PROMPT.md (raster input only here) |

## AI video-model workflows (need the user's paid video model)
| Name | Use |
|---|---|
| claymation-style-videos | 2-minute stop-motion claymation dental videos: ingredient images, reference collages, 12-clip continuity JSON (Gemini Avatar / Seedance 2.0 / Kling) |
| zack-d-style-animation-workflow | Zack D. Films-style 3D shorts: identity sheet, shots, Kling / Grok clips, VO |
| 2d-hindi-cartoon-video | Hindi story cartoons from still images + VO, YouTube packaging |
Ask before using these: they cost the user credits on an outside service.

## Not video engines (related)
Motion-field and wowkit (motion websites, rigged web characters), linkedin-carousel--studio (carousels),
logos-timeline-video-agent and video-makers-system-prompts (prompt packs for other agents).

## Routing quick table
| User wants | First choice | Also good |
|---|---|---|
| procedure / lab tutorial, 2D look | motion2d / vid-shark bench demo | rigpop-forge host + motion2d |
| procedure in 3D | template/ | |
| talking character reel, dialogue | rigpop-agents | vidliboom, rigpop-motion |
| full story episode | vid-liboom | rigpop-motion |
| whiteboard / revision notes | handdrawn/ | swap-studio, swap-draws, chalkline |
| app / website tutorial | screencast/ | |
| podcast or voice clip | clipcast | |
| real footage, stylised | rigpop-ink | |
| user acting it out | rangmanch-ar | doodle-mirror |
| claymation with video AI | claymation-style-videos | vid-shark clay (code only, free) |
| Zack D. style 3D short | zack-d workflow | template/ |
| horror short | template/ horror recipe | rigpop-ink pulp-horror on footage |

Rules that hold in every engine: raster art only (no SVG, even where an engine supports it), the user's own
character via rigpop-forge when they want to appear, VO drives timing, storyboard approved by the user,
`qa.py` / `motion_qa.py` before delivery, nothing published without the owner's consent.
