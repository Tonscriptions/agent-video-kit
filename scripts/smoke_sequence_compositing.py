"""Actual CLI sequence composites vs fixed V27 and an independent RGBA oracle.

Requires a native Python with NumPy/Pillow, local FFmpeg and an explicit font.
All fixtures are generated CC0 patterns. No model, server or download is used.
"""
from __future__ import annotations
import argparse,copy,hashlib,io,json,os,shutil,subprocess,sys,time,zipfile
from datetime import datetime,timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
BASELINE='6ba010e25e0301219d74d8070284a9046916dc1d'
TPS=90000;FPS=12;W,H=320,192;D=2*TPS;N=24

def sha(p):return 'sha256:'+hashlib.sha256(p.read_bytes()).hexdigest()
def save(p,v):p.write_text(json.dumps(v,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8',newline='\n')
def frozen():return {p.relative_to(ROOT).as_posix():sha(p) for p in sorted([*(ROOT/'product/src').rglob('*.py'),*(ROOT/'product/tests').rglob('*.py'),ROOT/'docs/specs/agent-project.schema.json'])}

def operations(case):
    """Authored project operations, independent of renderer internals."""
    ops=[]
    def seq(name):ops.append({'op':'add_sequence','id':name,'duration_tick':D})
    def track(seq,name,order):ops.append({'op':'add_track','sequence_id':seq,'track_id':name,'kind':'video','order':order})
    def leaf(seq,track,name,color,**kw):ops.append({'op':'append_clip','sequence_id':seq,'track_id':track,'id':name,
        'asset_id':color,'source_in_tick':0,'source_out_tick':D,'timeline_start_tick':0,'duration_tick':D,**kw})
    def group(child,**kw):
        target=kw.pop('target','seq_main');track=kw.pop('track','track_video_1' if target=='seq_main' else target+'_video_1')
        ops.append({'op':'append_sequence_clip','sequence_id':target,'track_id':track,'id':'parent',
                    'nested_sequence_id':child,'source_in_tick':0,'source_out_tick':D,'duration_tick':D,'timeline_start_tick':0,**kw})
    def mask(x,w):return {'type':'rectangle','x':x,'y':0.,'width':w,'height':1.}
    def two():
        seq('child');track('child','child_top',100 if case=='G02' else 1)
        leaf('child','child_video_1','red_leaf','red',mask=mask(0.,.65))
        leaf('child','child_top','blue_leaf','blue',mask=mask(.35,.65))
    duration=D
    if case in {'G01','G02','G03','G09','G11','G12','G13'}:
        two()
        if case=='G01':group('child',transform={'opacity':.5})
        elif case=='G02':
            group('child');track('seq_main','root_above',1);leaf('seq_main','root_above','occluder','green')
        elif case=='G03':
            seq('middle');group('child',target='middle',id='inner',transform={'opacity':.5});group('middle',transform={'opacity':.5})
        elif case=='G09':group('child',crop={'unit':'normalized','x':.25,'y':0.,'width':.5,'height':1.,'fit':'stretch'})
        elif case=='G11':group('child',transform={'scale':.65,'anchor':{'x':.35,'y':.5}},keyframes=[{'property':'transform.rotation','keyframes':[
            {'at_tick':0,'value':-15.,'interpolation':'linear'},{'at_tick':D,'value':45.,'interpolation':'linear'}]}])
        elif case=='G12':
            track('seq_main','background',-1);leaf('seq_main','background','base','gray')
            group('child',transform={'opacity':.5},blend={'mode':'multiply'})
        elif case=='G13':group('child',transition_in={'type':'fade','duration':.5})
    elif case=='G04':
        seq('child');leaf('child','child_video_1','marker','red',mask={'type':'rectangle','x':.2,'y':.4,'width':.1,'height':.2})
        group('child',transform={'position':{'x':.5,'y':.5},'anchor':{'x':.25,'y':.5},'rotation':180.})
    elif case=='G05':
        seq('child');leaf('child','child_video_1','leaf','red')
        group('child',transform={'position':{'x':.75,'y':.5},'scale':.5},mask=mask(.5,.2))
    elif case in {'G06','G07'}:
        seq('child');track('child','upper',1)
        first={'mask':mask(0.,.65)} if case=='G06' else {'transform':{'opacity':.5}}
        second={'mask':mask(.35,.65)} if case=='G06' else {'transform':{'opacity':.5}}
        leaf('child','child_video_1','bottom','gray',**first)
        leaf('child','upper','top','cyan',blend={'mode':'multiply'},**second)
        group('child')
    elif case=='G08':
        seq('child');leaf('child','child_video_1','first','red',source_out_tick=D//2,duration_tick=D//2)
        leaf('child','child_video_1','second','blue',source_out_tick=D//2,timeline_start_tick=D//2,duration_tick=D//2)
        group('child',keyframes=[{'property':'transform.opacity','keyframes':[{'at_tick':0,'value':.25,'interpolation':'linear'},
                                                                          {'at_tick':D,'value':.75,'interpolation':'linear'}]}])
    elif case=='G10':
        seq('child');track('seq_main','background',-1);leaf('seq_main','background','base','green',source_out_tick=2*D,duration_tick=2*D)
        leaf('child','child_video_1','first','red',source_out_tick=D//4,duration_tick=D//4)
        leaf('child','child_video_1','second','blue',source_out_tick=D//4,timeline_start_tick=3*D//4,duration_tick=D//4)
        group('child',timeline_start_tick=D//2);duration=2*D
    elif case=='G14':
        seq('child');leaf('child','child_video_1','leaf','red',transform={'scale':.25},keyframes=[
            {'property':'transform.scale','keyframes':[{'at_tick':0,'value':.25,'interpolation':'linear'},
                                                     {'at_tick':D,'value':.75,'interpolation':'linear'}]}])
        group('child')
    else:raise ValueError(case)
    return ops,duration

def oracle(case,sources):
    """W3C straight-alpha compositing and matrix inverse sampling in NumPy.

    This imports no product package, FFmpeg graph or project compiler. Expected
    source RGB comes from decoding the actual lossless published inputs.
    """
    import numpy as np
    yy,xx=np.mgrid[:H,:W]
    zero=np.zeros((H,W,4),np.float64)
    black=zero.copy();black[...,3]=1.
    def rgba(rgb):return np.concatenate((rgb.astype(np.float64)/255,np.ones((H,W,1))),axis=2)
    def cover(image,alpha):v=image.copy();v[...,3]*=alpha;return v
    def rect(image,x=0.,y=0.,width=1.,height=1.):
        return cover(image,((xx>=W*x)&(xx<=W*min(1,x+width))&(yy>=H*y)&(yy<=H*min(1,y+height))).astype(float))
    def over(bottom,top,mode='normal'):
        ab=bottom[...,3:4];a=top[...,3:4];cb=bottom[...,:3];cs=top[...,:3]
        blend=cb*cs if mode=='multiply' else cs
        color=(1-ab)*cs+ab*blend
        alpha=a+ab*(1-a)
        premul=color*a+cb*ab*(1-a)
        rgb=np.divide(premul,alpha,out=np.zeros_like(premul),where=alpha>0)
        return np.concatenate((rgb,alpha),axis=2)
    def sample(image,x,y):
        valid=(x>=-.5)&(x<W-.5)&(y>=-.5)&(y<H-.5)
        x=np.clip(x,0,W-1);y=np.clip(y,0,H-1)
        ix=np.floor(x).astype(int);iy=np.floor(y).astype(int)
        jx=np.minimum(ix+1,W-1);jy=np.minimum(iy+1,H-1)
        dx=(x-ix)[...,None];dy=(y-iy)[...,None]
        p=image.copy();p[...,:3]*=p[...,3:4]
        q=((p[iy,ix]*(1-dx)+p[iy,jx]*dx)*(1-dy)+(p[jy,ix]*(1-dx)+p[jy,jx]*dx)*dy)
        q*=valid[...,None]
        q[...,:3]=np.divide(q[...,:3],q[...,3:4],out=np.zeros_like(q[...,:3]),where=q[...,3:4]>0)
        return q
    def affine(image,scale=1.,angle=0.,position=(.5,.5),anchor=(.5,.5)):
        radians=np.deg2rad(angle);c,s=np.cos(radians),np.sin(radians)
        translation=np.array([[1,0,W*position[0]],[0,1,H*position[1]],[0,0,1.]])
        rotation=np.array([[c,-s,0],[s,c,0],[0,0,1.]])
        scaling=np.diag([scale,scale,1.]);pivot=np.array([[1,0,-W*anchor[0]],[0,1,-H*anchor[1]],[0,0,1.]])
        inv=np.linalg.inv(translation@rotation@scaling@pivot)
        pts=inv@np.stack((xx+.5,yy+.5,np.ones_like(xx))).reshape(3,-1)
        return sample(image,pts[0].reshape(H,W)-.5,pts[1].reshape(H,W)-.5)
    frames=[]
    for i in range(2*N if case=='G10' else N):
        at=i/FPS
        r,b,g,gray,cyan=(rgba(sources[name][i]) for name in ('red','blue','green','gray','cyan'))
        child=over(rect(r,width=.65),rect(b,x=.35,width=.65))
        bg=zero
        if case=='G01':child=cover(child,.5)
        elif case=='G02':child=g
        elif case=='G03':child=cover(cover(child,.5),.5)
        elif case=='G04':child=affine(rect(r,x=.2,y=.4,width=.1,height=.2),angle=180,anchor=(.25,.5))
        elif case=='G05':child=rect(affine(r,scale=.5,position=(.75,.5)),x=.5,width=.2)
        elif case=='G06':child=over(rect(gray,width=.65),rect(cyan,x=.35,width=.65),'multiply')
        elif case=='G07':child=over(cover(gray,.5),cover(cyan,.5),'multiply')
        elif case=='G08':
            name='red' if i<N//2 else 'blue';source=i if i<N//2 else i-N//2
            child=cover(rgba(sources[name][source]),.25+.5*i/N)
        elif case=='G09':child=sample(child,.25*W+(xx+.5)*.5-.5,yy)
        elif case=='G10':
            bg=g;local=i-N//2
            if 0<=local<N//4:child=rgba(sources['red'][local])
            elif 3*N//4<=local<N:child=rgba(sources['blue'][local-3*N//4])
            else:child=zero
        elif case=='G11':child=affine(child,scale=.65,angle=-15+60*i/N,anchor=(.35,.5))
        elif case=='G12':
            frames.append(np.clip(np.rint(over(gray,cover(child,.5),'multiply')[...,:3]*255),0,255).astype(np.uint8));continue
        elif case=='G13':child=cover(child,min(1,at/.5))
        elif case=='G14':child=affine(r,scale=.25+.5*i/N)
        # Delivery is opaque RGB: flatten the straight-alpha group over the
        # actual black root canvas before dropping alpha. Dropping it directly
        # would incorrectly turn a half-covered color into a full color.
        result=over(black,over(bg,child))
        frames.append(np.clip(np.rint(result[...,:3]*255),0,255).astype(np.uint8))
    return np.stack(frames)


def run(output,work,font,font_license):
    import numpy as np
    from PIL import Image,ImageDraw,ImageFont
    if output.exists() or work.exists():raise ValueError('Use fresh output/work directories; preserve earlier evidence')
    output.mkdir(parents=True);work.mkdir(parents=True);freeze=frozen();began=datetime.now(timezone.utc).isoformat()
    def ff(args,data=None):
        p=subprocess.run(['ffmpeg','-v','error',*map(str,args)],input=data,capture_output=True,timeout=300)
        if p.returncode:raise RuntimeError(p.stderr.decode('utf-8','replace'))
        return p.stdout
    def video(path):return np.frombuffer(ff(['-i',path,'-map','0:v:0','-an','-pix_fmt','rgb24','-f','rawvideo','pipe:1']),np.uint8).reshape(-1,H,W,3)
    def probe(path):return json.loads(subprocess.run(['ffprobe','-v','error','-count_frames','-show_streams','-show_format','-of','json',str(path)],capture_output=True,check=True).stdout)
    raw=subprocess.run(['git','-c','core.autocrlf=false','archive','--format=zip',BASELINE,'product/src','docs/specs/agent-project.schema.json'],cwd=ROOT,capture_output=True,check=True).stdout
    baseline=work/'baseline'
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        for item in archive.infolist():
            if item.is_dir():continue
            p=(baseline/item.filename).resolve();assert p.is_relative_to(baseline.resolve());p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(archive.read(item))
    sources={}
    for name,color in {'red':(240,0,0),'blue':(0,0,240),'green':(0,240,0),'gray':(160,160,160),'cyan':(0,160,160)}.items():
        frames=np.tile(np.array(color,np.uint8),(2*N,H,W,1))
        for i,frame in enumerate(frames):
            x=8+(i*7)%(W-40);frame[H-20:H-8,x:x+24]=(240,240,240)
        path=output/f'source-{name}.mp4'
        ff(['-f','rawvideo','-pix_fmt','rgb24','-s',f'{W}x{H}','-r',FPS,'-i','pipe:0','-an','-c:v','libx264rgb','-preset','ultrafast','-crf','0',path],frames.tobytes())
        sources[name]=video(path);assert np.array_equal(sources[name],frames)
    shutil.copyfile(font_license,output/'font-license.txt')
    provenance={'license_spdx':'CC0-1.0','fixture_description':'Five procedural RGB color plates with a moving white bar, 4 s/48 frames, lossless libx264rgb; no external footage or model inference',
                'generator':'scripts/smoke_sequence_compositing.py','generator_sha256':sha(Path(__file__)),
                'font':{'sha256':sha(font),'license_sha256':sha(font_license),'binary_distributed':False},
                'sources':{f'source-{n}.mp4':{'sha256':sha(output/f'source-{n}.mp4'),'probe':probe(output/f'source-{n}.mp4')} for n in sources},
                'baseline_ref':BASELINE,'new_model_inference':0,'third_party_binaries_distributed':False}
    save(output/'fixture-provenance.json',provenance)
    calls=[];bootstrap='import sys;sys.path.insert(0,sys.argv.pop(1));from ai_ad_editor.runtime import configure_local_runtime;configure_local_runtime();from ai_ad_editor.cli import main;raise SystemExit(main())'
    def cli(*args,old=False,allow_failure=False):
        command=[sys.executable,'-I','-B','-X','utf8','-c',bootstrap,str(baseline/'product/src' if old else ROOT/'product/src'),*map(str,args)]
        start=time.monotonic();p=subprocess.run(command,cwd=ROOT,capture_output=True,timeout=300);number=len(calls)
        (work/f'call-{number:03}.stdout.log').write_bytes(p.stdout);(work/f'call-{number:03}.stderr.log').write_bytes(p.stderr)
        value=json.loads(p.stdout.decode('utf-8-sig'));calls.append({'args':list(map(str,args)),'old':old,'exit_code':p.returncode,'seconds':time.monotonic()-start,'result':value});save(work/'partial-calls.json',calls)
        if p.returncode and not allow_failure:raise RuntimeError(value)
        return value
    cases=[];decoded={};reference={}
    labels=['overlap opacity','parent track slot','two opacity levels','canvas pivot','post-transform mask','isolated multiply',
            'fractional multiply','animated opacity','composite crop','visible window and gaps','animated rotation','parent multiply','group fade','child animated scale']
    for ordinal,title in enumerate(labels,1):
        code=f'G{ordinal:02}';project=work/code;cli('project','init',project)
        ops,duration=operations(code);names=sorted({v['asset_id'] for v in ops if v.get('asset_id')})
        for name in names:cli('media','ingest','--project',project,'--input',output/f'source-{name}.mp4','--asset-id',name,
            '--verification-status','verified','--permitted-use','commercial_ad','--source-url','local://generated-sequence-compositing',
            '--license-spdx','CC0-1.0','--evidence','local://scripts/smoke_sequence_compositing.py')
        p=json.loads((project/'project.json').read_text(encoding='utf-8-sig'))
        p['settings']['canvas'].update(width=W,height=H);p['settings']['timebase']['display_fps']={'num':FPS,'den':1}
        p['settings']['output']={'container':'mp4','video':{'codec':'libx264','preset':'ultrafast','crf':0,'pixel_format':'yuv444p'},'audio':{'codec':'aac','bitrate':'192k'}}
        save(project/'project.json',p);changes=project/'changes.json';save(changes,{'operations':ops});cli('timeline','compose','--project',project,'--input',changes)
        p=json.loads((project/'project.json').read_text(encoding='utf-8-sig'));p['sequences'][0]['duration_tick']=duration;save(project/'project.json',p)
        before=json.dumps({k:p[k] for k in ('settings','assets','sequences')},sort_keys=True);rights=(project/'rights-ledger.json').read_bytes()
        results={}
        for old in (True,False):
            name='before' if old else 'after';path=project/f'renders/{name}.mp4'
            results[name]=cli('render','--project',project,'--output',path,'--publish',old=old)
            shutil.copyfile(path,output/f'{code}-{name}.mp4')
            shutil.copyfile(path.with_suffix('.mp4.manifest.json'),output/f'{code}-{name}.mp4.manifest.json')
        quality=cli('quality','check','--project',project,'--input',project/'renders/after.mp4','--expensive',allow_failure=True)
        policy=cli('policy','audit','--project',project)
        after=json.loads((project/'project.json').read_text(encoding='utf-8-sig'))
        assert before==json.dumps({k:after[k] for k in ('settings','assets','sequences')},sort_keys=True) and rights==(project/'rights-ledger.json').read_bytes()
        expected=oracle(code,sources);reference[code]=expected
        ff(['-f','rawvideo','-pix_fmt','rgb24','-s',f'{W}x{H}','-r',FPS,'-i','pipe:0','-an','-c:v','libx264rgb','-preset','ultrafast','-crf','0',output/f'{code}-reference.mp4'],expected.tobytes())
        comparisons={}
        for name in ('before','after'):
            actual=video(output/f'{code}-{name}.mp4');assert actual.shape==expected.shape
            difference=np.abs(actual.astype(np.int16)-expected.astype(np.int16));maximum=difference.max(axis=(1,2,3))
            comparisons[name]={'max_rgb_error':int(difference.max()),'mean_rgb_error':float(difference.mean()),
                'frames_over_5':int(np.count_nonzero(maximum>5)),'pixels_over_5':int(np.count_nonzero(difference.max(axis=3)>5)),
                'per_frame_max_rgb_error':maximum.tolist(),'decoded_rgb_sha256':'sha256:'+hashlib.sha256(actual.tobytes()).hexdigest()}
            decoded[(code,name)]=actual
        record={'id':code,'title':title,'frame_count':len(expected),'fps':FPS,'duration_seconds':len(expected)/FPS,
            'comparison_scope':'All decoded RGB pixels, all output frames, against independent NumPy W3C alpha/matrix sampling; encoded RGB tolerance 5',
            'content_gate_passed':comparisons['after']['frames_over_5']==0,'comparisons':comparisons,'quality_result':quality,'policy_result':policy,
            'render_results':results,'authored_project_and_ledger_unchanged':True,'operations':ops,
            'reference_decoded_rgb_sha256':'sha256:'+hashlib.sha256(expected.tobytes()).hexdigest(),
            'outputs':{name:{'sha256':sha(output/f'{code}-{name}.mp4'),'probe':probe(output/f'{code}-{name}.mp4')} for name in ('before','after','reference')}}
        save(output/f'{code}-verification.json',record);cases.append(record)
        print(json.dumps({'case':code,'old_max':comparisons['before']['max_rgb_error'],'new_max':comparisons['after']['max_rgb_error'],'accepted':record['content_gate_passed']},ensure_ascii=False),flush=True)
    chosen=['G01','G04','G05','G11'];font_label=ImageFont.truetype(str(font),18)
    previews=[]
    for i in range(N):
        image=Image.new('RGB',(3*W,52+len(chosen)*(H+25)),(20,24,32));draw=ImageDraw.Draw(image)
        for col,title in enumerate(('V27 before','Current actual','Independent reference')):draw.text((col*W+12,12),title,font=font_label,fill='white')
        for row,code in enumerate(chosen):
            y=52+row*(H+25)
            for col,frames in enumerate((decoded[(code,'before')],decoded[(code,'after')],reference[code])):
                image.paste(Image.fromarray(frames[i]),(col*W,y+25));draw.text((col*W+10,y),code+' '+labels[int(code[1:])-1],font=font_label,fill='white')
        previews.append(image)
    previews[0].save(output/'comparison-first.png');previews[-1].save(output/'comparison-last.png')
    # GIF is sampled at 6 fps; durations sum exactly to 2,000 ms.
    gif=previews[::2];durations=[170,160,170]*4
    gif[0].save(output/'comparison.gif',save_all=True,append_images=gif[1:],duration=durations,loop=0,optimize=False,disposal=2)
    pw,ph=previews[0].size
    ff(['-f','rawvideo','-pix_fmt','rgb24','-s',f'{pw}x{ph}','-r',FPS,'-i','pipe:0','-an','-c:v','libx264','-crf','16','-pix_fmt','yuv444p',output/'comparison.mp4'],b''.join(v.tobytes() for v in previews))
    final=frozen();assert freeze==final
    gif_probe=[]
    with Image.open(output/'comparison.gif') as im:
        for i in range(im.n_frames):im.seek(i);gif_probe.append(im.info.get('duration',0))
    record={'started_at_utc':began,'finished_at_utc':datetime.now(timezone.utc).isoformat(),'baseline_ref':BASELINE,
        'frozen_before':freeze,'frozen_after':final,'frozen_file_count':len(freeze),'case_count':len(cases),'cli_count':len(calls),
        'cli_calls':calls,'cases':cases,'content_passed_cases':sum(v['content_gate_passed'] for v in cases),
        'new_decoded_frames':sum(v['frame_count'] for v in cases),'old_decoded_frames':sum(v['frame_count'] for v in cases),
        'independent_reference_frames':sum(v['frame_count'] for v in cases),'continuous_playback_accepted':False,'listening_accepted':False,
        'preview':{'mp4_probe':probe(output/'comparison.mp4'),'gif_encoded_frames':len(gif_probe),'gif_duration_ms':sum(gif_probe),'gif_frame_durations_ms':gif_probe},
        'provenance':provenance,'public_files':{p.name:{'sha256':sha(p),'bytes':p.stat().st_size} for p in sorted(output.iterdir()) if p.is_file()}}
    save(output/'verification.json',record)
    print(json.dumps({k:record[k] for k in ('case_count','cli_count','content_passed_cases','new_decoded_frames','frozen_file_count')},ensure_ascii=False),flush=True)

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True);parser.add_argument('--work',type=Path,required=True)
    parser.add_argument('--font',type=Path,required=True);parser.add_argument('--font-license',type=Path,required=True);args=parser.parse_args()
    run(args.output.resolve(),args.work.resolve(),args.font.resolve(),args.font_license.resolve())
