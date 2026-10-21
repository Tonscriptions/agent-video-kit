"""Canonical local canvas extension; the original display samples stay protected."""
from __future__ import annotations

import hashlib
import json
import math
import re
from fractions import Fraction

from .errors import AppError

PROTOCOL = 'agent-video-outpaint-mask-v1'


def _hash(value):
    return 'sha256:' + hashlib.sha256(json.dumps(value, ensure_ascii=True, sort_keys=True,
                                               separators=(',', ':')).encode('utf8')).hexdigest()


def geometry(source_width, source_height, *, width, height, offset_x=None, offset_y=None):
    values = (source_width, source_height, width, height)
    if any(type(v) is not int or not 1 <= v <= 8192 for v in values):
        raise AppError('OUTPAINT_GEOMETRY_INVALID', '扩图源和目标边长须为 1..8192 的整数', exit_code=2)
    if width * height > 16_777_216 or width < source_width or height < source_height:
        raise AppError('OUTPAINT_GEOMETRY_INVALID', '扩图画布须完整容纳原显示画面，且不超过 16,777,216 像素', exit_code=2)
    if (width, height) == (source_width, source_height):
        raise AppError('OUTPAINT_GEOMETRY_INVALID', '扩图要求至少一边严格扩大', exit_code=2)
    x = (width - source_width) // 2 if offset_x is None else offset_x
    y = (height - source_height) // 2 if offset_y is None else offset_y
    if any(type(v) is not int for v in (x, y)) or not 0 <= x <= width - source_width or not 0 <= y <= height - source_height:
        raise AppError('OUTPAINT_GEOMETRY_INVALID', '扩图放置须为完整保留原画面的非负整数坐标', exit_code=2)
    return {'protocol': PROTOCOL, 'width': width, 'height': height,
            'source_width': source_width, 'source_height': source_height,
            'offset_x': x, 'offset_y': y, 'outside_rgba': [127, 127, 127, 255],
            'original_rgba': 'preserve-normalized-display-cfr-samples',
            'generated_alpha': 255, 'mask': 'outside-original-half-open-rectangle'}


def mask_identity(spec):
    result = {'kind': 'generated-outpaint', 'channel': 'alpha', 'geometry': spec,
              'sha256': _hash(spec), 'clock': 'same-decoded-source-frames-and-pts'}
    result['plan_sha256'] = _hash(result)
    return result


def extend_plan(plan, *, width, height, offset_x=None, offset_y=None):
    """Called after the existing source range/display/CFR normalization plan."""
    spec = geometry(plan['video']['width'], plan['video']['height'], width=width, height=height,
                    offset_x=offset_x, offset_y=offset_y)
    plan['outpainting'] = spec
    plan['mask'] = mask_identity(spec)
    plan['video'].update(width=width, height=height)
    plan['warnings'].append({'code': 'OUTPAINT_MODEL_REVIEW_REQUIRED',
        'message': '仅生成原矩形外；画外结构、纹理、边界、时序与许可须复核，原显示画面受保护不等于生成质量通过'})
    return plan


def valid_plan(plan):
    try:
        spec = plan['outpainting']
        expected = geometry(spec['source_width'], spec['source_height'], width=spec['width'],
                            height=spec['height'], offset_x=spec['offset_x'], offset_y=spec['offset_y'])
        return (spec == expected and plan['mask'] == mask_identity(expected)
                and type(plan['video']['width']) is int and type(plan['video']['height']) is int
                and plan['video']['width'] == spec['width'] and plan['video']['height'] == spec['height']
                and plan['inpainting']['grow'] == 0 and plan['inpainting']['feather'] == 0
                and plan['inpainting']['threshold'] == .5
                and plan['engine'] in {'torchscript-lama-local-v1', 'diffusers-wan-vace-local-v1'})
    except (AppError, ValueError, KeyError, TypeError):
        return False


def recipe(plan, adapter, source_asset_id):
    """Store editable local inputs, independently of disposable validation files."""
    result = {'version': 1, 'source_asset_id': source_asset_id, 'source_sha256': plan['source']['sha256'],
              'adapter_id': adapter['adapter_id'], 'adapter_sha256': adapter['sha256'], 'engine': plan['engine'],
              'geometry': plan['outpainting'], 'range': plan['range'], 'fps': plan['video']['fps'],
              'frames': plan['video']['frames'], 'inpainting': plan['inpainting'],
              'generation': plan.get('generation')}
    result['sha256'] = _hash(result)
    return result


def validate_recipe(value, *, asset, assets):
    try:
        keys = {'version', 'source_asset_id', 'source_sha256', 'adapter_id', 'adapter_sha256',
                'engine', 'geometry', 'range', 'fps', 'frames', 'inpainting', 'generation', 'sha256'}
        if not isinstance(value, dict) or set(value) != keys or type(value['version']) is not int or value['version'] != 1:
            raise ValueError('recipe inventory/version')
        if value['sha256'] != _hash({k: v for k, v in value.items() if k != 'sha256'}):
            raise ValueError('recipe digest')
        if not isinstance(value['adapter_id'], str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._:-]{0,127}', value['adapter_id']):
            raise ValueError('adapter ID')
        for name in ('source_sha256', 'adapter_sha256'):
            if not isinstance(value[name], str) or not re.fullmatch(r'sha256:[a-f0-9]{64}', value[name]):
                raise ValueError('recipe '+name)
        parent = assets[value['source_asset_id']]
        if parent['id'] == asset['id'] or parent['kind'] != 'video' or parent['sha256'] != value['source_sha256'] or asset['kind'] != 'video':
            raise ValueError('source dependency')
        g = value['geometry']
        plan = {'engine': value['engine'], 'video': {'width': g['width'], 'height': g['height']},
                'outpainting': g, 'mask': mask_identity(g), 'inpainting': value['inpainting']}
        if not valid_plan(plan): raise ValueError('protected geometry')
        video = asset['probe']['video']
        if video['width'] != g['width'] or video['height'] != g['height']:
            raise ValueError('output raster')
        stream = next(s for s in parent['probe']['streams'] if s.get('codec_type') == 'video' and not s.get('disposition', {}).get('attached_pic'))
        sar_text = stream.get('sample_aspect_ratio')
        sar = Fraction(sar_text.replace(':', '/')) if sar_text not in (None, 'N/A', '0:1') else Fraction(1)
        rotation = float(next((s['rotation'] for s in stream.get('side_data_list', []) if 'rotation' in s), stream.get('tags', {}).get('rotate', 0)))
        if not math.isfinite(rotation) or rotation % 90 or sar <= 0: raise ValueError('source display transform')
        sw, sh = int(stream['width'])*float(sar), float(stream['height'])
        if abs(rotation) % 180 == 90: sw, sh = sh, sw
        scale = min(1., max(g['source_width'], g['source_height'])/max(sw, sh))
        if (max(1, round(sw*scale)), max(1, round(sh*scale))) != (g['source_width'], g['source_height']):
            raise ValueError('normalized source raster')
        r = value['range']
        if (set(r) != {'start_seconds', 'end_seconds'} or any(type(r[k]) not in {int, float} or not math.isfinite(r[k]) for k in r)
                or not 0 <= r['start_seconds'] < r['end_seconds']):
            raise ValueError('source range')
        if r['end_seconds'] > float(parent['probe']['duration_seconds']) + .001:
            raise ValueError('source range exceeds dependency')
        if not isinstance(value['fps'], str): raise ValueError('source CFR rate')
        rate = Fraction(value['fps'])
        if not 0 < rate <= 240 or type(value['frames']) is not int or value['frames'] != max(1, math.ceil((r['end_seconds']-r['start_seconds'])*float(rate)-1e-8)):
            raise ValueError('source CFR clock')
        out_stream = next(s for s in asset['probe']['streams'] if s.get('codec_type') == 'video' and not s.get('disposition', {}).get('attached_pic'))
        if (Fraction(video['fps']) != rate or int(out_stream['nb_frames']) != value['frames']
                or abs(float(video['duration_seconds'])-value['frames']/float(rate)) > .000001):
            raise ValueError('output CFR clock')
        from .local_inpainting import normalize_options
        if normalize_options(**value['inpainting']) != value['inpainting']: raise ValueError('repair settings')
        if value['engine'] == 'diffusers-wan-vace-local-v1':
            from .local_vace import normalize_generation
            if normalize_generation(**value['generation'], frames=value['frames']) != value['generation']: raise ValueError('generation settings')
        elif value['generation'] is not None: raise ValueError('LaMa generation settings')
    except (AppError, KeyError, TypeError, ValueError, ZeroDivisionError, OverflowError, StopIteration) as exc:
        raise AppError('OUTPAINT_RECIPE_INVALID', '扩图可编辑配方、源依赖、几何或输出画幅无效', exit_code=2, cause=str(exc)) from exc


def decoder_graph(plan, source_filter):
    if not valid_plan(plan):
        raise AppError('OUTPAINT_PLAN_INVALID', '扩图计划或合成蒙版身份无效', exit_code=10)
    s = plan['outpainting']
    x, y = s['offset_x'], s['offset_y']
    right, bottom = x + s['source_width'] - 1, y + s['source_height'] - 1
    # Both branches inherit the same exact PTS/count. The mask never depends on
    # source colors/alpha, and the protected branch has no pixel-changing filter.
    return (f"[0:{plan['video']['source_stream_index']}]{source_filter},"
            f"pad={s['width']}:{s['height']}:{x}:{y}:color=0x7f7f7fff,split=2[src][mb];"
            "[mb]format=gbrap,geq=r='255':g='255':b='255':a="
            f"'if(between(X,{x},{right})*between(Y,{y},{bottom}),0,255)',format=rgba[mask];"
            "[src][mask]hstack=inputs=2:shortest=1,format=rgba[paired]")


def rebind_recipe(value, *, source_asset_id, asset, assets):
    """Fragment IDs change; validate the original before hashing the new binding."""
    validate_recipe(value, asset=asset, assets=assets)
    result = dict(value)
    result['source_asset_id'] = source_asset_id
    result['sha256'] = _hash({k: v for k, v in result.items() if k != 'sha256'})
    return result
