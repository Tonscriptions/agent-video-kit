"""Copy only reviewed V78 bytes to main after native regression, then ordinary push."""
from __future__ import annotations
import argparse
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import time
from run_frozen_regression import frozen
from sync_timeline_preview_documents import BASE,CONTRACT,DOCUMENTS,FOLLOWUPS,REL,REPORT,ROOT,SKILLS,SCRIPTS

MAIN=Path('E:/dev/sandbox/AI广告剪辑')
BASE_COMMIT='00b8a30f28b58f5edfd3f454bea0d6b514d26e2a'
REMOTE='git@github.com:Tonscriptions/agent-video-kit.git'
CORE=set(DOCUMENTS+FOLLOWUPS)|{'.gitattributes',CONTRACT.relative_to(ROOT).as_posix(),REPORT.relative_to(ROOT).as_posix()}
CORE.update('product/src/ai_ad_editor/'+name for name in ('preview.py','artifact_locks.py','cli.py','capabilities.py'))
CORE.add('product/tests/test_timeline_preview.py')
CORE.update('skills/'+s+'/SKILL.md' for s in SKILLS)
CORE.update('scripts/'+s+'.py' for s in SCRIPTS)
DYNAMIC={REL+'/'+name for name in ('full-r2.json','full-r2.log','full-r2.source.json','full-r2.source.log')}
GENERATED={REL+'/'+name for name in ('skills-r1.json','release-r1.json','publication-copy-r1.json','staged-r1.json')}

def sha(path):return 'sha256:'+hashlib.sha256(Path(path).read_bytes()).hexdigest()
def read(path):return json.loads(Path(path).read_bytes())
def save(path,value):path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n')
def git(root,*args):return subprocess.run(['git','-c','gc.auto=0','-c','maintenance.auto=false',*args],cwd=root,check=True,capture_output=True).stdout

def reviewed_files():
    paths=set(CORE)
    paths.update(p.relative_to(ROOT).as_posix() for p in BASE.rglob('*') if p.is_file())
    for d in (ROOT/'docs/assets').glob('timeline-preview-20261020-v78-*'):
        if d.is_dir():paths.update(p.relative_to(ROOT).as_posix() for p in d.rglob('*') if p.is_file())
    paths-=DYNAMIC|GENERATED
    for name in paths:
        p=ROOT/name;assert p.is_file() and not p.is_symlink(),name
    changed={s.decode('utf8') for s in git(ROOT,'diff','--name-only','-z',BASE_COMMIT).split(b'\0') if s}
    changed.update(s.decode('utf8') for s in git(ROOT,'ls-files','--others','--exclude-standard','-z').split(b'\0') if s)
    assert changed<=paths|DYNAMIC|GENERATED,sorted(changed-paths-DYNAMIC-GENERATED)
    return {name:sha(ROOT/name) for name in sorted(paths)}

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--work',type=Path,required=True)
    parser.add_argument('--wait-seconds',type=int,default=0,help='wait for the already running frozen suite; never restart it')
    parser.add_argument('--preflight-only',action='store_true');args=parser.parse_args();work=args.work.resolve()
    assert work.is_relative_to(MAIN/'product/.runtime') and not work.exists();work.mkdir(parents=True)
    record={'status':'preflight','started_at_utc':datetime.now(timezone.utc).isoformat(),'generator_sha256':sha(__file__),
        'base_commit':BASE_COMMIT,'source':str(ROOT),'main':str(MAIN),'force_push':False,
        'network_scope':'authorized ordinary Git main push only','calls':[]}
    def run(label,command,cwd=MAIN,timeout=1800):
        command=list(map(str,command))
        if command[0]=='git':command=['git','-c','gc.auto=0','-c','maintenance.auto=false',*command[1:]]
        out=work/(label+'.stdout.log');err=work/(label+'.stderr.log');assert not out.exists() and not err.exists()
        with out.open('wb') as stdout,err.open('wb') as stderr:
            result=subprocess.run(command,cwd=cwd,stdout=stdout,stderr=stderr,timeout=timeout)
        record['calls'].append({'label':label,'command':command,'exit_code':result.returncode,'stdout_sha256':sha(out),'stderr_sha256':sha(err)})
        save(work/'run.json',record);assert result.returncode==0,label+'; original logs retained'
        return out.read_bytes()
    try:
        assert ROOT!=MAIN and ROOT.is_relative_to(MAIN/'product/.runtime/worktrees')
        assert git(ROOT,'branch','--show-current').decode().strip()=='work/timeline-preview'
        assert git(ROOT,'rev-parse','HEAD').decode().strip()==BASE_COMMIT
        assert git(MAIN,'branch','--show-current').decode().strip()=='main'
        assert git(MAIN,'remote','get-url','origin').decode().strip()==REMOTE
        assert git(MAIN,'rev-parse','HEAD').decode().strip()==BASE_COMMIT
        assert not git(MAIN,'status','--porcelain','-z'),'main contains changes'
        reviewed=reviewed_files();expected=read(BASE/'targeted-r7.json')['frozen_after'];assert expected==frozen()
        for name in ('native-r6','installed-r3','installed-r3/media','contexts-native-r3','contexts-installed-r2'):
            value=read(BASE/name/'verification.json');assert value['status']=='passed' and value['frozen_equal'] and value['frozen_after']==expected
        for name in ('lut-native-r1','lut-installed-r1'):
            value=read(BASE/name/'verification.json');assert value['status']=='passed' and value['frozen_equal'] and value['frozen_after']==expected
        candidate=read(BASE/'candidate-release-r4.json')
        assert candidate['status']=='passed-candidate-audit' and candidate['source_frozen_equal'] and candidate['frozen_inputs']==expected
        for row in candidate['syntax_parsed']:assert sha(ROOT/row['path'])==row['sha256']
        record.update(status='preflight_passed',reviewed_files=reviewed,frozen_inputs=expected);save(work/'run.json',record)
        print(json.dumps({'status':'preflight_passed','reviewed_files':len(reviewed),'frozen_inputs':len(expected)}),flush=True)
        if args.preflight_only:return
        deadline=time.monotonic()+args.wait_seconds
        while True:
            try:full=read(BASE/'full-r2.json')
            except (json.JSONDecodeError,OSError):
                assert time.monotonic()<deadline,'full receipt unavailable; no publication performed'
                time.sleep(10);continue
            if full.get('status')!='running':break
            assert time.monotonic()<deadline,'full regression still running; no publication performed'
            record['status']='waiting_for_existing_full_regression';save(work/'run.json',record)
            time.sleep(15)
        assert full['status']=='passed' and full['terminal_ok'] and full['exit_code']==full['source_suite_exit_code']==0
        assert full['methods']==1768 and full['skipped']==0 and full['frozen_equal']
        assert full['frozen_before']==full['frozen_after']==expected==frozen()
        assert full['external_fixtures_equal'] and full['external_fixture_count']==8 and full['external_fixture_manifest_unchanged'] and full['verification_scripts_equal']
        assert reviewed_files()==reviewed
        assert git(MAIN,'rev-parse','HEAD').decode().strip()==BASE_COMMIT and not git(MAIN,'status','--porcelain','-z'),'main changed while waiting'
        assert git(MAIN,'ls-remote','origin','refs/heads/main').decode().split()[0]==BASE_COMMIT,'remote changed'
        copied=[];paths=set(reviewed)|DYNAMIC
        for name in sorted(paths):
            source=ROOT/name;target=MAIN/name
            assert source.is_file() and not source.is_symlink() and target.resolve().is_relative_to(MAIN)
            target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(source,target)
            assert source.read_bytes()==target.read_bytes();copied.append({'path':name,'sha256':sha(target)})
        assert {name:sha(MAIN/name) for name in expected}==expected
        for name,row in full['external_fixtures_expected'].items():assert (MAIN/name).stat().st_size==row['bytes'] and sha(MAIN/name)==row['sha256']
        base=MAIN/REL
        run('skills',[sys.executable,'-E','-B','-X','utf8',MAIN/'scripts/audit_source_edit_skills.py','--expected-count','17','--output',base/'skills-r1.json'])
        audit=read(base/'skills-r1.json');mapping_path=MAIN/'video-cut-install-manifest.json';mapping=read(mapping_path)
        old=mapping['current_audit'];history=mapping.setdefault('audit_history',[])
        if old not in history:history.append(old)
        for item in mapping['skills']:
            row=next(r for r in audit['results'] if r['skill']==item['name']);previous=item['skill_md_sha256'];current=row['sha256'][7:]
            if previous!=current:
                item.setdefault('skill_md_sha256_history',[]).append(previous);item['previous_manifest_skill_md_sha256']=previous
            item.update(skill_md_sha256=current,validation=row['validator_stdout'],prefix_verified=True,registration_verified=True)
            assert Path(item['canonical_directory']).resolve()==(MAIN/'skills'/item['name']).resolve()
        mapping['current_audit']={'date':'2026-10-20','skill_count':17,'local_links_checked':audit['local_links_checked'],
            'record':REL+'/skills-r1.json','record_sha256':sha(base/'skills-r1.json'),'previous_hashes_preserved':True,
            'semantics':'V78 bounded offline author timeline frame/range preview; full graph before output trim; verified content/runtime cache, explicit export and pruning; RGBA/PCM/PTS and isolated installation; 4 Skill updates; no real-time, continuous playback/listening, natural quality, HDR or full CapCut parity acceptance'}
        save(mapping_path,mapping)
        run('documents',[sys.executable,'-E','-B','-X','utf8',MAIN/'scripts/sync_timeline_preview_documents.py'])
        run('release-audit',[sys.executable,'-E','-B','-X','utf8',MAIN/'scripts/audit_timeline_preview_release.py','--output',base/'release-r1.json'])
        save(base/'publication-copy-r1.json',{'status':'passed','source_base_commit':BASE_COMMIT,'source_directory':str(ROOT),
            'copied_files':copied,'frozen_input_count':len(expected),'all_frozen_bytes_equal_source_regression':True,
            'external_fixture_count':8,'all_external_fixture_bytes_equal_regression':True,
            'generated_on_main':['video-cut-install-manifest.json',*DOCUMENTS,*FOLLOWUPS,REPORT.relative_to(ROOT).as_posix(),
                REL+'/skills-r1.json',REL+'/release-r1.json'],'copy_generator_sha256':sha(__file__),'full_regression_sha256':sha(base/'full-r2.json')})
        stage=sorted(paths|(GENERATED-{REL+'/staged-r1.json'})|{'video-cut-install-manifest.json'})
        for offset in range(0,len(stage),40):
            batch=stage[offset:offset+40];run('stage-'+str(offset//40),['git','add','--',*batch])
            run('normalize-stage-'+str(offset//40),['git','add','--renormalize','--',*batch])
        run('staged-audit',[sys.executable,'-E','-B','-X','utf8',MAIN/'scripts/verify_staged_release.py','--full',base/'full-r2.json','--output',base/'staged-r1.json'])
        run('stage-proof',['git','add','--',REL+'/staged-r1.json'])
        assert git(MAIN,'cat-file','blob',':'+REL+'/staged-r1.json')==(base/'staged-r1.json').read_bytes()
        assert not git(MAIN,'diff','--name-only')
        run('whitespace',['git','diff','--cached','--check'])
        run('commit',['git','commit','--quiet','-m','feat: add content-verified offline timeline frame and range previews'])
        commit=git(MAIN,'rev-parse','HEAD').decode().strip();remote=git(MAIN,'ls-remote','origin','refs/heads/main').decode().split()[0]
        if remote!=commit:
            run('ordinary-push',['git','push','origin','main']);remote=git(MAIN,'ls-remote','origin','refs/heads/main').decode().split()[0]
        assert remote==commit and not git(MAIN,'status','--porcelain','-z')
        record.update(status='published',commit=commit,remote_main=remote,full_methods=full['methods'],full_seconds=full['suite_seconds'],
            frozen_input_count=len(expected),skill_count=17,skill_local_links=audit['local_links_checked'],main_clean=True)
    except BaseException as exc:
        record.update(status='failed',error={'type':type(exc).__name__,'message':str(exc)});raise
    finally:
        record['finished_at_utc']=datetime.now(timezone.utc).isoformat();save(work/'run.json',record)
    print(json.dumps({k:record[k] for k in ('status','commit','remote_main','full_methods','frozen_input_count','main_clean')}),flush=True)

if __name__=='__main__':main()
