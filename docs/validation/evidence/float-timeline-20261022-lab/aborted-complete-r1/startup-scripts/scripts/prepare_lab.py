"""Isolate ordinary timeline precision work from the live V92 frozen candidate."""
from datetime import datetime,timezone
import importlib.util,json
from pathlib import Path
import shutil

ROOT=Path(__file__).resolve().parents[1]
PARENT=Path('E:/dev/sandbox/AI广告剪辑/product/.runtime/color-precision-lab-20261021')
REL=ROOT/'docs/validation/evidence/float-timeline-20261022-lab'

def main():
    assert not (ROOT/'product/src').exists() and not (REL/'foundation-r1.json').exists()
    spec=importlib.util.spec_from_file_location('parent_frozen',PARENT/'scripts/run_frozen_regression.py')
    source=importlib.util.module_from_spec(spec);spec.loader.exec_module(source)
    frozen=source.frozen();assert len(frozen)==282
    lineage=json.loads((PARENT/'docs/validation/evidence/color-precision-20261021-lab/parent-rebase-r1.json').read_bytes())
    assert frozen==lineage['frozen_after']
    foundation=json.loads((PARENT/'docs/validation/evidence/color-precision-20261021-lab/foundation-r1.json').read_bytes())
    fixtures=json.loads((PARENT/'docs/validation/evidence/color-precision-20261021-lab/external-fixtures-r1.json').read_bytes())
    names=set(frozen)|set(foundation['dependency_artifact_inputs'])|{r['path'] for r in fixtures['fixtures']}
    names|={'scripts/run_frozen_regression.py','scripts/run_with_regression_fixtures.py','scripts/materialize_regression_fixtures.py'}
    rows={}
    for name in sorted(names):
        p=PARENT/name;target=ROOT/name;assert p.is_file() and not target.exists()
        target.parent.mkdir(parents=True,exist_ok=True);digest=source.sha(p);shutil.copyfile(p,target);assert source.sha(target)==digest
        rows[name]=digest
    assert source.frozen()==frozen
    REL.mkdir(parents=True,exist_ok=True)
    record={'status':'isolated-copy-from-live-unpublished-V92-candidate','at_utc':datetime.now(timezone.utc).isoformat(),
        'parent_root':str(PARENT),'parent_frozen_inputs':frozen,'copied_files':rows,'copied_count':len(rows),
        'dependency_artifact_inputs':foundation['dependency_artifact_inputs'],'external_fixtures':fixtures['fixtures'],
        'script_sha256':source.sha(Path(__file__)),'parent_full_methods_expected':2234,
        'parent_full_passed':False,'parent_published':False,'native_windows_only':True,
        'virtualization':False,'network':False,'new_timeline_implementation_started':False}
    (REL/'foundation-r1.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    print(json.dumps({'status':record['status'],'copied':len(rows),'frozen':len(frozen)}))

if __name__=='__main__':main()
