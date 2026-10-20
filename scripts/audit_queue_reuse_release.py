"""Bind V70 actual native evidence and final frozen release gates."""
from __future__ import annotations
import argparse
import ast
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import urllib.parse
from run_frozen_regression import frozen
from sync_queue_reuse_documents import DOCUMENTS, REPORT, CONTRACT

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'docs/validation/evidence/openfilm-batch-reuse-20261020-v70'


def read(path): return json.loads(path.read_bytes())
def sha(path): return 'sha256:' + hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--candidate', action='store_true')
    args = p.parse_args(); output = args.output.resolve(); assert not output.exists()
    current = frozen(); assert len(current) == 214
    inputs = {}

    def bind(path):
        path = Path(path); assert path.is_file(), path
        inputs[path.relative_to(ROOT).as_posix()] = sha(path)

    def receipt(name):
        path = BASE / name; bind(path); return read(path)

    def stable(value):
        assert value['frozen_equal'] and value['frozen_before'] == value['frozen_after'] == current

    focus = receipt('focus-r5.json'); stable(focus)
    assert focus['terminal_ok'] and focus['exit_code'] == 0 and focus['methods'] == 28 and focus['skipped'] == 0
    dev = receipt('native-r3/verification.json')
    actual = receipt('installed-r1/media/verification.json')
    install = receipt('installed-r1/verification.json')
    for value in (dev, actual, install):
        stable(value); assert value['status'] == 'passed' and not value['capcut_parity_accepted']
    assert sha(ROOT / 'scripts/smoke_queue_reuse.py')[7:] == dev['script_sha256'] == actual['script_sha256']
    assert install['isolated_cli_calls'] == 13 and install['module_origin_probes'] == 1
    assert len(install['calls']) == 7 and len(install['checks']) == 38 and all(c['ok'] for c in install['checks'])
    assert install['bundle']['wheels'] == install['installation']['wheels'] == 7
    assert len(install['resource_hashes']) == 143
    package = ROOT / 'product/src/ai_ad_editor'
    resources = {p.name: sha(p)[7:] for p in package.iterdir() if p.is_file() and p.suffix in {'.py', '.mjs', '.json', '.txt'}}
    assert resources == install['resource_hashes']
    installed = Path(install['installation']['target']) / 'site/ai_ad_editor'
    assert {p.name: sha(p)[7:] for p in installed.iterdir() if p.is_file() and p.suffix in {'.py', '.mjs', '.json', '.txt'}} == resources
    for value in (dev, actual):
        assert value['cli_calls'] == 10 and len(value['calls']) == 37
        assert len(value['checks']) == 22 and all(c['ok'] for c in value['checks'])
        assert not value['continuous_playback_review'] and not value['audio_listening_review']
        assert value['queue_result']['data']['summary'] == {'selected': 6, 'succeeded': 5, 'failed': 1, 'cancelled': 0, 'skipped': 0}
        assert value['queue_result']['data']['reuse_summary']['encoded_successes'] == 3
        assert value['queue_result']['data']['reuse_summary']['reused_successes'] == 2
        assert sum(e['type'] == 'render_started' for e in value['events']) == 3
        assert sum(e['type'] == 'reuse_started' for e in value['events']) == 2
        assert value['source_decoded']['frames'] == 24
        for name, decoded in value['decoded'].items():
            assert decoded['frames'] == len(decoded['frame_sha256']) == len(decoded['pts']) == 24
            for field in ('frame_sha256', 'pts', 'pcm_sha256', 'pcm_float_values', 'frames', 'alpha_min', 'alpha_max'):
                assert decoded[field] == dev['decoded'][name][field]
        public = {Path(r['path']).name: ROOT / r['path'] for r in value['public_files']}
        for row in value['public_files']:
            path = ROOT / row['path']; bind(path)
            assert sha(path)[7:] == row['sha256'] and path.stat().st_size == row['bytes']
        for source, copy in (('first.mp4', 'renamed.mp4'), ('alpha-first.webm', 'alpha-copy.webm')):
            assert sha(public[source]) == sha(public[copy])
            a, b = value['decoded'][source], value['decoded'][copy]
            assert all(a[k] == b[k] for k in ('frame_sha256', 'pts', 'pcm_sha256', 'pcm_float_values', 'frames', 'alpha_min', 'alpha_max'))
            manifest = read(public[copy + '.manifest.json'])
            assert manifest['command'] == [] and manifest['operation_id'].startswith('reuse_')
            assert manifest['filter_graph_transport']['mode'] == 'not_executed_copy'
            assert manifest['acceleration']['executed'] is False and manifest['reuse']['encoding_executed'] is False
            assert manifest['reuse']['source_operation_id'].startswith('render_')
        assert value['decoded']['alpha-copy.webm']['alpha_min'] == 0
        assert value['decoded']['alpha-copy.webm']['alpha_max'] == 255
    container = receipt('container-r1/verification.json'); stable(container)
    assert container['status'] == 'passed_actual_concat_rejected_before_encode'
    assert container['declared_format'] == 'png_pipe' and container['actual_format'] == 'concat'
    assert container['cli_calls'] == 5 and len(container['calls']) == 6
    assert container['encoding_started_events'] == 0 and not container['copied_outputs'] and container['events'] == []
    assert container['response']['data']['jobs'][0]['error']['code'] == 'QUEUE_REUSE_UNSUPPORTED'
    inventory = receipt('media-inventory-r1.json')
    assert inventory['status'] == 'passed' and len(inventory['public_files']) == 69 and len(inventory['final_media_probes']) == 16
    assert inventory['generator_sha256'] == sha(ROOT / 'scripts/audit_queue_reuse_media.py')
    for row in inventory['public_files']:
        path = ROOT / row['path']; bind(path)
        assert sha(path) == row['sha256'] and path.stat().st_size == row['bytes']
    static = receipt('static-review-r1.json')
    assert static['reviewed'] and len(static['files']) == 2
    assert not any(static[k] for k in ('continuous_playback_reviewed', 'audio_listening_reviewed', 'natural_footage_quality_accepted', 'full_capcut_parity'))
    for row in static['files']: assert sha(ROOT / row['path']) == row['sha256']
    skills = receipt('skills-r1.json'); mapping = read(ROOT / 'video-cut-install-manifest.json')
    bind(ROOT / 'video-cut-install-manifest.json')
    assert skills['skill_count'] == mapping['skill_count'] == 17 and skills['local_links_checked'] == 260
    assert mapping['current_audit']['record_sha256'] == sha(BASE / 'skills-r1.json')
    assert mapping['current_audit']['candidate'] == args.candidate
    for row in skills['results']:
        path = ROOT / 'skills' / row['skill'] / 'SKILL.md'; bind(path)
        assert sha(path) == row['sha256'] and row['installed_directory_resolves_to_repo'] and row['validator_exit_code'] == 0
        assert next(r for r in mapping['skills'] if r['name'] == row['skill'])['skill_md_sha256'] == row['sha256'][7:]
    # Preserve all original failed runs rather than rewriting them to passed.
    assert receipt('focus-r1.json')['exit_code'] != 0 and receipt('focus-r3.json')['exit_code'] != 0
    assert receipt('native-r1/verification.json')['status'] == 'failed'
    assert receipt('native-r2/verification.json')['status'] == 'passed'
    full = read(BASE / 'full-r1.json')
    if not args.candidate:
        stable(full); assert full['terminal_ok'] and full['exit_code'] == 0 and full['methods'] == 1564 and full['skipped'] == 0
        bind(BASE / 'full-r1.json'); bind(BASE / 'full-r1.log')
        assert sha(BASE / 'full-r1.log') == full['log_sha256']
        tree = ast.parse((ROOT / 'product/tests/test_queue_reuse.py').read_text(encoding='utf8'))
        methods = [n.name for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name.startswith('test_')]
        assert len(methods) == 28
        log = (BASE / 'full-r1.log').read_text(encoding='utf8')
        assert all(re.search(r'^' + name + r' .*\.\.\. ok$', log, re.M) for name in methods)
    documents = [*(ROOT / n for n in DOCUMENTS), REPORT, CONTRACT,
                 ROOT / 'docs/OpenFilm最新复用评估与成本取舍_2026-10-20.md']
    for path in documents:
        bind(path); text = path.read_text(encoding='utf8')
        if '<!-- V70-CURRENT -->' in text:
            text = text.split('<!-- V70-CURRENT -->', 1)[1].split('<!-- /V70-CURRENT -->', 1)[0]
        for raw in re.findall(r'!?\[[^\]]*\]\(([^\s)]+)\)', text):
            name = urllib.parse.unquote(raw.split('#', 1)[0])
            if name and not re.match(r'^[A-Za-z][A-Za-z0-9+.-]*:', name): assert (path.parent / name).exists(), (path, name)
    for path in BASE.rglob('*'):
        if path.is_file() and path != output and not (args.candidate and path.name in ('full-r1.json', 'full-r1.log')): bind(path)
    for name in ('smoke_queue_reuse', 'verify_queue_reuse_install', 'probe_queue_reuse_container',
                 'audit_queue_reuse_media', 'sync_queue_reuse_documents', 'audit_queue_reuse_release', 'finalize_queue_reuse'):
        bind(ROOT / 'scripts' / (name + '.py'))
    bind(ROOT / '.gitattributes')
    record = {'status': 'candidate_checks_passed_full_pending' if args.candidate else 'passed',
              'checked_at_utc': datetime.now(timezone.utc).isoformat(), 'frozen_inputs': current,
              'bound_files': inputs, 'full_methods': None if args.candidate else full['methods'],
              'native_cli_calls': 10, 'installed_cli_calls': 13, 'installed_module_probes': 1,
              'actual_container_cli_calls': 5, 'packaged_resources': 143, 'wheels': 7,
              'skills': 17, 'skill_links': 260, 'encodes_per_native_run': 3, 'copies_per_native_run': 2,
              'performance_accepted': False, 'full_capcut_parity': False, 'force_push': False}
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(record, ensure_ascii=False, indent=2) + '\n', encoding='utf8', newline='\n')
    print(json.dumps({k: record[k] for k in ('status', 'full_methods', 'packaged_resources', 'skills', 'skill_links')}))


if __name__ == '__main__': main()
