"""Actual archived/current CLI frame-coverage deliveries with original CC0 inputs.

Uses existing native NumPy/Pillow/FFmpeg and a caller-supplied local open font.
The source-clock oracle imports no product code; historical outputs are real.
"""
from __future__ import annotations
import argparse,copy,hashlib,io,json,math,shutil,subprocess,sys,time,zipfile
from datetime import datetime,timezone
from fractions import Fraction
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from smoke_speed_easing import integral,inverse
BASELINE='10f035c0c27727a8b0300e8220d264fc1873faa6'
W,H,TPS=512,288,90000

def sha(path):return 'sha256:'+hashlib.sha256(path.read_bytes()).hexdigest()
def save(path,value):path.write_text(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8',newline='\n')
def frozen():return {p.relative_to(ROOT).as_posix():sha(p) for p in sorted([*(ROOT/'product/src').rglob('*.py'),*(ROOT/'product/tests').rglob('*.py'),ROOT/'docs/specs/agent-project.schema.json'])}

def run(output,work,font,license_file,cases=None):
 import numpy as np
 from PIL import Image,ImageDraw,ImageFont
 if output.exists() or work.exists():raise ValueError('Use fresh output/work directories and retain prior evidence')
 assert font.is_file() and license_file.is_file()
 output.mkdir(parents=True);work.mkdir(parents=True)
 started=datetime.now(timezone.utc).isoformat();freeze=frozen()
 package=subprocess.run(['git','-c','core.autocrlf=false','archive','--format=zip',BASELINE,'product/src','docs/specs/agent-project.schema.json'],cwd=ROOT,capture_output=True,check=True).stdout
 baseline=work/'baseline';old_hashes={}
 with zipfile.ZipFile(io.BytesIO(package)) as archive:
  for entry in archive.infolist():
   if entry.is_dir():continue
   p=(baseline/entry.filename).resolve();assert p.is_relative_to(baseline.resolve());p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(archive.read(entry));old_hashes[entry.filename]=sha(p)
 for name in ('source.mp4','pulses.wav'):shutil.copyfile(ROOT/'docs/assets/text-animation-20261017'/name,output/name)
 shutil.copyfile(license_file,output/'font-license.txt')
 def ff(args,data=None):
  p=subprocess.run(['ffmpeg','-v','error',*map(str,args)],input=data,capture_output=True,timeout=300)
  if p.returncode:raise RuntimeError(p.stderr.decode('utf-8','replace'))
  return p.stdout
 ff(['-i',output/'source.mp4','-an','-vf','setpts=N*1001/(30000*TB)','-r','30000/1001','-frames:v','72','-c:v','libx264','-crf','0','-pix_fmt','yuv444p',output/'source-fractional.mp4'])
 provenance={'media_license_spdx':'CC0-1.0','original_generator':'scripts/smoke_subtitle_clock.py','original_generator_sha256':sha(ROOT/'scripts/smoke_subtitle_clock.py'),
  'inputs':{name:sha(output/name) for name in ('source.mp4','pulses.wav')},'fractional_derivative':{'path':'source-fractional.mp4','sha256':sha(output/'source-fractional.mp4'),'source':sha(output/'source.mp4'),'frames':72,'fps':'30000/1001','new_visual_content':False},
  'font':{'family':ImageFont.truetype(str(font),32).getname()[0],'sha256':sha(font),'license_sha256':sha(license_file),'license_spdx':'LicenseRef-DejaVu-Fonts','binary_distributed':False},'third_party_natural_footage':False,'new_model_inference':0}
 save(output/'fixture-provenance.json',provenance)
 calls=[]
 bootstrap='import sys;sys.path.insert(0,sys.argv.pop(1));from ai_ad_editor.runtime import configure_local_runtime;configure_local_runtime();from ai_ad_editor.cli import main;raise SystemExit(main())'
 def cli(*args,old=False,allow_failure=False):
  command=[sys.executable,'-I','-B','-X','utf8','-c',bootstrap,str(baseline/'product/src' if old else ROOT/'product/src'),*map(str,args)]
  began=time.monotonic();p=subprocess.run(command,cwd=ROOT,capture_output=True,timeout=300)
  (work/f'call-{len(calls):03}.stdout.log').write_bytes(p.stdout);(work/f'call-{len(calls):03}.stderr.log').write_bytes(p.stderr)
  value=json.loads(p.stdout.decode('utf-8-sig'));calls.append({'args':list(map(str,args)),'baseline':old,'exit_code':p.returncode,'seconds':time.monotonic()-began,'result':value});save(work/'partial-calls.json',calls)
  if p.returncode and not allow_failure:raise RuntimeError(json.dumps(value,ensure_ascii=False)[:4000])
  return value
 def decode(path):return np.frombuffer(ff(['-i',path,'-map','0:v:0','-an','-pix_fmt','rgb24','-f','rawvideo','pipe:1']),np.uint8).reshape(-1,H,W,3)
 def pcm(path):return 'sha256:'+hashlib.sha256(ff(['-i',path,'-map','0:a:0','-vn','-acodec','pcm_f32le','-f','f32le','pipe:1'])).hexdigest()
 def probe(path):return json.loads(subprocess.run(['ffprobe','-v','error','-count_frames','-show_streams','-show_format','-of','json',str(path)],capture_output=True,check=True).stdout)
 def step(left,right,*,start=.125,reverse=False,mode='linear',speeds=(1.,1.),controls=(),ticks=None):
  pieces=[(0.,right-left,*speeds,mode,controls)]
  duration_tick=round(integral(right-left,pieces)*TPS) if ticks is None else ticks
  return {'in':left,'out':right,'start_tick':round(start*TPS),'start':round(start*TPS)/TPS,'duration_tick':duration_tick,'duration':duration_tick/TPS,'reverse':reverse,'pieces':pieces}
 curve=step(.2,2.8,reverse=True,mode='bezier',speeds=(.6,2.8),controls=(.15,.05,.85,.7))
 inner={**copy.deepcopy(curve),'start':0.,'start_tick':0}
 scenarios={
  'retained-typing-tail':{'steps':[curve],'typing':True},
  'forward-bezier':{'steps':[step(.2,2.8,mode='bezier',speeds=(.6,2.8),controls=(.15,.05,.85,.7))]},
  'reverse-linear':{'steps':[step(.217,2.797,start=.137,reverse=True,speeds=(.6,2.8))]},
  'fractional-output':{'steps':[curve],'fps':[30000,1001]},
  'one-tick-boundary':{'steps':[step(.2,2.8,start=11251/TPS,ticks=2*TPS)]},
  'tiny-forward':{'steps':[step(.201,.205,speeds=(.016,.016),ticks=TPS//4)]},
  'tiny-reverse':{'steps':[step(.201,.205,reverse=True,speeds=(.016,.016),ticks=TPS//4)]},
  'double-reverse':{'steps':[inner,step(.125,inner['duration']-.125,start=.137,reverse=True,speeds=(.8,1.4))]},
  'fractional-source':{'steps':[step(.2,2.2,reverse=True,mode='bezier',speeds=(.6,2.8),controls=(.15,.05,.85,.7))],'source_fps':[30000,1001],'source_end':2.4024},
  'aligned-control':{'steps':[step(.25,2.75)]},
 }
 if cases:scenarios={name:scenarios[name] for name in cases.split(',')}
 records={};preview=None
 for name,config in scenarios.items():
  steps=config['steps'];rate=Fraction(*config.get('fps',[24,1]));source_rate=Fraction(*config.get('source_fps',[24,1]));project=work/name
  cli('project','init',project)
  p=json.loads((project/'project.json').read_text(encoding='utf-8-sig'));p['settings']['canvas'].update(width=W,height=H);p['settings']['timebase']['display_fps']={'num':rate.numerator,'den':rate.denominator};save(project/'project.json',p)
  source_name='source.mp4' if source_rate==24 else 'source-fractional.mp4'
  for path,asset,license_id,evidence in [(output/source_name,'frames','CC0-1.0',output/'fixture-provenance.json'),(output/'pulses.wav','pulses','CC0-1.0',output/'fixture-provenance.json'),*([(font,'local_font','LicenseRef-DejaVu-Fonts',output/'font-license.txt')] if config.get('typing') else [])]:
   cli('media','ingest','--project',project,'--input',path,'--asset-id',asset,'--source-url','local://authored-nested-frame-coverage','--license-spdx',license_id,'--verification-status','verified','--permitted-use','commercial_ad','--evidence',evidence)
  leaf_end=round(config.get('source_end',3.)*TPS);operations=[{'op':'add_sequence','id':'child_0','duration_tick':leaf_end}]
  for track,asset in [('child_0_video_1','frames'),('child_0_audio_1','pulses')]:operations.append({'op':'append_clip','sequence_id':'child_0','track_id':track,'id':'leaf' if asset=='frames' else 'audio','asset_id':asset,'source_in_tick':0,'source_out_tick':leaf_end,'duration_tick':leaf_end})
  subtitle=None
  if config.get('typing'):
   subtitle={'text':'HHHH   HHHH','style':{'font_asset_id':'local_font','fontsize':32,'y':'212','box':False,'expansion':'none'},'animation':{'type':'typewriter','delay':.12,'duration':2.3},'word_timing':[{'text':'HHHH','start_char':0,'start':.15,'end':1.4},{'text':'HHHH','start_char':7,'start':1.4,'end':2.8}]}
   operations.extend([{'op':'add_track','sequence_id':'child_0','track_id':'titles','kind':'subtitle','order':2},{'op':'append_clip','sequence_id':'child_0','track_id':'titles','id':'title','generator':{'type':'text'},'source_in_tick':0,'source_out_tick':leaf_end,'duration_tick':leaf_end,'subtitle':subtitle}])
  child='child_0'
  for index,s in enumerate(steps):
   target='seq_main' if index==len(steps)-1 else f'child_{index+1}'
   if target!='seq_main':operations.append({'op':'add_sequence','id':target,'duration_tick':s['start_tick']+s['duration_tick']})
   _,span,a,b,mode,controls=s['pieces'][0];point={'at_tick':0,'speed':a,'interpolation':mode}
   if controls:point['control_points']=list(controls)
   operations.append({'op':'append_sequence_clip','sequence_id':target,'track_id':'track_video_1' if target=='seq_main' else target+'_video_1','nested_sequence_id':child,'id':f'parent_{index}','source_in_tick':round(s['in']*TPS),'source_out_tick':round(s['out']*TPS),'timeline_start_tick':s['start_tick'],'duration_tick':s['duration_tick'],'reverse':s['reverse'],'speed_curve':{'keyframes':[point,{'at_tick':round(span*TPS),'speed':b}]}})
   child=target
  change=work/f'{name}-changes.json';save(change,{'operations':operations});cli('timeline','compose','--project',project,'--input',change)
  total_frames=math.ceil((steps[-1]['start']+steps[-1]['duration']+.25)*float(rate));total_tick=round(Fraction(total_frames,1)/rate*TPS)
  def restore_duration():
   p=json.loads((project/'project.json').read_text(encoding='utf-8-sig'));p['sequences'][0]['duration_tick']=total_tick;save(project/'project.json',p)
  restore_duration()
  def authored():
   p=json.loads((project/'project.json').read_text(encoding='utf-8-sig'));return 'sha256:'+hashlib.sha256(json.dumps({key:p[key] for key in ('assets','settings','sequences')},sort_keys=True).encode()).hexdigest()
  variants={};images={};invariants=[]
  for variant in ['before','after',*(['full','blank'] if subtitle else [])]:
   if variant in ('full','blank'):
    control=copy.deepcopy(subtitle);control.pop('animation');control.pop('word_timing')
    if variant=='blank':control['style']['fontcolor']='white@0'
    change=work/f'{name}-{variant}.json';save(change,{'operations':[{'op':'update_clip','sequence_id':'child_0','clip_id':'title','patch':{'subtitle':control}}]});cli('timeline','compose','--project',project,'--input',change);restore_duration()
   author,ledger=authored(),sha(project/'rights-ledger.json');path=project/f'renders/{variant}.mp4'
   result=cli('render','--project',project,'--output',path,'--crf','0','--pixel-format','yuv444p','--publish',old=variant=='before')
   final=output/f'{variant}-{name}.mp4';shutil.copyfile(path,final);shutil.copyfile(Path(str(path)+'.manifest.json'),Path(str(final)+'.manifest.json'))
   assert author==authored() and ledger==sha(project/'rights-ledger.json');invariants.append({'variant':variant,'authored_sha256':author,'ledger_sha256':ledger,'unchanged':True})
   images[variant]=decode(final);assert len(images[variant])==total_frames,(name,variant,len(images[variant]),total_frames)
   variants[variant]={'path':final.name,'sha256':sha(final),'frames':total_frames,'probe':probe(final),'audio_pcm_f32_sha256':pcm(final),'warnings':result['data'].get('warnings',[])}
   if variant=='after':
    quality=cli('quality','check','--project',project,'--input',path,'--require-audio','--expensive','--max-true-peak-dbfs','-1','--report',project/'validation/coverage.json',allow_failure=name in ('tiny-forward','tiny-reverse'))['data']
    manifest=json.loads(Path(str(final)+'.manifest.json').read_text(encoding='utf-8-sig'))
  policy=cli('policy','audit','--project',project)['data'];rows=[]
  for i in range(total_frames):
   at=float(Fraction(i,1)/rate);author=at;visible=True
   for s in reversed(steps):
    if not s['start']<=author<s['start']+s['duration']:visible=False;break
    author=inverse(s,author)
   wanted=max(0,min(71,math.floor(author*float(source_rate)+1e-7))) if visible else None
   row={'frame':i,'display_seconds':at,'author_seconds':author,'expected_visible':visible,'expected_source_frame':wanted}
   for variant in ('before','after'):
    frame=images[variant][i];present=bool(frame[140,250,1]>35);code=sum(1<<bit for bit in range(7) if frame[50,60+64*bit,0]>128)
    row[variant]={'present':present,'source_frame':code,'source_frame_error':abs(code-wanted) if visible and present else None,'visibility_matches':present==visible}
   rows.append(row)
  for variant in ('before','after'):
   variants[variant]['visibility_mismatch_frames']=[r['frame'] for r in rows if not r[variant]['visibility_matches']]
   variants[variant]['source_error_frames']=[r['frame'] for r in rows if (r[variant]['source_frame_error'] or 0)>1]
   variants[variant]['max_source_frame_error']=max(r[variant]['source_frame_error'] or 0 for r in rows)
   variants[variant]['full_frame_coverage_passed']=not (variants[variant]['visibility_mismatch_frames'] or variants[variant]['source_error_frames'])
  assert variants['after']['full_frame_coverage_passed'],(name,variants['after'])
  assert len({v['audio_pcm_f32_sha256'] for v in variants.values()})==1,(name,'changed audio')
  audio_samples=np.frombuffer(ff(['-i',output/variants['after']['path'],'-map','0:a:0','-vn','-acodec','pcm_f32le','-f','f32le','pipe:1']),np.float32)
  audio_review={'nonzero_pcm_samples':int(np.count_nonzero(audio_samples)),'sample_count':len(audio_samples),'maximum_absolute_sample':float(np.max(np.abs(audio_samples))) if len(audio_samples) else 0.,'unexpected_silence':not bool(np.any(audio_samples))}
  if not quality['ok']:
   assert name in ('tiny-forward','tiny-reverse') and audio_review['unexpected_silence'],(name,quality)
   assert [v['code'] for v in quality['errors']]==['OUTPUT_TRUE_PEAK_UNAVAILABLE'],(name,quality)
  else:assert not audio_review['unexpected_silence'],(name,'authored tone unexpectedly silent')
  prefix=None
  if subtitle:
   prior=json.loads((ROOT/'docs/assets/text-animation-20261017/evidence.json').read_text(encoding='utf-8-sig'))['records']['typing-nested-trim']
   boxes=prior['static_glyph_boxes'];checks=[];units=list(subtitle['text']);animation=subtitle['animation']
   for row in rows:
    author=row['author_seconds']-.5/TPS;count=sum(author>=round(animation['delay']+j*animation['duration']/len(units),9) for j in range(len(units))) if row['expected_visible'] else 0
    glyphs=sum(not c.isspace() for c in units[:count]);expected=images['blank'][row['frame']].copy();observations=[]
    for j,(left,top,right,bottom) in enumerate(boxes):
     if j<glyphs:expected[top:bottom,left:right]=images['full'][row['frame'],top:bottom,left:right]
     full=images['full'][row['frame'],top:bottom,left:right];actual=images['after'][row['frame'],top:bottom,left:right];mask=np.min(full,axis=2)>180
     selected=float(((full[:,:,2].astype(float)-actual[:,:,2])>45)[mask].mean()) if mask.any() and j<glyphs else 0.
     word=subtitle['word_timing'][j//4];want=j<glyphs and word['start']<=author<word['end']
     reveal=int(((actual[:,:,0]>180)&(actual[:,:,1]>180)&mask).sum())>15
     observations.append({'glyph':j,'revealed':reveal,'expected_revealed':j<glyphs,'selected_fraction':selected,'expected_selected':want,'matches':reveal==(j<glyphs) and (selected>=.98 if want else selected<=.01)})
    error=int(np.abs(images['after'][row['frame'],:,:,:2].astype(np.int16)-expected[:,:,:2].astype(np.int16)).max())
    checks.append({'frame':row['frame'],'prefix_rg_max_error':error,'glyph_observations':observations})
   prefix={'max_rg_error':max(r['prefix_rg_max_error'] for r in checks),'glyph_or_word_mismatches':sum(not o['matches'] for r in checks for o in r['glyph_observations']),'rows':checks,'glyph_boxes':boxes}
   assert prefix['max_rg_error']<=3 and prefix['glyph_or_word_mismatches']==0,(name,prefix)
  records[name]={'config':config,'operations':operations,'subtitle':subtitle,'total_frames':total_frames,'sequence_duration_tick':total_tick,'variants':variants,'rows':rows,'typing':prefix,'new_manifest_inputs':manifest['inputs'],'quality':quality,'policy':policy,'render_invariants':invariants,'all_variant_audio_equal':True,'decoded_audio_review':audio_review,'full_delivery_verified':bool(quality['ok'] and not audio_review['unexpected_silence'])}
  save(work/'partial-records.json',records)
  print(json.dumps({'case':name,'frames':total_frames,'old_visibility_failures':variants['before']['visibility_mismatch_frames'],'new_visibility_failures':variants['after']['visibility_mismatch_frames'],'old_max_source_error':variants['before']['max_source_frame_error'],'new_max_source_error':variants['after']['max_source_frame_error'],'full_delivery_verified':records[name]['full_delivery_verified'],'unexpected_silence':audio_review['unexpected_silence']}),flush=True)
  for index in sorted({0,total_frames//2,total_frames-1,*([50,51] if subtitle else [])}):Image.fromarray(images['after'][index]).save(output/f'selected-{name}-{index:03}.png')
  if preview is None:preview={'images':{k:v.copy() for k,v in images.items() if k in ('before','after')},'rows':copy.deepcopy(rows),'rate':rate,'config':config}
 # Preview the actual visible clip, including its failing historical tail.
 count=52 if list(records)[0]=='retained-typing-tail' else min(72,len(preview['rows']));strips=[]
 original=decode(output/'source.mp4');small=ImageFont.truetype(str(font),18)
 for i in range(count):
  wanted=preview['rows'][i]['expected_source_frame'];source=np.zeros((H,W,3),np.uint8) if wanted is None else original[wanted]
  image=Image.new('RGB',(W*3,H+44),(20,23,30));draw=ImageDraw.Draw(image)
  for col,(label,frame) in enumerate([('SOURCE AT AUTHOR TIME',source),('ARCHIVED CLI / BEFORE',preview['images']['before'][i]),('CURRENT CLI / FRAME COVERAGE',preview['images']['after'][i])]):
   image.paste(Image.fromarray(frame),(W*col,44));draw.text((W*col+8,12),label,font=small,fill='white')
  strips.append(image)
 rate=preview['rate'];ff(['-f','rawvideo','-pix_fmt','rgb24','-s',f'{W*3}x{H+44}','-r',f'{rate.numerator}/{rate.denominator}','-i','pipe:0','-an','-c:v','libx264','-crf','16','-pix_fmt','yuv420p',output/'nested-frame-comparison.mp4'],np.asarray([np.asarray(v) for v in strips],np.uint8).tobytes())
 durations=[int(round(100*(i+1)/float(rate)))*10-int(round(100*i/float(rate)))*10 for i in range(count)]
 smaller=[v.resize((1152,249),Image.Resampling.LANCZOS) for v in strips];smaller[0].save(output/'nested-frame-comparison.gif',save_all=True,append_images=smaller[1:],duration=durations,loop=0,disposal=2,optimize=False)
 sheet=Image.new('RGB',(W*3,(H+44)*3))
 samples=[0,count//2,count-1]
 for row,i in enumerate(samples):sheet.paste(strips[i],(0,row*(H+44)))
 sheet.save(output/'contact-sheet.png');after=frozen();assert after==freeze
 media={p.name:{'sha256':sha(p),'bytes':p.stat().st_size} for p in sorted(output.iterdir()) if p.is_file()}
 evidence={'started_at_utc':started,'finished_at_utc':datetime.now(timezone.utc).isoformat(),'baseline_ref':BASELINE,'baseline_source_sha256':old_hashes,'generator_sha256':sha(Path(__file__)),'clock_oracle_sha256':sha(ROOT/'scripts/smoke_speed_easing.py'),'frozen_before':freeze,'frozen_after':after,'provenance':provenance,'calls':calls,'records':records,'media':media,
  'gates':{'visible_frame_mismatches':0,'source_frame_error':1,'typing_prefix_rg_max_error':3,'glyph_or_word_mismatches':0,'equal_pcm_across_variants':True},
  'preview':{'frames':count,'fps':str(rate),'seconds':count/float(rate),'gif_durations_ms':durations,'gif_seconds':sum(durations)/1000,'audio':False,'static_samples':samples,'original_column':'original decoded frame selected by independent author-time oracle; black for authored gaps; no simulated product effect','continuous_playback_reviewed':False,'audio_listened':False},
  'limits':['Controlled FFmpeg 8.1 SDR CFR source/output frames; general VFR/HDR/complex grouping and performance not accepted','Source timing error gate is at most one registered source frame; visibility must match every output sample','Tiny 4 ms audio slowed to 250 ms becomes silent with the existing atempo chain; retain failed quality/complete delivery, not accepted by video coverage','Audio equality proves preservation between variants, not phase/tempo/listening quality','Publication timeline is explicitly aligned to the final frame grid; arbitrary nonaligned durations remain unaccepted','Original V24 failure and raw evidence are retained without rewriting historical results'],'new_model_inference':0}
 save(output/'evidence.json',evidence)
 print(json.dumps({'cases':len(records),'cli_calls':len(calls),'renders':sum(c['args'][0]=='render' for c in calls),'new_main_frames':sum(v['total_frames'] for v in records.values()),'control_frames':sum(v['total_frames']*(len(v['variants'])-2) for v in records.values()),'files':len(media)+1,'passed_deliveries':sum(v['full_delivery_verified'] for v in records.values()),'failed_deliveries':sum(not v['full_delivery_verified'] for v in records.values())}),flush=True)

if __name__=='__main__':
 parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True);parser.add_argument('--work',type=Path,required=True);parser.add_argument('--font',type=Path,required=True);parser.add_argument('--font-license',type=Path,required=True);parser.add_argument('--cases');args=parser.parse_args()
 run(args.output.resolve(),args.work.resolve(),args.font.resolve(),args.font_license.resolve(),args.cases)
