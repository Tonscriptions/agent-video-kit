"""Pause a complete authored child before the container's spatial processing.

Only detached graph data is created. The child and temporal graphs share real
FFmpeg inputs; no temporary media, pretend URI or author asset is introduced.
"""
from __future__ import annotations

import copy

from .errors import AppError
from .sequence_canvas import sequence_canvas


TIMING_FIELDS = ('source_in_tick', 'source_out_tick', 'duration_tick', 'speed',
                 'speed_curve', 'reverse', 'freeze')


def prepare(root, project, sequence, build_graph, namespace, *, stack=()):
    frozen = [(track, clip) for track in sequence.get('tracks', []) if not track.get('muted')
              for clip in track.get('clips', [])
              if clip.get('sequence_id') and clip.get('freeze')]
    if not frozen:
        return project, sequence, [], [], []
    if len(frozen) > 64 or len(stack) > 16:
        raise AppError('NESTED_FREEZE_GRAPH_LIMIT', '复合定格超过 64 个直接实例或 16 层递归配额', exit_code=2)
    detached = copy.deepcopy(project)
    target = next(s for s in detached['sequences'] if s['id'] == sequence['id'])
    sequences = {s['id']: s for s in project['sequences']}
    reserved = {str(value.get('id')) for value in project.get('assets', [])}
    for value in project['sequences']:
        reserved.add(value['id'])
        for track in value.get('tracks', []):
            reserved.add(track['id'])
            reserved.update(clip['id'] for clip in track.get('clips', []))

    def fresh(base):
        while base in reserved:
            base += '_'
        reserved.add(base)
        return base

    inputs, filters, metadata = [], [], []
    tps = project['settings']['timebase']['ticks_per_second']
    fps = project['settings']['timebase']['display_fps']
    for ordinal, (track, clip) in enumerate(frozen):
        child = sequences.get(clip['sequence_id'])
        if child is None:
            raise AppError('SEQUENCE_REFERENCE_MISSING', '复合定格的子序列不存在', exit_code=2)
        raster = sequence_canvas(project, child)
        child_project = copy.deepcopy(project)
        child_project['settings'].pop('adjustments', None)
        child_project['settings'].setdefault('output', {}).setdefault('video', {})['pixel_format'] = 'yuva420p'
        # Complete the child bus first: its nonlinear processing and automation
        # must not be re-evaluated independently on leaves during the pause.
        child_inputs, child_graph, child_meta, child_warnings = build_graph(
            root, child_project, child, _inline_stack=(*stack, sequence['id']), _allow_audio_only=True)
        internal = 'freeze_child_'
        aid = fresh(f'__freeze_asset_{sequence["id"]}_{ordinal}')
        sid = fresh(f'__freeze_sequence_{sequence["id"]}_{ordinal}')
        temporal_id = fresh(f'__freeze_temporal_{sequence["id"]}_{ordinal}')
        asset = {'id': aid, 'kind': 'video',
                 '_inline_video': {'sequence_id': child['id'], 'label': internal+'vout', 'canvas': raster},
                 '_inline_audio': {'label': internal+'aout'},
                 'probe': {'duration_seconds': child['duration_tick']/tps,
                           'video': {**raster, 'pix_fmt': 'rgba', 'fps': f'{fps["num"]}/{fps["den"]}'},
                           'audio': {'codec': 'pcm_f32le', 'channels': 2, 'sample_rate': 48000}}}
        temporal = {'id': temporal_id, 'canvas': raster, 'duration_tick': clip['duration_tick'], 'tracks': []}
        for kind in ('video', 'audio'):
            timing = {key: copy.deepcopy(clip[key]) for key in TIMING_FIELDS if key in clip}
            temporal['tracks'].append({'id': fresh(temporal_id+'_'+kind), 'kind': kind, 'order': 0,
                'clips': [{'id': fresh(temporal_id+'_'+kind+'_clip'), 'asset_id': aid,
                           'timeline_start_tick': 0, **timing}]})
        temporal_project = copy.deepcopy(child_project)
        temporal_project['assets'].append(asset)
        temporal_project['sequences'].append(temporal)
        temporal_inputs, temporal_graph, temporal_meta, temporal_warnings = build_graph(
            root, temporal_project, temporal, _inline_stack=(*stack, sequence['id']))
        if temporal_inputs:
            raise AppError('NESTED_FREEZE_GRAPH_INVALID', '内部定格只应消费已经合成的子输出', exit_code=6)
        prefix, offset = f'freeze{ordinal}_', inputs.count('-i')
        inputs.extend(child_inputs)
        combined = namespace(child_graph, internal, 0)+';'+temporal_graph
        filters.append(namespace(combined, prefix, offset))
        # The persistent container keeps its spatial/audio processing and its
        # containing sequence's animation clock. Its new source is identity;
        # all source-time operations have happened on the complete child.
        runtime_asset = copy.deepcopy(asset)
        runtime_asset['_inline_video'] = {'sequence_id': sid, 'label': prefix+'vout', 'canvas': raster}
        runtime_asset['_inline_audio'] = {'label': prefix+'aout'}
        runtime_asset['probe']['duration_seconds'] = clip['duration_tick']/tps
        detached['assets'].append(runtime_asset)
        virtual = {'id': sid, 'canvas': raster, 'duration_tick': clip['duration_tick'], 'tracks': []}
        for kind in ('video', 'audio'):
            virtual['tracks'].append({'id': fresh(sid+'_'+kind), 'kind': kind, 'order': 0,
                'clips': [{'id': fresh(sid+'_'+kind+'_clip'), 'asset_id': aid,
                           'timeline_start_tick': 0, 'duration_tick': clip['duration_tick'],
                           'source_in_tick': 0, 'source_out_tick': clip['duration_tick']}]})
        detached['sequences'].append(virtual)
        changed = next(c for t in target['tracks'] if t['id'] == track['id'] for c in t['clips'] if c['id'] == clip['id'])
        for key in ('freeze', 'speed_curve', 'reverse', 'speed'):
            changed.pop(key, None)
        changed.update(sequence_id=sid, source_in_tick=0, source_out_tick=clip['duration_tick'])
        metadata.append({'kind': 'sequence-inline-surface', 'purpose': 'nested-sequence-freeze',
            'clip_id': clip['id'], 'sequence_id': child['id'], 'runtime_sequence_id': sid, 'asset_id': aid,
            'authored_timing': {key: copy.deepcopy(clip[key]) for key in TIMING_FIELDS if key in clip},
            'native_canvas': raster, 'input_count': child_inputs.count('-i'), 'input_offset': offset,
            'video_clock': 'complete-child-retime-reverse-freeze-before-container-space',
            'audio_path': 'complete-authored-child-bus-before-freeze-and-parent-bus',
            'intermediate_files': 0, 'estimated_surface_working_bytes': raster['width']*raster['height']*16,
            'warnings': child_warnings+temporal_warnings,
            'inputs': [{'kind': 'sequence-inline-surface', 'purpose': 'nested-freeze-original-child',
                        'sequence_id': child['id'], 'native_canvas': raster, 'intermediate_files': 0,
                        'estimated_surface_working_bytes': raster['width']*raster['height']*16,
                        'inputs': child_meta}, *temporal_meta]})
    return detached, target, inputs, filters, metadata
