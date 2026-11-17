"""Tiny static server + headless Chromium page for a video project dir."""
import threading, http.server, socketserver, functools, random
CHROME_ARGS = ["--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"]
class _Q(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a): pass
def serve(directory):
    port = random.randint(9000, 9900)
    srv = socketserver.TCPServer(('127.0.0.1', port), functools.partial(_Q, directory=directory))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, port
def open_page(p, directory, width=1280, page='index.html', shim=None, height=None):
    import json, os
    try: P = json.load(open(os.path.join(directory, 'project.json')))
    except Exception: P = {}
    if shim is None: shim = bool(P.get('timeshim', False))
    if height is None: height = width * P.get('aspect', [16, 9])[1] // P.get('aspect', [16, 9])[0]
    srv, port = serve(directory)
    br = p.chromium.launch(args=CHROME_ARGS)
    pg = br.new_page(viewport={'width': width, 'height': height})
    if shim:  # virtual clock + seeded random for custom (non-template) scenes; see timeshim.js
        import os; pg.add_init_script(path=os.path.join(os.path.dirname(os.path.abspath(__file__)), 'timeshim.js'))
    pg.on('pageerror', lambda e: print('PAGE ERROR:', e))
    pg.on('console', lambda m: print('console:', m.text) if m.type in ('error', 'warning') else None)
    pg.goto(f'http://127.0.0.1:{port}/{page}')
    pg.wait_for_function('window.READY===true', timeout=90000)
    return br, pg, srv
