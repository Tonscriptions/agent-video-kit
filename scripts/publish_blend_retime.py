"""Publish reviewed V74 bytes after the existing full regression terminates."""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import time
from run_frozen_regression import frozen
from sync_blend_retime_documents import CONTRACT,DOCUMENTS,REL,REPORT,ROOT
from audit_blend_retime_release import SCRIPTS,SKILLS

MAIN=Path('E:/dev/sandbox/AI广告剪辑')
BASE_COMMIT='2e3fa5ff5c58be52c2f48fe28332c83e2be22e31'
REMOTE='git@github.com:Tonscriptions/agent-video-kit.git'
MODULES=('blend_automation.py','capabilities.py','convert.py','edit_planner.py','effect_automation.py',
    'render.py','retime_edits.py','schema_contract.py','validator.py','agent-project.schema.json')
TESTS=('test_blend_retime.py','test_retime_edits.py')
CORE=set(DOCUMENTS)|{'.gitattributes',CONTRACT.relative_to(ROOT).as_posix(),REPORT.relative_to(ROOT).as_posix(),
    'docs/specs/agent-project.schema.json','docs/specs/完整作者输出变速与磁吸联动契约_v0.1_2026-10-18.md',
    'docs/assets/retime-blend-20261020-v74-LICENSE.txt'}
CORE.update('product/src/ai_ad_editor/'+name for name in MODULES)
CORE.update('product/tests/'+name for name in TESTS)
CORE.update('skills/'+name+'/SKILL.md' for name in SKILLS)
CORE.update('scripts/'+name+'.py' for name in SCRIPTS)
DYNAMIC={REL+'/'+name for name in ('full-r2.json','full-r2.log','full-r2.source.json','full-r2.source.log')}
GENERATED={REL+'/'+name for name in ('skills-r1.json','release-r1.json','staged-r1.json','publication-copy-r1.json')}


def sha(path):return 'sha256:'+hashlib.sha256(Path(path).read_bytes()).hexdigest()
def read(path):return json.loads(Path(path).read_bytes())
def save(path,value):path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n')
def git(root,*arguments):return subprocess.run(['git',*arguments],cwd=root,check=True,capture_output=True).stdout


def reviewed_files():
    paths=set(CORE)
    paths.update(p.relative_to(ROOT).as_posix() for p in (ROOT/REL).rglob('*') if p.is_file())
    for directory in (ROOT/'docs/assets').glob('retime-blend-20261020-v74-*'):
        if directory.is_dir():paths.update(p.relative_to(ROOT).as_posix() for p in directory.rglob('*') if p.is_file())
    paths-=DYNAMIC|GENERATED
    for name in paths:
        path=ROOT/name;assert path.is_file() and not path.is_symlink(),name
    changed={raw.decode('utf8') for raw in git(ROOT,'diff','--name-only','-z',BASE_COMMIT).split(b'\0') if raw}
    changed.update(raw.decode('utf8') for raw in git(ROOT,'ls-files','--others','--exclude-standard','-z').split(b'\0') if raw)
    assert changed<=paths|DYNAMIC|GENERATED,sorted(changed-paths-DYNAMIC-GENERATED)
    return {name:sha(ROOT/name) for name in sorted(paths)}


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--work',type=Path,required=True)
    parser.add_argument('--preflight-only',action='store_true');parser.add_argument('--wait-seconds',type=int,default=43200)
    args=parser.parse_args();work=args.work.resolve();assert work.is_relative_to(MAIN/'product/.runtime') and not work.exists();work.mkdir(parents=True)
    record={'status':'preflight','started_at_utc':datetime.now(timezone.utc).isoformat(),'generator_sha256':sha(__file__),
        'base_commit':BASE_COMMIT,'source':str(ROOT),'main':str(MAIN),'network_scope':'authorized ordinary Git main push only',
        'force_push':False,'calls':[]}
    def run(label,command,cwd=MAIN,timeout=1800):
        command=list(map(str,command));out=work/(label+'.stdout.log');err=work/(label+'.stderr.log')
        assert not out.exists() and not err.exists()
        with out.open('wb') as stdout,err.open('wb') as stderr:
            result=subprocess.run(command,cwd=cwd,stdout=stdout,stderr=stderr,timeout=timeout)
        record['calls'].append({'label':label,'command':command,'exit_code':result.returncode,'stdout_sha256':sha(out),'stderr_sha256':sha(err)})
        save(work/'run.json',record);assert result.returncode==0,label+'; original native logs retained'
        return out.read_bytes()
    try:
        assert ROOT.resolve()!=MAIN.resolve() and ROOT.resolve().is_relative_to(MAIN/'product/.runtime/worktrees')
        assert git(ROOT,'branch','--show-current').decode().strip()=='work/retime-blend-clock'
        assert git(ROOT,'rev-parse','HEAD').decode().strip()==BASE_COMMIT
        assert git(MAIN,'branch','--show-current').decode().strip()=='main'
        assert git(MAIN,'remote','get-url','origin').decode().strip()==REMOTE
        assert git(MAIN,'rev-parse','HEAD').decode().strip()==BASE_COMMIT
        assert not git(MAIN,'status','--porcelain','-z'),'main has local changes before publication'
        reviewed=reviewed_files();expected=read(ROOT/REL/'targeted-r7.json')['frozen_after'];assert expected==frozen()
        for name in ('native-r3','installed-r2','installed-r2/media'):
            value=read(ROOT/REL/name/'verification.json');assert value['status']=='passed' and value['frozen_equal']
            assert value['frozen_after']==expected
        assert read(ROOT/REL/'candidate-release-r1.json')['status']=='passed-candidate-audit'
        record.update(status='preflight_passed',reviewed_files=reviewed,frozen_inputs=expected);save(work/'run.json',record)
        print(json.dumps({'status':'preflight_passed','reviewed_files':len(reviewed),'frozen_inputs':len(expected)}),flush=True)
        if args.preflight_only:return
        record['status']='waiting_for_existing_full_regression';save(work/'run.json',record)
        deadline=time.monotonic()+args.wait_seconds
        while True:
            assert time.monotonic()<deadline,'full regression wait deadline reached; no publication performed'
            try:full=read(ROOT/REL/'full-r2.json')
            except (json.JSONDecodeError,OSError):time.sleep(10);continue
            if full.get('status')=='failed':raise RuntimeError('existing full regression failed; no publication performed')
            if full.get('status')=='passed':break
            time.sleep(15)
        assert full['terminal_ok'] and full['exit_code']==0 and full['source_suite_exit_code']==0
        assert full['methods']==1667 and full['skipped']==0 and full['frozen_equal']
        assert full['frozen_before']==full['frozen_after']==expected==frozen()
        assert full['external_fixtures_equal'] and full['external_fixture_count']==8 and full['external_fixture_manifest_unchanged'] and full['verification_scripts_equal']
        assert reviewed_files()==reviewed,'reviewed source bytes changed during regression'
        assert git(MAIN,'rev-parse','HEAD').decode().strip()==BASE_COMMIT
        assert not git(MAIN,'status','--porcelain','-z'),'main changed while waiting'
        remote_before=git(MAIN,'ls-remote','origin','refs/heads/main').decode().split()[0]
        assert remote_before==BASE_COMMIT,'remote main changed; publication requires a fresh rebase and checks'
        paths=set(reviewed)|DYNAMIC;copied=[]
        for name in sorted(paths):
            source=ROOT/name;target=MAIN/name
            assert source.is_file() and not source.is_symlink() and target.resolve().is_relative_to(MAIN.resolve())
            target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(source,target)
            assert source.read_bytes()==target.read_bytes();copied.append({'path':name,'sha256':sha(target)})
        main_frozen={name:sha(MAIN/name) for name in expected};assert main_frozen==expected
        for name,row in full['external_fixtures_expected'].items():assert (MAIN/name).stat().st_size==row['bytes'] and sha(MAIN/name)==row['sha256']
        base=MAIN/REL
        run('skills',[sys.executable,'-E','-B','-X','utf8',MAIN/'scripts/audit_source_edit_skills.py',
            '--expected-count','17','--output',base/'skills-r1.json'])
        audit=read(base/'skills-r1.json');mapping_path=MAIN/'video-cut-install-manifest.json';mapping=read(mapping_path)
        old=mapping['current_audit'];history=mapping.setdefault('audit_history',[])
        if old not in history:history.append(old)
        for item in mapping['skills']:
            row=next(x for x in audit['results'] if x['skill']==item['name']);previous=item['skill_md_sha256'];current_hash=row['sha256'][7:]
            if previous!=current_hash:
                item.setdefault('skill_md_sha256_history',[]).append(previous);item['previous_manifest_skill_md_sha256']=previous
            item.update(skill_md_sha256=current_hash,validation=row['validator_stdout'],prefix_verified=True,registration_verified=True)
            assert Path(item['canonical_directory']).resolve()==(MAIN/'skills'/item['name']).resolve()
        mapping['current_audit']={'date':'2026-10-20','skill_count':17,'local_links_checked':audit['local_links_checked'],
            'record':REL+'/skills-r1.json','record_sha256':sha(base/'skills-r1.json'),'previous_hashes_preserved':True,
            'semantics':'V74 external blend author clocks and floating-point synthetic silence; 4 Skill updates; no natural quality, HDR or complete CapCut parity acceptance'}
        save(mapping_path,mapping)
        run('documents',[sys.executable,'-E','-B','-X','utf8',MAIN/'scripts/sync_blend_retime_documents.py'])
        run('release-audit',[sys.executable,'-E','-B','-X','utf8',MAIN/'scripts/audit_blend_retime_release.py','--output',base/'release-r1.json'])
        save(base/'publication-copy-r1.json',{'status':'passed','source_base_commit':BASE_COMMIT,'source_directory':str(ROOT),
            'copied_files':copied,'frozen_input_count':len(expected),'all_frozen_bytes_equal_source_regression':main_frozen==expected,
            'external_fixture_count':8,'all_external_fixture_bytes_equal_regression':True,
            'generated_on_main':['video-cut-install-manifest.json',*DOCUMENTS,CONTRACT.relative_to(ROOT).as_posix(),REPORT.relative_to(ROOT).as_posix(),
                REL+'/skills-r1.json',REL+'/release-r1.json'],'copy_generator_sha256':sha(__file__),'full_regression_sha256':sha(base/'full-r2.json')})
        stage=sorted(paths|GENERATED|{'video-cut-install-manifest.json'});stage.remove(REL+'/staged-r1.json')
        for offset in range(0,len(stage),40):
            batch=stage[offset:offset+40]
            run('stage-'+str(offset//40),['git','add','--',*batch])
            run('normalize-stage-'+str(offset//40),['git','add','--renormalize','--',*batch])
        run('staged-audit',[sys.executable,'-E','-B','-X','utf8',MAIN/'scripts/verify_staged_release.py',
            '--full',base/'full-r2.json','--output',base/'staged-r1.json'])
        run('stage-proof',['git','add','--',REL+'/staged-r1.json'])
        assert git(MAIN,'cat-file','blob',':'+REL+'/staged-r1.json')==(base/'staged-r1.json').read_bytes()
        assert not git(MAIN,'diff','--name-only'),'unstaged tracked changes before commit'
        run('whitespace',['git','diff','--cached','--check'])
        run('commit',['git','-c','gc.auto=0','-c','maintenance.auto=false','commit','--quiet','-m',
            'feat: preserve animated external blends through relative retiming'])
        commit=git(MAIN,'rev-parse','HEAD').decode().strip();remote=git(MAIN,'ls-remote','origin','refs/heads/main').decode().split()[0]
        if remote!=commit:
            run('ordinary-push',['git','push','origin','main']);remote=git(MAIN,'ls-remote','origin','refs/heads/main').decode().split()[0]
        assert remote==commit and git(MAIN,'branch','--show-current').decode().strip()=='main'
        assert not git(MAIN,'status','--porcelain','-z'),'main not clean after publication'
        record.update(status='published',commit=commit,remote_main=remote,full_methods=full['methods'],full_seconds=full['suite_seconds'],
            frozen_input_count=len(expected),skill_count=17,skill_local_links=audit['local_links_checked'],main_clean=True)
    except BaseException as exc:
        record.update(status='failed',error={'type':type(exc).__name__,'message':str(exc)});raise
    finally:
        record['finished_at_utc']=datetime.now(timezone.utc).isoformat();save(work/'run.json',record)
    print(json.dumps({k:record[k] for k in ('status','commit','remote_main','full_methods','frozen_input_count','main_clean')}),flush=True)


if __name__=='__main__':main()
