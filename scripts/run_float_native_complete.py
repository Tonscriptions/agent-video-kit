"""Serialize actual2320 behind the verified V94 ordinary publication."""
from datetime import datetime,timezone
import importlib.util,json,os,subprocess,sys,time
from pathlib import Path
from publish_float_native import source_gate,verify
from run_frozen_regression import frozen,sha
ROOT=Path(__file__).resolve().parents[1];MAIN=ROOT.parents[2];PARENT=ROOT.parent/'float-stream-lab-20261022'
REL=ROOT/'docs/validation/evidence/float-render-20261022-lab'

def read(path):
    for attempt in range(12):
        try:return json.loads(path.read_bytes())
        except (OSError,ValueError):
            if attempt==11:raise
            time.sleep(.025)
def utc():return datetime.now(timezone.utc).isoformat()
def save(path,value):path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf8')

def main():
    work=ROOT/'product/.runtime/float-render-20261022/complete-r1';output=REL/'full-r1.json'
    assert not work.exists() and not output.exists();work.mkdir(parents=True)
    record={'status':'checking','started_at_utc':utc(),'pid':os.getpid(),'expected_methods':2320,'suite_launched':False,
        'native_windows':True,'virtualization':False,'network':False,'published':False,'default_renderer_integrated':False}
    def checkpoint():save(work/'run.json',record)
    checkpoint()
    try:
        audit,_=source_gate(False);before=audit['frozen_inputs'];foundation=read(REL/'foundation-r1.json');parent_inputs=foundation['parent_frozen_inputs']
        assert len(before)==296 and len(parent_inputs)==292;deps=foundation['dependency_artifact_inputs'];assert len(deps)==9;verify(ROOT,deps)
        scripts={path.relative_to(ROOT).as_posix():sha(path) for path in sorted((ROOT/'scripts').glob('*.py'))}
        record.update(status='waiting-for-actual-parent-publication-and-isolated-install',frozen_inputs=before,
            verification_scripts=scripts,dependency_artifact_inputs=deps)
        checkpoint();parent_owner=PARENT/'product/.runtime/float-stream-20261022/release-chain-r1/run.json'
        while True:
            parent=read(parent_owner)
            if parent['status']=='published-V94-with-actual-full2299-and-installed182':break
            assert parent['status'] in ('waiting-for-actual-full2299-r1','publishing-reviewed-V94-host'),parent.get('error',parent['status'])
            time.sleep(5)
        verify(ROOT,before);verify(ROOT,scripts);verify(ROOT,deps);source_gate(False)
        publication=read(PARENT/'product/.runtime/float-stream-20261022/publication-r1/run.json')
        assert publication['status']=='published' and publication['commit']==publication['remote_main']==parent['commit'] and publication['main_clean'] and not publication['force_push']
        parent_full=read(MAIN/'docs/validation/evidence/float-stream-20261022-lab/full-r1.json')
        assert parent_full['terminal_ok'] and parent_full['methods']==2299 and parent_full['skipped']==0 and parent_full['frozen_before']==parent_full['frozen_after']==parent_inputs
        commit=subprocess.run(['git','-c','gc.auto=0','-c','maintenance.auto=false','rev-parse','HEAD'],cwd=MAIN,capture_output=True,check=True).stdout.decode().strip();assert commit==parent['commit']
        spec=importlib.util.spec_from_file_location('published_stream_parent',MAIN/'scripts/run_frozen_regression.py');module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);assert module.frozen()==parent_inputs
        fixtures=foundation['external_fixtures'];assert len(fixtures)==8
        for row in fixtures:
            assert sha(ROOT/row['path'])==row['sha256'] and (ROOT/row['path']).stat().st_size==row['bytes']
            assert parent_full['external_fixtures_expected'][row['path']]['sha256']==row['sha256']
        fixture_path=REL/'external-fixtures-r1.json';assert not fixture_path.exists()
        save(fixture_path,{'status':'passed','at_utc':utc(),'fixtures':fixtures,'copied_from_frozen_parent_manifest':True,'no_materialization':True,'published_parent_commit':commit})
        lineage_path=REL/'parent-binding-r1.json';save(lineage_path,{'status':'passed-published-V94-parent-binding','at_utc':utc(),
            'published_parent_commit':commit,'published_parent_frozen':parent_inputs,'frozen_after':before,
            'added_product_inputs':{key:value for key,value in before.items() if key not in parent_inputs},'parent_full_methods':2299,
            'parent_full_sha256':sha(MAIN/'docs/validation/evidence/float-stream-20261022-lab/full-r1.json'),'parent_release_owner_sha256':sha(parent_owner)})
        env=dict(os.environ);env.pop('AI_AD_EDITOR_AUDIO_CLOCK_FIXTURES',None)
        discovery='import sys,unittest;sys.path.insert(0,sys.argv[1]);from ai_ad_editor.runtime import configure_local_runtime;configure_local_runtime();print(unittest.defaultTestLoader.discover(sys.argv[2]).countTestCases())'
        result=subprocess.run([sys.executable,'-E','-B','-X','utf8','-c',discovery,str(ROOT/'product/src'),str(ROOT/'product/tests')],cwd=ROOT,env=env,capture_output=True,check=True)
        record.update(discovery_stdout=result.stdout.decode('utf8','replace'),discovery_stderr=result.stderr.decode('utf8','replace'));assert int(record['discovery_stdout'].strip())==2320
        inputs=[REL/name for name in ('foundation-r1.json','native-r2.json','native-r1.json','native-r1-repair-audit.json','static-review-r1.json','installed-r1/verification.json',
            'media-r1/verification.json','media-installed-r1/verification.json','discovery-r1.json')]+[fixture_path,lineage_path]
        bound={path.relative_to(ROOT).as_posix():sha(path) for path in inputs}
        command=list(map(str,[sys.executable,'-E','-B','-X','utf8',ROOT/'scripts/run_with_regression_fixtures.py','--fixture-manifest',fixture_path,'--output',output,
            '--html-runtime',MAIN/'product/.runtime/html-motion-runtime-20261018-e2.json','--rubberband',MAIN/'product/.runtime/rubberband-offline-probe-20261017/native/rubberband-4.0.0-gpl-executable-windows/rubberband.exe']))
        record.update(status='running-complete-native-suite',suite_launched=True,published_parent_commit=commit,bound_evidence=bound,command=command);checkpoint()
        with (REL/'full-r1.launcher.log').open('xb') as stream:result=subprocess.run(command,cwd=ROOT,env=env,stdout=stream,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW)
        full=read(output);record['suite_exit_code']=result.returncode
        assert result.returncode==0 and full['status']=='passed' and full['terminal_ok'] and full['methods']==2320 and full['skipped']==0
        assert full['frozen_before']==full['frozen_after']==before==frozen() and full['external_fixture_count']==8 and full['external_fixtures_equal'] and full['external_fixture_manifest_unchanged'] and full['verification_scripts_equal']
        verify(ROOT,scripts);verify(ROOT,deps);verify(ROOT,bound)
        record.update(status='passed-complete-native-suite-not-published',methods=2320,suite_seconds=full['suite_seconds'],full_receipt_sha256=sha(output),frozen_equal=True,dependencies_equal=True,verification_scripts_equal=True)
    except BaseException as exc:record.update(status='failed-preserved',error=repr(exc));raise
    finally:
        record['updated_at_utc']=utc();checkpoint();(REL/'full-r1.executed-owner.py.txt').write_bytes(Path(__file__).read_bytes())
        print(json.dumps({key:record.get(key) for key in ('status','suite_launched','methods','error')}),flush=True)

if __name__=='__main__':main()
