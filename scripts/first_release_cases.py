"""Reproduce the first release against a fresh native offline installation.

No network, virtual environments, models, or external media. Existing runs are
preserved. The generated fictional-product artwork and audio are CC0.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import time
import wave
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
TAG = 'v0.1.0-alpha.1'


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
    return 'sha256:' + h.hexdigest()


def write(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf8')


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--installed', type=Path, required=True)
    ap.add_argument('--output', type=Path, required=True, help='new owned run directory')
    ap.add_argument('--evidence', type=Path, required=True, help='new public evidence directory')
    ap.add_argument('--assets', type=Path, required=True, help='new public media directory')
    a = ap.parse_args()
    for p in (a.output, a.evidence, a.assets):
        if p.exists():
            raise SystemExit('Existing run preserved: ' + str(p))
        p.mkdir(parents=True)
    env = dict(os.environ)
    tmp = a.output / 'temp'
    tmp.mkdir()
    env.update(TMP=str(tmp), TEMP=str(tmp), TMPDIR=str(tmp),
               AI_AD_EDITOR_RUNTIME_DIR=str(a.output / 'runtime'),
               HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1', HF_HUB_DISABLE_TELEMETRY='1')
    prefix = [sys.executable, '-I', '-S', '-B', '-X', 'utf8', str(a.installed / 'run.py')]
    rows = []

    def cli(label, args, expected=0):
        command = prefix + list(map(str, args))
        start = time.monotonic()
        p = subprocess.run(command, cwd=ROOT, env=env, capture_output=True, timeout=300,
                           creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        (a.evidence / (label + '.stdout.json')).write_bytes(p.stdout)
        (a.evidence / (label + '.stderr.txt')).write_bytes(p.stderr)
        response = json.loads(p.stdout)
        row = {'id': label, 'argv': command, 'exit_code': p.returncode,
               'expected_exit_code': expected, 'seconds': round(time.monotonic() - start, 3),
               'stdout': label + '.stdout.json', 'stderr': label + '.stderr.txt',
               'stdout_sha256': sha(a.evidence / (label + '.stdout.json'))}
        rows.append(row)
        write(a.evidence / 'commands.json', rows)
        if p.returncode != expected:
            raise RuntimeError(label + ': ' + json.dumps(response, ensure_ascii=False))
        return response

    def native(label, args):
        p = subprocess.run(list(map(str, args)), cwd=ROOT, env=env, capture_output=True, timeout=300,
                           creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        (a.evidence / (label + '.log')).write_bytes(p.stdout + p.stderr)
        if p.returncode:
            raise RuntimeError(label + ': ' + p.stderr.decode('utf8', 'replace')[-3000:])
        return p.stdout

    try:
        for name, args in [('version', ['version']), ('doctor', ['doctor']),
                           ('capabilities', ['capabilities']), ('schema', ['schema', 'show']),
                           ('effects', ['effects', 'list'])]:
            cli(name, args)
        # Only the generator uses host Pillow. Every product command below is -I -S.
        from PIL import Image, ImageDraw, ImageFont
        font = Path(os.environ.get('WINDIR', 'C:/Windows')) / 'Fonts/segoeui.ttf'
        bold = font.with_name('segoeuib.ttf')
        if not font.is_file() or not bold.is_file():
            raise RuntimeError('Explicit existing Segoe UI fonts required for artwork generation')
        src = a.assets / 'input'
        src.mkdir()
        for i, (bg, accent, title, subtitle) in enumerate([
            ('#152943', '#b3d6ff', 'Less noise.', 'A small light. A clear desk.'),
            ('#dfe8f2', '#2363a0', 'More focus.', 'FIELD  /  DESK LIGHT'),
            ('#1f4247', '#9ce0cd', 'Make room.', 'FIELD  /  STUDIO EDITION'),
        ]):
            im = Image.new('RGB', (360, 640), bg)
            d = ImageDraw.Draw(im)
            d.text((28, 28), 'FIELD  /  LOCAL STUDY', fill=accent, font=ImageFont.truetype(font, 14))
            d.ellipse((24, 222, 336, 535), fill=accent)
            d.line((190, 478, 232, 323, 150, 273), fill='#f7f8fa', width=17)
            d.rounded_rectangle((113, 256, 194, 282), radius=12, fill='#f7f8fa')
            d.ellipse((151, 470, 229, 486), fill='#f7f8fa')
            d.text((28, 112), title, fill=accent, font=ImageFont.truetype(bold, 40))
            d.text((28, 166), subtitle, fill=accent, font=ImageFont.truetype(font, 14))
            d.text((28, 571), 'OPEN A BRIGHTER WORKDAY', fill=accent, font=ImageFont.truetype(bold, 16))
            d.text((28, 606), 'Fictional product / generated test artwork', fill=accent, font=ImageFont.truetype(font, 11))
            im.save(src / ('card-' + str(i + 1) + '.png'))
        # Quiet synthetic pulse, explicitly not claimed as music or reviewed audio.
        with wave.open(str(src / 'pulse.wav'), 'wb') as w:
            w.setparams((2, 2, 48000, 0, 'NONE', 'not compressed'))
            pcm = bytearray()
            for n in range(6 * 48000):
                t = n / 48000
                gain = max(0, 1 - (t % .5) / .14) * .06
                v = int(32767 * gain * math.sin(2 * math.pi * 440 * t))
                pcm.extend(struct.pack('<hh', v, v))
            w.writeframes(pcm)
        license_text = ('CC0 1.0 Universal\nThe fictional FIELD artwork, synthetic audio, template and edit JSON '
                        'created by scripts/first_release_cases.py are dedicated to the public domain.\n'
                        'No real product, model inference, downloaded media or font binary is included.\n'
                        'Text is rasterized with existing local Windows Segoe UI.\n')
        (a.assets / 'LICENSE.txt').write_text(license_text, encoding='utf8')
        project = a.output / 'project'
        cli('project-init', ['project', 'init', project, '--name', 'FIELD / first release'])
        ids = []
        for i, source in enumerate(sorted(src.glob('*'))):
            out = cli('ingest-' + str(i + 1), ['media', 'ingest', '--project', project, '--input', source,
                '--source-url', 'local://first-release-generated/' + source.name,
                '--license-spdx', 'CC0-1.0', '--license-url', a.assets / 'LICENSE.txt',
                '--evidence', a.assets / 'LICENSE.txt', '--creator', 'Agent Video Kit contributors',
                '--verification-status', 'verified', '--permitted-use', 'commercial_ad'])
            ids.append(out['data']['asset']['id'])
        cli('media-understand', ['media', 'understand', '--project', project, '--asset-id', ids[-1]])
        operations = [
            {'op': 'append_clip', 'track_id': 'track_video_1', 'asset_id': ids[0], 'source_in_tick': 0,
             'source_out_tick': 270000, 'duration_tick': 270000},
            {'op': 'append_clip', 'track_id': 'track_video_1', 'asset_id': ids[1], 'source_in_tick': 0,
             'source_out_tick': 270000, 'duration_tick': 270000},
            {'op': 'append_clip', 'track_id': 'track_audio_1', 'asset_id': ids[-1], 'source_in_tick': 0,
             'source_out_tick': 540000, 'duration_tick': 540000},
        ]
        changes = a.output / 'changes.json'
        write(changes, {'sequence_id': 'seq_main', 'operations': operations})
        shutil.copyfile(changes, a.evidence / 'changes.json')
        cli('timeline-compose', ['timeline', 'compose', '--project', project, '--input', changes])
        cli('validate', ['validate', '--project', project])
        cli('rights-check', ['rights', 'check', '--project', project])
        cli('policy-audit', ['policy', 'audit', '--project', project])
        cli('render-plan', ['render', '--project', project, '--output', project / 'renders/field.mp4',
                            '--width', 360, '--height', 640, '--dry-run'])
        cli('render', ['render', '--project', project, '--output', project / 'renders/field.mp4',
                       '--width', 360, '--height', 640, '--publish'])
        cli('quality', ['quality', 'check', '--project', project, '--input', project / 'renders/field.mp4',
                       '--require-audio', '--width', 360, '--height', 640, '--expensive'])
        cli('scopes', ['quality', 'scopes', '--project', project, '--input', project / 'renders/field.mp4',
                      '--at-seconds', 3.5])
        cli('export-package', ['convert', 'export', '--project', project, '--target-format', 'package',
                               '--output', a.output / 'field.avk.zip'])
        cli('import-package', ['convert', 'import', '--input', a.output / 'field.avk.zip',
                               '--output', a.output / 'restored'])
        cli('restored-validate', ['validate', '--project', a.output / 'restored'])
        # A real refusal: remote references must not be converted into an apparent success.
        cli('remote-refused', ['media', 'ingest', '--project', project, '--input', src / 'card-1.png',
                               '--source-url', 'https://example.invalid/asset.png'], expected=2)
        # Parameterized, actually rendered template, in a separate authored project.
        template_project = a.output / 'template-project'
        cli('template-project-init', ['project', 'init', template_project, '--name', 'FIELD / template'])
        out = cli('template-ingest', ['media', 'ingest', '--project', template_project, '--input', src / 'card-3.png',
            '--source-url', 'local://first-release-generated/card-3.png', '--license-spdx', 'CC0-1.0',
            '--license-url', a.assets / 'LICENSE.txt', '--evidence', a.assets / 'LICENSE.txt',
            '--verification-status', 'verified', '--permitted-use', 'commercial_ad'])
        template = a.output / 'template.json'
        variables = a.output / 'variables.json'
        shutil.copyfile(ROOT / 'product/examples/p0-basic/template.json', template)
        write(variables, {'asset_id': out['data']['asset']['id'], 'duration_tick': 270000})
        cli('template-apply', ['template', 'apply', '--project', template_project, '--input', template,
                               '--variables', variables])
        cli('template-render', ['render', '--project', template_project, '--output', template_project / 'renders/variant.mp4',
                                '--width', 360, '--height', 640, '--publish'])
        cli('template-quality', ['quality', 'check', '--project', template_project,
                                 '--input', template_project / 'renders/variant.mp4', '--width', 360, '--height', 640])
        shutil.copyfile(template, a.evidence / 'template.json')
        shutil.copyfile(variables, a.evidence / 'variables.json')
        shutil.copyfile(project / 'project.json', a.evidence / 'author-project.json')
        shutil.copyfile(project / 'rights-ledger.json', a.evidence / 'rights-ledger.json')
        shutil.copyfile(project / 'renders/field.mp4', a.assets / 'field.mp4')
        shutil.copyfile(template_project / 'renders/variant.mp4', a.assets / 'variant.mp4')
        for name in ('field', 'variant'):
            native(name + '-gif', ['ffmpeg', '-v', 'error', '-i', a.assets / (name + '.mp4'),
                '-filter_complex', 'fps=8,scale=240:-1:flags=lanczos,split[a][b];[a]palettegen[p];[b][p]paletteuse',
                '-loop', '0', a.assets / (name + '.gif')])
        for second in (1, 4):
            native('output-frame-' + str(second), ['ffmpeg', '-v', 'error', '-ss', str(second),
                '-i', a.assets / 'field.mp4', '-frames:v', '1', a.assets / ('output-frame-' + str(second) + '.png')])
        native('input-preview', ['ffmpeg', '-v', 'error', '-loop', '1', '-i', src / 'card-1.png',
            '-t', '3', '-r', '25', '-c:v', 'libx264', '-pix_fmt', 'yuv420p', a.assets / 'input.mp4'])
        probes = {}
        for f in sorted(a.assets.glob('*.mp4')):
            probe = json.loads(native(f.stem + '-probe', ['ffprobe', '-v', 'error', '-show_format',
                              '-show_streams', '-count_frames', '-of', 'json', f]))
            native(f.stem + '-decode', ['ffmpeg', '-v', 'error', '-i', f, '-f', 'null', '-'])
            probes[f.name] = probe
        write(a.evidence / 'media-probes.json', probes)
        ffmpeg_version = native('ffmpeg-version', ['ffmpeg', '-version']).decode('utf8', 'replace')
        result = {'status': 'passed', 'release': TAG, 'date_utc': datetime.now(timezone.utc).isoformat(),
                  'python': sys.version, 'native_windows': sys.platform == 'win32', 'virtualization': False,
                  'runtime_network': False, 'isolated_product_commands': len(rows),
                  'successes': sum(r['exit_code'] == 0 for r in rows),
                  'expected_refusals': sum(r['expected_exit_code'] != 0 for r in rows),
                  'recording': 'documentation replay of actual CLI logs; not a live terminal recording',
                  'ffmpeg': ffmpeg_version.splitlines()[0],
                  'visual_review': 'pending', 'continuous_playback_review': False, 'listening_review': False,
                  'new_model_inferences': 0,
                  'files': [{'path': f.relative_to(a.assets).as_posix(), 'bytes': f.stat().st_size,
                             'sha256': sha(f)} for f in sorted(a.assets.rglob('*')) if f.is_file()]}
        write(a.evidence / 'verification.json', result)
        print(json.dumps({k: v for k, v in result.items() if k != 'files'}, ensure_ascii=False))
    except BaseException as e:
        write(a.evidence / 'failure.json', {'status': 'failed-preserved', 'error': str(e), 'commands': len(rows)})
        raise


if __name__ == '__main__':
    main()
