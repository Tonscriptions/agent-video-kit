"""Preserve the pre-suite R1 failure and create a fresh R2 owner bound to V93+R16."""
import ast
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]
MAIN = ROOT.parents[2]
REL = ROOT / 'docs/validation/evidence/float-stream-20261022-lab'


def sha(path):
    return 'sha256:' + hashlib.sha256(path.read_bytes()).hexdigest()


def replace(text, old, new, count=1):
    assert text.count(old) == count, (old, text.count(old))
    return text.replace(old, new)


def main():
    evidence = REL / 'recovery-owner-r2'
    evidence.mkdir(exist_ok=False)
    for name in ('complete-r1', 'release-chain-r1'):
        path = ROOT / 'product/.runtime/float-stream-20261022' / name / 'run.json'
        data = json.loads(path.read_bytes())
        assert data['status'] == 'failed-preserved'
        if name == 'complete-r1':
            assert not data['suite_launched']
        shutil.copyfile(path, evidence / (name + '.failed.json'))
    source = ROOT / 'scripts/run_float_stream_complete.py'
    target = ROOT / 'scripts/run_float_stream_complete_r2.py'
    assert not target.exists()
    text = source.read_text('utf8')
    text = text.replace('complete-r1', 'complete-r2').replace('full-r1', 'full-r2')
    text = text.replace('external-fixtures-r1', 'external-fixtures-r2').replace('parent-binding-r1', 'parent-binding-r2')
    text = text.replace('passed-published-V93-parent-binding', 'passed-published-V93-and-R16-parent-binding')
    text = replace(text,
        "checkpoint();parent_owner=PARENT/'product/.runtime/float-timeline-20261022/release-chain-r2/run.json'",
        "checkpoint();parent_owner=MAIN/'product/.runtime/openfilm-reuse-lab-20261022-r16/product/.runtime/openfilm-r16-release/serialized-owner-r2/run.json'")
    text = replace(text,
        "if parent['status']=='published-V93-with-actual-full2280-and-installed163':break",
        "if parent['status']=='published-R16-research':break")
    text = replace(text,
        "assert parent['status'] in ('waiting-for-actual-full2280-r2','publishing-reviewed-V93-host'),parent.get('error',parent['status'])",
        "assert parent['status'] in ('checking-frozen-research-after-recovered-V93','publishing-verified-R16-research','committed-awaiting-ordinary-push'),parent.get('error',parent['status'])")
    text = replace(text,
        "publication=read(PARENT/'product/.runtime/float-timeline-20261022/publication-r2/run.json')",
        "publication=read(PARENT/'product/.runtime/float-timeline-20261022/publication-r3/run.json')")
    text = replace(text,
        "assert publication['status']=='published' and publication['commit']==publication['remote_main']==parent['commit'] and publication['main_clean'] and not publication['force_push']",
        "assert publication['status']=='published' and publication['commit']==publication['remote_main']==parent['parent_commit'] and publication['main_clean'] and not publication['force_push']\n"
        "        assert parent['published'] and parent['commit']==parent['remote_main'] and not parent['force_push']")
    old = "commit=subprocess.run(['git','-c','gc.auto=0','-c','maintenance.auto=false','rev-parse','HEAD'],cwd=MAIN,capture_output=True,check=True).stdout.decode().strip();assert commit==parent['commit']"
    new = old + "\n        def current_git(*args):\n            return subprocess.run(['git','-c','gc.auto=0','-c','maintenance.auto=false',*args],cwd=MAIN,capture_output=True,check=True).stdout\n" \
        "        assert current_git('branch','--show-current').decode().strip()=='main'\n" \
        "        assert current_git('remote','get-url','origin').decode().strip()=='git@github.com:Tonscriptions/agent-video-kit.git'\n" \
        "        assert current_git('ls-remote','origin','refs/heads/main').decode().split()[0]==commit\n" \
        "        assert not current_git('status','--porcelain','-z'),'Preserve unexpected main edits'"
    text = replace(text, old, new)
    text = replace(text, "'published_parent_commit':commit,'published_parent_frozen':parent_inputs,",
        "'published_parent_commit':commit,'published_product_commit':publication['commit'],'published_parent_frozen':parent_inputs,")
    text = replace(text,
        "'media-r4/verification.json','media-installed-r1/verification.json','discovery-r1.json')]+[fixture_path,lineage_path]",
        "'media-r4/verification.json','media-installed-r1/verification.json','discovery-r1.json',\n"
        "            'recovery-owner-r2/verification.json','recovery-owner-r2/complete-r1.failed.json',\n"
        "            'recovery-owner-r2/release-chain-r1.failed.json')]+[fixture_path,lineage_path]")
    text = replace(text, "'native_windows':True,'virtualization':False,'network':False,'published':False,'default_renderer_integrated':False}",
        "'native_windows':True,'virtualization':False,'network':False,'published':False,'default_renderer_integrated':False,\n"
        "        'prior_owner_stopped_before_suite':True,'prior_owner':'complete-r1','new_revision':'complete-r2'}")
    ast.parse(text)
    target.write_text(text, encoding='utf8', newline='\n')
    receipt = {'status': 'prepared-fresh-owner-with-preserved-pre-suite-failure',
        'at_utc': datetime.now(timezone.utc).isoformat(), 'source_script_sha256': sha(source),
        'new_script_sha256': sha(target), 'generator_sha256': sha(Path(__file__)),
        'original_full_suite_executed': False, 'new_full_suite_passed': False, 'expected_methods': 2299,
        'product_files_changed': 0, 'parent_product_version': 'V93', 'parent_documentation': 'R16',
        'failure_files': {p.name: sha(p) for p in evidence.glob('*.failed.json')}}
    (evidence / 'verification.json').write_text(json.dumps(receipt, ensure_ascii=False, indent=2)+'\n', encoding='utf8', newline='\n')
    print(json.dumps({'status': receipt['status'], 'new_script': str(target), 'full_suite_claimed_passed': False}, ensure_ascii=False))


if __name__ == '__main__':
    main()
