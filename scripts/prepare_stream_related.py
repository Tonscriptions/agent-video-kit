"""Reuse the bounded multicamera integration runner for native stream coverage."""
from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PARENT = ROOT.parent / 'multicam-source-range-lab-20261021'
REL = ROOT / 'docs/validation/evidence/multicam-stream-coverage-20261021-lab'


def sha(path):
    with Path(path).open('rb') as stream:
        return 'sha256:' + hashlib.file_digest(stream, 'sha256').hexdigest()


def main():
    source_path = PARENT / 'scripts/run_multicam_related_regressions.py'
    destination = ROOT / 'scripts/run_stream_related_regressions.py'
    assert not destination.exists()
    text = source_path.read_text('utf8')
    text = text.replace('from smoke_multicam_source_range import sha, write', '''import hashlib

def sha(path):
    with Path(path).open('rb') as stream:
        return 'sha256:' + hashlib.file_digest(stream, 'sha256').hexdigest()

def write(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + '.writing')
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\\n', encoding='utf8', newline='\\n')
    temporary.replace(path)
''')
    text = text.replace('multicam-source-range-20261021-lab', 'multicam-stream-coverage-20261021-lab')
    old = "    assert before == read(REL / 'parent-contract-refresh-r1.json')['frozen_after'] and len(before) == 257\n    fixtures = read(REL / 'external-fixtures-r1.json')\n    assert fixtures['status'] == 'passed' and fixtures['fixture_count'] == 8\n    fixture_inputs = {row['path']: row['sha256'] for row in fixtures['fixtures']}"
    new = """    expected = read(REL / 'after-r2.json')
    foundation = read(REL / 'foundation-r1.json')
    assert expected['terminal_ok'] and expected['methods'] == 22 and expected['frozen_equal']
    assert before == expected['frozen_before'] == expected['frozen_after'] and len(before) == 258
    previous = foundation['source_inputs']
    assert len(previous) == 257 and set(before) - set(previous) == {'product/tests/test_multicam_stream_coverage.py'}
    assert {name for name in previous if previous[name] != before[name]} == {'product/src/ai_ad_editor/' + name + '.py' for name in ('multicam', 'cli', 'capabilities')}
    fixtures = foundation['external_fixtures']
    assert len(fixtures) == 8
    fixture_inputs = {row['path']: row['sha256'] for row in fixtures}"""
    assert text.count(old) == 1
    text = text.replace(old, new)
    text = text.replace("names = ['test_multicam_source_range',", "names = ['test_multicam_stream_coverage', 'test_multicam_source_range',")
    text = text.replace('run_multicam_related_regressions.py', 'run_stream_related_regressions.py')
    text = text.replace('refresh_multicam_parent_contract.py', 'prepare_stream_related.py')
    text = text.replace("REL / 'external-fixtures-r1.json'", "REL / 'foundation-r1.json'")
    text = text.replace("'expected_methods': 80", "'expected_methods': 102")
    text = text.replace('int(match[1]) == 80', 'int(match[1]) == 102')
    text = text.replace('len(set(ids)) == 80', 'len(set(ids)) == 102')
    text = text.replace('"""Run the camera candidate with native clocks, empty ranges and media CLI controls."""',
        '"""Run native stream coverage with the exact camera, clock, empty-window and CLI controls."""')
    compile(text, str(destination), 'exec')
    assert '== 80' not in text and 'expected_methods\': 80' not in text
    destination.write_text(text, encoding='utf8', newline='\n')
    receipt = {'status': 'prepared-not-executed', 'expected_methods': 102, 'expected_frozen_inputs': 258,
        'source': str(source_path), 'source_sha256': sha(source_path), 'runner': str(destination),
        'runner_sha256': sha(destination), 'generator_sha256': sha(__file__),
        'scope': '22 native stream coverage +22 camera policy +16 empty window +32 nested clock +10 existing media/clock CLI; no full suite or publication.'}
    (REL / 'related-preparation-r1.json').write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + '\n', encoding='utf8', newline='\n')
    print(json.dumps({'status': receipt['status'], 'methods': 102}, ensure_ascii=False))


if __name__ == '__main__':
    main()
