"""Sequence-local, finite audio DAGs; no I/O or author-project mutation.

Audio pads are consumed exactly once. A bus-solo graph may use a second,
unpruned detector context so isolating a return cannot change its detector.
"""
from __future__ import annotations

import copy
import math
import re
from fractions import Fraction

from .errors import AppError
from .utils import ID_RE


MAX_NODES, MAX_EDGES, MAX_POINTS = 128, 512, 1024
EASINGS = {'linear', 'hold', 'ease_in', 'ease_out', 'ease_in_out', 'bezier'}
MASTER = 'master'


def fail(message, path='sequence.audio_routing', code='AUDIO_ROUTING_INVALID'):
    raise AppError(code, message, path=path, exit_code=2)


def obj(value, allowed, path, required=()):
    if not isinstance(value, dict) or set(value)-set(allowed) or set(required)-set(value):
        fail('路由对象字段缺失、类型错误或含未知字段', path)
    return value


def number(value, lo, hi, path):
    if type(value) not in (int, float) or not lo <= value <= hi or not math.isfinite(value):
        fail(f'必须为 {lo}..{hi} 的有限数字', path)
    return value


def array(value, maximum, path):
    if not isinstance(value, list) or len(value) > maximum:
        fail('必须为有界数组', path)
    return value


def identifier(value, path):
    if not isinstance(value, str) or not ID_RE.fullmatch(value):
        fail('标识符格式无效', path)
    return value


def points(value, duration, lo, hi, path):
    rows = array(value, 64, path)
    if not rows:
        fail('自动化必须至少包含一个点', path)
    previous = -1
    for i, point in enumerate(rows):
        p = f'{path}[{i}]'
        obj(point, {'at_tick', 'value', 'interpolation', 'control_points'}, p, {'at_tick', 'value'})
        tick = point['at_tick']
        if type(tick) is not int or not previous < tick <= duration:
            fail('自动化 tick 必须为 0..duration 严格递增整数', p+'.at_tick')
        previous = tick
        number(point['value'], lo, hi, p+'.value')
        interpolation = point.get('interpolation', 'linear')
        if not isinstance(interpolation, str) or interpolation not in EASINGS:
            fail('自动化插值类型无效', p+'.interpolation')
        if interpolation == 'bezier':
            controls = point.get('control_points')
            if not isinstance(controls, list) or len(controls) not in (2, 4):
                fail('Bezier 必须包含 2 或 4 个控制值', p+'.control_points')
            for n in controls:
                number(n, 0, 1, p+'.control_points')
        elif 'control_points' in point:
            fail('非 Bezier 自动化不接受控制值', p+'.control_points')
    return len(rows)


def automation(value, duration, path):
    count, seen = 0, set()
    for i, row in enumerate(array(value, 2, path)):
        p = f'{path}[{i}]'
        obj(row, {'property', 'keyframes'}, p, {'property', 'keyframes'})
        prop = row['property']
        if not isinstance(prop, str) or prop not in {'audio.volume', 'audio.pan'} or prop in seen:
            fail('自动化属性只允许唯一的 audio.volume/audio.pan', p+'.property')
        seen.add(prop)
        count += points(row['keyframes'], duration, -1 if prop == 'audio.pan' else 0,
                        1 if prop == 'audio.pan' else 4, p+'.keyframes')
    return count


COMPRESSOR = {'threshold': (.000976563, 1), 'ratio': (1, 20), 'attack': (.01, 2000),
              'release': (.01, 9000), 'makeup': (1, 64), 'knee': (1, 8),
              'level_in': (.015625, 64), 'level_sc': (.015625, 64), 'mix': (0, 1)}


def compressor(value, path, *, external=False):
    allowed = set(COMPRESSOR) | {'mode', 'link', 'detection'} if external else {'threshold', 'ratio', 'attack', 'release'}
    obj(value, allowed, path)
    for key, val in value.items():
        if key in COMPRESSOR:
            number(val, *COMPRESSOR[key], path+'.'+key)
        elif not isinstance(val, str) or val not in {'mode': {'upward', 'downward'}, 'link': {'average', 'maximum'},
                         'detection': {'peak', 'rms'}}[key]:
            fail('侧链枚举值无效', path+'.'+key)


def processor(value, path, *, master=False):
    numeric = {'volume': (0, 4), 'pan': (-1, 1), 'fade_in': (0, 86400), 'fade_out': (0, 86400),
               'pitch_semitones': (-24, 24), 'highpass': (20, 20000), 'lowpass': (20, 20000)}
    booleans = {'mute', 'muted', 'solo', 'dialogue_enhance', 'voice_enhance'}
    objects = {'compressor', 'equalizer', 'eq', 'reverb', 'loudnorm'}
    obj(value, set(numeric) | booleans | objects | {'noise_reduction', 'denoise'}, path)
    for key, val in value.items():
        p = path+'.'+key
        if key in numeric:
            number(val, *numeric[key], p)
        elif key in booleans:
            if type(val) is not bool or (master and key == 'solo'):
                fail('布尔处理字段无效；master 不接受 solo', p)
        elif key in {'noise_reduction', 'denoise'}:
            if type(val) is not bool:
                number(val, -80, -20, p)
        elif key == 'compressor':
            compressor(val, p)
        elif key in {'equalizer', 'eq'}:
            limits = {'frequency': (20, 20000), 'f': (20, 20000), 'gain': (-24, 24), 'g': (-24, 24), 'width': (.05, 10), 'w': (.05, 10)}
            obj(val, limits, p)
            for k, n in val.items():
                number(n, *limits[k], p+'.'+k)
        elif key == 'loudnorm':
            limits = {'i': (-70, -5), 'integrated': (-70, -5), 'tp': (-9, 0), 'true_peak': (-9, 0), 'lra': (1, 50)}
            obj(val, limits, p)
            for k, n in val.items():
                number(n, *limits[k], p+'.'+k)
        elif key == 'reverb':
            obj(val, {'in_gain', 'out_gain', 'delays', 'decays'}, p)
            for k in ('in_gain', 'out_gain'):
                if k in val:
                    number(val[k], 0, 1, p+'.'+k)
            parsed = []
            for k, default, hi in (('delays', '60|90', 90000), ('decays', '0.25|0.15', 1)):
                raw = val.get(k, default)
                if not isinstance(raw, str) or len(raw) > 2048 or not re.fullmatch(r'\d+(?:\.\d+)?(?:\|\d+(?:\.\d+)?)*', raw):
                    fail('混响延迟/衰减必须为数字与 |，不接受滤镜表达式', p+'.'+k)
                values = raw.split('|')
                if len(values) > 32:
                    fail('混响最多 32 条支路', p+'.'+k)
                for n in values:
                    number(float(n), 0, hi, p+'.'+k)
                parsed.append(values)
            if len(parsed[0]) != len(parsed[1]):
                fail('混响延迟和衰减数量不一致', p)


def plan(sequence):
    """Validate authored rows and return a detached, topologically sorted DAG."""
    routing = sequence.get('audio_routing')
    if routing is None:
        return None
    base = 'sequence.audio_routing'
    obj(routing, {'version', 'tracks', 'buses', 'master'}, base, {'version'})
    if type(routing['version']) is not int or routing['version'] != 1:
        fail('路由版本必须为整数 1', base+'.version')
    duration = sequence.get('duration_tick', 0)
    if type(duration) is not int or duration <= 0:
        fail('路由序列时长必须为正整数', 'sequence.duration_tick')
    tracks = {t['id']: t for t in sequence.get('tracks', []) if t.get('kind') in {'video', 'audio'}}
    buses = array(routing.get('buses', []), MAX_NODES-1, base+'.buses')
    if len(tracks)+len(buses)+1 > MAX_NODES:
        fail('命名音频路由超过 128 节点', base, 'AUDIO_ROUTING_BUDGET_EXCEEDED')
    nodes, edges, point_count = {}, [], 0
    for tid, track in tracks.items():
        nodes['track/'+tid] = {'id': tid, 'kind': 'track', 'audio': copy.deepcopy(track.get('audio') or {}), 'keyframes': []}
    rows = {}
    for i, row in enumerate(array(routing.get('tracks', []), MAX_NODES-1, base+'.tracks')):
        path = f'{base}.tracks[{i}]'
        obj(row, {'track_id', 'output', 'sends', 'keyframes', 'sidechain'}, path, {'track_id'})
        tid = identifier(row['track_id'], path+'.track_id')
        if tid not in tracks or tid in rows:
            fail('路由轨道缺失、类型不支持或重复', path+'.track_id', 'AUDIO_ROUTING_REFERENCE_INVALID')
        rows[tid] = (row, path)
    for i, row in enumerate(buses):
        path = f'{base}.buses[{i}]'
        obj(row, {'id', 'name', 'audio', 'output', 'sends', 'keyframes', 'sidechain'}, path, {'id'})
        bid = identifier(row['id'], path+'.id')
        if bid == MASTER or 'bus/'+bid in nodes:
            fail('总线 ID 重复或使用保留 master', path+'.id')
        if 'name' in row and (not isinstance(row['name'], str) or not 1 <= len(row['name']) <= 256):
            fail('总线名称必须为 1..256 字符', path+'.name')
        processor(row.get('audio', {}), path+'.audio')
        nodes['bus/'+bid] = {'id': bid, 'kind': 'bus', 'audio': copy.deepcopy(row.get('audio', {})), 'keyframes': []}
    master = routing.get('master', {})
    obj(master, {'audio', 'keyframes', 'sidechain'}, base+'.master')
    processor(master.get('audio', {}), base+'.master.audio', master=True)
    nodes[MASTER] = {'id': MASTER, 'kind': MASTER, 'audio': copy.deepcopy(master.get('audio', {})), 'keyframes': []}

    def bus_ref(bid, path):
        identifier(bid, path)
        key = 'bus/'+bid
        if key not in nodes:
            fail('引用的命名总线不存在', path, 'AUDIO_ROUTING_REFERENCE_INVALID')
        return key

    all_rows = [(key, *rows.get(node['id'], ({}, base+'.tracks'))) for key, node in nodes.items() if node['kind'] == 'track']
    all_rows += [('bus/'+r['id'], r, f'{base}.buses[{i}]') for i, r in enumerate(buses)]
    all_rows += [(MASTER, master, base+'.master')]
    for key, row, path in all_rows:
        node = nodes[key]
        point_count += automation(row.get('keyframes', []), duration, path+'.keyframes')
        node['keyframes'] = copy.deepcopy(row.get('keyframes', []))
        if key != MASTER:
            output = row.get('output', MASTER)
            if output is not None:
                dest = MASTER if output == MASTER else bus_ref(output, path+'.output')
                edges.append({'source': key, 'dest': dest, 'kind': 'output', 'tap': 'post_fader', 'gain': 1, 'keyframes': []})
            for i, send in enumerate(array(row.get('sends', []), MAX_EDGES, path+'.sends')):
                sp = f'{path}.sends[{i}]'
                obj(send, {'bus_id', 'gain', 'tap', 'keyframes'}, sp, {'bus_id'})
                dest = bus_ref(send['bus_id'], sp+'.bus_id')
                gain, tap = send.get('gain', 1), send.get('tap', 'post_fader')
                number(gain, 0, 4, sp+'.gain')
                if not isinstance(tap, str) or tap not in {'pre_fader', 'post_fader'}:
                    fail('发送采样点无效', sp+'.tap')
                if 'keyframes' in send:
                    point_count += points(send['keyframes'], duration, 0, 4, sp+'.keyframes')
                edges.append({'source': key, 'dest': dest, 'kind': 'send', 'tap': tap, 'gain': gain, 'keyframes': copy.deepcopy(send.get('keyframes', []))})
        if 'sidechain' in row:
            sc, sp = row['sidechain'], path+'.sidechain'
            obj(sc, {'bus_id', 'track_id', 'tap', 'compressor'}, sp)
            if ('bus_id' in sc) == ('track_id' in sc):
                fail('侧链必须且只能指定一个 bus_id 或 track_id', sp)
            if 'bus_id' in sc:
                source = bus_ref(sc['bus_id'], sp+'.bus_id')
            else:
                tid = identifier(sc['track_id'], sp+'.track_id')
                source = 'track/'+tid
                if source not in nodes:
                    fail('侧链轨道不存在', sp+'.track_id', 'AUDIO_ROUTING_REFERENCE_INVALID')
            tap = sc.get('tap', 'post_fader')
            if not isinstance(tap, str) or tap not in {'pre_fader', 'post_fader'}:
                fail('侧链采样点无效', sp+'.tap')
            compressor(sc.get('compressor', {}), sp+'.compressor', external=True)
            node['sidechain'] = copy.deepcopy(sc.get('compressor', {}))
            edges.append({'source': source, 'dest': key, 'kind': 'detector', 'tap': tap, 'gain': 1, 'keyframes': []})
    if len(edges) > MAX_EDGES or point_count > MAX_POINTS:
        fail('路由超过 512 边或 1024 自动化点', base, 'AUDIO_ROUTING_BUDGET_EXCEEDED')
    incoming = {key: 0 for key in nodes}
    for edge in edges:
        incoming[edge['dest']] += 1
    ready = sorted(key for key, degree in incoming.items() if not degree)
    order = []
    while ready:
        key = ready.pop(0)
        order.append(key)
        for edge in edges:
            if edge['source'] == key:
                incoming[edge['dest']] -= 1
                if not incoming[edge['dest']]:
                    ready.append(edge['dest']); ready.sort()
    if len(order) != len(nodes):
        fail('直达、发送或侧链形成循环，拒绝音频反馈', base, 'AUDIO_ROUTING_CYCLE')
    solos = {key for key, node in nodes.items() if node['kind'] == 'bus' and node['audio'].get('solo')}
    audio_edges = [e for e in edges if e['kind'] != 'detector']

    def closure(selected, backwards):
        found = set(selected)
        while True:
            before = len(found)
            for edge in audio_edges:
                a, b = (edge['dest'], edge['source']) if backwards else (edge['source'], edge['dest'])
                if a in found:
                    found.add(b)
            if len(found) == before:
                return found
    ancestors, descendants = closure(solos, True), closure(solos, False)
    for edge in edges:
        edge['audible'] = (not solos or edge['kind'] == 'detector' or edge['dest'] in ancestors or edge['source'] in descendants)
    return {'nodes': nodes, 'edges': edges, 'order': order, 'solos': sorted(solos),
            'automation_points': point_count, 'detector_context': bool(solos and any(e['kind'] == 'detector' for e in edges))}


def compile_graph(sequence, sources, filters, metadata, warnings, *, tps, process):
    """Consume root track pads and emit one exact-duration float master pad.

    process is the existing bounded audio processor; routing defines its
    pre/post-fader placement without introducing a second DSP implementation.
    """
    graph = plan(sequence)
    if graph is None:
        raise ValueError('compile_graph requires an explicit routing object')
    start_filter = len(filters)
    nodes, edges = graph['nodes'], graph['edges']
    samples = max(1, math.ceil(Fraction(sequence['duration_tick']*48000, tps)))
    counter = 0

    def label():
        nonlocal counter
        counter += 1
        return f'aroute{counter}'

    def chain(source, operations):
        target = label()
        filters.append((f'[{source}]' if source else '')+','.join(operations)+f'[{target}]')
        return target

    def silence():
        return chain(None, ['anullsrc=r=48000:cl=stereo', f'atrim=end_sample={samples}', 'asetpts=N/SR/TB'])

    def fanout(source, count):
        if not count:
            filters.append(f'[{source}]anullsink')
            return []
        if count == 1:
            return [source]
        pads = [label() for _ in range(count)]
        filters.append(f'[{source}]asplit={count}'+''.join(f'[{p}]' for p in pads))
        return pads

    def mix(pads):
        if not pads:
            return silence()
        if len(pads) == 1:
            return pads[0]
        target = label()
        filters.append(''.join(f'[{p}]' for p in pads)+f'amix=inputs={len(pads)}:duration=longest:dropout_transition=0:normalize=0[{target}]')
        return target

    # Every node has an exact sample length, including absent detector tracks.
    normalize = ['aresample=48000', 'aformat=sample_fmts=fltp:sample_rates=48000:channel_layouts=stereo',
                 f'apad=whole_len={samples}', f'atrim=end_sample={samples}', 'asetpts=N/SR/TB']
    source_sets = [{} for _ in range(2 if graph['detector_context'] else 1)]
    for key, node in nodes.items():
        if node['kind'] != 'track':
            continue
        source = chain(mix(sources.get(node['id'], [])), normalize)
        for output, pad in zip(source_sets, fanout(source, len(source_sets))):
            output[key] = pad
    external = {}

    def execute(track_sources, *, context=False):
        pending = {key: [] for key in nodes}
        detectors = {}
        master_output = None
        for key in graph['order']:
            node = nodes[key]
            signal = mix(([track_sources[key]] if node['kind'] == 'track' else [])+pending[key])
            if 'sidechain' in node:
                detector = detectors[key] if context or not graph['detector_context'] else external[key]
                # Equal clocks/lengths do not imply equal packet sizes. Native
                # sidechaincompress can end early with mismatched packet
                # scheduling; explicitly align both branches before its join.
                signal = chain(signal, ['asetnsamples=n=1024:p=0'])
                detector = chain(detector, ['asetnsamples=n=1024:p=0'])
                parameters = {'threshold': .125, 'ratio': 2, 'attack': 20, 'release': 250, **node['sidechain']}
                target = label()
                filters.append(f'[{signal}][{detector}]sidechaincompress='+':'.join(f'{k}={v}' for k, v in parameters.items())+f'[{target}]')
                signal = target
            control = copy.deepcopy(node['audio'])
            if node['kind'] == 'track':
                for field in ('fade_in', 'fade_out'):
                    if control.pop(field, None) and not context:
                        warnings.append({'code': 'RENDER_FEATURE_UNSUPPORTED', 'track_id': node['id'], 'feature': 'track_audio.'+field,
                                         'message': '轨道没有片段包络；请在片段或序列容器上声明音频淡入淡出'})
            fader = {field: control.pop(field) for field in ('volume', 'pan', 'fade_in', 'fade_out') if field in control}
            operations = process({}, control)+normalize
            if control.get('mute') or control.get('muted'):
                operations.append('volume=0')
            pre = chain(signal, operations)
            outgoing = [e for e in edges if e['source'] == key and
                        (context or (e['audible'] and (e['kind'] != 'detector' or not graph['detector_context'])))]
            extra = [e for e in edges if e['source'] == key and e['kind'] == 'detector'] if context else []
            requirements = [('edge', e) for e in outgoing]+[('external', e) for e in extra]
            taps = {}
            pre_requests = [r for r in requirements if r[1]['tap'] == 'pre_fader']
            pre_pads = fanout(pre, 1+len(pre_requests))
            post = chain(pre_pads[0], process({'keyframes': node['keyframes']}, fader)+normalize)
            for request, pad in zip(pre_requests, pre_pads[1:]):
                taps[id(request)] = pad
            post_requests = [r for r in requirements if r[1]['tap'] == 'post_fader']
            # master has no outgoing edge; preserve its only final result.
            post_pads = fanout(post, len(post_requests)+(1 if key == MASTER else 0))
            for request, pad in zip(post_requests, post_pads):
                taps[id(request)] = pad
            for request in requirements:
                kind, edge = request
                pad = taps[id(request)]
                if kind == 'external':
                    external[edge['dest']] = pad
                elif edge['kind'] == 'detector':
                    detectors[edge['dest']] = pad
                else:
                    if edge['kind'] == 'send' and (edge['keyframes'] or edge['gain'] != 1):
                        keyframes = [{'property': 'audio.volume', 'keyframes': edge['keyframes']}] if edge['keyframes'] else []
                        pad = chain(pad, process({'keyframes': keyframes}, {'volume': edge['gain']}) or ['anull'])
                    pending[edge['dest']].append(pad)
            if key == MASTER:
                master_output = post_pads[-1]
        if master_output is None:
            raise AssertionError('validated DAG has no master')
        return master_output

    if graph['detector_context']:
        context_master = execute(source_sets[0], context=True)
        filters.append(f'[{context_master}]anullsink')
    output = execute(source_sets[-1])
    size = sum(len(f.encode('utf-8')) for f in filters[start_filter:])
    if size > 4*1024**2:
        fail('路由滤镜图超过 4 MiB', code='AUDIO_ROUTING_BUDGET_EXCEEDED')
    metadata.append({'kind': 'sequence-audio-routing', 'sequence_id': sequence['id'], 'version': 1,
                     'sample_rate': 48000, 'channels': 2, 'output_samples': samples,
                     'nodes': copy.deepcopy(nodes), 'edges': copy.deepcopy(edges), 'topological_order': graph['order'],
                     'solo_buses': graph['solos'], 'unpruned_detector_context': graph['detector_context'],
                     'execution_passes': len(source_sets), 'execution_nodes': len(nodes)*len(source_sets),
                     'execution_edges': len(edges)*len(source_sets), 'automation_points': graph['automation_points'],
                     'filter_utf8_bytes': size, 'automatic_limiter': False, 'intermediate_files': 0,
                     'processing_order': ['input-float-sum', 'named-sidechain', 'tone-effects', 'mute',
                                          'pre-fader-tap', 'volume-pan-fades', 'post-fader-tap', 'output-and-sends'],
                     'sidechain_packet_samples': 1024})
    return output
