"""Install local fixed wheels and verify transparent input/output and endpoints."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
import zipfile

from run_frozen_regression import frozen

ROOT = Path(__file__).resolve().parents[1]


def digest(raw):
    return 'sha256:'+hashlib.sha256(raw).hexdigest()


def sha(path):
    return digest(path.read_bytes())


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n', encoding='utf-8', newline='\n')


def run(bundle, work, public, evidence):
    work.mkdir(parents=True, exist_ok=False)
    evidence.mkdir(parents=True, exist_ok=False)
    (evidence/'executed-generator.py').write_bytes(Path(__file__).read_bytes())
    before = frozen()
    smoke = json.loads((public/'verification.json').read_bytes())
    assert smoke['frozen_after'] == before and smoke['status'] == 'passed_scoped_delivery_precision'
    target = work/'installed'
    env = dict(os.environ)
    env.update(TEMP=str(work), TMP=str(work), TMPDIR=str(work), PYTHONDONTWRITEBYTECODE='1')
    started = time.monotonic()
    install = subprocess.run([sys.executable, '-I', '-B', '-X', 'utf8', str(bundle/'install.py'),
        '--bundle', str(bundle), '--target', str(target), '--manifest-sha256', sha(bundle/'manifest.json')],
        env=env, capture_output=True, timeout=180)
    (evidence/'install.stdout.json').write_bytes(install.stdout)
    (evidence/'install.stderr.log').write_bytes(install.stderr)
    calls, outputs = [], []

    def cli(*args):
        command = [sys.executable, '-I', '-S', '-B', '-X', 'utf8', str(target/'run.py'), *map(str, args)]
        start = time.monotonic()
        result = subprocess.run(command, cwd=work, env=env, capture_output=True, timeout=360)
        index = len(calls)+1
        (evidence/f'{index:02}.stdout.json').write_bytes(result.stdout)
        (evidence/f'{index:02}.stderr.log').write_bytes(result.stderr)
        calls.append({'index': index, 'command': command, 'exit_code': result.returncode,
                      'seconds': time.monotonic()-start, 'stdout_sha256': digest(result.stdout),
                      'stderr_sha256': digest(result.stderr)})
        save(evidence/'calls.json', calls)
        assert result.returncode == 0, (index, result.stdout.decode('utf-8', 'replace'), result.stderr.decode('utf-8', 'replace'))
        print(json.dumps({'isolated_cli_call': index, 'command': list(map(str, args[:2])), 'exit_code': 0}), flush=True)
        return json.loads(result.stdout)

    def decoded(path, *, alpha=False, audio=False):
        input_options = ['-c:v', 'libvpx-vp9'] if alpha and not audio else []
        options = (['-map', '0:a:0', '-vn', '-ar', '48000', '-ac', '2', '-f', 'f32le'] if audio else
                   ['-map', '0:v:0', '-an', '-fps_mode', 'passthrough', '-pix_fmt', 'rgba' if alpha else 'rgb24', '-f', 'rawvideo'])
        result = subprocess.run(['ffmpeg', '-v', 'error', *input_options, '-i', str(path), *options, 'pipe:1'],
                                capture_output=True, timeout=180)
        assert result.returncode == 0, result.stderr
        return result.stdout

    def compare(project, name, reference, *, alpha=False, mkv=False):
        output = project/'renders'/name
        options = (['--container', 'webm', '--video-codec', 'libvpx-vp9', '--audio-codec', 'libopus',
                    '--pixel-format', 'yuva420p'] if alpha else
                   ['--container', 'mkv', '--audio-codec', 'pcm_f32le', '--pixel-format', 'yuv444p'] if mkv else [])
        result = cli('render', '--project', project, '--output', output, '--crf', '0', *options, '--publish')
        picture, audio = decoded(output, alpha=alpha), decoded(output, audio=True)
        expected_picture, expected_audio = decoded(public/reference, alpha=alpha), decoded(public/reference, audio=True)
        assert picture == expected_picture and audio == expected_audio
        width, height = ((256, 64) if alpha else (240, 136))
        count = len(picture)//(width*height*(4 if alpha else 3))
        row = {'name': name, 'frames': count, 'stereo_sample_frames': len(audio)//8,
               'output_sha256': sha(output), 'decoded_video_sha256': digest(picture),
               'decoded_pcm_sha256': digest(audio), 'reference': reference,
               'decoded_video_pcm_equal_to_development': True,
               'quality': result['data']['quality'], 'delivery': result['data']['delivery']}
        if alpha:
            source_frames = list(range(5))+[4]*4+list(range(5, 12))
            expected_alpha = bytes((x+7*y+19*frame) % 256
                                   for frame in source_frames for y in range(height) for x in range(width))
            assert picture[3::4] == expected_alpha
            row.update(independent_original_alpha_max_error=0,
                       independent_original_alpha_sha256=digest(expected_alpha))
        outputs.append(row)
        shutil.copyfile(Path(result['data']['manifest']), evidence/(name+'.manifest.json'))
        return output

    try:
        assert install.returncode == 0, (install.stdout, install.stderr)
        cli('schema', 'show')
        capabilities = cli('capabilities')
        assert 'authored_cfr_sample_endpoints' in json.dumps(capabilities)
        assert 'separate_original_8_bit_alpha' in json.dumps(capabilities)
        alpha_project = work/'alpha'
        cli('convert', 'import', '--input', public/'DP02-project.zip', '--output', alpha_project)
        cli('validate', '--project', alpha_project, '--strict-rights')
        cli('policy', 'audit', '--project', alpha_project)
        compare(alpha_project, 'installed-alpha.webm', 'DP02-vp9-roundtrip.webm', alpha=True)
        fractional = work/'fractional'
        cli('convert', 'import', '--input', public/'DP09-project.zip', '--output', fractional)
        cli('validate', '--project', fractional, '--strict-rights')
        output = compare(fractional, 'installed-fractional.mp4', 'DP09-fractional-mp4.mp4')
        sequence_id = json.loads((fractional/'project.json').read_bytes())['sequences'][0]['id']
        cli('quality', 'check', '--project', fractional, '--input', output, '--sequence-id', sequence_id, '--require-audio')
        archive = work/'installed-authored.zip'
        cli('convert', 'export', '--project', fractional, '--target-format', 'package', '--output', archive)
        restored = work/'restored'
        cli('convert', 'import', '--input', archive, '--output', restored)
        compare(restored, 'installed-restored.mkv', 'DP08-fractional-pcm.mkv', mkv=True)
        wheel = next((bundle/'wheels').glob('ai_ad_editor-*.whl'))
        files = {}
        with zipfile.ZipFile(wheel) as package:
            names = [name for name in package.namelist() if name.startswith('ai_ad_editor/') and not name.endswith('/')]
            for name in names:
                installed = list(target.rglob(name))
                assert len(installed) == 1 and installed[0].read_bytes() == package.read(name), name
                assert (ROOT/'product/src'/name).read_bytes() == package.read(name), name
                files[name] = sha(installed[0])
        for name, source in (('agent-video-kit-cp313-win_amd64.zip', bundle.with_suffix('.zip')),
                             ('release-manifest.json', bundle/'manifest.json'),
                             ('install-receipt.json', target/'receipt.json')):
            shutil.copyfile(source, public/name)
        assert before == frozen()
        value = {'status': 'passed', 'native_windows': True, 'virtualization': False, 'virtual_environment': False,
            'installer_exit_code': install.returncode, 'isolated_cli_calls': len(calls), 'calls': calls,
            'installed_package_files': len(files), 'installed_files': files,
            'package_bytes_equal_to_wheel_and_source': True, 'outputs': outputs,
            'actual_new_frames': sum(row['frames'] for row in outputs),
            'actual_new_stereo_sample_frames': sum(row['stereo_sample_frames'] for row in outputs),
            'frozen_before': before, 'frozen_after': frozen(),
            'manifest_sha256': sha(public/'release-manifest.json'),
            'release_zip_sha256': sha(public/'agent-video-kit-cp313-win_amd64.zip'),
            'install_and_check_seconds': time.monotonic()-started, 'generator_sha256': sha(Path(__file__)),
            'new_model_forwards': 0, 'browser_invocations': 0, 'continuous_playback': False,
            'listening_review': False, 'other_machine_accepted': False}
        save(evidence/'verification.json', value)
        print(json.dumps({key: value[key] for key in ('status', 'isolated_cli_calls', 'installed_package_files',
                                                     'actual_new_frames', 'actual_new_stereo_sample_frames')}))
    except BaseException as exc:
        save(evidence/'failure.json', {'error': repr(exc), 'calls': calls, 'partials_preserved': True})
        raise


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    for key in ('bundle', 'work', 'public', 'evidence'):
        parser.add_argument('--'+key, type=Path, required=True)
    args = parser.parse_args()
    run(*(getattr(args, key).resolve() for key in ('bundle', 'work', 'public', 'evidence')))
