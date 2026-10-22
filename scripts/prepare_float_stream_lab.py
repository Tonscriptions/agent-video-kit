"""Isolate streaming integration from the live frozen2280 candidate."""
from datetime import datetime,timezone
import importlib.util,json,shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];PARENT=ROOT.parent/'float-timeline-lab-20261022'

def main():
    assert not (ROOT/'product/src').exists()
    spec=importlib.util.spec_from_file_location('host_parent_freeze',PARENT/'scripts/run_frozen_regression.py');module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    current=module.frozen();assert len(current)==288
    rel=PARENT/'docs/validation/evidence/float-timeline-20261022-lab';host=json.loads((rel/'host-r3.json').read_bytes());assert host['frozen_after']==host['frozen_before']==current
    foundation=json.loads((rel/'foundation-r1.json').read_bytes());owner=json.loads((PARENT/'product/.runtime/float-timeline-20261022/complete-r2/run.json').read_bytes())
    assert owner['status'] in ('waiting-for-actual-parent-publication-and-isolated-install','running-complete-native-suite','passed-complete-native-suite-not-published')
    names=set(current)|set(foundation['dependency_artifact_inputs'])|{r['path'] for r in foundation['external_fixtures']}|{'scripts/run_frozen_regression.py','scripts/run_with_regression_fixtures.py','scripts/materialize_regression_fixtures.py'}
    assert len(names)==308;copied={}
    for name in sorted(names):
        p=PARENT/name;t=ROOT/name;assert p.is_file() and not t.exists();digest=module.sha(p);t.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,t);assert module.sha(t)==digest;copied[name]=digest
    assert module.frozen()==current
    out=ROOT/'docs/validation/evidence/float-stream-20261022-lab/foundation-r1.json';out.parent.mkdir(parents=True,exist_ok=True)
    value={'status':'isolated-copy-of-tested288-input-host-candidate','at_utc':datetime.now(timezone.utc).isoformat(),'copied_files':copied,'copied_count':len(copied),'parent_root':str(PARENT),'parent_frozen_inputs':current,
        'parent_full_status_at_copy':owner['status'],'parent_full_methods_expected':2280,'parent_published':False,'dependency_artifact_inputs':foundation['dependency_artifact_inputs'],'external_fixtures':foundation['external_fixtures'],
        'generator_sha256':module.sha(Path(__file__)),'native_windows':True,'virtualization':False,'network':False}
    out.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf8');print(json.dumps({'status':value['status'],'copied':len(copied)}))

if __name__=='__main__':main()
