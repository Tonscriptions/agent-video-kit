"""Exercise registered HDemucs on local speech and a deterministic music fixture."""
from __future__ import annotations

import argparse
import contextlib
import io
import json
import math
import subprocess
import sys
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'product/src'))
from ai_ad_editor.cli import main as cli_main
from ai_ad_editor.runtime import configure_local_runtime
from ai_ad_editor.utils import atomic_write_json,sha256_file


def main() -> int:
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('source','model','python','evidence','output-root'):
        parser.add_argument('--'+name,required=True)
    parser.add_argument('--devices',nargs='+',choices=['cpu','cuda'],default=['cpu'])
    parser.add_argument('--segment-seconds',type=float,default=4)
    args=parser.parse_args();configure_local_runtime()
    import numpy as np
    root=Path(args.output_root).resolve()
    if root.exists():parser.error('output-root must be new')
    root.mkdir(parents=True)
    def decode(file):
        result=subprocess.run(['ffmpeg','-nostdin','-hide_banner','-loglevel','error','-i',str(file),'-ar','44100','-ac','2','-f','f32le','pipe:1'],capture_output=True,check=True,timeout=120)
        return np.frombuffer(result.stdout,dtype='<f4').reshape(-1,2).copy()
    def encode(file,data):
        subprocess.run(['ffmpeg','-nostdin','-hide_banner','-loglevel','error','-f','f32le','-ar','44100','-ac','2','-i','pipe:0','-c:a','pcm_f32le',str(file)],input=np.asarray(data,dtype='<f4').tobytes(),capture_output=True,check=True,timeout=120)
    clean=decode(Path(args.source).resolve())
    count=len(clean);seconds=count/44100;t=np.arange(count)/44100
    music=np.zeros((count,2),dtype=np.float64)
    for channel in range(2):
        for frequency in (164.81,220,261.63,329.63,392):
            music[:,channel]+=.1*np.sin(2*np.pi*frequency*t+channel*.25)*(1+.2*np.sin(2*np.pi*.75*t))
        music[:,channel]+=.12*np.sin(2*np.pi*82.405*t)
    rng=np.random.default_rng(771)
    for at in np.arange(0,seconds,.5):
        start=round(at*44100);length=min(count-start,round(.15*44100))
        noise=rng.normal(0,1,length)*np.exp(-np.arange(length)/(44100*.025))
        music[start:start+length]+=.3*noise[:,None]
    music*=np.sqrt(np.mean(clean.astype(np.float64)**2))/max(1e-8,np.sqrt(np.mean(music**2)))
    gain=.9/max(1,float(np.abs(clean+music).max()))
    clean*=gain;music*=gain;mixture=np.asarray(clean+music,dtype=np.float32)
    encode(root/'mixture.wav',mixture);encode(root/'reference-vocals.wav',clean);encode(root/'reference-accompaniment.wav',music)
    checks=[]
    def invoke(*argv,expected=0):
        output=io.StringIO()
        with contextlib.redirect_stdout(output):code=cli_main(list(argv))
        value=json.loads(output.getvalue())
        checks.append({'command':value['command'],'status':value['status'],'exit_code':code})
        print(json.dumps(checks[-1]),flush=True)
        if code!=expected:raise RuntimeError(output.getvalue())
        return value
    def si_sdr(reference,estimate):
        ref=reference.astype(np.float64).reshape(-1);est=estimate.astype(np.float64).reshape(-1)
        ref-=ref.mean();est-=est.mean()
        projection=ref*(float(ref@est)/max(1e-15,float(ref@ref)))
        return 10*math.log10(max(1e-15,float(projection@projection))/max(1e-15,float((est-projection)@(est-projection))))
    project=root/'project';invoke('project','init',str(project))
    asset=invoke('media','ingest','--project',str(project),'--input',str(root/'mixture.wav'))['data']['asset']['id']
    results=[]
    for device in args.devices:
        adapter_id='hdemucs_'+device
        register=['audio','adapter','register','--project',str(project),'--adapter-id',adapter_id,'--engine','torchaudio-hdemucs-local-v1','--model-path',str(Path(args.model).resolve()),'--executable',str(Path(args.python).resolve()),'--evidence',str(Path(args.evidence).resolve()),'--device',device,'--threads','4','--segment-seconds',str(args.segment_seconds),'--overlap','0.25']
        invoke(*register,'--dry-run');invoke(*register)
        invoke('audio','adapter','inspect','--project',str(project),'--adapter-id',adapter_id)
        command=['audio','separate','--project',str(project),'--asset-id',asset,'--adapter-id',adapter_id,'--vocals-asset-id','vocals_'+device,'--accompaniment-asset-id','accompaniment_'+device,'--track-id','track_audio_1','--stem','vocals','--apply','--replace-track','--sample-rate','44100']
        invoke(*command,'--dry-run');value=invoke(*command)
        output=value['data']['assets'];vocals=decode(project/output['vocals']['uri']);acc=decode(project/output['accompaniment']['uri'])
        assert vocals.shape==acc.shape==mixture.shape
        error=float(np.max(np.abs(vocals+acc-mixture)))
        assert error<1e-5,error
        baseline=si_sdr(clean,mixture);score=si_sdr(clean,vocals)
        assert score-baseline > 3, ('Controlled fixture vocal improvement below 3 dB', score-baseline)
        separation=value['data']['separation']
        results.append({'device':device,'samples':count,'seconds':seconds,'vocal_si_sdr_db':score,'mixture_si_sdr_db':baseline,'improvement_db':score-baseline,'mixture_max_abs_error':error,'output_sha256':{k:v['sha256'] for k,v in output.items()},'worker':separation['worker'],'report':Path(value['data']['report']).relative_to(root).as_posix()})
        print(json.dumps({'device':device,'improvement_db':score-baseline,'mixture_error':error}),flush=True)
    change=project/'cache/title.json'
    atomic_write_json(change,{'operations':[{'op':'add_track','track_id':'titles','kind':'subtitle','order':3},{'op':'append_clip','track_id':'titles','id':'title','generator':{'type':'text'},'source_in_tick':0,'source_out_tick':round(seconds*90000),'subtitle':{'text':'Local HDemucs vocal separation','style':{'fontsize':22,'x':'(w-text_w)/2','y':'(h-text_h)/2'}}}]})
    invoke('timeline','compose','--project',str(project),'--input',str(change))
    output=project/'renders/vocals.mp4'
    rendered=invoke('render','--project',str(project),'--output',str(output),'--profile','custom','--width','640','--height','360')
    invoke('quality','check','--project',str(project),'--input',str(output),'--width','640','--height','360','--require-audio')
    invoke('validate','--project',str(project));invoke('policy','audit','--project',str(project))
    rights=invoke('rights','check','--project',str(project),expected=7)
    atomic_write_json(root/'summary.json',{'checks':checks,'fixture':{'kind':'local Chinese speech plus deterministic equal-RMS synthetic chord/bass/percussion','source_sha256':'sha256:'+sha256_file(Path(args.source)),'mixture_sha256':'sha256:'+sha256_file(root/'mixture.wav'),'samples':count,'sample_rate':44100,'music_seed':771},'results':results,'render_sha256':'sha256:'+sha256_file(output),'render_manifest_sha256':'sha256:'+sha256_file(Path(rendered['data']['manifest'])),'rights_expected_exit':7,'rights_check':rights['data'],'runtime_network':'disabled','runtime_downloads':False,'docker_or_wsl_started':False,'browser_started':False})
    print(json.dumps({'output':str(root),'runs':len(results),'improvement_db':[r['improvement_db'] for r in results]}),flush=True)
    return 0


if __name__=='__main__':raise SystemExit(main())
