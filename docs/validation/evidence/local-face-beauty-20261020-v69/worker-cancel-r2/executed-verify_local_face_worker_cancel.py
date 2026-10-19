"""Prove cancellation after a Python child is assigned to the native face Job."""
from __future__ import annotations
import argparse
from datetime import datetime,timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import threading
import time
import traceback
from run_frozen_regression import frozen
from smoke_local_face import owned_direct_children

ROOT=Path(__file__).resolve().parents[1]


def sha(path):return 'sha256:'+hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for key in ('native-project','installed-project','installed','controller-python','evidence','work'):
        parser.add_argument('--'+key,type=Path,required=True)
    args=parser.parse_args()
    for key,value in vars(args).items():setattr(args,key,value.resolve())
    args.evidence.mkdir(parents=True,exist_ok=False);args.work.mkdir(parents=True,exist_ok=False)
    for name in ('verify_local_face_worker_cancel.py','smoke_local_face.py'):
        shutil.copyfile(ROOT/'scripts'/name,args.evidence/('executed-'+name))
    record={'status':'running','started_at_utc':datetime.now(timezone.utc).isoformat(),'frozen_before':frozen(),
            'calls':[],'successful_model_forwards_claimed':0,'quality_accepted':False,'full_capcut_parity':False}
    def save():
        (args.evidence/'verification.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n')
    save()
    try:
        installed_prefix=[args.controller_python,'-I','-S','-B','-X','utf8',args.installed/'run.py']
        env=dict(os.environ,TEMP=str(args.work),TMP=str(args.work),TMPDIR=str(args.work),
                 AI_AD_EDITOR_RUNTIME_DIR=str(args.work/'runtime'),PYTHONDONTWRITEBYTECODE='1')
        for name,project in (('development',args.native_project),('installed',args.installed_project)):
            authored=[project/'project.json',project/'rights-ledger.json'];before=[sha(p) for p in authored]
            data=json.loads(authored[0].read_bytes());source=data['assets'][0];adapter=data['extensions']['local_face']['adapters'][0]
            if name=='development':
                # Adapter paths are intentionally bound, including source paths.
                # Exercise the already registered source checkout, after proving
                # its runtime files are identical to the current release source.
                for entry in adapter['artifacts']:
                    if entry['role'].endswith(('.py','.txt')):
                        current=ROOT/'product/src/ai_ad_editor'/entry['role']
                        assert Path(entry['path']).read_bytes()==current.read_bytes()
                module=next(Path(e['path']) for e in adapter['artifacts'] if e['role']=='local_face.py')
                prefix=[args.controller_python,'-E','-B','-X','utf8','-c',
                        'import sys;sys.path.insert(0,'+repr(str(module.parent.parent))+');from ai_ad_editor.cli import main;raise SystemExit(main())']
            else:
                prefix=installed_prefix
            output=project/'validation'/('cancel-worker-v69-'+name+'.json');cancel=args.work/(name+'.cancel')
            assert not output.exists() and not cancel.exists()
            command=list(map(str,[*prefix,'face','scan','--project',project,'--asset-id',source['id'],
                     '--adapter-id',adapter['adapter_id'],'--max-frames','24','--output',output,'--cancel-file',cancel]))
            observation={};started=time.monotonic()
            process=subprocess.Popen(command,cwd=ROOT,env=env,stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
            def trigger():
                try:
                    while process.poll() is None:
                        pids=owned_direct_children(process.pid,executable_name=Path(adapter['python_executable']).name)
                        if pids:
                            observation.update(cli_pid=process.pid,observed_python_children=pids)
                            time.sleep(.05);cancel.write_text('cancel',encoding='utf8');observation['written']=True;return
                        time.sleep(.02)
                except BaseException as exc:
                    observation['monitor_error']=type(exc).__name__+': '+str(exc)
            monitor=threading.Thread(target=trigger,daemon=True);monitor.start()
            out,err=process.communicate(timeout=120);monitor.join(timeout=2)
            (args.evidence/(name+'.stdout.log')).write_bytes(out);(args.evidence/(name+'.stderr.log')).write_bytes(err)
            reply=json.loads(out);error=reply['errors'][0];cleanup=error['diagnostics']['process_cleanup']
            row={'name':name,'command':command,'exit_code':process.returncode,'seconds':time.monotonic()-started,
                 'stdout_sha256':'sha256:'+hashlib.sha256(out).hexdigest(),'stderr_sha256':'sha256:'+hashlib.sha256(err).hexdigest(),
                 'observation':observation,'process_cleanup':cleanup,'before_author_sha256':before,
                 'after_author_sha256':[sha(p) for p in authored],'no_partial_report':not output.exists()}
            record['calls'].append(row);save()
            assert process.returncode==8 and error['code']=='CANCELLED' and observation['written']
            assert set(observation['observed_python_children']) & set(cleanup['seen_pids'])
            assert cleanup['all_children_reaped'] and not cleanup['active_after_cleanup']
            assert row['after_author_sha256']==before and row['no_partial_report']
        record['status']='passed_worker_started_then_cancelled'
    except BaseException as exc:
        record.update(status='failed',error=type(exc).__name__+': '+str(exc),traceback=traceback.format_exc());raise
    finally:
        record['frozen_after']=frozen();record['frozen_equal']=record['frozen_before']==record['frozen_after']
        record['finished_at_utc']=datetime.now(timezone.utc).isoformat();save()
    print(json.dumps({'status':record['status'],'development_cli_calls':1,'isolated_cli_calls':1,'frozen_equal':record['frozen_equal']}))


if __name__=='__main__':main()
