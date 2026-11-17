"""video_only.mp4 + final_audio.wav -> <name>.mp4 (writes in /tmp first; some network FS choke on faststart).
Usage: python3 scripts/mux.py <project-dir> Output_Name.mp4"""
import sys, os, json, subprocess, tempfile, shutil
d, name = sys.argv[1], sys.argv[2]; T = json.load(open(os.path.join(d, 'timing.json')))
tmp = os.path.join(tempfile.gettempdir(), name)
subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-i', os.path.join(d, 'video_only.mp4'), '-i', os.path.join(d, 'final_audio.wav'),
    '-c:v', 'copy', '-c:a', 'aac', '-b:a', '192k', '-af', 'apad', '-t', str(T['duration']), '-movflags', '+faststart', tmp], check=True)
shutil.copy(tmp, os.path.join(d, name)); print('->', os.path.join(d, name))
