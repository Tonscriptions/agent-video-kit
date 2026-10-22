"""Publish the reviewed host candidate only after its actual full-r2 succeeds."""
from datetime import datetime,timezone
import json,os,subprocess,sys,time
from pathlib import Path
from float_timeline_release_docs import ROOT,MAIN,REL
from run_frozen_regression import sha

def read(p):
    for attempt in range(8):
        try:return json.loads(p.read_bytes())
        except (json.JSONDecodeError,OSError):
            if attempt==7:raise
            time.sleep(.025)
def save(p,v):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n',encoding='utf8')

def main():
    work=ROOT/'product/.runtime/float-timeline-20261022/release-chain-r2';assert not work.exists();work.mkdir(parents=True)
    state={'status':'waiting-for-actual-full2280-r2','started_at_utc':datetime.now(timezone.utc).isoformat(),'pid':os.getpid(),'generator_sha256':sha(Path(__file__)),'force_push':False,'main_integrated':False,'calls':[]}
    owner=ROOT/'product/.runtime/float-timeline-20261022/complete-r2/run.json'
    def checkpoint():save(work/'run.json',state)
    checkpoint()
    try:
        while True:
            value=read(owner)
            if value['status']=='passed-complete-native-suite-not-published':break
            assert value['status'] in ('waiting-for-actual-parent-publication-and-isolated-install','running-complete-native-suite'),value.get('error',value['status'])
            time.sleep(5)
        assert value['methods']==2280;state.update(full_owner_sha256=sha(owner),status='publishing-reviewed-V93-host');checkpoint()
        publication=ROOT/'product/.runtime/float-timeline-20261022/publication-r2';command=list(map(str,[sys.executable,'-E','-B','-X','utf8',ROOT/'scripts/publish_float_timeline.py','--work',publication]))
        with (work/'publish-reviewed-V93.log').open('xb') as stream:result=subprocess.run(command,cwd=ROOT,stdout=stream,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW)
        state['calls'].append({'command':command,'exit_code':result.returncode,'log_sha256':sha(work/'publish-reviewed-V93.log')});checkpoint();assert result.returncode==0
        published=read(publication/'run.json');assert published['status']=='published' and published['commit']==published['remote_main'] and published['main_clean'] and published['full_methods']==2280 and published['isolated_methods']==163 and not published['force_push']
        progress=MAIN/'product/.runtime/agent-video-kit-progress-20261021.json';old=progress.read_bytes();data=json.loads(old)
        stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ');backup=progress.with_name('progress-before-V93-host-release-'+stamp+'.json');backup.write_bytes(old)
        full=read(MAIN/REL/'full-r2.json');installed=read(MAIN/REL/'installed-r1/verification.json');skills=read(MAIN/REL/'skills-release-r2.json')
        data['main'].update(branch='main',version='V93',commit=published['commit'],remote_main=published['remote_main'],product_commit=published['commit'],clean=True,full_methods=2280,suite_seconds=full['suite_seconds'],skipped=0,frozen_inputs=288,
            full_receipt=str(MAIN/REL/'full-r2.json'),publication_record=str(publication/'run.json'),readme_and_numbered_actual_media_updated=True,verified_document_links=published['verified_links'],staged_blob_comparisons=published['compared_blobs'],skills=17,skill_links=skills['local_links_checked'],
            latest_documentation_update='V93 author-clock Float32 host/verified bundle library; full2280/installed163 actual; default streaming/render/audio/preview/cache and complete CapCut parity still incomplete')
        data['float_timeline_lab'].update(status='published-V93-library-host-default-render-not-integrated',published=True,published_commit=published['commit'],remote_main=published['remote_main'],full_suite_status=value['status'],full_suite_tool_session_id=None,full_suite_owner_pid=None,full_suite_started=True,full_methods=2280,full_seconds=full['suite_seconds'],full_suite_passed=True,full_receipt=str(MAIN/REL/'full-r2.json'),installed_status=installed['status'],installed_methods=163,publication_record=str(publication/'run.json'),public_main_readme_updated=True,main_untouched=False,release_chain_status='published',report=str(MAIN/'docs/validation/作者时钟浮点帧宿主与真实媒体独立实测_2026-10-22.md'),contract=str(MAIN/'docs/specs/作者时钟浮点帧宿主与缓存源边界_v0.1_2026-10-22.md'))
        data.update(updated_at_utc=datetime.now(timezone.utc).isoformat(),goal_status='active',previous_progress_snapshot=str(backup),current_goal_turn_classification='progress: actual full2280/installed163 host candidate published by ordinary push; high precision standard streaming/render/audio/preview/cache and complete CapCut parity remain unfinished')
        assert progress.read_bytes()==old,'Concurrent checkpoint update; retain both and merge actual publication state'
        temporary=progress.with_name('progress-V93-host-'+stamp+'.tmp');save(temporary,data);os.replace(temporary,progress)
        state.update(status='published-V93-with-actual-full2280-and-installed163',commit=published['commit'],remote_main=published['remote_main'],main_integrated=True)
    except BaseException as exc:state.update(status='failed-preserved',error=repr(exc));raise
    finally:
        state['updated_at_utc']=datetime.now(timezone.utc).isoformat();checkpoint();print(json.dumps({k:state.get(k) for k in ('status','commit','remote_main','error')}),flush=True)

if __name__=='__main__':main()
