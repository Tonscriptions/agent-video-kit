"""Reproduce the retained exposure-reference failure at explicit pixel/encoding boundaries."""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
from run_frozen_regression import frozen

ROOT = Path(__file__).resolve().parents[1]
def digest(raw): return 'sha256:'+hashlib.sha256(raw).hexdigest()
def sha(path): return digest(path.read_bytes())
def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n', encoding='utf-8', newline='\n')

def run(project, failed, output):
    import numpy as np
    from PIL import Image
    output.mkdir(parents=True, exist_ok=False)
    (output/'executed-generator.py').write_bytes(Path(__file__).read_bytes())
    before = frozen(); calls = []; manifest_path = failed/'CA04.manifest.json'
    manifest = json.loads(manifest_path.read_bytes()); executable = manifest['command'][0]

    def native(*args, data=None, cwd=None):
        command = [executable, '-hide_banner', '-v', 'error', '-y', *map(str, args)]
        r = subprocess.run(command, input=data, capture_output=True, timeout=120, cwd=cwd)
        calls.append({'command': command, 'cwd': str(cwd) if cwd else None,
                      'input_sha256': digest(data) if data is not None else None, 'exit_code': r.returncode,
                      'stdout_sha256': digest(r.stdout), 'stderr_sha256': digest(r.stderr)})
        save(output/'native-calls.json', calls); assert r.returncode == 0, r.stderr
        return r.stdout

    def decode(path):
        return np.frombuffer(native('-i', path, '-map', '0:v:0', '-an', '-pix_fmt', 'rgba', '-f', 'rawvideo', 'pipe:1'),
                             'u1').reshape(-1, 96, 160, 4)

    # Reuse the actual failed graph; only change its requested delivery codec to raw RGBA.
    # This is a diagnostic of that graph, not an independent renderer.
    command = manifest['command']; inputs = command[command.index('-i'):command.index('-filter_complex')]
    raw_target = output/'CA04-actual-graph-rgba.nut'
    native(*inputs, '-filter_complex', manifest['filter_complex'], '-map', '[vout]', '-map', '[aout]',
           '-t', '2', '-c:v', 'rawvideo', '-pix_fmt', 'rgba', '-c:a', 'pcm_f32le', '-f', 'nut', raw_target, cwd=project)
    actual_raw = decode(raw_target); master = decode(failed/'CA04.mkv')
    source = np.asarray(Image.open(failed/'source.png').convert('RGBA')); plain = []; encoded = []
    for frame in range(20):
        t = frame/10
        chain = f'exposure=exposure={-.5+.6*t:.6f}:black={.03-.02*t:.6f}'
        prefix = ['-filter_threads', '1', '-filter_complex_threads', '1', '-f', 'rawvideo', '-pix_fmt', 'rgba',
                  '-s', '160x96', '-r', '10', '-i', 'pipe:0']
        raw = native(*prefix, '-vf', chain, '-frames:v', '1', '-pix_fmt', 'rgba', '-f', 'rawvideo', 'pipe:1', data=source.tobytes())
        plain.append(np.frombuffer(raw, 'u1').reshape(96, 160, 4))
        graph = '[0:v]'+chain+'[fg];color=c=black:s=160x96:r=10:d=0.1[bg];[bg][fg]overlay=format=auto[v]'
        coded = native(*prefix, '-filter_complex', graph, '-map', '[v]', '-frames:v', '1', '-c:v', 'libx264',
            '-crf', '0', '-pix_fmt', 'yuv444p', '-color_primaries', 'bt709', '-color_trc', 'bt709',
            '-colorspace', 'bt709', '-color_range', 'tv', '-f', 'matroska', 'pipe:1', data=source.tobytes())
        raw = native('-i', 'pipe:0', '-an', '-pix_fmt', 'rgba', '-f', 'rawvideo', 'pipe:1', data=coded)
        encoded.append(np.frombuffer(raw, 'u1').reshape(96, 160, 4))
    plain, encoded = np.stack(plain), np.stack(encoded)
    def error(left, right): return int(np.abs(left[..., :3].astype('i2')-right[..., :3].astype('i2')).max())
    summary = {'premature_direct_RGBA_reference_to_master': error(plain, master),
               'direct_RGBA_reference_to_actual_raw_graph': error(plain, actual_raw),
               'same_composite_and_709_encoding_static_reference_to_master': error(encoded, master)}
    assert summary == {'premature_direct_RGBA_reference_to_master': 3,
        'direct_RGBA_reference_to_actual_raw_graph': 0, 'same_composite_and_709_encoding_static_reference_to_master': 0}, summary
    np.savez_compressed(output/'references.npz', direct_rgba=plain, same_delivery=encoded)
    for backend in ('colorbalance', 'exposure', 'colorlevels'):
        (output/(backend+'-help.txt')).write_bytes(native('-h', 'filter='+backend))
    assert frozen() == before
    record = {'status': 'passed_scoped_boundary_diagnosis', 'checked_at_utc': datetime.now(timezone.utc).isoformat(),
        'original_threshold': 2, 'threshold_changed': False, 'summary': summary, 'frames': len(master),
        'failed_manifest_sha256': sha(manifest_path), 'failed_master_sha256': sha(failed/'CA04.mkv'),
        'source_sha256': sha(failed/'source.png'), 'actual_raw_graph_sha256': sha(raw_target),
        'reference_sha256': sha(output/'references.npz'), 'ffmpeg_sha256': sha(Path(executable)),
        'native_calls': len(calls), 'generator_sha256': sha(Path(__file__)), 'frozen_before': before, 'frozen_after': frozen(),
        'algorithm_reference': 'same pinned FFmpeg; independent numeric/time authoring, not independent color science',
        'scope': 'actual raw graph agrees; encoded comparison must include opaque composite plus declared BT.709 delivery',
        'product_change_required': False, 'capcut_equivalence': False}
    save(output/'verification.json', record); print(json.dumps(summary))

if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    for key in ('project', 'failed', 'output'): p.add_argument('--'+key, type=Path, required=True)
    a = p.parse_args(); run(a.project.resolve(), a.failed.resolve(), a.output.resolve())
