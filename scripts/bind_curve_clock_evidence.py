"""Bind retained V81 media to an explicitly reviewed test-only correction."""
import hashlib
import json
from pathlib import Path
from run_frozen_regression import frozen

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'docs/validation/evidence/cfr-boundaries-20261021-v81'
TEST = 'product/tests/test_cli.py'
FULL_NAME = 'full-r2.json'
CANDIDATE_DOCUMENTS = 'documents-candidate-r2.json'
CANDIDATE_AUDIT = 'release-candidate-r3.json'


def read(path):
    return json.loads(path.read_bytes())


def validate_bridge(current):
    bridge = read(BASE / 'test-oracle-correction-r1.json')
    before, after = bridge['frozen_before'], bridge['frozen_after']
    assert len(before) == len(after) == 242 and set(before) == set(after)
    assert {n for n in before if before[n] != after[n]} == {TEST}
    assert before == read(BASE / 'assembly-r1.json')['frozen_inputs'] and after == current
    old_test = BASE / 'full-r1-original-test-cli.py.txt'
    assert 'sha256:' + hashlib.sha256(old_test.read_bytes()).hexdigest() == before[TEST]
    original = read(BASE / 'full-r1.json')
    assert original['status'] == 'failed' and original['frozen_before'] == original['frozen_after'] == before
    assert original['frozen_equal'] and original['external_fixtures_equal']
    old_case = read(BASE / 'oracle-case-before-r1.json')
    new_case = read(BASE / 'oracle-case-after-r1.json')
    assert old_case['case'] == new_case['case']
    for name, item in [('oracle-case-before-r1', old_case), ('oracle-case-after-r1', new_case)]:
        assert 'sha256:' + hashlib.sha256((BASE / (name + '.log')).read_bytes()).hexdigest() == item['log_sha256']
    assert 'sha256:' + hashlib.sha256((BASE / 'test-oracle-correction-r1.diff.txt').read_bytes()).hexdigest() == bridge['reviewed_diff_sha256']
    assert old_case['exit_code'] != 0 and not old_case['terminal_ok']
    assert old_case['frozen_before'] == old_case['frozen_after'] == before
    assert new_case['exit_code'] == 0 and new_case['terminal_ok'] and new_case['methods'] == 1
    assert new_case['frozen_before'] == new_case['frozen_after'] == after
    assert bridge['runtime_inputs_byte_equal'] and all(before[n] == after[n] for n in before if not n.startswith('product/tests/'))
    return bridge


def current_inputs():
    current = frozen()
    validate_bridge(current)
    return current


def bind_receipt(value, current):
    assert value['frozen_equal'] and value['frozen_before'] == value['frozen_after']
    if value['frozen_after'] == current:
        return False
    bridge = validate_bridge(current)
    assert value['frozen_after'] == bridge['frozen_before']
    return True
