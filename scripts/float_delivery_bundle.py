"""Bind the four tested Float32 candidates to one final source and delivery audit."""
from datetime import datetime, timezone
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
MAIN = ROOT.parents[2]
REL = 'docs/validation/evidence/float-delivery-20261022'
WORK = ROOT / 'product/.runtime/float-delivery-20261022'
REPORT = 'docs/validation/原片浮点渲染与预览合并交付实测_2026-10-22.md'
CONTRACT = 'docs/specs/原片浮点渲染与预览合并交付契约_v0.1_2026-10-22.md'
COMPONENTS = (
    ('V94', 'float-stream-lab-20261022', 'float-stream-20261022', 'float-stream-20261022-lab',
     'publish_float_stream', 292, 182, 176,
     'docs/validation/浮点视频流与作者音轨合成独立实测_2026-10-22.md',
     'docs/specs/浮点视频有界编码与作者音频接入_实验_v0.1_2026-10-22.md', 'float-stream-20261022-*'),
    ('V95', 'float-render-lab-20261022', 'float-render-20261022', 'float-render-20261022-lab',
     'publish_float_native', 296, 203, 178,
     'docs/validation/原生素材窗口解码与浮点音画合成实测_2026-10-22.md',
     'docs/specs/原生素材窗口浮点源_实验_v0.1_2026-10-22.md', 'float-render-20261022-*'),
    ('V96', 'float-standard-render-lab-20261022', 'float-standard-20261022', 'float-standard-20261022-lab',
     'publish_float_standard', 298, 220, 179,
     'docs/validation/标准CLI浮点交付实测_2026-10-22.md',
     'docs/specs/标准CLI浮点渲染接入契约_v0.1_2026-10-22.md', 'float-standard-20261022-*'),
    ('V97', 'float-preview-lab-20261022', 'float-preview-20261022', 'float-preview-20261022-lab',
     'publish_float_preview', 300, 260, 180,
     'docs/validation/浮点时间线预览与缓存实测_2026-10-22.md',
     'docs/specs/浮点时间线预览与缓存契约_v0.1_2026-10-22.md', 'float-preview-20261022-*'),
)


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for part in iter(lambda: stream.read(65536), b''):
            digest.update(part)
    return 'sha256:' + digest.hexdigest()


def read(path):
    return json.loads(Path(path).read_bytes())


def save(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n', encoding='utf8', newline='\n')


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def verify(base, entries):
    for name, digest in entries.items():
        assert sha(base / name) == digest, name


def git(*args):
    return subprocess.run(['git', '-c', 'gc.auto=0', '-c', 'maintenance.auto=false', *args], cwd=MAIN,
        capture_output=True, check=True, creationflags=subprocess.CREATE_NO_WINDOW).stdout


def prepare():
    evidence = ROOT / REL
    assert not evidence.exists()
    evidence.mkdir(parents=True)
    gates = evidence / 'component-gates-r1'
    gates.mkdir()
    previous = None
    summary = []
    bound = {}
    base_inputs = None
    child = ('import importlib,json,sys;from pathlib import Path;'
        'sys.path.insert(0,str(Path.cwd()/"scripts"));'
        'module=importlib.import_module(sys.argv[1]);audit,_=module.source_gate(False);'
        'print(json.dumps(audit,ensure_ascii=False))')
    for version, lab, series, rel, publisher, count, methods, resources, report, contract, assets in COMPONENTS:
        root = ROOT.parent / lab
        ev = root / 'docs/validation/evidence' / rel
        foundation_path, installed_path = ev / 'foundation-r1.json', ev / 'installed-r1/verification.json'
        foundation, installed = read(foundation_path), read(installed_path)
        current = installed['frozen_after']
        assert installed['frozen_before'] == current and len(current) == count
        assert installed['status'].startswith('passed-fresh-eight-wheel-')
        assert installed['isolated_methods']['methods'] == methods and installed['isolated_methods']['skipped'] == 0
        assert len(installed['resource_hashes']) == resources and len(installed['numpy_distribution']['files']) == 931
        assert all(row.get('ok', row.get('passed', False)) for row in installed['checks'])
        verify(root, current)
        if previous is None:
            base_inputs = foundation['parent_frozen_inputs']
            assert len(base_inputs) == 288
            dependencies, fixtures = foundation['dependency_artifact_inputs'], foundation['external_fixtures']
            assert len(dependencies) == 9 and len(fixtures) == 8
        else:
            assert foundation['parent_frozen_inputs'] == previous
            assert foundation['dependency_artifact_inputs'] == dependencies and foundation['external_fixtures'] == fixtures
        verify(root, dependencies)
        command = [sys.executable, '-E', '-B', '-X', 'utf8', '-c', child, publisher]
        result = subprocess.run(command, cwd=root, capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW)
        (gates / (version + '.stdout.json')).write_bytes(result.stdout)
        (gates / (version + '.stderr.log')).write_bytes(result.stderr)
        assert result.returncode == 0, (version, result.stderr.decode('utf8', 'replace')[-1500:])
        audit = json.loads(result.stdout)
        assert audit['frozen_inputs'] == current and not audit['complete_terminal_checked']
        gate = gates / (version + '.json')
        save(gate, {'status': 'passed-original-component-source-install-media-gate', 'version': version,
            'source_root': str(root), 'source_inputs': current, 'parent_inputs': foundation['parent_frozen_inputs'],
            'installed_methods': methods, 'installed_resources': resources,
            'foundation_receipt_sha256': sha(foundation_path), 'installed_receipt_sha256': sha(installed_path),
            'original_gate_script_sha256': sha(root / ('scripts/' + publisher + '.py')),
            'command': command, 'exit_code': 0, 'gate_stdout_sha256': sha(gates / (version + '.stdout.json')),
            'new_test_executions': 0, 'original_source_audit': audit})
        for p in (gate, gates / (version + '.stdout.json'), gates / (version + '.stderr.log')):
            bound[p.relative_to(ROOT).as_posix()] = sha(p)
        history = evidence / 'preserved-pre-suite-failures' / version
        history.mkdir(parents=True)
        owner = root / ('product/.runtime/' + series + '/complete-r1/run.json')
        failed = read(owner)
        assert failed['status'] == 'failed-preserved' and not failed['suite_launched']
        shutil.copyfile(owner, history / 'owner.json')
        bound[(history / 'owner.json').relative_to(ROOT).as_posix()] = sha(history / 'owner.json')
        summary.append({'version': version, 'source_root': str(root), 'source_count': count,
            'installed_methods': methods, 'resources': resources, 'gate': gate.relative_to(ROOT).as_posix(),
            'installed_receipt': str(installed_path), 'installed_receipt_sha256': sha(installed_path)})
        previous = current
        print(json.dumps({'version': version, 'source_count': count, 'installed_methods': methods, 'gate': 'passed'}, ensure_ascii=False), flush=True)
    assert previous == load(ROOT / 'scripts/run_frozen_regression.py', 'delivery_final_inputs').frozen()
    verify(MAIN, base_inputs)
    assert git('branch', '--show-current').decode().strip() == 'main'
    assert git('remote', 'get-url', 'origin').decode().strip() == 'git@github.com:Tonscriptions/agent-video-kit.git'
    commit = git('rev-parse', 'HEAD').decode().strip()
    assert git('ls-remote', 'origin', 'refs/heads/main').decode().split()[0] == commit
    assert not git('status', '--porcelain', '-z')
    research_owner = MAIN / 'product/.runtime/openfilm-reuse-lab-20261022-r16/product/.runtime/openfilm-r16-release/serialized-owner-r2/run.json'
    research = read(research_owner)
    assert research['status'] == 'published-R16-research' and research['commit'] == research['remote_main'] == commit
    changed = {n for n in previous if base_inputs.get(n) != previous[n]}
    added = set(previous) - set(base_inputs)
    save(evidence / 'prepared-r1.json', {'status': 'passed-four-candidate-lineage-and-existing-install-media-gates',
        'at_utc': datetime.now(timezone.utc).isoformat(), 'components': summary, 'frozen_inputs': previous,
        'published_parent_inputs': base_inputs, 'published_parent_commit': commit,
        'published_product_version': 'V93', 'published_research': 'R16', 'bound_evidence': bound,
        'research_owner': str(research_owner), 'research_owner_sha256': sha(research_owner),
        'dependency_artifact_inputs': dependencies, 'external_fixtures': fixtures,
        'changed_product_paths': sorted(changed), 'added_product_paths': sorted(added),
        'full_suite_passed': False, 'expected_final_methods': 2355, 'new_test_executions': 0,
        'generator_sha256': sha(Path(__file__)), 'native_windows': True, 'virtualization': False, 'network': False})
    print(json.dumps({'status': 'prepared-final-300-input-delivery', 'changed_paths': len(changed), 'added_paths': len(added), 'full_suite_claimed_passed': False}))


def audit():
    value = read(ROOT / REL / 'prepared-r1.json')
    assert value['status'] == 'passed-four-candidate-lineage-and-existing-install-media-gates'
    assert value['generator_sha256'] == sha(Path(__file__))
    current = load(ROOT / 'scripts/run_frozen_regression.py', 'delivery_current_inputs').frozen()
    assert current == value['frozen_inputs'] and len(current) == 300
    verify(ROOT, value['bound_evidence'])
    verify(ROOT, value['dependency_artifact_inputs'])
    for row in value['components']:
        installed = read(row['installed_receipt'])
        assert sha(row['installed_receipt']) == row['installed_receipt_sha256']
        gate = read(ROOT / row['gate'])
        assert installed['frozen_before'] == installed['frozen_after'] == gate['source_inputs']
        verify(Path(row['source_root']), gate['source_inputs'])
    assert sha(value['research_owner']) == value['research_owner_sha256']
    return value


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--prepare', action='store_true')
    args = parser.parse_args()
    if args.prepare:
        prepare()
    else:
        data = audit()
        print(json.dumps({'status': 'passed-existing-bundle-audit', 'frozen_inputs': len(data['frozen_inputs'])}))
