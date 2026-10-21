"""Editable eight-band HSL in encoded RGB, evaluated by local FFmpeg geq.

Every pixel expression initializes every register before reading it. No
cross-pixel/frame state, LUT interpolation, provider or Python video worker is
involved. Original hue determines all band weights simultaneously.
"""
from __future__ import annotations

import hashlib
from typing import Any, Callable

from .errors import AppError

ENGINE = 'encoded-rgb-eight-band-hsl-v1'
ALIASES = ('selective_hsl', 'hsl_bands', 'eight_band_hsl')
BANDS = {'red': 0, 'orange': 30, 'yellow': 60, 'green': 120,
         'cyan': 180, 'blue': 240, 'purple': 270, 'magenta': 300}
SPECS = {f'{band}_{axis}': ((f'{band}_{axis}',), 0.,
                           -180. if axis == 'hue' else -1.,
                           180. if axis == 'hue' else 1., ())
         for band in BANDS for axis in ('hue', 'saturation', 'lightness')}
SPECS['intensity'] = (('intensity',), 1., 0., 1., ())
MAX_KERNEL_BYTES = 64*1024


def matches(name: Any) -> bool:
    return str(name).strip().lower().replace('-', '_') in ALIASES


def validate(effect: dict, *, duration_tick: int | None = None) -> list[dict[str, str]]:
    from .effect_automation import _finite_number, normalized_tracks, validate_tracks
    if effect.get('enabled', True) is False:
        return []
    params = effect.get('parameters', effect)
    errors = []
    def fail(code, message, suffix):
        errors.append({'code': code, 'message': message, 'suffix': suffix})
    if not isinstance(params, dict):
        fail('SELECTIVE_HSL_PARAMETERS_INVALID', '分色 HSL parameters 必须是对象', '.parameters')
        return errors
    metadata = {'type', 'enabled', 'id', 'keyframes'} if params is effect else {'keyframes'}
    for name, value in params.items():
        if name in metadata:
            continue
        suffix = ('.parameters.' if params is not effect else '.')+name
        if name not in SPECS:
            fail('SELECTIVE_HSL_PARAMETER_UNSUPPORTED', '未知的分色 HSL 参数', suffix)
        elif not _finite_number(value) or not SPECS[name][2] <= value <= SPECS[name][3]:
            fail('SELECTIVE_HSL_VALUE_INVALID', '分色 HSL 参数必须是范围内的有限数字', suffix)
    raw = effect.get('keyframes', params.get('keyframes'))
    if raw is not None and not isinstance(raw, list):
        fail('EFFECT_AUTOMATION_KEYFRAMES_INVALID', '关键帧轨道必须是数组', '.keyframes')
    elif isinstance(raw, list) and any(not isinstance(item, dict) for item in raw):
        fail('EFFECT_AUTOMATION_KEYFRAMES_INVALID', '关键帧轨道必须是对象', '.keyframes')
    errors.extend(validate_tracks(normalized_tracks(effect), SPECS, duration_tick=duration_tick))
    return errors


def _weight(band: str) -> str:
    """Circular triangular partition, including unequal orange/purple sectors."""
    centers = list(BANDS.values())
    index = list(BANDS).index(band)
    center = centers[index]
    left = (center-centers[index-1]) % 360
    right = (centers[(index+1) % len(centers)]-center) % 360
    distance = f'mod(ld(7)-{center}+360,360)'
    # ld(6) is the original saturation until all three deltas are stored.
    return (f'if(gt(ld(6),0),if(lte({distance},{right}),1-({distance})/{right},'
            f'if(gte({distance},{360-left}),(({distance})-{360-left})/{left},0)),0)')


def compile_filter(effect: dict, expression: Callable[[tuple[str, ...], float], str]) -> tuple[str, dict]:
    """Compile static values and authored curves through the same RGB kernel."""
    from .effect_automation import normalized_tracks
    findings = validate(effect)
    if findings:
        raise AppError(findings[0]['code'], findings[0]['message'], exit_code=2, cause=str(findings))
    params = effect.get('parameters', effect)
    tracks = {track['property'] for track in normalized_tracks(effect)}
    values = {name: float(params.get(name, spec[1])) for name, spec in SPECS.items()}
    bypass = (not any(name != 'intensity' for name in tracks) and
              not any(value for name, value in values.items() if name != 'intensity'))
    bypass |= values['intensity'] == 0 and 'intensity' not in tracks
    metadata = {'kind': 'selective-hsl', 'engine': ENGINE,
                'bands_degrees': dict(BANDS), 'parameters': values,
                'animated_parameters': sorted(tracks), 'color_space': 'encoded-RGB-8-bit',
                'band_selection': 'original-hue-circular-triangular-partition',
                'achromatic_policy': 'unchanged', 'alpha': 'exact-input-alpha',
                'rounding': 'nearest-8-bit-after-final-RGB-intensity-mix',
                'bypass': bool(bypass), 'natural_quality_accepted': False,
                'full_capcut_parity': False}
    if bypass:
        return '', {**metadata, 'kernel_bytes': 0, 'kernel_sha256': 'sha256:'+hashlib.sha256(b'').hexdigest()}

    def parameter(name):
        import re
        # Existing author-clock expressions use t; geq exposes frame time T.
        raw = expression((name,), values[name]) if name in tracks else f'{values[name]:.8f}'
        raw = re.sub(r"\bt\b", "T", raw)
        return f'clip({raw},{SPECS[name][2]:g},{SPECS[name][3]:g})'

    def delta(axis):
        terms = [f'({_weight(band)})*({parameter(band+"_"+axis)})'
                 for band in BANDS if values[band+'_'+axis] != 0 or band+'_'+axis in tracks]
        return '+'.join(terms) or '0'

    # Registers 0..2 retain original RGB. Registers 3/4 initially hold max/delta;
    # later they hold hue/saturation shifts, then final chroma/X. Register 5 is
    # lightness, 6 saturation, 7 hue, 8 lightness shift then final RGB offset.
    initialization = (
        'st(0,r(X,Y)/255);st(1,g(X,Y)/255);st(2,b(X,Y)/255);'
        'st(3,max(ld(0),max(ld(1),ld(2))));'
        'st(4,min(ld(0),min(ld(1),ld(2))));'
        'st(5,(ld(3)+ld(4))/2);st(4,ld(3)-ld(4));'
        'st(6,if(gt(ld(4),0),ld(4)/max(1e-12,1-abs(2*ld(5)-1)),0));'
        'st(7,if(gt(ld(4),0),60*if(eq(ld(3),ld(0)),'
        'mod((ld(1)-ld(2))/max(ld(4),1e-12)+6,6),'
        'if(eq(ld(3),ld(1)),(ld(2)-ld(0))/max(ld(4),1e-12)+2,'
        '(ld(0)-ld(1))/max(ld(4),1e-12)+4)),0));')
    changes = (f'st(3,{delta("hue")});st(4,{delta("saturation")});st(8,{delta("lightness")});'
        'st(6,clip(if(gte(ld(4),0),ld(6)+(1-ld(6))*ld(4),ld(6)*(1+ld(4))),0,1));'
        'st(5,clip(if(gte(ld(8),0),ld(5)+(1-ld(5))*ld(8),ld(5)*(1+ld(8))),0,1));'
        'st(7,mod(ld(7)+ld(3)+360,360)/60);'
        'st(3,(1-abs(2*ld(5)-1))*ld(6));'
        'st(4,ld(3)*(1-abs(mod(ld(7),2)-1)));st(8,ld(5)-ld(3)/2);')
    rgb = ('if(lt(ld(7),1),ld(3),if(lt(ld(7),2),ld(4),if(lt(ld(7),4),0,if(lt(ld(7),5),ld(4),ld(3)))))',
           'if(lt(ld(7),1),ld(4),if(lt(ld(7),3),ld(3),if(lt(ld(7),4),ld(4),0)))',
           'if(lt(ld(7),2),0,if(lt(ld(7),3),ld(4),if(lt(ld(7),5),ld(3),ld(4))))')
    intensity = parameter('intensity')
    planes = []
    for index, (channel, component) in enumerate(zip('rgb', rgb)):
        final = f'floor(clip(255*(ld({index})+(({component})+ld(8)-ld({index}))*({intensity})),0,255)+0.5)'
        planes.append(f"{channel}='{initialization}{changes}{final}'")
    kernel = 'format=gbrap,geq='+':'.join(planes)+":a='alpha(X,Y)':interpolation=nearest"
    size = len(kernel.encode('utf8'))
    if size > MAX_KERNEL_BYTES:
        raise AppError('SELECTIVE_HSL_BUDGET', '分色 HSL 单实例表达式超过 64 KiB', exit_code=2)
    return kernel, {**metadata, 'kernel_bytes': size,
                    'kernel_sha256': 'sha256:'+hashlib.sha256(kernel.encode('utf8')).hexdigest()}
