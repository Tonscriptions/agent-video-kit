"""Local CLI area projections versus fixed V31, bilinear and cell-overlap truth.

Procedural CC0 sources only. NumPy/Pillow and an explicitly supplied licensed
font are used by this evidence generator, never by the product runtime.
The reference integrates source pixel cells directly; it uses no summed-area
tables, FFmpeg sampling expressions or product imports.
"""
from __future__ import annotations
import argparse,copy,hashlib,io,json,os,shutil,subprocess,sys,time,zipfile
from datetime import datetime,timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
BASELINE='6c0df5645a5ab4ccbdd746fe0cd5e10f23b4bf93'
TPS,FPS,W,H,N=90000,8,192,108,16
D=2*TPS

def sha(path):return 'sha256:'+hashlib.sha256(path.read_bytes()).hexdigest()
def save(path,value):path.write_text(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8',newline='\n')
def frozen():return {p.relative_to(ROOT).as_posix():sha(p) for p in sorted([*(ROOT/'product/src').rglob('*.py'),*(ROOT/'product/tests').rglob('*.py'),ROOT/'docs/specs/agent-project.schema.json'])}

def description(index):
    return ['three-pixel gray stripes','anisotropic RGB texture','fractional odd-raster crop',
            'animated crop and scale','quarter-turn off-center anchor','17-degree source-axis box',
            'soft alpha and hidden green','same-canvas shrink then parent mask','identity compatibility'][index-1]

def parameters(index,t):
    p={'fit':'stretch'}
    if index==3:p['crop']=(.101,.05,.67,.68)
    if index==4:p.update(crop=(.25*t,.05,.65,.8),scale=.7+.6*t)
    if index==5:p.update(rotation=90.,anchor=(.2,.6))
    if index==6:p.update(rotation=17.,scale=.8)
    if index==8:p.update(scale=1/3,parent_mask=True)
    return p

def source(index):
    import numpy as np
    w,h=(W,H) if index in (8,9) else ((577,325) if index==3 else (576,216 if index==2 else 324))
    yy,xx=np.mgrid[:h,:w];rgba=np.zeros((h,w,4),np.uint8);rgba[...,3]=255
    if index in (1,8):rgba[...,:3]=np.where((xx%3==2)[...,None],255,0)
    elif index==7:
        rgba[...,:3]=(240,30,10);rgba[...,3]=np.choose(xx%3,[0,96,255])
        rgba[xx%3==0,:3]=(0,255,0)
    else:
        rgba[...,0]=(xx%5)*55;rgba[...,1]=(yy%7)*35;rgba[...,2]=((xx+yy)%3)*120
    return rgba

def reference(image,p):
    import numpy as np
    sh,sw=image.shape[:2];cx,cy,cw,ch=p.get('crop',(0.,0.,1.,1.))
    cx*=sw;cy*=sh;cw*=sw;ch*=sh
    fx,fy=W/cw,H/ch;scale=p.get('scale',1.);anchor=p.get('anchor',(.5,.5))
    angle=np.deg2rad(p.get('rotation',0.));c,s=np.cos(angle),np.sin(angle)
    yy,xx=np.mgrid[:H,:W];dx=xx+.5-W/2;dy=yy+.5-H/2
    sx=cx+anchor[0]*cw+(c*dx+s*dy)/(scale*fx)
    sy=cy+anchor[1]*ch+(-s*dx+c*dy)/(scale*fy)
    fw,fh=max(1.,1/(scale*fx)),max(1.,1/(scale*fy))
    left=np.clip(sx-fw/2,cx,cx+cw);right=np.clip(sx+fw/2,cx,cx+cw)
    top=np.clip(sy-fh/2,cy,cy+ch);bottom=np.clip(sy+fh/2,cy,cy+ch)
    ix=np.floor(left).astype(int);iy=np.floor(top).astype(int)
    q=np.zeros((H,W,3),float);native=image[...,:3].astype(float)*(image[...,3:4]/255)
    # Explicit intersection with every potentially overlapping source cell.
    # Offsets are bounded by the footprint, independent of source image area.
    for ystep in range(int(np.ceil(fh))+2):
        y=iy+ystep;wy=np.maximum(0,np.minimum(bottom,y+1)-np.maximum(top,y))
        for xstep in range(int(np.ceil(fw))+2):
            x=ix+xstep;wx=np.maximum(0,np.minimum(right,x+1)-np.maximum(left,x))
            weight=wx*wy*((x>=0)&(x<sw)&(y>=0)&(y<sh))/(fw*fh)
            q+=native[np.clip(y,0,sh-1),np.clip(x,0,sw-1)]*weight[...,None]
    if p.get('parent_mask'):q[:,:W//2]=0
    return np.clip(np.rint(q),0,255).astype(np.uint8)

def operations(index,shape):
    h,w=shape[:2];p=parameters(index,0.);transform={}
    for key in ('scale','rotation'):
        if key in p:transform[key]=p[key]
    if 'anchor' in p:transform['anchor']=dict(zip(('x','y'),p['anchor']))
    crop={'fit':'stretch'}
    if 'crop' in p:crop.update(dict(zip(('x','y','width','height'),p['crop'])),unit='normalized')
    parent={'op':'append_sequence_clip','sequence_id':'seq_main','track_id':'track_video_1','id':'parent',
            'nested_sequence_id':'child','source_in_tick':0,'source_out_tick':D,'duration_tick':D,
            'timeline_start_tick':0,'crop':crop,'transform':transform}
    if index==4:
        def keys(prop,a,b):return {'property':prop,'keyframes':[{'at_tick':0,'value':a,'interpolation':'linear'},
                                         {'at_tick':D,'value':b,'interpolation':'linear'}]}
        parent['keyframes']=[keys('crop.x',0.,.25),keys('transform.scale',.7,1.3)]
    if index==8:parent['mask']={'type':'rectangle','x':.5,'y':0.,'width':.5,'height':1.}
    return [{'op':'add_sequence','id':'child','canvas':{'width':w,'height':h},'duration_tick':D},
            {'op':'append_clip','sequence_id':'child','track_id':'child_video_1','id':'texture','asset_id':'pattern',
             'source_in_tick':0,'source_out_tick':D,'duration_tick':D,'timeline_start_tick':0,'crop':{'fit':'stretch'}},parent]

def run(output,work,font,font_license):
    import numpy as np
    from PIL import Image,ImageDraw,ImageFont
    if output.exists() or work.exists():raise ValueError('Use fresh paths and preserve prior failures')
    output.mkdir(parents=True);work.mkdir(parents=True);before=frozen();started=datetime.now(timezone.utc).isoformat()
    for key in ('TEMP','TMP','TMPDIR'):os.environ[key]=str(work)
    def ff(args,data=None):
        p=subprocess.run(['ffmpeg','-v','error',*map(str,args)],input=data,capture_output=True,timeout=300)
        if p.returncode:raise RuntimeError(p.stderr.decode('utf-8','replace'))
        return p.stdout
    def probe(path):return json.loads(subprocess.check_output(['ffprobe','-v','error','-count_frames','-show_streams','-show_format','-of','json',str(path)]))
    def decode(path):
        v=next(s for s in probe(path)['streams'] if s['codec_type']=='video')
        return np.frombuffer(ff(['-i',path,'-map','0:v:0','-an','-pix_fmt','rgb24','-f','rawvideo','pipe:1']),np.uint8).reshape(-1,v['height'],v['width'],3)
    def encode(path,frames):
        h,w=frames.shape[1:3]
        ff(['-f','rawvideo','-pix_fmt','rgb24','-s',f'{w}x{h}','-r',FPS,'-i','pipe:0','-an',
            '-c:v','libx264rgb','-preset','ultrafast','-crf','0',path],frames.tobytes())
        assert np.array_equal(decode(path),frames)
    old=work/'baseline'
    archive_bytes=subprocess.check_output(['git','-c','core.autocrlf=false','archive','--format=zip',BASELINE,'product/src','docs/specs/agent-project.schema.json'],cwd=ROOT)
    with zipfile.ZipFile(io.BytesIO(archive_bytes)) as archive:
        for item in archive.infolist():
            if item.is_dir():continue
            path=(old/item.filename).resolve();assert path.is_relative_to(old.resolve());path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(archive.read(item))
    baseline_frozen={p.relative_to(old).as_posix():sha(p) for p in sorted(old.rglob('*')) if p.is_file()}
    calls=[];bootstrap='import sys;sys.path.insert(0,sys.argv.pop(1));from ai_ad_editor.runtime import configure_local_runtime;configure_local_runtime();from ai_ad_editor.cli import main;raise SystemExit(main())'
    def cli(*args,baseline=False,expected=0):
        argv=[sys.executable,'-I','-B','-X','utf8','-c',bootstrap,str(old/'product/src' if baseline else ROOT/'product/src'),*map(str,args)]
        began=time.monotonic();p=subprocess.run(argv,cwd=ROOT,capture_output=True,timeout=300);n=len(calls)
        (work/f'call-{n:03}.stdout.log').write_bytes(p.stdout);(work/f'call-{n:03}.stderr.log').write_bytes(p.stderr)
        value=json.loads(p.stdout.decode('utf-8-sig'))
        calls.append({'args':list(map(str,args)),'baseline':baseline,'exit_code':p.returncode,'seconds':time.monotonic()-began,'result':value})
        save(work/'partial-calls.json',calls);assert p.returncode==expected,(p.returncode,value)
        return value
    shutil.copyfile(font_license,output/'font-license.txt')
    provenance={'license_spdx':'CC0-1.0','description':'Procedural native RGB/RGBA pixel textures; no third-party footage or models.',
                'generator':'scripts/smoke_sequence_sampling.py','generator_sha256':sha(Path(__file__)),
                'font':{'sha256':sha(font),'license_sha256':sha(font_license),'binary_distributed':False},
                'ffmpeg':{'sha256':sha(Path(shutil.which('ffmpeg'))),'version':subprocess.check_output(['ffmpeg','-version']).decode('utf-8','replace').splitlines()[0]},
                'baseline_ref':BASELINE,'new_model_inference':0}
    save(output/'fixture-provenance.json',provenance)
    cases=[];frames_by_case={}
    for index in range(1,10):
        code=f'S{index:02}';image=source(index);source_path=output/(code+'-source.png');Image.fromarray(image).save(source_path)
        # The published original video composites transparent sources on black;
        # the PNG retains the actual alpha and hidden RGB used by the product.
        original=np.rint(image[...,:3]*(image[...,3:4]/255)).astype(np.uint8)
        encode(output/(code+'-source.mp4'),np.repeat(original[None],N,axis=0))
        project=work/code;cli('project','init',project)
        cli('media','ingest','--project',project,'--input',source_path,'--asset-id','pattern',
            '--verification-status','verified','--permitted-use','commercial_ad','--license-spdx','CC0-1.0',
            '--source-url','local://generated-sequence-sampling','--evidence','local://scripts/smoke_sequence_sampling.py')
        p=json.loads((project/'project.json').read_text(encoding='utf-8-sig'));p['settings']['canvas'].update(width=W,height=H)
        p['settings']['timebase']['display_fps']={'num':FPS,'den':1}
        p['settings']['output']={'container':'mp4','video':{'codec':'libx264','preset':'ultrafast','crf':0,'pixel_format':'yuv444p'},'audio':{'codec':'aac','bitrate':'192k'}}
        save(project/'project.json',p);ops=operations(index,image.shape);save(project/'changes.json',{'operations':ops})
        cli('timeline','compose','--project',project,'--input',project/'changes.json')
        p=json.loads((project/'project.json').read_text(encoding='utf-8-sig'));p['sequences'][0]['duration_tick']=D;save(project/'project.json',p)
        author={k:copy.deepcopy(p[k]) for k in ('settings','sequences','assets')};ledger=(project/'rights-ledger.json').read_bytes()
        results={};decoded={}
        for name in ('before','bilinear','area'):
            path=project/'renders'/(name+'.mp4')
            overrides=('--sequence-sampling','area') if name=='area' else ()
            results[name]=cli('render','--project',project,'--output',path,'--publish',*overrides,baseline=name=='before')
            shutil.copyfile(path,output/(code+'-'+name+'.mp4'));shutil.copyfile(path.with_suffix('.mp4.manifest.json'),output/(code+'-'+name+'.mp4.manifest.json'))
            decoded[name]=decode(path);assert decoded[name].shape==(N,H,W,3)
        truth=np.stack([reference(image,parameters(index,i/N)) for i in range(N)])
        encode(output/(code+'-reference.mp4'),truth);decoded['reference']=truth
        metrics={}
        for name in ('before','bilinear','area'):
            diff=np.abs(decoded[name].astype(np.int16)-truth.astype(np.int16))
            metrics[name]={'max_rgb_error':int(diff.max()),'mean_rgb_error':float(diff.mean()),
                           'per_frame_mean_rgb_error':diff.mean(axis=(1,2,3)).tolist(),
                           'pixels_over_4':int(np.count_nonzero(diff.max(axis=3)>4)),
                           'decoded_rgb_sha256':'sha256:'+hashlib.sha256(decoded[name].tobytes()).hexdigest(),
                           'passed':bool(diff.max()<=4)}
        assert np.array_equal(decoded['before'],decoded['bilinear']),'Default compatibility changed'
        quality=cli('quality','check','--project',project,'--input',project/'renders/area.mp4','--sequence-sampling','area')
        policy=cli('policy','audit','--project',project)
        after=json.loads((project/'project.json').read_text(encoding='utf-8-sig'))
        assert author=={k:after[k] for k in author} and ledger==(project/'rights-ledger.json').read_bytes()
        record={'id':code,'title':description(index),'operations':ops,'frame_count':N,'fps':FPS,'duration_seconds':N/FPS,
                'metrics':metrics,'content_gate_passed':metrics['area']['passed'],'gate':'Every RGB channel <=4 absolute error against independent source-cell intersections.',
                'reference_scope':'Source-axis separable box; general rotation is not exact rotated-pixel polygon integration.',
                'baseline_equals_current_bilinear':True,'authoring_and_ledger_unchanged':True,
                'render_results':results,'quality_result':quality,'policy_result':policy,
                'outputs':{n:{'sha256':sha(output/(code+'-'+n+'.mp4')),'probe':probe(output/(code+'-'+n+'.mp4'))} for n in ('source','before','bilinear','area','reference')},
                'source_png_sha256':sha(source_path)}
        save(output/(code+'-verification.json'),record);cases.append(record);frames_by_case[code]=decoded
        print(json.dumps({'case':code,'metrics':metrics},ensure_ascii=False),flush=True)
    # Real preflight failure: no output, no temporary directory, no operation or project mutation.
    project=work/'S01';p=json.loads((project/'project.json').read_text(encoding='utf-8-sig'))
    p['settings']['sequence_sampling']={'method':'area','max_working_bytes':1};save(project/'project.json',p)
    raw=(project/'project.json').read_bytes();prior_ops=sorted(x.name for x in (project/'operations').glob('*.json'))
    rejections=[]
    for extra in ((),('--dry-run',)):
        value=cli('render','--project',project,'--output',project/'renders/rejected.mp4',*extra,expected=2)
        assert value['errors'][0]['code']=='SEQUENCE_PROJECTION_BUDGET_EXCEEDED'
        assert raw==(project/'project.json').read_bytes() and prior_ops==sorted(x.name for x in (project/'operations').glob('*.json'))
        assert not (project/'renders/rejected.mp4').exists() and not (project/'renders/.tmp').exists()
        rejections.append(value)
    save(output/'budget-rejections.json',{'cases':rejections,'no_output_temp_operation_or_author_mutation':True})
    label=ImageFont.truetype(str(font),14);previews=[];chosen=['S01','S04','S06','S07']
    for i in range(N):
        image=Image.new('RGB',(4*W,44+len(chosen)*(H+28)),(20,24,32));draw=ImageDraw.Draw(image)
        for col,title in enumerate(('V31 actual','Default bilinear','Explicit area','Cell-overlap reference')):draw.text((col*W+6,12),title,font=label,fill='white')
        for row,code in enumerate(chosen):
            y=44+row*(H+28)
            for col,name in enumerate(('before','bilinear','area','reference')):
                draw.text((col*W+6,y),code+' '+description(int(code[1:])),font=label,fill='white')
                image.paste(Image.fromarray(frames_by_case[code][name][i]),(col*W,y+28))
        previews.append(image)
    previews[0].save(output/'comparison-first.png');previews[-1].save(output/'comparison-last.png')
    previews[0].save(output/'comparison.gif',save_all=True,append_images=previews[2::2],duration=250,loop=0,optimize=False,disposal=2)
    pw,ph=previews[0].size;ff(['-f','rawvideo','-pix_fmt','rgb24','-s',f'{pw}x{ph}','-r',FPS,'-i','pipe:0','-an',
                             '-c:v','libx264','-crf','16','-pix_fmt','yuv444p',output/'comparison.mp4'],b''.join(im.tobytes() for im in previews))
    gif_durations=[]
    with Image.open(output/'comparison.gif') as im:
        for i in range(im.n_frames):im.seek(i);gif_durations.append(im.info.get('duration',0))
    after=frozen();assert before==after
    assert baseline_frozen=={p.relative_to(old).as_posix():sha(p) for p in sorted(old.rglob('*')) if p.is_file()}
    record={'started_at_utc':started,'finished_at_utc':datetime.now(timezone.utc).isoformat(),
            'frozen_before':before,'frozen_after':after,'frozen_file_count':len(before),'baseline_ref':BASELINE,
            'baseline_source_hashes':baseline_frozen,'cases':cases,'case_count':len(cases),'content_passed_cases':sum(c['content_gate_passed'] for c in cases),
            'cli_calls':calls,'cli_count':len(calls),'budget_rejections':rejections,
            'new_area_frames':N*len(cases),'current_bilinear_control_frames':N*len(cases),'old_frames':N*len(cases),'reference_frames':N*len(cases),
            'continuous_playback_review':False,'listening_review':False,'new_model_inference':0,
            'preview':{'mp4_probe':probe(output/'comparison.mp4'),'gif_encoded_frames':len(gif_durations),'gif_duration_ms':sum(gif_durations)},
            'provenance':provenance,'public_files':{p.name:{'sha256':sha(p),'bytes':p.stat().st_size} for p in sorted(output.iterdir()) if p.is_file()}}
    save(output/'verification.json',record)
    print(json.dumps({k:record[k] for k in ('case_count','cli_count','content_passed_cases','new_area_frames','frozen_file_count')},ensure_ascii=False),flush=True)
    raise SystemExit(0 if record['content_passed_cases']==len(cases) else 1)

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('output','work','font','font-license'):parser.add_argument('--'+name,type=Path,required=True)
    a=parser.parse_args();run(a.output.resolve(),a.work.resolve(),a.font.resolve(),a.font_license.resolve())
