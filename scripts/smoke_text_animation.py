"""Actual local CLI animation/highlight renders, independent glyph controls.

Inputs are the byte-preserved V21 CC0 video/audio and an explicitly supplied
local open font/license. Archived failures are rendered by their real code.
"""
from __future__ import annotations
import argparse, bisect, copy, hashlib, io, json, math, shutil, subprocess, sys, time, zipfile
from datetime import datetime, timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from smoke_speed_easing import integral, forward, inverse
BASELINE='68006af9e7b3ea26efc697ab2871fad7bf22bf94'
W,H,TPS=512,288,90000

def sha(path):return 'sha256:'+hashlib.sha256(path.read_bytes()).hexdigest()
def save(path,value):path.write_text(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8',newline='\n')
def frozen():return {p.relative_to(ROOT).as_posix():sha(p) for p in sorted([*(ROOT/'product/src').rglob('*.py'),*(ROOT/'product/tests').rglob('*.py'),ROOT/'docs/specs/agent-project.schema.json'])}

def run(output,work,font,license_file,cases=None):
 import numpy as np
 from PIL import Image,ImageDraw,ImageFont
 if output.exists() or work.exists():raise ValueError('Use fresh directories; retain earlier failed evidence')
 assert font.is_file() and license_file.is_file()
 output.mkdir(parents=True);work.mkdir(parents=True)
 started=datetime.now(timezone.utc).isoformat();freeze=frozen()
 archive=subprocess.run(['git','-c','core.autocrlf=false','archive','--format=zip',BASELINE,'product/src','docs/specs/agent-project.schema.json'],cwd=ROOT,capture_output=True,check=True).stdout
 baseline=work/'baseline';old_hashes={}
 with zipfile.ZipFile(io.BytesIO(archive)) as package:
  for entry in package.infolist():
   if entry.is_dir():continue
   path=(baseline/entry.filename).resolve();assert path.is_relative_to(baseline.resolve())
   path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(package.read(entry));old_hashes[entry.filename]=sha(path)
 for name in ('source.mp4','pulses.wav'):shutil.copyfile(ROOT/'docs/assets/subtitle-clock-20261016'/name,output/name)
 shutil.copyfile(license_file,output/'font-license.txt')
 provenance={'media_license_spdx':'CC0-1.0','original_generator':'scripts/smoke_subtitle_clock.py','original_generator_sha256':sha(ROOT/'scripts/smoke_subtitle_clock.py'),
  'inputs':{name:sha(output/name) for name in ('source.mp4','pulses.wav')},'font':{'family':ImageFont.truetype(str(font),32).getname()[0],
  'sha256':sha(font),'license_spdx':'LicenseRef-DejaVu-Fonts','license_sha256':sha(license_file),'binary_distributed':False},'third_party_natural_footage':False,'new_model_inference':0}
 save(output/'fixture-provenance.json',provenance)
 calls=[]
 bootstrap='import sys;sys.path.insert(0,sys.argv.pop(1));from ai_ad_editor.runtime import configure_local_runtime;configure_local_runtime();from ai_ad_editor.cli import main;raise SystemExit(main())'
 def cli(*args,old=False):
  command=[sys.executable,'-I','-B','-X','utf8','-c',bootstrap,str(baseline/'product/src' if old else ROOT/'product/src'),*map(str,args)]
  began=time.monotonic();p=subprocess.run(command,cwd=ROOT,capture_output=True,timeout=300)
  (work/f'call-{len(calls):03}.stdout.log').write_bytes(p.stdout);(work/f'call-{len(calls):03}.stderr.log').write_bytes(p.stderr)
  value=json.loads(p.stdout.decode('utf-8-sig'));calls.append({'args':list(map(str,args)),'baseline':old,'seconds':time.monotonic()-began,'exit_code':p.returncode,'result':value});save(work/'partial-calls.json',calls)
  if p.returncode:raise RuntimeError(json.dumps(value,ensure_ascii=False)[:3000])
  return value
 def ff(args,data=None):
  p=subprocess.run(['ffmpeg','-v','error',*map(str,args)],input=data,capture_output=True,timeout=300)
  if p.returncode:raise RuntimeError(p.stderr.decode('utf-8','replace'))
  return p.stdout
 def decode(path):return np.frombuffer(ff(['-i',path,'-map','0:v:0','-an','-pix_fmt','rgb24','-f','rawvideo','pipe:1']),np.uint8).reshape(-1,H,W,3)
 def audio(path):return 'sha256:'+hashlib.sha256(ff(['-i',path,'-map','0:a:0','-vn','-acodec','pcm_f32le','-f','f32le','pipe:1'])).hexdigest()
 def glyph_boxes(frame):
  selected=np.min(frame,axis=2)>180;selected[:170]=False
  points=set(zip(*np.nonzero(selected)));boxes=[]
  while points:
   seed=points.pop();stack=[seed];cluster=[seed]
   while stack:
    y,x=stack.pop()
    for other in ((y-1,x),(y+1,x),(y,x-1),(y,x+1)):
     if other in points:points.remove(other);stack.append(other);cluster.append(other)
   if len(cluster)>15:
    ys,xs=zip(*cluster);boxes.append((max(0,min(xs)-2),max(170,min(ys)-2),min(W,max(xs)+3),min(H,max(ys)+3)))
  return sorted([tuple(map(int,box)) for box in boxes],key=lambda b:(b[1],b[0]))
 scenarios={
  'typing-center':{'animation':{'type':'typewriter','delay':.12,'duration':2.3}},
  'fade':{'animation':{'type':'fade_in','delay':.12,'duration':2.3}},
  'slide':{'animation':{'type':'slide_left','duration':2.3,'distance':60}},
  'pop':{'animation':{'type':'pop','delay':.12,'duration':2.3,'distance':35}},
  'bounce':{'animation':{'type':'bounce','duration':2.3,'distance':18}},
  'rotate':{'animation':{'type':'rotate','duration':2.3,'from_degrees':-10,'to_degrees':10}},
  'typing-multiline':{'animation':{'type':'typewriter','delay':.12,'duration':2.3},'text':'HHHH\nHHHH','style':{'y':'176','line_spacing':12}},
  'typing-wrap':{'animation':{'type':'typewriter','delay':.12,'duration':2.3},'text':'HHHH   HHHH','style':{'y':'176','line_spacing':12,'max_width':130}},
  'typing-inline':{'animation':{'type':'typewriter','delay':.12,'duration':2.3},'independent':False,'style':{'x':'60'}},
  'typing-nested':{'animation':{'type':'typewriter','delay':.12,'duration':2.3},'nested':True},
  'typing-nested-trim':{'animation':{'type':'typewriter','delay':.12,'duration':2.3},'nested':True,'trim':True},
  'typing-fractional':{'animation':{'type':'typewriter','delay':.12,'duration':2.3},'fps':[30000,1001]},
 }
 if cases:scenarios={name:scenarios[name] for name in cases.split(',')}
 records={};preview=None
 for name,config in scenarios.items():
  fps_pair=config.get('fps',[24,1]);fps=fps_pair[0]/fps_pair[1];typed=config['animation']['type']=='typewriter'
  project=work/name;cli('project','init',project)
  p=json.loads((project/'project.json').read_text(encoding='utf-8-sig'));p['settings']['canvas'].update(width=W,height=H);p['settings']['timebase']['display_fps']={'num':fps_pair[0],'den':fps_pair[1]};p['sequences'][0]['duration_tick']=round(90/fps*TPS) if fps_pair!=[24,1] else 3*TPS;save(project/'project.json',p)
  for path,asset,label,evidence in [(output/'source.mp4','frames','CC0-1.0',output/'fixture-provenance.json'),(output/'pulses.wav','pulses','CC0-1.0',output/'fixture-provenance.json'),(font,'local_font','LicenseRef-DejaVu-Fonts',output/'font-license.txt')]:
   cli('media','ingest','--project',project,'--input',path,'--asset-id',asset,'--source-url','local://authored-text-animation','--license-spdx',label,'--verification-status','verified','--permitted-use','commercial_ad','--evidence',evidence)
  text=config.get('text','HHHH   HHHH');entries=[{'text':'HHHH','start_char':0,'start':.15,'end':1.4},{'text':'HHHH','start_char':text.rfind('HHHH'),'start':1.4,'end':2.8}]
  subtitle={'text':text,'style':{'font_asset_id':'local_font','fontsize':32,'y':'212','box':False,'expansion':'none',**config.get('style',{})},'animation':config['animation'],'word_timing':entries}
  nested=config.get('nested',False);independent=config.get('independent',True);sequence='child' if nested else 'seq_main';vt='child_video_1' if nested else 'track_video_1';at='child_audio_1' if nested else 'track_audio_1'
  operations=[{'op':'add_sequence','id':'child','duration_tick':3*TPS}] if nested else []
  leaf={'op':'append_clip','sequence_id':sequence,'track_id':vt,'id':'leaf','asset_id':'frames','source_in_tick':0,'source_out_tick':3*TPS,'duration_tick':3*TPS};operations.append(leaf);target='leaf'
  if independent:
   target='title';operations.extend([{'op':'add_track','sequence_id':sequence,'track_id':'titles','kind':'subtitle','order':2},{'op':'append_clip','sequence_id':sequence,'track_id':'titles','id':target,'generator':{'type':'text'},'source_in_tick':0,'source_out_tick':3*TPS,'duration_tick':3*TPS,'subtitle':subtitle}])
  else:leaf['subtitle']=subtitle
  operations.append({'op':'append_clip','sequence_id':sequence,'track_id':at,'id':'audio','asset_id':'pulses','source_in_tick':0,'source_out_tick':3*TPS,'duration_tick':3*TPS})
  step=None
  if nested:
   trim=config.get('trim',False);span=2.6 if trim else 3.;pieces=[(0.,span,.6,2.8,'bezier',(.15,.05,.85,.7))];duration=round(integral(span,pieces)*TPS)/TPS
   step={'in':.2 if trim else 0.,'out':2.8 if trim else 3.,'start':.125 if trim else 0.,'duration':duration,'reverse':True,'pieces':pieces}
   operations.append({'op':'append_sequence_clip','track_id':'track_video_1','id':'container','nested_sequence_id':sequence,'source_in_tick':round(step['in']*TPS),'source_out_tick':round(step['out']*TPS),'timeline_start_tick':round(step['start']*TPS),'duration_tick':round(duration*TPS),'reverse':True,'speed_curve':{'keyframes':[{'at_tick':0,'speed':.6,'interpolation':'bezier','control_points':[.15,.05,.85,.7]},{'at_tick':round(span*TPS),'speed':2.8}]}})
  change=work/f'{name}-changes.json';save(change,{'operations':operations});cli('timeline','compose','--project',project,'--input',change)
  if nested or fps_pair!=[24,1]:
   p=json.loads((project/'project.json').read_text(encoding='utf-8-sig'));p['sequences'][0]['duration_tick']=round((step['start']+step['duration'])*TPS) if nested else round(90/fps*TPS);save(project/'project.json',p)
  def authored():
   p=json.loads((project/'project.json').read_text(encoding='utf-8-sig'));return 'sha256:'+hashlib.sha256(json.dumps({key:p[key] for key in ('assets','settings','sequences')},sort_keys=True).encode()).hexdigest()
  variants={};images={};unchanged=[]
  for variant in ['before','after','reference',*(['full','blank'] if typed else [])]:
   if variant not in ('before','after'):
    control=copy.deepcopy(subtitle);control.pop('word_timing')
    if variant in ('full','blank'):control.pop('animation')
    if variant=='blank':control['style']['fontcolor']='white@0'
    change=work/f'{name}-{variant}.json';save(change,{'operations':[{'op':'update_clip','sequence_id':sequence,'clip_id':target,'patch':{'subtitle':control}}]});cli('timeline','compose','--project',project,'--input',change)
    if fps_pair!=[24,1]:
     p=json.loads((project/'project.json').read_text(encoding='utf-8-sig'));p['sequences'][0]['duration_tick']=round(90/fps*TPS);save(project/'project.json',p)
   author,ledger=authored(),sha(project/'rights-ledger.json');path=project/f'renders/{variant}.mp4'
   result=cli('render','--project',project,'--output',path,'--crf','0','--pixel-format','yuv444p','--publish',old=variant=='before')
   final=output/f'{variant}-{name}.mp4';shutil.copyfile(path,final);shutil.copyfile(Path(str(path)+'.manifest.json'),Path(str(final)+'.manifest.json'))
   assert author==authored() and ledger==sha(project/'rights-ledger.json');unchanged.append({'variant':variant,'authored_sha256':author,'ledger_sha256':ledger,'unchanged':True})
   images[variant]=decode(final);probe=json.loads(subprocess.run(['ffprobe','-v','error','-count_frames','-show_streams','-show_format','-of','json',str(final)],capture_output=True,check=True).stdout)
   variants[variant]={'path':final.name,'sha256':sha(final),'manifest_sha256':sha(Path(str(final)+'.manifest.json')),'frames':len(images[variant]),'probe':probe,'audio_pcm_f32_sha256':audio(final),'warnings':result['data'].get('warnings',[])}
   if variant=='after':
    quality=cli('quality','check','--project',project,'--input',path,'--require-audio','--expensive',*([] if nested else ['--fail-on-black']),'--max-true-peak-dbfs','-1','--report',project/'validation/text-animation.json')['data']
    manifest=json.loads(Path(str(final)+'.manifest.json').read_text(encoding='utf-8-sig'));layout=next(v['subtitle_time_mapping'] for v in manifest['inputs'] if v.get('subtitle_time_mapping'))
  policy=cli('policy','audit','--project',project)['data'];rows=[]
  static_boxes=glyph_boxes(images['full'][-2]) if typed else None
  if typed:assert len(static_boxes)==8,(name,static_boxes)
  units=list(text.replace('\n',''));starts=[round(config['animation'].get('delay',0)+i*config['animation']['duration']/len(units),9) for i in range(len(units))]
  for i,frame in enumerate(images['after']):
   author=inverse(step,i/fps)-.5/TPS if step else i/fps;visible=not step or step['start']<=i/fps<step['start']+step['duration']
   row={'frame':i,'display_seconds':i/fps,'author_seconds':author,'visible':visible}
   for variant in ('before','after'):
    row[variant+'_rg_max_error']=int(np.abs(images[variant][i,:,:,:2].astype(np.int16)-images['reference'][i,:,:,:2].astype(np.int16)).max())
   if typed:
    count=bisect.bisect_right(starts,author) if visible else 0;glyphs=sum(not c.isspace() for c in units[:count]);expected=images['blank'][i].copy()
    for left,top,right,bottom in static_boxes[:glyphs]:expected[top:bottom,left:right]=images['full'][i,top:bottom,left:right]
    row['independent_prefix_rg_max_error']=int(np.abs(frame[:,:,:2].astype(np.int16)-expected[:,:,:2].astype(np.int16)).max())
    row.update(expected_graphemes=count,expected_glyphs=glyphs,word_observations=[])
    for j,(left,top,right,bottom) in enumerate(static_boxes):
     if j>=glyphs:continue
     control=images['full'][i,top:bottom,left:right];actual=frame[top:bottom,left:right];mask=np.min(control,axis=2)>180
     observed=float(((control[:,:,2].astype(float)-actual[:,:,2])>45)[mask].mean()) if mask.any() else 0.
     word=j//4;selected=visible and entries[word]['start']<=author<entries[word]['end']
     row['word_observations'].append({'glyph':j,'word':word,'selected_fraction':observed,'expected_selected':selected,'matches':observed>=.98 if selected else observed<=.01})
   source=sum(1<<bit for bit in range(7) if frame[50,60+64*bit,0]>128)
   if step and visible:
    candidates=sorted((forward(step,(j+1)/24),j) for j in range(72) if step['in']<=(j+1)/24<=step['out']);pos=max(0,bisect.bisect_right([x[0] for x in candidates],i/fps+2e-5)-1);wanted=candidates[pos][1]
   else:wanted=min(71,math.floor(i/fps*24+1e-6))
   row.update(source_frame=source,expected_source_frame=wanted,source_frame_error=abs(source-wanted) if visible else None);rows.append(row)
  record={'config':config,'subtitle':subtitle,'operations':operations,'step':step,'variants':variants,'clock':layout,'static_glyph_boxes':static_boxes,'rows':rows,'quality':quality,'policy':policy,'intentional_leading_black_seconds':step['start'] if step else 0.,'unchanged_after_renders':unchanged,
   'before_max_rg_error':max(r['before_rg_max_error'] for r in rows),'after_max_rg_error':max(r['after_rg_max_error'] for r in rows),
   'prefix_max_rg_error':max((r.get('independent_prefix_rg_max_error',0) for r in rows)),
   'word_mismatches':sum(not o['matches'] for r in rows for o in r.get('word_observations',[])),
   'max_source_frame_error':max(r['source_frame_error'] or 0 for r in rows),'all_variant_audio_equal':len({v['audio_pcm_f32_sha256'] for v in variants.values()})==1}
  bad_source=[r['frame'] for r in rows if (r['source_frame_error'] or 0)>1]
  record['full_delivery_verified']=not bad_source
  record['unresolved_product_failure']={'code':'NESTED_TRIM_REVERSE_EOF_BACKGROUND_LOSS','frames':bad_source,'text_prefix_and_word_gates_passed':True} if bad_source else None
  records[name]=record;save(work/'partial-records.json',records)
  print(json.dumps({key:record[key] for key in ('before_max_rg_error','after_max_rg_error','prefix_max_rg_error','word_mismatches','max_source_frame_error')}|{'case':name}),flush=True)
  assert record['after_max_rg_error']<=3 and record['prefix_max_rg_error']<=3 and record['word_mismatches']==0 and record['all_variant_audio_equal']
  # This fixture also exposes an existing video EOF defect. Preserve and label
  # the failed delivery instead of claiming all composition gates passed.
  assert not bad_source or name=='typing-nested-trim' and bad_source==[len(rows)-2,len(rows)-1] and record['max_source_frame_error']==5
  if preview is None:
   preview={key:images[key].copy() for key in ('before','after')};preview_fps=fps;preview_rate=f'{fps_pair[0]}/{fps_pair[1]}'
  for frame in (0,len(images['after'])//2,len(images['after'])-1):Image.fromarray(images['after'][frame]).save(output/f'selected-{name}-{frame:03}.png')
 original=decode(output/'source.mp4');small=ImageFont.truetype(str(font),18);strips=[]
 for i in range(len(preview['after'])):
  image=Image.new('RGB',(W*3,H+44),(20,23,30));draw=ImageDraw.Draw(image)
  for column,(label,frame) in enumerate([('ORIGINAL INPUT',original[min(len(original)-1,math.floor(i/preview_fps*24+1e-9))]),('ARCHIVED CLI / FAILED',preview['before'][i]),('CURRENT CLI / PREFIX + WORDS',preview['after'][i])]):
   image.paste(Image.fromarray(frame),(W*column,44));draw.text((W*column+10,12),label,font=small,fill='white')
  strips.append(image)
 ff(['-f','rawvideo','-pix_fmt','rgb24','-s',f'{W*3}x{H+44}','-r',preview_rate,'-i','pipe:0','-an','-c:v','libx264','-crf','16','-pix_fmt','yuv420p',output/'text-animation-comparison.mp4'],np.asarray([np.asarray(im) for im in strips],np.uint8).tobytes())
 durations=[round((i+1)*100/preview_fps)*10-round(i*100/preview_fps)*10 for i in range(len(strips))];gifs=[im.resize((1152,249)) for im in strips]
 gifs[0].save(output/'text-animation-comparison.gif',save_all=True,append_images=gifs[1:],duration=durations,loop=0,optimize=False,disposal=2)
 sheet=Image.new('RGB',(W*3,(H+44)*3))
 for row,index in enumerate((0,len(strips)//2,len(strips)-1)):sheet.paste(strips[index],(0,row*(H+44)))
 sheet.save(output/'contact-sheet.png');after=frozen();assert freeze==after
 media={p.name:{'sha256':sha(p),'bytes':p.stat().st_size} for p in sorted(output.iterdir()) if p.is_file()}
 evidence={'started_at_utc':started,'finished_at_utc':datetime.now(timezone.utc).isoformat(),'baseline_ref':BASELINE,'baseline_source_sha256':old_hashes,'generator_sha256':sha(Path(__file__)),'clock_oracle_sha256':sha(ROOT/'scripts/smoke_speed_easing.py'),'frozen_before':freeze,'frozen_after':after,'provenance':provenance,'calls':calls,'records':records,'media':media,
  'gates':{'rg_max_error':3,'prefix_rg_max_error':3,'source_frame_error':1,'word_mismatches':0,'equal_pcm_across_variants':True},
  'preview':{'frames':len(strips),'fps':preview_fps,'mp4_seconds':len(strips)/preview_fps,'gif_durations_ms':durations,'gif_seconds':sum(durations)/1000,'audio':False,'static_samples':[0,len(strips)//2,len(strips)-1],'continuous_playback_reviewed':False,'audio_listened':False},
  'limits':['controlled native Windows FFmpeg 8.1 SDR CFR samples; not complete CapCut parity','R/G controls establish joint geometry/opacity, not arbitrary color semantics','independent prefix oracle uses repeated native H glyphs; kerning/literals have separate unit renders','animated word color under rotation/motion not independently graded by this public batch','general bidi/CJK/emoji shaping, VFR/freezes/group spaces/HDR/performance pending','dynamic-size inline typewriter retains explicit legacy approximation'],'new_model_inference':0}
 save(output/'evidence.json',evidence)
 print(json.dumps({'cases':len(records),'cli_calls':len(calls),'renders':sum(c['args'][0]=='render' for c in calls),'new_main_frames':sum(v['variants']['after']['frames'] for v in records.values()),'files':len(media)+1}),flush=True)

if __name__=='__main__':
 parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True);parser.add_argument('--work',type=Path,required=True);parser.add_argument('--font',type=Path,required=True);parser.add_argument('--font-license',type=Path,required=True);parser.add_argument('--cases');args=parser.parse_args()
 run(args.output.resolve(),args.work.resolve(),args.font.resolve(),args.font_license.resolve(),args.cases)
