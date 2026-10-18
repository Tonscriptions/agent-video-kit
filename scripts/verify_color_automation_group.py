"""Verify animated effects on repeated compound containers using the installed CLI."""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import wave
from run_frozen_regression import frozen

ROOT = Path(__file__).resolve().parents[1]

def digest(raw): return 'sha256:'+hashlib.sha256(raw).hexdigest()
def sha(path): return digest(path.read_bytes())
def read(path): return json.loads(path.read_bytes())
def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False)+'\n', encoding='utf-8', newline='\n')
def walk(rows):
    for row in rows:
        yield row
        if isinstance(row.get('inputs'), list): yield from walk(row['inputs'])

def run(work, public, evidence, installed, source):
    import numpy as np
    from PIL import Image
    for path in (work, public, evidence): path.mkdir(parents=True, exist_ok=False)
    (evidence/'executed-generator.py').write_bytes(Path(__file__).read_bytes())
    before = frozen(); assert len(before) == 186
    baseline = read(ROOT/'docs/validation/evidence/color-native-release-r3-20261019-v58/verification.json')
    assert before == baseline['frozen_after']
    env = dict(os.environ)
    env.update(TEMP=str(work), TMP=str(work), TMPDIR=str(work), PYTHONDONTWRITEBYTECODE='1',
               AI_AD_EDITOR_RUNTIME_DIR=str(work/'runtime'))
    calls, natives = [], []

    def cli(*args):
        command = [sys.executable, '-I', '-S', '-B', '-X', 'utf8', str(installed/'run.py'), *map(str, args)]
        r = subprocess.run(command, env=env, cwd=work, capture_output=True, timeout=180)
        n = len(calls)+1; out, err = evidence/f'{n:03}.stdout.json', evidence/f'{n:03}.stderr.log'
        out.write_bytes(r.stdout); err.write_bytes(r.stderr)
        calls.append({'command': command, 'exit_code': r.returncode, 'stdout_sha256': sha(out), 'stderr_sha256': sha(err)})
        save(evidence/'calls.json', calls); assert r.returncode == 0, (n, r.stdout, r.stderr)
        return json.loads(r.stdout)

    def native(*args, data=None):
        command = ['ffmpeg', '-hide_banner', '-v', 'error', '-y', *map(str, args)]
        r = subprocess.run(command, env=env, input=data, capture_output=True, timeout=180)
        natives.append({'command': command, 'exit_code': r.returncode,
            'input_sha256': digest(data) if data is not None else None,
            'stdout_sha256': digest(r.stdout), 'stderr_sha256': digest(r.stderr)})
        save(evidence/'native-calls.json', natives); assert r.returncode == 0, r.stderr
        return r.stdout

    def rgba(path):
        return native('-i', path, '-map', '0:v:0', '-an', '-fps_mode', 'passthrough', '-pix_fmt', 'rgba', '-f', 'rawvideo', 'pipe:1')

    try:
        project = work/'project'
        cli('convert', 'import', '--input', source/'CA06.aevpkg.zip', '--output', project)
        p = read(project/'project.json'); root = p['sequences'][0]
        containers = [c for t in root['tracks'] for c in t['clips'] if c.get('sequence_id')]
        assert len(containers) == 2
        effect = {'type': 'color_balance', 'parameters': {}, 'keyframes': [{'property': 'red', 'keyframes': [
            {'at_tick': 0, 'value': .1, 'interpolation': 'linear'},
            {'at_tick': 90000, 'value': .3, 'interpolation': 'linear'}]}]}
        request = work/'compose.json'
        save(request, {'operations': [{'op': 'update_clip', 'clip_id': c['id'], 'patch': {'effects': [effect]}} for c in containers]})
        cli('timeline', 'compose', '--project', project, '--input', request)
        cli('validate', '--project', project, '--strict-rights')
        master = project/'renders/CA15-group.mkv'
        result = cli('render', '--project', project, '--output', master, '--container', 'mkv', '--video-codec', 'libx264',
            '--crf', '0', '--pixel-format', 'yuv444p', '--audio-codec', 'pcm_f32le', '--publish')
        shutil.copyfile(master, public/master.name)
        shutil.copyfile(result['data']['manifest'], public/'CA15-group.manifest.json')
        cli('policy', 'audit', '--project', project)
        cli('convert', 'export', '--project', project, '--target-format', 'package', '--output', public/'CA15-group.aevpkg.zip')
        actual_raw = rgba(master); actual = np.frombuffer(actual_raw, 'u1').reshape(-1, 96, 160, 4)
        image = np.asarray(Image.open(source/'source.png').convert('RGBA')); references = []
        for i in range(10):
            t = i/10
            # An opaque child composite, an explicit RGBA boundary, then the container's own effect.
            chain = (f'colorbalance=rs={.4*t:.6f},colorbalance=bs={.2-.4*t:.6f},format=rgba,'
                     f'colorbalance=rs={.1+.2*t:.6f}')
            graph = ('[0:v]'+chain+'[fg];color=c=black:s=160x96:r=10:d=0.1[bg];'
                     '[bg][fg]overlay=format=auto[v]')
            encoded = native('-filter_threads', '1', '-filter_complex_threads', '1', '-f', 'rawvideo', '-pix_fmt', 'rgba',
                '-s', '160x96', '-r', '10', '-i', 'pipe:0', '-filter_complex', graph, '-map', '[v]', '-frames:v', 1,
                '-c:v', 'libx264', '-crf', '0', '-pix_fmt', 'yuv444p', '-color_primaries', 'bt709', '-color_trc', 'bt709',
                '-colorspace', 'bt709', '-color_range', 'tv', '-f', 'matroska', 'pipe:1', data=image.tobytes())
            decoded = native('-i', 'pipe:0', '-an', '-pix_fmt', 'rgba', '-f', 'rawvideo', 'pipe:1', data=encoded)
            references.append(np.frombuffer(decoded, 'u1').reshape(96, 160, 4))
        expected = np.stack(references*2); assert actual.shape == expected.shape == (20, 96, 160, 4)
        rgb = int(np.abs(actual[..., :3].astype('i2')-expected[..., :3].astype('i2')).max())
        alpha = int(np.abs(actual[..., 3].astype('i2')-expected[..., 3].astype('i2')).max())
        assert rgb <= 2 and alpha == 0, (rgb, alpha)
        assert np.array_equal(actual[:10], actual[10:]), 'each repeated container must reset its local author clock'
        control = np.frombuffer(rgba(source/'CA06.mkv'), 'u1').reshape(actual.shape)
        changed = int(np.abs(actual[..., :3].astype('i2')-control[..., :3].astype('i2')).max())
        assert changed > 0, 'the container effect must visibly alter the rendered child'
        audio_raw = native('-i', master, '-map', '0:a:0', '-vn', '-ar', '48000', '-ac', '2', '-f', 'f32le', 'pipe:1')
        audio = np.frombuffer(audio_raw, '<f4').reshape(-1, 2)
        with wave.open(str(source/'source.wav'), 'rb') as stream:
            expected_audio = np.frombuffer(stream.readframes(96000), '<i2').reshape(-1, 2).astype('f4')/32768
        pcm = float(np.abs(audio-expected_audio).max()); assert audio.shape == (96000, 2) and pcm <= 2e-6
        manifest = read(public/'CA15-group.manifest.json')
        commands = [r for r in walk(manifest['inputs']) if r.get('kind') == 'effect-automation']
        assert len(commands) == 6 and len({r['target'] for r in commands}) == 6
        for i, row in enumerate(commands):
            path = project/row['command_file']; assert sha(path) == row['command_file_sha256']
            shutil.copyfile(path, public/f'CA15-group-{i:02}.ffcmd')
        np.savez_compressed(public/'CA15-group-reference.npz', rgba=expected)
        native('-i', master, '-c:v', 'libx264', '-crf', '16', '-pix_fmt', 'yuv420p', '-c:a', 'aac', public/'CA15-group.mp4')
        files = {}
        for name, value in baseline['installed_files'].items():
            paths = list(installed.rglob(name)); assert len(paths) == 1
            assert sha(paths[0]) == value == sha(ROOT/'product/src'/name); files[name] = value
        assert len(files) == 124 and frozen() == before and len(calls) == 6
        record = {'status': 'passed', 'checked_at_utc': datetime.now(timezone.utc).isoformat(),
            'isolated_cli_calls': len(calls), 'frames': len(actual), 'stereo_sample_frames': len(audio),
            'runtime_instances': len(commands), 'max_rgb_error': rgb, 'max_alpha_error': alpha, 'max_pcm_error': pcm,
            'container_changes_rgb_max': changed, 'repeated_instances_exact': True, 'unique_targets': True,
            'decoded_rgba_sha256': digest(actual_raw), 'decoded_pcm_sha256': digest(audio_raw),
            'installed_files': files, 'frozen_before': before, 'frozen_after': frozen(),
            'generator_sha256': sha(Path(__file__)), 'source_package_sha256': sha(source/'CA06.aevpkg.zip'),
            'reference': 'independent static per-frame native parameters, opaque child RGBA and identical declared delivery boundary',
            'network_used': False, 'virtual_environment': False, 'full_capcut_parity': False,
            'files': {p.relative_to(public).as_posix(): {'sha256': sha(p), 'bytes': p.stat().st_size} for p in sorted(public.rglob('*')) if p.is_file()}}
        save(evidence/'verification.json', record)
        print(json.dumps({k: record[k] for k in ('status', 'isolated_cli_calls', 'frames', 'runtime_instances', 'max_rgb_error', 'container_changes_rgb_max')}))
    except BaseException as exc:
        save(evidence/'failure.json', {'error': repr(exc), 'calls': calls, 'frozen_before': before}); raise

if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    for key in ('work', 'public', 'evidence', 'installed', 'source'): p.add_argument('--'+key, type=Path, required=True)
    a = p.parse_args(); run(*(getattr(a, k).resolve() for k in ('work', 'public', 'evidence', 'installed', 'source')))
