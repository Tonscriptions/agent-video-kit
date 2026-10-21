"""Prepare four unregistered deltas for the local multicamera coverage CLI."""
from pathlib import Path
import subprocess
import sys
from smoke_multicam_source_range import sha, write

ROOT = Path(__file__).resolve().parents[1]
MAIN = Path('E:/dev/sandbox/AI广告剪辑')
REL = ROOT / 'docs/validation/evidence/multicam-source-range-20261021-lab'
MARKER = 'MULTICAM-SOURCE-COVERAGE-LAB-20261021'


def main():
    output = REL / 'skills-draft-r1.json'
    assert not output.exists()
    roles = {
        'video-cut-agent-editor': 'Use the advertised source_shortfall policy when building media multicam plans; preserve the requested master duration and explicit audio tracks.',
        'video-cut-timeline': 'Review original requested intervals and actual covered intervals separately; trim preserves unity speed and places clips at their original reference event positions.',
        'video-cut-quality': 'Compare complete lossless event frames, both timeline gaps, explicit master PCM and output PTS. Encoded identity patches and GIFs have separate acceptance limits.',
        'video-cut-video-understand': 'Interpret relative_delay_seconds as source_time = reference_time + delay. The 50 Hz envelope estimates one offset; it does not estimate clock drift or choose semantic shots.',
    }
    validator = Path('C:/Users/carzy/.codex/skills/.system/skill-creator/scripts/quick_validate.py')
    record = {'status': 'preparing', 'registered': False, 'new_block_marker': MARKER, 'skills': {}}
    for name, role in roles.items():
        parent = MAIN / 'skills' / name / 'SKILL.md'
        body = parent.read_text('utf8')
        assert MARKER not in body
        snapshot = REL / 'skill-parent-snapshots-r1' / (name + '.md')
        snapshot.parent.mkdir(parents=True, exist_ok=True)
        snapshot.write_bytes(parent.read_bytes())
        block = f'''<!-- {MARKER} -->
{role}
When multicam_source_coverage is advertised, coverage shortfall defaults to reject. Explicit --source-shortfall trim intersects source coverage and leaves gaps; stretch clamps or slows and warns that event sync changes.
Completely disjoint coverage, locked apply targets and sub-tick segments reject. Dry-run performs audio analysis but writes no report or authored project.
Read the [coverage contract](../../docs/specs/多机位源覆盖与显式缺口策略_实验_v0.1_2026-10-21.md) and [real native/isolated evidence](../../docs/validation/多机位源覆盖与原速同步独立实验_2026-10-21.md).
NumPy is an explicit local dependency; the base seven-wheel bundle does not contain it. The isolated experiment copies the existing 2.4.2 distribution, without runtime installation or download.
Container duration does not establish per-stream video EOF. Offset confidence, tick rounding and natural multicamera quality require separate review.
This is an unregistered candidate; complete regression and main integration remain pending.
<!-- /{MARKER} -->'''
        position = body.index('\n---', 3) + 4 if body.startswith('---\n') else body.index('\n')
        draft = ROOT / 'skills' / name
        draft.mkdir(parents=True)
        target = draft / 'SKILL.md'
        target.write_text(body[:position] + '\n\n' + block + '\n' + body[position:], encoding='utf8', newline='\n')
        result = subprocess.run([sys.executable, '-E', '-B', '-X', 'utf8', validator, draft], cwd=ROOT, capture_output=True, timeout=60)
        assert result.returncode == 0, result.stdout.decode('utf8', 'replace') + result.stderr.decode('utf8', 'replace')
        record['skills'][name] = {'path': target.relative_to(ROOT).as_posix(), 'sha256': sha(target),
            'parent_sha256': sha(parent), 'parent_snapshot': snapshot.relative_to(ROOT).as_posix(),
            'new_block': block, 'registered': False, 'validator_exit_code': result.returncode,
            'validator_stdout': result.stdout.decode('utf8', 'replace')}
    record.update(status='passed-four-unregistered-drafts', skill_count=4, generator_sha256=sha(__file__))
    write(output, record)
    print('four unregistered video-cut Skill drafts validated; canonical Skills unchanged')


if __name__ == '__main__':
    main()
