"""Authored sequence rasters, independent of the containing timeline raster."""
from __future__ import annotations

from typing import Any

from .errors import AppError


def validate_canvas(value: Any, *, path: str = 'sequence.canvas') -> None:
    if value is None:
        return
    if not isinstance(value, dict) or set(value) != {'width', 'height'}:
        raise AppError('SEQUENCE_CANVAS_INVALID', '序列 canvas 必须为 width/height 对象，或 null 以继承项目画布', exit_code=2, path=path)
    for field in ('width', 'height'):
        if type(value[field]) is not int or not 2 <= value[field] <= 8192:
            raise AppError('SEQUENCE_CANVAS_INVALID', '序列画布宽高必须为 2..8192 的整数像素', exit_code=2, path=path+'.'+field)


def sequence_canvas(project: dict[str, Any], sequence: dict[str, Any]) -> dict[str, int]:
    value = sequence.get('canvas')
    validate_canvas(value)
    if value is None:
        value = project['settings']['canvas']
    return {field: int(value[field]) for field in ('width', 'height')}


def validate_output_alignment(canvas: dict[str, int], pixel_format: str) -> None:
    """Reject impossible subsampled encodes before allocating a render job."""
    horizontal = pixel_format in {'yuv420p', 'yuv420p10le', 'yuva420p', 'yuv422p', 'yuv422p10le'}
    vertical = pixel_format in {'yuv420p', 'yuv420p10le', 'yuva420p'}
    if (horizontal and canvas['width'] % 2) or (vertical and canvas['height'] % 2):
        raise AppError('OUTPUT_CANVAS_ALIGNMENT_INVALID', '当前输出像素格式要求偶数画布尺寸；请选择兼容分辨率或 4:4:4 输出',
                       exit_code=2, path='settings.canvas', cause=f'pixel_format={pixel_format}; canvas={canvas}')
