"""Prepare four unregistered offline-profile deltas against the actually published V87."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]
MAIN=Path('E:/dev/sandbox/AI广告剪辑')
REL=ROOT/'docs/validation/evidence/offline-media-profile-20261021-lab'
MARKER='OFFLINE-MEDIA-PROFILE-LAB-20261021'


def sha(path):
    with Path(path).open('rb') as stream:return 'sha256:'+hashlib.file_digest(stream,'sha256').hexdigest()


def main():
    output=REL/'skills-draft-r1.json';assert not output.exists()
    publication=MAIN/'product/.runtime/multicam-stream-coverage-lab-20261021/product/.runtime/multicam-stream-coverage-20261021/publication-r1/run.json'
    parent=json.loads(publication.read_bytes());assert parent['status']=='published' and parent['main_clean'] and parent['full_methods']==2019
    command=['git','-c','gc.auto=0','-c','maintenance.auto=false']
    actual=subprocess.check_output([*command,'rev-parse','HEAD'],cwd=MAIN,timeout=60).decode().strip()
    assert actual==parent['commit']==parent['remote_main']
    assert not subprocess.check_output([*command,'status','--porcelain'],cwd=MAIN,timeout=60).strip()
    installed=json.loads((REL/'installed-r1/verification.json').read_bytes())
    assert installed['status']=='passed' and installed['bundle']['wheels']==8 and installed['numpy_distribution']['base_bundle_includes_numpy']
    roles={
        'video-cut-agent-editor':'Use the complete media-analysis-v1 eight-wheel bundle for the current product. Run its copied native installer with the separately reviewed manifest SHA; launch the installed CLI with native Python -I -S -B and run.py.',
        'video-cut-timeline':'The media profile includes NumPy needed by source analysis and editing paths. Keep authored audio/video clocks and explicit master audio unchanged; installing a dependency is not a new timing or effect-quality acceptance.',
        'video-cut-quality':'Check eight local module origins, both NumPy .pyd origins, dot/solve/FFT execution and preserved license files. The pinned2.4.2 evidence compares931 original wheel files except pip-rewritten RECORD; do not replace these checks with host import success.',
        'video-cut-video-understand':'Multicam analysis can use NumPy from the actual offline bundle. Development-time source acquisition, offline build/install, model registration and media inference are separate steps; analysis must not download missing dependencies or model weights.',
    }
    old='Seven base offline wheels do not include NumPy; isolated evidence uses an explicit readonly RECORD/license-verified copy of existing local NumPy 2.4.2. Do not treat that copy as automatic dependency installation.'
    new='The current media-analysis-v1 profile ships eight pinned offline wheels, including NumPy 2.4.2. Earlier font-text-v1 experiments used an explicit local NumPy copy; those historical receipts do not establish the current profile. Verify the current bundle manifest, native-operation audit and module origins before use.'
    record={'status':'preparing','registered':False,'new_block_marker':MARKER,'skills':{},
        'published_snapshot_parent_commit':actual,'future_parent_refresh':{'before':old,'after':new,'require_each_actual_V88_parent':True},
        'merge_policy':'Only insert the new block and exact reviewed refresh into the actually published V88 parents; never replace full bodies with these V87 snapshots.'}
    validator=Path('C:/Users/carzy/.codex/skills/.system/skill-creator/scripts/quick_validate.py')
    for name,role in roles.items():
        path=MAIN/'skills'/name/'SKILL.md';body=path.read_text('utf8');assert MARKER not in body
        snapshot=REL/'skill-parent-snapshots-r1'/(name+'.md');snapshot.parent.mkdir(parents=True,exist_ok=True)
        assert not snapshot.exists();snapshot.write_bytes(path.read_bytes())
        block=f'''<!-- {MARKER} -->
{role}
Read the [offline media profile contract](../../docs/specs/离线媒体运行时与NumPy交付_实验_v0.1_2026-10-21.md) and [fresh native/installed evidence](../../docs/validation/八轮离线媒体运行时独立实验_2026-10-21.md).
The official pinned NumPy2.4.2 cp313 Windows x64 wheel and original notices are verified locally. The fresh eight-wheel install does not copy host NumPy and does not create a virtual environment, download at runtime or change global site-packages. Existing native Python/pip and FFmpeg are prerequisites.
Older core-v1/font-text-v1 bundles remain accepted only for products whose declared dependencies fit those profiles. Current products declaring NumPy require media-analysis-v1. Missing or changed sources must fail before building the product wheel.
This acceptance covers the stated pinned platform and synthetic media. A general dependency resolver, other ABIs, full model distribution, natural/HDR/long-form/RSS/playback/listening and complete CapCut parity are separate acceptance work.
This is an unregistered candidate; complete regression and main integration remain pending.
<!-- /{MARKER} -->'''
        at=body.index('\n---',3)+4 if body.startswith('---\n') else body.index('\n')
        folder=ROOT/'skills'/name;folder.mkdir(parents=True);target=folder/'SKILL.md'
        target.write_text(body[:at]+'\n\n'+block+'\n'+body[at:],encoding='utf8',newline='\n')
        result=subprocess.run([sys.executable,'-E','-B','-X','utf8',str(validator),str(folder)],cwd=ROOT,capture_output=True,timeout=60)
        assert result.returncode==0,result.stdout.decode('utf8','replace')+result.stderr.decode('utf8','replace')
        record['skills'][name]={'path':target.relative_to(ROOT).as_posix(),'sha256':sha(target),'parent_sha256':sha(path),
            'parent_snapshot':snapshot.relative_to(ROOT).as_posix(),'new_block':block,'registered':False,
            'validator_exit_code':result.returncode,'validator_stdout':result.stdout.decode('utf8','replace')}
    record.update(status='passed-four-unregistered-drafts',skill_count=4,generator_sha256=sha(__file__))
    output.write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n')
    print(json.dumps({'status':record['status'],'skill_count':4,'registered':False,'snapshot_parent_commit':actual}))


if __name__=='__main__':main()
