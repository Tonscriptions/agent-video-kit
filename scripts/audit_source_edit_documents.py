"""Check current V40 documents, published bytes and all local Markdown links."""
from __future__ import annotations

import argparse
import ast
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import urllib.parse
import zipfile

ROOT = Path(__file__).resolve().parents[1]
EV = ROOT/'docs/validation/evidence'


def sha(path):
    return 'sha256:' + hashlib.sha256(path.read_bytes()).hexdigest()


def run(output):
    assert not output.exists(), output
    output.write_text('{"status":"checking"}\n', encoding='utf-8', newline='\n')
    documents = [ROOT/'README.md', ROOT/'AGENTS.md', *sorted((ROOT/'docs').rglob('*.md'))]
    local = external = anchors = 0
    states = {}
    broken = []
    for path in documents:
        text = path.read_text(encoding='utf-8-sig')
        assert text.strip(), path
        clean = re.sub(r'^\s*```.*?^\s*```[^\n]*', '', text, flags=re.M | re.S)
        state = re.search(r'^\| 状态 \| ([^|]+)\|', clean, re.M)
        if state:
            states[path.relative_to(ROOT).as_posix()] = state[1].strip()
        for raw in re.findall(r'!?\[[^\]]*\]\((<[^>]+>|[^\s)]+)(?:\s+"[^\"]*")?\)', clean):
            target = raw.strip('<>')
            if re.match(r'^[a-zA-Z][a-zA-Z0-9+.-]*:', target) and not re.match(r'^[A-Za-z]:[/\\]', target):
                external += 1
                continue
            target = target.split('#', 1)[0]
            if not target:
                anchors += 1
                continue
            local += 1
            if not (path.parent/urllib.parse.unquote(target)).resolve().exists():
                broken.append({'document': path.relative_to(ROOT).as_posix(), 'target': raw})
    assert not broken, broken
    record = json.loads((EV/'source-edits-20261018.json').read_text(encoding='utf-8'))
    assert record['status'] == 'passed' and record['goal_still_active'] and not record['complete_capcut_parity_accepted']
    full = record['full']
    assert full['methods'] == 938 and full['skipped'] == 0 and full['frozen_equal']
    python = 0
    for name, digest in full['frozen_after'].items():
        assert sha(ROOT/name) == digest, name
        if name.endswith('.py'):
            ast.parse((ROOT/name).read_text(encoding='utf-8-sig'), filename=name)
            python += 1
    assert python == 127 and len(full['frozen_after']) == 132
    for name, item in record['public_media_audit']['public_sha256'].items():
        assert sha(ROOT/'docs/assets/source-edits-20261018'/name) == item['sha256'], name
    for section, folder in [('development_files', EV/'source-development-20261018'),
                            ('wheel', EV/'source-wheel-20261018')]:
        items = record[section]['files'] if section == 'wheel' else record[section]
        for name, item in items.items():
            path = folder/name
            assert sha(path) == item['sha256'], name
            if path.suffix in {'.zip', '.whl'}:
                with zipfile.ZipFile(path) as archive:
                    assert archive.testzip() is None
    for name, item in record['wheel']['source_files'].items():
        assert sha(ROOT/'product/src'/name) == item['sha256'], name
    for name, item in record['generators'].items():
        assert sha(ROOT/name) == item['sha256'], name
        ast.parse((ROOT/name).read_text(encoding='utf-8-sig'), filename=name)
    assert sha(EV/'source-final-full-20261018.log') == full['log_sha256']
    for item in record['skills']['results']:
        assert sha(ROOT/'skills'/item['skill']/'SKILL.md') == item['sha256']
    for name, item in record['static_review']['files'].items():
        assert sha(ROOT/name) == item['sha256'], name
    assert (ROOT/'sources/upstream/openfilm/LICENSE').read_bytes() == (ROOT/'product/src/ai_ad_editor/OPENFILM_LICENSE.txt').read_bytes()
    readme = (ROOT/'README.md').read_text(encoding='utf-8-sig')
    ids = [int(n) for n in re.findall(r'^\| V(\d+) \|', readme, re.M)]
    assert ids == list(range(1, 41)), ids
    assert '![真实源外扩与关联滚动剪口对照]' in readme and '本轮 V39：' not in readme
    for name in ('docs/README.md', 'docs/构建进度总表_2026-10-16.md', 'docs/产品需求与开发路线基线_2026-10-12.md',
                 'docs/validation/能力覆盖与验收矩阵_v0.1_2026-10-13.md', 'docs/validation/回归验证记录_2026-10-13.md'):
        text = (ROOT/name).read_text(encoding='utf-8-sig')
        assert '本轮 V40：' in text and '本轮 V39：' not in text, name
    validation = 'docs/validation/真实源外扩与关联Slip实测_2026-10-18.md'
    contract = 'docs/specs/真实源范围外扩与关联Slip契约_v0.1_2026-10-18.md'
    assert states[validation].startswith('有效') and states[contract].startswith('有效')
    assert 'FINAL-SOURCE-EDIT-RESULTS' not in (ROOT/validation).read_text(encoding='utf-8')
    progress = (ROOT/'docs/构建进度总表_2026-10-16.md').read_text(encoding='utf-8')
    for prefix in ('| 本次状态快照 |', '| 核对范围 |', '| 最近完整产品回归 |'):
        line = next(line for line in progress.splitlines() if line.startswith(prefix))
        assert '938' in line, line
    value = {'at_utc': datetime.now(timezone.utc).isoformat(), 'status': 'passed',
             'markdown_files': len(documents), 'local_file_links': local, 'broken_links': broken,
             'external_links_not_fetched': external, 'anchors_not_checked': anchors,
             'scope': 'Local documents/states/numbered results; frozen product bytes, raw CLI/media/failure records, wheel, Skills and original MIT. No extra render/model execution.',
             'states': states, 'numbered_rows': len(ids), 'frozen_files': 132, 'python_ast_files': python,
             'public_files': record['public_media_audit']['public_files'], 'generator_sha256': sha(Path(__file__)),
             'document_sha256': {p.relative_to(ROOT).as_posix(): sha(p) for p in documents}}
    output.write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n', encoding='utf-8', newline='\n')
    print(json.dumps({key: value[key] for key in ('status', 'markdown_files', 'local_file_links', 'numbered_rows', 'frozen_files', 'public_files')}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    run(args.output.resolve())
