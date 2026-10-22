"""Serialize the 2280-method candidate behind actual V92 publication and install."""
from datetime import datetime,timezone
import importlib.util,json,os,subprocess,sys,time
from pathlib import Path
from run_frozen_regression import frozen,sha
ROOT=Path(__file__).resolve().parents[1];MAIN=ROOT.parents[2];PARENT=ROOT.parent/'color-precision-lab-20261021'
REL=ROOT/'docs/validation/evidence/float-timeline-20261022-lab'

def read(p):return json.loads(p.read_bytes())
def utc():return datetime.now(timezone.utc).isoformat()
def save(p,v):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
def verify(base,rows):
    for name,value in rows.items():assert sha(base/name)==value,name+' changed'

def main():
    assert MAIN==Path('E:/dev/sandbox/AI广告剪辑')
    work=ROOT/'product/.runtime/float-timeline-20261022/complete-r1';output=REL/'full-r1.json'
    assert not work.exists() and not output.exists();work.mkdir(parents=True)
    record={'status':'checking','started_at_utc':utc(),'pid':os.getpid(),'expected_methods':2280,'suite_launched':False,
        'native_windows':True,'virtualization':False,'network':False,'published':False,'default_renderer_integrated':False}
    def checkpoint():save(work/'run.json',record)
    checkpoint()
    try:
        before=frozen();host=read(REL/'host-r3.json');foundation=read(REL/'foundation-r1.json')
        assert len(before)==288 and before==host['frozen_before']==host['frozen_after'] and host['result']['methods']==46 and host['result']['successful'] and host['result']['skipped']==0
        parent_inputs=foundation['parent_frozen_inputs'];assert len(parent_inputs)==282
        assert {k:before[k] for k in parent_inputs}==parent_inputs and len(set(before)-set(parent_inputs))==6
        deps=foundation['dependency_artifact_inputs'];verify(ROOT,deps)
        scripts={p.relative_to(ROOT).as_posix():sha(p) for p in sorted((ROOT/'scripts').glob('*.py'))}
        record.update(status='waiting-for-actual-parent-publication-and-isolated-install',frozen_inputs=before,verification_scripts=scripts,dependency_artifact_inputs=deps)
        checkpoint()
        parent_owner=PARENT/'product/.runtime/color-precision-20261021/release-chain-r1/run.json'
        while True:
            parent=read(parent_owner);installed=read(REL/'installed-r1/verification.json')
            assert parent['status']!='failed-preserved',parent.get('error','parent release failed')
            assert installed['status']!='failed-preserved',installed.get('error','isolated install failed')
            if parent['status']=='published-V92-with-actual-complete-and-installed-receipts' and installed['status']=='passed-fresh-eight-wheel-174-resources-real-media-and-163-methods':break
            assert parent['status'] in ('waiting-for-actual-complete-suite','finalize-actual-complete-documents','publish-reviewed-V92','published-V92-with-actual-complete-and-installed-receipts'),parent['status']
            assert installed['status'] in ('running','passed-fresh-eight-wheel-174-resources-real-media-and-163-methods'),installed['status']
            time.sleep(5)
        verify(ROOT,before);verify(ROOT,scripts);verify(ROOT,deps)
        assert installed['frozen_before']==installed['frozen_after']==before and installed['isolated_methods']['methods']==163 and installed['isolated_methods']['skipped']==0 and len(installed['resource_hashes'])==174
        publication=read(PARENT/'product/.runtime/color-precision-20261021/publication-r1/run.json')
        assert publication['status']=='published' and publication['commit']==publication['remote_main']==parent['commit'] and publication['main_clean'] and not publication['force_push']
        parent_full=read(MAIN/'docs/validation/evidence/color-precision-20261021-lab/full-r1.json')
        assert parent_full['terminal_ok'] and parent_full['methods']==2234 and parent_full['skipped']==0 and parent_full['frozen_before']==parent_full['frozen_after']==parent_inputs
        commit=subprocess.run(['git','-c','gc.auto=0','-c','maintenance.auto=false','rev-parse','HEAD'],cwd=MAIN,capture_output=True,check=True).stdout.decode().strip();assert commit==parent['commit']
        spec=importlib.util.spec_from_file_location('published_parent_frozen',MAIN/'scripts/run_frozen_regression.py');module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);assert module.frozen()==parent_inputs
        fixtures=foundation['external_fixtures'];assert len(fixtures)==8
        for row in fixtures:
            assert sha(ROOT/row['path'])==row['sha256'] and (ROOT/row['path']).stat().st_size==row['bytes']
            assert parent_full['external_fixtures_expected'][row['path']]['sha256']==row['sha256']
        fixture_path=REL/'external-fixtures-r1.json';assert not fixture_path.exists()
        save(fixture_path,{'status':'passed','at_utc':utc(),'fixtures':fixtures,'copied_from_frozen_parent_manifest':True,'no_materialization':True,'published_parent_commit':commit})
        lineage={'status':'passed-published-V92-parent-binding','at_utc':utc(),'published_parent_commit':commit,'published_parent_frozen':parent_inputs,
            'frozen_after':before,'added_product_inputs':{k:v for k,v in before.items() if k not in parent_inputs},'parent_full_methods':2234,
            'parent_full_sha256':sha(MAIN/'docs/validation/evidence/color-precision-20261021-lab/full-r1.json'),'parent_release_owner_sha256':sha(parent_owner)}
        save(REL/'parent-binding-r1.json',lineage)
        env=dict(os.environ);env.pop('AI_AD_EDITOR_AUDIO_CLOCK_FIXTURES',None)
        discovery='import sys,unittest;sys.path.insert(0,sys.argv[1]);from ai_ad_editor.runtime import configure_local_runtime;configure_local_runtime();print(unittest.defaultTestLoader.discover(sys.argv[2]).countTestCases())'
        count=subprocess.run([sys.executable,'-E','-B','-X','utf8','-c',discovery,str(ROOT/'product/src'),str(ROOT/'product/tests')],cwd=ROOT,env=env,capture_output=True,check=True)
        record.update(discovery_stdout=count.stdout.decode('utf8','replace'),discovery_stderr=count.stderr.decode('utf8','replace'));assert int(record['discovery_stdout'].strip())==2280
        inputs=[REL/'foundation-r1.json',REL/'host-r3.json',REL/'installed-r1/verification.json',REL/'media-r2/verification.json',REL/'media-installed-r1/verification.json',fixture_path,REL/'parent-binding-r1.json']
        bound={p.relative_to(ROOT).as_posix():sha(p) for p in inputs}
        command=list(map(str,[sys.executable,'-E','-B','-X','utf8',ROOT/'scripts/run_with_regression_fixtures.py','--fixture-manifest',fixture_path,'--output',output,
            '--html-runtime',MAIN/'product/.runtime/html-motion-runtime-20261018-e2.json','--rubberband',MAIN/'product/.runtime/rubberband-offline-probe-20261017/native/rubberband-4.0.0-gpl-executable-windows/rubberband.exe']))
        record.update(status='running-complete-native-suite',suite_launched=True,published_parent_commit=commit,bound_evidence=bound,command=command);checkpoint()
        with (REL/'full-r1.launcher.log').open('xb') as stream:result=subprocess.run(command,cwd=ROOT,env=env,stdout=stream,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW)
        full=read(output);record['suite_exit_code']=result.returncode
        assert result.returncode==0 and full['status']=='passed' and full['terminal_ok'] and full['methods']==2280 and full['skipped']==0
        assert full['frozen_before']==full['frozen_after']==before==frozen() and full['external_fixture_count']==8 and full['external_fixtures_equal'] and full['external_fixture_manifest_unchanged'] and full['verification_scripts_equal']
        verify(ROOT,scripts);verify(ROOT,deps);verify(ROOT,bound)
        record.update(status='passed-complete-native-suite-not-published',methods=2280,suite_seconds=full['suite_seconds'],full_receipt_sha256=sha(output),frozen_equal=True,dependencies_equal=True,verification_scripts_equal=True)
    except BaseException as exc:record.update(status='failed-preserved',error=repr(exc));raise
    finally:
        record['updated_at_utc']=utc();checkpoint();(REL/'full-r1.executed-owner.py.txt').write_bytes(Path(__file__).read_bytes())
        print(json.dumps({k:record.get(k) for k in ('status','suite_launched','methods','error')}),flush=True)

if __name__=='__main__':main()
