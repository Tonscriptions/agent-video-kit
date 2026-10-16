"""Actual R3 channel strategies, phase tradeoffs and retained short-pitch failures.

NumPy/Pillow are evidence-only dependencies. Production never downloads tools.
"""
from __future__ import annotations
import argparse,copy,hashlib,io,json,math,shutil,subprocess,sys,time,zipfile
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
BASELINE='cea69644285d1701e5c1bb420aa62eeaca69e0ff'
TPS=90000;RATE=48000;W,H=512,288

def sha(p):return 'sha256:'+hashlib.sha256(p.read_bytes()).hexdigest()
def save(p,v):p.write_text(json.dumps(v,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8',newline='\n')
def frozen():return {p.relative_to(ROOT).as_posix():sha(p) for p in sorted([*(ROOT/'product/src').rglob('*.py'),*(ROOT/'product/tests').rglob('*.py'),ROOT/'docs/specs/agent-project.schema.json'])}

def run(output,work,binary,font,font_license):
 import numpy as np
 from PIL import Image,ImageDraw,ImageFont
 if output.exists() or work.exists():raise ValueError('Use fresh output/work directories; preserve prior evidence')
 output.mkdir(parents=True);work.mkdir(parents=True);freeze=frozen();began=datetime.now(timezone.utc).isoformat()
 binary=binary.resolve();dll=binary.with_name('sndfile.dll');license_file=binary.with_name('COPYING.txt')
 assert all(p.is_file() for p in (binary,dll,license_file,font,font_license))
 engine={'engine':'rubberband-r3-offline-v1','executable':str(binary),'sha256':sha(binary),'dependencies':[{'path':str(dll),'sha256':sha(dll)}],'license_path':str(license_file),'license_sha256':sha(license_file),'license_spdx':'GPL-2.0-or-later'}
 raw=subprocess.run(['git','-c','core.autocrlf=false','archive','--format=zip',BASELINE,'product/src','docs/specs/agent-project.schema.json'],cwd=ROOT,capture_output=True,check=True).stdout
 baseline=work/'baseline'
 with zipfile.ZipFile(io.BytesIO(raw)) as archive:
  for entry in archive.infolist():
   if entry.is_dir():continue
   p=(baseline/entry.filename).resolve();assert p.is_relative_to(baseline.resolve());p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(archive.read(entry))
 for name in ('source.mp4','pulses.wav'):shutil.copyfile(ROOT/'docs/assets/nested-frame-coverage-20261017'/name,output/name)
 shutil.copyfile(font_license,output/'font-license.txt');shutil.copyfile(license_file,output/'rubberband-license.txt')
 def ff(args,data=None):
  p=subprocess.run(['ffmpeg','-v','error',*map(str,args)],input=data,capture_output=True,timeout=300)
  if p.returncode:raise RuntimeError(p.stderr.decode('utf-8','replace'))
  return p.stdout
 def pcm(path):return np.frombuffer(ff(['-i',path,'-map','0:a:0','-acodec','pcm_f32le','-f','f32le','pipe:1']),np.float32).reshape(-1,2)
 def probe(path):return json.loads(subprocess.run(['ffprobe','-v','error','-count_frames','-show_streams','-show_format','-of','json',str(path)],capture_output=True,check=True).stdout)
 ff(['-f','lavfi','-i','aevalsrc=0.2*sin(2*PI*400*t)|0.15*sin(2*PI*800*t):s=48000:d=3','-c:a','pcm_s16le',output/'stereo-tones.wav'])
 provenance={'media_license_spdx':'CC0-1.0','original_video_generator':'scripts/smoke_subtitle_clock.py','original_generator_sha256':sha(ROOT/'scripts/smoke_subtitle_clock.py'),'audio_generator':'FFmpeg aevalsrc 400/800 Hz stereo, 48 kHz signed16, 3 s','inputs':{n:sha(output/n) for n in ('source.mp4','pulses.wav','stereo-tones.wav')},'font':{'sha256':sha(font),'license_sha256':sha(font_license),'binary_distributed':False},'engine':engine,'third_party_binaries_distributed':False,'new_model_inference':0}
 for name,expr in [('antiphase.wav','0.2*sin(2*PI*400*t)|-0.2*sin(2*PI*400*t)'),('left-only.wav','0.2*sin(2*PI*400*t)|0')]:
  ff(['-f','lavfi','-i',f'aevalsrc={expr}:s=48000:d=3','-c:a','pcm_f32le',output/name]);provenance['inputs'][name]=sha(output/name)
 provenance['channel_fixture_generator']='FFmpeg aevalsrc, float32 stereo, 48 kHz, 3 s; exact antiphase or silent right'
 save(output/'fixture-provenance.json',provenance)
 calls=[];bootstrap='import sys;sys.path.insert(0,sys.argv.pop(1));from ai_ad_editor.runtime import configure_local_runtime;configure_local_runtime();from ai_ad_editor.cli import main;raise SystemExit(main())'
 def cli(*args,old=False,allow_failure=False):
  cmd=[sys.executable,'-I','-B','-X','utf8','-c',bootstrap,str(baseline/'product/src' if old else ROOT/'product/src'),*map(str,args)]
  start=time.monotonic();p=subprocess.run(cmd,cwd=ROOT,capture_output=True,timeout=300);index=len(calls)
  (work/f'call-{index:03}.stdout.log').write_bytes(p.stdout);(work/f'call-{index:03}.stderr.log').write_bytes(p.stderr)
  value=json.loads(p.stdout.decode('utf-8-sig'));calls.append({'args':list(map(str,args)),'old':old,'exit_code':p.returncode,'seconds':time.monotonic()-start,'result':value});save(work/'partial-calls.json',calls)
  if p.returncode and not allow_failure:raise RuntimeError(json.dumps(value,ensure_ascii=False)[:5000])
  return value
 def stats(samples):
  n=len(samples);result={'frames':n,'nonzero_per_channel':[int(np.count_nonzero(samples[:,c])) for c in range(2)],'rms':np.sqrt(np.mean(samples.astype(float)**2,axis=0)).tolist(),'pcm_sha256':'sha256:'+hashlib.sha256(samples.astype('<f4').tobytes()).hexdigest()}
  # Zero-padded central Hann FFT; exclude DC explicitly. This measures pitch,
  # not merely the expected-duration or nonzero gate.
  center=samples[n//8:n*7//8].astype(float);fft_size=1<<max(17,(len(center)-1).bit_length());freq=np.fft.rfftfreq(fft_size,1/RATE);spectrum=np.abs(np.fft.rfft(center*np.hanning(len(center))[:,None],n=fft_size,axis=0));mask=(freq>=100)&(freq<=1400)
  result['dominant_ac_hz']=[float(freq[mask][np.argmax(spectrum[mask,c])]) if np.any(samples[:,c]) else None for c in range(2)];result['decile_rms']=[np.sqrt(np.mean(part.astype(float)**2,axis=0)).tolist() for part in np.array_split(samples,10)]
  result['maximum_mono_sum']=float(np.max(np.abs(samples[:,0]+samples[:,1])))
  return result
 configs={
  'unity-four-ms':{'left':.201,'right':.205,'duration':.004,'nested':True,'audio':'pulses.wav'},
  'scalar-slow':{'left':.25,'right':.375,'duration':.25},
  'tiny-forward':{'left':.201,'right':.205,'duration':.25,'nested':True},
  'tiny-reverse':{'left':.201,'right':.205,'duration':.25,'nested':True,'reverse':True},
  'tiny-pulse-forward':{'left':.201,'right':.205,'duration':.25,'nested':True,'audio':'pulses.wav'},
  'tiny-pulse-reverse':{'left':.201,'right':.205,'duration':.25,'nested':True,'reverse':True,'audio':'pulses.wav'},
  'scalar-fast':{'left':.25,'right':.375,'duration':.0625},
  'nested-bezier':{'left':.2,'right':2.8,'duration':1.5,'nested':True,'curve':True},
 }
 configs={f'{name}-{mode}':{**config,'channel_mode':mode} for name,config in configs.items() for mode in ('together','apart')}
 for material in ('antiphase','left-only'):
  for mode in ('together','apart'):configs[f'{material}-{mode}']={'left':.25,'right':.375,'duration':.25,'audio':material+'.wav','channel_mode':mode}
 records={};preview=None
 for name,c in configs.items():
  project=work/name;cli('project','init',project)
  p=json.loads((project/'project.json').read_text(encoding='utf-8-sig'));p['settings']['canvas'].update(width=W,height=H);p['settings']['timebase']['display_fps']={'num':24,'den':1};save(project/'project.json',p)
  for path,asset in ((output/'source.mp4','frames'),(output/c.get('audio','stereo-tones.wav'),'sound')):
   cli('media','ingest','--project',project,'--input',path,'--asset-id',asset,'--source-url','local://authored-offline-audio-stretch','--license-spdx','CC0-1.0','--verification-status','verified','--permitted-use','commercial_ad','--evidence',output/'fixture-provenance.json')
  left,right,duration=c['left'],c['right'],c['duration'];frames=max(24,math.ceil((duration+.25)*24));ticks=round(frames/24*TPS)
  ops=[{'op':'append_clip','sequence_id':'seq_main','track_id':'track_video_1','id':'video','asset_id':'frames','source_in_tick':0,'source_out_tick':ticks,'duration_tick':ticks}]
  sound={'op':'append_clip','sequence_id':'seq_main','track_id':'track_audio_1','id':'sound_clip','asset_id':'sound','source_in_tick':round(left*TPS),'source_out_tick':round(right*TPS),'duration_tick':round(duration*TPS),'speed':(right-left)/duration,'reverse':c.get('reverse',False)}
  if c.get('nested'):
   ops += [{'op':'add_sequence','id':'child','duration_tick':3*TPS},{'op':'append_clip','sequence_id':'child','track_id':'child_audio_1','id':'sound_leaf','asset_id':'sound','source_in_tick':0,'source_out_tick':3*TPS,'duration_tick':3*TPS}]
   sound.pop('asset_id');sound.update(op='append_sequence_clip',nested_sequence_id='child')
  if c.get('curve'):sound['speed_curve']={'keyframes':[{'at_tick':0,'speed':.6,'interpolation':'bezier','control_points':[.15,.05,.85,.7]},{'at_tick':234000,'speed':2.8}]}
  ops.append(sound);change=work/f'{name}-changes.json';save(change,{'operations':ops});cli('timeline','compose','--project',project,'--input',change)
  original_p=json.loads((project/'project.json').read_text(encoding='utf-8-sig'));ledger=sha(project/'rights-ledger.json');variants={}
  for label,old,extension in [('before',True,'mp4'),('after',False,'mp4'),('precision',False,'mkv')]:
   p=copy.deepcopy(original_p)
   p['settings']['audio_stretch']={**engine,**({} if old else {'channel_mode':c['channel_mode']})}
   save(project/'project.json',p);authored=copy.deepcopy({k:p[k] for k in ('assets','settings','sequences')});path=project/f'renders/{label}.{extension}'
   args=['render','--project',project,'--output',path,'--crf','0','--pixel-format','yuv444p','--publish']
   if extension=='mkv':args+=['--container','mkv','--audio-codec','pcm_f32le']
   result=cli(*args,old=old);dest=output/f'{label}-{name}.{extension}';shutil.copyfile(path,dest);manifest=Path(str(path)+'.manifest.json');shutil.copyfile(manifest,Path(str(dest)+'.manifest.json'));m=json.loads(manifest.read_text(encoding='utf-8-sig'))
   now=json.loads((project/'project.json').read_text(encoding='utf-8-sig'));assert authored=={k:now[k] for k in authored} and ledger==sha(project/'rights-ledger.json')
   samples=pcm(dest);stats_full=stats(samples[:round(duration*RATE)]);variants[label]={'path':dest.name,'sha256':sha(dest),'probe':probe(dest),'audio_interval':stats_full,'all_audio_frames':len(samples),'engine_jobs':[i['audio_stretch'] for i in m['inputs'] if i.get('audio_stretch')],'unchanged_authored_project_and_ledger':True}
   if label=='precision':
    ff(['-i',dest,'-map','0:a:0','-c:a','pcm_f32le',output/f'after-{name}.wav'])
  quality=cli('quality','check','--project',project,'--input',project/'renders/after.mp4','--require-audio','--expensive','--max-true-peak-dbfs','-1')['data']
  policy=cli('policy','audit','--project',project)['data'];s=variants['precision']['audio_interval']
  expected=(400,None) if c.get('audio')=='left-only.wav' else (400,400) if c.get('audio') in ('pulses.wav','antiphase.wav') else (400,800)
  errors=[abs(actual-wanted) if actual is not None and wanted is not None else None for actual,wanted in zip(s['dominant_ac_hz'],expected)]
  pitch_pass=all(error is not None and error<=5 for error,wanted in zip(errors,expected) if wanted is not None)
  phase_pass=s['maximum_mono_sum']==0 if c.get('audio')=='antiphase.wav' else None
  if name.startswith('unity-four-ms-'):pitch_pass=bool(np.array_equal(pcm(output/variants['precision']['path'])[:192],pcm(output/'pulses.wav')[round(left*RATE):round(right*RATE)]))
  sample_pass=all((count>0)==(wanted is not None) for count,wanted in zip(s['nonzero_per_channel'],expected)) and len(pcm(output/variants['precision']['path']))==frames*2000
  records[name]={'config':c,'operations':ops,'variants':variants,'quality':quality,'policy':policy,'pitch_error_hz':errors,'expected_hz':expected,'mono_compatibility_gate':phase_pass,'phase_contract_required':c.get('audio')=='antiphase.wav','pitch_gate_5hz':pitch_pass,'sample_presence_gate':sample_pass,'controlled_delivery_passed':bool(quality['ok'] and sample_pass and pitch_pass and phase_pass is not False),'listening_accepted':False}
  assert quality['ok'] and sample_pass
  if name.startswith('unity-four-ms-'):assert s['nonzero_per_channel']==[189,189] and all(v>0 for v in variants['before']['audio_interval']['nonzero_per_channel'])
  if name.startswith(('scalar-slow-','scalar-fast-','nested-bezier-')):assert pitch_pass,(name,s)
  save(work/'partial-records.json',records);print(json.dumps({'case':name,'r3_pitch_hz':s['dominant_ac_hz'],'pitch_gate':pitch_pass,'sample_gate':sample_pass,'controlled_delivery_passed':records[name]['controlled_delivery_passed']}),flush=True)
  if name=='tiny-forward-apart':preview=records[name]
 # Show actual decoded video frames and actual PCM waveforms. Waveform axes
 # explicitly differ: original is 4 ms; rendered audio interval is 250 ms.
 original=pcm(output/'stereo-tones.wav')[round(.201*RATE):round(.205*RATE)];before=pcm(output/'before-tiny-forward-apart.mp4')[:12000];after=pcm(output/'precision-tiny-forward-apart.mkv')[:12000]
 source_frames=np.frombuffer(ff(['-i',output/'source.mp4','-an','-pix_fmt','rgb24','-f','rawvideo','pipe:1']),np.uint8).reshape(-1,H,W,3)
 before_frames=np.frombuffer(ff(['-i',output/'before-tiny-forward-apart.mp4','-an','-pix_fmt','rgb24','-f','rawvideo','pipe:1']),np.uint8).reshape(-1,H,W,3)
 after_frames=np.frombuffer(ff(['-i',output/'after-tiny-forward-apart.mp4','-an','-pix_fmt','rgb24','-f','rawvideo','pipe:1']),np.uint8).reshape(-1,H,W,3)
 strips=[];f=ImageFont.truetype(str(font),18);labels=['Original: 4 ms / 400+800 Hz','V26 together: 250 ms / pitch FAIL','V27 apart: 250 ms / pitch FAIL']
 for i in range(24):
  frame=Image.new('RGB',(1536,548),(18,22,30));d=ImageDraw.Draw(frame)
  for col,(video,samples,label) in enumerate(zip((source_frames,before_frames,after_frames),(original,before,after),labels)):
   x=col*W;frame.paste(Image.fromarray(video[i]),(x,32));d.text((x+12,7),label,font=f,fill='white')
   # Actual left/right PCM, identical amplitude scale; original and output time axes differ.
   indices=np.minimum(len(samples)-1,(np.arange(W-50)/(W-50)*len(samples)).astype(int))
   for channel,center,color in [(0,370,(71,215,170)),(1,455,(99,165,255))]:
    d.text((x+8,center-10),'L' if channel==0 else 'R',font=f,fill=color);d.line((x+35,center,x+W-10,center),fill=(70,75,85))
    ys=center-np.clip(samples[indices,channel],-.25,.25)*180
    d.line([(x+38+j,float(y)) for j,y in enumerate(ys)],fill=color,width=1)
   at=i/24
   if at<.25:cursor=x+38+round(at/.25*(W-50));d.line((cursor,335,cursor,495),fill=(245,190,75),width=2)
   d.text((x+12,520),'Actual L/R PCM; pitch NOT accepted',font=f,fill=(185,190,200))
  strips.append(frame)
 strips[0].save(output/'waveform-comparison.png');strips[-1].save(output/'selected-last-frame.png')
 ff(['-f','rawvideo','-pix_fmt','rgb24','-s','1536x548','-r','24','-i','pipe:0','-an','-c:v','libx264','-crf','18','-pix_fmt','yuv420p',output/'waveform-comparison.mp4'],b''.join(v.tobytes() for v in strips))
 palette=strips[0].resize((1152,411)).quantize(colors=128);gif=[v.resize((1152,411)).quantize(palette=palette,dither=Image.Dither.NONE) for v in strips];gif[0].save(output/'waveform-comparison.gif',save_all=True,append_images=gif[1:],duration=[50 if i%6==5 else 40 for i in range(24)],loop=0,optimize=False)
 with Image.open(output/'waveform-comparison.gif') as im:
  gif_frames=im.n_frames;gif_ms=0
  for i in range(gif_frames):im.seek(i);gif_ms+=im.info.get('duration',0)
 result={'started_at_utc':began,'finished_at_utc':datetime.now(timezone.utc).isoformat(),'baseline_ref':BASELINE,'generator_sha256':sha(Path(__file__)),'frozen_before':freeze,'frozen_after':frozen(),'records':records,'calls':calls,'preview':{'mp4':probe(output/'waveform-comparison.mp4'),'gif_encoded_frames':gif_frames,'gif_duration_ms':gif_ms,'gif_size':[1152,411],'sound':False,'continuous_playback_or_listening':False},'new_model_inference':0}
 assert result['frozen_before']==result['frozen_after'];save(output/'evidence.json',result);print(json.dumps({'cases':len(records),'calls':len(calls),'controlled_passed':sum(v['controlled_delivery_passed'] for v in records.values()),'gif_frames':gif_frames,'gif_ms':gif_ms}),flush=True)

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);p.add_argument('--work',type=Path,required=True);p.add_argument('--rubberband',type=Path,required=True);p.add_argument('--font',type=Path,required=True);p.add_argument('--font-license',type=Path,required=True);a=p.parse_args();run(a.output.resolve(),a.work.resolve(),a.rubberband,a.font.resolve(),a.font_license.resolve())
