"""Render-only authoring clocks for nested captions and title animation."""
from __future__ import annotations

import copy
from typing import Any

from .time_mapping import compose_expression


def make_clock(clip: dict[str, Any], maps: list[dict[str, Any]], tps: int,
               *, reverse: bool, approximate_freeze: bool = False) -> dict[str, Any]:
    return {
        'version': '1', 'maps': copy.deepcopy(maps),
        'authored_start_seconds': int(clip.get('timeline_start_tick', 0)) / tps,
        'authored_duration_seconds': max(1, int(clip.get('duration_tick', 1))) / tps,
        # Reverse traverses a half-open interval from its right edge. Sample
        # the preceding half tick to keep cue endpoints in the preceding cue.
        'reverse_boundary_bias_seconds': .5 / tps if reverse else 0.,
        'freeze_semantics_approximate': approximate_freeze,
        'clock': 'original-sequence-presentation-time',
    }


def clock_for_clip(clip: dict[str, Any], start: float, duration: float) -> dict[str, Any]:
    value = clip.get('_nested_subtitle_clock')
    if isinstance(value, dict):
        return value
    return {'version': '1', 'maps': [], 'authored_start_seconds': start,
            'authored_duration_seconds': duration, 'reverse_boundary_bias_seconds': 0.,
            'freeze_semantics_approximate': bool(clip.get('freeze')),
            'clock': 'original-sequence-presentation-time'}


def authored_expression(clock: dict[str, Any], variable: str = 't', *, sequential: bool = False) -> str:
    maps = clock.get('maps', [])
    value = compose_expression(maps, variable, inverse=True,
                               scratch_register=0 if sequential and maps else None)
    bias = clock.get('reverse_boundary_bias_seconds', 0.)
    return f'(({value})-{bias:.14g})' if bias else value


def restore_expression(clock: dict[str, Any], variable: str, *, clip_relative: bool) -> str:
    offset = clock.get('reverse_boundary_bias_seconds', 0.)
    if clip_relative:
        offset += clock['authored_start_seconds']
    value = f'(({variable})+{offset:.14g})' if offset else variable
    maps = clock.get('maps', [])
    return compose_expression(maps, value, scratch_register=0 if maps else None)
