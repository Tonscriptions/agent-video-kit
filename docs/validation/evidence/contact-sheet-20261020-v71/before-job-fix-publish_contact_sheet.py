"""Publish reviewed V71 bytes after existing V70 and isolated V71 runs finish.

This does not launch a regression, fetch dependencies, retarget Skills, reset a
checkout, force push or change any model. It waits for already-running gates.
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
from sync_contact_sheet_documents import DOCUMENTS,REPORT,CONTRACT

ROOT=Path(__file__).resolve().parents[1]
MAIN=Path('E:/dev/sandbox/AI广告剪辑')
REL='docs/validation/evidence/contact-sheet-20261020-v71'
ASSETS=('docs/assets/contact-sheet-20261020-v71-native-r1',
        'docs/assets/contact-sheet-20261020-v71-installed-r1')
DYNAMIC={REL+'/full-r1.json',REL+'/full-r1.log'}
FUTURE={REL+'/skills-r1.json',REL+'/release-r1.json',REL+'/staged-r1.json',REL+'/publication-copy-r1.json'}
REMOTE='git@github.com:Tonscriptions/agent-video-kit.git'
V70_RUN=MAIN/'product/.runtime/openfilm-batch-reuse-20261020-v70/finalization-r2/run.json'
SCRIPTS=('smoke_contact_sheet','verify_contact_sheet_install','audit_contact_sheet_media',
         'sync_contact_sheet_documents','audit_contact_sheet_release','publish_contact_sheet')
BASE_FILES={'product/src/ai_ad_editor/'+name+'.py' for name in ('cli','capabilities','contact_sheet')}
BASE_FILES|={'product/tests/test_contact_sheet.py','skills/video-cut-agent-editor/SKILL.md','skills/video-cut-quality/SKILL.md',
    REPORT.relative_to(ROOT).as_posix(),CONTRACT.relative_to(ROOT).as_posix()}
BASE_FILES|={'scripts/'+n+'.py' for n in SCRIPTS}


def sha(path):return 'sha256:'+hashlib.sha256(path.read_bytes()).hexdigest()
def read(path):return json.loads(path.read_bytes())
def save(path,value):path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n')
def git(root,*args):return subprocess.run(['git',*args],cwd=root,check=True,capture_output=True).stdout
def changed(root):return sorted(x.decode('utf8') for x in git(root,'ls-files','-m','-o','--exclude-standard','-z').split(b'\0') if x)


def source_files():
    names=set(BASE_FILES)
    for rel in (*ASSETS,REL):
        for path in (ROOT/rel).rglob('*'):
            if path.is_file():
                name=path.relative_to(ROOT).as_posix()
                if name not in DYNAMIC:names.add(name)
    assert not names.intersection(FUTURE), 'publication evidence must be new'
    return sorted(names)


def prepare(work):
    assert ROOT!=MAIN and git(ROOT,'branch','--show-current').strip()==b'work/openfilm-contact-sheet'
    assert git(MAIN,'branch','--show-current').strip()==b'main'
    assert git(MAIN,'remote','get-url','origin').decode().strip()==REMOTE
    v70=read(V70_RUN)
    assert v70['status'] in ('waiting_full','checking_delivery','committing','pushed')
    current=frozen();assert len(current)==216
    for rel in ('focus-r3.json','native-r1/verification.json','installed-r1/verification.json','media-inventory-r1.json'):
        value=read(ROOT/REL/rel);assert value['frozen_equal'] and value['frozen_after']==value['frozen_before']==current
    work.mkdir(parents=True,exist_ok=False)
    paths=source_files();receipt={'prepared_at_utc':datetime.now(timezone.utc).isoformat(),
        'source_root':str(ROOT),'main_root':str(MAIN),'source_branch':'work/openfilm-contact-sheet',
        'source_files':{name:sha(ROOT/name) for name in paths},'frozen_inputs':current,
        'main_base_before_v70':read(MAIN/'product/.runtime/openfilm-batch-reuse-20261020-v70/finalization-r1/reviewed-inputs.json')['base_commit'],
        'scope':'only V71 files; retain V70 publication; terminal isolated 216-byte-set regression; native install/media/Skills checks; ordinary main push'}
    save(work/'reviewed-inputs.json',receipt)
    print(json.dumps({'status':'prepared','static_files':len(paths),'frozen_inputs':216,'force_push':False}))


def guard(work):
    receipt=read(work/'reviewed-inputs.json');assert receipt['source_root']==str(ROOT)
    assert frozen()==receipt['frozen_inputs'] and source_files()==sorted(receipt['source_files'])
    for name,digest in receipt['source_files'].items():assert sha(ROOT/name)==digest,'reviewed bytes changed: '+name
    return receipt


def main_frozen():
    spec=importlib.util.spec_from_file_location('_contact_main_frozen',MAIN/'scripts/run_frozen_regression.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module.frozen()


def run(work,deadline_seconds):
    lock=os.open(work/'runner.lock',os.O_CREAT|os.O_EXCL|os.O_WRONLY);os.write(lock,str(os.getpid()).encode());os.close(lock)
    calls=[];record={'status':'waiting_existing_runs','started_at_utc':datetime.now(timezone.utc).isoformat(),
        'pid':os.getpid(),'calls':calls,'force_push':False,'goal_complete':False}
    def command(argv,label,timeout=180):
        argv=[str(x) for x in argv];out=work/(label+'.stdout.log');err=work/(label+'.stderr.log')
        with out.open('wb') as stdout,err.open('wb') as stderr:
            result=subprocess.run(argv,cwd=MAIN,stdout=stdout,stderr=stderr,timeout=timeout)
        calls.append({'label':label,'command':argv,'exit_code':result.returncode,'stdout_sha256':sha(out),'stderr_sha256':sha(err)})
        save(work/'run.json',record)
        if result.returncode:raise RuntimeError(label+' failed; retained native logs')
        return out.read_bytes()
    try:
        reviewed=guard(work);deadline=time.monotonic()+deadline_seconds
        while True:
            try:
                v70=read(V70_RUN)
                full=read(ROOT/REL/'full-r1.json')
            except json.JSONDecodeError:
                time.sleep(3);continue
            assert v70['status']!='stopped_for_review','V70 publisher stopped; do not alter main'
            if v70['status']=='pushed' and 'exit_code' in full:break
            if 'exit_code' in full:assert full['exit_code']==0 and full['terminal_ok'],'V71 full failed'
            if time.monotonic()>deadline:raise TimeoutError('existing runs not terminal; no publication')
            record['last_wait_at_utc']=datetime.now(timezone.utc).isoformat();save(work/'run.json',record);time.sleep(15)
        assert full['methods']==1589 and full['terminal_ok'] and full['exit_code']==0 and full['skipped']==0
        assert full['frozen_equal'] and full['frozen_after']==full['frozen_before']==reviewed['frozen_inputs']
        assert sha(ROOT/REL/'full-r1.log')==full['log_sha256'];guard(work)
        assert git(MAIN,'branch','--show-current').strip()==b'main'
        assert git(MAIN,'remote','get-url','origin').decode().strip()==REMOTE
        assert git(MAIN,'rev-parse','HEAD').decode().strip()==v70['commit']
        assert not changed(MAIN) and not git(MAIN,'diff','--cached','--name-only')
        assert git(MAIN,'ls-remote','--exit-code','origin','refs/heads/main').decode().split()[0]==v70['commit']
        previous=read(MAIN/'docs/validation/evidence/openfilm-batch-reuse-20261020-v70/full-r1.json')
        assert previous['terminal_ok'] and previous['methods']==1564 and main_frozen()==previous['frozen_after']
        assert previous['frozen_after']==previous['frozen_before'] and previous['frozen_equal']
        for rel in (*ASSETS,REL):assert not (MAIN/rel).exists(),'V71 target already present: '+rel
        record['status']='copying_reviewed_v71';save(work/'run.json',record)
        names=sorted(set(reviewed['source_files'])|DYNAMIC)
        for name in names:
            source,target=ROOT/name,MAIN/name;assert not source.is_symlink()
            target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(source,target);assert sha(source)==sha(target)
        assert main_frozen()==reviewed['frozen_inputs'];guard(work)
        copy_receipt={'status':'passed','copied_at_utc':datetime.now(timezone.utc).isoformat(),
            'source_root':str(ROOT),'source_branch':reviewed['source_branch'],'main_parent_commit':v70['commit'],
            'source_guard_sha256':sha(work/'reviewed-inputs.json'),'full_regression_location':'isolated branch',
            'all_216_relative_path_bytes_equal':True,'full_regression_sha256':sha(ROOT/REL/'full-r1.json'),
            'files':{name:sha(MAIN/name) for name in names},'goal_complete':False,'force_push':False}
        save(MAIN/REL/'publication-copy-r1.json',copy_receipt)
        attrs=MAIN/'.gitattributes';value=attrs.read_text(encoding='utf8');assert '# V71 native contact sheets' not in value
        value+='\n# V71 native contact sheets: preserve original native receipts and media bytes.\n'
        for rel in (*ASSETS,REL):value+=rel+'/** -text -whitespace\n'
        for path in (REPORT,CONTRACT):value+=path.relative_to(ROOT).as_posix()+' text eol=lf\n'
        attrs.write_text(value,encoding='utf8',newline='\n')
        prefix=[sys.executable,'-B','-X','utf8'];record['status']='checking_v71_delivery';save(work/'run.json',record)
        command([*prefix,MAIN/'scripts/audit_source_edit_skills.py','--expected-count','17','--output',MAIN/REL/'skills-r1.json'],'audit-skills')
        command([*prefix,MAIN/'scripts/sync_contact_sheet_documents.py'],'sync-documents')
        command([*prefix,MAIN/'scripts/audit_contact_sheet_release.py','--output',MAIN/REL/'release-r1.json'],'audit-release')
        allowed=set(names)|set(DOCUMENTS)|FUTURE|{'.gitattributes','video-cut-install-manifest.json','docs/OpenFilm最新复用评估与成本取舍_2026-10-20.md'}
        modified=changed(MAIN);assert set(modified)<=allowed,'unexpected main path changes'
        assert main_frozen()==full['frozen_after']
        paths=work/'stage-paths.nul';paths.write_bytes(b''.join(n.encode('utf8')+b'\0' for n in modified))
        command(['git','add','-A','--pathspec-from-file='+str(paths),'--pathspec-file-nul'],'stage-reviewed-paths')
        staged_before=set(git(MAIN,'diff','--cached','--name-only','-z').split(b'\0'))-{b''}
        command([*prefix,MAIN/'scripts/verify_staged_release.py','--full',MAIN/REL/'full-r1.json','--output',MAIN/REL/'staged-r1.json'],'verify-staged')
        command(['git','add','--',REL+'/staged-r1.json'],'stage-integrity-receipt')
        staged_after=set(git(MAIN,'diff','--cached','--name-only','-z').split(b'\0'))-{b''}
        assert staged_after==staged_before|{(REL+'/staged-r1.json').encode('utf8')}
        assert git(MAIN,'cat-file','blob',':'+REL+'/staged-r1.json')==(MAIN/REL/'staged-r1.json').read_bytes()
        command(['git','diff','--quiet'],'ensure-no-unstaged')
        command(['git','diff','--cached','--check'],'check-staged-whitespace');assert main_frozen()==full['frozen_after']
        record['status']='committing';save(work/'run.json',record)
        command(['git','-c','gc.auto=0','-c','maintenance.auto=false','commit','--quiet','-m',
            'feat: add native alpha contact sheets with actual frame anchors'],'commit',timeout=240)
        head=git(MAIN,'rev-parse','HEAD').decode().strip()
        remote=command(['git','ls-remote','--exit-code','origin','refs/heads/main'],'remote-after-hook').decode().split()[0]
        if remote!=head:
            command(['git','push','origin','main'],'ordinary-push',timeout=240)
            remote=command(['git','ls-remote','--exit-code','origin','refs/heads/main'],'remote-after-push').decode().split()[0]
        assert remote==head and not changed(MAIN)
        record.update(status='pushed',commit=head,remote_main=remote,full_methods=1589,staged_files=len(staged_after))
    except Exception as exc:
        record.update(status='stopped_for_review',error=type(exc).__name__+': '+str(exc));raise
    finally:
        record['finished_at_utc']=datetime.now(timezone.utc).isoformat();save(work/'run.json',record)
    print(json.dumps({k:record[k] for k in ('status','commit','remote_main','full_methods','goal_complete')}))


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--work',type=Path,required=True)
    mode=p.add_mutually_exclusive_group(required=True);mode.add_argument('--prepare',action='store_true');mode.add_argument('--check',action='store_true');mode.add_argument('--run',action='store_true')
    p.add_argument('--wait-seconds',type=int,default=10800);args=p.parse_args();work=args.work.resolve()
    assert work.is_relative_to(ROOT/'product/.runtime') and ROOT!=MAIN
    if args.prepare:prepare(work)
    elif args.check:guard(work);print(json.dumps({'status':'guard_passed'}))
    else:run(work,args.wait_seconds)


if __name__=='__main__':main()
