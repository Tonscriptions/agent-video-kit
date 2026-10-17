"""Re-decode completed fixture outputs and verify clocks independently of plans."""
from __future__ import annotations
import argparse,hashlib,json,math,subprocess,zipfile
from pathlib import Path
import numpy as np
from PIL import Image

ROOT=Path(__file__).resolve().parents[1]
FPS,W,H,SR=10,240,136,48000
def digest(raw):return 'sha256:'+hashlib.sha256(raw).hexdigest()
def sha(p):return digest(p.read_bytes())
def save(p,v):p.write_text(json.dumps(v,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8',newline='\n')
def ff(args):return subprocess.check_output(['ffmpeg','-v','error',*map(str,args)])
def rgb(path):return np.frombuffer(ff(['-i',path,'-an','-pix_fmt','rgb24','-f','rawvideo','pipe:1']),np.uint8).reshape(-1,H,W,3)
def pcm(path):return np.frombuffer(ff(['-i',path,'-vn','-ar',SR,'-ac',2,'-f','f32le','pipe:1']),'<f4').reshape(-1,2)

def run(public,work,output):
    record=json.loads((public/'verification.json').read_text(encoding='utf-8'))
    assert record['frozen_equal'] and record['frozen_before']==record['frozen_after']
    for name,expected in record['frozen_after'].items():assert sha(ROOT/name)==expected,name
    for name,item in record['files'].items():assert sha(public/name)==item['sha256'],name
    calls=json.loads((public/'cli-calls.json').read_text(encoding='utf-8'))
    with zipfile.ZipFile(public/'cli-logs.zip') as archive:
        assert len(archive.namelist())==2*len(calls)
        for c in calls:
            for stream in ('stdout','stderr'):
                raw=archive.read(f'{c["index"]:03}.{stream}.log')
                assert digest(raw)==c[stream+'_sha256']
            assert c['exit_code']==c['expected_exit_code']
    source={s:rgb(public/f'source-{s}.mp4') for s in 'abc'}
    sounds={s:pcm(public/f'sound-{s}.wav') for s in 'abc'}
    direct=np.concatenate([source[s][20:40] for s in 'abc']).astype(float)
    for cut,left,right in ((20,'a','b'),(40,'b','c')):
        for frame in range(cut-5,cut+5):
            weight=(frame-(cut-5))/10
            direct[frame]=source[left][20+frame-(cut-20)]*(1-weight)+source[right][frame-(cut-20)]*weight
    def author_times(scenario,frames):
        t=np.arange(frames)/FPS
        if scenario=='partial':s=2.1+t
        elif scenario in ('reverse','grandparent'):s=5-t
        elif scenario=='double':s=1+2*t
        elif scenario in ('curve','curve-reverse','parent-opacity'):
            phase=4-t if scenario=='curve-reverse' else t
            s=1+2*np.expm1(math.log(3)*phase/4)
        elif scenario=='twice':s=t%6
        else:s=1+t
        ids=np.ceil(s*FPS-1e-6).astype(int)-1 if scenario in ('reverse','grandparent','curve-reverse') else np.floor(s*FPS+1e-6).astype(int)
        return t,ids
    def window(a,b,reverse):
        n=round((b-a)*SR);result=np.zeros((n,2),float)
        times=b-np.arange(n)/SR if reverse else a+np.arange(n)/SR
        for start,end,source_in,sid in ((0.,2.5,2.,'a'),(1.5,4.5,1.5,'b'),(3.5,6.,1.5,'c')):
            lo,hi=max(a,start),min(b,end)
            if lo>=hi:continue
            left,right=(round((b-hi)*SR),round((b-lo)*SR)) if reverse else (round((lo-a)*SR),round((hi-a)*SR))
            samples=sounds[sid][round((source_in+lo-start)*SR):round((source_in+hi-start)*SR)]
            if reverse:samples=samples[::-1]
            clock=times[left:right];gain=np.ones(right-left)
            if sid!='c':gain*=np.clip((2.5 if sid=='a' else 4.5)-clock,0,1)
            if sid!='a':gain*=np.clip(clock-(1.5 if sid=='b' else 3.5),0,1)
            result[left:right]+=samples*gain[:,None]
        return result
    child={};checks=[]
    for case in record['cases']:
        cid,kind,scenario=case['id'],case['transition_type'],case['scenario']
        path=work/cid/'renders'/(cid+'-actual.mkv');assert sha(path)==case['render']['sha256']
        frames=rgb(path);audio=pcm(path)
        assert digest(frames.tobytes())==case['rgb_sha256'] and digest(audio.tobytes())==case['pcm_sha256']
        preview=rgb(public/case['render']['preview']);assert np.array_equal(frames,preview)
        assert len(frames)==case['frames'] and len(audio)==case['sample_frames'] and np.isfinite(audio).all()
        if kind not in child:child[kind]=rgb(work/('reference-'+kind)/'renders'/('fixed-child-'+kind+'.mkv'))
        t,ids=author_times(scenario,len(frames));reference=child[kind][ids].astype(float)
        independent=direct[ids].copy() if kind in ('dissolve','crossfade') else None
        if scenario=='parent-opacity':
            factor=(.4+t*.1)[:,None,None,None];reference*=factor
            if independent is not None:independent*=factor
        if scenario=='child-alpha':
            reference=.5*reference+.5*source['a'][:len(t)]
            independent=.5*independent+.5*source['a'][:len(t)]
        error=float(np.abs(frames.astype(float)-reference).max());assert error<=4,(cid,error)
        analytic=float(np.abs(frames.astype(float)-independent).max()) if independent is not None else None
        assert analytic is None or analytic<=4,(cid,analytic)
        expected=None
        if scenario in ('trim','partial','reverse','grandparent','child-alpha','twice'):
            expected=np.concatenate([window(0,6,False)]*2) if scenario=='twice' else window(
                2.1 if scenario=='partial' else 1,4.1 if scenario=='partial' else 5,scenario in ('reverse','grandparent'))
        pcm_error=float(np.abs(audio.astype(float)-expected).max()) if expected is not None else None
        assert pcm_error is None or pcm_error<=3e-7,(cid,pcm_error)
        checks.append({'id':cid,'frames':len(frames),'sample_frames':len(audio),'preview_rgb_exact':True,
                       'fixed_child_rgb_max':error,'independent_rgb_max':analytic,'independent_pcm_max':pcm_error})
    video_streams=audio_streams=0;probes={}
    for path in sorted(public.iterdir()):
        if path.suffix.lower() not in ('.mp4','.mkv','.wav'):continue
        raw=subprocess.check_output(['ffprobe','-v','error','-count_frames','-show_streams','-show_format','-of','json',str(path)])
        value=json.loads(raw);probes[path.name]=value
        video_streams+=sum(s['codec_type']=='video' for s in value['streams']);audio_streams+=sum(s['codec_type']=='audio' for s in value['streams'])
        ff(['-i',path,'-f','null','-'])
    with Image.open(public/'comparison.gif') as image:
        gif={'frames':image.n_frames,'width':image.width,'height':image.height,
             'duration_ms':sum((image.seek(i) or image.info.get('duration',0)) for i in range(image.n_frames))}
    assert gif==record['gif'] and gif=={'frames':20,'width':720,'height':544,'duration_ms':4000}
    results={'status':'passed','public_files':len(record['files'])+1,'public_bytes':sum(p.stat().st_size for p in public.iterdir() if p.is_file()),
             'public_sha256':{p.name:{'bytes':p.stat().st_size,'sha256':sha(p)} for p in sorted(public.iterdir()) if p.is_file()},
             'new_frames':sum(c['frames'] for c in checks),'new_sample_frames':sum(c['sample_frames'] for c in checks),
             'checks':checks,'cli_count':len(calls),'cli_success':sum(c['exit_code']==0 for c in calls),
             'expected_rejections':sum(c['exit_code']!=0 for c in calls),'gif':gif,'probes':probes,
             'video_streams_redecoded':video_streams,'audio_streams_redecoded':audio_streams,
             'continuous_playback_reviewed':False,'audio_listened':False,
             'limits':record['limits']+['Four of six independent PCM checks use hash-verified local lossless work MKVs; only C01/C03 lossless MKVs are public. All MP4 preview video packets retain exact decoded RGB; AAC is not a PCM oracle.']}
    save(output,results)
    print(json.dumps({k:results[k] for k in ('status','public_files','public_bytes','new_frames','new_sample_frames',
                      'cli_count','cli_success','expected_rejections','gif','video_streams_redecoded','audio_streams_redecoded')},indent=2))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--public',type=Path,required=True);p.add_argument('--work',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();run(a.public.resolve(),a.work.resolve(),a.output.resolve())
