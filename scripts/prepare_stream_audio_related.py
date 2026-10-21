"""Bind the audio-only correction to a fresh 104-method integration run."""
from __future__ import annotations

import ast
import difflib
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REL = ROOT / 'docs/validation/evidence/multicam-stream-coverage-20261021-lab'


def sha(path):
    with Path(path).open('rb') as stream:
        return 'sha256:' + hashlib.file_digest(stream, 'sha256').hexdigest()


def main():
    source = ROOT / 'scripts/run_stream_related_regressions.py'
    target = ROOT / 'scripts/run_stream_related_regressions_r2.py'
    assert not target.exists()
    previous = json.loads((REL / 'related-r1.json').read_bytes())
    control = json.loads((REL / 'audio-only-after-r1.json').read_bytes())
    assert previous['terminal_ok'] and previous['methods'] == previous['distinct_methods'] == 102
    assert control['terminal_ok'] and control['methods'] == control['distinct_methods'] == 2
    assert control['frozen_before'] == control['frozen_after']
    changed = {name for name in previous['frozen_before'] if previous['frozen_before'][name] != control['frozen_before'][name]}
    assert changed == {'product/src/ai_ad_editor/multicam.py', 'product/src/ai_ad_editor/capabilities.py', 'product/tests/test_multicam_stream_coverage.py'}
    before = source.read_text('utf8')
    after = before.replace("output = REL / 'related-r1.json'", "output = REL / 'related-r2.json'")
    after = after.replace("REL / 'after-r2.json'", "REL / 'audio-only-after-r1.json'")
    after = after.replace("expected['methods'] == 22", "expected['methods'] == 2")
    after = after.replace("'expected_methods': 102", "'expected_methods': 104")
    after = after.replace('int(match[1]) == 102', 'int(match[1]) == 104').replace('len(set(ids)) == 102', 'len(set(ids)) == 104')
    after = after.replace('run_stream_related_regressions.py', 'run_stream_related_regressions_r2.py')
    after = after.replace("'prepare_stream_related.py')", "'prepare_stream_audio_related.py', 'run_stream_audio_controls.py', 'run_stream_related_regressions.py')")
    assert "== 102" not in after and "'expected_methods': 102" not in after
    compile(after, str(target), 'exec')
    target.write_text(after, encoding='utf8', newline='\n')
    record = {'status': 'prepared-not-executed', 'expected_methods': 104, 'new_method_count': 24,
        'parent_integration_methods': 102, 'prior_102_sha256': sha(REL / 'related-r1.json'),
        'current_two_control_sha256': sha(REL / 'audio-only-after-r1.json'), 'changed_since_102': sorted(changed),
        'source_runner_sha256': sha(source), 'runner_sha256': sha(target), 'generator_sha256': sha(__file__),
        'scope': '24 current native-video coverage methods +22 parent multicam +16 empty-window +32 nested clock +10 existing CLI; no sum with historical102.'}
    (REL / 'related-preparation-r2.json').write_text(json.dumps(record, ensure_ascii=False, indent=2) + '\n', encoding='utf8', newline='\n')
    (REL / 'related-preparation-r2.patch').write_text(''.join(difflib.unified_diff(before.splitlines(True), after.splitlines(True), fromfile=source.name, tofile=target.name)), encoding='utf8', newline='\n')
    print(json.dumps({'status': record['status'], 'expected_methods': 104}))


if __name__ == '__main__':
    main()
