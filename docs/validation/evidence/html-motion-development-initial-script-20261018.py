"""Real native browser, editable-source portability and independent RGBA evidence.

All creative inputs below and the reused original grid glyphs are CC0. No
download, GUI, model, service, Docker or WSL is invoked. Requires explicitly
installed local runtime JSON, NumPy, Pillow and FontTools for fixture authoring.
"""
from __future__ import annotations
import argparse, contextlib, copy, io, json, os, shutil, subprocess, sys, threading, time
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'product/src'))
from ai_ad_editor.cli import main as cli_main
from ai_ad_editor.html_motion import inspect_source
from ai_ad_editor.media import ffmpeg_path
from ai_ad_editor.project import load_project, save_project
from ai_ad_editor.runtime import configure_local_runtime
from smoke_fragments import frozen, grid_font, save, sha

W,H,FPS,N,TPS=640,360,12,24,90000


def run(public,work,runtime):
    import numpy as np
    from PIL import Image,ImageDraw
    public.mkdir(parents=True,exist_ok=False);work.mkdir(parents=True,exist_ok=False)
    configure_local_runtime()
    before=frozen();calls=[];rows=[]
    save(public/'run-state.json',{'status':'running','source_before':before})
    def cli(*args,expected=0,error=None):
        out,err=io.StringIO(),io.StringIO();started=time.monotonic()
        with contextlib.redirect_stdout(out),contextlib.redirect_stderr(err):
            code=cli_main([str(a) for a in args])
        result=json.loads(out.getvalue())
        number=len(calls)+1
        record={'number':number,'args':list(map(str,args)),'exit_code':code,'stdout':out.getvalue(),
                'stderr':err.getvalue(),'seconds':time.monotonic()-started}
        calls.append(record);save(public/'cli'/f'{number:03}.json',record)
        assert code==expected,(number,result)
        if error:assert result['errors'][0]['code']==error,(number,result)
        return result
    def ff(args,data=None):
        process=subprocess.run([ffmpeg_path(),'-hide_banner','-v','error','-y',*map(str,args)],input=data,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        assert process.returncode==0,process.stderr.decode(errors='replace')
        return process.stdout
    def rgba(path):
        return np.frombuffer(ff(['-i',path,'-an','-f','rawvideo','-pix_fmt','rgba','pipe:1']),np.uint8).reshape(-1,H,W,4)
    def preview(array,path):
        ff(['-f','rawvideo','-pixel_format','rgb24','-video_size',f'{array.shape[2]}x{array.shape[1]}','-framerate',FPS,
            '-i','pipe:0','-an','-c:v','libx264rgb','-preset','ultrafast','-crf','0',path],array.astype(np.uint8).tobytes())
    def configure(project):
        p=load_project(project)[1]
        p['settings']['canvas'].update(width=W,height=H)
        p['settings']['timebase']['display_fps']={'num':FPS,'den':1}
        save_project(project,p)
        cli('motion','html-register','--project',project,'--input',runtime)
    template=public/'template';template.mkdir()
    grid_font(template/'font.ttf')
    (template/'index.html').write_text('''<!doctype html><html><head><meta charset="utf-8"><link rel="stylesheet" href="style.css"></head>
    <body><canvas id="marker" width="640" height="360"></canvas><div id="badge">VIDEO</div>
    <img id="product" src="bottle.svg"><div id="panel"><h1 id="title"></h1><div id="cta">CTA <i></i></div></div>
    <script type="module" src="scene.mjs"></script></body></html>''',encoding='utf-8')
    (template/'style.css').write_text('''@font-face{font-family:AgentGrid;src:url("font.ttf")}*{box-sizing:border-box;margin:0}
    html,body{width:640px;height:360px;overflow:hidden;background:transparent;font-family:AgentGrid}
    #marker{position:absolute;inset:0;pointer-events:none}#badge{position:absolute;left:44px;top:42px;color:#fff;
    font-size:20px;letter-spacing:5px;border-bottom:3px solid var(--brand);padding:0 0 8px}
    #product{position:absolute;width:125px;height:230px;right:48px;top:36px;filter:drop-shadow(0 12px 12px #0005)}
    #panel{position:absolute;left:36px;top:198px;width:568px;height:130px;background:#0b1528e6;border-radius:18px;
    border:1px solid #ffffff28;padding:23px 24px}h1{color:#fff;font-size:44px;line-height:1.3;letter-spacing:2px}
    #cta{position:absolute;right:23px;bottom:24px;color:var(--brand);font-size:22px;display:flex;gap:14px;align-items:center}
    i{display:block;width:12px;height:12px;border-radius:50%;background:var(--brand);animation:pulse 2s linear infinite}
    @keyframes pulse{0%,100%{opacity:.3;transform:scale(.8)}50%{opacity:1;transform:scale(1.2)}}''',encoding='utf-8')
    (template/'scene.mjs').write_text('''const canvas=document.getElementById('marker'),ctx=canvas.getContext('2d');
    const title=document.getElementById('title'),product=document.getElementById('product');
    window.film={width:640,height:360,duration:2,ready:document.fonts.ready,frame(t,p){
      title.textContent=p.title;document.documentElement.style.setProperty('--brand',p.brand);
      product.style.transform=`translateY(${Math.sin(t*Math.PI)*-7}px) rotate(${Math.sin(t*Math.PI)*3}deg)`;
      ctx.clearRect(0,0,640,360);ctx.fillStyle='#00ffcc';ctx.fillRect(8+Math.round(t*12),8,14,8);
    }};''',encoding='utf-8')
    (template/'bottle.svg').write_text('''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 125 230">
    <defs><linearGradient id="b"><stop stop-color="#effbff"/><stop offset=".35" stop-color="#bdd9e8"/>
    <stop offset="1" stop-color="#507288"/></linearGradient></defs><rect x="42" y="3" width="42" height="30" rx="6" fill="#13283d"/>
    <path d="M42 29h42v22c0 12 24 14 24 37v116c0 17-12 24-24 24H41c-13 0-24-7-24-24V88c0-23 25-25 25-37Z" fill="url(#b)"/>
    <rect x="23" y="98" width="79" height="83" rx="6" fill="#153149"/><path d="M46 127h30v8H46zM46 145h23v8H46z" fill="#fb923c"/>
    <path d="M30 87v108" stroke="#ffffff7a" stroke-width="5" stroke-linecap="round"/></svg>''',encoding='utf-8')
    manifest={'entry':'index.html','width':W,'height':H,'fps':{'num':FPS,'den':1},'duration_tick':2*TPS,
        'files':['index.html','style.css','scene.mjs','bottle.svg'],'resources':[{'path':'font.ttf','asset_id':'font'}],
        'variables':[{'name':'title','type':'string','default':'EDIT VIDEO','max_length':12},
                     {'name':'brand','type':'color','default':'#fb923c'}]}
    save(template/'manifest.json',manifest)
    save(public/'parameters.json',{'title':'EDIT 2','brand':'#38bdf8'})
    y,x=np.mgrid[0:H,0:W];background=np.zeros((H,W,3),np.uint8)
    background[:]=np.stack((18+x*20//W,29+y*28//H,50+x*26//W),axis=-1)
    image=Image.fromarray(background);draw=ImageDraw.Draw(image)
    draw.ellipse((32,60,340,370),fill='#21354a');draw.ellipse((250,-180,700,230),fill='#233e51')
    image.save(public/'source.png');background=np.asarray(image)
    preview(np.repeat(background[None],N,axis=0),public/'source.mp4')
    save(public/'fixture-provenance.json',{'license_spdx':'CC0-1.0','generator':'scripts/smoke_html_motion.py',
        'generator_sha256':sha(Path(__file__)),'source':'original HTML/CSS/SVG/Canvas/bottle/background plus original Agent Grid CC0 glyphs',
        'font_generator':'scripts/smoke_fragments.py:grid_font','width':W,'height':H,'fps':FPS,'frames':N,'seconds':2,
        'new_model_inference':0,'audio_streams':0,'virtualization':False,'network_downloads':0})
    project=work/'main';cli('project','init',project);configure(project)
    rights=['--verification-status','verified','--license-spdx','CC0-1.0','--permitted-use','commercial_ad','--evidence',public/'fixture-provenance.json']
    cli('media','ingest','--project',project,'--input',template/'font.ttf','--asset-id','font',*rights)
    cli('media','ingest','--project',project,'--input',public/'source.png','--asset-id','background',*rights)
    source=cli('motion','html-source','--project',project,'--input',template/'manifest.json','--asset-id','editable','--license-spdx','CC0-1.0')
    cli('motion','html-inspect','--project',project,'--source-asset-id','editable')
    p=load_project(project)[1]
    p['sequences'][0]['tracks'].append({'id':'overlay','kind':'video','order':1,'locked':False,'muted':False,'clips':[]})
    p['sequences'][0]['tracks'][0]['clips']=[{'id':'base','asset_id':'background','timeline_start_tick':0,'duration_tick':2*TPS,'source_in_tick':0,'source_out_tick':2*TPS}]
    p['sequences'][0]['duration_tick']=2*TPS;save_project(project,p)
    args=('motion','html-render','--project',project,'--source-asset-id','editable','--asset-id','orange','--apply','--track-id','overlay')
    dry=cli(*args,'--dry-run')
    first=cli(*args,'--expected-project-sha256',dry['data']['plan']['project_sha256'],'--idempotency-key','orange-once')
    replay=cli(*args,'--expected-project-sha256',dry['data']['plan']['project_sha256'],'--idempotency-key','orange-once')
    assert replay['data']['asset']['sha256']==first['data']['asset']['sha256']
    second=cli('motion','html-render','--project',project,'--from-asset-id','orange','--asset-id','blue','--params',public/'parameters.json')
    html_outputs={}
    for key,result in [('S01',first),('S02',second)]:
        path=project/result['data']['asset']['uri'];shutil.copyfile(path,public/f'{key}-alpha.mkv')
        shutil.copyfile(result['data']['report'],public/f'{key}-browser.json')
        pixels=rgba(path);assert len(pixels)==N
        points=[]
        for i,frame in enumerate(pixels):
            select=(frame[:,:,0]==0)&(frame[:,:,1]==255)&(frame[:,:,2]==204)&(frame[:,:,3]==255)
            ys,xs=np.where(select);observed=[int(xs.min()),int(ys.min()),int(xs.max())+1,int(ys.max())+1]
            expected=[8+i,8,22+i,16]
            assert observed==expected and len(xs)==112,(key,i,observed,expected)
            points.append({'frame':i,'bbox':observed,'pixels':len(xs)})
        assert np.all(pixels[:,0,0,3]==0)
        html_outputs[key]=pixels
        over=np.rint(pixels[:,:,:,:3].astype(float)*(pixels[:,:,:,3:4]/255.0)+background[None]*(1-pixels[:,:,:,3:4]/255.0)).clip(0,255).astype(np.uint8)
        preview(over,public/f'{key}-preview.mp4')
        rows.append({'id':key,'actual_frames':N,'independent_marker_frames':N,'marker_checks':points,
            'transparent_corner_frames':N,'browser_report':f'{key}-browser.json'})
    cli('render','--project',project,'--output',public/'S03-timeline.mkv','--container','mkv','--crf','0','--pixel-format','yuv444p','--audio-codec','pcm_f32le')
    actual=rgba(public/'S03-timeline.mkv')[:,:,:,:3]
    orange=html_outputs['S01'];a=orange[:,:,:,3:4]/255.0
    reference=np.rint(orange[:,:,:,:3].astype(float)*a+background[None]*(1-a)).clip(0,255).astype(np.uint8)
    difference=np.abs(actual.astype(int)-reference.astype(int))
    save(public/'S03-independent-composite.json',{'frames':len(actual),'max_rgb_error':int(difference.max()),
        'mean_rgb_error':float(difference.mean()),'threshold_max':8,'threshold_mean':1,
        'reference':'independent straight-alpha RGB over original PNG, no product renderer',
        'passed':bool(difference.max()<=8 and difference.mean()<=1)})
    assert difference.max()<=8 and difference.mean()<=1,(difference.max(),difference.mean())
    preview(actual,public/'S03-timeline.mp4')
    rows.append({'id':'S03','actual_frames':N,'independent_full_frame_alpha_composite':True,
        'max_rgb_error':int(difference.max()),'mean_rgb_error':float(difference.mean())})
    package=public/'editable-project.zip'
    cli('convert','export','--project',project,'--output',package,'--target-format','package')
    restored=work/'restored';cli('convert','import','--input',package,'--output',restored)
    cli('motion','html-register','--project',restored,'--input',runtime)
    cli('motion','html-inspect','--project',restored,'--source-asset-id','editable')
    rebuilt=cli('motion','html-render','--project',restored,'--from-asset-id','orange','--asset-id','restored-orange')
    assert np.array_equal(rgba(restored/rebuilt['data']['asset']['uri']),orange)
    shutil.copyfile(rebuilt['data']['report'],public/'S04-browser.json')
    rows.append({'id':'S04','actual_frames':N,'package_source_code_and_rgba_rebuild_equal':True})
    library=public/'library';request=work/'fragment-save.json'
    save(request,{'id':'html-title','version':1,'sequence_id':'seq_main','clip_ids':[first['data']['generated_clip']['id']]})
    cli('fragment','save','--project',project,'--library',library,'--input',request)
    recipient=work/'recipient';cli('project','init',recipient);configure(recipient)
    save(request,{'id':'html-title','version':1,'sequence_id':'seq_main','track_id':'track_video_1','at_tick':0,'instance_id':'html-one'})
    applied=cli('fragment','apply','--project',recipient,'--library',library,'--input',request)
    rp=load_project(recipient)[1]
    imported=next(a for a in rp['assets'] if a.get('html_motion'))
    imported_source=imported['html_motion']['source_asset_id']
    assert imported_source!='editable'
    inspected=inspect_source(recipient,rp,imported_source)
    assert inspected['data']['scene.mjs']==(template/'scene.mjs').read_bytes()
    third=cli('motion','html-render','--project',recipient,'--from-asset-id',imported['id'],'--asset-id','recipient-orange')
    assert np.array_equal(rgba(recipient/third['data']['asset']['uri']),orange)
    shutil.copyfile(third['data']['report'],public/'S05-browser.json')
    rows.append({'id':'S05','actual_frames':N,'fragment_id_remapped_source_and_rgba_rebuild_equal':True,
                 'resources':inspected['asset']['html_source']['resources']})
    gate=cli('rights','check','--project',project,expected=7)
    save(public/'publish-blocked.json',gate)
    cli('policy','audit','--project',project)
    cli('policy','audit','--project',recipient)
    # Preserve failed actual-browser scenarios and their cleanup receipts publicly.
    for key,extra,error,seconds in [('F01',"fetch('https://example.invalid/no-network').catch(()=>{});",'HTML_PAGE_ERROR',20),
        ('F02','let n=0;window.film.frame=()=>{const c=document.getElementById("marker").getContext("2d");c.clearRect(0,0,640,360);c.fillStyle="red";c.fillRect(++n,8,14,8)};','HTML_FRAME_NONDETERMINISTIC',30),
        ('F03','window.film.frame=()=>{while(true){}};','HTML_TIMEOUT',4)]:
        bad=work/key;bad.mkdir();(bad/'index.html').write_text('<canvas id="marker" width="640" height="360"></canvas><script>window.film={frame(){}};'+extra+'</script>',encoding='utf-8')
        save(bad/'manifest.json',{**manifest,'entry':'index.html','files':['index.html'],'resources':[]})
        cli('motion','html-source','--project',project,'--input',bad/'manifest.json','--asset-id',key+'-source')
        original=(project/'project.json').read_bytes()
        failed=cli('motion','html-render','--project',project,'--source-asset-id',key+'-source','--asset-id',key+'-bad','--timeout-seconds',seconds,expected=6,error=error)
        assert (project/'project.json').read_bytes()==original
        receipt=Path(failed['errors'][0]['path']);shutil.copyfile(receipt,public/f'{key}-failure.json')
        info=json.loads(receipt.read_text(encoding='utf-8'));assert info['cleanup']['all_children_reaped']
        rows.append({'id':key,'expected_rejection':error,'project_unchanged':True,'all_children_reaped':True})
    # Export source/ledger snapshots for inspection; actual runtime remains local-only configuration.
    save(public/'authored-project.json',load_project(project)[1])
    shutil.copyfile(project/'rights-ledger.json',public/'rights-ledger.json')
    compare=np.concatenate([np.repeat(background[None],N,axis=0),rgba(public/'S01-preview.mp4')[:,:,:,:3],rgba(public/'S02-preview.mp4')[:,:,:,:3]],axis=2)
    preview(compare,public/'comparison.mp4')
    images=[Image.fromarray(frame).resize((960,180),Image.Resampling.LANCZOS) for frame in compare[::2]]
    images[0].save(public/'comparison.gif',save_all=True,append_images=images[1:],duration=[167]*11+[163],loop=0,disposal=2)
    for i in (0,N//2,N-1):Image.fromarray(compare[i]).save(public/f'comparison-{i:02}.png')
    assert frozen()==before,'product changed during evidence run'
    files={p.relative_to(public).as_posix():{'bytes':p.stat().st_size,'sha256':sha(p)} for p in sorted(public.rglob('*')) if p.is_file() and p.name not in {'verification.json','run-state.json'}}
    save(public/'verification.json',{'status':'passed','engine':'agent-local-html-motion-v1','source_before':before,
        'source_after':frozen(),'source_frozen_equal':True,'calls':len(calls),'cases':rows,'files':files,
        'primary_encoded_html_frames':4*N,'native_timeline_frames':N,'full_frame_order_verification':'two additional fresh contexts for every HTML render',
        'original_font_license':'CC0-1.0','new_model_inference':0,'sound_review':'no audio in authored input; not listened',
        'visual_review':'machine-only at generation; static inspection recorded separately','capcut_parity_accepted':False})
    save(public/'run-state.json',{'status':'complete','source_frozen_equal':True})
    print(json.dumps({'calls':len(calls),'cases':len(rows),'files':len(files),'frames':5*N}))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True);parser.add_argument('--work',type=Path,required=True)
    parser.add_argument('--runtime',type=Path,required=True);args=parser.parse_args()
    run(args.output.resolve(),args.work.resolve(),args.runtime.resolve())
