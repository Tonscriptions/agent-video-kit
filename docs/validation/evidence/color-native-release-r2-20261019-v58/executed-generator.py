"""Install fixed wheels; replay color packages and edits in isolated native processes."""
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
import zipfile
from run_frozen_regression import frozen

ROOT = Path(__file__).resolve().parents[1]

def digest(raw): return 'sha256:'+hashlib.sha256(raw).hexdigest()
def sha(path): return digest(path.read_bytes())
def read(path): return json.loads(path.read_bytes())
def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n', encoding='utf-8', newline='\n')


def run(bundle, work, public, evidence):
    import numpy as np
    work.mkdir(parents=True, exist_ok=False); evidence.mkdir(parents=True, exist_ok=False)
    (evidence/'executed-generator.py').write_bytes(Path(__file__).read_bytes())
    before = frozen(); smoke = read(public/'verification.json')
    assert before == smoke['frozen_after']; calls = []; outputs = []; native_calls = []
    env = dict(os.environ)
    env.update(TEMP=str(work), TMP=str(work), TMPDIR=str(work), PYTHONDONTWRITEBYTECODE='1',
               AI_AD_EDITOR_RUNTIME_DIR=str(work/'runtime'))
    target = work/'installed'
    install_command = [sys.executable, '-I', '-B', '-X', 'utf8', str(bundle/'install.py'),
        '--bundle', str(bundle), '--target', str(target), '--manifest-sha256', sha(bundle/'manifest.json')]
    done = subprocess.run(install_command, env=env, capture_output=True, timeout=180)
    (evidence/'install.stdout.json').write_bytes(done.stdout); (evidence/'install.stderr.log').write_bytes(done.stderr)

    def cli(*args, expected=0):
        cmd = [sys.executable, '-I', '-S', '-B', '-X', 'utf8', str(target/'run.py'), *map(str, args)]
        r = subprocess.run(cmd, cwd=work, env=env, capture_output=True, timeout=180); i = len(calls)+1
        out, err = evidence/f'{i:03}.stdout.json', evidence/f'{i:03}.stderr.log'
        out.write_bytes(r.stdout); err.write_bytes(r.stderr)
        calls.append({'index': i, 'command': cmd, 'exit_code': r.returncode, 'expected_exit_code': expected,
                      'stdout_sha256': sha(out), 'stderr_sha256': sha(err)})
        save(evidence/'calls.json', calls)
        assert r.returncode == expected, (i, r.stdout, r.stderr)
        return json.loads(r.stdout)

    def decode(path, kind, alpha=False):
        prefix = ['-c:v', 'libvpx-vp9'] if alpha and kind == 'v' else []
        cmd = ['ffmpeg', '-v', 'error', *prefix, '-i', str(path), '-map', '0:'+kind+':0']
        cmd += ['-an', '-fps_mode', 'passthrough', '-pix_fmt', 'rgba', '-f', 'rawvideo'] if kind == 'v' else [
            '-vn', '-ar', '48000', '-ac', '2', '-f', 'f32le']
        cmd += ['pipe:1']; r = subprocess.run(cmd, env=env, capture_output=True, check=True, timeout=120)
        native_calls.append({'command': cmd, 'input_file_sha256': sha(path), 'stdout_sha256': digest(r.stdout),
                             'stderr_sha256': digest(r.stderr), 'exit_code': r.returncode})
        save(evidence/'native-calls.json', native_calls); return r.stdout

    def args(project, output, alpha=False):
        return ['render', '--project', project, '--output', output, '--container', 'webm' if alpha else 'mkv',
            '--video-codec', 'libvpx-vp9' if alpha else 'libx264', '--crf', '0',
            '--pixel-format', 'yuva420p' if alpha else 'yuv444p',
            '--audio-codec', 'libopus' if alpha else 'pcm_f32le', '--publish']

    def compare(project, name, reference, exact=True):
        alpha = reference.endswith('.webm'); output = project/'renders'/(name+('.webm' if alpha else '.mkv'))
        result = cli(*args(project, output, alpha)); shutil.copyfile(result['data']['manifest'], evidence/(name+'.manifest.json'))
        video, audio = decode(output, 'v', alpha), decode(output, 'a')
        rv, ra = decode(public/reference, 'v', alpha), decode(public/reference, 'a')
        assert len(video) == len(rv) and len(audio) == len(ra)
        rgba = np.frombuffer(video, 'u1').reshape(-1, 96, 160, 4).astype('i2')
        ref = np.frombuffer(rv, 'u1').reshape(-1, 96, 160, 4).astype('i2')
        rgb = int(np.abs(rgba[..., :3]-ref[..., :3]).max()); ae = int(np.abs(rgba[..., 3]-ref[..., 3]).max())
        pcm = float(np.abs(np.frombuffer(audio, '<f4')-np.frombuffer(ra, '<f4')).max())
        if exact: assert video == rv and audio == ra
        else: assert rgb <= 2 and ae == 0 and pcm <= 2e-6
        outputs.append({'name': name, 'reference': reference, 'frames': len(rgba), 'stereo_sample_frames': len(audio)//8,
            'max_rgb_error': rgb, 'max_alpha_error': ae, 'max_pcm_error': pcm, 'exact': exact,
            'output_sha256': sha(output), 'decoded_rgba_sha256': digest(video), 'decoded_pcm_sha256': digest(audio)})

    try:
        assert done.returncode == 0, (done.stdout, done.stderr)
        cli('schema', 'show'); caps = cli('capabilities')
        assert caps['data']['capabilities']['effects']['numeric_color_automation']['numeric_channels'] == 19
        catalog = cli('effects', 'list'); assert '0.5.0' in json.dumps(catalog)
        for row in smoke['cases']:
            name = row['name']; project = work/name
            cli('convert', 'import', '--input', public/(name+'.aevpkg.zip'), '--output', project)
            cli('validate', '--project', project, '--strict-rights'); compare(project, name, row['output'])
            cli('policy', 'audit', '--project', project)
        q = work/'edit.json'; project = work/'CA02'
        original = (project/'project.json').read_bytes()
        e = read(work/'CA01/project.json')['sequences'][0]['tracks'][0]['clips'][0]['effects']
        save(q, {'operations': [{'op': 'update_clip', 'clip_id': 'color_clip', 'patch': {'effects': e}}]})
        command = ['timeline', 'compose', '--project', project, '--input', q, '--idempotency-key', 'native-v58-color']
        first = cli(*command); changed = (project/'project.json').read_bytes(); assert changed != original
        second = cli(*command)
        assert first['operation_id'] == second['operation_id'] and (project/'project.json').read_bytes() == changed
        compare(project, 'installed-parameter-edit', 'CA01.mkv')
        previous = (project/'project.json').read_bytes()
        bad = json.loads(json.dumps(e)); bad[0]['keyframes'][0]['property'] = 'unknown_native_option'
        save(q, {'operations': [{'op': 'update_clip', 'clip_id': 'color_clip', 'patch': {'effects': bad}}]})
        invalid = cli('timeline', 'compose', '--project', project, '--input', q, expected=2)
        assert 'EFFECT_AUTOMATION_PROPERTY_UNSUPPORTED' in json.dumps(invalid)
        assert (project/'project.json').read_bytes() == previous
        negative = {'unknown_property_exit': 2, 'actual_error_code_present': True, 'project_bytes_unchanged': True}
        project = work/'CA01'; commands = sorted((project/'cache/effect-automation').glob('*.ffcmd'))
        assert commands; cache = commands[0]; original_cache = cache.read_bytes(); previous = (project/'project.json').read_bytes()
        try:
            cache.write_bytes(original_cache+b'# altered\n')
            invalid = cli(*args(project, project/'renders/tampered.mkv'), '--dry-run', expected=6)
            assert 'EFFECT_AUTOMATION_CACHE_HASH_MISMATCH' in json.dumps(invalid)
            assert not (project/'renders/tampered.mkv').exists() and (project/'project.json').read_bytes() == previous
        finally: cache.write_bytes(original_cache)
        cli(*args(project, project/'renders/restored.mkv'), '--dry-run')
        negative.update(cache_tamper_exit=6, cache_restored=True, formal_media_not_started=True)
        installed = {}; wheel = next((bundle/'wheels').glob('ai_ad_editor-*.whl'))
        with zipfile.ZipFile(wheel) as z:
            for name in z.namelist():
                if not name.startswith('ai_ad_editor/') or name.endswith('/'): continue
                files = list(target.rglob(name)); assert len(files) == 1
                assert files[0].read_bytes() == z.read(name) == (ROOT/'product/src'/name).read_bytes()
                installed[name] = sha(files[0])
        assert len(installed) == 124 and frozen() == before
        for name, source in [('agent-video-kit-cp313-win_amd64.zip', bundle.with_suffix('.zip')),
            ('release-manifest.json', bundle/'manifest.json'), ('install-receipt.json', target/'receipt.json')]:
            shutil.copyfile(source, public/name)
        record = {'status': 'passed', 'checked_at_utc': datetime.now(timezone.utc).isoformat(),
            'installer_exit_code': done.returncode, 'install_command': install_command,
            'isolated_cli_calls': len(calls), 'calls': calls, 'native_calls': len(native_calls), 'outputs': outputs,
            'installed_package_files': len(installed), 'installed_files': installed,
            'frozen_before': before, 'frozen_after': frozen(), 'package_bytes_equal_to_wheel_and_source': True,
            'actual_new_frames': sum(o['frames'] for o in outputs),
            'actual_new_stereo_sample_frames': sum(o['stereo_sample_frames'] for o in outputs),
            'negative': negative, 'release_zip_sha256': sha(public/'agent-video-kit-cp313-win_amd64.zip'),
            'manifest_sha256': sha(public/'release-manifest.json'), 'generator_sha256': sha(Path(__file__)),
            'virtual_environment': False, 'network_used': False, 'other_machine_accepted': False,
            'continuous_playback': False, 'human_listening': False, 'full_capcut_parity': False}
        save(evidence/'verification.json', record)
        print(json.dumps({k: record[k] for k in ('status', 'isolated_cli_calls', 'installed_package_files',
            'actual_new_frames', 'actual_new_stereo_sample_frames')}))
    except BaseException as exc:
        save(evidence/'failure.json', {'error': repr(exc), 'calls': calls, 'outputs': outputs, 'source_freeze': before}); raise


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    for key in ('bundle', 'work', 'public', 'evidence'): p.add_argument('--'+key, type=Path, required=True)
    a = p.parse_args(); run(a.bundle.resolve(), a.work.resolve(), a.public.resolve(), a.evidence.resolve())
