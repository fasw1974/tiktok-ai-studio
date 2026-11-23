import os,json,base64,pathlib,subprocess,urllib.request
O=pathlib.Path('output');O.mkdir(exist_ok=True)
key=os.getenv('OPENAI_API_KEY')
if not key:raise SystemExit('OPENAI_API_KEY belum ditetapkan dalam GitHub Actions Secrets')
topic=os.getenv('VIDEO_TOPIC','Takut Mati?')[:160]
cat=os.getenv('VIDEO_CATEGORY','dakwah')
lang=os.getenv('VIDEO_LANGUAGE','ms')
duration=int(os.getenv('VIDEO_DURATION','30'))
details=os.getenv('VIDEO_DETAILS','')[:1000]
def req(path,data,binary=False):
 r=urllib.request.Request('https://api.openai.com/v1/'+path,data=json.dumps(data,ensure_ascii=False).encode(),headers={'Authorization':'Bearer '+key,'Content-Type':'application/json'})
 with urllib.request.urlopen(r,timeout=240) as res:body=res.read()
 return body if binary else json.loads(body)
def run(cmd):subprocess.run(cmd,check=True)
def probe(path):return float(subprocess.check_output(['ffprobe','-v','error','-show_entries','format=duration','-of','default=noprint_wrappers=1:nokey=1',str(path)]).decode().strip())
def stamp(sec):
 n=round(sec*1000);h,n=divmod(n,3600000);m,n=divmod(n,60000);s,ms=divmod(n,1000)
 return f'{h:02}:{m:02}:{s:02},{ms:03}'
language='Bahasa Melayu Malaysia' if lang=='ms' else 'Japanese'
instruction=f'''Write a realistic 9:16 TikTok video narration in {language} for about {duration} seconds.
Topic: {topic}. Category: {cat}. Verified details from user: {details or 'None'}.
Return JSON object with key scenes containing EXACTLY three objects, each with keys narration and visual_prompt.
Narration: short spoken natural sentences, strong hook, useful middle and clear ending.
visual_prompt: English cinematic documentary photograph prompt, no letters or words.
Avoid invented Quran/hadith quotations, prices, claims or fake testimonials. No unsupported factual assertions.
Do not include markdown fences. Total narration must roughly fit duration.'''
print('Menjana skrip...')
result=req('chat/completions',{'model':'gpt-4.1-mini','messages':[{'role':'system','content':'Output valid JSON only.'},{'role':'user','content':instruction}],'response_format':{'type':'json_object'}})
scenes=json.loads(result['choices'][0]['message']['content'])['scenes']
if len(scenes)!=3:raise ValueError('Expected exactly three scenes')
script='\n\n'.join(x['narration'] for x in scenes)
(O/'skrip.txt').write_text(script,encoding='utf-8')
(O/'pelan.json').write_text(json.dumps(scenes,ensure_ascii=False,indent=2),encoding='utf-8')
print('Menjana imej...')
for i,scene in enumerate(scenes,1):
 data=req('images/generations',{'model':'gpt-image-1-mini','prompt':scene['visual_prompt']+' Photorealistic vertical 9:16, no text, no logos.','size':'1024x1536','n':1})
 (O/f'scene{i}.png').write_bytes(base64.b64decode(data['data'][0]['b64_json']))
print('Menjana narasi...')
audio=req('audio/speech',{'model':'gpt-4o-mini-tts','voice':'alloy','input':script,'response_format':'mp3'},binary=True)
(O/'voice.mp3').write_bytes(audio)
length=probe(O/'voice.mp3')
weights=[max(1,len(x['narration'])) for x in scenes]
durations=[length*w/sum(weights) for w in weights]
srt=[];start=0;concat=[]
print('Membina video...')
for i,(scene,dur) in enumerate(zip(scenes,durations),1):
 end=start+dur
 srt.append(f"{i}\n{stamp(start)} --> {stamp(end)}\n{scene['narration'].replace(chr(10),' ')}\n")
 part=O/f'part{i}.mp4'
 run(['ffmpeg','-y','-loglevel','error','-loop','1','-framerate','25','-i',str(O/f'scene{i}.png'),'-vf','scale=720:1280:force_original_aspect_ratio=increase,crop=720:1280,format=yuv420p','-t',f'{dur:.3f}','-c:v','libx264','-preset','veryfast','-crf','24',str(part)])
 concat.append(f"file 'part{i}.mp4'")
 start=end
(O/'subtitle.srt').write_text('\n'.join(srt),encoding='utf-8')
(O/'parts.txt').write_text('\n'.join(concat)+'\n',encoding='utf-8')
run(['ffmpeg','-y','-loglevel','error','-f','concat','-safe','0','-i',str(O/'parts.txt'),'-c','copy',str(O/'silent.mp4')])
run(['ffmpeg','-y','-loglevel','error','-i',str(O/'silent.mp4'),'-i',str(O/'voice.mp3'),'-vf',"subtitles=output/subtitle.srt:force_style='FontName=DejaVu Sans,FontSize=17,Outline=2,Shadow=1,Alignment=2,MarginV=100'",'-c:v','libx264','-preset','veryfast','-crf','24','-c:a','aac','-shortest','-movflags','+faststart',str(O/'tiktok-video.mp4')])
print('Selesai:',O/'tiktok-video.mp4','durasi sebenar',round(length,1))
