"""Independently verify the unchanged-scene, pre-outpaint VACE delivery retry."""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
from fractions import Fraction
import gzip
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import zipfile

ROOT=Path(__file__).resolve().parents[1]


def sha(p):return 'sha256:'+hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):return json.loads(p.read_bytes())


def main():
    import numpy as np
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('evidence','public','output'):parser.add_argument('--'+name,type=Path,required=True)
    args=parser.parse_args()
    for name,value in vars(args).items():setattr(args,name,value.resolve())
    args.output.mkdir(parents=True,exist_ok=False)
    calls=[]; files={}
    record={'status':'running','started_at_utc':datetime.now(timezone.utc).isoformat(),
        'source_scope':'exact archived V65 inputs; not later V66 outpaint code', 'calls':calls,'files':files,
        'natural_quality_accepted':False,'full_capcut_parity':False,'continuous_playback':False,'audio_listened':False}

    def save():
        (args.output/'verification.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n')

    def bind(p):files[p.relative_to(ROOT).as_posix()]={'sha256':sha(p),'bytes':p.stat().st_size}

    def command(argv,name):
        result=subprocess.run(list(map(str,argv)),cwd=ROOT,capture_output=True,timeout=120)
        out=args.output/(name+'.stdout.gz');err=args.output/(name+'.stderr.log')
        out.write_bytes(gzip.compress(result.stdout,mtime=0));err.write_bytes(result.stderr)
        calls.append({'name':name,'command':list(map(str,argv)),'exit_code':result.returncode,
            'stdout':out.name,'stderr':err.name,'stdout_sha256':sha(out),'stderr_sha256':sha(err),
            'raw_sha256':'sha256:'+hashlib.sha256(result.stdout).hexdigest(),'raw_bytes':len(result.stdout)})
        save();assert result.returncode==0,name
        return result.stdout

    save()
    try:
        original=read(args.evidence/'verification.json');snapshot=read(args.evidence/'source-snapshot.json')
        assert original['status']=='passed_actual_vace_resource_and_delivery_checks_quality_separate'
        assert original['frozen_before']==original['frozen_after']==snapshot['files'] and snapshot['file_count']==198
        assert sha(args.evidence/'source-snapshot.zip')==snapshot['archive_sha256']
        with zipfile.ZipFile(args.evidence/'source-snapshot.zip') as archive:
            assert set(archive.namelist())==set(snapshot['files'])
            for name,digest in snapshot['files'].items():assert 'sha256:'+hashlib.sha256(archive.read(name)).hexdigest()==digest
        summary=read(args.evidence/'actual-summary.json');result=summary['inpainting'];worker=result['worker']
        sys.path.insert(0,str(ROOT/'product/src'))
        from ai_ad_editor.cuda_admission import validate_execution
        validate_execution(worker['model_execution'],text_gpu_budget_mib=summary['adapter']['settings']['text_gpu_budget_mib'],model_calls=worker['metrics']['model_calls'])
        frames={}; pts={}; pcm={}
        for name in ('source','mask','repaired'):
            p=args.public/(name+'.mov')
            raw=command(['ffmpeg','-nostdin','-v','error','-i',p,'-map','0:v:0','-an','-fps_mode','passthrough',
                '-pix_fmt','rgba','-f','rawvideo','pipe:1'],'decode-'+name)
            frames[name]=np.frombuffer(raw,np.uint8).reshape(8,128,192,4)
            probe=json.loads(command(['ffprobe','-v','error','-select_streams','v:0','-show_frames','-show_streams','-of','json',p],'pts-'+name))
            pts[name]=[Fraction(v['best_effort_timestamp'])*Fraction(probe['streams'][0]['time_base']) for v in probe['frames']]
            if name!='mask':pcm[name]=command(['ffmpeg','-nostdin','-v','error','-i',p,'-map','0:a:0','-vn',
                '-ar','48000','-ac','1','-f','s16le','pipe:1'],'pcm-'+name)
        selected=frames['mask'][...,3]>127;source=frames['source'];actual=frames['repaired']
        assert np.array_equal(actual[~selected],source[~selected]) and np.array_equal(actual[...,3],source[...,3])
        assert all(v==[Fraction(i,8) for i in range(8)] for v in pts.values())
        assert pcm['source']==pcm['repaired'] and len(pcm['source'])==96000
        truth=np.load(args.public/'ground-truth.npz',allow_pickle=False)['frames']
        mse=float(np.square(actual[...,:3].astype(np.float64)-truth[...,:3].astype(np.float64))[selected].mean())
        psnr=100. if mse==0 else float(10*np.log10(255**2/mse))
        assert abs(psnr-summary['controlled_reconstruction']['masked_psnr_after_db'])<1e-5
        assert original['controlled_psnr_at_least_30']==(psnr>=30.)
        assert worker['network']=='disabled' and not worker['blocked_network_events'] and result['rgba_roundtrip_verified']
        assert summary['rights_expected_exit']==7
        for folder in (args.public,args.evidence):
            for p in folder.rglob('*'):
                if p.is_file() and not p.is_relative_to(args.output):bind(p)
        record.update(status='passed_delivery_quality_separate',base_commit=snapshot['base_commit'],
            archived_inputs=198,frames=8,fps='8/1',every_pts_equal=True,original_alpha_exact=True,
            outside_rgba_changed_pixels=0,audio_pcm_exact=True,mono_sample_frames=48000,
            psnr_db=psnr,controlled_gate_db=30.,controlled_quality_passed=psnr>=30.,
            window_calls=worker['metrics']['model_calls'],gpu_admission=worker['model_execution']['gpu_admission'],
            text_offload=worker['model_execution'].get('text_offload'),commercial_publish_blocked=True)
    except Exception as exc:
        record.update(status='failed',error=type(exc).__name__+': '+str(exc));raise
    finally:
        record['finished_at_utc']=datetime.now(timezone.utc).isoformat();save()
    print(json.dumps({k:record[k] for k in ('status','frames','window_calls','psnr_db','controlled_quality_passed')}))


if __name__=='__main__':main()
