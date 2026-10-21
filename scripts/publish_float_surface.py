"""Publish the V91-rebased float surface CLI after actual full2234 and installed117."""
from datetime import datetime,timezone
import argparse,importlib.util,json
from pathlib import Path
import shutil,subprocess,sys
from float_release_docs import ROOT,MAIN,REL,ASSETS,REPORT,CONTRACT,GUIDE,LATEST_DOCS,SKILLS,documents,skills,local_links
from run_frozen_regression import frozen,sha

PARENT='18f5dc766a80e0b47f096b1b93ccfe1cee0fb5f6'
helper_spec=importlib.util.spec_from_file_location('float_git_byte_verifier',MAIN/'scripts/native_index_release_tools.py')
helper=importlib.util.module_from_spec(helper_spec);helper_spec.loader.exec_module(helper)
git,staged_rows=helper.git,helper.staged_rows

def read(p):return json.loads(p.read_bytes())
def save(p,v):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n')
def verify(base,rows):
    for name,digest in rows.items():assert sha(base/name)==digest,name

def source_gate(complete=False):
    base=ROOT/REL;current=frozen();lineage=read(base/'parent-rebase-r1.json')
    assert current==lineage['frozen_after'] and len(current)==282 and lineage['published_parent_commit']==PARENT
    installed=read(base/'installed-r1/verification.json');kernel=read(base/'kernel-r11.json')
    assert kernel['status'].startswith('passed') and kernel['result']['methods']==86 and kernel['result']['skipped']==0
    assert installed['status'].startswith('passed-fresh-eight-wheel') and installed['frozen_before']==installed['frozen_after']==current
    assert installed['isolated_methods']['methods']==117 and installed['isolated_methods']['skipped']==0
    assert len(installed['resource_hashes'])==171 and len(installed['numpy_distribution']['original_files_except_rewritten_RECORD'])==931
    assert len(installed['isolated_methods']['origins'])==213 and installed['isolated_subprocess_CLI_calls']==18
    for p in (base/'surface-cli-media-r1/verification.json',base/'surface-cli-media-installed-r1/verification.json'):
        m=read(p);assert m['status'].startswith('passed-subprocess') and m['frozen_before']==m['frozen_after']==current
        verify(ROOT,{r['path']:r['sha256'] for r in m['assets']})
    verify(ROOT,read(base/'foundation-r1.json')['dependency_artifact_inputs'])
    audit={'status':'passed-source-preflight','frozen_inputs':current,'published_parent':PARENT,
        'parent_frozen_inputs':lineage['published_parent_frozen'],'source_git_helper_sha256':sha(MAIN/'scripts/native_index_release_tools.py'),
        'kernel_receipt_sha256':sha(base/'kernel-r11.json'),'installed_receipt_sha256':sha(base/'installed-r1/verification.json'),
        'complete_terminal_required':True,'complete_terminal_checked':False}
    full=None
    if complete:
        gate=read(base/'complete-gate-r1.json');full=read(base/'full-r1.json')
        assert gate['status']=='passed-complete-extra-frozen-inputs' and gate['complete_methods']==2234
        assert full['status']=='passed' and full['terminal_ok'] and full['methods']==2234 and full['skipped']==0
        assert full['frozen_before']==full['frozen_after']==current and full['external_fixture_count']==8
        assert full['external_fixtures_equal'] and full['external_fixture_manifest_unchanged'] and full['verification_scripts_equal']
        assert gate['full_receipt_sha256']==sha(base/'full-r1.json')
        for key in ('verification_scripts','dependency_artifact_inputs','bound_evidence'):verify(ROOT,gate[key])
        for name,row in full['external_fixtures_expected'].items():assert sha(ROOT/name)==row['sha256']
        final=read(base/'finalize-full-r1.json');assert final['status']=='passed-actual-full-document-projection' and final['complete_methods']==2234
        inventory=read(base/'media-inventory-full-r1.json');verify(ROOT,{r['path']:r['sha256'] for r in inventory['files']})
        assert len(inventory['files'])==134
        audit.update(status='passed-all-source-native-complete-and-installed-gates',complete_terminal_checked=True,
            full_receipt_sha256=sha(base/'full-r1.json'),complete_gate_sha256=sha(base/'complete-gate-r1.json'))
    return audit,full

def source_files(current):
    lineage=read(ROOT/REL/'parent-rebase-r1.json');parent=lineage['published_parent_frozen']
    names={name for name in current if parent.get(name)!=current[name]}
    assert len(names)==17
    names.update((REPORT,CONTRACT,GUIDE))
    for relative in (REL,ASSETS):
        names.update(p.relative_to(ROOT).as_posix() for p in (ROOT/relative).rglob('*') if p.is_file())
    names.update(p.relative_to(ROOT).as_posix() for p in (ROOT/'scripts').glob('*.py'))
    rows={}
    for name in sorted(names):
        p=ROOT/name;assert p.resolve().is_relative_to(ROOT) and not p.is_symlink() and p.stat().st_size<95*1024**2,name
        rows[name]=sha(p)
    return rows

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--work',required=True,type=Path);parser.add_argument('--preflight-only',action='store_true');args=parser.parse_args()
    work=args.work.resolve();assert work.is_relative_to(ROOT/'product/.runtime') and not work.exists();work.mkdir(parents=True)
    state={'status':'checking-source','started_at_utc':datetime.now(timezone.utc).isoformat(),
        'force_push':False,'main_integrated':False,'calls':[]}
    def checkpoint():save(work/'run.json',state)
    checkpoint()
    try:
        audit,full=source_gate(complete=not args.preflight_only);current=audit['frozen_inputs']
        state.update(status=audit['status'],source_audit=audit);checkpoint()
        if args.preflight_only:return
        assert git(MAIN,'branch','--show-current').decode().strip()=='main'
        assert git(MAIN,'rev-parse','HEAD').decode().strip()==PARENT
        assert git(MAIN,'remote','get-url','origin').decode().strip()=='git@github.com:Tonscriptions/agent-video-kit.git'
        assert git(MAIN,'ls-remote','origin','refs/heads/main').decode().split()[0]==PARENT
        assert not git(MAIN,'status','--porcelain','-z'),'Preserve unexpected main changes'
        spec=importlib.util.spec_from_file_location('float_main_freeze',MAIN/'scripts/run_frozen_regression.py')
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        assert module.frozen()==audit['parent_frozen_inputs']
        reviewed=source_files(current);state['source_files']=reviewed;checkpoint()
        tracked={p.decode('utf8') for p in git(MAIN,'ls-files','-z').split(b'\x00') if p}
        generated={REL+'/'+name for name in ('skills-release-r1.json','release-main-r1.json','publication-copy-r1.json','staged-release-r1.json')}
        for name in set(reviewed)|generated:
            target=MAIN/name;assert target.resolve().is_relative_to(MAIN) and not target.is_symlink()
            assert name in tracked or not target.exists(),'Existing untracked destination: '+name
        assert source_files(current)==reviewed
        state['status']='copying-reviewed-source';checkpoint()
        for name,digest in reviewed.items():
            target=MAIN/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/name,target);assert sha(target)==digest,name
        assert module.frozen()==current
        state['main_integrated']=True;checkpoint()
        documents(MAIN,full);names=skills(MAIN)
        attr=MAIN/'.gitattributes';text=attr.read_text('utf8')
        text+='\n# V92 immutable original/failed/native Float32 media and receipts.\n'+REL+'/** -text -whitespace\n'+ASSETS+'/** -text -whitespace\n'
        attr.write_text(text.rstrip()+'\n',encoding='utf8',newline='\n')
        command=list(map(str,[sys.executable,'-E','-B','-X','utf8',MAIN/'scripts/audit_source_edit_skills.py','--expected-count','17','--output',MAIN/REL/'skills-release-r1.json']))
        result=subprocess.run(command,cwd=MAIN,capture_output=True,timeout=600,creationflags=subprocess.CREATE_NO_WINDOW)
        for stream in ('stdout','stderr'):(work/('main-skills.'+stream+'.log')).write_bytes(getattr(result,stream))
        state['calls'].append({'command':command,'exit_code':result.returncode});checkpoint();assert result.returncode==0
        skill_audit=read(MAIN/REL/'skills-release-r1.json');mapping_path=MAIN/'video-cut-install-manifest.json';mapping=read(mapping_path)
        mapping.setdefault('audit_history',[]).append(mapping['current_audit'])
        for entry in mapping['skills']:
            row=next(r for r in skill_audit['results'] if r['skill']==entry['name']);old,new=entry['skill_md_sha256'],row['sha256'][7:]
            if old!=new:
                entry.setdefault('skill_md_sha256_history',[]).append(old);entry['previous_manifest_skill_md_sha256']=old
            entry.update(skill_md_sha256=new,validation=row['validator_stdout'],prefix_verified=True,registration_verified=True)
            assert Path(entry['canonical_directory']).resolve()==(MAIN/'skills'/entry['name']).resolve()
        mapping['current_audit']={'date':'2026-10-22','skill_count':17,'local_links_checked':skill_audit['local_links_checked'],
            'record':REL+'/skills-release-r1.json','record_sha256':sha(MAIN/REL/'skills-release-r1.json'),'previous_hashes_preserved':True,
            'semantics':'V92 native-clock Float32 surface CLI, relative D65 signals and independent linear-light core; full2234 and installed117 actual; default render/preview/cache integration and HDR/natural/full CapCut parity unaccepted'}
        save(mapping_path,mapping)
        doc_names=[*LATEST_DOCS,REPORT,CONTRACT,GUIDE,*('skills/'+name+'/SKILL.md' for name in names)]
        links=local_links(MAIN,doc_names)
        assert module.frozen()==current
        verify(MAIN,{r['path']:r['sha256'] for r in read(ROOT/REL/'media-inventory-full-r1.json')['files']})
        save(MAIN/REL/'release-main-r1.json',{'status':'passed-main-source-document-Skill-audit','base_commit':PARENT,
            'frozen_inputs':current,'full_methods':2234,'full_seconds':full['suite_seconds'],'full_skipped':0,
            'full_sha256':sha(MAIN/REL/'full-r1.json'),'installed_methods':117,'resources':171,'skills':17,
            'local_links':links,'documents':{name:sha(MAIN/name) for name in doc_names},'generator_sha256':sha(Path(__file__)),
            'ordinary_timeline_render_integrated':False,'HDR_accepted':False,'full_capcut_parity':False})
        save(MAIN/REL/'publication-copy-r1.json',{'status':'passed-reviewed-copy','source':str(ROOT),'copied_files':reviewed,
            'base_commit':PARENT,'frozen_inputs':current})
        changed={p.decode('utf8') for p in git(MAIN,'diff','--name-only','-z').split(b'\x00') if p}
        changed.update(p.decode('utf8') for p in git(MAIN,'ls-files','--others','--exclude-standard','-z').split(b'\x00') if p)
        allowed=set(reviewed)|generated|set(doc_names)|{'.gitattributes','video-cut-install-manifest.json'}
        assert changed<=allowed,sorted(changed-allowed)
        stage=work/'stage-paths.nul';stage.write_bytes(b'\x00'.join(name.encode('utf8') for name in sorted(changed))+b'\x00')
        git(MAIN,'add','--pathspec-from-file='+str(stage),'--pathspec-file-nul')
        git(MAIN,'add','--renormalize','--pathspec-from-file='+str(stage),'--pathspec-file-nul')
        assert not git(MAIN,'diff','--name-only')
        assert {p.decode('utf8') for p in git(MAIN,'diff','--cached','--name-only','-z').split(b'\x00') if p}==changed
        git(MAIN,'diff','--cached','--check')
        expected={**{name:sha(MAIN/name) for name in changed},**current}
        rows=staged_rows(expected)
        receipt=REL+'/staged-release-r1.json'
        save(MAIN/receipt,{'status':'passed','frozen_files':282,'compared_blobs':len(rows),'files':rows,
            'all_staged_bytes_equal_workspace':True,'all_frozen_bytes_equal_staged':True,'stream_buffer_bytes':65536,
            'full_sha256':sha(MAIN/REL/'full-r1.json'),'base_commit':PARENT})
        git(MAIN,'add','--',receipt);staged_rows({receipt:sha(MAIN/receipt)})
        assert module.frozen()==current and not git(MAIN,'diff','--name-only')
        git(MAIN,'diff','--cached','--check');state.update(status='passed-staged-audit',compared_blobs=len(rows),verified_links=len(links));checkpoint()
        git(MAIN,'commit','--quiet','-m','feat: add native-clock float surface CLI and linear-light core')
        commit=git(MAIN,'rev-parse','HEAD').decode().strip();assert git(MAIN,'rev-parse','HEAD^').decode().strip()==PARENT
        state.update(status='committed-awaiting-ordinary-push',commit=commit);checkpoint()
        git(MAIN,'push','origin','main')
        remote=git(MAIN,'ls-remote','origin','refs/heads/main').decode().split()[0]
        assert remote==commit and not git(MAIN,'status','--porcelain','-z') and module.frozen()==current
        state.update(status='published',remote_main=remote,main_clean=True,full_methods=2234,isolated_methods=117)
    except BaseException as error:
        state.update(status='failed-preserved',error={'type':type(error).__name__,'message':str(error)});raise
    finally:
        state['updated_at_utc']=datetime.now(timezone.utc).isoformat();checkpoint()
        print(json.dumps({k:state.get(k) for k in ('status','commit','remote_main','error')}),flush=True)

if __name__=='__main__':main()
