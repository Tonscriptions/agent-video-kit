"""Continue the reviewed V92 release only after the live complete suite succeeds."""
from datetime import datetime,timezone
import json,os
from pathlib import Path
import subprocess,sys,time
from float_release_docs import ROOT,MAIN,REL
from run_frozen_regression import sha

def read(p):return json.loads(p.read_bytes())
def save(p,v):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n')

def main():
    work=ROOT/'product/.runtime/color-precision-20261021/release-chain-r1'
    assert not work.exists();work.mkdir(parents=True)
    owner=ROOT/'product/.runtime/color-precision-20261021/complete-r1/run.json'
    state={'status':'waiting-for-actual-complete-suite','started_at_utc':datetime.now(timezone.utc).isoformat(),
        'pid':os.getpid(),'generator_sha256':sha(Path(__file__)),'calls':[],'force_push':False,'main_integrated':False}
    def checkpoint():save(work/'run.json',state)
    def run(name,arguments):
        command=list(map(str,[sys.executable,'-E','-B','-X','utf8',*arguments]));state['status']=name;checkpoint()
        with (work/(name+'.log')).open('xb') as stream:
            result=subprocess.run(command,cwd=ROOT,stdout=stream,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW)
        state['calls'].append({'name':name,'command':command,'exit_code':result.returncode,'log_sha256':sha(work/(name+'.log'))});checkpoint()
        assert result.returncode==0,name+' failed; review preserved log'
    checkpoint()
    try:
        while True:
            observed=read(owner)
            if observed['status']=='passed-complete-native-suite-not-published':break
            assert observed['status']=='running-complete-native-suite',observed.get('error',observed['status'])
            time.sleep(5)
        state.update(complete_owner_sha256=sha(owner),actual_full_methods=observed['methods']);checkpoint()
        assert observed['methods']==2234
        run('finalize-actual-complete-documents',[ROOT/'scripts/finalize_float_evidence.py','--stage','full'])
        publication=ROOT/'product/.runtime/color-precision-20261021/publication-r1'
        run('publish-reviewed-V92',[ROOT/'scripts/publish_float_surface.py','--work',publication])
        published=read(publication/'run.json')
        assert published['status']=='published' and published['main_clean'] and published['commit']==published['remote_main']
        assert published['full_methods']==2234 and published['isolated_methods']==117 and not published['force_push']
        progress=MAIN/'product/.runtime/agent-video-kit-progress-20261021.json';old=progress.read_bytes();value=json.loads(old)
        stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ');backup=progress.with_name('progress-before-float-V92-release-'+stamp+'.json');backup.write_bytes(old)
        full=read(ROOT/REL/'full-r1.json');skills=read(MAIN/REL/'skills-release-r1.json');installed=read(ROOT/REL/'installed-r1/verification.json')
        value['main'].update(branch='main',commit=published['commit'],remote_main=published['remote_main'],clean=True,version='V92',
            full_methods=2234,suite_seconds=full['suite_seconds'],skipped=0,frozen_inputs=282,
            full_receipt=str(MAIN/REL/'full-r1.json'),publication_record=str(publication/'run.json'),
            readme_and_numbered_actual_media_updated=True,verified_document_links=published['verified_links'],
            staged_blob_comparisons=published['compared_blobs'],skills=17,skill_links=skills['local_links_checked'],
            product_commit=published['commit'],latest_documentation_update='V92 native-clock Float32 surface CLI and independent linear-light core; actual complete2234 and installed117; OpenFilm R14/R15 preserved')
        lab=value['color_precision_lab'];lab.update(status='published-V92-surface-CLI-not-general-timeline-float-backend',
            published=True,published_commit=published['commit'],remote_main=published['remote_main'],
            full_suite_status=observed['status'],full_suite_tool_session_id=None,full_suite_pid=None,
            full_suite_passed=True,full_methods=2234,full_seconds=full['suite_seconds'],
            full_receipt=str(MAIN/REL/'full-r1.json'),installed_status=installed['status'],installed_tool_session_id=None,
            installed_methods=117,installed_seconds=installed['isolated_methods']['suite_seconds'],installed_subprocess_CLI_calls=18,
            publication_record=str(publication/'run.json'),registered_Skills_updated=True,
            report=str(MAIN/'docs/validation/浮点表面合成与高精度边界独立实测_2026-10-22.md'),
            contract=str(MAIN/'docs/specs/浮点表面合成与高精度边界_实验_v0.1_2026-10-22.md'),
            CLI_guide=str(MAIN/'docs/Agent浮点帧包CLI使用与验收边界_2026-10-22.md'),
            next_work=['Integrate explicit high-precision signal and alpha policy into ordinary editable timeline, preview and cache.',
                       'Cover effect/transition/subtitle/nesting boundaries with real native and natural media, retaining quantization reports.',
                       'Implement/validate ICC, absolute luminance, PQ/HLG/HDR metadata, display reference, antialiasing and real performance; do not claim complete CapCut parity.'])
        value.update(updated_at_utc=datetime.now(timezone.utc).isoformat(),goal_status='active',previous_progress_snapshot=str(backup),
            current_goal_turn_classification='V92 actual full2234/installed117 passed and ordinary publication verified; default timeline high precision and complete CapCut parity still unfinished')
        assert progress.read_bytes()==old,'Concurrent checkpoint change; preserve both and review'
        temporary=progress.with_name('progress-float-V92-'+stamp+'.tmp');save(temporary,value);os.replace(temporary,progress)
        state.update(status='published-V92-with-actual-complete-and-installed-receipts',commit=published['commit'],remote_main=published['remote_main'],main_integrated=True)
    except BaseException as error:state.update(status='failed-preserved',error=repr(error));raise
    finally:
        state['updated_at_utc']=datetime.now(timezone.utc).isoformat();checkpoint()
        print(json.dumps({k:state.get(k) for k in ('status','commit','remote_main','error')}),flush=True)

if __name__=='__main__':main()
