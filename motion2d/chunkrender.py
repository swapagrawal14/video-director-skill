"""Parallel chunked frame rendering, for sandboxes whose shell commands time out after ~2 minutes.

A full 1080p scene can take longer than one shell call allows. This splits the frame range into N chunks,
renders them in separate processes (in parallel, or one chunk per shell call), then concatenates them
losslessly and muxes the audio.

Contract: the scene file must be importable without side effects (keep the render loop under
`if __name__ == '__main__':`) and expose
    frame(t, step) -> HxWx3 uint8 BGR frame       (required)
    FPS, DUR, W, H                                 (optional; override with --fps/--dur/--size)
examples/zebra/scene.py already fits.

Warm-up: pose-pack casts are stateful (Cast.draw remembers the last pose to start the squash 'pop' on each
cut). A chunk that starts mid-shot would otherwise treat its first frame as a fresh cut and glitch. Each chunk
therefore renders --warmup seconds of frames before its start (discarded) so state matches a straight render.

    # everything in one go (fits a 2 min shell only for short/low-res ranges)
    python3 engine/chunkrender.py examples/zebra/scene.py --chunks 4 --audio examples/zebra/mix.wav --out out.mp4

    # long render, one chunk per shell call (each call stays under the timeout), then join
    python3 engine/chunkrender.py SCENE --chunks 8 --chunk 0 --work /tmp/cr
    ...                                    --chunk 7 --work /tmp/cr
    python3 engine/chunkrender.py SCENE --chunks 8 --join --work /tmp/cr --audio mix.wav --out final.mp4

    # quick low-res check of 1-2 s
    python3 engine/chunkrender.py SCENE --start 9 --end 11 --chunks 2 --scale 0.33 --out /tmp/test.mp4

Audio: --audio is a full-length mix (wav or any ffmpeg input); it is trimmed to [start, end) and muxed.
--loudnorm runs mix.loudnorm_filter (two-pass, linear) on it at mux time.
"""
import os, sys, argparse, importlib.util, subprocess, time

import numpy as np


def load_scene(path):
    path = os.path.abspath(path); d = os.path.dirname(path)
    eng = os.path.dirname(os.path.abspath(__file__))
    for p in (eng, d):
        if p not in sys.path: sys.path.insert(0, p)
    os.chdir(d)                                               # scenes often use relative asset paths
    spec = importlib.util.spec_from_file_location('scene_mod', path)
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
    return m


def plan(start, end, fps, chunks):
    """frame ranges [(s0, s1), ...] covering int(start*fps) .. int(end*fps)"""
    a, b = int(round(start * fps)), int(round(end * fps))
    edges = np.linspace(a, b, chunks + 1).round().astype(int)
    return [(int(edges[i]), int(edges[i + 1])) for i in range(chunks) if edges[i + 1] > edges[i]]


def chunk_path(work, i): return os.path.join(work, f'chunk_{i:03d}.mp4')


def render_chunk(args, i):
    m = load_scene(args.scene)
    fps = args.fps or getattr(m, 'FPS', 24)
    W, H = (args.size or (getattr(m, 'W', 1920), getattr(m, 'H', 1080)))
    end = args.end if args.end is not None else (args.dur or getattr(m, 'DUR'))
    rng = plan(args.start, end, fps, args.chunks)
    if i >= len(rng): return
    s0, s1 = rng[i]
    ow, oh = int(W * args.scale) // 2 * 2, int(H * args.scale) // 2 * 2
    out = chunk_path(args.work, i); tmp = out + '.part.mp4'
    # every chunk uses the same encoder settings so the concat demuxer can join them with -c copy
    proc = subprocess.Popen(['ffmpeg', '-y', '-loglevel', 'error', '-f', 'rawvideo', '-pix_fmt', 'bgr24', '-s', f'{ow}x{oh}',
                             '-r', str(fps), '-i', '-', '-c:v', 'libx264', '-preset', args.preset, '-crf', str(args.crf),
                             '-pix_fmt', 'yuv420p', '-g', str(fps * 2), tmp], stdin=subprocess.PIPE)
    import cv2
    warm0 = max(0, s0 - int(round(args.warmup * fps)))
    t0 = time.time()
    for step in range(warm0, s1):
        fr = m.frame(step / fps, step)
        if step < s0: continue                                  # warm-up: state only, frame discarded
        fr = np.ascontiguousarray(fr, dtype=np.uint8)
        if (ow, oh) != (fr.shape[1], fr.shape[0]): fr = cv2.resize(fr, (ow, oh), interpolation=cv2.INTER_AREA)
        proc.stdin.write(fr.tobytes())
    proc.stdin.close(); proc.wait()
    if proc.returncode: raise SystemExit(f'ffmpeg failed on chunk {i}')
    os.replace(tmp, out)
    print(f'chunk {i}: frames {s0}-{s1 - 1} ({s1 - s0}) +{s0 - warm0} warm-up in {time.time() - t0:.1f}s -> {out}', flush=True)


def join(args):
    m_fps = args.fps
    if not m_fps or args.end is None:
        m = load_scene(args.scene); m_fps = m_fps or getattr(m, 'FPS', 24)
        end = args.end if args.end is not None else (args.dur or getattr(m, 'DUR'))
    else:
        end = args.end
    n = len(plan(args.start, end, m_fps, args.chunks))
    parts = [chunk_path(args.work, i) for i in range(n)]
    missing = [p for p in parts if not os.path.exists(p)]
    if missing: raise SystemExit('missing chunks (render them first): ' + ' '.join(missing))
    lst = os.path.join(args.work, 'concat.txt')
    with open(lst, 'w') as f:
        for p in parts: f.write(f"file '{p}'\n")
    video = os.path.join(args.work, 'video.mp4')
    subprocess.run(['ffmpeg', '-y', '-v', 'error', '-f', 'concat', '-safe', '0', '-i', lst, '-c', 'copy', video], check=True)
    # encode in /tmp then copy: some workspace filesystems fail on the faststart rewrite
    tmp_out = os.path.join(args.work, 'final_tmp.mp4')
    if args.audio:
        af = []
        if args.loudnorm:
            from mix import loudnorm_filter
            cut = os.path.join(args.work, 'audio_cut.wav')
            subprocess.run(['ffmpeg', '-y', '-v', 'error', '-ss', str(args.start), '-t', str(end - args.start), '-i', args.audio,
                            '-vn', '-ac', '1', '-ar', '44100', cut], check=True)
            ln, _ = loudnorm_filter(cut); af = ['-af', ln]; ain = ['-i', cut]
        else:
            ain = ['-ss', str(args.start), '-t', str(end - args.start), '-i', args.audio]
        subprocess.run(['ffmpeg', '-y', '-v', 'error', '-i', video, *ain, '-map', '0:v', '-map', '1:a', *af, '-c:v', 'copy',
                        '-c:a', 'aac', '-b:a', '160k', '-ar', '48000', '-shortest', '-movflags', '+faststart', tmp_out], check=True)
    else:
        subprocess.run(['ffmpeg', '-y', '-v', 'error', '-i', video, '-c', 'copy', '-movflags', '+faststart', tmp_out], check=True)
    subprocess.run(['cp', tmp_out, args.out], check=True)
    mb = os.path.getsize(args.out) / 1e6
    print(f'joined {n} chunks -> {args.out} ({mb:.1f} MB)')


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('scene', help='scene .py exposing frame(t, step) [+ FPS, DUR, W, H]')
    ap.add_argument('--chunks', type=int, default=4)
    ap.add_argument('--chunk', type=int, help='render only this chunk index (one per shell call)')
    ap.add_argument('--join', action='store_true', help='only concat existing chunks + mux audio')
    ap.add_argument('--start', type=float, default=0.0)
    ap.add_argument('--end', type=float, help='seconds (default: scene DUR)')
    ap.add_argument('--dur', type=float, help='override scene DUR')
    ap.add_argument('--fps', type=int, help='override scene FPS')
    ap.add_argument('--size', type=lambda s: tuple(int(v) for v in s.lower().split('x')), help='override WxH the scene renders at')
    ap.add_argument('--scale', type=float, default=1.0, help='downscale output (e.g. 0.33 for quick checks)')
    ap.add_argument('--warmup', type=float, default=0.75, help='seconds rendered and discarded before each chunk')
    ap.add_argument('--crf', type=int, default=18)
    ap.add_argument('--preset', default='medium')
    ap.add_argument('--audio', help='full-length mix to trim to [start, end) and mux')
    ap.add_argument('--loudnorm', action='store_true', help='two-pass linear loudnorm (-16 LUFS / -1.5 dBTP) at mux')
    ap.add_argument('--work', default='/tmp/chunkrender')
    ap.add_argument('--out', default='/tmp/chunkrender/out.mp4')
    args = ap.parse_args()
    args.scene = os.path.abspath(args.scene); args.work = os.path.abspath(args.work); args.out = os.path.abspath(args.out)
    if args.audio: args.audio = os.path.abspath(args.audio)
    os.makedirs(args.work, exist_ok=True); os.makedirs(os.path.dirname(args.out), exist_ok=True)
    if args.chunk is not None: return render_chunk(args, args.chunk)
    if args.join: return join(args)
    # all chunks in parallel (one process each), then join
    t0 = time.time()
    me = [sys.executable, os.path.abspath(__file__)] + [a for a in sys.argv[1:]]
    procs = [subprocess.Popen(me + ['--chunk', str(i)]) for i in range(args.chunks)]
    codes = [p.wait() for p in procs]
    if any(codes): raise SystemExit(f'chunk failures: {codes}')
    print(f'rendered {args.chunks} chunks in {time.time() - t0:.1f}s')
    join(args)


if __name__ == '__main__':
    main()
