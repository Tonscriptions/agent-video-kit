"""Local OpenFilm subtitle segmentation with integer project clocks.

The vendored pure JS algorithm keeps Intl.Segmenter behavior; this Python
boundary owns validation, Unicode indexes, budgets and project tick precision.
"""
from __future__ import annotations

import copy
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
import json
import math
import os
from pathlib import Path
import re
import shutil
import subprocess
from typing import Any

from .captions import parse_caption_file
from .errors import AppError, argument_error
from .utils import sha256_file

PROTOCOL = 'agent-video-subtitle-segment-v1'
SOURCE_FORMAT = 'agent-subtitle-source-v1'
RESULT_FORMAT = 'agent-subtitle-segments-v1'
UPSTREAM = {'repository': 'openfilm/openfilm', 'revision': 'b138595d4c2d1fa5262b4a8a8c7cd98187c4b077',
            'path': 'packages/openfilm/studio/server/subtitle-segments.mjs', 'license': 'MIT',
            'sha256': 'sha256:b4791b6ec527379aeedaa5329ee7efc3855b8b5dc99cf36db25c2d4652e5784f'}
MAX_BYTES, MAX_LINE, MAX_TOTAL, MAX_WORK = 8 * 1024 * 1024, 2000, 100000, 25000000
RULE_KEYS = {'maxCells', 'maxChars', 'minUnits', 'pauseMs', 'minMs', 'maxMs', 'holdMs', 'closeGapMs', 'msPerCell'}
WEIGHTS = {'latin', 'space', 'clause', 'sentence'}
COSTS = {'piece', 'balance', 'short', 'over', 'long', 'cjk', 'cjkSingle', 'mixed', 'bracket',
         'leansBack', 'leansForward', 'conjunction', 'particle', 'pause', 'sentence', 'clause', 'distance', 'merge'}


def _text(value: Any, field: str, *, empty: bool = False) -> str:
    if not isinstance(value, str) or (not empty and not value.strip()) or '\0' in value or any(0xD800 <= ord(c) <= 0xDFFF for c in value):
        raise argument_error('字幕文字必须是有效、非空的 Unicode 字符串', field)
    if len(value) > MAX_LINE:
        raise AppError('SUBTITLE_SEGMENT_BUDGET', f'单行文字或译文超过 {MAX_LINE} 码点预算', exit_code=2, path=field)
    return value


def _integer(value: Any, field: str, *, minimum: int = 0) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not minimum <= value <= 2**63 - 1:
        raise argument_error('必须是范围内的整数 tick 或索引', field)
    return value


def _seconds(value: Any, tps: int, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise argument_error('字幕时码必须是有限数字秒', field)
    try:
        decimal = Decimal(str(value))
        if not decimal.is_finite() or decimal < 0:
            raise ValueError('Non-finite or negative time')
        return _integer(int((decimal * tps).to_integral_value(rounding=ROUND_HALF_UP)), field)
    except (ValueError, InvalidOperation) as exc:
        raise argument_error('字幕时码必须是非负有限数字秒', field) from exc


def checked_rules(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) - (RULE_KEYS | {'weight', 'cost'}):
        raise argument_error('分段规则包含未知字段', 'rules')
    for name, number in value.items():
        if name in {'weight', 'cost'}:
            allowed = WEIGHTS if name == 'weight' else COSTS
            if not isinstance(number, dict) or set(number) - allowed:
                raise argument_error('分段权重/代价包含未知字段', 'rules.' + name)
            for sub, n in number.items():
                if isinstance(n, bool) or not isinstance(n, (int, float)) or not math.isfinite(n) or not (-1000 if name == 'cost' else 0) <= n <= 1000:
                    raise argument_error('分段权重/代价必须是有界有限数字', 'rules.' + name + '.' + sub)
        else:
            upper = 3600000 if name.endswith('Ms') or name == 'msPerCell' else 2000
            lower = 0 if name in {'holdMs', 'closeGapMs', 'pauseMs', 'minMs', 'minUnits'} else 0.001
            if isinstance(number, bool) or not isinstance(number, (int, float)) or not math.isfinite(number) or not lower <= number <= upper:
                raise argument_error('分段规则必须是有界有限数字', 'rules.' + name)
    if value.get('minMs', 700) > value.get('maxMs', 7000):
        raise argument_error('minMs 不能大于 maxMs', 'rules')
    return copy.deepcopy(value)


def checked_source(value: Any, tps: int) -> dict[str, Any]:
    _integer(tps, 'ticks_per_second', minimum=1)
    if not isinstance(value, dict) or value.get('format') != SOURCE_FORMAT or value.get('ticks_per_second') != tps or isinstance(value.get('ticks_per_second'), bool):
        raise argument_error('字幕源格式或 ticks_per_second 与项目不一致', 'input')
    if set(value) - {'format', 'ticks_per_second', 'lines'}:
        raise argument_error('字幕源包含未知字段', 'input')
    lines = value.get('lines')
    if not isinstance(lines, list) or not 1 <= len(lines) <= 10000:
        raise argument_error('字幕源必须包含 1..10000 行', 'lines')
    out, ids, previous_end, total, work = [], set(), 0, 0, 0
    for index, item in enumerate(lines):
        field = f'lines[{index}]'
        if not isinstance(item, dict) or set(item) - {'id', 'text', 'start_tick', 'end_tick', 'marks', 'translation'}:
            raise argument_error('字幕行包含未知字段', field)
        lid = item.get('id')
        if not isinstance(lid, str) or not re.fullmatch(r'[A-Za-z0-9_.-]{1,128}', lid) or lid in ids:
            raise argument_error('字幕行 ID 必须有效且唯一', field + '.id')
        ids.add(lid)
        text = _text(item.get('text'), field + '.text')
        start = _integer(item.get('start_tick'), field + '.start_tick')
        end = _integer(item.get('end_tick'), field + '.end_tick', minimum=1)
        if start < previous_end or end <= start or end - start > tps * 86400:
            raise argument_error('字幕行必须有序、不重叠、正时长，单行不超过 24 小时', field)
        previous_end = end
        line = {'id': lid, 'text': text, 'start_tick': start, 'end_tick': end}
        marks = item.get('marks', [])
        if not isinstance(marks, list):
            raise argument_error('marks 必须是数组', field + '.marks')
        old_i, old_t, normalized = -1, start - 1, []
        for m in marks:
            if not isinstance(m, dict) or set(m) != {'index', 'start_tick'}:
                raise argument_error('mark 必须只包含 index 和 start_tick', field + '.marks')
            i, tick = _integer(m['index'], field + '.marks.index'), _integer(m['start_tick'], field + '.marks.start_tick')
            if not old_i < i < len(text) or not old_t < tick < end or tick < start:
                raise argument_error('mark 索引和时钟必须递增且位于原句内', field + '.marks')
            old_i, old_t = i, tick
            normalized.append({'index': i, 'start_tick': tick})
        if normalized:
            line['marks'] = normalized
        if 'translation' in item:
            line['translation'] = _text(item['translation'], field + '.translation', empty=True)
        total += len(text) + len(line.get('translation', ''))
        work += len(text)**2 + len(text) * len(line.get('translation', ''))**2
        out.append(line)
    if total > MAX_TOTAL or work > MAX_WORK:
        raise AppError('SUBTITLE_SEGMENT_BUDGET', '字幕总文字量或最坏分段/译文对齐工作量超过预算，请显式拆分批次', exit_code=2)
    return {'format': SOURCE_FORMAT, 'ticks_per_second': tps, 'lines': out}


def load_source(path: Path, tps: int) -> tuple[dict[str, Any], dict[str, Any]]:
    if not path.is_file() or path.stat().st_size > MAX_BYTES:
        raise argument_error('字幕输入不存在或超过 8 MiB', str(path))
    if path.suffix.lower() in {'.srt', '.vtt', '.ass', '.ssa', '.ttml', '.dfxp'}:
        segments = parse_caption_file(path)
        rules = {}
    else:
        try:
            value = json.loads(path.read_text(encoding='utf-8-sig'))
        except (UnicodeError, ValueError) as exc:
            raise argument_error('字幕输入必须是有效 UTF-8 JSON 或支持的字幕文件', str(path)) from exc
        if not isinstance(value, dict):
            raise argument_error('字幕输入 JSON 必须是对象', 'input')
        if value.get('format') == SOURCE_FORMAT:
            return checked_source(value, tps), {}
        if value.get('format') == RESULT_FORMAT:
            return checked_source(value.get('source'), tps), checked_rules(value.get('rules', {}))
        transcription = value.get('transcription', value)
        if not isinstance(transcription, dict):
            raise argument_error('ASR 报告缺少 transcription 对象', 'input')
        segments, rules = transcription.get('segments'), {}
    if not isinstance(segments, list) or not segments:
        raise argument_error('输入缺少非空时码 segments', 'input')
    lines = []
    for i, s in enumerate(segments):
        if not isinstance(s, dict) or s.get('marks') or s.get('words'):
            raise argument_error('逐字标记必须显式转换为 Unicode 码点/tick 的源格式，不能静默忽略', 'segments')
        lines.append({'id': f'line_{i+1:06d}', 'text': s.get('text'),
                      'start_tick': _seconds(s.get('start'), tps, 'segments.start'),
                      'end_tick': _seconds(s.get('end'), tps, 'segments.end')})
    return checked_source({'format': SOURCE_FORMAT, 'ticks_per_second': tps, 'lines': lines}, tps), rules


def checked_corrections(value: Any, input_sha256: str, source: dict[str, Any]) -> list[dict[str, Any]]:
    if value is None:
        return []
    if not isinstance(value, dict) or set(value) != {'expected_input_sha256', 'edits'} or value.get('expected_input_sha256') != input_sha256:
        raise AppError('SUBTITLE_SEGMENT_STALE_INPUT', '纠正必须绑定本次输入文件的原始 SHA-256', exit_code=2)
    edits = value.get('edits')
    if not isinstance(edits, list) or not 1 <= len(edits) <= 10000:
        raise argument_error('纠正必须包含 1..10000 个 edits', 'corrections')
    ids = {l['id'] for l in source['lines']}
    result = []
    for e in edits:
        if not isinstance(e, dict) or set(e) - {'line_id', 'part', 'text', 'target'} or e.get('line_id') not in ids or e.get('target', 'text') not in {'text', 'translation'}:
            raise argument_error('纠正行或目标无效', 'corrections.edits')
        part = _integer(e.get('part'), 'corrections.part')
        text = _text(e.get('text'), 'corrections.text', empty=True)
        result.append({'line_id': e['line_id'], 'part': part, 'text': text, 'target': e.get('target', 'text')})
    return result


def _worker(request: dict[str, Any]) -> dict[str, Any]:
    from .artifact_locks import artifact_entry
    vendor = Path(__file__).with_name('openfilm_subtitle_segments.mjs')
    if not vendor.is_file() or 'sha256:' + sha256_file(vendor) != UPSTREAM['sha256']:
        raise AppError('SUBTITLE_SEGMENT_SOURCE_CHANGED', '固定字幕分段算法缺失或摘要变化', exit_code=10)
    node = os.environ.get('AI_AD_EDITOR_NODE') or shutil.which('node')
    if not node or not Path(node).is_file() or (os.name == 'nt' and Path(node).suffix.lower() != '.exe'):
        raise AppError('SUBTITLE_SEGMENT_NODE_UNAVAILABLE', '字幕分段需要已有本地 Node >=22.2 原生可执行文件', exit_code=10)
    artifact_entry(vendor, 'subtitle-algorithm')
    artifact_entry(Path(__file__).with_name('subtitle_segment_worker.mjs'), 'subtitle-worker')
    env = dict(os.environ)
    for name in ('NODE_OPTIONS', 'NODE_PATH', 'NODE_EXTRA_CA_CERTS', 'NODE_REPL_EXTERNAL_MODULE'):
        env.pop(name, None)
    argv = [str(Path(node).resolve()), '--no-addons', '--disable-proto=throw', '--max-old-space-size=128',
            str(Path(__file__).with_name('subtitle_segment_worker.mjs'))]
    try:
        proc = subprocess.run(argv, input=json.dumps(request, ensure_ascii=False, allow_nan=False),
                              text=True, encoding='utf-8', errors='strict', stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                              env=env, timeout=30, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    except subprocess.TimeoutExpired as exc:
        raise AppError('SUBTITLE_SEGMENT_TIMEOUT', '字幕规划超过 30 秒预算', exit_code=6) from exc
    except OSError as exc:
        raise AppError('SUBTITLE_SEGMENT_NODE_UNAVAILABLE', '无法执行本地字幕规划器', exit_code=10, cause=str(exc)) from exc
    try:
        out = json.loads(proc.stdout)
        if not isinstance(out, dict) or out.get('protocol') != PROTOCOL or out.get('network') != 'disabled' or out.get('status') != 'succeeded' or proc.returncode:
            raise ValueError(str(out.get('message', proc.stderr[-1000:])) if isinstance(out, dict) else 'Invalid response')
        if not isinstance(out.get('lines'), list) or len(out['lines']) != len(request['lines']):
            raise ValueError('Result line inventory mismatch')
        return out
    except (ValueError, UnicodeError) as exc:
        raise AppError('SUBTITLE_SEGMENT_RESULT_INVALID', '本地字幕规划失败或结果无效', exit_code=6, cause=str(exc)) from exc


def segment_source(source: dict[str, Any], *, rules: dict[str, Any] | None = None,
                   edits: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    tps = source.get('ticks_per_second') if isinstance(source, dict) else None
    source = checked_source(source, tps)
    rules = checked_rules(rules or {})
    # Enforce the budget on corrected text as well, before starting Node.
    edits = edits or []
    if edits:
        edits = checked_corrections({'expected_input_sha256': 'internal', 'edits': edits}, 'internal', source)
        worst = copy.deepcopy(source)
        for line in worst['lines']:
            for target in ('text', 'translation'):
                additions = ''.join(e['text'] for e in edits if e['line_id'] == line['id'] and e['target'] == target)
                if additions:
                    line[target] = line.get(target, '') + additions
        checked_source(worst, tps)
    request_lines = []
    for line in source['lines']:
        base = line['start_tick']
        item = {'id': line['id'], 'text': line['text'], 'duration_ms': (line['end_tick'] - base) * 1000 / tps,
                'marks': [{'index': m['index'], 'start_ms': (m['start_tick'] - base) * 1000 / tps} for m in line.get('marks', [])]}
        if 'translation' in line:
            item['translation'] = line['translation']
        request_lines.append(item)
    raw = _worker({'protocol': PROTOCOL, 'network': 'disabled', 'lines': request_lines, 'rules': rules, 'edits': edits})
    revised, pieces, changes, warnings = [], [], [], []
    for original, result in zip(source['lines'], raw['lines']):
        if result.get('id') != original['id']:
            raise AppError('SUBTITLE_SEGMENT_RESULT_INVALID', '规划器更改了原句身份', exit_code=6)
        line = {**original, 'text': result['text']}
        line.pop('marks', None)
        base, end = line['start_tick'], line['end_tick']
        def tick(ms: Any) -> int:
            if isinstance(ms, bool) or not isinstance(ms, (int, float)) or not math.isfinite(ms):
                raise AppError('SUBTITLE_SEGMENT_RESULT_INVALID', '规划器返回非有限时钟', exit_code=6)
            return base + int((Decimal(str(ms)) * tps / 1000).to_integral_value(rounding=ROUND_HALF_UP))
        if result.get('marks'):
            line['marks'] = [{'index': m['index'], 'start_tick': tick(m['start_ms'])} for m in result['marks']]
        if 'translation' in result:
            line['translation'] = result['translation']
        previous, at = base, 0
        batch = result.get('pieces')
        if not isinstance(batch, list) or not batch:
            raise AppError('SUBTITLE_SEGMENT_RESULT_INVALID', '规划器没有返回分段', exit_code=6)
        for part, p in enumerate(batch):
            a, b = p['from'], p['to']
            start, stop = tick(p['start_ms']), tick(p['end_ms'])
            if p['part'] != part or not isinstance(a, int) or not isinstance(b, int) or not at <= a <= b <= len(line['text']) or line['text'][a:b] != p['text'] or line['text'][at:a].strip():
                raise AppError('SUBTITLE_SEGMENT_RESULT_INVALID', '分段丢失原文或字符范围无效', exit_code=6)
            if not base <= start < stop <= end or start < previous:
                raise AppError('SUBTITLE_SEGMENT_TIMING_UNREPRESENTABLE', '分段量化后无法保持原句内的正时长、不重叠时钟', exit_code=6)
            if 'translation' in p:
                trans = p['translation']
                if line.get('translation', '')[trans['from']:trans['to']] != trans['text']:
                    raise AppError('SUBTITLE_SEGMENT_RESULT_INVALID', '译文字符范围无效', exit_code=6)
            item = {k: copy.deepcopy(v) for k, v in p.items() if k not in {'start_ms', 'end_ms', 'marks'}}
            item.update({'line_id': line['id'], 'start_tick': start, 'end_tick': stop,
                         'timing_basis': 'provided-onsets-with-weighted-interiors' if line.get('marks') else 'estimated-from-line'})
            if p.get('marks'):
                item['marks'] = [{'index': m['index'], 'start_tick': tick(m['start_ms'])} for m in p['marks']]
            pieces.append(item)
            if stop - start < raw['rules']['minMs'] * tps / 1000:
                warnings.append({'code': 'SUBTITLE_SEGMENT_SHORT', 'line_id': line['id'], 'part': part})
            cap = raw['rules']['maxCells'] if re.search(r'[\u1100-\u11ff\u2e80-\ua4cf\uac00-\ud7ff\uf900-\ufaff\uff0c\u3002\uff1b\uff1a]', line['text']) else None
            if (cap is not None and p['cells'] > cap) or (cap is None and len(p['display_text']) > raw['rules']['maxChars']):
                warnings.append({'code': 'SUBTITLE_SEGMENT_UNBREAKABLE_WIDTH', 'line_id': line['id'], 'part': part})
            previous, at = stop, b
        if line['text'][at:].strip():
            raise AppError('SUBTITLE_SEGMENT_RESULT_INVALID', '分段尾部丢失原文', exit_code=6)
        if not line.get('marks'):
            warnings.append({'code': 'SUBTITLE_SEGMENT_ESTIMATED_TIMING', 'line_id': line['id']})
        if 'translation' in line:
            warnings.append({'code': 'SUBTITLE_TRANSLATION_HEURISTIC_ALIGNMENT', 'line_id': line['id']})
        changes.extend({'line_id': line['id'], **c} for c in result.get('changes', []))
        revised.append(line)
    new_source = checked_source({'format': SOURCE_FORMAT, 'ticks_per_second': tps, 'lines': revised}, tps)
    return {'format': RESULT_FORMAT, 'index_unit': 'unicode-code-point', 'source': new_source,
            'original_source': copy.deepcopy(source) if edits else None, 'rules': raw['rules'], 'pieces': pieces,
            'corrections': changes, 'algorithm': {**UPSTREAM, 'versions': raw['versions']}, 'network': 'disabled',
            'warnings': warnings}


def display_cues(result: dict[str, Any], mode: str) -> list[dict[str, Any]]:
    if mode not in {'original', 'translation', 'bilingual'}:
        raise argument_error('未知字幕显示模式', 'mode')
    cues = []
    for p in result['pieces']:
        translation = p.get('translation', {})
        if mode != 'original' and not translation.get('text', '').strip():
            raise argument_error('翻译/双语模式要求每行有非空、明确提供的译文', 'mode')
        text = p['display_text'] if mode == 'original' else translation['text'] if mode == 'translation' else p['display_text'] + '\n' + translation['text']
        if not text.strip():
            raise argument_error('字幕显示文字为空，请显式修订输入', 'text')
        group = (p['line_id'], translation.get('from'), translation.get('to'))
        if mode == 'translation' and cues and cues[-1]['translation_group'] == group:
            cues[-1]['end_tick'] = p['end_tick']
            cues[-1]['parts'].append(p['part'])
        else:
            cues.append({'start_tick': p['start_tick'], 'end_tick': p['end_tick'], 'text': text,
                         'line_id': p['line_id'], 'parts': [p['part']], 'translation_group': group})
    return cues


def srt_text(cues: list[dict[str, Any]], tps: int) -> str:
    def stamp(tick: int) -> str:
        # Integer half-up rounding, including very large absolute project ticks.
        ms = (tick * 2000 + tps) // (tps * 2)
        seconds, millisecond = divmod(ms, 1000)
        minute, second = divmod(seconds, 60)
        hour, minute = divmod(minute, 60)
        return f'{hour:02}:{minute:02}:{second:02},{millisecond:03}'
    output = []
    previous = None
    for i, cue in enumerate(cues, 1):
        a, b = stamp(cue['start_tick']), stamp(cue['end_tick'])
        if a == b:
            raise AppError('SUBTITLE_SEGMENT_SRT_QUANTIZATION', 'SRT 毫秒量化后时长为零，请使用更长的源时钟', exit_code=6)
        if previous is not None and cue['start_tick'] < previous:
            raise AppError('SUBTITLE_SEGMENT_RESULT_INVALID', '字幕显示时钟重叠', exit_code=6)
        previous = cue['end_tick']
        output.append(f'{i}\n{a} --> {b}\n{cue["text"]}\n')
    return '\n'.join(output)
