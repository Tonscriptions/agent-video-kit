"""Real native no-index install; isolated reorder execution and media readback."""
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


def digest(raw): return 'sha256:'+hashlib.sha256(raw).hexdigest()
def sha(path): return digest(path.read_bytes())


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n', encoding='utf-8', newline='\n')


def run(bundle, work, public, evidence):
    work.mkdir(parents=True, exist_ok=False);evidence.mkdir(parents=True, exist_ok=False)
    (evidence/'executed-generator.py').write_bytes(Path(__file__).read_bytes())
    before = frozen();smoke = json.loads((public/'verification.json').read_bytes())
    assert smoke['frozen_after'] == before and smoke['status'] == 'passed_scoped_magnetic_reorder'
    target = work/'installed';started = time.monotonic()
    env = dict(os.environ)
    env.update(TEMP=str(work), TMP=str(work), TMPDIR=str(work), PYTHONDONTWRITEBYTECODE='1')
    install = subprocess.run([sys.executable, '-I', '-B', '-X', 'utf8', str(bundle/'install.py'),
        '--bundle', str(bundle), '--target', str(target), '--manifest-sha256', sha(bundle/'manifest.json')],
        env=env, capture_output=True, timeout=180)
    (evidence/'install.stdout.json').write_bytes(install.stdout);(evidence/'install.stderr.log').write_bytes(install.stderr)
    calls, outputs = [], []

    def cli(*args):
        command = [sys.executable, '-I', '-S', '-B', '-X', 'utf8', str(target/'run.py'), *map(str, args)]
        begin = time.monotonic();result = subprocess.run(command, cwd=work, env=env, capture_output=True, timeout=360)
        index = len(calls)+1
        (evidence/f'{index:02}.stdout.json').write_bytes(result.stdout);(evidence/f'{index:02}.stderr.log').write_bytes(result.stderr)
        calls.append({'index': index, 'command': command, 'exit_code': result.returncode,
            'seconds': time.monotonic()-begin, 'stdout_sha256': digest(result.stdout), 'stderr_sha256': digest(result.stderr)})
        save(evidence/'calls.json', calls)
        assert result.returncode == 0, (index, result.stdout.decode('utf-8', 'replace'), result.stderr.decode('utf-8', 'replace'))
        print(json.dumps({'isolated_cli_call': index, 'command': list(map(str, args[:2])), 'exit_code': 0}), flush=True)
        return json.loads(result.stdout)

    def decoded(path, *, alpha=False, audio=False):
        inputs = ['-c:v', 'libvpx-vp9'] if alpha and not audio else []
        options = (['-map', '0:a:0', '-vn', '-ar', '48000', '-ac', '2', '-f', 'f32le'] if audio else
                   ['-map', '0:v:0', '-an', '-fps_mode', 'passthrough', '-pix_fmt', 'rgba' if alpha else 'rgb24', '-f', 'rawvideo'])
        result = subprocess.run(['ffmpeg', '-v', 'error', *inputs, '-i', str(path), *options, 'pipe:1'],
                                capture_output=True, timeout=180)
        assert result.returncode == 0, result.stderr
        return result.stdout

    def compare(project, name, reference, *, alpha=False):
        output = project/'renders'/name
        options = (['--container', 'webm', '--video-codec', 'libvpx-vp9', '--audio-codec', 'libopus',
                    '--pixel-format', 'yuva420p'] if alpha else
                   ['--container', 'mkv', '--audio-codec', 'pcm_f32le', '--pixel-format', 'yuv444p'])
        result = cli('render', '--project', project, '--output', output, '--crf', '0', *options, '--publish')
        picture, audio = decoded(output, alpha=alpha), decoded(output, audio=True)
        assert picture == decoded(public/reference, alpha=alpha)
        assert audio == decoded(public/reference, audio=True)
        p = json.loads((project/'project.json').read_bytes());size = p['settings']['canvas']
        width, height = size['width'], size['height'];frames = len(picture)//(width*height*(4 if alpha else 3))
        row = {'name': name, 'reference': reference, 'frames': frames, 'stereo_sample_frames': len(audio)//8,
            'output_sha256': sha(output), 'decoded_video_sha256': digest(picture), 'decoded_pcm_sha256': digest(audio),
            'decoded_video_pcm_equal_to_development': True, 'quality': result['data']['quality']}
        if alpha:
            order = list(range(30, 40))+list(range(10, 30))+list(range(40, 50))
            expected = bytes((x+7*y+19*frame) % 256 for frame in order for y in range(height) for x in range(width))
            assert picture[3::4] == expected
            row.update(independent_original_alpha_max_error=0, independent_original_alpha_sha256=digest(expected))
        outputs.append(row);shutil.copyfile(Path(result['data']['manifest']), evidence/(name+'.manifest.json'))
        return output

    try:
        assert install.returncode == 0, (install.stdout, install.stderr)
        cli('schema', 'show');capabilities = cli('capabilities')
        assert 'agent-main-track-reorder-v1' in json.dumps(capabilities)
        project = work/'reorder';cli('convert', 'import', '--input', public/'MR01-before-project.zip', '--output', project)
        cli('validate', '--project', project, '--strict-rights');cli('policy', 'audit', '--project', project)
        request = work/'reorder.json';save(request, {'action': 'reorder', 'clip_ids': ['c'], 'before_clip_id': 'a'})
        old = (project/'project.json').read_bytes()
        preview = cli('timeline', 'edit', '--project', project, '--input', request, '--dry-run')
        assert old == (project/'project.json').read_bytes()
        base = preview['data']['plan']['base_project_sha256']
        edit = ['timeline', 'edit', '--project', project, '--input', request,
                '--expected-project-sha256', base, '--idempotency-key', 'native-install-reorder']
        first = cli(*edit);new = (project/'project.json').read_bytes();replay = cli(*edit)
        assert first['operation_id'] == replay['operation_id'] and new == (project/'project.json').read_bytes()
        assert [c['id'] for c in json.loads(new)['sequences'][0]['tracks'][0]['clips']] == ['c', 'a', 'b', 'd']
        output = compare(project, 'installed-single.mkv', 'MR01.mkv')
        sid = json.loads(new)['sequences'][0]['id']
        cli('quality', 'check', '--project', project, '--input', output, '--sequence-id', sid, '--require-audio')
        archive = work/'reordered.zip';cli('convert', 'export', '--project', project, '--target-format', 'package', '--output', archive)
        restored = work/'restored';cli('convert', 'import', '--input', archive, '--output', restored)
        compare(restored, 'installed-restored.mkv', 'MR01.mkv')
        for name, reference, alpha in [('MR04', 'MR04.mkv', False), ('MR05', 'MR05.mkv', False), ('MR08', 'MR08.webm', True)]:
            project = work/name;cli('convert', 'import', '--input', public/(name+'-project.zip'), '--output', project)
            compare(project, 'installed-'+reference, reference, alpha=alpha)
        wheel = next((bundle/'wheels').glob('ai_ad_editor-*.whl'));files = {}
        with zipfile.ZipFile(wheel) as package:
            for name in package.namelist():
                if not name.startswith('ai_ad_editor/') or name.endswith('/'): continue
                installed = list(target.rglob(name));assert len(installed) == 1
                assert installed[0].read_bytes() == package.read(name) == (ROOT/'product/src'/name).read_bytes(), name
                files[name] = sha(installed[0])
        assert 'ai_ad_editor/magnetic_reorder.py' in files
        for name, source in [('agent-video-kit-cp313-win_amd64.zip', bundle.with_suffix('.zip')),
                             ('release-manifest.json', bundle/'manifest.json'), ('install-receipt.json', target/'receipt.json')]:
            shutil.copyfile(source, public/name)
        assert before == frozen()
        value = {'status': 'passed', 'native_windows': True, 'virtualization': False, 'virtual_environment': False,
            'installer_exit_code': install.returncode, 'isolated_cli_calls': len(calls), 'calls': calls,
            'installed_package_files': len(files), 'installed_files': files, 'package_bytes_equal_to_wheel_and_source': True,
            'outputs': outputs, 'actual_new_frames': sum(row['frames'] for row in outputs),
            'actual_new_stereo_sample_frames': sum(row['stereo_sample_frames'] for row in outputs),
            'frozen_before': before, 'frozen_after': frozen(), 'manifest_sha256': sha(public/'release-manifest.json'),
            'release_zip_sha256': sha(public/'agent-video-kit-cp313-win_amd64.zip'),
            'install_and_check_seconds': time.monotonic()-started, 'generator_sha256': sha(Path(__file__)),
            'new_model_forwards': 0, 'browser_invocations': 0, 'continuous_playback': False,
            'listening_review': False, 'other_machine_accepted': False}
        save(evidence/'verification.json', value)
        print(json.dumps({k: value[k] for k in ('status', 'isolated_cli_calls', 'installed_package_files', 'actual_new_frames', 'actual_new_stereo_sample_frames')}))
    except BaseException as exc:
        save(evidence/'failure.json', {'error': repr(exc), 'calls': calls, 'partials_preserved': True});raise


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    for key in ('bundle', 'work', 'public', 'evidence'): parser.add_argument('--'+key, type=Path, required=True)
    args = parser.parse_args();run(*(getattr(args, key).resolve() for key in ('bundle', 'work', 'public', 'evidence')))
