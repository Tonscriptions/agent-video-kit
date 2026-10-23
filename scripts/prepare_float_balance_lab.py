"""Copy the accepted, frozen levels candidate without touching live owners."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]
PARENT = ROOT.parent/'float-levels-lab-20261022'
REL = ROOT/'docs/validation/evidence/float-balance-20261022-lab'

def sha(path):
    return 'sha256:'+hashlib.sha256(path.read_bytes()).hexdigest()

def main():
    REL.mkdir(parents=True, exist_ok=True)
    assert not (REL/'foundation-r1.json').exists()
    proof_path=PARENT/'docs/validation/evidence/float-levels-20261022-lab/native-r2/verification.json'
    proof=json.loads(proof_path.read_bytes())
    assert proof['status']=='passed' and proof['methods']==242 and proof['skipped']==0
    assert proof['frozen_equal'] and proof['frozen_before']==proof['frozen_after']
    inputs=proof['frozen_after'];assert len(inputs)==314
    foundation=json.loads((PARENT/'docs/validation/evidence/float-levels-20261022-lab/foundation-r1.json').read_bytes())
    dependencies,fixtures=foundation['dependency_artifact_inputs'],foundation['external_fixtures']
    assert len(dependencies)==9 and len(fixtures)==8
    paths=dict(inputs,**dependencies)
    paths.update({item['path']:item['sha256'] for item in fixtures})
    for name in ('run_frozen_regression.py','run_with_regression_fixtures.py','materialize_regression_fixtures.py'):
        paths['scripts/'+name]=sha(PARENT/'scripts'/name)
    for name,expected in paths.items():
        source,destination=PARENT/name,ROOT/name
        assert sha(source)==expected,name
        destination.parent.mkdir(parents=True,exist_ok=True)
        assert not destination.exists(),name
        shutil.copyfile(source,destination)
        assert sha(source)==expected==sha(destination),name
    receipt={'status':'copied-exact-source-verified-levels314-candidate',
             'at_utc':datetime.now(timezone.utc).isoformat(),'parent_root':str(PARENT),
             'parent_source_proof':str(proof_path),'parent_source_proof_sha256':sha(proof_path),
             'parent_source_methods':242,'parent_complete_suite_passed_at_copy':False,
             'parent_published_at_copy':False,'parent_frozen_inputs':inputs,
             'copied_inputs':paths,'copied_count':len(paths),
             'dependency_artifact_inputs':dependencies,'external_fixtures':fixtures,
             'native_windows':True,'virtualization':False,'full_capcut_parity':False}
    (REL/'foundation-r1.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    (ROOT/'product/.runtime/temp').mkdir(parents=True,exist_ok=True)
    print(json.dumps({'copied_count':len(paths),'products':len(inputs),'dependencies':len(dependencies),'fixtures':len(fixtures)}))

if __name__=='__main__':main()
