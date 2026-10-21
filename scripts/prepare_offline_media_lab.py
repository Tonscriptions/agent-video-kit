"""Copy the exact audio-origin candidate for native offline media dependency work."""
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import shutil

ROOT=Path(__file__).resolve().parents[1]
UPSTREAM=ROOT.parent/'audio-source-origin-lab-20261021'
REL='docs/validation/evidence/offline-media-profile-20261021-lab'


def sha(path):
    with Path(path).open('rb') as stream:return 'sha256:'+hashlib.file_digest(stream,'sha256').hexdigest()


def main():
    receipt=ROOT/REL/'foundation-r1.json'
    assert not receipt.exists() and not (ROOT/'product/src').exists()
    audit_path=UPSTREAM/'docs/validation/evidence/audio-source-origin-20261021-lab/audit-r1.json'
    audit=json.loads(audit_path.read_bytes());inputs=audit['frozen_inputs']
    assert audit['status']=='passed-standalone-audit' and len(inputs)==259
    fixture_path=UPSTREAM/'docs/validation/evidence/audio-source-origin-20261021-lab/external-fixtures-r1.json'
    fixture=json.loads(fixture_path.read_bytes());assert fixture['status']=='passed' and fixture['fixture_count']==8
    names=set(inputs)|{row['path'] for row in fixture['fixtures']}
    names|={'scripts/'+name for name in ('run_frozen_regression.py','run_with_regression_fixtures.py','materialize_regression_fixtures.py')}
    copied={}
    for name in sorted(names):
        source=UPSTREAM/name;target=ROOT/name
        assert source.is_file() and not source.is_symlink() and source.resolve().is_relative_to(UPSTREAM)
        assert not target.exists() and target.resolve().is_relative_to(ROOT)
        digest=sha(source)
        if name in inputs:assert digest==inputs[name],name
        target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(source,target)
        assert sha(target)==digest;copied[name]=digest
    for name,digest in inputs.items():assert sha(UPSTREAM/name)==sha(ROOT/name)==digest
    (ROOT/'product/.runtime/temp').mkdir(parents=True)
    receipt.parent.mkdir(parents=True)
    data={'status':'copied-exact-parent-not-implemented-or-tested','at_utc':datetime.now(timezone.utc).isoformat(),
        'source_root':str(UPSTREAM),'source_inputs':inputs,'source_audit_sha256':sha(audit_path),
        'external_fixture_manifest_sha256':sha(fixture_path),'external_fixtures':fixture['fixtures'],'copied_files':copied,
        'native_windows':True,'virtualization':False,'network':False,'main_integrated':False,'full_suite_started':False,
        'generator_sha256':sha(__file__)}
    receipt.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n')
    print(json.dumps({'status':data['status'],'frozen_inputs':len(inputs),'copied_files':len(copied)}))


if __name__=='__main__':main()
