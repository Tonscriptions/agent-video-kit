"""Pure text decoding and explicit, source-bound camera planning for OCR."""
from __future__ import annotations
import math
from .errors import AppError


def ctc_decode(indices, probabilities, characters):
    """Collapse adjacent repeats, retaining repeats separated by the blank."""
    if len(indices) != len(probabilities):
        raise ValueError('OCR_CTC_SHAPE_INVALID')
    text, scores, previous = [], [], None
    for index, probability in zip(indices, probabilities):
        if type(index) is not int or not 0 <= index < len(characters) or not math.isfinite(probability) or not 0 <= probability <= 1:
            raise ValueError('OCR_CTC_TOKEN_INVALID')
        if index and index != previous:
            text.append(characters[index]); scores.append(probability)
        previous = index
    return ''.join(text), sum(scores) / len(scores) if scores else 0.


def bounded_center(x, y, zoom):
    """Translate around canvas center, without exposing outside-source pixels."""
    if not all(math.isfinite(v) for v in (x, y, zoom)) or not 0 <= x <= 1 or not 0 <= y <= 1 or not 1 < zoom <= 4:
        raise ValueError('OCR_ANCHOR_GEOMETRY_INVALID')
    lo, hi = 1 - zoom / 2, zoom / 2
    return max(lo, min(hi, .5 + zoom * (.5 - x))), max(lo, min(hi, .5 + zoom * (.5 - y)))


def anchor_plan(report, clip, canvas, *, query, frame_index, tps, zoom, hold_seconds, return_seconds):
    def reject(code, message):
        raise AppError(code, message, exit_code=2)
    if not isinstance(query, str) or not query or len(query) > 1024 or type(frame_index) is not int:
        reject('OCR_QUERY_INVALID', '需要非空精确文字与显式源帧号')
    if not all(math.isfinite(v) for v in (zoom, hold_seconds, return_seconds)) or not 1 < zoom <= 4 or not 0 < hold_seconds <= 10 or not 0 < return_seconds <= 10:
        reject('OCR_ANCHOR_OPTIONS_INVALID', 'zoom 需 >1 且 ≤4，hold/return 需为 (0,10] 秒')
    source = report['source']
    if clip.get('asset_id') != source['asset_id'] or source['kind'] != 'video':
        reject('OCR_ANCHOR_SOURCE_MISMATCH', '文字报告必须来自当前片段的同一视频资产')
    if tuple(canvas) != (source['width'], source['height']):
        reject('OCR_ANCHOR_CANVAS_UNSUPPORTED', '首版文字锚点要求序列与源视频同尺寸')
    camera_properties = {'transform.scale', 'scale', 'transform.position.x', 'transform.position.y', 'position.x', 'position.y', 'position_x', 'position_y', 'transform.rotation', 'rotation', 'transform.anchor.x', 'transform.anchor.y', 'anchor.x', 'anchor.y'}
    if clip.get('sequence_id') or clip.get('freeze') or clip.get('reverse') or clip.get('speed_curve') or clip.get('presentation_window') is not None or abs(float(clip.get('speed', 1))-1) > 1e-9 or clip.get('crop') or clip.get('transform') or clip.get('tracking_binding') or clip.get('effects') or clip.get('mask') or clip.get('blend') or clip.get('transition_in') or clip.get('transition_out') or any(str(k.get('property', '')) in camera_properties for k in clip.get('keyframes', [])):
        reject('OCR_ANCHOR_TRANSFORM_UNSUPPORTED', '请使用无裁切/变换/相关关键帧的正向一倍速直接片段')
    frames = [f for f in report['frames'] if f['frame_index'] == frame_index]
    if len(frames) != 1:
        reject('OCR_FRAME_NOT_SCANNED', '指定源帧未在此报告中识别')
    matches = [box for box in frames[0]['boxes'] if box['text'] == query]
    if len(matches) != 1:
        reject('OCR_QUERY_AMBIGUOUS' if matches else 'OCR_QUERY_NOT_FOUND', '指定帧的精确文字必须唯一；不会按置信度暗选')
    box = matches[0]
    start = round(float(frames[0]['pts_seconds']) * tps) - int(clip.get('source_in_tick', 0))
    duration = int(clip['duration_tick'])
    hold, tail = round(hold_seconds*tps), round(return_seconds*tps)
    if start < 0 or min(hold, tail) < 1 or start + hold + tail > duration:
        reject('OCR_ANCHOR_RANGE_INVALID', '指定文字帧或回全景区间超出片段作者时长')
    x, y, width, height = box['bbox']
    cx, cy = bounded_center(x+width/2, y+height/2, zoom)
    keyframes = []
    for prop, focus, home in (('transform.position.x', cx, .5), ('transform.position.y', cy, .5), ('transform.scale', zoom, 1.)):
        points = [{'at_tick': 0, 'value': home, 'interpolation': 'hold'}] if start else []
        points.extend([
            {'at_tick': start, 'value': focus, 'interpolation': 'hold'},
            {'at_tick': start+hold, 'value': focus, 'interpolation': 'ease_out'},
            {'at_tick': start+hold+tail, 'value': home, 'interpolation': 'hold'},
        ])
        keyframes.append({'property': prop, 'keyframes': points})
    return {'query': query, 'source_frame': frame_index, 'source_box': box, 'focus_start_tick': start,
            'return_end_tick': start+hold+tail, 'zoom': zoom, 'focus_center': [cx, cy], 'keyframes': keyframes,
            'method': 'recognized-text-box-explicit-source-frame', 'automatic_click_detection': False,
            'observation_protocol': 'agent-video-ocr-text-anchor-v1',
            'warnings': ['OCR_REVIEW_REQUIRED', 'TEXT_BOX_IS_NOT_BUTTON_BOUNDS']}
