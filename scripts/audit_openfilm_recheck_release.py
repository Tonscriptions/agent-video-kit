"""Bind the scoped OpenFilm source review, product checks, notices and docs."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import subprocess
import urllib.parse

from audit_openfilm_refresh import contents
from run_frozen_regression import frozen

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / 'docs/validation/evidence'
PREFIX = 'openfilm-recheck-'


def sha(path):
    return 'sha256:' + hashlib.sha256(path.read_bytes()).hexdigest()


def read(relative):
    return json.loads((EVIDENCE / relative).read_bytes())


def run(output):
    assert not output.exists()
    refresh = read(PREFIX + 'diff-20261018-r54/verification.json')
    native = read(PREFIX + 'native-final-20261018-r54/verification.json')
    full = read(PREFIX + 'product-20261018-r54/html-targeted-final.json')
    old = read(PREFIX + 'product-20261018-r54/html-targeted.json')
    initial = read(PREFIX + 'native-20261018-r54/failure.json')
    assert full['terminal_ok'] and full['methods'] == 73 and full['skipped'] == 0
    assert full['frozen_before'] == full['frozen_after'] == native['product_after'] == frozen()
    assert len(frozen()) == 176
    assert sha(EVIDENCE / (PREFIX + 'product-20261018-r54/html-targeted-final.log')) == full['log_sha256']
    assert old['methods'] == 73 and old['exit_code'] == 1 and not old['terminal_ok']
    assert sha(EVIDENCE / (PREFIX + 'product-20261018-r54/html-targeted.log')) == old['log_sha256']
    assert initial['status'] == 'failed_fixture_expectation' and initial['partial_outputs_retained']
    for name, expected in initial['executed_sources'].items():
        assert sha(EVIDENCE / (PREFIX + 'native-20261018-r54') / name) == expected
    assert native['upstream_counts'] == {'tests': 39, 'pass': 38, 'fail': 0, 'skipped': 1, 'cancelled': 0}
    assert native['generator_sha256'] == sha(ROOT / 'scripts/audit_openfilm_recheck.py')
    assert native['source_before'] == native['source_after'] == refresh['head_hashes']
    assert len(refresh['head_hashes']) == 713 and len(refresh['added']) == 13 and len(refresh['removed']) == 2 and len(refresh['changed']) == 53
    archive = Path(refresh['source_archive'])
    assert sha(archive) == native['source_archive_sha256'] == refresh['source_archive_sha256']
    files = contents(archive.read_bytes())
    assert {p: 'sha256:' + hashlib.sha256(b).hexdigest() for p, b in files.items()} == refresh['head_hashes']
    product = ROOT / 'product/src/ai_ad_editor'
    adoptions = {}
    for target, source in [('openfilm_subtitle_segments.mjs', 'studio/server/subtitle-segments.mjs'),
                           ('openfilm_overrides.mjs', 'src/overrides.mjs')]:
        assert (product / target).read_bytes() == files['packages/openfilm/' + source]
        adoptions[target] = sha(product / target)
    assert (product / 'OPENFILM_LICENSE.txt').read_bytes() == files['LICENSE'] == (archive.parent / 'LICENSE').read_bytes()
    bounds = (product / 'openfilm_text_bounds.mjs').read_bytes()
    assert bounds[bounds.index(b'export function cutText()'):] in files['packages/openfilm/src/shared.mjs']
    clock = re.search(rb'^export const FILM_CLOCK = .*;$', files['packages/openfilm/src/host.mjs'], re.M).group(0)
    assert clock in (product / 'openfilm_frame_clock.mjs').read_bytes()
    template = files['packages/openfilm/studio/ui/src/lib/template-controls.ts'].decode()
    fragment = template[template.index('const COLOR = '):template.index('/** The clip\'s own value of a custom property')]
    for a, b in {'value: string, isColor: (v: string) => boolean = () => false): VarField': 'value, isColor = () => false)',
                 'name: string, value: string): boolean': 'name, value)', 'field: VarField): string': 'field)',
                 'name: string): string': 'name)', 'num[2]!': 'num[2]', 'quoted[2]!': 'quoted[2]', 'words[0]!': 'words[0]'}.items():
        fragment = fragment.replace(a, b)
    fields = (product / 'openfilm_template_fields.mjs').read_bytes()
    assert fields[fields.index(b'const COLOR = '):] == fragment.encode()
    upstream = template[template.index('export function urlOf('):]
    regex = next(line.strip() for line in upstream.splitlines() if line.strip().startswith('const m = '))
    bridge = (product / 'html_template_dom.mjs').read_text(encoding='utf-8')
    actual = next(line.strip() for line in bridge[bridge.index('function urlValue('):].splitlines() if line.strip().startswith('const m = '))
    assert actual == regex
    for row in native['runs']:
        base = EVIDENCE / (PREFIX + 'native-final-20261018-r54')
        assert sha(base / (row['id'] + '.stdout.log')) == row['stdout_sha256']
        assert sha(base / (row['id'] + '.stderr.log')) == row['stderr_sha256']
    assert sum(row['timed_out'] for row in native['runs']) == 2
    # Inspect only the fixed test toolchain, never close unrelated user browsers.
    command = ['powershell.exe', '-NoProfile', '-Command',
        "@(Get-CimInstance Win32_Process | Where-Object { $_.ExecutablePath -like 'E:\\dev\\sandbox\\AI广告剪辑\\product\\.runtime\\html-toolchain\\*' } | Select-Object ProcessId,Name,ExecutablePath) | ConvertTo-Json -Compress"]
    result = subprocess.run(command, capture_output=True, timeout=30)
    assert result.returncode == 0
    assert not result.stdout.strip() or json.loads(result.stdout) in ([], None), result.stdout
    docs = ['README.md', 'docs/README.md', 'docs/OpenFilm当前复用决策_2026-10-18.md',
            'docs/OpenFilm最新源码复核与降本清单_2026-10-18.md',
            'docs/third-party/OpenFilm复用声明_2026-10-17.md', 'docs/构建进度总表_2026-10-16.md']
    links, doc_hashes = 0, {}
    for relative in docs:
        path = ROOT / relative
        text = path.read_text(encoding='utf-8-sig')
        assert '__HTML_RESULT__' not in text
        doc_hashes[relative] = sha(path)
        for raw in re.findall(r'!?\[[^\]]*\]\((<[^>]+>|[^\s)]+)(?:\s+"[^\"]*\")?\)', text):
            target = raw.strip('<>').split('#', 1)[0]
            if not target or re.match(r'^[a-zA-Z][a-zA-Z0-9+.-]*:', target):
                continue
            destination = (path.parent / urllib.parse.unquote(target)).resolve()
            assert destination == output or destination.exists(), (relative, target)
            links += 1
    assert '| V54 |' in (ROOT / 'README.md').read_text(encoding='utf-8')
    record = {'status': 'passed_scoped_openfilm_recheck_release', 'checked_at_utc': datetime.now(timezone.utc).isoformat(),
              'head': refresh['head'], 'upstream_files': 713, 'added': 13, 'removed': 2, 'changed': 53,
              'upstream_tests': native['upstream_counts'], 'targeted_product_methods': 73,
              'targeted_product_seconds': full['suite_seconds'], 'product_frozen_files': 176,
              'frozen_product': frozen(), 'product_full_regression_rerun': False,
              'fixed_adoptions_rechecked': list(adoptions) + ['original frame clock', 'original cutText', 'four template fields'],
              'new_adoption': 'CSS URL escape regex only; exact upstream expression with local function/interface',
              'licenses_equal': True, 'retained_fixture_failure': True, 'old_parser_watchdog_timeouts': 2,
              'research_encoded_frames': 0, 'new_model_calls': 0, 'new_offline_bundle': False,
              'upstream_browser_started': False, 'product_tests_used_native_headless_browser': True,
              'remaining_fixed_browser_toolchain_processes': [], 'virtualization': False,
              'target_editor_imported': False, 'final_cut_dtd_validated': False,
              'documents_checked': len(docs), 'document_links_checked': links, 'broken_links': 0,
              'document_hashes': doc_hashes, 'generator_sha256': sha(Path(__file__)),
              'source_review_receipt_sha256': sha(EVIDENCE / (PREFIX + 'native-final-20261018-r54/verification.json')),
              'targeted_product_receipt_sha256': sha(EVIDENCE / (PREFIX + 'product-20261018-r54/html-targeted-final.json')),
              'all_capcut_features_and_quality_accepted': False, 'goal_complete': False}
    output.write_text(json.dumps(record, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')
    print(json.dumps({k: record[k] for k in ['status', 'upstream_files', 'targeted_product_methods', 'product_frozen_files', 'document_links_checked', 'broken_links']}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    run(parser.parse_args().output.resolve())
