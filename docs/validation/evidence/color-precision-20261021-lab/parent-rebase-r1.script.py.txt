"""Rebase only the two queue fixes from actually published V91, retaining proof."""
from datetime import datetime,timezone
import importlib.util,json,subprocess
from pathlib import Path
from run_frozen_regression import frozen,sha

ROOT=Path(__file__).resolve().parents[1]
MAIN=Path('E:/dev/sandbox/AI广告剪辑')
REL=ROOT/'docs/validation/evidence/color-precision-20261021-lab'
PARENT='18f5dc766a80e0b47f096b1b93ccfe1cee0fb5f6'

def main():
    output=REL/'parent-rebase-r1.json';backup=REL/'before-parent-rebase-r1';assert not output.exists() and not backup.exists()
    before=frozen();kernel=json.loads((REL/'kernel-r11.json').read_bytes());assert before==kernel['frozen_after'] and len(before)==282
    publication=MAIN/'product/.runtime/audio-discontinuity-lab-20261021/product/.runtime/audio-discontinuity-20261021/publication-r2/run.json'
    p=json.loads(publication.read_bytes());assert p['status']=='published' and p['commit']==p['remote_main']==PARENT and p['main_clean']
    for ref in ('HEAD','origin/main'):
        assert subprocess.run(['git','-c','gc.auto=0','-c','maintenance.auto=false','rev-parse',ref],cwd=MAIN,check=True,capture_output=True,text=True).stdout.strip()==PARENT
    spec=importlib.util.spec_from_file_location('published_inventory',MAIN/'scripts/run_frozen_regression.py');module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    parent=module.frozen();assert len(parent)==267 and set(parent)<=set(before)
    modified=sorted(k for k in parent if parent[k]!=before[k])
    targets=['product/src/ai_ad_editor/queue_reuse.py','product/tests/test_queue_reuse.py']
    assert modified==sorted([*targets,'product/src/ai_ad_editor/cli.py','product/src/ai_ad_editor/capabilities.py'])
    backup.mkdir(parents=True);copies=[]
    for name in targets:
        source=MAIN/name;destination=ROOT/name;old=backup/name;old.parent.mkdir(parents=True,exist_ok=True);old.write_bytes(destination.read_bytes())
        assert sha(source)==parent[name] and sha(old)==before[name]
        destination.write_bytes(source.read_bytes());assert sha(destination)==parent[name]
        copies.append({'path':name,'before_sha256':before[name],'published_after_sha256':sha(destination),'saved_before':old.relative_to(ROOT).as_posix()})
    (backup/'manifest.json').write_text(json.dumps({'reason':'Preserve V91 queue pre-fix inputs before exact two-file migration from published parent','copies':copies},ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    after=frozen();assert set(after)==set(before) and sorted(k for k in before if before[k]!=after[k])==targets
    remaining=sorted(k for k in parent if parent[k]!=after[k]);assert remaining==['product/src/ai_ad_editor/capabilities.py','product/src/ai_ad_editor/cli.py']
    record={'status':'passed-exact-two-file-rebase-from-published-V91','at_utc':datetime.now(timezone.utc).isoformat(),
        'published_parent_commit':PARENT,'publication_receipt_sha256':sha(publication),'published_full_receipt_sha256':sha(MAIN/'docs/validation/evidence/audio-discontinuity-20261021-lab/full-r2.json'),
        'kernel_r11_before_rebase_sha256':sha(REL/'kernel-r11.json'),'frozen_before':before,'frozen_after':after,'published_parent_frozen':parent,
        'copied':copies,'remaining_common_changes':remaining,'new_product_inputs':sorted(set(after)-set(parent)),
        'new_methods_pre_rebase':86,'published_parent_methods':2148,'expected_complete_methods':2234,
        'complete_suite_started':False,'complete_suite_passed':False,'bundle_editor_commands_implemented':True,
        'timeline_renderer_integrated':False,'published':False}
    output.write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf8');output.with_suffix('.script.py.txt').write_bytes(Path(__file__).read_bytes())
    print(json.dumps({'status':record['status'],'frozen':len(after),'copied':len(copies),'new_inputs':len(record['new_product_inputs']),'expected_complete_methods':2234}))
if __name__=='__main__':main()
