"""Run the frame host over actual 16-bit source bundles; encode honest demos."""
from datetime import datetime,timezone
from fractions import Fraction
import argparse,copy,hashlib,json,math,os,shutil,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];PARENT=ROOT.parent/'color-precision-lab-20261021'
sys.path.append(str(ROOT/'scripts'))
INSTALLED=None
if '--installed' in sys.argv:
    INSTALLED=Path(sys.argv[sys.argv.index('--installed')+1]).resolve()
    assert sys.flags.isolated and sys.flags.no_site
    sys.path.insert(0,str(INSTALLED/'site'))
else:sys.path.insert(0,str(ROOT/'product/src'))
import numpy as np
from PIL import Image,ImageDraw
from run_frozen_regression import frozen,sha
from ai_ad_editor.runtime import configure_local_runtime
configure_local_runtime()
from ai_ad_editor.float_bundle_source import BundleSurfaceSource
from ai_ad_editor.float_timeline import FloatTimeline
from ai_ad_editor.float_color_signal import ColorSignal
from ai_ad_editor.media import ffmpeg_path,ffprobe_path
from ai_ad_editor.project import initial_project
from ai_ad_editor.schema_contract import make_validator

LINEAR=ColorSignal('bt709','linear')
def write(p,v):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(v,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf8')
def reference_sample(source,i):
    """Independent inverse geometry + premultiplied bilinear reference."""
    h,w=source.shape[:2];y,x=np.indices((h,w),dtype=np.float64)
    mask=(x-w/2)**2+(y-h/2)**2<=(.42*min(w,h))**2
    a=source[...,3].astype(np.float64)*mask
    premul=np.concatenate((source[...,:3].astype(np.float64)*a[...,None],a[...,None]),-1)
    angle=math.radians(-8+.8*i);zoom=.84;px=.4+.01*i;cx=w/2-.5;cy=h/2-.5
    dx=x-(w*px-.5);dy=y-(h/2-.5)
    xx=(math.cos(angle)*dx+math.sin(angle)*dy)/zoom+cx
    yy=(-math.sin(angle)*dx+math.cos(angle)*dy)/zoom+cy
    x0=np.floor(xx).astype(np.int64);y0=np.floor(yy).astype(np.int64);fx=xx-x0;fy=yy-y0;v=np.zeros_like(premul)
    for ox,oy,weight in ((0,0,(1-fx)*(1-fy)),(1,0,fx*(1-fy)),(0,1,(1-fx)*fy),(1,1,fx*fy)):
        sx=x0+ox;sy=y0+oy;valid=(sx>=0)&(sx<w)&(sy>=0)&(sy<h)
        v[valid]+=premul[sy[valid],sx[valid]]*weight[valid,None]
    alpha=v[...,3:4];colour=np.divide(v[...,:3],alpha,out=np.zeros_like(v[...,:3]),where=alpha>0)
    return np.concatenate((colour,alpha),-1).astype(np.float32)

def compose(bottom,top,opacity):
    a=bottom.astype(np.float64);b=top.astype(np.float64);ass=b[...,3:4]*opacity;ab=a[...,3:4];alpha=ass+ab*(1-ass)
    p=b[...,:3]*ass+a[...,:3]*ab*(1-ass)
    return np.concatenate((np.divide(p,alpha,out=np.zeros_like(p),where=alpha>0),alpha),-1).astype(np.float32)

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--revision',required=True);parser.add_argument('--installed');parser.add_argument('--reference');parser.add_argument('--source-root',type=Path);args=parser.parse_args()
    source_root=args.source_root.resolve() if args.source_root else (PARENT if (PARENT/'docs/assets/color-precision-20261021-lab').is_dir() else ROOT)
    out=ROOT/'docs/assets/float-timeline-20261022-lab'/('media-'+args.revision);evidence=ROOT/'docs/validation/evidence/float-timeline-20261022-lab'/('media-'+args.revision)
    assert not out.exists() and not evidence.exists();out.mkdir(parents=True);evidence.mkdir(parents=True)
    work=ROOT/'product/.runtime/float-timeline-20261022'/('media-'+args.revision);work.mkdir(parents=True,exist_ok=False)
    before=frozen();assert len(before)==288;calls=[];checks=[];frames_meta=[]
    record={'status':'running','started_at_utc':datetime.now(timezone.utc).isoformat(),'script_sha256':sha(Path(__file__)),'frozen_before':before,
        'native_calls':calls,'checks':checks,'native_windows':True,'virtualization':False,'network':False,'actual_CLI_processes':0,
        'default_render_preview_audio_cache_integrated':False,'published':False,'source_media_root':str(source_root),'source_material':'parent V92 procedurally generated 16-bit originals, byte-verified copied inputs'}
    def save():write(evidence/'verification.json',record)
    def check(name,condition,**details):
        checks.append(dict(name=name,passed=bool(condition),**details));save();assert condition,name
    def native(command):
        p=subprocess.run(list(map(str,command)),capture_output=True,timeout=180,cwd=ROOT,creationflags=subprocess.CREATE_NO_WINDOW)
        row={'command':list(map(str,command)),'exit_code':p.returncode,'stdout_bytes':len(p.stdout),'stdout_sha256':'sha256:'+hashlib.sha256(p.stdout).hexdigest(),
            'stderr_sha256':'sha256:'+hashlib.sha256(p.stderr).hexdigest()};calls.append(row)
        (evidence/('native-%02d.stderr.txt'%len(calls))).write_bytes(p.stderr);save();assert p.returncode==0,p.stderr.decode('utf8','replace')[-2000:]
        return p.stdout
    save()
    try:
        parent_assets=source_root/'docs/assets/color-precision-20261021-lab';parent_receipt=source_root/'docs/validation/evidence/color-precision-20261021-lab/surface-cli-media-r1/verification.json'
        previous=json.loads(parent_receipt.read_bytes());check('actual parent media terminal receipt',previous['status'].startswith('passed'),receipt_sha256=sha(parent_receipt))
        sources=[];copied={}
        for name in ('background','foreground'):
            original=parent_assets/'native-source-media-r1'/(name+'-16bit.mkv');target=out/'inputs'/original.name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(original,target)
            check(name+' original copied exactly',sha(original)==sha(target),sha256=sha(target))
            for p in sorted((parent_assets/'surface-cli-media-r1/bundles'/name).iterdir()):
                t=out/'bundles'/name/p.name;t.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,t);assert sha(t)==sha(p);copied[str(t.relative_to(ROOT)).replace('\\','/')]=sha(t)
            sources.append({'id':name,'kind':'video','uri':str(target.relative_to(ROOT)).replace('\\','/'),'sha256':sha(target),
                'probe':{'width':160,'height':96,'duration_tick':2000},'rights_ref':'rights_generated_'+name})
        p=initial_project('Float32 authored timeline real media','float_timeline_media');p['settings']['timebase']={'ticks_per_second':1000,'display_fps':{'num':10,'den':1}}
        p['settings']['canvas'].update(width=160,height=96,background='#000000');p['assets']=sources;seq=p['sequences'][0];seq.update(duration_tick=2000)
        base={'timeline_start_tick':0,'duration_tick':2000,'source_in_tick':0,'source_out_tick':2000}
        back=dict(base,id='background',asset_id='background');front=dict(base,id='foreground',asset_id='foreground',reverse=True,
            source_out_tick=1600,freeze={'at_tick':500,'duration_tick':400},mask={'type':'circle','radius':.42},transform={'scale':.84},
            keyframes=[{'property':key,'keyframes':[{'at_tick':0,'value':a,'interpolation':'linear'},{'at_tick':2000,'value':b,'interpolation':'linear'}]} for key,a,b in
                (('rotation',-8,8),('position.x',.4,.6),('opacity',.25,.85))])
        seq['tracks']=[{'id':'background','kind':'video','order':0,'clips':[back]},{'id':'foreground','kind':'video','order':1,'clips':[front]}]
        make_validator().validate(p);check('demonstration project passes actual packaged schema',True);write(out/'project.json',p);originals=copy.deepcopy(p)
        actual=[];baseline=[];max_error=0.
        with BundleSurfaceSource(ROOT,out/'bundles/background',sources[0]) as b,BundleSurfaceSource(ROOT,out/'bundles/foreground',sources[1]) as f:
            host=FloatTimeline(p,seq['id'],{'background':b,'foreground':f},working_signal=LINEAR)
            expected_indices=[15,14,13,12,11]+[10]*5+list(range(9,-1,-1))
            check('author output clock is exactly 20 frames at 10 FPS',host.frame_count==20)
            for i in range(20):
                value,meta=host.render_frame(i);background=b.fetch(i);foreground=f.fetch(expected_indices[i]);layer=reference_sample(foreground,i)
                expected=compose(background,layer,.25+.03*i);delta=float(np.max(np.abs(value.astype(np.float64)-expected)))
                max_error=max(max_error,delta);check('independent full Float32 reference frame '+str(i),delta<=2e-7,maximum_absolute_error=delta)
                check('original reverse/freeze native frame '+str(i),meta['layers'][-1]['native_frame_index']==expected_indices[i])
                actual.append(value);baseline.append(compose(background,f.fetch(i),1.));frames_meta.append(meta)
            host.verify_sources();record['frame_host_metadata']=host.metadata;record['source_providers']=[b.metadata,f.metadata]
        check('both source mmaps closed after verified context',b.closed and f.closed and b.pixels is None and f.pixels is None)
        check('authored project retained byte-equivalent data',p==originals)
        raw=out/'timeline.rgba-f32le';raw.write_bytes(b''.join(v.astype('<f4').tobytes() for v in actual));write(evidence/'frames.json',frames_meta)
        record['maximum_full_frame_reference_error']=max_error;record['original_frame_indices']=expected_indices
        for name,values in (('original',baseline),('timeline',actual)):
            # Video demos are SDR encodes; the accepted high-precision intermediate remains linear Float32.
            linear=np.stack(values)[...,:3].astype(np.float64);encoded=np.where(linear<.018,4.5*linear,1.099*np.maximum(linear,0)**.45-.099)
            quant=np.rint(np.clip(encoded,0,1)*65535).astype('<u2');planar=np.moveaxis(quant[...,[1,2,0]],-1,1);r=work/(name+'.gbrp16le');r.write_bytes(planar.tobytes())
            native([ffmpeg_path(),'-nostdin','-v','error','-threads','1','-f','rawvideo','-pixel_format','gbrp16le','-video_size','160x96','-framerate','10','-i',r,
                '-frames:v','20','-c:v','ffv1','-level','3','-pix_fmt','gbrp16le','-color_range','pc','-color_primaries','bt709','-color_trc','bt709',out/(name+'-16bit.mkv')])
            decoded=native([ffmpeg_path(),'-nostdin','-v','error','-threads','1','-i',out/(name+'-16bit.mkv'),'-map','0:v:0','-pix_fmt','gbrp16le','-f','rawvideo','pipe:1'])
            check(name+' lossless SDR16 every encoded channel byte',decoded==planar.tobytes())
            native([ffmpeg_path(),'-nostdin','-v','error','-threads','1','-i',out/(name+'-16bit.mkv'),'-c:v','libx264','-preset','medium','-crf','16','-pix_fmt','yuv420p',
                '-color_range','tv','-colorspace','bt709','-color_primaries','bt709','-color_trc','bt709','-movflags','+faststart','-an',out/(name+'.mp4')])
            native([ffmpeg_path(),'-nostdin','-v','error','-filter_complex_threads','1','-i',out/(name+'.mp4'),'-filter_complex',
                'fps=10,scale=320:-1:flags=lanczos,split[a][b];[a]palettegen[p];[b][p]paletteuse','-loop','0',out/(name+'.gif')])
            for ext in ('mp4','gif'):
                data=json.loads(native([ffprobe_path(),'-v','error','-select_streams','v:0','-show_frames','-show_streams','-show_entries',
                    'frame=best_effort_timestamp_time,duration_time:stream=width,height,avg_frame_rate,nb_frames','-of','json',out/(name+'.'+ext)]))
                times=[Fraction(v['best_effort_timestamp_time']) for v in data['frames']]
                check(name+'.'+ext+' actual every PTS and duration',times==[Fraction(i,10) for i in range(20)] and all(Fraction(v['duration_time'])==Fraction(1,10) for v in data['frames']))
                write(evidence/(name+'-'+ext+'-probe.json'),data)
            rgb=native([ffmpeg_path(),'-nostdin','-v','error','-threads','1','-i',out/(name+'.mp4'),'-pix_fmt','rgb24','-f','rawvideo','pipe:1'])
            check(name+' MP4 decoded exactly 20 full frames',len(rgb)==20*160*96*3)
            frames=np.frombuffer(rgb,np.uint8).reshape(20,96,160,3)
            for index in (0,9,19):Image.fromarray(frames[index]).save(work/(name+'-'+str(index)+'.png'))
        sheet=Image.new('RGB',(960,424),'#1b1e24');draw=ImageDraw.Draw(sheet)
        for row,name in enumerate(('original','timeline')):
            for col,index in enumerate((0,9,19)):
                image=Image.open(work/(name+'-'+str(index)+'.png')).resize((320,192));sheet.paste(image,(320*col,212*row+20));draw.text((320*col+8,212*row+3),name+' frame '+str(index),fill='white')
        sheet.save(out/'actual-MP4-frames-0-9-19.png');write(evidence/'visual-review-pending.json',{'prepared':True,'viewed':False,'continuous_playback_reviewed':False,'audio_reviewed':False})
        check('frozen implementation unchanged during real media execution',frozen()==before)
        if args.reference:
            previous=json.loads(Path(args.reference).read_bytes());name=next(k for k in previous['assets'] if k.endswith('/timeline.rgba-f32le'))
            check('fresh runtime reproduces every development Float32 pixel byte',sha(raw)==previous['assets'][name])
        origins={n:str(Path(m.__file__).resolve()) for n,m in sys.modules.items() if getattr(m,'__file__',None) and
            (n=='ai_ad_editor' or n.startswith('ai_ad_editor.') or n=='numpy' or n.startswith('numpy.') or n=='PIL' or n.startswith('PIL.'))}
        if INSTALLED:check('all actual media modules originate in fresh isolated installation',bool(origins) and all(Path(v).is_relative_to(INSTALLED/'site') for v in origins.values()))
        record.update(status='passed-real-media-float-author-host-not-default-renderer',finished_at_utc=datetime.now(timezone.utc).isoformat(),frozen_after=frozen(),
            installed_runtime_origins=origins if INSTALLED else None,isolated_python=bool(sys.flags.isolated and sys.flags.no_site),
            copied_bundle_files=copied,assets={str(v.relative_to(ROOT)).replace('\\','/'):sha(v) for v in sorted(out.rglob('*')) if v.is_file()},
            actual_subprocesses=len(calls),executed_author_frames=20,continuous_playback_reviewed=False,audio_generated=False,HDR_accepted=False)
    except BaseException as exc:record.update(status='failed-preserved',error=repr(exc),finished_at_utc=datetime.now(timezone.utc).isoformat());raise
    finally:
        save();(evidence/'executed-script.py.txt').write_bytes(Path(__file__).read_bytes());print(json.dumps({k:record.get(k) for k in ('status','error','actual_subprocesses','executed_author_frames','maximum_full_frame_reference_error')}),flush=True)

if __name__=='__main__':main()
