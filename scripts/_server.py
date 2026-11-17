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
def open_page(p, directory, width=1280, page='index.html'):
    srv, port = serve(directory)
    br = p.chromium.launch(args=CHROME_ARGS)
    pg = br.new_page(viewport={'width': width, 'height': width * 9 // 16})
    pg.on('pageerror', lambda e: print('PAGE ERROR:', e))
    pg.on('console', lambda m: print('console:', m.text) if m.type in ('error', 'warning') else None)
    pg.goto(f'http://127.0.0.1:{port}/{page}')
    pg.wait_for_function('window.READY===true', timeout=90000)
    return br, pg, srv
