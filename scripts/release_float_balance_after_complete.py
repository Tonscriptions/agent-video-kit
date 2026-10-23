"""Ordinary automatic publication after actual full2579 and a byte-reviewed stage."""
from datetime import datetime, timezone
import json
import os
import subprocess
import sys
import time

from run_float_balance_complete import ROOT,MAIN,WORK,REL,read,save,sha


def update_progress(publication):
    path=MAIN/'product/.runtime/agent-video-kit-progress-20261021.json'
    old=path.read_bytes();data=json.loads(old)
    (WORK/'release-chain-r1/private-progress-before.json').write_bytes(old)
    full=read(REL/'full-r1.json');installed=read(REL/'installed-r1/verification.json')
    data['main'].update(version='V104',branch='main',commit=publication['commit'],product_commit=publication['commit'],
        remote_main=publication['remote_main'],clean=True,frozen_inputs=316,full_methods=2579,
        suite_seconds=full['suite_seconds'],skipped=0,skills=17,
        full_receipt=str(MAIN/'docs/validation/evidence/float-balance-20261022-lab/full-r1.json'),
        publication_record=str(WORK/'publication-r1/run.json'),readme_and_numbered_actual_media_updated=True,
        latest_documentation_update='continuous Float32 three-way balance and creative Kelvin author channels shared by render/preview; full2579 and installed484, 189 resources; default migration/all operators/natural/HDR/full CapCut parity unfinished')
    data.setdefault('float_balance_lab',{}).update(status='published-V104-full2579-installed484',published=True,
        main_integrated=True,commit=publication['commit'],remote_main=publication['remote_main'],
        native_methods=284,new_methods=42,installed_methods=484,installed_resources=189,
        installed_suite_seconds=installed['isolated_methods']['suite_seconds'],full_suite_started=True,full_suite_passed=True,
        full_methods=2579,full_receipt=str(REL/'full-r1.json'),full_capcut_parity=False,
        publication_record=str(WORK/'publication-r1/run.json'))
    data.update(updated_at_utc=datetime.now(timezone.utc).isoformat(),goal_status='active')
    assert path.read_bytes()==old,'Concurrent private progress change preserved'
    save(path,data)


def main():
    work=WORK/'release-chain-r1';work.mkdir(parents=True,exist_ok=False)
    state={'status':'waiting-for-actual-full2579-and-reviewed-preflight','pid':os.getpid(),
        'started_at_utc':datetime.now(timezone.utc).isoformat(),'force_push':False,'main_integrated':False}
    def checkpoint():
        state['updated_at_utc']=datetime.now(timezone.utc).isoformat();save(work/'run.json',state)
    checkpoint()
    try:
        preflight=read(REL/'staging-preflight-r1.json')
        assert preflight['status']=='passed-private-native-staging-and-document-preflight' and not preflight['main_mutated']
        publisher=ROOT/'scripts/publish_float_balance.py'
        assert preflight['generator_sha256']==sha(publisher)
        assert preflight['documentation_generator_sha256']==sha(ROOT/'scripts/float_balance_release_docs.py')
        while True:
            owner=read(WORK/'complete-r1/run.json')
            if owner['status']=='passed-complete-native-suite-not-published':break
            assert owner['status'] in ['checking-source-and-install','waiting-for-actual-published-V103-full2537',
                'running-complete-native-suite'],owner.get('error',owner['status'])
            time.sleep(5)
        full=read(REL/'full-r1.json')
        assert owner['methods']==full['methods']==2579 and full['terminal_ok'] and full['skipped']==0
        assert owner['full_receipt_sha256']==sha(REL/'full-r1.json')
        assert full['frozen_before']==full['frozen_after']==preflight['source_audit']['frozen_inputs']
        assert preflight['generator_sha256']==sha(publisher)
        assert preflight['documentation_generator_sha256']==sha(ROOT/'scripts/float_balance_release_docs.py')
        state.update(status='publishing-reviewed-V104',full_receipt_sha256=sha(REL/'full-r1.json'));checkpoint()
        publication_work=WORK/'publication-r1'
        command=[sys.executable,'-E','-B','-X','utf8',str(publisher),'--work',str(publication_work)]
        with (work/'publish.log').open('xb') as stream:
            result=subprocess.run(command,cwd=ROOT,stdout=stream,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW)
        publication=read(publication_work/'run.json')
        assert result.returncode==0 and publication['status']=='published',publication.get('error')
        assert publication['commit']==publication['remote_main'] and publication['main_clean'] and not publication['force_push']
        state.update(status='published-V104-full2579-installed484',main_integrated=True,
            commit=publication['commit'],remote_main=publication['remote_main']);checkpoint()
        try:update_progress(publication)
        except Exception as exc:state['private_progress_update_error']=repr(exc)
    except BaseException as exc:
        state.update(status='failed-preserved',error=repr(exc));raise
    finally:
        checkpoint();print(json.dumps({k:state.get(k) for k in ['status','commit','remote_main','error']},ensure_ascii=False),flush=True)


if __name__=='__main__':main()
