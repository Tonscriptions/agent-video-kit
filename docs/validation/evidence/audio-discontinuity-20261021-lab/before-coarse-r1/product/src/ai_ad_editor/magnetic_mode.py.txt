"""Persistent, gapless main-track semantics over existing native edit plans."""
from __future__ import annotations

import copy

from .edit_planner import (_error, _integer, _merge, _plan_changes, normalize_request,
                           project_fingerprint, validate_editing)

ENGINE = 'agent-magnetic-mode-v1'


def main_track(sequence):
    tid = validate_editing(sequence)['main_track_id']
    return next((t for t in sequence['tracks'] if t['id'] == tid), None)


def enabled(sequence):
    value = sequence.get('editing')
    return isinstance(value, dict) and value.get('magnetic') is True


def validate(sequence):
    if not enabled(sequence):
        return
    track = main_track(sequence)
    if track is None:
        _error('EDIT_MAIN_TRACK_REQUIRED', '磁吸模式需要 video 主轨')
    if not isinstance(track.get('clips'), list) or any(not isinstance(c, dict) or
            type(c.get('timeline_start_tick')) is not int or c['timeline_start_tick'] < 0 or
            type(c.get('duration_tick')) is not int or c['duration_tick'] <= 0 for c in track['clips']):
        _error('EDIT_MAGNETIC_MAIN_GAP_OR_OVERLAP', '磁吸主轨片段必须使用非负整数起点和正整数时长')
    cursor = 0
    for c in sorted(track['clips'], key=lambda c: (c['timeline_start_tick'], str(c.get('id', '')))):
        if c['timeline_start_tick'] != cursor:
            _error('EDIT_MAGNETIC_MAIN_GAP_OR_OVERLAP', '磁吸主轨必须从零紧邻排列；使用 magnet/shift/insert/extract/trim 规划几何变化')
        cursor += c['duration_tick']


def boundary(sequence, at, excluded=()):
    _integer(at, 'edit.at_tick', 0)
    track = main_track(sequence)
    if track is None:
        _error('EDIT_MAIN_TRACK_REQUIRED', '磁吸编辑需要 video 主轨')
    ordered = sorted((c for c in track['clips'] if c['id'] not in excluded),
                     key=lambda c: (c['timeline_start_tick'], c['id']))
    points = []
    for i, c in enumerate(ordered):
        points.extend([(c['timeline_start_tick'], c['id']),
                       (c['timeline_start_tick']+c['duration_tick'], ordered[i+1]['id'] if i+1<len(ordered) else None)])
    tick, before = min(points or [(0, None)], key=lambda v: (abs(v[0]-at), v[0], v[1] or ''))
    return tick, before


def options(sequence):
    return {k: v for k, v in validate_editing(sequence).items() if k in {'sync', 'linkage', 'linked'}}


def summary(before, after, sequence_id, request, steps):
    old = next(s for s in before['sequences'] if s['id'] == sequence_id)
    new = next(s for s in after['sequences'] if s['id'] == sequence_id)
    return {'engine': ENGINE, 'base_project_sha256': project_fingerprint(before), 'sequence_id': sequence_id,
            'request': copy.deepcopy(request), 'main_track_id': validate_editing(new)['main_track_id'],
            'short_tick': 0, 'steps': steps, 'changes': _plan_changes(old, new),
            'before_duration_tick': old['duration_tick'], 'after_duration_tick': new['duration_tick'],
            'magnetic': enabled(new), 'warnings': [w for p in steps for w in p.get('warnings', [])],
            'limits': ['logical-tick-boundaries-not-screen-pixel-snapping', 'markers-and-bus-automation-remain-absolute',
                       'author-speed-curve-freeze-changes-need-explicit-follow-plans',
                       'existing-range-transition-tracking-and-nonlinear-lane-boundaries-remain']}


def maybe_plan(project, sequence_id, request):
    if not isinstance(request, dict):
        return None
    sequence = next((s for s in project['sequences'] if s['id'] == sequence_id), None)
    if sequence is None:
        return None
    action = request.get('action')
    if action == 'magnet':
        if set(request) != {'action', 'enabled'} or type(request['enabled']) is not bool:
            _error('EDIT_REQUEST_INVALID', 'magnet 只接受 action 与布尔 enabled')
        candidate = copy.deepcopy(project)
        target = next(s for s in candidate['sequences'] if s['id'] == sequence_id)
        target['editing'] = {**(target.get('editing') or {}), 'magnetic': request['enabled']}
        steps = []
        if request['enabled']:
            main = main_track(target)
            if main is None:
                _error('EDIT_MAIN_TRACK_REQUIRED', '磁吸模式需要 video 主轨')
            ordered = sorted(main['clips'], key=lambda c: (c['timeline_start_tick'], c['id']))
            cursor, gap = 0, False
            for c in ordered:
                if c['timeline_start_tick'] < cursor:
                    _error('EDIT_REORDER_MAIN_OVERLAP', '开启磁吸不裁切原有主轨重叠')
                gap |= c['timeline_start_tick'] != cursor
                cursor = c['timeline_start_tick']+c['duration_tick']
            if ordered and gap:
                from .magnetic_reorder import build_reorder_plan
                candidate, step = build_reorder_plan(candidate, sequence_id,
                    {'action': 'reorder', 'clip_ids': [ordered[-1]['id']], 'before_clip_id': None})
                steps.append(step)
            validate(next(s for s in candidate['sequences'] if s['id'] == sequence_id))
        return candidate, summary(project, candidate, sequence_id, request, steps)
    if not enabled(sequence) or action not in {'shift', 'remove'}:
        return None
    query = normalize_request(sequence, request)
    main = main_track(sequence)
    main_ids = {c['id'] for c in main['clips']}
    chosen = set(query['clip_ids'])
    if not chosen & main_ids:
        return None
    if chosen-main_ids:
        _error('EDIT_MAGNETIC_MIXED_SELECTION', '磁吸主轨移动/删除不接受混合主副轨选择；关联成员由规划器扩展')
    if query['options']['linked']:
        links = {c.get('link_id') for c in main['clips'] if c['id'] in chosen}-{None}
        chosen.update(c['id'] for c in main['clips'] if c.get('link_id') in links)
    opts = {k: query['options'][k] for k in ('sync', 'linkage', 'linked')}
    if action == 'shift':
        at = min(c['timeline_start_tick'] for c in main['clips'] if c['id'] in chosen)+query['delta_tick']
        tick, anchor = boundary(sequence, at, chosen)
        from .magnetic_reorder import build_reorder_plan
        candidate, step = build_reorder_plan(project, sequence_id,
            {'action': 'reorder', 'clip_ids': sorted(chosen), 'before_clip_id': anchor, 'options': opts})
        plan = summary(project, candidate, sequence_id, query, [step])
        plan.update(requested_tick=at, snapped_tick=tick, before_clip_id=anchor)
        return candidate, plan
    from .range_edits import build_range_plan
    spans = _merge([(c['timeline_start_tick'], c['timeline_start_tick']+c['duration_tick']) for c in main['clips'] if c['id'] in chosen])
    candidate, steps = project, []
    for first, last in reversed(spans):
        candidate, step = build_range_plan(candidate, sequence_id, {'action': 'extract', 'at_tick': first,
            'duration_tick': last-first, 'track_ids': [main['id']], 'options': opts})
        steps.append(step)
    validate(next(s for s in candidate['sequences'] if s['id'] == sequence_id))
    return candidate, summary(project, candidate, sequence_id, query, steps)


def insert(project, sequence_id, track, clip, at):
    sequence = next(s for s in project['sequences'] if s['id'] == sequence_id)
    tick, _ = boundary(sequence, at)
    incoming = copy.deepcopy(clip)
    incoming['timeline_start_tick'] = 0
    from .range_edits import build_range_plan
    candidate, plan = build_range_plan(project, sequence_id, {'action': 'insert', 'at_tick': tick,
        'items': [{'track_id': track['id'], 'clip': incoming}], 'options': options(sequence)})
    plan.update(magnetic=True, requested_tick=at, snapped_tick=tick)
    return candidate, plan


def trim(project, sequence_id, track, clip, change):
    allowed = {'op', 'sequence_id', 'track_id', 'clip_id', 'id', 'start_tick', 'end_tick', 'timeline_start_tick'}
    if set(change)-allowed or 'timeline_start_tick' in change:
        _error('EDIT_REQUEST_INVALID', '磁吸 trim 使用可见 start_tick/end_tick；落点另作 shift')
    first = _integer(change.get('start_tick', 0), 'start_tick', 0)
    last = _integer(change.get('end_tick', clip['duration_tick']), 'end_tick', 1)
    if not first < last <= clip['duration_tick']:
        _error('EDIT_REQUEST_INVALID', '磁吸 trim 范围必须在当前可见窗口内且非空')
    sequence = next(s for s in project['sequences'] if s['id'] == sequence_id)
    from .range_edits import build_range_plan
    candidate, steps = project, []
    for a, b in [(last, clip['duration_tick']), (0, first)]:
        if b > a:
            candidate, step = build_range_plan(candidate, sequence_id, {'action': 'extract',
                'at_tick': clip['timeline_start_tick']+a, 'duration_tick': b-a,
                'track_ids': [track['id']], 'options': options(sequence)})
            steps.append(step)
    return candidate, summary(project, candidate, sequence_id, change, steps)
