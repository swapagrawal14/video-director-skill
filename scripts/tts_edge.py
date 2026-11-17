#!/usr/bin/env python3
"""Free TTS fallback with exact word timings (needs internet; unofficial Microsoft Edge endpoint).
Usage: python3 scripts/tts_edge.py "text" out.mp3 [voice] [rate]
Voices: hi-IN-SwaraNeural (F), hi-IN-MadhurNeural (M) for Hindi/Hinglish (write Hinglish in Devanagari for best
pronunciation, or Latin for an Indian-English read); en-IN-NeerjaNeural; en-US-AndrewMultilingualNeural.
Writes out.mp3 and out.words.json ([{word,start,end}] seconds) -> feed to words_to_ass.py."""
import asyncio, json, sys, edge_tts
text, out = sys.argv[1], sys.argv[2]
voice = sys.argv[3] if len(sys.argv) > 3 else 'hi-IN-SwaraNeural'
rate = sys.argv[4] if len(sys.argv) > 4 else '+0%'
async def main():
    c = edge_tts.Communicate(text, voice, rate=rate, boundary='WordBoundary')
    words = []
    with open(out, 'wb') as f:
        async for ch in c.stream():
            if ch['type'] == 'audio': f.write(ch['data'])
            elif ch['type'] == 'WordBoundary':   # offset/duration in 100-ns ticks
                s = ch['offset'] / 1e7; words.append({'word': ch['text'], 'start': round(s, 3), 'end': round(s + ch['duration'] / 1e7, 3)})
    json.dump(words, open(out.rsplit('.', 1)[0] + '.words.json', 'w'), ensure_ascii=False, indent=0)
    print(out, len(words), 'words')
asyncio.run(main())
