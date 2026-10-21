"""Prepare four unregistered Skill deltas for the native nested-clock candidate."""
from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
MAIN = Path('E:/dev/sandbox/AI广告剪辑')
REL = 'docs/validation/evidence/nested-native-clock-20261021-lab'
CONTRACT = 'docs/specs/嵌套原生VFR时钟契约_实验_v0.1_2026-10-21.md'
REPORT = 'docs/validation/嵌套原生VFR时钟独立实验_2026-10-21.md'
MARKER = 'NATIVE-NESTED-CLOCK-LAB-20261021'
ROLES = {
    'video-cut-agent-editor': 'Keep the editable parent/child author graph and original source ranges. Report the advertised native-leaf scope when explaining the render plan.',
    'video-cut-timeline': 'Keep each reverse on its authored container and speed curves in their original source domain. Preserve cut-ins inside native frame holds and explicit authored duration.',
    'video-cut-quality': 'Compare every lossless reference frame and encoded PTS, including leading/trailing gaps. Identical repeated index descriptors are metadata aliases; preserve differing statuses and counts when reviewing source-index scans.',
    'video-cut-project-ops': 'Keep native-video-index and reverse-video files as verified derived caches. Transfer author recipes; use public cache list/prune operations and preserve current authored-reference protection.',
}


def sha(path):
    with Path(path).open('rb') as stream:
        return 'sha256:' + hashlib.file_digest(stream, 'sha256').hexdigest()


def main():
    evidence = ROOT / REL / 'skills-draft-r1.json'
    assert not evidence.exists()
    validator = Path('C:/Users/carzy/.codex/skills/.system/skill-creator/scripts/quick_validate.py')
    assert validator.is_file()
    audit = json.loads((ROOT / REL / 'audit-r1.json').read_bytes())
    assert audit['status'] == 'passed-standalone-audit' and audit['targeted_methods'] == 277
    rows = []
    snapshots = ROOT / REL / 'skills-parent-r1'
    snapshots.mkdir()
    temp = ROOT / 'product/.runtime/temp'
    temp.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ)
    env.update(TEMP=str(temp), TMP=str(temp), TMPDIR=str(temp), PYTHONDONTWRITEBYTECODE='1')
    old_probe = 'index probe that still runs on cache hits. Raster estimates are not process RSS guarantees.'
    new_probe = ('index probe. When capabilities expose native_video_frame_index, verified index hits skip that probe;\n'
                 'source/runtime SHA reads remain. Raster estimates are not process RSS guarantees.')
    old_clock = 'maps and explicit source CFR normalization. Audio still uses atempo windows'
    new_clock = ('maps and the selected source-clock policy. With nested_native_video_clock, native video leaves\n'
                 'retain original PTS/duration; virtual inline surfaces retain their child CFR contract. Audio still uses atempo windows')
    for name, role in ROLES.items():
        source = MAIN / 'skills' / name / 'SKILL.md'
        before = sha(source)
        text = source.read_text('utf8')
        parent_snapshot = snapshots / (name + '.md')
        parent_snapshot.write_bytes(source.read_bytes())
        assert text.count(old_probe) == 1
        text = text.replace(old_probe, new_probe)
        replacements = [{'old': old_probe, 'new': new_probe}]
        if name == 'video-cut-timeline':
            assert text.count(old_clock) == 1
            text = text.replace(old_clock, new_clock)
            replacements.append({'old': old_clock, 'new': new_clock})
        block = f'''When capabilities expose `nested_native_video_clock`, registered native video leaves preserve original PTS/duration through composed author clocks.
Use existing authored clips, source ticks, speed curves and reverse fields. Preserve native frame holds and real video EOF.
Virtual inline surfaces retain child CFR; general nested VFR effect combinations still need separate acceptance.
{role}
Read the [native nested-clock contract](../../{CONTRACT}) and [actual native/isolated evidence](../../{REPORT}).
Verified index hits skip full-source frame scans only; source/runtime hashes and final decode/encode remain. Existing expression, memory and disk limits apply.
The 32 new native interval oracles are part of 277 related methods. These proofs do not establish full CapCut parity, natural/HDR quality, audio quality, long-duration latency or total RSS.'''
        draft = ROOT / 'skills' / name
        assert not draft.exists()
        draft.mkdir(parents=True)
        target = draft / 'SKILL.md'
        target.write_text(text.rstrip() + '\n\n<!-- ' + MARKER + ' -->\n' + block + '\n<!-- /' + MARKER + ' -->\n', encoding='utf8', newline='\n')
        result = subprocess.run([sys.executable, '-E', '-B', '-X', 'utf8', str(validator), str(draft)],
                                cwd=ROOT, env=env, capture_output=True, timeout=60)
        assert result.returncode == 0, result.stdout + result.stderr
        links = []
        for token in re.findall(r'\[[^\]]*\]\(([^)\n]+)\)', block):
            resolved = (target.parent / token).resolve()
            assert resolved.is_relative_to(ROOT) and resolved.is_file()
            links.append(resolved.relative_to(ROOT).as_posix())
        assert sha(source) == before
        registered = Path('C:/Users/carzy/.codex/skills') / name
        assert registered.resolve() == (MAIN / 'skills' / name).resolve()
        rows.append({'skill': name, 'draft_sha256': sha(target), 'main_parent_sha256': before,
                     'main_parent_snapshot': parent_snapshot.relative_to(ROOT).as_posix(),
                     'new_block': block, 'planned_replacements': replacements,
                     'validator_exit_code': result.returncode, 'validator_stdout': result.stdout.decode('utf8').strip(),
                     'new_block_local_links': links, 'registered_path_still_main': True})
    record = {'status': 'passed-four-unregistered-skill-drafts', 'skill_count': 4, 'main_modified': False,
              'registration_changed': False, 'validator_sha256': sha(validator), 'generator_sha256': sha(__file__),
              'new_block_marker': MARKER, 'scope': 'Draft structure and new-block links; unchanged parent references retain their main audit and require the full 17-Skill audit before publication.',
              'V83_index_probe_guidance_correction_included': True, 'results': rows}
    evidence.write_text(json.dumps(record, ensure_ascii=False, indent=2) + '\n', encoding='utf8', newline='\n')
    print(json.dumps({k: record[k] for k in ('status', 'skill_count', 'main_modified', 'registration_changed')}))


if __name__ == '__main__':
    main()
