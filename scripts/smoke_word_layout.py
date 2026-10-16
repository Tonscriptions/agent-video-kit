"""Actual archived/current CLI glyph comparisons, controls and public previews.

Native Windows, local FFmpeg/NumPy/Pillow and explicitly licensed local fonts.
Original authored CC0 video/audio are reused byte-for-byte from V21. No model
inference, browser, network, service or GUI participates in execution.
"""
from __future__ import annotations
import argparse, bisect, copy, hashlib, io, json, math, shutil, subprocess, sys, time, zipfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))
from smoke_speed_easing import integral, forward, inverse
BASELINE = '7beb9ce0f2715f1c83067cc98f58e0a40c36d64b'
W, H, FPS, TPS = 512, 288, 24, 90000

def sha(path): return 'sha256:'+hashlib.sha256(path.read_bytes()).hexdigest()
def save(path, value): path.write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n', encoding='utf-8', newline='\n')
def frozen(): return {p.relative_to(ROOT).as_posix():sha(p) for p in sorted([*(ROOT/'product/src').rglob('*.py'), *(ROOT/'product/tests').rglob('*.py'), ROOT/'docs/specs/agent-project.schema.json'])}

def run(output, work, font, license_file, cjk_font, cjk_license, cases=None):
 import numpy as np
 from PIL import Image, ImageDraw, ImageFont, ImageSequence
 if output.exists() or work.exists(): raise ValueError('Use fresh directories; earlier failures are evidence')
 output.mkdir(parents=True); work.mkdir(parents=True)
 for path in (font, license_file, cjk_font, cjk_license):
  if not path.is_file(): raise ValueError(f'Local font/license missing: {path}')
 start=datetime.now(timezone.utc).isoformat(); frozen_before=frozen()
 archive=subprocess.run(['git','-c','core.autocrlf=false','archive','--format=zip',BASELINE,'product/src','docs/specs/agent-project.schema.json'],cwd=ROOT,capture_output=True,check=True).stdout
 baseline=work/'baseline'; old_hashes={}
 with zipfile.ZipFile(io.BytesIO(archive)) as package:
  for entry in package.infolist():
   if entry.is_dir(): continue
   path=(baseline/entry.filename).resolve()
   if not path.is_relative_to(baseline.resolve()): raise ValueError('Archive path escapes root')
   path.parent.mkdir(parents=True,exist_ok=True); path.write_bytes(package.read(entry)); old_hashes[entry.filename]=sha(path)
 for name in ('source.mp4','pulses.wav'): shutil.copyfile(ROOT/'docs/assets/subtitle-clock-20261016'/name, output/name)
 shutil.copyfile(license_file,output/'font-license.txt'); shutil.copyfile(cjk_license,output/'cjk-font-license.txt')
 fonts=[{'name':p.name,'family':ImageFont.truetype(str(p),28).getname()[0],'sha256':sha(p),'license_spdx':label,'license_sha256':sha(lic),'binary_distributed':False} for p,lic,label in [(font,license_file,'LicenseRef-DejaVu-Fonts'),(cjk_font,cjk_license,'Apache-2.0')]]
 provenance={'media_license_spdx':'CC0-1.0','source_generator':'scripts/smoke_subtitle_clock.py','source_generator_sha256':sha(ROOT/'scripts/smoke_subtitle_clock.py'),'source_inputs':{name:sha(output/name) for name in ('source.mp4','pulses.wav')},'fonts':fonts,'third_party_natural_footage':False,'model_inference':False}
 save(output/'fixture-provenance.json',provenance)
 calls=[]
 bootstrap='import sys;sys.path.insert(0,sys.argv.pop(1));from ai_ad_editor.runtime import configure_local_runtime;configure_local_runtime();from ai_ad_editor.cli import main;raise SystemExit(main())'
 def cli(*args, old=False):
  argv=[sys.executable,'-I','-B','-X','utf8','-c',bootstrap,str(baseline/'product/src' if old else ROOT/'product/src'),*map(str,args)]
  began=time.monotonic(); p=subprocess.run(argv,cwd=ROOT,capture_output=True,timeout=300)
  (work/f'call-{len(calls):03}.stdout.log').write_bytes(p.stdout); (work/f'call-{len(calls):03}.stderr.log').write_bytes(p.stderr)
  value=json.loads(p.stdout.decode('utf-8-sig')); calls.append({'args':list(map(str,args)),'baseline':old,'seconds':time.monotonic()-began,'exit_code':p.returncode,'result':value}); save(work/'partial-calls.json',calls)
  if p.returncode: raise RuntimeError(json.dumps(value,ensure_ascii=False)[:3000])
  return value
 def ff(args, data=None):
  p=subprocess.run(['ffmpeg','-v','error',*map(str,args)],input=data,capture_output=True,timeout=300)
  if p.returncode: raise RuntimeError(p.stderr.decode('utf-8','replace'))
  return p.stdout
 def decode(path): return np.frombuffer(ff(['-i',path,'-map','0:v:0','-an','-pix_fmt','rgb24','-f','rawvideo','pipe:1']),np.uint8).reshape(-1,H,W,3)
 def encode(path,frames,w,h): ff(['-f','rawvideo','-pix_fmt','rgb24','-s',f'{w}x{h}','-r',FPS,'-i','pipe:0','-an','-c:v','libx264','-crf','16','-pix_fmt','yuv420p',path],np.asarray(frames,np.uint8).tobytes())
 scenarios={
  'inline':{'text':'FEATURE BENEFIT','independent':False,'style':{'x':'72','y':'220'}},
  'center-repeat':{'text':'AV   VA   AV','style':{'y':'220','fontsize':32}},
  'multiline':{'text':'gyp   HI\nFEATURE   BENEFIT','style':{'x':'40','y':'184','fontsize':26,'line_spacing':10,'text_align':'right+bottom','boxw':420,'boxh':96}},
  'wrap':{'text':'FEATURE  BENEFIT  FEATURE','style':{'x':'40','y':'176','fontsize':24,'line_spacing':7,'max_width':215,'boxw':420,'text_align':'center'}},
  'styled':{'text':'FEATURE BENEFIT','style':{'x':'72','y':'220','borderw':2,'bordercolor':'black','shadowx':3,'shadowy':4,'shadowcolor':'black@0.6','box':True,'boxcolor':'blue@0.3','box_padding':7}},
  'moving':{'text':'FEATURE BENEFIT','style':{'x':'24+20*t','y':'214+4*sin(t)','fix_bounds':True}},
  'combining':{'text':'Cafe\u0301  AV  50%','style':{'x':'72','y':'220','expansion':'none'}},
  'cjk':{'text':'广   告   素   材','style':{'x':'72','y':'220','fontsize':30}},
  'nested-reverse':{'text':'FEATURE BENEFIT','independent':False,'style':{'x':'72','y':'220'},'nested':True},
 }
 if cases:
  selected=cases.split(',')
  if any(name not in scenarios for name in selected):raise ValueError('Unknown scenario')
  scenarios={name:scenarios[name] for name in selected}
 records={}; decoded={}; projects={}
 for name,config in scenarios.items():
  project=work/name; projects[name]=project; cli('project','init',project)
  p=json.loads((project/'project.json').read_text(encoding='utf-8-sig')); p['settings']['canvas'].update(width=W,height=H); p['settings']['timebase']['display_fps']={'num':FPS,'den':1}; p['sequences'][0]['duration_tick']=3*TPS; save(project/'project.json',p)
  for path,asset,label,evidence in [(output/'source.mp4','frames','CC0-1.0',output/'fixture-provenance.json'),(output/'pulses.wav','pulses','CC0-1.0',output/'fixture-provenance.json'),(cjk_font if name=='cjk' else font,'local_font',fonts[1 if name=='cjk' else 0]['license_spdx'],output/('cjk-font-license.txt' if name=='cjk' else 'font-license.txt'))]:
   cli('media','ingest','--project',project,'--input',path,'--asset-id',asset,'--source-url','local://authored-word-layout','--license-spdx',label,'--verification-status','verified','--permitted-use','commercial_ad','--evidence',evidence)
  style={'font_asset_id':'local_font','fontsize':28,'box':False,'active_color':'yellow',**config['style']}
  words=config['text'].split(); entries=[]; cursor=0
  for i,word in enumerate(words):
   at=config['text'].find(word,cursor);cursor=at+len(word);entries.append({'text':word,'start_char':at,'start':.15+i*2.5/len(words),'end':.15+(i+1)*2.5/len(words)})
  subtitle={'text':config['text'],'style':style,'word_timing':entries}
  independent=config.get('independent',True); nested=config.get('nested',False); sequence='child' if nested else 'seq_main'; video_track='child_video_1' if nested else 'track_video_1'; audio_track='child_audio_1' if nested else 'track_audio_1'
  operations=[{'op':'add_sequence','id':'child','duration_tick':3*TPS}] if nested else []
  leaf={'op':'append_clip','sequence_id':sequence,'track_id':video_track,'id':'leaf','asset_id':'frames','source_in_tick':0,'source_out_tick':3*TPS,'duration_tick':3*TPS}
  operations.append(leaf); target='leaf'
  if independent:
   target='title'; operations.extend([{'op':'add_track','sequence_id':sequence,'track_id':'titles','kind':'subtitle','order':2},{'op':'append_clip','sequence_id':sequence,'track_id':'titles','id':target,'generator':{'type':'text'},'source_in_tick':0,'source_out_tick':3*TPS,'duration_tick':3*TPS,'subtitle':subtitle}])
  else: leaf['subtitle']=subtitle
  operations.append({'op':'append_clip','sequence_id':sequence,'track_id':audio_track,'id':'audio','asset_id':'pulses','source_in_tick':0,'source_out_tick':3*TPS,'duration_tick':3*TPS})
  step=None
  if nested:
   pieces=[(0.,3.,.6,2.8,'bezier',(.15,.05,.85,.7))]; duration=round(integral(3.,pieces)*TPS)/TPS
   step={'in':0.,'out':3.,'start':0.,'duration':duration,'reverse':True,'pieces':pieces}
   operations.append({'op':'append_sequence_clip','track_id':'track_video_1','id':'container','nested_sequence_id':sequence,'source_in_tick':0,'source_out_tick':3*TPS,'duration_tick':round(duration*TPS),'reverse':True,'speed_curve':{'keyframes':[{'at_tick':0,'speed':.6,'interpolation':'bezier','control_points':[.15,.05,.85,.7]},{'at_tick':3*TPS,'speed':2.8,'interpolation':'linear'}]}})
  changes=work/f'{name}-changes.json'; save(changes,{'operations':operations}); cli('timeline','compose','--project',project,'--input',changes)
  if nested:
   p=json.loads((project/'project.json').read_text(encoding='utf-8-sig'));p['sequences'][0]['duration_tick']=round(step['duration']*TPS);save(project/'project.json',p)
  def author_hash():
   p=json.loads((project/'project.json').read_text(encoding='utf-8-sig'));return 'sha256:'+hashlib.sha256(json.dumps({k:p[k] for k in ('assets','settings','sequences')},sort_keys=True).encode()).hexdigest()
  unchanged=[]; variants={}; quality=None
  for variant in ('before','after','reference'):
   if variant=='reference':
    plain=copy.deepcopy(subtitle);plain.pop('word_timing');change=work/f'{name}-reference.json';save(change,{'operations':[{'op':'update_clip','sequence_id':sequence,'clip_id':target,'patch':{'subtitle':plain}}]});cli('timeline','compose','--project',project,'--input',change)
   authored,ledger=author_hash(),sha(project/'rights-ledger.json'); path=project/f'renders/{variant}.mp4'
   result=cli('render','--project',project,'--output',path,'--crf','0','--pixel-format','yuv444p','--publish',old=variant=='before')
   final=output/f'{variant}-{name}.mp4';shutil.copyfile(path,final);shutil.copyfile(Path(str(path)+'.manifest.json'),Path(str(final)+'.manifest.json'))
   frames=decode(final);decoded[variant+'-'+name]=frames
   assert authored==author_hash() and ledger==sha(project/'rights-ledger.json')
   unchanged.append({'variant':variant,'authored_sha256':authored,'ledger_sha256':ledger,'unchanged':True})
   probe=json.loads(subprocess.run(['ffprobe','-v','error','-count_frames','-show_streams','-show_format','-of','json',str(final)],capture_output=True,check=True).stdout)
   variants[variant]={'path':final.name,'sha256':sha(final),'manifest_sha256':sha(Path(str(final)+'.manifest.json')),'probe':probe,'frames':len(frames),'warnings':result['data'].get('warnings',[])}
   if variant=='after':quality=cli('quality','check','--project',project,'--input',path,'--require-audio','--expensive','--fail-on-black','--max-true-peak-dbfs','-1','--report',project/'validation/word-layout.json')['data']
  reference=decoded['reference-'+name]; rows=[]
  for variant in ('before','after'):
   frames=decoded[variant+'-'+name];assert frames.shape==reference.shape
   measured=[]
   for i,(frame,control) in enumerate(zip(frames,reference)):
    delta=np.abs(frame[:,:,:2].astype(np.int16)-control[:,:,:2].astype(np.int16));at=inverse(step,i/FPS)-.5/TPS if step else i/FPS
    active=[j for j,e in enumerate(entries) if e['start']<=at<e['end']]
    white=(control[:,:,0]>145)&(control[:,:,1]>160)&(control[:,:,2]>175);white[:176]=False
    # Derive word regions from the actual untimed encoded control, not from
    # product advance metrics. Large whitespace separates these fixtures.
    ys=np.flatnonzero(white.any(axis=1)); lines=[]
    for y in ys:
     if not lines or y-lines[-1][-1]>4:lines.append([int(y)])
     else:lines[-1].append(int(y))
    boxes=[]
    for line in lines:
     xs=np.flatnonzero(white[line[0]:line[-1]+1].any(axis=0));groups=[]
     for x in xs:
      if not groups or x-groups[-1][-1]>7:groups.append([int(x)])
      else:groups[-1].append(int(x))
     boxes.extend((group[0],line[0],group[-1]+1,line[-1]+1) for group in groups)
    if len(boxes)!=len(words):raise ValueError(f'Independent control segmentation failed {name} frame {i}: {len(boxes)} vs {len(words)}')
    counts=[]
    for left,top,right,bottom in boxes:
     selection=white[top:bottom,left:right] & (control[top:bottom,left:right,2].astype(np.int16)-frame[top:bottom,left:right,2].astype(np.int16)>45)
     counts.append(int(selection.sum()))
    observed=[j for j,count in enumerate(counts) if count>=10]
    source=sum(1<<bit for bit in range(7) if frame[50,60+64*bit,0]>128)
    if step:
     candidates=sorted((forward(step,(j+1)/FPS),j) for j in range(72));pos=max(0,bisect.bisect_right([x[0] for x in candidates],i/FPS+2e-5)-1);expected_source=candidates[pos][1]
    else:expected_source=i
    measured.append({'frame':i,'author_seconds':at,'rg_max_error':int(delta.max()),'rg_mean_error':float(delta.mean()),'word_boxes':boxes,'selected_counts':counts,'expected_active':active,'observed_active':observed,'timing_matches':active==observed,'source_frame':source,'expected_source_frame':expected_source,'source_frame_error':abs(source-expected_source)})
   variants[variant].update(rows=measured,max_rg_error=max(r['rg_max_error'] for r in measured),timing_mismatches=sum(not r['timing_matches'] for r in measured),max_source_frame_error=max(r['source_frame_error'] for r in measured))
  records[name]={'config':config,'subtitle':subtitle,'operations':operations,'step':step,'variants':variants,'quality':quality,'unchanged_after_renders':unchanged}; save(work/'partial-records.json',records)
  print(json.dumps({'case':name,'before_rg':variants['before']['max_rg_error'],'after_rg':variants['after']['max_rg_error'],'after_timing_mismatches':variants['after']['timing_mismatches']}),flush=True)
  assert variants['after']['max_rg_error']<=3 and variants['after']['timing_mismatches']==0 and variants['after']['max_source_frame_error']<=1
 # A silent source/old/current strip retains all output frames; labels and
 # scaling belong to preview generation, not to the product render itself.
 preview_case=next(iter(scenarios));originals=decode(output/'source.mp4');count=len(decoded['after-'+preview_case]);small=ImageFont.truetype(str(font),18)
 strips=[]
 for i in range(count):
  im=Image.new('RGB',(W*3,H+44),(20,23,30));d=ImageDraw.Draw(im)
  for column,(label,frame) in enumerate([('ORIGINAL INPUT PREFIX',originals[min(i,len(originals)-1)]),('ARCHIVED CLI / OVERPAINT',decoded['before-'+preview_case][i]),('CURRENT CLI / COLOR SELECTION',decoded['after-'+preview_case][i])]):
   im.paste(Image.fromarray(frame),(column*W,44));d.text((column*W+14,12),label,font=small,fill='white')
  strips.append(im)
 encode(output/'word-layout-comparison.mp4',[np.asarray(x) for x in strips],W*3,H+44)
 gif=[im.resize((1152,249)) for im in strips];durations=[round((i+1)*100/FPS)*10-round(i*100/FPS)*10 for i in range(count)]
 gif[0].save(output/'word-layout-comparison.gif',save_all=True,append_images=gif[1:],duration=durations,loop=0,optimize=False,disposal=2)
 samples=(0,count//2,count-1);sheet=Image.new('RGB',(W*3,(H+44)*len(samples)))
 for row,i in enumerate(samples):sheet.paste(strips[i],(0,row*(H+44)))
 sheet.save(output/'contact-sheet.png')
 # Include dedicated multi-line/CJK crops for actual manual image inspection.
 for name in ('multiline','wrap','cjk','styled','combining'):
  if name in scenarios:Image.fromarray(decoded['after-'+name][40]).save(output/f'selected-{name}.png')
 frozen_after=frozen();assert frozen_before==frozen_after
 media={p.name:{'sha256':sha(p),'bytes':p.stat().st_size} for p in output.iterdir() if p.suffix.lower() in {'.mp4','.gif','.png','.wav'}}
 result={'started_at_utc':start,'finished_at_utc':datetime.now(timezone.utc).isoformat(),'baseline_ref':BASELINE,'baseline_source_sha256':old_hashes,'generator_sha256':sha(Path(__file__)),'clock_oracle_sha256':sha(ROOT/'scripts/smoke_speed_easing.py'),'frozen_before':frozen_before,'frozen_after':frozen_after,'calls':calls,'records':records,'provenance':provenance,'media':media,'preview':{'frames':count,'fps':FPS,'mp4_seconds':count/FPS,'gif_frame_durations_ms':durations,'gif_seconds':sum(durations)/1000,'audio':False,'manual_selected_frames':list(samples),'continuous_playback_reviewed':False,'audio_listened':False},'gates':{'rg_max_error':3,'source_frame_error':1,'word_selection_blue_delta':45,'word_selection_pixels':10},'model_inference_runs':0,'limits':['synthetic controlled typography, not general natural quality','CJK font only accepts the four verified glyphs here','Pillow line-break choice remains separate from native paint selection','bidirectional/internal shaping-cluster highlights rejected','dynamic-size inline highlights suppressed with an explicit warning','word+animation combination incomplete','fontcolor opacity/color semantics beyond ordinary drawtext controls not accepted','no freeze/VFR/general group acceptance']}
 save(output/'evidence.json',result)
 print(json.dumps({'cases':len(records),'cli_calls':len(calls),'renders':sum(c['args'][0]=='render' for c in calls),'quality_checks':sum(c['args'][:2]==['quality','check'] for c in calls),'new_main_frames':sum(v['variants']['after']['frames'] for v in records.values()),'reference_frames':sum(v['variants']['reference']['frames'] for v in records.values()),'max_rg_error':max(v['variants']['after']['max_rg_error'] for v in records.values())}),flush=True)

if __name__=='__main__':
 parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True);parser.add_argument('--work',type=Path,required=True);parser.add_argument('--font',type=Path,required=True);parser.add_argument('--font-license',type=Path,required=True);parser.add_argument('--cjk-font',type=Path,required=True);parser.add_argument('--cjk-font-license',type=Path,required=True);parser.add_argument('--cases');args=parser.parse_args()
 run(args.output.resolve(),args.work.resolve(),args.font.resolve(),args.font_license.resolve(),args.cjk_font.resolve(),args.cjk_font_license.resolve(),args.cases)
