"""Retain native alpha-mode controls against independent linear-black luma."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'product/src'))
from ai_ad_editor.runtime import configure_local_runtime
from ai_ad_editor.media import ffmpeg_path


def main():
    configure_local_runtime()
    work = ROOT/'product/.runtime/float-preview-20261022/black-r3'; work.mkdir(parents=True, exist_ok=False)
    evidence = ROOT/'docs/validation/evidence/float-preview-20261022-lab/black-r3'
    evidence.mkdir()
    calls = []
    def call(name, args, payload=None):
        command = [ffmpeg_path(), '-nostdin', '-v', 'verbose', '-filter_complex_threads', '1', *map(str, args)]
        value = subprocess.run(command, input=payload, cwd=ROOT, capture_output=True, timeout=60, creationflags=subprocess.CREATE_NO_WINDOW)
        (evidence/(name+'.stderr.log')).write_bytes(value.stderr)
        (evidence/(name+'.stdout.bin')).write_bytes(value.stdout)
        calls.append({'name': name, 'command': command, 'exit_code': value.returncode,
                      'stdout_bytes': len(value.stdout), 'stdout_sha256': hashlib.sha256(value.stdout).hexdigest(),
                      'stderr': value.stderr.decode('utf8', 'replace')[-10000:]})
        assert value.returncode == 0, (name, value.stderr[-3000:])
        return value.stdout
    planes = np.ones((4, 16, 32), '<f4'); planes[:3] = .2; planes[3] = .25
    source = work/'linear.nut'
    call('source', ['-f', 'rawvideo', '-pixel_format', 'gbrapf32le', '-video_size', '32x16', '-framerate', '10',
        '-color_range', 'pc', '-colorspace', 'rgb', '-color_primaries', 'bt709', '-color_trc', 'linear', '-i', 'pipe:0',
        '-c:v', 'rawvideo', '-pix_fmt', 'gbrapf32le', '-f', 'nut', source], planes.tobytes())
    suffix = ('format=gbrpf32le,zscale=primariesin=709:transferin=linear:matrixin=gbr:rangein=full:'
        'primaries=709:transfer=709:matrix=709:range=limited:chromal=left:dither=none,format=yuv420p')
    variants = {'original_premultiply': 'premultiply=inplace=1,',
                'premultiply_retag_straight': 'premultiply=inplace=1,setparams=alpha_mode=straight,',
                'premultiply_retag_premultiplied': 'premultiply=inplace=1,setparams=alpha_mode=premultiplied,',
                'explicit_linear_black_opaque_alpha': "geq=r='r(X,Y)*alpha(X,Y)':g='g(X,Y)*alpha(X,Y)':b='b(X,Y)*alpha(X,Y)':a=1:interpolation=nearest,setparams=alpha_mode=straight,"}
    expected = 16+219*(1.099*(.2*.25)**.45-.099)
    actual = {}
    for name, prefix in variants.items():
        raw = call(name, ['-i', source, '-vf', prefix+suffix, '-an', '-f', 'rawvideo', '-pix_fmt', 'yuv420p', 'pipe:1'])
        actual[name] = {'center_Y': raw[8*32+16], 'expected_continuous_Y': expected, 'absolute_error': abs(raw[8*32+16]-expected)}
    def oetf(channel):
        value = f'{channel}(X,Y)*alpha(X,Y)'
        return "'"+f'if(lt({value},0.018),4.5*({value}),1.099*pow({value},0.45)-0.099)' + "'"
    explicit = 'geq='+':'.join(f'{c}={oetf(c)}' for c in ('r', 'g', 'b'))+':a=1:interpolation=nearest,setparams=alpha_mode=straight,'
    unchanged = suffix.replace('transferin=linear', 'transferin=709')
    raw = call('explicit_BT709_OETF', ['-i', source, '-vf', explicit+unchanged, '-an', '-f', 'rawvideo', '-pix_fmt', 'yuv420p', 'pipe:1'])
    actual['explicit_BT709_OETF'] = {'center_Y': raw[8*32+16], 'expected_continuous_Y': expected, 'absolute_error': abs(raw[8*32+16]-expected)}
    gray = np.arange(65536, dtype=np.float32).reshape(256, 256)/65535
    grid = np.ones((4, 256, 256), '<f4'); grid[:3] = gray; grid[3] = .25
    input_grid = ['-f', 'rawvideo', '-pixel_format', 'gbrapf32le', '-video_size', '256x256', '-framerate', '10',
                  '-color_range', 'pc', '-colorspace', 'rgb', '-color_primaries', 'bt709', '-color_trc', 'linear', '-i', 'pipe:0']
    geq_only = explicit.rstrip(',')
    rgba_encoded = call('encoded_geq_float32_before_alpha_drop', [*input_grid, '-vf', geq_only,
        '-an', '-f', 'rawvideo', '-pix_fmt', 'gbrapf32le', 'pipe:1'], grid.tobytes())
    rgb_encoded = call('encoded_geq_float32_after_alpha_drop', [*input_grid, '-vf', explicit+'format=gbrpf32le',
        '-an', '-f', 'rawvideo', '-pix_fmt', 'gbrpf32le', 'pipe:1'], grid.tobytes())
    geq_values = np.frombuffer(rgba_encoded, '<f4').reshape(4, 256, 256)
    dropped_values = np.frombuffer(rgb_encoded, '<f4').reshape(3, 256, 256)
    converted = call('65536_gray_alpha_quarter_OETF_10bit', [*input_grid, '-vf',
        (explicit+unchanged).replace('format=yuv420p', 'format=yuv444p10le'),
        '-an', '-f', 'rawvideo', '-pix_fmt', 'yuv444p10le', 'pipe:1'], grid.tobytes())
    planes_out = np.frombuffer(converted, '<u2').reshape(3, 256, 256)
    light = gray.astype(np.float64)*.25
    expected_grid = 64+876*np.where(light < .018, 4.5*light, 1.099*light**.45-.099)
    grid_error = float(np.max(np.abs(planes_out[0]-expected_grid)))
    encoded_expected = (expected_grid-64)/876
    geq_error = float(np.max(np.abs(geq_values[:3]-encoded_expected)))
    alpha_drop_error = float(np.max(np.abs(dropped_values-geq_values[:3])))
    post_drop_Y_error = float(np.max(np.abs(planes_out[0]-(64+876*dropped_values[0].astype(np.float64)))))
    result = {'status': 'passed-independent-control', 'cases': actual, 'calls': calls,
        'selected': 'explicit_BT709_OETF', 'independent_65536_gray_max_Y10_error': grid_error,
        'GEQ_OETF_max_RGB_error': geq_error, 'native_float_alpha_drop_max_RGB_change': alpha_drop_error,
        'native_Y10_max_error_relative_to_actual_alpha_drop_RGB': post_drop_Y_error,
        'GEQ_distinct_gray_values': len(np.unique(geq_values[0])),
        'after_native_alpha_drop_distinct_gray_values': len(np.unique(dropped_values[0])),
        'independent_gray_chroma_neutral': bool(np.all(planes_out[1:] == 512)), 'network': False, 'virtualization': False,
        'generator_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    result['status'] = 'passed-independent-viewing-control-with-measured-native-format-precision' if actual[result['selected']]['absolute_error'] <= .51 and grid_error <= 1 and geq_error <= 3e-7 and post_drop_Y_error <= .501 and result['independent_gray_chroma_neutral'] else 'failed'
    receipt = ROOT/'docs/validation/evidence/float-preview-20261022-lab/black-r3.json'
    receipt.write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n', encoding='utf8', newline='\n')
    (evidence/'executed-script.py.txt').write_bytes(Path(__file__).read_bytes())
    print(json.dumps({k: result[k] for k in ['status', 'independent_65536_gray_max_Y10_error', 'GEQ_OETF_max_RGB_error', 'native_float_alpha_drop_max_RGB_change', 'native_Y10_max_error_relative_to_actual_alpha_drop_RGB', 'GEQ_distinct_gray_values', 'after_native_alpha_drop_distinct_gray_values']}))
    assert result['status'].startswith('passed-')


if __name__ == '__main__':
    main()
