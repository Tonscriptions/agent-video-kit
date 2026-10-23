"""Publish reviewed V112 only after actual parent, source/package and full gates."""
from datetime import datetime,timezone
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import time
from run_frozen_regression import frozen,sha
from float_shaper_release_docs import accepted,documents,check_links,ROOT,MAIN,REL

WORK=ROOT/'product/.runtime/float-shaper-20261023/release-r3'
PARENT=ROOT.parent/'pipeline-recovery-lab-20261023'

def read(path):
    for attempt in range(12):
        try:return json.loads(path.read_bytes())
        except (OSError,ValueError):
            if attempt==11:raise
            time.sleep(.025)

def save(path,value):
    path.parent.mkdir(parents=True,exist_ok=True);tmp=path.with_name(path.name+'.'+str(os.getpid())+'.tmp')
    tmp.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n');os.replace(tmp,path)

def load(path,name):
    spec=importlib.util.spec_from_file_location(name,path);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module

def git(root,*args):
    result=subprocess.run(['git','-c','gc.auto=0','-c','maintenance.auto=false','-c','core.fsmonitor=false',*args],
        cwd=root,capture_output=True,timeout=3600 if args and args[0]=='push' else 600,creationflags=subprocess.CREATE_NO_WINDOW)
    assert result.returncode==0,result.stderr.decode('utf8','replace')[-3000:]
    return result.stdout

def main():
    WORK.mkdir(parents=True,exist_ok=False);before=frozen();assert len(before)==331
    scripts={p.relative_to(ROOT).as_posix():sha(p) for p in sorted((ROOT/'scripts').iterdir()) if p.is_file()}
    state=dict(status='waiting-for-actual-full2930-installed118',pid=os.getpid(),started_at_utc=datetime.now(timezone.utc).isoformat(),
        main_mutated=False,published=False,force_push=False,full_capcut_parity=False,frozen_inputs=before,verification_scripts=scripts)
    def checkpoint():state['updated_at_utc']=datetime.now(timezone.utc).isoformat();save(WORK/'run.json',state)
    def verify():
        assert frozen()==before
        assert {p.relative_to(ROOT).as_posix():sha(p) for p in sorted((ROOT/'scripts').iterdir()) if p.is_file()}==scripts
    checkpoint()
    try:
        deadline=time.monotonic()+36000
        while True:
            owner=read(ROOT/'product/.runtime/float-shaper-20261023/complete-r3/run.json')
            assert not owner['status'].startswith(('failed','aborted')),(owner['status'],owner.get('error'))
            if owner['status']=='passed-complete-native-suite-not-published':break
            assert time.monotonic()<deadline,'waiting for final full2930 exceeded ten hours'
            verify();time.sleep(10)
        records=accepted(True)
        assert owner['methods']==2930 and owner['frozen_inputs']==before and owner['verification_scripts']==scripts
        parent=read(PARENT/'product/.runtime/pipeline-recovery-20261023/release-r2/run.json')
        assert parent['status']=='published-V111-full2897-installed804'
        baseline=parent['commit'];assert owner['parent_commit']==baseline
        product=load(MAIN/'scripts/run_frozen_regression.py','shaper_main_frozen')
        previous=read(ROOT/REL/'foundation-r1.json')['parent_frozen_inputs']
        assert len(previous)==330 and product.frozen()==previous
        assert git(MAIN,'rev-parse','HEAD').decode().strip()==baseline
        assert git(MAIN,'ls-remote','origin','refs/heads/main').decode().split()[0]==baseline
        assert git(MAIN,'branch','--show-current').decode().strip()=='main'
        assert git(MAIN,'remote','get-url','origin').decode().strip()=='git@github.com:Tonscriptions/agent-video-kit.git'
        assert not git(MAIN,'status','--porcelain','-z')
        verify();state.update(status='building-reviewed-final-stage',parent_commit=baseline);checkpoint()
        preview=WORK/'preview';preview.mkdir();generated=documents(preview,True)
        attrs=(MAIN/'.gitattributes').read_text(encoding='utf-8-sig')
        attrs+='\n# V112 byte-preserved shaper proof and media\n'
        attrs+='docs/validation/evidence/float-shaper-20261023-lab/** -text\n'
        attrs+='docs/validation/evidence/float-shaper-20261023-lab/source-reference-*/** -diff\n'
        for folder in ('float-shaper-20261023-r1','float-shaper-20261023-installed-r1','float-shaper-4k-20261023-r1','float-shaper-review-20261023-r1'):
            attrs+='docs/assets/'+folder+'/** -text\n'
        generated['.gitattributes']=attrs;(preview/'.gitattributes').write_text(attrs,encoding='utf8',newline='\n')
        rows=dict(before)
        for directory in ('docs','scripts','sources'):
            for source in sorted((ROOT/directory).rglob('*')):
                if not source.is_file():continue
                assert not source.is_symlink() and source.resolve().is_relative_to(ROOT)
                name=source.relative_to(ROOT).as_posix();assert source.stat().st_size<95*(1<<20),name
                if name not in generated:rows[name]=sha(source)
        rows.update({name:sha(preview/name) for name in generated})
        links=check_links(generated,preview)
        stage=WORK/'native-stage';stage.mkdir()
        for name,digest in rows.items():
            source=preview/name if name in generated else ROOT/name
            target=stage/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(source,target);assert sha(target)==digest
        git(stage,'init','--quiet','--initial-branch=main');git(stage,'config','core.longpaths','true')
        pathspec=WORK/'paths.nul';pathspec.write_bytes(b'\0'.join(n.encode('utf8') for n in sorted(rows))+b'\0')
        git(stage,'add','--force','--pathspec-from-file='+str(pathspec),'--pathspec-file-nul')
        helper=load(MAIN/'scripts/native_index_release_tools.py','shaper_native_stage');helper.MAIN=stage
        compared=helper.staged_rows(rows);git(stage,'diff','--cached','--check')
        save(WORK/'fresh-staging.json',dict(status='passed-fresh-final-native-stage',files=rows,staged_blobs=compared,
            checked_document_links=links,source_receipts={n:sha(ROOT/n) for n in records},main_mutated=False))
        verify();assert product.frozen()==previous and git(MAIN,'rev-parse','HEAD').decode().strip()==baseline
        assert not git(MAIN,'status','--porcelain','-z')
        state.update(status='integrating-reviewed-final-snapshot',main_mutated=True);checkpoint()
        for name,digest in rows.items():
            source=preview/name if name in generated else ROOT/name;target=MAIN/name
            if target.exists():
                if sha(target)==digest:continue
                backup=WORK/'original-main'/name;backup.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(target,backup)
            target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(source,target);assert sha(target)==digest
        git(MAIN,'add','--force','--pathspec-from-file='+str(pathspec),'--pathspec-file-nul')
        helper.MAIN=MAIN;compared=helper.staged_rows(rows);git(MAIN,'diff','--cached','--check')
        assert product.frozen()==before and not git(MAIN,'diff','--name-only')
        public=Path(REL)/'publication-r1.json'
        save(MAIN/public,dict(status='passed-staged-final-snapshot-publication-audit',parent_commit=baseline,
            final_product_inputs=before,full_methods=2930,installed_methods=118,installed_resources=197,
            native_source_methods=118,native_first_round_failures=2,first_round_failure_preserved=True,
            checked_document_links=links,staged_blobs=compared,source_receipts={n:sha(ROOT/n) for n in records},
            fresh_staging_sha256=sha(WORK/'fresh-staging.json'),force_push=False,full_capcut_parity=False))
        git(MAIN,'add','--force','--',public.as_posix());helper.staged_rows({public.as_posix():sha(MAIN/public)})
        git(MAIN,'diff','--cached','--check')
        git(MAIN,'commit','--quiet','-m','feat: add local float 1D LUT and ordered shaper grading')
        commit=git(MAIN,'rev-parse','HEAD').decode().strip();assert git(MAIN,'rev-parse','HEAD^').decode().strip()==baseline
        state.update(status='committed-awaiting-ordinary-push',commit=commit);checkpoint();git(MAIN,'push','origin','main')
        remote=git(MAIN,'ls-remote','origin','refs/heads/main').decode().split()[0]
        assert remote==commit and product.frozen()==before and not git(MAIN,'status','--porcelain','-z')
        state.update(status='published-V112-full2930-installed118',published=True,main_clean=True,remote_main=remote,
            full_methods=2930,installed_methods=118,installed_resources=197);checkpoint()
    except BaseException as exc:state.update(status='failed-preserved',error=repr(exc));checkpoint();raise
    finally:print(json.dumps({k:state.get(k) for k in ('status','commit','remote_main','error')},ensure_ascii=False),flush=True)

if __name__=='__main__':main()
