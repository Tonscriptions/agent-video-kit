"""Original vector lettering through the native product CLI and independent geometry."""
from __future__ import annotations
import argparse,contextlib,hashlib,io,json,shutil,subprocess,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
sys.path.insert(0,str(ROOT/'product/src'))
from ai_ad_editor.cli import main
from ai_ad_editor.media import ffmpeg_path
from ai_ad_editor.project import load_project,save_project
from ai_ad_editor.runtime import configure_local_runtime
from run_frozen_regression import frozen

W,H,FPS,N=384,216,12,36
TPS=90000

def sha(path):return 'sha256:'+hashlib.sha256(Path(path).read_bytes()).hexdigest()
def save(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')


def run(public,work,evidence,runtime):
    import numpy as np
    from PIL import Image
    for p in (public,work,evidence):p.mkdir(parents=True,exist_ok=False)
    configure_local_runtime();before=frozen();calls=[];browsers=[]
    save(evidence/'state.json',{'status':'started','frozen_before':before})
    def cli(*args,expected=0):
        out,err=io.StringIO(),io.StringIO();start=time.monotonic()
        with contextlib.redirect_stdout(out),contextlib.redirect_stderr(err):code=main(list(map(str,args)))
        value=json.loads(out.getvalue());row={'args':list(map(str,args)),'exit_code':code,'result':value,'stderr':err.getvalue(),'seconds':time.monotonic()-start}
        calls.append(row);save(evidence/'cli'/f'{len(calls):03}.json',row)
        assert code==expected,(len(calls),value)
        return value
    def ff(*args,data=None):
        p=subprocess.run([ffmpeg_path(),'-hide_banner','-v','error','-y',*map(str,args)],input=data,capture_output=True)
        assert p.returncode==0,p.stderr.decode(errors='replace')
        return p.stdout
    def rgba(path):return np.frombuffer(ff('-i',path,'-f','rawvideo','-pix_fmt','rgba','-'),np.uint8).reshape(-1,H,W,4)
    def browser(path,name):
        value=json.loads(Path(path).read_bytes());save(evidence/(name+'.json'),value)
        assert value['cleanup']['all_children_reaped'] and not value['cleanup']['active_after_cleanup']
        assert value['worker']['cleanup']['browser_closed']
        assert value['worker']['cleanup']['pages_opened']==value['worker']['cleanup']['pages_closed']
        assert value['worker']['cleanup']['denied_requests']==0
        browsers.append({'label':name,'cleanup':value['cleanup'],'worker':value['worker']['cleanup']})
    plan={'version':'agent-stroke-motion-v1','width':W,'height':H,'fps':{'num':FPS,'den':1},
        'duration_tick':3*TPS,'stroke_width':7,'color':'#4ee2b1','characters':[
        {'text':'A','start_tick':0,'end_tick':TPS,'strokes':[[[64,160],[112,44],[160,160]],[[84,112],[140,112]]]},
        {'text':' ','start_tick':TPS,'end_tick':TPS*5//4,'strokes':[]},
        {'text':'I','start_tick':TPS*3//2,'end_tick':TPS*9//4,'strokes':[[[230,44],[290,44]],[[260,44],[260,160]],[[230,160],[290,160]]]}
    ]}
    save(public/'authored-plan.json',plan)
    save(public/'provenance.json',{'authored_geometry_and_background':'original Agent Video Kit fixture, CC0-1.0',
        'third_party_code':'OpenFilm and pdoom-video MIT; both licenses preserved in source bundle',
        'no_font_audio_media_or_model_downloads':True,'new_model_inference':0,'continuous_playback_review':False,
        'generator':Path(__file__).relative_to(ROOT).as_posix(),'generator_sha256':sha(__file__)})
    y,x=np.mgrid[:H,:W];bg=np.empty((H,W,3),np.uint8)
    bg[:,:,0]=14+x*10//W;bg[:,:,1]=23+y*12//H;bg[:,:,2]=38+x*14//W
    Image.fromarray(bg).save(public/'source.png')
    ff('-f','rawvideo','-pix_fmt','rgb24','-s',f'{W}x{H}','-r',FPS,'-i','-',
        '-c:v','libx264','-crf','16','-pix_fmt','yuv420p',public/'source.mp4',data=np.repeat(bg[None],N,axis=0).tobytes())
    project=work/'main';cli('project','init',project)
    p=load_project(project)[1];p['settings']['canvas'].update(width=W,height=H)
    p['settings']['timebase']['display_fps']={'num':FPS,'den':1};save_project(project,p)
    cli('motion','html-register','--project',project,'--input',runtime)
    cli('media','ingest','--project',project,'--input',public/'source.png','--asset-id','background',
        '--license-spdx','CC0-1.0','--verification-status','verified','--permitted-use','commercial_ad','--evidence',public/'provenance.json')
    source_args=('motion','stroke-source','--project',project,'--input',public/'authored-plan.json','--asset-id','ink-source','--creator','Agent Video Kit fixture','--license-spdx','LicenseRef-CC0-MIT')
    state=(project/'project.json').read_bytes();cli(*source_args,'--dry-run');assert state==(project/'project.json').read_bytes()
    source=cli(*source_args,'--idempotency-key','authored-ink')
    replay=cli(*source_args,'--idempotency-key','authored-ink');assert replay['warnings'][-1]['code']=='IDEMPOTENT_REPLAY'
    cli('motion','html-inspect','--project',project,'--source-asset-id','ink-source')
    shutil.copyfile(project/source['data']['asset']['uri'],public/'editable-source.zip')
    p=load_project(project)[1];seq=p['sequences'][0]
    seq['tracks'][0]['clips']=[{'id':'base','asset_id':'background','timeline_start_tick':0,'duration_tick':3*TPS,'source_in_tick':0,'source_out_tick':3*TPS}]
    seq['tracks'].append({'id':'ink','kind':'video','order':1,'locked':False,'muted':False,'clips':[]})
    seq['duration_tick']=3*TPS;save_project(project,p)
    args=('motion','html-render','--project',project,'--source-asset-id','ink-source','--asset-id','ink-green','--apply','--track-id','ink')
    cli(*args,'--dry-run');render=cli(*args,'--idempotency-key','ink-render')
    browser(render['data']['report'],'green-browser');raw=rgba(project/render['data']['asset']['uri'])
    assert raw.shape==(N,H,W,4)
    shutil.copyfile(project/render['data']['asset']['uri'],public/'green-alpha.nut')
    save(public/'blue-params.json',{'ink_color':'#60a5fa'})
    blue=cli('motion','html-render','--project',project,'--from-asset-id','ink-green','--asset-id','ink-blue','--params',public/'blue-params.json')
    browser(blue['data']['report'],'blue-browser');blue_pixels=rgba(project/blue['data']['asset']['uri'])
    assert np.array_equal(raw[:,:,:,3],blue_pixels[:,:,:,3]);assert not np.array_equal(raw,blue_pixels)
    save(public/'bad-params.json',{'ink_color':'red'})
    state=(project/'project.json').read_bytes();ledger=(project/'rights-ledger.json').read_bytes()
    bad=cli('motion','html-render','--project',project,'--from-asset-id','ink-green','--asset-id','bad-color','--params',public/'bad-params.json',expected=6)
    assert state==(project/'project.json').read_bytes() and ledger==(project/'rights-ledger.json').read_bytes()
    # Failed browser report survives and its native Job was closed as well.
    failure_report=Path(bad['errors'][0]['path'])
    if failure_report.is_file():browser(failure_report,'bad-color-browser')
    # Independent per-character path truncation; never consumes compiled geometry.
    yy,xx=np.mgrid[:H,:W];centers=np.stack((xx+.5,yy+.5),axis=-1);checks=[]
    for frame in range(N):
        moment=frame/FPS;distance=np.full((H,W),np.inf)
        for char in plan['characters']:
            ratio=max(0,min(1,(moment-char['start_tick']/TPS)/((char['end_tick']-char['start_tick'])/TPS)))
            segments=[(np.array(a,float),np.array(b,float)) for line in char['strokes'] for a,b in zip(line,line[1:])]
            budget=sum(float(np.linalg.norm(b-a)) for a,b in segments)*ratio
            for a,b in segments:
                length=float(np.linalg.norm(b-a))
                if budget<=0:break
                b=a+(b-a)*min(1,budget/length);vector=b-a
                u=np.clip(np.sum((centers-a)*vector,axis=-1)/np.sum(vector*vector),0,1)
                distance=np.minimum(distance,np.linalg.norm(centers-(a+u[:,:,None]*vector),axis=-1))
                budget-=length
        inner=distance<plan['stroke_width']/2-2;outer=distance>plan['stroke_width']/2+2
        correct=np.count_nonzero(raw[frame,:,:,3][inner]>=250)+np.count_nonzero(raw[frame,:,:,3][outer]<=5)
        checked=np.count_nonzero(inner)+np.count_nonzero(outer)
        coverage=correct/checked;assert coverage>=.999,(frame,coverage)
        checks.append({'frame':frame,'seconds':moment,'checked_pixels':int(checked),'correct_pixels':int(correct),'coverage':coverage})
    save(evidence/'independent-geometry.json',{'gate':.999,'edge_exclusion_px':2,'reference':'authored per-character segments and independent truncation, not generated geometry','frames':checks})
    cli('render','--project',project,'--output',project/'renders/ink.mp4')
    shutil.copyfile(project/'renders/ink.mp4',public/'result.mp4')
    cli('rights','check','--project',project,expected=7)
    package=work/'project.zip';cli('convert','export','--project',project,'--target-format','package','--output',package)
    restored=work/'restored';cli('convert','import','--input',package,'--output',restored)
    cli('motion','html-register','--project',restored,'--input',runtime)
    rebuilt=cli('motion','html-render','--project',restored,'--from-asset-id','ink-green','--asset-id','ink-restored')
    browser(rebuilt['data']['report'],'restored-browser')
    assert np.array_equal(rgba(restored/rebuilt['data']['asset']['uri']),raw)
    composed=rgba(public/'result.mp4')[:,:,:,:3]
    compare=np.concatenate((np.repeat(bg[None],N,axis=0),composed),axis=2)
    ff('-f','rawvideo','-pix_fmt','rgb24','-s',f'{W*2}x{H}','-r',FPS,'-i','-',
        '-c:v','libx264','-crf','16','-pix_fmt','yuv420p',public/'comparison.mp4',data=compare.tobytes())
    images=[Image.fromarray(f) for f in compare[::2]]
    images[0].save(public/'comparison.gif',save_all=True,append_images=images[1:],duration=[170,160]*9,loop=0,disposal=2)
    contact=np.concatenate([compare[i] for i in (0,18,35)],axis=0);Image.fromarray(contact).save(public/'contact.png')
    assert frozen()==before
    files={p.relative_to(public).as_posix():{'bytes':p.stat().st_size,'sha256':sha(p)} for p in sorted(public.rglob('*')) if p.is_file()}
    record={'status':'passed','frozen_equal':True,'frozen_before':before,'frozen_after':frozen(),'calls':len(calls),
        'successful_html_encodings':3,'primary_html_frames':3*N,'extra_order_redraws':6*N,
        'timeline_render_frames':N,'package_rgba_rebuild_equal':True,'geometry_frames':N,'geometry_min_coverage':min(r['coverage'] for r in checks),
        'browser_reports':browsers,'files':files,'generator_sha256':sha(__file__),'new_model_inference':0,
        'visual_review':'not yet viewed; static review is separate','continuous_playback_review':False,'audio_listened':False,
        'capcut_parity':False,'automatic_glyph_generation':False,'automatic_speech_alignment':False}
    save(evidence/'verification.json',record);save(public/'verification.json',record)
    save(evidence/'state.json',{'status':'passed','calls':len(calls),'frozen_equal':True})
    print(json.dumps({k:record[k] for k in ('status','calls','primary_html_frames','geometry_min_coverage','package_rgba_rebuild_equal')}))


if __name__=='__main__':
    p=argparse.ArgumentParser()
    for key in ('public','work','evidence','runtime'):p.add_argument('--'+key,type=Path,required=True)
    a=p.parse_args();run(*(getattr(a,k).resolve() for k in ('public','work','evidence','runtime')))
