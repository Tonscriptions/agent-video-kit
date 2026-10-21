"""Seed an exact verified V82 source onto the published V81 native Git base."""
import argparse
from datetime import datetime,timezone
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
from run_frozen_regression import frozen
ROOT=Path(__file__).resolve().parents[1]
BASE='5c77f58149252df1f1bbbdf0c7bd652b3b6235cd'

def sha(path):
    with path.open('rb') as stream:return 'sha256:'+hashlib.file_digest(stream,'sha256').hexdigest()

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--target',type=Path,required=True)
    target=parser.parse_args().target.resolve()
    assert target.is_relative_to(Path('E:/dev/sandbox/AI广告剪辑/product/.runtime/worktrees')) and target!=ROOT
    evidence=ROOT/'docs/validation/evidence/vfr-reverse-chunks-20261021-v82'
    regression=json.loads((evidence/'integration-r3.json').read_bytes());current=frozen()
    assert regression['terminal_ok'] and regression['methods']==50 and regression['skipped']==0
    assert regression['frozen_before']==regression['frozen_after']==current and len(current)==249
    git=['git','-c','gc.auto=0','-c','maintenance.auto=false']
    head=subprocess.check_output([*git,'rev-parse','HEAD'],cwd=target,text=True).strip();assert head==BASE
    spec=importlib.util.spec_from_file_location('target_freeze',target/'scripts/run_frozen_regression.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);before=module.frozen()
    assert len(before)==242 and set(before)<=set(current)
    changes={name for name,value in before.items() if current[name]!=value}
    assert changes=={'product/src/ai_ad_editor/'+name+'.py' for name in ('render','preview','capabilities','cli')},changes
    record={'status':'preflight-passed','started_at_utc':datetime.now(timezone.utc).isoformat(),
        'source':str(ROOT),'target':str(target),'git_base':head,'published_base_inputs':before,
        'source_inputs':current,'modified_base_inputs':sorted(changes),'added_core_inputs':sorted(set(current)-set(before))}
    for name,value in current.items():
        src=ROOT/name;dst=target/name;assert sha(src)==value
        dst.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(src,dst)
    directories=[
        'docs/validation/evidence/vfr-reverse-20261021-lab','docs/assets/vfr-reverse-20261021-lab',
        'docs/validation/evidence/vfr-reverse-chunks-20261021-v82','docs/assets/vfr-reverse-chunks-20261021-v82']
    for name in directories:shutil.copytree(ROOT/name,target/name)
    files=[
        'docs/specs/原生倒放帧区间与缓冲配额契约_原型_2026-10-21.md',
        'docs/validation/原生VFR倒放帧区间原型实测_2026-10-21.md']
    files+=['docs/specs/原生分块倒放缓存契约_v0.1_2026-10-21.md']
    files+=['scripts/'+name+'.py' for name in ('seed_reverse_chunks','probe_reverse_chunks','probe_reverse_orientation',
        'smoke_reverse_chunks','smoke_reverse_video_clock','verify_reverse_video_clock_install',
        'record_reverse_prototype','prepare_reverse_release')]
    for name in files:
        dst=target/name;dst.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/name,dst)
    after=module.frozen();assert after==current==frozen()
    record.update(status='passed',frozen_inputs_equal=True,target_inputs=after,
        copied_document_trees=directories,copied_scripts_and_documents=files,
        main_head_unchanged=BASE==subprocess.check_output([*git,'rev-parse','main'],cwd=target,text=True).strip(),
        finished_at_utc=datetime.now(timezone.utc).isoformat())
    assert record['main_head_unchanged']
    output=target/'docs/validation/evidence/vfr-reverse-chunks-20261021-v82/published-base-alignment-r1.json'
    output.write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n')
    print(json.dumps({'status':record['status'],'target':str(target),'frozen_inputs':len(after),'main_head':BASE}))

if __name__=='__main__':main()
