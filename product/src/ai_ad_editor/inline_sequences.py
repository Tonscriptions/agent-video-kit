"""Native child video surfaces, kept inside one FFmpeg graph.

Compose a transition-bearing child on its authored clock before an ancestor
retimes that picture. Audio keeps the original leaves and sequence buses, so
registered local stretch engines still see actual, hash-checked source files.
No generated asset or intermediate file is persisted in an author project.
"""
from __future__ import annotations

import copy
import json
import re

from .errors import AppError
from .sequence_canvas import sequence_canvas
from .source_transitions import compile_for_render


def graph_namespace(graph: str, prefix: str, input_offset: int) -> str:
    """Rename real pad labels, without editing quoted text or expressions."""
    output = []
    i, quoted = 0, False
    while i < len(graph):
        char = graph[i]
        if char == '\\' and i+1 < len(graph):
            output.append(graph[i:i+2]); i += 2; continue
        if char == "'":
            quoted = not quoted
        if char == '[' and not quoted:
            end = graph.find(']', i+1)
            if end < 0:
                raise AppError('SEQUENCE_INLINE_GRAPH_INVALID', '内部滤镜图标签未结束', exit_code=6)
            pad = graph[i+1:end]
            source = re.fullmatch(r'(\d+)(:[va](?::\d+)?)?', pad)
            renamed = str(int(source[1])+input_offset)+(source[2] or '') if source else prefix+pad
            output.append('['+renamed+']'); i = end+1; continue
        output.append(char); i += 1
    return ''.join(output)


def _references(sequence):
    return {c['sequence_id'] for t in sequence.get('tracks', []) for c in t.get('clips', []) if c.get('sequence_id')}


def transition_descendants(project, sequence_id):
    sequences = {s['id']:s for s in project['sequences']}
    reachable, bearing = set(), {}
    def visit(sid, stack=()):
        if sid in stack:
            raise AppError('SEQUENCE_CYCLE', '嵌套序列存在循环引用，拒绝渲染', exit_code=2, path='sequences')
        if sid not in sequences:
            raise AppError('SEQUENCE_REFERENCE_MISSING', '嵌套序列引用不存在', exit_code=2, path='sequences')
        reachable.add(sid)
        if sid in bearing:
            return bearing[sid]
        child = sequences[sid]
        flags = [visit(ref, (*stack,sid)) for ref in sorted(_references(child))]
        bearing[sid] = bool(child.get('source_transitions')) or any(flags) or any(
            c.get('presentation_window') or (c.get('sequence_id') and c.get('freeze'))
            for t in child.get('tracks', []) for c in t.get('clips', []))
        return bearing[sid]
    visit(sequence_id)
    return reachable, bearing


def prepare(root, project, sequence, build_graph, *, stack=()):
    """Plan child surfaces and compile audio handles without doing any I/O."""
    if sequence['id'] in stack:
        raise AppError('SEQUENCE_CYCLE', '嵌套序列存在循环引用，拒绝渲染', exit_code=2, path='sequences')
    # Validate the authored reference graph before creating detached instances.
    transition_descendants(project, sequence['id'])
    from .nested_freeze import prepare as prepare_freezes
    project, sequence, inputs, filters, metadata = prepare_freezes(
        root, project, sequence, build_graph, graph_namespace, stack=stack)
    reachable, bearing = transition_descendants(project, sequence['id'])
    direct = sorted(ref for ref in _references(sequence) if bearing[ref])
    if not direct:
        return project, sequence, inputs, filters, metadata
    sequences = {s['id']:s for s in project['sequences']}
    surfaces = {}
    for ordinal, sid in enumerate(direct):
        child = sequences[sid]
        def has_window(current, seen=()):
            if current in seen:
                raise AppError('SEQUENCE_CYCLE', '窗口子序列存在循环', exit_code=2)
            value = sequences[current]
            return any(c.get('presentation_window') for t in value['tracks'] for c in t['clips']) or any(
                has_window(ref, (*seen,current)) for ref in _references(value))
        def has_freeze(current, seen=()):
            if current in seen:
                raise AppError('SEQUENCE_CYCLE', '定格子序列存在循环', exit_code=2)
            value = sequences[current]
            return any(c.get('sequence_id') and c.get('freeze') for t in value['tracks'] for c in t['clips']) or any(
                has_freeze(ref, (*seen, current)) for ref in _references(value))
        complete_audio = has_window(sid) or has_freeze(sid)
        # Adjustments are selected-root controls, not authored child effects.
        child_project = {**project,'settings':copy.deepcopy(project['settings'])}
        child_project['settings'].pop('adjustments', None)
        output = child_project['settings'].get('output')
        output = output if isinstance(output, dict) else {}
        video = output.get('video')
        output['video'] = {**(video if isinstance(video, dict) else {}),'pixel_format':'yuva420p'}
        child_project['settings']['output'] = output
        child_inputs, graph, child_meta, warnings = build_graph(
            root, child_project, child, _video_only=not complete_audio, _inline_stack=(*stack,sequence['id']))
        prefix, offset = f'inline{ordinal}_', inputs.count('-i')
        inputs.extend(child_inputs)
        filters.append(graph_namespace(graph, prefix, offset))
        if not complete_audio:
            filters.append(f'[{prefix}aout]anullsink')
        raster = sequence_canvas(project, child)
        aid = f'__inline_video_{sid}'
        while any(a['id']==aid for a in project.get('assets', [])) or aid in surfaces:
            aid += '_'
        surfaces[aid] = {'sequence_id':sid,'label':prefix+'vout','canvas':raster,
                         'audio_label':prefix+'aout' if complete_audio else None}
        metadata.append({'kind':'sequence-inline-surface','sequence_id':sid,'asset_id':aid,
                         'input_offset':offset,'input_count':len(child_inputs) and child_inputs.count('-i'),
                         'filter_namespace':prefix,'native_canvas':raster,'inputs':child_meta,'warnings':warnings,
                         'video_clock':'child-authored-composite-before-ancestor-time-map',
                         'audio_path':'complete-authored-child-bus' if complete_audio else 'original-source-leaves-and-authored-buses',
                         'intermediate_files':0,'estimated_surface_working_bytes':raster['width']*raster['height']*16})
    detached = copy.deepcopy(project)
    # Native audio envelopes remain on original files. Compile all reachable
    # descendants once; the selected root was compiled by its caller already.
    for sid in sorted(reachable-{sequence['id']}):
        child = next(s for s in detached['sequences'] if s['id']==sid)
        if child.get('source_transitions'):
            detached, child, _ = compile_for_render(detached, sid)
            child.pop('source_transitions', None)
    tps = project['settings']['timebase']['ticks_per_second']
    fps = project['settings']['timebase'].get('display_fps', {'num':30,'den':1})
    for aid,surface in surfaces.items():
        child = next(s for s in detached['sequences'] if s['id']==surface['sequence_id'])
        asset = {'id':aid,'kind':'video','_inline_video':surface,
            'probe':{'duration_seconds':child['duration_tick']/tps,
                     'video':{**surface['canvas'],'pix_fmt':'rgba','fps':f'{fps["num"]}/{fps["den"]}'}}}
        if surface.get('audio_label'):
            asset['_inline_audio'] = {'label':surface['audio_label']}
            asset['probe']['audio'] = {'codec':'pcm_f32le','channels':2,'sample_rate':48000}
            child['tracks'] = [{'id':f'{aid}_{kind}_track','kind':kind,'order':0,'clips':[
                {'id':f'{aid}_{kind}_clip','asset_id':aid,'timeline_start_tick':0,
                 'duration_tick':child['duration_tick'],'source_in_tick':0,'source_out_tick':child['duration_tick']}]} for kind in ('video','audio')]
            child.pop('source_transitions', None)
        else:
            child['_inline_video_asset_id'] = aid
        detached['assets'].append(asset)
    return detached, next(s for s in detached['sequences'] if s['id']==sequence['id']), inputs, filters, metadata


def budget(metadata, root_projection, config):
    def charge(items):
        total = 0
        for item in items:
            if item.get('kind') == 'sequence-projection-budget':
                total += item['estimated_working_bytes']
            elif item.get('kind') == 'sequence-inline-surface':
                total += item['estimated_surface_working_bytes']+charge(item['inputs'])
        return total
    estimated = root_projection['estimated_working_bytes']+charge(metadata)
    result = {'kind':'sequence-inline-budget','estimated_working_bytes':estimated,
              'max_working_bytes':config['max_working_bytes'],
              'scope':'reachable-inline-surfaces-and-sequence-projection-not-process-rss',
              'intermediate_files':0,'time_disjoint_instances_charged':True}
    if estimated > config['max_working_bytes']:
        raise AppError('SEQUENCE_INLINE_BUDGET_EXCEEDED', '嵌套转场合成与投影工作栅格超过显式配额',
                       exit_code=2,path='settings.sequence_sampling.max_working_bytes',cause=json.dumps(result))
    return result
