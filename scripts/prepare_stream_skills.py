"""Validate four unregistered native-stream coverage Skill deltas; canonical Skills stay untouched."""
from pathlib import Path
import subprocess
import sys
from smoke_multicam_stream_coverage import sha, write

ROOT = Path(__file__).resolve().parents[1]
MAIN = Path('E:/dev/sandbox/AI广告剪辑')
REL = ROOT / 'docs/validation/evidence/multicam-stream-coverage-20261021-lab'
MARKER = 'MULTICAM-NATIVE-STREAM-COVERAGE-LAB-20261021'


def main():
    output = REL / 'skills-draft-r1.json'
    assert not output.exists()
    roles = {
        'video-cut-agent-editor': 'For multicam_source_coverage 0.3.0, use actual native-video coverage, independently of the longer container/audio duration. Review native bounds before authoring camera switches.',
        'video-cut-timeline': 'Keep reference events at their original positions: source_time = reference_time + relative_delay_seconds. Trim intersects actual first/last native-video intervals, retains unity speed and preserves leading/trailing gaps.',
        'video-cut-quality': 'Inspect full lossless RGBA and explicit master PCM, native first/last PTS plus duration, both output gaps and encoded PTS. Identity patches and MP4-derived GIFs establish separate bounded checks.',
        'video-cut-video-understand': 'Audio-offset analysis and native-video coverage are separate. Audio-only analysis may return valid delays with unknown video-coverage diagnostics; authoring a switch to that camera must refuse unknown coverage.',
    }
    validator = Path('C:/Users/carzy/.codex/skills/.system/skill-creator/scripts/quick_validate.py')
    record = {'status':'preparing','registered':False,'new_block_marker':MARKER,'skills':{}}
    for name, role in roles.items():
        parent = MAIN / 'skills' / name / 'SKILL.md'
        body = parent.read_text('utf-8')
        assert MARKER not in body
        snapshot = REL / 'skill-parent-snapshots-r1' / (name+'.md')
        snapshot.parent.mkdir(parents=True,exist_ok=True)
        assert not snapshot.exists()
        snapshot.write_bytes(parent.read_bytes())
        block = f'''<!-- {MARKER} -->
{role}
Native coverage uses first PTS, last PTS plus known duration, native time_base and the renderer's demux-origin rounding; retain the exact rational boundaries from the report. Container duration alone cannot establish video coverage.
Default shortfall policy rejects. Explicit trim leaves gaps at original reference positions; stretch clamps to the real first native frame, changes event timing and must retain its warning. Completely disjoint coverage rejects under every policy.
Dry-run reads existing verified native indices without writing caches, reports, snapshots or authored files. A hit reports zero source-frame probes but still reads hashes. Corrupt indices or changed source SHA reject; do not silently repair them or convert integrity errors into successful audio-only analysis.
Read the [native coverage contract](../../docs/specs/多机位原生帧覆盖与只读索引契约_实验_v0.1_2026-10-21.md) and [fresh native/isolated evidence](../../docs/validation/多机位原生视频覆盖独立实验_2026-10-21.md).
The base seven-wheel installer does not ship NumPy. This experiment explicitly copies the existing local NumPy 2.4.2 distribution with RECORD hashes and licenses; it is not automatic dependency installation.
Unknown-EOF audio-analysis controls include simulated video state. Nonzero audio stream origin, clock drift, natural multicamera quality, HDR, long-form/RSS, continuous playback and listening remain separate acceptance work.
This is an unregistered candidate; complete regression and main integration remain pending.
<!-- /{MARKER} -->'''
        position = body.index('\n---',3)+4 if body.startswith('---\n') else body.index('\n')
        folder = ROOT / 'skills' / name
        folder.mkdir(parents=True)
        target = folder/'SKILL.md'
        target.write_text(body[:position]+'\n\n'+block+'\n'+body[position:],encoding='utf-8',newline='\n')
        result = subprocess.run([sys.executable,'-E','-B','-X','utf8',validator,folder],cwd=ROOT,capture_output=True,timeout=60)
        assert result.returncode==0,result.stdout.decode('utf-8','replace')+result.stderr.decode('utf-8','replace')
        record['skills'][name] = {'path':target.relative_to(ROOT).as_posix(),'sha256':sha(target),
            'parent_sha256':sha(parent),'parent_snapshot':snapshot.relative_to(ROOT).as_posix(),
            'new_block':block,'registered':False,'validator_exit_code':result.returncode,
            'validator_stdout':result.stdout.decode('utf-8','replace')}
    record.update(status='passed-four-unregistered-drafts',skill_count=4,generator_sha256=sha(__file__),
        parent_merge_policy='Insert only this new block into actual published V86 parents; do not replace their full bodies with these earlier snapshots.')
    write(output,record)
    print('four native-stream coverage Skill deltas validated; canonical Skills unchanged')


if __name__=='__main__':
    main()
