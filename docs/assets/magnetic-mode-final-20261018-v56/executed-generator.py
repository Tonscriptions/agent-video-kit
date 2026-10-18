"""Actual local CLI magnet edits with original PCM/frame and whole-author references."""
from __future__ import annotations
import argparse
import contextlib
import copy
from datetime import datetime, timezone
import hashlib
import io
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
import wave

from run_frozen_regression import frozen

ROOT=Path(__file__).resolve().parents[1]
TPS,SR,FPS,W,H=90000,48000,10,160,64


def digest(raw):return 'sha256:'+hashlib.sha256(raw).hexdigest()
def sha(path):return digest(path.read_bytes())
def save(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8',newline='\n')


def run(work,public):
    import numpy as np
    from PIL import Image,ImageDraw
    work.mkdir(parents=True,exist_ok=False);public.mkdir(parents=True,exist_ok=False)
    (public/'executed-generator.py').write_bytes(Path(__file__).read_bytes())
    os.environ.update(TEMP=str(work),TMP=str(work),TMPDIR=str(work),PYTHONDONTWRITEBYTECODE='1')
    sys.path.insert(0,str(ROOT/'product/src'))
    from ai_ad_editor.cli import main
    from ai_ad_editor.project import save_project
    from ai_ad_editor.runtime import configure_local_runtime
    configure_local_runtime();before=frozen();calls=[];records=[];start=time.monotonic()

    def cli(*args,expected=0):
        output=io.StringIO()
        with contextlib.redirect_stdout(output):code=main(list(map(str,args)))
        result=json.loads(output.getvalue());name=f'cli/{len(calls)+1:03}.json';save(public/name,result)
        calls.append({'arguments':list(map(str,args)),'exit_code':code,'expected_exit_code':expected,
                      'result':name,'result_sha256':sha(public/name)})
        save(public/'calls.json',calls)
        assert code==expected,(args,result)
        return result

    def native(*args,data=None):
        result=subprocess.run(['ffmpeg','-v','error','-y',*map(str,args)],input=data,capture_output=True,timeout=180)
        assert result.returncode==0,result.stderr.decode('utf-8','replace')
        return result.stdout

    def picture(path):
        return np.frombuffer(native('-i',path,'-map','0:v:0','-an','-fps_mode','passthrough','-pix_fmt','rgb24','-f','rawvideo','pipe:1'),dtype=np.uint8).reshape(-1,H,W,3)

    def pcm(path):
        return np.frombuffer(native('-i',path,'-map','0:a:0','-vn','-ar',SR,'-ac',2,'-f','f32le','pipe:1'),dtype='<f4').reshape(-1,2)

    def clip(cid,at,aid='frames',duration=TPS,source=TPS,**fields):
        return {'id':cid,'asset_id':aid,'timeline_start_tick':at,'duration_tick':duration,
                'source_in_tick':source,'source_out_tick':source+duration,**fields}

    def track(tid,kind,clips,order=0,**fields):return {'id':tid,'kind':kind,'order':order,'clips':clips,**fields}

    def author(path,p):
        save_project(path,p);cli('validate','--project',path,'--strict-rights')

    def edit(path,name,request):
        q=public/(name+'-edit.json');save(q,request)
        return cli('timeline','edit','--project',path,'--input',q)

    def compose(path,name,operations):
        q=public/(name+'-compose.json');save(q,{'operations':operations})
        return cli('timeline','compose','--project',path,'--input',q)

    def render(path,name):
        target=path/'renders'/(name+'.mkv')
        result=cli('render','--project',path,'--output',target,'--container','mkv','--audio-codec','pcm_f32le',
                   '--pixel-format','yuv444p','--crf','0','--publish')
        shutil.copyfile(target,public/target.name)
        manifest=Path(result['data']['manifest'])
        shutil.copyfile(manifest,public/(name+'.manifest.json'))
        return target,result

    def record(path,name,expected_video,expected_audio,scope):
        target,result=render(path,name);video,audio=picture(target),pcm(target)
        assert video.shape==expected_video.shape,(name,video.shape,expected_video.shape)
        assert audio.shape==expected_audio.shape,(name,audio.shape,expected_audio.shape)
        pixel=int(np.max(np.abs(video.astype(np.int16)-expected_video.astype(np.int16))))
        error=float(np.max(np.abs(audio-expected_audio)))
        assert pixel<=2,(name,'pixels',pixel)
        assert error<=2e-6,(name,'PCM',error)
        native('-i',target,'-c:v','libx264','-crf',16,'-pix_fmt','yuv420p','-c:a','aac',public/(name+'.mp4'))
        frames=video.shape[0]
        probe=json.loads(subprocess.check_output(['ffprobe','-v','error','-show_streams','-show_format','-of','json',str(target)]))
        save(public/(name+'-probe.json'),probe)
        v=next(s for s in probe['streams'] if s['codec_type']=='video')
        assert v['avg_frame_rate']=='10/1'
        cli('policy','audit','--project',path)
        cli('convert','export','--project',path,'--target-format','package','--output',public/(name+'.aevpkg.zip'))
        row={'name':name,'scope':scope,'frames':frames,'stereo_sample_frames':len(audio),'max_rgb_error':pixel,
             'max_pcm_error':error,'source_reference_sha256':digest(expected_video.tobytes()),
             'pcm_reference_sha256':digest(expected_audio.tobytes()),'decoded_rgb_sha256':digest(video.tobytes()),
             'decoded_pcm_sha256':digest(audio.tobytes()),'output_sha256':sha(public/target.name)}
        records.append(row);save(public/'cases.json',records)
        return video,audio

    try:
        frames=[]
        for n in range(60):
            im=Image.new('RGB',(W,H),(n*4,)*3);d=ImageDraw.Draw(im)
            for bit in range(6):
                c=255 if n & (1<<bit) else 0;d.rectangle((bit*22,0,bit*22+17,20),fill=(c,)*3)
            d.text((6,35),f'ORIGINAL FRAME {n:02}',fill=(255,)*3,stroke_width=0)
            frames.append(np.asarray(im))
        source=np.stack(frames)
        native('-f','rawvideo','-pix_fmt','rgb24','-s',f'{W}x{H}','-r',FPS,'-i','pipe:0','-an','-c:v','ffv1','-pix_fmt','bgr0',public/'source.mkv',data=source.tobytes())
        source=picture(public/'source.mkv')
        samples=np.arange(6*SR,dtype=np.float64);freq=200+100*(samples//SR)
        raw=np.stack((np.rint(6000*np.sin(2*math.pi*freq*samples/SR)),np.rint(5000*np.cos(2*math.pi*(freq+70)*samples/SR))),axis=1).astype('<i2')
        with wave.open(str(public/'source.wav'),'wb') as f:f.setnchannels(2);f.setsampwidth(2);f.setframerate(SR);f.writeframes(raw.tobytes())
        signal=raw.astype(np.float32)/32768
        for name in ('DejaVuSans.ttf','LICENSE_DEJAVU'):
            shutil.copyfile(ROOT/'docs/assets/magnetic-reorder-v53-r5-20261018'/name,public/name)
        (public/'captions.srt').write_text('1\n00:00:00,000 --> 00:00:01,000\nONE\n\n2\n00:00:01,000 --> 00:00:02,000\nTWO\n\n3\n00:00:02,000 --> 00:00:03,000\nTHREE\n\n4\n00:00:03,000 --> 00:00:04,000\nFOUR\n',encoding='utf-8',newline='\n')
        save(public/'source-provenance.json',{'procedural_frames_audio_and_subtitles_license':'CC0-1.0',
             'source_video':sha(public/'source.mkv'),'source_audio':sha(public/'source.wav'),
             'font':{'sha256':sha(public/'DejaVuSans.ttf'),'license':'Bitstream-Vera','notice':'LICENSE_DEJAVU',
                     'copied_unmodified_from':'docs/assets/magnetic-reorder-v53-r5-20261018/DejaVuSans.ttf'},
             'video':{'frames':60,'fps':FPS,'width':W,'height':H},'audio':{'stereo_sample_frames':6*SR,'sample_rate':SR,'bits':16}})
        native('-i',public/'source.mkv','-i',public/'source.wav','-c:v','libx264','-crf',16,'-pix_fmt','yuv420p','-c:a','aac',public/'source-preview.mp4')
        base=work/'base';cli('project','init',base)
        for name,aid,license in [('source.mkv','frames','CC0-1.0'),('source.wav','sound','CC0-1.0'),('captions.srt','captions','CC0-1.0'),('DejaVuSans.ttf','font','Bitstream-Vera')]:
            cli('media','ingest','--project',base,'--input',public/name,'--asset-id',aid,'--verification-status','verified',
                '--permitted-use','commercial_ad','--license-spdx',license,'--source','local authored fixture or unmodified licensed font',
                '--creator','fixture authors or DejaVu/Bitstream authors','--evidence',public/('LICENSE_DEJAVU' if aid=='font' else 'source-provenance.json'))
        p=json.loads((base/'project.json').read_bytes());sid=p['sequences'][0]['id']
        p['settings']['canvas'].update(width=W,height=H);p['settings']['timebase']['display_fps']={'num':FPS,'den':1}
        p['sequences']=[{'id':sid,'name':'four main shots and complete stem','duration_tick':4*TPS,
            'editing':{'main_track_id':'shots'},'tracks':[
                track('shots','video',[clip(c,i*TPS,source=(i+1)*TPS) for i,c in enumerate('abcd')]),
                track('stem','audio',[clip('music',0,'sound',duration=4*TPS)])]}]
        author(base,p)

        def make(name):
            path=work/name;shutil.copytree(base,path)
            return path,copy.deepcopy(p)

        def enable(path,name):edit(path,name+'-enable',{'action':'magnet','enabled':True})
        def parts(arr,spans,rate):return np.concatenate([arr[round(a*rate):round(b*rate)] for a,b in spans])
        reordered=[(3,4),(1,2),(2,3),(4,5)]
        path,_=make('MM01');enable(path,'MM01')
        edit(path,'MM01',{'action':'shift','clip_ids':['c'],'delta_tick':-2*TPS})
        record(path,'MM01',parts(source,reordered,FPS),parts(signal,reordered,SR),'independent original frame and PCM permutation')
        path,_=make('MM02');enable(path,'MM02');compose(path,'MM02',[{'op':'remove_clip','clip_id':'b'}])
        record(path,'MM02',parts(source,[(1,2),(3,5)],FPS),parts(signal,[(1,2),(3,5)],SR),'independent original removal and source PCM slices')
        path,_=make('MM03');enable(path,'MM03');incoming=clip('e',round(1.3*TPS),source=0)
        compose(path,'MM03',[{'op':'append_clip','track_id':'shots',**incoming}])
        record(path,'MM03',parts(source,[(1,2),(0,1),(2,5)],FPS),np.concatenate((signal[SR:2*SR],np.zeros((SR,2),dtype=np.float32),signal[2*SR:5*SR])),
               'independent original insert plus exact silent stem interval')
        path,_=make('MM04');enable(path,'MM04')
        compose(path,'MM04',[{'op':'trim_clip','clip_id':'b','start_tick':TPS//5,'end_tick':TPS*4//5}])
        record(path,'MM04',parts(source,[(1,2),(2.2,2.8),(3,5)],FPS),parts(signal,[(1,2),(2.2,2.8),(3,5)],SR),'independent original head and tail extraction')
        path,q=make('MM05');root=q['sequences'][0]
        child={'id':'child','name':'processed child','duration_tick':4*TPS,'tracks':[
            track('child_audio','audio',[clip('child_voice',0,'sound',duration=4*TPS)])],
            'audio_routing':{'version':1,'tracks':[{'track_id':'child_audio','output':'fx'}],
                'buses':[{'id':'fx','audio':{'compressor':{'threshold':.1,'ratio':3}},
                    'keyframes':[{'property':'audio.volume','keyframes':[{'at_tick':0,'value':.2},{'at_tick':4*TPS,'value':1}]}]}]}}
        root['tracks'][1]['clips']=[{'id':'compound_stem','sequence_id':'child','timeline_start_tick':0,'duration_tick':4*TPS,
            'source_in_tick':0,'source_out_tick':4*TPS,'reverse':True,'audio':{'volume':.5,'fade_in':.1}}]
        q['sequences'].append(child);author(path,q);baseline,_=render(path,'MM05-before');baseline_audio=pcm(baseline)
        enable(path,'MM05');edit(path,'MM05',{'action':'shift','clip_ids':['c'],'delta_tick':-2*TPS})
        record(path,'MM05',parts(source,reordered,FPS),parts(baseline_audio,[(2,3),(0,1),(1,2),(3,4)],SR),
               'independent original picture; same-renderer complete pre-edit nested reverse bus reference')
        path,q=make('MM06');root=q['sequences'][0]
        root['tracks'][1]['clips'][0]['link_id']='caption_stem'
        root['tracks'].append(track('sub','subtitle',[clip('words',0,'captions',duration=4*TPS,source=0,
            link_id='caption_stem',subtitle={'style':{'font_asset_id':'font','font_size':18,'position':'center'}})],2))
        author(path,q);baseline,_=render(path,'MM06-before');baseline_video=picture(baseline)
        enable(path,'MM06');edit(path,'MM06',{'action':'shift','clip_ids':['c'],'delta_tick':-2*TPS})
        record(path,'MM06',parts(baseline_video,[(2,3),(0,1),(1,2),(3,4)],FPS),parts(signal,reordered,SR),
               'same-renderer complete subtitle glyph clock; independent original source PCM')
        # A restored editable package is rendered again; it is not another source oracle.
        restored=work/'restored';cli('convert','import','--input',public/'MM05.aevpkg.zip','--output',restored)
        out,_=render(restored,'MM05-restored')
        assert picture(out).tobytes()==picture(public/'MM05.mkv').tobytes()
        assert pcm(out).tobytes()==pcm(public/'MM05.mkv').tobytes()
        cli('policy','audit','--project',restored)
        # Expected atomic refusal retains all authored/project bytes.
        old=(path/'project.json').read_bytes()
        compose_path=public/'expected-invalid-geometry.json';save(compose_path,{'operations':[{'op':'update_clip','clip_id':'a','patch':{'duration_tick':TPS//2}}]})
        cli('timeline','compose','--project',path,'--input',compose_path,expected=2)
        assert (path/'project.json').read_bytes()==old
        # Actual encoded contact and short silent GIF, sampled from final outputs.
        contact=Image.new('RGB',(W*3,H*2),(30,30,30))
        for i,r in enumerate(records):
            image=Image.fromarray(picture(public/(r['name']+'.mkv'))[0]);contact.paste(image,((i%3)*W,(i//3)*H))
        contact.save(public/'contact-sheet.png')
        native('-i',public/'MM01.mp4','-vf','scale=480:192,fps=10','-an',public/'magnetic-mode.gif')
        after=frozen();assert before==after
        record={'status':'passed_scoped_magnetic_mode','started_duration_seconds':time.monotonic()-start,
            'checked_at_utc':datetime.now(timezone.utc).isoformat(),'frozen_before':before,'frozen_after':after,
            'cases':records,'cli_calls':calls,'native_package_roundtrip':True,
            'main_frames':sum(r['frames'] for r in records),'stereo_sample_frames':sum(r['stereo_sample_frames'] for r in records),
            'rgb_threshold':2,'pcm_threshold':2e-6,'continuous_playback':False,'human_listening':False,'full_capcut_parity':False,
            'files':[{'path':f.relative_to(public).as_posix(),'bytes':f.stat().st_size,'sha256':sha(f)} for f in sorted(public.rglob('*')) if f.is_file()]}
        save(public/'verification.json',record)
        print(json.dumps({k:record[k] for k in ('status','main_frames','stereo_sample_frames')},ensure_ascii=False))
    except BaseException as exc:
        save(public/'failure.json',{'error':repr(exc),'calls':calls,'completed_cases':records,'source_freeze':before})
        raise


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--work',type=Path,required=True);p.add_argument('--public',type=Path,required=True)
    a=p.parse_args();run(a.work.resolve(),a.public.resolve())
