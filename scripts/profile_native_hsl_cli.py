"""Record bounded Python profiling for one actual CLI render; not an FPS benchmark."""
from __future__ import annotations
import argparse
from datetime import datetime,timezone
import hashlib
import json
import os
from pathlib import Path
import pstats
import subprocess
import sys
import time
from run_frozen_regression import frozen

ROOT=Path(__file__).resolve().parents[1]
def sha(path):return 'sha256:'+hashlib.sha256(Path(path).read_bytes()).hexdigest()

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project',type=Path,required=True);parser.add_argument('--evidence',type=Path,required=True)
    args=parser.parse_args();project=args.project.resolve(strict=True);evidence=args.evidence.resolve()
    assert project.is_relative_to(ROOT/'product/.runtime') and evidence.is_relative_to(ROOT/'docs') and not evidence.exists()
    evidence.mkdir(parents=True);output=project/'renders/profile-native-r1.mp4';assert not output.exists()
    profile=evidence/'cli.pstats';assert not profile.exists()
    bootstrap='''import cProfile,sys
sys.path.insert(0,sys.argv.pop(1))
from ai_ad_editor.runtime import configure_local_runtime
configure_local_runtime()
from ai_ad_editor.cli import main
profiler=cProfile.Profile()
profile_path=sys.argv.pop(1)
try:
 result=profiler.runcall(main)
finally:
 profiler.dump_stats(profile_path)
raise SystemExit(result)
'''
    command=[sys.executable,'-E','-B','-X','utf8','-c',bootstrap,str(ROOT/'product/src'),str(profile),
        'render','--project',str(project),'--output',str(output),'--profile','custom','--width','1920','--height','1080']
    record={'status':'running','started_at_utc':datetime.now(timezone.utc).isoformat(),'generator_sha256':sha(__file__),
        'frozen_before':frozen(),'command':command,'network':False,'virtualization':False,'concurrent_load':'full-r3',
        'scope':'one instrumented Python CLI main; import/bootstrap before main excluded; Python profiler perturbs timing; FFmpeg is an opaque child, not a native filter/encoder profile',
        'fps_benchmark':False,'interactive_preview_accepted':False,'full_capcut_parity':False}
    def save():(evidence/'verification.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n')
    save()
    try:
        env=dict(os.environ);temp=ROOT/'product/.runtime/temp';temp.mkdir(parents=True,exist_ok=True)
        env.update(TEMP=str(temp),TMP=str(temp),TMPDIR=str(temp),PYTHONDONTWRITEBYTECODE='1',AI_AD_EDITOR_HSL_BACKEND='native')
        start=time.perf_counter();result=subprocess.run(command,cwd=ROOT,env=env,capture_output=True,timeout=600)
        record.update(wall_seconds=time.perf_counter()-start,exit_code=result.returncode)
        for stream in ('stdout','stderr'):
            path=evidence/(stream+'.log');path.write_bytes(getattr(result,stream));record[stream+'_sha256']=sha(path)
        assert result.returncode==0,result.stdout[-1600:].decode('utf8','replace')+result.stderr[-1200:].decode('utf8','replace')
        response=json.loads(result.stdout);manifest_path=Path(response['data']['manifest']);manifest=json.loads(manifest_path.read_bytes())
        kernels=[x for x in manifest['inputs'] if x.get('kind')=='selective-hsl'];assert len(kernels)==1 and kernels[0]['backend']=='ffmpeg:frei0r' and kernels[0]['sampled_frames']==60
        stats=pstats.Stats(str(profile));rows=[]
        for (filename,line,name),(primitive,calls,total,cumulative,callers) in stats.stats.items():
            rows.append({'filename':filename,'line':line,'name':name,'primitive_calls':primitive,'calls':calls,'total_seconds':total,'cumulative_seconds':cumulative})
        record.update(status='passed-diagnostic',profile_sha256=sha(profile),profile_total_calls=stats.total_calls,
            profile_total_seconds=stats.total_tt,top_cumulative=sorted(rows,key=lambda x:x['cumulative_seconds'],reverse=True)[:50],
            top_self=sorted(rows,key=lambda x:x['total_seconds'],reverse=True)[:30],output_sha256=sha(output),kernel_metadata=kernels,
            render_manifest_sha256=sha(manifest_path))
        (evidence/'manifest.json').write_bytes(manifest_path.read_bytes())
    except BaseException as exc:
        record.update(status='failed',error={'type':type(exc).__name__,'message':str(exc)});raise
    finally:
        record.update(finished_at_utc=datetime.now(timezone.utc).isoformat(),frozen_after=frozen())
        record['frozen_equal']=record['frozen_before']==record['frozen_after'];save()
    assert record['frozen_equal']
    print(json.dumps({'status':record['status'],'profile_total_seconds':record['profile_total_seconds'],'top_self':record['top_self'][:5]}))

if __name__=='__main__':main()
