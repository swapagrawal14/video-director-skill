"""Generate one VO wav per scene with Cartesia. Usage: python3 scripts/tts_cartesia.py <project-dir>
Env: CARTESIA_API_KEY (required), CARTESIA_VOICE_ID (required; your own cloned or library voice),
     CARTESIA_LANG (default from project.json "language", else "en"). Never commit keys."""
import json, os, sys, subprocess, concurrent.futures as cf
d = sys.argv[1]; P = json.load(open(os.path.join(d, 'project.json')))
key = os.environ.get('CARTESIA_API_KEY'); voice = os.environ.get('CARTESIA_VOICE_ID') or P.get('voice_id')
if not key or not voice: sys.exit('Set CARTESIA_API_KEY and CARTESIA_VOICE_ID')
lang = os.environ.get('CARTESIA_LANG') or P.get('language', 'en')
os.makedirs(os.path.join(d, 'vo'), exist_ok=True)
def go(i):
    text = P['scenes'][i].get('vo', '').strip(); out = os.path.join(d, 'vo', f's{i:02d}.wav')
    if not text: return i, 'no-vo', 0
    body = json.dumps({"model_id": P.get('tts_model', 'sonic-latest'), "transcript": text, "voice": {"mode": "id", "id": voice},
        "language": lang, "output_format": {"container": "wav", "encoding": "pcm_s16le", "sample_rate": 44100}})
    code = ''
    for _ in range(3):
        code = subprocess.run(['curl', '-s', '-o', out, '-w', '%{http_code}', 'https://api.cartesia.ai/tts/bytes', '-H', f'X-API-Key: {key}',
            '-H', 'Cartesia-Version: 2024-11-13', '-H', 'Content-Type: application/json', '-d', body], capture_output=True, text=True).stdout
        if code == '200': break
    return i, code, dur(out)
def dur(f):
    r = subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', f], capture_output=True, text=True).stdout.strip()
    return float(r or 0)
with cf.ThreadPoolExecutor(5) as ex:
    for x in ex.map(go, range(len(P['scenes']))): print(x)
