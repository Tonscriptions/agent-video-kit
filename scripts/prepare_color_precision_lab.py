"""Copy exact running V91 inputs; do not modify them or claim parent publication."""
from datetime import datetime,timezone
import importlib.util
import json
from pathlib import Path
import shutil

ROOT=Path(__file__).resolve().parents[1]
PARENT=Path('E:/dev/sandbox/AI广告剪辑/product/.runtime/audio-discontinuity-lab-20261021')
REL=ROOT/'docs/validation/evidence/color-precision-20261021-lab'
assert not (ROOT/'product').exists() and not REL.exists()
spec=importlib.util.spec_from_file_location('V91_running_parent_frozen_inputs',PARENT/'scripts/run_frozen_regression.py')
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
before=module.frozen();assert len(before)==267
audit=json.loads((PARENT/'docs/validation/evidence/audio-discontinuity-20261021-lab/audit-r1.json').read_bytes())
assert audit['frozen_inputs']==before and len(audit['fixture_inputs'])==8 and len(audit['dependency_artifact_inputs'])==9
names=set(before)|set(audit['fixture_inputs'])|set(audit['dependency_artifact_inputs'])|{
    'scripts/run_frozen_regression.py','scripts/run_with_regression_fixtures.py','scripts/materialize_regression_fixtures.py'}
copied={}
for name in sorted(names):
    source=PARENT/name;target=ROOT/name
    assert source.is_file() and not source.is_symlink() and not target.exists()
    target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(source,target)
    assert module.sha(source)==module.sha(target)
    copied[name]=module.sha(target)
assert module.frozen()==before and len(copied)==287
(ROOT/'product/.runtime/temp').mkdir(parents=True)
REL.mkdir(parents=True)
record={'status':'copied-exact-unpublished-V91-parent-inputs','created_at_utc':datetime.now(timezone.utc).isoformat(),
    'source_root':str(PARENT),'source_inputs':before,'external_fixture_inputs':audit['fixture_inputs'],
    'dependency_artifact_inputs':audit['dependency_artifact_inputs'],'copied_files':copied,'copied_count':287,
    'parent_inputs_unchanged':True,'parent_full_methods_expected':2145,'parent_full_pass_or_publication_claimed':False,
    'new_features_implemented':False,'native_windows':True,'virtualization':False,'network':False,
    'generator_sha256':module.sha(Path(__file__))}
(REL/'foundation-r1.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n')
print(json.dumps({'status':record['status'],'copied_files':287,'parent_source_unchanged':True}))
