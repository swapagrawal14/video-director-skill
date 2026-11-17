"""video_only.mp4 + final_audio.wav -> <name>.mp4, YouTube-spec: AAC 384k 48 kHz, BT.709 tags, faststart, optional
burned-in captions (project.json "burn_captions": "captions.ass") and embedded chapters (chapters.ffmeta if present).
Writes in /tmp first (some network filesystems choke on faststart). Usage: python3 scripts/mux.py <project-dir> Name.mp4"""
import sys, os, json, subprocess, tempfile, shutil
d, name = os.path.abspath(sys.argv[1]), sys.argv[2]; T = json.load(open(os.path.join(d, 'timing.json')))
P = json.load(open(os.path.join(d, 'project.json'))); here = os.path.dirname(os.path.abspath(__file__))
tmp = os.path.join(tempfile.gettempdir(), name)
cmd = ['ffmpeg', '-y', '-loglevel', 'error', '-i', os.path.join(d, 'video_only.mp4'), '-i', os.path.join(d, 'final_audio.wav')]
meta = os.path.join(d, 'chapters.ffmeta')
if os.path.exists(meta): cmd += ['-i', meta, '-map_metadata', '2', '-map_chapters', '2']
cmd += ['-map', '0:v', '-map', '1:a']
burn = P.get('burn_captions')
if burn:
    fonts = os.path.join(os.path.dirname(here), 'fonts')
    cmd += ['-vf', f"ass={os.path.join(d, burn)}:fontsdir={fonts}", '-c:v', 'libx264', '-preset', 'medium', '-crf', '17', '-pix_fmt', 'yuv420p',
            '-g', str(T['fps'] // 2)]
else: cmd += ['-c:v', 'copy']
cmd += ['-color_primaries', 'bt709', '-color_trc', 'bt709', '-colorspace', 'bt709',
        '-c:a', 'aac', '-b:a', '384k', '-ar', '48000', '-af', 'apad', '-t', str(T['duration']), '-movflags', '+faststart', tmp]
subprocess.run(cmd, check=True); shutil.copy(tmp, os.path.join(d, name)); print('->', os.path.join(d, name))
