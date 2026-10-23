"""Run one actual final complete suite after the repaired source and clean install."""
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import sys
import time

from run_frozen_regression import frozen, sha

ROOT=Path(__file__).resolve().parents[1]
MAIN=Path('E:/dev/sandbox/AI广告剪辑')
REL=ROOT/'docs/validation/evidence/pipeline-recovery-20261023'
WORK=ROOT/'product/.runtime/pipeline-recovery-20261023/complete-r1'
BASELINE='f3c81ab41434f95bdbb9c05ed867bf895d37891d'


def read(path):
    for attempt in range(12):
        try:return json.loads(path.read_bytes())
        except (OSError,ValueError):
            if attempt==11:raise
            time.sleep(.025)


def save(path,value):
    temporary=path.with_name(path.name+'.'+str(os.getpid())+'.tmp')
    temporary.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n')
    os.replace(temporary,path)


def git(*args):
    result=subprocess.run(['git','-c','gc.auto=0','-c','maintenance.auto=false','-c','core.fsmonitor=false',*args],
        cwd=MAIN,capture_output=True,timeout=240,creationflags=subprocess.CREATE_NO_WINDOW)
    assert result.returncode==0,result.stderr.decode('utf8','replace')[-2000:]
    return result.stdout


def main():
    WORK.mkdir(parents=True,exist_ok=False)
    before=frozen();assert len(before)==330
    scripts={p.relative_to(ROOT).as_posix():sha(p) for p in sorted((ROOT/'scripts').iterdir()) if p.is_file()}
    deps=read(REL/'foundation-r1.json')['dependency_artifact_inputs'];assert len(deps)==9
    state=dict(status='waiting-for-actual-installed804',pid=os.getpid(),started_at_utc=datetime.now(timezone.utc).isoformat(),
        expected_methods=2897,suite_launched=False,published=False,frozen_inputs=before,
        verification_scripts=scripts,dependency_artifact_inputs=deps,force_push=False,
        native_windows=True,virtualization=False,network_during_suite=False,full_capcut_parity=False)
    def checkpoint():
        state['updated_at_utc']=datetime.now(timezone.utc).isoformat();save(WORK/'run.json',state)
    def verify():
        assert frozen()==before
        assert {p.relative_to(ROOT).as_posix():sha(p) for p in sorted((ROOT/'scripts').iterdir()) if p.is_file()}==scripts
        assert all(sha(ROOT/n)==digest for n,digest in deps.items())
    checkpoint()
    try:
        discovery=read(REL/'discovery-r2.json')
        assert discovery['full_methods']==2897 and discovery['installed_methods']==804 and discovery['frozen_inputs']==before
        native=read(REL/'native-r3/verification.json')
        assert native['status']=='passed' and native['methods']==8 and native['skipped']==0
        assert native['frozen_before']==native['frozen_after']==before
        deadline=time.monotonic()+14400
        while True:
            continuation=read(ROOT/'product/.runtime/pipeline-recovery-20261023/continuation-r2/run.json')
            assert not continuation['status'].startswith(('failed','aborted')),(continuation['status'],continuation.get('error'))
            if continuation['status']=='passed-actual-installed804-awaiting-combined-full':break
            assert time.monotonic()<deadline,'wait for actual install exceeded four hours'
            verify();time.sleep(5)
        installed=read(REL/'installed-r1/verification.json')
        assert installed['status']=='passed-fresh-eight-wheel-197-resources-real-previews-and-804-methods'
        assert installed['isolated_methods']['methods']==804 and installed['isolated_methods']['skipped']==0
        assert installed['frozen_before']==installed['frozen_after']==before
        assert len(installed['resource_hashes'])==197
        verify()
        assert git('branch','--show-current').decode().strip()=='main'
        assert git('remote','get-url','origin').decode().strip()=='git@github.com:Tonscriptions/agent-video-kit.git'
        assert git('rev-parse','HEAD').decode().strip()==BASELINE
        assert git('ls-remote','origin','refs/heads/main').decode().split()[0]==BASELINE
        assert not git('status','--porcelain','-z')
        state.update(status='checking-eight-committed-external-fixtures',parent_commit=BASELINE);checkpoint()
        env=dict(os.environ,TEMP=str(ROOT/'product/.runtime/temp'),TMP=str(ROOT/'product/.runtime/temp'),TMPDIR=str(ROOT/'product/.runtime/temp'))
        manifest=REL/'external-fixtures-r1.json'
        command=[sys.executable,'-E','-B','-X','utf8',str(ROOT/'scripts/materialize_regression_fixtures.py'),
            '--ref',BASELINE,'--output',str(manifest)]
        result=subprocess.run(command,cwd=ROOT,env=env,capture_output=True,timeout=240,creationflags=subprocess.CREATE_NO_WINDOW)
        (WORK/'fixtures.stdout.log').write_bytes(result.stdout);(WORK/'fixtures.stderr.log').write_bytes(result.stderr)
        assert result.returncode==0,result.stderr.decode('utf8','replace')[-2000:]
        fixtures=read(manifest);assert fixtures['status']=='passed' and len(fixtures['fixtures'])==8
        html=MAIN/'product/.runtime/html-motion-runtime-20261018-e2.json'
        assert sha(html)=='sha256:9ec90b14285a76803571c58a2c4709a8e493e3a21cbba3c8b329f0aa2162b16e'
        audio=MAIN/'product/.runtime/rubberband-offline-probe-20261017/native/rubberband-4.0.0-gpl-executable-windows/rubberband.exe'
        command=[sys.executable,'-E','-B','-X','utf8',str(ROOT/'scripts/run_with_regression_fixtures.py'),
            '--fixture-manifest',str(manifest),'--output',str(REL/'full-r1.json'),
            '--html-runtime',str(html),'--rubberband',str(audio)]
        verify()
        state.update(status='running-complete-native-suite',suite_launched=True,command=command,
            source_receipt_sha256=sha(REL/'native-r3/verification.json'),installed_receipt_sha256=sha(REL/'installed-r1/verification.json'))
        checkpoint()
        with (WORK/'suite.stdout.log').open('wb') as out,(WORK/'suite.stderr.log').open('wb') as err:
            process=subprocess.Popen(command,cwd=ROOT,env=env,stdout=out,stderr=err,creationflags=subprocess.CREATE_NO_WINDOW)
            state['suite_owner_pid']=process.pid;checkpoint();code=process.wait()
        full=read(REL/'full-r1.json')
        assert code==0 and full['status']=='passed' and full['terminal_ok'],full.get('error')
        assert full['methods']==2897 and full['skipped']==0
        assert full['frozen_before']==full['frozen_after']==before
        assert full['external_fixtures_equal'] and full['verification_scripts_equal']
        verify();assert sha(html)==native['native_html_configuration']['sha256']
        state.update(status='passed-complete-native-suite-not-published',methods=2897,
            suite_seconds=full['suite_seconds'],skipped=0,full_receipt_sha256=sha(REL/'full-r1.json'))
        checkpoint()
    except BaseException as exc:
        state.update(status='failed-preserved',error=repr(exc));checkpoint();raise
    finally:
        print(json.dumps({k:state.get(k) for k in ['status','methods','suite_seconds','suite_launched','error']},ensure_ascii=False),flush=True)


if __name__=='__main__':main()
