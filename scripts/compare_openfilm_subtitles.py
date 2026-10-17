"""Compare the fixed upstream subtitle algorithm with the packaged local API.

This proves adaptation/clock/index behavior, not subtitle semantics or ASR
quality. Runs original tests without modifying or installing upstream code.
"""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'product/src'))
from ai_ad_editor.subtitle_segments import segment_source, UPSTREAM


def sha(path):
    return 'sha256:' + hashlib.sha256(path.read_bytes()).hexdigest()


def save(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False) + '\n', encoding='utf-8')


def inventory(root):
    return {p.relative_to(root).as_posix(): sha(p) for p in sorted(root.rglob('*')) if p.is_file()}


def cp_index(text, unit):
    return len(text.encode('utf-16-le')[:unit * 2].decode('utf-16-le'))


def run(source, output):
    output.mkdir(parents=True, exist_ok=False)
    module = source / UPSTREAM['path']
    test = module.with_name('subtitle-segments.test.mjs')
    assert sha(module) == UPSTREAM['sha256']
    before = inventory(source)
    selected = subprocess.run([shutil.which('node'), '--test', str(test)], capture_output=True)
    (output/'original-tests.stdout.log').write_bytes(selected.stdout)
    (output/'original-tests.stderr.log').write_bytes(selected.stderr)
    assert selected.returncode == 0, selected.stdout[-2500:]
    texts = [
        '它叫 OpenFilm，免费开源，MIT 协议。',
        '为了不再剪视频，我做了一个通用的视频agent',
        '我们先做一个原型（大概需要两周），然后再看效果。',
        '渲染一帧只要 3.5 秒，比以前快了 10 倍。',
        '我们准备了剧本、分镜、配乐、字幕、调色和最后的成片导出',
        '我今天没有去公司上班因为外面一直在下很大的雨',
        'Mr. Smith arrived at 3.5 s, e.g. right on time, and we started the demo.',
        'The U.S. economy grew 3.5% in Q1. Then it slowed.',
        'This is a really long sentence that goes on without any commas because we want to see where it breaks',
        '🎬 它叫 OpenFilm，免费开源，MIT 协议。',
        'Cafe\u0301 is ready, and the camera is rolling.',
        '𠮷野家的新广告，今天正式发布，欢迎观看。',
    ]
    cases, requests = [], []
    for n, text in enumerate(texts):
        for duration in (3500, 7000):
            for marked in (False, True):
                line = {'id': 'line', 'text': text, 'start_tick': 900017, 'end_tick': 900017 + duration * 90}
                marks = list(re.finditer(r"[A-Za-z0-9.']+|[一-鿿]|[\U00020000-\U0002ffff]", text))
                if marked:
                    line['marks'] = [{'index': m.start(), 'start_tick': 900017 + round(k * duration * 90 / len(marks))} for k, m in enumerate(marks)]
                if n % 2 == 0:
                    line['translation'] = 'A local video workflow. Every subtitle keeps its source text, and every edit stays on this computer.'
                rules = {'maxCells': 16, 'maxChars': 42}
                src = {'format': 'agent-subtitle-source-v1', 'ticks_per_second': 90000, 'lines': [line]}
                cases.append({'source': src, 'rules': rules})
                requests.append({'line': {'text': text, 'startMs': 0, 'endMs': duration,
                    'marks': [{'index': len(text[:m['index']].encode('utf-16-le')) // 2, 'startMs': (m['start_tick'] - 900017) / 90} for m in line.get('marks', [])]},
                    'translation': line.get('translation'), 'rules': rules})
    worker = output / 'upstream-reference.mjs'
    worker.write_text("import {readFileSync} from 'node:fs';\nimport {segmentLine,alignTranslation,subtitleEnd,subtitleCells,SUBTITLE_SEGMENT_RULES} from " + json.dumps(module.as_uri()) + ";\n"
        "const requests=JSON.parse(readFileSync(0,'utf8'));\n"
        "const result=requests.map(r=>{const R={...SUBTITLE_SEGMENT_RULES,...r.rules};const p=segmentLine(r.line,R);"
        "const tr=r.translation===undefined||r.translation===null?null:alignTranslation(r.translation,p,R);"
        "return p.map((x,i)=>({...x,display_text:subtitleEnd(x.text),cells:subtitleCells(subtitleEnd(x.text)),...(tr?{translation:tr[i]}:{})}));});\n"
        "process.stdout.write(JSON.stringify(result));\n", encoding='utf-8')
    raw_input = json.dumps(requests, ensure_ascii=False).encode('utf-8')
    (output/'upstream-request.json').write_bytes(raw_input)
    ref = subprocess.run([shutil.which('node'), str(worker)], input=raw_input, capture_output=True, timeout=30)
    (output/'upstream.stdout.json').write_bytes(ref.stdout)
    (output/'upstream.stderr.log').write_bytes(ref.stderr)
    assert ref.returncode == 0
    expected = json.loads(ref.stdout)
    comparisons = []
    for index, (case, raw) in enumerate(zip(cases, expected)):
        result = segment_source(case['source'], rules=case['rules'])
        line = case['source']['lines'][0]
        predicted = []
        for p in raw:
            item = {'part': p['part'], 'text': p['text'], 'display_text': p['display_text'], 'cells': p['cells'],
                    'from': cp_index(line['text'], p['from']), 'to': cp_index(line['text'], p['to']),
                    'start_tick': line['start_tick'] + round(p['startMs'] * 90), 'end_tick': line['start_tick'] + round(p['endMs'] * 90)}
            if p.get('marks'):
                item['marks'] = [{'index': cp_index(p['text'], m['index']), 'start_tick': line['start_tick'] + round(m['startMs'] * 90)} for m in p['marks']]
            if 'translation' in p:
                t = p['translation']
                item['translation'] = {'text': t['text'], 'from': cp_index(line['translation'], t['from']), 'to': cp_index(line['translation'], t['to'])}
            predicted.append(item)
        actual = [{k: v for k, v in p.items() if k not in {'line_id', 'timing_basis'}} for p in result['pieces']]
        comparison = {'case': index + 1, 'input': case, 'expected': predicted, 'actual': actual, 'equal': predicted == actual}
        comparisons.append(comparison)
        save(output/f'case-{index+1:02}.json', comparison)
        assert comparison['equal'], comparison
    after = inventory(source)
    assert after == before
    report = {'checked_at_utc': datetime.now(timezone.utc).isoformat(), 'status': 'passed',
        'source': UPSTREAM, 'source_files': len(before), 'source_unchanged': before == after,
        'original_tests': int(re.search(rb'# tests (\d+)', selected.stdout).group(1)),
        'case_count': len(comparisons), 'matched': sum(c['equal'] for c in comparisons),
        'scope': 'fixed original algorithm behavior, Unicode index and relative millisecond to integer tick adaptation; not independent semantic quality',
        'files': {p.name: sha(p) for p in sorted(output.iterdir()) if p.is_file()}, 'source_inventory': before}
    save(output/'verification.json', report)
    print(json.dumps({k:v for k,v in report.items() if k not in {'files','source_inventory'}}, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    run(args.source.resolve(), args.output.resolve())
