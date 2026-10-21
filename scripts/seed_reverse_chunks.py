"""Seed an E-drive native Git candidate from the byte-verified reverse prototype."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

ROOT=Path(__file__).resolve().parents[1]
DONOR=Path('E:/dev/sandbox/AI广告剪辑/product/.runtime/vfr-reverse-lab-20261021')
V81=Path('E:/dev/sandbox/AI广告剪辑/product/.runtime/worktrees/curve-clock-v81')

def sha(path):
    with path.open('rb') as stream:return 'sha256:'+hashlib.file_digest(stream,'sha256').hexdigest()

def main():
    assert ROOT==Path('E:/dev/sandbox/AI广告剪辑/product/.runtime/worktrees/reverse-chunks-v82')
    assert subprocess.check_output(['git','-c','gc.auto=0','-c','maintenance.auto=false','branch','--show-current'],cwd=ROOT,text=True).strip()=='work/vfr-reverse-chunks-v82'
    target=ROOT/'docs/validation/evidence/vfr-reverse-chunks-20261021-v82/foundation-r1.json'
    assert not target.exists()
    receipt=DONOR/'docs/validation/evidence/vfr-reverse-20261021-lab/prototype-audit-r1.json'
    origin=json.loads(receipt.read_bytes());assert origin['status']=='passed'
    inputs=origin['frozen_inputs'];assert len(inputs)==245
    assert all(sha(DONOR/name)==expected for name,expected in inputs.items())
    for name in inputs:
        path=ROOT/name;path.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(DONOR/name,path)
    assert all(sha(ROOT/name)==expected for name,expected in inputs.items())
    name='product/tests/test_cli.py'
    running=json.loads((V81/'docs/validation/evidence/cfr-boundaries-20261021-v81/full-r2.source.json').read_bytes())
    expected=running['frozen_before'][name]
    assert sha(V81/name)==expected
    before=sha(ROOT/name);assert before!=expected
    shutil.copyfile(V81/name,ROOT/name)
    for path in (DONOR/'scripts').glob('*.py'):
        if path.name=='seed_reverse_chunks.py':continue
        shutil.copyfile(path,ROOT/'scripts'/path.name)
    for prefix in ('docs/validation/evidence/vfr-reverse-20261021-lab','docs/assets/vfr-reverse-20261021-lab'):
        for path in (DONOR/prefix).rglob('*'):
            if path.is_file():
                out=ROOT/path.relative_to(DONOR);out.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(path,out)
    for name in ('docs/specs/原生倒放帧区间与缓冲配额契约_原型_2026-10-21.md',
                 'docs/validation/原生VFR倒放帧区间原型实测_2026-10-21.md'):
        out=ROOT/name;out.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(DONOR/name,out)
    current={name:sha(ROOT/name) for name in inputs}
    assert [name for name in inputs if inputs[name]!=current[name]]==['product/tests/test_cli.py']
    target.parent.mkdir(parents=True,exist_ok=True)
    value={'recorded_at_utc':datetime.now(timezone.utc).isoformat(),'branch':'work/vfr-reverse-chunks-v82',
        'git_base':'1f9ef4e0c37212424ec20962a725ccf78c596261','donor_audit_sha256':sha(receipt),
        'donor_root':str(DONOR),'donor_inputs':inputs,'initial_inputs':current,
        'V81_test_only_alignment':{'path':'product/tests/test_cli.py','before':before,'after':expected,
                                  'basis':'V81/full-r2.source.json/frozen_before'},
        'main_modified':False,'virtualization':False,'network':False,
        'historical_prototype_evidence_claims_current_source':False,
        'generator_sha256':sha(Path(__file__))}
    target.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n')
    (target.parent/'executed-seed.py.txt').write_bytes(Path(__file__).read_bytes())
    print(json.dumps({'frozen_inputs':len(current),'aligned_tests':1,'runtime_changed_during_seed':False}))

if __name__=='__main__':main()
