"""Actual complete-output retime with original frame/PCM clocks and separately authored audio references."""
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

    def compose(path,name,operations,expected=0):
        q=public/(name+'-compose.json');save(q,{'operations':operations})
        return cli('timeline','compose','--project',path,'--input',q,expected=expected)

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
            'editing':{'main_track_id':'shots','magnetic':True},'tracks':[
                track('shots','video',[clip(c,i*TPS,source=(i+1)*TPS) for i,c in enumerate('abcd')]),
                track('stem','audio',[clip('music',0,'sound',duration=4*TPS)])]}]
        author(base,p)

        def make(name):
            path=work/name;shutil.copytree(base,path)
            return path,copy.deepcopy(p)

        def retime(path,name,transform,ids=('b',),**options):
            return edit(path,name,{'action':'retime','clip_ids':list(ids),'transform':transform,**options})

        def join(*arrays):return np.concatenate(arrays)
        def chunk(array,a,b,rate):return array[round(a*rate):round(b*rate)]
        v=lambda a,b:chunk(source,a,b,FPS)
        a=lambda x,y:chunk(signal,x,y,SR)
        def native_tempo(name,original,speed,expected_samples):
            raw=native('-f','f32le','-ar',SR,'-ac',2,'-i','pipe:0','-af','atempo='+str(speed),
                '-f','f32le','pipe:1',data=original.astype('<f4').tobytes())
            output=np.frombuffer(raw,dtype='<f4').reshape(-1,2)
            assert len(output)>=expected_samples,(name,len(output),expected_samples)
            selected=output[-expected_samples:]
            save(public/(name+'-native-tempo.json'),{'reference':'independent raw PCM through native FFmpeg atempo',
                'input_samples':len(original),'raw_output_samples':len(output),'retained_samples':expected_samples,
                'selection':[len(output)-expected_samples,len(output)],'alignment':'actual-retimed-source-end',
                'source_pcm_sha256':digest(original.astype('<f4').tobytes()),'raw_pcm_sha256':digest(raw),
                'selected_pcm_sha256':digest(selected.tobytes()),'natural_quality_accepted':False})
            return selected

        def audio_reference(name,transforms):
            # Independently author plain source/audio clips. This shares the native
            # renderer's DSP; it is not an independent natural-quality oracle.
            path,q=make(name+'-audio-reference');s=q['sequences'][0]
            s.pop('editing',None);s['tracks']=[];position=0;clips=[]
            for i,(duration,transform) in enumerate(transforms):
                clips.append(clip('ref_'+str(i),position,'sound',source=(i+1)*TPS,
                    duration=duration,**transform));clips[-1]['source_out_tick']=(i+2)*TPS
                position+=duration
            s['duration_tick']=position;s['tracks']=[track('ref_picture','video',[
                clip('reference_picture',0,duration=position,source=0)]),track('ref_audio','audio',clips,1)]
            author(path,q);out,_=render(path,name+'-audio-reference');return pcm(out)

        path,_=make('RT01');retime(path,'RT01',{'speed':2})
        record(path,'RT01',join(v(1,2),v(2,3)[::2],v(3,5)),join(a(1,2.5),a(3,5)),
            'independent original frames; original BGM PCM with ripple extraction, unchanged playback speed')

        path,_=make('RT02');retime(path,'RT02',{'speed':.5})
        record(path,'RT02',join(v(1,2),np.repeat(v(2,3),2,axis=0),v(3,5)),
            join(a(1,3),np.zeros((SR,2),dtype=np.float32),a(3,5)),
            'independent original frame repetition; original BGM PCM and explicit inserted silent gap')

        # One continuous stem/caption is linked to B and crosses both its edges.
        path,q=make('RT03');s=q['sequences'][0]
        s['tracks'][0]['clips'][1]['link_id']='pair'
        s['tracks'][1]['clips'][0]['link_id']='pair'
        s['tracks'].append(track('sub','subtitle',[clip('words',0,'captions',duration=4*TPS,source=0,
            link_id='pair',subtitle={'style':{'font_asset_id':'font','fontsize':64,'position':'center'}})],2))
        author(path,q);baseline,_=render(path,'RT03-before');caption=picture(baseline)
        retime(path,'RT03',{'reverse':True})
        record(path,'RT03',join(caption[:10],caption[10:20][::-1],caption[20:]),
            join(a(1,2),a(2,3)[::-1],a(3,5)),
            'same-renderer pre-edit glyph graph reversed after composition; independent original reversed PCM')

        path,q=make('RT04');s=q['sequences'][0]
        s['tracks'][0]['clips'][1]['link_id']='pair';s['tracks'][1]['clips'][0]['link_id']='pair'
        s['tracks'].append(track('sub','subtitle',[clip('words',0,'captions',duration=4*TPS,source=0,
            link_id='pair',subtitle={'style':{'font_asset_id':'font','fontsize':64,'position':'center'}})],2))
        author(path,q);baseline,_=render(path,'RT04-before');caption=picture(baseline)
        retime(path,'RT04',{'freeze':{'at_tick':TPS//2,'duration_tick':TPS*3//10,'audio_mode':'silence'}})
        record(path,'RT04',join(caption[:15],np.repeat(caption[14:15],3,axis=0),caption[15:]),
            join(a(1,2.5),np.zeros((SR*3//10,2),dtype=np.float32),a(2.5,5)),
            'same-renderer complete glyph hold frame; independent original PCM and exact silence at shared host clock')

        curve={'keyframes':[{'at_tick':0,'speed':1,'interpolation':'hold'},
            {'at_tick':TPS*6//10,'speed':2,'interpolation':'hold'}, {'at_tick':TPS,'speed':2}]}
        expected=audio_reference('RT05',[(TPS,{}),(TPS*8//10,{'speed_curve':curve}),(TPS,{}),(TPS,{})])
        path,_=make('RT05');retime(path,'RT05',{'speed_curve':curve},sync_content='retime')
        record(path,'RT05',join(v(1,2),v(2,2.6),v(2.6,3)[::2],v(3,5)),expected,
            'independent piecewise source-frame integral; separately authored plain audio tempo graph, shared native DSP')

        # An already curved/reversed/frozen spatially animated child with a
        # compressor bus is retimed as one complete visible author output.
        path,q=make('RT06');s=q['sequences'][0];s['tracks']=s['tracks'][:1]
        child={'id':'original_child','name':'original complete bus','duration_tick':TPS,
            'tracks':[track('inner_picture','video',[clip('inner_pixels',0,source=2*TPS)]),
                track('inner_audio','audio',[clip('inner_voice',0,'sound',source=2*TPS)],1)],
            'audio_routing':{'version':1,'tracks':[{'track_id':'inner_audio','output':'fx'}],
                'buses':[{'id':'fx','audio':{'compressor':{'threshold':.1,'ratio':3}},
                    'keyframes':[{'property':'audio.volume','keyframes':[{'at_tick':0,'value':.2},{'at_tick':TPS,'value':1}]}]}]}}
        s['tracks'][0]['clips'][1]={'id':'b','sequence_id':child['id'],'timeline_start_tick':TPS,
            'duration_tick':TPS,'source_in_tick':0,'source_out_tick':TPS,'speed_curve':curve,'reverse':True,
            'freeze':{'at_tick':TPS*4//10,'duration_tick':TPS*2//10,'audio_mode':'silence'},
            'audio':{'volume':.5,'fade_in':.1},
            'keyframes':[{'property':'opacity','keyframes':[{'at_tick':0,'value':.4,'interpolation':'linear'},
                {'at_tick':TPS,'value':1,'interpolation':'linear'}]}]}
        q['sequences'].append(child);author(path,q);baseline,_=render(path,'RT06-before')
        original_video=picture(baseline)
        # The audio reference consumes an actual completed pre-edit bus export,
        # not the newly generated retime author sequences.
        ref,refq=make('RT06-audio-reference')
        cli('media','ingest','--project',ref,'--input',baseline,'--asset-id','completed_bus',
            '--verification-status','verified','--permitted-use','commercial_ad','--license-spdx','CC0-1.0',
            '--source','local original complete author output','--creator','fixture author','--evidence',public/'source-provenance.json')
        refq=json.loads((ref/'project.json').read_bytes());rs=refq['sequences'][0];rs.pop('editing',None)
        rs['duration_tick']=TPS*7//2;rs['tracks']=[track('reference_picture','video',[
            clip('reference_pixels',0,duration=TPS*7//2,source=0)]),track('reference','audio',[
            {'id':'retimed_bus','asset_id':'completed_bus','timeline_start_tick':TPS,'duration_tick':TPS//2,
             'source_in_tick':TPS,'source_out_tick':2*TPS,'speed':2}],1)]
        author(ref,refq);out,_=render(ref,'RT06-audio-reference');legacy_head=pcm(out)
        processed=pcm(baseline)[SR:2*SR]
        expected=join(np.zeros((SR,2),dtype=np.float32),native_tempo('RT06',processed,2,SR//2),
            np.zeros((2*SR,2),dtype=np.float32))
        save(public/'RT06-legacy-head-comparison.json',{'accepted_reference':False,
            'reason':'ordinary constant file path selects the native head; complete bus contract aligns actual retimed source end',
            'max_pcm_difference':float(np.max(np.abs(legacy_head-expected))),
            'legacy_reference_sha256':digest(legacy_head.tobytes()),'end_aligned_reference_sha256':digest(expected.tobytes())})
        retime(path,'RT06',{'speed':2})
        record(path,'RT06',join(original_video[:10],original_video[10:20:2],original_video[20:]),expected,
            'same-renderer pre-edit full animated/curved/reverse/freeze/processed bus; raw native atempo with independently selected actual end')

        path,_=make('RT07');retime(path,'RT07-first',{'speed':2})
        compose(path,'RT07-second',[{'op':'retime_clip','clip_id':'b','transform':{'speed':.5}}])
        record(path,'RT07',join(v(1,2),np.repeat(v(2,3)[::2],2,axis=0),v(3,5)),
            join(a(1,2.5),np.zeros((SR//2,2),dtype=np.float32),a(3,5)),
            'independent current-output downsample then repeat; original BGM plus exact new gap, no source-speed reset')

        expected=join(a(1,2),native_tempo('RT08-B',a(2,3),2,SR//2),a(3,4),native_tempo('RT08-D',a(4,5),2,SR//2))
        path,_=make('RT08');retime(path,'RT08',{'speed':2},ids=('b','d'),sync_content='retime')
        record(path,'RT08',join(v(1,2),v(2,3)[::2],v(3,4),v(4,5)[::2]),expected,
            'independent original two-host frame clock; original PCM through native atempo with actual-end selection')

        from ai_ad_editor.clip_windows import slice_clip
        path,q=make('RT09');s=q['sequences'][0];shots=s['tracks'][0]['clips']
        shots[1]=slice_clip(clip('b',TPS,duration=TPS*9//10,source=2*TPS,
            speed=2,reverse=True,freeze={'at_tick':TPS//5,'duration_tick':TPS*4//10,'audio_mode':'silence'}),
            TPS//10,TPS*7//10,start=TPS)
        shots[1]['source_out_tick']=3*TPS
        shots[2]['timeline_start_tick']=TPS*16//10;shots[3]['timeline_start_tick']=TPS*26//10
        s['duration_tick']=TPS*36//10;s['tracks'][1]['clips'][0]['duration_tick']=TPS*36//10
        s['tracks'][1]['clips'][0]['source_out_tick']=TPS*46//10
        author(path,q);baseline,_=render(path,'RT09-before');original_video=picture(baseline)
        retime(path,'RT09',{'speed':2})
        record(path,'RT09',join(original_video[:10],original_video[10:16:2],original_video[16:]),
            join(a(1,2.3),a(2.6,4.6)),
            'same-renderer previously windowed reverse/freeze author; independent original BGM ripple PCM')

        # Negative transactions, actual dry run and stale basis, never overwrite
        # any earlier failure receipt. Main/linked layout remains byte-identical.
        path,_=make('RT-transaction');old=(path/'project.json').read_bytes()
        q=public/'dry-run.json';save(q,{'action':'retime','clip_ids':['b'],'transform':{'speed':2}})
        cli('timeline','edit','--project',path,'--input',q,'--dry-run');assert (path/'project.json').read_bytes()==old
        cli('timeline','edit','--project',path,'--input',q,'--expected-project-sha256','sha256:'+'0'*64,expected=2)
        assert (path/'project.json').read_bytes()==old
        compose(path,'atomic-failure',[{'op':'retime_clip','clip_id':'b','transform':{'speed':2}},
            {'op':'update_clip','clip_id':'c','patch':{'duration_tick':0}}],expected=2)
        assert (path/'project.json').read_bytes()==old

        restored=work/'restored';cli('convert','import','--input',public/'RT06.aevpkg.zip','--output',restored)
        out,_=render(restored,'RT06-restored')
        assert picture(out).tobytes()==picture(public/'RT06.mkv').tobytes()
        assert pcm(out).tobytes()==pcm(public/'RT06.mkv').tobytes()
        cli('policy','audit','--project',restored)
        contact=Image.new('RGB',(W*3,H*3),(30,30,30))
        for i,r in enumerate(records):
            image=Image.fromarray(picture(public/(r['name']+'.mkv'))[min(14,r['frames']-1)])
            contact.paste(image,((i%3)*W,(i//3)*H))
        contact.save(public/'contact-sheet.png')
        native('-i',public/'RT04.mp4','-vf','scale=480:192,fps=10','-an',public/'retime.gif')
        after=frozen();assert before==after
        record={'status':'passed_scoped_complete_output_retime','started_duration_seconds':time.monotonic()-start,
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
