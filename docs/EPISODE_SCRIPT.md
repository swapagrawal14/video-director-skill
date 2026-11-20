# Script format

A vid-liboom script is a plain markdown file.

```markdown
# Episode title

## Scene: Park ki bench | bg=sky | mood=day
BABLU [proud]: Aaj toh mausam ekdum mast hai!
DIDI [sideeye]: Upar dekho, baadal aa rahe hain.
(stage directions go in brackets and are not spoken)
```

| Element | Meaning |
|---|---|
| `# Title` | Episode title, shown on the opening card |
| `## Scene: name \| bg=... \| mood=...` | Starts a scene. Moods: `day`, `sunset`, `night`, `rain` |
| `NAME: text` | A spoken line. The name picks the character and the voice |
| `NAME [pose]: text` | Same, in a pose from `assets/characters/NAME/<pose>.png` |
| `(text)` | Stage direction, kept in the plan but not spoken |

## Characters

Put transparent PNG cut-outs in `assets/characters/<NAME>/`, one file per pose, with `idle.png` as the default. Included: `BABLU`, `DIDI`, `UNCLE`.

## Voices

`voices.json` maps each speaker to a Cartesia voice id, with `DEFAULT` for anyone else. Set `CARTESIA_API_KEY` and pass `--voice`. Lines are cached in `output/cache/`.
