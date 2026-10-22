"""Run one actual LUT full suite after the final306 parent is published."""
from datetime import datetime, timezone
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import time

from run_frozen_regression import frozen, sha

ROOT=Path(__file__).resolve().parents[1]
MAIN=ROOT.parents[2]
PARENT=ROOT.parent/'float-crop-lab-20261022'
REL=ROOT/'docs/validation/evidence/float-lut-20261022-lab'
WORK=ROOT/'product/.runtime/float-lut-20261022'


def read(path):
    for attempt in range(12):
        try:return json.loads(path.read_bytes())
        except (OSError,ValueError):
            if attempt==11:raise
            time.sleep(.025)


def save(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    temporary=path.with_name(path.name+'.owner-'+str(os.getpid()))
    temporary.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n')
    os.replace(temporary,path)


def verify(base,entries):
    for name,digest in entries.items():assert sha(base/name)==digest,name


def input_map(base,name):
    spec=importlib.util.spec_from_file_location(name,base/'scripts/run_frozen_regression.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module.frozen()


def git(*args):
    return subprocess.run(['git','-c','gc.auto=0','-c','maintenance.auto=false',*args],cwd=MAIN,
        capture_output=True,check=True,creationflags=subprocess.CREATE_NO_WINDOW).stdout


def main():
    work=WORK/'complete-r1';work.mkdir(parents=True,exist_ok=False)
    output=REL/'full-r1.json';assert not output.exists()
    state={'status':'checking-source-and-install','pid':os.getpid(),'started_at_utc':datetime.now(timezone.utc).isoformat(),
        'expected_methods':2455,'suite_launched':False,'published':False,'network_during_suite':False,
        'native_windows':True,'virtualization':False,'full_capcut_parity':False}
    def checkpoint():
        state['updated_at_utc']=datetime.now(timezone.utc).isoformat();save(work/'run.json',state)
    checkpoint()
    try:
        before=frozen();assert len(before)==309
        scripts={p.relative_to(ROOT).as_posix():sha(p) for p in sorted((ROOT/'scripts').glob('*.py'))}
        foundation=read(REL/'foundation-r1.json');deps=foundation['dependency_artifact_inputs']
        assert len(deps)==9 and len(foundation['parent_frozen_inputs'])==306
        native=read(REL/'native-r3/verification.json')
        media=read(REL/'media-r1/verification.json')
        installed=read(REL/'installed-r1/verification.json')
        assert native['status']=='passed' and native['methods']==160 and native['skipped']==0
        assert installed['status']=='passed-fresh-eight-wheel-185-resources-real-previews-and-360-methods'
        assert installed['isolated_methods']['methods']==360 and installed['isolated_methods']['skipped']==0
        assert media['status']=='passed-public-CLI-floating-LUTs-and-native-float-previews'
        for receipt in [native,media,installed]:assert receipt['frozen_before']==receipt['frozen_after']==before
        verify(ROOT,before);verify(ROOT,deps)
        state.update(status='waiting-for-actual-published-V100-full2418',frozen_inputs=before,
            verification_scripts=scripts,dependency_artifact_inputs=deps,installed_methods=360)
        checkpoint()
        parent_work=PARENT/'product/.runtime/float-crop-20261022'
        parent_rel=PARENT/'docs/validation/evidence/float-crop-20261022-lab'
        while True:
            owner=read(parent_work/'complete-r1/run.json')
            release=read(parent_work/'release-chain-r1/run.json')
            assert not owner['status'].startswith('failed'),owner.get('error',owner['status'])
            assert not release['status'].startswith('failed'),release.get('error',release['status'])
            if release['status']=='published-V100-full2418-installed323':break
            time.sleep(5)
        parent_full=read(parent_rel/'full-r1.json')
        publication=read(parent_work/'publication-r1/run.json')
        parent_inputs=foundation['parent_frozen_inputs']
        assert owner['status']=='passed-complete-native-suite-not-published' and owner['methods']==2418
        assert parent_full['status']=='passed' and parent_full['terminal_ok'] and parent_full['methods']==2418 and parent_full['skipped']==0
        assert parent_full['frozen_before']==parent_full['frozen_after']==parent_inputs
        assert parent_full['external_fixtures_equal'] and parent_full['verification_scripts_equal']
        assert publication['status']=='published' and publication['main_clean']
        commit=publication['commit'];assert publication['remote_main']==commit
        assert input_map(PARENT,'crop_parent_source')==parent_inputs
        assert input_map(MAIN,'crop_published_parent')==parent_inputs
        assert git('branch','--show-current').decode().strip()=='main'
        assert git('remote','get-url','origin').decode().strip()=='git@github.com:Tonscriptions/agent-video-kit.git'
        assert git('rev-parse','HEAD').decode().strip()==commit
        assert git('ls-remote','origin','refs/heads/main').decode().split()[0]==commit
        assert not git('status','--porcelain','-z'),'Preserve unexpected main edits'
        verify(ROOT,before);verify(ROOT,scripts);verify(ROOT,deps)
        fixture_path=REL/'external-fixtures-r1.json'
        fixtures=foundation['external_fixtures'];assert len(fixtures)==8
        for row in fixtures:
            p=ROOT/row['path'];assert sha(p)==row['sha256'] and p.stat().st_size==row['bytes']
            assert parent_full['external_fixtures_expected'][row['path']]['sha256']==row['sha256']
        save(fixture_path,{'status':'passed','fixtures':fixtures,'copied_from_frozen_parent_manifest':True,
            'no_materialization':True,'published_parent_commit':commit})
        save(REL/'parent-full-r1.json',parent_full);save(REL/'parent-publication-r1.json',publication)
        save(REL/'parent-binding-r1.json',{'status':'passed-actual-published-parent306-full2418',
            'published_parent_commit':commit,'parent_inputs':parent_inputs,'candidate_inputs':before,
            'changed_product_paths':[n for n in before if parent_inputs.get(n)!=before[n]],
            'parent_full_sha256':sha(parent_rel/'full-r1.json'),'parent_publication_sha256':sha(parent_work/'publication-r1/run.json')})
        bound_names=['foundation-r1.json','native-r3/verification.json','media-r1/verification.json',
            'installed-r1/verification.json','media-installed-r1/verification.json','parent-full-r1.json',
            'parent-publication-r1.json','parent-binding-r1.json','external-fixtures-r1.json']
        bound={(REL/n).relative_to(ROOT).as_posix():sha(REL/n) for n in bound_names}
        env=dict(os.environ);env.pop('AI_AD_EDITOR_AUDIO_CLOCK_FIXTURES',None)
        bootstrap=('import sys,unittest;sys.path.insert(0,sys.argv[1]);'
            'from ai_ad_editor.runtime import configure_local_runtime;configure_local_runtime();'
            'print(unittest.defaultTestLoader.discover(sys.argv[2]).countTestCases())')
        result=subprocess.run([sys.executable,'-E','-B','-X','utf8','-c',bootstrap,str(ROOT/'product/src'),str(ROOT/'product/tests')],
            cwd=ROOT,env=env,capture_output=True,check=True)
        state.update(discovery_stdout=result.stdout.decode('utf8','replace'),discovery_stderr=result.stderr.decode('utf8','replace'))
        assert int(state['discovery_stdout'].strip())==2455
        command=list(map(str,[sys.executable,'-E','-B','-X','utf8',ROOT/'scripts/run_with_regression_fixtures.py',
            '--fixture-manifest',fixture_path,'--output',output,
            '--html-runtime',MAIN/'product/.runtime/html-motion-runtime-20261018-e2.json',
            '--rubberband',MAIN/'product/.runtime/rubberband-offline-probe-20261017/native/rubberband-4.0.0-gpl-executable-windows/rubberband.exe']))
        state.update(status='running-complete-native-suite',suite_launched=True,published_parent_commit=commit,
            command=command,bound_evidence=bound);checkpoint()
        with (REL/'full-r1.launcher.log').open('xb') as stream:
            result=subprocess.run(command,cwd=ROOT,env=env,stdout=stream,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW)
        full=read(output);state['suite_exit_code']=result.returncode
        assert result.returncode==0 and full['status']=='passed' and full['terminal_ok']
        assert full['methods']==2455 and full['skipped']==0 and full['frozen_before']==full['frozen_after']==before
        assert full['external_fixture_count']==8 and full['external_fixtures_equal'] and full['external_fixture_manifest_unchanged']
        assert full['verification_scripts_equal']
        verify(ROOT,before);verify(ROOT,scripts);verify(ROOT,deps);verify(ROOT,bound)
        state.update(status='passed-complete-native-suite-not-published',methods=2455,suite_seconds=full['suite_seconds'],
            full_receipt_sha256=sha(output),frozen_equal=True,verification_scripts_equal=True,dependencies_equal=True)
    except BaseException as exc:
        state.update(status='failed-preserved',error=repr(exc));raise
    finally:
        (REL/'full-r1.executed-owner.py.txt').write_bytes(Path(__file__).read_bytes())
        checkpoint();print(json.dumps({k:state.get(k) for k in ['status','suite_launched','methods','error']},ensure_ascii=False),flush=True)


if __name__=='__main__':main()
