"""Preserve scoped prior artifacts for a final combined snapshot; never relabel tests."""
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil

from run_frozen_regression import frozen, sha

ROOT=Path(__file__).resolve().parents[1]
REL=ROOT/'docs/validation/evidence/pipeline-recovery-20261023'
LABS=['float-levels-lab-20261022','float-balance-lab-20261022','float-hsl-lab-20261022',
      'float-tone-lab-20261022','float-gaussian-lab-20261022','float-spatial-lab-20261022',
      'float-sharpen-lab-20261022','float-keyer-lab-20261023']
COMMON={'docs/README.md','docs/构建进度总表_2026-10-16.md','docs/产品需求与开发路线基线_2026-10-12.md',
    'docs/Concat与剪映功能差异矩阵_2026-10-12.md','docs/validation/能力覆盖与验收矩阵_v0.1_2026-10-13.md',
    'docs/specs/AgentCLI契约_v0.1_2026-10-13.md'}


def main():
    output=REL/'lineage-r1.json';assert not output.exists()
    before=frozen();assert len(before)==330
    planned={};origins={}
    for name in LABS:
        parent=ROOT.parent/name
        files=[*(parent/'docs').rglob('*'),*(parent/'scripts').glob('*')]
        for source in files:
            if not source.is_file():continue
            assert not source.is_symlink() and source.resolve().is_relative_to(parent),str(source)
            relative=source.relative_to(parent).as_posix()
            if relative in COMMON:continue
            assert source.stat().st_size<95*(1<<20),relative
            digest=sha(source)
            if relative in planned:
                assert planned[relative]['sha256']==digest,('Different overlapping prior artifacts',relative)
            else:planned[relative]={'source':str(source),'sha256':digest,'bytes':source.stat().st_size}
            origins.setdefault(relative,[]).append(name)
    for name,row in planned.items():
        destination=ROOT/name
        if destination.exists():assert sha(destination)==row['sha256'],('Existing different recovery artifact',name)
    total=0;created=0
    for name,row in sorted(planned.items()):
        destination=ROOT/name
        if not destination.exists():
            destination.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(row['source'],destination)
            created+=1;total+=row['bytes']
        assert sha(destination)==row['sha256']==sha(Path(row['source']))
    owner_records=[]
    for name in LABS:
        parent=ROOT.parent/name
        for source in (parent/'product/.runtime').glob('*/complete-r1/run.json'):
            value=json.loads(source.read_bytes())
            assert value['status'].startswith('failed'),(name,value['status'])
            target=REL/'old-terminal-owners'/name/'complete-r1.json'
            assert not target.exists();target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(source,target)
            owner_records.append({'lab':name,'path':target.relative_to(ROOT).as_posix(),'sha256':sha(target),
                'status':value['status'],'suite_launched':value.get('suite_launched',False),
                'expected_methods':value.get('expected_methods')})
    assert frozen()==before
    value=dict(status='copied-original-prior-artifacts-with-failed-lineage-preserved',
        at_utc=datetime.now(timezone.utc).isoformat(),script_sha256=sha(Path(__file__)),
        artifacts=planned,origins=origins,created_files=created,created_bytes=total,
        old_terminal_complete_owners=owner_records,product_inputs_unchanged=True,
        new_tests_executed=0,full_suite_passed=False,published=False,full_capcut_parity=False)
    output.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n')
    print(json.dumps({'status':value['status'],'created_files':created,'created_bytes':total,'old_owners':len(owner_records)}))


if __name__=='__main__':main()
