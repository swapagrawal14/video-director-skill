import json,subprocess,sys,os  # set CARTESIA_API_KEY env (or use any TTS)
lines={'chai':"Masala chai, the desi way. Pour it high, from a brass kettle, straight into a clay kulhad. A pinch of elaichi, a curl of steam, and that's your evening sorted.",
'rocket':"Three, two, one. The engines roar, the smoke billows out, and up she goes, past the hills, past the clouds, all the way to the stars.",
'sprout':"Every big tree starts tiny. Drop a seed into the soil, give it a little water, let the sun do its magic, and watch it grow."}
for k,t in lines.items():
    body=json.dumps({"model_id":"sonic-latest","transcript":t,"voice":{"mode":"id","id":"ca587611-ddaf-4658-8e13-b130e1abfdb2"},"output_format":{"container":"wav","encoding":"pcm_s16le","sample_rate":44100},"language":"en"})
    r=subprocess.run(['curl','-s','-w','%{http_code}','-o',f'{k}/assets/vo.wav','-X','POST','https://api.cartesia.ai/tts/bytes','-H','Cartesia-Version: 2024-06-10',*(['-H','X-API-Key: '+os.environ['CARTESIA_API_KEY']] if os.environ.get('CARTESIA_API_KEY') else []),'-H','Content-Type: application/json','-d',body],capture_output=True,text=True)
    print(k,r.stdout,r.stderr[:200])
json.dump(lines,open('lines.json','w'))
