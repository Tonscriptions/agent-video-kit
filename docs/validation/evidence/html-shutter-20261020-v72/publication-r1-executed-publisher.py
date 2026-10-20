"""Publish reviewed V72 bytes after existing complete regression and V71 delivery.

No new test run, dependency fetch, model call, worktree reset, Skill retarget or
force push is performed. Shared docs are regenerated on main after source copy.
"""
from __future__ import annotations
import argparse
from datetime import datetime,timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

from run_frozen_regression import frozen
from sync_html_shutter_documents import BASE,REPORT,CONTRACT,RESEARCH,DOCUMENTS

ROOT=Path(__file__).resolve().parents[1]
MAIN=Path('E:/dev/sandbox/AI广告剪辑')
REL=BASE.relative_to(ROOT).as_posix()
R10='docs/validation/evidence/openfilm-shutter-20261020-r10'
PREVIOUS_REL='docs/validation/evidence/contact-sheet-20261020-v71'
REMOTE='git@github.com:Tonscriptions/agent-video-kit.git'
ASSETS=('docs/assets/html-shutter-20261020-v72-native-r1','docs/assets/html-shutter-20261020-v72-native-r2','docs/assets/html-shutter-20261020-v72-installed-r1')
DYNAMIC={REL+'/'+name for name in ('full-r1.json','full-r1.log','full-r1.source.json','full-r1.source.log')}
FUTURE={REL+'/'+name for name in ('skills-r1.json','release-r1.json','staged-r1.json','publication-copy-r1.json')}
SCRIPTS=('smoke_html_shutter','verify_html_shutter_install','audit_html_shutter_media','compare_html_shutter_default',
         'sync_html_shutter_documents','audit_html_shutter_release','publish_html_shutter','probe_openfilm_shutter',
         'materialize_regression_fixtures','run_with_regression_fixtures')
BASE_FILES={'product/src/ai_ad_editor/'+name for name in ('cli.py','capabilities.py','html_motion.py','html_shutter.py',
    'html_motion_worker.mjs','schema_contract.py','agent-project.schema.json')}
BASE_FILES|={'product/tests/test_html_shutter.py','docs/specs/agent-project.schema.json',
             *(f'skills/{name}/SKILL.md' for name in ('video-cut-agent-editor','video-cut-quality','video-cut-timeline')),
             *(f'scripts/{name}.py' for name in SCRIPTS),*(p.relative_to(ROOT).as_posix() for p in (REPORT,CONTRACT,RESEARCH))}


def sha(path):return 'sha256:'+hashlib.sha256(path.read_bytes()).hexdigest()
def read(path):return json.loads(path.read_bytes())
def save(path,data):path.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n')
def git(root,*argv):return subprocess.run(['git',*argv],cwd=root,check=True,capture_output=True).stdout
def changed(root):return sorted(x.decode('utf8') for x in git(root,'ls-files','-m','-o','--exclude-standard','-z').split(b'\0') if x)


def source_files():
    names=set(BASE_FILES)
    for folder in (*ASSETS,REL,R10):
        for path in (ROOT/folder).rglob('*'):
            if path.is_file() and path.relative_to(ROOT).as_posix() not in DYNAMIC:names.add(path.relative_to(ROOT).as_posix())
    assert not names.intersection(FUTURE),'choose fresh publication evidence'
    return sorted(names)


def prepare(work):
    assert ROOT!=MAIN and git(ROOT,'branch','--show-current').strip()==b'work/html-shutter-sampling'
    assert git(MAIN,'branch','--show-current').strip()==b'main' and git(MAIN,'remote','get-url','origin').decode().strip()==REMOTE
    current=frozen();assert len(current)==218
    for name in ('focus-r3.json','native-r2/verification.json','installed-r1/verification.json','default-compat-r1/verification.json','media-inventory-r1.json'):
        value=read(BASE/name);assert value['frozen_equal'] and value['frozen_before']==value['frozen_after']==current
        assert value.get('status','passed')=='passed'
    work.mkdir(parents=True,exist_ok=False);paths=source_files()
    save(work/'reviewed-inputs.json',{'prepared_at_utc':datetime.now(timezone.utc).isoformat(),'source_root':str(ROOT),
        'source_branch':'work/html-shutter-sampling','source_files':{name:sha(ROOT/name) for name in paths},'frozen_inputs':current,
        'scope':'V72 source and evidence; isolated 218-source/5-fixture full regression; ordinary main push; retain V71'})
    print(json.dumps({'status':'prepared','static_files':len(paths),'frozen_inputs':218,'force_push':False}))


def guard(work):
    value=read(work/'reviewed-inputs.json');assert value['source_root']==str(ROOT)
    assert frozen()==value['frozen_inputs'] and source_files()==sorted(value['source_files'])
    for name,digest in value['source_files'].items():assert sha(ROOT/name)==digest,'reviewed bytes changed: '+name
    return value


def main_frozen():
    spec=importlib.util.spec_from_file_location('_shutter_main_frozen',MAIN/'scripts/run_frozen_regression.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module.frozen()


def run(work,previous_run,wait_seconds):
    lock=os.open(work/'runner.lock',os.O_CREAT|os.O_EXCL|os.O_WRONLY);os.write(lock,str(os.getpid()).encode());os.close(lock)
    record={'status':'waiting_existing_runs','started_at_utc':datetime.now(timezone.utc).isoformat(),
            'pid':os.getpid(),'previous_run':str(previous_run),'calls':[],'force_push':False,'goal_complete':False}
    def command(label,argv,timeout=240):
        argv=list(map(str,argv));out=work/(label+'.stdout.log');err=work/(label+'.stderr.log')
        with out.open('wb') as stdout,err.open('wb') as stderr:result=subprocess.run(argv,cwd=MAIN,stdout=stdout,stderr=stderr,timeout=timeout)
        record['calls'].append({'label':label,'command':argv,'exit_code':result.returncode,'stdout_sha256':sha(out),'stderr_sha256':sha(err)})
        save(work/'run.json',record)
        if result.returncode:raise RuntimeError(label+' failed; retained native logs')
        return out.read_bytes()
    try:
        reviewed=guard(work);deadline=time.monotonic()+wait_seconds
        while True:
            try:
                previous=read(previous_run) if previous_run.exists() else {'status':'not_started'}
                full=read(BASE/'full-r1.json')
            except json.JSONDecodeError:
                time.sleep(3);continue
            assert previous['status']!='stopped_for_review','previous publisher stopped; preserve main'
            if 'exit_code' in full:assert full['exit_code']==0 and full['terminal_ok'],'V72 complete regression failed'
            if previous['status']=='pushed' and full.get('status')=='passed':break
            if time.monotonic()>deadline:raise TimeoutError('existing gates not terminal; no publication')
            record['last_wait_at_utc']=datetime.now(timezone.utc).isoformat();save(work/'run.json',record);time.sleep(15)
        assert full['methods']==1610 and full['skipped']==0 and full['frozen_equal']
        assert full['frozen_before']==full['frozen_after']==reviewed['frozen_inputs']
        assert full['external_fixtures_equal'] and full['external_fixture_count']==5 and full['external_fixture_manifest_unchanged'] and full['verification_scripts_equal']
        assert sha(BASE/'full-r1.log')==full['log_sha256'];guard(work)
        assert git(MAIN,'branch','--show-current').strip()==b'main' and git(MAIN,'remote','get-url','origin').decode().strip()==REMOTE
        assert git(MAIN,'rev-parse','HEAD').decode().strip()==previous['commit'] and not changed(MAIN) and not git(MAIN,'diff','--cached','--name-only')
        assert git(MAIN,'ls-remote','--exit-code','origin','refs/heads/main').decode().split()[0]==previous['commit']
        previous_full=read(MAIN/PREVIOUS_REL/'full-r2.json')
        assert previous_full['terminal_ok'] and previous_full['methods']==1589 and main_frozen()==previous_full['frozen_after']
        for name,expected in full['external_fixtures_after'].items():
            path=MAIN/name;assert path.stat().st_size==expected['bytes'] and sha(path)==expected['sha256']
        for folder in (*ASSETS,REL,R10):assert not (MAIN/folder).exists(),'target already present: '+folder
        record['status']='copying_reviewed_v72';save(work/'run.json',record)
        names=sorted(set(reviewed['source_files'])|DYNAMIC)
        for name in names:
            source,target=ROOT/name,MAIN/name;assert not source.is_symlink()
            target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(source,target);assert sha(source)==sha(target)
        assert main_frozen()==reviewed['frozen_inputs'];guard(work)
        save(MAIN/REL/'publication-copy-r1.json',{'status':'passed','copied_at_utc':datetime.now(timezone.utc).isoformat(),
             'source_root':str(ROOT),'source_branch':reviewed['source_branch'],'main_parent_commit':previous['commit'],
             'source_guard_sha256':sha(work/'reviewed-inputs.json'),'full_regression_location':'isolated branch',
             'all_218_relative_path_bytes_equal':True,'all_5_external_fixture_bytes_equal':True,
             'full_regression_sha256':sha(BASE/'full-r1.json'),'initially_copied_files':{name:sha(MAIN/name) for name in names},
             'shared_documents_regenerated_after_copy':True,'goal_complete':False,'force_push':False})
        path=MAIN/'.gitattributes';text=path.read_text(encoding='utf8');assert '# V72 HTML subframe shutter' not in text
        text+='\n# V72 HTML subframe shutter: preserve raw native evidence and media.\n'
        for folder in (*ASSETS,REL,R10):text+=folder+'/** -text -whitespace\n'
        for p in (REPORT,CONTRACT,RESEARCH):text+=p.relative_to(ROOT).as_posix()+' text eol=lf\n'
        path.write_text(text,encoding='utf8',newline='\n')
        prefix=[sys.executable,'-B','-X','utf8'];record['status']='checking_v72_delivery';save(work/'run.json',record)
        command('audit-skills',[*prefix,MAIN/'scripts/audit_source_edit_skills.py','--expected-count','17','--output',MAIN/REL/'skills-r1.json'])
        command('sync-documents',[*prefix,MAIN/'scripts/sync_html_shutter_documents.py'])
        command('audit-release',[*prefix,MAIN/'scripts/audit_html_shutter_release.py','--output',MAIN/REL/'release-r1.json'])
        allowed=set(names)|set(DOCUMENTS)|FUTURE|{'.gitattributes','video-cut-install-manifest.json','docs/OpenFilm最新复用评估与成本取舍_2026-10-20.md'}
        modified=changed(MAIN);assert set(modified)<=allowed,'unexpected main path changes'
        assert main_frozen()==full['frozen_after']
        paths=work/'stage-paths.nul';paths.write_bytes(b''.join(n.encode('utf8')+b'\0' for n in modified))
        command('stage-reviewed',['git','add','-A','--pathspec-from-file='+str(paths),'--pathspec-file-nul'])
        before=set(git(MAIN,'diff','--cached','--name-only','-z').split(b'\0'))-{b''}
        command('verify-staged',[*prefix,MAIN/'scripts/verify_staged_release.py','--full',MAIN/REL/'full-r1.json','--output',MAIN/REL/'staged-r1.json'])
        command('stage-receipt',['git','add','--',REL+'/staged-r1.json'])
        after=set(git(MAIN,'diff','--cached','--name-only','-z').split(b'\0'))-{b''}
        assert after==before|{(REL+'/staged-r1.json').encode('utf8')}
        assert git(MAIN,'cat-file','blob',':'+REL+'/staged-r1.json')==(MAIN/REL/'staged-r1.json').read_bytes()
        command('ensure-no-unstaged',['git','diff','--quiet']);command('check-whitespace',['git','diff','--cached','--check'])
        assert main_frozen()==full['frozen_after'];record['status']='committing';save(work/'run.json',record)
        command('commit',['git','-c','gc.auto=0','-c','maintenance.auto=false','commit','--quiet','-m',
                         'feat: add deterministic HTML subframe shutter with premultiplied alpha'])
        head=git(MAIN,'rev-parse','HEAD').decode().strip()
        remote=command('remote-after-hook',['git','ls-remote','--exit-code','origin','refs/heads/main']).decode().split()[0]
        if remote!=head:
            command('ordinary-push',['git','push','origin','main'])
            remote=command('remote-after-push',['git','ls-remote','--exit-code','origin','refs/heads/main']).decode().split()[0]
        assert remote==head and not changed(MAIN)
        record.update(status='pushed',commit=head,remote_main=remote,full_methods=1610,staged_files=len(after))
    except Exception as exc:
        record.update(status='stopped_for_review',error=type(exc).__name__+': '+str(exc));raise
    finally:
        record['finished_at_utc']=datetime.now(timezone.utc).isoformat();save(work/'run.json',record)
    print(json.dumps({key:record[key] for key in ('status','commit','full_methods','force_push')}))


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--work',type=Path,required=True)
    group=parser.add_mutually_exclusive_group(required=True)
    for name in ('prepare','check','run'):group.add_argument('--'+name,action='store_true')
    parser.add_argument('--previous-run',type=Path);parser.add_argument('--wait-seconds',type=int,default=43200)
    args=parser.parse_args();work=args.work.resolve();assert work.is_relative_to(ROOT/'product/.runtime') and ROOT!=MAIN
    if args.prepare:prepare(work)
    elif args.check:guard(work);print(json.dumps({'status':'guard_passed'}))
    else:
        assert args.previous_run is not None
        run(work,args.previous_run.resolve(),args.wait_seconds)


if __name__=='__main__':main()
