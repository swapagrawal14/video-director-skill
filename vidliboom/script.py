"""Parse a simple markdown script into scenes and dialogue lines.

Format:
    # Episode title
    ## Scene: <name> | bg=<background> | mood=<mood>
    BABLU: Line of dialogue
    BABLU [wave]: Line spoken in the "wave" pose
    (stage direction)
"""
import re
from dataclasses import dataclass, field


@dataclass
class Line:
    speaker: str
    text: str
    pose: str = "idle"


@dataclass
class Scene:
    name: str
    bg: str = "sky"
    mood: str = "day"
    lines: list = field(default_factory=list)
    directions: list = field(default_factory=list)


@dataclass
class Script:
    title: str
    scenes: list


def parse(text: str) -> Script:
    title, scenes = "Untitled", []
    for raw in text.splitlines():
        s = raw.strip()
        if not s:
            continue
        if s.startswith("## "):
            parts = [p.strip() for p in s[3:].split("|")]
            name = parts[0].removeprefix("Scene:").strip()
            opts = dict(p.split("=", 1) for p in parts[1:] if "=" in p)
            scenes.append(Scene(name, opts.get("bg", "sky"), opts.get("mood", "day")))
        elif s.startswith("# "):
            title = s[2:].strip()
        elif s.startswith("(") and scenes:
            scenes[-1].directions.append(s.strip("()"))
        else:
            m = re.match(r"^([A-Za-z\u0900-\u097F ]+?)\s*(?:\[(\w+)\])?\s*:\s*(.+)$", s)
            if m and scenes:
                scenes[-1].lines.append(Line(m.group(1).strip().upper(), m.group(3).strip(), m.group(2) or "idle"))
    return Script(title, scenes)
