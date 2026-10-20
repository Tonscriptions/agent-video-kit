"""Reproduce old early-exit assignment race and compare real suspended startup."""
from __future__ import annotations
import argparse
from datetime import datetime,timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from types import ModuleType
from unittest import mock

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'product/src'))
from ai_ad_editor.browser_process import BrowserProcessJob
from ai_ad_editor.errors import AppError
from run_frozen_regression import frozen


def sha(path):return 'sha256:'+hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for key in ('work','evidence','old-source'):parser.add_argument('--'+key,type=Path,required=True)
    args=parser.parse_args();work=args.work.resolve();evidence=args.evidence.resolve();old_path=args.old_source.resolve(strict=True)
    assert not work.exists() and not evidence.exists();work.mkdir(parents=True);evidence.mkdir(parents=True)
    module=ModuleType('ai_ad_editor._archived_browser_process');module.__package__='ai_ad_editor'
    exec(compile(old_path.read_bytes(),'<archived-browser-process>','exec'),module.__dict__)
    record={'status':'running','started_at_utc':datetime.now(timezone.utc).isoformat(),'script_sha256':sha(Path(__file__)),
            'old_source_sha256':sha(old_path),'current_source_sha256':sha(ROOT/'product/src/ai_ad_editor/browser_process.py'),
            'frozen_before':frozen(),'delay_seconds':.15,'delay_is_injected':True,
            'old_case_waits_for_real_natural_exit':True,'assignment_api_is_real_in_both_cases':True,'virtualization':False,'new_model_inference':0,'cases':{}}
    real=subprocess.Popen
    def run_case(name,kind):
        marker=work/(name+'.marker');job=kind(10);observations=[];processes=[]
        def delayed(*argv,**kwargs):
            child=real(*argv,**kwargs);processes.append(child)
            if name=='old':child.wait(timeout=5)  # actual early exit before real assignment
            else:time.sleep(.15)  # suspended new process cannot execute yet
            observations.append({'pid':child.pid,'creationflags':kwargs['creationflags'],'returncode_before_assignment':child.poll(),
                                 'marker_exists_before_assignment':marker.exists()})
            return child
        row={'observations':observations}
        try:
            with mock.patch('subprocess.Popen',side_effect=delayed):
                child=job.start([sys.executable,'-I','-S','-B','-c','from pathlib import Path;Path('+repr(str(marker))+').write_text("ran")'],
                    cwd=work,env=dict(os.environ),stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
            row.update(status='succeeded',returncode=child.wait(timeout=5))
        except AppError as exc:row.update(status='rejected',error=exc.as_dict())
        finally:row.update(cleanup=job.close(),final_returncodes=[p.poll() for p in processes],marker_exists_after=marker.exists())
        return row
    try:
        record['cases']['old']=run_case('old',module.BrowserProcessJob)
        record['cases']['current']=run_case('current',BrowserProcessJob)
        old,new=record['cases']['old'],record['cases']['current']
        assert old['status']=='rejected' and old['error']['code']=='HTML_JOB_UNAVAILABLE'
        assert old['observations'][0]['returncode_before_assignment']==0 and old['observations'][0]['marker_exists_before_assignment']
        assert new['status']=='succeeded' and new['returncode']==0
        assert new['observations'][0]['returncode_before_assignment'] is None and not new['observations'][0]['marker_exists_before_assignment']
        assert new['marker_exists_after'] and new['cleanup']['all_children_reaped']
        record['status']='passed_controlled_race'
    except BaseException as exc:
        record.update(status='failed',error={'type':type(exc).__name__,'message':str(exc)});raise
    finally:
        record.update(finished_at_utc=datetime.now(timezone.utc).isoformat(),frozen_after=frozen())
        record['frozen_equal']=record['frozen_before']==record['frozen_after']
        (evidence/'verification.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n')
    assert record['frozen_equal'];print(json.dumps({'status':record['status'],'old_rejected':True,'new_completed':True,'frozen_equal':True}))


if __name__=='__main__':main()
