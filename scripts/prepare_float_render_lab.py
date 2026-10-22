"""Isolate standard-render integration from live frozen292 stream candidate."""
from datetime import datetime,timezone
import importlib.util,json,shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];PARENT=ROOT.parent/'float-stream-lab-20261022'

def main():
    assert not (ROOT/'product/src').exists()
    spec=importlib.util.spec_from_file_location('stream_parent_freeze',PARENT/'scripts/run_frozen_regression.py');module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    current=module.frozen();assert len(current)==292
    rel=PARENT/'docs/validation/evidence/float-stream-20261022-lab'
    stream=json.loads((rel/'stream-r2.json').read_bytes());installed=json.loads((rel/'installed-r1/verification.json').read_bytes())
    assert stream['frozen_after']==stream['frozen_before']==current and stream['result']['methods']==9 and stream['result']['successful']
    assert installed['status']=='passed-fresh-eight-wheel-176-resources-real-media-and-182-methods' and installed['frozen_after']==installed['frozen_before']==current
    foundation=json.loads((rel/'foundation-r1.json').read_bytes());owner=json.loads((PARENT/'product/.runtime/float-stream-20261022/complete-r1/run.json').read_bytes())
    assert owner['status'] in ('waiting-for-actual-parent-publication-and-isolated-install','running-complete-native-suite','passed-complete-native-suite-not-published')
    names=set(current)|set(foundation['dependency_artifact_inputs'])|{row['path'] for row in foundation['external_fixtures']}|{'scripts/run_frozen_regression.py','scripts/run_with_regression_fixtures.py','scripts/materialize_regression_fixtures.py'}
    assert len(names)==312;copied={}
    for name in sorted(names):
        source=PARENT/name;target=ROOT/name;assert source.is_file() and not target.exists()
        digest=module.sha(source);target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(source,target);assert module.sha(target)==digest;copied[name]=digest
    assert module.frozen()==current
    out=ROOT/'docs/validation/evidence/float-render-20261022-lab/foundation-r1.json';out.parent.mkdir(parents=True,exist_ok=True)
    value={'status':'isolated-copy-of-tested292-input-stream-candidate','at_utc':datetime.now(timezone.utc).isoformat(),'copied_files':copied,'copied_count':len(copied),
        'parent_root':str(PARENT),'parent_frozen_inputs':current,'parent_full_status_at_copy':owner['status'],'parent_full_methods_expected':2299,'parent_published':False,
        'parent_stream_receipt_sha256':module.sha(rel/'stream-r2.json'),'parent_installed_receipt_sha256':module.sha(rel/'installed-r1/verification.json'),
        'dependency_artifact_inputs':foundation['dependency_artifact_inputs'],'external_fixtures':foundation['external_fixtures'],
        'generator_sha256':module.sha(Path(__file__)),'native_windows':True,'virtualization':False,'network':False}
    out.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf8');print(json.dumps({'status':value['status'],'copied':len(copied)}))

if __name__=='__main__':main()
