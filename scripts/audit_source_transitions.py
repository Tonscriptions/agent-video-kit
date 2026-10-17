"""Independently re-decode source-transition videos and PCM evidence."""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import zipfile


def sha(p):return 'sha256:'+hashlib.sha256(p.read_bytes()).hexdigest()
def digest(raw):return 'sha256:'+hashlib.sha256(raw).hexdigest()
def load(p):return json.loads(p.read_text(encoding='utf-8'))


def run(folder, local_work, report):
    import numpy as np
    from PIL import Image
    record=load(folder/'verification.json')
    assert record['frozen_before']==record['frozen_after']
    for name, item in record['files'].items():
        path=(folder/name).resolve()
        assert path.is_relative_to(folder.resolve())
        assert path.stat().st_size==item['bytes'] and sha(path)==item['sha256'],name
    def ff(path, audio=False):
        args=['ffmpeg','-v','error','-i',str(path)]
        args+=['-vn','-ar','48000','-ac','2','-f','f32le'] if audio else ['-an','-pix_fmt','rgb24','-f','rawvideo']
        return subprocess.check_output([*args,'pipe:1'])
    frames, audio, media={}, {}, {}
    for path in sorted(folder.iterdir()):
        if path.suffix not in {'.mp4','.mkv','.wav'}:continue
        probe=json.loads(subprocess.check_output(['ffprobe','-v','error','-show_streams','-show_format','-of','json',str(path)]))
        v=next((s for s in probe['streams'] if s['codec_type']=='video'),None)
        a=next((s for s in probe['streams'] if s['codec_type']=='audio'),None)
        meta={'sha256':sha(path),'bytes':path.stat().st_size}
        if v:
            raw=ff(path)
            array=np.frombuffer(raw,np.uint8).reshape(-1,int(v['height']),int(v['width']),3)
            expected=80 if path.name.startswith('source-') else 60
            assert len(array)==expected and v['avg_frame_rate']=='10/1',path
            frames[path.name]=array
            meta['video']={'frames':len(array),'width':v['width'],'height':v['height'],'fps':v['avg_frame_rate'],'rgb_sha256':digest(raw)}
        if a:
            raw=ff(path,True);array=np.frombuffer(raw,'<f4').reshape(-1,2)
            assert np.isfinite(array).all()
            audio[path.name]=array
            meta['audio']={'sample_frames':len(array),'sample_rate':48000,'channels':2,'pcm_sha256':digest(raw),'peak':float(np.abs(array).max())}
        media[path.name]=meta
    video_sources={sid:frames[f'source-{sid}.mp4'] for sid in ('a','b','c')}
    audio_sources={sid:audio[f'sound-{sid}.wav'] for sid in ('a','b','c')}
    pixels, samples=[],[]
    for case in record['cases']:
        cid=case['id'];preview=cid+'-actual.mp4'
        assert digest(frames[preview].tobytes())==case['decoded_rgb_sha256'],cid
        # Recompute every float render from source WAVs when local originals
        # exist. Two lossless examples are also public and checked identically.
        public=folder/(cid+'-actual.mkv')
        if public.is_file():
            actual=audio[public.name]
            assert digest(frames[public.name].tobytes())==case['decoded_rgb_sha256']
        elif local_work:
            path=Path(case['render']['local_mkv']).resolve()
            assert path.is_relative_to(local_work.resolve()) and sha(path)==case['render']['sha256']
            actual=np.frombuffer(ff(path,True),'<f4').reshape(-1,2)
        else:actual=None
        windows=[]
        if cid!='C06':
            seconds=.6 if cid=='C02' else 1
            windows=[(2-seconds/2,2+seconds/2)]
            if cid=='C01':windows.append((3.5,4.5))
        if actual is not None:
            assert digest(actual.tobytes())==case['decoded_pcm_sha256'] and len(actual)==288000
            ref=np.concatenate([audio_sources[s][96000:192000] for s in ('a','b','c')]).copy()
            for i,(a,b) in enumerate(windows if cid!='C04' else []):
                start,end=round(a*48000),round(b*48000)
                n=np.arange(end-start);gain=n/(end-start)
                left,right=('a','b') if i==0 else ('b','c')
                source_left=round((4-(b-a)/2)*48000)
                source_right=round((2-(b-a)/2)*48000)
                ref[start:end]=audio_sources[left][source_left+n]*(1-gain[:,None])+audio_sources[right][source_right+n]*gain[:,None]
            error=float(np.abs(actual-ref).max());assert error<=3e-7,(cid,error)
            samples.append({'id':cid,'sample_frames':len(actual),'independent_max_error':error,'public_lossless':public.is_file()})
        if cid in {'C01','C03','C04','C08'}:
            ref=np.concatenate([video_sources[s][20:40] for s in ('a','b','c')]).astype(float)
            if cid=='C04':
                ref[:20]=video_sources['a'][np.arange(59,19,-2)]
                ref[20:40]=video_sources['b'][np.arange(59,19,-2)]
            for i,(a,b) in enumerate(windows):
                left,right=('a','b') if i==0 else ('b','c')
                for k in range(round(a*10),round(b*10)):
                    n=k-(0 if i==0 else 20);gain=(k/10-a)/(b-a)
                    la,rb=(59-2*n,99-2*n) if cid=='C04' else (20+n,n)
                    if cid in {'C03','C08'}:
                        color=255 if cid=='C03' else 0
                        if gain<=.5:ref[k]=video_sources[left][la]*(1-2*gain)+color*2*gain
                        else:ref[k]=color*(2-2*gain)+video_sources[right][rb]*(2*gain-1)
                    else:ref[k]=video_sources[left][la]*(1-gain)+video_sources[right][rb]*gain
            error=float(np.abs(frames[preview].astype(float)-ref).max());assert error<=3,(cid,error)
            pixels.append({'id':cid,'frames':len(ref),'independent_max_rgb_error':error})
        if cid=='C06':
            assert np.array_equal(frames[preview],frames['authored-input.mp4'])
    calls=load(folder/'cli-calls.json')
    with zipfile.ZipFile(folder/'cli-logs.zip') as z:
        assert len(z.namelist())==2*len(calls)
        for call in calls:
            for suffix,key in (('stdout','stdout_sha256'),('stderr','stderr_sha256')):
                assert digest(z.read(f'{call["index"]:03}.{suffix}.log'))==call[key]
            assert call['exit_code']==call['expected_exit_code']
    with Image.open(folder/'comparison.gif') as gif:
        value={'frames':gif.n_frames,'width':gif.width,'height':gif.height,
               'duration_ms':sum((gif.seek(i) or gif.info.get('duration',0)) for i in range(gif.n_frames))}
    assert value==record['gif']
    actual_types={load(folder/(c['id']+'-project.json'))['sequences'][0].get('source_transitions',[{}])[0].get('type')
                  for c in record['cases'] if c['id']!='C06'}
    assert actual_types=={'dissolve','crossfade','dip_black','dip_white','wipe_left','wipe_right','wipe_up','wipe_down',
                          'slide_left','slide_right','slide_up','slide_down'}
    result={'at_utc':datetime.now(timezone.utc).isoformat(),'generator_sha256':sha(Path(__file__)),
            'all_published_file_hashes_match':True,'public_file_count':len(record['files'])+1,
            'public_bytes':sum(p.stat().st_size for p in folder.iterdir() if p.is_file()),
            'video_files':len(frames),'audio_streams':len(audio),'media':media,'gif':value,
            'independent_pixel_cases':pixels,'independent_pcm_cases':samples,'tested_types':sorted(actual_types),
            'cli_logs_verified':len(calls),'audio_listened':False,'continuous_playback_reviewed':False}
    report.parent.mkdir(parents=True,exist_ok=True)
    save_text=json.dumps(result,ensure_ascii=False,indent=2)+'\n'
    report.write_text(save_text,encoding='utf-8')
    print(json.dumps({k:v for k,v in result.items() if k not in {'media','independent_pcm_cases'}},ensure_ascii=False,indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--input',type=Path,required=True);p.add_argument('--local-work',type=Path)
    p.add_argument('--report',type=Path,required=True);a=p.parse_args();run(a.input.resolve(),a.local_work,a.report.resolve())
