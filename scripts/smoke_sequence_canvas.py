"""Native CLI independent sequence canvases, fixed V30 and a NumPy oracle.

Uses generated CC0 footage, local NumPy/Pillow/FFmpeg and an explicit font.
The spatial reference imports no product code; it samples native child pixels
using independent matrix algebra. C09 separately checks exact compatibility
with decoded V30 output, whose legacy leaf scaler uses a different kernel.
"""
from __future__ import annotations
import argparse,copy,hashlib,io,json,os,shutil,subprocess,sys,time,zipfile
from datetime import datetime,timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
BASELINE='abb84930b2d0f7c3ecd077a602be2dcfc14012cf'
TPS,FPS,W,H,N=90000,12,320,192,24
D=2*TPS

def sha(p):return 'sha256:'+hashlib.sha256(p.read_bytes()).hexdigest()
def save(p,value):p.write_text(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8',newline='\n')
def frozen():return {p.relative_to(ROOT).as_posix():sha(p) for p in sorted([*(ROOT/'product/src').rglob('*.py'),*(ROOT/'product/tests').rglob('*.py'),ROOT/'docs/specs/agent-project.schema.json'])}

def operations(code):
    ops=[]
    def seq(name,canvas):ops.append({'op':'add_sequence','id':name,'duration_tick':D,'canvas':canvas})
    def group(child,target='seq_main',**kw):
        ops.append({'op':'append_sequence_clip','sequence_id':target,'track_id':'track_video_1' if target=='seq_main' else target+'_video_1',
                    'id':'parent' if target=='seq_main' else 'inner','nested_sequence_id':child,
                    'timeline_start_tick':0,'source_in_tick':0,'source_out_tick':D,'duration_tick':D,**kw})
    def keys(prop,a,b):return {'property':prop,'keyframes':[{'at_tick':0,'value':a,'interpolation':'linear'},{'at_tick':D,'value':b,'interpolation':'linear'}]}
    seq('child',{'width':64,'height':128} if code!='C09' else None)
    leaf={'op':'append_clip','sequence_id':'child','track_id':'child_video_1','id':'leaf','asset_id':'pattern',
          'source_in_tick':0,'source_out_tick':D,'duration_tick':D,'timeline_start_tick':0,'crop':{'fit':'stretch'}}
    if code=='C07':leaf['mask']={'type':'rectangle','x':0.,'y':0.,'width':.5,'height':1.}
    ops.append(leaf)
    if code=='C01':group('child')
    elif code=='C02':group('child',crop={'fit':'fill'},transform={'rotation':90.,'scale':.5})
    elif code=='C03':group('child',keyframes=[keys('transform.anchor.x',0.,1.)])
    elif code=='C04':group('child',crop={'x':32,'y':0,'width':32,'height':128,'fit':'stretch'})
    elif code=='C05':group('child',crop={'unit':'normalized','x':0.,'y':0.,'width':.5,'height':1.,'fit':'stretch'},keyframes=[keys('crop.x',0.,.5)])
    elif code=='C06':group('child',transform={'anchor':{'x':0.,'y':.5},'rotation':90.},mask={'type':'rectangle','x':.5,'y':0.,'width':.5,'height':1.})
    elif code=='C07':
        seq('middle',{'width':192,'height':128});group('child','middle');group('middle',transform={'rotation':180.})
    elif code=='C08':
        ops.extend([{'op':'add_track','sequence_id':'child','track_id':'titles','kind':'subtitle','order':2},
          {'op':'append_clip','sequence_id':'child','track_id':'titles','id':'label','generator':{'type':'text'},'timeline_start_tick':0,
           'source_in_tick':0,'source_out_tick':D,'duration_tick':D,'subtitle':{'text':'H\nH','style':{'font_asset_id':'font',
           'fontsize':18,'fontcolor':'white','box':False,'x':'(w-text_w)/2','y':'(h-text_h)/2','borderw':0,'shadowx':0,'shadowy':0}}}])
        group('child')
    elif code=='C09':group('child')
    else:raise ValueError(code)
    return ops

def spatial_reference(code,sources):
    """Independent native-raster sampling, crop/fit/pivot matrices and alpha.

    C08 takes a separately rendered native child to isolate projection from
    text shaping; that case is explicitly not an independent glyph reference.
    C09 is an inherited-canvas compatibility control. All other inputs are the
    decoded published source, with no product-rendered reference component.
    """
    import numpy as np
    def rgba(rgb):return np.concatenate((rgb.astype(np.float64)/255,np.ones((*rgb.shape[:2],1))),axis=2)
    def sample(image,x,y,visible):
        h,w=image.shape[:2];x=np.clip(x,0,w-1);y=np.clip(y,0,h-1)
        ix=np.floor(x).astype(int);iy=np.floor(y).astype(int);jx=np.minimum(w-1,ix+1);jy=np.minimum(h-1,iy+1)
        dx=(x-ix)[...,None];dy=(y-iy)[...,None];p=image.copy();p[...,:3]*=p[...,3:4]
        q=((p[iy,ix]*(1-dx)+p[iy,jx]*dx)*(1-dy)+(p[jy,ix]*(1-dx)+p[jy,jx]*dx)*dy)*visible[...,None]
        q[...,:3]=np.divide(q[...,:3],q[...,3:4],out=np.zeros_like(q[...,:3]),where=q[...,3:4]>0)
        return q
    def project(image,w,h,*,crop=None,fit='fit',anchor=(.5,.5),position=(.5,.5),angle=0.,scale=1.):
        sh,sw=image.shape[:2];cx,cy,cw,ch=crop or (0.,0.,float(sw),float(sh))
        if fit=='stretch':fx,fy=w/cw,h/ch
        else:fx=fy=(max if fit=='fill' else min)(w/cw,h/ch)
        theta=np.deg2rad(angle);c,s=np.cos(theta),np.sin(theta)
        t=np.array([[1.,0,w*position[0]],[0,1.,h*position[1]],[0,0,1.]])
        r=np.array([[c,-s,0],[s,c,0],[0,0,1.]])
        z=np.diag([scale*fx,scale*fy,1.]);a=np.array([[1.,0,-cx-anchor[0]*cw],[0,1.,-cy-anchor[1]*ch],[0,0,1.]])
        yy,xx=np.mgrid[:h,:w];points=np.linalg.inv(t@r@z@a)@np.stack((xx+.5,yy+.5,np.ones_like(xx))).reshape(3,-1)
        sx=points[0].reshape(h,w)-.5;sy=points[1].reshape(h,w)-.5
        visible=(sx>=cx-.5)&(sx<cx+cw-.5)&(sy>=cy-.5)&(sy<cy+ch-.5)
        return sample(image,np.clip(sx,cx,cx+cw-1),np.clip(sy,cy,cy+ch-1),visible)
    result=[]
    for i in range(N):
        child=rgba(sources[i]);kw={}
        if code=='C02':kw={'fit':'fill','angle':90.,'scale':.5}
        elif code=='C03':kw={'anchor':(i/N,.5)}
        elif code=='C04':kw={'crop':(32.,0.,32.,128.),'fit':'stretch'}
        elif code=='C05':kw={'crop':(32*i/N,0.,32.,128.),'fit':'stretch'}
        elif code=='C06':kw={'anchor':(0.,.5),'angle':90.}
        elif code=='C07':
            child[:,33:,3]=0.;child=project(child,192,128);kw={'angle':180.}
        elif code=='C09':child=project(child,W,H,fit='stretch')
        layer=project(child,W,H,**kw)
        if code=='C06':layer[:,:W//2,3]=0.
        result.append(np.clip(np.rint(layer[...,:3]*layer[...,3:4]*255),0,255).astype(np.uint8))
    return np.stack(result)

def run(output,work,font,font_license):
    import numpy as np
    from PIL import Image,ImageDraw,ImageFont
    if output.exists() or work.exists():raise ValueError('Use fresh output/work paths; preserve earlier evidence')
    output.mkdir(parents=True);work.mkdir(parents=True);before=frozen();began=datetime.now(timezone.utc).isoformat()
    for key in ('TEMP','TMP','TMPDIR'):os.environ[key]=str(work)
    def ff(args,data=None):
        p=subprocess.run(['ffmpeg','-v','error',*map(str,args)],input=data,capture_output=True,timeout=300)
        if p.returncode:raise RuntimeError(p.stderr.decode('utf-8','replace'))
        return p.stdout
    def probe(p):return json.loads(subprocess.run(['ffprobe','-v','error','-count_frames','-show_streams','-show_format','-of','json',str(p)],capture_output=True,check=True).stdout)
    def video(p):
        v=next(s for s in probe(p)['streams'] if s['codec_type']=='video')
        return np.frombuffer(ff(['-i',p,'-map','0:v:0','-an','-pix_fmt','rgb24','-f','rawvideo','pipe:1']),np.uint8).reshape(-1,v['height'],v['width'],3)
    def encode(p,frames):
        h,w=frames.shape[1:3];ff(['-f','rawvideo','-pix_fmt','rgb24','-s',f'{w}x{h}','-r',FPS,'-i','pipe:0','-an','-c:v','libx264rgb','-preset','ultrafast','-crf','0',p],frames.tobytes())
    old=work/'baseline';archive_bytes=subprocess.run(['git','-c','core.autocrlf=false','archive','--format=zip',BASELINE,'product/src','docs/specs/agent-project.schema.json'],cwd=ROOT,capture_output=True,check=True).stdout
    with zipfile.ZipFile(io.BytesIO(archive_bytes)) as archive:
        for item in archive.infolist():
            if item.is_dir():continue
            p=(old/item.filename).resolve();assert p.is_relative_to(old.resolve());p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(archive.read(item))
    pattern=np.zeros((N,128,64,3),np.uint8);pattern[:,:,:32]=(230,20,20);pattern[:,:,32:]=(20,20,230)
    pattern[:,4:16,:]=(20,220,20)
    for i,frame in enumerate(pattern):
        x=4+(i*2)%44;frame[104:116,x:x+12]=(240,240,240)
    encode(output/'source-portrait.mp4',pattern);assert np.array_equal(video(output/'source-portrait.mp4'),pattern)
    shutil.copyfile(font_license,output/'font-license.txt')
    provenance={'license_spdx':'CC0-1.0','description':'Procedural 64x128 RGB portrait plate, green top marker, moving white bar, lossless RGB video; 2 s / 24 frames / 12 fps.',
      'generator':'scripts/smoke_sequence_canvas.py','generator_sha256':sha(Path(__file__)),'new_model_inference':0,
      'source':{'sha256':sha(output/'source-portrait.mp4'),'probe':probe(output/'source-portrait.mp4')},
      'font':{'sha256':sha(font),'license_sha256':sha(font_license),'binary_distributed':False},'baseline_ref':BASELINE}
    save(output/'fixture-provenance.json',provenance)
    calls=[];bootstrap='import sys;sys.path.insert(0,sys.argv.pop(1));from ai_ad_editor.runtime import configure_local_runtime;configure_local_runtime();from ai_ad_editor.cli import main;raise SystemExit(main())'
    def cli(*args,baseline=False,expected=0):
        argv=[sys.executable,'-I','-B','-X','utf8','-c',bootstrap,str(old/'product/src' if baseline else ROOT/'product/src'),*map(str,args)]
        started=time.monotonic();p=subprocess.run(argv,cwd=ROOT,capture_output=True,timeout=300);n=len(calls)
        (work/f'call-{n:03}.stdout.log').write_bytes(p.stdout);(work/f'call-{n:03}.stderr.log').write_bytes(p.stderr)
        value=json.loads(p.stdout.decode('utf-8-sig'));calls.append({'args':list(map(str,args)),'baseline':baseline,'exit_code':p.returncode,'seconds':time.monotonic()-started,'result':value});save(work/'partial-calls.json',calls)
        assert p.returncode==expected,(p.returncode,value)
        return value
    cases=[];decoded={};references={}
    titles=['portrait fit','fill then rotate reveals source','animated child anchor','native pixel crop','animated normalized crop',
            'parent rotation then mask','three independent rasters','local multiline text projection','inherited canvas control']
    for index,title in enumerate(titles,1):
        code=f'C{index:02}';project=work/code;cli('project','init',project)
        for asset,path,license_id in [('pattern',output/'source-portrait.mp4','CC0-1.0')]+([('font',font,'LicenseRef-DejaVu')] if code=='C08' else []):
            cli('media','ingest','--project',project,'--input',path,'--asset-id',asset,'--verification-status','verified','--permitted-use','commercial_ad',
                '--source-url','local://generated-sequence-canvas','--license-spdx',license_id,'--evidence','local://scripts/smoke_sequence_canvas.py')
        p=json.loads((project/'project.json').read_text(encoding='utf-8-sig'));p['settings']['canvas'].update(width=W,height=H)
        p['settings']['timebase']['display_fps']={'num':FPS,'den':1}
        p['settings']['output']={'container':'mp4','video':{'codec':'libx264','preset':'ultrafast','crf':0,'pixel_format':'yuv444p'},'audio':{'codec':'aac','bitrate':'192k'}}
        save(project/'project.json',p);ops=operations(code);save(project/'changes.json',{'operations':ops});cli('timeline','compose','--project',project,'--input',project/'changes.json')
        p=json.loads((project/'project.json').read_text(encoding='utf-8-sig'));p['sequences'][0]['duration_tick']=D;save(project/'project.json',p)
        author=json.dumps({k:p[k] for k in ('settings','sequences','assets')},sort_keys=True);rights=(project/'rights-ledger.json').read_bytes()
        results={}
        for baseline in (True,False):
            name='before' if baseline else 'after';path=project/f'renders/{name}.mp4'
            results[name]=cli('render','--project',project,'--output',path,'--publish',baseline=baseline)
            shutil.copyfile(path,output/f'{code}-{name}.mp4');shutil.copyfile(path.with_suffix('.mp4.manifest.json'),output/f'{code}-{name}.mp4.manifest.json')
            decoded[(code,name)]=video(path)
        local_result=None
        if code=='C08':
            local_path=project/'renders/local-child.mp4';local_result=cli('render','--project',project,'--sequence-id','child','--output',local_path,'--publish')
            shutil.copyfile(local_path,output/'C08-local-child.mp4');source=video(local_path);assert source.shape==(N,128,64,3)
        else:source=pattern
        expected=decoded[(code,'before')].copy() if code=='C09' else spatial_reference(code,source)
        references[code]=expected;encode(output/f'{code}-reference.mp4',expected)
        metrics={}
        for name in ('before','after'):
            actual=decoded[(code,name)];assert actual.shape==expected.shape
            diff=np.abs(actual.astype(np.int16)-expected.astype(np.int16));pixel=diff.max(axis=3)
            metrics[name]={'max_rgb_error':int(diff.max()),'mean_rgb_error':float(diff.mean()),'pixels_over_12':int(np.count_nonzero(pixel>12)),
              'fraction_pixels_over_12':float(np.mean(pixel>12)),'per_frame_mean_rgb_error':diff.mean(axis=(1,2,3)).tolist(),
              'decoded_rgb_sha256':'sha256:'+hashlib.sha256(actual.tobytes()).hexdigest()}
            metrics[name]['passed']=metrics[name]['max_rgb_error'] <= (0 if code=='C09' else 5)
        quality=cli('quality','check','--project',project,'--input',project/'renders/after.mp4')
        policy=cli('policy','audit','--project',project)
        current=json.loads((project/'project.json').read_text(encoding='utf-8-sig'))
        assert author==json.dumps({k:current[k] for k in ('settings','sequences','assets')},sort_keys=True) and rights==(project/'rights-ledger.json').read_bytes()
        record={'id':code,'title':title,'frame_count':N,'fps':FPS,'duration_seconds':N/FPS,'metrics':metrics,'content_gate_passed':metrics['after']['passed'],
          'reference_scope':('Decoded fixed V30 output as exact inherited-canvas compatibility control.' if code=='C09' else
                             'Independent native-child matrix/bilinear sampling; C08 uses actual standalone child raster to isolate projection, not independent glyph shaping.'),
          'gate':('All decoded RGB bytes equal fixed V30.' if code=='C09' else 'All decoded RGB pixels have maximum absolute channel error <= 5. Controlled raster acceptance, not a general quality benchmark.'),
          'operations':ops,'render_results':results,'local_child_render':local_result,'quality_result':quality,'policy_result':policy,
          'authored_project_and_ledger_unchanged':True,'reference_decoded_rgb_sha256':'sha256:'+hashlib.sha256(expected.tobytes()).hexdigest(),
          'outputs':{n:{'sha256':sha(output/f'{code}-{n}.mp4'),'probe':probe(output/f'{code}-{n}.mp4')} for n in ('before','after','reference')}}
        save(output/f'{code}-verification.json',record);cases.append(record)
        print(json.dumps({'case':code,'old':metrics['before'],'new':metrics['after']},ensure_ascii=False),flush=True)
    label_font=ImageFont.truetype(str(font),17);chosen=['C01','C02','C03','C06'];previews=[]
    for i in range(N):
        image=Image.new('RGB',(3*W,48+len(chosen)*(H+26)),(20,24,32));draw=ImageDraw.Draw(image)
        for column,title in enumerate(('V30 actual','Current actual','Independent reference')):draw.text((column*W+10,12),title,font=label_font,fill='white')
        for row,code in enumerate(chosen):
            y=48+row*(H+26)
            for column,frames in enumerate((decoded[(code,'before')],decoded[(code,'after')],references[code])):
                image.paste(Image.fromarray(frames[i]),(column*W,y+26));draw.text((column*W+8,y),code+' '+titles[int(code[1:])-1],font=label_font,fill='white')
        previews.append(image)
    previews[0].save(output/'comparison-first.png');previews[-1].save(output/'comparison-last.png')
    previews[0].save(output/'comparison.gif',save_all=True,append_images=previews[2::2],duration=[170,160,170]*4,loop=0,optimize=False,disposal=2)
    pw,ph=previews[0].size;ff(['-f','rawvideo','-pix_fmt','rgb24','-s',f'{pw}x{ph}','-r',FPS,'-i','pipe:0','-an','-c:v','libx264','-crf','16','-pix_fmt','yuv444p',output/'comparison.mp4'],b''.join(im.tobytes() for im in previews))
    after=frozen();assert before==after;gif_durations=[]
    with Image.open(output/'comparison.gif') as image:
        for i in range(image.n_frames):image.seek(i);gif_durations.append(image.info.get('duration',0))
    record={'started_at_utc':began,'finished_at_utc':datetime.now(timezone.utc).isoformat(),'baseline_ref':BASELINE,'frozen_before':before,'frozen_after':after,
      'frozen_file_count':len(before),'case_count':len(cases),'cli_count':len(calls),'cli_calls':calls,'cases':cases,
      'new_decoded_frames':N*len(cases),'old_decoded_frames':N*len(cases),'reference_frames':N*len(cases),'local_child_frames':N,
      'content_passed_cases':sum(c['content_gate_passed'] for c in cases),'continuous_playback_accepted':False,'listening_accepted':False,
      'preview':{'mp4_probe':probe(output/'comparison.mp4'),'gif_encoded_frames':len(gif_durations),'gif_duration_ms':sum(gif_durations),'gif_frame_durations_ms':gif_durations},
      'provenance':provenance,'public_files':{p.name:{'sha256':sha(p),'bytes':p.stat().st_size} for p in sorted(output.iterdir()) if p.is_file()}}
    save(output/'verification.json',record)
    print(json.dumps({k:record[k] for k in ('case_count','cli_count','content_passed_cases','new_decoded_frames','frozen_file_count')},ensure_ascii=False),flush=True)
    raise SystemExit(0 if record['content_passed_cases']==len(cases) else 1)

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('output','work','font','font-license'):parser.add_argument('--'+name,type=Path,required=True)
    args=parser.parse_args();run(args.output.resolve(),args.work.resolve(),args.font.resolve(),args.font_license.resolve())
