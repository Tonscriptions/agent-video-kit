"""Bounded explicit polylines using the original OpenFilm progressive ink core."""
from __future__ import annotations

import json
import math
from pathlib import Path
import re

from . import html_motion as html

ENGINE = 'agent-stroke-motion-v1'
MAX_INPUT = 2 * 1024**2


def bad(message, field='stroke'):
    html.fail('STROKE_PLAN_INVALID', message, field)


def number(value, field, low, high):
    if type(value) not in (int, float) or not low <= value <= high or not math.isfinite(value):
        bad('要求有限且范围内的数值', field)
    return value


def integer(value, field, low, high):
    if type(value) is not int or not low <= value <= high:
        bad('要求范围内的整数', field)
    return value


def prepare(value, ticks):
    keys = {'version','width','height','fps','duration_tick','stroke_width','color','characters'}
    if not isinstance(value, dict) or set(value) != keys or value['version'] != ENGINE:
        bad('描线清单字段或版本无效')
    if not isinstance(value['color'], str) or not re.fullmatch(r'#[0-9a-fA-F]{6}', value['color']):
        bad('color 必须为 #RRGGBB', 'color')
    spec, frames = html.validate_spec({k:value[k] for k in ('width','height','fps','duration_tick')} |
        {'entry':'index.html','variables':[{'name':'ink_color','type':'color','default':value['color']}]}, ticks)
    width = number(value['stroke_width'], 'stroke_width', 0.25, 64)
    chars = value['characters']
    if not isinstance(chars, list) or not 1 <= len(chars) <= 256:
        bad('要求 1..256 个码点', 'characters')
    st = {'strokes':[], 'lens':[], 'startLen':[], 'charRange':[], 'total':0}
    times, count, previous, ink = [], 0, 0, False
    for i, ch in enumerate(chars):
        if not isinstance(ch, dict) or set(ch) != {'text','start_tick','end_tick','strokes'}:
            bad('字符字段无效', str(i))
        text = ch['text']
        if not isinstance(text, str) or len(text) != 1 or 0xD800 <= ord(text) <= 0xDFFF or (ord(text) < 32 and text != ' '):
            bad('字符必须为一个 Unicode 码点，空白仅支持空格', str(i))
        start = integer(ch['start_tick'], str(i)+'.start_tick', previous, spec['duration_tick'])
        end = integer(ch['end_tick'], str(i)+'.end_tick', start+1, spec['duration_tick'])
        previous = end
        strokes = ch['strokes']
        if not isinstance(strokes, list) or (not strokes and text != ' ') or (strokes and text == ' '):
            bad('可见字符必须有笔画，空格不能含笔画', str(i))
        a = st['total']
        for j, pts in enumerate(strokes):
            if not isinstance(pts, list) or not 2 <= len(pts) <= 2048:
                bad('每笔要求 2..2048 个点', str(i))
            count += len(pts)
            if count > 32768 or len(st['strokes']) >= 2048 or count * frames > 8_000_000:
                html.fail('STROKE_PLAN_BUDGET', '超过笔画/点数/点帧预算')
            poly, lengths = [], [0]
            for p in pts:
                if not isinstance(p, list) or len(p) != 2:
                    bad('坐标要求 [x,y]', str(i))
                x = number(p[0], str(i)+'.x', width/2, spec['width']-width/2)
                y = number(p[1], str(i)+'.y', width/2, spec['height']-width/2)
                if poly:
                    lengths.append(lengths[-1]+math.hypot(x-poly[-1]['x'], y-poly[-1]['y']))
                poly.append({'x':x,'y':y})
            if lengths[-1] <= 0:
                bad('笔画长度必须大于零', str(i))
            st['startLen'].append(st['total'])
            st['strokes'].append(poly)
            st['lens'].append(lengths)
            st['total'] += lengths[-1]
            ink = True
        st['charRange'].append([a, st['total']])
        times.append([start/ticks, end/ticks])
    if not ink:
        bad('至少需要一个有笔画字符')
    return spec, {'stroke':st, 'times':times, 'stroke_width':width}, {
        'characters':len(chars),'strokes':len(st['strokes']),'points':count,'point_frames':count*frames,
        'frame_count':frames,'text':''.join(ch['text'] for ch in chars),'automatic_alignment':False}


PAGE = b'''<!doctype html><meta charset="utf-8"><style>
html,body{margin:0;background:transparent;overflow:hidden}canvas{display:block}</style><canvas></canvas>
<script type="module">
import {drawStrokeText,writtenLength} from './openfilm_stroke.mjs';
const plan=await (await fetch('./geometry.json')).json();
const c=document.querySelector('canvas'),ctx=c.getContext('2d');
c.width=plan.width;c.height=plan.height;
window.film={width:c.width,height:c.height,duration:plan.duration,frame(t,params){
 const color=params.ink_color;
 if(!/^#[0-9a-fA-F]{6}$/.test(color))throw new Error('STROKE_COLOR_INVALID: #RRGGBB required');
 ctx.clearRect(0,0,c.width,c.height);ctx.lineWidth=plan.stroke_width;
 ctx.lineCap='round';ctx.lineJoin='round';ctx.strokeStyle=color;
 drawStrokeText(ctx,plan.stroke,writtenLength(plan.stroke,plan.times,t));
}};
</script>'''


def build_source(root, project, manifest_path):
    path = html._local(root, manifest_path, 'input')
    if path.stat().st_size > MAX_INPUT:
        html.fail('STROKE_PLAN_BUDGET', '描线清单超过 2 MiB')
    raw = path.read_bytes()
    # Refuse duplicate keys as well as nonfinite JSON: no hidden last-key wins.
    def pairs(values):
        result = {}
        for key, value in values:
            if key in result:
                bad('JSON 字段重复', key)
            result[key] = value
        return result
    try:
        value = json.loads(raw.decode('utf-8'), object_pairs_hook=pairs, parse_constant=lambda v:bad('非有限 JSON', v))
    except (ValueError, UnicodeError, RecursionError) as exc:
        bad('无效 UTF-8 JSON: '+str(exc))
    ticks = project['settings']['timebase']['ticks_per_second']
    spec, geometry, summary = prepare(value, ticks)
    geometry.update(width=spec['width'], height=spec['height'], duration=spec['duration_tick']/ticks)
    files = {'index.html':PAGE, 'authored-plan.json':raw, 'geometry.json':html.encoded(geometry)}
    for name in ('openfilm_stroke.mjs','OPENFILM_EXAMPLES_LICENSE.txt','PDOOM_VIDEO_LICENSE.txt'):
        files[name] = Path(__file__).with_name(name).read_bytes()
    content, plan = html.pack_source(spec, files, ticks, [])
    plan['stroke'] = summary | {'engine':ENGINE, 'input_sha256':html.digest(raw)}
    return content, plan
