#!/usr/bin/env python3
"""video-director MCP server (stdio, no dependencies beyond Python 3.9+).

Lets any MCP client (Claude Desktop, Cursor, Windsurf, Cline, VS Code, ...) drive this repo:
read the skill and docs, browse prompt ideas, run engine stages, preview stills and run QA.

Config (Claude Desktop / Cursor style):
  {"mcpServers": {"video-director": {"command": "python3",
     "args": ["/path/to/video-director-skill/mcp/server.py"]}}}

Commands run with the repo as working directory, never through a shell. Long renders block until done
(or until `timeout` seconds) and return the tail of their output.
"""
import json, os, subprocess, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PY = sys.executable or 'python3'
ENGINES = {'screencast': 'python3 -m screencast <stage> <proj>', 'vidliboom': 'python3 -m vidliboom script.md -o out.mp4',
           'template': 'scripts/new_project.sh + scripts/render.py (3D/canvas, see SKILL.md)',
           'handdrawn': 'handdrawn/hd.py (see docs/HANDDRAWN.md)', 'motion2d': 'motion2d/ (see docs/MOTION2D.md)'}

TOOLS = [
    {'name': 'guide', 'description': 'Read SKILL.md, the director playbook. Call this first, then follow its First run section (ask the user what video they want).',
     'inputSchema': {'type': 'object', 'properties': {}}},
    {'name': 'read_doc', 'description': 'Read a doc from docs/ (e.g. SCREENCAST, HANDDRAWN, MOTION2D, CRAFT, ENGINE, CHARACTERS, AUDIO_CAPTIONS, EXPORT_QA, STYLES, FRESH_LOOK, EPISODE_SCRIPT).',
     'inputSchema': {'type': 'object', 'properties': {'name': {'type': 'string'}}, 'required': ['name']}},
    {'name': 'prompt_ideas', 'description': 'Ready-to-use video prompt ideas (tutorials, explainers, stories, promos, science, remixes).',
     'inputSchema': {'type': 'object', 'properties': {}}},
    {'name': 'list_engines', 'description': 'List the engines and how each is run.', 'inputSchema': {'type': 'object', 'properties': {}}},
    {'name': 'screencast', 'description': 'Run a screencast stage on a project dir holding script.json: capture | voice | build | sfx | stills | render | all. For stills pass times in args (seconds); for render an output path.',
     'inputSchema': {'type': 'object', 'properties': {'stage': {'type': 'string', 'enum': ['capture', 'voice', 'build', 'sfx', 'stills', 'render', 'all']},
                     'project': {'type': 'string'}, 'args': {'type': 'array', 'items': {'type': 'string'}}, 'timeout': {'type': 'number'}}, 'required': ['stage', 'project']}},
    {'name': 'episode', 'description': 'Render a dialogue cartoon episode from a script.md with vidliboom. args are extra CLI flags (e.g. ["--voice", "--format", "vertical"]).',
     'inputSchema': {'type': 'object', 'properties': {'script': {'type': 'string'}, 'out': {'type': 'string'}, 'args': {'type': 'array', 'items': {'type': 'string'}}, 'timeout': {'type': 'number'}}, 'required': ['script', 'out']}},
    {'name': 'run_script', 'description': 'Run any repo script in scripts/ (e.g. new_project.sh, tts_cartesia.py, build_timing.py, shot.py, music.py, render.py, mux.py, thumb.py) with an argument list.',
     'inputSchema': {'type': 'object', 'properties': {'name': {'type': 'string'}, 'args': {'type': 'array', 'items': {'type': 'string'}}, 'timeout': {'type': 'number'}}, 'required': ['name']}},
    {'name': 'qa', 'description': 'Run the QA gate on a finished MP4 (loudness, black/frozen frames, clipping, A/V sync). Nothing ships until it says PASS.',
     'inputSchema': {'type': 'object', 'properties': {'video': {'type': 'string'}, 'args': {'type': 'array', 'items': {'type': 'string'}}}, 'required': ['video']}},
]


def _read(rel):
    p = os.path.normpath(os.path.join(ROOT, rel))
    if not p.startswith(ROOT) or not os.path.isfile(p): raise ValueError(f'not found: {rel}')
    return open(p, encoding='utf-8').read()


def _run(cmd, timeout=None):
    try:
        r = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, timeout=timeout or 3600)
        out = (r.stdout + ('\n' + r.stderr if r.stderr else '')).strip()
        return f"exit {r.returncode}\n{out[-6000:]}"
    except subprocess.TimeoutExpired:
        return f'timed out after {timeout}s: {" ".join(cmd)}'


def call(name, a):
    a = a or {}
    if name == 'guide': return _read('SKILL.md')
    if name == 'read_doc':
        n = os.path.basename(a['name']).upper().removesuffix('.MD'); return _read(f'docs/{n}.md')
    if name == 'prompt_ideas': return _read('prompts/README.md')
    if name == 'list_engines': return '\n'.join(f'{k}: {v}' for k, v in ENGINES.items())
    if name == 'screencast':
        return _run([PY, '-m', 'screencast', a['stage'], os.path.abspath(a['project']), *a.get('args', [])], a.get('timeout'))
    if name == 'episode':
        return _run([PY, '-m', 'vidliboom', os.path.abspath(a['script']), '-o', os.path.abspath(a['out']), *a.get('args', [])], a.get('timeout'))
    if name == 'run_script':
        n = os.path.basename(a['name']); p = os.path.join(ROOT, 'scripts', n)
        if not os.path.isfile(p): raise ValueError(f'no such script: {n}')
        cmd = ['bash', p] if n.endswith('.sh') else (['node', p] if n.endswith('.js') else [PY, p])
        return _run(cmd + a.get('args', []), a.get('timeout'))
    if name == 'qa': return _run([PY, os.path.join(ROOT, 'scripts', 'qa.py'), os.path.abspath(a['video']), *a.get('args', [])])
    raise ValueError(f'unknown tool: {name}')


def main():
    for line in sys.stdin:
        line = line.strip()
        if not line: continue
        try: msg = json.loads(line)
        except ValueError: continue
        mid, method = msg.get('id'), msg.get('method')
        if mid is None: continue          # notifications (initialized, cancelled) need no reply
        try:
            if method == 'initialize':
                res = {'protocolVersion': msg.get('params', {}).get('protocolVersion', '2024-11-05'),
                       'capabilities': {'tools': {}}, 'serverInfo': {'name': 'video-director', 'version': '1.0.0'},
                       'instructions': 'Call guide first. Then ask the user what video they want (SKILL.md First run), preview stills, and run qa before delivering.'}
            elif method == 'tools/list': res = {'tools': TOOLS}
            elif method == 'tools/call':
                p = msg.get('params', {})
                try: res = {'content': [{'type': 'text', 'text': call(p.get('name'), p.get('arguments'))}]}
                except Exception as e: res = {'content': [{'type': 'text', 'text': f'error: {e}'}], 'isError': True}
            elif method == 'ping': res = {}
            else:
                print(json.dumps({'jsonrpc': '2.0', 'id': mid, 'error': {'code': -32601, 'message': f'method not found: {method}'}}), flush=True); continue
            print(json.dumps({'jsonrpc': '2.0', 'id': mid, 'result': res}), flush=True)
        except Exception as e:
            print(json.dumps({'jsonrpc': '2.0', 'id': mid, 'error': {'code': -32603, 'message': str(e)}}), flush=True)


if __name__ == '__main__':
    main()
