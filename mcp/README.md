# video-director MCP server

One file, no extra dependencies (Python 3.9+). It lets any MCP client drive this repo: read the playbook, browse prompt ideas, run engine stages, preview stills and run QA.

## Install
```
git clone https://github.com/swapagrawal14/video-director-skill
cd video-director-skill && bash scripts/setup.sh
```
Add it to your client's MCP config (Claude Desktop `claude_desktop_config.json`, Cursor `.cursor/mcp.json`, and the same shape in Windsurf, Cline or VS Code):
```json
{
  "mcpServers": {
    "video-director": {
      "command": "python3",
      "args": ["/absolute/path/to/video-director-skill/mcp/server.py"],
      "env": { "CARTESIA_API_KEY": "optional, for Cartesia voices" }
    }
  }
}
```
Claude Code: `claude mcp add video-director -- python3 /absolute/path/to/video-director-skill/mcp/server.py`

## Tools
| Tool | What it does |
|---|---|
| `guide` | Returns SKILL.md. The agent reads it, then asks you what video you want. |
| `read_doc` | Any doc in `docs/` (SCREENCAST, HANDDRAWN, MOTION2D, CRAFT, ...). |
| `prompt_ideas` | The prompt list from `prompts/README.md`. |
| `list_engines` | Engines and how each is run. |
| `screencast` | `capture`, `voice`, `build`, `sfx`, `stills`, `render` or `all` on a project dir. |
| `episode` | A dialogue cartoon from a script.md (vidliboom). |
| `run_script` | Any script in `scripts/` with an argument list (new project, TTS, timing, stills, music, render, mux, thumbnail). |
| `qa` | The QA gate on a finished MP4. Nothing ships until it passes. |

Commands run inside the repo folder without a shell. Long renders block until they finish and return the last part of their output.
