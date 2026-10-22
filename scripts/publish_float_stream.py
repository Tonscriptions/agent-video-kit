"""Ordinary main publication gated by actual frozen2299 and installed182."""
from datetime import datetime,timezone
import argparse,importlib.util,json,shutil,subprocess,sys
from pathlib import Path
from float_stream_release_docs import ROOT,MAIN,REL,ASSETS,REPORT,CONTRACT,LATEST_DOCS,documents,local_links,installed_gate,write
from run_frozen_regression import frozen,sha

spec=importlib.util.spec_from_file_location('host_git_verifier',MAIN/'scripts/native_index_release_tools.py')
helper=importlib.util.module_from_spec(spec);spec.loader.exec_module(helper);git,staged_rows=helper.git,helper.staged_rows
def read(p):return json.loads(p.read_bytes())
def save(p,v):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
def verify(base,rows):
    for name,digest in rows.items():assert sha(base/name)==digest,name+' changed'

def source_gate(complete):
    from float_stream_release_docs import current_evidence
    current=frozen();audio,stream,media,installed=current_evidence();installed=installed_gate()
    base=ROOT/REL;foundation=read(base/'foundation-r1.json');parent=foundation['parent_frozen_inputs']
    assert len(current)==292 and len(parent)==288 and {k:current[k] for k in parent}==parent and len(set(current)-set(parent))==4
    assert len(installed['numpy_distribution']['files'])==931 and installed['actual_discovery_CLI_processes']==3
    for name in ('media-r4','media-installed-r1'):
        value=read(base/name/'verification.json')
        assert value['status']=='passed-real-bounded-FFV1-and-independent-authored-PCM' and value['frozen_before']==value['frozen_after']==current
        assert value['actual_native_launches']==20 and value['actual_encoder_processes']==2 and value['actual_new_CLI_processes']==0 and value['actual_author_frames_each']==20
        assert value['all_reference_pixel_maximum_code_error']==0 and all(row['passed'] for row in value['checks'])
        for path,row in value['assets'].items():assert sha(ROOT/path)==row['sha256'] and (ROOT/path).stat().st_size==row['bytes']
        if name.startswith('media-installed'):
            assert value['isolated_python'] and value['regression_payload_hashes']==media['regression_payload_hashes']
    verify(ROOT,foundation['dependency_artifact_inputs'])
    audit={'status':'passed-native-stream-source-preflight','frozen_inputs':current,'parent_frozen_inputs':parent,
        'complete_terminal_required':True,'complete_terminal_checked':False,'git_helper_sha256':sha(MAIN/'scripts/native_index_release_tools.py'),
        'audio_receipt_sha256':sha(base/'audio-r3.json'),'stream_receipt_sha256':sha(base/'stream-r2.json'),'installed_receipt_sha256':sha(base/'installed-r1/verification.json')}
    full=None
    if complete:
        lineage=read(base/'parent-binding-r1.json');owner=read(ROOT/'product/.runtime/float-stream-20261022/complete-r1/run.json');full=read(base/'full-r1.json')
        assert lineage['status']=='passed-published-V93-parent-binding' and lineage['published_parent_frozen']==parent and lineage['frozen_after']==current
        assert owner['status']=='passed-complete-native-suite-not-published' and owner['methods']==2299 and owner['full_receipt_sha256']==sha(base/'full-r1.json')
        assert full['status']=='passed' and full['terminal_ok'] and full['methods']==2299 and full['skipped']==0 and full['frozen_before']==full['frozen_after']==current
        assert full['external_fixture_count']==8 and full['external_fixtures_equal'] and full['external_fixture_manifest_unchanged'] and full['verification_scripts_equal']
        for key in ('verification_scripts','dependency_artifact_inputs','bound_evidence'):verify(ROOT,owner[key])
        for name,row in full['external_fixtures_expected'].items():assert sha(ROOT/name)==row['sha256']
        audit.update(status='passed-native-stream-complete-and-installed-gates',complete_terminal_checked=True,published_parent=lineage['published_parent_commit'],
            full_receipt_sha256=sha(base/'full-r1.json'),owner_sha256=sha(ROOT/'product/.runtime/float-stream-20261022/complete-r1/run.json'))
    return audit,full

def finalize_full(full):
    from float_stream_release_docs import report
    report(full)
    assets={v.relative_to(ROOT).as_posix():sha(v) for v in sorted((ROOT/ASSETS).rglob('*')) if v.is_file()}
    save(ROOT/REL/'media-inventory-full-r1.json',{'status':'passed-all-current-and-failed-media-inventory','files':assets,
        'bytes':sum((ROOT/n).stat().st_size for n in assets),'full_sha256':sha(ROOT/REL/'full-r1.json')})
    save(ROOT/REL/'finalize-full-r1.json',{'status':'passed-actual-full-document-projection','full_methods':2299,
        'full_sha256':sha(ROOT/REL/'full-r1.json'),'report_sha256':sha(ROOT/REPORT),'contract_sha256':sha(ROOT/CONTRACT),'generator_sha256':sha(Path(__file__))})


def source_files(current,parent):
    names={n for n in current if parent.get(n)!=current[n]};assert len(names)==4
    names.update((REPORT,CONTRACT))
    for prefix in (REL,ASSETS):names.update(p.relative_to(ROOT).as_posix() for p in (ROOT/prefix).rglob('*') if p.is_file())
    names.update(p.relative_to(ROOT).as_posix() for p in (ROOT/'scripts').glob('*.py'))
    rows={}
    for name in sorted(names):
        p=ROOT/name;assert p.resolve().is_relative_to(ROOT) and not p.is_symlink() and p.stat().st_size<95*1024**2,name;rows[name]=sha(p)
    return rows

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--work',type=Path,required=True);parser.add_argument('--preflight-only',action='store_true');args=parser.parse_args()
    work=args.work.resolve();assert work.is_relative_to(ROOT/'product/.runtime') and not work.exists();work.mkdir(parents=True)
    state={'status':'checking-source','started_at_utc':datetime.now(timezone.utc).isoformat(),'force_push':False,'main_integrated':False,'calls':[]}
    def checkpoint():save(work/'run.json',state)
    checkpoint()
    try:
        audit,full=source_gate(not args.preflight_only);state.update(status=audit['status'],source_audit=audit);checkpoint()
        if args.preflight_only:return
        parent=audit['published_parent'];current=audit['frozen_inputs']
        assert git(MAIN,'branch','--show-current').decode().strip()=='main' and git(MAIN,'rev-parse','HEAD').decode().strip()==parent
        assert git(MAIN,'remote','get-url','origin').decode().strip()=='git@github.com:Tonscriptions/agent-video-kit.git'
        assert git(MAIN,'ls-remote','origin','refs/heads/main').decode().split()[0]==parent
        assert not git(MAIN,'status','--porcelain','-z'),'Preserve unexpected main edits'
        spec=importlib.util.spec_from_file_location('main_host_frozen',MAIN/'scripts/run_frozen_regression.py');module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);assert module.frozen()==audit['parent_frozen_inputs']
        finalize_full(full);reviewed=source_files(current,audit['parent_frozen_inputs']);state['source_files']=reviewed;checkpoint()
        tracked={p.decode('utf8') for p in git(MAIN,'ls-files','-z').split(b'\x00') if p}
        generated={REL+'/'+n for n in ('skills-release-r2.json','release-main-r2.json','publication-copy-r2.json','staged-release-r2.json')}
        for name in set(reviewed)|generated:
            target=MAIN/name;assert target.resolve().is_relative_to(MAIN) and not target.is_symlink();assert name in tracked or not target.exists(),'Existing untracked destination '+name
        assert reviewed==source_files(current,audit['parent_frozen_inputs']);state['status']='copying-reviewed-host-source';checkpoint()
        for name,value in reviewed.items():
            p=MAIN/name;p.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/name,p);assert sha(p)==value
        assert module.frozen()==current;state['main_integrated']=True;checkpoint();documents(MAIN,full)
        attr=MAIN/'.gitattributes';write(attr,attr.read_text('utf8')+'\n# V94 immutable host native/failed/media evidence.\n'+REL+'/** -text -whitespace\n'+ASSETS+'/** -text -whitespace\n')
        command=list(map(str,[sys.executable,'-E','-B','-X','utf8',MAIN/'scripts/audit_source_edit_skills.py','--expected-count','17','--output',MAIN/REL/'skills-release-r2.json']))
        result=subprocess.run(command,cwd=MAIN,capture_output=True,timeout=600,creationflags=subprocess.CREATE_NO_WINDOW)
        for stream in ('stdout','stderr'):(work/('skills.'+stream+'.log')).write_bytes(getattr(result,stream))
        state['calls'].append({'command':command,'exit_code':result.returncode});checkpoint();assert result.returncode==0
        skill_audit=read(MAIN/REL/'skills-release-r2.json');mapping_path=MAIN/'video-cut-install-manifest.json';mapping=read(mapping_path);mapping.setdefault('audit_history',[]).append(mapping['current_audit'])
        for entry in mapping['skills']:
            row=next(v for v in skill_audit['results'] if v['skill']==entry['name']);assert entry['skill_md_sha256']==row['sha256'][7:],'Internal host release does not change Skill bodies'
            assert Path(entry['canonical_directory']).resolve()==(MAIN/'skills'/entry['name']).resolve();entry.update(validation=row['validator_stdout'],prefix_verified=True,registration_verified=True)
        mapping['current_audit']={'date':'2026-10-22','skill_count':17,'local_links_checked':skill_audit['local_links_checked'],'record':REL+'/skills-release-r2.json','record_sha256':sha(MAIN/REL/'skills-release-r2.json'),'previous_hashes_preserved':True,
            'semantics':'V94 library-only bounded Float32-to-FFV1 video and authored native audio transport; actual full2299/installed182; existing Skills unchanged and registered; default renderer/preview/audio/cache/all effects and full CapCut parity unfinished'}
        save(mapping_path,mapping)
        names=[*LATEST_DOCS,REPORT,CONTRACT,*('skills/'+v['name']+'/SKILL.md' for v in mapping['skills'])];links=local_links(MAIN,names)
        assert module.frozen()==current;inventory=read(ROOT/REL/'media-inventory-full-r1.json');verify(MAIN,inventory['files'])
        save(MAIN/REL/'release-main-r2.json',{'status':'passed-main-source-document-and-17-Skill-audit','base_commit':parent,'frozen_inputs':current,'full_methods':2299,'full_seconds':full['suite_seconds'],'full_skipped':0,'installed_methods':182,'resources':176,'skills':17,
            'full_sha256':sha(MAIN/REL/'full-r1.json'),'local_links':links,'documents':{n:sha(MAIN/n) for n in names},'generator_sha256':sha(Path(__file__)),'default_renderer_integrated':False,'full_capcut_parity':False})
        save(MAIN/REL/'publication-copy-r2.json',{'status':'passed-reviewed-host-copy','source':str(ROOT),'copied_files':reviewed,'base_commit':parent,'frozen_inputs':current})
        changed={p.decode('utf8') for p in git(MAIN,'diff','--name-only','-z').split(b'\x00') if p};changed.update(p.decode('utf8') for p in git(MAIN,'ls-files','--others','--exclude-standard','-z').split(b'\x00') if p)
        allowed=set(reviewed)|generated|set(names)|{'.gitattributes','video-cut-install-manifest.json'};assert changed<=allowed,sorted(changed-allowed)
        stage=work/'paths.nul';stage.write_bytes(b'\x00'.join(n.encode('utf8') for n in sorted(changed))+b'\x00')
        git(MAIN,'add','--pathspec-from-file='+str(stage),'--pathspec-file-nul');git(MAIN,'add','--renormalize','--pathspec-from-file='+str(stage),'--pathspec-file-nul')
        assert not git(MAIN,'diff','--name-only');assert {v.decode('utf8') for v in git(MAIN,'diff','--cached','--name-only','-z').split(b'\x00') if v}==changed;git(MAIN,'diff','--cached','--check')
        rows=staged_rows({**{n:sha(MAIN/n) for n in changed},**current});receipt=REL+'/staged-release-r2.json'
        save(MAIN/receipt,{'status':'passed','frozen_files':292,'compared_blobs':len(rows),'files':rows,'all_staged_bytes_equal_workspace':True,'all_frozen_bytes_equal_staged':True,'stream_buffer_bytes':65536,'base_commit':parent,'full_sha256':sha(MAIN/REL/'full-r1.json')})
        git(MAIN,'add','--',receipt);staged_rows({receipt:sha(MAIN/receipt)});assert module.frozen()==current and not git(MAIN,'diff','--name-only');git(MAIN,'diff','--cached','--check')
        state.update(status='passed-staged-audit',compared_blobs=len(rows),verified_links=len(links));checkpoint()
        git(MAIN,'commit','--quiet','-m','feat: stream float author frames with verified native audio');commit=git(MAIN,'rev-parse','HEAD').decode().strip();assert git(MAIN,'rev-parse','HEAD^').decode().strip()==parent
        state.update(status='committed-awaiting-ordinary-push',commit=commit);checkpoint();git(MAIN,'push','origin','main');remote=git(MAIN,'ls-remote','origin','refs/heads/main').decode().split()[0]
        assert remote==commit and not git(MAIN,'status','--porcelain','-z') and module.frozen()==current
        state.update(status='published',remote_main=remote,main_clean=True,full_methods=2299,isolated_methods=182)
    except BaseException as exc:state.update(status='failed-preserved',error={'type':type(exc).__name__,'message':str(exc)});raise
    finally:
        state['updated_at_utc']=datetime.now(timezone.utc).isoformat();checkpoint();print(json.dumps({k:state.get(k) for k in ('status','commit','remote_main','error')}),flush=True)

if __name__=='__main__':main()
