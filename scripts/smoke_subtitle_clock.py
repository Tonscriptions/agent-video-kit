"""Actual old/new CLI caption renders, independent clock/pixel gates and previews.

Run with native NumPy/Pillow, local FFmpeg and an explicitly licensed font.
Uses authored CC0 geometry/audio only. No model inference or GUI.
"""
from __future__ import annotations
import argparse, array, bisect, hashlib, io, json, math, shutil, subprocess, sys, time, wave, zipfile
from datetime import datetime, timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from smoke_speed_easing import integral, forward, inverse
BASELINE='b345d95cc9adf585e56071840201fb50df5858e4'
TPS,FPS,W,H=90000,24,512,288

def sha(p):return 'sha256:'+hashlib.sha256(p.read_bytes()).hexdigest()
def save(p,v):p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')

def run(output,work,font,license_file):
 import numpy as np
 from PIL import Image,ImageDraw,ImageFont,ImageSequence
 if output.exists() or work.exists():raise ValueError('Use fresh directories; preserve previous evidence')
 if not font.is_file() or not license_file.is_file():raise ValueError('Explicit local font and license required')
 output.mkdir(parents=True);work.mkdir(parents=True)
 archive=subprocess.run(['git','-c','core.autocrlf=false','archive','--format=zip',BASELINE,'product/src','docs/specs/agent-project.schema.json'],cwd=ROOT,capture_output=True,check=True).stdout
 baseline=work/'baseline';old_hashes={}
 with zipfile.ZipFile(io.BytesIO(archive)) as z:
  for e in z.infolist():
   if e.is_dir():continue
   p=(baseline/e.filename).resolve()
   if not p.is_relative_to(baseline.resolve()):raise ValueError('Archive path outside target')
   p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(z.read(e));old_hashes[e.filename]=sha(p)
 paths=sorted([*(ROOT/'product/src').rglob('*.py'),*(ROOT/'product/tests').rglob('*.py'),ROOT/'docs/specs/agent-project.schema.json'])
 frozen={p.relative_to(ROOT).as_posix():sha(p) for p in paths}
 calls=[]
 bootstrap='import sys;sys.path.insert(0,sys.argv.pop(1));from ai_ad_editor.runtime import configure_local_runtime;configure_local_runtime();from ai_ad_editor.cli import main;raise SystemExit(main())'
 def cli(*args,old=False):
  start=time.monotonic();argv=[sys.executable,'-I','-B','-X','utf8','-c',bootstrap,str(baseline/'product/src' if old else ROOT/'product/src'),*map(str,args)]
  p=subprocess.run(argv,cwd=ROOT,capture_output=True,timeout=300)
  (work/f'call-{len(calls):03d}.stdout.log').write_bytes(p.stdout);(work/f'call-{len(calls):03d}.stderr.log').write_bytes(p.stderr)
  v=json.loads(p.stdout.decode('utf-8-sig'))
  calls.append({'argv':list(map(str,args)),'baseline':old,'exit_code':p.returncode,'seconds':time.monotonic()-start,'result':v})
  save(work/'partial-calls.json',calls)
  if p.returncode:raise RuntimeError(str(v)[:2500])
  return v
 def ff(args,data=None):
  p=subprocess.run(['ffmpeg','-v','error',*map(str,args)],input=data,capture_output=True,timeout=300)
  if p.returncode:raise RuntimeError(p.stderr.decode('utf-8','replace'))
  return p.stdout
 def decode(p):return np.frombuffer(ff(['-i',p,'-map','0:v:0','-an','-f','rawvideo','-pix_fmt','rgb24','pipe:1']),np.uint8).reshape(-1,H,W,3)
 def encode(p,frames,w=W,h=H):ff(['-f','rawvideo','-pix_fmt','rgb24','-s',f'{w}x{h}','-r',FPS,'-i','pipe:0','-an','-c:v','libx264','-crf',16,'-pix_fmt','yuv420p',p],np.asarray(frames,dtype=np.uint8).tobytes())
 large=ImageFont.truetype(str(font),36);small=ImageFont.truetype(str(font),16);caption=ImageFont.truetype(str(font),28)
 originals=[]
 for i in range(72):
  im=Image.new('RGB',(W,H),(60,90,120));d=ImageDraw.Draw(im)
  for bit in range(7):
   level=240 if i&(1<<bit) else 16;d.rectangle((32+bit*64,24,87+bit*64,79),fill=(level,)*3)
  d.text((32,100),f'SOURCE FRAME {i:02d}',font=large,fill='#de9438')
  d.text((34,160),f'{i/FPS:.3f} s | authored geometry / 24 fps',font=small,fill='#de9438')
  originals.append(np.asarray(im).copy())
 encode(output/'source.mp4',originals)
 samples=array.array('h')
 for i in range(3*48000):
  t=i/48000;a=.6 if .6<=t<.9 or 1.8<=t<2.1 else .03;v=round(32767*a*math.sin(2*math.pi*400*t));samples.extend((v,v))
 with wave.open(str(output/'pulses.wav'),'wb') as f:f.setparams((2,2,48000,0,'NONE','not compressed'));f.writeframes(samples.tobytes())
 shutil.copyfile(license_file,output/'font-license.txt')
 (output/'clip-cues.srt').write_text('1\n00:00:00,200 --> 00:00:00,800\nFEATURE\n\n2\n00:00:01,600 --> 00:00:02,400\nBENEFIT\n',encoding='utf-8',newline='\n')
 save(output/'fixture-provenance.json',{'generated_by':'scripts/smoke_subtitle_clock.py','synthetic_media_license_spdx':'CC0-1.0','third_party_natural_media':False,'model_inference':False,'font':{'name':font.name,'family':caption.getname()[0],'sha256':sha(font),'license_id':'LicenseRef-DejaVu-Fonts','license_sha256':sha(license_file),'font_binary_distributed':False},'inputs':{p.name:sha(p) for p in [output/'source.mp4',output/'pulses.wav',output/'clip-cues.srt',output/'font-license.txt']}})
 scenarios={
  'words-inline':{'kind':'words','parents':[{'mode':'ease_in'}]},
  'words-independent':{'kind':'words','independent':True,'parents':[{'speeds':(1.,1.),'reverse':True}]},
  'words-compound':{'kind':'words','parents':[{'mode':'bezier','controls':[.12,.02,.9,.3],'reverse':True},{'mode':'ease_out','speeds':(.8,2.),'reverse':True}]},
  'typing-trimmed':{'kind':'typing','parents':[{'mode':'ease_in','reverse':True,'in':.55,'out':2.75}]},
  'fade-inline':{'kind':'fade_in','parents':[{'mode':'ease_in','reverse':True}]},
  'fade-independent':{'kind':'fade_out','independent':True,'parents':[{'mode':'ease_in','reverse':True}]},
  'rotate-independent':{'kind':'rotate','independent':True,'parents':[{'mode':'ease_in','reverse':True}]},
  'srt-external':{'kind':'srt','independent':True,'parents':[{'mode':'ease_in','reverse':True}]},
  'blank-inline':{'kind':'blank','parents':[{'speeds':(1.,1.)}]},
  'blank-independent':{'kind':'blank','independent':True,'parents':[{'speeds':(1.,1.)}]},
  'control-inline':{'kind':'control','parents':[{'speeds':(1.,1.)}]},
  'control-independent':{'kind':'control','independent':True,'parents':[{'speeds':(1.,1.)}]},
 }
 decoded={};measurements={};specs={};quality={};retained={}
 for name,config in scenarios.items():
  project=work/name;cli('project','init',project,'--name',name)
  for asset,p in [('frames',output/'source.mp4'),('pulses',output/'pulses.wav'),('local_font',font)]:
   cli('media','ingest','--project',project,'--input',p,'--asset-id',asset,'--source-url','local://authored-subtitle-clock' if asset!='local_font' else 'local://licensed-DejaVu-font','--license-spdx','CC0-1.0' if asset!='local_font' else 'LicenseRef-DejaVu-Fonts','--verification-status','verified','--permitted-use','commercial_ad','--evidence',output/'fixture-provenance.json')
  value=json.loads((project/'project.json').read_text(encoding='utf-8-sig'));value['settings']['canvas'].update(width=W,height=H);value['settings']['timebase']['display_fps']={'num':FPS,'den':1};save(project/'project.json',value)
  independent=config.get('independent',False);kind=config['kind'];start=.25 if independent else 0.;duration=2.5 if independent else 3.
  style={'font_asset_id':'local_font','fontsize':28,'x':'72','y':'220','box':False,'fontcolor':'white','active_color':'yellow','borderw':0,'shadowx':0,'shadowy':0}
  text='FEATURE BENEFIT' if kind=='words' else '' if kind=='blank' else 'HHHHHH'
  subtitle={'text':text,'style':style}
  if kind=='words':subtitle['word_timing']=[{'text':'FEATURE','start':0,'end':duration/2},{'text':'BENEFIT','start':duration/2,'end':duration}]
  if kind in ['fade_in','fade_out','typing','rotate']:
   subtitle['animation']={'type':'typewriter' if kind=='typing' else kind,'duration':2.4 if kind=='typing' else 1.8 if kind.startswith('fade') else 2.3,'delay':.1 if kind=='typing' else 0}
  if kind=='rotate':style.update(x='200',y='145');subtitle['animation'].update(from_degrees=-25,to_degrees=25)
  if kind=='srt':
   ingested=cli('media','ingest','--project',project,'--input',output/'clip-cues.srt','--asset-id','cues','--source-url','local://authored-subtitle-clock','--license-spdx','CC0-1.0','--verification-status','verified','--permitted-use','commercial_ad','--evidence',output/'fixture-provenance.json')
   subtitle={'asset_uri':ingested['data']['asset']['uri'],'asset_time_base':'clip','style':{'font_asset_id':'local_font','fontsize':24}}
  operations=[{'op':'add_sequence','id':'child_0','duration_tick':3*TPS}]
  leaf={'op':'append_clip','sequence_id':'child_0','track_id':'child_0_video_1','id':'leaf','asset_id':'frames','source_in_tick':0,'source_out_tick':3*TPS,'duration_tick':3*TPS}
  if independent:
   operations += [leaf,{'op':'add_track','sequence_id':'child_0','track_id':'titles','kind':'subtitle','order':2},{'op':'append_clip','sequence_id':'child_0','track_id':'titles','id':'title','generator':{'type':'text'},'timeline_start_tick':round(start*TPS),'source_in_tick':0,'source_out_tick':round(duration*TPS),'duration_tick':round(duration*TPS),'subtitle':subtitle}]
  else:operations.append({**leaf,'subtitle':subtitle})
  operations.append({'op':'append_clip','sequence_id':'child_0','track_id':'child_0_audio_1','id':'audio','asset_id':'pulses','source_in_tick':0,'source_out_tick':3*TPS,'duration_tick':3*TPS})
  current='child_0';span=3.;steps=[]
  for level,parent in enumerate(config['parents']):
   target='seq_main' if level==len(config['parents'])-1 else f'child_{level+1}'
   left,right=parent.get('in',0.),parent.get('out',span);a,b=parent.get('speeds',(.6,4.));mode=parent.get('mode','linear');controls=parent.get('controls',[]);pieces=[(0.,right-left,a,b,mode,controls)];ticks=round(integral(right-left,pieces)*TPS);outspan=ticks/TPS
   steps.append({'in':left,'out':right,'start':0.,'duration':outspan,'reverse':parent.get('reverse',False),'pieces':pieces})
   if target!='seq_main':operations.append({'op':'add_sequence','id':target,'duration_tick':ticks})
   operations.append({'op':'append_sequence_clip','sequence_id':target,'track_id':'track_video_1' if target=='seq_main' else target+'_video_1','nested_sequence_id':current,'id':f'parent_{level}','source_in_tick':round(left*TPS),'source_out_tick':round(right*TPS),'duration_tick':ticks,'reverse':parent.get('reverse',False),'speed_curve':{'keyframes':[{'at_tick':0,'speed':a,'interpolation':mode,**({'control_points':controls} if controls else {})},{'at_tick':round((right-left)*TPS),'speed':b}]}})
   current,span=target,outspan
  value=json.loads((project/'project.json').read_text(encoding='utf-8-sig'));value['sequences'][0]['duration_tick']=round(span*TPS);save(project/'project.json',value)
  change=work/f'{name}-changes.json';save(change,{'operations':operations});cli('timeline','compose','--project',project,'--input',change);cli('validate','--project',project,'--strict-rights')
  def author_digest():
   p=json.loads((project/'project.json').read_text(encoding='utf-8-sig'));return hashlib.sha256(json.dumps({k:p[k] for k in ['assets','settings','sequences']},sort_keys=True).encode()).hexdigest()
  authored=author_digest();ledger=sha(project/'rights-ledger.json');specs[name]={'operations':operations,'oracle_steps':steps,'duration_tick':round(span*TPS),'caption_start':start,'caption_duration':duration,'kind':kind}
  for old in ([False] if kind in ['control','blank'] else [True,False]):
   label='before' if old else 'after';path=project/'renders'/f'{label}-{name}.mp4';cli('render','--project',project,'--output',path,'--publish',old=old)
   public=not(old and kind=='srt')
   target=output/path.name if public else path
   if public:shutil.copyfile(path,target);shutil.copyfile(path.with_suffix('.mp4.manifest.json'),target.with_suffix('.mp4.manifest.json'))
   frames=decode(target);decoded[label+'-'+name]=frames
   candidates=[];rev=sum(s['reverse'] for s in steps)%2
   for i in range(72):
    t=(i+rev)/FPS
    if not steps[0]['in']-1e-9<=t<=steps[0]['out']+1e-9:continue
    for step in steps:t=forward(step,t)
    candidates.append((t,i))
   candidates.sort();rows=[]
   for i,frame in enumerate(frames):
    at=i/FPS
    for step in reversed(steps):at=inverse(step,at)
    at-=.5/TPS if rev else 0.;local=at-start;visible=0<=local<duration
    source=sum(1<<bit for bit in range(7) if int(frame[50,60+64*bit,0])>128);pos=max(0,bisect.bisect_right([x[0] for x in candidates],i/FPS+2e-5)-1);expected_source=candidates[pos][1]
    row={'frame':i,'seconds':i/FPS,'authored_seconds':at,'local_caption_seconds':local,'observed_source_frame':source,'expected_source_frame':expected_source,'source_frame_error':abs(source-expected_source)}
    roi=frame[202:278].astype(np.float64)
    if kind=='words':
     yellow=(roi[:,:,0]>170)&(roi[:,:,1]>145)&(roi[:,:,2]<100);split=round(72+caption.getlength('FEATURE '));counts=[int(yellow[:,:split].sum()),int(yellow[:,split:].sum())];observed=0 if counts[0]>15 else 1 if counts[1]>15 else None;expected=(0 if local<duration/2 else 1) if visible else None
     row.update(expected=expected,observed=observed,yellow_counts=counts,matches=expected==observed and not all(c>15 for c in counts))
    elif kind=='typing':
     expected=sum(local>=.1+j*.4 for j in range(6)) if visible else 0;advance=caption.getlength('H');observed=sum(int((frame[210:278,round(72+j*advance):round(72+(j+1)*advance),:].min(axis=2)>175).sum())>12 for j in range(6));row.update(expected=expected,observed=observed,matches=expected==observed)
    elif kind in ['fade_in','fade_out','control','blank']:
     luma=roi@np.array([.2126,.7152,.0722]);background=frame[280,500].astype(np.float64)@np.array([.2126,.7152,.0722]);delta=float(luma.sum());expected=max(0.,min(1.,local/1.8 if kind=='fade_in' else (duration-local)/1.8)) if visible else 0.;row.update(luma_delta=delta,expected_opacity=expected)
    elif kind=='rotate':
     points=np.argwhere(frame[90:278].min(axis=2)>190);angle=None
     if len(points)>25:
      y,x=points.T;xx=x-x.mean();yy=y-y.mean();angle=math.degrees(.5*math.atan2(float((2*xx*yy).sum()),float((xx*xx-yy*yy).sum())))
     expected=-25+50*max(0.,min(1.,local/2.3));checked=visible and local>1.8 and local<duration-.02;error=None if angle is None else abs(angle-expected);row.update(expected_angle=expected,observed_angle=angle,angle_error=error,pose_checked=checked,matches=not checked or error is not None and error<=2.5)
    elif kind=='srt':
     expected=visible and (.2<=local<.8 or 1.6<=local<2.4);count=int((frame[175:278].min(axis=2)>175).sum());observed=count>20;row.update(expected=expected,observed=observed,white_count=count,matches=expected==observed)
    rows.append(row)
   pcm=np.frombuffer(ff(['-i',target,'-map','0:a:0','-vn','-ac',1,'-ar',48000,'-f','f32le','pipe:1']),np.float32);audio=[]
   for offset in range(0,len(pcm)-960,960):
    at=(offset+480)/48000
    if at>=span:continue
    source=at
    for step in reversed(steps):source=inverse(step,source)
    if min(abs(source-edge) for edge in [.6,.9,1.8,2.1])<.10:continue
    expected=.6<=source<.9 or 1.8<=source<2.1;rms=float(np.sqrt(np.mean(pcm[offset:offset+960].astype(np.float64)**2)));audio.append({'seconds':at,'source_seconds':source,'rms':rms,'expected_loud':expected,'matches':(rms>.15)==expected})
   record={'rows':rows,'max_source_frame_error':max(r['source_frame_error'] for r in rows),'audio_rows':audio,'audio_mismatch_count':sum(not r['matches'] for r in audio),'source_frame_gate':1,'audio_boundary_exclusion_source_seconds':.10,'audio_rms_gate':.15,'public_media':public,'media_sha256':sha(target),'continuous_playback_reviewed':False,'audio_listened':False}
   if any('matches' in r for r in rows):record['caption_mismatch_count']=sum(not r.get('matches',True) for r in rows)
   measurements[label+'-'+name]=record
   if not old:quality[name]=cli('quality','check','--project',project,'--input',path,'--require-audio','--expensive','--fail-on-black','--max-true-peak-dbfs','-1','--report',project/'validation/delivery.json')['data']
   assert authored==author_digest() and ledger==sha(project/'rights-ledger.json'),'Render mutated authored state/rights ledger'
  retained[name]={'authored_sha256':authored,'ledger_sha256':ledger,'unchanged_after_renders':True}
 # Calibrate integrated glyph brightness with independent, opaque real CLI controls.
 for name,config in scenarios.items():
  if not config['kind'].startswith('fade'):continue
  suffix='independent' if config.get('independent') else 'inline'
  blank=measurements['after-blank-'+suffix]['rows'][24]['luma_delta']
  control=measurements['after-control-'+suffix]['rows'][24]['luma_delta']-blank
  for label in ['before','after']:
   record=measurements[label+'-'+name]
   for row in record['rows']:
    row['observed_opacity']=(row['luma_delta']-blank)/control;row['opacity_error']=abs(row['observed_opacity']-row['expected_opacity']);row['matches']=row['opacity_error']<=.065
   record.update(caption_mismatch_count=sum(not r['matches'] for r in record['rows']),max_opacity_error=max(r['opacity_error'] for r in record['rows']),opacity_gate=.065,opaque_control_luma=control)
 # Source/baseline pixels are actual decoded footage, not simulated old behavior.
 panels=[];n=len(decoded['after-words-inline']);source_decoded=decode(output/'source.mp4')
 for i in range(n):
  im=Image.new('RGB',(W*3,340),'#101923');d=ImageDraw.Draw(im)
  for col,(key,title) in enumerate([(None,'ORIGINAL INPUT'),('before-words-inline','BASELINE b345d95'),('after-words-inline','CURRENT CLI')]):
   frame=source_decoded[i] if key is None else decoded[key][i];im.paste(Image.fromarray(frame),(col*W,35));d.text((col*W+16,9),title,font=small,fill='white')
  d.text((16,320),'Original is an unretimed prefix. Old/new use the same authored timeline.',font=small,fill='white');panels.append(np.asarray(im).copy())
 encode(output/'subtitle-clock-comparison.mp4',panels,W*3,340)
 durations=[round((i+1)*1000/FPS/10)*10-round(i*1000/FPS/10)*10 for i in range(n)]
 gif=[Image.fromarray(a).resize((1152,255)).convert('P',palette=Image.Palette.ADAPTIVE,colors=192) for a in panels]
 gif[0].save(output/'subtitle-clock-comparison.gif',save_all=True,append_images=gif[1:],duration=durations,loop=0,optimize=False)
 contact=Image.new('RGB',(W*3,H*3+90),'#101923');d=ImageDraw.Draw(contact)
 for row,index in enumerate([0,n//2,n-1]):
  for col,key in enumerate([None,'before-words-inline','after-words-inline']):
   contact.paste(Image.fromarray(source_decoded[index] if key is None else decoded[key][index]),(col*W,row*(H+30)+30));d.text((col*W+8,row*(H+30)+6),f'frame {index} / '+('source prefix' if key is None else key),font=small,fill='white')
 contact.save(output/'contact-sheet.png')
 probes={}
 for p in sorted(output.glob('*.mp4')):
  v=json.loads(subprocess.run(['ffprobe','-v','error','-count_frames','-show_streams','-show_format','-of','json',str(p)],capture_output=True,check=True).stdout);probes[p.name]=v
 with Image.open(output/'subtitle-clock-comparison.gif') as im:gif_ms=[f.info.get('duration',0) for f in ImageSequence.Iterator(im)]
 summary={k:{'frames':len(v['rows']),'source_max_error':v['max_source_frame_error'],'audio_mismatches':v['audio_mismatch_count'],'caption_mismatches':v.get('caption_mismatch_count'),'opacity_max_error':v.get('max_opacity_error'),'pose_samples':sum(r.get('pose_checked',False) for r in v['rows'])} for k,v in measurements.items()}
 after_hashes={p.relative_to(ROOT).as_posix():sha(p) for p in paths}
 evidence={'created_at_utc':datetime.now(timezone.utc).isoformat(),'baseline_ref':BASELINE,'baseline_source_sha256':old_hashes,'frozen_source_sha256_before':frozen,'frozen_source_sha256_after':after_hashes,'source_unchanged':frozen==after_hashes,'generator_sha256':sha(Path(__file__)),'oracle_helper_sha256':sha(ROOT/'scripts/smoke_speed_easing.py'),'oracle':'independent 8192-subinterval Simpson reciprocal-speed integration and inverse lookup; no product maps/filter expressions','calls':calls,'cli_call_count':len(calls),'quality_call_count':sum(c['argv'][:2]==['quality','check'] for c in calls),'summary':summary,'measurements':measurements,'timeline_specs':specs,'quality':quality,'authored_state':retained,'probes':probes,'gif':{'frames':len(gif_ms),'milliseconds':sum(gif_ms),'frame_durations_ms':gif_ms,'mp4_seconds':n/FPS,'silent':True,'source_shown_as_prefix':True},'review':{'static_frames_reviewed':[],'continuous_playback_reviewed':False,'audio_listened':False,'new_model_inference':0,'freeze_semantics_accepted':False,'jianying_equivalence_accepted':False,'external_baseline_font_frozen':False,'external_baseline_media_public':False},'media_sha256':{p.name:sha(p) for p in sorted(output.iterdir()) if p.is_file()}}
 save(output/'evidence.json',evidence);print(json.dumps({'summary':summary,'calls':len(calls),'gif':evidence['gif']},ensure_ascii=False),flush=True)
 assert frozen==after_hashes
 failures=[]
 for name,v in measurements.items():
  if not name.startswith('after-'):continue
  if v['max_source_frame_error']>1 or v['audio_mismatch_count'] or v.get('caption_mismatch_count',0):failures.append(name)
 assert not failures,failures

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);p.add_argument('--work',type=Path,required=True);p.add_argument('--font',type=Path,required=True);p.add_argument('--font-license',type=Path,required=True);a=p.parse_args();run(a.output.resolve(),a.work.resolve(),a.font.resolve(),a.font_license.resolve())
