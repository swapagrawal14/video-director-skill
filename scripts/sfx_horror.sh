#!/usr/bin/env bash
# Procedural horror sound kit, 100% ffmpeg (no downloads, no licences). 48 kHz stereo WAVs.
set -e
D=${1:-sfx}; mkdir -p "$D"; R=48000
# 1) Sub-bass drone: 38 Hz + detuned 38.7 Hz beating + 76 Hz overtone, slow tremolo, 20 s
ffmpeg -y -loglevel error -f lavfi -i "aevalsrc='0.35*sin(2*PI*38*t)+0.25*sin(2*PI*38.7*t)+0.08*sin(2*PI*76*t)':s=$R:d=20" \
  -af "tremolo=f=0.15:d=0.4,lowpass=f=120,afade=t=in:d=3,afade=t=out:st=17:d=3" -ac 2 "$D/drone_sub.wav"
# 2) Dark air bed: brown noise, band-limited, slow filter movement feel via tremolo
ffmpeg -y -loglevel error -f lavfi -i "anoisesrc=c=brown:a=0.4:r=$R:d=20" \
  -af "highpass=f=60,lowpass=f=900,tremolo=f=0.1:d=0.5,volume=0.5,afade=t=in:d=4" -ac 2 "$D/room_tone_dark.wav"
# 3) Riser (tension build, 4 s): rising sine sweep 200->1800 Hz + rising noise, exponential fade-in, hard stop
ffmpeg -y -loglevel error -f lavfi -i "aevalsrc='0.3*sin(2*PI*(200*t+200*t*t))':s=$R:d=4" -f lavfi -i "anoisesrc=c=white:a=0.2:r=$R:d=4" \
  -filter_complex "[1]highpass=f=2000[n];[0][n]amix=inputs=2:normalize=0,afade=t=in:d=4:curve=exp,aecho=0.8:0.6:60:0.4" -ac 2 "$D/riser_4s.wav"
# 4) Jump-scare stinger: low boom (pitch-drop sine) + noise burst + metallic screech, 2.5 s
ffmpeg -y -loglevel error \
  -f lavfi -i "aevalsrc='0.9*sin(2*PI*(90*t-30*t*t))*exp(-3*t)':s=$R:d=2.5" \
  -f lavfi -i "anoisesrc=c=pink:a=0.8:r=$R:d=2.5" \
  -f lavfi -i "aevalsrc='0.25*sin(2*PI*(1450+40*sin(2*PI*7*t))*t)*exp(-1.5*t)':s=$R:d=2.5" \
  -filter_complex "[1]afade=t=out:st=0:d=0.6[n];[0][n][2]amix=inputs=3:normalize=0,aecho=0.8:0.7:40|90:0.5|0.3,alimiter=limit=0.89" -ac 2 "$D/stinger.wav"
# 5) Heartbeat (lub-dub at 60 bpm, 8 s)
ffmpeg -y -loglevel error -f lavfi -i "aevalsrc='0.9*sin(2*PI*50*t)*(exp(-25*mod(t,1))+0.7*exp(-25*abs(mod(t,1)-0.25))*gt(mod(t,1),0.25))':s=$R:d=8" \
  -af "lowpass=f=150" -ac 2 "$D/heartbeat.wav"
echo "wrote $D/{drone_sub,room_tone_dark,riser_4s,stinger,heartbeat}.wav"
