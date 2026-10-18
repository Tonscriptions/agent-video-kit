"""Real offline HTML template changes, resource portability and original media."""
from __future__ import annotations
import argparse, contextlib, copy, io, json, shutil, subprocess, sys, time
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'product/src'))
from ai_ad_editor.cli import main
from ai_ad_editor.media import ffmpeg_path
from ai_ad_editor.project import load_project, save_project
from ai_ad_editor.runtime import configure_local_runtime
from smoke_fragments import frozen, grid_font, save, sha

W,H,FPS,N,TPS=384,216,6,12,90000


def run(work,public,evidence,runtime):
    import numpy as np
    from PIL import Image,ImageDraw
    for p in (work,public,evidence):p.mkdir(parents=True,exist_ok=False)
    configure_local_runtime();before=frozen();calls=[];reports=[]
    save(evidence/'state.json',{'status':'started','frozen_before':before})
    def cli(*args,expected=0,error=None):
        output,stderr=io.StringIO(),io.StringIO();started=time.monotonic()
        with contextlib.redirect_stdout(output),contextlib.redirect_stderr(stderr):code=main(list(map(str,args)))
        result=json.loads(output.getvalue());number=len(calls)+1
        row={'number':number,'args':list(map(str,args)),'exit_code':code,'stdout':result,'stderr':stderr.getvalue(),'seconds':time.monotonic()-started}
        calls.append(row);save(evidence/'cli'/f'{number:03}.json',row)
        assert code==expected,(number,result)
        if error:assert result['errors'][0]['code']==error,(number,result)
        return result
    def ff(args,data=None):
        value=subprocess.run([ffmpeg_path(),'-hide_banner','-v','error','-y',*map(str,args)],input=data,capture_output=True)
        assert value.returncode==0,value.stderr.decode(errors='replace')
        return value.stdout
    def rgba(path):
        raw=ff(['-i',path,'-an','-f','rawvideo','-pix_fmt','rgba','-threads','1','pipe:1'])
        return np.frombuffer(raw,np.uint8).reshape(N,H,W,4)
    def movie(array,path):
        ff(['-f','rawvideo','-pix_fmt','rgb24','-s',f'{array.shape[2]}x{array.shape[1]}','-r',FPS,'-i','pipe:0',
            '-an','-c:v','libx264rgb','-crf','0','-preset','ultrafast',path],array[:,:,:,:3].copy().tobytes())
    def configure(project):
        p=load_project(project)[1];p['settings']['canvas'].update(width=W,height=H)
        p['settings']['timebase']['display_fps']={'num':FPS,'den':1};save_project(project,p)
        cli('motion','html-register','--project',project,'--input',runtime)
    def report(result,key):
        source=Path(result.get('data',{}).get('report') or result['errors'][0]['path'])
        value=json.loads(source.read_text(encoding='utf-8'))
        assert value['cleanup']['all_children_reaped'] and value['cleanup']['active_after_cleanup']==[]
        save(evidence/(key+'-browser.json'),value);reports.append({'id':key,'cleanup':value['cleanup'],'worker':value.get('worker',{}).get('cleanup')})
        return value
    template=public/'template';template.mkdir();grid_font(template/'font.ttf')
    for name,color in [('original-product','#fb923c'),('new-product','#38bdf8')]:
        image=Image.new('RGBA',(96,128));draw=ImageDraw.Draw(image)
        draw.rounded_rectangle((34,0,62,20),radius=3,fill='#a9bac9')
        draw.rounded_rectangle((18,15,78,126),radius=14,fill=color)
        draw.rounded_rectangle((22,48,74,96),radius=5,fill='#13243b')
        draw.line((31,62,65,62),fill='white',width=3);draw.line((31,74,57,74),fill='white',width=3)
        image.save(template/(name+'.png'))
    (template/'index.html').write_text('''<!doctype html><meta charset="utf-8"><link rel="stylesheet" href="style.css">
      <div id="meter"></div><h1 id="title">EDIT VIDEO</h1><p id="cta">CTA</p><img id="product" src="product.png">
      <script type="module" src="scene.mjs"></script>''',encoding='utf-8')
    (template/'style.css').write_text('''@font-face{font-family:AgentGrid;src:url(font.ttf)}
      :root{--brand:#fb923c;--title-size:26px;--title-font:"AgentGrid";--note:"EDIT";--ratio:50%}
      *{margin:0;box-sizing:border-box}html,body{width:384px;height:216px;background:#101829;overflow:hidden}
      #meter{position:absolute;left:20px;top:20px;width:120px;height:12px;background:var(--brand)}
      h1{position:absolute;left:24px;top:76px;color:white;font-family:var(--title-font);font-size:var(--title-size)}
      #cta{position:absolute;left:24px;top:142px;color:var(--brand);font:20px AgentGrid}
      #product{position:absolute;left:268px;top:44px;width:96px;height:128px}''',encoding='utf-8')
    (template/'scene.mjs').write_text('''const title=document.getElementById('title'),product=document.getElementById('product');
      window.film={width:384,height:216,duration:2,ready:document.fonts.ready,frame(t){
        title.textContent=t<1?"EDIT VIDEO":"EDIT 2";
        product.style.transform=`translateY(${Math.round(Math.sin(t*Math.PI)*-8)}px)`;
      }};''',encoding='utf-8')
    save(template/'manifest.json',{'entry':'index.html','width':W,'height':H,'fps':{'num':FPS,'den':1},'duration_tick':2*TPS,
        'variables':[],'files':['index.html','style.css','scene.mjs'],
        'resources':[{'path':'font.ttf','asset_id':'font'},{'path':'product.png','asset_id':'product-original'}]})
    patch={'variables':{'--brand':'#38bdf8','--title-size':'30px'},'texts':[{'at':'#title','value':'VIDEO 2'},{'at':'#cta','value':'CTA 2'}],
        'images':[{'at':'#product','kind':'img','asset_id':'product-new'}]}
    save(public/'overrides.json',patch)
    save(public/'reset.json',{'variables':{k:None for k in patch['variables']},
        'texts':[{**x,'value':None} for x in patch['texts']],'images':[{**x,'asset_id':None} for x in patch['images']]})
    save(public/'provenance.json',{'license_spdx':'CC0-1.0','source':'original procedural product drawings and HTML/CSS; original grid font from smoke_fragments.py',
        'generator_sha256':sha(Path(__file__)),'width':W,'height':H,'frames':N,'fps':FPS,'seconds':2,'new_model_inference':0,'audio_streams':0})
    project=work/'main';cli('project','init',project);configure(project)
    rights=['--license-spdx','CC0-1.0','--verification-status','verified','--permitted-use','commercial_ad','--evidence',public/'provenance.json']
    for aid,path in [('font',template/'font.ttf'),('product-original',template/'original-product.png'),('product-new',template/'new-product.png')]:
        cli('media','ingest','--project',project,'--input',path,'--asset-id',aid,*rights)
    cli('motion','html-source','--project',project,'--input',template/'manifest.json','--asset-id','editable','--license-spdx','CC0-1.0')
    source_hash=next(a['sha256'] for a in load_project(project)[1]['assets'] if a['id']=='editable')
    original=cli('motion','html-render','--project',project,'--source-asset-id','editable','--asset-id','original')
    report(original,'S01');base=rgba(project/original['data']['asset']['uri'])
    old_project=(project/'project.json').read_bytes();old_ledger=(project/'rights-ledger.json').read_bytes()
    inspected=cli('motion','html-controls','--project',project,'--source-asset-id','editable','--frame-index','3','--overrides',public/'overrides.json')
    inspection=report(inspected,'S02')
    assert (project/'project.json').read_bytes()==old_project and (project/'rights-ledger.json').read_bytes()==old_ledger
    variables={v['name']:v for v in inspection['controls']['vars']}
    assert variables['--title-size']['field']=={'kind':'number','value':26,'unit':'px'}
    assert variables['--brand']['field']['kind']=='color' and variables['--title-font']['font']
    assert next(v['value'] for v in inspection['effective_controls']['vars'] if v['name']=='--title-size')=='30px'
    changed=cli('motion','html-render','--project',project,'--source-asset-id','editable','--asset-id','changed',
        '--overrides',public/'overrides.json','--apply','--track-id','track_video_1')
    report(changed,'S03');actual=rgba(project/changed['data']['asset']['uri'])
    assert np.all(base[:,20:32,20:140,:]==np.array([251,146,60,255],dtype=np.uint8))
    assert np.all(actual[:,20:32,20:140,:]==np.array([56,189,248,255],dtype=np.uint8))
    # Independently compare the opaque interiors of the actual replacement
    # PNG at its authored integer motion positions, not another renderer.
    picture=np.asarray(Image.open(template/'new-product.png').convert('RGBA'));interior=picture[:,:,3]==255
    for frame in range(N):
        import math
        # JS Math.round: floor(x+.5), including the negative half convention.
        offset=math.floor(math.sin(frame/FPS*math.pi)*-8+.5)
        assert np.array_equal(actual[frame,44+offset:172+offset,268:364][interior],picture[interior])
    inherited=cli('motion','html-render','--project',project,'--from-asset-id','changed','--asset-id','inherited')
    report(inherited,'S04');assert np.array_equal(actual,rgba(project/inherited['data']['asset']['uri']))
    reset=cli('motion','html-render','--project',project,'--from-asset-id','changed','--asset-id','reset','--overrides',public/'reset.json')
    report(reset,'S05');reset_pixels=rgba(project/reset['data']['asset']['uri']);assert np.array_equal(base,reset_pixels)
    package=work/'project.zip';cli('convert','export','--project',project,'--output',package,'--target-format','package')
    restored=work/'restored';cli('convert','import','--input',package,'--output',restored)
    cli('motion','html-register','--project',restored,'--input',runtime)
    rebuilt=cli('motion','html-render','--project',restored,'--from-asset-id','changed','--asset-id','rebuilt')
    report(rebuilt,'S06');assert np.array_equal(actual,rgba(restored/rebuilt['data']['asset']['uri']))
    library=work/'library';request=work/'fragment.json'
    save(request,{'id':'brand-card','version':1,'sequence_id':'seq_main','clip_ids':[changed['data']['generated_clip']['id']]})
    cli('fragment','save','--project',project,'--library',library,'--input',request)
    recipient=work/'recipient';cli('project','init',recipient);configure(recipient)
    save(request,{'id':'brand-card','version':1,'sequence_id':'seq_main','track_id':'track_video_1','at_tick':0,'instance_id':'brand-one'})
    cli('fragment','apply','--project',recipient,'--library',library,'--input',request)
    rp=load_project(recipient)[1];imported=next(a for a in rp['assets'] if a.get('html_motion'))
    replacement=imported['html_motion']['template_overrides']['images'][0]['asset_id']
    assert replacement!='product-new' and any(a['id']==replacement for a in rp['assets'])
    rebuilt2=cli('motion','html-render','--project',recipient,'--from-asset-id',imported['id'],'--asset-id','fragment-rebuilt')
    report(rebuilt2,'S07');assert np.array_equal(actual,rgba(recipient/rebuilt2['data']['asset']['uri']))
    for aid,label in [('original','original'),('changed','changed'),('reset','restored')]:
        p=load_project(project)[1];asset=next(a for a in p['assets'] if a['id']==aid)
        shutil.copyfile(project/asset['uri'],public/(label+'-alpha.nut'))
    movie(base,public/'original.mp4');movie(actual,public/'changed.mp4');movie(reset_pixels,public/'restored.mp4')
    combined=np.concatenate([base,actual,reset_pixels],axis=2)
    movie(combined,public/'comparison.mp4')
    gif=[Image.fromarray(v[:,:,:3]).resize((768,144),Image.Resampling.LANCZOS) for v in combined]
    gif[0].save(public/'comparison.gif',save_all=True,append_images=gif[1:],duration=[170,160]*6,loop=0,disposal=2)
    contact=Image.new('RGB',(W*3,H*3))
    for row,frame in enumerate((0,5,11)):contact.paste(Image.fromarray(combined[frame,:,:,:3]),(0,row*H))
    contact.save(public/'contact.png')
    # Negative controls are actual CLI attempts. Source and project remain
    # untouched; invalid image bytes are restored after the rejection.
    failed_patch=work/'invalid.json';save(failed_patch,{'texts':[{'at':'#removed','value':'No'}]})
    before_fail=(project/'project.json').read_bytes();ledger_fail=(project/'rights-ledger.json').read_bytes()
    failed=cli('motion','html-render','--project',project,'--source-asset-id','editable','--asset-id','bad',
        '--overrides',failed_patch,expected=6,error='HTML_OVERRIDE_TARGET_MISSING');report(failed,'F01')
    assert (project/'project.json').read_bytes()==before_fail and (project/'rights-ledger.json').read_bytes()==ledger_fail
    save(failed_patch,{'variables':{'--brand':'url(https://example.invalid/x)'}})
    cli('motion','html-render','--project',project,'--source-asset-id','editable','--asset-id','bad',
        '--overrides',failed_patch,'--dry-run',expected=2,error='HTML_OVERRIDE_INVALID')
    p=load_project(project)[1];asset=next(a for a in p['assets'] if a['id']=='product-new');path=project/asset['uri'];old=path.read_bytes()
    try:
        path.write_bytes(old+b'changed')
        cli('motion','html-render','--project',project,'--from-asset-id','changed','--asset-id','bad',
            '--dry-run',expected=2,error='HTML_OVERRIDE_INVALID')
    finally:path.write_bytes(old)
    gate=cli('rights','check','--project',project,expected=7);save(evidence/'publish-blocked.json',gate)
    cli('policy','audit','--project',project);cli('policy','audit','--project',recipient)
    assert next(a['sha256'] for a in load_project(project)[1]['assets'] if a['id']=='editable')==source_hash
    assert frozen()==before,'product or tests changed during real fixture'
    media={p.relative_to(public).as_posix():{'bytes':p.stat().st_size,'sha256':sha(p)} for p in sorted(public.rglob('*')) if p.is_file()}
    save(evidence/'verification.json',{'status':'passed','frozen_before':before,'frozen_after':frozen(),'frozen_equal':True,
        'actual_cli_calls':len(calls),'html_renders':6,'encoded_html_frames':6*N,'additional_order_redraws':12*N,
        'inspection_frames':2,'model_inference_calls':0,'source_zip_unchanged':True,'inherit_rgba_equal':True,'reset_original_rgba_equal':True,
        'package_rebuild_rgba_equal':True,'fragment_rebuild_rgba_equal':True,'replacement_asset_id_remapped':replacement,
        'independent_brand_pixels':N*12*120,'independent_opaque_image_pixels':int(interior.sum())*N,
        'browser_reports':reports,'media':media,'generator_sha256':sha(Path(__file__)),
        'visual_review':'not yet inspected at generation','continuous_playback':False,'listening':'no audio in fixture',
        'capcut_parity_accepted':False})
    save(evidence/'state.json',{'status':'complete','frozen_equal':True})
    print(json.dumps({'status':'passed','cli_calls':len(calls),'html_frames':6*N,'media_files':len(media)}))


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    for key in ('work','public','evidence','runtime'):parser.add_argument('--'+key,type=Path,required=True)
    args=parser.parse_args();run(*(getattr(args,k).resolve() for k in ('work','public','evidence','runtime')))
