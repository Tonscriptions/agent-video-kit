"""Own the pending native install -> reviewed stage -> full -> ordinary release."""
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import sys
import time

from run_float_sharpen_complete import ROOT, MAIN, REL, WORK, read, save, sha


def main():
    work=WORK/'finish-chain-r2';work.mkdir(parents=True,exist_ok=False)
    state={'status':'waiting-for-actual-installed741','pid':os.getpid(),
        'started_at_utc':datetime.now(timezone.utc).isoformat(), 'main_mutated':False,
        'full_suite_launched':False,'force_push':False,'full_capcut_parity':False}
    children=[]
    def checkpoint():
        state['updated_at_utc']=datetime.now(timezone.utc).isoformat();save(work/'run.json',state)
    def call(name,command):
        with (work/(name+'.log')).open('xb') as stream:
            result=subprocess.run(command,cwd=ROOT,stdin=subprocess.DEVNULL,stdout=stream,stderr=subprocess.STDOUT,
                timeout=2400,creationflags=subprocess.CREATE_NO_WINDOW)
        assert result.returncode==0,(name,result.returncode)
    def spawn(stem,owner_path):
        command=[sys.executable,'-E','-B','-X','utf8',str(ROOT/'scripts'/(stem+'.py'))]
        stream=(work/(stem+'.log')).open('xb')
        process=subprocess.Popen(command,cwd=ROOT,stdin=subprocess.DEVNULL,stdout=stream,stderr=subprocess.STDOUT,
            creationflags=subprocess.CREATE_NO_WINDOW|subprocess.CREATE_NEW_PROCESS_GROUP)
        children.append((process,stream))
        state.setdefault('children',{})[stem]={'pid':process.pid,'command':command,'owner':str(owner_path)}
        checkpoint()
        while not owner_path.exists():
            assert process.poll() is None,(stem,process.returncode)
            time.sleep(.1)
        owner=read(owner_path)
        assert owner['pid']==process.pid
        return process
    checkpoint()
    try:
        while True:
            installed=read(REL/'installed-r2/verification.json')
            if installed['status'].startswith('passed-'):break
            assert installed['status']=='running',installed.get('error',installed['status'])
            time.sleep(5)
        assert installed['status']=='passed-fresh-eight-wheel-196-resources-real-previews-and-741-methods'
        assert installed['isolated_methods']['methods']==741 and installed['isolated_methods']['skipped']==0
        state.update(status='generating-actual-installed-documents',installed_receipt_sha256=sha(REL/'installed-r2/verification.json'))
        checkpoint()
        call('actual-readme-preview-r2',[sys.executable,'-E','-B','-X','utf8',str(ROOT/'scripts/float_sharpen_release_docs.py'),'--revision','r2'])
        state['status']='reviewing-private-native-Git-stage';checkpoint()
        call('private-native-staging-r1',[sys.executable,'-E','-B','-X','utf8',str(ROOT/'scripts/publish_float_sharpen.py'),
            '--work',str(WORK/'staging-r1'),'--preflight-only'])
        preflight=read(REL/'staging-preflight-r1.json')
        assert preflight['status']=='passed-private-native-staging-and-document-preflight' and not preflight['main_mutated']
        assert preflight['generator_sha256']==sha(ROOT/'scripts/publish_float_sharpen.py')
        assert preflight['documentation_generator_sha256']==sha(ROOT/'scripts/float_sharpen_release_docs.py')
        state.update(status='starting-reviewed-complete-and-publication-owners',compared_blobs=preflight['compared_blobs'],
            virtual_publication_links=preflight['virtual_publication_links']);checkpoint()
        complete=spawn('run_float_sharpen_complete',WORK/'complete-r1/run.json')
        release=spawn('release_float_sharpen_after_complete',WORK/'release-chain-r1/run.json')
        state['status']='waiting-for-actual-parent-publication-full2836-and-ordinary-release';checkpoint()
        while True:
            owner=read(WORK/'complete-r1/run.json')
            publication=read(WORK/'release-chain-r1/run.json')
            assert not owner['status'].startswith('failed'),owner.get('error',owner['status'])
            assert not publication['status'].startswith('failed'),publication.get('error',publication['status'])
            if publication['status']=='published-V109-full2836-installed741':
                assert publication['commit']==publication['remote_main']
                state.update(status=publication['status'],commit=publication['commit'],remote_main=publication['remote_main'],
                    main_mutated=True,full_suite_launched=True)
                break
            assert complete.poll() is None or complete.returncode==0
            assert release.poll() is None or release.returncode==0
            time.sleep(5)
    except BaseException as exc:
        state.update(status='failed-preserved',error=repr(exc));raise
    finally:
        for process,stream in children:
            stream.close()
            # Failure does not kill a separately recorded owner that is still
            # making progress. Its files/PID remain available for recovery.
            state.setdefault('child_exit_codes',{})[str(process.pid)]=process.poll()
        checkpoint()
        (REL/'finish-chain-r2.executed-owner.py.txt').write_bytes(Path(__file__).read_bytes())
        print(json.dumps({k:state.get(k) for k in ('status','pid','compared_blobs','commit','error')},ensure_ascii=False),flush=True)


if __name__=='__main__':main()
