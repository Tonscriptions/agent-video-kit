"""Finish the already authorized V70 update only after terminal frozen checks.

Prepare a reviewed-byte guard first. Run waits for the existing full regression;
it never starts another suite, installs a model, changes sampling, or force pushes.
Unexpected local/remote changes stop publication for review.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

from run_frozen_regression import frozen

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'docs/validation/evidence/openfilm-batch-reuse-20261020-v70'
REMOTE='git@github.com:Tonscriptions/agent-video-kit.git'
from sync_queue_reuse_documents import DOCUMENTS as COMMON_DOCUMENTS, REPORT, CONTRACT
DOCUMENTS=[*COMMON_DOCUMENTS,'video-cut-install-manifest.json',
    REPORT.relative_to(ROOT).as_posix(),CONTRACT.relative_to(ROOT).as_posix(),
    'docs/OpenFilm最新复用评估与成本取舍_2026-10-20.md']
FUTURE={str((BASE/n).relative_to(ROOT)).replace('\\','/') for n in ('release-r1.json','staged-r1.json')}
DYNAMIC={str((BASE/n).relative_to(ROOT)).replace('\\','/') for n in ('full-r1.json','full-r1.log')}
KNOWN=set(DOCUMENTS)|{'.gitattributes',
    'skills/video-cut-agent-editor/SKILL.md','skills/video-cut-project-ops/SKILL.md',
    'product/tests/test_queue_reuse.py'}
KNOWN.update('product/src/ai_ad_editor/'+n+'.py' for n in ('capabilities','cli','queue_reuse'))
KNOWN.update('scripts/'+n+'.py' for n in ('smoke_queue_reuse','verify_queue_reuse_install',
    'probe_queue_reuse_container','audit_queue_reuse_media','sync_queue_reuse_documents',
    'audit_queue_reuse_release','finalize_queue_reuse'))


def in_scope(name):
    return (name in KNOWN or name.startswith(BASE.relative_to(ROOT).as_posix()+'/')
            or name.startswith('docs/assets/openfilm-batch-reuse-20261020-v70-'))


def sha(path):return 'sha256:'+hashlib.sha256(path.read_bytes()).hexdigest()
def read(path):return json.loads(path.read_bytes())
def save(path,value):path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n')


def git(*args):
    return subprocess.check_output(['git',*args],cwd=ROOT)


def changed():
    raw=git('status','--porcelain=v1','--untracked-files=all','-z')
    rows=[r for r in raw.split(b'\0') if r];names=[]
    for row in rows:
        assert row[:2] in (b' M',b'??',b'A ',b'M '),row[:2]
        name=row[3:].decode('utf8');assert '\n' not in name and '\r' not in name
        names.append(name)
    return sorted(names)


def ensure_repository():
    assert git('branch','--show-current').strip()==b'main'
    assert git('remote','get-url','origin').decode().strip()==REMOTE


def prepare(work):
    ensure_repository();assert not git('diff','--cached','--name-only')
    work.mkdir(parents=True,exist_ok=False);names=changed()
    assert names and not FUTURE.intersection(names)
    assert all(in_scope(n) for n in names),'unreviewed paths outside V70 scope'
    static={n:sha(ROOT/n) for n in set(names)|set(DOCUMENTS) if n not in DYNAMIC}
    receipt={'prepared_at_utc':datetime.now(timezone.utc).isoformat(),
        'base_commit':git('rev-parse','HEAD').decode().strip(),'dirty_names':names,
        'reviewed_static_bytes':static,'frozen_inputs':frozen(),
        'scope':'only existing V70 changes, terminal full/native/container/install receipts, reviewed docs, then ordinary main push'}
    save(work/'reviewed-inputs.json',receipt)
    print(json.dumps({'status':'prepared','static_files':len(static),'dirty_paths':len(names),
        'frozen_inputs':len(receipt['frozen_inputs']),'force_push':False}))


def guard(work):
    value=read(work/'reviewed-inputs.json');ensure_repository()
    assert git('rev-parse','HEAD').decode().strip()==value['base_commit'],'HEAD changed'
    assert not git('diff','--cached','--name-only'),'index changed'
    assert changed()==value['dirty_names'],'dirty path set changed'
    for name,digest in value['reviewed_static_bytes'].items():
        assert sha(ROOT/name)==digest,'reviewed bytes changed: '+name
    assert frozen()==value['frozen_inputs'],'runtime/test/schema bytes changed'
    return value


def run(work,wait_seconds):
    exclusive=os.open(work/'runner.lock',os.O_CREAT|os.O_EXCL|os.O_WRONLY)
    os.write(exclusive,str(os.getpid()).encode('ascii'));os.close(exclusive)
    calls=[];record={'status':'waiting_full','started_at_utc':datetime.now(timezone.utc).isoformat(),
        'pid':os.getpid(),'calls':calls,'force_push':False}
    save(work/'run.json',record)

    def command(values,label,timeout=180):
        values=list(map(str,values));result=subprocess.run(values,cwd=ROOT,capture_output=True,timeout=timeout)
        out=work/(label+'.stdout.log');err=work/(label+'.stderr.log')
        out.write_bytes(result.stdout);err.write_bytes(result.stderr)
        calls.append({'name':label,'command':values,'exit_code':result.returncode,
            'stdout':out.name,'stderr':err.name,'stdout_sha256':sha(out),'stderr_sha256':sha(err)})
        save(work/'run.json',record)
        if result.returncode:raise RuntimeError(label+' failed; retained logs in '+str(work))
        return result.stdout

    try:
        reviewed=guard(work);deadline=time.monotonic()+wait_seconds
        while True:
            try:full=read(BASE/'full-r1.json')
            except json.JSONDecodeError:full={}
            if 'exit_code' in full:break
            if time.monotonic()>deadline:raise TimeoutError('existing full regression is not terminal; no publication')
            record['last_wait_at_utc']=datetime.now(timezone.utc).isoformat();save(work/'run.json',record)
            time.sleep(15)
        assert full['exit_code']==0 and full['terminal_ok'] and full['skipped']==0 and full['methods']==1564
        assert full['frozen_equal'] and full['frozen_before']==full['frozen_after']==reviewed['frozen_inputs']
        guard(work)
        remote=command(['git','ls-remote','--exit-code','origin','refs/heads/main'],'remote-before').decode().split()[0]
        assert remote==reviewed['base_commit'],'remote main changed; no overwrite/rebase/force push'
        record['status']='checking_delivery';save(work/'run.json',record)
        prefix=[sys.executable,'-B','-X','utf8']
        command([*prefix,ROOT/'scripts/sync_queue_reuse_documents.py'],'sync-documents')
        command([*prefix,ROOT/'scripts/audit_queue_reuse_release.py',
            '--output',BASE/'release-r1.json'],'audit-release')
        names=changed();allowed=set(reviewed['dirty_names'])|set(DOCUMENTS)|FUTURE
        assert set(names)<=allowed,'unexpected paths after delivery checks'
        assert frozen()==reviewed['frozen_inputs'],'source changed after delivery checks'
        paths=work/'stage-paths.nul';paths.write_bytes(b''.join(n.encode('utf8')+b'\0' for n in names))
        command(['git','add','-A','--pathspec-from-file='+str(paths),'--pathspec-file-nul'],'stage-reviewed-paths')
        staged_before={n.decode('utf8') for n in git('diff','--cached','--name-only','-z').split(b'\0') if n}
        command([*prefix,ROOT/'scripts/verify_staged_release.py','--full',BASE/'full-r1.json',
            '--output',BASE/'staged-r1.json'],'verify-staged')
        staged_path=(BASE/'staged-r1.json').relative_to(ROOT).as_posix()
        command(['git','add','--',staged_path],'stage-integrity-receipt')
        staged_after={n.decode('utf8') for n in git('diff','--cached','--name-only','-z').split(b'\0') if n}
        assert staged_after==staged_before|{staged_path}
        assert git('cat-file','blob',':'+staged_path)==(ROOT/staged_path).read_bytes()
        command(['git','diff','--quiet'],'ensure-no-unstaged-changes')
        command(['git','diff','--cached','--check'],'check-staged-whitespace')
        assert frozen()==full['frozen_after']
        record['status']='committing';save(work/'run.json',record)
        command(['git','-c','gc.auto=0','-c','maintenance.auto=false','commit','--quiet','-m',
            'feat: reuse identical successful renders within one local queue run'],'commit',timeout=240)
        head=git('rev-parse','HEAD').decode().strip()
        remote=command(['git','ls-remote','--exit-code','origin','refs/heads/main'],'remote-after-hook').decode().split()[0]
        if remote!=head:
            command(['git','push','origin','main'],'ordinary-push',timeout=240)
            remote=command(['git','ls-remote','--exit-code','origin','refs/heads/main'],'remote-after-push').decode().split()[0]
        assert remote==head and not changed()
        record.update(status='pushed',commit=head,remote_main=remote,full_methods=1564,
            staged_files=len(staged_after),goal_complete=False)
    except Exception as exc:
        record.update(status='stopped_for_review',error=type(exc).__name__+': '+str(exc))
        raise
    finally:
        record['finished_at_utc']=datetime.now(timezone.utc).isoformat();save(work/'run.json',record)
    print(json.dumps({k:record[k] for k in ('status','commit','remote_main','full_methods','staged_files','goal_complete')}))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--work',type=Path,required=True)
    modes=parser.add_mutually_exclusive_group(required=True)
    modes.add_argument('--prepare',action='store_true');modes.add_argument('--check',action='store_true');modes.add_argument('--run',action='store_true')
    parser.add_argument('--wait-seconds',type=int,default=7200)
    args=parser.parse_args();work=args.work.resolve()
    assert work.is_relative_to(ROOT/'product/.runtime')
    if args.prepare:prepare(work)
    elif args.check:
        value=guard(work);print(json.dumps({'status':'guard_passed','static_files':len(value['reviewed_static_bytes'])}))
    else:run(work,args.wait_seconds)


if __name__=='__main__':main()
